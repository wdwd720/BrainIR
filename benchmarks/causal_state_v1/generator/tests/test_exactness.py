"""Exactness of the true causal state (review items 1, 2 and 5), on EVERY dev system of every test seed.

1. Off-manifold core detail is causally inert: two microstates with equal z (s0 and s0 + w, L w = 0; w = the detail a moderate
   single-unit core kick leaves, or random detail of that size on every core unit) have bit-identical z and readout futures under
   every supported intervention kind and sequence: no event, kicks (also clipped), current pulses, sequences, persistent currents,
   silencing of the same unit, of another core unit, of a group and persistently, gain / threshold / time-constant changes
   (including the extreme window tau 0.1 and gain 1.9), core-core edge scaling, and single-target compositions (kick then
   silence of the same unit 5-25 ms later; a persistent current followed by silencing).
2. equivalent_states: same z, different core AND nuisance microstate, different observed microstate, identical readout futures.
5. Pre-event rule: an intervention is not visible at its onset sample (item == twin up to and including it) for every kind, also
   at t = 0 of a restart.
"""

import numpy as np

from conftest import const_input, f_s, mid_state, probe_protocols
from p4synth import protocol as P
from p4synth.engine import CORE, FOL, GEN, RELAY


def _kinds(s, st):
    sp = s.spec
    cap = s.capability()
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    tg = s.core_targets()
    u, v = int(tg[0]), int(tg[len(tg) // 2] if len(tg) > 1 else tg[0])
    zc = s._z_of(st)
    vh = float(sp.b[sp.loc[u]] + sp.E[sp.loc[u]] @ zc)
    ks = {"none": [],
          "kick": [{"kind": "kick", "t": 0.0, "delta": {str(u): mk}}],
          "kick_clipped": [{"kind": "kick", "t": 0.0, "delta": {str(u): float((sp.lo[u] - vh - 5.0) * s.units()["v"])}}],
          "kick_pair_late": [{"kind": "kick", "t": 0.03, "delta": {str(u): -2 * mk, str(v): mk}}],
          "pulse": [{"kind": "current", "t0": 0.0, "t1": 0.05, "targets": {str(u): 2 * mc}}],
          "seq": [{"kind": "current_seq", "t0": 0.0, "seg": 0.01, "targets": {str(u): [mc, 0, -mc, mc]}}],
          "sil_same": [{"kind": "silence", "t0": 0.0, "t1": 0.1, "targets": [u]}],
          "sil_other": [{"kind": "silence", "t0": 0.0, "t1": 0.1, "targets": [v]}],
          "sil_group_persistent": [{"kind": "silence", "t0": 0.01, "t1": None, "targets": [int(x) for x in tg[:3]]}],
          "gain_up": [{"kind": "param", "t0": 0.0, "t1": 0.1, "targets": {str(u): {"gain": 1.5}}}],
          "gain_down": [{"kind": "param", "t0": 0.0, "t1": 0.1, "targets": {str(u): {"gain": 0.5}}}],
          "threshold": [{"kind": "param", "t0": 0.0, "t1": 0.1, "targets": {str(u): {"threshold": cap["param"]["moderate"]["threshold"]}}}],
          "tau": [{"kind": "param", "t0": 0.0, "t1": 0.1, "targets": {str(u): {"tau": 0.5}}}],
          "extreme": [{"kind": "param", "t0": 0.0, "t1": 0.15, "targets": {str(u): {"tau": 0.1, "gain": 1.9}}}],
          "kick_then_silence": [{"kind": "kick", "t": 0.0, "delta": {str(u): mk}},
                                {"kind": "silence", "t0": 0.015, "t1": 0.1, "targets": [u]}],
          "persistent_current_then_silence": [{"kind": "current", "t0": 0.0, "t1": None, "targets": {str(u): mc}},
                                              {"kind": "silence", "t0": 0.05, "t1": 0.12, "targets": [u]}]}
    ce = [e for e in s.edges if sp.role[e[0]] == CORE and sp.role[e[1]] == CORE]
    if ce:
        pick = [e for e in ce if u in e] or ce
        ks["edge"] = [{"kind": "edge_scale", "t0": 0.0, "t1": 0.1, "edges": [pick[0]], "factor": 0.0}]
    return ks


def _detail_kick(s, u, mk):
    sp = s.spec
    w = np.zeros(sp.Nc)
    w[sp.loc[u]] = mk
    return w - sp.E @ (sp.L[:, sp.loc[u]] * mk)


def test_off_manifold_detail_is_causally_inert(suite):
    worst = 0.0
    for s in suite.values():
        sp = s.spec
        st = mid_state(s)
        c = sp.units_of(CORE)
        cap = s.capability()
        mk = cap["kick"]["moderate"] / s.units()["v"]           # internal units (the detail is added to the microstate)
        u = int(s.core_targets()[0])
        rng = np.random.default_rng(3)
        xi = rng.normal(0.0, 1.0, sp.Nc) * mk
        details = {"kick_detail": _detail_kick(s, u, mk), "random_detail": xi - sp.E @ (sp.L @ xi)}
        base = s.base_protocol(t_end=0.25, stimulus=const_input(s))
        kinds = _kinds(s, st)
        for dname, w in details.items():
            s1 = st.copy()
            s1[c] += w
            np.testing.assert_allclose(s.true_state(s1), s.true_state(st), atol=1e-9 * max(1.0, np.abs(s.true_state(st)).max()))
            for name, ev in kinds.items():
                if dname == "random_detail" and name not in ("none", "sil_same", "sil_other", "tau", "kick_clipped", "extreme"):
                    continue
                a = s.simulate(dict(base, events=ev), full=True, restart_state=st)
                b = s.simulate(dict(base, events=ev), full=True, restart_state=s1)
                assert np.array_equal(a["z"], b["z"]) and np.array_equal(a["y"], b["y"]), (s.info["type"], s.info["variant"], dname, name)
        # without the internal copy (units only): z = L (v_c - b) differs by rounding only; futures agree to the numerical floor
        fs = f_s(s)
        s1 = st[:sp.N].copy()
        s1[c] += details["kick_detail"]
        for name in ("sil_same", "tau", "kick_then_silence"):
            a = s.simulate(dict(base, events=kinds[name]), restart_state=st)["y"]
            b = s.simulate(dict(base, events=kinds[name]), restart_state=s1)["y"]
            worst = max(worst, float(np.abs(a - b).max()) / fs)
    print("units-only restart: max |dy| / f_s =", worst)
    assert worst < 1e-8


def test_equivalent_states_nontrivial_and_equivalent(suite):
    for s in suite.values():
        sp = s.spec
        st = mid_state(s)
        eq = s.equivalent_states(st, 2, np.random.default_rng(5))
        c = sp.units_of(CORE)
        base = s.base_protocol(t_end=0.02, stimulus=const_input(s))
        x0 = s.simulate(base, restart_state=st)["x"][0]
        nuis = np.concatenate([sp.units_of(FOL), sp.units_of(GEN), sp.units_of(RELAY)]).astype(int)
        for e in eq:
            assert np.array_equal(s._z_of(e), s._z_of(st))
            assert np.any(np.abs(e[c] - st[c]) > 1e-9)                              # off-manifold core detail (L w = 0)
            if nuis.size:
                assert np.any(np.abs(e[nuis] - st[nuis]) > 1e-6)
            x1 = s.simulate(base, restart_state=e)["x"][0]
            assert np.abs(x1 - x0).max() > 1e-3 * s.obs_scale()["x"], (s.info["type"], s.info["variant"])
        for p in probe_protocols(s, t0=0.0, horizon=0.25):
            ref = s.simulate(p, restart_state=st)["y"]
            for e in eq:
                assert np.array_equal(s.simulate(p, restart_state=e)["y"], ref), (s.info["type"], s.info["variant"], p["events"])


def test_equivalent_states_within_reachable_range(suite):
    """Review round 3, B3: truth-equivalent states carry only detail that interventions actually leave. For every system, the
    observed x of equivalent states (4 per state, from states at 0.3 / 0.5 / 0.8 t_end) lies within the per-unit range of reachable
    trajectories (nominal and input-scaled 0.6 / 1.4 trajectories, +-3 m_s kicks on every targetable core unit, 3-unit group kicks
    of 3 m_s, 3 m_c pulses and silencing on core targets, and the pool states) widened by 0.5 obs_scale.x (the stated tolerance: the detail of an
    equivalent state sits at the original z, a combination real kicks reach only approximately); the largest |x_eq - x| / obs_scale.x is
    reported (review round 3: up to 6,441 before)."""
    worst, worst_out = {}, 0.0
    for s in suite.values():
        cap = s.capability()
        mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
        ox = s.obs_scale()["x"]
        tg = s.core_targets()
        rng = np.random.default_rng(11)
        protos = [s.base_protocol(), s.base_protocol(stimulus=s.nominal_stimulus(0.6)), s.base_protocol(stimulus=s.nominal_stimulus(1.4))]
        for i in range(8):
            u = [str(x) for x in rng.choice(tg, size=min(3, len(tg)), replace=False)]
            sg = float(rng.choice([-1.0, 1.0]))
            t = round(float(rng.uniform(0.3, 1.2)), 3)
            ev = [[{"kind": "kick", "t": t, "delta": {u[0]: sg * 3 * mk}}],
                  [{"kind": "kick", "t": t, "delta": {a: float(rng.choice([-1.0, 1.0])) * 3 * mk for a in u}}],
                  [{"kind": "current", "t0": t, "t1": t + 0.05, "targets": {u[0]: sg * 3 * mc}}],
                  [{"kind": "silence", "t0": t, "t1": t + 0.1, "targets": [int(u[0])]}]][i % 4]
            protos.append(s.base_protocol(events=ev))
        Xs = [s.simulate(p)["x"] for p in protos]
        o = s.simulate(s.base_protocol(), full=True)
        base = s.base_protocol(t_end=0.01, stimulus=const_input(s))
        short = s.base_protocol(t_end=0.05, stimulus=const_input(s))
        for f in (0.3, 0.5, 0.8):                  # +-3 m_s kicks on EVERY targetable core unit (what an intervention can leave)
            st = o["state"][int(f * (o["state"].shape[0] - 1))]
            for u in tg:
                for sg in (1.0, -1.0):
                    Xs.append(s.simulate(dict(short, events=[{"kind": "kick", "t": 0.0, "delta": {str(u): sg * 3 * mk}}]),
                                         restart_state=st)["x"])
        # the pool states whose nuisance units equivalent states borrow are themselves states of reachable trajectories
        s.equivalent_states(o["state"][100], 1, np.random.default_rng(0))
        for p in (getattr(s, "_eq_pool", None) or []):
            Xs.append(s.simulate(base, restart_state=p)["x"][:1])
        X = np.vstack(Xs)
        lo, hi = X.min(axis=0) - 0.5 * ox, X.max(axis=0) + 0.5 * ox
        dmax, out = 0.0, 0.0
        for f in (0.3, 0.5, 0.8):
            st = o["state"][int(f * (o["state"].shape[0] - 1))]
            x0 = s.simulate(base, restart_state=st)["x"][0]
            for e in s.equivalent_states(st, 4, np.random.default_rng(int(f * 10))):
                x1 = s.simulate(base, restart_state=e)["x"][0]
                dmax = max(dmax, float(np.abs(x1 - x0).max()) / ox)
                out = max(out, float(np.max(np.maximum(lo - x1, x1 - hi))) / ox)
        worst[f"T{s.info['type']:02d}-{s.info['variant']}"] = dmax
        worst_out = max(worst_out, out)
        assert out <= 0.0, (s.info["type"], s.info["variant"], out)
    v = np.array(list(worst.values()))
    print(f"equivalent states: max |x_eq - x| / obs_scale.x median {np.median(v):.2f}, max {v.max():.2f} "
          f"({max(worst, key=worst.get)}); > 10 x obs_scale in {int(np.sum(v > 10))} / {v.size} systems; largest excursion beyond the "
          f"reachable range {worst_out:.3f} obs_scale")


def test_moderate_kicks_do_not_clip(suite):
    """Review item 11: 'moderate' is non-saturating over the reachable state range: at 20 pool states per system (nominal,
    input-scaled and post-intervention trajectories), moderate kicks of either sign on every targetable unit stay inside the
    admissible range (core units: on their on-manifold potential, where the range acts). The clipping rates of the strong (3 m_s)
    and kick.hi (9 m_s) classes are reported per system."""
    rates = {}
    for s in suite.values():
        sp = s.spec
        mk = s.capability()["kick"]["moderate"] / s.units()["v"]     # internal units, like the unit potentials and the range
        cnt = {1: [0, 0], 3: [0, 0], 9: [0, 0]}
        for st in s.pool_states(20, np.random.default_rng(4)):
            z = s._z_of(st)
            for u in s.targetable:
                v = float(sp.b[sp.loc[u]] + sp.E[sp.loc[u]] @ z) if sp.role[u] == CORE else float(st[u])
                for m in (1, 3, 9):
                    for sg in (1.0, -1.0):
                        cnt[m][0] += 1
                        cnt[m][1] += int(not sp.lo[u] <= v + sg * m * mk <= sp.hi[u])
        assert cnt[1][1] == 0, (s.info["type"], s.info["variant"], cnt[1])
        rates[f"T{s.info['type']:02d}-{s.info['variant']}"] = (cnt[3][1] / cnt[3][0], cnt[9][1] / cnt[9][0])
    r3 = np.array([a for a, _ in rates.values()])
    r9 = np.array([b for _, b in rates.values()])
    print(f"clipping at pool states: moderate 0 everywhere; strong (3 m_s): {np.mean(r3 > 0):.2f} of the systems clip, max rate "
          f"{r3.max():.2f}; kick.hi (9 m_s): median rate {np.median(r9):.2f}, max {r9.max():.2f}",
          {k: v for k, v in rates.items() if v[0] > 0})


def _onset_kinds(s, t0):
    sp = s.spec
    cap = s.capability()
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    tg = s.core_targets()
    u, v = str(tg[0]), str(tg[-1])
    ks = {"kick": [{"kind": "kick", "t": t0, "delta": {u: 3 * mk}}],
          "pulse": [{"kind": "current", "t0": t0, "t1": t0 + 0.05, "targets": {u: 3 * mc}}],
          "seq": [{"kind": "current_seq", "t0": t0, "seg": 0.01, "targets": {u: [3 * mc, -3 * mc]}}],
          "sil.1": [{"kind": "silence", "t0": t0, "t1": t0 + 0.1, "targets": [int(u)]}],
          "sil.2": [{"kind": "silence", "t0": t0, "t1": t0 + 0.1, "targets": sorted({int(u), int(v)})}],
          "param.gain": [{"kind": "param", "t0": t0, "t1": t0 + 0.1, "targets": {u: {"gain": 1.9}}}],
          "param.threshold": [{"kind": "param", "t0": t0, "t1": t0 + 0.1, "targets": {u: {"threshold": 3.0}}}],
          "param.tau": [{"kind": "param", "t0": t0, "t1": t0 + 0.1, "targets": {u: {"tau": 0.1}}}],
          "latent_kick": [{"kind": "latent_kick", "t": t0, "dz": (0.5 * np.asarray(sp.latent.z_scale)).tolist()}]}
    ce = [e for e in s.edges if sp.role[e[0]] == CORE and sp.role[e[1]] == CORE]
    if ce:
        ks["edge.core"] = [{"kind": "edge_scale", "t0": t0, "t1": t0 + 0.1, "edges": [ce[0]], "factor": 0.0}]
    nuis = [x for x in s.targetable if sp.role[x] != CORE]
    if nuis:
        w = str(nuis[0])
        ks["nuisance.param"] = [{"kind": "param", "t0": t0, "t1": t0 + 0.1, "targets": {w: {"gain": 1.9, "threshold": 2.0}}}]
        ks["nuisance.silence"] = [{"kind": "silence", "t0": t0, "t1": t0 + 0.1, "targets": [int(w)]}]
    return ks


def test_no_event_visible_at_its_onset_sample(suite):
    """Item == twin (x, y, microstate) up to and including the onset sample, for every kind; from rest (onset 0.4 s) and at t = 0 of
    a restart (the lift / pool situation)."""
    changed = {}
    for s in suite.values():
        st = mid_state(s)
        for t0, kw in ((0.4, {}), (0.0, {"restart_state": st})):
            base = s.base_protocol(params_seed=3, t_end=0.55, stimulus=const_input(s) if kw else s.nominal_stimulus())
            tw = s.simulate(base, full=True, **kw)
            j = int(round(t0 / s.dt))
            for name, ev in _onset_kinds(s, t0).items():
                o = s.simulate(P.validate(dict(base, events=ev), allow_truth=True), full=True, **kw)
                for key in ("x", "y", "state"):
                    assert np.array_equal(o[key][:j + 1], tw[key][:j + 1]), (s.info["type"], s.info["variant"], t0, name, key)
                changed[name] = changed.get(name, 0) + int(not np.array_equal(o["state"][j + 1:], tw["state"][j + 1:]))
    # every kind acts after its onset sample
    assert all(v > 0 for v in changed.values()), changed
