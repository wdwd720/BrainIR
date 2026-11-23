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


def fig2() -> None:
    """Result 2-3 (POST HOC): each type's whole-type score in MANC (B1r) against MaleCNS (B2r), high-confidence matches; categories of
    `replication_v1/R_replication.json`."""
    plt = _plt()
    R = json.loads((RESEARCH / "replication_v1" / "R_replication.json").read_text(encoding="utf-8"))
    rows = pd.DataFrame(R["B1r_x_B2r"]["high"]["table"])
    fig, ax = plt.subplots(figsize=(4.4, 4.2))
    ax.axvline(0.5, color=AXIS, lw=0.8, ls="--", zorder=1)
    ax.axhline(0.5, color=AXIS, lw=0.8, ls="--", zorder=1)
    groups = (("replicated", S2, "replicated: driver in both"), ("single_fly_manc", S1, "single-fly hit, MANC (< 0.3 in MaleCNS)"),
              ("single_fly_malecns", S3, "single-fly hit, MaleCNS (< 0.3 in MANC)"))
    other = rows[~rows["category"].isin([g[0] for g in groups])]
    ax.scatter(other["B1r"], other["B2r"], s=10, color=MUTED, alpha=0.45, edgecolor="none", zorder=2, label="other types (incl. near-replicated)")
    for cat, col, lab in groups:
        d = rows[rows["category"] == cat]
        ax.scatter(d["B1r"], d["B2r"], s=22, color=col, edgecolor=SURFACE, linewidth=0.6, zorder=3, label=f"{lab} ({len(d)})")
    for t, dx, dy in (("DNg100", 0.0, -0.14), ("DNb08", 0.06, 0.12)):
        r = rows[rows["manc_type"] == t]
        if len(r):
            _label(ax, float(r["B1r"].iloc[0]), float(r["B2r"].iloc[0]), t, dx=dx, dy=dy)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("MANC (B1r): mean rhythm score")
    ax.set_ylabel("MaleCNS (B2r): mean rhythm score")
    ax.set_title(f"Post hoc: {len(rows)} types with a high-confidence\ncross-fly match", fontsize=9, color=INK, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    fig.tight_layout()
    _save(fig, "fig2_two_flies_posthoc")
    plt.close(fig)


def _ratio_ci(d: dict) -> tuple[float, float, float]:
    iv = (d.get("bootstrap") or {}).get("interval", {}).get("ratio")
    lo, hi = (iv[0], iv[1]) if isinstance(iv, (list, tuple)) else ((iv or {}).get("lo"), (iv or {}).get("hi"))
    return float(d["primary"]["ratio"]), float(lo), float(hi)


def fig3() -> None:
    """Results 1, 2 and 4: agreement as a fraction of the split-seed ceiling (95 % bootstrap intervals), from the locked run 4 files."""
    plt = _plt()
    A0 = json.loads((RESEARCH / "reliability_v2" / "A0.json").read_text(encoding="utf-8"))["A0"]["primary_one_member_each_side"]
    A = json.loads((RESEARCH / "reliability_v2" / "A.json").read_text(encoding="utf-8"))
    six = A["six_agreements_primary_homolog_consistent"]
    N = json.loads((RESEARCH / "reliability_v2" / "NOISE.json").read_text(encoding="utf-8"))["primary_homolog_consistent"]
    rows = [("Authors' screen: left vs right copy", _ratio_ci(A0), S1),
            ("MANC: left vs right", _ratio_ci(six["MANC-L vs MANC-R"]), S1),
            ("MaleCNS: left vs right", _ratio_ci(six["MaleCNS-L vs MaleCNS-R"]), S1),
            ("MANC vs MaleCNS, same side (L)", _ratio_ci(six["MANC-L vs MaleCNS-L"]), S2),
            ("MANC vs MaleCNS, same side (R)", _ratio_ci(six["MANC-R vs MaleCNS-R"]), S2),
            ("MANC vs MaleCNS, whole types", _ratio_ci(A["reference_R1_whole_type_cross_fly"]), S2),
            ("MANC: left vs right, paired design", _ratio_ci(N["observed_left_right_paired_design"]), S1),
            ("MANC: two Poisson copies of the counts", _ratio_ci(N["poisson"]["copy_vs_copy"]), S3)]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    for i, (lab, (v, lo, hi), col) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=col, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([v], [y], s=34, color=col, edgecolor=SURFACE, linewidth=0.8, zorder=3)
        ax.text(1.02, y, f"{v:.2f}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=8)
    ax.axvline(1.0, color=AXIS, lw=1)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("agreement / ceiling  (1 = as good as the screen with itself)")
    ax.grid(axis="y", visible=False)
    ax.set_title("How well screens of matched neurons agree", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig3_agreement")
    plt.close(fig)


def fig4() -> None:
    """Result 5 (pre-registered, PREREG v5 Part S): stability of each B1r or A1 driver across 16 Poisson copies of MANC's counts."""
    plt = _plt()
    S = json.loads((RESEARCH / "replication_v1" / "S_tests.json").read_text(encoding="utf-8"))
    rep = set(S["tests"]["b1r_drivers"]["replicated_from_locked_B2r"])
    drv = set(S["tests"]["b1r_drivers"]["drivers"]) | set(S["tests"]["a1_drivers"]["drivers"])
    rows = sorted([r for r in S["per_type"] if r["manc_type"] in drv], key=lambda r: (r["stability"], r["mean_copy_score"]))
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    for i, r in enumerate(rows):
        col = S2 if r["manc_type"] in rep else S1
        ax.barh(i, r["stability"], height=0.62, color=col, edgecolor=SURFACE, linewidth=1)
        ax.text(r["stability"] + 0.015, i, f"{r['stability']:.2f}", va="center", fontsize=7, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["manc_type"] + ("" if r["manc_type"] in S["tests"]["b1r_drivers"]["drivers"] else " (A1 only)") for r in rows], fontsize=8)
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("stability: fraction of 16 noisy copies in which the type is a driver")
    ax.grid(axis="y", visible=False)
    p1 = S["tests"]["b1r_drivers"]["primary_stability"]["p"]
    ax.set_title(f"Drivers replicated in MaleCNS (orange) or not (blue)\nexact one-sided rank test p = {p1:.2f} (pre-registered)", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig4_stability")
    plt.close(fig)


FIGS = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4}


if __name__ == "__main__":
    for name in sys.argv[1:] or list(FIGS):
        FIGS[name]()
