package ingest

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
	"google.golang.org/genproto/googleapis/type/date"
	"google.golang.org/genproto/googleapis/type/decimal"

	"github.com/hsin19/finchie/services/backend/internal/db/dbq"
	parserv1 "github.com/hsin19/finchie/services/backend/internal/gen/finchie/parser/v1"
)

// Document statuses, as stored in documents.status.
const (
	StatusPending     = "pending"
	StatusParsed      = "parsed"
	StatusNeedsReview = "needs_review"
	StatusDuplicate   = "duplicate"
	StatusFailed      = "failed"
)

// ErrInvalidResponse means the parser returned something that breaks the contract; retrying won't help.
var ErrInvalidResponse = errors.New("invalid parser response")

var kinds = map[parserv1.TransactionKind]string{
	parserv1.TransactionKind_TRANSACTION_KIND_PURCHASE:                "purchase",
	parserv1.TransactionKind_TRANSACTION_KIND_FOREIGN_TRANSACTION_FEE: "foreign_transaction_fee",
	parserv1.TransactionKind_TRANSACTION_KIND_ANNUAL_FEE:              "annual_fee",
	parserv1.TransactionKind_TRANSACTION_KIND_REFUND:                  "refund",
	parserv1.TransactionKind_TRANSACTION_KIND_REBATE:                  "rebate",
	parserv1.TransactionKind_TRANSACTION_KIND_PAYMENT:                 "payment",
}

// Store replaces everything previously derived from the document with the parser's result, in one
// transaction, and returns the document's new status.
func Store(ctx context.Context, pool *pgxpool.Pool, documentID int64, response *parserv1.ParseDocumentResponse) (string, error) {
	statement, transactions, err := convert(documentID, response.GetStatement())
	if err != nil {
		return "", err
	}

	var outcome string
	err = pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
		queries := dbq.New(tx)
		if err := queries.DeleteStatementsForDocument(ctx, documentID); err != nil {
			return err
		}

		finish := dbq.FinishDocumentParams{
			ID:            documentID,
			Parser:        &response.Parser,
			ParserVersion: &response.ParserVersion,
			Warnings:      append([]string{}, response.GetWarnings()...),
		}

		existing, err := queries.FindStatementByKey(ctx, dbq.FindStatementByKeyParams{
			Institution: statement.Institution,
			ClosingDate: statement.ClosingDate,
		})
		switch {
		case err == nil:
			// Another document already holds this statement (an e-mail and its bare PDF).
			reason := fmt.Sprintf("same statement as document %d", existing.DocumentID)
			finish.Status, finish.Error, outcome = StatusDuplicate, &reason, StatusDuplicate
			if err := queries.FinishDocument(ctx, finish); err != nil {
				return err
			}
			// A statement this document had before may have been a parent's.
			_, err := relink(ctx, queries)
			return err
		case !errors.Is(err, pgx.ErrNoRows):
			return err
		}

		statementID, err := queries.InsertStatement(ctx, statement)
		if err != nil {
			return err
		}
		for i := range transactions {
			transactions[i].StatementID = statementID
		}
		if _, err := queries.InsertTransactions(ctx, transactions); err != nil {
			return err
		}
		// Its lines may be parents or children of lines on other statements.
		if _, err := relink(ctx, queries); err != nil {
			return err
		}

		outcome = StatusParsed
		if !statement.Balanced {
			outcome = StatusNeedsReview
		}
		finish.Status = outcome
		return queries.FinishDocument(ctx, finish)
	})
	if err != nil {
		return "", fmt.Errorf("store parse result: %w", err)
	}
	return outcome, nil
}

func convert(documentID int64, s *parserv1.Statement) (dbq.InsertStatementParams, []dbq.InsertTransactionsParams, error) {
	if s == nil || s.GetReconciliation() == nil {
		return dbq.InsertStatementParams{}, nil, fmt.Errorf("%w: missing statement", ErrInvalidResponse)
	}
	var errs []error

	rec := s.GetReconciliation()
	statement := dbq.InsertStatementParams{
		DocumentID:  documentID,
		Institution: s.GetInstitution(),
		Currency:    s.GetCurrency(),
		StatedLabel: rec.GetStatedLabel(),
		Balanced:    rec.GetBalanced(),
	}
	statement.ClosingDate, errs = requiredDate(s.GetClosingDate(), "closing date", errs)
	statement.DueDate, errs = requiredDate(s.GetDueDate(), "due date", errs)
	statement.TotalDue, errs = requiredNumeric(s.GetTotalDue(), "total due", errs)
	statement.ComputedNewCharges, errs = requiredNumeric(rec.GetComputed(), "computed", errs)
	statement.StatedNewCharges, errs = requiredNumeric(rec.GetStated(), "stated", errs)

	transactions := make([]dbq.InsertTransactionsParams, 0, len(s.GetTransactions()))
	for i, t := range s.GetTransactions() {
		kind, ok := kinds[t.GetKind()]
		if !ok {
			errs = append(errs, fmt.Errorf("transaction %d: kind %s", i, t.GetKind()))
		}
		row := dbq.InsertTransactionsParams{
			LineNo:           int32(i),
			Description:      t.GetDescription(),
			Kind:             kind,
			PostingDate:      optionalDate(t.GetPostingDate()),
			OriginalCurrency: optionalString(t.GetOriginalCurrency()),
			Country:          optionalString(t.GetCountry()),
			CardLast4:        optionalString(t.GetCardLast4()),
		}
		row.TransactionDate, errs = requiredDate(t.GetTransactionDate(), fmt.Sprintf("transaction %d date", i), errs)
		row.Amount, errs = requiredNumeric(t.GetAmount(), fmt.Sprintf("transaction %d amount", i), errs)
		original, err := numeric(t.GetOriginalAmount())
		if err != nil {
			errs = append(errs, fmt.Errorf("transaction %d original amount: %w", i, err))
		}
		row.OriginalAmount = original
		transactions = append(transactions, row)
	}

	if len(errs) > 0 {
		return dbq.InsertStatementParams{}, nil, fmt.Errorf("%w: %w", ErrInvalidResponse, errors.Join(errs...))
	}
	return statement, transactions, nil
}

func requiredDate(d *date.Date, field string, errs []error) (pgtype.Date, []error) {
	value := optionalDate(d)
	if !value.Valid {
		errs = append(errs, fmt.Errorf("%s is missing", field))
	}
	return value, errs
}

func optionalDate(d *date.Date) pgtype.Date {
	if d == nil || d.GetYear() == 0 {
		return pgtype.Date{}
	}
	return pgtype.Date{
		Time:  time.Date(int(d.GetYear()), time.Month(d.GetMonth()), int(d.GetDay()), 0, 0, 0, 0, time.UTC),
		Valid: true,
	}
}

func requiredNumeric(d *decimal.Decimal, field string, errs []error) (pgtype.Numeric, []error) {
	value, err := numeric(d)
	if err != nil {
		errs = append(errs, fmt.Errorf("%s: %w", field, err))
	} else if !value.Valid {
		errs = append(errs, fmt.Errorf("%s is missing", field))
	}
	return value, errs
}

func numeric(d *decimal.Decimal) (pgtype.Numeric, error) {
	var value pgtype.Numeric
	if d == nil || d.GetValue() == "" {
		return value, nil
	}
	if err := value.Scan(d.GetValue()); err != nil {
		return pgtype.Numeric{}, fmt.Errorf("decimal %q: %w", d.GetValue(), err)
	}
	return value, nil
}

func optionalString(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
