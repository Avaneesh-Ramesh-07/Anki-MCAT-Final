<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { GradeFreeResponseResponse } from "@generated/anki/mcat_pb";

    import { formatSci } from "./sci-format";
    import type { FreeResponseQuestion } from "./types";

    export let question: FreeResponseQuestion;
    export let index: number;
    export let value: string;
    // When graded, the textarea locks and the rubric result / feedback is shown.
    export let graded = false;
    export let grade: GradeFreeResponseResponse | null = null;
    export let pending = false;
    export let onInput: (text: string) => void;
    // Optional: re-run grading for this question (offered when grading was
    // unavailable). Refreshes the shown grade only; never re-records evidence.
    export let onRetry: (() => void) | null = null;
    // Whether this FRQ will be graded by AI (true) or by keyword match (false),
    // per the Home-page toggle. Display-only: drives the flag + wording. The
    // Rust grader independently decides the real mode from the same config.
    export let gradedWithAi = true;

    // Stable ids so the textarea has a real accessible name + description.
    $: promptId = `frq-prompt-${question.id}`;
    $: hintId = `frq-hint-${question.id}`;
    $: metaId = `frq-meta-${question.id}`;
    // The hint only exists before grading; keep the described-by target stable.
    $: describedBy = graded ? metaId : `${metaId} ${hintId}`;

    // Verdict tone tracks the actual score — honest, and on the theme's
    // blue -> green "growth" metaphor (never red): full credit is green with a
    // check; partial/none is a calm blue, read as "not grown yet", not failure.
    type Tone = "none" | "full" | "partial" | "zero";
    let tone: Tone = "none";
    $: {
        if (!grade || !grade.graded) {
            tone = "none";
        } else if (grade.maxPoints > 0 && grade.pointsAwarded >= grade.maxPoints) {
            tone = "full";
        } else if (grade.pointsAwarded > 0) {
            tone = "partial";
        } else {
            tone = "zero";
        }
    }

    const VERDICT_ICON: Record<Tone, string> = {
        none: "",
        full: "✓",
        partial: "◐",
        zero: "○",
    };
    // Warm, non-grading study-partner line, matched to the outcome.
    const ENCOURAGEMENT: Record<Tone, string> = {
        none: "",
        full: "Full marks — clear and complete.",
        partial:
            "You're partway there. Check the criteria you missed below and refine your answer.",
        zero: "No points yet — and that's okay. Compare your answer with the reference below, then give it another go.",
    };
    $: verdictIcon = VERDICT_ICON[tone];
    $: encouragement = ENCOURAGEMENT[tone];
</script>

