"""Toy records with hand-derived statistics for brainir_causal.calibstats (goal5 section 8, acceptance criterion 11)."""

import json
import math

import numpy as np
import pytest

from brainir_causal import calibstats as C

DT = 0.001
T_END = 2.0
T = np.round(np.arange(0.0, T_END + DT / 2, DT), 9)
SYS = {"observed": [10, 11, 12], "targets_public": [10, 11, 12]}


def _proto(events=(), stim=((0.0, 0.0), (0.1, 1.0)), r0=None, wn=None, seed=1):
    return {"system": "toy", "params_seed": seed, "weight_noise": wn, "r0": r0 or {"kind": "rest"}, "t_end": T_END, "dt": DT,
            "stimulus": [list(s) for s in stim], "events": list(events)}


def _base(phase=0.0, amp=5.0):
    """Three rectified-positive units oscillating at 10 Hz after the input onset (0.1 s)."""
    on = (T >= 0.1).astype(float)
    x = np.stack([amp * (1.0 + np.sin(2 * np.pi * 10 * T + phase)) * on,
                  2.0 * (1.0 + np.cos(2 * np.pi * 10 * T + phase)) * on,
                  np.full_like(T, 0.5) * on], axis=1)
    y = x[:, :1] + x[:, 1:2]
    return x, y


def _rec(x, y, proto, key, meta=None):
    u = np.zeros((len(T), 1))
    for t0, s in proto["stimulus"]:
        u[T >= t0 - 1e-12, 0] = s
    return {"t": T.copy(), "x": x, "u": u, "y": y, "protocol": proto, "key": key, "meta": meta or {}}


def test_dimensionality_known_cases():
    t = np.linspace(0, 1, 1000, endpoint=False)
    X2 = np.stack([np.sin(2 * np.pi * 3 * t), np.cos(2 * np.pi * 3 * t)], axis=1)
    d = C.dimensionality(X2)
    assert d["pr"] == pytest.approx(2.0, rel=1e-3) and d["n90"] == 2 and d["n99"] == 2
    X1 = np.stack([np.sin(2 * np.pi * 3 * t), 2 * np.sin(2 * np.pi * 3 * t), np.zeros_like(t)], axis=1)
    d = C.dimensionality(X1)
    assert d["pr"] == pytest.approx(1.0, rel=1e-9) and d["n95"] == 1


def test_acf_and_spectrum_of_a_sinusoid():
    x = np.sin(2 * np.pi * 10 * T)[:, None]
    tau, cens = C.acf_decay(x, DT)
    expect = math.acos(1 / math.e) / (2 * math.pi * 10)          # cos(2 pi f tau) = 1/e for a pure sinusoid
    assert not cens[0] and tau[0] == pytest.approx(expect, abs=0.0015)
    sp = C.spectrum_stats(x, DT)
    assert sp["f_peak"] == pytest.approx(10.0, abs=1.0) and sp["prominence_log10"] > 1.0


def test_decay_time_of_an_exponential():
    t = np.arange(0, 0.5, DT)
    tau, cens = C.decay_time(3.0 * np.exp(-t / 0.03), DT)
    assert not cens and tau == pytest.approx(0.03, abs=DT)
    tau, cens = C.decay_time(np.ones(100), DT)
    assert cens


def test_record_kinds():
    x, y = _base()
    assert C.record_kind(_rec(x, y, _proto(), "a")) == "obs:nominal"
    assert C.record_kind(_rec(x, y, _proto(stim=((0.0, 0.0), (0.1, 1.3))), "b")) == "obs:stim"
    assert C.record_kind(_rec(x, y, _proto(r0={"kind": "state", "values": {"10": 1.0}}), "c")) == "obs:init"
    assert C.record_kind(_rec(x, y, _proto(wn={"sd": 0.05, "seed": 3}), "d")) == "obs:wnoise"
    ev = [{"kind": "kick", "t": 1.0, "delta": {"11": 4.0}}]
    assert C.record_kind(_rec(x, y, _proto(ev), "e")) == "int:kick"
    ev2 = ev + [{"kind": "silence", "t0": 1.5, "t1": None, "targets": [10]}]
    assert C.record_kind(_rec(x, y, _proto(ev2), "f")) == "int:mixed"


def _kick_pair(delta, key, tau=0.03, t_k=1.0, unit=11, col=1):
    x, y = _base()
    ev = [{"kind": "kick", "t": t_k, "delta": {str(unit): delta}}]
    xi = x.copy()
    k = int(round(t_k / DT))
    pre = xi[k, col]
    applied = delta if pre + delta >= 0 else -pre
    tt = T[k + 1:] - T[k + 1]
    xi[k + 1:, col] += applied * np.exp(-tt / tau)
    yi = xi[:, :1] + xi[:, 1:2]
    ri = _rec(xi, yi, _proto(ev), key)
    rt = _rec(x, y, _proto(), key + "_twin", meta={"twin_of": key})
    return ri, rt


