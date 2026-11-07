<script lang="ts">
import {
    type Openable,
    openUrl,
} from "#lib/documents.js";
import type { Snippet } from "svelte";

// A new tab, like a file opened from a mail client; an API URL also skips the client-side router.
let { doc, class: className = "", children }: { doc: Openable; class?: string; children: Snippet; } = $props();
</script>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- openUrl resolves the route; the rest are API URLs -->
<a class={className} href={openUrl(doc)} target="_blank" rel="noreferrer" data-sveltekit-reload>{@render children()}</a>
