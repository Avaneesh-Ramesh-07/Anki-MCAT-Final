# PRD: MCAT Scoring Models — Memory / Performance / Readiness (Implementation Spec v2)

> **Audience:** an engineer/agent implementing or auditing the three MCAT scoring
> models. This is a _specification of intended behavior_ — use it to check the
> code and to build the missing pieces. It reflects the corrections agreed on
> 2026-07-02.
>
> **Scope of files:** memory model `rslib/src/mcat/mastery.rs`; performance model
> `rslib/src/mcat/performance.rs`; proto `proto/anki/mcat.proto`; dashboard
> `ts/routes/readiness/`. Reviewer time→rating mapping lives in
> `qt/aqt/reviewer.py`. Readiness has no backend yet and must be built.

IMPORTANT: some of the stuff below is already implemented. some isn't. I believe most of the memory model is implemented and some of the performance model is implement, but it is PARAMOUNT that you verify this.

## As always, incorporate this into the existing RUST framework. DO NOT build a layer above the framework for these features.

## 0. How to use this doc

- Requirements are IDed (`S#`, `M#`, `P#`, `R#`) so you can tick each against the code.
- **DECISION** blocks are settled design choices — implement them as written, do not "fix" them.
- **MUST BE HANDLED** blocks are correctness hazards that an implementation is required to address explicitly.
- **STORAGE** blocks call out data-model changes an item implies.

---

## 1. Shared foundations (apply to all three models)

- **S1 — Topic identity.** A "topic" is an AAMC note tag `aamc::<section>::<topic>`
  (e.g. `aamc::bio-biochem::enzyme-kinetics`). A note may carry several `aamc::`
  tags; every matching tag receives that card's contribution.
- **S2 — Canonical sections.** Exactly four section codes, in exam order:
  `chem-phys`, `cars`, `bio-biochem`, `psych-soc`. The section is the first
  `::`-segment after the `aamc::` prefix.
- **S3 — Three numbers, shown separately.** Memory, Performance, and Readiness are
  always presented as three distinct scores, each with a point estimate + range.
  Readiness is the _only_ sanctioned composite; nothing else is blended.
- **S4 — Confidence range = 95% Wilson score interval.** Proportion `p` over `n`
  observations, `z = 1.96`. `n = 0` ⇒ `(0.0, 1.0)` (maximal uncertainty). Clamp to `[0,1]`.
- **S5 — Give-up / abstain rule (per model).** A model shows _no number_ until it
  has enough evidence; below the line it states _what evidence is missing_.
  Thresholds are tunable. **Memory** and **Performance** use a single evidence
  count; **Readiness** uses a compound rule (see R4).
- **S6 — FSRS is mandatory.** The scheduler is always FSRS (force-enabled on load);
  the memory model reads FSRS DSR state and must never fall back to SM-2.
- **S7 — Comfort signal source.** The reviewer collapses grading to **"Forgot"**
  (Again/1) and **"Got it"** graded by answer time (Easy ≤5s / Good ≤15s / Hard
  slower). Time influences the memory model **only** through this rating.
- **S8 — No AI.** All three models are pure statistics over data Anki already
  stores or over user-submitted practice tallies.

---

## 2. MEMORY MODEL — "Mastery Query" · (refinements below)

**M0 — Question:** _"Can you remember the facts right now?"_

**M1 — Inputs.** A card search (empty = whole collection) and `min_reviews`
(0 ⇒ default). Per card: FSRS `memory_state`, `decay` (default
`FSRS5_DEFAULT_DECAY`), last-review time (card field, else revlog), the note's
`aamc::` tags, and graded revlog entries `(taken_millis, button_chosen)`.

**M2 — Retrievability per card.** FSRS
`current_retrievability_seconds(state, seconds_since_last_review, decay)`.

**M3 — Unseen cards count as 0 and pull the mean down. (REQUIRED)**
A card with no memory state / no last review contributes **retrievability = 0**
to its topic's mean — it is _not_ skipped.

> **DECISION (M3):** unseen/unstudied cards MUST dilute the memory score. A high
> memory score while cards remain unseen misleads the user into thinking a topic
> is covered when it isn't. "Seen but weak" and "never seen" both lower the mean.

