# backend

The only public service (ADR 0002). It stores uploaded documents, parses them in background jobs through the parser service, keeps the results in Postgres, and serves them over HTTP together with the web app (ADR 0007).

## API

Defined spec-first in [`api/openapi.yaml`](api/openapi.yaml); `oapi-codegen` generates the Echo v5 handlers and types into `internal/api/openapi.gen.go`, and `internal/api/server.go` implements them.

| Method | Path | |
|---|---|---|
| `POST` | `/api/documents` | Multipart field `file`: an `.eml` or PDF. `201` when new, `200` when the same bytes were uploaded before |
| `GET` | `/api/documents` | Newest first, `?limit=` up to 500 |
| `GET` | `/api/documents/{id}` | Status, parser, warnings, error |
| `GET` | `/api/documents/{id}/content` | The original file. Only PDFs open in the browser; anything else downloads, with `nosniff`. The stored content type comes from the bytes (`%PDF`) or the `.eml` extension, never from what the browser declared, because the file is served from the web app's origin |
| `POST` | `/api/documents/{id}/reparse` | Parse the stored original again. The document's statement is replaced, so it gets a new id |
| `GET` | `/api/statements` | Newest closing date first, with each statement's transaction count |
| `GET` | `/api/statements/{id}` | One statement |
| `GET` | `/api/statements/{id}/transactions` | In statement order |
| `GET` | `/api/transactions` | Across all statements. Filters: `from`, `to` (transaction date), `closingFrom`, `closingTo` (the statement's closing date), `kind` (repeatable), `institution`, `card`, `overseas`, `q`; `sort` (`newest`, `oldest`, `largest`, `smallest`); `limit` 0–500 and `offset`. Returns the page plus `total` and `sum` for the whole match, and `byKind` / `byCard` facets that each ignore their own filter. While purchases are included, fees and refunds linked to a purchase fold into it as its `children` and amounts are net of them ([ADR 0009](../../docs/adr/0009-transaction-parents.md)) |
| `GET` | `/api/transactions/{id}` | One transaction with its parent and children, whichever statements they are on |
| `GET` | `/healthz` | `200` when the database answers |
| `GET` | anything else | The web app: a file from the embedded build, or its `200.html` shell for client-side routes. Unknown `/api/` paths stay `404` |

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
| `BACKEND_ACCESS_TEAM_DOMAIN` | — | Cloudflare Access team domain, `https://<team>.cloudflareaccess.com`. With `BACKEND_ACCESS_AUD`, every request but `/healthz` needs a valid Access token (ADR 0008). Leave both empty locally |
| `BACKEND_ACCESS_AUD` | — | The Finchie Access application's AUD tag (not a secret) |

`task backend:run` reads `../../.local/backend.env`.

## Development

```sh
task backend:generate   # after editing api/openapi.yaml or SQL; commit the output
task backend:lint
task backend:test       # integration tests start Postgres 18 with testcontainers
task backend:run
```

Integration tests need a Docker daemon and are skipped without one. Testcontainers uses `DOCKER_HOST` or the current Docker context; with Colima, `docker context use colima` (or `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock`).

Generated code (`internal/gen/`, `internal/db/dbq/`, `internal/api/openapi.gen.go`) is committed; don't edit it. After changing `api/openapi.yaml`, also run `task web:generate` for the web app's types.

The web app is embedded from `internal/web/dist/` (gitignored apart from `.gitkeep`). `task backend:web` builds `web/` and copies it there; without it, the binary still serves the API and answers app routes with a hint to build the UI.

## Image

`Dockerfile`: builds `web/` in a Node stage, embeds it, then a static binary on distroless, uid 1654. The build context is the repository root (`docker build -f services/backend/Dockerfile .`, or `task backend:image`); `Dockerfile.dockerignore` limits it to `web/` and `services/backend/`. The container healthcheck runs `/backend healthcheck`.
