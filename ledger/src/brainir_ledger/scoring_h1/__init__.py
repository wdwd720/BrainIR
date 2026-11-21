"""Exam 2 scoring (PREREG v3 Part S): identification of hemilineages from predicted motor phenotypes.

Pure functions on tables; the pipeline (`pipeline_h1.run`) adds the flag, the lock checks and the file reading. Written and tested
on synthetic data before the rulebook freeze (RUN3_PROMPT section 5, "Scoring code")."""

from __future__ import annotations

import numpy as np
import pandas as pd

DIMS = ["d1", "d2", "d3", "d4", "d5", "d6", "d7p", "d10", "d11", "d13", "d14", "d15"]  # PREREG v3 V2
ALL_DIMS = [f"d{i}" for i in range(1, 16)] + ["d7p"]
SEEDS = {"perm": 20261301, "boot": 20261302, "paired": 20261303}
TIE = 1e-12


class BlindErrorH1(RuntimeError):
    """Refusal: nothing computed, nothing written."""


def derive_d7p(row: pd.Series) -> str:
    """PREREG v3 V2: repeated leg movement, coordinated or not."""
    a, b = row.get("d7"), row.get("d8")
    if "yes" in (a, b):
        return "yes"
    if a == "no" and b == "no":
        return "no"
    if "unclear" in (a, b):
        return "unclear"
    return "not_assessed"


def standardise(P: pd.DataFrame) -> pd.DataFrame:
    """Each predicted column standardised across units (mean 0, sd 1, population sd); a constant column becomes 0."""
    Z = P[DIMS].astype(float)
    mu, sd = Z.mean(axis=0), Z.std(axis=0, ddof=0)
    Z = (Z - mu) / sd.where(sd > 0)
    return Z.fillna(0.0)


def observed(cons: pd.DataFrame) -> pd.DataFrame:
    """yes -> 1, no -> 0, anything else -> NaN (not coded)."""
    O = cons[DIMS].copy()
    for c in DIMS:
        O[c] = cons[c].map({"yes": 1.0, "no": 0.0})
    return O.astype(float)


def centre(O: pd.DataFrame) -> pd.DataFrame:
    """Each observed column centred over the units where it is coded (PREREG v3 S1)."""
    return O - O.mean(axis=0)


