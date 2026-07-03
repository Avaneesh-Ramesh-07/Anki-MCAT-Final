# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import html
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from anki.collection import Collection, OpChanges
from anki.decks import DeckCollapseScope, DeckId, DeckTreeNode
from anki.utils import int_time
from aqt import AnkiQt, gui_hooks
from aqt.deckoptions import display_options_for_deck_id
from aqt.operations import QueryOp
from aqt.operations.deck import (
    add_deck_dialog,
    remove_decks,
    rename_deck,
    reparent_decks,
    set_current_deck,
    set_deck_collapsed,
)
from aqt.qt import *
from aqt.sound import av_player
from aqt.toolbar import BottomBar
from aqt.utils import getOnlyText, openLink, shortcut, showInfo, tr


class DeckBrowserBottomBar:
    def __init__(self, deck_browser: DeckBrowser) -> None:
        self.deck_browser = deck_browser


@dataclass
class GardenBed:
    """Per-deck garden facts, computed off the UI thread in _compute_garden."""

    total: int  # cards in the deck
    mastered: int  # cards at FSRS retrievability >= 0.9 (the dashboard rule)
    next_due_secs: int | None  # until the soonest future review (None if none)
    new_remaining: int  # un-introduced new cards left (gated by the daily limit)
    new_per_day: int  # the deck's daily new-card limit


@dataclass
class RenderData:
    """Data from collection that is required to show the page."""

    tree: DeckTreeNode
    current_deck_id: DeckId
    studied_today: str
    sched_upgrade_required: bool
    # Per top-level deck garden facts (mastery + scheduling), computed off-thread.
    garden: dict[int, GardenBed]


@dataclass
class DeckBrowserContent:
    """Stores sections of HTML content that the deck browser will be
    populated with.

    Attributes:
        tree {str} -- HTML of the deck tree section
        stats {str} -- HTML of the stats section
    """

    tree: str
    stats: str


@dataclass
class RenderDeckNodeContext:
    current_deck_id: DeckId


