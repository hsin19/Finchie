import {
    describe,
    expect,
    it,
} from "vitest";
import { carriedQueries } from "./nav";

const carried = (routeId: string, query: string) => carriedQueries(routeId, new URLSearchParams(query));

describe("carriedQueries", () => {
    it("takes a month's bill to the transactions on it", () => {
        expect(carried("/statements", "m=2026-10")).toEqual({ statements: "?m=2026-10", transactions: "?closing=2026-10" });
    });

    it("takes the transactions of a closing month back to that month's bill", () => {
        expect(carried("/transactions", "closing=2026-10&kind=purchase")).toEqual({ statements: "?m=2026-10", transactions: "?closing=2026-10" });
        expect(carried("/transactions", "m=all&closing=2026-10")).toEqual({ statements: "?m=2026-10", transactions: "?m=all&closing=2026-10" });
    });

    it("keeps a month of transactions only where it means the same", () => {
        expect(carried("/transactions", "m=2026-10&q=uber")).toEqual({ statements: "", transactions: "?m=2026-10" });
    });

    it("carries nothing from other pages, or without a month", () => {
        expect(carried("/statements", "all")).toEqual({ statements: "", transactions: "" });
        expect(carried("/statements/[id]", "line=4")).toEqual({ statements: "", transactions: "" });
        expect(carried("/", "")).toEqual({ statements: "", transactions: "" });
    });
});
