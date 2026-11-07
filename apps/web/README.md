# web

The browser app (ADR 0007): a SvelteKit single-page app, embedded in the backend binary and served from the same origin as `/api`.

| Route | Page |
|---|---|
| `/` | Overview for a month: spending, dues, foreign transaction fees, rebates, spending by card and by kind, recent statements |
| `/statements` | Every statement with its reconciliation, plus documents that produced none |
| `/statements/{id}` | One statement: metadata, reconciliation by kind, its lines in statement order, processing log, re-parse |
| `/transactions` | Search across statements: period, card, kinds, overseas, text; totals for the whole match |
| `/upload` | Drop `.eml` / `.pdf` files and follow each through parsing |

Keys: `o` `s` `t` `u` switch pages, `/` searches, `j` `k` `Enter` `n` `p` move through transactions, `?` lists everything, `⌘K` opens the command palette.

## Development

```sh
task web:install
task web:dev        # Vite on :5173; /api is proxied to the backend on :8080 (task backend:run)
task web:check      # what CI runs: dprint, ESLint, svelte-check, Vitest, build
task web:generate   # after apps/backend/api/openapi.yaml changes; commit src/lib/api/schema.d.ts
task backend:web    # build into the backend, so the backend serves it on :8080
```

Node 26 (`.node-version`); the pnpm version is pinned in `package.json`.

## Layout

| Path | |
|---|---|
| `src/routes/` | Pages. Data comes from universal `load` functions; filters live in the URL |
| `src/routes/layout.css` | Design tokens (`@theme`) and the few custom utilities (`panel`, `label`, `control`) |
| `src/lib/api/` | Generated types (`schema.d.ts`) and the `openapi-fetch` client |
| `src/lib/money.ts` | Exact decimal arithmetic and formatting for amounts (ADR 0004) |
| `src/lib/labels.ts` | Bank names, kind and status labels, tone classes |
| `src/lib/fees.ts` | Pairs a foreign purchase with the fee charged for it |
| `src/lib/keys.ts` | Which key presses are shortcuts: never while typing, never while a dialog is open, never Enter or Space on a focused button or link |

## Pitfalls (SvelteKit 3)

- `#lib` is a package.json subpath import, so imports need the file extension: `#lib/money.js` (for `money.ts`), `#lib/components/Tag.svelte`.
- `+page.ts` / `+layout.ts` may only export SvelteKit's names (`load`, `ssr`, …); shared constants go in `src/lib/`. Type loads with `satisfies PageLoad`, not `: PageLoad`, or `data` loses its types.
- `svelte-check` reads proxy files that `svelte-kit sync` writes; run `pnpm typecheck`, which syncs first.
- `goto` options are `replace`, `reset: false` (keep scroll and focus), and `refreshAll`.
- Internal links go through `resolve()` (`svelte/no-navigation-without-resolve`). Links to API files use `FileLink`.
- A re-parse gives the statement a new id; the statement page follows it.
