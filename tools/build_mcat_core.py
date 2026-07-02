# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Build the original "MCAT Core" flashcard deck from resources/flashcards/*.json.

Each topic JSON ({topic, deck, aamc_tag, cards:[{front, back}]}) becomes a
subdeck under "MCAT Core" using the stock Basic note type (so cards render
cleanly, unlike custom third-party templates), with every card tagged by its
aamc:: topic so the Mastery Query picks it up. Exports tools/mcat_core.apkg.

Run from the repo root with the built env:
    out/pyenv/bin/python tools/build_mcat_core.py
"""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path[:0] = ["pylib", "out/pylib"]

import tempfile

from anki.collection import Collection, DeckIdLimit, ExportAnkiPackageOptions

FLASH_DIR = os.path.join(ROOT, "resources", "flashcards")
OUT = os.path.join(ROOT, "tools", "mcat_core.apkg")


def main() -> None:
    files = sorted(glob.glob(os.path.join(FLASH_DIR, "*.json")))
    if not files:
        print("no flashcard JSON found in", FLASH_DIR)
        return

    fd, path = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    os.unlink(path)
    col = Collection(path)
    try:
        basic = col.models.by_name("Basic")
        top_did = col.decks.id("MCAT Core")
        total = 0
        for f in files:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            deck_name = data["deck"]
            tag = data["aamc_tag"]
            cards = data["cards"]
            did = col.decks.id(deck_name)
            for c in cards:
                note = col.new_note(basic)
                note["Front"] = c["front"]
                note["Back"] = c["back"]
                note.tags = [tag]
                col.add_note(note, did)
            total += len(cards)
            print(f"  {deck_name}: {len(cards)} cards  [{tag}]")

        print(f"TOTAL: {total} cards across {len(files)} topics")
        col.export_anki_package(
            out_path=OUT,
            options=ExportAnkiPackageOptions(
                with_scheduling=False,
                with_deck_configs=True,
                with_media=False,
                legacy=False,
            ),
            limit=DeckIdLimit(deck_id=top_did),
        )
        print("WROTE", OUT, os.path.getsize(OUT), "bytes")
    finally:
        col.close()


if __name__ == "__main__":
    main()
