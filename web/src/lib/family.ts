// A line and the lines that adjust it (ADR 0009): a purchase with its foreign transaction fee, refunds,
// and points redemptions, which may be on later statements. Lists show the purchase net of them.

import type {
    Transaction,
    TransactionKind,
} from "#lib/api/client.js";
import {
    kindOrder,
    kinds,
} from "#lib/labels.js";
import {
    formatAmount,
    sign,
    sum,
} from "#lib/money.js";

type Line = Pick<Transaction, "amount" | "children">;

/** What the line came to in the end: its amount and every child's. */
export function net(t: Line): string {
    return sum([t.amount, ...(t.children ?? []).map(c => c.amount)]);
}

/** The children's amounts by kind, in kind order. */
export function adjustments(t: Line): { kind: TransactionKind; amount: string; }[] {
    const children = t.children ?? [];
    return kindOrder
        .filter(kind => children.some(c => c.kind === kind))
        .map(kind => ({ kind, amount: sum(children.filter(c => c.kind === kind).map(c => c.amount)) }));
}

/** "原 4,200 · 海外手續費 +63 · 退款 -4,200", or "" for a line without children. */
export function breakdown(t: Line): string {
    const parts = adjustments(t).map(a => `${kinds[a.kind].label} ${formatAmount(a.amount, { signed: true })}`);
    return parts.length > 0 ? [`原 ${formatAmount(t.amount)}`, ...parts].join(" · ") : "";
}

/** A purchase its refunds took back in full; what is left, if anything, is fees. */
export function refundedInFull(t: Line): boolean {
    const refunds = (t.children ?? []).filter(c => c.kind === "refund").map(c => c.amount);
    return refunds.length > 0 && sign(sum([t.amount, ...refunds])) === 0;
}
