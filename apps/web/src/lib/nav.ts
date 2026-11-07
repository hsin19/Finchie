import { isMonth } from "#lib/dates.js";
import type { ReadonlyURLSearchParams } from "$app/state";

type Query = "" | `?${string}`;

function query(entries: [string, string | null][]): Query {
    const params = new URLSearchParams(entries.filter((e): e is [string, string] => e[1] !== null)).toString();
    return params ? `?${params}` : "";
}

/**
 * What the page links in the header carry over from the page on screen: its month, in the parameter
 * that means that month on the other page. On /statements ?m= is a closing month; on /transactions it
 * is the month of the transactions, and ?closing= is the closing month.
 */
export function carriedQueries(routeId: string | null, params: ReadonlyURLSearchParams): { statements: Query; transactions: Query; } {
    const m = params.get("m");
    const closing = params.get("closing");
    if (routeId === "/statements" && isMonth(m)) return { statements: query([["m", m]]), transactions: query([["closing", m]]) };
    if (routeId === "/transactions") {
        return {
            statements: query([["m", isMonth(closing) ? closing : null]]),
            transactions: query([["m", isMonth(m) || m === "all" ? m : null], ["closing", isMonth(closing) ? closing : null]]),
        };
    }
    return { statements: "", transactions: "" };
}
