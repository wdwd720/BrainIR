"""Cross-model and cross-system evaluation (PROTOCOL.md section 4 families F, G, I, J; section 8 statistics).

Paired comparisons use the per-unit values that `evaluate.eval_predictive` / `eval_intervention` return under "_units" (unit = test
trajectory, keyed by its dataset key), so two models are always compared on exactly the same held-out data.

    G  reproducibility          models of one method fitted with different seeds: canonical correlations and linear cross-prediction
                                R^2 of their latent states (alignment FITTED on public validation data, MEASURED on hidden test data),
                                agreement of their predicted readouts, k agreement
    I  cross-mechanism          shared-dynamics model vs independent models on the systems of one group: paired differences in A and
                                C, parameter counts, leave-one-implementation-out (encoder-only adaptation vs from scratch)
    J  cross-connectome         the same rule for full systems of different networks
    F  dimension                selected k, range, k / N_obs, the evaluator's k-sweep
"""

from __future__ import annotations

import numpy as np

from .api import StateModel
from .data import Trajectory
from .evaluate import EvalConfig, _nmse, encode_at, idx, strip_units  # noqa: F401


# ------------------------------------------------------------------------------------------------------------ statistics
def _boot_p(b: np.ndarray, point: float) -> float:
    """Two-sided bootstrap p-value of H0: effect = 0 (fraction of resamples on the other side of 0, doubled)."""
    b = np.asarray(b, float)
    if len(b) == 0 or not np.isfinite(point):
        return float("nan")
    frac = float(np.mean(b <= 0)) if point > 0 else float(np.mean(b >= 0))
    return float(min(1.0, 2 * frac))


