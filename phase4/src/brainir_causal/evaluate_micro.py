"""Microstate equivalence under intervention and the interventional bisimulation-like test (benchmarks/causal_state_v1/PROTOCOL.md
sections 5.5-5.6; goal5 sections 32-33).

POOL (evalio.Pool): microstates, each with its observed history and the SIMULATED future readout from the exact microstate under S
intervention sequences and under no intervention ("none"). The model only encodes the histories (fresh copies).

5.5 MEV. CANDIDATE pairs = states of the SAME parameter draw from DIFFERENT pool source trajectories (states of one trajectory are
    trivially similar; different draws are different parameters); truth-only states (`main_pool`) never enter them. Latent distances
    are WHITENED: by the covariance of the model's encodings of PUBLIC training data (`latent_whitener`; eigenvalue floor 1e-6 x the
    largest, review H minor 11), else by the pool's own covariance (a development fallback, reported as `whiten_source`); either way the distance is
    invariant to invertible linear maps of z. For each sequence s the future divergence of a pair is the mean over the primary horizon
    and readout dimensions of the squared difference of the futures (in units of the public readout sd). MATCHED pairs = the M = 20
    closest candidate pairs in latent distance (a FIXED COUNT, ties at the threshold included; PROTOCOL 5.5, LOG P4-D14: a fixed
    QUANTILE cannot tighten with pool size, and for k >= 3 the 2 % quantile lies near 0.27 of the random distance, i.e. untestable by
    construction); RANDOM pairs = all candidate pairs; ratio_s = mean divergence of matched pairs / mean divergence of random pairs
    (the same matched set for every sequence). MEV = the MEAN OF ratio_s over the testable sequences (each sequence gets equal weight,
    so a large-effect sequence cannot dominate). 95 % CI by resampling pool source trajectories within their draw (a pair's weight =
    the product of its trajectories' multiplicities; the matched set is recomputed in every replicate as the closest pairs whose
    cumulative weight reaches M). NUMERICAL FLOOR (review H, B1; `floor_statistic`): the SAME statistic as the divergence (mean squared
    difference, public readout-sd units, rows 1..m of the primary horizon) between the two futures of each floor-state pair (a) the
    no-intervention future and a repeat run with a no-op breakpoint one sample after the restart, (b) the float64 continuation and the
    restart from the float32-rounded stored state; the floor is the larger of the two kinds' means over the floor states. A sequence
    is TESTABLE when its random-pair divergence is at least max(2 x floor, (2 f_s / y_sd)^2 = 0.01) (the detection floor: two effect
    floors). UNTESTABLE when the matched pairs are not close (median matched / median random latent distance > 0.2) or when no
    sequence is testable (untestable sequences are left out of the mean and listed). An untestable MEV does NOT satisfy criterion E
    (verdict.system_verdict). Every quantity is in readout-sd units, so scaling y changes nothing.
    SENSITIVITY (reported, never the verdict quantity): the same ratio under the draft's rule (the 2 % closest candidate pairs), with
    its own distance ratio and CI.
    Also reported (same candidate pairs, same rule, same resamples): truth-matched pairs (synthetic: z_true, whitened by its pool
    covariance), observation-matched pairs (the current readout, whitened) and PCA-matched pairs (the top-k public PCs of x, k = the
    model's k), each per sequence and averaged. TRUTH-EQUIVALENT pairs (synthetic: states of the full pool sharing `equiv_class`,
    including the truth-only states the builder constructs as equivalents: equal true causal state, different microstate detail that
    is visible in x) test the MODEL (review T round 3, N2): its whitened latent distance between equivalent states relative to the
    random candidate pairs (same whitening; a causal state maps them close: ratio near 0), and its PREDICTED-future divergence under
    the pool sequences (the divergence statistic on the model's own predictions from each state's history), relative to the
    detection floor of 5.5 (max(2 x numerical floor, the effect-floor term)) and to the predicted divergence of random candidate
    pairs. The divergence of their TRUE futures is zero up to numerics by construction: reported only as the builder's check.
5.6 BISIMULATION-LIKE (descriptive). The candidate pairs of 5.5 (truth-only states excluded), sampled evenly across 10 quantile
    bins of latent distance. Per pair: (1) the RMS
    difference of the current readouts; (2) per intervention kind, the RMS difference of the two states' RESPONSES (future under the
    sequence minus future under "none"), averaged over the sequences of that kind; (3) per sequence, the latent distance one primary
    horizon later (re-encoded from each state's TRUE future history) over the initial latent distance. Curves over the bins and
    Spearman correlations with the initial distance. No formal bisimulation claim.
"""

