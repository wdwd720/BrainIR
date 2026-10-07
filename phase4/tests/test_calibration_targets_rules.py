"""The calibration-target builder (scripts/p4/calibration_targets.py; LOG P4-D38): its documented rules (range rules, coverage rule,
change vs the earlier version), prose replacement without recomputation, and the shipped targets file (version 3) equals the builder's
output on its own per-system values."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PUB = REPO / "benchmarks" / "causal_state_v1" / "public"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CT = _load("p4_calibration_targets_under_test", REPO / "scripts" / "p4" / "calibration_targets.py")
DOC = _load("p4_calibration_targets_doc_under_test", REPO / "scripts" / "p4" / "calibration_targets_doc.py")


def test_range_rules():
    assert CT.target_range("pos", 2.0, 10.0) == [1.0, 20.0]
    assert CT.target_range("frac", 0.05, 0.95) == [0.0, 1.0]
    assert CT.target_range("frac", 0.3, 0.5) == pytest.approx([0.2, 0.6])
    assert CT.target_range("dim", 3, 43) == [2, 65]
    assert CT.target_range("dim", 1, 11) == [1, 17]
    assert CT.target_range("size", 3, 213) == [3, 266.25]
    assert CT.target_range("dt", 0.001, 0.001) == [0.0005, 0.005]
    with pytest.raises(ValueError):
        CT.target_range("other", 0.0, 1.0)


def test_one_significant_figure_rounding():
    assert CT._sig1(0.275, True) == 0.3 and CT._sig1(0.466, False) == 0.4
    assert CT._sig1(0.0606, True) == 0.07 and CT._sig1(0.613, False) == 0.6
    assert CT._sig1(0.3, True) == 0.3 and CT._sig1(197.0, False) == 100.0 and CT._sig1(6.0, True) == 6.0
    assert CT._sig1(0.0, True) == 0.0


def test_coverage_rule_regimes_and_overlap():
    def rg(lo, hi, med):
        return {"min": lo, "max": hi, "median": med}
    # two regimes: a = the low class's max rounded up, b = the high class's min rounded down
    assert CT.coverage(rg(0.466, 0.647, 0.53), rg(0.00433, 0.275, 0.06)) == [0.3, 0.4]
    assert CT.coverage(rg(197, 213, 211), rg(3, 6, 3)) == [6.0, 100.0]
    # overlapping classes: the two medians, a at least 0.01
    assert CT.coverage(rg(0.0401, 0.542, 0.363), rg(0.0, 0.246, 0.0)) == [0.01, 0.3]


def test_change_vs_earlier():
    cur = {"a": 2.0, "b": 0.0, "c": 1.0, "d": 3.0, "e": None, "f": 5.0}
    earlier = {"a": 1.0, "b": 1.0, "c": 0.0, "d": 3.0, "e": 1.0}
    c = CT.change(cur, earlier)
    assert (c["n_systems"], c["n_from_zero"], c["n_to_zero"]) == (4, 1, 1)
    assert c["ratio_median"] == pytest.approx(math.sqrt(2.0)) and c["ratio_max"] == pytest.approx(2.0)
    none = CT.change(cur, {})
    assert none["ratio_median"] is None and none["n_systems"] == 0


def _tiny_targets():
    prose = {k: f"text {k}" for k in CT.PROSE_KEYS}
    prose["rationale"] = {"n_obs": "old why"}
    per = {"real system 1": {"n_obs": 200.0, "dt": 0.001, "other_stat": 1.0},
           "real system 2": {"n_obs": 3.0, "dt": 0.001, "other_stat": 2.0}}
    classes = {"real system 1": "full", "real system 2": "mechanism"}
    counts = {"records": 10, "per_system": {"real system 1": 4, "real system 2": 6}}
    return CT.build(per, classes, {"statistics": {"other_stat": {"per_system": {"real system 1": 0.5}}}}, prose, version="t/1",
                    counts=counts)


def test_build_applies_the_rules():
    t = _tiny_targets()
    n = t["statistics"]["n_obs"]
    assert n["check"] and n["target_range"] == [3.0, 250.0] and n["coverage"] == [3.0, 200.0] and n["rationale"] == "old why"
    assert t["statistics"]["dt"]["target_range"] == [0.0005, 0.005] and t["statistics"]["dt"]["coverage"] is None
    o = t["statistics"]["other_stat"]
    assert not o["check"] and o["target_range"] is None and o["change_vs_earlier_design"]["ratio_max"] == pytest.approx(2.0)
    assert o["real_all"] == {"min": 1.0, "max": 2.0, "median": 1.5, "n": 2}


def test_apply_prose_changes_only_prose():
    t = _tiny_targets()
    prose = {k: f"new {k}" for k in CT.PROSE_KEYS}
    prose["rationale"] = {"n_obs": "new why", "dt": "dt why"}
    out = CT.apply_prose(t, prose)
    assert out["note"] == "new note" and out["statistics"]["n_obs"]["rationale"] == "new why"
    assert out["statistics"]["dt"]["rationale"] == "dt why" and "rationale" not in out["statistics"]["other_stat"]
    assert CT.compare(t, out) == [] and t["note"] == "text note"


def test_placeholders_fill_from_the_statistics():
    st = {"n_obs": {"real_full": {"min": 197, "max": 213}, "real_mechanism": {"min": 3, "max": 6}, "real_all": {"min": 3, "max": 213}},
          "dt": {"real_all": {"min": 0.001, "max": 0.001}}}
    assert DOC.fill_many("{n_obs|F:n} / {n_obs|M:n} / {n_obs|Amax:n} / {dt|A:msg}", st) == "197-213 / 3-6 / 213 / 1 ms"
    assert DOC.fill_many("{missing|A:x}", st) == "n/a"


@pytest.mark.skipif(not (PUB / "calibration_targets.json").exists(), reason="no targets file")
def test_shipped_targets_equal_the_builder_output_on_their_own_values():
    t = json.loads((PUB / "calibration_targets.json").read_text(encoding="utf-8"))
    v2 = json.loads((PUB / "calibration_targets_v2_explicit_init_design.json").read_text(encoding="utf-8"))
    assert t["version"] == "causal_state_v1/calibration_targets/3" and set(t["systems"]) == set(CT.LABELS)
    per: dict[str, dict] = {lab: {} for lab in t["systems"]}
    for nm, e in t["statistics"].items():
        for lab, v in e["per_system"].items():
            per[lab][nm] = v
    classes = {lab: s["class"] for lab, s in t["systems"].items()}
    counts = {"records": 0, "per_system": {lab: 1 for lab in per}}
    rebuilt = CT.build(per, classes, v2, CT.prose_of(t), version=t["version"], counts=counts)
    # the ratios of change_vs_earlier_design go through math.log / math.exp, whose last bit differs between C libraries (the file
    # was built on Windows; the sharded runner is Linux): identity at a relative 1e-12, orders of magnitude below any edit or rule drift
    assert CT.compare(t, rebuilt, tol=1e-12) == []
    assert {nm for nm, e in t["statistics"].items() if e.get("check")} == set(CT.CHECKED)
    # design v2: no explicit initial states in the design text
    assert "no explicit initial states" in t["design"]["initial_states"]
    assert not any(c.startswith("Strong initial states") for c in t["caveats"])
