---
target: free-response practice-test UI (FreeResponseCard.svelte)
total_score: 34
p0_count: 0
p1_count: 2
timestamp: 2026-07-02T20-27-04Z
slug: ts-routes-practice-tests-freeresponsecard-svelte
---

# Critique (re-run) — Free-Response Practice-Test UI

Method: dual-agent (A: a7d93baf1c3e2066c · B: a83d97b8fc00411f1)
Target: ts/routes/practice-tests/FreeResponseCard.svelte + PracticeTests.svelte. Register: product.
Browser overlays: skipped (no Chrome binary; dev server HTTP 500; graded state needs full app + live grader). Detector CLI is the deterministic evidence.

## Design Health Score

| #         | Heuristic                      | Score     | Key Issue                                                         |
| --------- | ------------------------------ | --------- | ----------------------------------------------------------------- |
| 1         | Visibility of System Status    | 3         | Async FRQ grading has no _visible_ "working…" line (only sr-only) |
| 2         | Match System / Real World      | 4         | Warm plain voice                                                  |
| 3         | User Control and Freedom       | 3         | Retry only on failure; successful FRQ can't be re-graded          |
| 4         | Consistency and Standards      | 3         | Night-mode verdict icons break (P1)                               |
| 5         | Error Prevention               | 3         | Blank FRQ silently graded 0                                       |
| 6         | Recognition Rather Than Recall | 4         | Prompt/answer/criteria/reference co-visible                       |
| 7         | Flexibility and Efficiency     | 3         | Single linear flow; no draft-save/shortcuts                       |
| 8         | Aesthetic and Minimalist       | 4         | Calm, uncluttered, on-brand                                       |
| 9         | Error Recovery                 | 4         | "AI grading isn't available right now" done right                 |
| 10        | Help and Documentation         | 3         | Inline caveat + hint; no upfront "how FRQ grading works"          |
| **Total** |                                | **34/40** | **Good — solid foundation, address the two weak areas**           |

Trend: 25 -> 34 (+9). Prior P0 and both P1s confirmed fixed, now strengths.

## Anti-Patterns Verdict

Does this look AI-generated? No — LOW risk. Clean on every absolute ban; consistent component vocabulary (mirrors QuestionCard); native affordances; no display fonts in labels; earned familiarity.

Deterministic scan: detect.mjs over both files -> exit 0, [], zero findings. Re-ran with --no-config; nothing suppressed. Detector and review agree: no mechanical slop introduced; remaining issues are contrast/disclosure/announcement judgment calls.

Visual overlays: skipped (no Chrome-for-Testing; dev server 500; graded state needs full app + live grader). Contrast computed by hand in both themes.

## Overall Impression

Fixes landed; the surface is now genuinely good. The 0/4 verdict (calm blue, ○, "No points yet — and that's okay… give it another go") is a textbook "encourage, don't grade," and the grading-unavailable state is the hard case done right. What remains: a real dark-mode contrast failure on the verdict icon, and the headline score silently ignoring the essays. Biggest opportunity: make dark mode carry the ✓, and disclose where free-response effort goes.

## What's Working

1. Score-driven verdict tone, never red (FreeResponseCard.svelte:29-58) — green ✓ only at full; calm blue ◐/○ for partial/zero; outcome-matched encouragement. Verified: tracks the actual score.
2. Grading-unavailable + safe Retry — calm copy, self-grade fallback, regradeFrq never re-records (PracticeTests.svelte:143-163), raw error in <details>.
3. Accessibility scaffolding — aria-labelledby accessible name, aria-live + aria-busy region, sr-only behind every color/glyph, skeleton with prefers-reduced-motion fallback.

## Priority Issues

[P1] Night-mode verdict/criterion icon glyphs nearly vanish. (FreeResponseCard.svelte:256-274)

- Why: color:#fff on a *-ink fill, but in night mode -ink tokens are lightened for text-on-dark (theme.scss:108-116). Measured: verdict-icon on sky-ink = 1.85:1, full on sage-ink = 1.81:1, info on ink-soft = 2.26:1 — all below the 3:1 non-text floor. The ✓ is invisible in dark mode. (Same systemic pattern in QuestionCard.)
- Fix: in .night-mode give the glyph a dark ink color on the light -ink fill (or *-tint fill + *-ink text).
- Command: /impeccable colorize.

[P1] Headline score silently excludes free-response. (PracticeTests.svelte:222-229; scorecard :370-389)

- Why: scorePct/scaled derive from MCQ-only flatQuestions, yet graded FRQ feed the readiness model via mergeTallies. Scorecard never discloses the number is MCQ-only.
- Fix: one-line note ("Free response is graded separately below and feeds your readiness — not this score") and/or a "Free response: X/Y pts (AI estimate)" line.
- Command: /impeccable clarify.

[P2] No visible status while FRQ grade asynchronously. (FreeResponseCard.svelte:93)

- Why: only sr-only signal; the most charged moment is silent shimmer.
- Fix: calm visible line at the Free Response results header while any FRQ pending.
- Command: /impeccable harden.

[P2] Textarea aria-describedby dangles after grading. (FreeResponseCard.svelte:72, :79-83)

- Why: #hintId only rendered {#if !graded}, so aria-describedby points at a missing id post-grade; .meta not associated at all.
- Fix: give .meta an id, include in aria-describedby, keep a stable target post-grade.
- Command: /impeccable harden.

[P3] Secondary-text tokens below AA. .tech uses ink-faint on inset = 4.14:1 (light) at 0.78rem — below 4.5 for body; ink-faint is "large/decorative only". Fix: ink-soft for .tech body. Command: /impeccable harden.

## Persona Red Flags

- "Maya" Anxious Pre-Med: undisclosed MCQ-only headline; silent shimmer with no reassuring words; "Score: 0/4" leads with the grading word before encouragement.
- Sam (Accessibility, night mode): night-mode ✓ invisible at ~1.8:1; dangling aria-describedby; textarea focus ring is box-shadow with outline:none (:200-204) — stripped in Windows forced-colors mode.
- Jordan (First-Timer): no upfront heads-up that Free Response is AI-graded, worth points, and not in the headline; take-view section styled like "Discrete Questions".

## Minor Observations

- Retry only in failure branch; can't re-run a successful grade (though regradeFrq is safe).
- Blank FRQ -> 0/N; a "You didn't answer this one" short-circuit would be kinder.
- ◐ vs ○ subtle at 0.85rem on same blue — leans on the number.
- Sibling QuestionCard uses terracotta #9c5a39 + ✗ for wrong MCQ; may read "red-ish" at 1am. Worth a cross-card decision on the "not-perfect" vocabulary.

## Questions to Consider

- Should the headline include an honestly-labeled FRQ estimate, or does mixing an AI estimate into the exact MCQ number violate "honest over impressive"?
- Is grading a blank as 0/4 honest, or should un-attempted FRQ read "not attempted"?
- "No red" is enforced for FRQ but MCQ uses terracotta — is the real principle "no alarm," and does terracotta pass?
- Should the verdict ever lead with "Score: 0/4," or lead with encouragement and relegate the number?
