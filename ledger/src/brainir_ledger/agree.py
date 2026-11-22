"""Run 4 agreement statistics (PREREG v4 G5, G6, G7; bootstrap seed from G10).

G5: type scores, bands and the fraction rhythmic of a screen's replicates. G6: Spearman agreement between two screens X and Y over a
type set, in the cross-half form with its matched ceiling, the full-seed form beside it, percentile bootstrap intervals over types,
the secondary measures (a)-(e), and the paired same-seed agreement. G7: the words for a comparison and the gap closure of an
intervention (with its paired second form).

Pure functions of replicate tables. No file access, nothing simulates, and no label is read.

Conventions
-----------
* A screen's replicate table has one row per (type, seed), with the columns ``type`` (str), ``seed`` (int), ``usable`` (bool) and
  ``score`` (float, which may be NaN only when not usable). Tables are checked strictly, and each of these raises ``ValueError``: a
  missing column, a duplicated (type, seed), a usable replicate without a finite score, a requested seed that does not occur in the
  table, and a requested type with no row among the requested seeds.
* Spearman is the Pearson correlation of average ranks (``scipy.stats.rankdata``). It is NaN when either vector is constant or has
  fewer than 3 entries. One row-wise kernel serves both the point estimates and the bootstrap, so the two cannot diverge.
* The two-pair averages (cross-half form, split-half or ceiling form) and the mean of the two replication directions are plain
  means: a NaN in either input gives NaN (no ``nanmean``).
* Bootstrap (G6, G10): each call starts ``default_rng(seed)`` and draws every resample index array up front as
  ``rng.integers(0, n, size=(n_boot, n))``. The indices are positions in ``types`` *in the order given*, so two calls over the same
  type list share their resamples. Every quantity is recomputed from the same resampled types. A resample is dropped from every
  interval (and counted, ``n_dropped``) if any Spearman of the comparison is NaN, that is, if a resampled vector is constant.
  G6 does not cover a resample whose ratio (or closure) has a denominator of exactly 0. Such a resample is left out of that one
  quantity's interval only, and counted separately (``n_ratio_zero_ceiling``, ``n_zero_denominator``); percentiles over infinite
  values would come out NaN. Intervals are 95 % percentile intervals (2.5, 97.5; numpy's linear interpolation).
* Dict results are JSON-ready (Python float, int, str, bool, list, dict). An undefined value (NaN) is written as None. Scalar
  results (``spearman``, ``cohen_kappa``, ``top_overlap``, ``paired_agreement``) are floats and may be NaN.
"""

from __future__ import annotations

import operator
from collections.abc import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import rankdata

__all__ = ["AT_CEILING", "BOOT_SEED", "NOT_JUDGED", "N_BOOT", "REAL_GAP", "bands", "closure", "closure_vectors", "cohen_kappa",
           "compare", "compare_vectors", "frac_rhythmic", "paired_agreement", "paired_closure", "replication_rate", "spearman",
           "top_overlap", "type_scores", "words"]

DRIVER = 0.5           # G5: driver band (type score >= 0.5); also the threshold of the fraction rhythmic
NON_DRIVER = 0.05      # G5: non-driver band (type score < 0.05)
BANDS = ("non_driver", "indeterminate", "driver")  # band codes 0, 1, 2
TOP_K = 30             # G6 (e)
CEILING_MIN = 0.2      # G7: c < 0.2 -> not judged
RATIO_MIN = 0.90       # G7: at the ceiling needs ratio >= 0.90 ...
UPPER_MIN = 1.00       # ... and the upper end of the ratio's 95 % interval >= 1.00
BOOT_SEED = 20261401   # G10
N_BOOT = 10_000        # G6
PERCENTILES = (2.5, 97.5)
AT_CEILING, REAL_GAP, NOT_JUDGED = "at the ceiling", "a real gap", "not judged"
COLUMNS = ("type", "seed", "usable", "score")
_CHUNK = 2_000         # bootstrap rows ranked at a time (bounds memory; results do not depend on it)
_NAN = float("nan")


# ------------------------------------------------------------------------------------------------------------- validation
def _seed_list(seeds: Iterable[int]) -> list[int]:
    try:
        out = [operator.index(s) for s in seeds]
    except TypeError as e:
        raise ValueError(f"seeds must be integers: {e}") from None
    if len(set(out)) != len(out):
        raise ValueError("duplicated seed in a seed set")
    return out


