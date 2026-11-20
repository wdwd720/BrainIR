"""Prediction tables (PREREG section 11): aggregation of per-replicate results into types.csv / replicates.parquet / legs.csv.

Prediction side only: nothing here reads labels.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

TYPES_COLUMNS = ["arm", "network", "manc_type", "n_members", "member_ids", "n_replicates", "n_usable", "mean_score", "median_score",
                 "frac_ge_0_5", "best_score", "median_freq_hz", "median_current", "median_n_active_readout", "status", "band",
                 "primary_score"]
DRIVER, NON_DRIVER = 0.5, 0.05


def band(score: float) -> str:
    if score >= DRIVER:
        return "driver"
    if score < NON_DRIVER:
        return "non_driver"
    return "indeterminate"


def status_from(n_usable: int, n_weak: int, n_strong: int) -> str:
    if n_usable > 0:
        return "ok"
    return "never_usable_weak" if n_weak >= n_strong else "never_usable_strong"


def type_row(arm: str, network: str, manc_type: str, member_ids: Iterable[int], reps: list[dict]) -> dict:
    """``reps``: one dict per replicate with keys usable (bool), score, frequency_hz, current, n_active_readout, final (weak/strong
    for unusable replicates)."""
    member_ids = [int(x) for x in member_ids]
    use = [r for r in reps if r["usable"]]
    sc = np.array([r["score"] for r in use], float)
    n_weak = sum(1 for r in reps if not r["usable"] and r.get("final") == "weak")
    n_strong = sum(1 for r in reps if not r["usable"] and r.get("final") != "weak")
    st = status_from(len(use), n_weak, n_strong)
    mean = float(sc.mean()) if len(sc) else None
    rhythmic_f = [r["frequency_hz"] for r in use if r["score"] >= 0.5 and r.get("frequency_hz")]
    primary = mean if mean is not None else 0.0
    return {"arm": arm, "network": network, "manc_type": manc_type, "n_members": len(member_ids),
            "member_ids": ";".join(str(i) for i in member_ids), "n_replicates": len(reps), "n_usable": len(use),
            "mean_score": mean, "median_score": float(np.median(sc)) if len(sc) else None,
            "frac_ge_0_5": float((sc >= 0.5).mean()) if len(sc) else None, "best_score": float(sc.max()) if len(sc) else None,
            "median_freq_hz": float(np.median(rhythmic_f)) if rhythmic_f else None,
            "median_current": float(np.median([r["current"] for r in use])) if use else None,
            "median_n_active_readout": float(np.median([r["n_active_readout"] for r in use])) if use else None,
            "status": st, "band": band(primary), "primary_score": primary}


def write_csv(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", float_format="%.10g")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_parquet(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, compression="zstd")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(obj, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finish_types(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    cols = TYPES_COLUMNS + [c for c in df.columns if c not in TYPES_COLUMNS]
    return df[cols].sort_values("manc_type").reset_index(drop=True)
