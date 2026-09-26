"""Microstate equivalence under intervention and the interventional bisimulation-like test (benchmarks/causal_state_v1/PROTOCOL.md
sections 5.5-5.6; goal5 sections 32-33).

POOL (evalio.Pool): microstates, each with its observed history and the SIMULATED future readout from the exact microstate under S
intervention sequences and under no intervention ("none"). The model only encodes the histories (fresh copies).

5.5 MEV. CANDIDATE pairs = states of the SAME parameter draw from DIFFERENT pool source trajectories (states of one trajectory are
    trivially similar; different draws are different parameters); truth-only states (`main_pool`) never enter them. Latent distances
    are WHITENED: by the covariance of the model's encodings of PUBLIC training data (`latent_whitener`; eigenvalue floor 1e-8 x the
    largest), else by the pool's own covariance (a development fallback, reported as `whiten_source`); either way the distance is
    invariant to invertible linear maps of z. For each sequence s the future divergence of a pair is the mean over the primary horizon
    and readout dimensions of the squared difference of the futures (in units of the public readout sd). MATCHED pairs = the M = 20
    closest candidate pairs in latent distance (a FIXED COUNT, ties at the threshold included; PROTOCOL 5.5, LOG P4-D14: a fixed
    QUANTILE cannot tighten with pool size, and for k >= 3 the 2 % quantile lies near 0.27 of the random distance, i.e. untestable by
    construction); RANDOM pairs = all candidate pairs; ratio_s = mean divergence of matched pairs / mean divergence of random pairs
    (the same matched set for every sequence). MEV = the MEAN OF ratio_s over the testable sequences (each sequence gets equal weight,
    so a large-effect sequence cannot dominate). 95 % CI by resampling pool source trajectories within their draw (a pair's weight =
    the product of its trajectories' multiplicities; the matched set is recomputed in every replicate as the closest pairs whose
    cumulative weight reaches M). UNTESTABLE when the matched pairs are not close (median matched / median random latent distance >
    0.2) or when no sequence's random pairs diverge at least 2x the numerical floor (sequences below the floor are left out of the mean
    and listed).
    SENSITIVITY (reported, never the verdict quantity): the same ratio under the draft's rule (the 2 % closest candidate pairs), with
    its own distance ratio and CI.
    Also reported (same candidate pairs, same rule, same resamples): truth-matched pairs (synthetic: z_true, whitened by its pool
    covariance), observation-matched pairs (the current readout, whitened) and PCA-matched pairs (the top-k public PCs of x, k = the
    model's k), each per sequence and averaged; and truth-EQUIVALENT pairs (synthetic: states sharing `equiv_class`, including the
    truth-only states constructed as equivalents: their mean divergence relative to the random pairs).
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
from .evalio import PRIMARY, EvalSystem, Pool
from .fresh import as_fresh, safe_call

MATCH_M = 20                 # matched pairs: the M closest candidate pairs (a fixed count; PROTOCOL 5.5)
MATCH_Q_SENS = 0.02          # sensitivity variant only (the draft's rule): the 2 % closest candidate pairs
RESOLUTION_MAX = 0.2
FLOOR_FACTOR = 2.0
EIG_FLOOR = 1e-8
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
    """Mean over testable sequences with its CI, and the per-sequence ratios."""
    if not testable.any():
        return {"mean": float("nan"), "ci95": [float("nan")] * 2, "per_sequence": {s: float(v) for s, v in zip(seqs, point)}}
    mean_rep = np.nanmean(reps[:, testable], axis=1) if reps is not None else None
    return {"mean": float(np.nanmean(point[testable])), "ci95": S.percentile_ci(mean_rep) if mean_rep is not None else [float("nan")] * 2,
            "per_sequence": {s: float(v) for s, v in zip(seqs, point)}}


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
    floor = pool.floor_div
    if floor is None:
        fl = [st.floor_div for st in pool.states if st.floor_div is not None]
        floor = float(np.mean(fl)) if fl else 0.0
    seq_testable = rm >= FLOOR_FACTOR * float(floor)
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
        reasons.append(f"no sequence's random pairs diverge {FLOOR_FACTOR} x the numerical floor {float(floor):.3g}")
    lat = _summ(points["latent"], boots["latent"], seqs, seq_testable)
    res["MEV"] = {"point": lat["mean"], "ci95": lat["ci95"]}
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
    # truth-equivalent pairs (synthetic): every pair of states of the FULL pool (incl. truth-only states) sharing an equivalence class,
    # their mean future divergence relative to the random pairs of the main pool
    classes: dict = {}
    for i_s, st in enumerate(full_pool.states):
        if st.equiv_class is not None:
            classes.setdefault(st.equiv_class, []).append(i_s)
    eq_pairs = [(a, b) for mem in classes.values() for x, a in enumerate(mem) for b in mem[x + 1:]]
    if eq_pairs and all(all(sq in st.futures for sq in seqs) for st in full_pool.states):
        FutF = _futures(full_pool, sysc, seqs)
        ea, eb = np.array([a for a, _ in eq_pairs]), np.array([b for _, b in eq_pairs])
        DIV_eq = np.stack([pair_divergence(FutF[sq], ea, eb) for sq in seqs])
        with np.errstate(divide="ignore", invalid="ignore"):
            r_eq = np.where(rm > 0, DIV_eq.mean(1) / rm, np.nan)
        res["comparisons"]["truth_equivalent"] = {"mean": float(np.nanmean(r_eq[seq_testable])) if seq_testable.any() else float("nan"),
                                                  "n_pairs": len(eq_pairs), "n_classes": len(classes),
                                                  "per_sequence": {sq: float(v) for sq, v in zip(seqs, r_eq)}}
    res["numerical_floor"] = float(floor)
    res["testable"] = not reasons
    res["untestable_reason"] = "; ".join(reasons) or None
    res["sequences"] = seqs
    res["_units"] = {"dz": dz.tolist(), "ti": tix[ii].tolist(), "tj": tix[jj].tolist(), "traj_draw": traj_draw.tolist(),
                     "div": DIV.tolist()}
    return res


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
