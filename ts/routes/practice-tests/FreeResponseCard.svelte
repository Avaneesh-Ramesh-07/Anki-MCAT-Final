<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { GradeFreeResponseResponse } from "@generated/anki/mcat_pb";

    import type { FreeResponseQuestion } from "./types";

    export let question: FreeResponseQuestion;
    export let index: number;
    export let value: string;
    // When graded, the textarea locks and the rubric result / feedback is shown.
    export let graded = false;
    export let grade: GradeFreeResponseResponse | null = null;
    export let pending = false;
    export let onInput: (text: string) => void;
</script>

<div class="question" class:graded>
    <div class="stem">
        <span class="qnum">FR{index}</span>
        <span>{question.prompt}</span>
    </div>

    <textarea
        class="answer"
        rows="5"
        placeholder="Write your response…"
        {value}
        disabled={graded}
        on:input={(e) => onInput(e.currentTarget.value)}
    ></textarea>

    <div class="meta">Worth {question.max_points} points · graded by rubric</div>

    {#if graded}
        {#if pending}
            <div class="feedback pending">Grading your response…</div>
        {:else if grade && grade.graded}
            <div class="feedback right">
                <div class="verdict">
                    <span class="verdict-icon" aria-hidden="true">✓</span>
                    Score: {grade.pointsAwarded} / {grade.maxPoints} points
                </div>
                <div class="criteria">
                    {#each grade.criteria as c (c.id)}
                        <div class="criterion" class:met={c.met}>
                            <span class="cmark">{c.met ? "✓" : "✗"}</span>
                            <span class="cpts">
                                {c.pointsAwarded}/{c.pointsPossible}
                            </span>
                            <span class="crat">{c.rationale}</span>
                        </div>
                    {/each}
                </div>
                {#if grade.feedback}
                    <div class="fb">
                        <strong>Feedback:</strong>
                        {grade.feedback}
                    </div>
                {/if}
                <div class="reference">
                    <strong>Reference answer:</strong>
                    {question.reference_answer}
                </div>
            </div>
        {:else}
            <div class="feedback unavailable">
                <div class="verdict">
                    <span class="verdict-icon" aria-hidden="true">!</span>
                    AI grading unavailable{#if grade && grade.error}
                        — {grade.error}{/if}
                </div>
                <div class="reference">
                    <strong>Reference answer (self-grade):</strong>
                    {question.reference_answer}
                </div>
            </div>
        {/if}
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
            outline: none;
            border-color: var(--mcat-sky-ink);
            box-shadow: 0 0 0 1px var(--mcat-sky-ink);
        }
        &:disabled {
            opacity: 0.85;
        }
    }
    .meta {
        margin-top: 0.4rem;
        font-size: 0.8rem;
        color: var(--mcat-ink-faint);
    }
    .feedback {
        margin-top: 0.9rem;
        padding: 0.85rem 1rem;
        border-radius: var(--mcat-radius);
        border: 1px solid var(--mcat-border);
        background: var(--mcat-inset);
        font-size: 0.92rem;
        line-height: 1.55;

        &.right {
            border-color: var(--mcat-sage-ink);
            background: var(--mcat-sage-tint);
        }
        &.unavailable {
            border-color: var(--mcat-blush-ink);
            background: var(--mcat-blush-tint);
        }
        &.pending {
            color: var(--mcat-ink-soft);
            font-style: italic;
        }
    }
    .verdict {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-weight: 800;
        margin-bottom: 0.55rem;
    }
    .verdict-icon {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 1.35rem;
        height: 1.35rem;
        border-radius: var(--mcat-radius-pill);
        font-size: 0.85rem;
        background: var(--mcat-sage-ink);
        color: #fff;
    }
    .unavailable .verdict-icon {
        background: var(--mcat-blush-ink);
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
        color: var(--mcat-blush-ink);
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
</style>