def paired_diff(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean of (a - b) over the units both models were scored on (e.g. A NMSE per trajectory), bootstrap CI and p-value."""
    keys = sorted(set(units_a) & set(units_b))
    d = np.array([units_a[k] - units_b[k] for k in keys], float)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return {"diff": float("nan"), "ci95": [float("nan")] * 2, "n": 0, "p": float("nan")}
    rng = np.random.default_rng(seed)
    b = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    m = float(d.mean())
    return {"diff": m, "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))], "n": int(len(d)), "p": _boot_p(b, m)}


def paired_ratio_diff(units_a: dict, units_b: dict, n_boot: int = 2000, seed: int = 0) -> dict:
    """Effect-error ratio difference: sum num_a / sum den - sum num_b / sum den on common units (den = the true effect, identical
    for both models); units are (num, den, post_nmse) tuples as returned by eval_intervention."""
    keys = sorted(set(units_a) & set(units_b))
    if not keys:
        return {"diff": float("nan"), "ci95": [float("nan")] * 2, "n": 0, "p": float("nan")}
    na = np.array([units_a[k][0] for k in keys], float)
    nb = np.array([units_b[k][0] for k in keys], float)
    den = np.array([units_a[k][1] for k in keys], float)
    if den.sum() <= 0:
        return {"diff": float("nan"), "ci95": [float("nan")] * 2, "n": len(keys), "p": float("nan")}
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(n_boot):
        s = rng.integers(0, len(keys), len(keys))
        if den[s].sum() > 0:
            b.append((na[s].sum() - nb[s].sum()) / den[s].sum())
    m = float((na.sum() - nb.sum()) / den.sum())
    return {"diff": m, "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))], "n": len(keys), "p": _boot_p(np.array(b), m),
            "ratio_a": float(na.sum() / den.sum()), "ratio_b": float(nb.sum() / den.sum())}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values (NaNs are left out of the family and returned as NaN)."""
    items = sorted(((k, v) for k, v in pvals.items() if np.isfinite(v)), key=lambda kv: kv[1])
    m = len(items)
    out, running = {k: float("nan") for k in pvals}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


# ------------------------------------------------------------------------------------------------------------ latent samples
def latent_samples(model: StateModel, sid: str, trajs: list[Trajectory], times_s: tuple[float, ...] = (0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5),
                   ) -> tuple[np.ndarray, list[tuple[str, int]]]:
    """Encodings at fixed times of each trajectory: (n, k) and the (key, index) of every row."""
    Z, where = [], []
    for tr in trajs:
        for t in times_s:
            i = idx(t, tr.dt)
            if i < len(tr.t):
                Z.append(encode_at(model, sid, tr, i))
                where.append((tr.key, i))
    return (np.stack(Z) if Z else np.zeros((0, 0))), where


def _whiten(Z: np.ndarray, ridge: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    mu = Z.mean(0)
    C = np.cov((Z - mu).T) if Z.shape[1] > 1 else np.array([[np.var(Z[:, 0])]])
    C = np.atleast_2d(C) + ridge * (np.trace(np.atleast_2d(C)) / max(1, Z.shape[1]) + 1e-12) * np.eye(Z.shape[1])
    w, V = np.linalg.eigh(C)
    return mu, V @ np.diag(1.0 / np.sqrt(np.maximum(w, 1e-12))) @ V.T


def cca_fit_apply(Za_fit, Zb_fit, Za_eval, Zb_eval) -> list[float]:
    """Canonical correlations: directions fitted on (Za_fit, Zb_fit), correlations measured on (Za_eval, Zb_eval)."""
    ma, Wa = _whiten(Za_fit)
    mb, Wb = _whiten(Zb_fit)
    A, B = (Za_fit - ma) @ Wa, (Zb_fit - mb) @ Wb
    U, _, Vt = np.linalg.svd(A.T @ B / len(A), full_matrices=False)
    r = min(Za_fit.shape[1], Zb_fit.shape[1])
    ca = ((Za_eval - ma) @ Wa @ U)[:, :r]
    cb = ((Zb_eval - mb) @ Wb @ Vt.T)[:, :r]
    out = []
    for j in range(r):
        a, b = ca[:, j] - ca[:, j].mean(), cb[:, j] - cb[:, j].mean()
        den = np.sqrt((a @ a) * (b @ b))
        out.append(float(abs(a @ b) / den) if den > 0 else float("nan"))
    return out


def cross_r2(Z_from_fit, Z_to_fit, Z_from_eval, Z_to_eval, ridge: float = 1e-3) -> float:
    """R^2 (variance-weighted) of a ridge map Z_from -> Z_to fitted on the fit set, measured on the eval set."""
    mu, sd = Z_from_fit.mean(0), Z_from_fit.std(0) + 1e-9
    A = (Z_from_fit - mu) / sd
    ym = Z_to_fit.mean(0)
    W = np.linalg.solve(A.T @ A + ridge * len(A) * np.eye(A.shape[1]), A.T @ (Z_to_fit - ym))
    P = ((Z_from_eval - mu) / sd) @ W + ym
    sst = float(((Z_to_eval - Z_to_eval.mean(0)) ** 2).sum())
    return float(1 - ((P - Z_to_eval) ** 2).sum() / sst) if sst > 0 else float("nan")


# ------------------------------------------------------------------------------------------------------------ G
def eval_reproducibility(models: list[StateModel], sid: str, val: list[Trajectory], test: list[Trajectory], scale: np.ndarray,
                         cfg: EvalConfig = EvalConfig(), horizon_s: float | None = None) -> dict:
    """G: all pairs of models (same method, different seeds). Alignment (CCA directions, ridge maps) is fitted on PUBLIC validation
    trajectories and measured on the hidden test trajectories (goal4 sections 44, 65). Latent states are sampled every half
    start-time spacing from the first start time on."""
    horizon_s = cfg.primary_horizon_s if horizon_s is None else horizon_s
    step = (cfg.start_times_s[1] - cfg.start_times_s[0]) / 2 if len(cfg.start_times_s) > 1 else cfg.start_times_s[0]
    t_last = min(float(tr.t[-1]) for tr in list(val) + list(test))
    times = tuple(float(t) for t in np.arange(cfg.start_times_s[0], t_last - 1e-9, step))
    Zv = [latent_samples(m, sid, val, times)[0] for m in models]
    Zt = [latent_samples(m, sid, test, times)[0] for m in models]
    ks = [int(z.shape[1]) for z in Zv]
    preds = []
    for m in models:
        rows = []
        for tr in test:
            for t0 in cfg.start_times_s:
                i0, n = idx(t0, tr.dt), idx(horizon_s, tr.dt)
                if i0 + n < len(tr.t):
                    z0 = encode_at(m, sid, tr, i0)
                    rows.append(np.asarray(m.rollout(sid, z0, tr.u[i0: i0 + n + 1], [], tr.dt)["y"], float)[1:])
        preds.append(rows)
    pairs = []
    for a in range(len(models)):
        for b in range(a + 1, len(models)):
            cc = cca_fit_apply(Zv[a], Zv[b], Zt[a], Zt[b])
            agree = [_nmse(pa, pb, scale) for pa, pb in zip(preds[a], preds[b])]
            pairs.append({"a": a, "b": b, "cca_mean": float(np.nanmean(cc)), "cca": cc,
                          "r2_a_to_b": cross_r2(Zv[a], Zv[b], Zt[a], Zt[b]), "r2_b_to_a": cross_r2(Zv[b], Zv[a], Zt[b], Zt[a]),
                          "prediction_disagreement_nmse": float(np.mean(agree)) if agree else float("nan")})
    return {"k": ks, "k_agree": len(set(ks)) == 1, "pairs": pairs,
            "cca_mean": float(np.nanmean([p["cca_mean"] for p in pairs])) if pairs else float("nan"),
            "r2_min_mean": float(np.nanmean([min(p["r2_a_to_b"], p["r2_b_to_a"]) for p in pairs])) if pairs else float("nan"),
            "prediction_disagreement_nmse": float(np.nanmean([p["prediction_disagreement_nmse"] for p in pairs])) if pairs else float("nan")}


# ------------------------------------------------------------------------------------------------------------ I / J
def n_params(model: StateModel, sids: list[str]) -> dict:
    """Parameter counts from the model's self-report: encoder + readout of the given systems + the transition law."""
    npar = (model.info() or {}).get("n_params") or {}
    enc = sum(int((npar.get("encoder") or {}).get(s, 0)) for s in sids)
    ro = sum(int((npar.get("readout") or {}).get(s, 0)) for s in sids)
    tr = int(npar.get("transition", 0) or 0)
    return {"encoder": enc, "readout": ro, "transition": tr, "total": enc + ro + tr, "reported": bool(npar)}


def sharing_comparison(shared_res: dict[str, dict], indep_res: dict[str, dict], shared_params: dict, indep_params: dict,
                       tau_a: float, c_margin: float = 0.05, a_key: str = "A_nmse_h250ms", c_key: str = "C_w250ms",
                       n_boot: int = 2000, seed: int = 0) -> dict:
    """I / J (PROTOCOL.md section 7): per system, paired differences shared - independent in A (per trajectory) and C (effect error on
    held-out intervention pairs). Non-inferiority: A difference upper CI <= tau_a x independent A; C difference upper CI <= c_margin.
    shared_res / indep_res: {system_id: {"A": eval_predictive result, "C": eval_intervention result}} (with "_units")."""
    per = {}
    ok_all = True
    for sid in sorted(set(shared_res) & set(indep_res)):
        sa, ia = shared_res[sid].get("A") or {}, indep_res[sid].get("A") or {}
        da = paired_diff((sa.get("_units") or {}).get(a_key, {}), (ia.get("_units") or {}).get(a_key, {}), n_boot, seed)
        a_ind = (ia.get(a_key) or {}).get("mean", float("nan"))
        a_ok = bool(np.isfinite(da["ci95"][1]) and da["ci95"][1] <= tau_a * a_ind)
        sc, ic = shared_res[sid].get("C") or {}, indep_res[sid].get("C") or {}
        dc = paired_ratio_diff((sc.get("_units") or {}).get(c_key, {}), (ic.get("_units") or {}).get(c_key, {}), n_boot, seed)
        c_ok = bool(dc["n"] == 0 or (np.isfinite(dc["ci95"][1]) and dc["ci95"][1] <= c_margin))
        per[sid] = {"A_diff": da, "A_independent": a_ind, "A_noninferior": a_ok, "C_diff": dc, "C_noninferior": c_ok}
        ok_all = ok_all and a_ok and c_ok
    fewer = shared_params["total"] < indep_params["total"] if shared_params["reported"] and indep_params["reported"] else None
    return {"per_system": per, "noninferior_all": ok_all, "shared_params": shared_params, "independent_params": indep_params,
            "fewer_parameters": fewer}


def loio_comparison(adapted_res: dict, scratch_res: dict, a_key: str = "A_nmse_h250ms", c_key: str = "C_w250ms",
                    n_boot: int = 2000, seed: int = 0) -> dict:
    """Leave-one-implementation-out (goal4 section 19): encoder-only adaptation to a held-out implementation (f frozen, fitted on the
    other implementations) vs a from-scratch model on the SAME limited data of the held-out implementation. Negative differences
    favour the adapted model."""
    da = paired_diff((adapted_res.get("A") or {}).get("_units", {}).get(a_key, {}), (scratch_res.get("A") or {}).get("_units", {}).get(a_key, {}),
                     n_boot, seed)
    dc = paired_ratio_diff((adapted_res.get("C") or {}).get("_units", {}).get(c_key, {}), (scratch_res.get("C") or {}).get("_units", {}).get(c_key, {}),
                           n_boot, seed)
    beats = bool(np.isfinite(da["ci95"][1]) and da["ci95"][1] < 0) or bool(dc["n"] and np.isfinite(dc["ci95"][1]) and dc["ci95"][1] < 0)
    worse = bool(np.isfinite(da["ci95"][0]) and da["ci95"][0] > 0) or bool(dc["n"] and np.isfinite(dc["ci95"][0]) and dc["ci95"][0] > 0)
    return {"A_diff": da, "C_diff": dc, "adapted_beats_scratch": beats and not worse, "adapted_worse": worse}


def sharing_verdict(comparison: dict, loio: list[dict] | None) -> str:
    """'supported' when the shared model is non-inferior on A and C with fewer parameters AND encoder-only adaptation beats a
    from-scratch model for at least half of the held-out implementations (and is worse for none); 'rejected' otherwise;
    'untestable' when the method cannot fit shared dynamics or parameter counts are missing."""
    if comparison is None or comparison.get("fewer_parameters") is None:
        return "untestable"
    if loio is not None and len(loio) == 0:
        return "untestable"          # no leave-one-implementation-out result (e.g. the method cannot adapt an encoder)
    loio_ok = bool(loio) and sum(r["adapted_beats_scratch"] for r in loio) * 2 >= len(loio) and not any(r["adapted_worse"] for r in loio)
    return "supported" if (comparison["noninferior_all"] and comparison["fewer_parameters"] and loio_ok) else "rejected"


# ------------------------------------------------------------------------------------------------------------ F
def dimension_summary(model: StateModel, sid: str, n_observed: int) -> dict:
    info = model.info() or {}
    k = (info.get("k") or {}).get(sid)
    rng = (info.get("k_range") or {}).get(sid)
    ab = (info.get("abstain") or {}).get(sid) or {}
    return {"k": k, "k_range": rng, "n_observed": int(n_observed), "compression": (float(k) / n_observed if k and n_observed else None),
            "abstain": ab, "lipschitz_bound": info.get("lipschitz_bound")}
