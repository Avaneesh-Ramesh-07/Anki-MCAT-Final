#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Curate the eval set for tools/eval_grader.py from MCAT_Qbook.pdf.

Extracts up to N multiple-choice questions per subject (with the keyed answer and
the answer explanation) from the QBook — which is organized into 7 subject
chapters (questions) plus a Solutions section whose per-subject solution numbering
restarts at 1, mirroring the chapter order. Writes them to a git-ignored local
file (verbatim ground truth must never be committed; see the content policy).

Run:  out/pyenv/bin/python tools/curate_eval_set.py [--per-subject 50]
Requires: pymupdf  (out/pyenv/bin/python -m pip install pymupdf)
Output:   resources/ground_truth/eval_set.json  (git-ignored)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz  # type: ignore[import-untyped]  # pymupdf

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "resources" / "ground_truth" / "MCAT_Qbook.pdf"
OUT = ROOT / "resources" / "ground_truth" / "eval_set.json"

# QBook chapter -> our subject key. Chapter 8 (Graph Practice) is skipped: it
# depends on figures we can't feed as text. Solutions restart numbering in this
# same order.
SUBJECTS = [
    ("Chapter 1: Biology", "biology"),
    ("Chapter 2: Biochemistry", "biochemistry"),
    ("Chapter 3: Psychology", "psychology"),
    ("Chapter 4: General Chemistry", "gen-chem"),
    ("Chapter 5: Physics", "physics"),
    ("Chapter 6: Sociology", "sociology"),
    ("Chapter 7: Organic Chemistry", "orgo"),
]

# zero-width space, ZWNJ, ZWJ, BOM, soft hyphen
_ZW = dict.fromkeys(map(ord, "\u200b‌‍﻿\xad"), None)


def clean(text: str) -> str:
    text = text.translate(_ZW).replace("\t", " ")
    # strip stray control chars (e.g. the \x07 list-bullet glyph) but keep \n
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # drop the per-page copyright/running-header noise
    lines = [
        ln
        for ln in text.split("\n")
        if "Next Step Pre-Med" not in ln and not re.fullmatch(r"\s*\d+\s*", ln)
    ]
    return "\n".join(lines)


def page_ranges(
    doc: fitz.Document,
) -> tuple[list[tuple[str, str, int, int]], tuple[int, int]]:
    """Return [(chapter_title, subject, start_pdf_page, end_pdf_page)] and the
    (start, end) of the Solutions section, all 1-indexed inclusive."""
    toc = doc.get_toc()  # [level, title, page]
    starts = {title: int(page) for _, title, page in toc}
    sol_start = starts.get("Solutions")
    assert sol_start is not None, "Solutions bookmark not found in the PDF TOC"
    ranges: list[tuple[str, str, int, int]] = []
    for i, (title, subject) in enumerate(SUBJECTS):
        start = starts[title]
        nxt = (
            SUBJECTS[i + 1][0] if i + 1 < len(SUBJECTS) else "Chapter 8: Graph Practice"
        )
        end = starts[nxt] - 1
        ranges.append((title, subject, start, end))
    return ranges, (sol_start, int(doc.page_count))


def subject_text(doc: fitz.Document, start: int, end: int) -> str:
    return clean("\n".join(doc[p - 1].get_text() for p in range(start, end + 1)))


def parse_questions(text: str) -> dict[int, dict]:
    """number -> {stem, options{A..D}}."""
    # split into blocks starting at "N." at a line start
    blocks = re.split(r"\n\s*(\d+)\.\s", "\n" + text)
    # blocks = [pre, num, body, num, body, ...]
    out: dict[int, dict] = {}
    for i in range(1, len(blocks) - 1, 2):
        num = int(blocks[i])
        body = " ".join(blocks[i + 1].split())
        parsed = split_options(body)
        if parsed and num not in out:
            stem_end, options = parsed
            stem = body[:stem_end].strip()
            if len(stem) > 15:  # skip fragments
                out[num] = {"stem": stem, "options": options}
    return out


def split_options(body: str) -> tuple[int, dict[str, str]] | None:
    """Find 'A) ... B) ... C) ... D) ...'; return (stem_end_index, {A..D})."""
    marks: dict[str, int] = {}
    for letter in "ABCD":
        m = re.search(rf"(?<![A-Za-z0-9]){letter}\)\s", body)
        if not m:
            return None
        marks[letter] = m.start()
    if not (marks["A"] < marks["B"] < marks["C"] < marks["D"]):
        return None
    order = list("ABCD")
    options: dict[str, str] = {}
    for j, letter in enumerate(order):
        seg_start = marks[letter] + len(letter) + 2  # past "X) "
        seg_end = marks[order[j + 1]] if j + 1 < len(order) else len(body)
        options[letter] = body[seg_start:seg_end].strip()
    return marks["A"], options


def parse_solutions(text: str) -> list[tuple[int, str, str]]:
    """Ordered [(number, correct_letter, explanation)] across the whole Solutions
    section (numbering restarts per subject)."""
    out = []
    # a solution starts with "N. <letter> is correct" (letter may sit on the next
    # line after the number)
    pat = re.compile(r"\n\s*(\d+)\.\s*([A-D])\s+is\s+correct", re.IGNORECASE)
    matches = list(pat.finditer("\n" + text))
    for i, m in enumerate(matches):
        num = int(m.group(1))
        letter = m.group(2).upper()
        expl_start = m.end()
        expl_end = matches[i + 1].start() if i + 1 < len(matches) else len(text) + 1
        expl = " ".join(("\n" + text)[expl_start:expl_end].split())
        out.append((num, letter, expl))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-subject", type=int, default=50)
    args = ap.parse_args()

    doc = fitz.open(PDF)
    ranges, (sol_start, sol_end) = page_ranges(doc)
    sol_text = subject_text(doc, sol_start, sol_end)
    # Questions and solutions share ONE continuous global numbering (biology
    # 1..520, biochemistry 521..860, ...), so match by global number and take the
    # subject from the chapter the question was parsed from — no segmentation.
    global_sols: dict[int, tuple[str, str]] = {}
    for num, letter, expl in parse_solutions(sol_text):
        global_sols.setdefault(num, (letter, expl))
    print(
        f"Solutions section p{sol_start}-{sol_end}: {len(global_sols)} solutions parsed"
    )

    curated: list[dict] = []
    for idx, (title, subject, start, end) in enumerate(ranges):
        questions = parse_questions(subject_text(doc, start, end))
        sols = global_sols
        matched = 0
        for num in sorted(questions):
            if matched >= args.per_subject:
                break
            if num not in sols:
                continue
            letter, expl = sols[num]
            if not expl or len(expl) < 20:
                continue
            q = questions[num]
            curated.append(
                {
                    "subject": subject,
                    "id": f"{subject}-{num}",
                    "stem": q["stem"],
                    "options": q["options"],
                    "correct": letter,
                    "explanation": expl,
                }
            )
            matched += 1
        print(
            f"  {subject:14s} p{start}-{end}: parsed_q={len(questions):4d} "
            f"sols={len(sols):4d} matched={matched}"
        )

    OUT.write_text(json.dumps(curated, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(curated)} questions across {len(ranges)} subjects -> {OUT}")
    print("(git-ignored; verbatim ground truth, do not commit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
