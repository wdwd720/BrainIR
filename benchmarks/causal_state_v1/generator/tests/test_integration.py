"""Integration accuracy: the fast structured integrator equals a brute-force RK4 of the full microstate; RK4 step convergence;
output-step consistency; speed."""

import time

import numpy as np
import pytest

from conftest import one_per_type
from p4synth import protocol as P
from p4synth.engine import CORE, FOL, GEN, RELAY
from p4synth.integrate import simulate as fast_sim
from p4synth.reference import simulate_reference

STEP_TOL = 1e-3          # addendum 1: |y(h) - y(h/2)| < STEP_TOL x the readout floor
STEP_TOL_EXTREME = 1.5e-3  # stated bound under the extreme window (tau 0.1, gain 1.9): 148 / 150 systems of 3 seeds meet 1e-3


def _mixed_events(s):
    sp = s.spec
    core = [u for u in s.targetable if sp.role[u] == CORE] or list(sp.units_of(CORE))
    c0, c1, c2 = int(core[0]), int(core[1 % len(core)]), int(core[2 % len(core)])
    ev = [{"kind": "kick", "t": 0.3, "delta": {c0: 5.0}},
          {"kind": "current", "t0": 0.4, "t1": 0.45, "targets": {c1: 20.0}},
          {"kind": "silence", "t0": 0.5, "t1": 0.6, "targets": [c2]},
          {"kind": "param", "t0": 0.62, "t1": 0.7, "targets": {c0: {"gain": 1.5, "threshold": 1.0, "tau": 0.3}}},
          {"kind": "edge_scale", "t0": 0.7, "t1": 0.8, "edges": [[c1, c0]], "factor": 0.2},
          {"kind": "current_seq", "t0": 0.82, "seg": 0.01, "targets": {c2: [5.0, 0.0, -5.0]}},
          {"kind": "latent_kick", "t": 0.85, "dz": [0.1] * sp.k}]
    fol, gen, rel = list(sp.units_of(FOL)), list(sp.units_of(GEN)), list(sp.units_of(RELAY))
    if fol:
        ev += [{"kind": "kick", "t": 0.35, "delta": {int(fol[0]): -3.0}},
               {"kind": "current", "t0": 0.36, "t1": 0.5, "targets": {int(fol[-1]): 4.0}},
               {"kind": "silence", "t0": 0.52, "t1": None, "targets": [int(fol[len(fol) // 2])]},
               {"kind": "param", "t0": 0.3, "t1": 0.5, "targets": {int(fol[1 % len(fol)]): {"tau": 0.4, "gain": 1.3, "threshold": 0.5}}}]
        fe = [e for e in s.edges if sp.role[e[0]] == FOL][:3]
        if fe:
            ev.append({"kind": "edge_scale", "t0": 0.2, "t1": 0.9, "edges": fe, "factor": 0.3})
    # one scaled edge of every (post role, pre role) class the system lists (core-core, follower-follower, generator-generator,
    # relay-core)
    classes = {}
    for e in s.edges:
        classes.setdefault((int(sp.role[e[0]]), int(sp.role[e[1]])), e)
    for i, e in enumerate(classes.values()):
        ev.append({"kind": "edge_scale", "t0": round(0.25 + 0.05 * i, 3), "t1": round(0.6 + 0.05 * i, 3), "edges": [e], "factor": 1.6})
    if gen:
        ev += [{"kind": "silence", "t0": 0.55, "t1": 0.65, "targets": [int(gen[0])]},
               {"kind": "kick", "t": 0.66, "delta": {int(gen[1]): 1.5}},
               {"kind": "param", "t0": 0.2, "t1": 0.4, "targets": {int(gen[0]): {"tau": 0.6, "gain": 0.8}}}]
    if rel:
        ev += [{"kind": "kick", "t": 0.31, "delta": {int(rel[0]): 0.5}},
               {"kind": "silence", "t0": 0.45, "t1": 0.52, "targets": [int(rel[-1])]}]
    return ev


@pytest.mark.parametrize("t", [2, 9, 13, 15, 20, 21, 25])
def test_fast_integrator_equals_bruteforce(by_type, t):
    s = by_type[t][0]
    for wn, pn in [(None, None), ({"sd": 0.1, "seed": 4}, {"sd": 0.05, "seed": 9})]:
        q = P.validate(s.base_protocol(t_end=1.0, params_seed=3, events=_mixed_events(s), weight_noise=wn, process_noise=pn),
                       allow_truth=True)
        d = s._draw(3, 1.0, q["weight_noise"])
        out = fast_sim(s.spec, d, q, full=True, process_noise=q["process_noise"])
        ref = simulate_reference(s.spec, d, q, process_noise=q["process_noise"])
        assert out["info"]["success"]
        assert np.abs(out["state"][:, :s.n_units] - ref).max() <= 1e-10 * np.abs(ref).max()


def test_step_self_convergence(suite):
    """Addendum 1 (review item 9; review v3.3 C1, C2): halving the internal step changes y by less than STEP_TOL x the readout floor
    (0.05 sd(y)) over the full default duration, for EVERY system at params_spread 1, 1.5 and 2 (the benchmark's nominal, OOD and
    robustness spreads) under three protocols: plain (a 3 m_s kick and a 3 m_c pulse), extreme (plus tau factor 0.1 and gain 1.9
    on a core unit for 0.4 s, overlapping both; bound STEP_TOL_EXTREME) and kick.hi (plus kicks of +9 m_s and -9 m_s at 0.5 s and
    1.2 s: the steps after a core kick of 2 m_s or more are refined x 8 for 100 ms; gain / tau refinement is kept 30 ms past the window); the step is independent of the output dt
    (h = dt / n_sub, h <= h_max). Scope of the bounds: spreads <= 2, kicks up to the kick.hi range (9 m_s)."""
    worst = {}
    for s in suite.values():
        cap = s.capability()
        tg = s.core_targets()
        mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
        ev = [{"kind": "kick", "t": 0.7, "delta": {str(tg[-1]): 3 * mk}},
              {"kind": "current", "t0": 0.8, "t1": 0.9, "targets": {str(tg[len(tg) // 2]): 3 * mc}}]
        extreme = [{"kind": "param", "t0": 0.6, "t1": 1.0, "targets": {str(tg[0]): {"tau": 0.1, "gain": 1.9}}}]
        hi = [{"kind": "kick", "t": 0.5, "delta": {str(tg[0]): 9 * mk}}, {"kind": "kick", "t": 1.2, "delta": {str(tg[-1]): -9 * mk}}]
        for spread in (1.0, 1.5, 2.0):
            for name, evs in (("plain", ev), ("extreme", ev + extreme), ("kickhi", ev + hi)):
                p = s.base_protocol(params_seed=2, params_spread=spread, events=evs)
                o1 = s.simulate(p, full=True)
                n0 = o1["info"]["n_sub"]
                assert o1["info"]["h"] <= s.spec.h_max + 1e-15
                o2 = s.simulate(p, full=True, nsub=2 * n0)
                r = float(np.abs(o1["y"] - o2["y"]).max()) / cap["readout_floor"]
                worst[f"T{s.info['type']:02d}-{s.info['variant']}-{name}-s{spread}"] = r
    print({k: f"{v:.1e}" for k, v in sorted(worst.items(), key=lambda kv: -kv[1])[:12]})
    for name in ("plain", "extreme", "kickhi"):
        v = [x for k_, x in worst.items() if f"-{name}-" in k_]
        print(f"{name}: max {max(v):.2e}, median {np.median(v):.1e}, n = {len(v)}")
    bad = {k: v for k, v in worst.items() if v >= (STEP_TOL_EXTREME if "-extreme-" in k else STEP_TOL)}
    assert not bad, bad
    # the step does not depend on the output dt: the same trajectory sampled at dt and at 2 dt agrees on the common samples
    s = one_per_type(suite)[1]
    a = s.simulate(s.base_protocol(t_end=1.0), full=True)
    b = s.simulate(s.base_protocol(t_end=1.0, dt=2 * s.dt), full=True)
    assert a["info"]["h"] == b["info"]["h"]
    np.testing.assert_allclose(a["y"][::2], b["y"], rtol=1e-12, atol=1e-12)


def test_output_step_consistency(suite):
    """dt = 2 ms (the OOD temporal-sampling shift) reproduces the 1 ms trajectory at the common samples."""
    for s in one_per_type(suite)[::2]:
        a = s.simulate(s.base_protocol(t_end=1.0))
        b = s.simulate(s.base_protocol(t_end=1.0, dt=2 * s.dt))
        sc = s.obs_scale()
        assert np.abs(a["y"][::2] - b["y"]).max() / sc["y"] < 2e-3
        assert np.abs(a["x"][::2] - b["x"]).max() / sc["x"] < 2e-3


def test_robust_under_extreme_interventions(suite):
    """Addendum 2: every system integrates stably at the benchmark's largest magnitudes - time-constant factor 0.1, gain factor 1.9,
    kicks and currents at the top of the hi ranges (9 x moderate) - on units of every role, and under far-out truth events; the
    result is finite, bounded and flagged info['success'] = True."""
    from p4synth.engine import FOL as _F, GEN as _G, RELAY as _R
    for s in suite.values():
        cap = s.capability()
        mk, mc = cap["kick"]["hi_range"][1], cap["current"]["hi_range"][1]
        tg = s.core_targets()
        u0, u1 = str(tg[0]), str(tg[-1])
        nuis = [u for u in s.targetable if s.spec.role[u] in (_F, _G, _R)]
        zs = np.asarray(s.spec.latent.z_scale)
        evs = [[{"kind": "kick", "t": 0.5, "delta": {u0: mk}}, {"kind": "kick", "t": 0.9, "delta": {u1: -mk}}],
               [{"kind": "current", "t0": 0.4, "t1": None, "targets": {u0: mc, u1: -mc}}],
               [{"kind": "silence", "t0": 0.3, "t1": None, "targets": [int(u) for u in tg[: max(3, len(tg) // 2)]]}],
               [{"kind": "param", "t0": 0.3, "t1": None, "targets": {u0: {"gain": 1.9, "tau": 0.1, "threshold": -3.0}}},
                {"kind": "param", "t0": 0.6, "t1": 1.2, "targets": {u1: {"gain": 1.9, "tau": 0.1}}}],
               [{"kind": "latent_set", "t": 0.5, "z": (4 * zs).tolist()}],
               [{"kind": "current_seq", "t0": 0.3, "seg": 5 * s.dt, "targets": {u0: [mc, -mc] * 10}}]]
        if nuis:
            v = str(nuis[0])
            evs.append([{"kind": "param", "t0": 0.2, "t1": None, "targets": {v: {"gain": 1.9, "tau": 0.1}}},
                        {"kind": "kick", "t": 0.5, "delta": {v: mk}},
                        {"kind": "current", "t0": 0.7, "t1": 0.9, "targets": {str(nuis[-1]): mc}}])
        for i, ev in enumerate(evs):
            p = s.base_protocol(params_seed=9, events=ev, weight_noise={"sd": 0.1, "seed": 1} if i % 2 else None,
                                process_noise={"sd": 0.1, "seed": 2} if i == 3 else None)
            o = s.simulate(p, full=True)
            assert o["info"]["success"], (s.info["type"], s.info["variant"], i)
            assert np.all(np.isfinite(o["state"])) and np.all(np.isfinite(o["y"])), (s.info["type"], i)
            assert np.abs(o["z"] / zs).max() < 50, (s.info["type"], i, np.abs(o["z"] / zs).max())


def test_failure_is_reported(suite):
    """Addendum 2: a non-finite integration is reported through info['success'] = False (a vector field returning NaN)."""
    import copy as _copy
    from p4synth.integrate import simulate as _sim
    s = one_per_type(suite)[0]
    d = _copy.copy(s._draw(0, 1.0, None))
    d.f = lambda z, u: [float("nan")] * len(z)
    q = P.validate(s.base_protocol(t_end=0.2), allow_truth=True)
    o = _sim(s.spec, d, q, full=True)
    assert o["info"]["success"] is False


def test_speed(suite):
    """CPU time of a default (2 s at 1 ms for most systems) nominal trajectory, one system per type."""
    ts = {}
    for s in one_per_type(suite):
        p = s.base_protocol(params_seed=3)
        s.simulate(p)
        t0 = time.process_time()
        for _ in range(3):
            s.simulate(p)
        ts[s.info["type"]] = (time.process_time() - t0) / 3 / (s.t_end_default / 2.0)
    print({t: round(v, 3) for t, v in ts.items()})
    # review round 3, B5: limits with a stated margin over the measured values (dev tier 20260926, this sandbox: median 0.107 s,
    # max 0.536 s, T20-sat with 111 observed units; reference platform, previous package: max 0.467 s): median x 1.9, max x 1.5
    assert np.median(list(ts.values())) < 0.2             # contract: about 0.2 s for a typical 2 s trajectory
    assert max(ts.values()) < 0.8                         # types 20 / 21 (k up to ~80, h = 0.5 ms), 18-subhopf (h = 0.25 ms)
