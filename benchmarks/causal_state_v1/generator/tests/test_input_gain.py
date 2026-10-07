"""Supralinear input responses (calibration targets v3): input_gain_elasticity_y computed with
ref/calibstats on the event-free nominal and stimulus records of the calibration design over the capability's input range."""

import numpy as np

from conftest import const_input, one_per_type
from p4synth import protocol as P
from p4synth.calib import calibration_protocols
from p4synth.latents import input_gain_factor
from ref import calibstats as CS


def _elasticity(s):
    recs = []
    for p, meta in calibration_protocols(s, n_int=0):
        if meta["kind"] not in ("obs.nominal", "obs.stim"):
            continue
        q = P.validate(p)
        o = s.simulate(q)
        recs.append({"t": o["t"], "x": o["x"], "u": o["u"], "y": o["y"], "protocol": q, "key": str(len(recs)), "meta": {}})
    g = CS.stats_input_gain(recs, CS.system_scales(recs))
    return g["input_gain_elasticity_y"], g["input_scale_min"], g["input_scale_max"]


def test_input_gain_factor_is_one_at_nominal():
    U = np.array([[0.0], [0.6], [1.0], [1.4]])
    g = input_gain_factor(U, 2.5, 0.25)
    assert abs(g[2] - 1.0) < 1e-12 and g[0] < 1e-3 and np.all(np.diff(g) > 0)
    # two-channel inputs use the mean channel: nominal [1, 1] -> 1
    assert abs(input_gain_factor(np.array([[1.0, 1.0]]), 2.5, 0.25)[0] - 1.0) < 1e-12


def test_readout_elasticity_suite(suite):
    vals = {}
    for sid, s in suite.items():
        e, lo, hi = _elasticity(s)
        cap = s.capability()["stimulus"]["range"]
        assert cap[0] - 1e-9 <= lo and hi <= cap[1] * max(1, np.sqrt(s.input_dim)) + 1e-9     # the declared range is unchanged
        vals[sid] = (s.info["type"], e)
    inside = np.mean([1.41 <= e <= 13.6 for _, e in vals.values()])
    med = float(np.median([e for _, e in vals.values()]))
    print({f"T{t:02d}": round(e, 2) for t, e in sorted(vals.values())})
    assert inside >= 0.8 and 2.5 <= med <= 6.0, (inside, med)


def test_type1_readout_stays_linear(by_type):
    for s in by_type[1]:
        ro = s.spec.latent.ro
        active = [kd for j, kd in enumerate(ro.kinds) if np.any(ro.R[j] != 0)]
        assert ro.in_gain is None and set(active) == {"lin"}
    for s in one_per_type_nonlinear(by_type):
        assert s.spec.latent.ro.in_gain is not None


def one_per_type_nonlinear(by_type):
    return [by_type[t][0] for t in sorted(by_type) if t != 1]


def test_readout_active_in_intervention_windows(suite):
    """The input-dependent readout gain makes the readout nearly silent at zero input (g(0) <= 1.3e-4). The benchmark's intervention
    windows (onsets in [0.15, 0.5] of the trajectory) lie after the default stimulus onset (0.1 s, nominal input 1.0), and every
    input level of the capability's range keeps g >= 0.1: the readout varies by more than the effect floor inside the windows."""
    for s in suite.values():
        ro = s.spec.latent.ro
        cap = s.capability()
        lo, hi = cap["stimulus"]["range"]
        assert 0.15 * s.t_end_default > cap["stimulus"]["max_onset"] and cap["stimulus"]["nominal"][1][0] <= 0.15 * s.t_end_default
        if ro.in_gain is not None:
            g = input_gain_factor(np.array([[lo], [1.0], [hi], [0.0]]), *ro.in_gain)
            assert g[0] >= 0.1 and abs(g[1] - 1.0) < 1e-12 and g[3] <= 1.3e-4, (s.info["type"], g)
        o = s.simulate(s.base_protocol(), full=True)
        a, b = int(0.15 * s.t_end_default / s.dt), int(0.5 * s.t_end_default / s.dt)
        fs = cap["readout_floor"]
        # at least one readout channel is well above the floor throughout the windows (the readout is active)
        assert np.all(np.max(np.abs(o["y"][a:b]), axis=1) > 2 * fs), (s.info["type"], s.info["variant"])


def test_nominal_input_behaviour_unchanged(suite):
    """g(1) = 1: at the nominal input the readout equals the un-modulated readout G(z, u)."""
    for s in one_per_type(suite)[::3]:
        o = s.simulate(s.base_protocol(t_end=0.5, stimulus=const_input(s)), full=True)
        ro = s.spec.latent.ro
        if ro.in_gain is None:
            continue
        import copy
        plain = copy.copy(ro)
        plain.in_gain = None
        d = s._draw(0, 1.0, None)
        y0 = plain(s.spec.latent.features(o["zh"], o["u"], d.P), o["u"], d.P.get("ro_gain", 1.0))
        np.testing.assert_allclose(o["y"] / s.units()["y"], y0, rtol=1e-12, atol=1e-12)     # public units
