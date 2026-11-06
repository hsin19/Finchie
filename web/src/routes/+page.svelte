<script lang="ts">
import type { Statement } from "#lib/api/client.js";
import Bar from "#lib/components/Bar.svelte";
import MonthSelect from "#lib/components/MonthSelect.svelte";
import Tag from "#lib/components/Tag.svelte";
import {
    formatBytes,
    monthOf,
    shortDate,
    today,
} from "#lib/dates.js";
import {
    cardLabel,
    documentStatus,
    institution,
    kindOrder,
    kinds,
    tone,
} from "#lib/labels.js";
import {
    approx,
    formatAmount,
    negate,
    subtract,
    sum,
} from "#lib/money.js";
import { goto } from "$app/navigation";
import { resolve } from "$app/paths";
import type { PageProps } from "./$types";

let { data }: PageProps = $props();

const kindTotal = (kind: string) => data.current.byKind.find(k => k.kind === kind);

const spend = $derived(data.current.sum);
const change = $derived.by(() => {
    const before = approx(data.previous.sum);
    return before > 0 ? ((approx(spend) - before) / before) * 100 : undefined;
});

const due = $derived.by(() => {
    const upcoming = data.statements.filter(s => s.dueDate >= today());
    const next = upcoming.map(s => s.dueDate).sort()[0];
    return { amount: sum(upcoming.map(s => s.totalDue)), next, count: upcoming.length };
});

const fxFee = $derived(kindTotal("foreign_transaction_fee")?.amount ?? "0");
const fxShare = $derived(approx(data.overseas.sum) > 0 ? (approx(fxFee) / approx(data.overseas.sum)) * 100 : undefined);
const rebate = $derived(kindTotal("rebate"));

const cards = $derived([...data.current.byCard].sort((a, b) => approx(b.amount) - approx(a.amount)));
const topCard = $derived(Math.max(...cards.map(c => approx(c.amount)), 1));

const byDocument = $derived(new Map(data.statements.map(s => [s.documentId, s])));
const counts = $derived.by(() => {
    const c = { parsed: 0, pending: 0, needs_review: 0, failed: 0 };
    for (const d of data.documents) {
        const status = documentStatus(d);
        if (status in c) c[status as keyof typeof c]++;
    }
    return c;
});

function reconciliation(s: Statement): string {
    if (s.reconciliation.balanced) return "balanced";
    return `Δ ${formatAmount(subtract(s.reconciliation.stated, s.reconciliation.computed), { signed: true })} · 需確認`;
}
</script>

