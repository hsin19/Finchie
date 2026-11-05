import {
    api,
    need,
} from "#lib/api/client.js";
import { monthOf } from "#lib/dates.js";
import { error } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

// No parent(): a re-parse replaces the statement (new id), and this page follows it itself instead of
// reloading a statement that no longer exists.
export const load = (async ({ fetch, params }) => {
    const id = Number(params.id);
    if (!Number.isSafeInteger(id) || id <= 0) error(404, `statement ${params.id} not found`);

    const client = api(fetch);
    const statement = need(await client.GET("/api/statements/{id}", { params: { path: { id } } }));
    const [transactions, document] = await Promise.all([
        client.GET("/api/statements/{id}/transactions", { params: { path: { id } } }),
        client.GET("/api/documents/{id}", { params: { path: { id: statement.documentId } } }),
    ]);
    return {
        statement,
        transactions: need(transactions),
        document: need(document),
        prompt: `statements/${statement.institution}/${monthOf(statement.closingDate)}`,
    };
}) satisfies PageLoad;
