# parser

Stateless gRPC service that turns a raw statement (an e-mail or a PDF) into structured data: statement fields, transactions, and a reconciliation of the transactions against the printed total. It also opens a document for reading (`OpenDocument`, `reading.py`): an e-mail's headers, body, and attachments with the PDFs decrypted, so the web app can show them without the password (ADR 0012). It keeps no state and talks to nothing but its caller, the backend (ADR 0002). The contract is [`proto/finchie/parser/v1/parser.proto`](../../proto/finchie/parser/v1/parser.proto).

## How a document is parsed

1. **Extract PDFs** (`documents.py`). An `.eml` yields its PDF attachments; a bare PDF is used as-is.
2. **Pick the attachment and parser** (`pipeline.py`). A known attachment name (`TSB_Creditcard_Estatement_*.pdf`) wins, so payment slips and other PDFs in the same e-mail are ignored. Otherwise each parser checks the first page for its bank's name.
3. **Decrypt** (`pdf.py`). Try no password, then every configured one.
4. **Parse** (`parsers/<bank>.py`). Read the statement fields and every line, classify each line (purchase, foreign transaction fee, annual fee, refund, rebate, payment), and add up the new charges to compare with the amount the statement prints.

| Parser | Notes |
|---|---|
| `esun.credit_card` | Several cards per bill; rebates listed separately |
| `taishin.credit_card` | Several Richart cards per bill; long descriptions wrap onto the lines around the row |
| `cathay.credit_card` | Due date taken from the auto-debit notice, which already accounts for holidays |
| `hsbc.credit_card` | Labels and descriptions are images. Rows come from the text layer, descriptions from OCR of the description column, matched by baseline. The new-charges subtotal and total due are the 4th and 5th unlabelled amounts on the transaction pages |

Adding a bank: subclass `StatementParser`, register it in `parsers/__init__.py`, write a synthetic fixture test, and run `task parser:test-real` against real statements.

## Errors

| Exception | gRPC status | Backend retries? |
|---|---|---|
| `UnsupportedDocumentError` | `UNIMPLEMENTED` | No |
| `InvalidDocumentError` | `INVALID_ARGUMENT` | No |
| `PasswordRequiredError` | `FAILED_PRECONDITION` | No |
| `LayoutError` (bank changed its layout) | `INTERNAL` | No |

An unbalanced statement is not an error: it comes back `OK` with `reconciliation.balanced = false`.

## Configuration

Environment variables, prefix `PARSER_`, nested keys split by `__`. Local runs also read `../../.local/parser.env`.

| Variable | Default | |
|---|---|---|
| `PARSER_PDF_PASSWORDS__<INSTITUTION>` | — | One per bank whose PDFs are encrypted, e.g. `PARSER_PDF_PASSWORDS__TAISHIN` |
| `PARSER_PORT` | `50051` | |
| `PARSER_WORKERS` | `2` | Concurrent parses; the backend also limits concurrency |
| `PARSER_MAX_MESSAGE_MB` | `33` | gRPC message limit. Keep it 1 above the backend's `BACKEND_MAX_UPLOAD_MB`: a request is the whole file plus its other fields |
| `PARSER_OCR` | `true` | Without OCR, HSBC descriptions are empty and a warning is returned |
| `PARSER_LOG_LEVEL` | `INFO` | |

## Development

```sh
task parser:test        # synthetic fixtures
task parser:test-real   # every file in .local/statements must reconcile
task parser:lint
task parser:run         # gRPC on :50051, with health checking and reflection
```

Code under `src/finchie/` is generated from `proto/` (`task proto`); don't edit it.

## Image

`Dockerfile`: Python 3.13 slim, runs as uid 1654, OCR models baked in at build time. The container healthcheck runs `python -m finchie_parser.healthcheck`. Expose the port only on the internal network.
