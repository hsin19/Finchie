import {
    api,
    need,
    type TransactionQuery,
} from "#lib/api/client.js";
import {
    isMonth,
    monthRange,
    shiftMonth,
} from "#lib/dates.js";
import type { PageLoad } from "./$types";

export const load = (async ({ fetch, url, parent }) => {
    const { latestMonth } = await parent();
    const m = url.searchParams.get("m");
    const month = isMonth(m) ? m : latestMonth;

    // Totals only (limit 0). With kind=purchase, `sum` and byCard are spending, while byKind (which
    // ignores the kind filter) still has fees, rebates, and payments.
    const client = api(fetch);
    const purchases = (query: TransactionQuery) => client.GET("/api/transactions", { params: { query: { kind: ["purchase"], limit: 0, ...query } } });
    const [current, previous, overseas] = await Promise.all([
        purchases(monthRange(month)),
        purchases(monthRange(shiftMonth(month, -1))),
        purchases({ ...monthRange(month), overseas: true }),
    ]);
    return { month, current: need(current), previous: need(previous), overseas: need(overseas) };
}) satisfies PageLoad;
