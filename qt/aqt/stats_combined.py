# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Combined statistics window.

Hosts the `stats` SvelteKit page in an API-enabled webview. That page has two
accordion sections: the MCAT readiness dashboard on top and Anki's normal
graphs below, so it needs to call both the MCAT model RPCs (mastery /
performance / readiness) and the graphs RPC.
"""

from __future__ import annotations

from typing import Any

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
        # The stats page's top-left "Home" button calls bridgeCommand("home");
        # close this window and land on the Home screen.
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        self.web.load_sveltekit_page("stats")
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


def show_combined_stats(mw: aqt.main.AnkiQt) -> CombinedStatsDialog:
    return CombinedStatsDialog(mw)
