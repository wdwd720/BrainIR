"""Generic calibration statistics of simulated neural systems (goal5 section 8; acceptance criterion 11).

The same functions describe any system from its trajectory RECORDS, so the synthetic suite can be checked against targets
computed from PUBLIC real data without touching any hidden data or any system identity:

    sysrec, records = load_dataset_dir(d)         # one system of a dataset directory (manifest.json, index.jsonl, traj/)
    stats = compute_all(records, sysrec)          # one system -> flat dict {statistic: value}
    table = pool({label: stats}, {label: cls})    # per-system values + pooled / per-class summaries
    report = compare(suite_stats, targets)        # a (synthetic) suite against the frozen targets
    describe(name), dependence(name)              # definition; 'system' / 'design' / 'mixed' (what the value depends on)

Statistics marked 'design' or 'mixed' depend on the experimental design (intervention magnitudes, onsets, initial states, input
schedules), so targets are comparable only with data built by the same design. Input schedules are always read without no-op
breakpoints (`step_schedule`).

A RECORD is a dict: ``t`` (T,), ``x`` (T, N_obs) observed microstate, ``u`` (T, n_u) exogenous input, ``y`` (T, n_y) readout,
``protocol`` (``events``, ``stimulus``, ``r0``, ``params_seed``, ``weight_noise``, ``dt``, ``t_end``), and optionally ``family``,
``split``, ``key``, ``meta`` (``twin_of``: key of the intervention trajectory whose counterfactual twin this record is) or
``info`` (``pair``: a label shared by an intervention trajectory and its twin within one system). The columns of ``x`` follow
``sysrec["observed"]`` (unit ids); event targets are unit ids. Events follow protocol v1 / v2 (kick, current, current_seq,
silence, edge_scale, param); an instantaneous event at time t acts after the sample at t.

Everything here is descriptive (numpy / scipy only). Statistics that need interventions use (intervention, twin) pairs: the twin
has the same parameters, initial state, noise and input, and no events, so ``x_int - x_twin`` is the causal effect of the events.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
from scipy import signal

STAT_VERSION = "p4-calibstats-2"     # 2: input schedules read without no-op breakpoints (pairing, record kinds); dataset loader

# ------------------------------------------------------------------------------------------------------------------ constants
ACTIVE_REL = 1e-3            # a unit is active when its temporal sd exceeds ACTIVE_REL x the system scale s_x
RESP_THRESHOLDS = (0.01, 0.10)   # response sparsity: max |effect| of a unit above this fraction of s_x
FLOOR_REL = 1e-6             # a sample is "at the floor" when x - min_unit <= FLOOR_REL x s_x (rectified units sit at 0)
NEAR_MAX_REL = 0.9           # "near the maximum": x >= 0.9 x the unit's own (or the system's) maximum
F32_EPS = float(np.finfo(np.float32).eps)
MAX_RECORDS_PER_KIND = 40    # per-trajectory statistics use at most this many records of each kind (evenly spaced)
POOL_STRIDE_S = 0.005        # temporal sub-sampling for pooled PCA / scales


# ------------------------------------------------------------------------------------------------------------------ helpers
def _f(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _med(vals) -> float | None:
    v = [float(a) for a in vals if a is not None and math.isfinite(float(a))]
    return float(np.median(v)) if v else None


def _pct(vals, qs=(5, 25, 50, 75, 95)) -> dict:
    v = np.asarray([float(a) for a in vals if a is not None and math.isfinite(float(a))])
    if v.size == 0:
        return {f"p{q}": None for q in qs}
    return {f"p{q}": float(np.percentile(v, q)) for q in qs}


def _events(rec: dict) -> list[dict]:
    return list((rec.get("protocol") or {}).get("events") or [])


def event_start(e: dict) -> float:
    return float(e["t"]) if "t" in e else float(e["t0"])


def event_end(e: dict, t_end: float) -> float:
    """End of the event's action (instantaneous events end at their time; t1 = None means until the end)."""
    k = e["kind"]
    if k in ("kick", "latent_set", "latent_kick"):
        return float(e["t"])
    if k == "current_seq":
        m = max((len(v) for v in (e.get("targets") or {}).values()), default=0)
        return float(e["t0"]) + float(e["seg"]) * m
    t1 = e.get("t1")
    return float(t_end) if t1 is None else float(t1)


def event_targets(e: dict) -> list[int]:
    k = e["kind"]
    if k == "kick":
        return sorted(int(n) for n in e["delta"])
    if k in ("current", "current_seq", "param"):
        return sorted(int(n) for n in e["targets"])
    if k == "silence":
        return sorted(int(n) for n in e["targets"])
    if k in ("edge_scale", "edge_remove"):
        return sorted({int(a) for ed in e["edges"] for a in ed})
    return []


def step_schedule(stim) -> list:
    """The piecewise-constant input schedule [[t, value], ...] sorted by time and WITHOUT no-op breakpoints (entries that repeat
    the value in force). A counterfactual twin may carry such breakpoints at its item's event times, because it keeps the item's
    integration pieces; they do not change the input, but compared literally they would make the twin's protocol differ from its
    item's (no pair) and turn a nominal input into an 'other schedule' (wrong record kind, wrong end of the input segment)."""
    out: list = []
    for t, v in sorted(((float(t), v) for t, v in (stim or [])), key=lambda a: a[0]):
        if out and np.array_equal(np.asarray(out[-1][1], dtype=float), np.asarray(v, dtype=float)):
            continue
        out.append([t, v])
    return out


def _stimulus(rec: dict) -> list:
    return step_schedule((rec.get("protocol") or {}).get("stimulus"))


def record_kind(rec: dict) -> str:
    """'int:<event kind>' / 'int:mixed' for trajectories with events; for event-free ones 'obs:wnoise' (structural noise),
    'obs:init' (initial state other than rest), 'obs:nominal' (one step to the nominal input 1.0) or 'obs:stim' (any other input
    schedule). The schedule is read without no-op breakpoints (`step_schedule`)."""
    ev = _events(rec)
    if ev:
        kinds = sorted({e["kind"] for e in ev})
        return "int:" + (kinds[0] if len(kinds) == 1 else "mixed")
    p = rec.get("protocol") or {}
    if p.get("weight_noise"):
        return "obs:wnoise"
    r0 = p.get("r0") or {}
    if r0.get("kind") not in (None, "zero", "rest"):
        return "obs:init"
    vals = [v for _, v in _stimulus(rec)]
    nz = [v for v in vals if np.any(np.asarray(v, dtype=float) != 0)]
    if len(nz) == 1 and np.allclose(np.asarray(nz[0], dtype=float), 1.0) and np.array_equal(np.asarray(vals[-1]), np.asarray(nz[0])):
        return "obs:nominal"
    return "obs:stim"


def _stim_onset_and_scale(rec: dict) -> tuple[float | None, float | None, float | None]:
    """(time of the first non-zero input segment, its scale (norm for vector inputs), its end time); no-op breakpoints ignored."""
    p = rec.get("protocol") or {}
    stim = _stimulus(rec)
    t_end = float(p.get("t_end", rec["t"][-1]))
    for i, (t, v) in enumerate(stim):
        a = np.asarray(v, dtype=float)
        if np.any(a != 0):
            end = stim[i + 1][0] if i + 1 < len(stim) else t_end
            return t, float(np.linalg.norm(a)) if a.ndim else float(abs(a)), end
    return None, None, None


def _idx(t: np.ndarray, time: float) -> int:
    return int(np.clip(np.searchsorted(t, time - 1e-9), 0, len(t) - 1))


