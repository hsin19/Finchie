import {
    api,
    need,
} from "#lib/api/client.js";
import { error } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

export const load = (async ({ fetch, params }) => {
    const id = Number(params.id);
    if (!Number.isSafeInteger(id) || id <= 0) error(404, `document ${params.id} not found`);

    const client = api(fetch);
    const [document, preview] = await Promise.all([
        client.GET("/api/documents/{id}", { params: { path: { id } } }),
        client.GET("/api/documents/{id}/preview", { params: { path: { id } } }),
    ]);
    return { document: need(document), preview: need(preview), command: `documents show ${id}` };
}) satisfies PageLoad;
