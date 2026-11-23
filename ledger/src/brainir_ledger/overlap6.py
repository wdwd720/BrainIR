"""PREREG v6 G2-G3: hit-list overlap at a cut and the graded (AUROC) version, with their within-animal references and type-resample
intervals. Inputs are per-type score vectors aligned on one type list: full-seed scores and the two seed halves of each screen.

- G2 (rulebook v5 R2.2 at cut z): n_X, n_Y, k, the replication rates, the chance expectation n_X n_Y / N, the hypergeometric
  p = P(K >= k), OC = k / min(n_X, n_Y), cross-half OC = mean(OC(X1, Y2), OC(X2, Y1)), ceiling = mean(OC(X1, X2), OC(Y1, Y2)), OC ratio;
  Clopper-Pearson for k / n_X; 10,000 type resamples (`default_rng(seed)`), undefined resamples dropped and counted.
- G3: AUROC of Y's score for X's drivers (ties one half), both directions, and each animal's within-animal reference
  mean(AUROC(X2; X1 drivers), AUROC(X1; X2 drivers)).
"""

from __future__ import annotations

import numpy as np
from scipy import stats

N_BOOT = 10_000
SEED = 20261601


def clopper_pearson(k: int, n: int, a: float = 0.05) -> list[float | None]:
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


def _oc(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise overlap coefficient of boolean matrices (NaN when a list is empty)."""
    k = (a & b).sum(-1).astype(float)
    m = np.minimum(a.sum(-1), b.sum(-1)).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(m > 0, k / np.where(m > 0, m, 1), np.nan)


def auroc(score: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """Row-wise AUROC of `score` for the boolean labels `pos` (average ranks: ties count one half); NaN if a class is empty."""
    score, pos = np.atleast_2d(score), np.atleast_2d(pos)
    r = stats.rankdata(score, axis=-1)
    npos = pos.sum(-1).astype(float)
    nneg = pos.shape[-1] - npos
    u = (r * pos).sum(-1) - npos * (npos + 1) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where((npos > 0) & (nneg > 0), u / np.where((npos > 0) & (nneg > 0), npos * nneg, 1), np.nan)
    return out


def _ci(v: np.ndarray) -> dict:
    ok = v[np.isfinite(v)]
    return {"lo": float(np.percentile(ok, 2.5)) if ok.size else None, "hi": float(np.percentile(ok, 97.5)) if ok.size else None,
            "n_dropped": int(v.size - ok.size)}


def _f(x) -> float | None:
    x = float(x)
    return x if np.isfinite(x) else None


def overlap(sx, sy, sx1, sx2, sy1, sy2, cut: float, *, seed: int = SEED, n_boot: int = N_BOOT, names=None) -> dict:
    """G2 at one cut (all vectors aligned on one type list)."""
    sx, sy, sx1, sx2, sy1, sy2 = (np.asarray(v, float) for v in (sx, sy, sx1, sx2, sy1, sy2))
    X, Y = sx >= cut, sy >= cut
    X1, X2, Y1, Y2 = sx1 >= cut, sx2 >= cut, sy1 >= cut, sy2 >= cut
    N, nx, ny, k = len(sx), int(X.sum()), int(Y.sum()), int((X & Y).sum())
    cross = np.nanmean([_oc(X1, Y2), _oc(X2, Y1)]) if np.isfinite([_oc(X1, Y2), _oc(X2, Y1)]).all() else np.nan
    ceil = np.nanmean([_oc(X1, X2), _oc(Y1, Y2)]) if np.isfinite([_oc(X1, X2), _oc(Y1, Y2)]).all() else np.nan
    point = {"N": N, "n_x": nx, "n_y": ny, "k": k, "rate_x_in_y": _f(k / nx) if nx else None, "rate_y_in_x": _f(k / ny) if ny else None,
             "chance_expectation": nx * ny / N if N else None,
             "hypergeom_p": float(stats.hypergeom.sf(k - 1, N, ny, nx)) if N else None,
             "rate_x_in_y_clopper_pearson": clopper_pearson(k, nx), "OC": _f(_oc(X, Y)), "OC_cross_half": _f(cross),
             "OC_within_animal": _f(ceil), "OC_ratio": _f(cross / ceil) if np.isfinite(cross) and np.isfinite(ceil) and ceil > 0 else None}
    if names is not None:
        point["types_in_both"] = sorted(str(names[i]) for i in np.flatnonzero(X & Y))
    idx = np.random.default_rng(seed).integers(0, N, size=(n_boot, N))
    bX1, bX2, bY1, bY2, bX, bY = X1[idx], X2[idx], Y1[idx], Y2[idx], X[idx], Y[idx]
    c = (_oc(bX1, bY2) + _oc(bX2, bY1)) / 2
    w = (_oc(bX1, bX2) + _oc(bY1, bY2)) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(w > 0, c / np.where(w > 0, w, 1), np.nan)
        rx = np.where(bX.sum(1) > 0, (bX & bY).sum(1) / np.maximum(bX.sum(1), 1), np.nan)
    boot = {"n_boot": n_boot, "seed": seed, "OC_cross_half": _ci(c), "OC_within_animal": _ci(w), "OC_ratio": _ci(ratio),
            "rate_x_in_y": _ci(rx)}
    return {"cut": cut, "point": point, "bootstrap_95": boot}


def graded(sx, sy, sx1, sx2, sy1, sy2, cut: float, *, seed: int = SEED, n_boot: int = N_BOOT) -> dict:
    """G3 at one cut: AUROC of Y's score for X's drivers and of X's score for Y's drivers, with within-animal references."""
    sx, sy, sx1, sx2, sy1, sy2 = (np.asarray(v, float) for v in (sx, sy, sx1, sx2, sy1, sy2))
    N = len(sx)

    def within(a1, a2, idx=None):
        if idx is None:
            return (auroc(a2, a1 >= cut) + auroc(a1, a2 >= cut)) / 2
        return (auroc(a2[idx], a1[idx] >= cut) + auroc(a1[idx], a2[idx] >= cut)) / 2

    point = {"auroc_y_for_x_drivers": _f(auroc(sy, sx >= cut)[0]), "auroc_x_for_y_drivers": _f(auroc(sx, sy >= cut)[0]),
             "within_x": _f(within(sx1, sx2)[0]), "within_y": _f(within(sy1, sy2)[0])}
    idx = np.random.default_rng(seed).integers(0, N, size=(n_boot, N))
    boot = {"n_boot": n_boot, "seed": seed, "auroc_y_for_x_drivers": _ci(auroc(sy[idx], sx[idx] >= cut)),
            "auroc_x_for_y_drivers": _ci(auroc(sx[idx], sy[idx] >= cut)), "within_x": _ci(within(sx1, sx2, idx)),
            "within_y": _ci(within(sy1, sy2, idx))}
    return {"cut": cut, "point": point, "bootstrap_95": boot}
