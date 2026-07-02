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


def test_performance_and_readiness_from_python():
    from anki import mcat_pb2

    col = getEmptyCol()
    try:
        # No evidence: performance emits all four sections as "not tested", and
        # readiness abstains (no full-length exam on record).
        perf = col._backend.performance_query(min_questions=0)
        assert len(perf.sections) == 4
        assert all(s.not_tested for s in perf.sections)
        assert perf.sections_tested == 0
        ready = col._backend.readiness_query(search="", min_reviews=0, min_questions=0)
        assert ready.overall.abstain
        assert not ready.overall.has_completed_full_length

        # A topical test feeds the performance headline.
        col._backend.record_practice_result(
            test_id="cars-1",
            section_code="cars",
            topic_results=[
                mcat_pb2.PracticeTopicResult(
                    topic="aamc::cars::humanities", correct=6, answered=10
                )
            ],
            exam_kind=mcat_pb2.ExamKind.EXAM_KIND_TOPICAL,
            exam_id="t1",
        )
        perf = col._backend.performance_query(min_questions=0)
        assert perf.sections_tested == 1
        cars = next(s for s in perf.sections if s.section_code == "cars")
        assert not cars.not_tested and not cars.abstain
        assert cars.correct == 6 and cars.answered == 10
        # Topical evidence alone must not satisfy readiness (needs a full-length).
        ready = col._backend.readiness_query(search="", min_reviews=0, min_questions=0)
        assert ready.overall.abstain

        # A full-length exam must NOT move the performance headline, but it does
        # flip the readiness full-length gate.
        col._backend.record_practice_result(
            test_id="full-length",
            section_code="",
            topic_results=[
                mcat_pb2.PracticeTopicResult(
                    topic="aamc::cars::humanities", correct=7, answered=10
                )
            ],
            exam_kind=mcat_pb2.ExamKind.EXAM_KIND_FULL_LENGTH,
            exam_id="fl1",
        )
        perf2 = col._backend.performance_query(min_questions=0)
        cars2 = next(s for s in perf2.sections if s.section_code == "cars")
        assert cars2.answered == 10  # unchanged: full-length excluded from performance
        ready2 = col._backend.readiness_query(search="", min_reviews=0, min_questions=0)
        assert ready2.overall.has_completed_full_length
        assert not ready2.overall.abstain  # a completed full-length now exists
    finally:
        col.close()


def test_grade_free_response_degrades_without_key(monkeypatch):
    from anki import mcat_pb2

    # No API key -> the grader must return graded=false with a reason, never a
    # hard error (so the app degrades gracefully).
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    col = getEmptyCol()
    try:
        resp = col._backend.grade_free_response(
            prompt="Explain why competitive inhibition raises apparent Km.",
            answer="It competes for the active site.",
            max_points=4,
            rubric=[
                mcat_pb2.RubricCriterion(
                    id="c1",
                    description="mentions competition for the active site",
                    points=4,
                    required_concepts=["competes for active site"],
                    disqualifiers=[],
                )
            ],
            model="",
        )
        assert not resp.graded
        assert resp.error  # a human-readable reason
        assert resp.points_awarded == 0
        assert resp.max_points == 4
    finally:
        col.close()
