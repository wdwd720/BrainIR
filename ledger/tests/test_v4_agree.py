"""Run 4 agreement statistics (PREREG v4 G5-G7) on synthetic screens with known answers. No real prediction, score table or label
is read."""

from __future__ import annotations

import inspect
import json

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from brainir_ledger import agree as AG

H8 = (list(range(8)), list(range(8, 16)))  # G6: 16 seeds -> 0..7 and 8..15


def _screen(base: dict[str, float], rng, *, noise: float = 0.0, p_unusable: float = 0.0, seeds=range(16)) -> pd.DataFrame:
    """One replicate per (type, seed): score = clip(base + N(0, noise), 0, 1); unusable with probability p_unusable (score NaN)."""
    rows = []
    for t, b in base.items():
        for s in seeds:
            ok = bool(rng.uniform() >= p_unusable)
            sc = float(np.clip(b + rng.normal(0.0, noise), 0.0, 1.0))
            rows.append({"type": t, "seed": int(s), "usable": ok, "score": sc if ok else np.nan})
    return pd.DataFrame(rows)


def _flat(scores: dict[str, float], seeds=range(16)) -> pd.DataFrame:
    """Every replicate of a type has the same score (no seed noise), so each half's type scores equal the full-seed ones."""
    return pd.DataFrame([{"type": t, "seed": s, "usable": True, "score": float(v)} for t, v in scores.items() for s in seeds])


def _base(n: int, rng, p_zero: float = 0.3) -> dict[str, float]:
    v = rng.uniform(0.0, 1.0, n)
    v[rng.uniform(size=n) < p_zero] = 0.0
    return {f"DNt{i:02d}": float(x) for i, x in enumerate(v)}


def _six(X: pd.DataFrame, Y: pd.DataFrame, types, halves=H8):
    h1, h2 = halves
    ts = lambda df, s: AG.type_scores(df, s, types)
    return ts(X, h1 + h2), ts(Y, h1 + h2), ts(X, h1), ts(X, h2), ts(Y, h1), ts(Y, h2)


# ------------------------------------------------------------------------------------------------------------------- G5
def _small() -> pd.DataFrame:
    return pd.DataFrame([("A", 0, True, 0.2), ("A", 1, False, np.nan), ("A", 2, True, 0.6), ("A", 3, True, 0.4),
                         ("B", 0, False, np.nan), ("B", 1, False, 0.9), ("B", 2, False, np.nan), ("B", 3, False, np.nan),
                         ("C", 0, False, 0.9), ("C", 1, True, 0.1), ("C", 2, True, 0.7), ("C", 3, True, 0.5)],
                        columns=["type", "seed", "usable", "score"])


def test_type_scores_mean_over_usable_zero_if_none():
    df = _small()
    s = AG.type_scores(df)
    assert list(s.index) == ["A", "B", "C"]
    assert s["A"] == pytest.approx(0.4)                 # (0.2 + 0.6 + 0.4) / 3; the unusable seed 1 is ignored
    assert s["B"] == 0.0                                # no usable replicate (its unusable 0.9 does not count)
    assert s["C"] == pytest.approx((0.1 + 0.7 + 0.5) / 3)
    sub = AG.type_scores(df, seeds=[0, 1])
    assert sub.to_dict() == pytest.approx({"A": 0.2, "B": 0.0, "C": 0.1})
    assert list(AG.type_scores(df, types=["C", "A"]).index) == ["C", "A"]


def test_frac_rhythmic_counts_every_replicate_and_unusable_as_not_rhythmic():
    f = AG.frac_rhythmic(_small())
    # A: 0.2, (unusable), 0.6, 0.4 -> 1 of 4; B: all unusable (one carries 0.9) -> 0; C: (unusable 0.9), 0.1, 0.7, 0.5 -> 2 of 4
    assert f.to_dict() == {"A": 0.25, "B": 0.0, "C": 0.5}
    assert AG.frac_rhythmic(_small(), seeds=[2, 3], types=["C"]).to_dict() == {"C": 1.0}


