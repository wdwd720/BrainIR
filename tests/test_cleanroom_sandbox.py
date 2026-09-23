"""The clean-room runner confines a method to the bundle copy: an escape attempt fails, the example method runs.

Uses the committed blind bundle (no dataset needed); the example method does not simulate, so this takes seconds.
"""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from brainir import paths

DNG = paths.repo_root() / "benchmarks" / "dng100"
RUNNER = DNG / "cleanroom" / "run_method.py"
BUNDLE = DNG / "public_blind"

ESCAPE = '''
import os
from pathlib import Path
import brainir.paths as P
p = P.repo_root() / "benchmarks" / "dng100" / "oracle" / "oracle.json"
print(p.read_text(encoding="utf-8")[:10])   # must be refused by the sandbox
'''
SUBPROCESS_ESCAPE = '''
import subprocess, sys
print(subprocess.run([sys.executable, "-c", "print(1)"], capture_output=True))
'''
LEGIT = '''
import os, json
import pandas as pd
b = os.environ["BRAINIR_BUNDLE"]; n = os.environ["BRAINIR_NETWORK"]
df = pd.read_parquet(f"{b}/networks/{n}/neurons.parquet")
json.dump({"n": int(len(df))}, open(os.environ["BRAINIR_OUT"] + ".probe.json", "w"))
'''


def _runner():
    spec = importlib.util.spec_from_file_location("dng100_run_method", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not (BUNDLE / "manifest.json").exists(), reason="blind bundle not present")
@pytest.mark.parametrize("src, expect_ok, needle", [(ESCAPE, False, "clean room"), (SUBPROCESS_ESCAPE, False, "clean room"), (LEGIT, True, "")])
def test_sandbox_confines_methods(tmp_path, src, expect_ok, needle):
    method = tmp_path / "method.py"
    method.write_text(src, encoding="utf-8")
    out = tmp_path / "out"
    rec = _runner().run(method, BUNDLE, out, ["manc_v1.2.1"], seed=0, timeout_s=300)
    run = rec["runs"][0]
    if expect_ok:
        assert run["returncode"] == 0, run["stderr_tail"]
        assert json.loads((out / "prediction_manc_v1.2.1.json.probe.json").read_text())["n"] == 4604
    else:
        assert run["returncode"] != 0 and needle in run["stderr_tail"], run["stderr_tail"]
    assert rec["sandbox"]["sha256"] and rec["bundle"]["tier"] == "A" and "method_args" in rec


@pytest.mark.skipif(not (BUNDLE / "manifest.json").exists(), reason="blind bundle not present")
def test_example_method_runs_and_prediction_validates(tmp_path):
    from brainir.benchmark.prediction import BrainIRMechanismPrediction

    rec = _runner().run(DNG / "cleanroom" / "example_method.py", BUNDLE, tmp_path / "out", ["male-cns_v1.0"], seed=0, timeout_s=300)
    run = rec["runs"][0]
    assert run["returncode"] == 0, run["stderr_tail"]
    pred = BrainIRMechanismPrediction.from_json((tmp_path / "out" / "prediction_male-cns_v1.0.json").read_text(encoding="utf-8"))
    assert pred.digest() == run["prediction_sha256"] and len(pred.core_neurons) == run["n_core"]
