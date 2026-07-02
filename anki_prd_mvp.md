# PRD: MCAT Readiness Features for Anki — MVP (No AI)

> Turns the **Avaneesh Ramesh BrainLift** (Spiky POVs + DOK 3 Insights) into buildable features,
> **built directly inside the existing Anki codebase** — not a plugin, add-on, or layer on top.
> AI-dependent features are deferred (see [anki_prd_post_mvp.md](anki_prd_post_mvp.md)). Technical
> reasoning follows [anki_tech_stack.md](anki_tech_stack.md): **one Rust engine (`rslib/`), two
> clients (desktop + Android), one protobuf IPC boundary**.

---

## 1. The Wednesday bar (hard MVP deliverable — "core works on both screens, no AI")

This is the must-hit milestone. Everything in §5+ is MVP product scope that builds on this core.

**Desktop**
- Anki **forked and building from source** (`just run` / `just build`).
- **Your Rust change working end to end** — the diff, **3 Rust unit tests**, and **1 test that calls it from Python**.
- A **review loop running on your exam deck** (the real Anki reviewer over an MCAT deck).
- A **memory model running, with an honest score: a range + the give-up rule** (see §6).
- An **installer that runs on a clean machine** (Briefcase — `qt/installer/`).

**Mobile**
- A phone app that **builds and runs on a real device or emulator** (AnkiDroid built against this fork's `anki` crate via `rsdroid`).
- It **loads your exam deck and runs a real review session on the shared engine.**
  **Two-way sync is *not* required yet; reviewing the same deck is.**

**Proof (the deliverable artifacts)**
- **Commit hash** + a **clean-build recording**, the **test results**, a **clean-machine install recording**, and a **screen recording of a review session on the phone.**

> Scope note: the Wednesday core = fork/build + the Rust memory-model change + review loop + the
> memory model (range + give-up rule) + installer + a phone review session. Practice tests,
> readiness roll-up, gating, and the timeline (§5) are the same MVP, sequenced after the core.

---

## 2. Why not just load an MCAT deck into vanilla Anki?

Anki is a bare spaced-repetition engine: a flashcard scheduler (FSRS) plus open deck sharing.
That is not enough for MCAT prep, for four reasons grounded in the BrainLift:

- **Flashcards test isolated facts, not the *relationships between ideas* the MCAT actually asks.**
  The MCAT is a synthesis exam (Source 6); flashcards are a memorization tool and work best on
  simple chunks (Source 1, Insight 1). Pure recall says little about exam readiness.
- **Anki has no practice tests** — especially the synthesis-style, topic-level tests that mirror the
  exam (Insight 1). Active retrieval in a test setting beats passive restudy (Source 2 / Roediger).
- **Anki has no way to measure knowledge / proficiency / readiness honestly.** Self-report
  (Hard/Good/Easy) inflates confidence (Source 3 / Bjork; Insight 3); a 100% flashcard score is a
  fluency illusion, not a readiness number.
- **Open deck search exposes unvetted, often-wrong decks** (Source 7, SPOV 1). A topically-correct
  but learning-science-poor deck misleads a learner who can't self-assess.

The MVP fixes the *inputs* (vetted fact-level decks), replaces self-report with a behavioral signal,
adds exam-style testing, and produces a defensible readiness estimate — **all without AI.**

---

## 3. Integration principle — inside the codebase, not a layer on top

**This is a hard architectural requirement.** Every feature is implemented **inside Anki's own
layers**, not as an add-on/plugin or external service:

- New logic lands in the **Rust core** (`rslib/`), exposed through the **protobuf IPC contract**
  (`proto/anki/*.proto`) — the single boundary every client uses. Build codegen
  (`rslib/proto/build.rs`) then regenerates the Rust trait (`rslib/src/services.rs`), the Python
  binding (`pylib/anki/_backend_generated.py`), and the TS client (`@generated/backend`).
- The desktop UI is added as **SvelteKit routes** (`ts/routes/`) served by `mediasrv`, and Qt glue
  in `qt/aqt/`. New strings go in `ftl/core/`.
- Because all real logic lives in the **shared `anki` crate**, the same engine change **ships to the
  phone unchanged** via `rsdroid`'s JNI bridge (per anki_tech_stack.md §1, §3) — no Kotlin
  reimplementation of scheduling or scoring.

The "real Rust engine change" requirement is satisfied by changing the engine itself (§4), not by
wrapping it.

---

## 4. Required Rust engine change — the Mastery Query (memory model)

**What.** A new backend RPC that returns, **per AAMC topic**, the **comfort-augmented DSR memory
score** and a **statistical range** (plus the underlying mastered-card count / mean recall), fast
enough to power the dashboard on a **50,000-card** deck. This single change satisfies *both*
Wednesday requirements: it **is** "your Rust change," and it **is** the memory model.

**Why Rust, not Python.** The aggregation scans the whole card/revlog set per dashboard load; doing
it in Rust over the collection's SQLite avoids marshalling the full card set across the PyO3/JNI
boundary, and the *same compiled query ships to the phone* via `rsdroid`. (anki_tech_stack.md §1.)

**Where it goes (in-codebase).**
- Proto: new `proto/anki/mcat.proto` with a `McatService` (modeled on `StatsService`), or extend
  `stats.proto` — per notes.md, a dedicated `mcat.proto` + `rslib/src/mcat/` is preferred.
- Rust impl: new `rslib/src/mcat/` implementing the generated trait for `Collection` (pattern:
  `rslib/src/stats/service.rs`, `stats/card.rs`); SQL aggregation over `cards` + `revlog`.
- Reuses existing FSRS state: `FsrsMemoryState` (`rslib/src/card/mod.rs`), retrievability
  (`extract_fsrs_retrievability` in `rslib/src/storage/sqlite.rs`; `current_retrievability_seconds`
  in `rslib/src/stats/card.rs`), and `RevlogEntry.taken_millis` (`rslib/src/revlog/mod.rs`).
- Expose: `qt/aqt/mediasrv.py` (`exposed_backend_list`); call from Svelte via `@generated/backend`.

**Required proof (Wednesday).** ≥3 Rust unit tests (`rslib/src/mcat/`) + 1 Python-calling test
(`pylib/tests/test_mcat.py`); undo-still-works / no-collection-corruption check; the diff.

**AAMC topic key (confirmed).** An **AAMC topic is attached via a tag** convention (e.g.
`aamc::biochem::amino-acids`). This tag is the **shared key across the whole MVP**: it drives the
Mastery Query aggregation (this section), **the topical practice tests (F3)**, the linear gating
(F8), and the readiness roll-up (F7). One topic tag → one memory score, one topical test, one
gate, one readiness component.

---

## 5. Feature catalog (BrainLift-driven, no AI)

Each feature traces to a Spiky POV / Insight. AI-only items (SPOV 2, Insight 2) are deferred (§9).

### F1 — Curated Deck Catalog (SPOV 1, Insight 4)
Replace open "Get Shared Decks" with a **curated catalog of empirically-solid, fact/terminology-level
decks** (no open-ended synthesis cards); users can't point it at arbitrary URLs.
- **R1.1** Curated catalog of vetted decks, each with an "empirically solid" status set by a steward.
- **R1.2** Catalog decks are **fact/terminology-level only** (deck-level flag + ingestion lint).
- **R1.3** Deck metadata: AAMC category/subtopic, card count, vetting status, version.
- **R1.4** Catalog is statically bundled or from a single trusted endpoint — no arbitrary URLs.
- **R1.5** Recommend decks for the user's current topic/gap rather than a search box (Insight 4).
- **Touchpoints:** repoint `_onShared()` in `qt/aqt/deckbrowser.py` (away from `aqt.appShared`);
  catalog metadata via `proto/anki/decks.proto` + `rslib/src/decks/mod.rs`; install reuses
  `qt/aqt/import_export/`; new `ts/routes/catalog/` page.

### F2 — Answer-Time Comfort Signal → the memory model (Insight 3)
FSRS spacing is driven by the self-reported button; learners exaggerate comfort. Replace that signal
with **answer latency**, and define the **memory-model score = the DSR score Anki already computes,
augmented with the comfort-level change.**
- **R2.1** Per-card **comfort score** from answer latency, normalized to the user's own rolling
  distribution (z-score/percentile) so it's robust to fast vs. slow users.
- **R2.2** Detect confidence mismatches (e.g. "Easy" + slow = likely guessing) and use the mismatch
  as the **comfort adjustment that discounts the raw DSR/retrievability** to form the memory score.
- **R2.3** Comfort **augments, not replaces** FSRS scheduling in the MVP (don't destabilize the
  proven algorithm); it is the augmentation applied to the existing DSR (§6, §4).
- **R2.4** Cap/clean outliers (idle, backgrounded) — reuse FSRS time-capping.
- **Touchpoints:** read `rslib/src/revlog/mod.rs` (`taken_millis`, `button_chosen`); DSR in
  `rslib/src/card/mod.rs` + `rslib/src/stats/card.rs`; compute in `rslib/src/mcat/`.

### F3 — Topical Synthesis Practice Tests, MCQ (Insight 1)
A **topical test mode**: synthesis-style **multiple-choice** questions for the user's current AAMC
topic, with **trick questions + pre-authored explanations** of why each distractor is wrong
(targets overconfidence). Static content — **no AI.**
- **R3.1** Topical MCQ test mode **keyed by AAMC topic**: the same `aamc::…` topic tag that drives
  the memory model (§4) selects which questions appear, so a topic's flashcards and its topical
  practice test share one AAMC topic key. Each question is tagged to its AAMC topic.
- **R3.2** Trick questions with pre-authored per-distractor explanations.
- **R3.3** Tests are **scored and timed**; attempts persist per topic for the readiness model.
- **R3.4** Distinct from flashcards — discrete graded sessions, not scheduled FSRS cards.
- **R3.5** *(Post-MVP hook)* item-type field so written/short-answer items (F4/F5, AI) slot in later.
- **Touchpoints:** new MCQ/attempt data model + RPCs in `proto/anki/mcat.proto` + `rslib/src/mcat/`
  (persist attempts in the collection DB); reference `qt/aqt/customstudy.py`; new
  `ts/routes/practice-test/` page.

### F6 — Full-Length Practice Tests, MCQ (Insight 1)
A **full-length MCQ mode** across all four MCAT sections (Bio/Biochem, Chem/Phys, Psych/Soc, CARS)
in realistic proportions/timing. Carries the **highest weight** in readiness (Insight 5).
- **Touchpoints:** extends the F3 engine (section sequencing + timing) — same service/module/route.

### F7 — Topical & Full Readiness Scores (Insight 5, Insight 6)
Honest, **separately shown** scores with ranges — never one blended number.
- **R7.1 Topical readiness** = weighted sum, **lowest → highest**:
  (1) **DSR memory score** (the §6 memory model), (2) **synthesis topical-test score**,
  (3) **full-length test score**. **Missing component → 0** (Insight 5; anti-overconfidence).
- **R7.2 Full readiness** = percentage that **assumes every question wrong on unstudied topics**
  (Insight 6), aggregated across topics by the **AAMC Content Category Distribution** weights, each
  topic scored by R7.1. (No separate coverage-map UI; "unstudied = 0" is intrinsic to this formula.)
- **R7.3** Transparent component breakdown (not a black box).
- **R7.4 Give-up rule** = abstain until there is **enough review evidence** (≥N graded reviews on the
  topic/exam; N tunable). Below the line, show what evidence is missing — never a number (§6).
- **R7.5** Show **memory / performance / readiness** as three distinct numbers, each with a point
  estimate, **range**, "how-sure" indicator, last-updated, and main reasons.
- **Touchpoints:** the §4 Mastery Query powers this; readiness module in `rslib/src/mcat/`; static
  AAMC weight table (config/resource); `ts/routes/readiness/` dashboard modeled on `ts/routes/graphs/`.

### F8 — Linear Progression Gating (Insight 7)
Enforce facts → topical tests → full-length tests.
- **R8.1** A topical test (F3) unlocks only after **X rounds of flashcards** on that topic.
- **R8.2** A full-length test (F6) unlocks only after **Y rounds of topical tests** (excluding a baseline).
- **R8.3** X and Y are **defaults, adjustable**.
- **Touchpoints:** thresholds in `proto/anki/deck_config.proto` + `rslib/src/deckconfig/mod.rs`;
  gate check in the F3 service; round counts from revlog + recorded attempts.

### F9 — Adjustable Ideal Timeline (Insight 7)
- **R9.1** Generate an ideal study timeline from exam date + AAMC weights + current readiness (F7).
- **R9.2** Adjustable (move exam date, reweight, change daily load) and recomputes.
- **R9.3** Respects the F8 gates.
- **Touchpoints:** planning module under `rslib/src/mcat/` (consumes F7+F8); UI on/near `ts/routes/readiness/`.

---

## 6. Memory model — design & the honest score (research)

The Wednesday core requires "a memory model running, with an honest score: a range + the give-up
rule." Per Insight 3, the **memory score = Anki's existing DSR (Difficulty, Stability,
Retrievability), augmented with the answer-time comfort change** — not a new model.

