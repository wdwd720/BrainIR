"""Realized kick sizes (addition B): the FULL (truth-side) simulate output reports, for every requested kick event, the realized
offset of every kicked unit after the admissible-range clipping (core units: clipped on their on-manifold potential), in the
order of the canonical protocol (the order the kicks are applied in; each entry carries its event_index and the requested
offsets); public outputs do not carry it. Checked on every dev system of every test seed: one entry per kick event with its units
and requested offsets, unclipped kicks realize their request exactly, clipped kicks are smaller with the same sign, several kicks
at one sample chain (each sees the previous ones: the floor kick puts the unit's on-manifold potential exactly on the floor), and
replaying the realized offsets reproduces the trajectory."""

import numpy as np

from conftest import const_input, mid_state
from p4synth import protocol as P
from p4synth.engine import CORE


def _protocol(s):
    sp = s.spec
    mk = s.capability()["kick"]["moderate"]
    tg = s.core_targets()
    u, v = str(tg[0]), str(tg[-1])
    nuis = [x for x in s.targetable if sp.role[x] != CORE]
    e1 = {u: mk}
    if nuis:
        e1[str(nuis[0])] = -mk
    evs = [{"kind": "kick", "t": 0.01, "delta": e1},
           {"kind": "kick", "t": 0.01, "delta": {u: -1e4}},                     # same sample: clipped at the floor
           {"kind": "kick", "t": 0.05, "delta": {v: 3 * mk, u: 1e4}},          # u clipped at the ceiling
           {"kind": "kick", "t": 0.099, "delta": {u: mk}}]                     # the last integrated step
    if nuis:
        evs.append({"kind": "kick", "t": 0.07, "delta": {str(nuis[-1]): -1e4}})
    return s.base_protocol(t_end=0.1, stimulus=const_input(s), events=evs), int(u)


def test_kicks_applied_reports_realized_offsets(suite):
    n_clip = n_sys = 0
    for s in suite.values():
        sp = s.spec
        st = mid_state(s)
        p, u = _protocol(s)
        o = s.simulate(p, full=True, restart_state=st)
        ka = o["info"]["kicks_applied"]
        assert "kicks_applied" not in s.simulate(p, restart_state=st)["info"]
        q = P.validate(p)
        kicks = [(j, e) for j, e in enumerate(q["events"]) if e["kind"] == "kick"]
        assert len(ka) == len(kicks) == sum(e["kind"] == "kick" for e in p["events"])
        for (j, e), r in zip(kicks, ka):
            assert r["event_index"] == j and abs(r["t"] - e["t"]) < 1e-12
            assert r["requested"] == {int(a): float(d) for a, d in e["delta"].items()} and sorted(r["units"]) == sorted(r["requested"])
            for a, d in r["requested"].items():
                got = r["units"][a]
                if abs(d) >= 1e3:                                            # clipped: smaller, same sign (or 0)
                    assert abs(got) < abs(d) and got * d >= 0
                    n_clip += 1
        # the kicks at 0.01 s chain in canonical order; unclipped ones realize their request exactly, the floor kick puts the
        # on-manifold potential of u (after the kicks before it) exactly on the floor
        c = sp.loc[u]
        n1 = int(round(0.01 / s.dt))
        z = o["z"][n1].copy()
        sv = s.units()["v"]                          # realized offsets are public; the model's potentials are internal
        for r in (r for r in ka if abs(r["t"] - 0.01) < 1e-12):
            for a, d in r["requested"].items():
                if abs(d) < 1e3:
                    assert abs(r["units"][a] - d) <= 1e-12 * max(1.0, abs(sp.lo[u] * sv))    # (v + d) - v: rounding only
                else:
                    vh = float(sp.b[c] + sp.E[c] @ z)
                    assert abs(vh + r["units"][a] / sv - sp.lo[u]) <= 1e-9 * max(1.0, abs(sp.lo[u]))
                if sp.role[a] == CORE:
                    z = z + sp.L[:, sp.loc[a]] * r["units"][a] / sv
        # replay with the realized offsets (no clipping left) reproduces the trajectory
        rep = dict(p, events=[{"kind": "kick", "t": r["t"], "delta": {str(a): float(x) for a, x in r["units"].items()}} for r in ka])
        o2 = s.simulate(rep, full=True, restart_state=st)
        scale = s.obs_scale()
        assert np.abs(o2["y"] - o["y"]).max() <= 1e-9 * scale["y"]
        assert np.abs(o2["x"] - o["x"]).max() <= 1e-9 * scale["x"]
        assert np.abs(o2["z"] - o["z"]).max() <= 1e-9 * max(1.0, float(np.abs(o["z"]).max()))
        n_sys += 1
    print(f"kicks_applied: {n_sys} systems, {n_clip} clipped kick offsets reported (each smaller than requested, same sign)")
