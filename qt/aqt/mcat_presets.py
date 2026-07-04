# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Keep the fork's "MCAT Core" decks on their own deck-config preset (capped at
20 new cards/day) instead of the shared *Default* preset.

If the Default preset's new-cards/day is high (as some collections have it), a
topic deck otherwise introduces its whole backlog at once. Deck-config presets
identical to Default don't survive ``.apkg`` import, so this can't be shipped in
the package; instead we repair it on collection load: any ``MCAT Core`` /
``MCAT Core::*`` deck still sitting on the Default preset is moved to an
"MCAT Core" preset. The move is self-healing (covers fresh imports too) and
idempotent — decks already off Default are left alone, so a preset the user has
customised (or intentionally reassigned) is never clobbered."""

from __future__ import annotations

from anki.collection import Collection
from anki.decks import DeckConfigId

_PRESET_NAME = "MCAT Core"
_NEW_PER_DAY = 20
_DEFAULT_CONFIG_ID = 1  # the built-in "Default" preset every deck starts on


def ensure_mcat_core_preset(col: Collection) -> None:
    """Move MCAT decks off the shared Default preset onto a 20/day "MCAT Core"
    preset. Cheap no-op once done. Never raises — must not block collection load."""
    try:
        on_default = [
            deck
            for deck in col.decks.all()
            if deck.get("conf") == _DEFAULT_CONFIG_ID
            and (
                deck["name"] == _PRESET_NAME
                or deck["name"].startswith(_PRESET_NAME + "::")
            )
        ]
        if not on_default:
            return
        cfg = next(
            (c for c in col.decks.all_config() if c["name"] == _PRESET_NAME), None
        )
        if cfg is None:
            # Create it at 20/day. If it already exists, leave its value alone so
            # a user who raised/lowered it keeps their choice.
            cfg = col.decks.add_config(_PRESET_NAME)
            cfg["new"]["perDay"] = _NEW_PER_DAY
            col.decks.update_config(cfg)
        for deck in on_default:
            col.decks.set_config_id_for_deck_dict(deck, DeckConfigId(cfg["id"]))
    except Exception:
        pass
