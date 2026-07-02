// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import { describe, expect, it } from "vitest";

import type { FrqGrade } from "./scoring";
import { frqTopicTallies, mergeTallies, scoreSection, topicTallies } from "./scoring";
import type { OptionLetter, PracticeTest, Question } from "./types";

function mcq(id: string, correct: OptionLetter, tags: string[]): Question {
    return {
        id,
        stem: id,
        options: { A: "a", B: "b", C: "c", D: "d" },
        correct,
        explanation: "",
        distractor_notes: {},
        topic_tags: tags,
        figure: null,
    };
}

function test_(discrete: Question[]): PracticeTest {
    return {
        test_id: "t",
        section: "S",
        section_code: "bio-biochem",
        composition: { passages: 0, passage_questions: 0, discrete_questions: discrete.length, total: discrete.length },
        passages: [],
        discrete_questions: discrete,
    };
}

describe("MCQ scoring (unchanged, FRQ-agnostic)", () => {
    const pt = test_([
        mcq("q1", "A", ["aamc::bio-biochem::genetics"]),
        mcq("q2", "B", ["aamc::bio-biochem::genetics"]),
    ]);

    it("scores multiple choice by === correct", () => {
        const s = scoreSection(pt, { q1: "A", q2: "C" });
        expect(s.correct).toBe(1);
        expect(s.total).toBe(2);
    });

    it("topicTallies counts per tag, unanswered = wrong", () => {
        const t = topicTallies(pt, { q1: "A" }); // q2 unanswered
        expect(t).toEqual([{ topic: "aamc::bio-biochem::genetics", correct: 1, answered: 2 }]);
    });
});

describe("frqTopicTallies", () => {
    it("carries partial credit as points_awarded / max_points per tag", () => {
        const grades: FrqGrade[] = [
            { topic_tags: ["aamc::bio-biochem::carbohydrates"], pointsAwarded: 3, maxPoints: 4 },
            { topic_tags: ["aamc::bio-biochem::carbohydrates"], pointsAwarded: 1, maxPoints: 2 },
        ];
        expect(frqTopicTallies(grades)).toEqual([
            { topic: "aamc::bio-biochem::carbohydrates", correct: 4, answered: 6 },
        ]);
    });

    it("credits every tag on a multi-tag FRQ", () => {
        const grades: FrqGrade[] = [
            { topic_tags: ["aamc::chem-phys::gen-chem", "aamc::chem-phys::orgo"], pointsAwarded: 2, maxPoints: 4 },
        ];
        const out = frqTopicTallies(grades).sort((a, b) => a.topic.localeCompare(b.topic));
        expect(out).toEqual([
            { topic: "aamc::chem-phys::gen-chem", correct: 2, answered: 4 },
            { topic: "aamc::chem-phys::orgo", correct: 2, answered: 4 },
        ]);
    });
});

describe("mergeTallies", () => {
    it("sums MCQ and FRQ evidence by topic", () => {
        const mcqT = [{ topic: "aamc::bio-biochem::genetics", correct: 4, answered: 5 }];
        const frqT = [
            { topic: "aamc::bio-biochem::genetics", correct: 2, answered: 4 },
            { topic: "aamc::bio-biochem::carbohydrates", correct: 3, answered: 4 },
        ];
        const merged = mergeTallies(mcqT, frqT).sort((a, b) => a.topic.localeCompare(b.topic));
        expect(merged).toEqual([
            { topic: "aamc::bio-biochem::carbohydrates", correct: 3, answered: 4 },
            { topic: "aamc::bio-biochem::genetics", correct: 6, answered: 9 },
        ]);
    });
});
