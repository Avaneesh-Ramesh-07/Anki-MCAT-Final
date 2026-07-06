# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""MCAT home / landing page.

The main window's default screen. Shows the student's overall MCAT readiness
score in big, calm type, and offers one-tap paths into the rest of the app
(their deck garden, the two kinds of practice test, statistics) plus sync.

Rendered as server HTML into ``mw.web`` (the DeckBrowser pattern) so it inherits
the app-wide Organic/Natural re-skin — warm paper, Fraunces headings, paper
grain — with no extra build wiring. The readiness score is fetched off the main
thread via a QueryOp so landing here never blocks startup.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from anki.collection import Collection
from aqt import AnkiQt
from aqt.mcat_limits import MCAT_NEW_PER_DAY_CAP
from aqt.operations import QueryOp
from aqt.sound import av_player
from aqt.theme import Theme, theme_manager
from aqt.toolbar import BottomBar

# Suggested-next-step model
##############################################################################
# The home page steers the student through the priority sequence
# flashcards -> topical tests -> full-length test, based on their live state.


@dataclass(frozen=True)
class TopicalTest:
    test_id: str
    label: str
    section: str


# The authoritative topical-test catalog lives in the web layer
# (ts/routes/practice-tests/tests.ts); we mirror just what the home page needs to
# reason about coverage. Keep this in sync if tests are added/removed.
TOPICAL_TEST_ROSTER: list[TopicalTest] = [
    TopicalTest("chem-phys-1", "Chem/Phys Test 1", "chem-phys"),
    TopicalTest("chem-phys-2", "Chem/Phys Test 2", "chem-phys"),
    TopicalTest("cars-1", "CARS Test 1", "cars"),
    TopicalTest("bio-biochem-1", "Bio/Biochem Test 1", "bio-biochem"),
    TopicalTest("bio-biochem-2", "Bio/Biochem Test 2", "bio-biochem"),
    TopicalTest("psych-soc-1", "Psych/Soc Test 1", "psych-soc"),
    TopicalTest("psych-soc-2", "Psych/Soc Test 2", "psych-soc"),
]
_ROSTER_BY_ID: dict[str, TopicalTest] = {t.test_id: t for t in TOPICAL_TEST_ROSTER}
_ROSTER_IDS: set[str] = set(_ROSTER_BY_ID)

# Flashcard discipline tag (last segment of aamc::<section>::<discipline>) -> name.
TOPIC_LABEL: dict[str, str] = {
    "biochemistry": "Biochemistry",
    "biology": "Biology",
    "gen-chem": "General Chemistry",
    "orgo": "Organic Chemistry",
    "physics": "Physics",
    "psychology": "Psychology",
    "sociology": "Sociology",
}

# Performance at/above this counts as "strong": steer toward breadth (new tests)
# rather than retaking. 0-1 scale. Also the per-test "scored below 85%" cutoff.
STRONG_PERFORMANCE = 0.85


@dataclass
class Suggestion:
    """A single 'what to do next' recommendation shown on the home page."""

    heading: str
    body: str  # may contain simple <b> emphasis
    cta_cmd: str  # pycmd fired by the primary button (decks/topical/fullLength)
    cta_label: str
    secondary_text: str = ""  # optional second line (may contain <b>)
    secondary_cmd: str = ""  # if set, the secondary line gets its own button
    secondary_label: str = ""
    hint: str = ""  # subtle guidance line (no button)


@dataclass
class HomeData:
    score: float
    low: float
    high: float
    abstain: bool
    suggestion: Suggestion | None


def _section_of(tag: str) -> str:
    parts = tag.split("::")
    return parts[1] if len(parts) >= 2 else ""


def _topic_label(tag: str) -> str:
    seg = tag.split("::")[-1]
    return TOPIC_LABEL.get(seg, seg.replace("-", " ").title())


