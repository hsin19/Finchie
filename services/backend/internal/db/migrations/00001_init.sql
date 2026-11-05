-- +goose Up

-- Originals are the source of truth: everything below them can be rebuilt by parsing again (ADR 0005).
CREATE TABLE documents (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256         BYTEA       NOT NULL UNIQUE,
    filename       TEXT        NOT NULL,
    content_type   TEXT        NOT NULL,
    content        BYTEA       NOT NULL,
    received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    status         TEXT        NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'parsed', 'needs_review', 'duplicate', 'failed')),
    error          TEXT,
    parser         TEXT,
    parser_version TEXT,
    warnings       TEXT[]      NOT NULL DEFAULT '{}',
    parsed_at      TIMESTAMPTZ
);

CREATE TABLE statements (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id          BIGINT  NOT NULL UNIQUE REFERENCES documents (id) ON DELETE CASCADE,
    institution          TEXT    NOT NULL,
    closing_date         DATE    NOT NULL,
    due_date             DATE    NOT NULL,
    currency             CHAR(3) NOT NULL,
    total_due            NUMERIC NOT NULL,
    computed_new_charges NUMERIC NOT NULL,
    stated_new_charges   NUMERIC NOT NULL,
    stated_label         TEXT    NOT NULL,
    balanced             BOOLEAN NOT NULL,
    -- The same statement uploaded as an e-mail and as a bare PDF hashes differently.
    UNIQUE (institution, closing_date)
);

CREATE TABLE transactions (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    statement_id      BIGINT  NOT NULL REFERENCES statements (id) ON DELETE CASCADE,
    line_no           INTEGER NOT NULL,
    transaction_date  DATE    NOT NULL,
    posting_date      DATE,
    description       TEXT    NOT NULL,
    kind              TEXT    NOT NULL
        CHECK (kind IN ('purchase', 'foreign_transaction_fee', 'annual_fee', 'refund', 'rebate', 'payment')),
    amount            NUMERIC NOT NULL,
    original_amount   NUMERIC,
    original_currency CHAR(3),
    country           CHAR(2),
    card_last4        TEXT,
    UNIQUE (statement_id, line_no)
);

CREATE INDEX transactions_transaction_date_idx ON transactions (transaction_date);

-- +goose Down
DROP TABLE transactions;
DROP TABLE statements;
DROP TABLE documents;