**Research question: what is the best way to build this memory model?** Things to settle/validate:
- **Aggregation:** per AAMC topic, take **mean FSRS retrievability** across the topic's cards
  (unstudied cards = 0), then **adjust by the comfort signal** (effortful/guessed recalls discount
  the raw value). Stability/difficulty inform the confidence indicator and down-weight fragile cards.
- **The range (pure statistics, no AI):** Wilson / beta-binomial confidence intervals on per-topic
  recall, widened by small sample size; aggregated under the AAMC weights for the full score.
- **The give-up rule:** abstain (show no number) until ≥N graded reviews of evidence exist for the
  topic/exam — "a system that knows when it doesn't know."
- **Calibration (how we'll know it's honest):** on held-out reviews, when the model says 80% the
  observed recall should be ≈80% (Brier score / log-loss). This is the primary, defensible proof.
- **Open:** the comfort→DSR adjustment function, the mastery threshold, and N for the give-up rule —
  to be tuned and reported with their effect, not hand-picked.

---

## 7. Mobile (shared-engine review; sync deferred)

Per the Wednesday bar, the phone must **build, run, load the exam deck, and run a real review
session on the shared engine** — **two-way sync is explicitly out of MVP scope.** Because the engine
is the shared `anki` crate, this is an AnkiDroid build against this fork (pin `rsdroid`'s `anki`
dependency to the fork, build via `cargo-ndk`), not new review logic. No Android/NDK build config
lives in this repo (it's in the separate Anki-Android / Anki-Android-Backend repos, per
anki_tech_stack.md §3). The Rust memory-model change (§4) ships to the phone automatically; surfacing
its scores in a Kotlin UI is post-MVP.

