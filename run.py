#!/usr/bin/env python3
"""proof-swarm CLI.

Run several small local models as different roles and make them derive (and
check) simple proofs. Output streams live by default, so you watch each model
reason in real time; pass --no-stream to buffer instead.

Examples:
    uv run python run.py --list
    uv run python run.py --problem even_plus_even --mode single
    uv run python run.py --problem even_plus_odd  --mode verify --rounds 2
    uv run python run.py --problem sqrt2_irrational --mode debate
    uv run python run.py --problem even_plus_even --mode vote --samples 5
    uv run python run.py --problem even_plus_odd  --mode planted --samples 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from proofswarm import config
from proofswarm import orchestrator as orch
from proofswarm.llm import Agent, available_models
from proofswarm.scoring import score

ROOT = Path(__file__).parent
PROBLEMS_PATH = ROOT / "problems" / "problems.json"
RUNS_DIR = ROOT / "runs"


def load_problems() -> dict:
    return json.loads(PROBLEMS_PATH.read_text())


def build_scored(problem: dict, result) -> dict | None:
    """Turn a run's result into a comparable score record.

    Two shapes: `planted` returns a dict of catch-rate metrics; every other
    mode returns proof text scored against the problem's ground-truth answer.
    """
    if isinstance(result, dict):  # planted mode
        return {
            "metric": "catch_rate",
            "catch_rate": result["catch_rate"],
            "caught": result["caught"],
            "samples": result["samples"],
            "correct": result["catch_rate"] >= 0.5,
        }
    if "answer" in problem:
        return score(result, problem["answer"])
    return None


def save_run(problem_key: str, problem: dict, args, result, scored, elapsed: float) -> Path:
    """Write a run to runs/ so experiments are comparable and reproducible."""
    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
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
    return path


def build_agents(stream: bool = True):
    m, t, s = config.MODELS, config.TEMPERATURES, config.SEED
    # Each role gets its own seed so same-model agents don't produce identical
    # token streams; the whole set is still reproducible from config.SEED.
    prover = Agent("Prover", m["prover"], orch.PROVER_SYSTEM, t["prover"], seed=s, stream=stream)
    critic = Agent("Critic", m["critic"], orch.CRITIC_SYSTEM, t["critic"], seed=s + 1, stream=stream)
    prover_b = Agent("Prover-B", m["critic"], orch.PROVER_SYSTEM, t["prover_b"], seed=s + 2, stream=stream)
    judge = Agent("Judge", m["judge"], orch.JUDGE_SYSTEM, t["judge"], seed=s + 3, stream=stream)
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
        choices=["single", "verify", "debate", "vote", "planted"],
        default="verify",
    )
    ap.add_argument("--rounds", type=int, default=2, help="verify: revision rounds")
    ap.add_argument("--samples", type=int, default=5, help="vote/planted: samples")
    ap.add_argument("--no-stream", action="store_true", help="buffer output instead of streaming live")
    ap.add_argument("--list", action="store_true", help="list problems and exit")
    args = ap.parse_args()

    problems = load_problems()

    if args.list or not args.problem:
        print("Available problems:\n")
        for key, p in problems.items():
            tags = " [planted]" if "flawed_proof" in p else ""
            print(f"  {key}{tags}\n    {p['statement']}\n    ({p['note']})\n")
        return

    if args.problem not in problems:
        sys.exit(f"Unknown problem '{args.problem}'. Use --list to see options.")

    problem = problems[args.problem]
    if args.mode == "planted" and "flawed_proof" not in problem:
        haves = [k for k, p in problems.items() if "flawed_proof" in p]
        sys.exit(f"'{args.problem}' has no planted bug. Try one of: {', '.join(haves)}")

    check_models_present()
    stream = not args.no_stream
    prover, critic, prover_b, judge = build_agents(stream=stream)

    print(f"=== {args.problem} | mode={args.mode} ===")
    print(f"Statement: {problem['statement']}")

    start = time.monotonic()
    if args.mode == "single":
        result = orch.single(problem, prover)
    elif args.mode == "verify":
        result = orch.verify(problem, prover, [critic], rounds=args.rounds)
    elif args.mode == "debate":
        result = orch.debate(problem, prover, prover_b, judge)
    elif args.mode == "vote":
        result = orch.vote(problem, prover, samples=args.samples)
    else:  # planted
        result = orch.planted(problem, critic, samples=args.samples)
    elapsed = time.monotonic() - start

    scored = build_scored(problem, result)

    # When streaming, the full text already scrolled by; don't reprint it.
    if not stream and isinstance(result, str):
        print("\n===================== FINAL =====================\n")
        print(result)

    if scored is not None:
        if scored.get("metric") == "catch_rate":
            print(f"\n[catch rate: {scored['caught']}/{scored['samples']} "
                  f"({scored['catch_rate']:.0%})  -> {'CAUGHT' if scored['correct'] else 'MISSED'}]")
        else:
            mark = "CORRECT" if scored["correct"] else "INCORRECT"
            print(f"\n[score: {mark}  expected '{scored['expected']}', got '{scored['got']}']")

    saved = save_run(args.problem, problem, args, result, scored, elapsed)
    print(f"[saved run to {saved.relative_to(ROOT)}  ({elapsed:.0f}s)]")


if __name__ == "__main__":
    main()
