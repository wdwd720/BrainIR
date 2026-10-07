"""TRUE-STATE / OBS-SHORTCUT with the trajectory's effective draw parameters as static context (review E round 3, N-new-1; LOG
P4-D43): on a toy whose every trajectory has its own draw (latent speed, readout gain, current gain), a reference on z alone has an
error floor that the complete state [z, draw] removes."""

from __future__ import annotations

import numpy as np
import pytest
from test_lift_toysys import DT, ToyLinear, passive_protocol

from brainir_causal import protocol as P
from brainir_causal import refs as R

CFG = R.LearnerConfig(steps_one=1000, steps_multi=150, readout_steps=800, threads=2)
TINY = R.LearnerConfig(steps_one=150, steps_multi=20, readout_steps=150, threads=2)
DRAW_SD = 0.35


class ToyDraw(ToyLinear):
    """ToyLinear whose every trajectory has its own ARTIFICIAL draw (a function of params_seed): the latent dynamics run w times
    faster, the readout has gain gy and currents act with gain gi, (log w, log gy, log gi) = DRAW_SD x standard normals. The true
    causal state z is closed only given the draw."""

    def draw(self, seed: int) -> np.ndarray:
        return DRAW_SD * np.random.default_rng(10_000 + int(seed)).standard_normal(3)

    def simulate(self, proto: dict, full: bool = False) -> dict:
        q = P.validate(proto)
        dt = q["dt"]
        T = round(q["t_end"] / dt) + 1
        t = np.round(np.arange(T) * dt, 9)
        u = np.zeros((T, 1))
        for ts, v in q["stimulus"]:
            u[t >= ts - 1e-9, 0] = float(v if not isinstance(v, list) else v[0])
        lw, lgy, lgi = self.draw(q["params_seed"])
        A = np.exp(lw) * self.A
        s = np.zeros(self.n)
        S = np.zeros((T, self.n))
        for i in range(T):
            S[i] = s
            if i == T - 1:
                break
            ti = t[i]
            for e in q["events"]:
                if e["kind"] == "kick" and abs(e["t"] - ti) < dt / 2:
                    dx = np.zeros(self.n)
                    for kk, v in e["delta"].items():
                        dx[int(kk)] += v
                    s = s + self.Minv @ dx
            cur = np.zeros(self.n)
            for e in q["events"]:
                if e["kind"] == "current" and e["t0"] <= ti + 1e-9 and (e["t1"] is None or ti < e["t1"] - 1e-9):
                    for kk, v in e["targets"].items():
                        cur[int(kk)] += v
            ds = np.zeros(self.n)
            ds[:2] = A @ s[:2] + self.b * u[i, 0]
            ds[2:] = -s[2:] / self.tau_w
            s = s + dt * (ds + np.exp(lgi) * (self.Minv @ cur))
        X = S @ self.M.T
        Y = np.exp(lgy) * (S[:, :2] @ self.G.T)
        out = {"t": t, "x": X, "u": u, "y": Y, "info": {}}
        if full:
            out["z"] = S[:, :2].copy()
            out["state"] = X.copy()
        return out


def draw_records(sysm: ToyDraw, n_passive: int, n_kick: int, n_pulse: int, seed: int):
    """Records like test_lift_toysys.make_records, with the truth {"z": {key: z}, "draw": {key: (3,)}}."""
    rng = np.random.default_rng(seed)
    recs, z, dr = [], {}, {}

    def add(proto, split="train", meta=None):
        q = P.validate(proto)
        r = sysm.simulate(q, full=True)
        key = P.protocol_hash(q)
        recs.append({"key": key, "system_id": "toy", "split": split, "family": "", "protocol": q, "t": r["t"], "x": r["x"], "u": r["u"],
                     "y": r["y"], "meta": meta or {}})
        z[key], dr[key] = r["z"], sysm.draw(q["params_seed"])
        return recs[-1]

    for i in range(n_passive):
        add(passive_protocol(1000 + seed * 1000 + i, stim=float(rng.uniform(0.5, 1.5)), t_on=float(rng.uniform(0.05, 0.4))))
    for i in range(n_kick + n_pulse):
        base = passive_protocol(2000 + seed * 1000 + i, stim=float(rng.uniform(0.5, 1.5)), t_on=float(rng.uniform(0.05, 0.3)))
        unit = int(rng.integers(0, sysm.n))
        t_ev = round(float(rng.uniform(0.4, 0.9)), 2)
        if i < n_kick:
            ev = {"kind": "kick", "t": t_ev, "delta": {str(unit): float(rng.choice([-1, 1]) * rng.uniform(0.5, 2.0))}}
        else:
            ev = {"kind": "current", "t0": t_ev, "t1": round(t_ev + 0.1, 2), "targets": {str(unit): float(rng.uniform(-8, 8))}}
        rint = add(dict(base, events=[ev]))
        add(P.counterfactual(rint["protocol"]), split="twin", meta={"twin_of": rint["key"]})
    return recs, {"z": z, "draw": dr}


