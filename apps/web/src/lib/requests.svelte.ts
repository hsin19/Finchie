import {
    type FilterChanges,
    withChanges,
} from "#lib/filters.js";
import type { ReadonlyURLSearchParams } from "$app/state";

/**
 * The query a page asked for last. page.url, and the page's data, change only once the requested page
 * has loaded, so a change made while it loads has to build on the request or it drops it: two filters
 * clicked in quick succession, or a search sent while a filter is still loading.
 */
export class QueryRequests {
    #current: () => ReadonlyURLSearchParams;
    #pending = $state.raw<{ params: URLSearchParams; push: boolean; }>();

    constructor(current: () => ReadonlyURLSearchParams) {
        this.#current = current;
    }

    /** The query as last asked for; the page's own while nothing is loading. */
    get params(): ReadonlyURLSearchParams {
        return this.#pending?.params ?? this.#current();
    }

    /**
     * Applies `changes` to the query asked for last. A replace while a push is still loading would
     * overwrite the history entry before it, losing what Back should return to, so it pushes too.
     */
    request(changes: FilterChanges, { replace = false } = {}): { query: string; replace: boolean; } {
        const push = !replace || (this.#pending?.push ?? false);
        const params = withChanges(this.params, changes);
        this.#pending = { params, push };
        return { query: params.toString(), replace: !push };
    }

    /** A navigation finished: the page's own query is the one to build on again. */
    settle(): void {
        this.#pending = undefined;
    }
}
