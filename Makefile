.PHONY: test cov mutation lean-build oracle-verify

# Offline (no Lean toolchain needed) - these run in CI.
test:
	uv run pytest -q

cov:
	uv run pytest --cov

mutation:
	uv run mutmut run

# Require the Lean toolchain + a built formal/ project (see README). Manual gates.
lean-build:
	cd formal && PATH="$$HOME/.elan/bin:$$PATH" lake build ProofSwarm

oracle-verify:
	PATH="$$HOME/.elan/bin:$$PATH" uv run python scripts/oracle_verify.py
