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
SELECT s.id, s.document_id, s.institution, s.closing_date, s.due_date, s.currency, s.total_due,
       s.computed_new_charges, s.stated_new_charges, s.stated_label, s.balanced,
       (SELECT count(*) FROM transactions t WHERE t.statement_id = s.id)::integer AS transaction_count
FROM statements s
ORDER BY s.closing_date DESC, s.id DESC
LIMIT @row_limit;

-- name: GetStatement :one
SELECT s.id, s.document_id, s.institution, s.closing_date, s.due_date, s.currency, s.total_due,
       s.computed_new_charges, s.stated_new_charges, s.stated_label, s.balanced,
       (SELECT count(*) FROM transactions t WHERE t.statement_id = s.id)::integer AS transaction_count
FROM statements s
WHERE s.id = @id;

-- name: StatementExists :one
SELECT EXISTS (SELECT 1 FROM statements WHERE id = @id);

-- name: ListTransactions :many
SELECT t.id, t.statement_id, s.institution, t.transaction_date, t.posting_date, t.description, t.kind, t.amount,
       t.original_amount, t.original_currency, t.country, t.card_last4
FROM transactions t
JOIN statements s ON s.id = t.statement_id
WHERE t.statement_id = @statement_id
ORDER BY t.line_no;
