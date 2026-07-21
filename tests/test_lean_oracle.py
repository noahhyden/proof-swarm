"""Tests for the Lean formal oracle - written before the implementation.

These are offline: the real `lake env lean` subprocess is injected as a `runner`
so every branch of the oracle's logic is exercised without a Lean toolchain.
The real runner is the one uncovered seam (marked pragma in the module).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proofswarm import lean_oracle as lo
from proofswarm.lean_oracle import (
    LEAN_STATEMENTS,
    _build_source,
    _parse_mathlib_rev,
    _uses_sorry,
    check,
)


def _ok(_source, _timeout):
    return (0, "")


def _err(_source, _timeout):
    return (1, "error: unknown identifier 'foo'")


def _boom(_source, _timeout):
    raise AssertionError("runner should not be called")


def test_parity_problems_are_registered():
    for key in ("even_plus_even", "even_plus_odd", "product_of_odds"):
        assert key in LEAN_STATEMENTS


def test_uses_sorry_detects_cheats():
    assert _uses_sorry("by sorry")
    assert _uses_sorry("exact admit")
    assert not _uses_sorry("ha.add hb")


def test_sorry_is_rejected_without_running_lean():
    v = check("even_plus_even", "by sorry", runner=_boom)
    assert v.ok is False
    assert "sorry" in v.output.lower()


def test_admit_is_rejected_without_running_lean():
    v = check("even_plus_even", "by admit", runner=_boom)
    assert v.ok is False


def test_accepts_when_kernel_exits_zero():
    v = check("even_plus_even", "ha.add hb", runner=_ok)
    assert v.ok is True


def test_rejects_when_kernel_errors():
    v = check("even_plus_even", "by ring", runner=_err)
    assert v.ok is False
    assert "error" in v.output.lower()


def test_rejects_sorry_warning_in_kernel_output():
    def runner(_s, _t):
        return (0, "warning: declaration uses 'sorry'")

    v = check("even_plus_even", "by exact?", runner=runner)
    assert v.ok is False


def test_rejects_error_in_output_even_when_exit_zero():
    # Some Lean diagnostics report an error without a nonzero exit; the word
    # 'error' in output must still fail. Kills the "error" string mutant.
    def runner(_s, _t):
        return (0, "foo.lean:1:0: error: type mismatch")

    v = check("even_plus_even", "by tauto", runner=runner)
    assert v.ok is False


def test_timeout_is_a_failure_not_a_crash():
    def runner(_s, _t):
        raise TimeoutError

    v = check("even_plus_even", "by tauto", runner=runner)
    assert v.ok is False
    assert "timeout" in v.output.lower()


def test_unknown_problem_raises():
    with pytest.raises(KeyError):
        check("does_not_exist", "trivial", runner=_ok)


def test_build_source_splices_signature_and_proof():
    src = _build_source("even_plus_even", "ha.add hb")
    assert src.startswith("import Mathlib")
    assert "namespace ProofSwarmCheck" in src
    assert "end ProofSwarmCheck" in src
    # signature and proof must be joined by ':=' so Lean sees a real proof term
    assert LEAN_STATEMENTS["even_plus_even"] + " := ha.add hb" in src


def test_parse_mathlib_rev():
    manifest = {"packages": [{"name": "mathlib", "rev": "abc123"}]}
    assert _parse_mathlib_rev(manifest) == "abc123"


def test_parse_mathlib_rev_skips_other_packages():
    manifest = {
        "packages": [
            {"name": "batteries", "rev": "other"},
            {"name": "mathlib", "rev": "the-one"},
        ]
    }
    assert _parse_mathlib_rev(manifest) == "the-one"


def test_parse_mathlib_rev_missing_is_unknown():
    assert _parse_mathlib_rev({"packages": []}) == "unknown"


def test_parse_mathlib_rev_no_packages_key():
    # A manifest with no 'packages' key must not blow up. Kills the default mutant.
    assert _parse_mathlib_rev({}) == "unknown"


def test_mathlib_rev_unknown_when_manifest_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(lo, "FORMAL_DIR", tmp_path)
    assert lo.mathlib_rev() == "unknown"


def test_mathlib_rev_reads_manifest(tmp_path, monkeypatch):
    (tmp_path / "lake-manifest.json").write_text(
        json.dumps({"packages": [{"name": "mathlib", "rev": "deadbeef"}]})
    )
    monkeypatch.setattr(lo, "FORMAL_DIR", tmp_path)
    assert lo.mathlib_rev() == "deadbeef"


def test_lean_version_unknown_when_toolchain_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(lo, "FORMAL_DIR", tmp_path)
    assert lo.lean_version() == "unknown"


def test_lean_version_reads_toolchain(tmp_path, monkeypatch):
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.32.0\n")
    monkeypatch.setattr(lo, "FORMAL_DIR", tmp_path)
    assert "v4.32.0" in lo.lean_version()


def test_verdict_carries_version_metadata():
    v = check("product_of_odds", "ha.mul hb", runner=_ok)
    assert isinstance(v.lean_version, str) and v.lean_version
    assert isinstance(v.mathlib_rev, str) and v.mathlib_rev
