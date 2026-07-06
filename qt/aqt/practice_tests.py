# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""MCAT practice tests window.

Hosts the `practice-tests` SvelteKit page in a webview. The same page serves
both entry points: the default view lists the topical tests, and loading it
with ``?mode=full-length`` scopes it to the full-length exam. The test content
is statically bundled into the SvelteKit route, so this dialog only needs to
load the page and manage its window geometry.
"""

from __future__ import annotations

from typing import Any

import aqt
import aqt.main
from aqt.qt import *
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind


class PracticeTestsDialog(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt, full_length: bool = False) -> None:
        QDialog.__init__(self, mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.full_length = full_length
        # Distinct geometry key so the two windows remember their own size.
        self.name = "mcatFullLength" if full_length else "mcatPracticeTests"
        self.setWindowTitle(
            "Full-Length Practice Test" if full_length else "Topical Practice Tests"
        )
        disable_help_button(self)

        self.web = AnkiWebView(parent=self, kind=AnkiWebViewKind.PRACTICE_TESTS)
        self.web.setMinimumSize(760, 560)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        restoreGeom(self, self.name, default_size=(920, 820))
        # Pass the Home-page AI-grading toggle through so each free-response card
        # can flag whether it will be graded by AI or by keyword match. (The Rust
        # grader decides the real mode from the same config; this is display-only.)
        ai = "1" if mw.col.get_config("mcatAiGrading", True) else "0"
        base = "practice-tests?mode=full-length" if full_length else "practice-tests"
        sep = "&" if "?" in base else "?"
        # The page's top-left "Home" button (shown only on the test list) calls
        # bridgeCommand("home"); close this window and land on the Home screen.
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self.web.load_sveltekit_page(f"{base}{sep}ai={ai}")
        self.show()
        self.activateWindow()

    def _on_bridge_cmd(self, cmd: str) -> Any:
        if cmd == "home":
            # Defer so we don't tear down the webview from inside its own callback.
            QTimer.singleShot(0, self._go_home)
        return False

    def _go_home(self) -> None:
        self.mw.moveToState("home")
        self.reject()

    def reject(self) -> None:
        self.web.cleanup()
        self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def show_practice_tests(mw: aqt.main.AnkiQt) -> PracticeTestsDialog:
    return PracticeTestsDialog(mw)


def show_full_length(mw: aqt.main.AnkiQt) -> PracticeTestsDialog:
    return PracticeTestsDialog(mw, full_length=True)
