-- name: DeleteStatementsForDocument :exec
DELETE FROM statements
WHERE document_id = @document_id;

-- name: FindStatementByKey :one
SELECT id, document_id
FROM statements
WHERE institution = @institution AND closing_date = @closing_date;

-- name: InsertStatement :one
INSERT INTO statements (document_id, institution, closing_date, due_date, currency, total_due,
                        computed_new_charges, stated_new_charges, stated_label, balanced)
VALUES (@document_id, @institution, @closing_date, @due_date, @currency, @total_due,
        @computed_new_charges, @stated_new_charges, @stated_label, @balanced)
RETURNING id;

-- name: InsertTransactions :copyfrom
INSERT INTO transactions (statement_id, line_no, transaction_date, posting_date, description, kind, amount,
                          original_amount, original_currency, country, card_last4)
VALUES (@statement_id, @line_no, @transaction_date, @posting_date, @description, @kind, @amount,
        @original_amount, @original_currency, @country, @card_last4);

-- name: ListStatements :many
SELECT id, document_id, institution, closing_date, due_date, currency, total_due,
       computed_new_charges, stated_new_charges, stated_label, balanced
FROM statements
ORDER BY closing_date DESC, id DESC
LIMIT @row_limit;

-- name: StatementExists :one
SELECT EXISTS (SELECT 1 FROM statements WHERE id = @id);

-- name: ListTransactions :many
SELECT id, transaction_date, posting_date, description, kind, amount, original_amount, original_currency,
       country, card_last4
FROM transactions
WHERE statement_id = @statement_id
ORDER BY line_no;
