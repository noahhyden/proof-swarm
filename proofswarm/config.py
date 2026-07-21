"""Central configuration - one place to change models, sampling, and backend.

Keeping this here (instead of scattered constants) is the cheap-now move that
saves pain later: swapping models, pointing at a remote Ollama, or changing the
seed is a one-line edit, and every run record captures these values so old
experiments stay interpretable.
"""

from __future__ import annotations

import os

# Bump this whenever the shape of a runs/*.json record changes, so historical
# records remain interpretable.
SCHEMA_VERSION = 1

# Fixed seed for reproducible sampling. `vote` mode deliberately varies it.
SEED = 42

# Where the Ollama server lives. Override with the OLLAMA_HOST env var to point
# at a remote or non-default instance without touching code.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Which pulled model each role uses. We are deliberately using ONE model
# (qwen2.5:3b) for every role right now, to establish a clean baseline before
# introducing the confound of different models per role. Per-role seeds (see
# run.py) still keep the agents from producing identical token streams.
# To go multi-model later, just point these at other pulled models.
_BASELINE_MODEL = "qwen2.5:3b"
MODELS = {
    "prover": _BASELINE_MODEL,
    "critic": _BASELINE_MODEL,
    "judge": _BASELINE_MODEL,
}

# Per-role default sampling temperature.
TEMPERATURES = {
    "prover": 0.7,
    "critic": 0.3,
    "prover_b": 0.9,
    "judge": 0.2,
}
