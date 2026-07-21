"""The multi-agent reasoning patterns.

Each function takes a `problem` dict (see problems/problems.json) and returns a
final proof attempt as text. The point of this file is to be *read*: every
pattern is a short, explicit choreography of who says what to whom.
"""

from __future__ import annotations

import re
from collections import Counter

from .llm import Agent

# --- Role prompts --------------------------------------------------------------

PROVER_SYSTEM = (
    "You are a careful mathematics student. Prove the given statement step by "
    "step. State every definition you use. Do not skip steps. Explain as if to "
    "a curious child: short sentences, plain words. End with a line 'ANSWER: '"
    "followed by your one-sentence conclusion."
)

CRITIC_SYSTEM = (
    "You are a strict but kind proof checker. Read the student's proof. For each "
    "step, decide if it is justified. Point out any leap, missing definition, or "
    "error. If the proof is fully correct, say 'VERDICT: CORRECT'. Otherwise say "
    "'VERDICT: NEEDS WORK' and list exactly what to fix."
)

JUDGE_SYSTEM = (
    "You are an impartial mathematics judge. You are shown two proofs of the same "
    "statement. Decide which is more rigorous and clear, or if both fail. "
    "Explain briefly, then end with 'WINNER: A', 'WINNER: B', or 'WINNER: NEITHER'."
)


def _problem_prompt(problem: dict) -> str:
    return (
        f"Statement: {problem['statement']}\n"
        f"Helpful definitions: {problem.get('definitions', 'none given')}\n\n"
        "Prove this statement."
    )


# --- Patterns ------------------------------------------------------------------

def single(problem: dict, prover: Agent) -> str:
    """Baseline: one model, one attempt."""
    return prover.ask(_problem_prompt(problem))


def verify(problem: dict, prover: Agent, critics: list[Agent], rounds: int = 2) -> str:
    """Prover derives; critics push back; prover revises. Repeat `rounds` times."""
    prover.reset()
    proof = prover.ask(_problem_prompt(problem), remember=True)
    print(f"\n[{prover.name}] initial proof:\n{proof}\n")

    for r in range(rounds):
        feedback = []
        all_correct = True
        for critic in critics:
            verdict = critic.ask(
                f"Statement: {problem['statement']}\n\nProof to check:\n{proof}"
            )
            print(f"[{critic.name}] round {r + 1}:\n{verdict}\n")
            feedback.append(f"{critic.name} says:\n{verdict}")
            if "VERDICT: CORRECT" not in verdict.upper():
                all_correct = False

        if all_correct:
            print("All critics satisfied — stopping early.")
            break

        proof = prover.ask(
            "Critics reviewed your proof:\n\n"
            + "\n\n".join(feedback)
            + "\n\nRevise your proof to address every point. Keep it clear.",
            remember=True,
        )
        print(f"[{prover.name}] revision {r + 1}:\n{proof}\n")

    return proof


def debate(problem: dict, prover_a: Agent, prover_b: Agent, judge: Agent) -> str:
    """Two provers each attempt the proof; a judge picks the sounder one."""
    proof_a = prover_a.ask(_problem_prompt(problem))
    proof_b = prover_b.ask(_problem_prompt(problem))
    print(f"\n[{prover_a.name}] proof A:\n{proof_a}\n")
    print(f"[{prover_b.name}] proof B:\n{proof_b}\n")

    ruling = judge.ask(
        f"Statement: {problem['statement']}\n\n"
        f"=== Proof A ===\n{proof_a}\n\n=== Proof B ===\n{proof_b}"
    )
    print(f"[{judge.name}] ruling:\n{ruling}\n")

    winner = ruling.upper()
    if "WINNER: A" in winner:
        return proof_a
    if "WINNER: B" in winner:
        return proof_b
    return "Judge found neither proof adequate.\n\n" + ruling


def _extract_answer(text: str) -> str:
    match = re.search(r"ANSWER:\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else text.strip().lower()[:80]


def vote(problem: dict, prover: Agent, samples: int = 5) -> str:
    """Self-consistency: sample many times, majority-vote the final answer."""
    prover.temperature = max(prover.temperature, 0.8)  # need diversity
    answers = []
    proofs = []
    for i in range(samples):
        proof = single(problem, prover)
        proofs.append(proof)
        ans = _extract_answer(proof)
        answers.append(ans)
        print(f"sample {i + 1} answer: {ans}")

    winner, count = Counter(answers).most_common(1)[0]
    print(f"\nMajority answer ({count}/{samples}): {winner}")
    # Return the first proof that produced the winning answer.
    for proof, ans in zip(proofs, answers):
        if ans == winner:
            return proof
    return proofs[0]
