"""The experiment loop (brainir_causal.loop) on the toy system, and the PROTOCOL 5.17 success rule."""

from __future__ import annotations

import numpy as np

from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal.api import CausalStateMethod, CausalStateModel, Designer, get_designer
from brainir_causal.loop import DirectSim, active_success, curves, run_loop


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
                       meta={"role": "d0", "store_key": r["store_key"]}) for q, r in zip(protos, res)]


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


def test_passive_designer_spends_the_same_simulator_trajectories(tmp_path):
    sid, pub, ctx = toy_ctx(tmp_path)
    sim = DirectSim(ctx)
    d0 = _d0(sid, pub, sim)
    rec = run_loop(_MeanLearner(), get_designer("passive"), sid, pub, d0, sim, budget=2, checkpoints=(2,), batch=2, seed=0)
    assert rec["spent"] == 2 and rec["ledger"]["trajectories"] == 4 and rec["ledger"]["experiments"] == 0


def test_invalid_proposals_are_refused_and_the_loop_stops(tmp_path):
    sid, pub, ctx = toy_ctx(tmp_path)
    sim = DirectSim(ctx)
    rec = run_loop(_MeanLearner(), _BadDesigner(), sid, pub, _d0(sid, pub, sim), sim, budget=4, checkpoints=(4,), batch=2, seed=0)
    assert rec["refused"] >= 3 and rec["stopped_early"] and rec["spent"] == 0 and not rec["checkpoints"]


def _rows(effect_own: float, n_sys: int = 12):
    rows = []
    rng = np.random.default_rng(0)
    for s in range(n_sys):
        for d, base in (("own", effect_own), ("random", 1.0), ("fixed", 1.0)):
            for seed in range(3):
                for b in (10, 25, 50, 100, 200):
                    ee = base * (b ** -0.3) + 0.01 * rng.standard_normal()
                    rows.append({"system": f"s{s}", "designer": d, "loop_seed": seed, "budget": b, "EE": ee, "sim_calls": 2 * b})
    return rows


def test_active_success_rule():
    good = active_success(_rows(0.5), own="own")
    assert good["success"] and good["success_fixed_budget"] and good["success_fewer_experiments"]
    same = active_success(_rows(1.0), own="own")
    assert not same["success_fixed_budget"]
    bad = active_success(_rows(1.5), own="own")
    assert not bad["success"] and bad["any_budget_worse"]
    cv = curves(_rows(0.5))
    assert set(cv) == {"own", "random", "fixed"} and cv["own"][10]["mean"] < cv["random"][10]["mean"]


def test_missing_checkpoints_are_carried_forward():
    rows = [r for r in _rows(0.5) if not (r["designer"] == "own" and r["budget"] == 200)]
    res = active_success(rows, own="own")
    assert res["per_budget"][200]["random"]["n_systems"] == 12
