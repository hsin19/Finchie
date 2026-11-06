<script lang="ts">
import {
    api,
    type Transaction,
    type TransactionFamily,
    type TransactionKind,
    type TransactionLink,
    TRANSACTIONS_PAGE_SIZE as PAGE_SIZE,
    type TransactionSort,
} from "#lib/api/client.js";
import Dialog from "#lib/components/Dialog.svelte";
import FileLink from "#lib/components/FileLink.svelte";
import MonthSelect from "#lib/components/MonthSelect.svelte";
import Tag from "#lib/components/Tag.svelte";
import {
    monthOf,
    shortDate,
    weekday,
} from "#lib/dates.js";
import {
    breakdown,
    net,
    refundedInFull,
} from "#lib/family.js";
import { onKeys } from "#lib/keys.svelte.js";
import {
    cardLabel,
    institution,
    kindOrder,
    kinds,
    tone,
} from "#lib/labels.js";
import {
    approx,
    formatAmount,
    sum,
} from "#lib/money.js";
import { goto } from "$app/navigation";
import { resolve } from "$app/paths";
import { page } from "$app/state";
import type { PageProps } from "./$types";

let { data }: PageProps = $props();

const items = $derived(data.result.items);
const statements = $derived(new Map(data.statements.map(s => [s.id, s])));
const documents = $derived(new Map(data.documents.map(d => [d.id, d])));

// ---- URL-backed filters

function navigate(changes: Record<string, string | string[] | null>, { replace = false, keepPage = false } = {}) {
    const dropped = [...Object.keys(changes), ...(keepPage ? [] : ["page"])];
    const kept = [...page.url.searchParams].filter(([key]) => !dropped.includes(key));
    const added = Object.entries(changes).flatMap(([key, value]) => (value === null ? [] : [value].flat()).filter(v => v !== "").map(v => [key, v]));
    const query = new URLSearchParams([...kept, ...added]).toString();
    return goto(query ? resolve(`/transactions?${query}`) : resolve("/transactions"), { reset: false, replace });
}

// Search applies while typing, a moment after the last key. The box follows the URL (Back, [t], the
// command palette) except when the URL change is the search the box itself sent: by then the user
// may have typed more.
const urlQuery = $derived(page.url.searchParams.get("q") ?? "");
let search = $state(page.url.searchParams.get("q") ?? "");
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let sentQuery: string | undefined;

$effect(() => {
    const q = urlQuery;
    if (q === sentQuery) {
        sentQuery = undefined;
        return;
    }
    clearTimeout(searchTimer);
    search = q;
});

// Leaving the page drops a search that was not sent yet, instead of navigating back here.
$effect(() => () => clearTimeout(searchTimer));

function sendSearch() {
    clearTimeout(searchTimer);
    const q = search.trim();
    if (q === urlQuery) return;
    sentQuery = q;
    void navigate({ q: q || null }, { replace: true });
}
function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(sendSearch, 250);
}
function onSearchKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
        search = "";
        sendSearch();
    } else if (event.key === "Enter" || event.key === "ArrowDown") {
        event.preventDefault();
        sendSearch();
        (event.currentTarget as HTMLInputElement).blur();
        selectedId = items[0]?.id;
    }
}

// No kind filter means every kind. Toggling one off from "all" keeps the rest.
const activeKinds = $derived(new Set<TransactionKind>(data.filters.kinds.length > 0 ? data.filters.kinds : kindOrder));
function toggleKind(kind: TransactionKind) {
    const next = kindOrder.filter(k => (k === kind ? !activeKinds.has(k) : activeKinds.has(k)));
    const all = next.length === 0 || next.length === kindOrder.length;
    void navigate({ kind: all ? null : next });
}
const kindCounts = $derived(new Map(data.result.byKind.map(k => [k.kind, k])));

// Card picker: each bank, then each of its cards. Counts come from the byCard facet, which
// ignores the card filter, so every option shows what picking it would give.
const cardOptions = $derived.by(() => {
    const options: { value: string; label: string; }[] = [];
    const banks = [...new Set(data.result.byCard.map(c => c.institution))];
    for (const bank of banks) {
        const cards = data.result.byCard.filter(c => c.institution === bank);
        options.push({ value: bank, label: `${institution(bank).code} (all) · ${cards.reduce((n, c) => n + c.count, 0)}` });
        for (const c of cards) if (c.cardLast4) options.push({ value: `${bank}:${c.cardLast4}`, label: `${cardLabel(bank, c.cardLast4)} · ${c.count}` });
    }
    return options;
});
const cardValue = $derived(data.filters.institution ? `${data.filters.institution}${data.filters.card ? `:${data.filters.card}` : ""}` : "");

