<script lang="ts">
// A dashed meter, like a progress bar drawn with "▮▮▮▮". Decorative: the number sits beside it.
let { percent, color = "var(--color-accent)", height = 8 }: { percent: number; color?: string; height?: number; } = $props();
const width = $derived(Math.max(0, Math.min(100, percent)));
</script>

<div aria-hidden="true" class="w-full" style:height="{height}px" style:background="repeating-linear-gradient(90deg, var(--color-line) 0 5px, transparent 5px 7px)">
    <div style:height="{height}px" style:width="{width}%" style:background="repeating-linear-gradient(90deg, {color} 0 5px, transparent 5px 7px)"></div>
</div>