def effect_error(m, test, h: int = 100) -> float:
    """Pooled relative effect error over the test pairs at horizon h (samples)."""
    by = {r["key"]: r for r in test}
    num = den = 0.0
    for r in test:
        tw = r["meta"].get("twin_of")
        if not tw:
            continue
        ri = by[tw]
        ev = ri["protocol"]["events"]
        t0 = min(P.event_start(e) for e in ev)
        i0 = round(t0 / DT)
        rel = [dict(e, **({"t": e["t"] - t0} if "t" in e else {"t0": e["t0"] - t0, "t1": e["t1"] - t0})) for e in ev]
        out = m.intervention_effect("toy", ri["x"][: i0 + 1], ri["u"][: i0 + 1], ri["u"][i0: i0 + h + 1], rel, DT)
        true = ri["y"][i0 + 1: i0 + h + 1] - r["y"][i0 + 1: i0 + h + 1]
        num += float(np.sum((out["effect"][1: h + 1] - true) ** 2))
        den += float(np.sum(true ** 2))
    return num / den


@pytest.fixture(scope="module")
def toy_draw():
    s = ToyDraw()
    train, truth = draw_records(s, n_passive=20, n_kick=40, n_pulse=24, seed=0)
    test, ttruth = draw_records(s, n_passive=4, n_kick=16, n_pulse=10, seed=5)
    return s, train, truth, test, ttruth


@pytest.fixture(scope="module")
def small():
    """A small draw toy fitted with a tiny budget (structure tests)."""
    s = ToyDraw()
    train, truth = draw_records(s, n_passive=6, n_kick=12, n_pulse=6, seed=0)
    test, ttruth = draw_records(s, n_passive=2, n_kick=4, n_pulse=2, seed=5)
    m = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=TINY)
    m.register_records(test, ttruth["z"], ttruth["draw"])
    return s, train, truth, test, ttruth, m


@pytest.mark.slow
def test_the_draw_removes_the_error_floor_of_a_z_only_reference(toy_draw):
    s, train, truth, test, ttruth = toy_draw
    with_draw = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=CFG)
    z_only = R.fit_reference("true_state_zonly", "toy", train, s.record(), truth=truth, cfg=CFG)
    with_draw.register_records(test, ttruth["z"], ttruth["draw"])
    z_only.register_records(test, ttruth["z"])
    e_draw, e_z = effect_error(with_draw, test), effect_error(z_only, test)
    # z alone cannot know the trajectory's speed, readout gain or current gain: a floor however well the learner fits (measured
    # when written: 0.36 for z alone, 0.07 for [z, draw] at this horizon of 1 s)
    assert e_z > 0.1, e_z
    assert e_draw < 0.4 * e_z, (e_draw, e_z)
    assert with_draw.info()["draw_context"] and not z_only.info()["draw_context"]
    # the z-only reference's effect calibration shrinks the undetermined late effect; with the draw it stays near 1
    assert with_draw.beta[-1] > z_only.beta[-1]


def test_the_draw_is_static_context_with_zero_dynamics(small):
    _s, _train, _truth, test, ttruth, m = small
    info = m.info()
    assert info["k"]["toy"] == 5 and info["k_dynamic"]["toy"] == 2 and info["k_context"]["toy"] == 3
    assert m.fit_notes["static_context"] == {"dims": 3, "kept": 3, "dropped_constant": 0}
    r = next(q for q in test if q["protocol"].get("events"))
    z0 = m.encode("toy", r["x"][:61], r["u"][:61], DT)
    assert np.allclose(z0[:2], ttruth["z"][r["key"]][60]) and np.allclose(z0[2:], ttruth["draw"][r["key"]])
    ev = [{"kind": "kick", "t": 0.05, "delta": {"1": 2.0}}, {"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {"3": 5.0}}]
    ro = m.rollout("toy", z0, r["u"][60: 101], ev, DT)
    assert np.allclose(ro["z"][:, 2:], z0[2:])                    # no dynamics, no intervention moves the draw
    assert not np.any(m.read_in("toy", z0, ev[0])["dz"][2:])
    lifts = m.lift("toy", r["x"][:61], r["u"][:61], np.array([0.5, -0.3, 1.0, 1.0, 1.0]), 2)
    assert lifts and all(not np.any(q["predicted_dz"][2:]) for q in lifts)
    # the channel effect's context gain exists and is used
    assert info["context_gain"] and m.Wg.shape == (2, 3)


def test_registration_without_draw_and_the_z_only_fallback(small):
    s, train, truth, test, ttruth, m = small
    before = m.n_registered_without_draw
    r = test[1]
    m.register_truth(r["x"][:, :] + 1e-3, r["u"], ttruth["z"][r["key"]], DT)          # no draw: the training-mean draw, counted
    assert m.n_registered_without_draw == before + 1
    z0 = m.encode("toy", r["x"][:41] + 1e-3, r["u"][:41], DT)
    assert np.allclose(z0[2:], m.stat_fill)
    # a system without draw information: z alone, with the reason recorded
    fb = R.fit_reference("true_state", "toy", train, s.record(), truth={"z": truth["z"]}, cfg=TINY)
    assert fb.info()["k"]["toy"] == 2 and not fb.info()["draw_context"]
    assert fb.fit_notes["static_context"].startswith("off: no draw information")
    # constant draw coordinates carry nothing learnable: dropped
    dr4 = {k: np.concatenate([v, [7.0]]) for k, v in truth["draw"].items()}
    m4 = R.TruthStateModel("z", cfg=TINY)
    m4.fit_truth("toy", train, s.record(), truth["z"], dr4)
    assert m4.fit_notes["static_context"] == {"dims": 4, "kept": 3, "dropped_constant": 1} and m4.info()["k"]["toy"] == 5
