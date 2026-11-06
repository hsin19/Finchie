# ADR 0009: Transaction parents

## Decision

A line that adjusts another points at it: `transactions.parent_id`. A foreign transaction fee's parent is the purchase it was charged for; a refund's or a points redemption's is the purchase it takes back, possibly on an earlier statement. One level only: a parent has no parent. The statement's lines stay exactly as printed, so reconciliation and a bill's amount are untouched; parents only change how lines are added up and shown.

| Child | Parent, when clear | Otherwise |
|---|---|---|
| Foreign transaction fee | The purchase on the same statement, day, and card: by the merchant named in the fee line, else the one the fee is closest to 1.5% of. One fee per purchase, best pairs first | No parent |
| Refund | Within 90 days before, same bank, card, and merchant: the latest purchase of the same amount in NT$ or in its foreign currency, each purchase refunded in full once; or several refunds of one day adding up to such a purchase | No parent: part of one of several purchases, tax-free refunds, card balance refunds |
| Points redemption (`點數折抵_…`) | The one purchase of that merchant on the same day | No parent |

**Worked out, not stored by hand.** Banks print no link, so the backend derives it from the lines. Every time a statement is stored, and once at start, every link is cleared and worked out again from all the lines, under an advisory lock. Statements can arrive in any order and a re-parse gives a statement's lines new IDs; working everything out again is cheap at a person's volume and leaves no stale or order-dependent links.

**Folded in lists.** While a search includes purchases, a line with a parent is not a row of its own but one of its parent's `children`, and the row's amounts, totals, card facet, and amount sorts are net of them: a booking refunded in full whose fee was not refunded is one row of 63, "原 4,200 · 海外手續費 +63 · 退款 -4,200". A refund on a later statement thus counts in the purchase's month and statement, not where it was printed. Asked for fees or refunds alone, they are rows again. The kind facet always counts lines as printed, so the fee total stays visible.

**Traceable.** `GET /api/transactions/{id}` returns a line with its parent and children wherever they are; the web app links each to its statement, scrolled to the line.

## Alternatives considered

- **Link fees only, in the web app.** What V2 did first: a fee was matched to a purchase on the same page. It could not fold a fee into its purchase across pages or in totals and sorts, and refunds, which cross statements, could not be done that way at all.
- **Have the parser link lines.** It knows each bank's layout, but sees one statement at a time; refunds need the whole ledger.
- **Keep refunds where they are printed and only mark the link.** Totals per month would match the statements, but a purchase refunded next month would still count as spent this month and show up as a credit then.