def _halves(halves: Sequence[Iterable[int]]) -> tuple[list[int], list[int]]:
    if len(halves) != 2:
        raise ValueError("halves must be a pair (first half, second half)")
    h1, h2 = _seed_list(halves[0]), _seed_list(halves[1])
    if not h1 or not h2:
        raise ValueError("both seed halves must be non-empty")
    if set(h1) & set(h2):
        raise ValueError(f"seed halves overlap: {sorted(set(h1) & set(h2))}")
    return h1, h2


def _type_list(types: Iterable[str]) -> list[str]:
    if isinstance(types, str):
        raise TypeError("types must be a list of type names, not one string")
    tl = [str(t) for t in types]
    if not tl:
        raise ValueError("empty type list")
    if len(set(tl)) != len(tl):
        raise ValueError("duplicated type in the type list")
    return tl


def _replicates(df: pd.DataFrame) -> pd.DataFrame:
    """A validated copy of a replicate table with normalised dtypes (type str, seed int64, usable bool, score float)."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("a screen must be a pandas DataFrame of replicates")
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"replicate table lacks column(s) {missing}")
    if df["type"].isna().any():
        raise ValueError("replicate table has a missing type")
    seed = pd.to_numeric(df["seed"], errors="raise").to_numpy(dtype=float, na_value=np.nan)
    if not (np.isfinite(seed).all() and (seed == np.round(seed)).all()):
        raise ValueError("seeds must be integers (no missing value)")
    if not df["usable"].isin([True, False]).all():
        raise ValueError("usable must be True or False for every replicate")
    usable = df["usable"].astype(bool).to_numpy()
    score = pd.to_numeric(df["score"], errors="raise").to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(score[usable]).all():
        raise ValueError("a usable replicate has no finite score")
    d = pd.DataFrame({"type": df["type"].astype(str).to_numpy(), "seed": seed.astype(np.int64), "usable": usable, "score": score})
    dup = d.duplicated(["type", "seed"])
    if dup.any():
        first = d.loc[dup, ["type", "seed"]].iloc[0].tolist()
        raise ValueError(f"{int(dup.sum())} duplicated (type, seed) replicate(s), e.g. {first}")
    return d


def _select(d: pd.DataFrame, seeds: Iterable[int] | None) -> pd.DataFrame:
    if seeds is None:
        return d
    want = _seed_list(seeds)
    if not want:
        raise ValueError("empty seed set")
    have = set(d["seed"].tolist())
    absent = [s for s in want if s not in have]
    if absent:
        raise ValueError(f"seed(s) {absent} do not occur in the replicate table")
    return d[d["seed"].isin(want)]


def _type_index(d: pd.DataFrame, types: Iterable[str] | None) -> pd.Index:
    present = set(d["type"].tolist())
    if types is None:
        return pd.Index(sorted(present), name="type")
    tl = _type_list(types)
    missing = [t for t in tl if t not in present]
    if missing:
        raise ValueError(f"{len(missing)} type(s) have no replicate among the requested seeds, e.g. {missing[:5]}")
    return pd.Index(tl, name="type")


# ------------------------------------------------------------------------------------------------------------------- G5
def type_scores(df: pd.DataFrame, seeds: Iterable[int] | None = None, types: Iterable[str] | None = None) -> pd.Series:
    """G5 type score: the mean ``score`` over the usable replicates whose seed is in ``seeds`` (all seeds if None), or 0.0 if the
    type has no usable replicate among them (run 2's ``primary_score``). Indexed by type: sorted by name, or in the order of
    ``types``. A type in ``types`` with no row among the selected seeds raises ``ValueError``, as does a seed absent from the
    table."""
    d = _select(_replicates(df), seeds)
    idx = _type_index(d, types)
    mean = d[d["usable"]].groupby("type")["score"].mean()
    return mean.reindex(idx).fillna(0.0).astype(float).rename("type_score")


def frac_rhythmic(df: pd.DataFrame, seeds: Iterable[int] | None = None, types: Iterable[str] | None = None) -> pd.Series:
    """G5 fraction rhythmic: the share of all replicates (usable or not) in the seed set with score >= 0.5. An unusable replicate
    counts as not rhythmic, whatever score it carries."""
    d = _select(_replicates(df), seeds)
    idx = _type_index(d, types)
    rhythmic = (d["usable"] & (d["score"] >= DRIVER)).astype(float)
    return rhythmic.groupby(d["type"]).mean().reindex(idx).astype(float).rename("frac_rhythmic")


def _band_codes(v: np.ndarray) -> np.ndarray:
    return np.where(v >= DRIVER, 2, np.where(v < NON_DRIVER, 0, 1))


def bands(s: pd.Series) -> pd.Series:
    """G5 bands: 'driver' (>= 0.5), 'non_driver' (< 0.05), else 'indeterminate'. A non-finite score raises ``ValueError``."""
    s = s if isinstance(s, pd.Series) else pd.Series(s)
    v = s.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(v).all():
        raise ValueError("bands of a non-finite score")
    return pd.Series(np.array(BANDS, dtype=object)[_band_codes(v)], index=s.index, name="band")


# ----------------------------------------------------------------------------------------------------------- Spearman
def _centred_ranks(V: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Average ranks of each row of V (k, n), centred by their exact mean (n + 1) / 2, with each row's sum of squares. Average
    ranks are multiples of 1/2, so a constant row (all ranks (n + 1) / 2) has centred ranks and a sum of squares of exactly 0."""
    if V.shape[1] == 0:
        return np.zeros(V.shape), np.zeros(V.shape[0])
    D = rankdata(V, method="average", axis=1) - (V.shape[1] + 1) / 2.0
    return D, (D * D).sum(axis=1)


def _rho_rows(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    """Row-wise Pearson correlation of centred ranks (= Spearman). NaN for a constant row or fewer than 3 columns."""
    (Da, ssa), (Db, ssb) = a, b
    out = np.full(Da.shape[0], np.nan)
    if Da.shape[1] < 3:
        return out
    den = ssa * ssb
    ok = den > 0
    out[ok] = (Da * Db).sum(axis=1)[ok] / np.sqrt(den[ok])
    return np.clip(out, -1.0, 1.0)


def spearman(x, y) -> float:
    """Spearman correlation with average ranks (positional; no index alignment). NaN if either vector is constant or the length is
    below 3. Mismatched lengths or a non-finite value raise ``ValueError``."""
    a = np.asarray(x, dtype=float)
    b = np.asarray(y, dtype=float)
    if a.ndim != 1 or a.shape != b.shape:
        raise ValueError("spearman needs two 1-D vectors of the same length")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("spearman of a non-finite value")
    return float(_rho_rows(_centred_ranks(a[None, :]), _centred_ranks(b[None, :]))[0])


# -------------------------------------------------------------------------------------------------- G6 secondary measures
def _kappa_codes(ia: np.ndarray, ib: np.ndarray, n_cat: int) -> float:
    """Cohen's kappa from integer category codes, in exact integer arithmetic: (n * agree - S) / (n^2 - S) with
    S = sum_k count_a(k) count_b(k), which equals (p_o - p_e) / (1 - p_e). NaN when p_e == 1 (or no item)."""
    n = len(ia)
    if n == 0:
        return _NAN
    agree = int((ia == ib).sum())
    s = int(sum(int(p) * int(q) for p, q in zip(np.bincount(ia, minlength=n_cat), np.bincount(ib, minlength=n_cat))))
    den = n * n - s
    return _NAN if den == 0 else (n * agree - s) / den


def cohen_kappa(a: Iterable, b: Iterable) -> float:
    """Cohen's kappa of two equal-length label sequences (G6 (d) applies it to the three bands). NaN when the expected agreement is
    1 (both raters use one and the same category) or the sequences are empty."""
    a, b = list(a), list(b)
    if len(a) != len(b):
        raise ValueError("cohen_kappa needs two sequences of the same length")
    cats = {c: i for i, c in enumerate(sorted(set(a) | set(b), key=str))}
    return _kappa_codes(np.array([cats[c] for c in a], dtype=np.int64), np.array([cats[c] for c in b], dtype=np.int64), len(cats))


def _replication(a: np.ndarray, b: np.ndarray) -> dict:
    """G6 (c) for one pair: of A's drivers the share that are drivers in B, the reverse, and their plain mean."""
    da, db = a >= DRIVER, b >= DRIVER
    both = int((da & db).sum())
    a_to_b = both / int(da.sum()) if da.any() else _NAN
    b_to_a = both / int(db.sum()) if db.any() else _NAN
    return {"n_drivers_a": int(da.sum()), "n_drivers_b": int(db.sum()), "n_drivers_both": both, "a_to_b": a_to_b,
            "b_to_a": b_to_a, "mean": (a_to_b + b_to_a) / 2}


def _top_set(names: Sequence[str], v: np.ndarray, k: int) -> set[str]:
    """The top k types with a NON-ZERO score (score descending, ties by name ascending); fewer if fewer are non-zero (PREREG v4 G6 e:
    zero-score types never enter a top list, so an alphabetical tie-break among zeros cannot inflate the overlap)."""
    order = sorted((i for i in range(len(names)) if float(v[i]) > 0), key=lambda i: (-float(v[i]), names[i]))
    return {names[i] for i in order[:k]}


def _top_overlap(names: Sequence[str], a: np.ndarray, b: np.ndarray, k: int = TOP_K) -> float:
    """G6 (e): |A & B| / max(|A|, |B|) with A, B the top-k non-zero types of each vector (ties by name); NaN if both are empty."""
    A, B = _top_set(names, a, k), _top_set(names, b, k)
    m = max(len(A), len(B))
    if m == 0:
        return _NAN
    return len(A & B) / m


def _aligned(x: pd.Series, y: pd.Series) -> tuple[list[str], np.ndarray, np.ndarray]:
    x, y = pd.Series(x), pd.Series(y)
    names = [str(t) for t in x.index]
    ynames = [str(t) for t in y.index]
    if len(set(names)) != len(names) or len(set(ynames)) != len(ynames) or set(names) != set(ynames):
        raise ValueError("the two score vectors must cover the same types, each once")
    a = x.to_numpy(dtype=float, na_value=np.nan)
    b = pd.Series(y.to_numpy(dtype=float, na_value=np.nan), index=ynames).reindex(names).to_numpy()
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("non-finite type score")
    return names, a, b


def replication_rate(x: pd.Series, y: pd.Series) -> dict:
    """G6 (c) for two type-score vectors (aligned by type): ``a_to_b`` = of the drivers (>= 0.5) in x, the fraction that are also
    drivers in y (None if x has none); ``b_to_a`` the reverse; ``mean`` their plain mean (None if either is undefined)."""
    _, a, b = _aligned(x, y)
    return _json(_replication(a, b))


def top_overlap(x: pd.Series, y: pd.Series, k: int = TOP_K) -> float:
    """G6 (e) for two type-score vectors (aligned by type): the top-k NON-ZERO types of each (score descending, ties by name ascending;
    fewer if fewer are non-zero); |A & B| / max(|A|, |B|), NaN if both are empty."""
    names, a, b = _aligned(x, y)
    return _top_overlap(names, a, b, k)


# ------------------------------------------------------------------------------------------------------------- G6 core
def _div(a: float, b: float) -> float:
    if not (np.isfinite(a) and np.isfinite(b)) or b == 0:
        return _NAN
    return float(a / b)


def _mean(vals: Sequence[float]) -> float:
    return float(np.mean(np.asarray(vals, dtype=float)))  # NaN propagates


def _pct(a: np.ndarray) -> list[float]:
    if a.size == 0:
        return [_NAN, _NAN]
    return [float(q) for q in np.percentile(a, PERCENTILES)]


def _num(x) -> float:
    return _NAN if x is None else float(x)


def _json(o):
    """NaN and infinities -> None; numpy scalars -> Python scalars; tuples -> lists."""
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    if o is None or isinstance(o, str):
        return o
    raise TypeError(f"not JSON-ready: {type(o).__name__}")


# internal vector keys -> the public argument names of compare_vectors / closure_vectors (for error messages)
_ARG = {"X": "x_full", "X_h1": "x1", "X_h2": "x2", "Y": "y_full", "Y_h1": "y1", "Y_h2": "y2", "B": "xb_full", "B_h1": "xb1",
        "B_h2": "xb2", "A": "xa_full", "A_h1": "xa1", "A_h2": "xa2", "Z": "ya_full", "Z_h1": "ya1", "Z_h2": "ya2"}


def _check_vectors(series: dict[str, pd.Series]) -> tuple[list[str], dict[str, np.ndarray]]:
    """Type-score Series that must all be indexed by the same types in the same order (each type once) with finite values. Returns
    the type list and the values as arrays."""
    keys = list(series)
    first = series[keys[0]]
    if not isinstance(first, pd.Series):
        raise TypeError(f"{_ARG[keys[0]]} must be a pandas Series indexed by type")
    tl = [str(t) for t in first.index]
    if not tl:
        raise ValueError("empty type-score vectors")
    if len(set(tl)) != len(tl):
        raise ValueError(f"duplicated type in {_ARG[keys[0]]}")
    out = {}
    for k in keys:
        s = series[k]
        if not isinstance(s, pd.Series):
            raise TypeError(f"{_ARG[k]} must be a pandas Series indexed by type")
        if [str(t) for t in s.index] != tl:
            raise ValueError(f"{_ARG[k]} is not indexed by the same types in the same order as {_ARG[keys[0]]}")
        a = s.to_numpy(dtype=float, na_value=np.nan)
        if not np.isfinite(a).all():
            raise ValueError(f"non-finite type score in {_ARG[k]}")
        out[k] = a
    return tl, out


def _equal_members(member_counts: Mapping[str, tuple[int, int]] | None, tl: list[str]) -> np.ndarray | None:
    if member_counts is None:
        return None
    mc = {str(k): v for k, v in member_counts.items()}
    missing = [t for t in tl if t not in mc]
    if missing:
        raise ValueError(f"member_counts lacks {len(missing)} type(s), e.g. {missing[:5]}")
    eq = []
    for t in tl:
        n_left, n_right = mc[t]
        eq.append(operator.index(n_left) == operator.index(n_right))
    return np.array(eq, dtype=bool)


def _draw(n: int, n_boot: int, seed: int) -> np.ndarray:
    n_boot = operator.index(n_boot)
    if n_boot < 1:
        raise ValueError("n_boot must be at least 1")
    rng = np.random.default_rng(seed)
    return rng.integers(0, n, size=(n_boot, n))


def _resampled_rhos(v: dict[str, np.ndarray], pairs: Sequence[tuple[str, str]], idx: np.ndarray) -> dict[tuple[str, str], np.ndarray]:
    """Spearman of every pair on every resample (rows of idx): each vector is resampled and ranked once per chunk."""
    names = sorted({k for p in pairs for k in p})
    out = {p: np.empty(idx.shape[0]) for p in pairs}
    for lo in range(0, idx.shape[0], _CHUNK):
        rows = idx[lo:lo + _CHUNK]
        ranks = {k: _centred_ranks(v[k][rows]) for k in names}
        for p in pairs:
            out[p][lo:lo + _CHUNK] = _rho_rows(ranks[p[0]], ranks[p[1]])
    return out


def _pairs(x: str, y: str) -> list[tuple[str, str]]:
    """The five Spearmans of one comparison: full seeds; the two cross-half pairs; the two split-half (ceiling) pairs."""
    return [(x, y), (f"{x}_h1", f"{y}_h2"), (f"{x}_h2", f"{y}_h1"), (f"{x}_h1", f"{x}_h2"), (f"{y}_h1", f"{y}_h2")]


_LABELS = ("X~Y", "X_h1~Y_h2", "X_h2~Y_h1", "X_h1~X_h2", "Y_h1~Y_h2")


def _pair_block(v: dict[str, np.ndarray], rh: dict, x: str, y: str, seed: int) -> tuple[dict, dict]:
    """Point estimates, bootstrap intervals and words for the comparison of screens ``x`` and ``y`` (G6, G7); also returns the
    per-resample rho_x and c for the closure."""
    P = _pairs(x, y)
    r = [spearman(v[a], v[b]) for a, b in P]
    rho_x, c = (r[1] + r[2]) / 2, (r[3] + r[4]) / 2
    ratio = _div(rho_x, c)
    B = [rh[p] for p in P]
    b_x, b_c = (B[1] + B[2]) / 2, (B[3] + B[4]) / 2
    with np.errstate(divide="ignore", invalid="ignore"):
        b_ratio = b_x / b_c
    keep = ~np.isnan(np.vstack(B)).any(axis=0)  # G6: a resample with a constant vector (a NaN Spearman) is dropped
    ratio_ok = keep & np.isfinite(b_ratio)       # beyond G6: a ceiling of exactly 0 leaves only the ratio undefined
    iv = {"rho_full": _pct(B[0][keep]), "rho_x": _pct(b_x[keep]), "c": _pct(b_c[keep]), "ratio": _pct(b_ratio[ratio_ok])}
    block = {"primary": {"rho_full": r[0], "rho_x": rho_x, "c": c, "ratio": ratio,
                         "rho_x_pairs": {_LABELS[1]: r[1], _LABELS[2]: r[2]}, "c_pairs": {_LABELS[3]: r[3], _LABELS[4]: r[4]}},
             "bootstrap": {"n_boot": int(keep.size), "seed": int(seed), "percentiles": list(PERCENTILES), "n_used": int(keep.sum()),
                           "n_dropped": int((~keep).sum()), "n_ratio_zero_ceiling": int((keep & ~ratio_ok).sum()), "interval": iv},
             "words": words(ratio, iv["ratio"], c)}
    return block, {"rho_x": b_x, "c": b_c}


_FORMS = {"full": (("X", "Y"),), "cross": (("X_h1", "Y_h2"), ("X_h2", "Y_h1")), "split": (("X_h1", "X_h2"), ("Y_h1", "Y_h2"))}


def _secondary(v: dict[str, np.ndarray], tl: list[str], eq: np.ndarray | None) -> dict:
    """G6 (a)-(e), each in the three forms. A form's value is the plain mean over its pairs (one pair for "full"); every pair is
    listed with its own value. In "full" and "cross", a is X's vector and b is Y's; in "split", a is the first half and b the
    second."""
    def per_form(fn, combine):
        return {f: combine([{"a": a, "b": b, **fn(v[a], v[b])} for a, b in prs]) for f, prs in _FORMS.items()}

    def rho_on(mask_of):
        def fn(a, b):
            m = mask_of(a, b)
            return {"n": int(m.sum()), "rho": spearman(a[m], b[m])}
        return fn

    def mean_of(key):
        return lambda rows: {"value": _mean([r[key] for r in rows]), "pairs": rows}

    def replication(rows):
        return {"a_to_b": _mean([r["a_to_b"] for r in rows]), "b_to_a": _mean([r["b_to_a"] for r in rows]),
                "mean": _mean([r["mean"] for r in rows]), "pairs": rows}

    out = {"nonzero": per_form(rho_on(lambda a, b: (a > 0) | (b > 0)), mean_of("rho"))}
    out["equal_members"] = None if eq is None else {"n_types": int(eq.sum()), **per_form(rho_on(lambda a, b: eq), mean_of("rho"))}
    out["replication"] = per_form(_replication, replication)
    out["kappa"] = per_form(lambda a, b: {"kappa": _kappa_codes(_band_codes(a), _band_codes(b), len(BANDS))}, mean_of("kappa"))
    out["top30"] = per_form(lambda a, b: {"overlap": _top_overlap(tl, a, b, TOP_K)}, mean_of("overlap"))
    return out


# ------------------------------------------------------------------------------------------------------------------- G7
def words(ratio: float | None, ratio_interval: Sequence[float | None] | None, c: float | None) -> str:
    """G7: 'not judged' if c < 0.2; otherwise 'at the ceiling' if ratio >= 0.90 and the upper end of its 95 % interval is >= 1.00;
    otherwise 'a real gap'. An undefined c, ratio or upper end (NaN or None) gives 'not judged': the rule cannot be applied."""
    c_, r_ = _num(c), _num(ratio)
    hi = _num(ratio_interval[1]) if ratio_interval is not None else _NAN
    if not np.isfinite(c_) or c_ < CEILING_MIN:
        return NOT_JUDGED
    if not (np.isfinite(r_) and np.isfinite(hi)):
        return NOT_JUDGED
    return AT_CEILING if (r_ >= RATIO_MIN and hi >= UPPER_MIN) else REAL_GAP


# ------------------------------------------------------------------------------------------------------------ public G6
def compare_vectors(x_full: pd.Series, y_full: pd.Series, x1: pd.Series, x2: pd.Series, y1: pd.Series, y2: pd.Series, *,
                    member_counts: Mapping[str, tuple[int, int]] | None = None, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> dict:
    """G6 agreement of screens X and Y, and the G7 words, from precomputed type scores. Each of the six Series must be indexed by the
    same types in the same order (each type once), or ``ValueError`` is raised. x1 and x2 are X's type scores from the first and
    second seed half, and x_full is from all seeds of both halves; the same holds for Y. The bootstrap resamples positions in this
    order. Use this function directly when a type score is not G5's mean over replicates (for example A0's per-side mean over
    member neurons). ``compare`` builds the six vectors with ``type_scores`` and returns this function's result.

    Result (JSON-ready; None means undefined):
    * ``n_types``.
    * ``primary``: rho_full = rho(x_full, y_full); rho_x = (rho(x1, y2) + rho(x2, y1)) / 2 (the primary cross-half agreement);
      c = (rho(x1, x2) + rho(y1, y2)) / 2 (the matched ceiling); ratio = rho_x / c; and each pair's rho.
    * ``bootstrap``: n_boot resamples of the types (``default_rng(seed)``); 2.5 and 97.5 percentiles of rho_full, rho_x, c and ratio
      over the kept resamples; ``n_dropped`` (a constant resampled vector, G6) and ``n_ratio_zero_ceiling`` (kept resamples
      whose ceiling is exactly 0, left out of the ratio interval only).
    * ``words``: G7 ('at the ceiling', 'a real gap' or 'not judged').
    * ``secondary``: G6 (a) ``nonzero``, (b) ``equal_members`` (only with ``member_counts``, type -> (n_left, n_right); else None),
      (c) ``replication``, (d) ``kappa`` and (e) ``top30``. Each has "full", "cross" and "split" forms (see ``_secondary``)."""
    tl, v = _check_vectors({"X": x_full, "Y": y_full, "X_h1": x1, "X_h2": x2, "Y_h1": y1, "Y_h2": y2})
    eq = _equal_members(member_counts, tl)
    rh = _resampled_rhos(v, _pairs("X", "Y"), _draw(len(tl), n_boot, seed))
    block, _ = _pair_block(v, rh, "X", "Y", seed)
    return _json({"n_types": len(tl), **block, "secondary": _secondary(v, tl, eq)})


def _three(df: pd.DataFrame, tl: list[str], h1: list[int], h2: list[int]) -> tuple[pd.Series, pd.Series, pd.Series]:
    """A screen's G5 type scores on h1 + h2, on h1 and on h2."""
    return type_scores(df, h1 + h2, tl), type_scores(df, h1, tl), type_scores(df, h2, tl)


def compare(X: pd.DataFrame, Y: pd.DataFrame, types: list[str], halves: tuple[list[int], list[int]], *,
            member_counts: dict[str, tuple[int, int]] | None = None, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> dict:
    """G6 agreement of two screens' replicate tables over ``types``, given in a fixed order because the bootstrap resamples
    positions. Every type must have rows in each half of both screens. The halves (h1, h2) must be disjoint, and each of their seeds
    must occur in both screens. Type scores follow G5 on h1 + h2, h1 and h2. Returns ``compare_vectors`` of these six vectors."""
    tl = _type_list(types)
    h1, h2 = _halves(halves)
    xf, x1, x2 = _three(X, tl, h1, h2)
    yf, y1, y2 = _three(Y, tl, h1, h2)
    return compare_vectors(xf, yf, x1, x2, y1, y2, member_counts=member_counts, n_boot=n_boot, seed=seed)


def closure_vectors(xb_full: pd.Series, xb1: pd.Series, xb2: pd.Series, xa_full: pd.Series, xa1: pd.Series, xa2: pd.Series,
                    y_full: pd.Series, y1: pd.Series, y2: pd.Series, *, ya_full: pd.Series | None = None, ya1: pd.Series | None = None,
                    ya2: pd.Series | None = None, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> dict:
    """G7 gap closure from precomputed type scores: before = X (xb_*), after = X' (xa_*), target Y (y_*). All Series must be indexed
    by the same types in the same order, as in ``compare_vectors``. ``ya_full``, ``ya1`` and ``ya2`` (all three or none) give a
    changed target Y' for the after pair (see ``closure``). ``closure`` returns this function's result."""
    series = {"B": xb_full, "B_h1": xb1, "B_h2": xb2, "A": xa_full, "A_h1": xa1, "A_h2": xa2, "Y": y_full, "Y_h1": y1, "Y_h2": y2}
    new_y = (ya_full, ya1, ya2)
    if any(s is not None for s in new_y):
        if any(s is None for s in new_y):
            raise ValueError("give all three of ya_full, ya1 and ya2, or none of them")
        series.update({"Z": ya_full, "Z_h1": ya1, "Z_h2": ya2})
    tl, v = _check_vectors(series)
    ya = "Z" if "Z" in v else "Y"
    pairs = list(dict.fromkeys(_pairs("B", "Y") + _pairs("A", ya)))
    rh = _resampled_rhos(v, pairs, _draw(len(tl), n_boot, seed))
    before, bb = _pair_block(v, rh, "B", "Y", seed)
    after, ab = _pair_block(v, rh, "A", ya, seed)
    rx_b, c_b, rx_a = before["primary"]["rho_x"], before["primary"]["c"], after["primary"]["rho_x"]
    with np.errstate(divide="ignore", invalid="ignore"):
        arr = (ab["rho_x"] - bb["rho_x"]) / (bb["c"] - bb["rho_x"])
    undefined = np.isnan(bb["rho_x"]) | np.isnan(bb["c"]) | np.isnan(ab["rho_x"])  # G6 drop: a needed Spearman is NaN
    zero_den = ~undefined & ~np.isfinite(arr)                                         # c(X, Y) == rho_x(X, Y): no closure
    keep = ~undefined & ~zero_den
    return _json({"n_types": len(tl), "y_changed": ya == "Z", "before": before, "after": after,
                  "closure": _div(rx_a - rx_b, c_b - rx_b), "closure_interval": _pct(arr[keep]),
                  "closure_bootstrap": {"n_boot": int(keep.size), "seed": int(seed), "percentiles": list(PERCENTILES),
                                        "n_used": int(keep.sum()), "n_dropped": int(undefined.sum()),
                                        "n_zero_denominator": int(zero_den.sum())},
                  "after_ratio_vs_before_ceiling": _div(rx_a, c_b),
                  "reported": before["words"] == REAL_GAP, "closes_whole_gap": after["words"] == AT_CEILING})


def closure(X_before: pd.DataFrame, X_after: pd.DataFrame, Y: pd.DataFrame, types: list[str], halves: tuple[list[int], list[int]],
            n_boot: int = N_BOOT, seed: int = BOOT_SEED, *, Y_after: pd.DataFrame | None = None) -> dict:
    """G7 gap closure of an intervention that turns X into X' (compared with the same Y). The formula is
    closure = (rho_x(X', Y) - rho_x(X, Y)) / (c(X, Y) - rho_x(X, Y)), and its percentile interval uses the same resamples for every
    quantity. The interval leaves out a resample in which a Spearman it needs is undefined (``n_dropped``), or in which its
    denominator is exactly 0 (``n_zero_denominator``).

    ``before`` and ``after`` hold each pair's primary block, bootstrap and words, identical to ``compare`` on that pair with the same
    seed. The after pair's words use its own ratio rho_x(X', Y) / c(X', Y). ``after_ratio_vs_before_ceiling`` = rho_x(X', Y) /
    c(X, Y) is reported beside it. ``reported`` is True only when the before pair is 'a real gap': G7 reports the closure only then,
    but it is always computed. ``closes_whole_gap`` is True when the after pair is 'at the ceiling'.

    ``Y_after`` is not in G7's wording. Use it for an intervention that changes both screens of the pair, for example a re-scoring
    of both sides (B1.2) or another floor for both sides (B4.4). The after pair is then (X', Y'), and the same formula is used with
    rho_x(X', Y') in place of rho_x(X', Y). Returns ``closure_vectors`` of the screens' G5 type scores."""
    tl = _type_list(types)
    h1, h2 = _halves(halves)
    ya = _three(Y_after, tl, h1, h2) if Y_after is not None else (None, None, None)
    return closure_vectors(*_three(X_before, tl, h1, h2), *_three(X_after, tl, h1, h2), *_three(Y, tl, h1, h2), ya_full=ya[0],
                           ya1=ya[1], ya2=ya[2], n_boot=n_boot, seed=seed)


def paired_agreement(X: pd.DataFrame, Y: pd.DataFrame, types: list[str], seeds: Iterable[int]) -> float:
    """G6 paired same-seed agreement: Spearman of the two screens' type scores on the same ``seeds`` (labelled second statistic;
    its reference is the relabelling control, B2.4)."""
    tl = _type_list(types)
    sl = _seed_list(seeds)
    return spearman(type_scores(X, sl, tl).to_numpy(), type_scores(Y, sl, tl).to_numpy())


def paired_closure(X_before: pd.DataFrame, X_after: pd.DataFrame, Y: pd.DataFrame, types: list[str], seeds: Iterable[int],
                   r_ref: float, *, Y_after: pd.DataFrame | None = None) -> dict:
    """G7 paired form (second statistic): (rho_p(X', Y) - rho_p(X, Y)) / (r_ref - rho_p(X, Y)), with rho_p = ``paired_agreement``
    and r_ref = the relabelling control's paired agreement. ``Y_after`` as in ``closure``."""
    rb = paired_agreement(X_before, Y, types, seeds)
    ra = paired_agreement(X_after, Y if Y_after is None else Y_after, types, seeds)
    return _json({"rho_p_before": rb, "rho_p_after": ra, "r_ref": float(r_ref), "closure_p": _div(ra - rb, float(r_ref) - rb),
                  "y_changed": Y_after is not None})
