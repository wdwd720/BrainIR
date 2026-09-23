"""The frozen benchmark must still be the frozen benchmark: BENCHMARK_LOCK.json vs the tree."""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from brainir import paths

FREEZE = paths.repo_root() / "benchmarks" / "dng100" / "freeze.py"
LOCK = FREEZE.parent / "BENCHMARK_LOCK.json"


def _load():
    spec = importlib.util.spec_from_file_location("dng100_freeze", FREEZE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not LOCK.exists(), reason="benchmark not frozen yet")
def test_tree_matches_benchmark_lock():
    res = _load().check()
    assert res["ok"], {k: v for k, v in res.items() if v and k != "ok"}


@pytest.mark.skipif(not LOCK.exists(), reason="benchmark not frozen yet")
def test_lock_covers_the_normative_artefacts():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    files = lock["files"]
    for must in ("oracle/oracle.json", "oracle/cross_connectome_reference.json", "oracle/tier_a_salt.txt", "evaluator/evaluate.py",
                 "cleanroom/run_method.py", "cleanroom/_sandbox.py", "PROTOCOL.md", "public/manifest.json", "public_blind/manifest.json",
                 "baselines/results/baselines_summary.md", "baselines/results/null_distributions.md"):
        assert must in files, must
    assert any(k.startswith("src/brainir/sim/") for k in lock["code_files"]) and "uv.lock" in lock["code_files"]
    assert set(lock["dataset_manifests_sha256"]) >= {"manc:v1.2.1", "manc:v1.2.3", "male-cns:v1.0"}
    assert lock["bundles"]["public"]["tier"] == "B" and lock["bundles"]["public_blind"]["tier"] == "A"
