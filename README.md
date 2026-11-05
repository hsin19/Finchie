# Finchie

Finchie = Finance + Finch

A self-hosted personal finance platform. It turns bank and credit card statements into a ledger and, later, tracks investments, so you can see where your money goes and where you stand.

> **V2 is under construction on `main`.** V1 (a Python batch job plus a Go API on MongoDB) is frozen at tag [`v1.0.0`](https://github.com/hsin19/Finchie/tree/v1.0.0) and no longer on `main`.

## Components

**Services** (deployed)

| Path | What it is | Status |
|---|---|---|
| [`services/backend`](services/backend/) | Go. The only public service: API, document ingestion, background jobs, and (later) the web app's static files. Owns the database. | ✅ Upload, parse, and read statements |
| [`services/parser`](services/parser/) | Python. Stateless parser behind gRPC: a raw statement goes in, structured data comes out. Internal only. | ✅ 4 banks |

**Shared**

| Path | What it is | Status |
|---|---|---|
| [`proto/`](proto/) | gRPC contracts, managed with buf. Generated code is committed inside each service. | ✅ |
| `web/` | TypeScript web app | Planned |

Design decisions and their reasons are in [`docs/adr/`](docs/adr/): 0001 rewrite as V2, 0002 architecture, 0003 tech stack, 0004 money and dates, 0005 ingestion pipeline, 0006 test data.

## Why V2

V1 stalled on Gmail OAuth (7-day refresh tokens unless the app passes Google's verification), its parser returned wrong data without noticing, money was `float64`, and the deployment plan (Azure + GitHub Pages) no longer matched where things run. The scope also grew: Finchie now absorbs InTheGreenYet, an investment tracker on Notion that was too slow. Details in [ADR 0001](docs/adr/0001-rewrite-as-v2.md).

## Architecture

```
browser ── Cloudflare Access ── Tunnel ──▶ backend (Go) ── gRPC ──▶ parser (Python)
                                             │
                                             └── Postgres
```

- The backend stores every uploaded document as-is, then a background job asks the parser to read it. Parsed results can always be rebuilt from the stored originals.
- Every parsed statement is reconciled: the transactions must add up to the amount printed on the statement. Statements that don't are kept but flagged for review instead of being trusted.
- The parser never touches the database. Retries, back-off, and concurrency limits live in the backend's job queue.

## Supported statements

| Institution | Source | Notes |
|---|---|---|
| E.SUN Bank | PDF attached to the e-statement e-mail | |
| Taishin Bank | Password-protected PDF | One bill can list several Richart cards |
| Cathay United Bank | Password-protected PDF | |
| HSBC Taiwan | Password-protected PDF | Transaction descriptions are images, read with OCR |

Upload the e-mail (`.eml`) or the PDF itself.

## Getting started

Prerequisites: Go 1.27+, [uv](https://docs.astral.sh/uv/), [Task](https://taskfile.dev/), Docker (for Postgres).

```sh
task --list              # everything you can run
task check               # what CI runs: proto checks, lint, and tests for both services
docker compose up -d     # local Postgres
task parser:run          # gRPC on :50051
task backend:run         # HTTP on :8080
curl -F file=@statement.eml localhost:8080/api/documents
```

Local configuration and secrets go in `.local/` (gitignored):

| File | Contents |
|---|---|
| `.local/backend.env` | `BACKEND_DATABASE_URL=postgres://finchie:finchie@localhost:5432/finchie?sslmode=disable` |
| `.local/parser.env` | `PARSER_PDF_PASSWORDS__<INSTITUTION>=…` for each bank whose PDFs are encrypted |
| `.local/statements/` | Real statements for `task parser:test-real` |

`docker compose --profile app up --build` runs Postgres, the parser, and the backend as containers (needs BuildKit, i.e. `docker buildx`). See each service's README for every variable it reads.

## CI and releases

GitHub Actions in [`.github/workflows/`](.github/workflows/README.md): `check.yml` runs on PRs, pushes to `main`, and releases. Pushing a `v*` tag (`git tag v2.0.0 && git push origin v2.0.0`) builds both images for `linux/amd64` and `linux/arm64`, smoke-checks each, and publishes `ghcr.io/hsin19/finchie-backend` and `ghcr.io/hsin19/finchie-parser` tagged `2.0.0`, `2.0`, and `sha-<short sha>`.

## Deployment

The homelab's Docker Compose runs the released images behind Cloudflare Tunnel and Access (not set up yet). Only the backend is reachable from outside; the parser stays on the internal network. Pin a version tag, never `latest`.
