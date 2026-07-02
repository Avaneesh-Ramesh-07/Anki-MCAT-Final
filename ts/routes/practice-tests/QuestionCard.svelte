<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { OptionLetter, Question } from "./types";
    import { OPTION_LETTERS } from "./types";

    export let question: Question;
    export let index: number;
    export let selected: OptionLetter | null;
    // When graded, options are locked and correctness/explanation is shown.
    export let graded = false;
    export let onSelect: (letter: OptionLetter) => void;

    $: isCorrect = graded && selected === question.correct;
</script>

<div class="question" class:graded>
    <div class="stem">
        <span class="qnum">Q{index}</span>
        <span>{question.stem}</span>
    </div>

    <div class="options" role="radiogroup" aria-label={`Question ${index} options`}>
        {#each OPTION_LETTERS as letter (letter)}
            {@const chosen = selected === letter}
            {@const correct = letter === question.correct}
            <label
                class="option"
                class:chosen
                class:correct={graded && correct}
                class:wrong={graded && chosen && !correct}
            >
                <input
                    type="radio"
                    name={question.id}
                    value={letter}
                    checked={chosen}
                    disabled={graded}
                    on:change={() => onSelect(letter)}
                />
                <span class="letter">{letter}</span>
                <span class="text">{question.options[letter]}</span>
                {#if graded && correct}
                    <span class="mark correct-mark">✓ correct</span>
                {:else if graded && chosen && !correct}
                    <span class="mark wrong-mark">✗ your answer</span>
                {/if}
            </label>
        {/each}
    </div>

    {#if graded}
        <div class="feedback" class:right={isCorrect} class:wrong={!isCorrect}>
            <div class="verdict">
                <span class="verdict-icon" aria-hidden="true">
                    {isCorrect ? "✓" : "✗"}
                </span>
                {#if selected == null}
                    Not answered — correct answer is {question.correct}.
                {:else if isCorrect}
                    Correct
                {:else}
                    Incorrect — correct answer is {question.correct}.
                {/if}
            </div>
            <div class="explanation">{question.explanation}</div>
            {#if selected != null && !isCorrect && question.distractor_notes[selected]}
                <div class="distractor">
                    <strong>Why {selected} is wrong:</strong>
                    {question.distractor_notes[selected]}
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
        color: var(--mcat-sage-ink);
        font-variant-numeric: tabular-nums;
    }
    .options {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
    }
    .option {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        padding: 0.6rem 0.75rem;
        border: 1px solid var(--mcat-border);
        border-radius: var(--mcat-radius);
        cursor: pointer;
        background: var(--mcat-inset);
        transition:
            border-color 0.12s var(--mcat-ease),
            background 0.12s var(--mcat-ease);

        &:hover:not(.correct):not(.wrong) {
            border-color: var(--mcat-sage);
        }
        &.chosen:not(.correct):not(.wrong) {
            border-color: var(--mcat-sky-ink);
            box-shadow: 0 0 0 1px var(--mcat-sky-ink);
        }
        &.correct {
            border-color: var(--mcat-sage-ink);
            background: var(--mcat-sage-tint);
        }
        &.wrong {
            border-color: var(--mcat-blush-ink);
            background: var(--mcat-blush-tint);
        }
    }
    .option input {
        margin-top: 0.25rem;
        accent-color: var(--mcat-sage-ink);
    }
    .letter {
        flex: 0 0 auto;
        font-weight: 800;
        min-width: 1.1em;
        color: var(--mcat-ink);
    }
    .text {
        flex: 1;
        line-height: 1.45;
    }
    .mark {
        flex: 0 0 auto;
        font-size: 0.75rem;
        font-weight: 800;
        align-self: center;
    }
    .correct-mark {
        color: var(--mcat-sage-ink);
    }
    .wrong-mark {
        color: var(--mcat-blush-ink);
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
        &.wrong {
            border-color: var(--mcat-blush-ink);
            background: var(--mcat-blush-tint);
        }
    }
    .verdict {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-weight: 800;
        margin-bottom: 0.45rem;
    }
    .verdict-icon {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 1.35rem;
        height: 1.35rem;
        border-radius: var(--mcat-radius-pill);
        font-size: 0.85rem;
    }
    .right .verdict-icon {
        background: var(--mcat-sage-ink);
        color: #fff;
    }
    .wrong .verdict-icon {
        background: var(--mcat-blush-ink);
        color: #fff;
    }
    // In night mode the *-ink fills are lightened (they double as text-on-dark),
    // so a white glyph drops to ~1.8:1. Use a dark glyph on the light fill.
    :global(.night-mode) .right .verdict-icon,
    :global(.night-mode) .wrong .verdict-icon {
        color: var(--mcat-inset);
    }
    .distractor {
        margin-top: 0.55rem;
        color: var(--mcat-ink-soft);
    }
</style>
