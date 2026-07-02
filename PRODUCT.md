# Product

## Register

product

## Users

Pre-med students preparing for the MCAT. They arrive anxious and time-pressured,
often studying late at night, measuring themselves against a high-stakes exam
that gates medical school. Their context is repeated, effortful self-testing:
reviewing flashcards, taking practice questions, and checking "am I ready yet?"
The emotional weight is the defining trait — the numbers on screen can either
reassure or frighten.

## Product Purpose

An MCAT-focused build of Anki that separates three honest signals of readiness —
**Memory** (can you recall facts now?), **Performance** (can you answer exam-style
questions?), and **Readiness** (what would you score today?) — and shows them
plainly, with confidence ranges and give-up rules instead of a single blended,
AI-flavored number. Success is a student who trusts the numbers, understands what
each one means, and feels steadied rather than judged when they open the app.

## Brand Personality

Calm, encouraging, honest. Three words: **reassuring, warm, trustworthy.** The
voice is a supportive study partner — human and plain-spoken, never clinical and
never babyish. It celebrates progress without hype and states limits without
alarm (no red "failure" signals, no false precision).

## Anti-references

- Clinical medical-dashboard aesthetics (stark white, dense tables, red alerts).
- Gamified kids'-app look — cartoon mascots, confetti, loud primary colors,
  patronizing tone. Friendly must not tip into childish for adult test-takers.
- Hype-driven "AI readiness score" products that collapse everything into one
  authoritative-looking number.
- High-saturation SaaS marketing gradients and hero-metric templates.

## Design Principles

1. **Lower the temperature.** Every screen should make an overwhelmed studier
   feel calmer. Calm is the primary job, not a nice-to-have.
2. **Honest over impressive.** Show ranges, evidence counts, and "not enough
   evidence yet" states. Never fake precision or blend away uncertainty.
3. **Encourage, don't grade.** Progress reads as growth (blue → green), never as
   failure (no red for scores). Copy is supportive and specific.
4. **Warm, not childish.** Hand-drawn softness and friendly rounded type earn
   trust; keep it tasteful enough for an adult preparing for medical school.
5. **Consistent across surfaces.** Readiness, practice tests, and results share
   one calm visual language so the tool disappears into the studying.

## Accessibility & Inclusion

Target WCAG 2.1 AA. Body text ≥ 4.5:1, large/decorative ≥ 3:1 (validated in both
light and the night-sketchbook dark theme). Respect `prefers-reduced-motion`:
the score-bar fill and card entrances degrade to their final state with no
animation. Score bars expose `role="progressbar"` with `aria-valuenow/min/max`
and a text label, so meaning never depends on color alone. Must work in both
Anki light mode and night mode.
