# MCAT Free-Response Grader — Evaluation

> **Archived.** This is the original MCQ-based _model-competence_ eval — does the
> grader model understand MCAT content well enough to grade it? The current
> _grader-accuracy_ eval (keyword vs. AI on real answers) now lives in
> [EVAL.md](EVAL.md).

This document explains the offline evaluation that backs the **AI grader** used
for free-response questions (FRQ) in the MCAT topical practice tests: what the
eval is for, exactly what it does, how to reproduce it, and the result from the
run of record. It is written to be self-explanatory months later, with no prior
context.

- **Harness:** [`tools/eval_grader.py`](tools/eval_grader.py)
- **Curation (one-time):** [`tools/curate_eval_set.py`](tools/curate_eval_set.py)
- **Result of record:** composite accuracy **0.801** (350 questions,
  `gpt-4.1`, 2026-07-03). Full table below.

---

## 1. Why this eval exists

The practice tests contain hand-authored free-response questions. Each FRQ ships
with a rubric, and an OpenAI model grades a student's written answer against that
rubric at submission time (the in-app grader lives in Rust:
[`rslib/src/backend/mcat.rs`](rslib/src/backend/mcat.rs), RPC
`GradeFreeResponse`). Before trusting a model to assign partial credit that feeds
the student's Performance score, we need evidence that the model actually
understands MCAT content well enough to grade it.

**Purpose in one sentence:** measure how reliably the chosen OpenAI model reasons
about real MCAT material, so we can justify (and, later, re-justify when we change
models) using it as the FRQ grader.

### What this eval is and is NOT

- It is **not** a direct test of the FRQ grader or the rubrics. It does not send
  FRQs or rubrics to the model.
- It **is** a test of the model's underlying subject competence — the knowledge
  the grader relies on — measured on a curated, ground-truth multiple-choice set
  with official answer explanations.

The reasoning: if the model can independently answer curated MCAT questions and
its reasoning matches the official explanations, it has the subject
understanding needed to apply a rubric fairly. If it cannot, no rubric will make
its grading trustworthy. A direct FRQ-grading eval would require a labeled corpus
of graded student essays, which we do not have; this MCQ-based proxy is the
strongest signal available from the ground-truth material we do have.

### "Don't train the grader on ground truth" — how it's honored

The **answering agent** (step 1 below), like the real in-app FRQ grader, never
sees any answer key or explanation. Only the **judge** (step 3) sees ground
truth, and the judge never grades a real student — it only scores the eval. The
grader's knowledge is thus never seeded from the ground-truth corpus.

---

## 2. What the eval does (pipeline)

The eval is a two-model pipeline run over the curated set, one question at a time,
grouped by subject. Every model call is deterministic (`temperature: 0`, fixed
`seed`) and constrained to return JSON.

1. **Answering agent** — given _only_ the question stem and options (no key, no
   explanation), the model picks an answer and writes 2–4 sentences of reasoning.
   This mirrors what the in-app grader has access to: the problem, not the answer.

2. **Judge** — given the ground-truth correct answer, the ground-truth
   explanation, **and** the agent's choice + reasoning, the model scores how well
   the agent's answer and reasoning match the ground truth on a `0.0–1.0` scale.
   Correct choice with sound, on-topic reasoning scores high; wrong choices or
   reasoning that contradicts the explanation score low.

3. **Composite accuracy** — the **mean judge score** across all graded questions,
   reported per subject and overall. A raw **exact-match rate** (did the agent
   pick the keyed letter?) is reported alongside as a baseline. Composite accuracy
   is the headline metric because it credits partially-right reasoning and
   penalizes right-for-the-wrong-reason answers, which is closer to how rubric
   grading behaves than a pure right/wrong count.

```
stem + options ──▶ [ANSWERING AGENT] ──▶ {choice, reasoning}
                       (no ground truth)          │
                                                   ▼
ground-truth answer + explanation ─▶ [JUDGE] ─▶ score 0..1
                                                   │
                                  mean over all ◀──┘  =  composite accuracy
```

Both the answering-agent and judge system prompts are defined at the top of
[`tools/eval_grader.py`](tools/eval_grader.py) (`ANSWER_SYSTEM`, `JUDGE_SYSTEM`).

---

## 3. The curated ground-truth set

- **Source:** `resources/ground_truth/MCAT_Qbook.pdf` (copyrighted MCAT
  material; see content policy below).
- **Builder:** [`tools/curate_eval_set.py`](tools/curate_eval_set.py) extracts
  the PDF with `pymupdf`, cleans control/zero-width characters, parses each
  question's stem + options, and matches each to its correct letter + explanation
  using the Qbook's continuous global question numbering.
- **Output:** `resources/ground_truth/eval_set.json` — **50 questions per
  subject × 7 subjects = 350** MCQs, each `{subject, id, stem, options, correct,
  explanation}`.
- Subjects: `biochemistry`, `biology`, `gen-chem`, `orgo`, `physics`,
  `psychology`, `sociology`.

The eval set was curated **by subject (7)** deliberately, so accuracy can be read
per content area rather than as a single opaque number.

