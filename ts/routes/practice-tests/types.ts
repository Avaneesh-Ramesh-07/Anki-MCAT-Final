// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

export type OptionLetter = "A" | "B" | "C" | "D";

export interface Question {
    id: string;
    stem: string;
    options: Record<OptionLetter, string>;
    correct: OptionLetter;
    explanation: string;
    distractor_notes: Partial<Record<OptionLetter, string>>;
    topic_tags: string[];
    figure: string | null;
}

export interface Passage {
    passage_id: string;
    title: string;
    topic_tags: string[];
    passage_text: string;
    questions: Question[];
}

export interface Composition {
    passages: number;
    passage_questions: number;
    discrete_questions: number;
    total: number;
}

/** One rubric criterion — self-contained so an LLM with no MCAT knowledge can
 * apply it (award 0..points from these fields alone; any disqualifier -> 0). */
export interface RubricCriterion {
    id: string;
    description: string;
    points: number;
    required_concepts: string[];
    disqualifiers: string[];
    // Literal match terms authored offline from the ground-truth reference
    // answer; used by the keyword-match grader when AI grading is off.
    keywords?: string[];
}

/** A free-response question, graded by the AI grader against its rubric.
 * `reference_answer` is for authoring/eval/post-grade display only — it is
 * NEVER sent to the grader. `max_points` must equal the sum of rubric points. */
export interface FreeResponseQuestion {
    type: "free_response";
    id: string;
    prompt: string;
    max_points: number;
    rubric: RubricCriterion[];
    reference_answer: string;
    topic_tags: string[];
    ground_truth_ref?: string;
    figure: string | null;
}

export interface PracticeTest {
    test_id: string;
    section: string;
    section_code: string;
    composition: Composition;
    passages: Passage[];
    discrete_questions: Question[];
    // Free-response questions are kept in their own array (never mixed into the
    // MCQ arrays), so multiple-choice scoring never sees an FRQ.
    free_response_questions?: FreeResponseQuestion[];
}

export const OPTION_LETTERS: OptionLetter[] = ["A", "B", "C", "D"];
