"""Synthetic ground-truth recovery (K) and failure / abstention quality (L) (PROTOCOL.md section 4; goal4 sections 21, 79).

ORCHESTRATOR SIDE: these functions read synthetic TRUTH (latent trajectories, true dimension, implementation groups) and are run only
on the held-out and final suites (Level B) and for the pre-registered calibration on the dev suite.

    K  latent recovery      cross-fitted R^2 of the TRUE latent from the model's latent (linear and random-feature regressors), and of
                            the model's latent from the true latent (does z carry anything else?), at sampled times of test trajectories;
                            linear CCA between them
       dimension recovery   the selected k equals the true k; the true k lies in the reported range
    L  abstention           per system: expected = non-compressible control ("none"); flagged = the model's own abstention flags;
                            confident-wrong = a compact claim that fails the protocol's interventional or closure criterion
"""

from __future__ import annotations

import numpy as np

from .api import StateModel
from .data import Trajectory
from .evaluate import EvalConfig, _rff, _ridge_cv_fit_predict, encode_at, idx
from .evaluate_cross import cca_fit_apply


def _cross_r2(X: np.ndarray, Y: np.ndarray, groups: np.ndarray, kind: str, seed: int) -> float:
    """Two-fold (by trajectory) cross-fitted R^2 of Y from X (variance-weighted over Y's columns). 'rff' = the linear features plus
    min(256, max(16, n / 8)) random Fourier features (nests the linear map); ridge penalties chosen by an inner split by trajectory."""
    rng = np.random.default_rng(seed)
    u = np.unique(groups)
    fold = np.isin(groups, u[rng.permutation(len(u))[: len(u) // 2]])
    if fold.sum() < 5 or (~fold).sum() < 5:
        return float("nan")
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    if kind == "rff":
        F = np.hstack([Xs, _rff(X, int(min(256, max(16, len(X) // 8))), np.random.default_rng(seed + 1))])
    else:
        F = Xs
    pred = np.zeros_like(Y, dtype=np.float64)
    for tr in (fold, ~fold):
        pred[~tr] = _ridge_cv_fit_predict(F[tr], Y[tr], F[~tr], groups[tr], seed=seed)
    sst = float(((Y - Y.mean(0)) ** 2).sum())
    return float(1 - ((pred - Y) ** 2).sum() / sst) if sst > 0 else float("nan")


def eval_latent_recovery(model: StateModel, sid: str, trajs: list[Trajectory], z_true: dict[str, np.ndarray], cfg: EvalConfig = EvalConfig(),
                         n_times: int = 12) -> dict:
    """K: z_model vs z_true at n_times evenly spaced samples (after the first start time) of each test trajectory."""
    Zm, Zt, g = [], [], []
    for ti, tr in enumerate(trajs):
        if tr.key not in z_true:
            continue
        i0 = idx(cfg.start_times_s[0], tr.dt)
        for i in np.linspace(i0, len(tr.t) - 1, n_times).astype(int):
            Zm.append(encode_at(model, sid, tr, int(i)))
            Zt.append(np.asarray(z_true[tr.key][int(i)], float))
            g.append(ti)
    if len(Zm) < 20:
        return {"note": "too few samples"}
    Zm, Zt, g = np.stack(Zm), np.stack(Zt), np.array(g)
    half = np.isin(g, np.unique(g)[::2])
    cc = cca_fit_apply(Zm[half], Zt[half], Zm[~half], Zt[~half]) if (half.sum() > 10 and (~half).sum() > 10) else []
    return {"n_samples": int(len(Zm)), "k_model": int(Zm.shape[1]), "k_true": int(Zt.shape[1]),
            "r2_true_from_model_linear": _cross_r2(Zm, Zt, g, "linear", cfg.seed),
            "r2_true_from_model_rff": _cross_r2(Zm, Zt, g, "rff", cfg.seed),
            "r2_model_from_true_linear": _cross_r2(Zt, Zm, g, "linear", cfg.seed),
            "r2_model_from_true_rff": _cross_r2(Zt, Zm, g, "rff", cfg.seed),
            "cca": cc, "cca_mean": float(np.mean(cc)) if cc else float("nan")}


def dimension_recovery(k_selected, k_range, k_true) -> dict:
    """K: dimension recovery against the truth ("none" for non-compressible controls)."""
    if k_true == "none" or k_true is None:
        return {"k_true": "none", "k_selected": k_selected, "applicable": False}
    exact = k_selected is not None and int(k_selected) == int(k_true)
    in_range = bool(k_range) and int(k_range[0]) <= int(k_true) <= int(k_range[1])
    return {"k_true": int(k_true), "k_selected": k_selected, "k_range": k_range, "exact": bool(exact), "in_range": bool(in_range or exact),
            "error": (int(k_selected) - int(k_true)) if k_selected is not None else None}


def abstained(ab: dict | None) -> bool:
    ab = ab or {}
    return bool(ab.get("no_compact_state") or ab.get("causal_equivalence_failed"))


def abstention_row(system_truth: dict, ab: dict | None, verdict: dict | None) -> dict:
    """L for one system. system_truth: {'k': int | 'none', 'trap': str | None, 'closed_dynamics': bool}; ab: the model's abstention
    flags for this system; verdict: {'interventional': bool, 'closed': bool, ...} from the protocol's criteria (or None)."""
    noncompressible = system_truth.get("k") == "none"
    flag = abstained(ab)
    unresolved = bool((ab or {}).get("dimension_unresolved"))
    passes = None if verdict is None else bool(verdict.get("interventional") and verdict.get("closed"))
    return {"noncompressible": noncompressible, "trap": system_truth.get("trap"), "closed_dynamics": system_truth.get("closed_dynamics"),
            "abstained": flag, "dimension_unresolved": unresolved,
            "correct_abstention": noncompressible and flag, "missed_abstention": noncompressible and not flag,
            "false_alarm": (not noncompressible) and flag,
            "confident_wrong": (not flag) and (passes is False)}


def abstention_summary(rows: list[dict]) -> dict:
    nc = [r for r in rows if r["noncompressible"]]
    co = [r for r in rows if not r["noncompressible"]]
    return {"n_noncompressible": len(nc), "n_compressible": len(co),
            "abstention_recall": (sum(r["correct_abstention"] for r in nc) / len(nc)) if nc else float("nan"),
            "false_alarm_rate": (sum(r["false_alarm"] for r in co) / len(co)) if co else float("nan"),
            "confident_wrong_rate": (sum(r["confident_wrong"] for r in rows) / len(rows)) if rows else float("nan")}
