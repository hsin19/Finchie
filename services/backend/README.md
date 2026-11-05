# backend

The only public service (ADR 0002). It stores uploaded documents, parses them in background jobs through the parser service, keeps the results in Postgres, and serves them over HTTP.

## API

Defined spec-first in [`api/openapi.yaml`](api/openapi.yaml); `oapi-codegen` generates the Echo v5 handlers and types into `internal/api/openapi.gen.go`, and `internal/api/server.go` implements them.

| Method | Path | |
|---|---|---|
| `POST` | `/api/documents` | Multipart field `file`: an `.eml` or PDF. `201` when new, `200` when the same bytes were uploaded before |
| `GET` | `/api/documents` | Newest first, `?limit=` up to 500 |
| `GET` | `/api/documents/{id}` | Status, parser, warnings, error |
| `POST` | `/api/documents/{id}/reparse` | Parse the stored original again |
| `GET` | `/api/statements` | Newest closing date first |
| `GET` | `/api/statements/{id}/transactions` | In statement order |
| `GET` | `/healthz` | `200` when the database answers |

Amounts are decimal strings; statement dates are `YYYY-MM-DD` (ADR 0004).

## Ingestion

1. Upload: the document is stored with its SHA-256 and a `parse_document` River job is inserted **in the same transaction**, so every stored document has a job.
2. The job calls the parser over gRPC (`BACKEND_PARSE_TIMEOUT`) and, in one transaction, replaces whatever the document produced before.
3. The document ends up as:

| Status | Meaning |
|---|---|
| `pending` | Queued, being parsed, or waiting to retry |
| `parsed` | Stored; transactions add up to the statement |
| `needs_review` | Stored, but the transactions do not add up |
| `duplicate` | Another document already holds this statement (same institution and closing date) |
| `failed` | The parser rejected it (`error` says why), or it stayed unreachable for every attempt |

Only `UNAVAILABLE`, `DEADLINE_EXCEEDED`, and `RESOURCE_EXHAUSTED` are retried (6 attempts with River's back-off); everything else fails at once (ADR 0005).

## Database

- Schema: goose migrations in `internal/db/migrations/`, embedded and applied at startup together with River's own migrations. Add a new file for every change; never edit an applied one.
- Queries: plain SQL in `internal/db/queries/`, compiled by sqlc into `internal/db/dbq/`.

## Configuration

| Variable | Default | |
|---|---|---|
| `BACKEND_DATABASE_URL` | — | Required. Postgres connection string |
| `BACKEND_HTTP_ADDR` | `:8080` | |
| `BACKEND_PARSER_ADDR` | `localhost:50051` | Parser gRPC address (plaintext, internal network only) |
| `BACKEND_PARSE_TIMEOUT` | `120s` | Deadline for one parse |
| `BACKEND_PARSE_CONCURRENCY` | `2` | Documents parsed at once; keep at or below the parser's workers |
| `BACKEND_MAX_UPLOAD_MB` | `32` | |
| `BACKEND_LOG_FORMAT` | `json` | `json` or `text` |

`task backend:run` reads `../../.local/backend.env`.

## Development

```sh
task backend:generate   # after editing api/openapi.yaml or SQL; commit the output
task backend:lint
task backend:test       # integration tests start Postgres 18 with testcontainers
task backend:run
```

Integration tests need a Docker daemon and are skipped without one. Testcontainers uses `DOCKER_HOST` or the current Docker context; with Colima, `docker context use colima` (or `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock`).

Generated code (`internal/gen/`, `internal/db/dbq/`, `internal/api/openapi.gen.go`) is committed; don't edit it.

## Image

`Dockerfile`: static binary on distroless, uid 1654. The container healthcheck runs `/backend healthcheck`.
