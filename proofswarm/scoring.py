"""Score a proof attempt against a problem's ground-truth answer.

This is intentionally simple and transparent: it normalizes text and checks
whether the known answer's key tokens appear in the model's stated ANSWER line.
It does NOT judge whether the *proof* is rigorous - only whether the final
claim matches. (Judging rigor is what the `verify`/`debate` modes explore.)

Why it exists: an experiment repo without ground truth accumulates runs you can
never score. Capturing correctness at run time is cheap; reconstructing it later
means re-running everything.
"""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def extract_answer(text: str) -> str:
    """Pull the model's final claim (the 'ANSWER:' line, else a fallback)."""
    match = re.search(r"ANSWER:\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()[:120]


def score(proof_text: str, expected_answer: str) -> dict:
    """Return {correct, expected, got} for a single proof attempt.

    `expected_answer` is a short phrase whose tokens must all appear in the
    model's stated answer (order-independent). Keep expected answers terse so
    this stays robust to phrasing differences.
    """
    got = extract_answer(proof_text)
    got_norm = set(_normalize(got).split())
    expected_tokens = [t for t in _normalize(expected_answer).split() if t]
    correct = bool(expected_tokens) and all(t in got_norm for t in expected_tokens)
    return {"correct": correct, "expected": expected_answer, "got": got}
