# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Tests for the home page's 'suggested next step' decision tree.

``build_suggestion`` is pure (no Qt / collection), so we exercise every branch of
the priority sequence flashcards -> topical -> full-length directly.
"""

from __future__ import annotations

from aqt.home import TOPICAL_TEST_ROSTER, build_suggestion


def _sug(**kw):
    base = dict(
        has_due=False,
        due_total=0,
        perf_score=0.0,
        perf_abstain=True,
        mastered_sections={},
        taken=set(),
        per_test_score={},
    )
    base.update(kw)
    return build_suggestion(**base)


# 1. Flashcards due today ----------------------------------------------------


def test_due_flashcards_primary_and_unlock_hint():
    s = _sug(has_due=True, due_total=12)
    assert s.cta_cmd == "decks"
    assert "12" in s.body
    assert s.secondary_cmd == ""  # nothing fully mastered yet
    assert s.hint  # "master all of a topic's cards..." guidance


def test_due_flashcards_singular_grammar():
    s = _sug(has_due=True, due_total=1)
    assert "flashcard ready" in s.body  # singular, no trailing 's'
    assert "flashcards" not in s.body


def test_due_flashcards_with_mastered_topic_suggests_its_test():
    s = _sug(
        has_due=True,
        due_total=5,
        mastered_sections={"bio-biochem": ["Biochemistry"]},
    )
    assert s.cta_cmd == "decks"
    assert s.secondary_cmd == "topical"
    assert "Biochemistry" in s.secondary_text
    assert "Bio/Biochem Test 1" in s.secondary_text  # untaken preferred
    assert s.hint == ""


def test_due_takes_priority_over_performance():
    s = _sug(
        has_due=True,
        due_total=3,
        perf_abstain=False,
        perf_score=0.50,
        taken={"bio-biochem-1"},
        per_test_score={"bio-biochem-1": 0.50},
    )
    assert s.cta_cmd == "decks"


# 2a. No topical test taken yet ---------------------------------------------


def test_no_tests_taken_suggests_first_topical():
    s = _sug(has_due=False, perf_abstain=True)
    assert s.cta_cmd == "topical"
    assert "first topical" in s.heading.lower()


def test_no_tests_taken_prefers_mastered_section_test():
    s = _sug(
        has_due=False,
        perf_abstain=True,
        mastered_sections={"psych-soc": ["Psychology"]},
    )
    assert s.cta_cmd == "topical"
    assert "Psych/Soc Test 1" in s.body


# 2b. Performance below 85% -> retake weak (depth) --------------------------


def test_low_performance_retakes_only_sub85_tests():
    s = _sug(
        has_due=False,
        perf_abstain=False,
        perf_score=0.70,
        taken={"bio-biochem-1", "chem-phys-1"},
        per_test_score={"bio-biochem-1": 0.60, "chem-phys-1": 0.90},
    )
    assert s.cta_cmd == "topical"
    assert "weak" in s.heading.lower()
    assert "Bio/Biochem Test 1" in s.body  # the sub-85% one
    assert "Chem/Phys Test 1" not in s.body  # the >=85% one is not listed
    assert "70%" in s.body


def test_low_performance_no_weak_test_falls_back_to_untaken():
    # Overall <85% but the single taken test is >=85% (topic weighting) -> breadth.
    s = _sug(
        has_due=False,
        perf_abstain=False,
        perf_score=0.80,
        taken={"bio-biochem-1"},
        per_test_score={"bio-biochem-1": 0.90},
    )
    assert s.cta_cmd == "topical"
    assert "haven't tried" in s.body


# 2c. Performance >= 85% -> breadth first (confirmed tie-break) --------------


def test_strong_performance_suggests_new_untaken_test():
    s = _sug(
        has_due=False,
        perf_abstain=False,
        perf_score=0.90,
        taken={"bio-biochem-1"},
        per_test_score={"bio-biochem-1": 0.95},
    )
    assert s.cta_cmd == "topical"
    assert s.cta_label == "Take a new topical test"


def test_strong_performance_breadth_wins_over_weak_retake():
    # 85-99% band with BOTH a sub-85% test AND untaken tests -> take untaken first.
    s = _sug(
        has_due=False,
        perf_abstain=False,
        perf_score=0.90,
        taken={"bio-biochem-1"},
        per_test_score={"bio-biochem-1": 0.80},  # weak, yet overall >= 85%
    )
    assert s.cta_cmd == "topical"
    assert s.cta_label == "Take a new topical test"
    assert "Retake" not in s.cta_label


# 2d. Performance >= 85% and every test taken -> full-length ----------------


def test_all_taken_and_strong_suggests_full_length():
    taken = {t.test_id for t in TOPICAL_TEST_ROSTER}
    s = _sug(
        has_due=False,
        perf_abstain=False,
        perf_score=0.92,
        taken=taken,
        per_test_score={tid: 0.90 for tid in taken},
    )
    assert s.cta_cmd == "fullLength"
    assert "full-length" in s.heading.lower()