**M4 — Two-pass aggregation.** Pass 1 collects each card's retrievability + rated
latencies and a global latency list. Pass 2 folds each card into its topic
accumulators and one collection-wide `overall` accumulator.

**M5 — Headline memory score = MEAN RETRIEVABILITY. (REQUIRED)**
`memory_score = retrievability_sum / total_cards` (0 if no cards). This — not the
"fraction mastered" — is the number the dashboard MUST display as the Memory score.

> **DECISION (M5):** the dashboard reads **mean retrievability** as the Memory
> headline. `mastered_count/total_cards` is shown only as supporting detail.

**M6 — Comfort augmentation stays DISABLED. (DECISION)**
`comfort_factor = 1 − MAX_COMFORT_PENALTY · (effortful_reviews / reviews)`, with
`MAX_COMFORT_PENALTY = 0.0`, i.e. `comfort_factor = 1`.

> **DECISION (M6) — why 0, do not change:** FSRS consumes the **rating**, not raw
> answer latency. The fork's reviewer already maps answer-time → rating (S7), so
> slowness is _already_ reflected in the rating → FSRS → retrievability. Applying
> an additional latency penalty here would **double-count** time. There is no way
> (and no need) to pass raw `taken_millis` into FSRS separately. Keep the penalty
> at 0; `effortful_reviews` may remain computed for future tunability but MUST NOT
> affect the score while the reviewer owns the time→rating mapping.

**M7 — Range.** Wilson interval (S4) of the raw mean over `reviews`, multiplied by
`comfort_factor` (=1), clamped.

**M8 — Abstain** when `reviews < min_reviews`.

**M9 — Output (`TopicMastery`), per topic + `overall`:** `topic`, `memory_score`
(mean retrievability), `range_low`, `range_high`, `mastered_count`, `total_cards`,
`reviews`, `abstain`. Topics sorted by tag.

**M10 — Tunables:** `MASTERED_RETRIEVABILITY = 0.9`; `SLOW_LATENCY_FACTOR = 1.5`;
`DEFAULT_MIN_REVIEWS = 5`; `GOOD_BUTTON = 3`; `MAX_COMFORT_PENALTY = 0.0` (see M6).

---

## 3. PERFORMANCE MODEL — topical practice tests · (add recency decay + dashboard coverage)

**P0 — Question:** _"Can you answer new, exam-style questions on this topic?"_
This measures **extrapolation to unseen questions**, which is why staleness must
lower it (P3).

**P1 — Independent from memory. (REQUIRED)**
Performance is computed **only** from submitted practice-test evidence — never
from card reviews / FSRS state — and memory is never derived from practice
evidence. Two separate truth sources, by design.

> **DECISION (P1):** keep the models fully decoupled. Do not let one read the other's store.

**P2 — Evidence submission & storage.** On grading a topical test, the client
submits `(test_id, section_code, [(topic, correct, answered)])`. Evidence
accumulates per `aamc::` topic.

> **STORAGE (P2 → P3):** the store MUST record **timing** so recency decay is
> possible. Recommended: keep per-attempt records `{ t: unix_time, correct,
> answered }` per topic (not just cumulative totals), so each attempt can be
> weighted by age. At minimum, store the last-attempt timestamp per topic.

**P3 — Recency decay. (NEW — REQUIRED)**
A topic's performance score MUST **decay toward 0 as time since the last topical
test on that topic grows.** Rationale: performance predicts the ability to answer
_new_ questions today; evidence from long ago is weaker proof of that.

- **P3.1** Recommended model — recency-weighted accuracy. Each attempt `i` gets a
  weight `w_i = decay(now − t_i)`; the topic score is
  `Σ(w_i · correct_i) / Σ(w_i · answered_i)`.
- **P3.2** Default decay = exponential half-life: `decay(Δ) = 0.5 ^ (Δdays / HALF_LIFE_DAYS)`,
  `HALF_LIFE_DAYS` tunable (suggested default **30**). Monotonically decreasing, `∈ (0,1]`.
- **P3.3** The Wilson range uses the (recency-weighted) effective `n`, so a stale
  topic shows a lower score **and** a wider range.
