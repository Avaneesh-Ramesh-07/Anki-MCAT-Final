# MCAT Topical Practice Tests (original content)

Original, AAMC-style topical practice tests authored for the app's readiness /
"Performance" model. These questions are **written from scratch**. A commercial
question book was consulted **privately, as ground truth only** — to calibrate topic
coverage, difficulty, and distractor style — and is **never reproduced**. The source PDF
is git-ignored (`resources/*.pdf`) and must not be committed or distributed.

> **MCAT is a registered trademark of the Association of American Medical Colleges
> (AAMC). This material is independently authored and is not reviewed, sponsored, or
> endorsed by the AAMC.**

## Planned set

6 tests, 2 per science section (CARS deferred — no source material):

| File | Section | Status |
|---|---|---|
| `bio-biochem-1.json` | Biological & Biochemical Foundations | **exemplar (in review)** |
| `bio-biochem-2.json` | Biological & Biochemical Foundations | pending sign-off |
| `chem-phys-1.json` / `-2.json` | Chemical & Physical Foundations | pending sign-off |
| `psych-soc-1.json` / `-2.json` | Psych/Social/Bio Foundations of Behavior | pending sign-off |

Each test mirrors a real section: ~59 questions = 10 passages (4–7 questions each) +
15 discrete questions, with per-section discipline weightings (AAMC "What's on the MCAT").

## Tag taxonomy

Every question carries one or more `aamc::<section-code>::<topic>` tags. The section code
matches the app's Mastery Query convention (`rslib/src/mcat/mastery.rs`, prefix `aamc::`),
so imported questions aggregate by topic automatically. Section codes:

- `bio-biochem` — Biological and Biochemical Foundations of Living Systems
- `chem-phys` — Chemical and Physical Foundations of Biological Systems
- `psych-soc` — Psychological, Social, and Biological Foundations of Behavior

Example: `aamc::bio-biochem::enzyme-kinetics`.

## File schema

```jsonc
{
  "test_id": "bio-biochem-1",
  "section": "Biological and Biochemical Foundations of Living Systems",
  "section_code": "bio-biochem",
  "composition": { "passages": 10, "passage_questions": 44, "discrete_questions": 15 },
  "weighting_target": { "biology": 0.65, "biochemistry": 0.25, "gen-chem": 0.05, "orgo": 0.05 },
  "passages": [
    {
      "passage_id": "bio-biochem-1-p1",
      "topic_tags": ["aamc::bio-biochem::enzyme-kinetics"],
      "passage_text": "…original passage…",
      "figure": null,                       // always null — no fabricated tables/graphs (see Content policy)
      "questions": [ /* Question objects */ ]
    }
  ],
  "discrete_questions": [ /* Question objects */ ]
}
```

### Question object

```jsonc
{
  "id": "bio-biochem-1-p1-q1",
  "stem": "…",
  "options": { "A": "…", "B": "…", "C": "…", "D": "…" },
  "correct": "C",
  "explanation": "why the keyed answer is correct",
  "distractor_notes": { "A": "why wrong", "B": "why wrong", "D": "why wrong" },
  "topic_tags": ["aamc::bio-biochem::enzyme-kinetics"],
  "ground_truth_ref": "concept only (e.g. 'Michaelis-Menten, QBook Ch2') — original scenario/values",
  "figure": null,
  "qa": {
    "single_defensible_answer": true,   // exactly one option is correct; others defensibly wrong
    "original_not_copied": true,        // new scenario/numbers/framing, not a paraphrase of any source item
    "reviewed": false                   // flip to true only after a human/SME correctness pass
  }
}
```

## QA policy

A question is trustworthy enough to feed a readiness number only if:

1. **single_defensible_answer** — the keyed option is unambiguously correct and each
   distractor has a written reason it is wrong (`distractor_notes`).
2. **original_not_copied** — verified against a text extraction of the source chapter for
   no verbatim overlap.
3. **reviewed** — a human/SME has confirmed correctness. Authoring sets this `false`; do
   not treat `reviewed:false` items as validated.

This mirrors the answer-verification discipline the readiness model already applies to the
memory score (abstain when evidence is thin): an unreviewed item should not silently become
false confidence.

## Content policy

- **No fabricated tables, graphs, or figures.** The `figure` field is always `null`.
  Passages and questions are text/conceptual only; we do not invent data sets that look
  empirical.
- **Quantitative questions state their givens in the stem** as explicit hypotheticals
  (e.g., "a mutant with a lower Km"), not as invented experimental results.
- If a topic genuinely needs a figure (e.g., a real graph-interpretation skill), source a
  real, license-cleared figure — do not synthesize one.
