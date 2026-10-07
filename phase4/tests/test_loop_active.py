"""The experiment loop (brainir_causal.loop) on the toy system, the PROTOCOL 5.17 success rule (review E, M4) and the magnitude budget
(review H, minor 3)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

import brainir_causal.designers  # noqa: F401 - registers the reference designers
from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal.api import CausalStateMethod, CausalStateModel, Designer, get_designer
from brainir_causal.loop import (
    DirectSim,
    active_success,
    budget_ratio,
    checkpoint_grid,
    curves,
    magnitude_budget,
    mde_by_simulation,
    passage_budget,
    run_loop,
)


class _ConstModel(CausalStateModel):
    def __init__(self, n_y: int, mean: np.ndarray, n_seen: int):
        self.k = {}
        self.mean, self.n_y, self.n_seen = mean, n_y, n_seen

    def encode(self, sid, x_hist, u_hist, dt):
        return np.zeros(1)

    def rollout(self, sid, z0, u_future, events, dt):
        n = len(u_future)
        return {"z": np.zeros((n, 1)), "y": np.tile(self.mean, (n, 1))}

    def readout(self, sid, z, u):
        return np.tile(self.mean, (len(np.atleast_2d(z)), 1))

    def supports(self, sid, kind):
        return True


class _MeanLearner(CausalStateMethod):
    name = "mean_learner"

    def fit(self, data, *, systems, config=None, seed=0):
        y = np.concatenate([np.asarray(r.y, float) for r in data])
        return _ConstModel(y.shape[1], y.mean(0), len(data))


class _BadDesigner(Designer):
    name = "bad"

    def propose(self, sid, system, model, data, n, budget_left, rng):
        return [{"system": sid, "params_seed": 5, "t_end": 4.0, "dt": 0.01, "events": [{"kind": "edge_scale", "t0": 1.0, "t1": 2.0,
                                                                                     "edges": [[0, 5]], "factor": 1.5}]}] * n


def toy_ctx(tmp_path):
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    from brainir_causal.synthadapter import suite_systems
    obj = suite_systems("toy", S.DEV_SEED)[sid]
    ctx = S.SimContext(ints[sid], store_root=tmp_path / "store", synthetic_system=obj)
    return sid, pubs[sid], ctx


def _d0(sid, pub, sim):
    s = S.FamilySampler(pub, np.random.default_rng(0), S.seed_counter(False, "d0test"), targets=pub["targets_public"])
    protos = [P.validate(s.obs("obs.stim")) for _ in range(2)]
    res = sim.run(protos)
    from brainir_causal.data import Trajectory
    return [Trajectory(key=r["key"], system_id=sid, split="train", family="obs.stim", protocol=q, t=r["t"], x=r["x"], u=r["u"], y=r["y"],
                       meta={"role": "d0", "store_key": r["store_key"]}) for q, r in zip(protos, res, strict=True)]


# ------------------------------------------------------------------------------------------------------------ the loop
def test_loop_spends_the_budget_with_twins_and_checkpoints(tmp_path):
    sid, pub, ctx = toy_ctx(tmp_path)
    sim = DirectSim(ctx)
    d0 = _d0(sid, pub, sim)
    rec = run_loop(_MeanLearner(), get_designer("random"), sid, pub, d0, sim, budget=4, checkpoints=(2, 4), batch=2, seed=0)
    assert rec["spent"] == 4 and [c["budget"] for c in rec["checkpoints"]] == [2, 4]
    data = rec["data"]
    items = [r for r in data if r.protocol.get("events")]
    twins = [r for r in data if r.meta.get("twin_of")]
    assert len(items) == 4 and len(twins) == 4 and {t.meta["twin_of"] for t in twins} == {r.key for r in items}
    assert rec["ledger"]["experiments"] == 4 and rec["ledger"]["trajectories"] == 8 and rec["refused"] == 0
    assert set(rec["models"]) == {2, 4}
    mb = rec["checkpoints"][-1]["magnitude_budget"]
    assert mb["n_intervention_protocols"] == 4 and mb == magnitude_budget(rec["executed"])


def test_loop_writes_the_experiment_protocols(tmp_path):
    sid, pub, ctx = toy_ctx(tmp_path)
    sim = DirectSim(ctx)
    rec = run_loop(_MeanLearner(), get_designer("random"), sid, pub, _d0(sid, pub, sim), sim, budget=2, checkpoints=(2,), batch=2, seed=0,
                   out_dir=tmp_path / "loop")
    rows = [json.loads(line) for line in (tmp_path / "loop" / "experiments.jsonl").read_text(encoding="utf-8").splitlines()]
    items = [r for r in rows if not r["twin_of"]]
    assert len(items) == 2 and all(r["protocol"]["events"] for r in items)
    assert all(r["protocol"] is None for r in rows if r["twin_of"]) and rec["magnitude_budget"]["n_intervention_protocols"] == 2


def test_passive_designer_spends_the_same_simulator_trajectories(tmp_path):
    sid, pub, ctx = toy_ctx(tmp_path)
    sim = DirectSim(ctx)
    rec = run_loop(_MeanLearner(), get_designer("passive"), sid, pub, _d0(sid, pub, sim), sim, budget=2, checkpoints=(2,), batch=2, seed=0)
    assert rec["spent"] == 2 and rec["ledger"]["trajectories"] == 4 and rec["ledger"]["experiments"] == 0


def test_invalid_proposals_are_refused_and_the_loop_stops(tmp_path):
    sid, pub, ctx = toy_ctx(tmp_path)
    sim = DirectSim(ctx)
    rec = run_loop(_MeanLearner(), _BadDesigner(), sid, pub, _d0(sid, pub, sim), sim, budget=4, checkpoints=(4,), batch=2, seed=0)
    assert rec["refused"] >= 3 and rec["stopped_early"] and rec["spent"] == 0 and not rec["checkpoints"]


def test_magnitude_budget_keeps_kicks_and_currents_apart():
    base = {"system": "s", "params_seed": 1, "t_end": 2.0, "dt": 0.01}
    mb = magnitude_budget([{**base, "events": [{"kind": "kick", "t": 0.5, "delta": {"1": 2.0, "2": -1.0}},
                                               {"kind": "current", "t0": 1.0, "t1": 1.5, "targets": {"3": 4.0}},
                                               {"kind": "current", "t0": 1.8, "t1": None, "targets": {"3": -1.0}}]},
                           {**base, "events": []}])
    assert mb["kick_magnitude"] == 3.0 and math.isclose(mb["current_dose"], 4.0 * 0.5 + 1.0 * 0.2)
    assert mb["n_intervention_protocols"] == 1 and mb["n_events"] == 3
    fine = magnitude_budget([{**base, "dt": 0.001, "events": [{"kind": "kick", "t": 0.5, "delta": {"1": 2.0}}]}])
    assert fine["kick_magnitude"] == 2.0                                    # independent of dt


# ------------------------------------------------------------------------------------------------------------ evaluated checkpoints
BUDGETS = (10, 25, 50, 100, 200)


def _curve(b, eff=1.0, level=1.0):
    return 0.2 + level * (eff * b / 10.0) ** -0.5


def _rows(n_sys=30, effs=None, noise=0.03, seed=0, designers=("own", "random", "fixed"), budgets=BUDGETS):
    """Simulated evaluated checkpoints: each designer's curve is the common learning curve at eff x budget, plus a per-seed offset and
    per-budget noise."""
    effs = effs or {"own": 1.0, "random": 1.0, "fixed": 1.0}
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_sys):
        level = float(rng.uniform(0.6, 1.4))
        for d in designers:
            for sd in range(3):
                off = noise * rng.standard_normal()
                for b in budgets:
                    rows.append({"system": f"s{s}", "designer": d, "loop_seed": sd, "budget": b,
                                 "EE": float(_curve(b, effs[d], level) + off + noise * rng.standard_normal()), "sim_calls": 2 * b})
    return rows


def test_passage_budget_interpolates_and_censors():
    c = {10: 1.0, 25: 0.8, 50: 0.5, 100: 0.4}
    b, ok = passage_budget(c, 0.65)
    assert ok and 25 < b < 50 and math.isclose(b, math.exp(math.log(25) + 0.5 * (math.log(50) - math.log(25))))
    assert passage_budget(c, 1.5) == (10.0, True)
    assert passage_budget(c, 0.1) == (100.0, False)


def test_budget_ratio_is_unbiased_under_the_null():
    ratios = [budget_ratio(_rows(n_sys=25, seed=k), own="own", n_boot=200, seed=k)["ratio"] for k in range(20)]
    assert 0.9 < float(np.mean(ratios)) < 1.1


def test_budget_ratio_detects_a_twice_as_efficient_design():
    br = budget_ratio(_rows(n_sys=40, effs={"own": 2.0, "random": 1.0, "fixed": 1.0}), own="own", n_boot=500)
    assert br["success"] and 0.35 < br["ratio"] < 0.75


def test_leave_one_seed_out_targets():
    rows = _rows(n_sys=3)
    grid, _ = checkpoint_grid(rows)
    br = budget_ratio(own="own", grid=grid, n_boot=100)
    for s, ps in br["per_system"].items():
        ref100 = {sd: grid[(s, "random", sd)][100] for sd in range(3)}
        for r in ps["seeds"]:
            assert math.isclose(r["target"], np.mean([v for i, v in ref100.items() if i != r["loop_seed"]]))


def test_censored_curves_contribute_the_largest_budget():
    rows = [r for r in _rows(n_sys=4) if r["designer"] in ("random", "fixed")]
    for s in range(4):
        for sd in range(3):
            for b in BUDGETS:
                rows.append({"system": f"s{s}", "designer": "own", "loop_seed": sd, "budget": b, "EE": 5.0})
    br = budget_ratio(rows, own="own", n_boot=100)
    assert br["censored_own"] == 12 and all(p["b_own"] == 200.0 for p in br["per_system"].values())


def test_active_success_rule_and_matched_control():
    good = active_success(_rows(effs={"own": 2.0, "random": 1.0, "fixed": 1.0}), own="own", n_boot=500)
    assert good["success"] and good["success_fixed_budget"] and good["success_fewer_experiments"]
    null = active_success(_rows(seed=3), own="own", n_boot=500)
    assert not null["success_fixed_budget"]
    bad = active_success(_rows(effs={"own": 0.5, "random": 1.0, "fixed": 1.0}), own="own", n_boot=500)
    assert not bad["success"] and bad["any_budget_worse"]
    matched = active_success(_rows(effs={"own": 2.0, "random": 1.0, "fixed": 1.0, "random_matched": 2.0},
                                   designers=("own", "random", "fixed", "random_matched")), own="own", n_boot=500)
    assert matched["success"] and "matched_control" in matched and not matched["matched_control"]["fixed_budget"]["success"]
    cv = curves(_rows(effs={"own": 2.0, "random": 1.0, "fixed": 1.0}), n_boot=200)
    assert cv["own"][10]["mean"] < cv["random"][10]["mean"] and cv["own"][10]["sim_calls"] == 20


def test_failures_are_charged_and_comparator_failures_excluded():
    rows = _rows(n_sys=10)
    with pytest.raises(ValueError):
        active_success([r for r in rows if r["designer"] != "fixed"], own="own", n_boot=100)
    own_missing = [r for r in rows if not (r["designer"] == "own" and r["system"] == "s0")]
    res = active_success(own_missing, own="own", n_boot=100)
    assert res["charged"]["missing_loop"] == 3 and "s0" not in res["excluded_systems"]
    ref_missing = [r for r in rows if not (r["designer"] == "random" and r["system"] == "s1")]
    res = active_success(ref_missing, own="own", n_boot=100)
    assert "s1" in res["excluded_systems"] and res["n_systems"] == 9 and "s1" in res["budget_ratio"]["excluded"]
    early = [r for r in rows if not (r["designer"] == "own" and r["system"] == "s2" and r["loop_seed"] == 0 and r["budget"] == 200)]
    grid, counts = checkpoint_grid(early)
    assert counts["carried_forward"] == 1 and grid[("s2", "own", 0)][200] == grid[("s2", "own", 0)][100]


def test_mde_by_simulation_smoke():
    res = mde_by_simulation(_rows(n_sys=12, designers=("random", "fixed")), efficiencies=(1.0, 3.0), n_sim=6, n_boot=200, seed=0)
    t = res["table"]
    assert set(t) == {1.0, 3.0} and t[3.0]["either"] >= t[1.0]["either"] and t[1.0]["fixed_budget"] <= 0.5
    assert 0.8 < t[1.0]["mean_estimated_ratio"] < 1.25 and t[3.0]["mean_estimated_ratio"] < 0.8


def test_each_rule_is_tested_at_alpha_0025():
    from brainir_causal.loop import RULE_ALPHA
    assert RULE_ALPHA == 0.025
    res = active_success(_rows(n_sys=12, effs={"own": 2.0, "random": 1.0, "fixed": 1.0}), own="own", n_boot=400)
    assert res["alpha_per_rule"] == 0.025 and res["budget_ratio"]["alpha"] == 0.025 and res["fixed_budget"]["alpha"] == 0.025
    loose = active_success(_rows(n_sys=12, effs={"own": 2.0, "random": 1.0, "fixed": 1.0}), own="own", n_boot=400, alpha=0.05)
    assert loose["budget_ratio"]["upper_bound"] <= res["budget_ratio"]["upper_bound"]
