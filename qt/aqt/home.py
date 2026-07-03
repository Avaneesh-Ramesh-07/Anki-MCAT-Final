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

from typing import Any

from anki.collection import Collection
from aqt import AnkiQt
from aqt.operations import QueryOp
from aqt.sound import av_player
from aqt.toolbar import BottomBar


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
        def get_data(col: Collection) -> tuple[float, float, float, bool]:
            try:
                resp = col._backend.readiness_query(
                    search="", min_reviews=0, min_questions=0
                )
                o = resp.overall
                return (o.readiness_score, o.range_low, o.range_high, o.abstain)
            except Exception:
                # Never let a scoring hiccup keep the student off the home screen.
                return (0.0, 0.0, 0.0, True)

        QueryOp(
            parent=self.mw,
            op=get_data,
            success=lambda d: self._render(*d),
        ).run_in_background()

    # Rendering
    ##########################################################################

    def _render(
        self, score: float, low: float, high: float, abstain: bool
    ) -> None:
        self.web.stdHtml(self._html(score, low, high, abstain), context=self)
        # Home carries no bottom actions; clear any leftover from a prior state.
        self.bottom.draw(
            buf="", link_handler=self._link_handler, web_context=HomeBottomBar(self)
        )

    def _html(self, score: float, low: float, high: float, abstain: bool) -> str:
        if abstain:
            value = "—"
            sub = "Take a full-length practice exam to unlock your readiness score."
            value_class = "score-value score-value--none"
        else:
            value = f"{round(score * 100)}%"
            value_class = "score-value"
            if high > low:
                sub = f"Likely {round(low * 100)}–{round(high * 100)}% — you’re growing."
            else:
                sub = "Keep watering — every review helps you grow."

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
    <p class="home-greet">Welcome back to your MCAT prep</p>
    <div class="score-hero">
      <div class="score-label">Your Readiness Score</div>
      <div class="{value_class}">{value}</div>
      <p class="score-sub">{sub}</p>
    </div>

    <div class="nav-grid">
      {"".join(cards)}
    </div>

    <button class="sync-pill" onclick="return pycmd('sync')" title="Sync your collection (Y)">
      {self._ICON_SYNC}<span>Sync</span>
    </button>
  </div>
</div>
"""

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
.home-greet {
    margin: 0;
    color: var(--fg-subtle);
    font-size: 1rem;
    letter-spacing: 0.02em;
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
@media (prefers-reduced-motion: reduce) {
    .nav-card, .sync-pill { transition: none; }
}
"""
