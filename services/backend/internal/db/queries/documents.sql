-- name: UpsertDocument :one
-- Returns the existing row when the same bytes were uploaded before; `created` tells which.
INSERT INTO documents (sha256, filename, content_type, content)
VALUES (@sha256, @filename, @content_type, @content)
ON CONFLICT (sha256) DO UPDATE SET sha256 = EXCLUDED.sha256
RETURNING id, (xmax = 0)::boolean AS created;

-- name: GetDocument :one
SELECT id, sha256, filename, content_type, octet_length(content)::integer AS size_bytes, received_at,
       status, error, parser, parser_version, warnings, parsed_at
FROM documents
WHERE id = @id;

-- name: ListDocuments :many
SELECT id, sha256, filename, content_type, octet_length(content)::integer AS size_bytes, received_at,
       status, error, parser, parser_version, warnings, parsed_at
FROM documents
ORDER BY received_at DESC, id DESC
LIMIT @row_limit;

-- name: GetDocumentContent :one
SELECT filename, content_type, content
FROM documents
WHERE id = @id;

-- name: MarkDocumentPending :exec
UPDATE documents
SET status = 'pending', error = NULL
WHERE id = @id;

-- name: FinishDocument :exec
UPDATE documents
SET status         = @status,
    error          = sqlc.narg(error),
    parser         = sqlc.narg(parser),
    parser_version = sqlc.narg(parser_version),
    warnings       = @warnings,
    parsed_at      = now()
WHERE id = @id;
