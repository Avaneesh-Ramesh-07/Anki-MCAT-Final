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

export interface TopicTally {
    topic: string;
    correct: number;
    answered: number;
}

/**
 * Per-`aamc::`-topic correct/answered tally for one test, submitted to the
 * performance model. Exam-style: every question counts toward `answered` (a
 * blank counts as answered-and-wrong), matching `scoreSection`. A question with
 * several `aamc::` tags contributes to each.
 */
export function topicTallies(
    test: PracticeTest,
    answers: Record<string, OptionLetter>,
): TopicTally[] {
    const map = new Map<string, { correct: number; answered: number }>();
    for (const q of sectionQuestions(test)) {
        const isCorrect = answers[q.id] === q.correct;
        for (const tag of q.topic_tags ?? []) {
            const entry = map.get(tag) ?? { correct: 0, answered: 0 };
            entry.answered += 1;
            if (isCorrect) {
                entry.correct += 1;
            }
            map.set(tag, entry);
        }
    }
    return [...map].map(([topic, v]) => ({ topic, correct: v.correct, answered: v.answered }));
}

/** A graded free-response result, ready to fold into topic evidence. Partial
 * credit is carried as points: `correct` += points awarded, `answered` += max. */
export interface FrqGrade {
    topic_tags: string[];
    pointsAwarded: number;
    maxPoints: number;
}

/** Per-`aamc::`-topic tally from graded FRQs (points_awarded / max_points). */
export function frqTopicTallies(grades: FrqGrade[]): TopicTally[] {
    const map = new Map<string, { correct: number; answered: number }>();
    for (const g of grades) {
        for (const tag of g.topic_tags ?? []) {
            const entry = map.get(tag) ?? { correct: 0, answered: 0 };
            entry.correct += g.pointsAwarded;
            entry.answered += g.maxPoints;
            map.set(tag, entry);
        }
    }
    return [...map].map(([topic, v]) => ({ topic, correct: v.correct, answered: v.answered }));
}

/** Sum two topic-tally lists by topic (e.g. MCQ evidence + FRQ evidence). */
export function mergeTallies(a: TopicTally[], b: TopicTally[]): TopicTally[] {
    const map = new Map<string, { correct: number; answered: number }>();
    for (const t of [...a, ...b]) {
        const entry = map.get(t.topic) ?? { correct: 0, answered: 0 };
        entry.correct += t.correct;
        entry.answered += t.answered;
        map.set(t.topic, entry);
    }
    return [...map].map(([topic, v]) => ({ topic, correct: v.correct, answered: v.answered }));
}
