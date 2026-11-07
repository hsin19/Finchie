# parser

Stateless gRPC service that turns a raw statement (an e-mail or a PDF) into structured data: statement fields, transactions, and a reconciliation of the transactions against the printed total. It also opens a document for reading (`OpenDocument`, `reading.py`): an e-mail's headers, body, and attachments with the PDFs decrypted, so the web app can show them without the password (ADR 0012). The file it marks primary, the one the app opens, is the PDF parsing would take as the statement (step 2 below), or the first PDF when none is. It keeps no state and talks to nothing but its caller, the backend (ADR 0002). The contract is [`proto/finchie/parser/v1/parser.proto`](../../proto/finchie/parser/v1/parser.proto).

## How a document is parsed

1. **Extract PDFs** (`documents.py`). An `.eml` yields its PDF attachments; a bare PDF is used as-is.
2. **Pick the attachment and parser** (`select_statement` in `pipeline.py`). A PDF is decrypted (`pdf.py`: no password, then every configured one) when it has to be read, at most once. First choice is a PDF whose name a parser knows (`TSB_Creditcard_Estatement_*.pdf`) and whose first page names that parser's bank, so payment slips and other PDFs in the same e-mail are ignored. Next, a known name that no password opens: the document fails for its password rather than parse another attachment that names the bank. Otherwise the first PDF any parser recognizes by its bank's name, skipping PDFs that are locked or unreadable. With nothing recognized, a locked PDF fails the document for its password, else an unreadable one as invalid, else it is unsupported.
3. **Parse** (`parsers/<bank>.py`). Read the statement fields and every line, classify each line (purchase, foreign transaction fee, annual fee, refund, rebate, payment), and add up the new charges to compare with the amount the statement prints.

| Parser | Notes |
|---|---|
| `esun.credit_card` | Several cards per bill; rebates listed separately |
| `taishin.credit_card` | Several Richart cards per bill; long descriptions wrap onto the lines around the row, never across a page break |
| `cathay.credit_card` | Due date taken from the auto-debit notice, which already accounts for holidays. Payments are checked against 繳款小計; a mismatch is a warning, since payments are not part of the reconciled new charges |
| `hsbc.credit_card` | Labels and descriptions are images. Rows come from the text layer, descriptions from OCR of the description column, matched by baseline. The new-charges subtotal and total due are the 4th and 5th unlabelled amounts on the transaction pages. Rows without a country or currency are classified by words in their description (年費, 回饋/折抵, 國外交易手續費; interest and other charges count as purchases, as at the other banks); without one, a payment in the payments section and a foreign transaction fee among the new charges |

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
| `PARSER_HOST` | `[::]` | Address to listen on |
| `PARSER_PORT` | `50051` | |
| `PARSER_WORKERS` | `4` | Threads for every call: `ParseDocument`, `OpenDocument`, and health checks. Keep it above the backend's `BACKEND_PARSE_CONCURRENCY` (2), or parses that take every thread starve previews and the container healthcheck, which gives up after 3 seconds |
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
