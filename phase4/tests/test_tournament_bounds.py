"""The Level B full-state bound's candidates (E13, LOG P4-D51): FULL-STATE with the joint one-step fit (`refs.BOUND_EXTRA_REFS`) is fitted
in the tournament's reference stage beside the verdict references and competes for the bound with the FULL-STATE reference and the
full-state baselines, by the pre-registered rule: lowest median EE per system kind, a missing result counts as 10, ties go to
"ref:full_state". The calibration never fits it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from brainir_causal import calibrate as CAL
from brainir_causal import harness as H
from brainir_causal import refs as R

ROOT = Path(__file__).resolve().parents[2]


def _tournament():
    spec = importlib.util.spec_from_file_location("p4_tournament_bounds_under_test", ROOT / "scripts" / "p4" / "tournament.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["p4_tournament_bounds_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _res(ee: float) -> dict:
    return {"items": {"effects": {"EE_cb_medium": {"point": ee}}}}


def test_the_reference_stage_fits_the_extra_bound_candidates_and_the_calibration_does_not():
    T = _tournament()
    assert "full_state_joint" in R.BOUND_EXTRA_REFS
    assert set(T.REF_JOB_NAMES) == set(H.REF_EVAL_NAMES) | set(R.BOUND_EXTRA_REFS)
    assert all(n in T.REF_WEIGHT for n in T.REF_JOB_NAMES)                 # every reference job has a scheduling weight
    assert not set(R.BOUND_EXTRA_REFS) & set(CAL.REFS) and "full_state_joint" not in CAL.calib_fit_names()


def test_full_state_joint_competes_for_the_bound_by_the_pre_registered_rule():
    T = _tournament()
    systems = {"syn-a": {"kind": "synthetic"}, "syn-b": {"kind": "synthetic"}, "syn-c": {"kind": "synthetic"}, "real:A:m1": {"kind": "real"}}
    refs = {"syn-a": {"full_state": _res(0.5), "full_state_joint": _res(0.3), "id_shortcut": _res(0.9)},
            "syn-b": {"full_state": _res(0.6), "full_state_joint": _res(0.2), "id_shortcut": _res(0.9)},
            "syn-c": {"full_state": _res(0.4), "full_state_joint": _res(0.35), "id_shortcut": _res(0.9)},
            "real:A:m1": {"full_state": _res(0.7), "id_shortcut": _res(0.9)}}          # no joint result on the real system: counts 10
    b = T.choose_bounds(refs, {}, systems)
    assert b["choice_by_kind"]["full_state"]["synthetic"] == "ref:full_state_joint"      # median 0.30 < 0.50
    assert b["choice_by_kind"]["full_state"]["real"] == "ref:full_state"                 # missing = 10
    assert b["median_ee_by_kind"]["full_state"]["real"]["ref:full_state_joint"] == 10.0
    assert b["full_state"]["syn-a"] == "ref:full_state_joint" and b["full_state"]["real:A:m1"] == "ref:full_state"
    assert "ref:full_state_joint" not in b["median_ee_by_kind"]["id_shortcut"]["synthetic"]   # a full-state candidate only
    fx = T.bound_effects(b["full_state"]["syn-a"], "syn-a", refs, {}, 0)                 # its effects come from its own result
    assert fx == H.verdict_effects(refs["syn-a"]["full_state_joint"])
    # a tie goes to the FULL-STATE reference
    tie = {s: dict(r, full_state_joint=r["full_state"]) for s, r in refs.items()}
    assert T.choose_bounds(tie, {}, systems)["choice_by_kind"]["full_state"]["synthetic"] == "ref:full_state"
    # the choice carries over to new systems of the kind (the Level C mapping)
    assert T.bounds_for_systems(b, {"syn-new": {"kind": "synthetic"}})["full_state"]["syn-new"] == "ref:full_state_joint"


def test_infrastructure_failures_are_never_taken_for_results():
    """A final infrastructure failure (the Backend's exception after its re-submissions, an InfraFault marker, the host gate, staging
    freshness) is never stored as a stage's output nor charged to a method; the round is marked incomplete instead. A job's own error
    stays its result."""
    T = _tournament()
    assert T.infra_failure(RuntimeError("call failed repeatedly on Modal (infrastructure): FileNotFoundError(2, 'No such file')"))
    assert T.infra_failure({"__infra__": True, "error": "InfraFault (WorkerDied): died twice"})
    assert T.infra_failure({"sid": "x", "error": "RuntimeError: no admissible host after 400 attempts"})
    assert T.infra_failure({"sid": "x", "error": "InfraFault (PackInfraError): packed child driver of slot 3 exited -9"})
    assert T.infra_failure({"sid": "x", "error": "ValueError: the method raised"}) is None
    assert T.infra_failure({"sid": "x", "result": {"items": {}}}) is None
