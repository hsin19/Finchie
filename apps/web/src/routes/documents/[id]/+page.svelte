<script lang="ts">
import {
    documentContentUrl,
    previewBodyUrl,
    previewFileUrl,
} from "#lib/api/client.js";
import Tag from "#lib/components/Tag.svelte";
import {
    formatBytes,
    shortDateTime,
} from "#lib/dates.js";
import { onKeys } from "#lib/keys.svelte.js";
import { documentStatus } from "#lib/labels.js";
import { resolve } from "$app/paths";
import type { PageProps } from "./$types";

let { data }: PageProps = $props();

const doc = $derived(data.document);
const email = $derived(data.preview.email);
const files = $derived(data.preview.files);
const statement = $derived(data.statements.find(s => s.documentId === doc.id));

function open(index: number) {
    window.open(previewFileUrl(doc.id, index), "_blank", "noreferrer");
}

// [1]–[9] open that file; [f] the statement, as everywhere else.
const keys: Record<string, () => void> = {
    f: () => {
        const statementFile = files.find(f => f.primary);
        if (statementFile) open(statementFile.index);
    },
};
for (let n = 1; n <= 9; n++) {
    keys[String(n)] = () => {
        if (n <= files.length) open(n - 1);
    };
}
onKeys(keys);
</script>

<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
    <h1 class="m-0 min-w-0 text-[18px] font-bold break-words">{email?.subject || doc.filename}</h1>
    <Tag status={documentStatus(doc)} label />
    <span class="ml-auto flex flex-wrap gap-x-4 text-[12px]">
        {#if statement}
            <a href={resolve("/statements/[id]", { id: String(statement.id) })} class="text-dim hover:text-ink">這份文件的帳單 →</a>
        {/if}
        <!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- an API URL, not a route -->
        <a href={documentContentUrl(doc.id)} class="text-dim hover:text-ink" data-sveltekit-reload>下載原始檔 ↓</a>
    </span>
</div>

<div class="grid gap-3 md:grid-cols-[1fr_1.3fr]">
    <section class="panel p-3.5">
        <h2 class="label mb-2.5">{email ? "HEADERS · 信件" : "META"}</h2>
        <dl class="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            {#if email}
                <dt class="text-mute">from</dt>
                <dd class="m-0 min-w-0 break-words">{email.sender || "—"}</dd>
                <dt class="text-mute">to</dt>
                <dd class="m-0 min-w-0 break-words text-dim">{email.recipient || "—"}</dd>
                <dt class="text-mute">date</dt>
                <dd class="m-0 text-dim">{email.date ? shortDateTime(email.date) : "—"}</dd>
            {/if}
            <dt class="text-mute">document</dt>
            <dd class="m-0 min-w-0 truncate">#{doc.id} {doc.filename} · {formatBytes(doc.sizeBytes)}</dd>
            <dt class="text-mute">received</dt>
            <dd class="m-0 text-dim">{shortDateTime(doc.receivedAt)}</dd>
            {#if doc.error}
                <dt class="text-mute">error</dt>
                <dd class="m-0 min-w-0 break-words text-neg">{doc.error}</dd>
            {/if}
        </dl>
    </section>

    <section class="panel p-3.5">
        <h2 class="label mb-1">FILES · 附件（{files.length}）</h2>
        {#each files as file (file.index)}
            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-t border-rule py-2 first-of-type:border-t-0">
                <span class="w-[3ch] text-accent">{file.index < 9 ? `[${file.index + 1}]` : ""}</span>
                <!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- an API URL, not a route -->
                <a href={previewFileUrl(doc.id, file.index)} target="_blank" rel="noreferrer" data-sveltekit-reload class="min-w-0 grow break-all text-ink hover:text-accent">{file.filename}</a>
                <span class="text-[12px] {file.locked ? 'text-neg' : 'text-mute'}">
                    {#if file.primary}<span class="text-accent">[f]</span> 帳單 ·{/if}
                    {formatBytes(file.sizeBytes)} · {file.contentType !== "application/pdf" ? "下載" : file.locked ? "需要密碼" : "免密碼"}
                </span>
            </div>
        {:else}
            <p class="m-0 pt-1.5 text-mute">沒有附件</p>
        {/each}
    </section>
</div>

{#if email?.hasBody}
    <section class="panel overflow-hidden">
        <h2 class="label px-3.5 py-2.5">BODY · 內文</h2>
        <!-- Its own response sandboxes the body as well (ADR 0012); links open in a new tab. -->
        <iframe
            title="信件內文"
            src={previewBodyUrl(doc.id)}
            sandbox="allow-popups allow-popups-to-escape-sandbox"
            referrerpolicy="no-referrer"
            class="block h-[75vh] w-full border-0 bg-white"
        ></iframe>
    </section>
{/if}