def _ranks(S: np.ndarray, true_col: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Percentile rank and rank position of the true candidate in each row of S (rows = labelled units, cols = candidates)."""
    t = S[np.arange(S.shape[0]), true_col][:, None]
    gt = (S > t + TIE).sum(1)
    lt = (S < t - TIE).sum(1)
    eq = S.shape[1] - gt - lt - 1  # ties other than the true candidate itself
    pr = (lt + 0.5 * eq) / (S.shape[1] - 1)
    pos = 1 + gt + 0.5 * eq
    return pr, pos


def identification(Z: pd.DataFrame, O: pd.DataFrame, *, min_coded: int = 3) -> dict:
    """PREREG v3 S2. Z: candidates x DIMS (standardised predictions, all units). O: units x DIMS observed (1/0/NaN)."""
    Oc = centre(O)
    coded = O.notna().sum(axis=1)
    H = [h for h in O.index if coded[h] >= min_coded and h in Z.index]
    if not H:
        return {"n": 0, "units": [], "mean_pr": None}
    A = Oc.loc[H, DIMS].fillna(0.0).to_numpy()  # uncoded dims contribute nothing
    S = A @ Z[DIMS].to_numpy().T
    true_col = np.array([Z.index.get_loc(h) for h in H])
    pr, pos = _ranks(S, true_col)
    return {"n": len(H), "units": H, "pr": dict(zip(H, pr.tolist())), "pos": dict(zip(H, pos.tolist())),
            "mean_pr": float(pr.mean()), "top1": float((pos <= 1).mean()), "top3": float((pos <= 3).mean()),
            "_S": S, "_true": true_col}


def permutation_null(res: dict, *, n_perm: int = 10_000, seed: int = SEEDS["perm"]) -> dict:
    """PREREG v3 S2: observed rows permuted among the labelled units (candidates unchanged). Returns the one-sided p of the mean
    percentile rank and the null distribution's mean and 2.5-97.5 % range for the mean rank, top-1 and top-3 ("chance")."""
    S, true_col = res["_S"], res["_true"]
    obs = res["mean_pr"]
    rng = np.random.default_rng(seed)
    ge, m, t1, t3 = 0, np.empty(n_perm), np.empty(n_perm), np.empty(n_perm)
    for i in range(n_perm):
        perm = rng.permutation(S.shape[0])
        pr, pos = _ranks(S[perm], true_col)
        m[i], t1[i], t3[i] = pr.mean(), (pos <= 1).mean(), (pos <= 3).mean()
        ge += m[i] >= obs - TIE
    band = lambda x: {"mean": float(x.mean()), "lo": float(np.percentile(x, 2.5)), "hi": float(np.percentile(x, 97.5))}  # noqa: E731
    return {"p": (1 + ge) / (n_perm + 1), "null_mean_pr": band(m), "null_top1": band(t1), "null_top3": band(t3), "n_perm": n_perm,
            "seed": seed}


def permutation_p(res: dict, *, n_perm: int = 10_000, seed: int = SEEDS["perm"]) -> float:
    return permutation_null(res, n_perm=n_perm, seed=seed)["p"]


def bootstrap_ci(values, *, n_boot: int = 10_000, seed: int = SEEDS["boot"]) -> dict:
    v = np.asarray(list(values), float)
    rng = np.random.default_rng(seed)
    means = np.array([v[rng.integers(0, len(v), len(v))].mean() for _ in range(n_boot)])
    return {"lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5)), "n_boot": n_boot, "seed": seed}


def paired_bootstrap(pr_a: dict, pr_b: dict, *, n_boot: int = 10_000, seed: int = SEEDS["paired"]) -> dict:
    units = sorted(set(pr_a) & set(pr_b))
    a = np.array([pr_a[u] for u in units])
    b = np.array([pr_b[u] for u in units])
    rng = np.random.default_rng(seed)
    d = np.array([(a[i] - b[i]).mean() for i in (rng.integers(0, len(units), len(units)) for _ in range(n_boot))])
    return {"n": len(units), "diff": float((a - b).mean()), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)),
            "n_boot": n_boot, "seed": seed}


def decide(res: dict, p: float, ci: dict, n_units_ge3: int, value_vs_wiring: dict | None, null_mean: float = 0.5) -> dict:
    """PREREG v3 S3: "predicts" needs p < 0.05 and the interval's lower bound above both 0.5 and the permutation-null mean;
    "adds value beyond wiring" additionally needs "predicts" and the paired interval above 0."""
    under = n_units_ge3 < 20
    predicts = bool((not under) and p < 0.05 and ci["lo"] > max(0.5, null_mean))
    above = bool(value_vs_wiring is not None and value_vs_wiring["lo"] > 0)
    return {"underpowered": bool(under), "model_predicts": predicts, "adds_value_beyond_wiring": bool(predicts and above),
            "hm_ranks_above_best_wiring_descriptive": above}


def lab_as_prediction(O_lab: pd.DataFrame, units: list[str]) -> pd.DataFrame:
    """Ceiling (S4.1): a lab's matrix as predictions over all units: missing -> the column mean, then standardised."""
    P = O_lab.reindex(units)[DIMS].astype(float)
    P = P.fillna(P.mean(axis=0)).fillna(0.0)
    return standardise(P)


def auroc(scores, labels) -> float | None:
    s, y = np.asarray(scores, float), np.asarray(labels, int)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def per_dim_auroc(Z: pd.DataFrame, O: pd.DataFrame) -> dict:
    out, cells_s, cells_y = {}, [], []
    for d in DIMS:
        m = O[d].notna() & O.index.isin(Z.index)
        units = O.index[m]
        s, y = Z.loc[units, d].to_numpy(), O.loc[units, d].to_numpy()
        out[d] = {"n": int(m.sum()), "n_yes": int((y == 1).sum()), "auroc": auroc(s, y)}
        cells_s += list(s)
        cells_y += list(y)
    out["pooled"] = {"n": len(cells_y), "auroc": auroc(cells_s, cells_y)}
    return out