from __future__ import annotations

import numpy as np

from . import stats as S
from .evalio import PRIMARY, EvalSystem, Pool, detection_floor_sq
from .fresh import as_fresh, safe_call

MATCH_M = 20                 # matched pairs: the M closest candidate pairs (a fixed count; PROTOCOL 5.5)
MATCH_Q_SENS = 0.02          # sensitivity variant only (the draft's rule): the 2 % closest candidate pairs
RESOLUTION_MAX = 0.2
FLOOR_FACTOR = 2.0
MEV_CAP = 10.0               # the worst admissible MEV, charged to non-finite bootstrap replicates (finite bounds, PROTOCOL 11)
EIG_FLOOR = 1e-6             # whitening eigenvalue floor relative to the largest eigenvalue (review H, minor 11)
CHUNK_ELEMS = 16_000_000     # array elements per chunk of pair differences (pools of 600 states have about 21,000 pairs)


# ------------------------------------------------------------------------------------------------------------ whitening
def whitener(A: np.ndarray, eig_floor: float = EIG_FLOOR) -> tuple[np.ndarray, np.ndarray]:
    """(mean, W) such that (a - mean) @ W is whitened with the FULL covariance of A; eigenvalues below eig_floor x the largest are
    floored."""
    A = np.atleast_2d(np.asarray(A, np.float64))
    if A.shape[0] == 1 and A.shape[1] > 1:
        A = A.T
    mu = A.mean(0)
    C = np.atleast_2d(np.cov((A - mu).T)) if A.shape[1] > 1 else np.array([[float(np.var(A[:, 0]))]])
    lam, V = np.linalg.eigh(C)
    lam = np.maximum(lam, max(float(lam.max()), 1e-300) * eig_floor)
    return mu, V @ np.diag(1.0 / np.sqrt(lam)) @ V.T


def latent_whitener(model, sid: str, hists: list[tuple[np.ndarray, np.ndarray, float]], eig_floor: float = EIG_FLOOR):
    """Whitener from the model's encodings of PUBLIC training histories [(x_hist, u_hist, dt), ...]; None if encodings fail."""
    F = as_fresh(model)
    Z = []
    for xh, uh, dt in hists:
        z, err = safe_call(F.encode, sid, xh, uh, dt)
        if err or z is None or not np.isfinite(z).all():
            return None
        Z.append(np.asarray(z, float).reshape(-1))
    if len(Z) < 3:
        return None
    return whitener(np.stack(Z), eig_floor)


