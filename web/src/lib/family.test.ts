import {
    describe,
    expect,
    it,
} from "vitest";
import type { TransactionLink } from "./api/client";
import {
    breakdown,
    net,
    refundedInFull,
} from "./family";

function child(kind: TransactionLink["kind"], amount: string, original?: [string, string]): TransactionLink {
    const link: TransactionLink = { id: 0, statementId: 0, kind, transactionDate: "2026-07-20", amount };
    return original ? { ...link, originalCurrency: original[0], originalAmount: original[1] } : link;
}

describe("family", () => {
    // Refunded in full on a later statement; the fee was not refunded.
    const booking = { amount: "4200", children: [child("refund", "-4200"), child("foreign_transaction_fee", "63")] };

    it("nets the children into the amount", () => {
        expect(net(booking)).toBe("63");
        expect(net({ amount: "120" })).toBe("120");
    });

    it("spells out what the net is made of, by kind", () => {
        expect(breakdown(booking)).toBe("原 4,200 · 海外手續費 +63 · 退款 -4,200");
        expect(breakdown({ amount: "120" })).toBe("");
    });

    it("knows a purchase refunded in full, fees or not", () => {
        expect(refundedInFull(booking)).toBe(true);
        expect(refundedInFull({ amount: "2150", children: [child("refund", "-431")] })).toBe(false);
        expect(refundedInFull({ amount: "4200", children: [child("foreign_transaction_fee", "63")] })).toBe(false);
    });

    it("knows a refund in full in the foreign currency, whatever the rate did", () => {
        const order = {
            amount: "2150",
            originalCurrency: "CNY",
            originalAmount: "470.00",
            children: [child("refund", "-431", ["CNY", "-94.00"]), child("refund", "-1712", ["CNY", "-376.00"])],
        };
        expect(net(order)).toBe("7");
        expect(refundedInFull(order)).toBe(true);
        expect(refundedInFull({ ...order, children: [child("refund", "-431", ["CNY", "-94.00"])] })).toBe(false);
        expect(refundedInFull({ ...order, children: order.children.map(c => ({ ...c, originalCurrency: "USD" })) })).toBe(false);
    });
});
