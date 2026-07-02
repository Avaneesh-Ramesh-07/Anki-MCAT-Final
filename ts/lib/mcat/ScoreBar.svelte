<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<!--
    A calm, loading-bar-style score meter for the MCAT surfaces.

    - Fills gently on mount (soft blue -> sage green as the score rises; never
      red). The fill colour is derived from the value, not its position, so a
      low score reads blue and a high score reads green.
    - Accessible: exposes role="progressbar" with aria-valuenow/min/max and a
      text label, so meaning never depends on colour. Honours
      prefers-reduced-motion (jumps straight to the final width).
    - `value` is 0..1, or null for the honest "not enough evidence yet" state.
    - `size="lg"` (default) shows a heading row with the big percentage;
      `size="sm"` is a compact inline bar for table cells.
-->
<script lang="ts">
    export let label: string;
    export let value: number | null = null;
    export let caption = "";
    export let abstainText = "Not enough evidence yet";
    export let size: "lg" | "sm" = "lg";
    // Seconds to wait before the fill animates — lets a group stagger gently.
    export let delay = 0;
    // Hide the visible text label (e.g. when a card heading already names it).
    // The accessible name is preserved on the track's aria-label regardless.
    export let showLabel = true;

    const clamp = (v: number): number => Math.max(0, Math.min(1, v));
    $: has = value != null && !Number.isNaN(value);
    $: v = has ? clamp(value as number) : 0;
    $: pctNum = Math.round(v * 100);
    $: pctStr = `${pctNum}%`;
    $: valueLabel = has ? `${pctNum} percent` : abstainText;
</script>

<div
    class="score-bar"
    class:sm={size === "sm"}
    class:abstain={!has}
    style={`--pct:${pctStr}; --mcat-fill-delay:${delay}s`}
>
    {#if size === "lg"}
        <div class="head" class:head--pct-only={!showLabel}>
            {#if showLabel}
                <span class="label"><slot name="icon" />{label}</span>
            {/if}
            {#if has}
                <span class="pct">{pctStr}</span>
            {:else}
                <span class="pct pct--none" aria-hidden="true">—</span>
            {/if}
        </div>
    {/if}

    <div class="row">
        <div
            class="track"
            role="progressbar"
            aria-label={`${label}: ${valueLabel}`}
            aria-valuenow={has ? pctNum : undefined}
            aria-valuemin={has ? 0 : undefined}
            aria-valuemax={has ? 100 : undefined}
        >
            {#if has}
                <div class="fill"></div>
            {/if}
        </div>
        {#if size === "sm"}
            <span class="pct-inline">{has ? pctStr : "—"}</span>
        {/if}
    </div>

    {#if caption}
        <p class="caption">{caption}</p>
    {/if}
</div>

<style lang="scss">
    .score-bar {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    .head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.75rem;
    }
    .head--pct-only {
        justify-content: flex-end;
    }
    .label {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        font-weight: 700;
        font-size: 1.05rem;
        color: var(--mcat-ink);
    }
    .pct {
        font-weight: 800;
        font-size: 2.1rem;
        line-height: 1;
        font-variant-numeric: tabular-nums;
        // colour tracks the score: reads blue when low, green when high.
        color: color-mix(
            in srgb,
            var(--mcat-sky-ink),
            var(--mcat-sage-ink) var(--pct)
        );
    }
    .pct--none {
        color: var(--mcat-ink-faint);
        font-size: 1.6rem;
    }

    .row {
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    .track {
        position: relative;
        flex: 1;
        height: 0.85rem;
        border-radius: var(--mcat-radius-pill);
        background: var(--mcat-track);
        box-shadow: inset 0 1px 2px rgba(88, 74, 54, 0.12);
        overflow: hidden;
    }
    .fill {
        height: 100%;
        width: var(--pct);
        border-radius: var(--mcat-radius-pill);
        // colour derived from the value (not position), soft top sheen on top.
        --fill-color: color-mix(
            in srgb,
            var(--mcat-score-low),
            var(--mcat-score-high) var(--pct)
        );
        background: linear-gradient(
            180deg,
            color-mix(in srgb, var(--fill-color), #fff 24%),
            var(--fill-color)
        );
        box-shadow: 0 0 0 1px color-mix(in srgb, var(--fill-color), #000 8%) inset;
        animation: mcat-fill var(--mcat-fill-dur) var(--mcat-ease) var(--mcat-fill-delay, 0s) both;
    }
    @keyframes mcat-fill {
        from {
            width: 0;
        }
        to {
            width: var(--pct);
        }
    }

    // ---- abstain: friendly, non-alarming empty rail ----------------------
    .abstain .track {
        background: repeating-linear-gradient(
            -45deg,
            var(--mcat-inset),
            var(--mcat-inset) 6px,
            transparent 6px,
            transparent 12px
        );
        border: 1px dashed var(--mcat-border-strong);
        box-shadow: none;
    }

    // ---- compact variant for table cells ---------------------------------
    .sm {
        gap: 0.25rem;
    }
    .sm .track {
        height: 0.5rem;
    }
    .pct-inline {
        min-width: 2.6rem;
        text-align: right;
        font-weight: 700;
        font-size: 0.85rem;
        font-variant-numeric: tabular-nums;
        color: var(--mcat-ink);
    }
    .sm.abstain .pct-inline {
        color: var(--mcat-ink-faint);
    }

    .caption {
        margin: 0;
        font-size: 0.85rem;
        line-height: 1.45;
        color: var(--mcat-ink-soft);
    }

    @media (prefers-reduced-motion: reduce) {
        .fill {
            animation: none;
            width: var(--pct);
        }
    }
</style>
