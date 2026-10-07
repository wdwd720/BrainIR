"""Resampling statistics for the Phase 4 evaluator (benchmarks/causal_state_v1/PROTOCOL.md section 11).

Conventions (fixed by the protocol):
- percentile bootstrap with B = 2,000 resamples by default;
- the resampling unit is a CLUSTER, never a time step: within a system the IDENTITY CELL (a family x target set x magnitude class;
  its states stay together; cells are nested in FAMILIES, the unit of the class-balanced jackknife), across systems the system instance.
  Every row-level function takes an optional `groups` array: rows with the same group are resampled together;
- ratios are ratios of SUMS over the resampled clusters (never means of per-item ratios); the CLASS-BALANCED ratio is the unweighted
  mean over magnitude classes of the per-class ratio of sums (`CellDesign`, `boot_class_balanced`). Its CI (review E, N2 / M2, round 3
  N-new-4) is NOT a within-class multinomial bootstrap (that under-covered: classes of 2-4 cells, no small-sample rescaling, no family
  level): it is the delete-one-FAMILY jackknife (always families, never a fallback to cells) with Student-t quantiles and
  Bell-McCaffrey degrees of freedom (`bell_mccaffrey_df`), on the log scale for a single ratio and on the linear scale for a paired
  difference, after merging classes with fewer than MIN_CLASS_UNITS families; no interval below MIN_FAMILIES_CI families
  (`class_balanced_estimate`); its Estimate carries t-distributed replicates, so bounds and one-sided p-values work as for bootstrap
  Estimates;
- paired comparisons resample the SAME clusters for both arms;
- NON-FINITE REPLICATES ARE COUNTED AGAINST THE CLAIM, never dropped silently: a lower bound treats them as -inf, an upper bound as
  +inf (`percentile_ci`, `one_sided_upper`, `one_sided_lower`), and a one-sided p-value counts them on the null side (`boot_pvalue`);
  their number is reported (`Estimate.n_nonfinite_reps`);
- ONE alpha convention for confirmatory tests: one-sided at alpha = 0.05, the decision is p = (1 + count) / (1 + B) <= alpha and the
  reported bound is the one-sided 95 % bound (`noninferiority`); Holm's step-down procedure within the primary family (`holm`);
- system-level CIs: UNSTRATIFIED system resampling, or the RESCALED stratified bootstrap (each stratum's deviations multiplied by
  sqrt(n_h / (n_h - 1)); plain within-stratum resampling shrinks the variance by (n_h - 1) / n_h, review E B6), never with strata of
  size 1 (they are merged); failures in paired system comparisons are charged the worst admissible value when one is given (review E,
  M7), and the charged count is reported;
- binary system fractions: the one-sided Clopper-Pearson bound (`clopper_pearson_lower`).

Implementation: per-cluster sums are precomputed once, and each replicate is a vector of cluster multiplicities (multinomial counts),
so a replicate costs one weighted sum. All functions are deterministic given `seed`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

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


# ------------------------------------------------------------------------------------------------------------ bounds
def _quantile_against(r: np.ndarray, q: float, side: str) -> float:
    """The q-quantile of the replicates with non-finite replicates counted against the claim: as -inf for a lower bound ("lower"),
    as +inf for an upper bound ("upper"). Without non-finite replicates: the linear-interpolation quantile."""
    r = np.asarray(r, np.float64)
    if r.size == 0:
        return float("nan")
    fin = np.isfinite(r)
    if fin.all():
        return float(np.quantile(r, q))
    v = np.where(fin, r, -np.inf if side == "lower" else np.inf)
    return float(np.quantile(v, q, method="lower" if side == "lower" else "higher"))


def percentile_ci(reps: np.ndarray, level: float = 0.95) -> list[float]:
    """Two-sided percentile interval; non-finite replicates count against the claim on both sides (they widen the interval)."""
    r = np.asarray(reps, dtype=np.float64)
    if r.size == 0:
        return [float("nan"), float("nan")]
    a = (1.0 - level) / 2.0
    return [_quantile_against(r, a, "lower"), _quantile_against(r, 1.0 - a, "upper")]


def one_sided_upper(reps: np.ndarray | None, level: float = 1.0 - ALPHA) -> float:
    """One-sided upper bound (the `level` quantile; non-finite replicates count as +inf)."""
    if reps is None or len(reps) == 0:
        return float("nan")
    return _quantile_against(np.asarray(reps, np.float64), level, "upper")


def one_sided_lower(reps: np.ndarray | None, level: float = 1.0 - ALPHA) -> float:
    """One-sided lower bound (the 1 - `level` quantile; non-finite replicates count as -inf)."""
    if reps is None or len(reps) == 0:
        return float("nan")
    return _quantile_against(np.asarray(reps, np.float64), 1.0 - level, "lower")


@dataclass
class Estimate:
    """A point estimate with its percentile CI and the bootstrap replicates (kept for paired tests; strip before reporting)."""
    point: float
    ci95: list[float]
    n_units: int
    reps: np.ndarray | None = None
    n_nonfinite_reps: int = 0        # replicates that were non-finite (counted against the claim in every bound)
    n_charged: int = 0               # units charged the worst admissible value (failures in paired comparisons)
    n_dropped: int = 0               # units left out (non-finite values without an admissible worst value)
    extra: dict = field(default_factory=dict)

    def as_dict(self, keep_reps: bool = False) -> dict:
        d = {"point": self.point, "ci95": self.ci95, "n_units": self.n_units, "n_nonfinite_reps": self.n_nonfinite_reps,
             "n_charged": self.n_charged, "n_dropped": self.n_dropped, **self.extra}
        if keep_reps and self.reps is not None:
            d["reps"] = self.reps.tolist()
        return d


def make_estimate(point: float, reps: np.ndarray | None, n_units: int, *, worst: float | None = None, **extra) -> Estimate:
    """Estimate with the percentile CI of `reps` and the count of non-finite replicates. With `worst` (the worst admissible value of
    a statistic whose claims are upper bounds, e.g. a gain +1, the MEV cap), non-finite replicates are REPLACED by it: they still count
    against the claim, and the bounds stay finite; without it they count as -inf / +inf (`percentile_ci`)."""
    r = None if reps is None else np.asarray(reps, np.float64)
    nf = 0 if r is None else int((~np.isfinite(r)).sum())
    if r is not None and worst is not None and nf:
        r = np.where(np.isfinite(r), r, float(worst))
        extra["worst_charged"] = float(worst)
    ci = percentile_ci(r) if r is not None else [float("nan"), float("nan")]
    counts = {k: extra.pop(k) for k in ("n_charged", "n_dropped") if k in extra}
    return Estimate(float(point), ci, int(n_units), r, nf, extra=extra, **counts)


def _nan_estimate(n: int = 0) -> Estimate:
    return Estimate(float("nan"), [float("nan"), float("nan")], n, None)


# ------------------------------------------------------------------------------------------------------------ row estimators
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
    return make_estimate(float(v.mean()), reps, g)


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
    return make_estimate(float(num.sum() / den.sum()), reps, g)


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
    return make_estimate(point, reps, g)


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


def gain_vec(e1: np.ndarray, e2: np.ndarray, floor: float = 0.01) -> np.ndarray:
    """Vectorised `gain` (NaN where either input is non-finite)."""
    e1, e2 = np.asarray(e1, np.float64), np.asarray(e2, np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        g = np.maximum(-1.0, (e1 - e2) / np.maximum(e1, floor))
    return np.where(np.isfinite(e1) & np.isfinite(e2), g, np.nan)


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
    return make_estimate(gain(float(e1.mean()), float(e2.mean()), floor), gain_vec(m1, m2, floor), g)


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
    return make_estimate(float(stat(rows, np.ones(n))), reps, g)


# ------------------------------------------------------------------------------------------------------------ identity cells
@dataclass
class CellDesign:
    """Items grouped into identity cells (the resampling units within a system). A cell belongs to ONE magnitude class and ONE
    family (a cell id that occurs with several classes or families is split, so the design is always nested)."""
    cells: list[tuple]            # unique (cell id, class, family) keys
    item_cell: np.ndarray         # (n_items,) index into cells
    cell_class: np.ndarray        # (n_cells,) index into classes
    classes: list[str]
    cell_family: np.ndarray       # (n_cells,) index into families
    families: list[str]

    @classmethod
    def build(cls, cells: Sequence, classes: Sequence, families: Sequence | None = None) -> CellDesign:
        fam = list(families) if families is not None else ["all"] * len(cells)
        keys = [(str(c), str(k), str(f)) for c, k, f in zip(cells, classes, fam)]
        uniq = sorted(set(keys))
        pos = {k: i for i, k in enumerate(uniq)}
        cls_names = sorted({k[1] for k in uniq})
        fam_names = sorted({k[2] for k in uniq})
        return cls(cells=uniq, item_cell=np.array([pos[k] for k in keys], dtype=np.int64),
                   cell_class=np.array([cls_names.index(k[1]) for k in uniq], dtype=np.int64), classes=cls_names,
                   cell_family=np.array([fam_names.index(k[2]) for k in uniq], dtype=np.int64), families=fam_names)

    @property
    def n_cells(self) -> int:
        return len(self.cells)

    def cell_sums(self, values: np.ndarray) -> np.ndarray:
        return np.bincount(self.item_cell, weights=np.asarray(values, np.float64), minlength=self.n_cells)

    def weights(self, n_boot: int, seed: int, mode: str = "class") -> np.ndarray:
        """(n_boot, n_cells) cell multiplicities. mode "cells": all cells resampled together; "class": cells resampled within their
        magnitude class (every class keeps its cell count, so the class-balanced mean is defined in every replicate); "family_cell":
        two-stage, families drawn with replacement, then the cells of each drawn family with replacement."""
        rng = np.random.default_rng(seed)
        n = self.n_cells
        W = np.zeros((n_boot, n))
        if n == 0:
            return W
        if mode == "cells":
            return rng.multinomial(n, np.full(n, 1.0 / n), size=n_boot).astype(np.float64)
        if mode == "class":
            for k in range(len(self.classes)):
                idx = np.flatnonzero(self.cell_class == k)
                W[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1.0 / len(idx)), size=n_boot)
            return W
        if mode == "family_cell":
            n_f = len(self.families)
            Ff = rng.multinomial(n_f, np.full(n_f, 1.0 / n_f), size=n_boot)          # family multiplicities
            for f in range(n_f):
                idx = np.flatnonzero(self.cell_family == f)
                # the sum of Ff[b, f] independent resamples of the family's cells = one multinomial with Ff[b, f] * len(idx) trials
                W[:, idx] = rng.multinomial(Ff[:, f] * len(idx), np.full(len(idx), 1.0 / len(idx)))
            return W
        raise ValueError(f"unknown resampling mode {mode!r}")


#: review E, N2 / M2 and round 3, N-new-4. The resampling UNIT of a class-balanced CI is ALWAYS the FAMILY (cells are nested in
#: families); there is no fallback to cells (a design without any family structure has each cell as its own family). A magnitude class
#: with fewer than MIN_CLASS_UNITS families carrying signal is merged into its neighbour toward 'moderate' (below -> weak -> moderate,
#: hi -> strong -> moderate, na -> moderate; a class without a neighbour present joins the class with the most units), repeatedly,
#: until every class has at least that many families or one class is left. With fewer than MIN_FAMILIES_CI families carrying signal
#: there is NO interval ("too few families"): the criterion's input is missing.
MIN_CLASS_UNITS = 3
MIN_FAMILIES_CI = 4
CLASS_TOWARD = {"below": "weak", "weak": "moderate", "hi": "strong", "strong": "moderate", "na": "moderate"}


def merge_small_classes(cell_class_names: Sequence[str], cell_unit: Sequence, min_units: int = MIN_CLASS_UNITS,
                        cell_signal: Sequence[float] | None = None) -> dict[str, str]:
    """{original class: class it is merged into} under the rule of MIN_CLASS_UNITS (deterministic; identity when nothing merges);
    cell_unit = the family of every cell. With cell_signal (per cell, e.g. the truth denominator), only cells with a positive value
    count as units: a class without signal is always merged (its items' errors stay CHARGED in the neighbour class, never dropped), and
    no leave-one-family-out replicate can leave a class without a denominator."""
    names = [str(c) for c in cell_class_names]
    fams = [str(f) for f in cell_unit]
    sig = [True] * len(names) if cell_signal is None else [bool(s > 0) for s in cell_signal]
    mapping = {c: c for c in sorted(set(names))}

    def n_fam(c: str) -> int:
        return len({f for k, f, s in zip(names, fams, sig, strict=True) if mapping[k] == c and s})
    while True:
        present = sorted(set(mapping.values()))
        small = [c for c in present if n_fam(c) < min_units]
        if len(present) <= 1 or not small:
            return mapping
        c = min(small, key=lambda k: (n_fam(k), k))
        tgt = CLASS_TOWARD.get(c)
        seen = {c}
        while tgt is not None and tgt not in present and tgt not in seen:
            seen.add(tgt)
            tgt = CLASS_TOWARD.get(tgt)
        if tgt is None or tgt not in present or tgt == c:
            tgt = max((k for k in present if k != c), key=lambda k: (n_fam(k), k))
        for k, v in list(mapping.items()):
            if v == c:
                mapping[k] = tgt


def _unit_class_sums(cell_vals: np.ndarray, cell_unit: np.ndarray, cell_class: np.ndarray, n_units: int, n_classes: int) -> np.ndarray:
    out = np.zeros((n_units, n_classes))
    np.add.at(out, (cell_unit, cell_class), np.asarray(cell_vals, np.float64))
    return out


def _cb_value(arms_u: list[tuple[np.ndarray, np.ndarray]], signs: Sequence[float], keep: np.ndarray | None = None) -> float:
    tot = 0.0
    for (Nu, Du), sg in zip(arms_u, signs, strict=True):
        N = Nu.sum(0) if keep is None else Nu[keep].sum(0)
        D = Du.sum(0) if keep is None else Du[keep].sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            tot += float(sg) * float(np.mean(np.where(D > 0, N / np.where(D > 0, D, 1.0), np.nan)))
    return tot


def bell_mccaffrey_df(Du: np.ndarray) -> float:
    """Bell-McCaffrey degrees of freedom of the class-balanced statistic (the mean over K classes of per-class ratios of sums = K
    weighted-least-squares intercepts) with family weights Du (families x classes: summed truth denominators). Working model: one
    random effect per FAMILY (the items of a family move together); leverage h_fk = D_fk / D_k with the CR3-type adjustment
    a_fk = 1 / (1 - h_fk) (the delete-one-family jackknife is a CR3-type estimator). With B_fg = [f = g] sum_k c a_fk h_fk -
    sum_k h_fk c a_gk h_gk (c = 1 / K) and M = B'B: df = tr(M)^2 / tr(M^2), in [1, F - 1]. Equal family weights give F - 1; a class
    carried by one dominant family drives it toward 1 (review E, N-new-4: few or unequal families)."""
    F, K = Du.shape
    c = 1.0 / K
    D = Du.sum(0)
    h = np.where(D > 0, Du / np.where(D > 0, D, 1.0), 0.0)
    a = 1.0 / np.clip(1.0 - h, 1e-9, None)
    B = np.diag((c * a * h).sum(1)) - h @ (c * a * h).T
    M = B.T @ B
    tr, tr2 = float(np.trace(M)), float(np.trace(M @ M))
    return float(np.clip(tr * tr / tr2, 1.0, max(1.0, F - 1.0))) if tr2 > 0 else float(max(1.0, F - 1.0))


def jackknife_class_balanced(arms: list[tuple[np.ndarray, np.ndarray]], signs: Sequence[float], cell_class: np.ndarray, n_classes: int,
                             cell_unit: np.ndarray) -> dict:
    """Delete-one-FAMILY jackknife of sum_a sign_a x (class-balanced ratio of arm a) (one arm: the class-balanced EE; two arms with signs
    +1 / -1: a paired difference on the same cells). arms = [(cell num sums, cell den sums)]; cell_unit = the family of every cell.
    Returns {"point", "jack" (per-family leave-one-out values), "se", "df" (`bell_mccaffrey_df` of the first arm's family weights),
    "n_units"}."""
    units, uinv = np.unique(np.asarray(cell_unit).astype(str), return_inverse=True)
    nU = len(units)
    arms_u = [(_unit_class_sums(nc, uinv, cell_class, nU, n_classes), _unit_class_sums(dc, uinv, cell_class, nU, n_classes))
              for nc, dc in arms]
    point = _cb_value(arms_u, signs)
    if nU < 2:
        return {"point": point, "jack": np.array([]), "se": float("nan"), "df": float("nan"), "n_units": nU}
    jack = np.empty(nU)
    for i in range(nU):
        keep = np.ones(nU, bool)
        keep[i] = False
        jack[i] = _cb_value(arms_u, signs, keep)
    se = float(np.sqrt((nU - 1) / nU * np.sum((jack - jack.mean()) ** 2)))
    return {"point": point, "jack": jack, "se": se, "df": bell_mccaffrey_df(arms_u[0][1]), "n_units": nU}


def t_replicates(center: float, se: float, df: float, n_boot: int, seed: int, log_scale: bool = False) -> np.ndarray:
    """Replicates of the jackknife-t interval (seeded draws of center + se x T, T ~ Student t with df degrees of freedom; on the log
    scale exp(log center + se_log x T)): their percentiles are the t-interval and `boot_pvalue` on them is the t-test p-value, so the
    Estimate works everywhere a bootstrap Estimate does (independent draws, never a sorted grid: differences of two such Estimates
    treat them as independent)."""
    rng = np.random.default_rng(seed)
    T = rng.standard_t(df, size=n_boot) if np.isfinite(df) else rng.standard_normal(n_boot)
    with np.errstate(over="ignore"):                   # a huge log-scale interval (df ~ 1) overflows to +inf: counted against the claim
        return np.exp(np.log(center) + se * T) if log_scale else center + se * T


def class_structure(design: CellDesign, cell_den: np.ndarray) -> tuple[np.ndarray, bool, dict[str, str]]:
    """(the family of every cell, whether the design had no family labels, the class merge mapping) of a class-balanced statistic: the
    ONE definition used by `class_balanced_estimate` and by the per-class values the verdict reports (review E, M1 / N-new-6)."""
    cls_names = [design.classes[k] for k in design.cell_class]
    fam_names = [design.families[f] for f in design.cell_family]
    no_families = len(set(fam_names)) <= 1 and design.n_cells > 1
    units = np.array(["|".join(c) for c in design.cells] if no_families else fam_names, dtype=object)
    return units, no_families, merge_small_classes(cls_names, units, cell_signal=cell_den)


def class_values(num, den, design: CellDesign) -> dict[str, dict]:
    """{merged class: {"point": its ratio of sums, "n_cells", "n_families", "members"}}: the per-class ratios whose unweighted mean is the
    class-balanced statistic (point values; review E, M1: the per-class condition of criterion A, rule R3p of PROTOCOL section 9;
    N-new-6: the merge pattern)."""
    num, den = np.asarray(num, np.float64), np.asarray(den, np.float64)
    nc, dc = design.cell_sums(num), design.cell_sums(den)
    units, _, mapping = class_structure(design, dc)
    cls_names = [design.classes[k] for k in design.cell_class]
    out: dict[str, dict] = {}
    for k in sorted(set(mapping.values())):
        cells = [i for i, c in enumerate(cls_names) if mapping[c] == k]
        D = float(dc[cells].sum())
        out[k] = {"point": float(nc[cells].sum() / D) if D > 0 else float("nan"), "n_cells": len(cells),
                  "n_families": len({units[i] for i in cells if dc[i] > 0}), "members": sorted(c for c, v in mapping.items() if v == k)}
    return out


def class_balanced_estimate(arms: list[tuple[np.ndarray, np.ndarray]], signs: Sequence[float], design: CellDesign, n_boot: int = N_BOOT,
                            seed: int = 0, log_scale: bool = True) -> Estimate:
    """The class-balanced statistic of PROTOCOL 5.1 (one arm) or a paired difference of two (signs +1 / -1) with its CI (review E, N2 /
    M2; round 3, N-new-4): the delete-one-FAMILY jackknife (always families; a design without family labels has each cell as its own
    family), classes merged by `merge_small_classes` (at least MIN_CLASS_UNITS families per class), Student-t quantiles with the
    Bell-McCaffrey degrees of freedom of `bell_mccaffrey_df` (small when the families are few or a class rests on one dominant family);
    a single ratio on the LOG scale (exp(log point +- t se_log), se_log from the jackknife of the log statistic), a difference on the
    linear scale. Fewer than MIN_FAMILIES_CI families with signal: no interval (the criterion's input is missing). In simulations of
    review E's layouts (4-20 families x 2 cells x 4 states, family / cell log-sd 0.3-0.6, t3 item errors capped at 10x), P(upper bound
    < truth) 0.008-0.051 (mean 0.027) and 95 % coverage 0.945-0.991; the family jackknife with Satterthwaite df and a cell fallback it
    replaces gave 0.029-0.29 (review E: 0.06-0.13 at 6-8 families, 0.18-0.29 below 6). For a paired difference only the UPPER bound is
    used by any rule (B, C, H2, H3, H6); it is conservative (P(upper < truth) <= 0.007), while the lower bound is liberal (P(lower >
    truth) up to 0.075) and is descriptive only (review E, N-new-7)."""
    cls_names = [design.classes[k] for k in design.cell_class]
    signal = np.min(np.vstack([np.asarray(d, np.float64) for _, d in arms]), axis=0)
    units, no_families, mapping = class_structure(design, signal)
    merged = sorted(set(mapping.values()))
    mc = np.array([merged.index(mapping[c]) for c in cls_names], dtype=np.int64)
    n_sig = len({u for u, s in zip(units, signal, strict=True) if s > 0})
    jk = jackknife_class_balanced(arms, signs, mc, len(merged), units)
    point = jk["point"]
    extra = {"n_classes": len(merged), "classes_merged": {k: v for k, v in mapping.items() if k != v}, "method": "", "df": jk["df"],
             "n_jackknife_units": jk["n_units"], "n_families_with_signal": n_sig,
             "jackknife_unit": "cell (no family labels: every cell is its own family)" if no_families else "family"}
    if not np.isfinite(point):
        return make_estimate(float("nan"), None, design.n_cells, **extra)
    if n_sig < MIN_FAMILIES_CI or not np.isfinite(jk["se"]):
        extra["method"] = f"too few families ({n_sig} < {MIN_FAMILIES_CI}): no interval (review E, N-new-4)"
        return make_estimate(point, None, design.n_cells, **extra)
    use_log = log_scale and len(arms) == 1 and point > 0 and bool(np.all(jk["jack"] > 0))
    if use_log:
        lj = np.log(jk["jack"])
        nU = len(lj)
        se_l = float(np.sqrt((nU - 1) / nU * np.sum((lj - lj.mean()) ** 2)))
        reps = t_replicates(point, se_l, jk["df"], n_boot, seed, log_scale=True)
        extra.update({"method": "log-scale family jackknife, t with Bell-McCaffrey df", "se_log": se_l})
    else:
        reps = t_replicates(point, jk["se"], jk["df"], n_boot, seed)
        extra.update({"method": "family jackknife, t with Bell-McCaffrey df", "se": jk["se"]})
    return make_estimate(point, reps, design.n_cells, **extra)


def class_balanced_from_cells(num_c: np.ndarray, den_c: np.ndarray, cell_class: np.ndarray, n_classes: int,
                              W: np.ndarray) -> np.ndarray:
    """Class-balanced ratio for every row of the weight matrix W (n_rep, n_cells): per class the ratio of weighted sums, then the
    unweighted mean over the classes with a positive weighted denominator."""
    onehot = np.zeros((len(cell_class), n_classes))
    onehot[np.arange(len(cell_class)), cell_class] = 1.0
    N = W @ (num_c[:, None] * onehot)
    D = W @ (den_c[:, None] * onehot)
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.where(D > 0, N / np.where(D > 0, D, 1.0), np.nan)
    present = D > 0
    cnt = present.sum(1)
    return np.where(cnt > 0, np.nansum(np.where(present, R, 0.0), axis=1) / np.maximum(cnt, 1), np.nan)


def boot_class_balanced(num, den, design: CellDesign, n_boot: int = N_BOOT, seed: int = 0, mode: str = "class") -> Estimate:
    """Class-balanced ratio of sums (PROTOCOL 5.1: the unweighted mean over magnitude classes of the per-class ratio of sums, classes
    merged by `merge_small_classes`) with the family-jackknife-t CI of `class_balanced_estimate` (review E, N2 / M2: one method for A,
    C, H and B; `mode` is kept for callers and recorded, the cells are always clustered in their families). Every item must be in the
    design (num, den per item)."""
    num, den = np.asarray(num, np.float64), np.asarray(den, np.float64)
    if len(num) == 0 or not np.isfinite(den).all() or den.sum() <= 0:
        return _nan_estimate(design.n_cells if len(num) else 0)
    est = class_balanced_estimate([(design.cell_sums(num), design.cell_sums(den))], [1.0], design, n_boot, seed, log_scale=True)
    est.extra["mode"] = mode
    return est


def boot_class_balanced_diff(num_a, num_b, den, design: CellDesign, n_boot: int = N_BOOT, seed: int = 0, mode: str = "class",
                             den_b=None) -> Estimate:
    """PAIRED difference of class-balanced ratios on the same items (the same cells, the same leave-one-family-out sets; den is
    truth-based, shared by both models unless den_b is given), with the linear-scale family-jackknife-t CI of
    `class_balanced_estimate`."""
    num_a, num_b, den = (np.asarray(v, np.float64) for v in (num_a, num_b, den))
    den_b = den if den_b is None else np.asarray(den_b, np.float64)
    if len(num_a) == 0 or den.sum() <= 0 or den_b.sum() <= 0:
        return _nan_estimate(0)
    arms = [(design.cell_sums(num_a), design.cell_sums(den)), (design.cell_sums(num_b), design.cell_sums(den_b))]
    est = class_balanced_estimate(arms, [1.0, -1.0], design, n_boot, seed, log_scale=False)
    est.extra["mode"] = mode
    return est


# ------------------------------------------------------------------------------------------------------------ systems
def merge_small_strata(labels: Sequence[str]) -> list[str]:
    """Strata of size 1 are never used: all singleton strata are pooled into one stratum; if that pooled stratum is itself a
    singleton, it joins the largest stratum."""
    labels = [str(x) for x in labels]
    cnt = {k: labels.count(k) for k in set(labels)}
    single = {k for k, c in cnt.items() if c == 1}
    if not single:
        return labels
    out = [("~merged" if x in single else x) for x in labels]
    if len(single) == 1:
        others = {k: c for k, c in cnt.items() if k not in single}
        if others:
            big = max(sorted(others), key=lambda k: others[k])
            out = [(big if x == "~merged" else x) for x in out]
    return out


def stratified_system_boot(values_by_system: dict[str, float], strata: dict[str, str] | None = None,
                           stat: Callable[[np.ndarray], float] = np.mean, n_boot: int = N_BOOT, seed: int = 0) -> Estimate:
    """Statistic over SYSTEMS with a system bootstrap. Without strata: UNSTRATIFIED resampling. With strata: the RESCALED stratified
    bootstrap (PROTOCOL 11; review E, B6): in every stratum h (n_h >= 2; singleton strata are merged, `merge_small_strata`) the
    resampled values are replaced by the pseudo-values m_h + sqrt(n_h / (n_h - 1)) (y* - m_h), so each stratum mean has the unbiased
    variance s_h^2 / n_h instead of (n_h - 1) / n_h of it; the statistic is applied to the pseudo-sample."""
    sids = sorted(values_by_system)
    v = np.array([values_by_system[s] for s in sids], dtype=np.float64)
    if len(v) == 0:
        return _nan_estimate(0)
    rng = np.random.default_rng(seed)
    reps = np.empty(n_boot)
    if strata is None or len(v) < 2:
        for b in range(n_boot):
            reps[b] = stat(v[rng.integers(0, len(v), len(v))])
        return make_estimate(float(stat(v)), reps, len(v), stratified=False)
    st = np.array(merge_small_strata([strata.get(s, "all") for s in sids]))
    groups = [np.flatnonzero(st == k) for k in np.unique(st)]
    for b in range(n_boot):
        parts = []
        for m in groups:
            y = v[m]
            ys = y[rng.integers(0, len(m), len(m))]
            mh = y.mean()
            parts.append(mh + np.sqrt(len(m) / (len(m) - 1.0)) * (ys - mh) if len(m) > 1 else ys)
        reps[b] = stat(np.concatenate(parts))
    return make_estimate(float(stat(v)), reps, len(v), stratified=True, n_strata=len(groups))


def paired_system_boot(a_by_system: dict[str, float], b_by_system: dict[str, float], strata: dict[str, str] | None = None,
                       n_boot: int = N_BOOT, seed: int = 0, *, worst: float | None = None) -> Estimate:
    """Mean paired difference a - b over systems (unstratified, or the rescaled stratified bootstrap with `strata`). With `worst`
    (the worst admissible value of the metric, e.g. EE 10, SMS / ICG +1), a system on which an arm failed or produced a non-finite
    value (or is missing from one arm) is CHARGED that value for that arm (review E, M7); without it such systems are dropped. Both
    counts are reported (n_charged, n_dropped)."""
    keys = sorted(set(a_by_system) | set(b_by_system)) if worst is not None else sorted(set(a_by_system) & set(b_by_system))
    d, charged, dropped = {}, 0, 0
    for s in keys:
        va, vb = a_by_system.get(s, np.nan), b_by_system.get(s, np.nan)
        va = float(va) if va is not None else np.nan
        vb = float(vb) if vb is not None else np.nan
        if worst is not None:
            if not np.isfinite(va):
                va, charged = float(worst), charged + 1
            if not np.isfinite(vb):
                vb, charged = float(worst), charged + 1
        if np.isfinite(va) and np.isfinite(vb):
            d[s] = va - vb
        else:
            dropped += 1
    est = stratified_system_boot(d, strata, np.mean, n_boot, seed)
    est.n_charged, est.n_dropped = charged, dropped + (0 if worst is not None else
                                                       len(set(a_by_system) ^ set(b_by_system)))
    return est


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


def noninferiority(diff: Estimate, margin: float, alpha: float = ALPHA) -> dict:
    """ONE-SIDED test at level alpha on a lower-is-better scale (diff = method - comparator, or a statistic against a threshold):
    H0: diff >= margin, H1: diff < margin. Decision: p <= alpha; the reported bound is the one-sided (1 - alpha) upper bound (the
    same convention for every confirmatory test)."""
    if diff is None or not np.isfinite(diff.point) or diff.reps is None:
        return {"p": 1.0, "pass": False, "margin": float(margin), "diff": getattr(diff, "point", float("nan")),
                "upper_one_sided": float("nan"), "note": "not computable"}
    p = boot_pvalue(diff.reps, margin, "less")
    return {"p": p, "pass": bool(p <= alpha), "margin": float(margin), "diff": diff.point,
            "upper_one_sided": one_sided_upper(diff.reps, 1.0 - alpha), "alpha": alpha, "n_nonfinite_reps": diff.n_nonfinite_reps}


def superiority(diff: Estimate, alpha: float = ALPHA) -> dict:
    """Lower-is-better scale, diff = method - baseline. H1: diff < 0 (one-sided)."""
    return noninferiority(diff, 0.0, alpha)


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


def clopper_pearson_lower(k: int, n: int, conf: float = 0.975) -> float:
    """One-sided Clopper-Pearson lower bound of a proportion k / n at confidence `conf` (0.975 = the protocol's P_m bound)."""
    from scipy.stats import beta
    if n == 0:
        return float("nan")
    if k <= 0:
        return 0.0
    return float(beta.ppf(1.0 - conf, k, n - k + 1))


def binomial_lower_ci(k: int, n: int, level: float = 0.95) -> float:
    """Lower end of the two-sided Clopper-Pearson interval at `level` (= the one-sided (1 + level) / 2 bound)."""
    return clopper_pearson_lower(k, n, 1.0 - (1.0 - level) / 2.0)
