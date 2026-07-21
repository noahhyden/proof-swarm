"""The multi-agent reasoning patterns.

Each pattern function takes a `problem` dict (see problems/problems.json) and
returns its final artifact. The point of this file is to be *read*: every
pattern is a short, explicit choreography of who says what to whom.

Output goes through `_say`, which prints a `[Role] label:` header and then the
reply. When an agent streams (the default), the reply is printed live as the
model generates it, so you watch the reasoning happen in real time.
"""

from __future__ import annotations

from collections import Counter

from .llm import Agent
from .scoring import extract_answer

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


def _say(agent: Agent, label: str, message: str, remember: bool = False) -> str:
    """Print a `[Role] label:` header, then the reply (streamed live if enabled)."""
    print(f"\n[{agent.name}] {label}:")
    text = agent.ask(message, remember=remember)
    if not agent.stream:  # if streaming, ask() already echoed the reply
        print(text)
    return text


def _caught_bug(verdict: str) -> bool:
    """A critic 'caught' a flaw if it did not return a clean CORRECT verdict."""
    return "VERDICT: CORRECT" not in verdict.upper()


# --- Patterns ------------------------------------------------------------------

def single(problem: dict, prover: Agent) -> str:
    """Baseline: one model, one attempt."""
    return _say(prover, "proof", _problem_prompt(problem))


def verify(problem: dict, prover: Agent, critics: list[Agent], rounds: int = 2) -> str:
    """Prover derives; critics push back; prover revises. Repeat `rounds` times."""
    prover.reset()
    proof = _say(prover, "initial proof", _problem_prompt(problem), remember=True)

    for r in range(rounds):
        feedback = []
        all_correct = True
        for critic in critics:
            verdict = _say(
                critic,
                f"round {r + 1}",
                f"Statement: {problem['statement']}\n\nProof to check:\n{proof}",
            )
            feedback.append(f"{critic.name} says:\n{verdict}")
            if _caught_bug(verdict):
                all_correct = False

        if all_correct:
            print("\nAll critics satisfied - stopping early.")
            break

        proof = _say(
            prover,
            f"revision {r + 1}",
            "Critics reviewed your proof:\n\n"
            + "\n\n".join(feedback)
            + "\n\nRevise your proof to address every point. Keep it clear.",
            remember=True,
        )

    return proof


def debate(problem: dict, prover_a: Agent, prover_b: Agent, judge: Agent) -> str:
    """Two provers each attempt the proof; a judge picks the sounder one."""
    proof_a = _say(prover_a, "proof A", _problem_prompt(problem))
    proof_b = _say(prover_b, "proof B", _problem_prompt(problem))

    ruling = _say(
        judge,
        "ruling",
        f"Statement: {problem['statement']}\n\n"
        f"=== Proof A ===\n{proof_a}\n\n=== Proof B ===\n{proof_b}",
    )

    winner = ruling.upper()
    if "WINNER: A" in winner:
        return proof_a
    if "WINNER: B" in winner:
        return proof_b
    return "Judge found neither proof adequate.\n\n" + ruling


def vote(problem: dict, prover: Agent, samples: int = 5) -> str:
    """Self-consistency: sample many times, majority-vote the final answer."""
    prover.temperature = max(prover.temperature, 0.8)  # need diversity
    base_seed = prover.seed
    answers, proofs = [], []
    for i in range(samples):
        # Derive each sample's seed from the base (base_seed + i), never from
        # the mutated field, so the whole vote is reproducible from one seed.
        prover.seed = base_seed + i
        proof = _say(prover, f"sample {i + 1}", _problem_prompt(problem))
        proofs.append(proof)
        answers.append(extract_answer(proof).lower())

    winner, count = Counter(answers).most_common(1)[0]
    print(f"\nMajority answer ({count}/{samples}): {winner}")
    for proof, ans in zip(proofs, answers):
        if ans == winner:
            return proof
    return proofs[0]


def planted(problem: dict, critic: Agent, samples: int = 5) -> dict:
    """Feed the critic a known-flawed proof and measure how often it catches it.

    This is the real test of whether a critic verifies or just rubber-stamps:
    the proof has a deliberate error (`problem['flawed_proof']` / `['bug']`), so
    the *correct* behavior is VERDICT: NEEDS WORK. We run the critic `samples`
    times with varied seeds and report the catch rate. Auto-detection only sees
    the verdict; read the transcript to confirm it caught THIS bug, not just
    nitpicked style.
    """
    flawed = problem["flawed_proof"]
    bug = problem["bug"]
    print(f"\n[planted bug] {bug}")
    print(f"\n[flawed proof under review]\n{flawed}")

    base_seed = critic.seed
    caught = 0
    for i in range(samples):
        critic.seed = base_seed + i
        verdict = _say(
            critic,
            f"review {i + 1}",
            f"Statement: {problem['statement']}\n\nProof to check:\n{flawed}",
        )
        if _caught_bug(verdict):
            caught += 1

    rate = caught / samples if samples else 0.0
    print(f"\nCatch rate: {caught}/{samples} ({rate:.0%}) flagged the flawed proof.")
    return {
        "bug": bug,
        "samples": samples,
        "caught": caught,
        "catch_rate": rate,
        "flawed_proof": flawed,
    }
