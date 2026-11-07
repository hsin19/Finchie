<script lang="ts">
import { resolve } from "$app/paths";
import { page } from "$app/state";
</script>

<section class="panel flex flex-col gap-2 p-4">
    <div><span class="whitespace-pre text-neg">[ERR ]</span> <span class="text-dim">HTTP {page.status}</span></div>
    <p class="m-0 text-ink">{page.error?.message ?? "Something went wrong"}</p>
    {#if page.status === 404}
        <p class="m-0 text-mute">找不到這個頁面或資料。<a href={resolve("/")}>← 回總覽</a></p>
    {:else}
        <!-- Once the Cloudflare Access session expires, API calls are redirected to its login page and
             fail here; a full reload goes through Access, which signs in again. -->
        <p class="m-0 text-mute">連不到 backend，或登入過期了：重新整理會重新登入。</p>
        <div>
            <button type="button" class="control" onclick={() => location.reload()}>重新整理</button>
        </div>
    {/if}
</section>
