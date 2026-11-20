"""Pre-lock arm diagnostics (PREDICTION SIDE: never reads labels; DNg100 is the only type examined by name).

Computes every number quoted in research/ledger/gates/ARM_DIAGNOSTICS.md and freezes two per-type descriptions before the
predictions lock, so that run 2 cannot choose them after seeing labels:
  gates/B4_halts_split.csv   - per type called `halts` at 128: do the rhythm-losing replicates have fewer active front-leg
                               MNs than their paired background run (median difference < 0), or the same or more?
  gates/B2_mapping_split.csv - per B2 group: every MaleCNS member has a curated body match and no conflicting `mancType`
                               string ("clean"), or not.
Writes gates/ARM_DIAGNOSTICS.json.

    uv run --project ledger --no-sync python ledger/scripts/arm_diagnostics.py
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import PREDICTIONS, data_dir  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402
from brainir_ledger.scoring.stats import spearman  # noqa: E402

GATES = PREDICTIONS.parent / "gates"


def tab(arm: str) -> pd.DataFrame:
    return pd.read_csv(PREDICTIONS / arm / "types.csv").set_index("manc_type")


def reps(arm: str) -> pd.DataFrame:
    return pd.read_parquet(PREDICTIONS / arm / "replicates.parquet")


def b2_section() -> dict:
    out: dict = {}
    b1, b2, a1 = tab("B1"), tab("B2"), tab("A1")
    r2 = reps("B2")
    d = r2[r2.manc_type == "DNg100"]
    out["DNg100"] = {"B2_primary_score": float(b2.loc["DNg100", "primary_score"]), "B1_primary_score": float(b1.loc["DNg100", "primary_score"]),
                     "A1_primary_score": float(a1.loc["DNg100", "primary_score"]), "n_replicates": int(len(d)),
                     "n_usable": int(d.usable.sum()), "currents": sorted({float(x) for x in d.current}),
                     "n_tuning_runs": sorted({int(x) for x in d.n_tuning_runs}),
                     "n_with_le1_active_readout": int((d.n_active_readout <= 1).sum()),
                     "n_active_all_range_of_those": [int(d[d.n_active_readout <= 1].n_active_all.min()), int(d[d.n_active_readout <= 1].n_active_all.max())]}
    acc = {}
    for arm in ("B1", "B2"):
        u = reps(arm)
        u = u[u.usable]
        acc[arm] = {"usable_replicates": int(len(u)), "frac_zero_active_readout": float((u.n_active_readout == 0).mean()),
                    "frac_accepted_at_start_current_128": float((u.current == 128).mean())}
    out["acceptance"] = acc
    # mapping split per B2 group
    net, groups, _ = AR.malecns_network()
    from brainir import paths
    import pyarrow.feather as feather
    ann = feather.read_table(glob.glob(str(paths.data_root() / "raw" / "external" / "malecns_v1.0_body_annotations" / "*.feather"))[0]) \
        .to_pandas().set_index("bodyId")
    rows = []
    for t, mem in sorted(groups.items()):
        clean = True
        for m in mem:
            bid = int(net.table.loc[m, "bodyId"])
            a = ann.loc[bid] if bid in ann.index else None
            if a is None or pd.isna(a.get("mancBodyid")) or (pd.notna(a.get("mancType")) and str(a["mancType"]) != t):
                clean = False
        rows.append({"manc_type": t, "n_members": len(mem), "mapping": "clean" if clean else "fallback_or_conflict", "in_B1": t in b1.index})
    split = pd.DataFrame(rows)
    split.to_csv(GATES / "B2_mapping_split.csv", index=False, lineterminator="\n")
    common = b1.index.intersection(b2.index)
    agree = {"all": {"n": int(len(common)), "spearman_B1_B2": spearman(b1.loc[common, "primary_score"], b2.loc[common, "primary_score"])}}
    for kind in ("clean", "fallback_or_conflict"):
        s = [t for t in split.loc[split.mapping == kind, "manc_type"] if t in common]
        agree[kind] = {"n": len(s), "spearman_B1_B2": spearman(b1.loc[s, "primary_score"], b2.loc[s, "primary_score"]),
                       "spearman_A1_B2": spearman(a1.loc[s, "primary_score"], b2.loc[s, "primary_score"])}
    out["agreement_by_mapping"] = agree
    return out


def b4_section() -> dict:
    t = tab("B4")
    rep = reps("B4")
    bg = rep[rep.manc_type == "__background__"].set_index("seed")
    tr = rep[(rep.current == 128) & (rep.manc_type != "__background__")]
    rows, n_lost = [], 0
    for ty in t.index[t.call_128 == "halts"]:
        d = tr[tr.manc_type == ty].set_index("seed")
        base_ok = bg.index[bg.score >= 0.5]
        lost = d.loc[[s for s in d.index if s in base_ok and d.loc[s, "score"] < 0.5]]
        n_lost += len(lost)
        diff = float((lost.n_active_readout - bg.loc[lost.index, "n_active_readout"]).median())
        rows.append({"manc_type": ty, "n_rhythm_lost": int(len(lost)), "median_delta_active_readout_vs_background": diff,
                     "halt_kind": "fewer_active_MNs_than_background" if diff < 0 else "same_or_more_active_MNs"})
    split = pd.DataFrame(rows)
    split.to_csv(GATES / "B4_halts_split.csv", index=False, lineterminator="\n")
    # verdict bounds of the rhythm-losing replicates, from the job results (they carry n_active_all and n_high_fr)
    res = {r["key"]: r for r in read_log(data_dir() / "arms" / "B4" / "results.pkl") if "error" not in r}
    lost_keys = []
    for ty in split.manc_type:
        for s in AR.SEEDS:
            if bg.loc[s, "score"] >= 0.5:
                r = res[f"B4|{ty}|I128|s{s}"]
                if r["score"] < 0.5:
                    lost_keys.append(r)
    stock_strong = sum(1 for r in lost_keys if r["verdict"] == "strong")
    b1_strong = sum(1 for r in lost_keys if r["n_active_all"] > 1500 or r["n_high_fr"] > 200)
    over_1500 = sum(1 for r in lost_keys if r["n_active_all"] > 1500)
    return {"background_rhythmic_seeds": int((bg.score >= 0.5).sum()), "calls_128": {k: int(v) for k, v in t.call_128.value_counts().items()},
            "halts_split": {k: int(v) for k, v in split.halt_kind.value_counts().items()}, "n_rhythm_losing_replicates": int(n_lost),
            "n_lost_verdict_strong_under_B4_stock_bounds": stock_strong,
            "stock_bounds": "ScreenConfig(): n_active_lower 5, n_active_upper 1500, n_high_fr_upper 100",
            "n_lost_beyond_B1_bounds (active > 1500 or high-firing > 200)": b1_strong, "n_lost_active_over_1500": over_1500,
            "DNg100": {c: t.loc["DNg100", c] for c in t.columns if c.startswith(("call_", "frac_halt_"))}}


def b5_section() -> dict:
    t = tab("B5")
    return {"DNg100_per_strength": {c: float(t.loc["DNg100", c]) for c in sorted(t.columns) if c.startswith("score_I")}}


def main() -> None:
    out = {"B2": b2_section(), "B4": b4_section(), "B5": b5_section()}
    (GATES / "ARM_DIAGNOSTICS.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
