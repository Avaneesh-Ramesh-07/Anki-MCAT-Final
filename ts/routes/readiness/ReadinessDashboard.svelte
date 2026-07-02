<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import "$lib/mcat/theme.scss";

    import type {
        MasteryQueryResponse,
        PerformanceQueryResponse,
        ReadinessQueryResponse,
        TopicReadiness,
    } from "@generated/anki/mcat_pb";

    import ScoreBar from "$lib/mcat/ScoreBar.svelte";
    import CoverageGarden from "$lib/mcat/CoverageGarden.svelte";

    export let mastery: MasteryQueryResponse;
    export let performance: PerformanceQueryResponse;
    export let readiness: ReadinessQueryResponse;

    const pct = (v: number): string => `${Math.round(v * 100)}%`;

    const SECTION_LABEL: Record<string, string> = {
        "chem-phys": "Chem/Phys",
        cars: "CARS",
        "bio-biochem": "Bio/Biochem",
        "psych-soc": "Psych/Soc",
    };

    // Memory
    $: overall = mastery.overall;
    $: topics = [...mastery.topics].sort((a, b) => a.topic.localeCompare(b.topic));

    // Performance (Rust emits all four sections in canonical order).
    $: perfOverall = performance.overall;

    // Readiness
    $: readyOverall = readiness.overall;
    $: readyTopics = [...readiness.topics].sort((a, b) =>
        a.topic.localeCompare(b.topic),
    );

    // Group readiness topics by test section, with human-readable topic names
    // (never the raw `aamc::section::topic` tag).
    const sectionOf = (tag: string): string => tag.split("::")[1] ?? "";
    const prettyTopic = (tag: string): string =>
        (tag.split("::")[2] ?? tag)
            .replace(/[-_]/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase())
            .trim();

    $: readySections = ["chem-phys", "cars", "bio-biochem", "psych-soc"]
        .map((code) => ({
            code,
            label: SECTION_LABEL[code] ?? code,
            topics: readyTopics.filter((t) => sectionOf(t.topic) === code),
        }))
        .filter((s) => s.topics.length > 0);

    // Expandable-by-section (accordion); open the first section by default.
    let openReady: Record<string, boolean> = {};
    let didAutoOpenReady = false;
    $: if (!didAutoOpenReady && readySections.length) {
        openReady = { [readySections[0].code]: true };
        didAutoOpenReady = true;
    }
    const toggleReady = (code: string): void => {
        openReady = { ...openReady, [code]: !openReady[code] };
    };

    // "How sure" bucket from the confidence-interval width.
    function confidence(low: number, high: number): string {
        const width = high - low;
        if (width < 0.15) {
            return "High confidence";
        }
        if (width < 0.3) {
            return "Medium confidence";
        }
        return "Low confidence";
    }

    // Why a topic's readiness is abstaining (which gate failed first).
    function readinessReason(t: TopicReadiness): string {
        if (!t.hasCompletedFullLength) {
            return "no full-length yet";
        }
        if (t.topicalTests < 1) {
            return "needs a topical test";
        }
        if (t.reviewedCards < 5) {
            return `only ${t.reviewedCards} cards`;
        }
        return "not enough evidence yet";
    }
</script>

