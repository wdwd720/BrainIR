"""Resampling statistics for the Phase 4 evaluator (benchmarks/causal_state_v1/PROTOCOL.md section 11).

Conventions (fixed by the protocol):
- percentile bootstrap with B = 2,000 resamples by default;
- the resampling unit is a CLUSTER (a test item with its twin; items that share a start state or a source trajectory share a group id;
  a system instance across systems), never a time step. Every function takes an optional `groups` array: rows with the same group
  are resampled together; without it every row is its own cluster;
- ratios are ratios of SUMS over the resampled clusters (never means of per-item ratios);
- paired comparisons resample the SAME clusters for both arms;
- bootstrap p-values are (1 + count) / (1 + B), where count is the number of replicates on the null side;
- Holm's step-down procedure controls the family-wise error of the primary family.

Implementation: per-cluster sums are precomputed once, and each replicate is a vector of cluster multiplicities (multinomial counts),
so a replicate costs one weighted sum. All functions are deterministic given `seed`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

N_BOOT = 2000
ALPHA = 0.05


# ------------------------------------------------------------------------------------------------------------ cluster helpers
def cluster_index(groups: Sequence | np.ndarray | None, n: int) -> tuple[np.ndarray, int]:
    """(inverse index of each row into its cluster, number of clusters). Without groups every row is its own cluster."""
    if groups is None:
        return np.arange(n), n
    g = np.asarray(groups)
    if len(g) != n:
        raise ValueError(f"groups has {len(g)} entries for {n} rows")
    _, inv = np.unique(g.astype(str), return_inverse=True)
    return inv, int(inv.max()) + 1 if n else 0


def cluster_sums(values: np.ndarray, inv: np.ndarray, n_clusters: int) -> np.ndarray:
    """Per-cluster sums of a 1-D (rows) or 2-D (rows x columns) array."""
    v = np.asarray(values, dtype=np.float64)
    if v.ndim == 1:
        return np.bincount(inv, weights=v, minlength=n_clusters)
    out = np.zeros((n_clusters, v.shape[1]))
    np.add.at(out, inv, v)
    return out


def multiplicities(n_clusters: int, n_boot: int, seed: int) -> np.ndarray:
    """(n_boot, n_clusters) resampling counts: each row is one bootstrap resample of the clusters with replacement."""
    rng = np.random.default_rng(seed)
    if n_clusters == 0:
        return np.zeros((n_boot, 0))
    return rng.multinomial(n_clusters, np.full(n_clusters, 1.0 / n_clusters), size=n_boot).astype(np.float64)


def percentile_ci(reps: np.ndarray, level: float = 0.95) -> list[float]:
    r = np.asarray(reps, dtype=np.float64)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return [float("nan"), float("nan")]
    a = (1.0 - level) / 2.0 * 100.0
    return [float(np.percentile(r, a)), float(np.percentile(r, 100.0 - a))]


@dataclass
class Estimate:
    """A point estimate with its percentile CI and the bootstrap replicates (kept for paired tests; strip before reporting)."""
    point: float
    ci95: list[float]
    n_units: int
    reps: np.ndarray | None = None

    def as_dict(self, keep_reps: bool = False) -> dict:
        d = {"point": self.point, "ci95": self.ci95, "n_units": self.n_units}
        if keep_reps and self.reps is not None:
            d["reps"] = self.reps.tolist()
        return d


def _nan_estimate(n: int = 0) -> Estimate:
    return Estimate(float("nan"), [float("nan"), float("nan")], n, None)


# ------------------------------------------------------------------------------------------------------------ estimators
def boot_mean(values, groups=None, n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """Mean over rows with a cluster bootstrap CI (a cluster's rows are resampled together; the mean is over the resampled ROWS).
    Non-finite values are an error here: callers cap them first (the protocol never drops a failed prediction)."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) == 0:
        return _nan_estimate(0)
    if not np.isfinite(v).all():
        raise ValueError("boot_mean got non-finite values; cap them before resampling")
    inv, g = cluster_index(groups, len(v))
    s, c = cluster_sums(v, inv, g), np.bincount(inv, minlength=g).astype(np.float64)
    W = multiplicities(g, n_boot, seed)
    den = W @ c
    reps = np.where(den > 0, (W @ s) / np.where(den > 0, den, 1.0), np.nan)
    return Estimate(float(v.mean()), percentile_ci(reps), g, reps)


def boot_ratio(num, den, groups=None, n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """sum(num) / sum(den) with a cluster bootstrap CI (ratio of resampled sums)."""
    num, den = np.asarray(num, np.float64), np.asarray(den, np.float64)
    if len(num) == 0 or not np.isfinite(den).all() or den.sum() <= 0:
        return _nan_estimate(len(num))
    inv, g = cluster_index(groups, len(num))
    sn, sd = cluster_sums(num, inv, g), cluster_sums(den, inv, g)
    W = multiplicities(g, n_boot, seed)
    d = W @ sd
    reps = np.where(d > 0, (W @ sn) / np.where(d > 0, d, 1.0), np.nan)
    return Estimate(float(num.sum() / den.sum()), percentile_ci(reps), g, reps)


def boot_ratio_diff(num_a, den_a, num_b, den_b, groups=None, n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """PAIRED difference sum(num_a)/sum(den_a) - sum(num_b)/sum(den_b) on the same rows (clusters resampled together for both)."""
    arrs = [np.asarray(v, np.float64) for v in (num_a, den_a, num_b, den_b)]
    n = len(arrs[0])
    if n == 0 or any(len(a) != n for a in arrs) or arrs[1].sum() <= 0 or arrs[3].sum() <= 0:
        return _nan_estimate(n)
    inv, g = cluster_index(groups, n)
    sums = [cluster_sums(a, inv, g) for a in arrs]
    W = multiplicities(g, n_boot, seed)
    na, da, nb, db = (W @ s for s in sums)
    ok = (da > 0) & (db > 0)
    reps = np.where(ok, na / np.where(da > 0, da, 1.0) - nb / np.where(db > 0, db, 1.0), np.nan)
    point = float(arrs[0].sum() / arrs[1].sum() - arrs[2].sum() / arrs[3].sum())
    return Estimate(point, percentile_ci(reps), g, reps)


def boot_mean_diff(a, b, groups=None, n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """PAIRED difference of means mean(a) - mean(b) over the same rows."""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    if len(a) != len(b):
        raise ValueError("paired arrays differ in length")
    return boot_mean(a - b, groups, n_boot, seed)


def gain(e1: float, e2: float, floor: float = 0.01) -> float:
    """Fractional error reduction (e1 - e2) / max(e1, floor), clipped at -1 (the state-mediation / closure gains of PROTOCOL 5.3-5.4:
    a near-perfect base prediction cannot turn noise into a huge ratio)."""
    if not (np.isfinite(e1) and np.isfinite(e2)):
        return float("nan")
    return float(max(-1.0, (e1 - e2) / max(e1, floor)))


def boot_gain(e1_rows, e2_rows, groups=None, n_boot: int = N_BOOT, seed: int = 0, floor: float = 0.01) -> Estimate:
    """gain(mean e1, mean e2) of per-row errors with a cluster bootstrap CI (the unit is the cluster of rows)."""
    e1, e2 = np.asarray(e1_rows, np.float64), np.asarray(e2_rows, np.float64)
    if len(e1) == 0:
        return _nan_estimate(0)
    inv, g = cluster_index(groups, len(e1))
    s1, s2 = cluster_sums(e1, inv, g), cluster_sums(e2, inv, g)
    c = np.bincount(inv, minlength=g).astype(np.float64)
    W = multiplicities(g, n_boot, seed)
    n = W @ c
    m1 = np.where(n > 0, (W @ s1) / np.where(n > 0, n, 1.0), np.nan)
    m2 = np.where(n > 0, (W @ s2) / np.where(n > 0, n, 1.0), np.nan)
    reps = np.array([gain(a, b, floor) for a, b in zip(m1, m2)])
    return Estimate(gain(float(e1.mean()), float(e2.mean()), floor), percentile_ci(reps), g, reps)


def boot_stat(rows: np.ndarray, stat: Callable[[np.ndarray, np.ndarray], float], groups=None, n_boot: int = N_BOOT,
              seed: int = 0) -> Estimate:
    """General cluster bootstrap: stat(rows, weights) -> float, where weights are the resampling multiplicities of the ROWS (a
    cluster's multiplicity copied to each of its rows). Use for statistics that are not sums (e.g. a matched-pair ratio)."""
    rows = np.asarray(rows)
    n = len(rows)
    if n == 0:
        return _nan_estimate(0)
    inv, g = cluster_index(groups, n)
    W = multiplicities(g, n_boot, seed)
    reps = np.array([stat(rows, w[inv]) for w in W])
    return Estimate(float(stat(rows, np.ones(n))), percentile_ci(reps), g, reps)


# ------------------------------------------------------------------------------------------------------------ systems
def stratified_system_boot(values_by_system: dict[str, float], strata: dict[str, str] | None = None,
                           stat: Callable[[np.ndarray], float] = np.mean, n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """Statistic over SYSTEMS with a bootstrap that resamples systems within their stratum (the synthetic type), so every type keeps
    its share (PROTOCOL section 11: synthetic unit = system instance, CIs by resampling systems stratified by type)."""
    sids = sorted(values_by_system)
    v = np.array([values_by_system[s] for s in sids], dtype=np.float64)
    if len(v) == 0:
        return _nan_estimate(0)
    st = np.array([(strata or {}).get(s, "all") for s in sids])
    rng = np.random.default_rng(seed)
    groups = {k: np.flatnonzero(st == k) for k in np.unique(st)}
    reps = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.concatenate([m[rng.integers(0, len(m), len(m))] for m in groups.values()])
        reps[b] = stat(v[idx])
    return Estimate(float(stat(v)), percentile_ci(reps), len(v), reps)


def paired_system_boot(a_by_system: dict[str, float], b_by_system: dict[str, float], strata: dict[str, str] | None = None,
                       n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """Mean paired difference a - b over the systems present in both (stratified system bootstrap)."""
    common = sorted(set(a_by_system) & set(b_by_system))
    d = {s: float(a_by_system[s]) - float(b_by_system[s]) for s in common
         if np.isfinite(a_by_system[s]) and np.isfinite(b_by_system[s])}
    return stratified_system_boot(d, strata, np.mean, n_boot, seed)


# ------------------------------------------------------------------------------------------------------------ tests
def boot_pvalue(reps: np.ndarray | None, threshold: float, alternative: str = "less") -> float:
    """One-sided bootstrap p-value (1 + count) / (1 + B) for H1: statistic < threshold ("less") or > threshold ("greater"); count =
    replicates on the null side (>= threshold for "less"). Non-finite replicates count on the null side (a failure never helps)."""
    if reps is None or len(reps) == 0:
        return 1.0
    r = np.asarray(reps, np.float64)
    if alternative == "less":
        cnt = int(np.sum(~(r < threshold)))
    elif alternative == "greater":
        cnt = int(np.sum(~(r > threshold)))
    else:
        raise ValueError(alternative)
    return float((1 + cnt) / (1 + len(r)))


def noninferiority(diff: Estimate, margin: float) -> dict:
    """Lower-is-better scale, diff = method - baseline. H0: diff >= margin; H1: diff < margin. Passes when the upper CI < margin."""
    if not np.isfinite(diff.point):
        return {"p": 1.0, "pass": False, "margin": margin, "diff": diff.point, "ci95": diff.ci95, "note": "not computable"}
    p = boot_pvalue(diff.reps, margin, "less")
    return {"p": p, "pass": bool(np.isfinite(diff.ci95[1]) and diff.ci95[1] < margin), "margin": float(margin), "diff": diff.point,
            "ci95": diff.ci95}


def superiority(diff: Estimate) -> dict:
    """Lower-is-better scale, diff = method - baseline. H1: diff < 0 (one-sided)."""
    return noninferiority(diff, 0.0)


def holm(pvalues: dict[str, float] | Sequence[float], alpha: float = ALPHA) -> dict:
    """Holm's step-down procedure. Returns {"adjusted": {...}, "reject": {...}} keyed like the input (list input -> integer keys).
    Missing / non-finite p-values count as 1 (a test that cannot be computed stays in the family and is never rejected)."""
    items = list(pvalues.items()) if isinstance(pvalues, dict) else list(enumerate(pvalues))
    keys = [k for k, _ in items]
    p = np.array([float(v) if v is not None and np.isfinite(v) else 1.0 for _, v in items], dtype=np.float64)
    m = len(p)
    order = np.argsort(p, kind="stable")
    adj = np.empty(m)
    running = 0.0
    for rank, j in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[j]))
        adj[j] = running
    return {"adjusted": {k: float(adj[i]) for i, k in enumerate(keys)},
            "reject": {k: bool(adj[i] <= alpha) for i, k in enumerate(keys)}, "alpha": alpha, "m": m}


def binomial_lower_ci(k: int, n: int, level: float = 0.95) -> float:
    """Clopper-Pearson lower bound of a proportion (reported next to system-bootstrap CIs of verdict fractions)."""
    from scipy.stats import beta
    if n == 0:
        return float("nan")
    if k == 0:
        return 0.0
    return float(beta.ppf((1 - level) / 2, k, n - k + 1))
