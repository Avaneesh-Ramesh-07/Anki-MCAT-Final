<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import "$lib/mcat/theme.scss";

    import { bridgeCommand } from "@tslib/bridgecommand";
    import { gradeFreeResponse, recordPracticeResult } from "@generated/backend";
    import type { GradeFreeResponseResponse } from "@generated/anki/mcat_pb";
    import { ExamKind } from "@generated/anki/mcat_pb";

    import ScoreBar from "$lib/mcat/ScoreBar.svelte";
    import FreeResponseCard from "./FreeResponseCard.svelte";
    import QuestionCard from "./QuestionCard.svelte";
    import { formatSci } from "./sci-format";
    import type { FrqGrade } from "./scoring";
    import {
        frqTopicTallies,
        mergeTallies,
        scoreSection,
        sectionQuestions,
        topicTallies,
    } from "./scoring";
    import {
        compositionSummary,
        FULL_LENGTH_SECTIONS,
        FULL_LENGTH_TOTAL,
        PRACTICE_TESTS,
    } from "./tests";
    import type {
        FreeResponseQuestion,
        OptionLetter,
        PracticeTest,
        Question,
    } from "./types";

    type View = "list" | "take" | "results";

    // When true, this window is the dedicated full-length entry point: the list
    // view offers only the full-length exam. Otherwise it lists the topical
    // tests. Set from the `?mode=full-length` query param by the route.
    export let fullLength = false;
    // Whether AI grading is on (the Home-page toggle, passed via the `?ai=`
    // query param). Only used to label each FRQ "AI-graded" vs "Keyword match" —
    // the actual grading mode is decided in the Rust grader from the same config.
    export let aiGrading = true;

    let view: View = "list";
    // One section for a topical test; the four MCAT sections for a full-length.
    let sections: PracticeTest[] = [];
    let isFullLength = false;
    // Question id -> chosen option letter.
    let answers: Record<string, OptionLetter> = {};
    // Free-response state: id -> typed answer / AI grade / grading-in-flight.
    let frqAnswers: Record<string, string> = {};
    let frqGrades: Record<string, GradeFreeResponseResponse> = {};
    let frqPending: Record<string, boolean> = {};

    const SECTION_LABEL: Record<string, string> = {
        "chem-phys": "Chemical & Physical Foundations",
        cars: "Critical Analysis & Reasoning Skills (CARS)",
        "bio-biochem": "Biological & Biochemical Foundations",
        "psych-soc": "Psychological, Social & Biological Foundations",
    };

    function startTest(test: PracticeTest): void {
        sections = [test];
        isFullLength = false;
        answers = {};
        frqAnswers = {};
        frqGrades = {};
        frqPending = {};
        view = "take";
        scrollTop();
    }

    function startFullLength(): void {
        sections = FULL_LENGTH_SECTIONS;
        isFullLength = true;
        answers = {};
        frqAnswers = {};
        frqGrades = {};
        frqPending = {};
        view = "take";
        scrollTop();
    }

    function backToList(): void {
        sections = [];
        answers = {};
        frqAnswers = {};
        frqGrades = {};
        frqPending = {};
        view = "list";
        scrollTop();
    }

    function select(question: Question, letter: OptionLetter): void {
        answers = { ...answers, [question.id]: letter };
    }

    // Map the JSON rubric (snake_case) to the grader RPC's proto shape (camelCase).
    function toProtoRubric(q: FreeResponseQuestion) {
        return q.rubric.map((c) => ({
            id: c.id,
            description: c.description,
            points: c.points,
            requiredConcepts: c.required_concepts,
            disqualifiers: c.disqualifiers,
            keywords: c.keywords ?? [],
        }));
    }

    // Grade every FRQ via the backend AI grader (in parallel). The grader gets
    // only the prompt + rubric + answer — never the reference answer. Only
    // successfully-graded FRQ contribute topic evidence.
    async function gradeFrqs(frqs: FreeResponseQuestion[]): Promise<FrqGrade[]> {
        const graded: FrqGrade[] = [];
        await Promise.all(
            frqs.map(async (q) => {
                frqPending = { ...frqPending, [q.id]: true };
                try {
                    const g = await gradeFreeResponse({
                        prompt: q.prompt,
                        answer: frqAnswers[q.id] ?? "",
                        maxPoints: q.max_points,
                        rubric: toProtoRubric(q),
                        model: "",
                    });
                    frqGrades = { ...frqGrades, [q.id]: g };
                    if (g.graded) {
                        graded.push({
                            topic_tags: q.topic_tags,
                            pointsAwarded: g.pointsAwarded,
                            maxPoints: g.maxPoints,
                        });
                    }
                } catch (e) {
                    console.error("FRQ grading failed", q.id, e);
                } finally {
                    frqPending = { ...frqPending, [q.id]: false };
                }
            }),
        );
        return graded;
    }

    // Re-grade a single FRQ from the results screen — used by the card's Retry
    // affordance when the grader was unavailable at submit (or the student wants
    // another read). This refreshes the visible grade only; it deliberately does
    // NOT re-post to the performance model, so a retry can never double-count a
    // topic's evidence.
    async function regradeFrq(q: FreeResponseQuestion): Promise<void> {
        frqPending = { ...frqPending, [q.id]: true };
        try {
            const g = await gradeFreeResponse({
                prompt: q.prompt,
                answer: frqAnswers[q.id] ?? "",
                maxPoints: q.max_points,
                rubric: toProtoRubric(q),
                model: "",
            });
            frqGrades = { ...frqGrades, [q.id]: g };
        } catch (e) {
            console.error("FRQ regrade failed", q.id, e);
        } finally {
            frqPending = { ...frqPending, [q.id]: false };
        }
    }

    async function submit(): Promise<void> {
        // Show the local MCQ score immediately; FRQ grading + recording to the
        // performance model are best-effort and must never block the results screen.
        view = "results";
        scrollTop();
        const mcqTallies = sections.flatMap((s) => topicTallies(s, answers));
        const frqs = sections.flatMap((s) => s.free_response_questions ?? []);
        let frqGradeList: FrqGrade[] = [];
        try {
            frqGradeList = await gradeFrqs(frqs);
        } catch (e) {
            console.error("FRQ grading batch failed", e);
        }
        try {
            const merged = mergeTallies(mcqTallies, frqTopicTallies(frqGradeList));
            if (isFullLength) {
                // One submission spanning all four sections; each tag carries its
                // own section, so the engine re-splits it via the tag prefix.
                await recordPracticeResult({
                    testId: "full-length",
                    sectionCode: "",
                    examKind: ExamKind.FULL_LENGTH,
                    examId: `fl-${Date.now()}`,
                    topicResults: merged,
                });
            } else {
                const test = sections[0];
                await recordPracticeResult({
                    testId: test.test_id,
                    sectionCode: test.section_code,
                    examKind: ExamKind.TOPICAL,
                    examId: `${test.test_id}-${Date.now()}`,
                    topicResults: merged,
                });
            }
        } catch (e) {
            console.error("failed to record practice result", e);
        }
    }

    function retake(): void {
        answers = {};
        frqAnswers = {};
        frqGrades = {};
        frqPending = {};
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
    $: examTitle = isFullLength
        ? "Full-Length Practice Exam"
        : (sections[0]?.section ?? "");

    // CARS uses a side-by-side reading layout (long passage kept in view beside
    // its questions), so those views need a wider container.
    $: hasCars = sections.some((s) => s.section_code === "cars");

    // Number each question in display order for stable "Q1..Qn" labels.
    $: numberOf = (() => {
        const map: Record<string, number> = {};
        flatQuestions.forEach((q, i) => (map[q.id] = i + 1));
        return map;
    })();

    // Free-response questions across the exam, numbered "FR1..FRn".
    $: flatFrqs = sections.flatMap((s) => s.free_response_questions ?? []);
    $: frqNumberOf = (() => {
        const map: Record<string, number> = {};
        flatFrqs.forEach((q, i) => (map[q.id] = i + 1));
        return map;
    })();

    // Free-response points that actually graded. Reported as an honest separate
    // line — FRQ feed the readiness model (via mergeTallies), never the MCQ-only
    // headline score, so the results screen must say where that effort went.
    $: frqGradedList = flatFrqs.filter((q) => frqGrades[q.id]?.graded);
    $: frqPointsAwarded = frqGradedList.reduce(
        (n, q) => n + (frqGrades[q.id]?.pointsAwarded ?? 0),
        0,
    );
    $: frqPointsMax = frqGradedList.reduce(
        (n, q) => n + (frqGrades[q.id]?.maxPoints ?? 0),
        0,
    );
    // True while any FRQ on the results screen is still being graded (async).
    $: frqGrading = flatFrqs.some((q) => frqPending[q.id]);
</script>

<div class="mcat">
    <div class="practice-tests" class:wide={hasCars}>
        {#if view === "list"}
            <button class="home-btn" on:click={() => bridgeCommand("home")}>
                ← Home
            </button>
            <header class="page-head">
                <h1>{fullLength ? "Full-length practice exam" : "Practice tests"}</h1>
                <p class="subtitle">
                    {#if fullLength}
                        Take a full-length exam that mirrors the real MCAT — all four
                        sections in order. Submit to see your score, an approximate
                        scaled score, and full explanations — take it as a check-in, not
                        a verdict.
                    {:else}
                        Drill a single MCAT section. Submit to see your score, an
                        approximate scaled score, and full explanations — take it as a
                        check-in, not a verdict.
                    {/if}
                </p>
            </header>

            {#if fullLength}
                <button class="full-length-card" on:click={startFullLength}>
                    <span class="badge">Full-length</span>
                    <span class="fl-title">MCAT Full-Length Exam</span>
                    <span class="fl-detail">
                        {FULL_LENGTH_TOTAL} questions · 4 sections · Chem/Phys → CARS → Bio/Biochem
                        → Psych/Soc
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
                        <h2>
                            {SECTION_LABEL[section.section_code] ?? section.section}
                        </h2>
                        <span>{compositionSummary(section)}</span>
                    </div>
                {/if}

                {#each section.passages as passage (passage.passage_id)}
                    <section
                        class="passage"
                        class:split={section.section_code === "cars"}
                    >
                        <div class="passage-read">
                            <h2 class="passage-title">{formatSci(passage.title)}</h2>
                            <div class="passage-text">
                                {formatSci(passage.passage_text)}
                            </div>
                        </div>
                        <div class="passage-questions">
                            {#each passage.questions as q (q.id)}
                                <QuestionCard
                                    question={q}
                                    index={numberOf[q.id]}
                                    selected={answers[q.id] ?? null}
                                    onSelect={(letter) => select(q, letter)}
                                />
                            {/each}
                        </div>
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

                {#if (section.free_response_questions ?? []).length}
                    <section class="passage">
                        <h2 class="passage-title">Free Response</h2>
                        {#each section.free_response_questions ?? [] as q (q.id)}
                            <FreeResponseCard
                                question={q}
                                index={frqNumberOf[q.id]}
                                value={frqAnswers[q.id] ?? ""}
                                gradedWithAi={aiGrading}
                                onInput={(text) =>
                                    (frqAnswers = { ...frqAnswers, [q.id]: text })}
                            />
                        {/each}
                    </section>
                {/if}
            {/each}

            <div class="submit-bar">
                <div class="submit-note">
                    {#if answeredCount < totalCount}
                        {totalCount - answeredCount} question(s) still unanswered — you can
                        still submit.
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
                        approx. scaled score (472–528) · {correctCount}/{totalCount} correct
                        ({scorePct}%)
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

                {#if flatFrqs.length}
                    <div class="frq-score" aria-live="polite">
                        <span class="frq-score-label">Free response</span>
                        {#if frqPointsMax > 0}
                            <span class="frq-score-val">
                                {frqPointsAwarded} / {frqPointsMax}
                            </span>
                            <span class="frq-score-cap">
                                points ({aiGrading ? "AI estimate" : "keyword match"}) ·
                                feeds your Readiness
                            </span>
                        {:else if frqGrading}
                            <span class="frq-score-val pending">grading…</span>
                        {:else}
                            <span class="frq-score-cap">
                                graded below · feeds your Readiness
                            </span>
                        {/if}
                    </div>
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
                                <div class="bd-name">
                                    {SECTION_LABEL[s.sectionCode] ?? s.section}
                                </div>
                                <div class="bd-bar">
                                    <ScoreBar
                                        label={SECTION_LABEL[s.sectionCode] ??
                                            s.section}
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
                Scaled scores are a documented linear approximation of the MCAT 118–132
                scale — AAMC's exact raw-to-scaled curves are not public, so treat these
                as estimates.
            </p>

            {#each sections as section (section.test_id)}
                {#if isFullLength}
                    <div class="section-banner">
                        <h2>
                            {SECTION_LABEL[section.section_code] ?? section.section}
                        </h2>
                    </div>
                {/if}
                {#each section.passages as passage (passage.passage_id)}
                    <section
                        class="passage"
                        class:split={section.section_code === "cars"}
                    >
                        <div class="passage-read">
                            <h2 class="passage-title">{formatSci(passage.title)}</h2>
                            <div class="passage-text">
                                {formatSci(passage.passage_text)}
                            </div>
                        </div>
                        <div class="passage-questions">
                            {#each passage.questions as q (q.id)}
                                <QuestionCard
                                    question={q}
                                    index={numberOf[q.id]}
                                    selected={answers[q.id] ?? null}
                                    graded={true}
                                    onSelect={() => {}}
                                />
                            {/each}
                        </div>
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

                {#if (section.free_response_questions ?? []).length}
                    <section class="passage">
                        <h2 class="passage-title">Free Response</h2>
                        {#each section.free_response_questions ?? [] as q (q.id)}
                            <FreeResponseCard
                                question={q}
                                index={frqNumberOf[q.id]}
                                value={frqAnswers[q.id] ?? ""}
                                graded={true}
                                grade={frqGrades[q.id] ?? null}
                                pending={frqPending[q.id] ?? false}
                                gradedWithAi={aiGrading}
                                onInput={() => {}}
                                onRetry={() => regradeFrq(q)}
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
    .home-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        margin-bottom: 1.1rem;
        padding: 0.45em 1.1em;
        border-radius: var(--mcat-radius-pill, 999px);
        border: 1px solid var(--mcat-border);
        background: var(--mcat-surface);
        color: var(--mcat-ink);
        font: inherit;
        font-weight: 700;
        font-size: 0.85rem;
        cursor: pointer;
        transition:
            border-color 0.15s var(--mcat-ease),
            color 0.15s var(--mcat-ease),
            transform 0.15s var(--mcat-ease);

        &:hover {
            border-color: var(--mcat-sage-ink);
            color: var(--mcat-sage-ink);
            transform: translateY(-1px);
        }
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
        // Opaque, not a blurred backdrop: a backdrop-filter on a sticky header
        // re-blurs everything behind it on every scroll frame, which was the
        // main cause of slow scrolling through a test.
        background: var(--mcat-canvas);
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

    // ---- CARS side-by-side reading layout ------------------------------
    // Wider canvas so the passage and its questions each get a readable column.
    .practice-tests.wide {
        max-width: 1180px;
    }
    // A CARS passage: passage text on the left (kept in view via sticky +
    // independent scroll), its questions on the right.
    .passage.split {
        display: grid;
        grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
        gap: 1.5rem;
        align-items: start;
    }
    .passage.split .passage-read {
        position: sticky;
        top: 3.25rem; // clears the sticky take-view header
        max-height: calc(100vh - 4.5rem);
        overflow-y: auto;
    }
    .passage.split .passage-text {
        margin-bottom: 0;
    }
    .passage.split .passage-questions {
        min-width: 0;
    }
    // Collapse to the normal stacked layout only when the window is genuinely
    // narrow. The practice-test window is 920px default / 760px min, so keep the
    // split active well below that (47rem ≈ 752px) — otherwise it never shows.
    @media (max-width: 47rem) {
        .passage.split {
            display: block;
        }
        .passage.split .passage-read {
            position: static;
            max-height: none;
            overflow: visible;
        }
        .passage.split .passage-text {
            margin-bottom: 1rem;
        }
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
    // Free-response result, surfaced up in the scorecard next to the MCQ score.
    // Kept visually distinct (a calm sky pill) because it feeds Readiness rather
    // than the MCQ-only headline.
    .frq-score {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        justify-content: center;
        gap: 0.35rem 0.6rem;
        max-width: 30rem;
        margin: 1.1rem auto 0;
        padding: 0.6rem 1rem;
        border-radius: var(--mcat-radius);
        background: var(--mcat-sky-tint);
        border: 1px solid color-mix(in srgb, var(--mcat-sky-ink), transparent 70%);
    }
    .frq-score-label {
        font-weight: 800;
        color: var(--mcat-ink);
    }
    .frq-score-val {
        font-weight: 800;
        font-size: 1.5rem;
        line-height: 1;
        font-variant-numeric: tabular-nums;
        color: var(--mcat-sky-ink);
    }
    .frq-score-val.pending {
        font-size: 1rem;
        color: var(--mcat-ink-faint);
    }
    .frq-score-cap {
        flex-basis: 100%;
        color: var(--mcat-ink-soft);
        font-size: 0.82rem;
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
