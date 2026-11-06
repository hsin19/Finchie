import {
    describe,
    expect,
    it,
} from "vitest";
import type { Transaction } from "./api/client";
import { matchingFee } from "./fees";

let nextId = 1;
function tx(description: string, kind: Transaction["kind"], amount: string, date = "2026-10-16", statementId = 1): Transaction {
    return { id: nextId++, statementId, institution: "hsbc", transactionDate: date, description, kind, amount };
}

describe("matchingFee", () => {
    const emirates = tx("SSPEMIRATESLLCABUDH", "purchase", "556");
    const autogrill = tx("AutogrillMiddleEast", "purchase", "635");
    const dutyFree = tx("LCAUO5ADDFDUTYFREEA", "purchase", "918");
    const emiratesFee = tx("國外交易手續費SSPEMIRATESL", "foreign_transaction_fee", "8");
    const autogrillFee = tx("國外交易手續費Autogril1Mid", "foreign_transaction_fee", "10");
    const dutyFreeFee = tx("國外交易手續費LCAUO5ADDFDU", "foreign_transaction_fee", "14");
    const refund = tx("RefundGlobalblue·co", "refund", "-6553");
    const day = [refund, emiratesFee, autogrillFee, dutyFreeFee, emirates, autogrill, dutyFree];

    it("pairs a named fee with its merchant", () => {
        expect(matchingFee(emiratesFee, day)).toBe(emirates);
        expect(matchingFee(dutyFree, day)).toBe(dutyFreeFee);
    });

    it("falls back to the typical rate when the name was misread", () => {
        // OCR read "Autogrill" as "Autogril1": no prefix match, but 10 / 635 is 1.6%.
        expect(matchingFee(autogrillFee, day)).toBe(autogrill);
        expect(matchingFee(autogrill, day)).toBe(autogrillFee);
    });

    it("pairs an unnamed fee by rate", () => {
        const stream = tx("STREAMING*SERVICE", "purchase", "479", "2026-09-18", 2);
        const coffee = tx("COFFEE", "purchase", "120", "2026-09-18", 2);
        const fee = tx("國外交易服務費", "foreign_transaction_fee", "7", "2026-09-18", 2);
        expect(matchingFee(fee, [stream, coffee, fee])).toBe(stream);
    });

    it("pairs within a card when a statement lists several", () => {
        const card = (t: Transaction, last4: string) => ({ ...t, cardLast4: last4 });
        const onA = card(tx("UBER *TRIP", "purchase", "300", "2026-09-20", 3), "1111");
        const onB = card(tx("UBER *TRIP", "purchase", "300", "2026-09-20", 3), "2222");
        const feeOnB = card(tx("國外交易手續費UBER *TRIP", "foreign_transaction_fee", "5", "2026-09-20", 3), "2222");
        const day = [onA, onB, feeOnB];
        expect(matchingFee(feeOnB, day)).toBe(onB);
        expect(matchingFee(onA, day)).toBeUndefined();
        expect(matchingFee(onB, day)).toBe(feeOnB);
    });

    it("leaves other kinds and other days alone", () => {
        expect(matchingFee(refund, day)).toBeUndefined();
        const otherDay = tx("SSPEMIRATESLLCABUDH", "purchase", "556", "2026-10-17");
        expect(matchingFee(otherDay, [...day, otherDay])).toBeUndefined();
    });
});