---

## 4. How to run it

Requires an OpenAI API key with network egress. The key is read from the
environment or from `.env.local` / `.env` at the repo root (loaded automatically;
see [`.env.example`](.env.example)). `pymupdf` and `httpx` must be present in the
project pyenv (`out/pyenv`); curation installs `pymupdf` once.

```bash
# 1. (one-time) build the curated ground-truth set from the Qbook PDF
out/pyenv/bin/python tools/curate_eval_set.py

# 2. run the full eval (350 questions)
out/pyenv/bin/python tools/eval_grader.py

# cheaper variants:
out/pyenv/bin/python tools/eval_grader.py --subject biology         # one subject
out/pyenv/bin/python tools/eval_grader.py --limit 10                # 10/subject smoke run
out/pyenv/bin/python tools/eval_grader.py --model gpt-4o            # try another model
```

- Model defaults to `OPENAI_EVAL_MODEL` (env) else `gpt-4.1`.
- **No key ⇒ prints a notice and exits 0** (safe in CI; the eval is never a build
  gate).
- Each run prints the per-subject + overall table and saves a timestamped
  `resources/ground_truth/eval_results_<UTC-timestamp>.json` with every per-question
  record (agent choice, key, exact-match, judge score).

### Content policy (why results aren't committed)

`resources/ground_truth/` is **git-ignored in its entirety**. The Qbook PDF, the
curated `eval_set.json` (verbatim ground-truth questions + explanations), and the
`eval_results_*.json` files must **never** be committed or distributed — they
contain copyrighted MCAT source material. This `EVAL.md` (approach + aggregate
numbers) is safe to commit; the underlying data is not.

---

## 5. Result of record

Full 350-question run:

| Field                                     | Value                                            |
| ----------------------------------------- | ------------------------------------------------ |
| Date (UTC)                                | 2026-07-03 (`eval_results_20260703-193019.json`) |
| Model                                     | `gpt-4.1`                                        |
| Questions                                 | 350 (50 × 7 subjects)                            |
| **Composite accuracy (mean judge score)** | **0.801**                                        |
| Exact-match rate (baseline)               | 0.763                                            |

Per subject:

| Subject      | n       | Composite accuracy | Exact-match |
| ------------ | ------- | ------------------ | ----------- |
| sociology    | 50      | 0.910              | 0.880       |
| biology      | 50      | 0.872              | 0.840       |
| biochemistry | 50      | 0.860              | 0.800       |
| psychology   | 50      | 0.810              | 0.780       |
| physics      | 50      | 0.752              | 0.700       |
| gen-chem     | 50      | 0.732              | 0.720       |
| orgo         | 50      | 0.668              | 0.620       |
| **OVERALL**  | **350** | **0.801**          | **0.763**   |

### How to read this

- Composite accuracy (0.801) sits above the exact-match baseline (0.763),
  meaning the judge is crediting sound reasoning even on some questions where the
  final letter was wrong — as intended.
- **Knowledge/verbal-heavy subjects score high** (sociology, biology,
  biochemistry, psychology: ~0.81–0.91). The model is a reliable grader for these,
  which is where most FRQ rubric points live (bio/biochem and psych/soc tests).
- **Calculation-heavy subjects still trail but improved markedly** (physics,
  gen-chem, orgo: ~0.67–0.75, up from ~0.54–0.58 under `gpt-4o-mini`). `gpt-4.1`
  handles multi-step quantitative work far better, though orgo remains the weakest.

### Implications for the grader

- The default `gpt-4.1` is well justified across FRQ content: it grades the
  conceptual, higher-scoring subjects reliably and now handles the
  calculation-heavy subjects far better than `gpt-4o-mini` did. FRQ rubrics are
  also capped at `max_points ≤ 4` (≈ ≤4 MCQs of evidence), so a mis-grade has
  bounded impact on the Performance score.
- If FRQ coverage of organic chemistry / general chemistry / physics expands, or
  if higher grading fidelity is wanted there, re-run this eval with a stronger
  model and set `OPENAI_GRADER_MODEL` accordingly. The eval is the mechanism for
  justifying any such model change — re-run it and update the "Result of record"
  table above.

---

## 6. Related files

- In-app grader (Rust): [`rslib/src/backend/mcat.rs`](rslib/src/backend/mcat.rs),
  proto [`proto/anki/mcat.proto`](proto/anki/mcat.proto) (`GradeFreeResponse`).
- FRQ content + rubrics: [`resources/practice_tests/`](resources/practice_tests/)
  (see its `README.md` for the FRQ schema and per-test counts), authored via
  [`tools/build_frq.py`](tools/build_frq.py).
- Eval harness: [`tools/eval_grader.py`](tools/eval_grader.py); curation:
  [`tools/curate_eval_set.py`](tools/curate_eval_set.py).
- Keys / config: [`.env.example`](.env.example) (`OPENAI_API_KEY`,
  `OPENAI_EVAL_MODEL`, `OPENAI_GRADER_MODEL`, `OPENAI_BASE_URL`).