def test_pair_statistics_of_a_single_kick():
    ri, rt = _kick_pair(3.0, "k1")
    pairs = C.pair_twins([ri, rt])
    assert len(pairs) == 1 and pairs[0][0] is ri
    sc = C.system_scales([ri, rt])
    ps = C._pair_stats(ri, rt, SYS, sc, C._col_of(SYS))
    assert ps["pre_event_maxabs"] == 0.0
    assert ps["resp_frac_1pct"] == 0.0                               # only the kicked unit changes
    assert ps["self_decay_s"] == pytest.approx(0.03, abs=2 * DT)
    assert ps["decay_x_s"] == pytest.approx(0.03, abs=2 * DT)
    assert ps["kick_clipped"] is False
    assert ps["latency_y_peak_s"] == pytest.approx(DT, abs=DT)       # the readout effect peaks right after the kick


def test_step_schedule_drops_only_no_op_breakpoints():
    assert C.step_schedule([[0.0, 0.0], [0.1, 1.0], [0.7, 1.0], [0.9, 1.0]]) == [[0.0, 0.0], [0.1, 1.0]]
    assert C.step_schedule([[0.1, 1.0], [0.0, 0.0], [0.5, 2.0]]) == [[0.0, 0.0], [0.1, 1.0], [0.5, 2.0]]   # sorted, real steps kept
    assert C.step_schedule([[0.0, [0.0, 1.0]], [0.3, [0.0, 1.0]], [0.4, [1.0, 1.0]]]) == [[0.0, [0.0, 1.0]], [0.4, [1.0, 1.0]]]
    assert C.step_schedule(None) == []


def test_twins_with_no_op_breakpoints_are_paired_and_read_as_nominal():
    """A counterfactual twin that keeps its item's integration pieces carries no-op stimulus breakpoints at the event times."""
    ri, rt = _kick_pair(3.0, "k3")
    rt["protocol"] = {**rt["protocol"], "stimulus": [[0.0, 0.0], [0.1, 1.0], [1.0, 1.0]]}
    pairs = C.pair_twins([ri, rt])
    assert len(pairs) == 1 and pairs[0] == (ri, rt)
    assert C.record_kind(rt) == "obs:nominal"
    assert C._stim_onset_and_scale(rt) == (0.1, 1.0, T_END)          # the input segment does not end at the no-op breakpoint
    # a real change of the input is still a different protocol: no pair
    rt2 = {**rt, "protocol": {**rt["protocol"], "stimulus": [[0.0, 0.0], [0.1, 1.0], [1.0, 1.2]]}}
    assert C.pair_twins([ri, rt2]) == []
    assert C.record_kind(rt2) == "obs:stim"
    st = C.compute_all([ri, rt], SYS)
    assert st["counts"]["n_pairs"] == 1 and st["counts"]["record_kinds"] == {"int:kick": 1, "obs:nominal": 1}


