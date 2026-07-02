# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""The MCAT readiness model (single source of truth for the home screen and the
MCAT Readiness tab).

Topical readiness (per AAMC discipline) is a weighted sum of three signals,
ordered lowest -> highest weight (Insight 4):
  * Memory  — the DSR / flashcard recall score (Mastery Query)          W_MEMORY
  * Synthesis — the topical practice-test score (performance model)     W_SYNTHESIS
  * Full-length — the full-length practice-test score (performance)     W_FULL_LENGTH
A component the user has not completed counts as 0, and each component carries a
statistical range, so topical readiness is itself a range.

Full readiness (Insight 5) is the AAMC-content-category-weighted sum of the
per-discipline topical readiness, with any *unstudied* discipline counting as 0
(i.e. it assumes every question is missed on topics you haven't touched). It is
reported as a range and is the headline "Readiness" score.
"""

from __future__ import annotations

import math

# Topical-readiness component weights (low -> high). Memory is capped at 5%.
W_MEMORY = 0.05
W_SYNTHESIS = 0.35
W_FULL_LENGTH = 0.60

# AAMC content-category distribution across the seven science disciplines
# (each value is that discipline's share of the exam's science content; derived
# from AAMC's per-section discipline percentages, normalized to sum to ~1).
AAMC_TOPIC_WEIGHTS: dict[str, float] = {
    "aamc::bio-biochem::biology": 0.25,
    "aamc::psych-soc::psychology": 0.217,
    "aamc::bio-biochem::biochemistry": 0.167,
    "aamc::chem-phys::gen-chem": 0.117,
    "aamc::psych-soc::sociology": 0.10,
    "aamc::chem-phys::physics": 0.083,
    "aamc::chem-phys::orgo": 0.067,
}

# Topical practice tests are section-level, so a discipline's synthesis score
# comes from its section's test attempts.
TOPIC_SECTION: dict[str, str] = {
    "aamc::bio-biochem::biology": "bio-biochem",
    "aamc::bio-biochem::biochemistry": "bio-biochem",
    "aamc::chem-phys::gen-chem": "chem-phys",
    "aamc::chem-phys::physics": "chem-phys",
    "aamc::chem-phys::orgo": "chem-phys",
    "aamc::psych-soc::psychology": "psych-soc",
    "aamc::psych-soc::sociology": "psych-soc",
}

TOPIC_LABELS: dict[str, str] = {
    "aamc::bio-biochem::biology": "Biology",
    "aamc::bio-biochem::biochemistry": "Biochemistry",
    "aamc::chem-phys::gen-chem": "General Chemistry",
    "aamc::chem-phys::physics": "Physics",
    "aamc::chem-phys::orgo": "Organic Chemistry",
    "aamc::psych-soc::psychology": "Psychology",
    "aamc::psych-soc::sociology": "Sociology",
}


def wilson(correct: int, total: int) -> tuple[float, float, float]:
    """(point estimate, 95% low, 95% high) for a proportion; (0,0,0) with no data."""
    if total <= 0:
        return (0.0, 0.0, 0.0)
    p = correct / total
    z = 1.96
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))
    return (p, max(0.0, center - margin), min(1.0, center + margin))


def _section_performance(attempts: list) -> dict[str, tuple[float, float, float]]:
    """section_code -> (score, low, high) aggregated over topical-test attempts."""
    agg: dict[str, tuple[int, int]] = {}
    for a in attempts:
        sec = a.get("section_code")
        overall = a.get("overall", {})
        try:
            c = int(overall.get("correct", 0))
            t = int(overall.get("total", 0))
        except (TypeError, ValueError):
            continue
        if sec and t > 0:
            cc, tt = agg.get(sec, (0, 0))
            agg[sec] = (cc + c, tt + t)
    return {sec: wilson(c, t) for sec, (c, t) in agg.items()}


def compute(
    memory_by_tag: dict[str, tuple[float, float, float]],
    attempts: list | None,
) -> dict:
    """Compute per-discipline topical readiness and the full readiness range.

    memory_by_tag: {aamc tag: (memory_score, low, high)} from the Mastery Query.
    attempts: list of recorded topical-test attempts (each has section_code +
    overall {correct,total}).
    """
    sec_perf = _section_performance(attempts or [])
    topics: list[dict] = []
    full = full_low = full_high = 0.0
    total_w = sum(AAMC_TOPIC_WEIGHTS.values()) or 1.0

    for tag, weight in AAMC_TOPIC_WEIGHTS.items():
        mem, mem_lo, mem_hi = memory_by_tag.get(tag, (0.0, 0.0, 0.0))
        syn, syn_lo, syn_hi = sec_perf.get(TOPIC_SECTION[tag], (0.0, 0.0, 0.0))
        # Full-length practice tests are not implemented yet -> 0 (counts against).
        fl = fl_lo = fl_hi = 0.0

        r = W_MEMORY * mem + W_SYNTHESIS * syn + W_FULL_LENGTH * fl
        r_lo = W_MEMORY * mem_lo + W_SYNTHESIS * syn_lo + W_FULL_LENGTH * fl_lo
        r_hi = W_MEMORY * mem_hi + W_SYNTHESIS * syn_hi + W_FULL_LENGTH * fl_hi

        topics.append(
            {
                "tag": tag,
                "label": TOPIC_LABELS[tag],
                "memory": mem,
                "synthesis": syn,
                "full_length": fl,
                "readiness": r,
                "low": r_lo,
                "high": r_hi,
            }
        )
        full += weight * r
        full_low += weight * r_lo
        full_high += weight * r_hi

    topics.sort(key=lambda t: t["readiness"], reverse=True)

    # Overall Performance summary (fraction correct across all attempts).
    all_attempts = attempts or []
    oc = sum(int(a.get("overall", {}).get("correct", 0)) for a in all_attempts)
    ot = sum(int(a.get("overall", {}).get("total", 0)) for a in all_attempts)
    p_score, p_low, p_high = wilson(oc, ot)

    return {
        "topics": topics,
        "full": {
            "readiness": full / total_w,
            "low": full_low / total_w,
            "high": full_high / total_w,
        },
        "performance": {
            "score": p_score,
            "low": p_low,
            "high": p_high,
            "attempts": len(all_attempts),
        },
    }
