<script lang="ts" module>
import {
    type Document,
    documentContentUrl,
    previewPdfUrl,
} from "#lib/api/client.js";
import { documentStatus } from "#lib/labels.js";
import { resolve } from "$app/paths";

export type Openable = Pick<Document, "id" | "contentType" | "status" | "error">;

/**
 * Where a document opens (ADR 0012): its statement PDF, decrypted. An e-mail no parser recognized
 * opens on its own page instead, to see what it is; anything else downloads as uploaded.
 */
export function openUrl(doc: Openable): string {
    if (doc.contentType === "message/rfc822" && documentStatus(doc) === "skipped") {
        return resolve("/documents/[id]", { id: String(doc.id) });
    }
    if (doc.contentType === "application/pdf" || doc.contentType === "message/rfc822") return previewPdfUrl(doc.id);
    return documentContentUrl(doc.id);
}
</script>

<script lang="ts">
import type { Snippet } from "svelte";

// A new tab, like a file opened from a mail client; an API URL also skips the client-side router.
let { doc, class: className = "", children }: { doc: Openable; class?: string; children: Snippet; } = $props();
</script>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- openUrl resolves the route; the rest are API URLs -->
<a class={className} href={openUrl(doc)} target="_blank" rel="noreferrer" data-sveltekit-reload>{@render children()}</a>
