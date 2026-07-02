<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<!--
    "Growth Garden" coverage map for the MCAT readiness dashboard.

    Each MCAT section is a garden "bed"; each subtopic is a "plant" whose growth
    stage (seed → sprout → bud → bloom) and colour reflect the student's comfort.
    Comfort uses the app's calm blue→green score gradient (never red); an
    unstudied topic is a soft dashed "seed", read as an invitation, not a
    failure. Beds start collapsed (progressive disclosure); expand one to reveal
    its plants, and hover / focus / tap a plant for an honest detail popover.

    Read-only over data the dashboard already loads (readiness + performance) —
    no backend calls here. Reuses the `.mcat` tokens + the ScoreBar value→colour
    technique; needs no d3.
-->
<script lang="ts">
    import type {
        PerformanceQueryResponse,
        ReadinessQueryResponse,
        TopicReadiness,
    } from "@generated/anki/mcat_pb";

    export let readiness: ReadinessQueryResponse;
    export let performance: PerformanceQueryResponse;

    // Growth-stage thresholds on the 0..1 comfort (readiness) scale.
    const BUD = 0.34;
    const BLOOM = 0.67;

    type Stage = "seed" | "sprout" | "bud" | "bloom";
    type Accent = "sky" | "blush" | "sage";

    // The 4 canonical sections, always rendered as beds (topics are discovered
    // per user, so a bed can legitimately be empty). Accent mirrors the model
    // cards above (sky / blush / sage).
    const SECTIONS: { code: string; label: string; accent: Accent }[] = [
        { code: "chem-phys", label: "Chem / Phys", accent: "sky" },
        { code: "cars", label: "CARS", accent: "blush" },
        { code: "bio-biochem", label: "Bio / Biochem", accent: "sage" },
        { code: "psych-soc", label: "Psych / Soc", accent: "sky" },
    ];

    const STAGE_LABEL: Record<Stage, string> = {
        seed: "Not planted yet",
        sprout: "Sprouting",
        bud: "Budding",
        bloom: "Blooming",
    };

    interface Plant {
        topic: string;
        subtopic: string;
        comfort: number | null; // null = abstain / no evidence
        pct: number; // 0..100 for the colour-mix (0 when abstaining)
        stage: Stage;
        rangeLow: number;
        rangeHigh: number;
        hasMemory: boolean;
        hasTopical: boolean;
        hasFullLength: boolean;
        topical: number;
        fullLength: number;
        hint: string; // encouraging "what unlocks this" line for the seed state
        aria: string;
    }

    interface Bed {
        code: string;
        label: string;
        accent: Accent;
        plants: Plant[];
        bedComfort: number | null; // mean readiness of non-abstaining plants
        counts: Record<Stage, number>;
        scaled: number | null; // section scaled score when tested
    }

    function stageFor(comfort: number | null): Stage {
        if (comfort == null) {
            return "seed";
        }
        if (comfort < BUD) {
            return "sprout";
        }
        if (comfort < BLOOM) {
            return "bud";
        }
        return "bloom";
    }

    function prettifyTopic(tag: string): string {
        const seg = tag.split("::")[2] ?? "";
        return seg
            .replace(/[-_]/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase())
            .trim();
    }

    // Encouraging invitation for an abstaining topic — which gate to clear next.
    function unlockHint(t: TopicReadiness): string {
        if (!t.hasCompletedFullLength) {
            return "A full-length exam unlocks readiness here.";
        }
        if (t.topicalTests < 1) {
            return "A topical test starts this one growing.";
        }
        if (t.reviewedCards < 5) {
            return `Study a few more cards (only ${t.reviewedCards} so far).`;
        }
        return "A little more practice will grow this.";
    }

    const pct = (v: number): string => `${Math.round(v * 100)}%`;

    function toPlant(t: TopicReadiness): Plant {
        const comfort = t.abstain ? null : t.readinessScore;
        const c = t.components;
        const subtopic = prettifyTopic(t.topic) || "General";
        const stage = stageFor(comfort);
        const aria = comfort == null
            ? `${subtopic}: not planted yet — ${unlockHint(t)}`
            : `${subtopic}: ${STAGE_LABEL[stage].toLowerCase()}, ${pct(comfort)} comfort`;
        return {
            topic: t.topic,
            subtopic,
            comfort,
            pct: comfort == null ? 0 : Math.round(comfort * 100),
            stage,
            rangeLow: t.rangeLow,
            rangeHigh: t.rangeHigh,
            hasMemory: c?.hasMemory ?? false,
            hasTopical: c?.hasTopical ?? false,
            hasFullLength: c?.hasFullLength ?? false,
            topical: c?.topical ?? 0,
            fullLength: c?.fullLength ?? 0,
            hint: unlockHint(t),
            aria,
        };
    }

    function sectionOf(tag: string): string {
        // aamc::<section>::<topic> — segment 1 is the section code.
        return tag.split("::")[1] ?? "";
    }

    $: sectionScaled = new Map(
        performance.sections
            .filter((s) => !s.abstain && !s.notTested)
            .map((s) => [s.sectionCode, s.scaledScore]),
    );

    $: beds = SECTIONS.map((sec): Bed => {
        const plants = readiness.topics
            .filter((t) => t.topic && sectionOf(t.topic) === sec.code)
            .map(toPlant)
            .sort((a, b) => {
                // Blooms first, seeds last; then alphabetical within a stage.
                const order: Record<Stage, number> = { bloom: 0, bud: 1, sprout: 2, seed: 3 };
                return order[a.stage] - order[b.stage]
                    || a.subtopic.localeCompare(b.subtopic);
            });
        const studied = plants.filter((p) => p.comfort != null);
        const bedComfort = studied.length
            ? studied.reduce((n, p) => n + (p.comfort ?? 0), 0) / studied.length
            : null;
        const counts: Record<Stage, number> = { bloom: 0, bud: 0, sprout: 0, seed: 0 };
        for (const p of plants) {
            counts[p.stage] += 1;
        }
        return {
            ...sec,
            plants,
            bedComfort,
            counts,
            scaled: sectionScaled.get(sec.code) ?? null,
        };
    });

    // --- progressive disclosure (accordion; multiple beds may be open) --------
    let open: Record<string, boolean> = {};
    let didAutoOpen = false;
    // Open the most-planted bed once, for a friendlier first impression.
    $: if (!didAutoOpen && beds.some((b) => b.plants.length)) {
        const best = [...beds].sort((a, b) => b.plants.length - a.plants.length)[0];
        if (best && best.plants.length) {
            open = { [best.code]: true };
        }
        didAutoOpen = true;
    }
    const toggle = (code: string) => (open = { ...open, [code]: !open[code] });

    // --- plant detail popover (hover / focus / tap) ---------------------------
    let panelEl: HTMLElement;
    let detail: { plant: Plant; accent: Accent; top: number; left: number } | null = null;
    let pinned = false;

    function place(node: HTMLElement): { top: number; left: number } {
        const panel = panelEl.getBoundingClientRect();
        const r = node.getBoundingClientRect();
        const top = r.bottom - panel.top + 8;
        const left = Math.max(
            8,
            Math.min(r.left - panel.left, panel.width - 248),
        );
        return { top, left };
    }

    function showDetail(e: Event, plant: Plant, accent: Accent): void {
        detail = { plant, accent, ...place(e.currentTarget as HTMLElement) };
    }
    function hideDetail(): void {
        if (!pinned) {
            detail = null;
        }
    }
    function pinDetail(e: Event, plant: Plant, accent: Accent): void {
        if (detail && detail.plant.topic === plant.topic && pinned) {
            pinned = false;
            detail = null;
        } else {
            pinned = true;
            detail = { plant, accent, ...place(e.currentTarget as HTMLElement) };
        }
    }
    function onKey(e: KeyboardEvent): void {
        if (e.key === "Escape") {
            pinned = false;
            detail = null;
        }
    }
