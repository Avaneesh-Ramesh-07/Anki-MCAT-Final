# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""MCAT readiness dashboard window.

Hosts the `readiness` SvelteKit page in an API-enabled webview so it can call
the MasteryQuery backend RPC (the memory model).
"""

from __future__ import annotations

import aqt
import aqt.main
from aqt.qt import *
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind


class ReadinessDialog(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        QDialog.__init__(self, mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.name = "mcatReadiness"
        self.setWindowTitle("MCAT Readiness")
        disable_help_button(self)

        self.web = AnkiWebView(parent=self, kind=AnkiWebViewKind.READINESS)
        self.web.setMinimumSize(700, 500)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        restoreGeom(self, self.name, default_size=(820, 760))
        self.web.load_sveltekit_page("readiness")
        self.show()
        self.activateWindow()

    def reject(self) -> None:
        self.web.cleanup()
        self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def show_readiness(mw: aqt.main.AnkiQt) -> ReadinessDialog:
    return ReadinessDialog(mw)
