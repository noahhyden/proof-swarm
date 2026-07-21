#!/usr/bin/env python3
"""Establish a baseline: one model, one attempt, every problem.

This is the control we measure everything else against. Before asking whether
`verify`/`debate`/`vote` help, we need to know how the raw model does alone.
Uses the single configured model (config.MODELS) in `single` mode, scores each
result against ground truth, and prints a summary table. Each attempt is also
saved to runs/ like any other run.

    uv run python baseline.py            # all problems
    uv run python baseline.py --stream   # watch each derivation live
"""

from __future__ import annotations

import argparse
import time
from types import SimpleNamespace

from proofswarm import config
from proofswarm import orchestrator as orch
from proofswarm.llm import Agent

from run import build_scored, check_models_present, load_problems, save_run


def main() -> None:
    ap = argparse.ArgumentParser(description="Single-model baseline over all problems.")
    ap.add_argument("--stream", action="store_true", help="stream each derivation live")
    args = ap.parse_args()

    check_models_present()
    problems = load_problems()
    model = config.MODELS["prover"]
    print(f"Baseline: model={model}  seed={config.SEED}  mode=single\n")

    rows = []
    for key, problem in problems.items():
        # Fresh agent per problem so nothing carries over between them.
        prover = Agent("Prover", model, orch.PROVER_SYSTEM,
                       config.TEMPERATURES["prover"], seed=config.SEED, stream=args.stream)
        start = time.monotonic()
        result = orch.single(problem, prover)
        elapsed = time.monotonic() - start

        scored = build_scored(problem, result)
        run_args = SimpleNamespace(mode="single", rounds=0, samples=0)
        save_run(key, problem, run_args, result, scored, elapsed)

        correct = scored["correct"] if scored else None
        rows.append((key, correct, elapsed, scored["got"] if scored else ""))

    # Summary table.
    print("\n=================== BASELINE SUMMARY ===================")
    print(f"{'problem':<20} {'result':<9} {'sec':>5}  answer")
    print("-" * 70)
    n_correct = 0
    for key, correct, elapsed, got in rows:
        mark = "n/a" if correct is None else ("CORRECT" if correct else "INCORRECT")
        n_correct += 1 if correct else 0
        got_short = got.replace("\n", " ")[:32]
        print(f"{key:<20} {mark:<9} {elapsed:>5.0f}  {got_short}")
    scoreable = sum(1 for _, c, _, _ in rows if c is not None)
    print("-" * 70)
    print(f"score: {n_correct}/{scoreable} correct   ({model})")


if __name__ == "__main__":
    main()
