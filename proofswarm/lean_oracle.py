"""Lean 4 formal oracle: the proof-assistant kernel decides correctness.

A candidate Lean proof is spliced into the formalized statement for a problem,
compiled with `lake env lean`, and accepted iff the kernel exits cleanly with no
`sorry`. This is a golden oracle - deterministic and trustworthy - unlike the
token scorer it complements. See docs/lean-oracle-spec.md.

The subprocess call is injected as `runner` so the decision logic is fully
testable offline; the real runner (`_run_lean`) is the one uncovered seam.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

FORMAL_DIR = Path(__file__).resolve().parent.parent / "formal"

# Formalized statement signatures (the part before ':='). The oracle splices a
# candidate proof after the ':='. Each must have a reference proof in
# formal/ProofSwarm/Parity.lean, kept in sync by the live/mutation tests.
LEAN_STATEMENTS: dict[str, str] = {
    "even_plus_even": "theorem candidate (a b : ℤ) (ha : Even a) (hb : Even b) : Even (a + b)",
    "even_plus_odd": "theorem candidate (a b : ℤ) (ha : Even a) (hb : Odd b) : Odd (a + b)",
    "product_of_odds": "theorem candidate (a b : ℤ) (ha : Odd a) (hb : Odd b) : Odd (a * b)",
}

Runner = Callable[[str, int], "tuple[int, str]"]


@dataclass
class Verdict:
    ok: bool
    output: str
    lean_version: str
    mathlib_rev: str


def _uses_sorry(proof: str) -> bool:
    """True if the proof tries to cheat the kernel with `sorry`/`admit`."""
    return re.search(r"\b(sorry|admit)\b", proof) is not None


def _build_source(problem_id: str, proof: str) -> str:
    """The temp Lean file: import Mathlib, then the statement with the proof."""
    signature = LEAN_STATEMENTS[problem_id]
    return (
        "import Mathlib\n"
        "namespace ProofSwarmCheck\n"
        f"{signature} := {proof}\n"
        "end ProofSwarmCheck\n"
    )


def lean_version() -> str:
    path = FORMAL_DIR / "lean-toolchain"
    return path.read_text().strip() if path.exists() else "unknown"


def _parse_mathlib_rev(manifest: dict) -> str:
    for pkg in manifest.get("packages", []):
        if pkg.get("name") == "mathlib":
            return pkg.get("rev", "unknown")
    return "unknown"


def mathlib_rev() -> str:
    path = FORMAL_DIR / "lake-manifest.json"
    if not path.exists():
        return "unknown"
    return _parse_mathlib_rev(json.loads(path.read_text()))


def _run_lean(source: str, timeout_s: int) -> tuple[int, str]:  # pragma: no cover
    """Compile `source` with `lake env lean`, return (returncode, output).

    Runs inside FORMAL_DIR so `import Mathlib` resolves against the built
    project. This is the real-subprocess seam; logic is tested via injection.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".lean", dir=FORMAL_DIR, delete=True
    ) as fh:
        fh.write(source)
        fh.flush()
        try:
            proc = subprocess.run(
                ["lake", "env", "lean", fh.name],
                cwd=FORMAL_DIR,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            # check() expects the runner to raise TimeoutError on timeout.
            raise TimeoutError(str(exc)) from exc
    return proc.returncode, (proc.stdout + proc.stderr)


def check(
    problem_id: str,
    lean_proof: str,
    timeout_s: int = 60,
    runner: Runner | None = None,
) -> Verdict:
    """Ask the Lean kernel whether `lean_proof` proves `problem_id`."""
    if problem_id not in LEAN_STATEMENTS:
        raise KeyError(f"no formalized statement for '{problem_id}'")

    meta = (lean_version(), mathlib_rev())

    if _uses_sorry(lean_proof):
        return Verdict(False, "rejected: proof uses sorry/admit", *meta)

    run = runner or _run_lean
    source = _build_source(problem_id, lean_proof)
    try:
        returncode, output = run(source, timeout_s)
    except TimeoutError:
        return Verdict(False, f"timeout after {timeout_s}s", *meta)

    lowered = output.lower()
    ok = returncode == 0 and "sorry" not in lowered and "error" not in lowered
    return Verdict(ok, output.strip(), *meta)
