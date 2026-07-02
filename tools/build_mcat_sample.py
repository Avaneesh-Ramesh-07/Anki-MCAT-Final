# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Build a small AAMC-tagged MCAT sample deck for exercising the Mastery Query
(the memory model). Creates a temp collection, enables FSRS, adds `aamc::`-tagged
notes across a few topics, reviews each card once (one topic answered slowly to
demonstrate the answer-time comfort discount), prints the live per-topic mastery
numbers, and exports `tools/mcat_sample.apkg`.

Run from the repo root with the built env:
    out\\pyenv\\Scripts\\python.exe tools\\build_mcat_sample.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
# `anki` is a namespace package merged across source (pylib) + generated (out/pylib)
sys.path[:0] = ["pylib", "out/pylib"]

import tempfile

from anki.collection import Collection, DeckIdLimit, ExportAnkiPackageOptions
from anki.scheduler.v3 import CardAnswer
from anki.utils import int_time

FAST_MS = 3000
SLOW_MS = 13000  # > 1.5x median -> "effortful" -> comfort discount

# topic tag -> (list of (front, back), latency_ms used when reviewing)
TOPICS = {
    "aamc::bio-biochem::amino-acids": (
        [
            ("Which amino acid has no chiral center?", "Glycine"),
            ("Net charge of an amino acid zwitterion at physiological pH?", "Zero"),
            ("Which amino acid has a thiol (-SH) side chain?", "Cysteine"),
        ],
        FAST_MS,
    ),
    "aamc::bio-biochem::enzyme-kinetics": (
        [
            (
                "In Michaelis-Menten kinetics, what does Km represent?",
                "[substrate] at half Vmax",
            ),
            ("How does a competitive inhibitor affect Vmax?", "No change"),
            (
                "A low Km indicates what about enzyme-substrate affinity?",
                "High affinity",
            ),
        ],
        FAST_MS,
    ),
    "aamc::chem-phys::thermodynamics": (
        [
            ("Sign of delta-G for a spontaneous process?", "Negative"),
            ("State the first law of thermodynamics.", "Energy is conserved"),
            ("For an isothermal ideal-gas process, what is delta-U?", "Zero"),
        ],
        FAST_MS,
    ),
    "aamc::chem-phys::circuits": (
        [
            ("State Ohm's law.", "V = IR"),
            (
                "How does total resistance change for resistors in parallel?",
                "It decreases",
            ),
            ("Unit of capacitance?", "Farad"),
        ],
        FAST_MS,
    ),
    # answered slowly -> should show a lower (comfort-discounted) memory score
    "aamc::psych-soc::memory": (
        [
            (
                "Memory store holding info ~15-30s without rehearsal?",
                "Short-term memory",
            ),
            ("Term for memory of facts and events?", "Declarative (explicit) memory"),
            ("Who proposed the multi-store model of memory?", "Atkinson and Shiffrin"),
        ],
        SLOW_MS,
    ),
}

OUT = os.path.join(ROOT, "tools", "mcat_sample.apkg")


def main() -> None:
    fd, path = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    os.unlink(path)
    col = Collection(path)
    try:
        col.set_config("fsrs", True)
        deck_id = col.decks.id("MCAT Sample")
        col.decks.set_current(deck_id)  # scheduler queues from the current deck
        notetype = col.models.by_name("Basic")

        latency_by_card: dict[int, int] = {}
        for tag, (cards, latency) in TOPICS.items():
            for front, back in cards:
                note = col.new_note(notetype)
                note["Front"] = front
                note["Back"] = back
                note.tags = [tag]
                col.add_note(note, deck_id)
                for card in note.cards():
                    latency_by_card[card.id] = latency

        # Review every new card once (rating Good). One FSRS review is enough to
        # populate memory state, so retrievability/scores become non-zero.
        answered = 0
        for _ in range(500):
            queued = col.sched.get_queued_cards(fetch_limit=1)  # type: ignore[union-attr]
            if not queued.cards:
                break
            top = queued.cards[0]
            answer = CardAnswer(
                card_id=top.card.id,
                current_state=top.states.current,
                new_state=top.states.good,
                rating=CardAnswer.GOOD,
                answered_at_millis=int_time(1000),
                milliseconds_taken=latency_by_card.get(top.card.id, FAST_MS),
            )
            col.sched.answer_card(answer)  # type: ignore[union-attr]
            answered += 1

        # Diagnostics: show the live memory model over the freshly-studied deck.
        cids = col.find_cards("")
        try:
            mem: object = col.get_card(cids[0]).memory_state
        except Exception as exc:  # pragma: no cover - diagnostic only
            mem = f"<unavailable: {exc}>"
        print(f"answered={answered} cards={len(cids)} sample_memory_state={mem}")
        resp = col._backend.mastery_query(search="", min_reviews=1)
        print("per-topic memory model (min_reviews=1):")
        for t in sorted(resp.topics, key=lambda t: t.topic):
            print(
                f"  {t.topic}: score={t.memory_score:.3f} "
                f"range=[{t.range_low:.3f},{t.range_high:.3f}] "
                f"mastered={t.mastered_count}/{t.total_cards} "
                f"reviews={t.reviews} abstain={t.abstain}"
            )
        o = resp.overall
        print(
            f"  OVERALL: score={o.memory_score:.3f} reviews={o.reviews} abstain={o.abstain}"
        )

        col.export_anki_package(
            out_path=OUT,
            options=ExportAnkiPackageOptions(
                with_scheduling=True,
                with_deck_configs=True,
                with_media=False,
                legacy=False,
            ),
            limit=DeckIdLimit(deck_id=deck_id),
        )
        print(f"WROTE {OUT}")
    finally:
        col.close()


if __name__ == "__main__":
    main()
