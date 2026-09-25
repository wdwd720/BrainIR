"""The Phase 3 benchmark and method locks (goal4 sections 71 "METHOD LOCK", 57, 86): hashed files must not change after freezing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BENCH_LOCK = ROOT / "benchmarks" / "state_discovery_v1" / "BENCHMARK_LOCK.json"
METHOD_LOCK = ROOT / "research" / "phase3" / "METHOD_LOCK.json"


@pytest.mark.skipif(not BENCH_LOCK.exists(), reason="benchmark not frozen yet")
def test_benchmark_lock_is_intact():
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "p3" / "freeze_benchmark.py"), "--check"], capture_output=True, text=True,
                       timeout=600)
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-2000:]


@pytest.mark.skipif(not BENCH_LOCK.exists(), reason="benchmark not frozen yet")
def test_the_lock_is_benchmark_version_3():
    import json
    lock = json.loads(BENCH_LOCK.read_text(encoding="utf-8"))
    assert lock.get("benchmark_version") == 3 and lock["git_tag"] == "state-discovery-benchmark-v3"
    assert lock["supersedes"]["git_tag"] == "state-discovery-benchmark-v2"
    assert lock["tolerances"].get("tau_H") is not None and "tau_gap" in lock["tolerances"]


@pytest.mark.skipif(not METHOD_LOCK.exists(), reason="method not locked yet")
def test_method_lock_is_intact():
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "p3" / "method_lock_p3.py"), "--check"], capture_output=True, text=True,
                       timeout=600)
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-2000:]