def test_type_scores_are_strict():
    df = _small()
    with pytest.raises(ValueError, match="no replicate"):
        AG.type_scores(df, types=["A", "Z"])                                   # a type with no rows at all
    extra = pd.concat([df, pd.DataFrame([("D", 3, False, np.nan)], columns=df.columns)], ignore_index=True)
    with pytest.raises(ValueError, match="no replicate"):
        AG.type_scores(extra, seeds=[0, 1], types=["A", "D"])                  # D has rows, but none among the seeds
    with pytest.raises(ValueError, match="do not occur"):
        AG.type_scores(df[df["seed"] < 2], seeds=[0, 1, 2])                    # a requested seed is absent
    bad = df.copy()
    bad.loc[0, "score"] = np.nan
    with pytest.raises(ValueError, match="usable replicate"):
        AG.type_scores(bad)                                                    # usable without a score
    with pytest.raises(ValueError, match="duplicated"):
        AG.type_scores(pd.concat([df, df.iloc[[0]]], ignore_index=True))       # (type, seed) twice
    with pytest.raises(ValueError, match="lacks"):
        AG.type_scores(df.drop(columns="usable"))
    strs = df.copy()
    strs["usable"] = strs["usable"].map({True: "True", False: "False"})
    with pytest.raises(ValueError, match="usable"):
        AG.type_scores(strs)                                                   # "False" would be truthy
    with pytest.raises(ValueError, match="empty"):
        AG.type_scores(df, seeds=[])


def test_bands_thresholds():
    s = pd.Series([0.5, 0.4999, 0.05, 0.0499, 0.0, 1.0], index=list("abcdef"))
    assert AG.bands(s).tolist() == ["driver", "indeterminate", "indeterminate", "non_driver", "non_driver", "driver"]
    assert list(AG.bands(s).index) == list("abcdef")
    with pytest.raises(ValueError):
        AG.bands(pd.Series([0.3, np.nan]))


# ------------------------------------------------------------------------------------------------------- Spearman, (c)-(e)
def test_spearman_matches_scipy_with_ties():
    rng = np.random.default_rng(3)
    for _ in range(60):
        n = int(rng.integers(3, 40))
        a, b = np.round(rng.uniform(0, 1, n), 1), np.round(rng.uniform(0, 1, n), 1)
        a[rng.uniform(size=n) < 0.4] = 0.0
        b[rng.uniform(size=n) < 0.4] = 0.0
        if np.ptp(a) == 0 or np.ptp(b) == 0:
            assert np.isnan(AG.spearman(a, b))
        else:
            assert AG.spearman(a, b) == pytest.approx(spearmanr(a, b).statistic, abs=1e-12)
    assert AG.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert AG.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert np.isnan(AG.spearman([1, 2], [2, 1]))           # length < 3
    assert np.isnan(AG.spearman([1, 1, 1], [1, 2, 3]))     # constant
    with pytest.raises(ValueError):
        AG.spearman([1, 2, 3], [1, 2])
    with pytest.raises(ValueError):
        AG.spearman([1, np.nan, 3], [1, 2, 3])


def test_cohen_kappa_hand_computed():
    D, N, I = "driver", "non_driver", "indeterminate"
    a = [D, D, N, N, I, N]
    b = [D, N, N, N, I, I]
    # p_o = 4/6; counts a (D, N, I) = (2, 3, 1), b = (1, 3, 2): p_e = (2 + 9 + 2) / 36 = 13/36 -> (24/36 - 13/36) / (23/36) = 11/23
    assert AG.cohen_kappa(a, b) == pytest.approx(11 / 23)
    assert AG.cohen_kappa([D, N], [N, D]) == pytest.approx(-1.0)   # p_o = 0, p_e = 1/2
    assert AG.cohen_kappa([D, N, I], [D, N, I]) == 1.0
    assert np.isnan(AG.cohen_kappa([N, N, N], [N, N, N]))          # expected agreement 1
    # the same through scores -> bands: 0.7, 0.5 drivers; 0.0, 0.01, 0.04 non-drivers; 0.2 indeterminate
    x = pd.Series([0.7, 0.5, 0.0, 0.01, 0.2, 0.04])
    y = pd.Series([0.9, 0.0, 0.03, 0.0, 0.3, 0.1])
    assert AG.cohen_kappa(AG.bands(x), AG.bands(y)) == pytest.approx(11 / 23)


