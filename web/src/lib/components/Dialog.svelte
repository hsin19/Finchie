<script lang="ts">
import type { Snippet } from "svelte";

// A native modal <dialog>: focus trap, Esc, and the backdrop come with it.
let { open = $bindable(false), title, children }: { open: boolean; title: string; children: Snippet; } = $props();
let dialog: HTMLDialogElement | undefined = $state();

$effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
});
</script>

<dialog
    bind:this={dialog}
    aria-label={title}
    class="panel m-auto mt-[12vh] w-[min(560px,calc(100vw-32px))] p-0 text-ink backdrop:bg-black/60"
    onclose={() => (open = false)}
    onclick={event => {
        if (event.target === dialog) open = false;
    }}
>
    {#if open}{@render children()}{/if}
</dialog>
