# MCAT FRQ Grader — Accuracy Eval

The free-response (FRQ) grader has two modes: an **AI grader** (`gpt-4.1`) and a
deterministic, offline **keyword-match fallback** (used when AI grading is toggled
off on the Home page). Keyword lists are authored from the ground-truth reference
answers; the matcher lives in
[`rslib/src/backend/mcat.rs`](rslib/src/backend/mcat.rs) (`keyword_grade`). This
benchmarks the two graders against realistic student answers.

> Earlier MCQ-based model-competence evals are archived in
> [OLD_EVAL.md](OLD_EVAL.md).

## Method

For each of the **89 FRQs**, three answers of known outcome are graded by _both_
real graders (via the backend RPC, toggling `mcatAiGrading`):

- **correct** — the ground-truth reference answer (should earn credit);
- **off-topic wrong** — a _different_ FRQ's reference answer graded against this
  rubric (should score 0);
- **jargon-heavy wrong** — a fluent answer that uses the right terminology but
  states incorrect science (should score 0); authored from the ground truth and
  saved to `resources/ground_truth/frq_adversarial.json`.

A grader is "correct" on an item when it credits a correct answer (awards ≥ 50% of
points) or rejects a wrong one (< 50%).

## Accuracy

| Answer type        |   Keyword grader | AI grader (`gpt-4.1`) |
| ------------------ | ---------------: | --------------------: |
| Correct answers    |     100% (89/89) |          100% (89/89) |
| Off-topic wrong    |    96.6% (86/89) |          100% (89/89) |
| Jargon-heavy wrong |    **0% (0/89)** |     **84.3% (75/89)** |
| **Overall**        |        **65.5%** |             **94.8%** |

## Read-out

- Both graders reliably **credit correct answers** and **reject off-topic** ones.
- The gap is **jargon-heavy wrong answers**: keyword matching is fooled by _every_
  one (it can't tell "sounds right" from "is right"); the AI reads the reasoning
  and catches ~85%.
- That single failure mode is the whole story — it drops keyword accuracy to
  **65.5%** vs. the AI's **94.8%**. Keyword grading is a fine offline fallback, but
  only the AI protects a student from a confident, wrong answer.

_Reproduce:_ grade `frq_adversarial.json` (plus each FRQ's reference / off-topic
answer) with `mcatAiGrading` off (keyword) then on (AI) via
`col._backend.grade_free_response`. `resources/ground_truth/` is git-ignored
(copyrighted source material).