def test_top30_overlap_ties_broken_by_name():
    """PREREG v4 G6 (e): only non-zero types enter a top list (ties among them by name); |A & B| / max(|A|, |B|)."""
    names = [f"t{i:02d}" for i in range(40)]
    x = pd.Series(0.0, index=names)
    y = pd.Series(0.0, index=names)
    x.iloc[:20] = 1.0 - 0.01 * np.arange(20)       # t00..t19 distinct positive; t20..t39 zero
    y.iloc[20:] = 0.5 + 0.01 * np.arange(20)       # t20..t39 distinct positive; t00..t19 zero
    # zero-score types never enter a list: A = t00..t19, B = t20..t39 -> no overlap (the old name tie-break gave 20/30)
    assert AG.top_overlap(x, y) == 0.0
    assert AG.top_overlap(x, y.iloc[::-1]) == 0.0                         # aligned by type, not by position
    assert np.isnan(AG.top_overlap(pd.Series(0.0, index=names), pd.Series(0.0, index=names[::-1])))  # both empty
    z = pd.Series(0.0, index=names)
    z.iloc[:40] = 1.0                                                     # 40 tied positive: top 30 by name = t00..t29
    w = pd.Series(0.0, index=names)
    w.iloc[10:40] = 2.0                                                   # 30 positive: t10..t39
    assert AG.top_overlap(z, w) == pytest.approx(20 / 30)                 # {t10..t29}
    few = pd.Series([0.9, 0.1, 0.0, 0.3, 0.2], index=list("abcde"))
    assert AG.top_overlap(few, few[::-1] * 0 + 1) == pytest.approx(4 / 5)  # A = {a,b,d,e}, B = all five -> 4 / 5


def test_replication_rate_both_directions_and_nan():
    x = pd.Series([0.6, 0.7, 0.1, 0.55, 0.0], index=list("abcde"))
    y = pd.Series([0.9, 0.2, 0.3, 0.1, 0.0], index=list("abcde"))
    r = AG.replication_rate(x, y)          # drivers x {a, b, d}, y {a}
    assert r["a_to_b"] == pytest.approx(1 / 3) and r["b_to_a"] == 1.0 and r["mean"] == pytest.approx(2 / 3)
    none = pd.Series(0.1, index=list("abcde"))
    r = AG.replication_rate(none, y)
    assert r["a_to_b"] is None and r["b_to_a"] == 0.0 and r["mean"] is None
    json.dumps(r, allow_nan=False)


# ------------------------------------------------------------------------------------------------------------------- G6
def test_identical_screens_are_at_the_ceiling():
    rng = np.random.default_rng(1)
    base = _base(40, rng)
    X = _screen(base, rng, noise=0.08, p_unusable=0.1)
    types = sorted(base)
    out = AG.compare(X, X.copy(), types, H8, n_boot=2000)
    p, b = out["primary"], out["bootstrap"]
    assert p["rho_full"] == pytest.approx(1.0, abs=1e-12)
    assert p["rho_x"] == p["c"] >= 0.2       # the cross pairs are the split pairs; seed noise keeps both below 1
    assert p["ratio"] == 1.0 and b["interval"]["ratio"] == [1.0, 1.0]
    assert out["words"] == "at the ceiling"
    sec = out["secondary"]
    assert sec["kappa"]["full"]["value"] == 1.0
    assert sec["replication"]["full"]["mean"] == 1.0
    assert sec["top30"]["full"]["value"] == 1.0
    assert sec["nonzero"]["full"]["value"] == pytest.approx(1.0)
    assert sec["equal_members"] is None
    json.dumps(out, allow_nan=False)


def test_unrelated_screen_is_a_real_gap():
    rng = np.random.default_rng(2)
    bx = _base(60, rng, p_zero=0.0)
    by = dict(zip(bx, rng.uniform(0, 1, 60)))     # its own stable type effect, unrelated to X's: noise relative to X
    X = _screen(bx, rng, noise=0.05)
    Y = _screen(by, rng, noise=0.05)
    out = AG.compare(X, Y, sorted(bx), H8, n_boot=2000)
    p = out["primary"]
    assert p["c"] > 0.8                             # each screen reproduces itself across seeds
    assert abs(p["rho_x"]) < 0.3 and abs(p["rho_full"]) < 0.3
    assert out["bootstrap"]["interval"]["ratio"][1] < 1.0
    assert out["words"] == "a real gap"


