-- Search filters: a NULL argument means "no filter". SearchTransactions and TransactionTotals must
-- apply the same ones.

-- name: SearchTransactions :many
SELECT t.id, t.statement_id, s.institution, t.transaction_date, t.posting_date, t.description, t.kind, t.amount,
       t.original_amount, t.original_currency, t.country, t.card_last4
FROM transactions t
JOIN statements s ON s.id = t.statement_id
WHERE (sqlc.narg(from_date)::date IS NULL OR t.transaction_date >= sqlc.narg(from_date)::date)
  AND (sqlc.narg(to_date)::date IS NULL OR t.transaction_date <= sqlc.narg(to_date)::date)
  AND (sqlc.narg(closing_from)::date IS NULL OR s.closing_date >= sqlc.narg(closing_from)::date)
  AND (sqlc.narg(closing_to)::date IS NULL OR s.closing_date <= sqlc.narg(closing_to)::date)
  AND (sqlc.narg(kinds)::text[] IS NULL OR t.kind = ANY (sqlc.narg(kinds)::text[]))
  AND (sqlc.narg(institution)::text IS NULL OR s.institution = sqlc.narg(institution)::text)
  AND (sqlc.narg(card_last4)::text IS NULL OR t.card_last4 = sqlc.narg(card_last4)::text)
  AND (NOT @overseas::boolean OR t.original_currency IS NOT NULL OR t.country <> 'TW')
  AND (sqlc.narg(query)::text IS NULL OR strpos(lower(t.description), lower(sqlc.narg(query)::text)) > 0)
ORDER BY t.transaction_date DESC, t.statement_id DESC, t.line_no
LIMIT @row_limit OFFSET @row_offset;

-- name: TransactionTotals :many
-- One row per (kind, card) with flags for whether that group passes the kind and card filters, so
-- the caller can build the full total and both facets from a single scan.
SELECT t.kind,
       s.institution,
       t.card_last4,
       (sqlc.narg(kinds)::text[] IS NULL OR t.kind = ANY (sqlc.narg(kinds)::text[]))::boolean AS kind_match,
       ((sqlc.narg(institution)::text IS NULL OR s.institution = sqlc.narg(institution)::text)
           -- IS NOT DISTINCT FROM: rows without a card (payments) must give false, not NULL.
           AND (sqlc.narg(card_last4)::text IS NULL OR t.card_last4 IS NOT DISTINCT FROM sqlc.narg(card_last4)::text))::boolean AS card_match,
       count(*)::integer AS row_count,
       sum(t.amount)::numeric AS amount
FROM transactions t
JOIN statements s ON s.id = t.statement_id
WHERE (sqlc.narg(from_date)::date IS NULL OR t.transaction_date >= sqlc.narg(from_date)::date)
  AND (sqlc.narg(to_date)::date IS NULL OR t.transaction_date <= sqlc.narg(to_date)::date)
  AND (sqlc.narg(closing_from)::date IS NULL OR s.closing_date >= sqlc.narg(closing_from)::date)
  AND (sqlc.narg(closing_to)::date IS NULL OR s.closing_date <= sqlc.narg(closing_to)::date)
  AND (NOT @overseas::boolean OR t.original_currency IS NOT NULL OR t.country <> 'TW')
  AND (sqlc.narg(query)::text IS NULL OR strpos(lower(t.description), lower(sqlc.narg(query)::text)) > 0)
GROUP BY t.kind, s.institution, t.card_last4
ORDER BY t.kind, s.institution, t.card_last4;
