---
target: free-response practice-test UI (FreeResponseCard.svelte)
total_score: 25
p0_count: 1
p1_count: 2
timestamp: 2026-07-02T19-56-19Z
slug: ts-routes-practice-tests-freeresponsecard-svelte
---

# Critique — Free-Response Practice-Test UI

Method: dual-agent (A: a77c085303edb1363 · B: ae9f60666a3669bc5)
Target: ts/routes/practice-tests/FreeResponseCard.svelte + integration in PracticeTests.svelte. Register: product.
Browser overlays: not available (no Chrome binary; dev server HTTP 500; graded state needs full app + live grader). Detector CLI is the deterministic evidence.

## Design Health Score

| #         | Heuristic                       | Score     | Key Issue                                                                                           |
| --------- | ------------------------------- | --------- | --------------------------------------------------------------------------------------------------- |
| 1         | Visibility of System Status     | 2         | Async grade is an italic text line — no aria-live, no spinner/skeleton (FreeResponseCard.svelte:39) |
| 2         | Match System / Real World       | 3         | Plain and warm; "FR1"/"graded by rubric" mildly jargony                                             |
| 3         | User Control and Freedom        | 3         | Textarea locks on grade; retake resets; no regrade/abort                                            |
| 4         | Consistency and Standards       | 2         | Verdict icon always green ✓ even at 0/4 — opposite of QuestionCard's ✓/✗ convention                 |
| 5         | Error Prevention                | 2         | Empty answer silently graded 0; no length guidance (:26-35)                                         |
| 6         | Recognition Rather Than Recall  | 3         | Reference answer + rationale shown post-grade; rubric hidden while writing                          |
| 7         | Flexibility and Efficiency      | 3         | Adequate; single textarea, no shortcuts                                                             |
| 8         | Aesthetic and Minimalist Design | 3         | Calm and clean; results view is one long fully-expanded wall                                        |
| 9         | Error Recovery                  | 2         | Prints raw backend grade.error, no retry (:69-74)                                                   |
| 10        | Help and Documentation          | 2         | No AI-grade honesty caveat at the results moment                                                    |
| **Total** |                                 | **25/40** | **Acceptable — significant improvements needed before these users are reassured**                   |

## Anti-Patterns Verdict

Does this look AI-generated? No — above-average, restrained work.

LLM assessment: Clean on nearly every absolute ban (no side-stripe borders, gradient text, eyebrows, numbered scaffolding, identical-card-grid). Earns familiarity by reusing the MCQ QuestionCard shell. The one genuine strangeness-without-purpose is semantic: the results verdict borrows QuestionCard's success grammar but detaches it from correctness (green ✓ regardless of score) — see P0.

Deterministic scan: detect.mjs over both Svelte files → exit 0, zero findings, []. No mechanical slop tells, no false positives. Detector and design review agree: the problems are emotional-honesty/judgment issues, not pattern-level slop.

Visual overlays: not available this run (no Chrome-for-Testing binary; dev server HTTP 500; graded FRQ state needs full app + live OpenAI call + temp route + i18n mock — out of scope for read-only critique). Emotional/contrast findings verified by reading source.

## Overall Impression

Good scaffolding — the calmest, most familiar way to add an AI grader to a practice test. But it fumbles the one moment that matters most for this product: when an anxious pre-med meets the machine's judgment. A 0/4 answer renders as a green success card with a checkmark, no encouraging copy, and a full reference answer under the dimmed attempt. The reassurance discipline real elsewhere ("check-in, not a verdict"; "not enough evidence yet") didn't travel to the results screen. Biggest opportunity: make the verdict tone track the score, and carry the honesty voice into this moment.

## What's Working

1. Earned familiarity through component reuse — the card mirrors QuestionCard exactly, so the FRQ feature feels native, not grafted-on.
2. "No red" is honored honestly — missed criteria use blush terracotta #9c5a39 and sage/blush tints, never red for a score.
3. Resilient failure posture — grading is best-effort async (PracticeTests.svelte:142-154); results show instantly and a grader outage degrades to self-grade-against-reference.

## Priority Issues

