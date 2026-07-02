# PRD: MCAT Readiness Features for Anki — Post-MVP (AI Layer)

> The AI-dependent features from the Avaneesh Ramesh BrainLift, deferred out of the MVP.
> These build directly on the MVP's practice-test engine and readiness model.
> Hybrid format: product requirements + technical mapping to real Anki components.
>
> **Companion doc:** [anki_prd_mvp.md](anki_prd_mvp.md) (F1, F2, F3, F6, F7, F8, F9 —
> no AI). Feature IDs are stable across both docs; this doc covers **F4 and F5**.

---

## Context

The MVP delivers the full non-AI loop: curated fact decks (F1), an answer-time comfort
signal (F2), MCQ topical and full-length practice tests (F3, F6), a weighted AAMC readiness
score (F7), progression gating (F8), and an adjustable timeline (F9).

What the MVP **cannot** do is assess _synthesis through production_ — the BrainLift's
strongest, "spikiest" claim. The MCAT is a synthesis exam (Source 6), and active retrieval
in a testing setting beats passive review (Source 2 / Roediger). MCQ tests retrieval
recognition; they don't force the learner to _generate_ an explanation, and a correct MCQ
answer can be a lucky guess that inflates the readiness score (Source 3 / Bjork — fluency
illusion). This layer closes that gap with two AI-powered features:

- **F4** — written/short-answer items graded 1–10 (SPOV 2).
- **F5** — an "explain your reasoning" step scored by similarity to the canonical
  explanation (Insight 2).

Both require an LLM, which is why they are post-MVP: Anki today is offline-first with **zero
outbound model calls**, so adding them is the single biggest architectural change in the
whole roadmap (see "AI integration" below).

### Effect on the three models

