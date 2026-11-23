"""Figures of the preprint (RUN5_PROMPT Part P), each drawn from locked files only.

    uv run --project ledger --no-sync --with matplotlib==3.9.2 python ledger/scripts/posthoc/paper_figures_v5.py [fig1 fig2 ...]

Writes `research/ledger/paper/figures/<name>.svg` and `.png`. Colours: the dataviz reference palette (light mode), categorical slots in
fixed order, at most three categories per scatter (others in muted grey), identity never by colour alone (direct labels / legend).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from brainir_ledger import RESEARCH  # noqa: E402

FIG = RESEARCH / "paper" / "figures"
PERTYPE = RESEARCH / "pertype_v1"
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"   # categorical slots 1-3 (validated all-pairs in light mode)


def _plt():
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID,
                         "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "svg.hashsalt": "brainir-ledger-v5",
                         "svg.fonttype": "none"})
    return plt


def _save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", metadata={"Date": None})
    fig.savefig(FIG / f"{name}.png", dpi=200, metadata={"Software": None})
    print("wrote", FIG / f"{name}.svg")


def _label(ax, x, y, text, dx=0.02, dy=0.02):
    ax.annotate(text, (x, y), xytext=(x + dx, y + dy), fontsize=8, color=INK, arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.6})


def fig1() -> None:
    """Result 1: left against right copy in the authors' published single-neuron screen (A0), types with one copy per side."""
    plt = _plt()
    a = pd.read_csv(PERTYPE / "A0_copies.csv", dtype={"manc_type": str})
    a = a[a["type_one_each_side"].astype(str).str.lower() == "true"]
    w = a.pivot_table(index="manc_type", columns="side", values="score", aggfunc="first").dropna()
    a0 = json.loads((RESEARCH / "reliability_v2" / "A0.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(4.2, 4.0))
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, zorder=1)
    ax.scatter(w["L"], w["R"], s=16, color=S1, alpha=0.75, edgecolor=SURFACE, linewidth=0.6, zorder=2)
    for t in ("DNg100", "DNb08"):
        if t in w.index:
            _label(ax, w.loc[t, "L"], w.loc[t, "R"], t, dx=-0.25, dy=0.05)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("left copy: mean rhythm score (128 runs)")
    ax.set_ylabel("right copy: mean rhythm score (128 runs)")
    ax.set_title(f"Authors' single-neuron screen: {len(w)} types\nwith one copy per side", fontsize=9, color=INK, loc="left")
    _save(fig, "fig1_a0_left_right")
    plt.close(fig)
    return a0


FIGS = {"fig1": fig1}


if __name__ == "__main__":
    for name in sys.argv[1:] or list(FIGS):
        FIGS[name]()
