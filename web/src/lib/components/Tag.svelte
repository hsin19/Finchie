<script lang="ts">
import {
    statuses,
    tone,
} from "#lib/labels.js";

let { status, label = false }: { status: keyof typeof statuses; label?: boolean; } = $props();
const s = $derived(statuses[status]);
</script>

<span class="whitespace-pre {tone[s.tone]}" title={s.label}>{s.tag}</span>{#if label}<span class="ml-2 text-dim">{s.label}</span>{/if}
