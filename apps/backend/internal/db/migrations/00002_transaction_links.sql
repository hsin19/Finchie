-- +goose Up

-- A line that adjusts another points at it: a foreign transaction fee, a refund, or a points
-- redemption at the purchase it belongs to. One level only (a parent has no parent). Derived from the
-- lines, like them: worked out again whenever a statement is stored (ADR 0009).
ALTER TABLE transactions ADD COLUMN parent_id BIGINT REFERENCES transactions (id) ON DELETE SET NULL;

CREATE INDEX transactions_parent_id_idx ON transactions (parent_id) WHERE parent_id IS NOT NULL;

-- +goose Down
ALTER TABLE transactions DROP COLUMN parent_id;
