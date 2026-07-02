<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import "$lib/mcat/theme.scss";

    import ScoreBar from "$lib/mcat/ScoreBar.svelte";
    import QuestionCard from "./QuestionCard.svelte";
    import { scoreSection, sectionQuestions } from "./scoring";
    import { compositionSummary, FULL_LENGTH_SECTIONS, FULL_LENGTH_TOTAL, PRACTICE_TESTS } from "./tests";
    import type { OptionLetter, PracticeTest, Question } from "./types";

    type View = "list" | "take" | "results";

    // When true, this window is the dedicated full-length entry point: the list
    // view offers only the full-length exam. Otherwise it lists the topical
    // tests. Set from the `?mode=full-length` query param by the route.
    export let fullLength = false;

    let view: View = "list";
    // One section for a topical test; the four MCAT sections for a full-length.
    let sections: PracticeTest[] = [];
    let isFullLength = false;
    // Question id -> chosen option letter.
    let answers: Record<string, OptionLetter> = {};

    const SECTION_LABEL: Record<string, string> = {
        "chem-phys": "Chemical & Physical Foundations",
        "cars": "Critical Analysis & Reasoning Skills (CARS)",
        "bio-biochem": "Biological & Biochemical Foundations",
        "psych-soc": "Psychological, Social & Biological Foundations",
    };

    function startTest(test: PracticeTest): void {
        sections = [test];
        isFullLength = false;
        answers = {};
        view = "take";
        scrollTop();
    }

    function startFullLength(): void {
        sections = FULL_LENGTH_SECTIONS;
        isFullLength = true;
        answers = {};
        view = "take";
        scrollTop();
    }

    function backToList(): void {
        sections = [];
        answers = {};
        view = "list";
        scrollTop();
    }

    function select(question: Question, letter: OptionLetter): void {
        answers = { ...answers, [question.id]: letter };
    }

    function submit(): void {
        // Performance scoring is disabled for now, so results aren't recorded to
        // the performance model — we just show the local score for this test.
        view = "results";
        scrollTop();
    }

    function retake(): void {
        answers = {};
        view = "take";
        scrollTop();
    }

    function scrollTop(): void {
        // Runs in the browser only (ssr disabled for this app).
        if (typeof window !== "undefined") {
            window.scrollTo({ top: 0 });
        }
    }

    // ---- derived state -------------------------------------------------
    $: flatQuestions = sections.flatMap((s) => sectionQuestions(s));
    $: answeredCount = flatQuestions.filter((q) => answers[q.id] != null).length;
    $: totalCount = flatQuestions.length;
    $: correctCount = flatQuestions.filter((q) => answers[q.id] === q.correct).length;
    $: scorePct = totalCount === 0 ? 0 : Math.round((correctCount / totalCount) * 100);
    $: scoreFraction = totalCount === 0 ? 0 : correctCount / totalCount;
    $: sectionScores = sections.map((s) => scoreSection(s, answers));
    $: scaledTotal = sectionScores.reduce((n, s) => n + s.scaled, 0);
    $: examTitle = isFullLength ? "Full-Length Practice Exam" : (sections[0]?.section ?? "");

    // Number each question in display order for stable "Q1..Qn" labels.
    $: numberOf = (() => {
        const map: Record<string, number> = {};
        flatQuestions.forEach((q, i) => (map[q.id] = i + 1));
        return map;
    })();
</script>