- **P3.4** Abstain (P5) is judged on **raw** total answered (the tests did happen);
  decay lowers the score/confidence rather than re-hiding it. (Tunable; confirm at build.)

**P4 — Roll-ups.** Per section: sum topic evidence by S2 (recency-weighted per P3).
Scaled score: documented linear map `round(118 + fraction·14)` per section
(`SCALE_MIN=118`, `SCALE_MAX=132`; four sections ⇒ `[472,528]`). `scaled_total`
sums only non-abstaining sections. Also an `overall` rollup.

**P5 — Abstain** when a topic/section has fewer than `DEFAULT_MIN_QUESTIONS = 5`
answered (raw).

**P6 — Coverage transparency in the dashboard. (NEW — REQUIRED)**
Performance reflects **only sections/topics the user has actually tested.** The
dashboard MUST make this explicit rather than implying full-exam coverage:

- **P6.1** Show all four canonical sections (S2). For sections with no evidence,
  render a clear **"Not tested yet"** state (not blank, not 0%).
- **P6.2** Label the performance headline as covering _tested topics only_, and
  show `scaled_total` with an indicator of how many of the 4 sections it includes
  (e.g. "≈ scaled 510 · 2 of 4 sections tested").
- **P6.3** Never present a partial `scaled_total` as if it were a full 472–528 exam score.

**P7 — Tunables:** `DEFAULT_MIN_QUESTIONS = 5`; `SCALE_MIN=118`; `SCALE_MAX=132`;
`HALF_LIFE_DAYS = 30` (P3).

---

## 4. READINESS MODEL — the composite · (build this)

**R0 — Question:** _"What would you score on the real exam today?"_ Readiness is
the only sanctioned composite; it consumes Memory + Performance + Full-length.

**R1 — No backend exists yet.** Build: a `ReadinessQuery` RPC + `TopicReadiness`
message, a `readiness` module in `rslib/src/mcat/`, a static **AAMC Content
Category Distribution** weight table (resource/config), and the **full-length
test** input (see R3). The dashboard's third card currently shows "Not available yet."

**R2 — Topical readiness = weighted sum of three components.**

```
readiness(topic) = 0.05 · memory(topic)
                 + 0.45 · topical_test(topic)
                 + 0.50 · fulllength_topic(topic)
```

- **R2.1 Weights (DECISION):** flashcards/memory **5%**, topical practice tests
  **45%**, full-length practice test **50%**. (Ordering: memory lowest → topical
  middle → full-length highest, per Insight 5: realistic proportions/timing is the
  strongest evidence.)
- **R2.2 Missing component ⇒ 0** (not "ignored"). A topic with strong memory but no
  topical/full-length evidence is dragged down — anti-overconfidence.

**R3 — Full-length component is TOPIC-RESOLVED and captures the stress factor. (REQUIRED)**
The `fulllength_topic(topic)` component is the user's accuracy on **that topic's
questions _within_ completed full-length exams** — not a single global full-length
number, and not the standalone topical-test score.

> **DECISION / RATIONALE (R3):** a student performs differently on a short,
> isolated topical test than on the _same topic_ embedded in a full-length exam
> (fatigue, timing pressure, interleaving). Scoring the full-length component
> **per topic** — while _also_ keeping the standalone topical-test score as its own
> 45% component — is what encodes this stress/timing difference into readiness.
> Both a topical-test score (R2, component 2) and a full-length-derived topical
> score (R2, component 3) must feed the sum.
>
> **STORAGE (R3):** record full-length attempts with a per-topic breakdown
> `{ exam_id, t, [(topic, correct, answered)] }`, plus a global count of completed
> full-length exams (for R4). Edge case: if a completed full-length contained no
> questions for `topic`, that topic's component 3 = 0 (per R2.2).

**R4 — Give-up rule (compound). (REQUIRED)**
Readiness for a topic **abstains** (shows no number) until **BOTH**:

1. **Evidence gate:** the topic has ≥ `N` graded reviews **and** ≥ `N` topical
   practice tests covering it (`N` tunable, suggested small, e.g. 5 / 1 — confirm at build), **AND**
2. **Full-length gate:** the user has completed **≥ 1 full-length practice exam.**