class DeckBrowser:
    _render_data: RenderData

    def __init__(self, mw: AnkiQt) -> None:
        self.mw = mw
        self.web = mw.web
        self.bottom = BottomBar(mw, mw.bottomWeb)
        self.scrollPos = QPoint(0, 0)
        self._refresh_needed = False

    def show(self) -> None:
        av_player.stop_and_clear_queue()
        self.web.set_bridge_command(self._linkHandler, self)
        # redraw top bar for theme change
        self.mw.toolbar.redraw()
        self.refresh()

    def refresh(self) -> None:
        self._renderPage()
        self._refresh_needed = False

    def refresh_if_needed(self) -> None:
        if self._refresh_needed:
            self.refresh()

    def op_executed(
        self, changes: OpChanges, handler: object | None, focused: bool
    ) -> bool:
        if changes.study_queues and handler is not self:
            self._refresh_needed = True

        if focused:
            self.refresh_if_needed()

        return self._refresh_needed

    # Event handlers
    ##########################################################################

    def _linkHandler(self, url: str) -> Any:
        if ":" in url:
            (cmd, arg) = url.split(":", 1)
        else:
            cmd = url
            arg = ""
        if cmd == "open":
            self.set_current_deck(DeckId(int(arg)))
        elif cmd == "continue":
            self._study_deck(DeckId(int(arg)))
        elif cmd == "review":
            self._study_deck(DeckId(int(arg)))
        elif cmd == "opts":
            self._showOptions(arg)
        elif cmd == "import":
            self.mw.onImport()
        elif cmd == "create":
            self._on_create()
        elif cmd == "drag":
            source, target = arg.split(",")
            self._handle_drag_and_drop(DeckId(int(source)), DeckId(int(target or 0)))
        elif cmd == "collapse":
            self._collapse(DeckId(int(arg)))
        elif cmd == "v2upgrade":
            self._confirm_upgrade()
        elif cmd == "v2upgradeinfo":
            if self.mw.col.sched_ver() == 1:
                openLink("https://faqs.ankiweb.net/the-anki-2.1-scheduler.html")
            else:
                openLink("https://faqs.ankiweb.net/the-2021-scheduler.html")
        elif cmd == "select":
            set_current_deck(
                parent=self.mw, deck_id=DeckId(int(arg))
            ).run_in_background()
        elif cmd == "tended":
            self._show_tended_info(DeckId(int(arg)))
        return False

    def _show_tended_info(self, did: DeckId) -> None:
        """Explain why a fully-tended bed can't be studied further right now: the
        daily new-card limit is a hard cap, so more cards unlock tomorrow."""
        bed = self._garden_bed_data(did)
        name = html.escape(self.mw.col.decks.name(did))
        parts = [f"<b>{name}</b> is tended for today. 🌱", ""]
        if bed and bed.new_remaining > 0:
            cap = (
                f" (currently {bed.new_per_day} per day for this deck)"
                if bed.new_per_day
                else ""
            )
            parts.append(
                "Anki only lets you start a fixed number of <b>new</b> cards each "
                f"day{cap} — a hard limit that keeps your future reviews from "
                "piling up. You've hit today's limit here, with "
                f"<b>{bed.new_remaining}</b> topics still waiting to be planted."
            )
            parts.append("")
            parts.append(
                "Come back <b>tomorrow</b> to plant the next batch — or raise the "
                "daily new-card limit in this deck's Options if you want more now."
            )
        else:
            parts.append(
                "You've already started every card in this deck — from here it's "
                "all about watering (reviewing) what you've grown."
            )
        when = self._humanize_secs(bed.next_due_secs) if bed else None
        if when:
            parts += ["", f"Your next review here is due in <b>{when}</b>."]
        showInfo("<br>".join(parts), parent=self.mw, textFormat="rich")

    def set_current_deck(self, deck_id: DeckId) -> None:
        set_current_deck(parent=self.mw, deck_id=deck_id).success(
            lambda _: self.mw.onOverview()
        ).run_in_background(initiator=self)

    def _study_deck(self, deck_id: DeckId) -> None:
        """Select the deck and begin studying it immediately (skip overview)."""

        def begin(_: OpChanges) -> None:
            self.mw.col.startTimebox()
            self.mw.moveToState("review")

        set_current_deck(parent=self.mw, deck_id=deck_id).success(
            begin
        ).run_in_background(initiator=self)

    # HTML generation
    ##########################################################################

    _body = """
<div class="garden-page">
%(tree)s
%(stats)s
</div>
"""

    def _renderPage(self, reuse: bool = False) -> None:
        if not reuse:

            def get_data(col: Collection) -> RenderData:
                tree = col.sched.deck_due_tree()
                return RenderData(
                    tree=tree,
                    current_deck_id=col.decks.get_current_id(),
                    studied_today=col.studied_today(),
                    sched_upgrade_required=not col.v3_scheduler(),
                    garden=self._compute_garden(col, tree),
                )

            def success(output: RenderData) -> None:
                self._render_data = output
                self.__renderPage(None)

            QueryOp(
                parent=self.mw,
                op=get_data,
                success=success,
            ).run_in_background()
        else:
            self.web.evalWithCallback("window.pageYOffset", self.__renderPage)

    def __renderPage(self, offset: int | None) -> None:
        data = self._render_data
        content = DeckBrowserContent(
            tree=self._renderDeckTree(data.tree),
            stats=self._renderStats(),
        )
        gui_hooks.deck_browser_will_render_content(self, content)
        self.web.stdHtml(
            self._v1_upgrade_message(data.sched_upgrade_required)
            + self._body % content.__dict__,
            css=["css/deckbrowser.css"],
            js=[
                "js/vendor/jquery.min.js",
                "js/vendor/jquery-ui.min.js",
                "js/deckbrowser.js",
            ],
            context=self,
        )
        self._drawButtons()
        if offset is not None:
            self._scrollToOffset(offset)
        gui_hooks.deck_browser_did_render(self)

    def _scrollToOffset(self, offset: int) -> None:
        self.web.eval("window.scrollTo(0, %d, 'instant');" % offset)

    def _renderStats(self) -> str:
        return '<div id="studiedToday"><span>{}</span></div>'.format(
            self._render_data.studied_today
        )

    # A blooming flower (mastered card): moss stem + leaves, coloured petals.
    _FLOWER_SVG = (
        '<svg viewBox="0 0 40 50" aria-hidden="true">'
        '<path class="stem" d="M20 49V26" />'
        '<path class="leaf" d="M20 37c-5 .2-9.6-2.6-11-7.7 6.1-1.2 10.2 1.9 11 7.1z" />'
        '<path class="leaf" d="M20 32c4.7-.2 8.9-2.9 10-7.8-5.7-1-9.5 1.9-10 6.9z" />'
        '<g class="petals">'
        '<circle cx="20" cy="15" r="5.4"/><circle cx="13.4" cy="19" r="5.4"/>'
        '<circle cx="26.6" cy="19" r="5.4"/><circle cx="16" cy="9.8" r="5.4"/>'
        '<circle cx="24" cy="9.8" r="5.4"/></g>'
        '<circle class="core" cx="20" cy="15" r="3.3"/>'
        "</svg>"
    )
    # A weed (unmastered/unstudied): tangled, thorny, dried — clearly not a bloom.
    _WEED_SVG = (
        '<svg viewBox="0 0 40 50" aria-hidden="true">'
        '<g class="weed-stalk">'
        '<path d="M20 49C19 39 14.6 34.6 10 30.8" />'
        '<path d="M20 49C21.6 38.6 25.8 34.6 30 30" />'
        '<path d="M20 49V30" />'
        '<path d="M13.6 34.6 9 31.2M15.6 30.4 10 29M25 31.4l5.2-2.2M23.4 35.4l5.6 1'
        "M20 33l-3.6-5.6M20 33l3.6-5.6M20 28v-6\" />"
        "</g></svg>"
    )
    # Watering-can droplet, for the "needs watering" badge and the Water button.
    _DROP_SVG = (
        '<svg viewBox="0 0 16 20" aria-hidden="true" class="drop">'
        '<path d="M8 1S2 9 2 13a6 6 0 0 0 12 0C14 9 8 1 8 1z" /></svg>'
    )

    def _renderDeckTree(self, top: DeckTreeNode) -> str:
        ctx = RenderDeckNodeContext(current_deck_id=self._render_data.current_deck_id)
        beds = "".join(self._garden_bed(child, ctx) for child in top.children)
        if not beds:
            beds = (
                '<div class="garden-empty"><p>Your garden is empty — '
                "create a deck to plant your first bed.</p></div>"
            )
        intro = (
            '<div class="garden-head"><h1>Your study garden</h1>'
            '<p class="garden-intro">Each deck is a flowerbed. Reviewing cards when '
            "they’re due <b>waters your plants</b>; mastered cards bloom, while "
            "untended ones grow over with <b>weeds</b>.</p></div>"
        )
        return f'<div class="garden">{intro}<div class="beds">{beds}</div></div>'

    def _compute_garden(
        self, col: Collection, tree: DeckTreeNode
    ) -> dict[int, GardenBed]:
        """Per top-level bed, the facts the garden needs, computed off the UI
        thread. "Mastered" uses the SAME rule as the readiness dashboard — a
        card is mastered when its current FSRS retrievability is >= 0.9
        (MasteryQuery), whose `overall` rollup pools every card the deck search
        matches. We also gather the soonest future review and how many new cards
        remain behind the daily limit, for the "tended" messaging."""
        garden: dict[int, GardenBed] = {}
        today = col.sched.today
        now = int_time()
        db = col.db
        for node in tree.children:
            did = int(node.deck_id)
            name = (
                col.decks.name(DeckId(did)).replace("\\", "\\\\").replace('"', '\\"')
            )
            total = mastered = 0
            try:
                overall = col._backend.mastery_query(
                    search=f'deck:"{name}"', min_reviews=0
                ).overall
                total, mastered = int(overall.total_cards), int(overall.mastered_count)
            except Exception:
                pass
            # Soonest future card: reviews/day-learning (queue 2/3, due=day number)
            # and intraday learning (queue 1, due=unix ts).
            next_secs: int | None = None
            new_remaining = 0
            if db is not None:
                cands: list[int] = []
                day = db.scalar(
                    "select min(due) from cards where did=? and queue in (2,3) and due>?",
                    did,
                    today,
                )
                if day is not None:
                    cands.append((int(day) - today) * 86400)
                ts = db.scalar(
                    "select min(due) from cards where did=? and queue=1 and due>?",
                    did,
                    now,
                )
                if ts is not None:
                    cands.append(int(ts) - now)
                positive = [s for s in cands if s > 0]
                if positive:
                    next_secs = min(positive)
                new_remaining = int(
                    db.scalar("select count(*) from cards where did=? and queue=0", did)
                    or 0
                )
            try:
                new_per_day = int(
                    col.decks.config_dict_for_deck_id(DeckId(did))["new"]["perDay"]
                )
            except Exception:
                new_per_day = 0
            garden[did] = GardenBed(
                total, mastered, next_secs, new_remaining, new_per_day
            )
        return garden

    def _garden_bed_data(self, did: DeckId) -> GardenBed | None:
        return getattr(self._render_data, "garden", {}).get(int(did))

    def _garden_counts(self, did: DeckId) -> tuple[int, int]:
        """(total cards, mastered cards) for a deck, read from the off-thread
        cache. "Mastered" is FSRS retrievability >= 0.9 — the same definition the
        readiness dashboard uses — so a card blooms as soon as you review it well
        and reverts toward a weed as its recall fades."""
        bed = self._garden_bed_data(did)
        return (bed.total, bed.mastered) if bed else (0, 0)

    def _humanize_secs(self, secs: int | None) -> str | None:
        """A friendly 'in N days' (or a smaller unit when it's under a day)."""
        if not secs or secs <= 0:
            return None
        days = round(secs / 86400)
        if days < 1:
            return self.mw.col.format_timespan(secs)
        return f"{days} day" if days == 1 else f"{days} days"

    def _garden_scene(self, mastered: int, total: int) -> str:
        """A bed of up to CAP glyphs: flowers (mastered) mixed among weeds
        (everything not yet mastered), so the balance reads at a glance."""
        cap = 12
        if total <= 0:
            return ""
        flowers = max(0, min(cap, round(cap * mastered / total)))
        if mastered > 0 and flowers == 0:
            flowers = 1
        # Spread the flowers evenly through the weeds for a natural mixed bed.
        cells: list[str] = []
        acc = 0
        fi = 0
        for i in range(cap):
            prev, acc = acc, ((i + 1) * flowers) // cap
            if acc > prev:
                cells.append(
                    f'<span class="g-cell g-flower f{fi % 3}" style="--n:{i}">'
                    f"{self._FLOWER_SVG}</span>"
                )
                fi += 1
            else:
                cells.append(
                    f'<span class="g-cell g-weed" style="--n:{i}">{self._WEED_SVG}</span>'
                )
        return (
            '<div class="scene"><div class="growth">'
            + "".join(cells)
            + '</div><div class="soil"></div></div>'
        )

    def _watering_badge(self, due: int) -> str:
        if due <= 0:
            return ""
        return (
            f'<span class="water-badge">{self._DROP_SVG}'
            f"Needs watering · {due}</span>"
        )

    def _bed_actions(self, node: DeckTreeNode) -> str:
        did = node.deck_id
        due = node.review_count + node.learn_count
        if due:
            primary = (
                "<button class='bed-btn bed-btn-water' "
                "onclick=\"event.stopPropagation(); return pycmd('review:%d')\">"
                "%s Water</button>" % (did, self._DROP_SVG)
            )
        elif node.new_count:
            primary = (
                "<button class='bed-btn bed-btn-plant' "
                "onclick=\"event.stopPropagation(); return pycmd('continue:%d')\">"
                "Plant seeds</button>" % did
            )
        else:
            bed = self._garden_bed_data(DeckId(did))
            when = self._humanize_secs(bed.next_due_secs) if bed else None
            label = (
                f"Tended for today. Water it again in {when}!"
                if when
                else "Tended for today ✓"
            )
            primary = (
                "<button class='bed-btn bed-btn-tended' "
                "onclick=\"event.stopPropagation(); return pycmd('tended:%d')\">"
                "%s</button>" % (did, label)
            )
        gear = (
            "<button class='bed-gear' title='Deck options' "
            "onclick=\"event.stopPropagation(); return pycmd('opts:%d')\">"
            "<img src='/_anki/imgs/gears.svg' class=gears></button>" % did
        )
        return f'<div class="bed-actions">{primary}{gear}</div>'

    def _garden_bed(self, node: DeckTreeNode, ctx: RenderDeckNodeContext) -> str:
        did = node.deck_id
        total, mastered = self._garden_counts(DeckId(did))
        # Skip empty beds (e.g. an empty Default deck).
        if total <= 0:
            return ""
        due = node.review_count + node.learn_count
        current = " current" if did == ctx.current_deck_id else ""
        thirsty = " thirsty" if due else ""
        name = html.escape(node.name)
        aria = "%s: %d of %d cards mastered%s" % (
            name,
            mastered,
            total,
            ", cards due now" if due else "",
        )
        # Unambiguous progress, matching the readiness dashboard's wording. (An
        # earlier "{weeds} to tend" count read like a backlog of locked cards.)
        stats = (
            f'<span class="stat stat-plants">{mastered}</span>'
            f'<span class="stat-of">of {total} mastered</span>'
        )
        return f"""
<div class="bed{current}{thirsty}" role="button" tabindex="0"
     aria-label="{aria}"
     onclick="pycmd('open:{did}')"
     onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();pycmd('open:{did}')}}">
  <div class="bed-top">
    <h2 class="bed-name">{name}</h2>
    {self._watering_badge(due)}
  </div>
  {self._garden_scene(mastered, total)}
  <div class="bed-foot">
    <div class="bed-stats">{stats}</div>
    {self._bed_actions(node)}
  </div>
</div>"""

    # Options
    ##########################################################################

    def _showOptions(self, did: str) -> None:
        m = QMenu(self.mw)
        a = m.addAction(tr.actions_rename())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._rename(DeckId(int(did))))
        a = m.addAction(tr.actions_options())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._options(DeckId(int(did))))
        a = m.addAction(tr.actions_export())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._export(DeckId(int(did))))
        a = m.addAction(tr.actions_delete())
        assert a is not None
        qconnect(a.triggered, lambda b, did=did: self._delete(DeckId(int(did))))
        gui_hooks.deck_browser_will_show_options_menu(m, int(did))
        m.popup(QCursor.pos())

    def _export(self, did: DeckId) -> None:
        self.mw.onExport(did=did)

    def _rename(self, did: DeckId) -> None:
        def prompt(name: str) -> None:
            new_name = getOnlyText(
                tr.decks_new_deck_name(), default=name, title=tr.actions_rename()
            )
            if not new_name or new_name == name:
                return
            else:
                rename_deck(
                    parent=self.mw, deck_id=did, new_name=new_name
                ).run_in_background()

        QueryOp(
            parent=self.mw, op=lambda col: col.decks.name(did), success=prompt
        ).run_in_background()

    def _options(self, did: DeckId) -> None:
        display_options_for_deck_id(did)

    def _collapse(self, did: DeckId) -> None:
        node = self.mw.col.decks.find_deck_in_tree(self._render_data.tree, did)
        if node:
            node.collapsed = not node.collapsed
            set_deck_collapsed(
                parent=self.mw,
                deck_id=did,
                collapsed=node.collapsed,
                scope=DeckCollapseScope.REVIEWER,
            ).run_in_background()
            self._renderPage(reuse=True)

    def _handle_drag_and_drop(self, source: DeckId, target: DeckId) -> None:
        reparent_decks(
            parent=self.mw, deck_ids=[source], new_parent=target
        ).run_in_background()

    def _delete(self, did: DeckId) -> None:
        deck = self.mw.col.decks.find_deck_in_tree(self._render_data.tree, did)
        assert deck is not None
        deck_name = deck.name
        remove_decks(
            parent=self.mw, deck_ids=[did], deck_name=deck_name
        ).run_in_background()

    # Top buttons
    ######################################################################

    drawLinks = [
        ["", "create", tr.decks_create_deck()],
        ["Ctrl+Shift+I", "import", tr.decks_import_file()],
    ]

    def _drawButtons(self) -> None:
        buf = ""
        drawLinks = deepcopy(self.drawLinks)
        for b in drawLinks:
            if b[0]:
                b[0] = tr.actions_shortcut_key(val=shortcut(b[0]))
            buf += """
<button title='%s' onclick='pycmd(\"%s\");'>%s</button>""" % tuple(b)
        self.bottom.draw(
            buf=buf,
            link_handler=self._linkHandler,
            web_context=DeckBrowserBottomBar(self),
        )

    def _on_create(self) -> None:
        if op := add_deck_dialog(
            parent=self.mw, default_text=self.mw.col.decks.current()["name"]
        ):
            op.run_in_background()

    ######################################################################

    def _v1_upgrade_message(self, required: bool) -> str:
        if not required:
            return ""

        update_required = tr.scheduling_update_required().replace("V2", "v3")

        return f"""
<center>
<div class=callout>
    <div>
      {update_required}
    </div>
    <div>
      <button onclick='pycmd("v2upgrade")'>
        {tr.scheduling_update_button()}
      </button>
      <button onclick='pycmd("v2upgradeinfo")'>
        {tr.scheduling_update_more_info_button()}
      </button>
    </div>
</div>
</center>
"""

    def _confirm_upgrade(self) -> None:
        if self.mw.col.sched_ver() == 1:
            self.mw.col.mod_schema(check=True)
            self.mw.col.upgrade_to_v2_scheduler()
        self.mw.col.set_v3_scheduler(True)

        showInfo(tr.scheduling_update_done())
        self.refresh()