# ------------------------------------------------------------------------------------------------------------ pair machinery
def _pairs(pool: Pool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(i, j, trajectory index of i, trajectory index of j) for same-draw, different-trajectory pairs; plus trajectory -> draw."""
    draws = np.array([s.draw for s in pool.states])
    trajs = np.array([s.traj for s in pool.states])
    names, tix = np.unique(trajs, return_inverse=True)
    ii, jj = np.triu_indices(len(pool.states), 1)
    keep = (draws[ii] == draws[jj]) & (tix[ii] != tix[jj])
    ii, jj = ii[keep], jj[keep]
    traj_draw = np.array([draws[np.flatnonzero(tix == t)[0]] for t in range(len(names))])
    return ii, jj, tix, traj_draw


def _dist(A: np.ndarray, ii: np.ndarray, jj: np.ndarray, wh: tuple[np.ndarray, np.ndarray] | None) -> np.ndarray:
    mu, W = wh if wh is not None else whitener(A)
    Aw = (A - mu) @ W
    return np.sqrt(((Aw[ii] - Aw[jj]) ** 2).sum(axis=1))


def _futures(pool: Pool, sysc: EvalSystem, seqs: list[str]) -> dict[str, np.ndarray]:
    m = sysc.horizon_steps(PRIMARY, pool.dt)
    out = {}
    for s in seqs:
        out[s] = np.stack([np.asarray(st.futures[s], np.float64)[1: m + 1] for st in pool.states]) / sysc.y_sd
    return out


def _predicted_futures(F, sid: str, states: list, pool: Pool, sysc: EvalSystem, seqs: list[str]) -> dict[str, np.ndarray]:
    """{sequence: (n_states, m, n_y)} the model's PREDICTED readout futures of the given pool states under the pool sequences (rows
    1..m of the primary horizon, readout-sd units; 'none' = the model's prediction without events under the common input), from
    each state's own history (`intervention_effect`); NaN where the model fails or abstains."""
    m = sysc.horizon_steps(PRIMARY, pool.dt)
    n_y = int(sysc.n_y)
    base_u = (pool.sequences.get("none") or next(iter(pool.sequences.values()), {}) or {}).get("u_future")
    out = {s: np.full((len(states), m, n_y), np.nan) for s in seqs}
    for k, st in enumerate(states):
        for s in seqs:
            spec = pool.sequences.get(s) or {}
            uf = spec.get("u_future", base_u)
            if uf is None:
                continue
            ev = [] if s == "none" else list(spec.get("events") or [])
            r, err = safe_call(F.intervention_effect, sid, st.x_hist, st.u_hist, np.asarray(uf, np.float64), ev, pool.dt)
            if err is not None or not isinstance(r, dict) or r.get("abstain") or r.get("y_int") is None:
                continue
            y = np.asarray(r["y_int"], np.float64)
            y = y[:, None] if y.ndim == 1 else y
            if y.shape[0] < m + 1 or y.shape[1] != n_y or not np.isfinite(y[1: m + 1]).all():
                continue
            out[s][k] = y[1: m + 1] / sysc.y_sd
    return out


def pair_divergence(Fut: np.ndarray, ii: np.ndarray, jj: np.ndarray) -> np.ndarray:
    """Mean squared difference of the futures Fut (states x rows x readouts) for every pair (ii[k], jj[k]), in chunks."""
    n = len(ii)
    out = np.empty(n)
    per = max(1, CHUNK_ELEMS // max(1, int(np.prod(Fut.shape[1:]))))
    for a in range(0, n, per):
        d = Fut[ii[a: a + per]] - Fut[jj[a: a + per]]
        out[a: a + per] = (d * d).reshape(len(d), -1).mean(axis=1)
    return out


class _Match:
    """Matched-set rule on one distance vector: the closest pairs whose cumulative (resampling) weight reaches `need`, ties at the
    threshold distance included; pairs of weight 0 (not in the resample) never count."""

    def __init__(self, d: np.ndarray):
        self.d = np.asarray(d, np.float64)
        self.order = np.argsort(self.d, kind="stable")
        self.ds = self.d[self.order]

    def select(self, w: np.ndarray, need: float) -> np.ndarray | None:
        cw = np.cumsum(w[self.order])
        if len(cw) == 0 or cw[-1] <= 0:
            return None
        k = min(int(np.searchsorted(cw, min(float(need), float(cw[-1])) - 1e-9)), len(cw) - 1)
        idx = self.order[: int(np.searchsorted(self.ds, self.ds[k], side="right"))]
        return idx[w[idx] > 0]


def _ratios(DIV: np.ndarray, idx: np.ndarray | None, w: np.ndarray, rm: np.ndarray) -> np.ndarray:
    """Per sequence: weighted mean divergence of the matched pairs idx over the random pairs' weighted mean rm."""
    if idx is None or len(idx) == 0:
        return np.full(DIV.shape[0], np.nan)
    ws = w[idx]
    mm = (DIV[:, idx] @ ws) / ws.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(rm > 0, mm / rm, np.nan)


def _boot_ratios(DIV: np.ndarray, matchers: dict[str, _Match], rules: dict[str, tuple[str, str, float]], ti: np.ndarray, tj: np.ndarray,
                 traj_draw: np.ndarray, n_boot: int, seed: int) -> dict[str, np.ndarray]:
    """Bootstrap replicates (n_boot x S) of the matched ratios for every rule {name: (matcher name, "count" | "quantile", M or q)},
    all on the same resamples (paired). The unit is the pool source trajectory within its draw; a pair's weight = the product of its
    trajectories' multiplicities; the random-pair mean and the matched set are recomputed in every replicate."""
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(traj_draw == g) for g in np.unique(traj_draw)]
    out = {name: np.full((n_boot, DIV.shape[0]), np.nan) for name in rules}
    for b in range(n_boot):
        c = np.zeros(len(traj_draw))
        for members in groups:
            np.add.at(c, members[rng.integers(0, len(members), len(members))], 1.0)
        w = c[ti] * c[tj]
        tot = float(w.sum())
        if tot <= 0:
            continue
        rm = (DIV @ w) / tot
        for name, (mname, kind, par) in rules.items():
            need = par if kind == "count" else par * tot
            out[name][b] = _ratios(DIV, matchers[mname].select(w, need), w, rm)
    return out


def _summ(point: np.ndarray, reps: np.ndarray, seqs: list[str], testable: np.ndarray) -> dict:
    """Mean over testable sequences with its CI, and the per-sequence ratios. A replicate whose mean is non-finite (no matched pair
    with positive weight, or no finite testable sequence) is charged the worst admissible value MEV_CAP: counted against the claim
    (MEV <= tau), with finite bounds (PROTOCOL 11)."""
    if not testable.any():
        return {"mean": float("nan"), "ci95": [float("nan")] * 2, "per_sequence": {s: float(v) for s, v in zip(seqs, point)},
                "n_nonfinite_reps": 0}
    with np.errstate(invalid="ignore"):
        mean_rep = np.nanmean(reps[:, testable], axis=1) if reps is not None else None
    est = S.make_estimate(float(np.nanmean(point[testable])) if np.isfinite(point[testable]).any() else float("nan"), mean_rep, 0,
                          worst=MEV_CAP)
    return {"mean": est.point, "ci95": est.ci95 if mean_rep is not None else [float("nan")] * 2,
            "per_sequence": {s: float(v) for s, v in zip(seqs, point)}, "n_nonfinite_reps": est.n_nonfinite_reps}


def floor_statistic(pool: Pool, sysc: EvalSystem) -> dict:
    """The MEV numerical floor (PROTOCOL 5.5; review H, B1) with the divergence's own statistic: for every floor state and pair kind
    ("noop": [no-intervention future, repeat with a no-op breakpoint one sample after the restart]; "f32": [float64 continuation,
    restart from the float32-rounded stored state]) the mean squared difference of the two futures in public readout-sd units over
    rows 1..m of the primary horizon; per kind the mean over the floor states; the floor is the larger kind mean. Without floor
    futures: the pool's (or states') `floor_div`, which must already be this statistic; else 0 (reported as source "none")."""
    m = sysc.horizon_steps(PRIMARY, pool.dt)
    per_kind: dict[str, list[float]] = {}
    for st in pool.states:
        for kind, pair in (st.floor_futures or {}).items():
            if pair is None or len(pair) != 2:
                continue
            a, b = (np.asarray(v, np.float64) for v in pair)
            a = a[:, None] if a.ndim == 1 else a
            b = b[:, None] if b.ndim == 1 else b
            if len(a) <= m or len(b) <= m:
                continue
            d = (a[1: m + 1] - b[1: m + 1]) / sysc.y_sd
            v = float(np.mean(d * d))
            per_kind.setdefault(kind, []).append(v if np.isfinite(v) else float("inf"))
    if per_kind:
        means = {k: float(np.mean(v)) for k, v in per_kind.items()}
        return {"floor": float(max(means.values())), "per_kind": means, "n_states": {k: len(v) for k, v in per_kind.items()},
                "source": "floor_futures"}
    if pool.floor_div is not None:
        return {"floor": float(pool.floor_div), "per_kind": {}, "n_states": {}, "source": "pool.floor_div"}
    fl = [st.floor_div for st in pool.states if st.floor_div is not None]
    if fl:
        return {"floor": float(np.mean(fl)), "per_kind": {}, "n_states": {"state": len(fl)}, "source": "state.floor_div"}
    return {"floor": 0.0, "per_kind": {}, "n_states": {}, "source": "none"}


def main_pool(pool: Pool) -> Pool:
    """The pool without its TRUTH-ONLY states (synthetic truth-equivalent microstates constructed by the dataset builder, marked
    meta["truth_only"]): those enter only the truth-equivalent comparison, never the model's pairing or the bisimulation curves."""
    keep = [st for st in pool.states if not st.meta.get("truth_only")]
    if len(keep) == len(pool.states):
        return pool
    return Pool(system_id=pool.system_id, dt=pool.dt, states=keep, sequences=pool.sequences, floor_div=pool.floor_div, meta=pool.meta)


# ------------------------------------------------------------------------------------------------------------ 5.5
def _nan_mev(res: dict, testable: bool, reason: str | None, **extra) -> dict:
    return {**res, "testable": testable, "untestable_reason": reason, "MEV": {"point": float("nan"), "ci95": [float("nan")] * 2}, **extra}


def eval_microstate(model, sysc: EvalSystem, pool: Pool, *, whiten_z=None, k_model: int | None = None, m_match: int = MATCH_M,
                    q_sens: float = MATCH_Q_SENS, n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """5.5: MEV (fixed-count matching) with its testability, CI, the quantile-rule sensitivity and the comparison pairings (see the
    module docstring)."""
    F = as_fresh(model)
    sid = sysc.system_id
    full_pool, pool = pool, main_pool(pool)
    res: dict = {"n_states": len(pool.states), "n_truth_only_states": len(full_pool.states) - len(pool.states)}
    if len(pool.states) < 10:
        return _nan_mev(res, False, "pool too small")
    Z, n_fail = [], 0
    for st in pool.states:
        z, err = safe_call(F.encode, sid, st.x_hist, st.u_hist, pool.dt)
        if err or z is None or not np.isfinite(np.asarray(z, float)).all():
            n_fail += 1
            Z.append(None)
        else:
            Z.append(np.asarray(z, float).reshape(-1))
    if n_fail:
        return _nan_mev(res, True, None, n_encode_failed=n_fail, note="non-finite or failed encodings")
    Z = np.stack(Z)
    ii, jj, tix, traj_draw = _pairs(pool)
    if len(ii) < 10:
        return _nan_mev(res, False, "too few same-draw pairs")
    seqs = [sq for sq in pool.sequences if all(sq in st.futures for st in pool.states)]
    if "none" not in seqs and all("none" in st.futures for st in pool.states):
        seqs.append("none")
    Fut = _futures(pool, sysc, seqs)
    DIV = np.stack([pair_divergence(Fut[sq], ii, jj) for sq in seqs])
    n_pairs = len(ii)
    res["n_pairs"] = n_pairs
    res["whiten_source"] = "train" if whiten_z is not None else "pool"
    rm = DIV.mean(1)
    fls = floor_statistic(full_pool, sysc)
    floor = fls["floor"]
    detect = detection_floor_sq(sysc.floor_frac)
    seq_testable = (rm >= FLOOR_FACTOR * floor) & (rm >= detect)
    # distance vectors: the model's latent and the comparison pairings (same candidate pairs, same rule, same resamples)
    dz = _dist(Z, ii, jj, whiten_z)
    dists = {"latent": dz}
    Yn = np.stack([np.asarray(st.y_now, float).reshape(-1) for st in pool.states]) / sysc.y_sd
    dists["observation"] = _dist(Yn, ii, jj, None)
    k_eff = int(min(k_model or Z.shape[1], sysc.pca_comps.shape[0]))
    X = np.stack([st.x_hist[-1] for st in pool.states]).astype(np.float64)
    dists["pca_k"] = _dist((X - sysc.pca_mean) @ sysc.pca_comps[:k_eff].T, ii, jj, None)
    if all(st.z_true is not None for st in pool.states):
        dists["truth"] = _dist(np.stack([np.asarray(st.z_true, float).reshape(-1) for st in pool.states]), ii, jj, None)
    matchers = {name: _Match(d) for name, d in dists.items()}
    rules = {name: (name, "count", float(m_match)) for name in dists}
    rules["latent_quantile"] = ("latent", "quantile", float(q_sens))
    ones = np.ones(n_pairs)
    sel_m = matchers["latent"].select(ones, m_match)
    sel_q = matchers["latent"].select(ones, q_sens * n_pairs)
    med_all = float(np.median(dz))
    rho = float(np.median(dz[sel_m]) / med_all) if med_all > 0 else float("inf")
    rho_q = float(np.median(dz[sel_q]) / med_all) if med_all > 0 else float("inf")
    points = {name: _ratios(DIV, matchers[mn].select(ones, par if kind == "count" else par * n_pairs), ones, rm)
              for name, (mn, kind, par) in rules.items()}
    boots = _boot_ratios(DIV, matchers, rules, tix[ii], tix[jj], traj_draw, n_boot, seed)
    reasons = []
    if not rho <= RESOLUTION_MAX:
        reasons.append(f"matched pairs not close (median distance ratio {rho:.3g} > {RESOLUTION_MAX})")
    if not seq_testable.any():
        reasons.append(f"no sequence's random-pair divergence reaches max({FLOOR_FACTOR} x the numerical floor {floor:.3g}, the "
                       f"detection floor {detect:.3g})")
    lat = _summ(points["latent"], boots["latent"], seqs, seq_testable)
    # the descriptive value is always reported; the verdict quantity MEV is NaN (with the reason) when the MEV is untestable
    res["MEV_descriptive"] = {"point": lat["mean"], "ci95": lat["ci95"], "n_nonfinite_reps": lat["n_nonfinite_reps"]}
    res["MEV"] = ({"point": lat["mean"], "ci95": lat["ci95"], "n_nonfinite_reps": lat["n_nonfinite_reps"]} if not reasons else
                  {"point": float("nan"), "ci95": [float("nan"), float("nan")], "untestable": "; ".join(reasons)})
    res["matched"] = {"rule": "count", "M": int(m_match), "n_pairs": len(sel_m), "fraction_of_candidates": len(sel_m) / n_pairs,
                      "median_dist_ratio": rho}
    res["per_sequence"] = {sq: {"ratio": float(r), "random_div": float(v), "testable": bool(t)}
                           for sq, r, v, t in zip(seqs, points["latent"], rm, seq_testable)}
    qs = _summ(points["latent_quantile"], boots["latent_quantile"], seqs, seq_testable)
    res["sensitivity"] = {"quantile_rule": {"q": float(q_sens), "MEV": {"point": qs["mean"], "ci95": qs["ci95"]}, "n_pairs": len(sel_q),
                                            "median_dist_ratio": rho_q,
                                            "testable_under_its_rule": bool(rho_q <= RESOLUTION_MAX and seq_testable.any()),
                                            "per_sequence": qs["per_sequence"]}}
    res["comparisons"] = {name: _summ(points[name], boots[name], seqs, seq_testable) for name in dists if name != "latent"}
    res["comparisons"]["pca_k"]["k"] = k_eff
    # truth-equivalent pairs (synthetic; review T round 3, N2): every pair of states of the FULL pool (incl. truth-only states)
    # sharing an equivalence class. They test the MODEL: its whitened latent distance (same whitening as the MEV) relative to the
    # random candidate pairs, and its predicted-future divergence relative to the detection floor and to random pairs. The true-future
    # divergence (zero up to numerics by construction) is only the builder's construction check.
    classes: dict = {}
    for i_s, st in enumerate(full_pool.states):
        if st.equiv_class is not None:
            classes.setdefault(st.equiv_class, []).append(i_s)
    eq_pairs = [(a, b) for mem in classes.values() for x, a in enumerate(mem) for b in mem[x + 1:]]
    if eq_pairs:
        res["comparisons"]["truth_equivalent"] = _truth_equivalent(F, sid, full_pool, pool, sysc, Z, dz, ii, jj, whiten_z, seqs,
                                                                   seq_testable, rm, floor, detect, classes, eq_pairs, seed)
    res["numerical_floor"] = float(floor)
    res["floor_detail"] = fls
    res["detection_floor"] = detect
    res["k"] = int(Z.shape[1])
    res["testable"] = not reasons
    res["untestable_reason"] = "; ".join(reasons) or None
    res["sequences"] = seqs
    res["_units"] = {"dz": dz.tolist(), "ti": tix[ii].tolist(), "tj": tix[jj].tolist(), "traj_draw": traj_draw.tolist(),
                     "div": DIV.tolist()}
    return res


def _finite_mean(v) -> float:
    a = np.asarray(v, np.float64).reshape(-1)
    a = a[np.isfinite(a)]
    return float(a.mean()) if a.size else float("nan")


def _truth_equivalent(F, sid: str, full_pool: Pool, pool: Pool, sysc: EvalSystem, Z: np.ndarray, dz: np.ndarray, ii: np.ndarray,
                      jj: np.ndarray, whiten_z, seqs: list[str], seq_testable: np.ndarray, rm: np.ndarray, floor: float, detect: float,
                      classes: dict, eq_pairs: list[tuple[int, int]], seed: int, n_random_max: int = 200) -> dict:
    """The truth-equivalent comparison of 5.5 (module docstring; review T round 3, N2)."""
    full = full_pool.states
    main_row = {id(st): r for r, st in enumerate(pool.states)}
    need = sorted({a for a, _ in eq_pairs} | {b for _, b in eq_pairs})
    enc: dict[int, np.ndarray] = {}
    n_fail = 0
    for i_f in need:
        r = main_row.get(id(full[i_f]))
        if r is not None:
            enc[i_f] = Z[r]
            continue
        z, err = safe_call(F.encode, sid, full[i_f].x_hist, full[i_f].u_hist, full_pool.dt)
        zz = None if err or z is None else np.asarray(z, np.float64).reshape(-1)
        if zz is None or zz.shape[0] != Z.shape[1] or not np.isfinite(zz).all():
            n_fail += 1
            continue
        enc[i_f] = zz
    ok = [(a, b) for a, b in eq_pairs if a in enc and b in enc]
    out: dict = {"n_pairs": len(eq_pairs), "n_classes": len(classes), "n_pairs_encoded": len(ok), "n_encode_failed": n_fail}
    mu, W = whiten_z if whiten_z is not None else whitener(Z)
    d_eq = np.array([float(np.sqrt(((((enc[a] - mu) @ W) - ((enc[b] - mu) @ W)) ** 2).sum())) for a, b in ok])
    med_r, mean_r = float(np.median(dz)), float(np.mean(dz))
    out["latent_distance_ratio"] = float(np.median(d_eq) / med_r) if len(d_eq) and med_r > 0 else float("nan")
    out["latent_distance_ratio_mean"] = float(np.mean(d_eq) / mean_r) if len(d_eq) and mean_r > 0 else float("nan")
    # the model's predicted futures: the states of the encoded equivalent pairs and a seeded sample of random candidate pairs
    rng = np.random.default_rng([int(seed), 7919])
    n_r = int(min(len(ii), max(len(ok), 1) * 2, n_random_max))
    pick = np.sort(rng.choice(len(ii), size=n_r, replace=False)) if n_r else np.zeros(0, int)
    eq_states = sorted({a for a, _ in ok} | {b for _, b in ok})
    rnd_states = sorted({int(ii[k]) for k in pick} | {int(jj[k]) for k in pick})
    states = [full[i] for i in eq_states] + [pool.states[i] for i in rnd_states]
    pos_eq = {i: k for k, i in enumerate(eq_states)}
    pos_rd = {i: len(eq_states) + k for k, i in enumerate(rnd_states)}
    PF = _predicted_futures(F, sid, states, full_pool, sysc, seqs)
    ea = np.array([pos_eq[a] for a, _ in ok], int)
    eb = np.array([pos_eq[b] for _, b in ok], int)
    ra = np.array([pos_rd[int(ii[k])] for k in pick], int)
    rb = np.array([pos_rd[int(jj[k])] for k in pick], int)
    gate = max(FLOOR_FACTOR * float(floor), float(detect))
    pred_eq, pred_rd, over, rel = {}, {}, {}, {}
    for s in seqs:
        de = pair_divergence(PF[s], ea, eb) if len(ea) else np.zeros(0)
        dr = pair_divergence(PF[s], ra, rb) if len(ra) else np.zeros(0)
        pred_eq[s] = _finite_mean(de)
        pred_rd[s] = _finite_mean(dr)
        over[s] = pred_eq[s] / gate if gate > 0 else float("nan")
        rel[s] = pred_eq[s] / pred_rd[s] if pred_rd[s] and np.isfinite(pred_rd[s]) and pred_rd[s] > 0 else float("nan")
    test = [s for s, t in zip(seqs, seq_testable) if t]
    out["predicted_divergence"] = {"per_sequence": pred_eq, "random_pairs_per_sequence": pred_rd, "n_random_pairs": int(n_r),
                                   "over_detection_floor": over, "relative_to_random": rel, "detection_floor": gate,
                                   "mean_over_detection_floor": _finite_mean([over[s] for s in test]),
                                   "mean_relative_to_random": _finite_mean([rel[s] for s in test])}
    # the builder's construction check: TRUE futures of equivalent states agree up to numerics
    if all(all(sq in st.futures for sq in seqs) for st in full):
        FutF = _futures(full_pool, sysc, seqs)
        ta, tb = np.array([a for a, _ in eq_pairs]), np.array([b for _, b in eq_pairs])
        DIV_eq = np.stack([pair_divergence(FutF[sq], ta, tb) for sq in seqs])
        with np.errstate(divide="ignore", invalid="ignore"):
            r_eq = np.where(rm > 0, DIV_eq.mean(1) / rm, np.nan)
        out["construction_check"] = {"true_future_ratio": float(np.nanmean(r_eq[seq_testable])) if seq_testable.any() else float("nan"),
                                     "per_sequence": {sq: float(v) for sq, v in zip(seqs, r_eq)},
                                     "note": "true futures of truth-equivalent states: zero up to numerics by construction (a check of "
                                             "the dataset builder, not of the model)"}
    return out


# ------------------------------------------------------------------------------------------------------------ 5.6
def eval_bisimulation(model, sysc: EvalSystem, pool: Pool, *, whiten_z=None, n_bins: int = 10, max_pairs: int = 3000,
                      seed: int = 0) -> dict:
    """5.6: bisimulation-like curves against the initial latent distance (descriptive)."""
    from scipy.stats import spearmanr
    F = as_fresh(model)
    sid = sysc.system_id
    pool = main_pool(pool)
    m = sysc.horizon_steps(PRIMARY, pool.dt)
    Z = []
    for st in pool.states:
        z, err = safe_call(F.encode, sid, st.x_hist, st.u_hist, pool.dt)
        if err or z is None or not np.isfinite(np.asarray(z, float)).all():
            return {"note": "non-finite or failed encodings"}
        Z.append(np.asarray(z, float).reshape(-1))
    Z = np.stack(Z)
    ii, jj, _, _ = _pairs(pool)
    if len(ii) < n_bins * 2:
        return {"note": "too few pairs"}
    mu, W = whiten_z if whiten_z is not None else whitener(Z)
    Zw = (Z - mu) @ W
    d0 = np.sqrt(((Zw[ii] - Zw[jj]) ** 2).sum(1))
    rng = np.random.default_rng(seed)
    edges = np.quantile(d0, np.linspace(0, 1, n_bins + 1))
    b = np.clip(np.searchsorted(edges, d0, side="right") - 1, 0, n_bins - 1)
    per = max(1, max_pairs // n_bins)
    pick = np.concatenate([rng.permutation(np.flatnonzero(b == k))[:per] for k in range(n_bins)])
    ii, jj, d0, b = ii[pick], jj[pick], d0[pick], b[pick]
    sd = sysc.y_sd
    Yn = np.stack([np.asarray(st.y_now, float).reshape(-1) for st in pool.states]) / sd
    q1 = np.sqrt(((Yn[ii] - Yn[jj]) ** 2).mean(1))
    seqs = [s for s in pool.sequences if s != "none" and all(s in st.futures for st in pool.states)]
    has_none = all("none" in st.futures for st in pool.states)
    resp_by_kind: dict[str, list[np.ndarray]] = {}
    if has_none:
        base = np.stack([np.asarray(st.futures["none"], float)[1: m + 1] for st in pool.states]) / sd
        for s in seqs:
            fut = np.stack([np.asarray(st.futures[s], float)[1: m + 1] for st in pool.states]) / sd
            diff = np.sqrt(pair_divergence(fut - base, ii, jj))
            kind = str(pool.sequences[s].get("kind", s))
            resp_by_kind.setdefault(kind, []).append(diff)
    q2 = {k: np.mean(np.stack(v), axis=0) for k, v in resp_by_kind.items()}
    q3: dict[str, np.ndarray] = {}
    involved = np.unique(np.concatenate([ii, jj]))
    for s in (["none"] if has_none else []) + seqs:
        if not all(st.x_futures is not None and s in st.x_futures for st in pool.states):
            continue
        uf = np.asarray(pool.sequences.get(s, {}).get("u_future", None), float) if s in pool.sequences else None
        Zf = np.full(Z.shape, np.nan)
        ok = True
        for a in involved:
            st = pool.states[a]
            xf = np.asarray(st.x_futures[s], float)
            if len(xf) <= m:
                ok = False
                break
            u_next = uf[1: m + 1] if uf is not None and uf.ndim == 2 and len(uf) > m else np.repeat(st.u_hist[-1:], m, axis=0)
            z, err = safe_call(F.encode, sid, np.vstack([st.x_hist, xf[1: m + 1]]), np.vstack([st.u_hist, u_next]), pool.dt)
            if err or z is None or not np.isfinite(np.asarray(z, float)).all():
                ok = False
                break
            Zf[a] = np.asarray(z, float).reshape(-1)
        if not ok:
            continue
        Zfw = (Zf - mu) @ W
        d1 = np.sqrt(((Zfw[ii] - Zfw[jj]) ** 2).sum(1))
        q3[s] = d1 / np.maximum(d0, 1e-12)
    bins = []
    for k in range(n_bins):
        sel = b == k
        if not sel.any():
            continue
        row = {"bin": k, "n": int(sel.sum()), "latent_dist": float(d0[sel].mean()), "readout_diff": float(q1[sel].mean()),
               "response_diff": {kk: float(v[sel].mean()) for kk, v in q2.items()},
               "latent_expansion": {s: float(np.median(v[sel])) for s, v in q3.items()}}
        bins.append(row)

    def rho(v):
        r = spearmanr(d0, v)
        return float(r.statistic) if np.isfinite(r.statistic) else float("nan")

    return {"n_pairs": len(ii), "bins": bins,
            "spearman": {"readout_diff": rho(q1), **{f"response_diff:{k}": rho(v) for k, v in q2.items()},
                         **{f"latent_expansion:{s}": rho(v) for s, v in q3.items()}},
            "latent_expansion_median": {s: float(np.median(v)) for s, v in q3.items()},
            "whiten_source": "train" if whiten_z is not None else "pool"}
