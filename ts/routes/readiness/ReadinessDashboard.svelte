<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import "$lib/mcat/theme.scss";

    import type { MasteryQueryResponse } from "@generated/anki/mcat_pb";

    import ScoreBar from "$lib/mcat/ScoreBar.svelte";

    export let mastery: MasteryQueryResponse;

    const pct = (v: number): string => `${Math.round(v * 100)}%`;

    $: overall = mastery.overall;
    $: topics = [...mastery.topics].sort((a, b) => a.topic.localeCompare(b.topic));
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
                Three honest signals, side by side — no blended black-box number. This fills in
                gently as you study, one review at a time. You've got this.
            </p>
        </header>

        <div class="models">
            <!-- Memory -->
            <section class="model" style="--card-accent: var(--mcat-sky); --card-tint: var(--mcat-sky-tint);">
                <div class="model-head">
                    <span class="doodle" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M9 18h6" />
                            <path d="M10 21h4" />
                            <path d="M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.3 1 2.5h6c0-1.2.3-1.8 1-2.5A6 6 0 0 0 12 3Z" />
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
                        caption={`likely ${pct(overall.rangeLow)}–${pct(overall.rangeHigh)} · ${overall.reviews} reviews`}
                    />
                    <p class="method">Comfort-augmented FSRS retrievability.</p>
                {:else}
                    <ScoreBar label="Memory" value={null} showLabel={false} />
                    <p class="method">Study a few more cards to unlock this score.</p>
                {/if}
            </section>

            <!-- Performance -->
            <section class="model" style="--card-accent: var(--mcat-blush); --card-tint: var(--mcat-blush-tint);">
                <div class="model-head">
                    <span class="doodle" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M15.5 4.5l4 4L9 19l-4.5 1L5.5 15.5 15.5 4.5Z" />
                            <path d="M14 6l4 4" />
                        </svg>
                    </span>
                    <div>
                        <h2>Performance</h2>
                        <p class="question">Can you answer new exam-style questions?</p>
                    </div>
                </div>
                <ScoreBar
                    label="Performance"
                    value={null}
                    abstainText="Not available yet"
                    delay={0.12}
                    showLabel={false}
                />
                <p class="method">Performance scoring is turned off for now.</p>
            </section>

            <!-- Readiness -->
            <section class="model" style="--card-accent: var(--mcat-sage); --card-tint: var(--mcat-sage-tint);">
                <div class="model-head">
                    <span class="doodle" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M6 21V4" />
                            <path d="M6 4c3-1.5 6 1.5 9 0 v7 c-3 1.5-6-1.5-9 0" />
                        </svg>
                    </span>
                    <div>
                        <h2>Readiness</h2>
                        <p class="question">What would you score today?</p>
                    </div>
                </div>
                <ScoreBar label="Readiness" value={null} abstainText="Not available yet" delay={0.24} showLabel={false} />
                <p class="method">Unlocks once you've logged some practice questions.</p>
            </section>
        </div>

        <!-- Memory by topic -->
        <section class="panel">
            <h2 class="section-title">Memory by AAMC topic</h2>
            {#if topics.length === 0}
                <div class="empty">
                    <span class="empty-doodle" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="4" y="3" width="16" height="18" rx="2.5" />
                            <path d="M8 8h8M8 12h8M8 16h5" />
                        </svg>
                    </span>
                    <p>
                        No <code>aamc::</code>-tagged cards yet. Import the sample deck
                        (<code>tools/mcat_sample.apkg</code>), or tag your cards
                        <code>aamc::section::topic</code> and your topic breakdown will appear here.
                    </p>
                </div>
            {:else}
                <div class="topic-list">
                    {#each topics as t (t.topic)}
                        <div class="topic-row">
                            <div class="topic-name">{t.topic}</div>
                            <div class="topic-bar">
                                <ScoreBar
                                    label={t.topic}
                                    value={t.abstain ? null : t.memoryScore}
                                    size="sm"
                                    abstainText="not enough evidence yet"
                                />
                            </div>
                            <div class="topic-meta">
                                <span class="chip">{t.masteredCount}/{t.totalCards} mastered</span>
                                <span class="muted">{t.reviews} reviews</span>
                                {#if !t.abstain}
                                    <span class="muted">likely {pct(t.rangeLow)}–{pct(t.rangeHigh)}</span>
                                {/if}
                            </div>
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
