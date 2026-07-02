// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Scoring for topical tests and the full-length exam. The scaled-score mapping
// mirrors the Rust performance model (rslib/src/mcat/performance.rs): a
// documented *linear* approximation of the MCAT 118-132 section scale. AAMC's
// true raw->scaled tables are not public, so this is an estimate, not exact.

import type { OptionLetter, PracticeTest, Question } from "./types";

export const SCALE_MIN = 118;
export const SCALE_MAX = 132;

/** Linear raw->scaled approximation: [0,1] -> [118,132]. */
export function scaledFromFraction(fraction: number): number {
    const span = SCALE_MAX - SCALE_MIN;
    const scaled = Math.round(SCALE_MIN + fraction * span);
    return Math.max(SCALE_MIN, Math.min(SCALE_MAX, scaled));
}

/** Every question in a test, in display order (passages then discretes). */
export function sectionQuestions(test: PracticeTest): Question[] {
    const qs: Question[] = [];
    for (const p of test.passages) {
        qs.push(...p.questions);
    }
    qs.push(...test.discrete_questions);
    return qs;
}

export interface SectionScore {
    sectionCode: string;
    section: string;
    correct: number;
    total: number;
    fraction: number;
    scaled: number;
}

/** Exam-style section score: correct / total (unanswered counts as wrong). */
export function scoreSection(
    test: PracticeTest,
    answers: Record<string, OptionLetter>,
): SectionScore {
    const qs = sectionQuestions(test);
    const total = qs.length;
    const correct = qs.filter((q) => answers[q.id] === q.correct).length;
    const fraction = total === 0 ? 0 : correct / total;
    return {
        sectionCode: test.section_code,
        section: test.section,
        correct,
        total,
        fraction,
        scaled: scaledFromFraction(fraction),
    };
}

// Note: per-topic/performance tallying was removed while performance scoring is
// disabled. `scoreSection` above is still used for the local per-test score
// shown on the results screen.
