"""Offline tests for the multi-agent patterns, driven by fake agents.

No model is called: a FakeAgent returns scripted replies, so every branch of
single/verify/debate/vote/planted is exercised deterministically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proofswarm import orchestrator as orch
from proofswarm.orchestrator import _problem_prompt

PROBLEM = {
    "statement": "The sum of an even integer and an odd integer is always odd.",
    "definitions": "x is even if x = 2a; x is odd if x = 2a + 1.",
}
PLANTED = {**PROBLEM, "flawed_proof": "e + o = 2(a+b+1), so even.", "bug": "absorbs +1"}


class FakeAgent:
    def __init__(self, name, replies, stream=False):
        self.name = name
        self.replies = list(replies)
        self.stream = stream
        self.temperature = 0.7
        self.seed = 42
        self.reset_called = False
        self.messages = []  # everything this agent was asked
        self.seeds = []  # the seed in effect at each call

    def ask(self, message, remember=False):
        self.messages.append(message)
        self.seeds.append(self.seed)
        return self.replies.pop(0)

    def reset(self):
        self.reset_called = True


def test_problem_prompt_includes_statement_and_definitions():
    p = _problem_prompt(PROBLEM)
    assert PROBLEM["statement"] in p
    assert PROBLEM["definitions"] in p
    assert "Prove this statement" in p


def test_problem_prompt_falls_back_when_no_definitions():
    p = _problem_prompt({"statement": "S"})
    assert "none given" in p


def test_single_returns_the_proof_and_sends_the_problem():
    prover = FakeAgent("Prover", ["a proof ANSWER: odd"])
    assert orch.single(PROBLEM, prover) == "a proof ANSWER: odd"
    assert PROBLEM["statement"] in prover.messages[0]


def test_single_streaming_branch():
    prover = FakeAgent("Prover", ["streamed ANSWER: odd"], stream=True)
    assert orch.single(PROBLEM, prover) == "streamed ANSWER: odd"


def test_verify_revises_then_stops_when_critic_satisfied():
    prover = FakeAgent("Prover", ["initial", "revised"])
    critic = FakeAgent("Critic", ["VERDICT: NEEDS WORK", "VERDICT: CORRECT"])
    result = orch.verify(PROBLEM, prover, [critic], rounds=2)
    assert result == "revised"
    assert prover.reset_called
    # the critic must actually be shown the proof it is meant to check
    assert "initial" in critic.messages[0]
    # the revision request must carry the critic's feedback back to the prover
    assert "NEEDS WORK" in prover.messages[1]


def test_verify_stops_immediately_when_first_verdict_correct():
    prover = FakeAgent("Prover", ["initial"])
    critic = FakeAgent("Critic", ["VERDICT: CORRECT"])
    assert orch.verify(PROBLEM, prover, [critic], rounds=2) == "initial"


def test_verify_runs_all_rounds_when_never_satisfied():
    prover = FakeAgent("Prover", ["p0", "p1", "p2"])
    critic = FakeAgent("Critic", ["VERDICT: NEEDS WORK", "VERDICT: NEEDS WORK"])
    assert orch.verify(PROBLEM, prover, [critic], rounds=2) == "p2"


def test_debate_winner_a():
    a, b = FakeAgent("A", ["proofA"]), FakeAgent("B", ["proofB"])
    judge = FakeAgent("Judge", ["reasons... WINNER: A"])
    assert orch.debate(PROBLEM, a, b, judge) == "proofA"
    # the judge must be shown both proofs
    assert "proofA" in judge.messages[0] and "proofB" in judge.messages[0]


def test_debate_winner_b():
    a, b = FakeAgent("A", ["proofA"]), FakeAgent("B", ["proofB"])
    judge = FakeAgent("Judge", ["reasons... WINNER: B"])
    assert orch.debate(PROBLEM, a, b, judge) == "proofB"


def test_debate_neither():
    a, b = FakeAgent("A", ["proofA"]), FakeAgent("B", ["proofB"])
    judge = FakeAgent("Judge", ["both wrong WINNER: NEITHER"])
    out = orch.debate(PROBLEM, a, b, judge)
    assert "neither" in out.lower()


def test_vote_picks_majority_answer():
    replies = ["x ANSWER: odd", "y ANSWER: even", "z ANSWER: odd"]
    prover = FakeAgent("Prover", replies)
    # majority is 'odd' (2 of 3); returns the first proof that produced it
    assert orch.vote(PROBLEM, prover, samples=3) == "x ANSWER: odd"


def test_planted_reports_catch_rate():
    critic = FakeAgent(
        "Critic",
        ["VERDICT: NEEDS WORK", "VERDICT: CORRECT", "VERDICT: NEEDS WORK"],
    )
    result = orch.planted(PLANTED, critic, samples=3)
    assert result["caught"] == 2
    assert result["samples"] == 3
    assert abs(result["catch_rate"] - 2 / 3) < 1e-9
    # the critic must be shown the flawed proof it is meant to catch
    assert PLANTED["flawed_proof"] in critic.messages[0]


def test_vote_sends_the_problem_each_sample():
    prover = FakeAgent("Prover", ["a ANSWER: odd", "b ANSWER: odd"])
    orch.vote(PROBLEM, prover, samples=2)
    assert all(PROBLEM["statement"] in m for m in prover.messages)


def test_vote_derives_ascending_seeds_from_base():
    # Determinism contract: sample i uses base_seed + i (not - i), so the whole
    # vote replays from one seed. Kills the base_seed +/- i mutant.
    prover = FakeAgent("Prover", ["a ANSWER: odd", "b ANSWER: odd", "c ANSWER: odd"])
    prover.seed = 100
    orch.vote(PROBLEM, prover, samples=3)
    assert prover.seeds == [100, 101, 102]
