"""One-shot scoring (run 2): join frozen predictions with frozen labels and compute PREREG sections 7-8.

    uv run --project ledger --no-sync python -m brainir_ledger.scoring.pipeline --out research/ledger/score_v1

Refuses to run unless research/ledger/UNBLIND.json exists and names the SHA-256 of both lock files (`require_unblind`).
Tests call `score_tables` directly on synthetic tables with a synthetic flag in a temporary directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import LABELS, PREDICTIONS, RESEARCH
from ..labels import aggregate as AGG
from . import require_unblind
from . import stats as ST

UNINFORMED_BASELINES = ["S1_direct_mn", "S2_twohop_signed", "S3_twohop_abs", "S4_total_out", "S5_out_partners", "S6_premotor",
                        "S7_n_members"]
INFORMED_BASELINE = "S8_informed"
SEEDS = {"boot": 20261120, "perm": 20261121, "paired": 20261122}


def load_arm(pred_dir: Path, arm: str) -> pd.DataFrame | None:
    p = pred_dir / arm / "types.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df.set_index("manc_type", drop=False)


def labeled_set(type_labels: pd.DataFrame, field: str = "front", include_exposed: bool = False) -> pd.Series:
    """manc_type -> 1/0 for types whose consensus `field` is yes/no (exposed excluded unless asked)."""
    t = type_labels[type_labels[field].isin(["yes", "no"])]
    if not include_exposed:
        t = t[~t["exposed"].astype(bool)]
    return pd.Series((t[field] == "yes").astype(int).to_numpy(), index=t["manc_type"].to_numpy())


def evaluate(scores: pd.Series, y: pd.Series, *, n_boot: int = 10_000, n_perm: int = 10_000) -> dict:
    common = [t for t in y.index if t in scores.index]
    s = scores.reindex(common).astype(float).to_numpy()
    yy = y.reindex(common).to_numpy()
    out = {"n": len(common), "n_pos": int(yy.sum()), "n_neg": int(len(yy) - yy.sum())}
    if out["n_pos"] == 0 or out["n_neg"] == 0:
        out["auroc"] = None
        return out
    out.update({"auroc": ST.auroc(s, yy), "boot": ST.bootstrap_auroc(s, yy, n_boot=n_boot, seed=SEEDS["boot"]),
                "perm": ST.permutation_p(s, yy, n_perm=n_perm, seed=SEEDS["perm"]), "bands": ST.precision_npv(s, yy),
                "calibration": ST.calibration(s, yy)})
    return out


def score_tables(pred_dir: Path, labels_dir: Path, *, n_boot: int = 10_000, n_perm: int = 10_000) -> dict:
    """Everything except the guard (callers must have called `require_unblind`)."""
    type_labels = pd.read_csv(labels_dir / "type_labels.csv")
    res: dict = {"prereg": "research/ledger/PREREG.md v1", "analyses": {}}
    a1 = load_arm(pred_dir, "A1")
    if a1 is None:
        raise FileNotFoundError("A1/types.csv is required (primary prediction)")
    y = labeled_set(type_labels)
    y = y[y.index.isin(a1.index)]
    prim = evaluate(a1["primary_score"], y, n_boot=n_boot, n_perm=n_perm)
    base = load_arm(pred_dir, "S")
    best = None
    if base is not None and prim.get("auroc") is not None:
        aucs = {b: ST.auroc(base[b].reindex(y.index).astype(float).to_numpy(), y.to_numpy()) for b in UNINFORMED_BASELINES if b in base}
        best = max(aucs, key=lambda k: (aucs[k], k)) if aucs else None
        prim["baselines_auroc"] = aucs
        if INFORMED_BASELINE in base:
            prim["informed_auroc"] = ST.auroc(base[INFORMED_BASELINE].reindex(y.index).astype(float).to_numpy(), y.to_numpy())
            prim["vs_informed"] = ST.paired_bootstrap_diff(a1["primary_score"].reindex(y.index).to_numpy(), base[INFORMED_BASELINE]
                                                           .reindex(y.index).astype(float).to_numpy(), y.to_numpy(), n_boot=n_boot,
                                                           seed=SEEDS["paired"])
    if best is not None:
        prim["best_baseline"] = best
        prim["vs_best_baseline"] = ST.paired_bootstrap_diff(a1["primary_score"].reindex(y.index).to_numpy(),
                                                            base[best].reindex(y.index).astype(float).to_numpy(), y.to_numpy(),
                                                            n_boot=n_boot, seed=SEEDS["paired"])
    if prim.get("auroc") is not None:
        prim["decision"] = ST.primary_decision(prim["n"], prim["n_pos"], prim["n_neg"], prim["boot"]["lo"],
                                               prim.get("vs_best_baseline", {}).get("lo"))
    res["primary"] = prim
    A = res["analyses"]
    # 4 exposed included; 6 authors vs BrainIR; 7 never-usable excluded
    y_all = labeled_set(type_labels, include_exposed=True)
    A["exposed_included"] = evaluate(a1["primary_score"], y_all[y_all.index.isin(a1.index)], n_boot=n_boot, n_perm=n_perm)
    A["exposed_only"] = evaluate(a1["primary_score"], y_all[y_all.index.isin(a1.index) & ~y_all.index.isin(y.index)], n_boot=n_boot,
                                 n_perm=n_perm)
    ok = a1[a1["status"] == "ok"]
    A["never_usable_excluded"] = evaluate(ok["primary_score"], y[y.index.isin(ok.index)], n_boot=n_boot, n_perm=n_perm)
    for arm in ("B1", "B1-alt", "A1-lo10", "B2", "B5"):
        df = load_arm(pred_dir, arm)
        if df is not None:
            A[arm] = evaluate(df["primary_score"], y[y.index.isin(df.index)], n_boot=n_boot, n_perm=n_perm)
    b1 = load_arm(pred_dir, "B1")
    if b1 is not None:
        common = a1.index.intersection(b1.index)
        A["A1_vs_B1_spearman"] = ST.spearman(a1.loc[common, "primary_score"], b1.loc[common, "primary_score"])
    # 5 single-neuron screens summarised per type
    for arm in ("A0", "B0"):
        df = load_arm(pred_dir, arm)
        if df is not None:
            for col in ("type_max", "type_mean"):
                if col in df:
                    A[f"{arm}_{col}"] = evaluate(df[col].fillna(0.0), y[y.index.isin(df.index)], n_boot=n_boot, n_perm=n_perm)
    # 11 controls
    ctl = sorted(p.name for p in pred_dir.glob("B1-ctl-*") if (p / "types.csv").exists())
    if ctl:
        aucs = {}
        for c in ctl:
            df = load_arm(pred_dir, c)
            aucs[c] = evaluate(df["primary_score"], y[y.index.isin(df.index)], n_boot=200, n_perm=200).get("auroc")
        v = [x for x in aucs.values() if x is not None]
        A["controls"] = {"per_control": aucs, "mean": float(np.mean(v)) if v else None, "min": min(v) if v else None,
                         "max": max(v) if v else None}
    # 14 every baseline with interval
    if base is not None:
        A["baselines"] = {b: evaluate(base[b].astype(float), y[y.index.isin(base.index)], n_boot=n_boot, n_perm=n_perm)
                          for b in UNINFORMED_BASELINES + [INFORMED_BASELINE] if b in base}
    # 1-3 preparation / specificity / systematic subsets: consensus recomputed from the records
    rec_path = labels_dir / "records.jsonl"
    if rec_path.exists():
        recs = AGG.read_records(rec_path)
        exposed = set(type_labels.loc[type_labels["exposed"].astype(bool), "manc_type"])
        for name, flt in {"headless_only": lambda r: r["preparation"] == "headless",
                          "intact_only": lambda r: r["preparation"] in ("intact_free", "intact_tethered"),
                          "clean_lines": lambda r: r["line_specificity"] in ("clean", "minor_offtarget"),
                          "nonspecific_lines": lambda r: r["line_specificity"] in ("multi_dn", "unknown"),
                          "systematic_only": lambda r: r["source_type"] == "systematic_screen"}.items():
            sub = AGG.type_labels(recs, flt=flt, exposed=exposed)
            ys = labeled_set(sub)
            A[name] = evaluate(a1["primary_score"], ys[ys.index.isin(a1.index)], n_boot=n_boot, n_perm=n_perm)
    # 9 per-leg-pair predictions (B3)
    b3legs = pred_dir / "B3" / "legs.csv"
    if b3legs.exists():
        legs = pd.read_csv(b3legs)
        A["B3_pairs"] = {}
        for seg in ("front", "middle", "hind"):
            sc = legs[legs["leg"] == seg].set_index("manc_type")["score"]
            ys = labeled_set(type_labels, field=seg)
            A["B3_pairs"][seg] = evaluate(sc, ys[ys.index.isin(sc.index)], n_boot=n_boot, n_perm=n_perm)
    # 10 frequency
    if "freq_hz" in type_labels:
        tl = type_labels.dropna(subset=["freq_hz"]).set_index("manc_type")
        f = a1["median_freq_hz"].dropna()
        common = [t for t in tl.index if t in f.index and t in y.index]
        A["frequency"] = {"n": len(common), "spearman": ST.spearman(f.loc[common], tl.loc[common, "freq_hz"]) if len(common) >= 3 else None}
    # 12 stop and modulation (B4)
    b4 = load_arm(pred_dir, "B4")
    if b4 is not None and "call_128" in b4:
        tl = type_labels.set_index("manc_type")
        common = [t for t in b4.index if t in tl.index and tl.loc[t, "stop_call"] in ("stops", "no_stop")]
        pred = ["stops" if b4.loc[t, "call_128"] == "halts" else "no_stop" for t in common]
        true = [tl.loc[t, "stop_call"] for t in common]
        A["B4_stop"] = {"n": len(common), "raw_agreement": float(np.mean([p == q for p, q in zip(pred, true)])) if common else None,
                        "kappa": ST.cohen_kappa(pred, true) if common else None,
                        "confusion": pd.crosstab(pd.Series(pred, name="pred"), pd.Series(true, name="label")).to_dict() if common else {}}
    # 12b modulation: B4 middle-strength calls against the type-level effect on ongoing walking
    if b4 is not None and "call_128" in b4 and "walking_effect" in type_labels:
        tl = type_labels.set_index("manc_type")
        cmap = {"halts": "stops", "speeds_up": "speeds", "slows_down": "slows", "no_effect": "none", "no_effect_low_n": "none"}
        common = [t for t in b4.index if t in tl.index and tl.loc[t, "walking_effect"] in ("stops", "slows", "speeds", "none")]
        pred = [cmap.get(b4.loc[t, "call_128"], "none") for t in common]
        true = [tl.loc[t, "walking_effect"] for t in common]
        A["B4_modulation"] = {"n": len(common), "raw_agreement": float(np.mean([p == q for p, q in zip(pred, true)])) if common else None,
                              "kappa": ST.cohen_kappa(pred, true) if common else None}
    # 13 fixed-strength grid: AUROC at every strength
    b5 = load_arm(pred_dir, "B5")
    if b5 is not None:
        A["B5_per_strength"] = {c: evaluate(b5[c].fillna(0.0), y[y.index.isin(b5.index)], n_boot=n_boot, n_perm=n_perm)
                                for c in sorted(b5.columns) if c.startswith("score_I")}
    return res


def run_scoring(out: Path, pred_dir: Path = PREDICTIONS, labels_dir: Path = LABELS, research: Path = RESEARCH) -> dict:
    flag = require_unblind(research / "UNBLIND.json", research)
    res = score_tables(pred_dir, labels_dir)
    res["unblind_flag"] = flag
    out.mkdir(parents=True, exist_ok=True)
    (out / "score.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    run_scoring(a.out)


if __name__ == "__main__":
    main()
