package statements

import (
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

type StatementType int

const (
	CreditCardBill StatementType = 1
)

type SourceType int

const (
	CreditCard SourceType = 1
)

type Statement struct {
	ID             string         `bson:"_id" json:"-"`
	Type           StatementType  `bson:"type" json:"type"`
	SourceType     SourceType     `bson:"source_type" json:"source_type"`
	SourceName     string         `bson:"source_name" json:"source_name"`
	SourceID       *string        `bson:"source_id,omitempty" json:"source_id,omitempty"`
	TotalAmount    float64        `bson:"total_amount" json:"total_amount"`
	PreviousAmount *float64       `bson:"previous_amount,omitempty" json:"previous_amount,omitempty"`
	PreviousPaid   *float64       `bson:"previous_paid,omitempty" json:"previous_paid,omitempty"`
	PreviousUnpaid *float64       `bson:"previous_unpaid,omitempty" json:"previous_unpaid,omitempty"`
	CurrentAmount  *float64       `bson:"current_amount,omitempty" json:"current_amount,omitempty"`
	Currency       string         `bson:"currency" json:"currency"`
	PaymentDueDate *time.Time     `bson:"payment_due_date,omitempty" json:"payment_due_date,omitempty"`
	Transactions   *[]Transaction `bson:"transactions,omitempty" json:"transactions,omitempty"`
	Extra          any            `bson:"extra,omitempty" json:"extra,omitempty"`
}

func (b *Statement) Normalize() error {
	if b.SourceName == "" || b.TotalAmount <= 0 || b.Currency == "" {
		return errors.New("invalid statement: missing required fields")
	}

	b.GenerateID()

	if b.Transactions == nil {
		b.Transactions = &[]Transaction{}
	}

	for i, detail := range *b.Transactions {
		detail.StatementID = b.ID

		err := detail.Normalize()
		if err != nil {
			return fmt.Errorf("invalid transaction at index %d: %w", i, err)
		}
		(*b.Transactions)[i] = detail
	}

	if len(*b.Transactions) == 0 && b.TotalAmount > 0 {
		b.Transactions = &[]Transaction{
			{
				ID:          b.ID,
				Description: "Total Amount",
				Amount:      b.TotalAmount,
				Date:        b.PaymentDueDate.UTC(),
				StatementID: b.ID,
			},
		}
	}

	return nil
}

func (b *Statement) GenerateID() {
	if b.ID == "" {
		switch {
		case b.SourceID != nil:
			b.ID = fmt.Sprintf("%s_%s", b.SourceName, *b.SourceID)

		case b.PaymentDueDate != nil:
			b.ID = fmt.Sprintf("%s_%s", b.SourceName, b.PaymentDueDate.UTC().Format(time.RFC3339))

		default:
			b.ID = fmt.Sprintf("%s_%s", b.SourceName, uuid.NewString())
		}
	}
}

type Transaction struct {
	ID            string         `bson:"_id" json:"id"`
	Description   string         `bson:"description" json:"description"`
	Amount        float64        `bson:"amount" json:"amount"`
	Date          time.Time      `bson:"date" json:"date"`
	StatementID   string         `bson:"statement_id,omitempty" json:"-"`
	PaymentSource *PaymentSource `bson:"payment_source,omitempty" json:"-"`
	Extra         any            `bson:"extra,omitempty" json:"extra,omitempty"`
}

func (bd *Transaction) Normalize() error {
	if bd.PaymentSource != nil {
		bd.PaymentSource = nil
	}
	return nil
}

type PaymentSource struct {
	Type          string `bson:"type" json:"type"`
	TransactionID string `bson:"transaction_id" json:"transaction_id"`
	StatementID   string `bson:"statement_id" json:"statement_id"`
}
