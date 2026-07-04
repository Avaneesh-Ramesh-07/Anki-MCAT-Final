#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Offline eval harness for the MCAT free-response AI grader.

Measures how reliably the chosen OpenAI model reasons about MCAT content — the
justification for trusting it as the rubric-based FRQ grader. It does NOT test
the FRQ grader directly; instead it exercises the model's underlying subject
competence on a curated, ground-truth MCQ set (with answer explanations), which
is the knowledge the grader relies on.

Pipeline (per question, by subject):
  1. ANSWERING AGENT (no ground truth): given only the stem + options, the model
     picks an answer and writes its reasoning.
  2. JUDGE (with ground truth): given the ground-truth explanation + the agent's
     answer/reasoning, the model scores 0..1 for how well they match.
  3. COMPOSITE ACCURACY = mean judge score (reported per subject + overall),
     alongside a raw exact-match rate baseline.

"Don't train the grader on ground truth" is honored: the answering agent (like
the in-app FRQ grader) never sees the explanation/key; only the judge does.

Inputs:  resources/ground_truth/eval_set.json  (from tools/curate_eval_set.py)
Outputs: printed per-subject table + resources/ground_truth/eval_results_<ts>.json
Both live under the git-ignored ground_truth dir.

Run:  OPENAI_API_KEY=sk-... out/pyenv/bin/python tools/eval_grader.py
      (flags: --subject bio --limit 10 --model gpt-4o-mini)
No key -> prints a notice and exits 0 (so it's safe in CI).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print(
        "httpx is required (out/pyenv already has it). Run with out/pyenv/bin/python."
    )
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = ROOT / "resources" / "ground_truth" / "eval_set.json"
OPENAI_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
)
DEFAULT_MODEL = os.environ.get("OPENAI_EVAL_MODEL", "gpt-4.1")


def load_local_env() -> None:
    """Load KEY=VALUE lines from .env.local / .env (repo root) into the
    environment without overriding vars already set. No dependency on
    python-dotenv."""
    for name in (".env.local", ".env"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.strip().strip('"').strip("'")
            if val:
                os.environ.setdefault(key.strip(), val)


def openai_json(
    client: httpx.Client, api_key: str, model: str, system: str, user: str
) -> dict:
    """One deterministic chat call that must return a JSON object."""
    resp = client.post(
        OPENAI_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0,
            "seed": 7,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=90.0,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


ANSWER_SYSTEM = (
    "You are taking the MCAT. Answer the multiple-choice question. Think briefly, "
    'then respond ONLY with JSON: {"choice":"A|B|C|D","reasoning":"<2-4 '
    'sentences on why that option is correct>"}.'
)

JUDGE_SYSTEM = (
    "You are an expert MCAT grader with access to the official answer explanation. "
    "Judge how well a student's chosen answer AND reasoning match the ground-truth "
    "explanation. Reward correct choice with sound, on-topic reasoning; penalize "
    "wrong choices or reasoning that contradicts the explanation. Respond ONLY with "
    'JSON: {"score":<float 0..1>,"justification":"<1-2 sentences>"}.'
)


def answer_question(client, key, model, q: dict) -> dict:
    opts = "\n".join(f"{k}) {v}" for k, v in q["options"].items())
    user = f"Question:\n{q['stem']}\n\nOptions:\n{opts}"
    out = openai_json(client, key, model, ANSWER_SYSTEM, user)
    return {
        "choice": str(out.get("choice", "")).strip()[:1].upper(),
        "reasoning": out.get("reasoning", ""),
    }


def judge_answer(client, key, model, q: dict, agent: dict) -> dict:
    opts = "\n".join(f"{k}) {v}" for k, v in q["options"].items())
    user = (
        f"Question:\n{q['stem']}\n\nOptions:\n{opts}\n\n"
        f"GROUND-TRUTH correct answer: {q['correct']}\n"
        f"GROUND-TRUTH explanation:\n{q['explanation']}\n\n"
        f"STUDENT chose: {agent['choice']}\n"
        f"STUDENT reasoning:\n{agent['reasoning']}\n\n"
        "Score 0..1 for how well the student's answer + reasoning match the ground truth."
    )
    out = openai_json(client, key, model, JUDGE_SYSTEM, user)
    try:
        score = float(out.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "score": max(0.0, min(1.0, score)),
        "justification": out.get("justification", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Evaluate the MCAT grader LLM's reliability."
    )
    ap.add_argument("--subject", help="only evaluate this subject")
    ap.add_argument(
        "--limit", type=int, help="max questions per subject (cheap smoke run)"
    )
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    load_local_env()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print(
            "OPENAI_API_KEY not set — skipping eval (this is expected in CI). Exit 0."
        )
        return 0
    if not EVAL_SET.exists():
        print(f"Eval set not found: {EVAL_SET}\nRun tools/curate_eval_set.py first.")
        return 1

    questions = json.loads(EVAL_SET.read_text())
    by_subject: dict[str, list[dict]] = {}
    for q in questions:
        if args.subject and q["subject"] != args.subject:
            continue
        by_subject.setdefault(q["subject"], []).append(q)

    results: list[dict] = []
    with httpx.Client() as client:
        for subject, qs in sorted(by_subject.items()):
            if args.limit:
                qs = qs[: args.limit]
            for i, q in enumerate(qs, 1):
                try:
                    agent = answer_question(client, key, args.model, q)
                    verdict = judge_answer(client, key, args.model, q, agent)
                except Exception as e:  # noqa: BLE001 - per-item resilience
                    print(f"  [{subject} {i}] error: {e}")
                    continue
                results.append(
                    {
                        "subject": subject,
                        "id": q.get("id", ""),
                        "agent_choice": agent["choice"],
                        "correct": q["correct"],
                        "exact_match": agent["choice"] == q["correct"],
                        "judge_score": verdict["score"],
                    }
                )
                print(
                    f"  [{subject} {i}/{len(qs)}] chose {agent['choice']} "
                    f"(key {q['correct']}) judge={verdict['score']:.2f}"
                )

    if not results:
        print("No results.")
        return 1

    # Per-subject + overall composite accuracy.
    print("\n=== Composite accuracy (mean judge score 0..1) ===")
    subjects = sorted({r["subject"] for r in results})
    for subject in subjects:
        rs = [r for r in results if r["subject"] == subject]
        mean = sum(r["judge_score"] for r in rs) / len(rs)
        exact = sum(r["exact_match"] for r in rs) / len(rs)
        print(
            f"  {subject:14s} n={len(rs):3d}  accuracy={mean:.3f}  exact-match={exact:.3f}"
        )
    overall = sum(r["judge_score"] for r in results) / len(results)
    overall_exact = sum(r["exact_match"] for r in results) / len(results)
    print(
        f"  {'OVERALL':14s} n={len(results):3d}  accuracy={overall:.3f}  exact-match={overall_exact:.3f}"
    )

    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    out_path = EVAL_SET.parent / f"eval_results_{ts}.json"
    out_path.write_text(
        json.dumps(
            {
                "model": args.model,
                "n": len(results),
                "composite_accuracy": overall,
                "exact_match_rate": overall_exact,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nComposite accuracy: {overall:.3f}  (saved {out_path.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
