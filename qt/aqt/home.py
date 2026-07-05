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

from dataclasses import dataclass
from typing import Any

from anki.collection import Collection
from aqt import AnkiQt
from aqt.deckbrowser import MCAT_NEW_PER_DAY_CAP
from aqt.operations import QueryOp
from aqt.sound import av_player
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
<style>{self._CSS}</style>
<div class="home">
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
        filter 0.2s ease;
}
.sp-cta:hover {
    transform: translateY(-2px);
    filter: brightness(1.05);
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
.ai-toggle:hover { border-color: var(--border-strong); transform: translateY(-1px); }
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
