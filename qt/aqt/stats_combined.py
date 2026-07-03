# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Combined statistics window.

Hosts the `stats` SvelteKit page in an API-enabled webview. That page has two
accordion sections: the MCAT readiness dashboard on top and Anki's normal
graphs below, so it needs to call both the MCAT model RPCs (mastery /
performance / readiness) and the graphs RPC.
"""

from __future__ import annotations

import aqt
import aqt.main
from aqt.qt import *
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind


class CombinedStatsDialog(QDialog):
    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        QDialog.__init__(self, mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.name = "mcatCombinedStats"
        self.setWindowTitle("Statistics")
        disable_help_button(self)

        self.web = AnkiWebView(parent=self, kind=AnkiWebViewKind.DECK_STATS)
        self.web.setMinimumSize(700, 500)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        restoreGeom(self, self.name, default_size=(900, 820))
        self.web.load_sveltekit_page("stats")
        self.show()
        self.activateWindow()

    def reject(self) -> None:
        self.web.cleanup()
        self.web = None  # type: ignore[assignment]
        saveGeom(self, self.name)
        QDialog.reject(self)


def show_combined_stats(mw: aqt.main.AnkiQt) -> CombinedStatsDialog:
    return CombinedStatsDialog(mw)
