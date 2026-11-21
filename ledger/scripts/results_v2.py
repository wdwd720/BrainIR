"""Run-2 results material (RUN2_PROMPT section 8 "The results"), AFTER the unblinding: the scorecard (one row per labeled type),
the ROC curve and the scorecard figure for the primary set, and markdown tables drawn from `results/run2/{P,S-a,S-b,S-c}.json`.
Reporting only: no number here is a new analysis; the primary set is re-derived and must match run P exactly.

    uv run --project ledger --no-sync --with matplotlib==3.9.2 python ledger/scripts/results_v2.py
        # -> research/ledger/results/run2/{scorecard.csv, roc_primary.png, scorecard_primary.png, tables.md}
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
R = REPO / "research" / "ledger"
OUT = R / "results" / "run2"


def exposed_v2() -> set[str]:
    ex = pd.read_csv(R / "kit_v2" / "exposed_types.csv")
    s = {t for v in ex["manc_types"].dropna() for t in str(v).split(";") if t}
    s |= set(pd.read_csv(R / "labels_v2" / "exposed_v2.csv")["manc_type"].dropna())
    return s


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    P = json.loads((OUT / "P.json").read_text())["primary"]["result"]
    a1 = pd.read_csv(R / "predictions" / "A1" / "types.csv").set_index("manc_type")
    tl = pd.read_csv(R / "labels_v2" / "type_labels.csv").set_index("manc_type")
    ex = exposed_v2()
    recs = [json.loads(x) for x in (R / "labels_v2" / "records.jsonl").read_text().splitlines() if x.strip()]
    by_type = collections.defaultdict(list)
    for r in recs:
        by_type[r["manc_type"]].append(r)

    # primary set, re-derived (must equal run P)
    prim = tl[tl["front"].isin(["yes", "no"]) & tl.index.isin(a1.index) & ~tl.index.isin(ex)].copy()
    prim["score"] = a1.loc[prim.index, "primary_score"].astype(float)
    prim = prim[np.isfinite(prim["score"])]
    assert (len(prim), int((prim["front"] == "yes").sum()), int((prim["front"] == "no").sum())) == (P["n"], P["n_pos"], P["n_neg"]), "primary set differs from run P"

    # scorecard: every type with a final record
    rows = []
    for t in sorted(set(tl.index[tl["n_records"] > 0])):
        rr = by_type.get(t, [])
        rows.append({"manc_type": t, "a1_primary_score": float(a1.loc[t, "primary_score"]) if t in a1.index else None,
                     "a1_band": a1.loc[t, "band"] if t in a1.index else None, "front": tl.loc[t, "front"], "middle": tl.loc[t, "middle"],
                     "hind": tl.loc[t, "hind"], "in_primary_set": t in prim.index, "exposed": t in ex,
                     "best_preparation": tl.loc[t, "best_preparation"], "best_specificity": tl.loc[t, "best_specificity"],
                     "n_records": int(tl.loc[t, "n_records"]), "confidence": tl.loc[t, "confidence"],
                     "preparations": ";".join(sorted({str(r.get("preparation")) for r in rr})),
                     "sources": ";".join(sorted({str(r.get("doi")) for r in rr}))})
    sc = pd.DataFrame(rows).sort_values(["in_primary_set", "a1_primary_score"], ascending=[False, False], na_position="last")
    sc.to_csv(OUT / "scorecard.csv", index=False, lineterminator="\n")

    # ROC
    y = (prim["front"] == "yes").to_numpy().astype(int)
    s = prim["score"].to_numpy()
    thr = np.unique(np.concatenate([[np.inf], np.sort(s)[::-1], [-np.inf]]))[::-1]
    tpr = [((s >= t) & (y == 1)).sum() / y.sum() for t in thr]
    fpr = [((s >= t) & (y == 0)).sum() / (1 - y).sum() for t in thr]
    fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=150)
    # tied scores enter together: a straight segment (ties count one half, as in the AUROC)
    ax.plot(fpr, tpr, color="#1f4e79", lw=2, marker="o", ms=3, label=f"A1, AUROC {P['auroc']:.3f}")
    ax.plot([0, 1], [0, 1], ls="--", color="#999999", lw=1, label="chance")
    ax.set_xlabel("false-positive rate (label: no front-leg rhythm)")
    ax.set_ylabel("true-positive rate (label: front-leg rhythm)")
    ax.set_title(f"Primary set, labels v2 (n = {P['n']}: {P['n_pos']} yes, {P['n_neg']} no)", fontsize=9)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(OUT / "roc_primary.png")
    plt.close(fig)

    # scorecard figure: A1 score by label, primary set
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=150)
    rng = np.random.default_rng(0)
    for i, lab in enumerate(["no", "yes"]):
        v = prim.loc[prim["front"] == lab, "score"].to_numpy()
        ax.scatter(np.full(len(v), i) + rng.uniform(-0.12, 0.12, len(v)), v, s=22, alpha=0.8,
                   color=("#8c2d04" if lab == "yes" else "#4d4d4d"), edgecolor="none")
    ax.set_xticks([0, 1], ["no front-leg rhythm", "front-leg rhythm"])
    ax.set_ylabel("A1 score (type-level rhythm score)")
    ax.set_yscale("symlog", linthresh=0.01)
    ax.set_ylim(-0.002, 1.05)
    ax.axhline(0, color="#cccccc", lw=0.6, zorder=0)
    ax.text(0.5, 0.0008, "score exactly 0", ha="center", va="bottom", fontsize=7, color="#777777")
    ax.set_title("Scorecard, primary set (one dot per type)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "scorecard_primary.png")
    plt.close(fig)
    print(json.dumps({"scorecard_rows": len(sc), "primary_set": len(prim), "figures": ["roc_primary.png", "scorecard_primary.png"]}))


if __name__ == "__main__":
    sys.exit(main())