<div class="flex flex-wrap items-center gap-2">
    <div class="flex grow flex-wrap gap-x-4 gap-y-0.5 rounded-[6px] border border-dashed border-line px-2.5 py-2 text-[12px] text-dim">
        <span><span class="text-pos">●</span> ok {counts.parsed}</span>
        <span><span class="text-accent">●</span> run {counts.pending}</span>
        <span><span class="text-neg">●</span> chk {counts.needs_review}</span>
        {#if counts.failed}<span><span class="text-neg">●</span> err {counts.failed}</span>{/if}
        <span>rows {data.current.byKind.reduce((n, k) => n + k.count, 0)}</span>
    </div>
    <MonthSelect months={data.months} value={data.month} onchange={m => void goto(resolve(`/?m=${m}`), { reset: false })} />
</div>

<div class="grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-3">
    <div class="panel flex flex-col gap-1 p-3 md:p-3.5">
        <div class="text-[10px] tracking-[0.12em] text-mute">SPEND · 本月消費</div>
        <div class="text-[20px] font-bold text-ink-bright md:text-[24px]">{formatAmount(spend)}</div>
        <div class="text-[11px] {change === undefined ? 'text-mute' : change > 0 ? 'text-neg' : 'text-pos'}">
            {change === undefined ? "no prior month" : `${change > 0 ? "+" : ""}${change.toFixed(1)}% m/m`}
        </div>
    </div>
    <div class="panel flex flex-col gap-1 p-3 md:p-3.5">
        <div class="text-[10px] tracking-[0.12em] text-mute">DUE · 待繳</div>
        <div class="text-[20px] font-bold text-ink-bright md:text-[24px]">{formatAmount(due.amount)}</div>
        <div class="text-[11px] text-dim">{due.next ? `next ${shortDate(due.next).replace("-", "/")} · ${due.count} 張` : "沒有待繳帳單"}</div>
    </div>
    <div class="panel flex flex-col gap-1 p-3 md:p-3.5">
        <div class="text-[10px] tracking-[0.12em] text-mute">FX_FEE · 海外手續費</div>
        <div class="text-[20px] font-bold text-neg md:text-[24px]">{formatAmount(fxFee)}</div>
        <div class="text-[11px] text-dim">{fxShare === undefined ? "沒有海外消費" : `${fxShare.toFixed(1)}% of overseas ${formatAmount(data.overseas.sum)}`}</div>
    </div>
    <div class="panel flex flex-col gap-1 p-3 md:p-3.5">
        <div class="text-[10px] tracking-[0.12em] text-mute">REWARD · 回饋</div>
        <div class="text-[20px] font-bold text-pos md:text-[24px]">{formatAmount(rebate ? negate(rebate.amount) : "0")}</div>
        <div class="text-[11px] text-dim">{rebate ? `${rebate.count} 筆入帳回饋` : "本月沒有回饋入帳"}</div>
    </div>
</div>

<div class="grid gap-3 md:grid-cols-[1.35fr_1fr]">
    <div class="flex flex-col gap-3">
        <section class="panel p-3 md:p-3.5">
            <h2 class="label mb-3">BY_CARD · 各卡消費</h2>
            {#if cards.length === 0}
                <p class="m-0 text-mute">這個月沒有消費。</p>
            {/if}
            <div class="flex flex-col gap-2.5">
                {#each cards as card (`${card.institution}-${card.cardLast4}`)}
                    <a
                        class="flex flex-col gap-1 text-ink hover:text-ink"
                        href={resolve(`/transactions?m=${data.month}&kind=purchase&card=${card.institution}${card.cardLast4 ? `:${card.cardLast4}` : ""}`)}
                    >
                        <span class="flex justify-between gap-2">
                            <span>{cardLabel(card.institution, card.cardLast4)} <span class="text-mute">{institution(card.institution).name}</span></span>
                            <span>{formatAmount(card.amount)} <span class="text-mute">{approx(spend) > 0 ? Math.round((approx(card.amount) / approx(spend)) * 100) : 0}%</span></span>
                        </span>
                        <Bar percent={(approx(card.amount) / topCard) * 100} />
                    </a>
                {/each}
            </div>
        </section>

        <section class="panel p-3 md:p-3.5">
            <h2 class="label mb-1">BY_KIND · 種類</h2>
            <table class="w-full border-collapse">
                <thead>
                    <tr class="text-left text-mute">
                        <th class="py-2 pr-2 font-medium">KIND</th>
                        <th class="py-2 pr-2 text-right font-medium">ROWS</th>
                        <th class="py-2 text-right font-medium">TWD</th>
                    </tr>
                </thead>
                <tbody>
                    {#each kindOrder.map(kindTotal).filter(k => k !== undefined) as k (k.kind)}
                        <tr class="border-t border-rule">
                            <td class="py-2 pr-2">
                                <a class="text-dim hover:text-ink" href={resolve(`/transactions?m=${data.month}&kind=${k.kind}`)}>{kinds[k.kind].short}
                                    <span class="text-mute">{kinds[k.kind].label}</span></a>
                            </td>
                            <td class="py-2 pr-2 text-right text-dim">{k.count}</td>
                            <td class="py-2 text-right {tone[kinds[k.kind].tone]}">{formatAmount(k.amount)}</td>
                        </tr>
                    {:else}
                        <tr class="border-t border-rule"><td colspan="3" class="py-2 text-mute">沒有資料</td></tr>
                    {/each}
                </tbody>
            </table>
        </section>
    </div>

    <section class="panel p-3 md:p-3.5">
        <div class="mb-1 flex items-baseline justify-between">
            <h2 class="label">STATEMENTS · 最近的帳單</h2>
            <a href={resolve("/statements")} class="text-[12px]">all →</a>
        </div>
        {#each data.documents.slice(0, 8) as doc (doc.id)}
            {@const statement = byDocument.get(doc.id)}
            <a
                href={statement ? resolve("/statements/[id]", { id: String(statement.id) }) : resolve("/upload")}
                class="flex min-h-11 flex-col gap-0.5 border-t border-rule py-2.5 text-ink hover:text-ink"
            >
                <span>
                    <Tag status={documentStatus(doc)} />
                    {#if statement}
                        {institution(statement.institution).name} {monthOf(statement.closingDate)}
                    {:else}
                        {doc.filename}
                    {/if}
                </span>
                <span class="text-[12px] text-mute">
                    {#if statement}
                        {statement.transactionCount} 筆 · {reconciliation(statement)} · {shortDate(statement.dueDate).replace("-", "/")} 到期 {formatAmount(statement.totalDue)}
                    {:else if doc.status === "pending"}
                        parsing… · {formatBytes(doc.sizeBytes)}
                    {:else}
                        {doc.error ?? doc.status}
                    {/if}
                </span>
            </a>
        {:else}
            <p class="m-0 border-t border-rule pt-2.5 text-mute">還沒有帳單。<a href={resolve("/upload")}>上傳第一份 →</a></p>
        {/each}
    </section>
</div>