// ---- Selection and detail

let selectedId = $state<number>();
let sheet = $state(false);
const cursor = $derived(items.findIndex(t => t.id === selectedId));
const selected = $derived(cursor >= 0 ? items[cursor] : undefined);

function select(t: Transaction | undefined, { open = false } = {}) {
    selectedId = t?.id;
    if (t && open && !matchMedia("(min-width: 1024px)").matches) sheet = true;
    if (t) document.getElementById(`tx-${t.id}`)?.scrollIntoView({ block: "nearest" });
}

// The selected line's parent and children (ADR 0009), which may be on other statements.
let family = $state<TransactionFamily>();
const linkedId = $derived(selected && (selected.parent || selected.children?.length) ? selected.id : undefined);
$effect(() => {
    const id = linkedId;
    family = undefined;
    if (id === undefined) return;
    const controller = new AbortController();
    api()
        .GET("/api/transactions/{id}", { params: { path: { id } }, signal: controller.signal })
        .then(({ data }) => (family = data))
        // Aborted, or failed: the panel shows the line without its links.
        .catch(() => undefined);
    return () => controller.abort();
});

/** Where a linked line is: its statement, scrolled to the line. */
function lineHref(link: Pick<TransactionLink, "id" | "statementId">) {
    return resolve(`/statements/[id]?line=${link.id}`, { id: String(link.statementId) });
}

function statementLabel(statementId: number) {
    const statement = statements.get(statementId);
    return statement ? `${institution(statement.institution).name} ${monthOf(statement.closingDate)}` : `#${statementId}`;
}

// ---- Paging

const first = $derived(data.result.total === 0 ? 0 : (data.pageNumber - 1) * PAGE_SIZE + 1);
const last = $derived((data.pageNumber - 1) * PAGE_SIZE + items.length);
const pages = $derived(Math.max(1, Math.ceil(data.result.total / PAGE_SIZE)));
function goPage(n: number) {
    if (n < 1 || n > pages || n === data.pageNumber) return;
    selectedId = undefined;
    void navigate({ page: n === 1 ? null : String(n) }, { keepPage: true });
}

// ---- Sort: by date or by amount; clicking the active one flips its direction.

const byDate = $derived(data.sort === "newest" || data.sort === "oldest");
const sortTitles: Record<TransactionSort, string> = { newest: "新到舊", oldest: "舊到新", largest: "大筆在前", smallest: "小筆在前" };
function setSort(sort: TransactionSort) {
    selectedId = undefined;
    void navigate({ sort: sort === "newest" ? null : sort });
}

// Mobile lists the page grouped by day when sorted by date.
const days = $derived.by(() => {
    const groups: { date: string; items: Transaction[]; }[] = [];
    for (const t of items) {
        if (groups.at(-1)?.date !== t.transactionDate) groups.push({ date: t.transactionDate, items: [] });
        groups.at(-1)!.items.push(t);
    }
    return groups;
});

function amountTone(t: Transaction) {
    if (refundedInFull(t)) return "text-mute";
    return t.kind === "purchase" ? "text-ink" : tone[kinds[t.kind].tone];
}

function original(t: Transaction) {
    return t.originalAmount && t.originalCurrency ? `${t.originalCurrency} ${formatAmount(t.originalAmount)}` : "";
}

function rate(t: Transaction) {
    if (!t.originalAmount || !t.originalCurrency || approx(t.originalAmount) === 0) return undefined;
    return `${(approx(t.amount) / approx(t.originalAmount)).toFixed(2)} TWD / ${t.originalCurrency}`;
}

onKeys({
    "j": () => select(items[Math.min(cursor + 1, items.length - 1)]),
    "k": () => select(items[Math.max(cursor - 1, 0)]),
    "Enter": () => select(selected ?? items[0], { open: true }),
    "x": () => {
        selectedId = undefined;
        sheet = false;
    },
    "Escape": () => (selectedId = undefined),
    "n": () => goPage(data.pageNumber + 1),
    "p": () => goPage(data.pageNumber - 1),
    "/": () => document.getElementById("q")?.focus(),
});
</script>