def _join_labels(test_ids: list[str]) -> str:
    labels = [_ROSTER_BY_ID[t].label for t in test_ids if t in _ROSTER_BY_ID]
    if len(labels) <= 1:
        return labels[0] if labels else ""
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def build_suggestion(
    *,
    has_due: bool,
    due_total: int,
    perf_score: float,
    perf_abstain: bool,
    mastered_sections: dict[str, list[str]],
    taken: set[str],
    per_test_score: dict[str, float],
) -> Suggestion:
    """Pick the single best next step. Pure (no Qt/collection access), so it can
    be unit-tested directly.

    Priority: study due flashcards -> topical tests (weak first below 85%, then
    breadth) -> full-length. ``taken`` is a subset of the roster ids; each entry
    has a latest score in ``per_test_score``.
    """
    untaken = [t for t in TOPICAL_TEST_ROSTER if t.test_id not in taken]
    untaken_by_section: dict[str, list[TopicalTest]] = {}
    for t in untaken:
        untaken_by_section.setdefault(t.section, []).append(t)

    def test_for_section(section: str) -> TopicalTest | None:
        # Prefer an untaken test in the section; else its lowest-scoring taken one.
        opts = untaken_by_section.get(section)
        if opts:
            return opts[0]
        taken_in = [
            t
            for t in TOPICAL_TEST_ROSTER
            if t.section == section and t.test_id in taken
        ]
        if taken_in:
            return min(taken_in, key=lambda t: per_test_score.get(t.test_id, 0.0))
        return None

    # 1. Flashcards due today ------------------------------------------------
    if has_due:
        plural = "s" if due_total != 1 else ""
        sug = Suggestion(
            heading="Review today's flashcards",
            body=(
                f"You have <b>{due_total}</b> flashcard{plural} ready to review "
                "today. Watering your garden keeps every topic fresh."
            ),
            cta_cmd="decks",
            cta_label="Water your garden",
        )
        # Secondary: a fully-mastered topic -> a topical test that exercises it.
        for section, topics in mastered_sections.items():
            test = test_for_section(section)
            if test is not None:
                sug.secondary_text = (
                    f"You've fully mastered <b>{topics[0]}</b> — put it to the test "
                    f"with <b>{test.label}</b>."
                )
                sug.secondary_cmd = "topical"
                sug.secondary_label = "Take the test"
                break
        else:
            if not mastered_sections:
                sug.hint = (
                    "Master all of a topic's cards to unlock a recommended "
                    "topical test."
                )
        return sug

    # 2. Flashcards done for today ------------------------------------------
    # 2a. No topical test taken yet.
    if perf_abstain or not taken:
        first: TopicalTest | None = None
        for section in mastered_sections:
            first = test_for_section(section)
            if first is not None:
                break
        if first is None:
            first = untaken[0] if untaken else TOPICAL_TEST_ROSTER[0]
        return Suggestion(
            heading="Take your first topical test",
            body=(
                "Your flashcards are done for today. Start building your "
                f"performance score with a topical practice test — try "
                f"<b>{first.label}</b>."
            ),
            cta_cmd="topical",
            cta_label="Start a topical test",
        )

    pct = round(perf_score * 100)
    weak = sorted(
        (t for t in taken if per_test_score.get(t, 0.0) < STRONG_PERFORMANCE),
        key=lambda t: per_test_score.get(t, 0.0),
    )

    # 2b. Performance below 85% -> shore up weak areas (depth).
    if perf_score < STRONG_PERFORMANCE:
        if weak:
            plural = "s" if len(weak) != 1 else ""
            return Suggestion(
                heading="Shore up your weak spots",
                body=(
                    f"Your performance score is <b>{pct}%</b>. Retake the "
                    f"test{plural} where you scored below 85%: "
                    f"<b>{_join_labels(weak)}</b>."
                ),
                cta_cmd="topical",
                cta_label="Retake a topical test",
            )
        if untaken:
            return Suggestion(
                heading="Broaden your coverage",
                body=(
                    f"Your performance score is <b>{pct}%</b>. Keep climbing — "
                    f"take a topical test you haven't tried yet: "
                    f"<b>{untaken[0].label}</b>."
                ),
                cta_cmd="topical",
                cta_label="Take a topical test",
            )
        lowest = min(taken, key=lambda t: per_test_score.get(t, 0.0))
        return Suggestion(
            heading="Keep improving",
            body=(
                f"Your performance score is <b>{pct}%</b>. Revisit your lowest "
                f"test to push it higher: <b>{_ROSTER_BY_ID[lowest].label}</b>."
            ),
            cta_cmd="topical",
            cta_label="Retake a topical test",
        )

    # 2c. Performance >= 85% with untaken tests remaining -> breadth first.
    if untaken:
        return Suggestion(
            heading="Broaden your coverage",
            body=(
                f"Nice — you're at <b>{pct}%</b>. Take a topical test you haven't "
                f"tried yet to widen your prep: <b>{untaken[0].label}</b>."
            ),
            cta_cmd="topical",
            cta_label="Take a new topical test",
        )

    # 2d. Performance >= 85% and every topical test taken -> full-length.
    return Suggestion(
        heading="Time for a full-length test",
        body=(
            f"You've taken every topical test and you're at <b>{pct}%</b>. Put it "
            "all together with a full, timed MCAT simulation."
        ),
        cta_cmd="fullLength",
        cta_label="Start a full-length test",
    )


def build_home_suggestion(col: Collection) -> Suggestion | None:
    """Gather the live signals from the collection (safe to run off the main
    thread) and build the home-page suggestion."""
    # Flashcards ready today. New cards are capped per top-level deck at the same
    # daily limit the garden's "Plant seeds" enforces (MCAT_NEW_PER_DAY_CAP), so
    # this count is correct on open even when a deck's preset allows more (e.g. a
    # deck whose preset is set high still contributes at most the daily cap).
    root = col.sched.deck_due_tree()
    due_total = sum(
        n.review_count + n.learn_count + min(n.new_count, MCAT_NEW_PER_DAY_CAP)
        for n in root.children
    )

    # Overall performance (0-1); abstains until a topical test has been taken.
    perf = col._backend.performance_query(min_questions=0).overall
    perf_score, perf_abstain = perf.score, perf.abstain

    # Fully-mastered flashcard topics: every card in the deck mastered.
    mastered_sections: dict[str, list[str]] = {}
    for t in col._backend.mastery_query(search="", min_reviews=0).topics:
        if t.total_cards > 0 and t.mastered_count == t.total_cards and not t.abstain:
            section = _section_of(t.topic)
            if section:
                mastered_sections.setdefault(section, []).append(_topic_label(t.topic))

    # Per-topical-test taken status + latest score. No RPC exposes per-test data,
    # so read the raw attempt store; retakes append, keep the most recent per id.
    store = col.get_config("mcatPerformance", {})
    attempts = store.get("topical", []) if isinstance(store, dict) else []
    latest: dict[str, dict] = {}
    for a in attempts:
        tid = a.get("test_id")
        if tid in _ROSTER_IDS and a.get("t", 0) >= latest.get(tid, {}).get("t", -1):
            latest[tid] = a
    taken = set(latest)
    per_test_score: dict[str, float] = {}
    for tid, a in latest.items():
        topics = a.get("topics", {}) or {}
        correct = sum(int(v.get("correct", 0)) for v in topics.values())
        answered = sum(int(v.get("answered", 0)) for v in topics.values())
        per_test_score[tid] = (correct / answered) if answered else 0.0

    return build_suggestion(
        has_due=due_total > 0,
        due_total=due_total,
        perf_score=perf_score,
        perf_abstain=perf_abstain,
        mastered_sections=mastered_sections,
        taken=taken,
        per_test_score=per_test_score,
    )


# Readiness forest
##############################################################################
# A calm, decorative garden/forest that grows with the readiness score. It's
# rendered as inline SVG + CSS behind the Home content, framing the centered
# column in the left/right gutters, a ground strip, and a soft sky. Nearer items
# are drawn larger + sharper and farther ones smaller + hazier (a gentle 3-D),
# and the whole scene shifts subtly with the cursor (parallax). Animals arrive
# at readiness checkpoints: bees + butterflies >= 50%, squirrels >= 65%,
# deer >= 80%. All motion is slow/ambient and freezes under reduced-motion.

_CLOUD_SVG = (
    '<svg class="cloud-svg" viewBox="0 0 120 46" aria-hidden="true">'
    '<path d="M24 44C11 44 5 33 12 25 7 15 22 9 31 15 36 4 57 5 60 16c9-8 26-1 23 12'
    ' 11 1 12 15 0 16Z"/></svg>'
)

