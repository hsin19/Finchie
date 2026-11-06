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

function child(kind: TransactionLink["kind"], amount: string): TransactionLink {
    return { id: 0, statementId: 0, kind, transactionDate: "2026-07-20", amount };
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
});
