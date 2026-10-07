"""Review v3.3 (N7): every published intervention kind and parameter field has an HONEST moderate magnitude.

On every dev system of every test seed, from the mid-trajectory state (nominal draw and input), the readout detectability
ES = RMS(y_int - y_twin) / (0.05 sd(y)) over the primary horizon (12.5 % of t_end) of the PUBLISHED moderate magnitude, both signs,
on EVERY targetable core unit (the population the benchmark draws core items from; the capability probe uses the same
definition): kick (instantaneous), current (a pulse of moderate_reference_duration), every published param field (a window of
moderate_reference_duration). The median ES lies in [3, 10). Reported, not asserted: the same at a second state (0.35 t_end),
and the ES of silencing (no magnitude). Kinds / fields that are not published are the SAME for every system (a per-system
support flag would be a public field): param fields = ["threshold"], edge_scale unsupported."""

import numpy as np

from p4synth import protocol as P

LO, HI = 3.0, 10.0


def _es(s, st, twin, base, fs, evs):
    vals = []
    for ev in evs:
        y = s.simulate(dict(base, events=[ev]), restart_state=st)["y"]
        vals.append(float(np.sqrt(np.mean((y - twin) ** 2))) / fs)
    return float(np.median(vals)) if vals else float("nan")


def _events(kind, cap, units):
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    out = []
    for u in units:
        for sg in (1.0, -1.0):
            if kind == "kick":
                out.append({"kind": "kick", "t": 0.0, "delta": {str(u): sg * mk}})
            elif kind == "current":
                out.append({"kind": "current", "t0": 0.0, "t1": cap["current"]["moderate_reference_duration"],
                            "targets": {str(u): sg * mc}})
            elif kind == "silence":
                if sg > 0:
                    out.append({"kind": "silence", "t0": 0.0, "t1": cap["param"]["moderate_reference_duration"], "targets": [int(u)]})
            else:                                   # a param field
                m = cap["param"]["moderate"][kind]
                val = sg * m if kind == "threshold" else 1.0 + sg * m
                out.append({"kind": "param", "t0": 0.0, "t1": cap["param"]["moderate_reference_duration"],
                            "targets": {str(u): {kind: val}}})
    return out


def test_published_moderates_are_in_the_moderate_detectability_class(suite):
    rows, published = {}, set()
    for s in suite.values():
        cap = s.capability()
        published.add((tuple(cap["param"]["fields"]), cap["edge_scale"]["supported"], cap["param"]["supported"]))
        o = s.simulate(s.base_protocol(), full=True)
        fs = 0.05 * float(np.sqrt(np.mean(np.var(o["y"], axis=0))))
        H = P.snap(0.125 * s.t_end_default, s.dt)
        base = s.base_protocol(t_end=H, stimulus=[[0.0, [1.0] * s.input_dim if s.input_dim > 1 else 1.0]])
        tg = s.core_targets()
        r = {}
        for f, key in ((0.5, "mid"), (0.35, "second")):
            st = o["state"][int(round(f * s.t_end_default / s.dt))]
            twin = s.simulate(base, restart_state=st)["y"]
            for kind in ["kick", "current"] + list(cap["param"]["fields"]) + ["silence"]:
                r[(kind, key)] = _es(s, st, twin, base, fs, _events(kind, cap, tg))
        rows[f"T{s.info['type']:02d}-{s.info['variant']}"] = r
    kinds = sorted({k for r in rows.values() for k, _ in r})
    for k in kinds:
        for key in ("mid", "second"):
            a = np.array([r[(k, key)] for r in rows.values() if (k, key) in r])
            print(f"{k:10s} {key:6s} state: median ES {np.median(a):.2f} [{a.min():.2f}, {a.max():.2f}], "
                  f"outside [3, 10): {int(np.sum((a < LO) | (a >= HI)))} / {a.size}")
    assert len(published) == 1 and published == {(("threshold",), False, True)}, published
    for lab, r in rows.items():
        for (k, key), v in r.items():
            if k != "silence" and key == "mid":
                assert LO <= v < HI, (lab, k, v)