# A blooming flower (reused from the deck-browser garden). __V__ is swapped for a
# petal-colour variant class (f0 clay / f1 sky / f2 gold).
_FLOWER_SVG = (
    '<svg class="flower-svg __V__" viewBox="0 0 40 50" aria-hidden="true">'
    '<path class="fl-stem" d="M20 49V26"/>'
    '<path class="fl-leaf" d="M20 37c-5 .2-9.6-2.6-11-7.7 6.1-1.2 10.2 1.9 11 7.1z"/>'
    '<path class="fl-leaf" d="M20 32c4.7-.2 8.9-2.9 10-7.8-5.7-1-9.5 1.9-10 6.9z"/>'
    '<g class="fl-petals"><circle cx="20" cy="15" r="5.4"/><circle cx="13.4" cy="19" r="5.4"/>'
    '<circle cx="26.6" cy="19" r="5.4"/><circle cx="16" cy="9.8" r="5.4"/>'
    '<circle cx="24" cy="9.8" r="5.4"/></g><circle class="fl-core" cx="20" cy="15" r="3.3"/></svg>'
)

# A young sprout (early growth, from the coverage garden).
_SPROUT_SVG = (
    '<svg class="flower-svg" viewBox="0 0 40 50" aria-hidden="true">'
    '<path class="sp-stem" d="M20 49V30"/>'
    '<path class="sp-leaf" d="M20 34c-4 0-8-2.6-8.8-7 4.4-.9 8 1.8 8.8 6.2Z"/>'
    '<path class="sp-leaf" d="M20 32c3.6-.4 7-3.4 7.4-7.8-4.2-.4-7 2.6-7.4 7Z"/></svg>'
)

_GRASS_SVG = (
    '<svg class="grass-svg" viewBox="0 0 34 26" aria-hidden="true">'
    '<path d="M6 26C5 17 3 12 1 8M11 26C11 16 10 11 8 6M17 26C17 15 18 10 17 4'
    'M23 26C23 16 25 11 27 6M28 26C29 17 31 12 33 8"/></svg>'
)

_BEE_SVG = (
    '<svg class="bee-svg" viewBox="0 0 30 20" aria-hidden="true">'
    '<g class="bee-wings"><ellipse class="bee-wing" cx="12" cy="6" rx="4.6" ry="6.6"/>'
    '<ellipse class="bee-wing" cx="18" cy="6" rx="4.6" ry="6.6"/></g>'
    '<ellipse class="bee-body" cx="15" cy="13" rx="8" ry="5.4"/>'
    '<rect class="bee-stripe" x="12.3" y="8.4" width="2.3" height="9.4" rx="1.1"/>'
    '<rect class="bee-stripe" x="16" y="9" width="2.1" height="8.2" rx="1"/></svg>'
)

_BUTTERFLY_SVG = (
    '<svg class="bfly-svg" viewBox="0 0 28 24" aria-hidden="true">'
    '<g class="bfly-wings">'
    '<path class="bfly-wing" d="M14 12C10 4 2 3 3 9c-1 4 4 8 11 3Z"/>'
    '<path class="bfly-wing" d="M14 12C10 20 3 21 4 16c0-3 5-5 10-4Z"/>'
    '<path class="bfly-wing" d="M14 12C18 4 26 3 25 9c1 4-4 8-11 3Z"/>'
    '<path class="bfly-wing" d="M14 12C18 20 25 21 24 16c0-3-5-5-10-4Z"/></g>'
    '<rect class="bfly-body" x="13.2" y="5.5" width="1.6" height="13.5" rx="0.8"/></svg>'
)

_SQUIRREL_SVG = (
    '<svg class="critter-svg" viewBox="0 0 44 40" aria-hidden="true">'
    '<path class="cr-fill" d="M31 39C43 39 45 20 34 13c8 11-3 19-9 16Z"/>'
    '<path class="cr-fill" d="M15 39c-6 0-9-6-6-12 2-5 8-8 13-6 1-4 7-6 10-2 3 4 0 9-3 9'
    ' 2 4-2 11-8 11Z"/>'
    '<circle class="cr-fill" cx="31" cy="15" r="5"/>'
    '<path class="cr-fill" d="M33 9c0-3 4-2 3 1Z"/>'
    '<circle class="cr-eye" cx="33" cy="14" r="1"/></svg>'
)

_DEER_SVG = (
    '<svg class="critter-svg" viewBox="0 0 72 64" aria-hidden="true">'
    '<g class="cr-fill">'
    '<rect x="19" y="33" width="3.4" height="22" rx="1.6"/>'
    '<rect x="28" y="33" width="3.4" height="22" rx="1.6"/>'
    '<rect x="43" y="33" width="3.4" height="22" rx="1.6"/>'
    '<rect x="51" y="33" width="3.4" height="22" rx="1.6"/>'
    '<path d="M16 24c6-7 34-7 43 1 5 4 3 13-4 13H21c-8 0-11-9-5-14Z"/>'
    '<path d="M55 25c3-4 5-11 10-13 3-1 5 1 4 4-1 4-6 8-7 11Z"/>'
    '<ellipse cx="64" cy="12" rx="4.6" ry="3.3"/>'
    '<path d="M61 9c-2-3 1-5 3-3Z"/></g>'
    '<path class="cr-antler" d="M65 9c1-4-1-6 1-9M66 6c2-1 4-1 4-3M65 4c-2-1-3-2-4-4"/></svg>'
)


def _tree_svg(kind: str, fullness: float) -> str:
    """One tree glyph. `fullness` (0..1) grows the canopy; below ~0.28 the tree
    is a bare dormant sapling. `kind` is 'conifer' or 'round'."""
    if kind == "conifer" and fullness >= 0.28:
        body = (
            '<rect class="trunk" x="45" y="104" width="10" height="44" rx="4"/>'
            '<path class="canopy conifer" d="M50 76 L88 122 L12 122 Z"/>'
            '<path class="canopy conifer" d="M50 48 L80 98 L20 98 Z"/>'
            '<path class="canopy conifer" d="M50 20 L72 68 L28 68 Z"/>'
        )
    elif fullness < 0.28:
        body = (
            '<path class="branch" d="M50 148V54M50 92L32 72M50 104L70 82'
            'M50 76L36 58M50 66L66 50"/>'
        )
    else:
        f = 0.72 + fullness * 0.5
        body = (
            '<rect class="trunk" x="45" y="94" width="10" height="54" rx="4"/>'
            '<g class="canopy round">'
            f'<circle cx="50" cy="50" r="{34 * f:.1f}"/>'
            f'<circle cx="28" cy="66" r="{23 * f:.1f}"/>'
            f'<circle cx="72" cy="66" r="{23 * f:.1f}"/>'
            f'<circle cx="50" cy="76" r="{25 * f:.1f}"/>'
            "</g>"
        )
    return (
        f'<svg class="tree-svg" viewBox="0 0 100 152" aria-hidden="true">{body}</svg>'
    )