[P0] False-positive verdict — green ✓ "success" card on any score, including 0/4. (FreeResponseCard.svelte:41-45, :142-145, :162-172)

- Why: emotional core of the feature; a failing score shown as a green checkmark is dishonest and confusing, eroding brand trust; violates "honest over impressive."
- Fix: derive verdict tone from points ratio; reserve ✓/sage for full credit; calm neutral (sky/ink, dot/pencil glyph) for partial/zero; add one warm non-grading line on low scores. Icon is aria-hidden → sighted-user harm; fix is logic/CSS.
- Command: /impeccable clarify (+ /impeccable colorize for ratio→tone).

[P1] Textarea has no accessible name. (:21-33)

- Why: prompt is a <span>, field relies on a vanishing placeholder → unlabeled multiline field for SR users. WCAG 2.1 AA 4.1.2/3.3.2 failure.
- Fix: aria-labelledby the prompt (give it an id) or wrap a real <label>; placeholder as hint only.
- Command: /impeccable harden.

[P1] Loading & error states aren't announced, and the error is raw. (:39, :69-74)

- Why: .pending has no aria-live/aria-busy; unavailable branch prints raw backend grade.error (e.g. "429 rate limit exceeded") — alarming, not a calm voice.
- Fix: aria-live="polite" region; skeleton instead of italic line; map errors to one reassuring sentence + Retry.
- Command: /impeccable harden.

[P2] --mcat-ink-faint used for load-bearing text below its own contrast contract. (:128-132)

- Why: "Worth N points · graded by rubric" carries meaning but uses the token labeled "< 4.5:1 as body" (theme.scss:33). Verified night-mode #8e867b on #2a2724 ≈ 4.1:1 (fails AA).
- Fix: use --mcat-ink-soft for the meta line (and audit sibling .scaled-note).
- Command: /impeccable colorize.

[P2] No length/scope guidance for a rubric-graded answer. (:26-35)

- Why: students don't know how much to write; blank/under-answers silently graded 0 (PracticeTests.svelte:119).
- Fix: hint ("aim for ~2-4 sentences") and/or soft counter; gentle confirm on empty submit.
- Command: /impeccable clarify.

## Persona Red Flags

Sam (Accessibility-Dependent): unlabeled textarea (:21-33); async result never announced (:39) so field appears inert after submit; criterion met/unmet is glyph+color with no text status (:48-53), inconsistent with QuestionCard; raw backend error read aloud verbatim.

"Maya" the Anxious Pre-Med (project persona): green ✓ on 0/4 reads as gaslighting; no length guidance spikes pre-submit anxiety; no encouragement at the low-score moment; reference answer sits under her dimmed, locked attempt inviting harsh self-comparison; "AI grading unavailable — [technical error]" reads as "the machine broke and it's on me."

Jordan (First-Timer): no explanation of what "AI grading" is or how far to trust it before being handed a score; the "!" unavailable card is ambiguous and reuses the success badge shape (:70-71); "graded by rubric" sets an expectation the take view doesn't meet.

## Minor Observations

- .answer:disabled { opacity: 0.85 } (:124-126) dims the student's own submitted text on results — the text they most want to re-read.
- Textarea focus is a 1px ring (:119-123) while buttons use 2px — thin/inconsistent for a keyboard-first field.
- The "!" unavailable badge reuses the success-badge shape; an "i" info glyph would read less alarming.
- Headline scorecard is MCQ-only (PracticeTests.svelte:199-204): FRQ points feed topic evidence but never the top scaled number; add a one-line "essays inform your topic map, not this score."
- Reference answer always fully expanded; no truncation/expand for long answers.

## Questions to Consider

- If the AI grade is an estimate everywhere else, why does the FRQ verdict present "Score: X/Y" with an authoritative success checkmark? Should it carry an "AI-reviewed, not final" caveat?
- Is a checkmark ever the honest icon for a graded score, or should scores use a neutral mark and reserve ✓ strictly for "criterion met"?
- Why does the headline score silently exclude free-response — what does that teach about whether writing matters?
- Should rubric criteria be visible while writing (open-book), or is hiding them part of the test — and is that intentional and communicated?
