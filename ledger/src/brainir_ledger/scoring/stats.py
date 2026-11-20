"""Statistics of the pre-registered analysis (PREREG.md sections 7-8). Pure functions of arrays; no file access.

Conventions: ``scores`` are real numbers (higher = predicted more likely rhythmic); ``labels`` are 0/1 (1 = activation
evokes rhythmic front-leg movement). AUROC uses average ranks for ties (Mann-Whitney U / (n_pos n_neg)).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata, spearmanr


def _check(scores, labels) -> tuple[np.ndarray, np.ndarray]:
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels).astype(int)
    if s.shape != y.shape or s.ndim != 1:
        raise ValueError("scores and labels must be 1-D arrays of the same length")
    if not np.isin(y, (0, 1)).all():
        raise ValueError("labels must be 0/1")
    if not np.all(np.isfinite(s)):
        raise ValueError("scores must be finite")
    return s, y


def auroc(scores, labels) -> float:
    """Area under the ROC curve with average ranks for ties; NaN if a class is empty."""
    s, y = _check(scores, labels)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s, method="average")
    u = r[y == 1].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def _auroc_rows(S: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """AUROC for each row of S (scores) with labels Y (same shape), average ranks."""
    R = rankdata(S, method="average", axis=1)
    n1 = Y.sum(axis=1)
    n0 = Y.shape[1] - n1
    u = (R * Y).sum(axis=1) - n1 * (n1 + 1) / 2.0
    with np.errstate(invalid="ignore", divide="ignore"):
        return u / (n1 * n0)


def bootstrap_auroc(scores, labels, *, n_boot: int = 10_000, seed: int = 20261120, alpha: float = 0.05,
                    chunk: int = 2_000) -> dict:
    """Stratified percentile bootstrap (positives and negatives resampled separately)."""
    s, y = _check(scores, labels)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return {"auroc": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_boot": 0}
    rng = np.random.default_rng(seed)
    vals = []
    for start in range(0, n_boot, chunk):
        k = min(chunk, n_boot - start)
        bp = pos[rng.integers(0, len(pos), size=(k, len(pos)))]
        bn = neg[rng.integers(0, len(neg), size=(k, len(neg)))]
        S = np.concatenate([bp, bn], axis=1)
        Y = np.concatenate([np.ones((k, len(pos))), np.zeros((k, len(neg)))], axis=1)
        vals.append(_auroc_rows(S, Y))
    v = np.concatenate(vals)
    return {"auroc": auroc(s, y), "lo": float(np.quantile(v, alpha / 2)), "hi": float(np.quantile(v, 1 - alpha / 2)),
            "n_boot": int(n_boot), "seed": int(seed)}


def permutation_p(scores, labels, *, n_perm: int = 10_000, seed: int = 20261121, chunk: int = 2_000) -> dict:
    """One-sided permutation p-value for AUROC > 0.5: p = (1 + #{AUROC_perm >= AUROC_obs}) / (1 + n_perm)."""
    s, y = _check(scores, labels)
    obs = auroc(s, y)
    if not np.isfinite(obs):
        return {"auroc": obs, "p": float("nan"), "n_perm": 0}
    rng = np.random.default_rng(seed)
    ge = 0
    for start in range(0, n_perm, chunk):
        k = min(chunk, n_perm - start)
        Y = np.array([rng.permutation(y) for _ in range(k)])
        S = np.broadcast_to(s, Y.shape)
        ge += int((_auroc_rows(S, Y) >= obs - 1e-12).sum())
    return {"auroc": obs, "p": (1 + ge) / (1 + n_perm), "n_perm": int(n_perm), "seed": int(seed)}


def paired_bootstrap_diff(scores_a, scores_b, labels, *, n_boot: int = 10_000, seed: int = 20261122, alpha: float = 0.05,
                          chunk: int = 2_000) -> dict:
    """Paired stratified bootstrap of AUROC(a) - AUROC(b) on the same types."""
    a, y = _check(scores_a, labels)
    b, _ = _check(scores_b, labels)
    ip, ineg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    if len(ip) == 0 or len(ineg) == 0:
        return {"diff": float("nan"), "lo": float("nan"), "hi": float("nan")}
    rng = np.random.default_rng(seed)
    vals = []
    for start in range(0, n_boot, chunk):
        k = min(chunk, n_boot - start)
        idx = np.concatenate([ip[rng.integers(0, len(ip), size=(k, len(ip)))], ineg[rng.integers(0, len(ineg), size=(k, len(ineg)))]], axis=1)
        Y = y[idx]
        vals.append(_auroc_rows(a[idx], Y) - _auroc_rows(b[idx], Y))
    v = np.concatenate(vals)
    return {"auroc_a": auroc(a, y), "auroc_b": auroc(b, y), "diff": auroc(a, y) - auroc(b, y), "lo": float(np.quantile(v, alpha / 2)),
            "hi": float(np.quantile(v, 1 - alpha / 2)), "n_boot": int(n_boot), "seed": int(seed)}


def band_of(score: float, *, driver: float = 0.5, non_driver: float = 0.05) -> str:
    if score >= driver:
        return "driver"
    if score < non_driver:
        return "non_driver"
    return "indeterminate"


def precision_npv(scores, labels, *, driver: float = 0.5, non_driver: float = 0.05) -> dict:
    s, y = _check(scores, labels)
    d = s >= driver
    nd = s < non_driver
    return {"n_driver": int(d.sum()), "n_driver_yes": int((d & (y == 1)).sum()),
            "precision_driver": float((y[d] == 1).mean()) if d.any() else float("nan"),
            "n_non_driver": int(nd.sum()), "n_non_driver_no": int((nd & (y == 0)).sum()),
            "npv_non_driver": float((y[nd] == 0).mean()) if nd.any() else float("nan"),
            "n_indeterminate": int((~d & ~nd).sum())}


CALIBRATION_BINS = (0.0, 0.05, 0.25, 0.5, 0.75, 1.0000001)


def calibration(scores, labels, bins=CALIBRATION_BINS) -> dict:
    s, y = _check(scores, labels)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (s >= lo) & (s < hi)
        rows.append({"bin": [lo, min(hi, 1.0)], "n": int(m.sum()), "frac_yes": float(y[m].mean()) if m.any() else None,
                     "mean_score": float(s[m].mean()) if m.any() else None})
    p = np.clip(s, 0.0, 1.0)
    return {"bins": rows, "brier": float(np.mean((p - y) ** 2)) if len(y) else float("nan")}


def cohen_kappa(a, b) -> float:
    """Cohen's kappa for two equal-length sequences of categorical labels."""
    a = np.asarray(a, dtype=object)
    b = np.asarray(b, dtype=object)
    if len(a) != len(b) or len(a) == 0:
        return float("nan")
    cats = sorted(set(a.tolist()) | set(b.tolist()), key=str)
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return float("nan") if pe >= 1 else (po - pe) / (1 - pe)


def spearman(x, y) -> float:
    r = spearmanr(np.asarray(x, float), np.asarray(y, float))
    return float(r.statistic if hasattr(r, "statistic") else r[0])


def primary_decision(n_types: int, n_pos: int, n_neg: int, ci_lo: float, diff_lo: float | None) -> dict:
    """PREREG section 7 decision rules, tested in a fixed order: underpowered -> nothing is claimed; "adds value beyond
    wiring" can only be claimed when "the model predicts" holds. The permutation p-value is descriptive."""
    under = n_types < 20 or n_pos < 5 or n_neg < 5
    predicts = (not under) and bool(ci_lo is not None and np.isfinite(ci_lo) and ci_lo > 0.5)
    adds = predicts and diff_lo is not None and bool(np.isfinite(diff_lo) and diff_lo > 0.0)
    return {"underpowered": bool(under), "model_predicts": predicts, "adds_value_beyond_wiring": adds}
