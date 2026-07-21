# CLAUDE.md - proof-swarm conventions

Guidance for any agent (human or AI) working in this repo.

## What this project is

An experiment in making several small, locally-run LLMs - each playing a
different **role** (prover / critic / judge) - derive and check simple math
proofs, and whether multi-agent setups reason better than one model alone. It is
a learning sandbox: prize **readable, explicit** code over cleverness or
frameworks. Every prompt sent to a model should be plain and inspectable.

## Process & ports - ataegina is the ONLY allowed mechanism

**Any process this project starts that listens on a port or needs tracking MUST
be brought up through [ataegina](https://github.com/noahhyden/ataegina-cli.)**
ataegina gives each git worktree a stable index `N` and derives non-colliding
ports (`5173+N` frontend, `8000+N` backend) plus a per-worktree database and
tracked process list, so parallel agents/branches never collide.

Hard rules:

- **Never hardcode a port** (no `--port 8000`, no `PORT=5173`). Reference
  `$FRONTEND_PORT` / `$BACKEND_PORT` / `$BACKEND_URL`, which ataegina exports.
- **Never launch a project server directly** - no `uvicorn ...`, `flask run`,
  `python -m http.server`, `npm run dev`, or `<server> &`. Instead declare the
  command in `ataegina.config.sh` (`FRONTEND_CMD` / `BACKEND_CMD`) and start it
  with `ataegina up`; stop it with `ataegina down`.
- **Check health with `ataegina doctor`** before assuming a port is free.
- If you add per-agent model servers (e.g. one Ollama instance per role on its
  own port), each one is a tracked process and goes through ataegina - do not
  spawn them by hand.

**Exception - external shared daemons.** The Ollama server (fixed port `11434`,
installed as a system service) is an external dependency this repo consumes, not
a process the repo owns, so it is out of ataegina's scope. Everything the repo
*itself* brings up is in scope.

## Python

- Environment and dependencies are managed with **uv**. Use `uv sync` to set up,
  `uv run <cmd>` to run. Do not use bare `pip` or stdlib `venv`.
- Dependencies live in `pyproject.toml`, not loose `pip install` calls.

## Experiments are data - keep them reproducible

- Every run writes a JSON record to `runs/` (gitignored). Do not remove or
  silently change the record schema; bump `schema_version` in `src/config.py`
  if the shape changes, so old records stay interpretable.
- Each problem in `problems/problems.json` carries a ground-truth `answer`.
  Keep it; the scorer (`src/scoring.py`) needs it to say whether a run was
  correct. A problem without a known answer cannot be scored - add one.

### Seeding and determinism (borrowed from von-neumann CLAUDE.md sec 7)

The sibling repo `noahhyden/von-neumann` treats this as the one discipline that
silently breaks everything downstream if ignored, and the same rules apply here:

- **Seed is explicit state, threaded, never ambient.** A single fixed `SEED`
  lives in `src/config.py`; every `Agent` carries it and passes it into the
  model call. Never seed from a wall clock, and never call an unseeded RNG in
  the reasoning path. Derive per-sample seeds from the base (`base_seed + i` in
  `vote`), not from a mutated field, so a whole experiment replays from one
  number.
- **Iteration order is deterministic.** Use ordered containers (lists, dicts),
  not sets, anywhere the order affects output. Sets are fine only for pure
  membership checks (e.g. "is this model pulled?").
- **No wall-clock value ever feeds a result.** Timestamps may name a run file;
  they must not change what a run produces.
- **Honest caveat - LLM inference is only best-effort deterministic.** Unlike
  von-neumann's pure numeric fold (bit-exact mulberry32), an LLM with a fixed
  seed reproduces only against the *same model build, quantization, and Ollama
  version*. Record those in each run (we capture `models` + `seed`) so a
  divergence is diagnosable rather than mysterious. Do not claim bit-exactness.

## Tests

- `tests/` holds **model-free** logic tests that run without Ollama. Keep them
  fast and offline; they run in CI. Anything needing a live model is a manual
  experiment, not a unit test.
