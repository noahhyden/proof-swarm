# Spec: Lean 4 formal oracle (golden, bit-exact)

Status: IMPLEMENTED (phase 1). Parity problems formalized and proven; oracle
built tests-first with 100% coverage; live + mutation verified via
`make oracle-verify`. Decisions below resolved: **Mathlib from the start**
(pinned Lean v4.32.0 + Mathlib rev in `formal/lake-manifest.json`).
Remaining: sqrt2 / sum_first_n formalization, triangle_angle_sum (may drop),
and wiring a `--mode lean` into `run.py`.

## Motivation

Our current scorer (`src/scoring.py`) matches tokens against a ground-truth
string. The baseline exposed its weakness: `qwen2.5:3b` scored "4/6", but at
least two "failures" were the scorer missing an answer the model never labeled
with `ANSWER:`, not wrong mathematics. A substring check is not an oracle.

A proof-assistant kernel *is* an oracle: if a proof typechecks in Lean 4, it is
correct - deterministically, with no judgment call. This matches the repo's
determinism discipline (the kernel is trusted and reproducible) and gives a
correctness signal we can actually build on.

## Goal

Provide `check(problem_id, lean_proof) -> Verdict` where the Lean 4 kernel
decides whether `lean_proof` proves the formalized statement for `problem_id`.
`Verdict` records `ok: bool`, the kernel's `output`, and the pinned
`lean_version` + `mathlib_rev` so any result is reproducible and diagnosable.

## Scope

**Covers:**
- A `formal/` Lean project with one **formalized theorem statement per problem**
  (human-written and reviewed - we control formalization so it is trustworthy).
- An oracle module (`src/lean_oracle.py`) that splices a candidate proof into
  the statement, invokes Lean via `lake`, and parses pass/fail from the kernel.
- A new run path where the model is asked to emit a **Lean 4 tactic proof**, and
  the oracle - not the token scorer - decides correctness.
- Pinned toolchain (`lean-toolchain`) and Mathlib revision (`lake-manifest.json`)
  captured in every run record.

**Does NOT cover (explicit non-goals for this phase):**
- **Autoformalization** (NL -> Lean). The literature puts SoTA NL->Lean at ~66%
  reliability; making the formalizer part of the oracle would poison the signal.
  We formalize statements by hand and review them. Models prove; they do not
  formalize (yet).
- Grading natural-language prose proofs (that is the separate OPC-R1-8B judge
  tier, deferred).
- Generating proofs automatically / any prover training.

## Interface

```python
# src/lean_oracle.py
@dataclass
class Verdict:
    ok: bool
    output: str          # kernel stdout/stderr, trimmed
    lean_version: str
    mathlib_rev: str

def check(problem_id: str, lean_proof: str, timeout_s: int = 60) -> Verdict: ...
```

- Statements live in `formal/ProofSwarm/<Problem>.lean` as
  `theorem <id> : <statement> := by <PROOF_HOLE>`.
- `check` substitutes `lean_proof` for `<PROOF_HOLE>`, runs `lake env lean` on a
  temp file, and returns `ok=True` iff Lean exits 0 with no `sorry`/errors.
- A proof containing `sorry` or `admit` is `ok=False` (no cheating the kernel).

## Formalization plan (initial problems)

Most of our set is provable with Mathlib in a few lines:
- `even_plus_even`, `even_plus_odd`, `product_of_odds` -> `Even`/`Odd` +
  `parity_simps` / `omega` / `decide`.
- `sqrt2_irrational` -> Mathlib already has `irrational_sqrt_two`; the exercise
  becomes proving the statement using it.
- `sum_first_n` -> `Finset.sum_range_id_mul_two` / induction.
- `triangle_angle_sum` -> geometry; likely deferred (Mathlib support is heavier).

Each formalized statement gets a human-reviewed **reference proof** committed
alongside it, which doubles as the oracle's own self-test (below).

## Determinism

- Pin `lean-toolchain` to an exact Lean version and Mathlib to an exact git rev
  in `lake-manifest.json`. The kernel is deterministic; pinning makes the whole
  oracle reproducible across machines (unlike the LLM itself).
- Record `lean_version` + `mathlib_rev` in every run JSON (bump
  `schema_version`).

## How we verify it (discipline stages 2-4)

- **tests-first (offline, mocked Lean):** proof-splicing, `sorry`/`admit`
  rejection, timeout handling, output parsing - all unit-tested with a fake
  `lake` runner. Target 100% coverage on `lean_oracle` logic; the real
  subprocess call is the one `# pragma: no cover` seam.
- **live verification:** the committed reference proof of each formalized
  problem must return `ok=True`; running the real kernel end to end.
- **mutation red-teaming:** for each problem, a **broken** proof (e.g. reference
  proof with a wrong step, or `sorry`) must return `ok=False`. An oracle that
  passes a broken proof is worse than useless. This is the formal analogue of
  the in-product `planted` mode.

## Tooling & setup cost (honest)

- No Lean toolchain is installed here. Setup: `elan` (Lean version manager) ->
  Lean 4 -> a `lake` project depending on Mathlib.
- **Mathlib is large:** first build/download of the Mathlib cache is on the
  order of GBs and can take a while even with `lake exe cache get` (prebuilt
  olean cache). This is a one-time cost; document it in README setup.
- CI implication: the offline oracle tests (mocked) run in normal CI; the
  live/mutation Lean checks need a job with the toolchain + Mathlib cache
  (slower, separate workflow or manual `make oracle-verify`).

## Risks / open questions

- **[RISK] Models rarely emit valid Lean without training.** Early pass rates
  on real Lean proofs from a 3B model may be ~0. That is a *finding*, not a
  failure - it cleanly separates "can reason" from "can reason in Lean," and
  motivates the NL-judge tier. We measure it honestly.
- **[GAP] triangle_angle_sum** may not be cheaply formalizable; may drop from
  the formal core initially.
- **[DECISION] one Lean file vs Mathlib dependency** - do we accept the heavy
  Mathlib build now, or start with a Mathlib-free project (only Lean core:
  `omega`, `decide`) that can do the parity problems but not sqrt2/sum? See
  question below.

## Proposed phased plan

1. This spec approved.
2. `formal/` Lean project + 3 parity statements with reference proofs (decide
   Mathlib vs core first).
3. `src/lean_oracle.py` + offline mocked tests (tests-first), 100% cov.
4. Live: reference proofs pass; mutation: broken proofs fail.
5. Wire a `--mode lean` (or oracle flag) into `run.py`; record versions.
6. README/CLAUDE.md docs. Push. Then expand problem coverage.
