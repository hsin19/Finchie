import {
    describe,
    expect,
    it,
} from "vitest";
import type { Statement } from "./api/client";
import {
    closingMonths,
    closingRange,
    monthlyBills,
    pendingInstitutions,
    percentChange,
} from "./bills";

function statement(institution: string, closingDate: string, totalDue: string): Statement {
    return {
        id: 0,
        documentId: 0,
        institution,
        closingDate,
        dueDate: closingDate,
        currency: "TWD",
        totalDue,
        transactionCount: 0,
        reconciliation: { balanced: true, computed: totalDue, stated: totalDue, statedLabel: "" },
    };
}

const statements = [
    statement("hsbc", "2026-11-03", "1200"),
    statement("esun", "2026-10-27", "300.5"),
    statement("hsbc", "2026-10-03", "800"),
    statement("taishin", "2026-10-01", "5000"),
    statement("taishin", "2026-09-01", "4000"),
];

describe("bills", () => {
    it("lists the months with a statement, newest first", () => {
        expect(closingMonths(statements)).toEqual(["2026-11", "2026-10", "2026-09"]);
    });

    it("sums each month by bank, banks in chart order, empty months included", () => {
        const [october, november, december] = monthlyBills(statements, ["2026-10", "2026-11", "2026-12"]);
        expect(october).toEqual({
            month: "2026-10",
            total: "6100.5",
            parts: [
                { institution: "taishin", amount: "5000" },
                { institution: "hsbc", amount: "800" },
                { institution: "esun", amount: "300.5" },
            ],
        });
        expect(november.parts).toEqual([{ institution: "hsbc", amount: "1200" }]);
        expect(december).toEqual({ month: "2026-12", total: "0", parts: [] });
    });

    it("knows which banks have not closed this month yet", () => {
        expect(pendingInstitutions(statements, "2026-11", "2026-10")).toEqual(["taishin", "esun"]);
        expect(pendingInstitutions(statements, "2026-10", "2026-09")).toEqual([]);
    });

    it("filters transactions by the statement's closing month", () => {
        expect(closingRange("2026-02")).toEqual({ closingFrom: "2026-02-01", closingTo: "2026-02-28" });
    });

    it("compares only with a positive amount", () => {
        expect(percentChange("150", "100")).toBe(50);
        expect(percentChange("150", "0")).toBeUndefined();
    });
});
