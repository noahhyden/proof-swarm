"""Offline tests for the pure logic — no model or Ollama needed.

Run:  uv run python -m pytest tests/ -q
  or: uv run python tests/test_logic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.orchestrator import _extract_answer


def test_extract_answer_reads_answer_line():
    proof = "Step 1...\nStep 2...\nANSWER: the sum is even"
    assert _extract_answer(proof) == "the sum is even"


def test_extract_answer_is_case_insensitive():
    assert _extract_answer("answer: Odd") == "odd"


def test_extract_answer_falls_back_when_no_marker():
    text = "No marker here, just prose."
    assert _extract_answer(text) == text.strip().lower()[:80]


if __name__ == "__main__":
    test_extract_answer_reads_answer_line()
    test_extract_answer_is_case_insensitive()
    test_extract_answer_falls_back_when_no_marker()
    print("all tests passed")
