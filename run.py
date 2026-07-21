#!/usr/bin/env python3
"""proof-swarm CLI.

Run several small local models as different roles and make them derive (and
check) simple proofs.

Examples:
    python run.py --list
    python run.py --problem even_plus_even --mode single
    python run.py --problem even_plus_odd  --mode verify --rounds 2
    python run.py --problem sqrt2_irrational --mode debate
    python run.py --problem even_plus_even --mode vote --samples 5
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src import orchestrator as orch
from src.llm import Agent, available_models

ROOT = Path(__file__).parent
PROBLEMS_PATH = ROOT / "problems" / "problems.json"
RUNS_DIR = ROOT / "runs"

# Which pulled model each role uses. Change these to whatever you `ollama pull`.
# Using different models per role makes "debate" and "verify" more interesting
# than cloning one model, but all-same also works fine.
PROVER_MODEL = "qwen2.5:3b"
CRITIC_MODEL = "llama3.2:3b"
JUDGE_MODEL = "gemma2:2b"


def load_problems() -> dict:
    return json.loads(PROBLEMS_PATH.read_text())


def save_run(problem_key: str, args, result: str) -> Path:
    """Write a run to runs/ so experiments are comparable later."""
    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = RUNS_DIR / f"{stamp}_{problem_key}_{args.mode}.json"
    path.write_text(
        json.dumps(
            {
                "problem": problem_key,
                "mode": args.mode,
                "rounds": args.rounds,
                "samples": args.samples,
                "models": {
                    "prover": PROVER_MODEL,
                    "critic": CRITIC_MODEL,
                    "judge": JUDGE_MODEL,
                },
                "timestamp_utc": stamp,
                "result": result,
            },
            indent=2,
        )
    )
    return path


def build_agents():
    prover = Agent("Prover", PROVER_MODEL, orch.PROVER_SYSTEM, temperature=0.7)
    critic = Agent("Critic", CRITIC_MODEL, orch.CRITIC_SYSTEM, temperature=0.3)
    prover_b = Agent("Prover-B", CRITIC_MODEL, orch.PROVER_SYSTEM, temperature=0.9)
    judge = Agent("Judge", JUDGE_MODEL, orch.JUDGE_SYSTEM, temperature=0.2)
    return prover, critic, prover_b, judge


def check_models_present() -> None:
    have = set(available_models())
    if not have:
        sys.exit(
            "Could not reach Ollama. Is it installed and running?\n"
            "  Install: curl -fsSL https://ollama.com/install.sh | sh\n"
            "  Then:    ollama serve  (usually starts automatically)"
        )
    needed = {PROVER_MODEL, CRITIC_MODEL, JUDGE_MODEL}
    missing = [m for m in needed if m not in have]
    if missing:
        pulls = "\n".join(f"  ollama pull {m}" for m in missing)
        sys.exit(f"Missing models. Pull them first:\n{pulls}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-agent proof derivation.")
    ap.add_argument("--problem", help="problem key (see --list)")
    ap.add_argument(
        "--mode",
        choices=["single", "verify", "debate", "vote"],
        default="verify",
    )
    ap.add_argument("--rounds", type=int, default=2, help="verify: revision rounds")
    ap.add_argument("--samples", type=int, default=5, help="vote: number of samples")
    ap.add_argument("--list", action="store_true", help="list problems and exit")
    args = ap.parse_args()

    problems = load_problems()

    if args.list or not args.problem:
        print("Available problems:\n")
        for key, p in problems.items():
            print(f"  {key}\n    {p['statement']}\n    ({p['note']})\n")
        return

    if args.problem not in problems:
        sys.exit(f"Unknown problem '{args.problem}'. Use --list to see options.")

    check_models_present()
    problem = problems[args.problem]
    prover, critic, prover_b, judge = build_agents()

    print(f"=== {args.problem} | mode={args.mode} ===")
    print(f"Statement: {problem['statement']}\n")

    if args.mode == "single":
        result = orch.single(problem, prover)
    elif args.mode == "verify":
        result = orch.verify(problem, prover, [critic], rounds=args.rounds)
    elif args.mode == "debate":
        result = orch.debate(problem, prover, prover_b, judge)
    else:  # vote
        result = orch.vote(problem, prover, samples=args.samples)

    print("\n===================== FINAL =====================\n")
    print(result)

    saved = save_run(args.problem, args, result)
    print(f"\n[saved run to {saved.relative_to(ROOT)}]")


if __name__ == "__main__":
    main()
