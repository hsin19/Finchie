// A month's bill is the statements that closed in it, one per bank. Its amount is what those
// statements say is due: for a card paid in full every month, that month's net charges.

import type {
    Statement,
    TransactionSearch,
} from "#lib/api/client.js";
import {
    type Month,
    monthOf,
    monthRange,
} from "#lib/dates.js";
import { institutionOrder } from "#lib/labels.js";
import {
    approx,
    sum,
} from "#lib/money.js";

/** Statements by the month they closed in. */
export function byClosingMonth(statements: readonly Statement[]): Map<Month, Statement[]> {
    const months = new Map<Month, Statement[]>();
    for (const s of statements) {
        const month = monthOf(s.closingDate);
        months.set(month, [...(months.get(month) ?? []), s]);
    }
    return months;
}

/** Months with at least one statement, newest first. */
export function closingMonths(statements: readonly Statement[]): Month[] {
    return [...byClosingMonth(statements).keys()].sort().reverse();
}

export function totalDue(statements: readonly Statement[]): string {
    return sum(statements.map(s => s.totalDue));
}

/** Transaction search filter for the statements that closed in `month`. */
export function closingRange(month: Month): { closingFrom: string; closingTo: string; } {
    const { from, to } = monthRange(month);
    return { closingFrom: from, closingTo: to };
}

/** Banks that had a statement the month before `month` but none in it yet. */
export function pendingInstitutions(statements: readonly Statement[], month: Month, previous: Month): string[] {
    const months = byClosingMonth(statements);
    const issued = new Set((months.get(month) ?? []).map(s => s.institution));
    const expected = new Set((months.get(previous) ?? []).map(s => s.institution));
    return sortInstitutions([...expected].filter(i => !issued.has(i)));
}

/** Percent change from `before` to `after`; undefined without a positive `before` to compare with. */
export function percentChange(after: string, before: string): number | undefined {
    const base = approx(before);
    return base > 0 ? ((approx(after) - base) / base) * 100 : undefined;
}

/**
 * Foreign transaction fees as a percent of overseas purchases, given purchase searches of all lines
 * and of overseas ones. Purchases count as printed (the kind facet), not as the search's sum, which
 * nets refunds and fees into them (ADR 0009): a booking refunded in full would leave its fee as 100%.
 */
export function fxFeeShare(all: TransactionSearch, overseas: TransactionSearch): { percent: number; of: string; } | undefined {
    const fee = all.byKind.find(k => k.kind === "foreign_transaction_fee")?.amount ?? "0";
    const purchases = overseas.byKind.find(k => k.kind === "purchase")?.amount ?? "0";
    return approx(purchases) > 0 ? { percent: (approx(fee) / approx(purchases)) * 100, of: purchases } : undefined;
}

export interface MonthBill {
    month: Month;
    total: string;
    /** Amount due per bank, in chart order; banks without a statement that month are left out. */
    parts: { institution: string; amount: string; }[];
}

/** The bill of each of `months`, in the order given. */
export function monthlyBills(statements: readonly Statement[], months: readonly Month[]): MonthBill[] {
    const grouped = byClosingMonth(statements);
    return months.map(month => {
        const closed = grouped.get(month) ?? [];
        const banks = sortInstitutions([...new Set(closed.map(s => s.institution))]);
        const parts = banks.map(institution => ({ institution, amount: totalDue(closed.filter(s => s.institution === institution)) }));
        return { month, total: totalDue(closed), parts };
    });
}

export function sortInstitutions(ids: string[]): string[] {
    const rank = (id: string) => {
        const i = institutionOrder.indexOf(id);
        return i === -1 ? institutionOrder.length : i;
    };
    return ids.toSorted((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}