def test_compare_equals_compare_vectors():
    rng = np.random.default_rng(4)
    base = _base(35, rng)
    types = sorted(base)
    X = _screen(base, rng, noise=0.15, p_unusable=0.2)
    Y = _screen({t: float(np.clip(v + rng.normal(0, 0.2), 0, 1)) for t, v in base.items()}, rng, noise=0.15, p_unusable=0.2)
    mc = {t: (1 + i % 3, 1 + i % 2) for i, t in enumerate(types)}
    out = AG.compare(X, Y, types, H8, member_counts=mc, n_boot=500)
    assert out == AG.compare_vectors(*_six(X, Y, types), member_counts=mc, n_boot=500)
    json.dumps(out, allow_nan=False)


def test_secondary_measures_use_the_named_pairs():
    rng = np.random.default_rng(5)
    base = _base(45, rng)
    types = sorted(base)
    X = _screen(base, rng, noise=0.15, p_unusable=0.2)
    Y = _screen({t: float(np.clip(v + rng.normal(0, 0.2), 0, 1)) for t, v in base.items()}, rng, noise=0.15, p_unusable=0.2)
    mc = {t: (1 + i % 3, 1 + i % 2) for i, t in enumerate(types)}
    out = AG.compare(X, Y, types, H8, member_counts=mc, n_boot=200)
    xf, yf, x1, x2, y1, y2 = _six(X, Y, types)
    v = {"X": xf, "Y": yf, "X_h1": x1, "X_h2": x2, "Y_h1": y1, "Y_h2": y2}
    p = out["primary"]
    assert p["rho_full"] == pytest.approx(AG.spearman(xf, yf))
    assert p["rho_x"] == pytest.approx((AG.spearman(x1, y2) + AG.spearman(x2, y1)) / 2)
    assert p["c"] == pytest.approx((AG.spearman(x1, x2) + AG.spearman(y1, y2)) / 2)
    assert p["ratio"] == pytest.approx(p["rho_x"] / p["c"])
    eq = np.array([mc[t][0] == mc[t][1] for t in types])
    assert out["secondary"]["equal_members"]["n_types"] == int(eq.sum())
    forms = {"full": [("X", "Y")], "cross": [("X_h1", "Y_h2"), ("X_h2", "Y_h1")], "split": [("X_h1", "X_h2"), ("Y_h1", "Y_h2")]}
    sec = out["secondary"]
    for form, prs in forms.items():
        nz = []
        for a, b in prs:
            m = ((v[a] > 0) | (v[b] > 0)).to_numpy()
            nz.append(AG.spearman(v[a][m], v[b][m]))
        assert sec["nonzero"][form]["value"] == pytest.approx(np.mean(nz))
        assert sec["equal_members"][form]["value"] == pytest.approx(np.mean([AG.spearman(v[a][eq], v[b][eq]) for a, b in prs]))
        reps = [AG.replication_rate(v[a], v[b]) for a, b in prs]
        for key in ("a_to_b", "b_to_a", "mean"):
            assert sec["replication"][form][key] == pytest.approx(np.mean([r[key] for r in reps]))
        kap = [AG.cohen_kappa(AG.bands(v[a]), AG.bands(v[b])) for a, b in prs]
        assert sec["kappa"][form]["value"] == pytest.approx(np.mean(kap))
        assert sec["top30"][form]["value"] == pytest.approx(np.mean([AG.top_overlap(v[a], v[b]) for a, b in prs]))
        assert [(r["a"], r["b"]) for r in sec["nonzero"][form]["pairs"]] == prs


def _bruteforce(vecs: dict[str, np.ndarray], n_boot: int, seed: int) -> dict:
    """G6's bootstrap written out row by row with the scalar Spearman: positions resampled with default_rng(seed); a resample with a
    NaN Spearman dropped from every interval; one whose ceiling is exactly 0 left out of the ratio interval only."""
    n = len(vecs["X"])
    idx = np.random.default_rng(seed).integers(0, n, size=(n_boot, n))
    kept, ratios, n_const, n_zero = [], [], 0, 0
    for row in idx:
        r = [AG.spearman(vecs[a][row], vecs[b][row]) for a, b in
             (("X", "Y"), ("X_h1", "Y_h2"), ("X_h2", "Y_h1"), ("X_h1", "X_h2"), ("Y_h1", "Y_h2"))]
        if np.isnan(r).any():
            n_const += 1
            continue
        rx, c = (r[1] + r[2]) / 2, (r[3] + r[4]) / 2
        kept.append((r[0], rx, c))
        if c == 0:
            n_zero += 1
        else:
            ratios.append(rx / c)
    K = np.array(kept)
    iv = {k: list(np.percentile(K[:, j], [2.5, 97.5])) for j, k in enumerate(("rho_full", "rho_x", "c"))}
    iv["ratio"] = list(np.percentile(ratios, [2.5, 97.5]))
    return {"n_const": n_const, "n_zero": n_zero, "interval": iv}