</script>

<svelte:window on:keydown={onKey} />

<section class="panel garden" bind:this={panelEl}>
    <h2 class="section-title">Your growth garden</h2>
    <p class="intro">
        Every topic is a seed. It sprouts as you study and blooms as you get
        comfortable — pick a section to tend its plants.
    </p>

    <div class="beds">
        {#each beds as bed (bed.code)}
            <div
                class="bed"
                style={`--bed-accent: var(--mcat-${bed.accent}); --bed-tint: var(--mcat-${bed.accent}-tint);`}
            >
                <button
                    class="bed-head"
                    aria-expanded={open[bed.code] ? "true" : "false"}
                    aria-controls={`plot-${bed.code}`}
                    on:click={() => toggle(bed.code)}
                >
                    <span class="bed-title">
                        {bed.label}
                        <span class="bed-count">{bed.plants.length} topics</span>
                    </span>

                    <span class="bed-summary">
                        {#if bed.scaled != null}
                            <span class="chip">≈ scaled {bed.scaled}</span>
                        {/if}
                        {#if bed.bedComfort != null}
                            <span
                                class="comfort-dot"
                                style={`--pct:${Math.round(bed.bedComfort * 100)}%`}
                                aria-hidden="true"
                            ></span>
                            <span class="comfort-val">{pct(bed.bedComfort)}</span>
                        {:else}
                            <span class="muted">growing</span>
                        {/if}
                        <svg class="caret" class:open={open[bed.code]} viewBox="0 0 16 16" aria-hidden="true">
                            <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                        </svg>
                    </span>
                </button>

                {#if open[bed.code]}
                    {#if bed.plants.length}
                        <ul class="plot" id={`plot-${bed.code}`}>
                            {#each bed.plants as p, i (p.topic)}
                                <li>
                                    <button
                                        class="plant"
                                        class:seed={p.stage === "seed"}
                                        style={`--pct:${p.pct}%; --i:${i};`}
                                        aria-label={p.aria}
                                        on:mouseenter={(e) => showDetail(e, p, bed.accent)}
                                        on:focus={(e) => showDetail(e, p, bed.accent)}
                                        on:mouseleave={hideDetail}
                                        on:blur={hideDetail}
                                        on:click={(e) => pinDetail(e, p, bed.accent)}
                                    >
                                        <span class="glyph" aria-hidden="true">
                                            {#if p.stage === "seed"}
                                                <svg viewBox="0 0 24 24" fill="none" stroke="var(--mcat-ink-faint)" stroke-width="1.4" stroke-linecap="round">
                                                    <ellipse cx="12" cy="15" rx="4.5" ry="5.5" stroke-dasharray="2.5 2.5" />
                                                    <path d="M12 9.5c1.5-.5 2.5-1.8 2.5-3.5" stroke-dasharray="2.5 2.5" />
                                                </svg>
                                            {:else if p.stage === "sprout"}
                                                <svg viewBox="0 0 24 24" fill="none" stroke="var(--mcat-ink-soft)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                                                    <path d="M12 21v-7" />
                                                    <path d="M12 15c-1.8 0-3.6-1.2-4-3.2 2 -.4 3.6.8 4 2.8Z" fill="var(--plant-color)" stroke="none" />
                                                    <path d="M12 14c1.6-.2 3.2-1.6 3.4-3.6-1.9-.2-3.2 1.2-3.4 3.2Z" fill="var(--plant-color)" stroke="none" />
                                                </svg>
                                            {:else if p.stage === "bud"}
                                                <svg viewBox="0 0 24 24" fill="none" stroke="var(--mcat-ink-soft)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                                                    <path d="M12 21v-9" />
                                                    <path d="M12 16c-1.9 0-3.8-1.3-4-3.4 2.1-.4 3.8.9 4 3Z" fill="var(--plant-color)" stroke="none" />
                                                    <path d="M9.8 7.4C9.8 5.5 12 3.5 12 3.5s2.2 2 2.2 3.9a2.2 2.2 0 0 1-4.4 0Z" fill="var(--plant-color)" stroke="none" />
                                                </svg>
                                            {:else}
                                                <svg viewBox="0 0 24 24" fill="none" stroke="var(--mcat-ink-soft)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                                                    <path d="M12 21v-8" />
                                                    <path d="M12 17c-1.9 0-3.8-1.3-4-3.4 2.1-.4 3.8.9 4 3Z" fill="var(--plant-color)" stroke="none" />
                                                    <g fill="var(--plant-color)" stroke="none">
                                                        <circle cx="12" cy="7" r="2.1" />
                                                        <circle cx="8.6" cy="8.4" r="2.1" />
                                                        <circle cx="15.4" cy="8.4" r="2.1" />
                                                        <circle cx="9.8" cy="5.2" r="2.1" />
                                                        <circle cx="14.2" cy="5.2" r="2.1" />
                                                    </g>
                                                    <circle cx="12" cy="6.9" r="1.5" fill="var(--mcat-surface)" stroke="none" />
                                                </svg>
                                            {/if}
                                        </span>
                                        <span class="plant-label">{p.subtopic}</span>
                                    </button>
                                </li>
                            {/each}
                        </ul>
                    {:else}
                        <div class="bed-empty" id={`plot-${bed.code}`}>
                            <span class="glyph glyph--empty" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="var(--mcat-ink-faint)" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="2.5 2.5">
                                    <path d="M4 19h16" />
                                    <ellipse cx="12" cy="15" rx="3.5" ry="4.5" />
                                </svg>
                            </span>
                            <p>No seeds planted yet — a topical test in this section starts it growing.</p>
                        </div>
                    {/if}
                {/if}
            </div>
        {/each}
    </div>

    {#if detail}
        <div
            class="detail"
            class:pinned
            style={`top:${detail.top}px; left:${detail.left}px; --bed-accent: var(--mcat-${detail.accent}); --bed-tint: var(--mcat-${detail.accent}-tint); --pct:${detail.plant.pct}%;`}
            role="tooltip"
        >
            <div class="detail-head">{detail.plant.subtopic}</div>
            <div class="detail-stage">
                <span class="stage-dot" class:seed={detail.plant.stage === "seed"}></span>
                {STAGE_LABEL[detail.plant.stage]}
            </div>
            {#if detail.plant.comfort != null}
                <div class="detail-comfort">
                    {pct(detail.plant.comfort)} comfort
                    <span class="muted">· likely {pct(detail.plant.rangeLow)}–{pct(detail.plant.rangeHigh)}</span>
                </div>
                <div class="detail-components">
                    <span class="pip" class:off={!detail.plant.hasMemory}>Memory</span>
                    <span class="pip" class:off={!detail.plant.hasTopical}>
                        Topical{#if detail.plant.hasTopical}
                            <b>≈{pct(detail.plant.topical)}</b>{/if}
                    </span>
                    <span class="pip" class:off={!detail.plant.hasFullLength}>
                        Full-length{#if detail.plant.hasFullLength}
                            <b>≈{pct(detail.plant.fullLength)}</b>{/if}
                    </span>
                </div>
                <p class="detail-note">Practice figures are approximate section-level signals.</p>
            {:else}
                <p class="detail-hint">{detail.plant.hint}</p>
            {/if}
        </div>
    {/if}
</section>

<style lang="scss">
    // ---- panel chrome (matches the sibling readiness panels) ----------------
    .panel {
        position: relative;
        margin-top: 1.75rem;
        padding: 1.4rem 1.5rem 1.5rem;
        background: var(--mcat-surface);
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        box-shadow: var(--mcat-shadow);
    }
    .section-title {
        margin: 0 0 0.35rem;
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--mcat-ink);
    }
    .intro {
        margin: 0 0 1.1rem;
        max-width: 60ch;
        font-size: 0.9rem;
        line-height: 1.5;
        color: var(--mcat-ink-soft);
    }

    // ---- beds ---------------------------------------------------------------
    .beds {
        display: flex;
        flex-direction: column;
        gap: 0.7rem;
    }
    .bed {
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius);
        background: color-mix(in srgb, var(--bed-tint), var(--mcat-surface) 45%);
        overflow: hidden;
    }
    .bed-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        width: 100%;
        padding: 0.75rem 0.95rem;
        background: none;
        border: none;
        cursor: pointer;
        font: inherit;
        color: var(--mcat-ink);
        text-align: left;

        &:hover {
            background: color-mix(in srgb, var(--bed-tint), transparent 35%);
        }
        &:focus-visible {
            outline: 2px solid var(--bed-accent);
            outline-offset: -2px;
        }
    }
    .bed-title {
        font-weight: 700;
        font-size: 1rem;
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
    }
    .bed-count {
        font-weight: 600;
        font-size: 0.8rem;
        color: var(--mcat-ink-faint);
    }
    .bed-summary {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        white-space: nowrap;
    }
    .comfort-dot {
        width: 0.85rem;
        height: 0.85rem;
        border-radius: var(--mcat-radius-pill);
        background: color-mix(in srgb, var(--mcat-score-low), var(--mcat-score-high) var(--pct));
        box-shadow: 0 0 0 1px color-mix(in srgb, var(--mcat-score-high), #000 8%) inset;
    }
    .comfort-val {
        font-weight: 700;
        font-size: 0.85rem;
        font-variant-numeric: tabular-nums;
        color: var(--mcat-ink);
    }
    .chip {
        padding: 0.12rem 0.55rem;
        border-radius: var(--mcat-radius-pill);
        background: var(--bed-tint);
        color: var(--mcat-ink);
        font-weight: 700;
        font-size: 0.78rem;
    }
    .muted {
        color: var(--mcat-ink-soft);
        font-size: 0.85rem;
    }
    .caret {
        width: 1rem;
        height: 1rem;
        color: var(--mcat-ink-soft);
        transition: transform 0.18s var(--mcat-ease);
    }
    .caret.open {
        transform: rotate(180deg);
    }

    // ---- plot of plants -----------------------------------------------------
    .plot {
        list-style: none;
        margin: 0;
        padding: 0.4rem 0.9rem 1rem;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(94px, 1fr));
        gap: 0.35rem 0.5rem;
    }
    .plot li {
        display: flex;
    }
    .plant {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.15rem;
        width: 100%;
        padding: 0.55rem 0.35rem 0.5rem;
        border: 1px solid transparent;
        border-radius: var(--mcat-radius);
        background: none;
        cursor: pointer;
        font: inherit;
        color: var(--mcat-ink-soft);
        --plant-color: color-mix(in srgb, var(--mcat-score-low), var(--mcat-score-high) var(--pct));
        animation: garden-grow var(--mcat-fill-dur) var(--mcat-ease) calc(var(--i) * 0.035s) both;

        &:hover,
        &:focus-visible {
            background: var(--bed-tint);
            border-color: color-mix(in srgb, var(--bed-accent), transparent 55%);
        }
        &:focus-visible {
            outline: 2px solid var(--bed-accent);
            outline-offset: 1px;
        }
    }
    .glyph {
        display: grid;
        place-items: center;
        width: 2.6rem;
        height: 2.6rem;

        svg {
            width: 100%;
            height: 100%;
            transform-origin: 50% 90%;
        }
    }
    .plant-label {
        font-size: 0.78rem;
        line-height: 1.2;
        font-weight: 600;
        color: var(--mcat-ink);
        text-align: center;
        overflow-wrap: anywhere;
    }
    .plant.seed .plant-label {
        color: var(--mcat-ink-faint);
        font-weight: 500;
    }

    @keyframes garden-grow {
        from {
            opacity: 0;
            transform: scale(0.6) translateY(4px);
        }
        to {
            opacity: 1;
            transform: scale(1) translateY(0);
        }
    }

    // ---- empty bed (inviting, not a failure) --------------------------------
    .bed-empty {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        padding: 0.3rem 0.95rem 1rem;
        color: var(--mcat-ink-soft);
        font-size: 0.88rem;
        line-height: 1.45;

        p {
            margin: 0;
            max-width: 46ch;
        }
    }
    .glyph--empty {
        flex: 0 0 auto;
        width: 2rem;
        height: 2rem;
    }

    // ---- detail popover -----------------------------------------------------
    .detail {
        position: absolute;
        z-index: 10;
        width: 240px;
        padding: 0.7rem 0.8rem;
        background: var(--mcat-surface);
        border: 1px solid var(--mcat-border-strong);
        border-radius: var(--mcat-radius);
        box-shadow: var(--mcat-shadow-lift);
        pointer-events: none;
        font-size: 0.85rem;
    }
    .detail.pinned {
        pointer-events: auto;
    }
    .detail-head {
        font-weight: 800;
        color: var(--mcat-ink);
        margin-bottom: 0.15rem;
    }
    .detail-stage {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        color: var(--mcat-ink-soft);
        font-weight: 600;
        margin-bottom: 0.4rem;
    }
    .stage-dot {
        width: 0.7rem;
        height: 0.7rem;
        border-radius: var(--mcat-radius-pill);
        background: color-mix(in srgb, var(--mcat-score-low), var(--mcat-score-high) var(--pct));
    }
    .stage-dot.seed {
        background: none;
        border: 1px dashed var(--mcat-ink-faint);
    }
    .detail-comfort {
        color: var(--mcat-ink);
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .detail-components {
        display: flex;
        flex-wrap: wrap;
        gap: 0.3rem;
        margin-bottom: 0.4rem;
    }
    .pip {
        padding: 0.1rem 0.45rem;
        border-radius: var(--mcat-radius-pill);
        background: var(--bed-tint);
        color: var(--mcat-ink);
        font-size: 0.72rem;
        font-weight: 700;

        b {
            font-variant-numeric: tabular-nums;
            margin-inline-start: 0.15rem;
        }
    }
    .pip.off {
        background: transparent;
        border: 1px dashed var(--mcat-border-strong);
        color: var(--mcat-ink-faint);
    }
    .detail-note {
        margin: 0;
        font-size: 0.74rem;
        color: var(--mcat-ink-faint);
        line-height: 1.35;
    }
    .detail-hint {
        margin: 0;
        color: var(--mcat-ink-soft);
        line-height: 1.4;
    }

    @media (prefers-reduced-motion: reduce) {
        .plant {
            animation: none;
        }
        .caret {
            transition: none;
        }
    }
</style>
