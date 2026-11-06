<script lang="ts">
import { resolve } from "$app/paths";
import { page } from "$app/state";
</script>

<section class="panel flex flex-col gap-2 p-4">
    <div><span class="whitespace-pre text-neg">[ERR ]</span> <span class="text-dim">HTTP {page.status}</span></div>
    <p class="m-0 text-ink">{page.error?.message ?? "Something went wrong"}</p>
    <p class="m-0 text-mute">
        {#if page.status === 404}找不到這個頁面或資料。{:else}backend 可能沒有在跑：`task backend:run`。{/if}
        <a href={resolve("/")}>← 回總覽</a>
    </p>
</section>