def build_forest(readiness: float) -> str:
    """The decorative forest layer whose lushness tracks the readiness score
    (0..1). Returns the `.forest` markup plus the parallax script. Layout is
    seeded so it stays put across re-renders and only fills in as the score
    grows."""
    r = max(0.0, min(1.0, readiness))
    rng = random.Random(20260705)

    def n(base: float, span: float) -> int:
        return max(0, round(base + r * span))

    def item(
        cls: str,
        x: float,
        y: float,
        w: float,
        depth: float,
        i: int,
        svg: str,
        dur: float | None = None,
    ) -> str:
        extra = f";--dur:{dur:.0f}s" if dur is not None else ""
        return (
            f'<span class="{cls}" style="left:{x:.1f}%;bottom:{y:.1f}%;'
            f'--w:{w:.0f}px;--depth:{depth:.2f};--i:{i}{extra}">{svg}</span>'
        )

    def tree() -> str:
        full = max(0.0, min(1.0, r + rng.uniform(-0.12, 0.12)))
        return _tree_svg(rng.choice(["conifer", "round", "round"]), full)

    def flower() -> str:
        if r < 0.32 or rng.random() > (0.3 + r * 0.7):
            return _SPROUT_SVG
        return _FLOWER_SVG.replace("__V__", rng.choice(["f0", "f1", "f2"]))

    lx, rx = (2.0, 32.0), (68.0, 98.0)  # gutters; center [34..66] stays clear
    parts: list[str] = []
    i = 0

    # sky: a soft sun + a couple of slow clouds
    sky = ['<div class="sun"></div>']
    for _c in range(2 + (1 if r > 0.5 else 0)):
        sky.append(
            f'<span class="cloud" style="top:{rng.uniform(6, 30):.0f}%;'
            f"width:{rng.uniform(90, 150):.0f}px;--dur:{rng.uniform(50, 80):.0f}s;"
            f'animation-delay:{rng.uniform(-45, 0):.0f}s">{_CLOUD_SVG}</span>'
        )
    parts.append(f'<div class="band sky">{"".join(sky)}</div>')

    # far: small hazy trees on the horizon
    far = []
    for k in range(n(3, 5)):
        far.append(
            item(
                "tree",
                rng.uniform(*(lx if k % 2 == 0 else rx)),
                rng.uniform(30, 46),
                rng.uniform(46, 66),
                rng.uniform(0.15, 0.32),
                i,
                tree(),
            )
        )
        i += 1
    parts.append(f'<div class="band far">{"".join(far)}</div>')

    # mid: medium trees + a deer at the treeline (>= 80%)
    mid = []
    for k in range(n(2, 6)):
        mid.append(
            item(
                "tree",
                rng.uniform(*(lx if k % 2 == 0 else rx)),
                rng.uniform(10, 26),
                rng.uniform(78, 104),
                rng.uniform(0.4, 0.6),
                i,
                tree(),
            )
        )
        i += 1
    if r >= 0.80:
        mid.append(item("critter deer", 22.0, 12.0, 64, 0.55, i, _DEER_SVG))
        i += 1
    parts.append(f'<div class="band mid">{"".join(mid)}</div>')

    # near: big edge trees + the flower beds + grass + a squirrel (>= 65%)
    near = []
    for k in range(n(1, 3)):
        near.append(
            item(
                "tree",
                rng.uniform(*((0.0, 13.0) if k % 2 == 0 else (87.0, 100.0))),
                rng.uniform(-2, 8),
                rng.uniform(120, 168),
                rng.uniform(0.82, 1.0),
                i,
                tree(),
            )
        )
        i += 1
    for lo, hi in ((1.0, 22.0), (78.0, 99.0)):
        for _k in range(n(0, 6)):
            near.append(
                item(
                    "flower",
                    rng.uniform(lo, hi),
                    rng.uniform(1, 12),
                    rng.uniform(34, 52),
                    rng.uniform(0.8, 1.0),
                    i,
                    flower(),
                )
            )
            i += 1
        for _k in range(n(1, 3)):
            near.append(
                item(
                    "grass",
                    rng.uniform(lo, hi),
                    rng.uniform(0, 6),
                    rng.uniform(30, 46),
                    rng.uniform(0.78, 0.98),
                    i,
                    _GRASS_SVG,
                )
            )
            i += 1
    if r >= 0.65:
        near.append(item("critter squirrel", 12.0, 9.0, 34, 0.9, i, _SQUIRREL_SVG))
        i += 1
        if r >= 0.85:
            near.append(item("critter squirrel", 87.0, 7.0, 30, 0.85, i, _SQUIRREL_SVG))
            i += 1
    parts.append(f'<div class="band near">{"".join(near)}</div>')

    # flying fauna: bees + butterflies once readiness passes 50%
    fauna = []
    if r >= 0.50:
        for _k in range(1 + round((r - 0.5) * 6)):
            fauna.append(
                item(
                    "bee",
                    rng.uniform(10, 90),
                    rng.uniform(20, 55),
                    rng.uniform(20, 30),
                    rng.uniform(0.5, 0.9),
                    i,
                    _BEE_SVG,
                    dur=rng.uniform(9, 15),
                )
            )
            i += 1
        for _k in range(round((r - 0.5) * 4)):
            cls = "butterfly b1" if _k % 2 else "butterfly"
            fauna.append(
                item(
                    cls,
                    rng.uniform(8, 92),
                    rng.uniform(16, 48),
                    rng.uniform(20, 30),
                    rng.uniform(0.5, 0.85),
                    i,
                    _BUTTERFLY_SVG,
                    dur=rng.uniform(12, 18),
                )
            )
            i += 1
    parts.append(f'<div class="band near fauna">{"".join(fauna)}</div>')

    parts.append('<div class="ground"></div>')

    return (
        f'<div class="forest" aria-hidden="true" style="--richness:{r:.2f}">'
        + "".join(parts)
        + "</div>"
        + _FOREST_PARALLAX_JS
    )


