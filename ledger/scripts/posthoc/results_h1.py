"""Exam 2 report material (PREREG v3 S6, RUN3_PROMPT section 9 "Scorecard", "Figures"): runs only AFTER the frozen pipeline's primary
run exists (results/run3/primary.json). Reads the locked H-M table and the locked consensus, and writes:

    results/run3/scorecard.csv     one row per hemilineage: class, coded dimensions, percentile rank, rank position, predicted values,
                                   observed cells
    results/run3/fig_scorecard.png percentile rank per scored unit (sorted), by class, with the permutation-null band
    results/run3/fig_matrix.png    predicted (standardised) and observed matrices side by side, same unit order

    uv run --project ledger --no-sync --with matplotlib==3.9.2 python ledger/scripts/posthoc/results_h1.py
No number here is new: ranks come from primary.json; values from the locked files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.scoring_h1 import DIMS, standardise  # noqa: E402

OUT = RESEARCH / "results" / "run3"
NAMES = {"d1": "any movement", "d2": "front legs", "d3": "middle legs", "d4": "hind legs", "d5": "flex/lower, held",
         "d6": "extend/rise, held", "d7p": "repeated leg mvt", "d10": "jump/takeoff", "d11": "wings", "d13": "wing buzz/flight",
         "d14": "halteres", "d15": "abdomen"}


def main() -> None:
    prim_p = OUT / "primary.json"
    if not prim_p.is_file():
        raise SystemExit("results/run3/primary.json does not exist: nothing is unblinded; refused")
    prim = json.loads(prim_p.read_text())
    units = pd.read_csv(RESEARCH / "hl_units" / "UNITS_v1.csv", dtype={"unit": str}).set_index("unit")
    P = pd.read_csv(RESEARCH / "predictions_h1" / "H-M" / "predicted.csv", dtype={"unit": str}).set_index("unit")
    cons = pd.read_csv(RESEARCH / "labels_h1" / "consensus.csv", dtype={"unit": str}).set_index("unit").reindex(units.index)
    pr, pos = prim["H-M"].get("pr", {}), prim["H-M"].get("pos", {})
    rows = []
    for u in units.index:
        c = cons.loc[u] if u in cons.index else pd.Series(dtype=object)
        coded = [d for d in DIMS if c.get(d) in ("yes", "no")]
        rows.append({"unit": u, "class": units.loc[u, "nt_class"], "n_coded_primary": len(coded), "scored": u in pr,
                     "percentile_rank": pr.get(u), "rank_position": pos.get(u),
                     **{f"pred_{d}": float(P.loc[u, d]) for d in DIMS}, **{f"obs_{d}": c.get(d, "") for d in DIMS}})
    sc = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    sc.to_csv(OUT / "scorecard.csv", index=False, lineterminator="\n", float_format="%.6g")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = sc[sc["scored"]].sort_values("percentile_rank", ascending=False)
    colors = {"excitatory": "#1f77b4", "inhibitory": "#d62728", "motor": "#2ca02c", "mixed": "#7f7f7f"}
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(range(len(s)), s["percentile_rank"], color=[colors.get(c, "#7f7f7f") for c in s["class"]])
    ax.set_xticks(range(len(s)))
    ax.set_xticklabels(s["unit"], rotation=90, fontsize=8)
    null = (prim.get("chance") or {}).get("null_mean_pr") or {}
    if null:
        ax.axhspan(null["lo"], null["hi"], color="#bbbbbb", alpha=0.35, label="permutation null 2.5-97.5 %")
        ax.axhline(null["mean"], color="#555555", lw=1, ls="--", label="permutation null mean")
    ax.axhline(prim["H-M"]["mean_pr"], color="black", lw=1.5, label=f"mean percentile rank {prim['H-M']['mean_pr']:.3f}")
    ax.set_ylim(0, 1)
    ax.set_ylabel("percentile rank of the true hemilineage")
    ax.set_title("Exam 2 scorecard: does the model's predicted phenotype pick out the right hemilineage? (H-M)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=v) for v in colors.values()]
    leg1 = ax.legend(handles, list(colors), loc="upper right", fontsize=8, title="class")
    ax.add_artist(leg1)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_scorecard.png", dpi=150)
    plt.close(fig)

    order = list(s["unit"]) + [u for u in units.index if u not in set(s["unit"])]
    Z = standardise(P.loc[order])
    obs = np.full((len(order), len(DIMS)), np.nan)
    for i, u in enumerate(order):
        for j, d in enumerate(DIMS):
            v = cons.loc[u, d] if u in cons.index else None
            obs[i, j] = 1.0 if v == "yes" else (0.0 if v == "no" else np.nan)
    fig, axes = plt.subplots(1, 2, figsize=(11, 11), sharey=True)
    im = axes[0].imshow(Z[DIMS].to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-3, vmax=3)
    axes[0].set_title("predicted (H-M)\nstandardised per dimension")
    from matplotlib.colors import ListedColormap

    cm = ListedColormap(["#6baed6", "#252525"])  # 0 = no (blue), 1 = yes (black)
    cm.set_bad("#f2f2f2")  # not coded (light grey)
    axes[1].imshow(np.ma.masked_invalid(obs), aspect="auto", cmap=cm, vmin=0, vmax=1)
    axes[1].set_title("observed consensus\n(black = yes, blue = no, grey = not coded)")
    for ax in axes:
        ax.set_xticks(range(len(DIMS)))
        ax.set_xticklabels([NAMES[d] for d in DIMS], rotation=60, ha="right", fontsize=8)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels(order, fontsize=7)
    fig.colorbar(im, ax=axes[0], fraction=0.04)
    fig.tight_layout()
    fig.savefig(OUT / "fig_matrix.png", dpi=150)
    plt.close(fig)
    print(json.dumps({"scorecard_rows": len(sc), "scored": int(sc["scored"].sum())}))


if __name__ == "__main__":
    main()