> **DECISION (R4):** with no full-length exam on record, readiness MUST abstain
> entirely — it may never show a number from memory+topical alone. This is
> intentional and interacts with R2.2: before any full-length, component 3 = 0
> would cap readiness at 50%, but we don't even show that — we abstain until a
> full-length exists.

**R5 — Full (overall) readiness (Insight 6).** Aggregate per-topic R2 across all
topics, weighted by the **AAMC Content Category Distribution**, **assuming every
question wrong on unstudied topics** ("unstudied = 0" is intrinsic; no separate
coverage-map UI).

**R6 — Transparency (REQUIRED).** Show the component breakdown (5/45/50
contributions), point estimate, **range**, a "how-sure" indicator, last-updated,
and main reasons. Never a black box.

**R7 — Output (proposed).** `ReadinessQueryResponse { topics: [TopicReadiness],
overall }` where `TopicReadiness { topic, readiness_score, range_low, range_high,
components { memory, topical, full_length }, abstain }`, and `overall` is the
AAMC-weighted full readiness (R5).

**R8 — Tunables:** component weights `{0.05, 0.45, 0.50}` (R2.1); evidence gate `N`
and full-length gate (R4); AAMC weight table values (R5).

---

## 5. MUST BE HANDLED (correctness hazards — required)

- **MBH-1 — Two different "zeros." (REQUIRED)** `R2.2` "missing = 0" (a component
  the user hasn't done on an _otherwise-studied_ topic) and `R5` "unstudied = 0"
  (a topic the user has _never touched_) are different situations. The
  implementation MUST handle both, and MUST distinguish them from **abstain**:
  - _Abstain_ (S5/M8/P5/R4) = "not enough evidence" → show a message, **never a 0**.
  - _Score-of-0 component_ (R2.2) = a real, studied topic missing one component →
    contributes 0 to the sum and drags the (shown) readiness down.
  - _Unstudied = 0_ (R5) = untouched topics contribute 0 to the AAMC-weighted
    **full** readiness aggregate, lowering it.
  - **UX rule:** abstain and score-of-0 MUST NOT render identically. Per-topic
    display of an abstaining topic shows "not enough evidence"; the full-readiness
    aggregate still counts unstudied/thin topics as 0 (conservative). Define, in
    code, exactly how a topic that would abstain individually contributes to the
    full aggregate (recommended: treat as 0, consistent with anti-overconfidence).

- **MBH-2 — No double-counting of time (memory).** Keep `MAX_COMFORT_PENALTY = 0`
  while the reviewer owns time→rating (M6). If that reviewer mapping is ever
  removed, revisit — but do not stack both.

- **MBH-3 — Partial coverage never masquerades as a full score.** Performance
  `scaled_total` (P6) and full readiness (R5) must both make missing coverage
  visible rather than silently reporting a smaller-but-full-looking number.

---

## 6. Open / tunable parameters (report effect, don't hand-pick silently)

| Param                                          | Model          | Default            | Notes                       |
| ---------------------------------------------- | -------------- | ------------------ | --------------------------- |
| `MASTERED_RETRIEVABILITY`                      | Memory         | 0.9                | "mastered" recall threshold |
| `DEFAULT_MIN_REVIEWS`                          | Memory         | 5                  | abstain gate                |
| `MAX_COMFORT_PENALTY`                          | Memory         | 0.0                | keep 0 (M6)                 |
| `DEFAULT_MIN_QUESTIONS`                        | Performance    | 5                  | abstain gate                |
| `HALF_LIFE_DAYS`                               | Performance    | 30                 | recency decay (P3)          |
| Scaled map                                     | Perf/Readiness | linear 118–132     | documented approximation    |
| Component weights                              | Readiness      | 0.05 / 0.45 / 0.50 | fixed by decision (R2.1)    |
| Readiness evidence gate `N` + full-length gate | Readiness      | tbd / ≥1 exam      | R4                          |
| AAMC content weights                           | Readiness      | table              | R5 resource                 |

**Calibration target:** when a model says 80%, observed outcomes should be ≈80%
(Brier / log-loss). Ranges + give-up rules exist to keep thin estimates honest.
