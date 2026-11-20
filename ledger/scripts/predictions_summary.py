"""Predictions-only summary (PREDICTION SIDE: never reads labels) -> research/ledger/predictions/SUMMARY.json.

Per arm: number of types, usable types, predicted drivers / indeterminate / non-drivers (band of the primary score; B4: its
categorical calls at strength 128). Agreement between the authors' screen and BrainIR's (A1 vs B1, A0 vs B0) and between the
two animals (B2 MaleCNS vs B1 MANC, on the MANC types present in both).

    uv run --project ledger --no-sync python ledger/scripts/predictions_summary.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import PREDICTIONS  # noqa: E402
from brainir_ledger.scoring.stats import spearman  # noqa: E402


def load(arm: str) -> pd.DataFrame | None:
    p = PREDICTIONS / arm / "types.csv"
    return pd.read_csv(p).set_index("manc_type") if p.exists() else None


def agree(a: pd.DataFrame, b: pd.DataFrame, col_a: str = "primary_score", col_b: str = "primary_score") -> dict:
    common = a.index.intersection(b.index)
    x = pd.to_numeric(a.loc[common, col_a], errors="coerce").fillna(0.0)
    y = pd.to_numeric(b.loc[common, col_b], errors="coerce").fillna(0.0)
    top_a = set(x.sort_values(ascending=False).index[:10])
    top_b = set(y.sort_values(ascending=False).index[:10])
    out = {"n_common_types": int(len(common)), "spearman": spearman(x, y), "top10_overlap": len(top_a & top_b)}
    if "band" in a and "band" in b and a["band"].notna().all() and b["band"].notna().all():
        out["band_agreement"] = float((a.loc[common, "band"] == b.loc[common, "band"]).mean())
        out["band_crosstab"] = pd.crosstab(a.loc[common, "band"], b.loc[common, "band"]).to_dict()
    return out


def main() -> None:
    arms = sorted(p.name for p in PREDICTIONS.iterdir() if p.is_dir() and (p / "types.csv").exists())
    per_arm = {}
    for arm in arms:
        t = load(arm)
        row = {"n_types": int(len(t))}
        if "status" in t:
            row["n_usable_types"] = int((t["status"] == "ok").sum()) if arm not in ("B4", "B5", "S") else None
            row["n_never_usable"] = int((t["status"] != "ok").sum()) if arm not in ("B4", "B5", "S") else None
        if "band" in t and t["band"].notna().any():
            vc = t["band"].value_counts()
            row.update(n_driver=int(vc.get("driver", 0)), n_indeterminate=int(vc.get("indeterminate", 0)),
                       n_non_driver=int(vc.get("non_driver", 0)))
        if arm == "B4":
            row["calls_128"] = {k: int(v) for k, v in t["call_128"].value_counts().items()}
            row["calls_by_strength"] = {c: {k: int(v) for k, v in t[c].value_counts().items()} for c in t.columns if c.startswith("call_")}
            row["n_base_rhythmic"] = sorted({int(v) for c in t.columns if c.startswith("n_base_rhythmic_") for v in t[c].dropna()})
        if arm == "S":
            row["columns"] = [c for c in t.columns if c.startswith("S")]
        per_arm[arm] = row
    a1, b1 = load("A1"), load("B1")
    out = {"per_arm": per_arm, "agreement": {}}
    if a1 is not None and b1 is not None:
        out["agreement"]["authors_vs_brainir_type_level (A1 vs B1)"] = agree(a1, b1)
    if a1 is not None and load("B1-alt") is not None:
        out["agreement"]["A1 vs B1-alt"] = agree(a1, load("B1-alt"))
    a0, b0 = load("A0"), load("B0")
    if a0 is not None and b0 is not None:
        out["agreement"]["authors_vs_brainir_single_neuron (A0 vs B0, per-type max)"] = agree(a0, b0, "type_max", "type_max")
    b2 = load("B2")
    if b2 is not None and b1 is not None:
        out["agreement"]["two_animals (B2 MaleCNS vs B1 MANC)"] = agree(b1, b2)
        out["agreement"]["two_animals (B2 MaleCNS vs B1 MANC)"]["n_b2_groups"] = int(len(b2))
        out["agreement"]["two_animals (B2 MaleCNS vs B1 MANC)"]["n_b2_groups_not_in_B1"] = int(len(b2.index.difference(b1.index)))
    if b2 is not None and a1 is not None:
        out["agreement"]["B2 MaleCNS vs A1 (authors, MANC)"] = agree(a1, b2)
    ctl = [a for a in arms if a.startswith("B1-ctl-")]
    if ctl and b1 is not None:
        out["agreement"]["B1 vs each control"] = {c: agree(b1, load(c)) for c in ctl}
    p = PREDICTIONS / "SUMMARY.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    for arm, r in per_arm.items():
        print(arm, {k: v for k, v in r.items() if k not in ("calls_by_strength", "columns")})
    for k, v in out["agreement"].items():
        if isinstance(v, dict) and "spearman" in v:
            print(k, {kk: vv for kk, vv in v.items() if kk != "band_crosstab"})


if __name__ == "__main__":
    main()
