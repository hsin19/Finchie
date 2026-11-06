import type { Transaction } from "#lib/api/client.js";
import { approx } from "#lib/money.js";

// Banks charge a foreign transaction fee per foreign purchase, as a separate line on the same day.
// Some name the merchant in the fee line ("國外交易手續費SSPEMIRATESL"), some don't ("國外交易服務費");
// the fee is about 1.5% of the purchase either way.

const TYPICAL_RATE = 0.015;

/** The merchant part of a description, letters and digits only: "A·T·B·SERVIZ" → "atbserviz". */
function merchantKey(description: string): string {
    return description.replace(/國外交易(手續|服務)費/g, "").replace(/[^\p{L}\p{N}]/gu, "").toLowerCase();
}

function rateDistance(fee: Transaction, purchase: Transaction): number {
    const amount = approx(purchase.amount);
    return amount === 0 ? Infinity : Math.abs(approx(fee.amount) / amount - TYPICAL_RATE);
}

/** E.SUN and Taishin list several cards on one statement; a fee belongs to a purchase on its card. */
function sameCard(a: Transaction, b: Transaction): boolean {
    return !a.cardLast4 || !b.cardLast4 || a.cardLast4 === b.cardLast4;
}

function bestMatch(fee: Transaction, candidates: Transaction[]): Transaction | undefined {
    const purchases = candidates.filter(p => sameCard(fee, p));
    const key = merchantKey(fee.description);
    if (key) {
        const named = purchases.find(p => merchantKey(p.description).startsWith(key));
        if (named) return named;
    }
    // Without a merchant name, the closest rate wins, within a plausible range.
    const ranked = purchases.filter(p => rateDistance(fee, p) <= 0.01).sort((a, b) => rateDistance(fee, a) - rateDistance(fee, b));
    return ranked[0];
}

/** The fee charged for a purchase, or the purchase a fee was charged for, among `items`. */
export function matchingFee(selected: Transaction, items: Transaction[]): Transaction | undefined {
    const sameDay = items.filter(t => t.id !== selected.id && t.statementId === selected.statementId && t.transactionDate === selected.transactionDate);
    const purchases = sameDay.filter(t => t.kind === "purchase");
    const fees = sameDay.filter(t => t.kind === "foreign_transaction_fee");

    if (selected.kind === "foreign_transaction_fee") return bestMatch(selected, purchases);
    if (selected.kind !== "purchase") return undefined;
    // A purchase's fee is the fee whose best match is this purchase.
    return fees.find(fee => bestMatch(fee, [selected, ...purchases])?.id === selected.id);
}