@pytest.mark.parametrize("n_types", [4, 8])
def test_bootstrap_matches_row_by_row_definition(n_types):
    rng = np.random.default_rng(10 + n_types)
    types = [f"T{i}" for i in range(n_types)]

    def tie_heavy():
        v = np.round(rng.uniform(0, 1, n_types), 1)
        v[rng.uniform(size=n_types) < 0.5] = 0.0
        v[:2] = (0.0, 0.8)  # never constant on the full type set
        return pd.Series(v, index=types)

    s = {k: tie_heavy() for k in ("X", "Y", "X_h1", "X_h2", "Y_h1", "Y_h2")}
    n_boot, seed = 300, 77
    out = AG.compare_vectors(s["X"], s["Y"], s["X_h1"], s["X_h2"], s["Y_h1"], s["Y_h2"], n_boot=n_boot, seed=seed)
    ref = _bruteforce({k: v.to_numpy() for k, v in s.items()}, n_boot, seed)
    b = out["bootstrap"]
    assert b["n_dropped"] == ref["n_const"] > 0
    assert b["n_used"] == n_boot - ref["n_const"]
    assert b["n_ratio_zero_ceiling"] == ref["n_zero"]
    for k, iv in ref["interval"].items():
        assert b["interval"][k] == pytest.approx(iv, abs=1e-12)


def test_zero_ceiling_resamples_leave_out_only_the_ratio():
    types = list("abcde")
    up = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5], index=types)
    down = pd.Series(up.to_numpy()[::-1], index=types)
    # rho(x1, x2) = 1 and rho(y1, y2) = -1 on every non-constant resample: c = 0, so only the ratio is undefined
    out = AG.compare_vectors(up, up, up, up, up, down, n_boot=500)
    b = out["bootstrap"]
    assert out["primary"]["c"] == 0.0 and out["primary"]["ratio"] is None and out["words"] == "not judged"
    assert b["n_ratio_zero_ceiling"] == b["n_used"] > 0 and b["n_used"] + b["n_dropped"] == 500
    assert b["interval"]["ratio"] == [None, None]
    assert b["interval"]["c"] == [0.0, 0.0] and b["interval"]["rho_x"] == [0.0, 0.0] and b["interval"]["rho_full"] == [1.0, 1.0]
    json.dumps(out, allow_nan=False)


def test_bootstrap_does_not_depend_on_the_chunk_size(monkeypatch):
    rng = np.random.default_rng(12)
    base = _base(25, rng)
    types = sorted(base)
    Y = _screen(base, rng, noise=0.2, p_unusable=0.1)
    Xb = _screen({t: float(np.clip(0.5 * v + 0.5 * rng.uniform(), 0, 1)) for t, v in base.items()}, rng, noise=0.2)
    Xa = _screen({t: float(np.clip(v + rng.normal(0, 0.1), 0, 1)) for t, v in base.items()}, rng, noise=0.2)
    one_chunk = AG.compare(Xb, Y, types, H8, n_boot=1500), AG.closure(Xb, Xa, Y, types, H8, n_boot=1500)
    monkeypatch.setattr(AG, "_CHUNK", 37)   # 1500 resamples in 41 chunks, the last one partial
    assert (AG.compare(Xb, Y, types, H8, n_boot=1500), AG.closure(Xb, Xa, Y, types, H8, n_boot=1500)) == one_chunk


def test_bootstrap_is_deterministic_and_seeded():
    rng = np.random.default_rng(6)
    base = _base(30, rng)
    types = sorted(base)
    X = _screen(base, rng, noise=0.2)
    Y = _screen(base, rng, noise=0.3)
    a = AG.compare(X, Y, types, H8, n_boot=1000)
    assert a == AG.compare(X, Y, types, H8, n_boot=1000)
    c = AG.compare(X, Y, types, H8, n_boot=1000, seed=1)
    assert c["primary"] == a["primary"] and c["bootstrap"]["interval"] != a["bootstrap"]["interval"]
    assert a["bootstrap"]["seed"] == 20261401 == AG.BOOT_SEED
    for f in (AG.compare, AG.compare_vectors, AG.closure, AG.closure_vectors):
        params = inspect.signature(f).parameters
        assert params["seed"].default == 20261401 and params["n_boot"].default == 10_000


