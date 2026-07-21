# proof-swarm

An experiment: can several small, locally-run language models - working together
as different **roles** rather than one big model - be pushed to *derive* simple
mathematical proofs step by step, and check each other's reasoning?

This repo is a learning sandbox. It is deliberately small and readable. There is
**no framework magic** - every prompt and every message sent to a model is plain
Python you can read and change.

## The idea

The classic textbook proofs (sum of two evens, √2 is irrational, triangle angle
sum) live inside every model's training data, so a model reciting them proves
nothing about *reasoning*. The interesting questions are:

1. Can a small model **derive** a proof on a *novel or perturbed* problem, where
   memorization doesn't help?
2. Do **multiple instances in different roles** reason better than one alone?

We explore three multi-agent patterns:

| Mode | What happens |
|------|--------------|
| `single` | One model attempts the proof. Baseline. |
| `verify` | A **Prover** derives; one or more **Critics** check each step and push back; the Prover revises. |
| `debate` | Two Provers argue for their approach; a **Judge** picks the sounder derivation. |
| `vote` | Sample the same problem N times, majority-vote the final answer (self-consistency). |

## Hardware note

Built and tested on a CPU-only machine (16 cores, 27 GB RAM, no CUDA). Small
models (1-3B, 4-bit) run fine here. If you have an NVIDIA/ROCm GPU, Ollama will
use it automatically.

## Setup

```bash
# 1. Install Ollama (one-time; needs your confirmation for sudo)
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the small models we use as different "agents"
ollama pull qwen2.5:3b
ollama pull llama3.2:3b
ollama pull gemma2:2b

# 3. Python deps (via uv - https://github.com/astral-sh/uv)
uv sync

# 4. Run a proof attempt
uv run python run.py --problem even_plus_even --mode verify
```

## Usage

```bash
# List built-in problems
uv run python run.py --list

# Baseline: one model
uv run python run.py --problem even_plus_even --mode single

# Prover + Critic loop (the interesting one)
uv run python run.py --problem even_plus_odd --mode verify --rounds 2

# Two provers debate, a judge decides
uv run python run.py --problem sqrt2_irrational --mode debate

# Self-consistency vote
uv run python run.py --problem even_plus_even --mode vote --samples 5
```

Add your own problems in `problems/problems.json`. The perturbed ones (e.g.
`even_plus_odd`) are where memorization stops helping - that's the real test.

## Formal oracle (Lean 4) - the golden tier

The token scorer (`src/scoring.py`) is cheap but brittle. The real ground truth
is a proof-assistant kernel: if a proof typechecks in **Lean 4**, it is correct,
deterministically. `src/lean_oracle.py` splices a candidate Lean proof into a
formalized statement (`formal/ProofSwarm/`) and asks the kernel. Pinned to Lean
`v4.32.0` + Mathlib (rev in `formal/lake-manifest.json`) for reproducibility.

Setup (one-time; Mathlib's cache is multi-GB):

```bash
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y
export PATH="$HOME/.elan/bin:$PATH"
cd formal && lake exe cache get && lake build ProofSwarm   # downloads Mathlib oleans
```

Then verify the oracle end to end (references accepted, broken/`sorry` rejected):

```bash
make oracle-verify
```

Its decision logic is fully unit-tested offline (a fake kernel runner is
injected), so CI stays fast and green without Lean; the live kernel check is the
manual `make oracle-verify` gate.

## Development

```bash
make test      # fast offline tests
make cov       # tests + 100% coverage gate (enforced in CI)
make mutation  # mutation-test the pure logic
```

See `CLAUDE.md` for the binding dev discipline and conventions.

## Where this can go

The orchestrator talks to models through one small interface (`src/llm.py`), so
Ollama is swappable. The formal oracle covers the parity problems today; next is
extending it (sqrt2 via Mathlib's `irrational_sqrt_two`, induction for
`sum_first_n`) and asking models to emit Lean directly - the path to "reasoning
you can actually trust."