<div class="question" class:graded>
    <div class="stem">
        <span class="qnum">FR{index}</span>
        <span id={promptId}>{formatSci(question.prompt)}</span>
    </div>

    <textarea
        class="answer"
        rows="5"
        placeholder="Write your response…"
        aria-labelledby={promptId}
        aria-describedby={describedBy}
        {value}
        disabled={graded}
        on:input={(e) => onInput(e.currentTarget.value)}
    ></textarea>

    <div id={metaId} class="meta">
        Worth {question.max_points} points ·
        <span
            class="mode-flag"
            class:keyword={!gradedWithAi}
            title={gradedWithAi
                ? "Graded by AI against the rubric"
                : "Graded by matching rubric keywords (AI grading is off)"}
        >
            {gradedWithAi ? "AI-graded" : "Keyword match"}
        </span>
    </div>
    {#if !graded}
        <div id={hintId} class="hint">
            Aim for a few clear sentences — enough to cover each rubric point.
        </div>
    {/if}

    {#if graded}
        <div class="result-region" aria-live="polite" aria-busy={pending}>
            {#if pending}
                <div class="feedback skeleton">
                    <p class="grading-note">Reading your response…</p>
                    <div class="sk-bar sk-title" aria-hidden="true"></div>
                    <div class="sk-bar" aria-hidden="true"></div>
                    <div class="sk-bar short" aria-hidden="true"></div>
                </div>
            {:else if grade && grade.graded}
                <div class="feedback {tone}">
                    <div class="verdict">
                        <span class="verdict-icon" aria-hidden="true">
                            {verdictIcon}
                        </span>
                        Score: {grade.pointsAwarded} / {grade.maxPoints} points
                    </div>
                    <div class="encourage">{encouragement}</div>
                    <div class="criteria">
                        {#each grade.criteria as c (c.id)}
                            <div class="criterion" class:met={c.met}>
                                <span class="cmark" aria-hidden="true">
                                    {c.met ? "✓" : "○"}
                                </span>
                                <span class="sr-only">
                                    {c.met ? "Criterion met." : "Criterion not met."}
                                </span>
                                <span class="cpts">
                                    {c.pointsAwarded}/{c.pointsPossible}
                                </span>
                                <span class="crat">{formatSci(c.rationale)}</span>
                            </div>
                        {/each}
                    </div>
                    {#if grade.feedback}
                        <div class="fb">
                            <strong>Feedback:</strong>
                            {formatSci(grade.feedback)}
                        </div>
                    {/if}
                    <div class="reference">
                        <strong>Reference answer:</strong>
                        {formatSci(question.reference_answer)}
                    </div>
                    <p class="caveat">
                        {#if gradedWithAi}
                            AI-reviewed against the rubric — an estimate to guide your
                            studying, not a final grade.
                        {:else}
                            Matched against the rubric's keywords — a rough check to
                            guide your studying, not a final grade. (AI grading is off.)
                        {/if}
                    </p>
                </div>
            {:else}
                <div class="feedback unavailable">
                    <div class="verdict">
                        <span class="verdict-icon info" aria-hidden="true">i</span>
                        {gradedWithAi
                            ? "AI grading isn't available right now"
                            : "Grading isn't available right now"}
                    </div>
                    <div class="encourage">
                        No problem — use the reference answer below to grade yourself,
                        or try again in a moment.
                    </div>
                    {#if onRetry}
                        <button type="button" class="retry" on:click={onRetry}>
                            Try grading again
                        </button>
                    {/if}
                    <div class="reference">
                        <strong>Reference answer (self-grade):</strong>
                        {formatSci(question.reference_answer)}
                    </div>
                    {#if grade && grade.error}
                        <details class="tech">
                            <summary>Technical details</summary>
                            {grade.error}
                        </details>
                    {/if}
                </div>
            {/if}
        </div>
    {/if}
</div>

<style lang="scss">
    .question {
        padding: 1.15rem 1.25rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius-lg);
        background: var(--mcat-surface);
        box-shadow: var(--mcat-shadow);
        margin-bottom: 1rem;
    }
    .stem {
        display: flex;
        gap: 0.6rem;
        font-weight: 600;
        line-height: 1.55;
        margin-bottom: 0.85rem;
        color: var(--mcat-ink);
    }
    .qnum {
        flex: 0 0 auto;
        font-weight: 800;
        color: var(--mcat-blush-ink);
        font-variant-numeric: tabular-nums;
    }
    .answer {
        width: 100%;
        box-sizing: border-box;
        padding: 0.65rem 0.75rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius);
        background: var(--mcat-inset);
        color: var(--mcat-ink);
        font: inherit;
        line-height: 1.5;
        resize: vertical;

        &:focus {
            // Transparent outline keeps a visible ring under Windows
            // forced-colors / high-contrast, where box-shadow is stripped.
            outline: 2px solid transparent;
            outline-offset: 2px;
            border-color: var(--mcat-sky-ink);
            box-shadow: 0 0 0 2px var(--mcat-sky-ink);
        }
        // Locked after submit: keep the student's own words fully readable
        // (they re-read them against the criteria); signal "locked" via the
        // surface + cursor, not by dimming the text.
        &:disabled {
            opacity: 1;
            background: var(--mcat-surface-2);
            cursor: default;
        }
    }
    .meta {
        margin-top: 0.4rem;
        font-size: 0.8rem;
        color: var(--mcat-ink-soft);
    }
    // How this FRQ will be graded — AI (sky) vs keyword match (neutral). Calm
    // palette only (never red), matching the rest of the card.
    .mode-flag {
        display: inline-flex;
        align-items: center;
        gap: 0.25em;
        padding: 0.08em 0.6em;
        border-radius: var(--mcat-radius-pill);
        font-weight: 700;
        font-size: 0.74rem;
        background: var(--mcat-sky-tint);
        color: var(--mcat-sky-ink);
    }
    .mode-flag::before {
        content: "✦"; // "AI" spark
        font-size: 0.8em;
    }
    .mode-flag.keyword {
        background: var(--mcat-inset);
        color: var(--mcat-ink-soft);
    }
    .mode-flag.keyword::before {
        content: "⌕"; // magnifier — keyword search
    }
    .hint {
        margin-top: 0.3rem;
        font-size: 0.82rem;
        color: var(--mcat-ink-soft);
    }
    .feedback {
        margin-top: 0.9rem;
        padding: 0.85rem 1rem;
        border-radius: var(--mcat-radius);
        border: 1px solid var(--mcat-border);
        background: var(--mcat-inset);
        font-size: 0.92rem;
        line-height: 1.55;

        // Full credit: green "grown". Reserve the success check + sage for this.
        &.full {
            border-color: var(--mcat-sage-ink);
            background: var(--mcat-sage-tint);
        }
        // Partial / none: calm blue "not grown yet" — honest, never red.
        &.partial,
        &.zero {
            border-color: var(--mcat-sky-ink);
            background: var(--mcat-sky-tint);
        }
        &.unavailable {
            border-color: var(--mcat-border-strong);
            background: var(--mcat-inset);
        }
    }
    .verdict {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
    }
    .verdict-icon {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 1.35rem;
        height: 1.35rem;
        border-radius: var(--mcat-radius-pill);
        font-size: 0.85rem;
        background: var(--mcat-sky-ink); // partial / zero default
        color: #fff;
    }
    .full .verdict-icon {
        background: var(--mcat-sage-ink);
    }
    .verdict-icon.info {
        background: var(--mcat-ink-soft);
        font-style: italic;
        font-weight: 700;
    }
    // In night mode the accent *-ink fills are lightened (they double as
    // text-on-dark), so a white glyph on them drops to ~1.8:1. Use a dark
    // glyph on the light fill instead so the ✓/◐/○/i stays legible.
    :global(.night-mode) .verdict-icon {
        color: var(--mcat-inset);
    }
    .encourage {
        color: var(--mcat-ink);
        margin-bottom: 0.55rem;
    }
    .criteria {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        margin-bottom: 0.55rem;
    }
    .criterion {
        display: grid;
        grid-template-columns: 1.2rem 2.6rem 1fr;
        align-items: start;
        gap: 0.5rem;
    }
    .cmark {
        font-weight: 800;
        color: var(--mcat-sky-ink);
    }
    .criterion.met .cmark {
        color: var(--mcat-sage-ink);
    }
    .cpts {
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        color: var(--mcat-ink);
    }
    .crat {
        color: var(--mcat-ink-soft);
    }
    .fb,
    .reference {
        margin-top: 0.5rem;
        color: var(--mcat-ink-soft);
    }
    .caveat {
        margin: 0.6rem 0 0;
        font-size: 0.8rem;
        font-style: italic;
        color: var(--mcat-ink-soft);
    }
    .retry {
        margin: 0.2rem 0 0.4rem;
        padding: 0.4rem 0.85rem;
        border: 1px solid var(--mcat-border-strong);
        border-radius: var(--mcat-radius-pill);
        background: var(--mcat-surface);
        color: var(--mcat-ink);
        font: inherit;
        font-weight: 700;
        font-size: 0.85rem;
        cursor: pointer;
        transition: background 0.15s var(--mcat-ease);

        &:hover {
            background: var(--mcat-surface-2);
        }
        &:focus-visible {
            outline: 2px solid var(--mcat-sky-ink);
            outline-offset: 2px;
        }
    }
    .tech {
        margin-top: 0.5rem;
        font-size: 0.78rem;
        // ink-soft (not ink-faint) so this small body text clears AA in both
        // themes; ink-faint is reserved for >=18px / decorative.
        color: var(--mcat-ink-soft);

        summary {
            cursor: pointer;
        }
    }

    // Skeleton loader (product register: skeletons over spinners).
    .skeleton {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    // Visible, calm reassurance shown while the AI grade is in flight (also
    // announced via the aria-live result region).
    .grading-note {
        margin: 0;
        color: var(--mcat-ink-soft);
        font-style: italic;
    }
    .sk-bar {
        height: 0.72rem;
        border-radius: var(--mcat-radius-pill);
        background: linear-gradient(
            90deg,
            var(--mcat-track) 25%,
            var(--mcat-inset) 37%,
            var(--mcat-track) 63%
        );
        background-size: 400% 100%;
        animation: sk-shimmer 1.4s ease-in-out infinite;
    }
    .sk-title {
        width: 45%;
        height: 0.9rem;
    }
    .sk-bar.short {
        width: 70%;
    }
    @keyframes sk-shimmer {
        0% {
            background-position: 100% 0;
        }
        100% {
            background-position: 0 0;
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .sk-bar {
            animation: none;
            background: var(--mcat-track);
        }
    }

    .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
    }
</style>