def test_compare_is_strict():
    rng = np.random.default_rng(7)
    base = _base(10, rng)
    types = sorted(base)
    X = _screen(base, rng, noise=0.1)
    with pytest.raises(ValueError, match="do not occur"):
        AG.compare(X, X[X["seed"] < 8], types, H8)                     # Y lacks the second half
    with pytest.raises(ValueError, match="overlap"):
        AG.compare(X, X, types, ([0, 1, 2], [2, 3]))
    with pytest.raises(ValueError, match="no replicate"):
        AG.compare(X, X, [*types, "DNzz"], H8)
    with pytest.raises(ValueError, match="duplicated type"):
        AG.compare(X, X, [*types, types[0]], H8)
    holed = X[~((X["type"] == types[0]) & (X["seed"] >= 8))]
    with pytest.raises(ValueError, match="no replicate"):
        AG.compare(holed, X, types, H8)                                  # a type without rows in one half
    with pytest.raises(ValueError, match="member_counts"):
        AG.compare(X, X, types, H8, member_counts={types[0]: (1, 1)})
    with pytest.raises(ValueError, match="n_boot"):
        AG.compare(X, X, types, H8, n_boot=0)
    with pytest.raises(TypeError):
        AG.compare(X, X, "DNt00", H8)
    six = _six(X, X, types)
    with pytest.raises(ValueError, match="same order"):
        AG.compare_vectors(six[0], six[1].iloc[::-1], *six[2:])
    with pytest.raises(ValueError, match="same order"):
        AG.compare_vectors(six[0], six[1].iloc[1:], *six[2:])
    with pytest.raises(TypeError):
        AG.compare_vectors(six[0], six[1].to_numpy(), *six[2:])


# ------------------------------------------------------------------------------------------------------------------- G7
def test_words_rule():
    assert AG.words(0.95, [0.8, 1.0], 0.5) == "at the ceiling"
    assert AG.words(0.90, [0.7, 1.3], 0.2) == "at the ceiling"
    assert AG.words(0.95, [0.8, 0.99], 0.5) == "a real gap"
    assert AG.words(0.89, [0.7, 1.1], 0.5) == "a real gap"
    assert AG.words(0.95, [0.8, 1.2], 0.19) == "not judged"     # ceiling too low, whatever the ratio
    assert AG.words(None, [None, None], 0.5) == "not judged"
    assert AG.words(0.95, [None, None], 0.5) == "not judged"    # no interval: the rule cannot be applied
    assert AG.words(0.95, [0.8, 1.2], None) == "not judged"


def _ranked(types, ranks) -> pd.DataFrame:
    return _flat(dict(zip(types, np.asarray(ranks, float) / 10)))


def test_closure_known_answer():
    types = [f"T{i}" for i in range(10)]
    Y = _ranked(types, range(1, 11))
    before = _ranked(types, [6, 5, 4, 3, 2, 1, 7, 8, 9, 10])   # sum d^2 = 70 -> rho = 1 - 6 * 70 / 990
    after = _ranked(types, [2, 1, 3, 4, 5, 6, 7, 8, 9, 10])    # sum d^2 = 2
    out = AG.closure(before, after, Y, types, H8, n_boot=2000)
    rb, ra = 1 - 6 * 70 / 990, 1 - 6 * 2 / 990
    # no seed noise: each half equals the full-seed vector, so c = 1 and rho_x = rho_full
    assert out["before"]["primary"]["c"] == pytest.approx(1.0) and out["after"]["primary"]["c"] == pytest.approx(1.0)
    assert out["before"]["primary"]["rho_x"] == pytest.approx(rb)
    assert out["after"]["primary"]["rho_x"] == pytest.approx(ra)
    assert out["closure"] == pytest.approx((ra - rb) / (1 - rb)) and out["closure"] == pytest.approx(68 / 70)
    assert out["after_ratio_vs_before_ceiling"] == pytest.approx(ra)
    assert out["before"]["words"] == "a real gap" and out["reported"] is True
    cb = out["closure_bootstrap"]
    assert cb["n_used"] + cb["n_dropped"] + cb["n_zero_denominator"] == 2000 and cb["n_used"] > 1900
    lo, hi = out["closure_interval"]
    assert lo <= hi <= 1.0 + 1e-12
    assert out["y_changed"] is False
    json.dumps(out, allow_nan=False)
    # an intervention that changes both screens: the after pair (before, before) agrees perfectly -> closure 1
    both = AG.closure(before, before, Y, types, H8, n_boot=500, Y_after=before)
    assert both["closure"] == pytest.approx(1.0) and both["closes_whole_gap"] is True and both["y_changed"] is True


