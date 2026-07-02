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
        page = "practice-tests?mode=full-length" if full_length else "practice-tests"
        self.web.load_sveltekit_page(page)
        self.show()
        self.activateWindow()

    def reject(self) -> None:
        self.web.cleanup()
        self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def show_practice_tests(mw: aqt.main.AnkiQt) -> PracticeTestsDialog:
    return PracticeTestsDialog(mw)


def show_full_length(mw: aqt.main.AnkiQt) -> PracticeTestsDialog:
    return PracticeTestsDialog(mw, full_length=True)
