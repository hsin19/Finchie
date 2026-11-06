import { error } from "@sveltejs/kit";
import createClient from "openapi-fetch";
import type {
    components,
    paths,
} from "./schema";

// Generated from services/backend/api/openapi.yaml by `task web:generate`.
type Schemas = components["schemas"];
export type CardTotal = Schemas["CardTotal"];
export type Document = Schemas["Document"];
export type DocumentStatus = Schemas["DocumentStatus"];
export type KindTotal = Schemas["KindTotal"];
export type Statement = Schemas["Statement"];
export type Transaction = Schemas["Transaction"];
export type TransactionFamily = Schemas["TransactionFamily"];
export type TransactionKind = Schemas["TransactionKind"];
export type TransactionLink = Schemas["TransactionLink"];
export type TransactionSearch = Schemas["TransactionSearch"];
export type TransactionSort = Schemas["TransactionSort"];
export type TransactionQuery = NonNullable<paths["/api/transactions"]["get"]["parameters"]["query"]>;

/** Dependency of the layout load: invalidate it after an upload or re-parse. */
export const LEDGER = "app:ledger";

export const TRANSACTIONS_PAGE_SIZE = 50;

/** In a load function pass its `fetch`, so SvelteKit can track and replay the requests. */
export function api(fetchFn: typeof fetch = fetch) {
    return createClient<paths>({ fetch: fetchFn });
}

interface Result {
    data?: unknown;
    error?: unknown;
    response: Response;
}

type Data<R extends Result> = NonNullable<R["data"]>;

function message(result: Result): string {
    const body = result.error as { message?: unknown; } | undefined;
    return typeof body?.message === "string" ? body.message : result.response.statusText || `HTTP ${result.response.status}`;
}

/** For load functions: an error response becomes SvelteKit's error page. */
export function need<R extends Result>(result: R): Data<R> {
    if (result.data === undefined) error(result.response.status, message(result));
    return result.data as Data<R>;
}

/** For event handlers: an error response becomes an Error to show next to the control. */
export function unwrap<R extends Result>(result: R): Data<R> {
    if (result.data === undefined) throw new Error(message(result));
    return result.data as Data<R>;
}

export function documentContentUrl(id: number): string {
    return `/api/documents/${id}/content`;
}
