package api

import (
	"encoding/hex"

	"github.com/jackc/pgx/v5/pgtype"
	openapi_types "github.com/oapi-codegen/runtime/types"

	"github.com/hsin19/Finchie/services/backend/internal/db/dbq"
)

func toDocument(row dbq.GetDocumentRow) Document {
	doc := Document{
		Id:            row.ID,
		Filename:      row.Filename,
		ContentType:   row.ContentType,
		SizeBytes:     int(row.SizeBytes),
		Sha256:        hex.EncodeToString(row.Sha256),
		ReceivedAt:    row.ReceivedAt.Time,
		Status:        DocumentStatus(row.Status),
		Error:         row.Error,
		Parser:        row.Parser,
		ParserVersion: row.ParserVersion,
		Warnings:      row.Warnings,
	}
	if doc.Warnings == nil {
		doc.Warnings = []string{}
	}
	if row.ParsedAt.Valid {
		doc.ParsedAt = &row.ParsedAt.Time
	}
	return doc
}

func toStatement(row dbq.Statement) Statement {
	return Statement{
		Id:          row.ID,
		DocumentId:  row.DocumentID,
		Institution: row.Institution,
		ClosingDate: openapi_types.Date{Time: row.ClosingDate.Time},
		DueDate:     openapi_types.Date{Time: row.DueDate.Time},
		Currency:    row.Currency,
		TotalDue:    decimalString(row.TotalDue),
		Reconciliation: Reconciliation{
			Balanced:    row.Balanced,
			Computed:    decimalString(row.ComputedNewCharges),
			Stated:      decimalString(row.StatedNewCharges),
			StatedLabel: row.StatedLabel,
		},
	}
}

func toTransaction(row dbq.ListTransactionsRow) Transaction {
	tx := Transaction{
		Id:               row.ID,
		TransactionDate:  openapi_types.Date{Time: row.TransactionDate.Time},
		Description:      row.Description,
		Kind:             TransactionKind(row.Kind),
		Amount:           decimalString(row.Amount),
		OriginalCurrency: row.OriginalCurrency,
		Country:          row.Country,
		CardLast4:        row.CardLast4,
	}
	if row.PostingDate.Valid {
		tx.PostingDate = &openapi_types.Date{Time: row.PostingDate.Time}
	}
	if row.OriginalAmount.Valid {
		original := decimalString(row.OriginalAmount)
		tx.OriginalAmount = &original
	}
	return tx
}

// decimalString renders NUMERIC exactly as Postgres stores it ("780.00", "-6553").
func decimalString(n pgtype.Numeric) string {
	value, err := n.Value()
	if err != nil || value == nil {
		return ""
	}
	s, _ := value.(string)
	return s
}