_FOREST_PARALLAX_JS = """
<script>
(function () {
  var f = document.querySelector('.forest');
  if (!f) return;
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  } catch (e) {}
  var raf = 0, tx = 0, ty = 0;
  window.addEventListener('pointermove', function (e) {
    var w = window.innerWidth || 1, h = window.innerHeight || 1;
    tx = (e.clientX / w - 0.5) * 2;
    ty = (e.clientY / h - 0.5) * 2;
    if (!raf) {
      raf = requestAnimationFrame(function () {
        raf = 0;
        f.style.setProperty('--px', tx.toFixed(3));
        f.style.setProperty('--py', ty.toFixed(3));
      });
    }
  }, { passive: true });
})();
</script>
"""


_FOREST_CSS = """
.home { position: relative; overflow: hidden; }
.home-inner { position: relative; z-index: 1; }

.forest {
    position: absolute;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    overflow: hidden;
    filter: saturate(calc(0.5 + var(--richness, 0) * 0.6));
    animation: forest-in 0.9s ease both;
    /* light palette — the .mcat garden colours, hardcoded because Home isn't
       inside a .mcat scope */
    --sky-tint: #cfe4ef;
    --sun: #f6ead0;
    --cloud: #fbfaf6;
    --bark: #8a6a4a;
    --leaf: #7c9a6d;
    --leaf-deep: #4c6142;
    --grass: #93ac79;
    --bloom-clay: #cf8f5f;
    --bloom-sky: #7fb0d0;
    --bloom-gold: #e3b466;
    --core: #f0d9a8;
    --bee-body: #e0a94e;
    --bee-stripe: #5a4326;
    --wing: rgba(255, 255, 255, 0.82);
    --critter: #b07d4f;
}
:root.night-mode .forest {
    opacity: 0.9;
    --sky-tint: #2c3f4c;
    --sun: #5f5a46;
    --cloud: #3a3630;
    --bark: #705540;
    --leaf: #6f9e83;
    --leaf-deep: #3f6a55;
    --grass: #4a6a52;
    --bloom-clay: #c98f68;
    --bloom-sky: #6d9ec0;
    --bloom-gold: #c6a06a;
    --core: #cbb98a;
    --bee-body: #cf9a4a;
    --bee-stripe: #3a2c18;
    --wing: rgba(220, 230, 240, 0.5);
    --critter: #9a7550;
}
@keyframes forest-in { from { opacity: 0; } to { opacity: 1; } }

/* sky */
.forest .sky {
    height: 62%;
    inset: 0 0 auto 0;
    background: linear-gradient(to bottom,
        color-mix(in srgb, var(--sky-tint) 72%, transparent) 0%, transparent 82%);
}
.forest .sun {
    position: absolute;
    top: 7%;
    right: 13%;
    width: 130px;
    height: 130px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--sun) 0%, transparent 68%);
    opacity: 0.8;
}
.forest .cloud {
    position: absolute;
    color: var(--cloud);
    opacity: 0.75;
    animation: cloud-drift var(--dur, 60s) linear infinite;
}
.forest .cloud-svg { width: 100%; height: auto; fill: currentColor; }

/* depth bands + cursor parallax */
.forest .band {
    position: absolute;
    inset: 0;
    transform: translate(calc(var(--px, 0) * var(--par, 0px)),
        calc(var(--py, 0) * var(--par, 0px) * 0.4));
    transition: transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
    will-change: transform;
}
.forest .band.sky { --par: 2px; z-index: 0; }
.forest .band.far { --par: 4px; z-index: 1; }
.forest .band.mid { --par: 9px; z-index: 2; }
.forest .band.near { --par: 16px; z-index: 3; }

/* scenery items: sized by width (so transform stays free for sway), depth drives
   haze + fade */
.forest .tree, .forest .flower, .forest .grass {
    position: absolute;
    width: var(--w, 60px);
    transform-origin: bottom center;
    filter: blur(calc((1 - var(--depth, 1)) * 1.5px));
    opacity: calc(0.5 + var(--depth, 1) * 0.5);
    animation: sway calc(6s + var(--depth, 0.5) * 4s) ease-in-out infinite alternate;
    animation-delay: calc(var(--i, 0) * -0.9s);
}
.forest svg { display: block; width: 100%; height: auto; overflow: visible; }

@keyframes sway {
    from { transform: rotate(calc(-0.55deg - var(--depth, 0.5) * 0.8deg)); }
    to   { transform: rotate(calc(0.55deg + var(--depth, 0.5) * 0.8deg)); }
}
@keyframes cloud-drift {
    from { transform: translateX(-14vw); }
    to   { transform: translateX(114vw); }
}

/* trees */
.forest .trunk { fill: var(--bark); }
.forest .canopy { fill: var(--leaf); }
.forest .canopy.conifer { fill: var(--leaf-deep); }
.forest .branch {
    fill: none;
    stroke: var(--bark);
    stroke-width: 4;
    stroke-linecap: round;
    stroke-linejoin: round;
}

/* flowers + sprouts */
.forest .fl-stem, .forest .sp-stem {
    fill: none;
    stroke: var(--leaf-deep);
    stroke-width: 2.4;
    stroke-linecap: round;
}
.forest .fl-leaf, .forest .sp-leaf { fill: var(--leaf); }
.forest .fl-core { fill: var(--core); }
.forest .fl-petals { fill: var(--bloom-clay); }
.forest .f1 .fl-petals { fill: var(--bloom-sky); }
.forest .f2 .fl-petals { fill: var(--bloom-gold); }

/* grass */
.forest .grass-svg {
    fill: none;
    stroke: var(--leaf);
    stroke-width: 2.4;
    stroke-linecap: round;
}

/* ground mound */
.forest .ground {
    position: absolute;
    left: -6%;
    right: -6%;
    bottom: -2%;
    height: 24%;
    z-index: 2;
    opacity: 0.92;
    border-radius: 50% 50% 0 0 / 26% 26% 0 0;
    background: radial-gradient(130% 120% at 50% 100%,
        var(--grass) 0%, var(--grass) 62%, transparent 100%);
}

/* animals */
.forest .bee, .forest .butterfly, .forest .critter {
    position: absolute;
    width: var(--w, 26px);
    opacity: calc(0.55 + var(--depth, 0.7) * 0.45);
    filter: blur(calc((1 - var(--depth, 1)) * 0.8px));
}
.forest .bee { animation: bee-fly var(--dur, 11s) ease-in-out infinite; }
.forest .butterfly { animation: flit var(--dur, 14s) ease-in-out infinite; }
.forest .critter { transform-origin: bottom center; }
.forest .squirrel { animation: hop 5s ease-in-out infinite; }
.forest .deer { animation: idle-bob 6s ease-in-out infinite; }

.forest .bee-body { fill: var(--bee-body); }
.forest .bee-stripe { fill: var(--bee-stripe); }
.forest .bee-wing { fill: var(--wing); }
.forest .bee-wings { transform-origin: 15px 6px; animation: buzz 0.18s ease-in-out infinite; }
.forest .bfly-wing { fill: var(--bloom-clay); }
.forest .butterfly.b1 .bfly-wing { fill: var(--bloom-sky); }
.forest .bfly-body { fill: var(--bark); }
.forest .bfly-wings { transform-origin: 14px 12px; animation: flap 0.34s ease-in-out infinite; }
.forest .cr-fill { fill: var(--critter); }
.forest .cr-eye { fill: #2c2c24; }
.forest .cr-antler {
    fill: none;
    stroke: var(--bark);
    stroke-width: 2;
    stroke-linecap: round;
}

@keyframes buzz { 0%, 100% { transform: scaleY(1); } 50% { transform: scaleY(0.5); } }
@keyframes flap { 0%, 100% { transform: scaleX(1); } 50% { transform: scaleX(0.32); } }
@keyframes idle-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
@keyframes hop { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
@keyframes bee-fly {
    0%   { transform: translate(0, 0) rotate(-4deg); }
    25%  { transform: translate(42px, -26px) rotate(6deg); }
    50%  { transform: translate(14px, -48px) rotate(-3deg); }
    75%  { transform: translate(-32px, -18px) rotate(5deg); }
    100% { transform: translate(0, 0) rotate(-4deg); }
}
@keyframes flit {
    0%   { transform: translate(0, 0) rotate(-6deg); }
    33%  { transform: translate(-36px, -42px) rotate(8deg); }
    66%  { transform: translate(32px, -66px) rotate(-8deg); }
    100% { transform: translate(0, 0) rotate(-6deg); }
}

/* keep the centred content readable on smaller windows */
@media (max-width: 900px) {
    .forest .band.mid, .forest .band.near { opacity: 0.72; }
}
@media (max-width: 680px) {
    .forest .tree, .forest .flower, .forest .grass,
    .forest .bee, .forest .butterfly, .forest .critter { display: none; }
    .forest .sky { height: 38%; }
    .forest .ground { height: 15%; }
}

@media (prefers-reduced-motion: reduce) {
    .forest, .forest .cloud, .forest .tree, .forest .flower, .forest .grass,
    .forest .bee, .forest .butterfly, .forest .critter,
    .forest .bee-wings, .forest .bfly-wings {
        animation: none !important;
    }
    .forest .band { transition: none !important; transform: none !important; }
}
"""


