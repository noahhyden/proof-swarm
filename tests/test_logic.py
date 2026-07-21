"""Offline tests for the pure logic - no model or Ollama needed.

Run:  uv run pytest -q
  or: uv run python tests/test_logic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("all tests passed")