def _subsample(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    return sorted({int(round(i)) for i in np.linspace(0, n - 1, k)})


def _col_of(sysrec: dict) -> dict[int, int]:
    obs = [int(a) for a in (sysrec.get("observed") or [])]
    return {u: i for i, u in enumerate(obs)}


def _arr(rec: dict, k: str) -> np.ndarray:
    a = np.asarray(rec[k], dtype=np.float64)
    return a[:, None] if a.ndim == 1 else a


# ------------------------------------------------------------------------------------------------------------------ pairing
def _protocol_without_events(rec: dict) -> dict:
    p = {k: v for k, v in (rec.get("protocol") or {}).items() if k != "events"}
    if "stimulus" in p:
        p["stimulus"] = step_schedule(p["stimulus"])
    return p


def pair_twins(records: list[dict]) -> list[tuple[dict, dict]]:
    """(intervention record, twin record) pairs, from ``meta.twin_of`` links or else from shared ``info.pair`` labels. A pair is
    kept only if the twin's protocol equals the intervention's without events, the input schedules compared without no-op
    breakpoints (`step_schedule`)."""
    by_key = {r.get("key"): r for r in records if r.get("key")}
    pairs = []
    for r in records:
        tw = (r.get("meta") or {}).get("twin_of")
        if tw and tw in by_key and _events(by_key[tw]) and not _events(r):
            pairs.append((by_key[tw], r))
    if not pairs:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for r in records:
            lab = (r.get("info") or {}).get("pair")
            if lab is not None:
                groups[((r.get("protocol") or {}).get("system"), lab)].append(r)
        for g in groups.values():
            ints = [r for r in g if _events(r)]
            tws = [r for r in g if not _events(r)]
            if len(ints) == 1 and len(tws) == 1:
                pairs.append((ints[0], tws[0]))
    out = []
    for a, b in pairs:
        if _protocol_without_events(a) == _protocol_without_events(b) and np.asarray(a["x"]).shape == np.asarray(b["x"]).shape:
            out.append((a, b))
    return out


# ------------------------------------------------------------------------------------------------------------------ primitives
def dimensionality(X: np.ndarray, standardize: bool = False) -> dict:
    """Participation ratio and number of principal components for 90 / 95 / 99 % of the variance of the rows of X (samples x
    features), after centring (and scaling each non-constant column to unit variance if ``standardize``)."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[0] < 2 or X.shape[1] < 1:
        return {"pr": None, "n90": None, "n95": None, "n99": None}
    X = X - X.mean(axis=0)
    sd = X.std(axis=0)
    keep = sd > 1e-12 * max(1.0, float(sd.max()) if sd.size else 1.0)
    X = X[:, keep]
    if X.shape[1] == 0:
        return {"pr": None, "n90": None, "n95": None, "n99": None}
    if standardize:
        X = X / X.std(axis=0)
    s = np.linalg.svd(X, compute_uv=False) ** 2
    tot = float(s.sum())
    if tot <= 0:
        return {"pr": None, "n90": None, "n95": None, "n99": None}
    lam = s / tot
    cum = np.cumsum(lam)
    n = lambda q: int(min(len(lam), np.searchsorted(cum, q - 1e-12) + 1))  # noqa: E731
    return {"pr": float(1.0 / np.sum(lam ** 2)), "n90": n(0.90), "n95": n(0.95), "n99": n(0.99)}


def acf_decay(X: np.ndarray, dt: float) -> tuple[list[float], list[bool]]:
    """Per column (mean removed): the first lag at which the autocorrelation falls below 1/e (linear interpolation); columns
    whose autocorrelation stays above 1/e up to half the window are censored at that lag."""
    X = np.asarray(X, dtype=np.float64)
    T = X.shape[0]
    X = X - X.mean(axis=0)
    var = (X ** 2).sum(axis=0)
    ok = var > 1e-20
    taus, cens = [], []
    if not ok.any():
        return taus, cens
    n = 1 << int(np.ceil(np.log2(2 * T)))
    F = np.fft.rfft(X[:, ok], n=n, axis=0)
    ac = np.fft.irfft(F * np.conj(F), n=n, axis=0)[:T]
    ac = ac / ac[0]
    half = max(2, T // 2)
    thr = 1.0 / math.e
    for j in range(ac.shape[1]):
        a = ac[:half, j]
        below = np.nonzero(a < thr)[0]
        if below.size == 0:
            taus.append(half * dt)
            cens.append(True)
            continue
        i = int(below[0])
        if i == 0:
            taus.append(0.0)
        else:
            a0, a1 = a[i - 1], a[i]
            frac = (a0 - thr) / (a0 - a1) if a0 != a1 else 0.0
            taus.append((i - 1 + frac) * dt)
        cens.append(False)
    return taus, cens


def spectrum_stats(X: np.ndarray, dt: float) -> dict:
    """Welch spectra (segment length = the largest power of two <= the window) of the mean-removed columns, each normalised to
    unit total power, then averaged. Returns the dominant frequency, its prominence (peak / median power density), the spectral
    centroid and the 5 / 50 / 95 % cumulative-power frequencies. The DC bin is excluded."""
    X = np.asarray(X, dtype=np.float64)
    T = X.shape[0]
    X = X - X.mean(axis=0)
    ok = X.std(axis=0) > 1e-12
    out = {"f_peak": None, "prominence_log10": None, "centroid": None, "f05": None, "f50": None, "f95": None}
    if T < 16 or not ok.any():
        return out
    nper = 1 << int(np.floor(np.log2(max(8, T))))
    f, P = signal.welch(X[:, ok], fs=1.0 / dt, nperseg=nper, axis=0, detrend="constant")
    P = P[1:]
    f = f[1:]
    tot = P.sum(axis=0)
    good = tot > 0
    if not good.any():
        return out
    Pm = (P[:, good] / tot[good]).mean(axis=1)
    i = int(np.argmax(Pm))
    c = np.cumsum(Pm) / Pm.sum()
    out.update(f_peak=float(f[i]), prominence_log10=float(np.log10(max(Pm[i], 1e-300) / max(np.median(Pm), 1e-300))),
               centroid=float((f * Pm).sum() / Pm.sum()),
               f05=float(f[np.searchsorted(c, 0.05)]), f50=float(f[np.searchsorted(c, 0.50)]), f95=float(f[min(len(f) - 1, np.searchsorted(c, 0.95))]))
    return out


def decay_time(E: np.ndarray, dt: float) -> tuple[float | None, bool]:
    """Time from the peak of a non-negative effect profile E(t) to its first fall below peak / e (linear interpolation);
    censored (returns the remaining window length, True) when it never falls that far."""
    E = np.asarray(E, dtype=np.float64)
    if E.size < 2 or not np.isfinite(E).all() or E.max() <= 0:
        return None, False
    ip = int(np.argmax(E))
    thr = E[ip] / math.e
    after = np.nonzero(E[ip:] < thr)[0]
    if after.size == 0:
        return (E.size - 1 - ip) * dt, True
    j = ip + int(after[0])
    e0, e1 = E[j - 1], E[j]
    frac = (e0 - thr) / (e0 - e1) if e0 != e1 else 0.0
    return (j - 1 - ip + frac) * dt, False


# ------------------------------------------------------------------------------------------------------------------ scales
def system_scales(records: list[dict]) -> dict:
    """s_x / s_y = 99th percentile of |x| / |y| over all samples of all units (sub-sampled in time); a unit is active when its
    temporal sd over the concatenated records exceeds ACTIVE_REL x s."""
    xs, ys = [], []
    for r in records:
        t = np.asarray(r["t"], dtype=float)
        dt = float(np.median(np.diff(t))) if t.size > 1 else 1.0
        st = max(1, int(round(POOL_STRIDE_S / dt)))
        xs.append(_arr(r, "x")[::st])
        ys.append(_arr(r, "y")[::st])
    X, Y = np.concatenate(xs), np.concatenate(ys)
    s_x = float(np.percentile(np.abs(X), 99)) or 1.0
    s_y = float(np.percentile(np.abs(Y), 99)) or 1.0
    return {"s_x": s_x, "s_y": s_y, "active_x": X.std(axis=0) > ACTIVE_REL * s_x, "active_y": Y.std(axis=0) > ACTIVE_REL * s_y,
            "unit_max_x": X.max(axis=0), "unit_min_x": X.min(axis=0), "sys_max_x": float(X.max()), "X_pool": X}


# ------------------------------------------------------------------------------------------------------------------ groups
def stats_sizes(records: list[dict], sysrec: dict) -> dict:
    r = records[0]
    t = np.asarray(r["t"], dtype=float)
    kinds = defaultdict(int)
    for q in records:
        kinds[record_kind(q)] += 1
    durs = [float(np.asarray(q["t"])[-1] - np.asarray(q["t"])[0]) for q in records]
    return {"n_obs": int(_arr(r, "x").shape[1]), "n_y": int(_arr(r, "y").shape[1]), "n_u": int(_arr(r, "u").shape[1]),
            "dt": float(np.median(np.diff(t))), "duration_s": _med(durs), "n_records": len(records),
            "n_targets_public": len(sysrec.get("targets_public") or []), "record_kinds": dict(kinds)}


def stats_rates(records: list[dict], sc: dict) -> dict:
    X = sc["X_pool"][:, sc["active_x"]]
    out = {"s_x": sc["s_x"], "s_y": sc["s_y"], "frac_units_active": float(np.mean(sc["active_x"])) if sc["active_x"].size else None,
           "frac_readout_active": float(np.mean(sc["active_y"])) if sc["active_y"].size else None}
    if X.size:
        pos = X[X > FLOOR_REL * sc["s_x"]]
        q = _pct(pos.ravel(), (5, 25, 50, 75, 95, 99))
        out.update({f"rate_active_{k}": v for k, v in q.items()})
        out.update({f"rate_active_rel_{k}": (None if v is None else v / sc["s_x"]) for k, v in q.items()})
        peaks = sc["unit_max_x"][sc["active_x"]]
        q = _pct(peaks, (5, 50, 95))
        out.update({f"peak_rate_{k}": v for k, v in q.items()})
        out.update({f"peak_rate_rel_{k}": (None if v is None else v / sc["s_x"]) for k, v in q.items()})
        out["peak_rate_max"] = float(peaks.max())
        lo = sc["unit_min_x"][sc["active_x"]]
        out["frac_samples_at_floor"] = float(np.mean(X <= lo + FLOOR_REL * sc["s_x"]))
        out["frac_samples_near_unit_max"] = float(np.mean(X >= NEAR_MAX_REL * peaks))
        out["frac_samples_near_system_max"] = float(np.mean(X >= NEAR_MAX_REL * sc["sys_max_x"]))
    return out


def stats_dimensionality(records: list[dict], sc: dict) -> dict:
    by_kind = defaultdict(list)
    for r in records:
        by_kind[record_kind(r)].append(r)
    per_traj = defaultdict(list)
    obs_rows, all_rows = [], []
    for kind, recs in by_kind.items():
        for i in _subsample(len(recs), MAX_RECORDS_PER_KIND):
            r = recs[i]
            x, y = _arr(r, "x"), _arr(r, "y")
            for nm, arr in (("x", x), ("y", y)):
                d = dimensionality(arr)
                for k, v in d.items():
                    per_traj[f"dim_{nm}_traj_{k}"].append(v)
            ds = dimensionality(x, standardize=True)
            per_traj["dim_x_traj_std_pr"].append(ds["pr"])
            t = np.asarray(r["t"], dtype=float)
            st = max(1, int(round(POOL_STRIDE_S / float(np.median(np.diff(t))))))
            all_rows.append(x[::st])
            if kind.startswith("obs:"):
                obs_rows.append(x[::st])
    out = {k: _med(v) for k, v in per_traj.items()}
    for nm, rows in (("obs", obs_rows), ("all", all_rows)):
        if rows:
            d = dimensionality(np.concatenate(rows))
            out.update({f"dim_x_pooled_{nm}_{k}": v for k, v in d.items()})
            ds = dimensionality(np.concatenate(rows), standardize=True)
            out[f"dim_x_pooled_{nm}_std_pr"] = ds["pr"]
    return out


def stats_timescales(records: list[dict], sc: dict) -> dict:
    by_kind = defaultdict(list)
    for r in records:
        if record_kind(r).startswith("obs:"):
            by_kind[record_kind(r)].append(r)
    taus, cens, spx, spy = [], [], defaultdict(list), defaultdict(list)
    lat = []
    for recs in by_kind.values():
        for i in _subsample(len(recs), MAX_RECORDS_PER_KIND):
            r = recs[i]
            t = np.asarray(r["t"], dtype=float)
            dt = float(np.median(np.diff(t)))
            on, _, _ = _stim_onset_and_scale(r)
            i0 = _idx(t, t[0] + max(0.25, 0.2 * (t[-1] - t[0])))      # skip the onset transient
            x = _arr(r, "x")[i0:, sc["active_x"]]
            y = _arr(r, "y")[i0:, sc["active_y"]]
            if x.shape[0] >= 16 and x.shape[1]:
                tt, cc = acf_decay(x, dt)
                taus += tt
                cens += cc
                for k, v in spectrum_stats(x, dt).items():
                    spx[k].append(v)
            if y.shape[0] >= 16 and y.shape[1]:
                for k, v in spectrum_stats(y, dt).items():
                    spy[k].append(v)
            if on is not None and record_kind(r) == "obs:nominal":
                xa = _arr(r, "x")[:, sc["active_x"]]
                n = np.linalg.norm(xa - xa[_idx(t, on)], axis=1)
                if n.max() > 0:
                    j = np.nonzero(n[_idx(t, on):] >= 0.1 * n.max())[0]
                    if j.size:
                        lat.append(float(j[0]) * dt)
    out = {"acf_decay_s_median": _med([a for a, c in zip(taus, cens) if not c] or taus),
           "acf_decay_s_p10": _f(np.percentile(taus, 10)) if taus else None, "acf_decay_s_p90": _f(np.percentile(taus, 90)) if taus else None,
           "acf_censored_frac": float(np.mean(cens)) if cens else None, "onset_latency_10pct_s": _med(lat)}
    for nm, sp in (("x", spx), ("y", spy)):
        for k, v in sp.items():
            out[f"spec_{nm}_{k}"] = _med(v)
        if sp.get("prominence_log10"):
            out[f"spec_{nm}_oscillatory_frac"] = float(np.mean([p is not None and p > 1.0 for p in sp["prominence_log10"]]))
    return out


def _pair_stats(ri: dict, rt: dict, sysrec: dict, sc: dict, col: dict[int, int]) -> dict:
    t = np.asarray(ri["t"], dtype=float)
    dt = float(np.median(np.diff(t)))
    t_end = float((ri.get("protocol") or {}).get("t_end", t[-1]))
    ev = sorted(_events(ri), key=event_start)
    e0 = ev[0]
    ts0 = event_start(e0)
    te0 = event_end(e0, t_end)
    t_next = event_start(ev[1]) if len(ev) > 1 else t[-1] + dt
    i0, inext = _idx(t, ts0), min(len(t), _idx(t, t_next) if len(ev) > 1 else len(t))
    xi, xt, yi, yt = _arr(ri, "x"), _arr(rt, "x"), _arr(ri, "y"), _arr(rt, "y")
    D, Dy = xi - xt, yi - yt
    out: dict[str, Any] = {"kind": e0["kind"], "n_events": len(ev), "n_targets_first": len(event_targets(e0)),
                           "persistent_first": te0 >= t_end - 1e-9 and e0["kind"] not in ("kick",)}
    out["pre_event_maxabs"] = float(np.abs(D[:i0]).max()) if i0 > 0 else 0.0
    W = slice(i0, len(t))
    xw = xt[W][:, sc["active_x"]] if sc["active_x"].any() else xt[W]
    den_x = max(float(np.linalg.norm(xw - xw.mean(axis=0))), 1e-3 * sc["s_x"] * math.sqrt(max(1, xw.size)))
    yw = yt[W][:, sc["active_y"]] if sc["active_y"].any() else yt[W]
    den_y = max(float(np.linalg.norm(yw - yw.mean(axis=0))), 1e-3 * sc["s_y"] * math.sqrt(max(1, yw.size)))
    out["eff_rel_x"] = float(np.linalg.norm(D[W])) / den_x
    out["eff_rel_y"] = float(np.linalg.norm(Dy[W])) / den_y
    out["eff_rms_x"] = float(np.sqrt(np.mean(D[W] ** 2)))
    out["eff_rms_y"] = float(np.sqrt(np.mean(Dy[W] ** 2)))
    out["eff_rms_x_rel_scale"] = out["eff_rms_x"] / sc["s_x"]
    out["eff_rms_y_rel_scale"] = out["eff_rms_y"] / sc["s_y"]
    # first-event window
    Wf = slice(i0, max(i0 + 2, inext))
    Df, Dyf = D[Wf], Dy[Wf]
    tg = event_targets(e0)
    if len(tg) == 1:
        c = col.get(tg[0])
        mx = np.abs(Df).max(axis=0) if Df.size else np.zeros(D.shape[1])
        others = np.ones(D.shape[1], dtype=bool)
        if c is not None:
            others[c] = False
        denom = max(1, int(others.sum()))
        for thr in RESP_THRESHOLDS:
            out[f"resp_frac_{int(round(thr * 100))}pct"] = float(np.sum(mx[others] > thr * sc["s_x"])) / denom
        out["resp_frac_y_1pct"] = float(np.mean(np.abs(Dyf).max(axis=0) > 0.01 * sc["s_y"])) if Dyf.size else None
        if e0["kind"] == "kick" and c is not None:
            dlt = float(list(e0["delta"].values())[0])
            pre = float(xi[i0, c])
            out["kick_rel_scale"] = abs(dlt) / sc["s_x"]
            out["kick_clipped"] = bool(pre + dlt < 0.0 and dlt < 0.0)
            prof = np.abs(D[i0 + 1:inext, c]) if inext > i0 + 1 else np.zeros(0)
            if prof.size >= 2 and prof[0] > 0:
                below = np.nonzero(prof < prof[0] / math.e)[0]
                out["self_decay_s"] = float(below[0]) * dt if below.size else None
                out["self_decay_censored"] = bool(below.size == 0)
        if e0["kind"] == "current":
            out["current_abs"] = float(abs(list(e0["targets"].values())[0]))
            out["current_duration_s"] = te0 - ts0
    # decay after the first event ends (transient events only), latency of the readout effect
    if not out["persistent_first"]:
        ie = _idx(t, te0)
        if inext - ie >= 3:
            E = np.linalg.norm(D[ie:inext], axis=1)
            tau, cz = decay_time(E, dt)
            out["decay_x_s"], out["decay_x_censored"] = tau, cz
            Ey = np.linalg.norm(Dy[ie:inext], axis=1)
            tau, cz = decay_time(Ey, dt)
            out["decay_y_s"], out["decay_y_censored"] = tau, cz
    Ey = np.linalg.norm(Dyf, axis=1)
    if Ey.size and Ey.max() > 0:
        out["latency_y_peak_s"] = float(np.argmax(Ey)) * dt
    # persistence: effect norm at the end of the first-event window relative to its peak
    E = np.linalg.norm(Df, axis=1)
    if E.size and E.max() > 0:
        out["effect_end_over_peak"] = float(E[-1] / E.max())
    out["_effect_rows"] = D[W][::max(1, int(round(POOL_STRIDE_S / dt)))]      # sub-sampled every 5 ms for the pooled PCA
    return out


def stats_interventions(records: list[dict], sysrec: dict, sc: dict, obs_basis: np.ndarray | None) -> dict:
    col = _col_of(sysrec)
    pairs = pair_twins(records)
    ps = [_pair_stats(a, b, sysrec, sc, col) for a, b in pairs]
    out: dict[str, Any] = {"n_pairs": len(ps)}
    if not ps:
        return out
    floor_pre = max(p["pre_event_maxabs"] for p in ps)
    is32 = any(np.asarray(r["x"]).dtype == np.float32 for r in records)
    floor = max(floor_pre, (F32_EPS * sc["s_x"]) if is32 else 0.0, 1e-300)
    out["noise_floor_pre_event_maxabs"] = floor_pre
    out["noise_floor_abs"] = floor
    out["noise_floor_rel_scale"] = floor / sc["s_x"]
    for fam in sorted({p["kind"] for p in ps}) + ["all"]:
        sel = [p for p in ps if fam == "all" or p["kind"] == fam]
        tag = "" if fam == "all" else f"_{fam}"
        for key in ("eff_rel_x", "eff_rel_y", "eff_rms_x_rel_scale", "eff_rms_y_rel_scale"):
            v = [p[key] for p in sel]
            q = _pct(v, (5, 25, 50, 75, 95))
            out.update({f"{key}{tag}_{k}": vv for k, vv in q.items()})
        for thr in (1e-3, 1e-2, 1e-1):
            out[f"frac_eff_rel_y_below_{thr:g}{tag}"] = float(np.mean([p["eff_rel_y"] < thr for p in sel]))
            out[f"frac_eff_rel_x_below_{thr:g}{tag}"] = float(np.mean([p["eff_rel_x"] < thr for p in sel]))
        for key in ("resp_frac_1pct", "resp_frac_10pct", "resp_frac_y_1pct", "decay_x_s", "decay_y_s", "latency_y_peak_s",
                    "effect_end_over_peak", "self_decay_s"):
            v = [p.get(key) for p in sel if p.get(key) is not None]
            if v:
                out[f"{key}{tag}_median"] = _med(v)
                if key.startswith("resp_frac"):
                    out[f"{key}{tag}_mean"] = float(np.mean(v))
                    out[f"{key}{tag}_p90"] = float(np.percentile(v, 90))
                    out[f"{key}{tag}_any"] = float(np.mean([a > 0 for a in v]))
        cz = [p["decay_x_censored"] for p in sel if "decay_x_censored" in p]
        if cz:
            out[f"decay_x_censored_frac{tag}"] = float(np.mean(cz))
        out[f"snr_floor_x{tag}_median"] = _med([p["eff_rms_x"] / floor for p in sel])
    ks = [p for p in ps if "kick_rel_scale" in p]
    if ks:
        out.update({f"kick_rel_scale_{k}": v for k, v in _pct([p["kick_rel_scale"] for p in ks], (5, 50, 95)).items()})
        out["kick_clipped_frac"] = float(np.mean([p["kick_clipped"] for p in ks]))
    sd = [p["self_decay_s"] for p in ps if p.get("self_decay_s") is not None]
    dx = [p["decay_x_s"] for p in ps if p.get("decay_x_s") is not None and p.get("kind") == "kick"]
    if sd and dx:
        out["persistence_ratio_kick"] = float(np.median(dx) / max(np.median(sd), 1e-12))
    cu = [p for p in ps if "current_abs" in p]
    if cu:
        out.update({f"current_abs_{k}": v for k, v in _pct([p["current_abs"] for p in cu], (5, 50, 95)).items()})
        out.update({f"current_duration_s_{k}": v for k, v in _pct([p["current_duration_s"] for p in cu], (5, 50, 95)).items()})
    # dimensionality of the intervention responses and their energy outside the passive (observational) subspace
    rows = np.concatenate([p.pop("_effect_rows") for p in ps])
    d = dimensionality(np.vstack([rows, -rows]))       # effects are differences: symmetrise instead of centring
    out.update({f"dim_effect_x_{k}": v for k, v in d.items()})
    if obs_basis is not None and obs_basis.size and rows.size:
        tot = float((rows ** 2).sum())
        if tot > 0:
            res = rows - (rows @ obs_basis) @ obs_basis.T
            frac = float((res ** 2).sum() / tot)
            out["effect_energy_outside_passive95"] = frac if frac > 1e-12 else 0.0     # rounding residue when the basis spans all
    out["_eff_rms_x"] = [p["eff_rms_x"] for p in ps]
    out["_eff_rms_y"] = [p["eff_rms_y"] for p in ps]
    return out


def stats_kick_clipping(records: list[dict], sysrec: dict) -> dict:
    """Fraction of negative kicks on observed targets whose requested offset exceeds the pre-kick value, i.e. whose applied
    offset was clipped at the rest floor (all records with kicks; the sample at the kick time is the pre-kick state)."""
    col = _col_of(sysrec)
    n_neg, n_clip, n_all = 0, 0, 0
    for r in records:
        t = np.asarray(r["t"], dtype=float)
        x = _arr(r, "x")
        for e in _events(r):
            if e["kind"] != "kick":
                continue
            i = _idx(t, float(e["t"]))
            for u, d in e["delta"].items():
                c = col.get(int(u))
                if c is None:
                    continue
                n_all += 1
                if float(d) < 0:
                    n_neg += 1
                    n_clip += int(x[i, c] + float(d) < 0.0)
    if not n_all:
        return {}
    return {"kick_clipped_frac_all": n_clip / n_all, "kick_clipped_frac_of_negative": (n_clip / n_neg) if n_neg else None}


def _aligned_spread(recs: list[dict], sc: dict) -> dict:
    """Spread across parameter (or weight-noise) draws of event-free trajectories aligned at the input onset."""
    items = []
    for r in recs:
        on, _, _ = _stim_onset_and_scale(r)
        if on is None:
            continue
        t = np.asarray(r["t"], dtype=float)
        items.append((_idx(t, on), r))
    if len(items) < 3:
        return {}
    L = min(len(np.asarray(r["t"])) - i for i, r in items)
    if L < 10:
        return {}
    out = {}
    for nm, act in (("x", sc["active_x"]), ("y", sc["active_y"])):
        if not act.any():
            continue
        seg = lambda it: _arr(it[1], nm)[it[0]:it[0] + L][:, act]  # noqa: E731   draws are streamed (memory), two passes
        M = sum(seg(it) for it in items) / len(items)
        S = np.sqrt(sum((seg(it) - M) ** 2 for it in items) / len(items))      # population sd over draws, as np.std
        rms = lambda z: float(np.sqrt(np.mean(z ** 2)))  # noqa: E731
        out[f"param_spread_{nm}_rel_level"] = rms(S) / max(rms(M), 1e-300)
        out[f"param_spread_{nm}_rel_dynamics"] = rms(S) / max(rms(M - M.mean(axis=0)), 1e-300)
        out[f"param_spread_{nm}_abs_rms"] = rms(S)
    return out


def stats_param_uncertainty(records: list[dict], sc: dict) -> dict:
    nom = [r for r in records if record_kind(r) == "obs:nominal"]
    wn = [r for r in records if record_kind(r) == "obs:wnoise"]
    out = {}
    for tag, recs in (("params", nom), ("wnoise", wn)):
        for k, v in _aligned_spread(recs, sc).items():
            out[f"{tag}_{k}"] = v
    sds = [float(r["protocol"]["weight_noise"]["sd"]) for r in wn]
    if sds:
        out["wnoise_sd_max"] = max(sds)
    return out


INIT_HIGH_RATIO = 3.0        # an initial-state record ends in a HIGH-activity state when its late RMS exceeds 3 x the nominal one
LATE_FRAC = 0.25             # "late" = the last quarter of the trajectory


def stats_init_states(records: list[dict], sc: dict) -> dict:
    """Where the design's initial states lead: late activity (RMS of the active units over the last quarter of the trajectory) of
    the event-free initial-state records relative to the median late activity of the nominal records. A ratio well above 1 means
    that the initial state moved the system into another persistent state (e.g. a second attractor); a ratio near 1 means it
    relaxed back to the nominal behaviour."""
    def late(r, nm, act):
        a = _arr(r, nm)
        i0 = int(round((1.0 - LATE_FRAC) * (a.shape[0] - 1)))
        z = a[i0:][:, act]
        return float(np.sqrt(np.mean(z ** 2))) if z.size else None
    nom = [r for r in records if record_kind(r) == "obs:nominal"]
    ini = [r for r in records if record_kind(r) == "obs:init"]
    out: dict[str, Any] = {}
    if not nom or not ini:
        return out
    for nm, act in (("x", sc["active_x"]), ("y", sc["active_y"])):
        m0 = _med([late(r, nm, act) for r in nom])
        if not m0:
            continue
        ratios = [v / m0 for v in (late(r, nm, act) for r in ini) if v is not None]
        if not ratios:
            continue
        out[f"init_late_rms_ratio_{nm}_median"] = _med(ratios)
        out[f"init_late_rms_ratio_{nm}_p90"] = float(np.percentile(ratios, 90))
        out[f"init_high_state_frac_{nm}"] = float(np.mean([q > INIT_HIGH_RATIO for q in ratios]))
    return out


def stats_input_gain(records: list[dict], sc: dict) -> dict:
    pts = []
    for r in records:
        k = record_kind(r)
        if k not in ("obs:nominal", "obs:stim"):
            continue
        on, s, end = _stim_onset_and_scale(r)
        if on is None or not s:
            continue
        t = np.asarray(r["t"], dtype=float)
        a, b = _idx(t, on + 0.25 * (end - on)), _idx(t, end)
        if b - a < 5:
            continue
        x = _arr(r, "x")[a:b][:, sc["active_x"]]
        y = _arr(r, "y")[a:b][:, sc["active_y"]]
        pts.append((s, float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0, float(np.sqrt(np.mean(y ** 2))) if y.size else 0.0))
    out = {}
    if pts:
        s = np.array([p[0] for p in pts])
        out["input_scale_min"], out["input_scale_max"] = float(s.min()), float(s.max())
        for nm, j in (("x", 1), ("y", 2)):
            R = np.array([p[j] for p in pts])
            ok = (R > 0) & (s > 0)
            if ok.sum() >= 3 and np.ptp(np.log(s[ok])) > 1e-6:
                g = np.polyfit(np.log(s[ok]), np.log(R[ok]), 1)[0]
                out[f"input_gain_elasticity_{nm}"] = float(g)
            out[f"input_response_rms_{nm}_rel_scale_median"] = _med(R / (sc["s_x"] if nm == "x" else sc["s_y"]))
    return out


def stats_event_design(records: list[dict]) -> dict:
    """Timing and duration of the public events (the design, not a response)."""
    kick_d, cur_i, cur_dur, sil_p, t_ev = [], [], [], [], []
    for r in records:
        t_end = float((r.get("protocol") or {}).get("t_end", np.asarray(r["t"])[-1]))
        for e in _events(r):
            t_ev.append(event_start(e) / max(t_end, 1e-12))
            if e["kind"] == "kick":
                kick_d += [abs(float(v)) for v in e["delta"].values()]
            elif e["kind"] == "current":
                cur_i += [abs(float(v)) for v in e["targets"].values()]
                cur_dur.append(event_end(e, t_end) - event_start(e))
            elif e["kind"] == "silence":
                sil_p.append(e.get("t1") is None)
    out = {}
    if kick_d:
        out.update({f"design_kick_abs_{k}": v for k, v in _pct(kick_d, (5, 50, 95)).items()})
    if cur_i:
        out.update({f"design_current_abs_{k}": v for k, v in _pct(cur_i, (5, 50, 95)).items()})
        out.update({f"design_current_duration_s_{k}": v for k, v in _pct(cur_dur, (5, 50, 95)).items()})
    if sil_p:
        out["design_silence_persistent_frac"] = float(np.mean(sil_p))
    if t_ev:
        out.update({f"design_event_time_rel_{k}": v for k, v in _pct(t_ev, (5, 50, 95)).items()})
    return out


# ------------------------------------------------------------------------------------------------------------------ definitions
_DEFS = [
    # (key prefix, definition); the first matching prefix wins, so longer prefixes come first
    ("n_obs", "number of observed units (columns of x)"),
    ("n_y", "readout dimension (columns of y)"),
    ("n_u", "exogenous input dimension (columns of u)"),
    ("n_targets_public", "number of units that development interventions may target"),
    ("dt", "output sampling interval (s)"),
    ("duration_s", "median trajectory duration (s)"),
    ("s_x", "rate scale s_x: 99th percentile of |x| over all samples of all observed units (sub-sampled every 5 ms)"),
    ("s_y", "readout scale s_y: 99th percentile of |y| over all samples"),
    ("frac_units_active", "fraction of observed units whose temporal sd over all records exceeds 1e-3 s_x"),
    ("frac_readout_active", "fraction of readout units whose temporal sd exceeds 1e-3 s_y"),
    ("rate_active_rel_", "percentile of the samples of active observed units that are above the floor, divided by s_x"),
    ("rate_active_", "percentile of the samples of active observed units that are above the floor (units of x)"),
    ("peak_rate_rel_", "percentile across active observed units of each unit's maximum, divided by s_x"),
    ("peak_rate_", "percentile across active observed units of each unit's maximum (units of x); _max = the largest"),
    ("frac_samples_at_floor", "fraction of samples of active units at their lower bound (within 1e-6 s_x of the unit's minimum; rectified units at 0)"),
    ("frac_samples_near_unit_max", "fraction of samples of active units at >= 90 % of that unit's own maximum"),
    ("frac_samples_near_system_max", "fraction of samples of active units at >= 90 % of the largest value of any unit (saturation proxy)"),
    ("dim_x_traj_std_pr", "participation ratio of one trajectory's x after z-scoring each active unit (median over trajectories)"),
    ("dim_x_traj_", "PCA of one trajectory's x (covariance, centred): participation ratio (pr) or number of components for 90/95/99 % variance (n90/n95/n99); median over trajectories (up to 40 per record kind)"),
    ("dim_y_traj_", "the same for the readout y of one trajectory"),
    ("dim_x_pooled_obs_std_pr", "participation ratio of the pooled event-free trajectories after z-scoring each unit"),
    ("dim_x_pooled_obs_", "PCA of all event-free trajectories pooled (sub-sampled every 5 ms): pr / n90 / n95 / n99"),
    ("dim_x_pooled_all_std_pr", "participation ratio of all pooled trajectories after z-scoring each unit"),
    ("dim_x_pooled_all_", "PCA of all trajectories pooled, including interventions: pr / n90 / n95 / n99"),
    ("dim_effect_x_", "PCA (uncentred) of the intervention effects x_int - x_twin pooled over all (intervention, twin) pairs and post-onset samples: pr / n90 / n95 / n99"),
    ("effect_energy_outside_passive95", "fraction of the pooled intervention-effect energy outside the subspace holding 95 % of the variance of the event-free trajectories (how much interventions excite directions passive activity does not visit)"),
    ("acf_decay_s_median", "median over active units and event-free trajectories of the lag (s) at which the autocorrelation first drops below 1/e (window after the onset transient); uncensored units only. For oscillating units this is about a quarter period, not a memory time"),
    ("acf_decay_s_p10", "10th percentile of the autocorrelation decay lag (s), censored values included"),
    ("acf_decay_s_p90", "90th percentile of the autocorrelation decay lag (s), censored values included"),
    ("acf_censored_frac", "fraction of units whose autocorrelation stays above 1/e for half the window (slow drift / persistent activity)"),
    ("onset_latency_10pct_s", "time (s) from the input onset until ||x(t) - x(onset)|| first reaches 10 % of its maximum (nominal trajectories)"),
    ("spec_x_oscillatory_frac", "fraction of event-free trajectories whose unit-averaged normalised power spectrum has a peak >= 10 x its median"),
    ("spec_y_oscillatory_frac", "the same for the readout"),
    ("spec_x_", "Welch spectrum of the active units of x after the onset transient, each unit normalised to unit power, averaged: dominant frequency f_peak (Hz), prominence_log10 (log10 of peak / median density), centroid (Hz), f05 / f50 / f95 (Hz at 5 / 50 / 95 % cumulative power); median over event-free trajectories"),
    ("spec_y_", "the same for the readout y"),
    ("noise_floor_pre_event_maxabs", "largest |x_int - x_twin| before the first event over all pairs (numerical reproducibility of the simulator)"),
    ("noise_floor_abs", "noise floor = max(pre-event difference, float32 resolution x s_x) (units of x)"),
    ("noise_floor_rel_scale", "noise floor divided by s_x"),
    ("eff_rel_x", "intervention effect in x: ||x_int - x_twin||_F / ||x_twin - mean_t x_twin||_F over the window from the first event to the end (effect relative to the twin's own variability); percentiles over pairs; suffix = kind of the first event"),
    ("eff_rel_y", "the same for the readout y"),
    ("eff_rms_x_rel_scale", "RMS of x_int - x_twin from the first event to the end, divided by s_x; percentiles over pairs"),
    ("eff_rms_y_rel_scale", "RMS of y_int - y_twin divided by s_y; percentiles over pairs"),
    ("frac_eff_rel_y_below_", "fraction of pairs whose relative readout effect eff_rel_y is below the threshold (near-zero effects)"),
    ("frac_eff_rel_x_below_", "fraction of pairs whose relative effect eff_rel_x is below the threshold"),
    ("resp_frac_y_1pct", "over single-target first events: the fraction of readout units whose |effect| in the first-event window exceeds 1 % of s_y (_median / _mean / _p90 over events; _any = fraction of events with at least one responding readout unit)"),
    ("resp_frac_1pct", "response sparsity over single-target first events: the fraction of the OTHER observed units whose max |effect| in the first-event window exceeds 1 % of s_x (_median / _mean / _p90 over events; _any = fraction of events with at least one responding unit)"),
    ("resp_frac_10pct", "the same with a 10 % of s_x threshold"),
    ("decay_x_censored_frac", "fraction of transient first events whose effect norm in x does not fall below peak / e before the next event or the end"),
    ("decay_x_s", "time (s) from the peak of ||x_int - x_twin|| after the end of a transient first event to its fall below peak / e; median over pairs"),
    ("decay_y_s", "the same for the readout effect"),
    ("latency_y_peak_s", "time (s) from the first event's onset to the peak of the readout effect norm within the first-event window; median over pairs"),
    ("effect_end_over_peak", "effect norm in x at the end of the first-event window divided by its peak (persistence); median over pairs"),
    ("self_decay_s", "time (s) for a kicked observed unit's own effect to fall below 1/e of its initial jump; median over single-target kicks"),
    ("persistence_ratio_kick", "median network effect decay time after kicks divided by the median decay of the kicked unit's own effect (recurrent persistence)"),
    ("snr_floor_x", "median over pairs of the effect RMS in x divided by the noise floor"),
    ("snr_param_x_median", "median over pairs of the effect RMS in x divided by the RMS spread of x across parameter draws (nominal trajectories)"),
    ("snr_param_x_p10", "10th percentile of the same ratio"),
    ("snr_param_y_median", "the same for the readout"),
    ("snr_param_y_p10", "10th percentile of the same ratio for the readout"),
    ("kick_rel_scale_", "|kick offset| / s_x for single-target first kicks; percentiles"),
    ("kick_clipped_frac_all", "fraction of kick offsets on observed targets (all records) that were clipped at the lower bound"),
    ("kick_clipped_frac_of_negative", "the same among negative offsets"),
    ("kick_clipped_frac", "fraction of single-target first kicks that were clipped at the lower bound"),
    ("current_abs_", "|current| of single-target first current events (input units); percentiles"),
    ("current_duration_s_", "duration (s) of single-target first current events; percentiles"),
    ("params_param_spread_", "spread across parameter draws: nominal trajectories aligned at the input onset; rel_level = RMS(sd over draws) / RMS(mean over draws); rel_dynamics = RMS(sd) / RMS(mean - its time average); abs_rms in units of x / y"),
    ("wnoise_param_spread_", "the same for trajectories with structural weight noise (which also differ in parameter draw)"),
    ("wnoise_sd_max", "largest structural weight-noise sd in the public records"),
    ("init_late_rms_ratio_", "late activity (RMS of the active units over the last quarter of the trajectory) of each event-free initial-state record divided by the median late activity of the nominal records; median / 90th percentile over the initial-state records"),
    ("init_high_state_frac_", "fraction of event-free initial-state records whose late activity exceeds 3 x the nominal late activity (the initial state moved the system into another persistent, high-activity state)"),
    ("input_scale_min", "smallest non-zero input scale in the event-free records"),
    ("input_scale_max", "largest input scale in the event-free records"),
    ("input_gain_elasticity_", "slope of log(response RMS during the input) against log(input scale) over event-free trajectories"),
    ("input_response_rms_", "RMS of the response during the input divided by the scale (s_x or s_y); median"),
    ("design_", "design of the public protocols (not a response): event magnitudes, durations, persistent-silencing fraction, event times relative to the duration"),
]


def describe(name: str) -> str:
    """Definition of a statistic key produced by compute_all."""
    for pre, d in _DEFS:
        if name.startswith(pre):
            return d
    return ""


# ------------------------------------------------------------------------------------------------------------------ dependence
#: What a statistic's value depends on. 'system': a property of the system's own dynamics under the benchmark's nominal
#: conditions (the intervention design changes it little); 'design': set mainly by the experimental design (intervention
#: magnitudes, onsets, durations, initial states, input schedules, which records exist), so it is comparable only between data
#: built with the SAME design; 'mixed': a system response whose value also scales with the design.
DEPENDENCE_CLASSES = {
    "system": "a property of the system's own dynamics under nominal conditions; the intervention design changes it little",
    "design": "set mainly by the experimental design (magnitudes, onsets, durations, initial states, input schedules, record mix); "
              "comparable only between data built with the same design",
    "mixed": "a system response whose value also scales with the design",
}
_DEPENDENCE = [
    # (key prefix, class, reason); the first matching prefix wins, so longer prefixes come first
    ("n_targets_public", "system", "size of the public target set of the system record"),
    ("n_obs", "system", "size of the observed population"),
    ("n_y", "system", "readout dimension"),
    ("n_u", "system", "input dimension"),
    ("dt", "design", "output sampling of the protocols"),
    ("duration_s", "design", "trajectory duration of the protocols"),
    ("s_x", "mixed", "99th percentile of |x|: raised by initial states and interventions near the top of the rate range"),
    ("s_y", "mixed", "99th percentile of |y|: depends on the conditions sampled"),
    ("frac_units_active", "system", "which units ever vary"),
    ("frac_readout_active", "system", "which readout units ever vary"),
    ("rate_active", "mixed", "activity levels over all records, including initial states and interventions"),
    ("peak_rate", "design", "per-unit maxima: dominated by the largest initial states and interventions of the design"),
    ("frac_samples_at_floor", "system", "rectification: the share of time active units spend at their lower bound (a pool over all records, which the intervention design changes little)"),
    ("frac_samples_near", "design", "saturation proxy: dominated by initial states near the top of the rate range"),
    ("kick_clipped", "design", "sign and magnitude distribution of the kicks relative to the state they hit"),
    ("dim_x_traj", "system", "dimensionality of single trajectories (a median over records of every kind, which the intervention design changes little)"),
    ("dim_y_traj", "system", "dimensionality of the readout of single trajectories (a median over records of every kind)"),
    ("dim_x_pooled_obs", "mixed", "diversity of the passive design (parameter draws, input schedules, initial states)"),
    ("dim_x_pooled_all", "mixed", "diversity of the whole design, interventions included"),
    ("dim_effect_x", "design", "spread of the intervention targets, kinds and magnitudes"),
    ("effect_energy_outside_passive95", "mixed", "a system property (directions passive activity does not visit) seen through the design's passive diversity and intervention set"),
    ("acf_decay_s_p90", "mixed", "upper tail of the autocorrelation times across units and records: long correlations in records that settle into another persistent state"),
    ("acf_", "system", "passive autocorrelation time"),
    ("onset_latency", "system", "response latency to the input onset"),
    ("spec_", "system", "passive spectrum"),
    ("noise_floor", "design", "how twins are integrated (shared integration pieces give an exact zero before the event) and the storage precision"),
    ("eff_", "design", "effect size scales with the intervention magnitude classes"),
    ("frac_eff_", "design", "share of near-zero effects is set by the lowest magnitude classes"),
    ("resp_frac", "mixed", "propagation through the system, thresholded against a fixed fraction of the scale (magnitude-dependent)"),
    ("decay_x_censored_frac", "mixed", "persistence relative to the window left after the event (onset design)"),
    ("decay_x_s_median", "system", "relaxation time after an event ends (all kinds pooled)"),
    ("decay_y_s_median", "system", "relaxation time of the readout effect after an event ends (all kinds pooled)"),
    ("decay_", "mixed", "relaxation after events of one kind, whose durations and magnitudes are set by the design"),
    ("self_decay", "system", "relaxation time of a kicked unit (weakly affected by clipping of large negative kicks)"),
    ("persistence_ratio", "mixed", "ratio of the network's and the kicked unit's relaxation times; the latter depends on the kick sizes"),
    ("init_", "mixed", "a system property (other persistent states) revealed only by the initial states of the design"),
    ("latency_y_peak", "mixed", "readout-effect timing, bounded by the window from the onset to the end (onset design)"),
    ("effect_end_over_peak", "mixed", "persistence relative to the window left after the event (onset and duration design)"),
    ("snr_floor", "design", "effect sizes over the design's numerical floor"),
    ("snr_param", "design", "effect sizes (magnitude classes) over the parameter spread"),
    ("kick_rel_scale", "design", "kick magnitudes of the design over the system scale"),
    ("current_abs", "design", "current magnitudes of the design"),
    ("current_duration", "design", "pulse durations of the design"),
    ("params_param_spread", "mixed", "the system's sensitivity to its parameter distribution, over the design's nominal records"),
    ("wnoise_param_spread", "mixed", "sensitivity to structural noise at the design's noise levels"),
    ("wnoise_sd_max", "design", "largest structural-noise level of the design"),
    ("input_scale", "design", "input levels of the design"),
    ("input_gain_elasticity", "mixed", "nonlinearity of the input response, a local slope over the design's input levels and schedules"),
    ("input_response_rms", "mixed", "input-response size over the design's input levels"),
    ("design_", "design", "the protocol design itself"),
]


def dependence(name: str) -> tuple[str, str]:
    """(class, reason) of a statistic key: 'system', 'design' or 'mixed' (DEPENDENCE_CLASSES)."""
    for pre, cls, why in _DEPENDENCE:
        if name.startswith(pre):
            return cls, why
    return "mixed", "not classified"


# ------------------------------------------------------------------------------------------------------------------ datasets
def load_dataset_dir(d, *, system_id: str | None = None, max_per_kind: int | None = None) -> tuple[dict, list[dict]]:
    """(public system record, trajectory records) of one system in a dataset directory of the benchmark's format:
    ``manifest.json`` ({"systems": {system_id: public record}, ...}), ``index.jsonl`` (one row per record: key, system_id, split,
    family, protocol, meta, info) and ``traj/<key>.npz`` (t, x, u, y). ``system_id`` is needed only when the manifest lists
    several systems. Every record is loaded by default (the construction of the calibration targets); with ``max_per_kind``, at
    most that many non-twin records per record kind (evenly spaced in index order) plus the twins of the kept records."""
    import json
    from pathlib import Path

    d = Path(d)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    systems = man.get("systems") or {}
    if system_id is None:
        if len(systems) != 1:
            raise ValueError(f"{d}: the manifest lists {len(systems)} systems; pass system_id")
        system_id = next(iter(systems))
    sysrec = systems[system_id]
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r.get("system_id", system_id) == system_id]
    if max_per_kind is not None:
        twins = [r for r in rows if (r.get("meta") or {}).get("twin_of")]
        by_kind: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if not (r.get("meta") or {}).get("twin_of"):
                by_kind[record_kind(r)].append(r)
        keep = [rs[i] for rs in by_kind.values() for i in _subsample(len(rs), int(max_per_kind))]
        kept = {r["key"] for r in keep}
        rows = keep + [r for r in twins if r["meta"]["twin_of"] in kept]
    recs = []
    for r in rows:
        with np.load(d / "traj" / f"{r['key']}.npz", allow_pickle=False) as z:
            recs.append({"t": z["t"], "x": z["x"], "u": z["u"], "y": z["y"], "protocol": r.get("protocol") or {},
                         "family": r.get("family"), "split": r.get("split"), "key": r.get("key"), "meta": r.get("meta") or {},
                         "info": r.get("info") or {}})
    return sysrec, recs


# ------------------------------------------------------------------------------------------------------------------ top level
def stats_of_dataset_dir(d) -> dict:
    """compute_all over EVERY record of one system's p4-dataset-1 directory (the targets' record selection; criterion 11 on the volume
    where the public part lives): {"system_id", "n_records", "stats"}."""
    pub, recs = load_dataset_dir(d)
    return {"system_id": pub["system_id"], "n_records": len(recs), "stats": compute_all(recs, pub)}


def compute_all(records: list[dict], sysrec: dict) -> dict:
    """Every statistic for ONE system (flat dict; counts under 'counts')."""
    if not records:
        raise ValueError("no records")
    sc = system_scales(records)
    out: dict[str, Any] = {"stat_version": STAT_VERSION}
    sizes = stats_sizes(records, sysrec)
    out["counts"] = {"n_records": sizes.pop("n_records"), "record_kinds": sizes.pop("record_kinds")}
    out.update(sizes)
    out.update(stats_rates(records, sc))
    out.update(stats_dimensionality(records, sc))
    # passive 95 % subspace (observational records, active units kept in their columns)
    obs = [r for r in records if record_kind(r).startswith("obs:")]
    basis = None
    if obs:
        X = np.concatenate([_arr(r, "x")[:: max(1, int(round(POOL_STRIDE_S / float(np.median(np.diff(np.asarray(r['t'], dtype=float)))))))]
                            for r in obs])
        Xc = X - X.mean(axis=0)
        U, s, Vt = np.linalg.svd(Xc, full_matrices=False)
        lam = s ** 2 / max(float((s ** 2).sum()), 1e-300)
        k = int(min(len(lam), np.searchsorted(np.cumsum(lam), 0.95 - 1e-12) + 1))
        basis = Vt[:k].T
    out.update(stats_timescales(records, sc))
    iv = stats_interventions(records, sysrec, sc, basis)
    out["counts"]["n_pairs"] = iv.pop("n_pairs", 0)
    eff_x, eff_y = iv.pop("_eff_rms_x", []), iv.pop("_eff_rms_y", [])
    out.update(iv)
    pu = stats_param_uncertainty(records, sc)
    out.update(pu)
    # effect size relative to the variability across parameter draws (the benchmark's "biological" variability)
    for nm, eff in (("x", eff_x), ("y", eff_y)):
        sp = pu.get(f"params_param_spread_{nm}_abs_rms")
        if eff and sp:
            out[f"snr_param_{nm}_median"] = _med([e / sp for e in eff])
            out[f"snr_param_{nm}_p10"] = _f(np.percentile([e / sp for e in eff], 10))
    out.update(stats_kick_clipping(records, sysrec))
    out.update(stats_init_states(records, sc))
    out.update(stats_input_gain(records, sc))
    out.update(stats_event_design(records))
    return {k: (_f(v) if isinstance(v, (float, np.floating)) else (int(v) if isinstance(v, (np.integer,)) else v)) for k, v in out.items()}


def pool(per_system: dict[str, dict], classes: dict[str, str]) -> dict:
    """Per statistic: the per-system values and {min, max, median, n} over all systems and per class."""
    names = sorted({k for s in per_system.values() for k, v in s.items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
    out = {}
    for nm in names:
        vals = {lab: s.get(nm) for lab, s in per_system.items()}
        ent = {"per_system": vals}
        groups = {"all": list(vals)}
        for lab, c in classes.items():
            groups.setdefault(c, []).append(lab)
        for g, labs in groups.items():
            v = [float(vals[lab]) for lab in labs if vals.get(lab) is not None and math.isfinite(float(vals[lab]))]
            ent[g] = {"min": min(v), "max": max(v), "median": float(np.median(v)), "n": len(v)} if v else {"min": None, "max": None, "median": None, "n": 0}
        out[nm] = ent
    return out


def compare(stats: dict, targets: dict, *, min_inside_frac: float = 0.5) -> dict:
    """Check statistics against target ranges.

    ``stats``: one system's ``compute_all`` output, or {label: compute_all output} for a suite. ``targets``: {statistic:
    {"target_range": [lo, hi], "check": bool, "min_inside_frac": float, "coverage": [a, b] | None, ...}} (the ``statistics``
    block of calibration_targets.json). Entries with ``check`` false are descriptive and skipped. For each checked statistic:
    the fraction of systems whose value lies inside the range, whether the suite's [min, max] overlaps the real range, the
    optional coverage condition (suite min <= a and suite max >= b) and the 'ok' flag (inside fraction >= the entry's
    min_inside_frac, default ``min_inside_frac``, AND overlap AND coverage). Statistics a suite does not produce are listed as
    missing."""
    suite = stats if stats and all(isinstance(v, dict) and "stat_version" in v for v in stats.values()) else {"system": stats}
    rep, n_ok, n_tested, missing = {}, 0, 0, []
    for nm, tg in targets.items():
        rng = tg.get("target_range")
        if tg.get("check") is False or not rng or rng[0] is None or rng[1] is None:
            continue
        lo, hi = float(rng[0]), float(rng[1])
        v = [float(s[nm]) for s in suite.values() if s.get(nm) is not None and not isinstance(s.get(nm), (dict, list, bool))]
        if not v:
            missing.append(nm)
            continue
        inside = float(np.mean([(lo <= a <= hi) for a in v]))
        real = tg.get("real_all") or {}
        rlo, rhi = real.get("min"), real.get("max")
        overlap = True if rlo is None or rhi is None else (min(v) <= rhi and max(v) >= rlo)
        cov = tg.get("coverage")
        covered = True if not cov else (min(v) <= float(cov[0]) and max(v) >= float(cov[1]))
        need = float(tg.get("min_inside_frac", min_inside_frac))
        ok = inside >= need and overlap and covered
        n_tested += 1
        n_ok += int(ok)
        rep[nm] = {"target_range": [lo, hi], "values": {"min": min(v), "median": float(np.median(v)), "max": max(v), "n": len(v)},
                   "inside_frac": inside, "min_inside_frac": need, "overlaps_real_range": bool(overlap), "coverage_ok": bool(covered),
                   "ok": bool(ok)}
    return {"stat_version": STAT_VERSION, "n_tested": n_tested, "n_ok": n_ok, "missing": missing, "min_inside_frac": min_inside_frac,
            "statistics": rep}
