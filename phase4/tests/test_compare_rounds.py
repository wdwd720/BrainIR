"""The packed / unpacked bit-identity check of the Level B dry run (scripts/p4/compare_rounds.py; research/phase4/LEVEL_B_EXECUTION.md
section 5): timings never count, scientific values always do, dataclass records (stats.Estimate with its bootstrap array) compare by
content, model bytes are reported but do not gate, and the experiment loops gate when both rounds ran them."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import pickle
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def _cr():
    spec = importlib.util.spec_from_file_location("p4_compare_rounds", REPO / "scripts" / "p4" / "compare_rounds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@dataclasses.dataclass
class _Est:
    point: float
    reps: np.ndarray


def _eval(point: float, reps_shift: float = 0.0, wall: float = 1.0) -> dict:
    est = _Est(point, np.arange(5.0) + reps_shift)
    return {"sid": "s", "result": {"mediation": {"SMS": {"point": point, "_wall_s": wall}, "_estimates": {"SMS": est}},
                                   "isolation": {"n_cpu": 48 if wall > 1 else 20}}, "eval_job_wall_s": wall * 10}


def _round(root: Path, name: str, ev: dict, model: bytes, loop_exp: list | None = None) -> Path:
    r = root / name
    (r / "m" / "evals").mkdir(parents=True)
    (r / "m" / "fits").mkdir(parents=True)
    (r / "refs").mkdir(parents=True)
    (r / "m" / "evals" / "s_s0.pkl").write_bytes(pickle.dumps(ev))
    (r / "m" / "fits" / "s_s0.pkl").write_bytes(model)
    (r / "refs" / "s.pkl").write_bytes(pickle.dumps({"results": {"R": {"x": 1.0, "fit_wall_s": 3.0}}}))
    if loop_exp is not None:
        ld = r / "m" / "loops" / "s_own_s0"
        ld.mkdir(parents=True)
        (ld / "experiments.jsonl").write_text("\n".join(json.dumps(e) for e in loop_exp) + "\n", encoding="utf-8")
        (ld / "loop_record.json").write_text(json.dumps({"budget": 10, "learner_wall_s": len(loop_exp) * 1.5}), encoding="utf-8")
        (ld / "ckpt_0010.pkl").write_bytes(model)
    return r


def test_timings_and_hosts_do_not_count_but_science_does(tmp_path):
    cr = _cr()
    a = _round(tmp_path, "a", _eval(0.25, wall=2.0), b"model-a")
    b = _round(tmp_path, "b", _eval(0.25, wall=9.0), b"model-b")      # other timings, other host CPU count, other model bytes
    res = cr.compare(a, b)
    assert res["bit_identical"] and not res["model_bytes_identical"] and res["evals"]["identical"] == 1 and res["refs"]["identical"] == 1
    c = _round(tmp_path, "c", _eval(0.25 + 1e-12), b"model-a")          # a last-bit difference of a scientific value
    res = cr.compare(a, c)
    assert not res["bit_identical"] and "SMS" in res["evals"]["different"][0]["first_difference"]


def test_dataclass_estimates_compare_by_array_content(tmp_path):
    cr = _cr()
    a = _round(tmp_path, "a", _eval(0.25), b"m")
    b = _round(tmp_path, "b", _eval(0.25, reps_shift=1e-9), b"m")      # same point, different bootstrap replicates
    res = cr.compare(a, b)
    assert not res["bit_identical"] and "_estimates" in res["evals"]["different"][0]["first_difference"]


def test_loops_gate_when_both_rounds_ran_them(tmp_path):
    cr = _cr()
    exp = [{"key": "k1", "outcome": [0.1, float("nan")], "sim_wall_s": 2.0}]
    a = _round(tmp_path, "a", _eval(0.25), b"m", loop_exp=exp)
    b = _round(tmp_path, "b", _eval(0.25), b"m", loop_exp=[dict(exp[0], sim_wall_s=7.0)])
    res = cr.compare(a, b)
    assert res["loops"]["compared"] and res["loops"]["identical"] == 2 and res["bit_identical"]
    c = _round(tmp_path, "c", _eval(0.25), b"m", loop_exp=[dict(exp[0], outcome=[0.2, float("nan")])])
    assert not cr.compare(a, c)["bit_identical"]
    d = _round(tmp_path, "d", _eval(0.25), b"m")                         # no loops in one round: nothing to compare, not a failure
    res = cr.compare(a, d)
    assert not res["loops"]["compared"] and res["bit_identical"]
