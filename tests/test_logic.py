"""Offline tests for the pure logic - no model or Ollama needed.

Run:  uv run pytest -q
  or: uv run python tests/test_logic.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.orchestrator import _caught_bug
from src.scoring import extract_answer, score


def test_extract_answer_reads_answer_line():
    assert extract_answer("Step 1...\nANSWER: the sum is even") == "the sum is even"


def test_extract_answer_falls_back_when_no_marker():
    text = "No marker here, just prose."
    assert extract_answer(text) == text.strip()[:120]


def test_score_correct_when_tokens_present():
    result = score("blah blah\nANSWER: therefore the result is odd", "odd")
    assert result["correct"] is True


def test_score_incorrect_when_token_absent():
    result = score("blah blah\nANSWER: the result is even", "odd")
    assert result["correct"] is False


def test_score_all_tokens_required():
    # expected 'n 1 2' -> every token must appear in the answer
    good = score("ANSWER: 1+2+...+n = n(n+1)/2", "n 1 2")
    bad = score("ANSWER: it is n", "n 1 2")
    assert good["correct"] is True
    assert bad["correct"] is False


def test_caught_bug_detects_verdict():
    assert _caught_bug("VERDICT: NEEDS WORK - step 3 is wrong") is True
    assert _caught_bug("Looks good. VERDICT: CORRECT") is False


def test_planted_problems_are_well_formed():
    # Any problem that offers a planted bug must carry both a flawed proof and
    # a description of the bug, or planted mode has nothing to score.
    problems = json.loads((Path(__file__).resolve().parent.parent
                           / "problems" / "problems.json").read_text())
    planted = {k: p for k, p in problems.items() if "flawed_proof" in p}
    assert planted, "expected at least one planted-bug problem"
    for key, p in planted.items():
        assert p.get("flawed_proof"), f"{key} missing flawed_proof text"
        assert p.get("bug"), f"{key} missing bug description"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("all tests passed")