{#snippet linked(l: Transaction, arrow: string, from: Transaction)}
    <a href={lineHref(l)} class="flex flex-col gap-0.5 rounded-[4px] px-1.5 py-1 text-ink hover:bg-raised hover:text-ink">
        <span class="flex gap-2">
            <span class="text-accent">{arrow}</span>
            <span class={tone[kinds[l.kind].tone]}>{kinds[l.kind].short}</span>
            <span class="grow truncate">{l.description}</span>
            <span class={l.kind === "purchase" ? "text-ink" : tone[kinds[l.kind].tone]}>{formatAmount(l.amount)}</span>
        </span>
        <span class="pl-5 text-[12px] text-mute">
            {shortDate(l.transactionDate)}{l.statementId === from.statementId ? "" : ` · ${statementLabel(l.statementId)}`}
            {#if l.kind === "foreign_transaction_fee" && approx(from.amount) > 0}
                · {((approx(l.amount) / approx(from.amount)) * 100).toFixed(1)}%
            {/if}
        </span>
    </a>
{/snippet}

{#snippet detail(t: Transaction)}
    {@const statement = statements.get(t.statementId)}
    {@const doc = statement ? documents.get(statement.documentId) : undefined}
    <div class="flex flex-col gap-3">
        <div class="text-[16px] font-bold break-words">{t.description}</div>
        <div class="flex flex-col gap-0.5">
            <div class="text-[24px] font-bold {amountTone(t)}">{formatAmount(net(t))} <span class="text-[13px] font-normal text-mute">{statement?.currency ?? "TWD"}</span></div>
            {#if breakdown(t)}<div class="text-[12px] text-dim">{breakdown(t)}{refundedInFull(t) ? " · 已全額刷退" : ""}</div>{/if}
        </div>
        <dl class="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt class="text-mute">date</dt>
            <dd class="m-0">{t.transactionDate}{t.postingDate && t.postingDate !== t.transactionDate ? `（入帳 ${shortDate(t.postingDate)}）` : ""}</dd>
            <dt class="text-mute">kind</dt>
            <dd class="m-0 {tone[kinds[t.kind].tone]}">{kinds[t.kind].short} <span class="text-mute">{kinds[t.kind].label}</span></dd>
            {#if original(t)}
                <dt class="text-mute">original</dt>
                <dd class="m-0">{original(t)}</dd>
                <dt class="text-mute">rate</dt>
                <dd class="m-0 text-dim">{rate(t)}</dd>
            {/if}
            {#if t.country}
                <dt class="text-mute">country</dt>
                <dd class="m-0">{t.country}</dd>
            {/if}
            <dt class="text-mute">card</dt>
            <dd class="m-0">{institution(t.institution).name} {cardLabel(t.institution, t.cardLast4)}</dd>
            {#if statement}
                <dt class="text-mute">statement</dt>
                <dd class="m-0">
                    <a href={resolve("/statements/[id]", { id: String(statement.id) })}>{t.institution} {monthOf(statement.closingDate)}</a>
                    <Tag status={statement.reconciliation.balanced ? "parsed" : "needs_review"} />
                </dd>
            {/if}
            {#if doc}
                <dt class="text-mute">parser</dt>
                <dd class="m-0 text-dim">{doc.parser} v{doc.parserVersion}</dd>
            {/if}
        </dl>
        {#if family && (family.parent || family.children.length > 0)}
            <div class="flex flex-col gap-1 border-t border-dashed border-line pt-2.5">
                <div class="label">LINKED · 關聯</div>
                {#if family.parent}
                    {@render linked(family.parent, "↑", t)}
                {/if}
                {#each family.children as child (child.id)}
                    {@render linked(child, "↓", t)}
                {/each}
            </div>
        {/if}
        {#if doc}
            <FileLink id={doc.id}>原始檔 #{doc.id} {doc.filename} →</FileLink>
        {/if}
    </div>
{/snippet}

<section class="panel flex flex-col gap-2.5 p-3 md:p-3.5">
    <div class="flex items-center gap-2 rounded-[4px] border border-line-strong bg-ground px-2.5">
        <label for="q" class="text-accent whitespace-nowrap">[/] 搜尋</label>
        <input
            id="q"
            type="search"
            autocomplete="off"
            placeholder="商店名稱，例如 uber"
            class="min-h-10 min-w-0 grow border-none bg-transparent text-ink outline-none"
            bind:value={search}
            oninput={onSearchInput}
            onkeydown={onSearchKeydown}
        />
        <span class="hidden text-[12px] text-mute sm:inline">[esc] 清除</span>
    </div>
    <div class="flex flex-wrap items-center gap-2">
        <MonthSelect all months={data.months} value={data.period} onchange={m => void navigate({ m })} />
        {#if data.filters.closing}
            <button type="button" class="control pressed" title="移除這個篩選" onclick={() => void navigate({ closing: null })}>
                {data.filters.closing} 結帳的帳單 <span class="text-mute">×</span>
            </button>
        {/if}
        <select class="control" aria-label="卡片" value={cardValue} onchange={event => void navigate({ card: event.currentTarget.value || null })}>
            <option value="">all cards</option>
            {#each cardOptions as option (option.value)}
                <option value={option.value}>{option.label}</option>
            {/each}
            {#if cardValue && !cardOptions.some(o => o.value === cardValue)}<option value={cardValue}>{cardValue}</option>{/if}
        </select>
        <div role="group" aria-label="交易種類" class="flex gap-1.5 overflow-x-auto whitespace-nowrap">
            {#each kindOrder as kind (kind)}
                {@const on = activeKinds.has(kind)}
                <button type="button" aria-pressed={on} class="control shrink-0 {on ? 'pressed' : 'text-mute'}" onclick={() => toggleKind(kind)}>
                    {on ? "[x]" : "[ ]"} {kinds[kind].short} <span class="text-mute">{kindCounts.get(kind)?.count ?? 0}</span>
                </button>
            {/each}
        </div>
        <label class="flex min-h-9 items-center gap-1.5 text-dim">
            <input type="checkbox" class="accent-accent" checked={data.filters.overseas} onchange={event => void navigate({ overseas: event.currentTarget.checked ? "1" : null })} />
            只看海外
        </label>
    </div>
</section>

<div class="flex flex-wrap gap-x-5 gap-y-1 border-b border-dashed border-line px-0.5 pb-2 text-dim">
    <span>rows <span class="text-ink">{data.result.total}</span></span>
    <span>sum <span class="text-ink">{formatAmount(data.result.sum)}</span></span>
    {#each kindOrder.filter(k => k !== "purchase" && activeKinds.has(k) && kindCounts.has(k)) as kind (kind)}
        <span>{kinds[kind].short} <span class={tone[kinds[kind].tone]}>{formatAmount(kindCounts.get(kind)!.amount)}</span></span>
    {/each}
    <span role="group" aria-label="排序" class="ml-auto flex items-center gap-2 text-mute">
        sort
        <button
            type="button"
            aria-pressed={byDate}
            title={sortTitles[data.sort === "oldest" ? "newest" : "oldest"]}
            class={byDate ? "text-ink" : "hover:text-ink"}
            onclick={() => setSort(data.sort === "newest" ? "oldest" : "newest")}
        >
            date{byDate ? (data.sort === "oldest" ? " ▲" : " ▼") : ""}
        </button>
        <button
            type="button"
            aria-pressed={!byDate}
            title={sortTitles[data.sort === "largest" ? "smallest" : "largest"]}
            class={byDate ? "hover:text-ink" : "text-ink"}
            onclick={() => setSort(data.sort === "largest" ? "smallest" : "largest")}
        >
            amount{byDate ? "" : data.sort === "smallest" ? " ▲" : " ▼"}
        </button>
    </span>
</div>

<div class="grid gap-3 {selected ? 'lg:grid-cols-[1fr_340px]' : ''}">
    <section class="panel min-w-0 px-3.5 pt-1 pb-2.5">
        <!-- Desktop: a table. -->
        <div class="hidden overflow-x-auto md:block">
            <table class="w-full border-collapse">
                <thead>
                    <tr class="text-left text-mute">
                        <th class="w-4 py-2 pr-1 font-medium"><span class="sr-only">選取</span></th>
                        <th class="px-2 py-2 font-medium">DATE</th>
                        <th class="px-2 py-2 font-medium">MERCHANT</th>
                        <th class="px-2 py-2 font-medium">KIND</th>
                        <th class="px-2 py-2 font-medium">CARD</th>
                        <th class="px-2 py-2 font-medium">CTRY</th>
                        <th class="px-2 py-2 text-right font-medium">ORIG</th>
                        <th class="py-2 pl-2 text-right font-medium">TWD</th>
                    </tr>
                </thead>
                <tbody>
                    {#each items as t (t.id)}
                        <tr
                            id="tx-{t.id}"
                            class="cursor-pointer border-t border-rule {t.id === selectedId ? 'bg-raised' : 'hover:bg-raised/60'}"
                            onclick={() => select(t, { open: true })}
                        >
                            <td class="py-2 pr-1 text-accent">{t.id === selectedId ? "▶" : ""}</td>
                            <td class="px-2 py-2 whitespace-nowrap">{shortDate(t.transactionDate)}</td>
                            <td class="max-w-[320px] px-2 py-2">
                                <span class="block truncate">{t.description}</span>
                                {#if breakdown(t)}<span class="block truncate text-[11px] text-mute">{breakdown(t)}</span>{/if}
                            </td>
                            <td class="px-2 py-2 {tone[kinds[t.kind].tone]}">{kinds[t.kind].short}</td>
                            <td class="px-2 py-2 whitespace-nowrap text-dim">{cardLabel(t.institution, t.cardLast4)}</td>
                            <td class="px-2 py-2 text-dim">{t.country ?? "—"}</td>
                            <td class="px-2 py-2 text-right whitespace-nowrap text-dim">{original(t)}</td>
                            <td class="py-2 pl-2 text-right whitespace-nowrap {amountTone(t)}">{formatAmount(net(t))}</td>
                        </tr>
                    {:else}
                        <tr class="border-t border-rule"><td colspan="8" class="py-3 text-mute">沒有符合的交易。</td></tr>
                    {/each}
                </tbody>
            </table>
        </div>

        <!-- Mobile: grouped by day when sorted by date; by amount, one list with the date on each row. -->
        {#snippet mobileRow(t: Transaction, withDate: boolean)}
            <button type="button" class="flex min-h-11 w-full flex-col gap-0.5 border-t border-rule py-2.5 text-left text-ink" onclick={() => select(t, { open: true })}>
                <span class="flex w-full justify-between gap-2.5">
                    <span class="truncate">{t.description}</span>
                    <span class="shrink-0 {amountTone(t)}">{formatAmount(net(t))}</span>
                </span>
                <span class="text-[12px] text-mute">
                    {withDate ? `${shortDate(t.transactionDate)} · ` : ""}{cardLabel(t.institution, t.cardLast4)} · {kinds[t.kind].short}{original(t) ? ` · ${original(t)}` : ""}{breakdown(t) ? ` · ${breakdown(t)}` : ""}
                </span>
            </button>
        {/snippet}
        <div class="md:hidden">
            {#if byDate}
                {#each days as day (day.date)}
                    <div class="flex justify-between pt-3 pb-1.5 text-[12px] tracking-[0.06em] text-mute">
                        <span>{shortDate(day.date)} {weekday(day.date)}</span>
                        <span>{formatAmount(sum(day.items.map(net)))}</span>
                    </div>
                    {#each day.items as t (t.id)}
                        {@render mobileRow(t, false)}
                    {/each}
                {:else}
                    <p class="m-0 py-3 text-mute">沒有符合的交易。</p>
                {/each}
            {:else}
                {#each items as t (t.id)}
                    {@render mobileRow(t, true)}
                {:else}
                    <p class="m-0 py-3 text-mute">沒有符合的交易。</p>
                {/each}
            {/if}
        </div>

        <div class="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2.5 text-[12px] text-mute">
            <span>{first}–{last} / {data.result.total}</span>
            <span class="flex items-center gap-2">
                <span class="hidden lg:inline"><span class="text-accent">[j/k]</span> 上下移動 · <span class="text-accent">[enter]</span> 詳細 ·</span>
                <button type="button" class="control min-h-8" disabled={data.pageNumber <= 1} onclick={() => goPage(data.pageNumber - 1)}>[p] prev</button>
                <button type="button" class="control min-h-8" disabled={data.pageNumber >= pages} onclick={() => goPage(data.pageNumber + 1)}>[n] next</button>
            </span>
        </div>
    </section>

    {#if selected}
        <aside aria-label="交易詳細" class="panel hidden self-start p-3.5 lg:sticky lg:top-3 lg:block">
            <div class="mb-3 flex items-center justify-between">
                <h2 class="label">TXN #{selected.id}</h2>
                <button type="button" class="text-mute hover:text-ink" aria-label="關閉詳細" onclick={() => (selectedId = undefined)}>[x]</button>
            </div>
            {@render detail(selected)}
        </aside>
    {/if}
</div>

<Dialog bind:open={sheet} title="交易詳細">
    {#if selected}
        <div class="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 class="label">TXN #{selected.id}</h2>
            <button type="button" class="text-mute" aria-label="關閉" onclick={() => (sheet = false)}>[x]</button>
        </div>
        <div class="p-4">{@render detail(selected)}</div>
    {/if}
</Dialog>
