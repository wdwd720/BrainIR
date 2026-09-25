"""Benchmark version 3: distinct-lift rejection in latent lifting (pre-lock review B M4 / m3), applied kick offsets of the real engine
(review D M1) and the synthetic kick-clip lister (review D M2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from brainir_state import evaluate as E
from brainir_state.api import StateModel
from brainir_state.evaluate_lift import eval_lifting, lift_supported
from brainir_state.realgen import applied_kick_totals

ROOT = Path(__file__).resolve().parents[2]
DT, T_END = 0.01, 3.0
W = np.array([1.0, 1.0, 0.5, 0.0])                 # input weights of the 4 toy neurons


# ------------------------------------------------------------------------------------------------ a toy system with an exact state
def _simulate(p: dict) -> dict:
    """dx/dt = -x + w u per neuron (Euler, dt 10 ms); kicks add to x after the sample at their time; y = x0 + x1 (= the state)."""
    n = int(round(p["t_end"] / p["dt"]))
    t = np.round(np.arange(n + 1) * p["dt"], 9)
    u = np.zeros((n + 1, 1))
    for ts, s in p["stimulus"]:
        u[t >= ts - 1e-9, 0] = s
    kicks = {}
    for e in p.get("events") or []:
        if e["kind"] == "kick":
            kicks.setdefault(int(round(e["t"] / p["dt"])), []).append(e)
    x = np.zeros((n + 1, 4))
    for i in range(n):
        xi = x[i].copy()
        for e in kicks.get(i, ()):
            for j, d in e["delta"].items():
                xi[int(j)] += d
        x[i + 1] = xi + p["dt"] * (-xi + W * u[i, 0])
    y = (x[:, 0] + x[:, 1])[:, None]
    return {"t": t, "x": x, "u": u, "y": y, "z": y.copy()}


class ToyModel(StateModel):
    """z = x0 + x1 (closed: dz/dt = -z + 2u), y = z."""
    k = {"toy": 1}

    def __init__(self, lifts=None):
        self.lifts = lifts
        self.requested = []

    def encode(self, sid, x_hist, u_hist, dt):
        self._stash = np.asarray(x_hist[-1])        # state an encode call leaves behind; rollouts must never see it
        return np.array([x_hist[-1][0] + x_hist[-1][1]])

    def rollout(self, sid, z0, u, events, dt):
        assert not hasattr(self, "_stash"), "rollout ran on the object that encode() wrote to"
        z = [np.asarray(z0, float)]
        for i in range(len(u) - 1):
            z.append(z[-1] + dt * (-z[-1] + 2.0 * u[i, 0]))
        z = np.stack(z)
        return {"z": z, "y": z.copy()}

    def readout(self, sid, z, u):
        return np.asarray(z)[..., :1]

    def lift(self, sid, x, z, delta_z, n_candidates=3):
        self.requested.append(float(np.linalg.norm(delta_z)))
        d = float(delta_z[0])
        return [lf(d) for lf in self.lifts][:n_candidates]


def _kick(n, d, scale=1.0):
    return [{"kind": "kick", "t": 0.0, "delta": {str(n): d * scale}}]


def _cases():
    base = {"dt": DT, "t_end": T_END, "stimulus": [[0.0, 0.0], [0.2, 0.8]], "events": []}
    return [{"protocol": base, "t": 1.0}, {"protocol": dict(base, stimulus=[[0.0, 0.0], [0.3, 1.2]]), "t": 1.5}]


def test_two_distinct_lifts_give_a_testable_invariance_ratio():
    m = ToyModel([lambda d: _kick(0, d), lambda d: _kick(1, d)])        # same latent shift through two different neurons
    r = eval_lifting(m, "toy", _cases(), _simulate, np.ones(1), E.EvalConfig(n_boot=50), future_s=0.5)
    assert r["supported"] and r["n_distinct"] == 8 and r["n_near_identical"] == 0 and r["n_duplicate_events"] == 0, r
    assert r["implementation_invariance"]["testable"] and r["implementation_invariance_ratio"] < 1e-6, r
    assert r["achieved_shift_rel_error"]["mean"] < 0.05, r


def test_identical_and_near_identical_lifts_are_rejected():
    # the same event set twice, and the same kick scaled by 1.0001 (distinct events, but the achieved microstate change has
    # cosine ~1): one distinct lift per requested shift -> no same-shift pair -> untestable, never a perfect ratio
    m = ToyModel([lambda d: _kick(0, d), lambda d: _kick(0, d), lambda d: _kick(0, d, 1.0001)])
    r = eval_lifting(m, "toy", _cases(), _simulate, np.ones(1), E.EvalConfig(n_boot=50), future_s=0.5)
    assert r["n_candidates"] == 12 and r["n_duplicate_events"] == 4 and r["n_near_identical"] == 4 and r["n_distinct"] == 4, r
    inv = r["implementation_invariance"]
    assert not inv["testable"] and "fewer than two distinct" in inv["reason"] and "implementation_invariance_ratio" not in r, r
    assert r["achieved_shift_rel_error"]["mean"] < 0.05, r            # the near-identical lift still counts for the shift


def test_shift_scale_uses_every_case():
    # the first case never gets an input (z stays 0): version 2 took sd(z) from the first case only, so delta_z would be ~1e-9
    m = ToyModel([lambda d: _kick(0, d), lambda d: _kick(1, d)])
    cases = _cases()
    cases[0] = {"protocol": dict(cases[0]["protocol"], stimulus=[[0.0, 0.0]]), "t": 1.0}
    eval_lifting(m, "toy", cases, _simulate, np.ones(1), E.EvalConfig(n_boot=50), future_s=0.5)
    assert min(m.requested) > 1e-3, m.requested


def test_models_without_lift_are_unsupported_without_simulation():
    class NoLift(ToyModel):
        lift = StateModel.lift

    def boom(p):
        raise AssertionError("simulated although lift() is not implemented")

    assert lift_supported(ToyModel([])) and not lift_supported(NoLift([]))
    r = eval_lifting(NoLift([]), "toy", _cases(), boom, np.ones(1), E.EvalConfig(n_boot=50))
    assert r["supported"] is False and "not implemented" in r["reason"], r
    r2 = eval_lifting(ToyModel([]), "toy", _cases(), _simulate, np.ones(1), E.EvalConfig(n_boot=50), future_s=0.5)
    assert r2["supported"] is False and "no usable candidate" in r2["reason"] and not r2["implementation_invariance"]["testable"], r2


# ------------------------------------------------------------------------------------------------ applied kick offsets (real engine)
BUNDLE = ROOT / "benchmarks" / "dng100" / "public_blind"
STORE = ROOT / "data" / "phase3" / "store"
PUBLIC = ROOT / "data" / "phase3" / "real_public"
SYSTEMS = ROOT / "benchmarks" / "state_discovery_v1" / "hidden" / "systems_internal.json"


def _clipped_public_kick_row():
    """A public kick trajectory (stored by the version-2 engine) with at least one kick that the engine clips at 0."""
    from brainir_state.store import TrajectoryStore
    store = TrajectoryStore(STORE)
    for line in (PUBLIC / "index.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        evs = [e for e in r["protocol"].get("events") or [] if e["kind"] == "kick"]
        if not evs or r["system_id"] != "real:net1:full":
            continue
        rec = store.get(r["key"])
        if rec is None:
            continue
        pos = {int(n): i for i, n in enumerate(rec["neurons"])}
        for e in evs:
            i = int(round(e["t"] / r["protocol"]["dt"]))
            for k, d in e["delta"].items():
                pre = float(rec["rates"][i, pos[int(k)]]) if int(k) in pos else 0.0
                if pre + d < 0 and pre > 0:            # a partly applied (clipped) kick
                    return r, rec
    return None, None


@pytest.mark.skipif(not (BUNDLE.exists() and STORE.exists() and PUBLIC.exists() and SYSTEMS.exists()), reason="needs the public data")
def test_engine_records_applied_kicks_and_keeps_the_rates_bitwise():
    from brainir_state.realsim import RealEngine, RealSystem, kicks_applied_from_record
    row, stored = _clipped_public_kick_row()
    if row is None:
        pytest.skip("no clipped public kick trajectory in the store")
    d = json.loads(SYSTEMS.read_text(encoding="utf-8"))[row["system_id"]]
    system = RealSystem(system_id=d["system_id"], network=d["network"], mode=d["mode"], keep=tuple(d["keep"]), observed=tuple(d["observed"]),
                        readout=tuple(d["readout"]), stimulus=tuple(d["stimulus"]))
    rec = RealEngine(BUNDLE, d["network"]).run(system, row["protocol"])
    # the rates are bitwise those of the stored record, which the engine wrote before it recorded applied kicks
    for key in ("t", "neurons", "rates", "u"):
        assert np.array_equal(rec[key], stored[key]), key
    ka = rec["info"]["kicks_applied"]
    evs = [e for e in row["protocol"]["events"] if e["kind"] == "kick"]
    assert len(ka) == len(evs) and all(a["requested"] == {k: float(v) for k, v in e["delta"].items()} for a, e in zip(ka, evs))
    back = kicks_applied_from_record(stored, row["protocol"])
    n_clip = 0
    for a, b in zip(ka, back):
        for n, req in a["requested"].items():
            assert abs(a["applied"][n] - b["applied"][n]) < 1e-4 * max(1.0, abs(req)), (a, b)
            if a["applied"][n] != req:
                n_clip += 1
                assert req < 0 and -a["applied"][n] >= 0 and abs(a["applied"][n]) < abs(req)
    assert n_clip >= 1
    tot = applied_kick_totals({"kicks_applied": ka})
    assert tot["n_clipped"] == n_clip and tot["applied_abs_total"] < tot["requested_abs_total"] and tot["source"] == "engine"
    assert applied_kick_totals({}) is None and applied_kick_totals(None) is None


def test_hidden_rows_carry_applied_kicks():
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    from generate_real_hidden import row_info
    proto = {"system": "real:x:full", "params_seed": 1, "t_end": 0.01, "dt": 0.001, "stimulus": [[0.0, 1.0]],
             "events": [{"kind": "kick", "t": 0.002, "delta": {"3": -5.0, "4": 2.0}}]}
    meta = {"system_id": "real:x:full", "family": "H_kick_A", "role": "test", "pair": "H_kick_A:0"}
    engine_rec = {"info": {"kicks_applied": [{"t": 0.002, "requested": {"3": -5.0, "4": 2.0}, "applied": {"3": -1.5, "4": 2.0}}]}}
    info = row_info(meta, engine_rec, proto)
    assert info["pair"] == "H_kick_A:0" and info["kicks_applied"] == engine_rec["info"]["kicks_applied"]
    # a record stored before version 3 (no kicks_applied): reconstructed from the stored pre-kick rates
    rates = np.zeros((11, 2), np.float32)
    rates[:, 0] = 1.5
    old = {"t": np.round(np.arange(11) * 0.001, 9), "neurons": np.array([3, 4], np.int32), "rates": rates, "info": {"engine": "p3-realsim-1"}}
    info2 = row_info(meta, old, proto)
    assert info2["kicks_applied"][0]["applied"] == {"3": -1.5, "4": 2.0} and info2["kicks_applied"][0]["source"] == "record"
    tot = applied_kick_totals(info2)
    assert tot["n_clipped"] == 1 and tot["n_null"] == 0 and tot["source"] == "record"
    assert "kicks_applied" not in row_info(meta, old, dict(proto, events=[]))


# ------------------------------------------------------------------------------------------------ synthetic kick-clip lister
def test_kick_clip_replay_flags_kicks_leaving_the_bijection_range():
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    import kick_clip_pairs as K
    from p3synth.core import PHI_ID, PHI_LOGI, PHI_TANH, Phi
    assert K.kick_leaves_range(PHI_TANH, 1.0, 1.5) and not K.kick_leaves_range(PHI_TANH, 1.0, 0.9)
    assert K.kick_leaves_range(PHI_LOGI, 2.0, -0.1) and K.kick_leaves_range(PHI_LOGI, 2.0, 2.0) and not K.kick_leaves_range(PHI_LOGI, 2.0, 1.5)
    assert not K.kick_leaves_range(PHI_ID, 1.0, 1e6)
    phi = Phi(np.array([PHI_TANH, PHI_LOGI, PHI_ID]), np.array([1.0, 2.0, 1.0]))
    proto = {"dt": 0.01, "events": [{"kind": "kick", "t": 0.05, "delta": {"0": 1.5, "1": 0.5, "2": 100.0}},
                                    {"kind": "kick", "t": 0.05, "delta": {"1": 0.6}},          # sequential: 1.5 + 0.6 leaves (0, 2)
                                    {"kind": "kick", "t": 0.1, "delta": {"0": 0.1}}]}
    rep = K.replay_kicks(phi, {5: np.zeros(3), 10: np.zeros(3)}, proto)
    assert rep["n_kick_events"] == 3 and rep["n_kicked_neurons"] == 5 and rep["n_outside"] == 2, rep
    assert rep["max_abs_dv_over_scale"] > 5, rep                        # arctanh / logit next to the boundary: a huge jump


@pytest.mark.skipif(not (ROOT / "data" / "phase3" / "synthetic_truth" / "dev" / "kick_clip_pairs.json").exists(),
                    reason="needs the dev kick-clip list")
def test_kick_clip_worker_reproduces_a_listed_dev_pair():
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    import kick_clip_pairs as K
    listed = json.loads((ROOT / "data" / "phase3" / "synthetic_truth" / "dev" / "kick_clip_pairs.json").read_text(encoding="utf-8"))
    assert listed["format"] == K.FORMAT and listed["n_clipped"] == len(listed["clipped_keys"]) == len(listed["pairs"])
    p0 = listed["pairs"][0]
    rows = [json.loads(line) for line in (ROOT / "data" / "phase3" / "synthetic_dev" / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    row = next(r for r in rows if r["key"] == p0["key"])
    out = K._system_worker(("dev", row["system_id"], [row]))[0]
    assert out["n_outside"] == p0["n_outside"] > 0 and abs(out["max_abs_dv_over_scale"] - p0["max_abs_dv_over_scale"]) < 1e-9
    twin = next(r for r in rows if r["key"] == p0["twin_key"])
    assert twin["split"] == "twin" and (twin.get("info") or {}).get("pair") == p0["pair"]
