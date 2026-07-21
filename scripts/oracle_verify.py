#!/usr/bin/env python3
"""Live verification + mutation red-team of the Lean oracle.

Requires the Lean toolchain and a built formal/ project (see README). CI cannot
run this (no toolchain), so it is a manual gate: `make oracle-verify`.

- live verification: each reference proof must be ACCEPTED by the real kernel.
- mutation red-team: a broken proof and a `sorry` must be REJECTED. An oracle
  that accepts a broken proof is worse than useless.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proofswarm.lean_oracle import check

# Human-reviewed reference proofs (must match formal/ProofSwarm/Parity.lean).
REFERENCE = {
    "even_plus_even": "ha.add hb",
    "even_plus_odd": "ha.add_odd hb",
    "product_of_odds": "ha.mul hb",
}
# Deliberately broken proofs (must be rejected).
BROKEN = {
    "even_plus_even": "by ring",
    "even_plus_odd": "hb.add_even ha",  # wrong lemma direction / nonexistent here
    "product_of_odds": "ha.add hb",  # add instead of mul: wrong goal
}


def main() -> int:
    failures: list[str] = []

    for pid, proof in REFERENCE.items():
        v = check(pid, proof, timeout_s=120)
        print(f"[live]     {pid:<18} reference -> ok={v.ok}")
        if not v.ok:
            failures.append(f"reference proof for {pid} was REJECTED: {v.output[:120]}")

    for pid, proof in BROKEN.items():
        v = check(pid, proof, timeout_s=120)
        print(f"[mutation] {pid:<18} broken    -> ok={v.ok}")
        if v.ok:
            failures.append(f"oracle ACCEPTED a broken proof for {pid}")

    v = check("even_plus_even", "by sorry", timeout_s=120)
    print(f"[mutation] even_plus_even     sorry     -> ok={v.ok}")
    if v.ok:
        failures.append("oracle ACCEPTED a sorry proof")

    if failures:
        print("\nORACLE VERIFICATION FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOracle verified: references accepted, broken/sorry rejected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