---

## 8. Phasing

- **Phase 0 — Wednesday core:** fork+build; the §4 Mastery Query (Rust change, e2e tests); review
  loop on the exam deck; the §6 memory model (range + give-up rule); installer; phone builds + runs a
  review session on the shared deck.
- **Phase 1 — Inputs + testing:** F1 curated catalog; F2 comfort signal wired into the memory score;
  F3 topical MCQ tests (trick questions).
- **Phase 2 — Readiness + pacing:** F7 topical → full readiness (Insight 5/6); F6 full-length tests;
  F8 gating; F9 timeline.

---

## 9. Deferred to post-MVP (AI — explicitly out of this MVP)

- **SPOV 2 — written/short-answer questions graded 1–10 by AI** (partial credit) → F4, post-MVP doc.
- **Insight 2 — "explain your reasoning" + AI similarity score** vs. model explanations → F5, post-MVP.
- MVP performance model is **MCQ-only**; the F3 item model is built so AI items slot in without a rewrite.

---

## 10. Traceability (BrainLift → MVP feature)

| BrainLift item | MVP feature | Status |
|---|---|---|
| SPOV 1 (empirically-solid decks, no open search) | F1 | In MVP |
| Insight 4 (recommend reliable fact/terminology decks) | F1 | In MVP |
| Insight 3 (comfort from answer time; memory score = DSR + comfort) | F2 + §4 + §6 | In MVP |
| Insight 1 (topical synthesis + full-length tests, trick questions) | F3, F6 | **MCQ only** in MVP |
| Insight 5 (topical readiness = weighted sum, missing = 0) | F7 | In MVP |
| Insight 6 (full readiness, AAMC-weighted, unstudied = 0) | F7 | In MVP |
| Insight 7 (linear gating + adjustable timeline) | F8, F9 | In MVP |
| §7a-style real Rust engine change | Mastery Query (§4) | In MVP |
| **SPOV 2** (written questions, AI 1–10 grading) | **F4 → post-MVP** | Requires AI |
| **Insight 2** (AI explanation-similarity scoring) | **F5 → post-MVP** | Requires AI |

---

## 11. Open questions / assumptions

1. **Rust change = the Mastery Query (memory model).** Assumed it serves both "your Rust change" and
   "memory model running." Confirm, or pick a different engine change (e.g. topic-aware scheduling).
2. **AAMC topic representation** — **confirmed: a tag** convention (`aamc::…`), used as the shared
   key for the memory model (§4), the topical practice tests (F3), gating (F8), and readiness (F7).
3. **No coverage-map feature** — "unstudied = 0" lives in the readiness formula (R7.2); the give-up
   rule is **review-evidence-based**, not coverage-based.
4. **MCQ bank + AAMC weight table** are content workstreams the MVP depends on (supplied, not authored here).
5. **Exam = MCAT** throughout.
