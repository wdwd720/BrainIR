"""Referee test 2: what do exam 1's labels encode?

Inputs (locked): results/run2/scorecard.csv (primary set, labels, sources, preparation), predictions/S/types.csv (wiring
baselines), predictions/A1/types.csv, predictions_v2/{B1r,B2r}/types.csv, labels_v2/records.jsonl (exam 1 final records),
labels_audit_v1/ERROR_RATES.json (types whose exam 1 label the consensus tiers decide).
Questions:
 (a) how the two classes split by source (atlas only vs other papers) and preparation;
 (b) AUROC of the source indicator itself, of every wiring baseline and of the screens, overall and within strata;
 (c) whether two-step signed counting wins through its magnitude (no-types having large negative values) rather than through
     positive paths to the motor neurons;
 (d) how many labels, per class, the tie-break tiers decide, and how many 'no' types also carry eligible 'yes' records.
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t2_exam1_labels.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")
ATLAS = "10.7554/elife.34275"


def auroc(score: pd.Series, y: pd.Series) -> float:
    ok = score.notna()  # types absent from a screen (e.g. not in MaleCNS) are dropped, as the frozen scorer does
    score, y = score[ok], y[ok]
    pos, neg = score[y == 1].to_numpy(float), score[y == 0].to_numpy(float)
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return round(float((gt + 0.5 * eq) / (len(pos) * len(neg))), 3)


def main() -> None:
    sc = pd.read_csv(ROOT / "results/run2/scorecard.csv")
    ps = sc[sc["in_primary_set"]].copy().set_index("manc_type")
    ps["y"] = (ps["front"] == "yes").astype(int)
    ps["atlas_only"] = ps["sources"].fillna("").apply(lambda s: set(x.strip() for x in s.split(";")) == {ATLAS})
    ps["headless"] = ps["best_preparation"] == "headless"
    S = pd.read_csv(ROOT / "predictions/S/types.csv").set_index("manc_type")
    base = ["S1_direct_mn", "S2_twohop_signed", "S3_twohop_abs", "S4_total_out", "S5_out_partners", "S6_premotor", "S7_n_members"]
    for b in base:
        ps[b] = S.loc[ps.index, b].astype(float)
    for arm, sub in (("A1", "predictions"), ("B1r", "predictions_v2"), ("B2r", "predictions_v2")):
        t = pd.read_csv(ROOT / sub / arm / "types.csv").set_index("manc_type")["primary_score"].astype(float).fillna(0.0)
        ps[arm] = t.reindex(ps.index)
    er = json.loads((ROOT / "labels_audit_v1/ERROR_RATES.json").read_text())
    tiers = {r["manc_type"]: r["without_tiers"] for r in er["by_design_L5"]["decided_by_tiers"]}
    ps["decided_by_tiers"] = [t in tiers for t in ps.index]
    ps["without_tiers"] = [tiers.get(t, "") for t in ps.index]

    # eligible exam 1 records per type (no sighting, mapping confidence not low)
    rec = [json.loads(l) for l in (ROOT / "labels_v2/records.jsonl").read_text().splitlines() if l.strip()]
    cnt: dict[str, Counter] = defaultdict(Counter)
    for r in rec:
        if r.get("saw_simulation_score") or r.get("mapping_confidence") == "low":
            continue
        t = r.get("manc_type")
        if t in ps.index:
            cnt[t][(r.get("front_leg_rhythm"), r.get("preparation"), r.get("line_specificity"))] += 1
    ps["eligible_yes"] = [sum(v for (f, _, _), v in cnt[t].items() if f == "yes") for t in ps.index]
    ps["eligible_no"] = [sum(v for (f, _, _), v in cnt[t].items() if f == "no") for t in ps.index]
    ps["eligible_headless_yes"] = [sum(v for (f, p, _), v in cnt[t].items() if f == "yes" and p == "headless") for t in ps.index]
    ps["eligible_headless_no"] = [sum(v for (f, p, _), v in cnt[t].items() if f == "no" and p == "headless") for t in ps.index]

    out: dict = {}
    out["composition"] = {
        "n": int(len(ps)), "yes": int(ps.y.sum()), "no": int((1 - ps.y).sum()),
        "yes_atlas_only": int((ps.y & ps.atlas_only).sum()), "no_atlas_only": int(((1 - ps.y).astype(bool) & ps.atlas_only).sum()),
        "best_preparation_by_label": {k: v for k, v in ps.groupby("front")["best_preparation"].value_counts().to_dict().items().__iter__()}.__repr__(),
        "decided_by_tiers_yes": int((ps.y.astype(bool) & ps.decided_by_tiers).sum()),
        "decided_by_tiers_no": int(((1 - ps.y).astype(bool) & ps.decided_by_tiers).sum()),
        "no_types_with_an_eligible_yes_record": sorted(t for t in ps.index if ps.loc[t, "y"] == 0 and ps.loc[t, "eligible_yes"] > 0),
        "yes_types_with_an_eligible_no_record": sorted(t for t in ps.index if ps.loc[t, "y"] == 1 and ps.loc[t, "eligible_no"] > 0),
    }
    strata = {
        "all_39": ps,
        "non_atlas_only": ps[~ps.atlas_only],
        "not_decided_by_tiers": ps[~ps.decided_by_tiers],
        "headless_best_preparation": ps[ps.headless],
    }
    out["auroc"] = {}
    for name, d in strata.items():
        row = {"n": int(len(d)), "yes": int(d.y.sum()), "no": int((1 - d.y).sum())}
        row["atlas_only_indicator"] = auroc(d.atlas_only.astype(float), d.y)
        for c in ["A1", "B1r", "B2r"] + base:
            row[c] = auroc(d[c], d.y)
        out["auroc"][name] = row
    # (c) magnitude vs sign in two-step signed counting
    s2, s3 = ps["S2_twohop_signed"], ps["S3_twohop_abs"]
    out["twohop"] = {
        "S2_by_label": {lab: {"n_neg": int((s2[ps.front == lab] < 0).sum()), "n_zero": int((s2[ps.front == lab] == 0).sum()),
                              "n_pos": int((s2[ps.front == lab] > 0).sum()), "median": float(s2[ps.front == lab].median())}
                        for lab in ("yes", "no")},
        "spearman_S2_vs_S3_over_39": round(float(spearmanr(s2, s3).statistic), 3),
        "auroc_minus_S3_(fewer_paths_predicts_yes)": auroc(-s3, ps.y),
        "auroc_S2_over_S3_ratio_(net_sign_only)": auroc(s2 / s3.replace(0, np.nan).fillna(1.0), ps.y),
        "auroc_S2_positive_part_only": auroc(s2.clip(lower=0), ps.y),
        "auroc_S2_negative_part_only": auroc(s2.clip(upper=0), ps.y),
    }
    cols = ["front", "best_preparation", "atlas_only", "decided_by_tiers", "without_tiers", "eligible_yes", "eligible_no",
            "eligible_headless_yes", "eligible_headless_no", "A1", "B1r", "B2r", "S2_twohop_signed", "S3_twohop_abs", "S4_total_out"]
    out["table"] = ps[cols].sort_values(["front", "S3_twohop_abs"]).reset_index().to_dict(orient="records")
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "table"}, indent=1, default=str))
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_rows", 60):
        print(ps[cols].sort_values(["front", "S3_twohop_abs"]))


if __name__ == "__main__":
    main()
