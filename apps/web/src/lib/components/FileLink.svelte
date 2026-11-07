<script lang="ts">
import { documentContentUrl } from "#lib/api/client.js";
import type { Snippet } from "svelte";

// The original upload, served by the backend API rather than an app route, so it opens in a new
// tab and skips the client-side router.
let { id, class: className = "", children }: { id: number; class?: string; children: Snippet; } = $props();
</script>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- an API URL, not a route -->
<a class={className} href={documentContentUrl(id)} target="_blank" rel="noreferrer" data-sveltekit-reload>{@render children()}</a>
