import {
    api,
    need,
    type TransactionKind,
    type TransactionQuery,
    TRANSACTIONS_PAGE_SIZE as PAGE_SIZE,
} from "#lib/api/client.js";
import { closingRange } from "#lib/bills.js";
import {
    isMonth,
    type Month,
    monthRange,
} from "#lib/dates.js";
import { kindOrder } from "#lib/labels.js";
import type { PageLoad } from "./$types";

function isKind(value: string): value is TransactionKind {
    return (kindOrder as string[]).includes(value);
}

// Every filter lives in the URL (?m=2026-10&kind=purchase&card=hsbc:4417&q=uber&overseas=1&page=2),
// so a filtered view can be bookmarked and the back button undoes a filter. ?closing=2026-10 keeps the
// rows of the statements that closed that month; it replaces the default period instead of adding to it.
export const load = (async ({ fetch, url, parent }) => {
    const { latestMonth } = await parent();
    const params = url.searchParams;
    const m = params.get("m");
    const closingParam = params.get("closing");
    const closing = isMonth(closingParam) ? closingParam : undefined;
    const period: Month | "all" = m === "all" ? "all" : isMonth(m) ? m : closing ? "all" : latestMonth;
    const kinds = params.getAll("kind").filter(isKind);
    const [institution = "", card = ""] = (params.get("card") ?? "").split(":");
    const q = params.get("q") ?? "";
    const overseas = params.get("overseas") === "1";
    const pageNumber = Math.max(1, Math.floor(Number(params.get("page"))) || 1);

    const query: TransactionQuery = {
        ...(period === "all" ? {} : monthRange(period)),
        ...(closing ? closingRange(closing) : {}),
        kind: kinds.length > 0 ? kinds : undefined,
        institution: institution || undefined,
        card: card || undefined,
        q: q || undefined,
        overseas: overseas || undefined,
        limit: PAGE_SIZE,
        offset: (pageNumber - 1) * PAGE_SIZE,
    };
    const result = need(await api(fetch).GET("/api/transactions", { params: { query } }));
    return { period, filters: { kinds, institution, card, q, overseas, closing }, pageNumber, result };
}) satisfies PageLoad;