<div class="mcat">
    <div class="dashboard">
        <header class="page-head">
            <h1>Your MCAT readiness</h1>
            <svg class="underline" viewBox="0 0 200 8" aria-hidden="true">
                <path
                    d="M2 5.5 C 40 1.5, 70 1.5, 100 4 S 165 7, 198 2.5"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                    stroke-linecap="round"
                />
            </svg>
            <p class="subtitle">
                Three honest signals, side by side — no blended black-box number. This
                fills in gently as you study, one review at a time. You've got this.
            </p>
        </header>

        <div class="models">
            <!-- Memory -->
            <section
                class="model"
                style="--card-accent: var(--mcat-sky); --card-tint: var(--mcat-sky-tint);"
            >
                <div class="model-head">
                    <span class="doodle" aria-hidden="true">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <path d="M9 18h6" />
                            <path d="M10 21h4" />
                            <path
                                d="M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.3 1 2.5h6c0-1.2.3-1.8 1-2.5A6 6 0 0 0 12 3Z"
                            />
                        </svg>
                    </span>
                    <div>
                        <h2>Memory</h2>
                        <p class="question">Can you recall the facts right now?</p>
                    </div>
                </div>
                {#if overall && !overall.abstain}
                    <ScoreBar
                        label="Memory"
                        value={overall.memoryScore}
                        delay={0}
                        showLabel={false}
                        caption={`likely ${pct(overall.rangeLow)}–${pct(overall.rangeHigh)} · ${overall.reviews} cards studied`}
                    />
                    <p class="method">Comfort-augmented FSRS retrievability.</p>
                    <p class="range-note">
                        Range = a 95% confidence band from how many cards you've studied
                        — it narrows as you review more.
                    </p>
                {:else}
                    <ScoreBar label="Memory" value={null} showLabel={false} />
                    <p class="method">Study a few more cards to unlock this score.</p>
                {/if}
            </section>

            <!-- Performance -->
            <section
                class="model"
                style="--card-accent: var(--mcat-blush); --card-tint: var(--mcat-blush-tint);"
            >
                <div class="model-head">
                    <span class="doodle" aria-hidden="true">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <path d="M15.5 4.5l4 4L9 19l-4.5 1L5.5 15.5 15.5 4.5Z" />
                            <path d="M14 6l4 4" />
                        </svg>
                    </span>
                    <div>
                        <h2>Performance</h2>
                        <p class="question">
                            Can you answer new exam-style questions on topics you've
                            studied?
                        </p>
                    </div>
                </div>
                {#if perfOverall && !perfOverall.abstain}
                    <ScoreBar
                        label="Performance"
                        value={perfOverall.score}
                        delay={0.12}
                        showLabel={false}
                        caption={`likely ${pct(perfOverall.rangeLow)}–${pct(perfOverall.rangeHigh)} · tested topics only`}
                    />
                    <p class="method">
                        Recency-weighted accuracy on practice questions ·
                        {performance.sectionsTested} of 4 sections tested{#if performance.sectionsTested === 4}
                            · ≈ scaled {performance.scaledTotal}{:else if performance.sectionsTested > 0}
                            · ≈ scaled {performance.scaledTotal} (partial){/if}
                    </p>
                    <p class="range-note">
                        Range = a 95% confidence band from how many practice questions
                        you've answered — it narrows as you answer more.
                    </p>
                {:else}
                    <ScoreBar
                        label="Performance"
                        value={null}
                        abstainText="Not enough evidence yet"
                        delay={0.12}
                        showLabel={false}
                    />
                    <p class="method">
                        Take a topical practice test to unlock this score.
                    </p>
                {/if}
            </section>

            <!-- Readiness -->
            <section
                class="model"
                style="--card-accent: var(--mcat-sage); --card-tint: var(--mcat-sage-tint);"
            >
                <div class="model-head">
                    <span class="doodle" aria-hidden="true">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <path d="M6 21V4" />
                            <path d="M6 4c3-1.5 6 1.5 9 0 v7 c-3 1.5-6-1.5-9 0" />
                        </svg>
                    </span>
                    <div>
                        <h2>Readiness</h2>
                        <p class="question">What would you score today?</p>
                    </div>
                </div>
                {#if readyOverall && !readyOverall.abstain}
                    <ScoreBar
                        label="Readiness"
                        value={readyOverall.readinessScore}
                        delay={0.24}
                        showLabel={false}
                        caption={`likely ${pct(readyOverall.rangeLow)}–${pct(readyOverall.rangeHigh)}`}
                    />
                    {#if readyOverall.components}
                        <div
                            class="breakdown"
                            title="Contribution to readiness — Memory 5% · Topical 45% · Full-length 50%"
                        >
                            <span
                                class="seg mem"
                                style="flex:{Math.max(
                                    readyOverall.components.memoryContribution,
                                    0.001,
                                )}"
                            ></span>
                            <span
                                class="seg top"
                                style="flex:{Math.max(
                                    readyOverall.components.topicalContribution,
                                    0.001,
                                )}"
                            ></span>
                            <span
                                class="seg fl"
                                style="flex:{Math.max(
                                    readyOverall.components.fullLengthContribution,
                                    0.001,
                                )}"
                            ></span>
                        </div>
                    {/if}
                    <p class="method">
                        {confidence(readyOverall.rangeLow, readyOverall.rangeHigh)} · memory
                        5% · topical 45% · full-length 50%
                    </p>
                    <p class="range-note">
                        Range = your three signals' bands blended by weight; sections
                        you haven't tested count as a certain 0, which lowers it.
                    </p>
                {:else}
                    <ScoreBar
                        label="Readiness"
                        value={null}
                        abstainText="Not enough evidence yet"
                        delay={0.24}
                        showLabel={false}
                    />
                    <p class="method">
                        Take a full-length exam to unlock your readiness score.
                    </p>
                {/if}
            </section>
        </div>

        <CoverageGarden {readiness} {performance} />

        <!-- Memory by topic -->
        <section class="panel">
            <h2 class="section-title">Memory by AAMC topic</h2>
            {#if topics.length === 0}
                <div class="empty">
                    <span class="empty-doodle" aria-hidden="true">
                        <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.7"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <rect x="4" y="3" width="16" height="18" rx="2.5" />
                            <path d="M8 8h8M8 12h8M8 16h5" />
                        </svg>
                    </span>
                    <p>
                        No <code>aamc::</code>
                        -tagged cards yet. Import the sample deck (
                        <code>tools/mcat_sample.apkg</code>
                        ), or tag your cards
                        <code>aamc::section::topic</code>
                        and your topic breakdown will appear here.
                    </p>
                </div>
            {:else}
                <div class="topic-list">
                    {#each topics as t (t.topic)}
                        <div class="topic-row">
                            <div class="topic-name">{prettyTopic(t.topic)}</div>
                            <div class="topic-bar">
                                <ScoreBar
                                    label={prettyTopic(t.topic)}
                                    value={t.abstain ? null : t.memoryScore}
                                    size="sm"
                                    abstainText="not enough evidence yet"
                                />
                            </div>
                            <div class="topic-meta">
                                <span class="chip">
                                    {t.masteredCount}/{t.totalCards} mastered
                                </span>
                                <span class="muted">{t.reviews} cards studied</span>
                                {#if !t.abstain}
                                    <span class="muted">
                                        likely {pct(t.rangeLow)}–{pct(t.rangeHigh)}
                                    </span>
                                {/if}
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </section>

        <!-- Performance by section (all four, incl. "Not tested yet") -->
        <section class="panel">
            <h2 class="section-title">Performance by section</h2>
            <div class="topic-list">
                {#each performance.sections as s (s.sectionCode)}
                    <div class="topic-row">
                        <div class="topic-name">
                            {SECTION_LABEL[s.sectionCode] ?? s.sectionCode}
                        </div>
                        <div class="topic-bar">
                            <ScoreBar
                                label={s.sectionCode}
                                value={s.notTested || s.abstain ? null : s.score}
                                size="sm"
                                abstainText={s.notTested
                                    ? "Not tested yet"
                                    : "not enough evidence yet"}
                            />
                        </div>
                        <div class="topic-meta">
                            {#if !s.abstain}
                                <span class="chip">scaled {s.scaledScore}</span>
                                <span class="muted">{s.correct}/{s.answered}</span>
                            {:else if !s.notTested}
                                <span class="muted">
                                    {s.correct}/{s.answered} · thin
                                </span>
                            {/if}
                        </div>
                    </div>
                {/each}
            </div>
        </section>

        <!-- Readiness by section → topic (expandable; abstain = dashed rail, never 0%) -->
        <section class="panel">
            <h2 class="section-title">Readiness by section</h2>
            {#if readySections.length === 0}
                <div class="empty">
                    <p>
                        Readiness fills in per topic once you have card reviews, a
                        topical test, and at least one full-length exam on record.
                    </p>
                </div>
            {:else}
                <div class="rsecs">
                    {#each readySections as sec (sec.code)}
                        <div class="rsec">
                            <button
                                class="rsec-head"
                                aria-expanded={openReady[sec.code] ? "true" : "false"}
                                aria-controls={`ready-${sec.code}`}
                                on:click={() => toggleReady(sec.code)}
                            >
                                <span class="rsec-name">
                                    {sec.label}
                                    <span class="rsec-count">
                                        {sec.topics.length}
                                        {sec.topics.length === 1 ? "topic" : "topics"}
                                    </span>
                                </span>
                                <svg
                                    class="rcaret"
                                    class:open={openReady[sec.code]}
                                    viewBox="0 0 16 16"
                                    aria-hidden="true"
                                >
                                    <path
                                        d="M4 6l4 4 4-4"
                                        fill="none"
                                        stroke="currentColor"
                                        stroke-width="1.8"
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                    />
                                </svg>
                            </button>
                            {#if openReady[sec.code]}
                                <div class="topic-list" id={`ready-${sec.code}`}>
                                    {#each sec.topics as t (t.topic)}
                                        <div class="topic-row">
                                            <div class="topic-name">
                                                {prettyTopic(t.topic)}
                                            </div>
                                            <div class="topic-bar">
                                                <ScoreBar
                                                    label={prettyTopic(t.topic)}
                                                    value={t.abstain
                                                        ? null
                                                        : t.readinessScore}
                                                    size="sm"
                                                    abstainText="not enough evidence yet"
                                                />
                                            </div>
                                            <div class="topic-meta">
                                                {#if t.components}
                                                    <span
                                                        class="pips"
                                                        title="Memory · Topical · Full-length (dim = missing)"
                                                    >
                                                        <span
                                                            class="pip mem"
                                                            class:off={!t.components
                                                                .hasMemory}
                                                        >
                                                            M
                                                        </span>
                                                        <span
                                                            class="pip top"
                                                            class:off={!t.components
                                                                .hasTopical}
                                                        >
                                                            T
                                                        </span>
                                                        <span
                                                            class="pip fl"
                                                            class:off={!t.components
                                                                .hasFullLength}
                                                        >
                                                            F
                                                        </span>
                                                    </span>
                                                {/if}
                                                {#if t.abstain}
                                                    <span class="muted">
                                                        {readinessReason(t)}
                                                    </span>
                                                {:else}
                                                    <span class="muted">
                                                        likely {pct(t.rangeLow)}–{pct(
                                                            t.rangeHigh,
                                                        )}
                                                    </span>
                                                {/if}
                                            </div>
                                        </div>
                                    {/each}
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            {/if}
        </section>
    </div>
</div>

<style lang="scss">
    .dashboard {
        max-width: 900px;
        margin: 0 auto;
        padding: 2rem 1.5rem 3rem;
    }
    .page-head {
        margin-bottom: 2rem;
    }
    h1 {
        margin: 0;
        font-size: clamp(1.7rem, 1.2rem + 1.6vw, 2.3rem);
        font-weight: 800;
        letter-spacing: -0.01em;
        color: var(--mcat-ink);
        text-wrap: balance;
    }
    .underline {
        display: block;
        width: min(240px, 60%);
        height: 8px;
        margin: 0.15rem 0 0.75rem;
        color: var(--mcat-sage);
    }
    .subtitle {
        margin: 0;
        max-width: 62ch;
        font-size: 1rem;
        line-height: 1.55;
        color: var(--mcat-ink-soft);
    }

    // ---- model cards -----------------------------------------------------
    .models {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.15rem;
        margin-bottom: 2.25rem;
    }
    .model {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        padding: 1.35rem 1.4rem 1.45rem;
        background: var(--mcat-surface);
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        box-shadow: var(--mcat-shadow);
    }
    .model-head {
        display: flex;
        align-items: flex-start;
        gap: 0.8rem;
    }
    .doodle {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: var(--mcat-radius);
        background: var(--card-tint);
        color: var(--card-accent);

        svg {
            width: 1.5rem;
            height: 1.5rem;
        }
    }
    .model h2 {
        margin: 0;
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--mcat-ink);
    }
    .question {
        margin: 0.15rem 0 0;
        font-size: 0.9rem;
        line-height: 1.4;
        color: var(--mcat-ink-soft);
    }
    .method {
        margin: 0;
        font-size: 0.8rem;
        line-height: 1.45;
        color: var(--mcat-ink-faint);
    }
    // Short "where the range comes from" note. ink-soft (AA) since it's
    // meaningful explanatory text, with a hairline to set it apart from .method.
    .range-note {
        margin: 0.1rem 0 0;
        padding-top: 0.5rem;
        border-top: 1px solid var(--mcat-border);
        font-size: 0.78rem;
        line-height: 1.45;
        color: var(--mcat-ink-soft);
    }

    // ---- panels (topic / section lists) ----------------------------------
    .panel {
        margin-top: 1.75rem;
        padding: 1.4rem 1.5rem 1.5rem;
        background: var(--mcat-surface);
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        box-shadow: var(--mcat-shadow);
    }
    .section-title {
        margin: 0 0 1.1rem;
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--mcat-ink);
    }

    // ---- readiness section accordion ----------------------------------------
    .rsecs {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
    }
    .rsec {
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius);
        overflow: hidden;
    }
    .rsec-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        width: 100%;
        padding: 0.7rem 0.95rem;
        background: var(--mcat-surface-2);
        border: none;
        cursor: pointer;
        font: inherit;
        color: var(--mcat-ink);
        text-align: left;

        &:hover {
            background: var(--mcat-inset);
        }
        &:focus-visible {
            outline: 2px solid var(--mcat-sage-ink);
            outline-offset: -2px;
        }
    }
    .rsec-name {
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
        font-weight: 700;
        font-size: 1rem;
    }
    .rsec-count {
        font-weight: 600;
        font-size: 0.8rem;
        color: var(--mcat-ink-faint);
    }
    .rcaret {
        width: 1rem;
        height: 1rem;
        flex: 0 0 auto;
        color: var(--mcat-ink-soft);
        transition: transform 0.18s var(--mcat-ease);
    }
    .rcaret.open {
        transform: rotate(180deg);
    }
    .rsec .topic-list {
        padding: 0.2rem 0.95rem 0.6rem;
    }
    .rsec .topic-row:last-child {
        border-bottom: none;
    }
    @media (prefers-reduced-motion: reduce) {
        .rcaret {
            transition: none;
        }
    }

    .topic-list {
        display: flex;
        flex-direction: column;
    }
    .topic-row {
        display: grid;
        grid-template-columns: minmax(9rem, 1.1fr) minmax(7rem, 1.4fr) auto;
        align-items: center;
        gap: 0.75rem 1.1rem;
        padding: 0.7rem 0;
        border-bottom: 1px solid var(--mcat-border);

        &:last-child {
            border-bottom: none;
        }
    }
    .topic-name {
        font-weight: 600;
        font-size: 0.92rem;
        color: var(--mcat-ink);
        overflow-wrap: anywhere;
    }
    .topic-bar {
        min-width: 0;
    }
    .topic-meta {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        flex-wrap: wrap;
        gap: 0.4rem 0.7rem;
        font-size: 0.8rem;
    }
    .chip {
        padding: 0.15rem 0.6rem;
        border-radius: var(--mcat-radius-pill);
        background: var(--mcat-sage-tint);
        color: var(--mcat-sage-ink);
        font-weight: 700;
        white-space: nowrap;
    }
    .muted {
        color: var(--mcat-ink-soft);
        white-space: nowrap;
    }

    // ---- readiness component breakdown bar (5 / 45 / 50) -----------------
    .breakdown {
        display: flex;
        width: 100%;
        height: 8px;
        gap: 2px;
        border-radius: var(--mcat-radius-pill);
        overflow: hidden;
    }
    .seg {
        display: block;
        min-width: 2px;
        border-radius: var(--mcat-radius-pill);
        &.mem {
            background: var(--mcat-sky);
        }
        &.top {
            background: var(--mcat-blush);
        }
        &.fl {
            background: var(--mcat-sage);
        }
    }

    // ---- per-topic component pips (M / T / FL) ---------------------------
    .pips {
        display: inline-flex;
        gap: 0.25rem;
    }
    .pip {
        display: grid;
        place-items: center;
        width: 1.15rem;
        height: 1.15rem;
        border-radius: 999px;
        font-size: 0.62rem;
        font-weight: 700;
        color: white;
        &.mem {
            background: var(--mcat-sky);
        }
        &.top {
            background: var(--mcat-blush);
        }
        &.fl {
            background: var(--mcat-sage);
        }
        &.off {
            opacity: 0.28;
            filter: grayscale(0.5);
        }
    }

    // ---- empty state -----------------------------------------------------
    .empty {
        display: flex;
        align-items: flex-start;
        gap: 0.9rem;
        padding: 0.5rem 0;
        color: var(--mcat-ink-soft);
        line-height: 1.55;

        p {
            margin: 0;
            max-width: 60ch;
        }
    }
    .empty-doodle {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: var(--mcat-radius);
        background: var(--mcat-sky-tint);
        color: var(--mcat-sky-ink);

        svg {
            width: 1.5rem;
            height: 1.5rem;
        }
    }
    code {
        font-size: 0.85em;
        padding: 0.05rem 0.35rem;
        border-radius: 6px;
        background: var(--mcat-inset);
        color: var(--mcat-ink);
    }

    @media (max-width: 33rem) {
        .topic-row {
            grid-template-columns: 1fr;
            gap: 0.4rem;
        }
        .topic-meta {
            justify-content: flex-start;
        }
    }
</style>
