# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Exercises the MCAT Mastery Query (the memory model) over the full
Python -> generated binding -> Rust backend chain."""

from tests.shared import getEmptyCol


def _add_tagged_note(col, front, tags):
    note = col.new_note(col.models.by_name("Basic"))
    note["Front"] = front
    note["Back"] = "answer"
    note.tags = tags
    col.add_note(note, col.decks.id("Default"))


def test_mastery_query_from_python():
    col = getEmptyCol()
    try:
        # two AAMC topics plus one untagged note
        _add_tagged_note(col, "q1", ["aamc::biochem::amino-acids"])
        _add_tagged_note(col, "q2", ["aamc::physics::kinematics"])
        _add_tagged_note(col, "q3", [])

        resp = col._backend.mastery_query(search="", min_reviews=0)

        topics = sorted(t.topic for t in resp.topics)
        assert topics == [
            "aamc::biochem::amino-acids",
            "aamc::physics::kinematics",
        ]
        # unstudied cards -> nothing mastered, no reviews, abstaining, score 0
        for t in resp.topics:
            assert t.total_cards == 1
            assert t.mastered_count == 0
            assert t.reviews == 0
            assert t.abstain
            assert t.memory_score == 0.0
        # overall rollup sees all three cards and abstains (no reviews yet)
        assert resp.overall.total_cards == 3
        assert resp.overall.abstain
    finally:
        col.close()
