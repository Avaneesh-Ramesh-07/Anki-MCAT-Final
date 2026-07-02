// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// The six topical practice tests are statically bundled into this route (no
// backend RPC). Vite inlines these JSON files at build time.
import bioBiochem1 from "./tests/bio-biochem-1.json";
import bioBiochem2 from "./tests/bio-biochem-2.json";
import cars1 from "./tests/cars-1.json";
import chemPhys1 from "./tests/chem-phys-1.json";
import chemPhys2 from "./tests/chem-phys-2.json";
import psychSoc1 from "./tests/psych-soc-1.json";
import psychSoc2 from "./tests/psych-soc-2.json";

import type { PracticeTest } from "./types";

// Imported JSON is typed structurally; cast through unknown to our model.
export const PRACTICE_TESTS: PracticeTest[] = [
    chemPhys1,
    chemPhys2,
    cars1,
    bioBiochem1,
    bioBiochem2,
    psychSoc1,
    psychSoc2,
] as unknown as PracticeTest[];

// The four sections of a full-length exam, in real MCAT order:
// Chem/Phys (59) -> CARS (53) -> Bio/Biochem (59) -> Psych/Soc (59) = 230.
export const FULL_LENGTH_SECTIONS: PracticeTest[] = [
    chemPhys1,
    cars1,
    bioBiochem1,
    psychSoc1,
] as unknown as PracticeTest[];

export const FULL_LENGTH_TOTAL: number = FULL_LENGTH_SECTIONS.reduce(
    (n, t) => n + t.composition.total,
    0,
);

export function getTest(testId: string): PracticeTest | undefined {
    return PRACTICE_TESTS.find((t) => t.test_id === testId);
}

/** Flatten every question in a test into display order (passages then discretes). */
export function allQuestions(test: PracticeTest) {
    const out: { passageTitle: string | null; question: PracticeTest["discrete_questions"][number] }[] = [];
    for (const p of test.passages) {
        for (const q of p.questions) {
            out.push({ passageTitle: p.title, question: q });
        }
    }
    for (const q of test.discrete_questions) {
        out.push({ passageTitle: null, question: q });
    }
    return out;
}

/** Human-readable composition summary, e.g. "59 questions · 10 passages + 15 discrete". */
export function compositionSummary(test: PracticeTest): string {
    const c = test.composition;
    return `${c.total} questions · ${c.passages} passages + ${c.discrete_questions} discrete`;
}