class HomeBottomBar:
    def __init__(self, home: Home) -> None:
        self.home = home


class Home:
    def __init__(self, mw: AnkiQt) -> None:
        self.mw = mw
        self.web = mw.web
        self.bottom = BottomBar(mw, mw.bottomWeb)

    def show(self) -> None:
        av_player.stop_and_clear_queue()
        self.web.set_bridge_command(self._link_handler, self)
        self.mw.toolbar.redraw()
        self.refresh()

    def refresh(self) -> None:
        def get_data(col: Collection) -> HomeData:
            score = low = high = 0.0
            abstain = True
            try:
                o = col._backend.readiness_query(
                    search="", min_reviews=0, min_questions=0
                ).overall
                score, low, high, abstain = (
                    o.readiness_score,
                    o.range_low,
                    o.range_high,
                    o.abstain,
                )
            except Exception:
                # Never let a scoring hiccup keep the student off the home screen.
                pass
            try:
                suggestion = build_home_suggestion(col)
            except Exception:
                suggestion = None
            return HomeData(score, low, high, abstain, suggestion)

        QueryOp(
            parent=self.mw,
            op=get_data,
            success=self._render,
        ).run_in_background()

    # Rendering
    ##########################################################################

    def _render(self, data: HomeData) -> None:
        self.web.stdHtml(self._html(data), context=self)
        # Home carries no bottom actions; clear any leftover from a prior state.
        self.bottom.draw(
            buf="", link_handler=self._link_handler, web_context=HomeBottomBar(self)
        )

    def _html(self, data: HomeData) -> str:
        if data.abstain:
            value = "—"
            sub = "Take a full-length practice exam to unlock your readiness score."
            value_class = "score-value score-value--none"
        else:
            value = f"{round(data.score * 100)}%"
            value_class = "score-value"
            if data.high > data.low:
                sub = (
                    f"Likely {round(data.low * 100)}–{round(data.high * 100)}% — "
                    "you’re growing."
                )
            else:
                sub = "Keep watering — every review helps you grow."

        # Free-response AI-grading toggle (collection config; default on). When
        # off, the Rust grader falls back to a keyword match against the rubric.
        ai_on = bool(self.mw.col.get_config("mcatAiGrading", True))

        # Light/dark toggle reflects Anki's current effective theme.
        night_on = bool(theme_manager.night_mode)

        # The decorative forest grows with readiness (0 until a full-length
        # unlocks the score, matching the abstain "plant me" state).
        richness = 0.0 if data.abstain else max(0.0, min(1.0, data.score))
        forest = build_forest(richness)

        suggestion_html = self._suggestion_html(data.suggestion)

        cards = [
            self._nav_card(
                "decks",
                "Your garden",
                "Tend your decks and study what’s due",
                self._ICON_LEAF,
            ),
            self._nav_card(
                "topical",
                "Topical Practice Tests",
                "Focused sets by AAMC section",
                self._ICON_FLASK,
            ),
            self._nav_card(
                "fullLength",
                "Full-Length Practice Test",
                "A full timed MCAT simulation",
                self._ICON_CLIP,
            ),
            self._nav_card(
                "stats",
                "Statistics",
                "Readiness + your study history",
                self._ICON_CHART,
            ),
        ]

        return f"""
<style>{self._CSS}{_FOREST_CSS}</style>
<div class="home">
  {forest}
  <div class="home-inner">
    <div class="score-hero">
      <div class="score-label">Your Readiness Score</div>
      <div class="{value_class}">{value}</div>
      <p class="score-sub">{sub}</p>
    </div>
    {suggestion_html}
    <div class="nav-grid">
      {"".join(cards)}
    </div>

    <div class="home-footer">
      <button class="ai-toggle{" on" if night_on else ""}" role="switch"
              aria-checked="{"true" if night_on else "false"}"
              onclick="return pycmd('toggleTheme')"
              title="Switch between light and dark mode.">
        <span class="switch" aria-hidden="true"><span class="knob"></span></span>
        <span class="ai-label">Dark mode&nbsp;<b>{"On" if night_on else "Off"}</b></span>
      </button>
      <button class="ai-toggle{" on" if ai_on else ""}" role="switch"
              aria-checked="{"true" if ai_on else "false"}"
              onclick="return pycmd('toggleAi')"
              title="How free-response answers are graded. When off, they're graded by keyword match instead of AI.">
        <span class="switch" aria-hidden="true"><span class="knob"></span></span>
        <span class="ai-label">AI grading&nbsp;<b>{"On" if ai_on else "Off"}</b></span>
      </button>
      <button class="sync-pill" onclick="return pycmd('sync')" title="Sync your collection (Y)">
        {self._ICON_SYNC}<span>Sync</span>
      </button>
    </div>
    <p class="home-foot-note">
      {"Free-response answers are graded by AI." if ai_on else "AI grading is off — free-response answers are graded by keyword match."}
    </p>
  </div>
</div>
"""

    def _suggestion_html(self, s: Suggestion | None) -> str:
        if s is None:
            return ""
        extra = ""
        if s.secondary_cmd:
            extra = f"""
      <div class="sp-secondary">
        <p class="sp-sec-text">{s.secondary_text}</p>
        <button class="sp-sec-btn" onclick="return pycmd('{s.secondary_cmd}')">{s.secondary_label}</button>
      </div>"""
        elif s.hint:
            extra = f'\n      <p class="sp-hint">{s.hint}</p>'
        return f"""
    <div class="suggested-path">
      <div class="sp-eyebrow">Suggested next step</div>
      <h2 class="sp-heading">{s.heading}</h2>
      <p class="sp-body">{s.body}</p>
      <button class="sp-cta" onclick="return pycmd('{s.cta_cmd}')">{s.cta_label}</button>{extra}
    </div>"""

    def _nav_card(self, cmd: str, title: str, desc: str, icon: str) -> str:
        return f"""
<button class="nav-card" onclick="return pycmd('{cmd}')">
  <span class="nav-ico" aria-hidden="true">{icon}</span>
  <span class="nav-text">
    <span class="nav-title">{title}</span>
    <span class="nav-desc">{desc}</span>
  </span>
</button>"""

    # Event handling
    ##########################################################################

    def _link_handler(self, url: str) -> Any:
        if url == "decks":
            self.mw.moveToState("deckBrowser")
        elif url == "topical":
            import aqt.practice_tests

            aqt.practice_tests.show_practice_tests(self.mw)
        elif url == "fullLength":
            import aqt.practice_tests

            aqt.practice_tests.show_full_length(self.mw)
        elif url == "stats":
            import aqt.stats_combined

            aqt.stats_combined.show_combined_stats(self.mw)
        elif url == "sync":
            self.mw.on_sync_button_clicked()
        elif url == "toggleAi":
            current = bool(self.mw.col.get_config("mcatAiGrading", True))
            self.mw.col.set_config("mcatAiGrading", not current)
            self.refresh()
        elif url == "toggleTheme":
            # Flip Anki's theme (light <-> dark), then re-render so the home
            # page + forest pick up the new night-mode class.
            self.mw.set_theme(Theme.LIGHT if theme_manager.night_mode else Theme.DARK)
            self.refresh()
        return False

    # Inline icons (stroke inherits currentColor)
    ##########################################################################

    _ICON_LEAF = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M11 20A7 7 0 0 1 4 13c0-5 4-9 15-9 0 8-4 13-8 15Z"/>'
        '<path d="M7 20c1-6 4-9 9-11"/></svg>'
    )
    _ICON_FLASK = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9 3h6M10 3v6l-5 9a1.5 1.5 0 0 0 1.3 2.3h11.4A1.5 1.5 0 0 0 20 18l-5-9V3"/>'
        '<path d="M7 15h10"/></svg>'
    )
    _ICON_CLIP = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="5" y="4" width="14" height="17" rx="2.5"/>'
        '<path d="M9 4a3 3 0 0 1 6 0M9 11h6M9 15h4"/></svg>'
    )
    _ICON_CHART = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 20h16"/><path d="M7 20v-6M12 20V8M17 20v-9"/></svg>'
    )
    _ICON_SYNC = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20 11a8 8 0 0 0-14-4M4 5v3h3"/>'
        '<path d="M4 13a8 8 0 0 0 14 4M20 19v-3h-3"/></svg>'
    )

    _CSS = """
.home {
    min-height: calc(100vh - 40px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem 1.25rem 3rem;
}
.home-inner {
    width: 100%;
    max-width: 760px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2rem;
}
.score-hero { text-align: center; }
.score-label {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--fg-subtle);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.score-value {
    font-family: var(--heading-font);
    font-weight: 700;
    font-optical-sizing: auto;
    font-size: clamp(4rem, 15vw, 7.5rem);
    line-height: 1.02;
    color: var(--button-primary-bg);
    margin: 0.2rem 0 0.4rem;
}
.score-value--none {
    color: var(--fg-faint);
    font-size: clamp(3rem, 10vw, 5rem);
}
.score-sub {
    margin: 0 auto;
    max-width: 46ch;
    color: var(--fg-subtle);
    line-height: 1.5;
    font-size: 0.95rem;
}
.suggested-path {
    width: 100%;
    box-sizing: border-box;
    text-align: center;
    padding: 1.5rem 1.6rem 1.6rem;
    border: 1px solid var(--border);
    border-radius: 24px 20px 24px 20px;
    background: var(--canvas-elevated);
    box-shadow: 0 10px 30px -16px rgba(93, 112, 82, 0.4);
}
.sp-eyebrow {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--button-primary-bg);
}
.sp-heading {
    font-family: var(--heading-font);
    font-weight: 700;
    font-size: 1.5rem;
    line-height: 1.15;
    color: var(--fg);
    margin: 0.35rem 0 0.5rem;
}
.sp-body {
    margin: 0 auto;
    max-width: 52ch;
    color: var(--fg-subtle);
    line-height: 1.55;
    font-size: 0.98rem;
}
.sp-body b { color: var(--fg); font-weight: 700; }
.sp-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1.1rem;
    padding: 0.7em 1.6em;
    border: none;
    border-radius: 999px;
    background: var(--button-primary-bg);
    color: #fff;
    font: inherit;
    font-weight: 700;
    font-size: 0.95rem;
    cursor: pointer;
    box-shadow: 0 8px 20px -10px rgba(93, 112, 82, 0.7);
    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease,
        background 0.2s ease;
}
.sp-cta:hover {
    /* Set background + color explicitly: the app's global button:hover rule
       has higher specificity than a class and would otherwise wash the button
       white, hiding the white label. */
    background: color-mix(in srgb, var(--button-primary-bg), black 10%);
    color: #fff;
    transform: translateY(-2px);
    box-shadow: 0 14px 26px -12px rgba(93, 112, 82, 0.75);
}
.sp-cta:active { transform: translateY(0) scale(0.99); }
.sp-secondary {
    margin-top: 1.15rem;
    padding-top: 1rem;
    border-top: 1px dashed var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
}
.sp-sec-text {
    margin: 0;
    max-width: 52ch;
    color: var(--fg-subtle);
    font-size: 0.9rem;
    line-height: 1.5;
}
.sp-sec-text b { color: var(--fg); font-weight: 700; }
.sp-sec-btn {
    display: inline-flex;
    align-items: center;
    padding: 0.5em 1.2em;
    border-radius: 999px;
    border: 1px solid var(--border-strong);
    background: transparent;
    color: var(--button-primary-bg);
    font: inherit;
    font-weight: 700;
    font-size: 0.85rem;
    cursor: pointer;
    transition:
        background 0.2s ease,
        transform 0.2s ease;
}
.sp-sec-btn:hover {
    background: color-mix(in srgb, var(--button-primary-bg), transparent 90%);
    transform: translateY(-1px);
}
.sp-hint {
    margin: 1rem 0 0;
    font-size: 0.82rem;
    color: var(--fg-faint);
    font-style: italic;
}
.nav-grid {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.9rem;
}
@media (max-width: 620px) {
    .nav-grid { grid-template-columns: 1fr; }
}
.nav-card {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    text-align: start;
    padding: 1rem 1.1rem;
    border: 1px solid var(--border);
    border-radius: 22px 18px 20px 18px;
    background: var(--canvas-elevated);
    box-shadow: 0 4px 18px -8px rgba(93, 112, 82, 0.28);
    cursor: pointer;
    font: inherit;
    color: var(--fg);
    transition:
        transform 0.22s ease,
        box-shadow 0.22s ease,
        border-color 0.22s ease;
}
.nav-card:nth-child(even) { border-radius: 18px 22px 18px 20px; }
.nav-card:hover {
    /* pin bg: the global button:hover rule would otherwise wash it white */
    background: var(--canvas-elevated);
    transform: translateY(-3px);
    box-shadow: 0 16px 32px -12px rgba(93, 112, 82, 0.34);
    border-color: var(--border-strong);
}
.nav-card:active { transform: translateY(-1px) scale(0.99); }
.nav-ico {
    flex: 0 0 auto;
    display: grid;
    place-items: center;
    width: 2.9rem;
    height: 2.9rem;
    border-radius: 50%;
    background: color-mix(in srgb, var(--button-primary-bg), transparent 88%);
    color: var(--button-primary-bg);
}
.nav-ico svg { width: 1.5rem; height: 1.5rem; }
.nav-title { display: block; font-weight: 700; font-size: 1.02rem; }
.nav-desc { display: block; color: var(--fg-subtle); font-size: 0.82rem; margin-top: 0.1rem; }
.sync-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6em 1.4em;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--canvas-elevated);
    color: var(--fg);
    font: inherit;
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}
.sync-pill svg { width: 1.05rem; height: 1.05rem; }
.sync-pill:hover {
    background: var(--canvas-inset);
    border-color: var(--border-strong);
    transform: translateY(-1px);
}
.home-footer {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    flex-wrap: wrap;
    justify-content: center;
}
.ai-toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.5em 1em 0.5em 0.7em;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--canvas-elevated);
    color: var(--fg);
    font: inherit;
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}
.ai-toggle:hover { background: var(--canvas-elevated); border-color: var(--border-strong); transform: translateY(-1px); }
.ai-toggle .switch {
    position: relative;
    width: 2.1rem;
    height: 1.2rem;
    flex: 0 0 auto;
    border-radius: 999px;
    background: var(--border-strong);
    transition: background 0.2s ease;
}
.ai-toggle .knob {
    position: absolute;
    top: 0.15rem;
    left: 0.15rem;
    width: 0.9rem;
    height: 0.9rem;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
    transition: left 0.2s ease;
}
.ai-toggle.on .switch { background: var(--button-primary-bg); }
.ai-toggle.on .knob { left: 1.05rem; }
.ai-label b { color: var(--fg-subtle); font-weight: 800; }
.ai-toggle.on .ai-label b { color: var(--button-primary-bg); }
.home-foot-note {
    margin: 0.1rem 0 0;
    font-size: 0.78rem;
    color: var(--fg-faint);
    text-align: center;
}
@media (prefers-reduced-motion: reduce) {
    .nav-card, .sync-pill, .ai-toggle .switch, .ai-toggle .knob,
    .sp-cta, .sp-sec-btn { transition: none; }
}
"""
