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

export interface PracticeTest {
    test_id: string;
    section: string;
    section_code: string;
    composition: Composition;
    passages: Passage[];
    discrete_questions: Question[];
}

export const OPTION_LETTERS: OptionLetter[] = ["A", "B", "C", "D"];