def test_closure_not_reported_unless_before_is_a_real_gap():
    types = [f"T{i}" for i in range(10)]
    Y = _ranked(types, range(1, 11))
    after = _ranked(types, [2, 1, 3, 4, 5, 6, 7, 8, 9, 10])
    at_ceiling = AG.closure(Y, after, Y, types, H8, n_boot=500)   # before = Y: rho_x = c, so the closure is 0/0
    assert at_ceiling["before"]["words"] == "at the ceiling"
    assert at_ceiling["reported"] is False and at_ceiling["closure"] is None
    json.dumps(at_ceiling, allow_nan=False)
    rng = np.random.default_rng(8)
    flat = {t: 0.5 for t in types}
    noise_x, noise_y = _screen(flat, rng, noise=0.3), _screen(flat, rng, noise=0.3)   # no type effect: c near 0
    nj = AG.closure(noise_x, after, noise_y, types, H8, n_boot=500)
    assert nj["before"]["primary"]["c"] < 0.2 and nj["before"]["words"] == "not judged" and nj["reported"] is False


def test_closure_pairs_equal_compare_and_closure_vectors():
    rng = np.random.default_rng(9)
    base = _base(30, rng)
    types = sorted(base)
    Y = _screen(base, rng, noise=0.1)
    Xb = _screen({t: float(np.clip(0.4 * v + 0.6 * rng.uniform(), 0, 1)) for t, v in base.items()}, rng, noise=0.1)
    Xa = _screen({t: float(np.clip(0.8 * v + 0.2 * rng.uniform(), 0, 1)) for t, v in base.items()}, rng, noise=0.1)
    out = AG.closure(Xb, Xa, Y, types, H8, n_boot=1000)
    cb, ca = AG.compare(Xb, Y, types, H8, n_boot=1000), AG.compare(Xa, Y, types, H8, n_boot=1000)
    for k in ("primary", "bootstrap", "words"):
        assert out["before"][k] == cb[k] and out["after"][k] == ca[k]
    xb, _, xb1, xb2, y1, y2 = _six(Xb, Y, types)
    xa, yf, xa1, xa2, _, _ = _six(Xa, Y, types)
    assert out == AG.closure_vectors(xb, xb1, xb2, xa, xa1, xa2, yf, y1, y2, n_boot=1000)
    with pytest.raises(ValueError, match="all three"):
        AG.closure_vectors(xb, xb1, xb2, xa, xa1, xa2, yf, y1, y2, ya_full=yf)


def test_paired_agreement_uses_only_the_given_seeds():
    types = [f"T{i}" for i in range(12)]
    sc = np.linspace(0.0, 1.0, 12)
    X = pd.concat([_flat(dict(zip(types, sc)), seeds=range(8)), _flat(dict(zip(types, sc[::-1])), seeds=range(8, 16))])
    Y = _flat(dict(zip(types, sc ** 2)), seeds=range(8))     # monotone in X's first eight seeds
    assert AG.paired_agreement(X, Y, types, range(8)) == pytest.approx(1.0)
    Yr = _flat(dict(zip(types, sc[::-1])), seeds=range(8))
    assert AG.paired_agreement(X, Yr, types, range(8)) == pytest.approx(-1.0)
    with pytest.raises(ValueError, match="do not occur"):
        AG.paired_agreement(X, Y, types, range(16))             # Y has seeds 0..7 only
    pc = AG.paired_closure(X, X, Yr, types, range(8), r_ref=1.0, Y_after=Y)
    assert pc["rho_p_before"] == pytest.approx(-1.0) and pc["rho_p_after"] == pytest.approx(1.0)
    assert pc["closure_p"] == pytest.approx(1.0)                # (1 - (-1)) / (1 - (-1))
    json.dumps(pc, allow_nan=False)