These features upgrade the **performance model** (MCQ → MCQ + graded production) and
sharpen the **readiness model** (a generation-based confidence adjustment replaces the
MVP's answer-time-only overconfidence penalty).

---

## Goals / Non-Goals

**Goals**

- Add graded written retrieval so practice resembles the synthesis the real exam demands (transfer-appropriate processing, Source 4).
- Give partial-credit, _explanatory_ feedback (1–10 + rationale), not binary right/wrong.
- Use a generation-based signal to detect and dampen overconfidence (lucky-guess correct MCQs).
- Keep the AI dependency **isolated, optional, and privacy-respecting** — the MVP must keep working with AI off/offline.

**Non-Goals**

- AI that **generates study content** or replaces the learner's own retrieval (explicitly out of scope per BrainLift — no RAG, no synthesis-for-the-user).
- Real-time/per-keystroke grading; an async "submit → results" flow is sufficient.
- Replacing MCQ scoring — written items _augment_ the existing test engine.

---

## Feature Catalog

### F4 — Written Answers + AI Grading (1–10)

**Source:** SPOV 2; Source 2 (active retrieval in a test setting); Source 4 (format fidelity).

**Problem.** The MCAT is MCQ, but binary MCQ grading doesn't tell the learner _what_ they
got wrong, and passively reading "how concepts interrelate" is inefficient. Written
retrieval forces synthesis, and partial-credit grading makes the feedback actionable.

**Requirements.**

- R4.1 Topical tests (F3) and optionally full-length tests (F6) include **short-answer/essay** items alongside MCQ. (Relies on the MVP item-type hook, R3.5.)
- R4.2 **AI grades on a 1–10 scale** (not binary) to give partial credit, with a written rationale of what was correct and what to improve.
- R4.3 Grading must be **rubric-anchored** (model answer + rubric per question) for consistency and to limit AI variance.
- R4.4 Grading runs **async** ("submit test → see results"); latency and cost are budgeted for batch grading, not per-keystroke.
- R4.5 Written-item scores feed the readiness model (F7) — either as an enriched topical-test component or a distinct synthesis component (decision below).

**Anki touchpoints.**

- Extends the MVP practice-test data model and RPC service (F3) with written item type, rubric storage, and a grade record (1–10 + rationale).
- Grading itself runs in the **external-AI service** (see architecture), not in core `rslib`.
- UI: a written-answer input + a results view showing score and rationale, added to the Practice Test Svelte route.

**Success metrics.** Grading agreement with human raters (target correlation / Cohen's κ ≥ agreed threshold); learners report the 1–10 + rationale is actionable.

---

### F5 — "Explain Your Reasoning" Similarity Scoring

**Source:** Insight 2; Source 3 (overconfidence / fluency illusion); Source 2 (active synthesis).

**Problem.** Even correct MCQ answers can be lucky guesses. Asking _why_ an answer is
correct forces synthesis and exposes shallow understanding the MCQ alone can't detect.

**Requirements.**

- R5.1 After answering a (synthesis) MCQ item, the user writes **why** their answer is correct.
- R5.2 AI computes a **similarity score** between the user's rationale and the canonical explanation.
- R5.3 (Insight 2) Higher similarity → higher confidence in the readiness estimate; a low similarity on a _correct_ answer flags an overconfidence/luck case and **dampens that item's readiness contribution** — this generalizes the MVP's answer-time-only penalty (R7.1b).
- R5.4 Reuses the same external-AI integration and rubric/explanation store as F4.

**Anki touchpoints.**

- Adds a reasoning-capture step to the F3 test flow and a similarity field on the attempt record.
- Updates the F7 readiness computation (`rslib/src/stats/`) so R7.1b consumes the similarity-based dampener in addition to answer-time mismatch.
- Same external-AI service and Claude-API path as F4.

**Success metrics.** Similarity score predicts performance on later items in the same topic (validity check); correct-but-low-similarity cases correlate with worse full-length performance.

---

## AI Integration (the key architectural decision)

This is the defining constraint of the post-MVP layer and the reason it isn't in the MVP.

- **Anki is offline-first with no LLM calls today.** F4/F5 introduce a network dependency.
- **Recommended design:** route grading and similarity through the **Claude API** (e.g.,
  `claude-opus-4-8` for grading quality, or a cheaper Claude model where cost dominates)
  behind a **dedicated backend grading service** that the app calls — **not** embedded in
  the syncable core `rslib`. This keeps the collection format, sync, and offline study
  paths clean and unchanged.
- **Privacy & opt-in:** written answers and rationales leave the device, so the feature is
  **explicit opt-in** with clear disclosure. Without consent or network, the app falls back
  to **MCQ-only** (the full MVP experience) — no feature is _blocked_ by AI being off.
- **Rubric anchoring** (R4.3) and a fixed prompt/rubric per question are required to keep
  1–10 grades and similarity scores consistent across attempts and model versions.
- **Cost/latency budget:** batch/async grading at submit time; cache grades per
  (question, answer) where reuse is safe.

**Open question — readiness integration (R4.5):** should written-item scores be folded into
the existing topical-test component of F7, or added as a _new, higher-weighted_ synthesis
component? The BrainLift weights production-of-synthesis highly, which argues for a distinct
component — to be decided with real grading data.

---

## AI Evaluation & Safety Gates (blocking — run before any student sees AI output)

The spec gates the AI work hard: _AI claims with no traceable source → the AI section scores
zero_, and every AI output must be checked against a held-out set and beat a simpler method.
These gates are **blocking**: F4/F5 do not ship to a user until each passes. (Mirrors the
Friday AI requirements; the MVP doc tracks these in its TODO → Post-MVP / AI list.)

- **G1 — Traceable source (hard requirement).** Every grade (F4) and similarity score (F5)
  cites its **named source** — the per-question rubric + model answer it was scored against.
  No rubric, no grade. (Spec hard limit: untraceable AI ⇒ the AI section = 0.)
- **G2 — Pre-release eval with a cutoff.** Before students see AI output, run the grader on a
  **held-out** set and report **accuracy and wrong-answer rate** against a **pre-set cutoff**;
  block any item or config that fails it. For F4, measure agreement with human raters
  (correlation / Cohen's κ ≥ the agreed threshold).
- **G3 — Beat a simpler baseline.** F5's LLM similarity must be shown to **beat a keyword /
  TF-IDF (vector) baseline** on the same held-out rationales — otherwise the baseline wins. A
  fancier method that doesn't beat the cheap one isn't justified.
- **G4 — AI-off still scores.** With AI disabled or offline, the app falls back to the full
  MCQ MVP experience and still produces all three scores — no feature is _blocked_ by AI being
  off.
- **G5 — Prompt-injection defense.** Any text the model consumes (user rationales, stored
  model answers) is **untrusted**: a hidden-instruction attempt in an input must not change a
  grade or leak the rubric. Test with adversarial inputs (spec §10).
- **G6 — §7f card-generation check — N/A by design.** We do **not** generate study cards with
  AI (see Non-Goals), so the §7f gold-set card check doesn't apply. State this as a deliberate
  skip in the Friday "what AI you built / what you skipped" note so the choice is on the record,
  not a silent omission.
- **G7 — Grading stability.** Grades and similarity scores must be stable across attempts and
  model versions — rubric anchoring (R4.3), a fixed prompt per question, and caching per
  (question, answer) where reuse is safe.

---

## How features reach the UI/backend (shared technical pattern)

Same proto → Rust → TS/Py pattern as the MVP (see [anki_prd_mvp.md](anki_prd_mvp.md)),
extended with the external grading service:

- New/extended messages on the practice-test service for written items, grades, and
  similarity scores (`proto/anki/`, service impl pattern in `rslib/src/stats/service.rs`).
- The grading service is a separate process/endpoint the backend calls out to; the core
  Rust/Python layers only persist results and never call the model directly.
- Svelte: extend the Practice Test route (`ts/routes/`) with the written-answer input,
  reasoning step, and results view; new strings in `ftl/core/`.

---

## Phasing & Dependencies

Single post-MVP phase; both features share the AI integration.

1. **AI integration spike** — stand up the Claude-API grading service, opt-in flow, offline fallback, rubric store. (Prerequisite for both F4 and F5.)
2. **F4** Written answers + 1–10 grading (SPOV 2).
3. **F5** Explain-your-reasoning similarity scoring (Insight 2), then wire its dampener into F7.

**Dependencies:** F4, F5 → require MVP F3/F6 test engine + F7 readiness model, plus the
AI integration spike. F5's readiness dampener → modifies MVP R7.1b.

---

## Cross-Cutting Risks & Open Questions

- **AI is the biggest architectural shift** — network dependency, privacy posture, cost,
  latency, and graceful degradation must all be solved before either feature ships.
- **Grading variance / fairness:** AI grades must be stable across attempts and model
  versions; rubric anchoring and evaluation against human raters are mandatory.
- **Privacy/compliance:** written answers leaving the device needs disclosure and consent;
  confirm what's acceptable for the target user base.
- **Readiness weighting (R4.5):** unresolved until there's grading data.
- **Don't regress the MVP:** AI off/offline must always fall back to the full MCQ experience.

---

## Success Metrics (rollup)

- **Validity:** explanation-similarity (F5) and written scores (F4) predict full-length performance better than MCQ alone.
- **Actionability:** learners rate the 1–10 + rationale feedback as useful.
- **Trust:** the overconfidence dampener measurably reduces correct-but-shallow inflation of the readiness score.
- **Safety:** AI-off fallback works; opt-in and disclosure are clear.

---

## Traceability (BrainLift → Post-MVP Feature)

| BrainLift item                                                      | Post-MVP Feature |
| ------------------------------------------------------------------- | ---------------- |
| SPOV 2 (written questions, AI 1–10 grading)                         | F4               |
| Insight 2 (explanation-similarity scoring, overconfidence dampener) | F5               |

_(All other SPOVs/Insights are delivered in the MVP — see [anki_prd_mvp.md](anki_prd_mvp.md).)_
