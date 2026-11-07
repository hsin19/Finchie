# mailbox

A Cloudflare Email Worker that takes statements Gmail forwards to an address on Email Routing and
uploads each e-mail to the backend, exactly as a person uploading the `.eml` would. Design and
reasons: [ADR 0010](../../docs/adr/0010-mail-ingestion.md).

```
bank ──▶ Gmail ──filter, forward──▶ finchie@<domain> (Email Routing) ──▶ this Worker
     ──POST /api/documents, Access service token──▶ backend (dedupe, parse, reconcile as usual)
```

| Mail | What happens |
|---|---|
| Forwarded by the owner's Gmail (envelope sender `owner+caf_=…@gmail.com`, or the owner's own address) | Uploaded. Anything the backend cannot parse shows up as a document marked skip or err |
| From `google.com`, such as Gmail's "confirm forwarding" message | Forwarded to the owner, who confirms the new forwarding address with it. Email Routing checks DMARC first, so the From header can be trusted |
| Anything else | Rejected at SMTP time; nothing is stored |
| Upload fails (backend down, token refused) or anything else goes wrong | Rejected, so the bounce reaches the owner's Gmail: upload that one by hand |

## Settings

All four are Worker secrets, so nothing personal is in this repository: whoever deploys the Worker
puts them in (`wrangler secret put`, or Cloudflare's API). The route (an Email Routing address that
runs this Worker) and the service token belong to the deployment's Cloudflare configuration too.

| Secret | What it is |
|---|---|
| `FINCHIE_URL` | The backend's public URL |
| `OWNER_EMAIL` | The Gmail address that forwards statements |
| `ACCESS_CLIENT_ID`, `ACCESS_CLIENT_SECRET` | The Access service token; the backend lets it upload and nothing else |

Until all four are set the Worker rejects every message.

## Commands

```bash
task mailbox:install
task mailbox:check     # dprint, tsc, tests, and a bundle (wrangler deploy --dry-run)
task mailbox:deploy    # by hand; `pnpm exec wrangler login` once first
```

Deploys are by hand: the Worker changes rarely, and a CI deploy would need a Cloudflare API token in
this repository.