def test_load_dataset_dir(tmp_path):
    recs = []
    for i in range(5):
        x, y = _base(phase=0.1 * i)
        recs.append(_rec(x, y, _proto(seed=i), f"n{i}"))
    ri, rt = _kick_pair(3.0, "k1")
    rt["protocol"] = {**rt["protocol"], "stimulus": [[0.0, 0.0], [0.1, 1.0], [1.0, 1.0]]}
    recs += [ri, rt]
    (tmp_path / "traj").mkdir()
    rows = []
    for r in recs:
        np.savez_compressed(tmp_path / "traj" / f"{r['key']}.npz", t=r["t"], x=r["x"].astype(np.float32), u=r["u"].astype(np.float32),
                            y=r["y"].astype(np.float32))
        rows.append({"key": r["key"], "system_id": "toy", "split": "train", "family": "f", "protocol": r["protocol"], "meta": r["meta"],
                     "info": {}})
    (tmp_path / "index.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"format": "p4-dataset-1", "systems": {"toy": SYS}}), encoding="utf-8")
    sysrec, got = C.load_dataset_dir(tmp_path)
    assert sysrec == SYS and len(got) == 7 and got[0]["x"].dtype == np.float32
    assert len(C.pair_twins(got)) == 1
    _, capped = C.load_dataset_dir(tmp_path, max_per_kind=2)
    kinds = [C.record_kind(r) for r in capped]
    assert kinds.count("obs:nominal") == 3 and kinds.count("int:kick") == 1     # 2 nominal records + the kept item's twin
    assert len(C.pair_twins(capped)) == 1


def test_every_statistic_has_a_definition_and_a_dependence_class():
    recs = []
    for i in range(4):
        x, y = _base(phase=0.3 * i)
        recs.append(_rec(x, y, _proto(seed=i), f"n{i}"))
    ri, rt = _kick_pair(3.0, "k1")
    st = C.compute_all(recs + [ri, rt], SYS)
    for k in st:
        if k in ("stat_version", "counts"):
            continue
        assert C.describe(k), k
        cls, why = C.dependence(k)
        assert cls in C.DEPENDENCE_CLASSES and why != "not classified", k
    assert C.dependence("spec_x_f_peak")[0] == "system" and C.dependence("eff_rel_y_p50")[0] == "design"
    assert C.dependence("effect_energy_outside_passive95")[0] == "mixed" and C.dependence("decay_x_censored_frac")[0] == "mixed"


def test_initial_states_that_end_in_another_persistent_state():
    recs = []
    for i in range(3):
        x, y = _base(phase=0.2 * i)
        recs.append(_rec(x, y, _proto(seed=i), f"n{i}"))
    x, y = _base()
    relax = _rec(x, y, _proto(r0={"kind": "state", "values": {"10": 9.0}}, seed=5), "i0")        # relaxes to the nominal behaviour
    high = _rec(x * 10.0, y * 10.0, _proto(r0={"kind": "state", "values": {"10": 200.0}}, seed=6), "i1")   # stays 10x higher
    sc = C.system_scales(recs + [relax, high])
    st = C.stats_init_states(recs + [relax, high], sc)
    assert st["init_high_state_frac_x"] == 0.5 and st["init_high_state_frac_y"] == 0.5
    assert st["init_late_rms_ratio_x_median"] == pytest.approx((1.0 + 10.0) / 2, rel=0.05)
    assert C.dependence("init_high_state_frac_x")[0] == "mixed" and C.describe("init_high_state_frac_x")


def test_negative_kick_on_a_unit_at_rest_is_clipped():
    # unit 12 (column 2) sits at 0.5 after the onset; a kick of -2 is clipped to -0.5
    ri, rt = _kick_pair(-2.0, "k2", unit=12, col=2)
    out = C.stats_kick_clipping([ri, rt], SYS)
    assert out["kick_clipped_frac_all"] == 1.0 and out["kick_clipped_frac_of_negative"] == 1.0


def test_input_gain_elasticity_of_a_square_law():
    recs = []
    for i, s in enumerate((0.6, 0.8, 1.0, 1.2, 1.4)):
        x, y = _base()
        x = x * s ** 2
        y = y * s ** 2
        recs.append(_rec(x, y, _proto(stim=((0.0, 0.0), (0.1, s))), f"s{i}"))
    sc = C.system_scales(recs)
    g = C.stats_input_gain(recs, sc)
    assert g["input_gain_elasticity_x"] == pytest.approx(2.0, abs=1e-6)
    assert g["input_scale_min"] == 0.6 and g["input_scale_max"] == 1.4


def test_compute_all_end_to_end_and_compare():
    recs = []
    for i in range(4):
        x, y = _base(phase=0.3 * i)
        recs.append(_rec(x, y, _proto(seed=i), f"n{i}"))
    ri, rt = _kick_pair(3.0, "k1")
    recs += [ri, rt]
    st = C.compute_all(recs, SYS)
    assert st["n_obs"] == 3 and st["counts"]["n_pairs"] == 1
    assert st["spec_x_f_peak"] == pytest.approx(10.0, abs=1.0)
    assert st["params_param_spread_x_rel_level"] > 0          # phases differ across the draws
    assert all(C.describe(k) for k in st if k not in ("stat_version", "counts"))
    targets = {"n_obs": {"target_range": [2, 10], "check": True, "real_all": {"min": 3, "max": 200}, "coverage": [6, 100]},
               "spec_x_f_peak": {"target_range": [5, 20], "check": True, "real_all": {"min": 7, "max": 17}},
               "s_x": {"target_range": [0, 1], "check": False}}
    rep = C.compare({"a": st, "b": st}, targets)
    assert rep["n_tested"] == 2
    assert rep["statistics"]["spec_x_f_peak"]["ok"] is True
    assert rep["statistics"]["n_obs"]["coverage_ok"] is False and rep["statistics"]["n_obs"]["ok"] is False
    table = C.pool({"a": st, "b": st}, {"a": "full", "b": "mechanism"})
    assert table["n_obs"]["all"]["n"] == 2 and table["n_obs"]["full"]["min"] == 3