<div class="mcat">
    <div class="practice-tests">
        {#if view === "list"}
            <header class="page-head">
                <h1>{fullLength ? "Full-length practice exam" : "Practice tests"}</h1>
                <p class="subtitle">
                    {#if fullLength}
                        Take a full-length exam that mirrors the real MCAT — all four sections
                        in order. Submit to see your score, an approximate scaled score, and
                        full explanations — take it as a check-in, not a verdict.
                    {:else}
                        Drill a single MCAT section. Submit to see your score, an approximate
                        scaled score, and full explanations — take it as a check-in, not a
                        verdict.
                    {/if}
                </p>
            </header>

            {#if fullLength}
                <button class="full-length-card" on:click={startFullLength}>
                    <span class="badge">Full-length</span>
                    <span class="fl-title">MCAT Full-Length Exam</span>
                    <span class="fl-detail">
                        {FULL_LENGTH_TOTAL} questions · 4 sections · Chem/Phys → CARS → Bio/Biochem → Psych/Soc
                    </span>
                    <span class="start">Start full-length →</span>
                </button>
            {:else}
                <h2 class="section-title">Topical tests</h2>
                <div class="test-grid">
                    {#each PRACTICE_TESTS as test (test.test_id)}
                        <button class="test-card" on:click={() => startTest(test)}>
                            <span class="section">{test.section}</span>
                            <span class="composition">{compositionSummary(test)}</span>
                            <span class="start">Start test →</span>
                        </button>
                    {/each}
                </div>
            {/if}
        {:else if view === "take"}
            <header class="page-head sticky">
                <button class="link-btn" on:click={backToList}>← Back to tests</button>
                <div class="progress">{answeredCount} / {totalCount} answered</div>
            </header>

            <h1 class="test-title">{examTitle}</h1>

            {#each sections as section (section.test_id)}
                {#if isFullLength}
                    <div class="section-banner">
                        <h2>{SECTION_LABEL[section.section_code] ?? section.section}</h2>
                        <span>{compositionSummary(section)}</span>
                    </div>
                {/if}

                {#each section.passages as passage (passage.passage_id)}
                    <section class="passage">
                        <h2 class="passage-title">{passage.title}</h2>
                        <div class="passage-text">{passage.passage_text}</div>
                        {#each passage.questions as q (q.id)}
                            <QuestionCard
                                question={q}
                                index={numberOf[q.id]}
                                selected={answers[q.id] ?? null}
                                onSelect={(letter) => select(q, letter)}
                            />
                        {/each}
                    </section>
                {/each}

                {#if section.discrete_questions.length}
                    <section class="passage">
                        <h2 class="passage-title">Discrete Questions</h2>
                        {#each section.discrete_questions as q (q.id)}
                            <QuestionCard
                                question={q}
                                index={numberOf[q.id]}
                                selected={answers[q.id] ?? null}
                                onSelect={(letter) => select(q, letter)}
                            />
                        {/each}
                    </section>
                {/if}
            {/each}

            <div class="submit-bar">
                <div class="submit-note">
                    {#if answeredCount < totalCount}
                        {totalCount - answeredCount} question(s) still unanswered — you can still submit.
                    {:else}
                        All questions answered.
                    {/if}
                </div>
                <button class="primary" on:click={submit}>Submit exam</button>
            </div>
        {:else if view === "results"}
            <header class="page-head">
                <button class="link-btn" on:click={backToList}>← Back to tests</button>
            </header>

            <div class="scorecard">
                {#if isFullLength}
                    <div class="score-big">{scaledTotal}</div>
                    <div class="score-detail">
                        approx. scaled score (472–528) · {correctCount}/{totalCount} correct ({scorePct}%)
                    </div>
                    <div class="scorecard-bar">
                        <ScoreBar label="Overall correct" value={scoreFraction} />
                    </div>
                {:else}
                    <ScoreBar
                        label="Your score"
                        value={scoreFraction}
                        caption={`${correctCount} / ${totalCount} correct · approx. scaled ${sectionScores[0]?.scaled} (118–132)`}
                    />
                {/if}
                <h2 class="test-title in-card">{examTitle}</h2>
                <button class="secondary" on:click={retake}>Retake</button>
            </div>

            {#if isFullLength}
                <section class="panel">
                    <h2 class="section-title tight">Section breakdown</h2>
                    <div class="breakdown">
                        {#each sectionScores as s (s.sectionCode)}
                            <div class="breakdown-row">
                                <div class="bd-name">{SECTION_LABEL[s.sectionCode] ?? s.section}</div>
                                <div class="bd-bar">
                                    <ScoreBar
                                        label={SECTION_LABEL[s.sectionCode] ?? s.section}
                                        value={s.total === 0 ? 0 : s.correct / s.total}
                                        size="sm"
                                    />
                                </div>
                                <div class="bd-meta">
                                    <span class="muted">{s.correct}/{s.total}</span>
                                    <span class="chip">scaled {s.scaled}</span>
                                </div>
                            </div>
                        {/each}
                    </div>
                </section>
            {/if}

            <p class="scaled-note">
                Scaled scores are a documented linear approximation of the MCAT 118–132 scale — AAMC's
                exact raw-to-scaled curves are not public, so treat these as estimates.
            </p>

            {#each sections as section (section.test_id)}
                {#if isFullLength}
                    <div class="section-banner">
                        <h2>{SECTION_LABEL[section.section_code] ?? section.section}</h2>
                    </div>
                {/if}
                {#each section.passages as passage (passage.passage_id)}
                    <section class="passage">
                        <h2 class="passage-title">{passage.title}</h2>
                        <div class="passage-text">{passage.passage_text}</div>
                        {#each passage.questions as q (q.id)}
                            <QuestionCard
                                question={q}
                                index={numberOf[q.id]}
                                selected={answers[q.id] ?? null}
                                graded={true}
                                onSelect={() => {}}
                            />
                        {/each}
                    </section>
                {/each}
                {#if section.discrete_questions.length}
                    <section class="passage">
                        <h2 class="passage-title">Discrete Questions</h2>
                        {#each section.discrete_questions as q (q.id)}
                            <QuestionCard
                                question={q}
                                index={numberOf[q.id]}
                                selected={answers[q.id] ?? null}
                                graded={true}
                                onSelect={() => {}}
                            />
                        {/each}
                    </section>
                {/if}
            {/each}

            <div class="submit-bar">
                <button class="secondary" on:click={backToList}>Back to tests</button>
                <button class="primary" on:click={retake}>Retake</button>
            </div>
        {/if}
    </div>
</div>

<style lang="scss">
    .practice-tests {
        max-width: 820px;
        margin: 0 auto;
        padding: 2rem 1.25rem 3rem;
        color: var(--mcat-ink);
    }
    .page-head {
        margin-bottom: 1.5rem;
    }
    .page-head.sticky {
        position: sticky;
        top: 0;
        z-index: 5;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.7rem 0;
        margin-bottom: 0.5rem;
        background: color-mix(in srgb, var(--mcat-canvas), transparent 8%);
        backdrop-filter: blur(6px);
        border-bottom: 1px solid var(--mcat-border);
    }
    h1 {
        margin: 0 0 0.4rem;
        font-size: clamp(1.6rem, 1.2rem + 1.4vw, 2.1rem);
        font-weight: 800;
        letter-spacing: -0.01em;
        text-wrap: balance;
    }
    .subtitle {
        margin: 0;
        max-width: 64ch;
        line-height: 1.55;
        color: var(--mcat-ink-soft);
    }
    .test-title {
        font-size: 1.3rem;
        font-weight: 700;
        margin: 1rem 0 1.25rem;
    }
    .test-title.in-card {
        margin: 0.75rem 0 1rem;
        font-size: 1.05rem;
        color: var(--mcat-ink-soft);
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        margin: 1.75rem 0 0.9rem;
    }
    .section-title.tight {
        margin-top: 0;
    }

    // ---- full-length card ----------------------------------------------
    .full-length-card {
        width: 100%;
        text-align: left;
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        padding: 1.4rem 1.5rem;
        border: 1px solid transparent;
        border-radius: var(--mcat-radius-lg);
        background: linear-gradient(
            135deg,
            var(--mcat-sage-tint),
            var(--mcat-sky-tint)
        );
        cursor: pointer;
        color: var(--mcat-ink);
        font: inherit;
        box-shadow: var(--mcat-shadow);
        transition:
            transform 0.16s var(--mcat-ease),
            box-shadow 0.16s var(--mcat-ease);

        &:hover {
            transform: translateY(-2px);
            box-shadow: var(--mcat-shadow-lift);
        }
        &:focus-visible {
            outline: 2px solid var(--mcat-sage-ink);
            outline-offset: 2px;
        }
    }
    .badge {
        align-self: flex-start;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        padding: 0.2rem 0.65rem;
        border-radius: var(--mcat-radius-pill);
        background: var(--mcat-primary);
        color: var(--mcat-primary-ink);
    }
    .fl-title {
        font-weight: 800;
        font-size: 1.25rem;
    }
    .fl-detail {
        color: var(--mcat-ink-soft);
        font-size: 0.9rem;
    }

    // ---- landing grid --------------------------------------------------
    .test-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1rem;
    }
    .test-card {
        text-align: left;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding: 1.15rem 1.25rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        background: var(--mcat-surface);
        cursor: pointer;
        color: var(--mcat-ink);
        font: inherit;
        box-shadow: var(--mcat-shadow);
        transition:
            border-color 0.16s var(--mcat-ease),
            transform 0.16s var(--mcat-ease),
            box-shadow 0.16s var(--mcat-ease);

        &:hover {
            border-color: var(--mcat-sage);
            transform: translateY(-2px);
            box-shadow: var(--mcat-shadow-lift);
        }
        &:focus-visible {
            outline: 2px solid var(--mcat-sage-ink);
            outline-offset: 2px;
        }
    }
    .section {
        font-weight: 700;
        font-size: 1.05rem;
        line-height: 1.35;
    }
    .composition {
        color: var(--mcat-ink-soft);
        font-size: 0.88rem;
    }
    .start {
        margin-top: 0.25rem;
        font-weight: 700;
        color: var(--mcat-sage-ink);
        font-size: 0.9rem;
    }

    // ---- section banner (full-length) ----------------------------------
    .section-banner {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
        margin: 1.75rem 0 1rem;
        padding-bottom: 0.55rem;
        border-bottom: 2px solid var(--mcat-sage);

        h2 {
            margin: 0;
            font-size: 1.15rem;
            font-weight: 700;
        }
        span {
            color: var(--mcat-ink-soft);
            font-size: 0.85rem;
        }
    }

    // ---- passages ------------------------------------------------------
    .passage {
        margin-bottom: 1.75rem;
    }
    .passage-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0 0 0.6rem;
    }
    .passage-text {
        padding: 1rem 1.15rem;
        margin-bottom: 1rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius);
        background: var(--mcat-inset);
        line-height: 1.65;
        white-space: pre-wrap;
    }

    // ---- progress / submit --------------------------------------------
    .progress {
        font-variant-numeric: tabular-nums;
        font-weight: 700;
        color: var(--mcat-ink-soft);
    }
    .submit-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
        margin-top: 1.5rem;
        padding-top: 1.25rem;
        border-top: 1px solid var(--mcat-border);
    }
    .submit-note {
        color: var(--mcat-ink-soft);
        font-size: 0.9rem;
    }

    // ---- results scorecard --------------------------------------------
    .scorecard {
        text-align: center;
        padding: 1.75rem 1.5rem;
        margin-bottom: 1.25rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        background: var(--mcat-surface);
        box-shadow: var(--mcat-shadow);
    }
    .score-big {
        font-size: 3.25rem;
        font-weight: 800;
        line-height: 1;
        font-variant-numeric: tabular-nums;
        color: var(--mcat-sage-ink);
    }
    .score-detail {
        color: var(--mcat-ink-soft);
        margin-top: 0.4rem;
        font-size: 1rem;
    }
    .scorecard-bar {
        max-width: 30rem;
        margin: 1.1rem auto 0;
        text-align: left;
    }

    // ---- section breakdown --------------------------------------------
    .panel {
        padding: 1.4rem 1.5rem;
        margin-bottom: 1.25rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        background: var(--mcat-surface);
        box-shadow: var(--mcat-shadow);
    }
    .breakdown {
        display: flex;
        flex-direction: column;
    }
    .breakdown-row {
        display: grid;
        grid-template-columns: minmax(8rem, 1.2fr) minmax(7rem, 1.6fr) auto;
        align-items: center;
        gap: 0.6rem 1rem;
        padding: 0.65rem 0;
        border-bottom: 1px solid var(--mcat-border);

        &:last-child {
            border-bottom: none;
        }
    }
    .bd-name {
        font-weight: 600;
        font-size: 0.9rem;
    }
    .bd-bar {
        min-width: 0;
    }
    .bd-meta {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 0.6rem;
        font-variant-numeric: tabular-nums;
    }
    .chip {
        padding: 0.15rem 0.6rem;
        border-radius: var(--mcat-radius-pill);
        background: var(--mcat-sage-tint);
        color: var(--mcat-sage-ink);
        font-weight: 700;
        font-size: 0.8rem;
        white-space: nowrap;
    }
    .muted {
        color: var(--mcat-ink-soft);
        font-size: 0.85rem;
        white-space: nowrap;
    }
    .scaled-note {
        font-size: 0.8rem;
        color: var(--mcat-ink-faint);
        line-height: 1.55;
    }

    // ---- buttons -------------------------------------------------------
    button.primary,
    button.secondary {
        border-radius: var(--mcat-radius-pill);
        padding: 0.6rem 1.4rem;
        font-weight: 700;
        font-size: 0.95rem;
        font-family: inherit;
        cursor: pointer;
        border: 1px solid transparent;
        transition:
            transform 0.12s var(--mcat-ease),
            background 0.16s var(--mcat-ease),
            box-shadow 0.16s var(--mcat-ease);
    }
    button.primary {
        background: var(--mcat-primary);
        color: var(--mcat-primary-ink);
        box-shadow: var(--mcat-shadow);
    }
    button.primary:hover {
        background: var(--mcat-primary-hover);
        transform: translateY(-1px);
        box-shadow: var(--mcat-shadow-lift);
    }
    button.secondary {
        background: var(--mcat-surface);
        color: var(--mcat-ink);
        border-color: var(--mcat-border-strong);
    }
    button.secondary:hover {
        background: var(--mcat-inset);
    }
    button.primary:focus-visible,
    button.secondary:focus-visible {
        outline: 2px solid var(--mcat-sage-ink);
        outline-offset: 2px;
    }
    .link-btn {
        background: none;
        border: none;
        color: var(--mcat-sage-ink);
        cursor: pointer;
        font: inherit;
        font-weight: 700;
        padding: 0.2rem 0;
    }
    .link-btn:hover {
        text-decoration: underline;
    }

    @media (max-width: 33rem) {
        .breakdown-row {
            grid-template-columns: 1fr;
            gap: 0.35rem;
        }
        .bd-meta {
            justify-content: flex-start;
        }
    }
</style>
