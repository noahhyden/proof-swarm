#!/usr/bin/env python3
"""proof-swarm CLI.

Run several small local models as different roles and make them derive (and
check) simple proofs.

Examples:
    uv run python run.py --list
    uv run python run.py --problem even_plus_even --mode single
    uv run python run.py --problem even_plus_odd  --mode verify --rounds 2
    uv run python run.py --problem sqrt2_irrational --mode debate
    uv run python run.py --problem even_plus_even --mode vote --samples 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src import orchestrator as orch
from src.llm import Agent, available_models
from src.scoring import score

ROOT = Path(__file__).parent
PROBLEMS_PATH = ROOT / "problems" / "problems.json"
RUNS_DIR = ROOT / "runs"


def load_problems() -> dict:
    return json.loads(PROBLEMS_PATH.read_text())


def save_run(problem_key: str, problem: dict, args, result: str, elapsed: float):
    """Write a run to runs/; return (path, scored_dict_or_None)."""
    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    scored = score(result, problem["answer"]) if "answer" in problem else None
    path = RUNS_DIR / f"{stamp}_{problem_key}_{args.mode}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": config.SCHEMA_VERSION,
                "problem": problem_key,
                "statement": problem["statement"],
                "mode": args.mode,
                "rounds": args.rounds,
                "samples": args.samples,
                "seed": config.SEED,
                "models": config.MODELS,
                "timestamp_utc": stamp,
                "elapsed_seconds": round(elapsed, 1),
                "scored": scored,
                "result": result,
            },
            indent=2,
        )
    )
    return path, scored


def build_agents():
    m, t = config.MODELS, config.TEMPERATURES
    prover = Agent("Prover", m["prover"], orch.PROVER_SYSTEM, temperature=t["prover"])
    critic = Agent("Critic", m["critic"], orch.CRITIC_SYSTEM, temperature=t["critic"])
    prover_b = Agent("Prover-B", m["critic"], orch.PROVER_SYSTEM, temperature=t["prover_b"])
    judge = Agent("Judge", m["judge"], orch.JUDGE_SYSTEM, temperature=t["judge"])
    return prover, critic, prover_b, judge


def check_models_present() -> None:
    have = set(available_models())
    if not have:
        sys.exit(
            "Could not reach Ollama. Is it installed and running?\n"
            "  Install: curl -fsSL https://ollama.com/install.sh | sh\n"
            "  Then:    ollama serve  (usually starts automatically)"
        )
    needed = set(config.MODELS.values())
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

    start = time.monotonic()
    if args.mode == "single":
        result = orch.single(problem, prover)
    elif args.mode == "verify":
        result = orch.verify(problem, prover, [critic], rounds=args.rounds)
    elif args.mode == "debate":
        result = orch.debate(problem, prover, prover_b, judge)
    else:  # vote
        result = orch.vote(problem, prover, samples=args.samples)
    elapsed = time.monotonic() - start

    print("\n===================== FINAL =====================\n")
    print(result)

    saved, scored = save_run(args.problem, problem, args, result, elapsed)
    if scored is not None:
        mark = "CORRECT" if scored["correct"] else "INCORRECT"
        print(f"\n[score: {mark}  expected '{scored['expected']}', got '{scored['got']}']")
    print(f"[saved run to {saved.relative_to(ROOT)}  ({elapsed:.0f}s)]")


if __name__ == "__main__":
    main()
