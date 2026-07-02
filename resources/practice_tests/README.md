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

| File                           | Section                                  | Status                   |
| ------------------------------ | ---------------------------------------- | ------------------------ |
| `bio-biochem-1.json`           | Biological & Biochemical Foundations     | **exemplar (in review)** |
| `bio-biochem-2.json`           | Biological & Biochemical Foundations     | pending sign-off         |
| `chem-phys-1.json` / `-2.json` | Chemical & Physical Foundations          | pending sign-off         |
| `psych-soc-1.json` / `-2.json` | Psych/Social/Bio Foundations of Behavior | pending sign-off         |

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
    "composition": {
        "passages": 10,
        "passage_questions": 44,
        "discrete_questions": 15
    },
    "weighting_target": {
        "biology": 0.65,
        "biochemistry": 0.25,
        "gen-chem": 0.05,
        "orgo": 0.05
    },
    "passages": [
        {
            "passage_id": "bio-biochem-1-p1",
            "topic_tags": ["aamc::bio-biochem::enzyme-kinetics"],
            "passage_text": "…original passage…",
            "figure": null, // always null — no fabricated tables/graphs (see Content policy)
            "questions": [/* Question objects */]
        }
    ],
    "discrete_questions": [/* Question objects */]
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
    "distractor_notes": {
        "A": "why wrong",
        "B": "why wrong",
        "D": "why wrong"
    },
    "topic_tags": ["aamc::bio-biochem::enzyme-kinetics"],
    "ground_truth_ref": "concept only (e.g. 'Michaelis-Menten, QBook Ch2') — original scenario/values",
    "figure": null,
    "qa": {
        "single_defensible_answer": true, // exactly one option is correct; others defensibly wrong
        "original_not_copied": true, // new scenario/numbers/framing, not a paraphrase of any source item
        "reviewed": false // flip to true only after a human/SME correctness pass
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

## Free-response questions (FRQ)

Each test also carries a `free_response_questions` array (kept separate from the MCQ
arrays so multiple-choice scoring never sees an FRQ). FRQs are AI-graded against a rubric
by the backend `GradeFreeResponse` RPC (`rslib/src/backend/mcat.rs`, OpenAI). The graded
points fold into the Performance model via `recordPracticeResult` as
`correct = points_awarded, answered = max_points`.

**Count per test** = `20% × (weighting_target% × section question count)` (59/59/59/53),
rounded half-up — ~13 per science test, ~11 for CARS (~89 total). Authored via
`tools/build_frq.py` (single source of truth; idempotently dual-writes both JSON copies and
validates `max_points == Σ rubric points`). Keep `max_points ≤ 4` (one rubric point ≈ one
MCQ of evidence, so an FRQ doesn't dominate the abstain gate / Wilson n).

### FRQ object schema

```jsonc
{
    "type": "free_response",
    "id": "bio-biochem-1-frq1",
    "prompt": "…the question…",
    "max_points": 4,                       // == sum of rubric[].points
    "rubric": [
        {
            "id": "c1",
            "description": "what earns these points (the grader applies this verbatim)",
            "points": 2,
            "required_concepts": ["concept the answer must express", "…"],
            "disqualifiers": ["statement that voids this criterion even if concepts appear"]
        }
    ],
    "reference_answer": "model answer — for authoring/eval/post-grade display ONLY; never sent to the grader",
    "topic_tags": ["aamc::bio-biochem::carbohydrates"],
    "ground_truth_ref": "concept only — original framing",
    "figure": null,
    "qa": { "single_defensible_answer": true, "original_not_copied": true, "reviewed": false }
}
```

Rubric-design rule: each criterion must be self-contained so an LLM with **no MCAT
knowledge** can apply it — an explicit `description`, integer `points`, `required_concepts`
(award only if expressed), and `disqualifiers` (award 0 if present). The reference answer is
authored from the ground truth but is **never** given to the grader (it grades from the
rubric alone). The eval harness (`tools/eval_grader.py` + `tools/curate_eval_set.py`)
measures the grader model's MCAT reliability and reports a composite accuracy.
