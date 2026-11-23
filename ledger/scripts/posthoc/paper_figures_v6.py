"""Figures of PREPRINT_v1 (RUN6_PROMPT section 8: up to six, drawn by script from locked files, plain axis labels and full legends).
Inputs: `pertype_v1/` (LOCK_pertype_v1), `reliability_v2/` (LOCK_reliability_v2), `replication_v1/` (LOCK_replication_v1),
`posthoc_v6/` (LOCK_posthoc_v6), `thirdfly_v1/` (LOCK_thirdfly_v1). Output: `paper/figures_v1/*.svg|png`.

    uv run --project ledger --no-sync --with matplotlib==3.9.2 python ledger/scripts/posthoc/paper_figures_v6.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brainir_ledger import RESEARCH  # noqa: E402

FIG = RESEARCH / "paper" / "figures_v1"
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#8a5cd6"   # categorical slots in fixed order


def _plt():
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID,
                         "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False, "svg.hashsalt": "brainir-ledger-v6",
                         "svg.fonttype": "none"})
    return plt


def _save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", metadata={"Date": None})
    fig.savefig(FIG / f"{name}.png", dpi=200, metadata={"Software": None})
    print("wrote", FIG / f"{name}.png")


def _j(rel: str) -> dict:
    return json.loads((RESEARCH / rel).read_text(encoding="utf-8"))


def _ratio(d: dict) -> tuple[float, float, float]:
    iv = d["bootstrap"]["interval"]["ratio"]
    return float(d["primary"]["ratio"]), float(iv[0]), float(iv[1])


def fig1() -> None:
    """Left against right copy in the authors' published single-neuron screen, types with one copy per side."""
    plt = _plt()
    a = pd.read_csv(RESEARCH / "pertype_v1" / "A0_copies.csv", dtype={"manc_type": str})
    a = a[a["type_one_each_side"].astype(str).str.lower() == "true"]
    w = a.pivot_table(index="manc_type", columns="side", values="score", aggfunc="first").dropna()
    fig, ax = plt.subplots(figsize=(4.2, 4.0))
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, zorder=1)
    ax.scatter(w["L"], w["R"], s=16, color=S1, alpha=0.75, edgecolor=SURFACE, linewidth=0.6, zorder=2)
    for t in ("DNg100", "DNb08"):
        if t in w.index:
            ax.annotate(t, (w.loc[t, "L"], w.loc[t, "R"]), xytext=(w.loc[t, "L"] - 0.28, w.loc[t, "R"] + 0.05), fontsize=8, color=INK,
                        arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.6})
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("left copy: mean rhythm score (128 runs)")
    ax.set_ylabel("right copy: mean rhythm score (128 runs)")
    ax.set_title(f"Authors' single-neuron screen (MANC): {len(w)} cell types\nwith one copy on each side", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig1_left_right_authors")
    plt.close(fig)


def fig2() -> None:
    """Agreement as a fraction of the ceiling: left vs right, count noise, across animals (95 % intervals)."""
    plt = _plt()
    A0 = _j("reliability_v2/A0.json")["A0"]["primary_one_member_each_side"]
    A = _j("reliability_v2/A.json")["six_agreements_primary_homolog_consistent"]
    N = _j("reliability_v2/NOISE.json")["primary_homolog_consistent"]
    C = _j("thirdfly_v1/C_tests.json")
    c1 = C["C1"]["label_consistent_noDNg100"] if isinstance(C.get("C1"), dict) else None
    c2 = C["C2"]["label_consistent_noDNg100"] if isinstance(C.get("C2"), dict) else None
    prim = C["primary_procedure"]
    c3 = C["C3"][prim] if isinstance(C["C3"].get(prim), dict) else None
    rows = [("Authors' screen, MANC: left vs right copy", _ratio(A0), S1),
            ("Our screen, MANC: left vs right", _ratio(A["MANC-L vs MANC-R"]), S1),
            ("Our screen, MaleCNS: left vs right", _ratio(A["MaleCNS-L vs MaleCNS-R"]), S1)]
    if c1:
        rows.append(("Our screen, BANC: left vs right (pre-registered)", _ratio(c1), S1))
    rows.append(("MANC: two copies with resampled synapse counts", _ratio(N["poisson"]["copy_vs_copy"]), S3))
    if c2:
        rows.append(("BANC: two copies with resampled synapse counts", _ratio(c2["copy_vs_copy"]), S3))
    if c3:
        rows += [("MANC vs MaleCNS (post hoc)", _ratio(c3["MANC-MaleCNS (reference, post hoc)"]["three_animal_noDNg100"]), S2),
                 ("MANC vs BANC (pre-registered)", _ratio(c3["MANC-BANC"]["three_animal_noDNg100"]), S2),
                 ("MaleCNS vs BANC (pre-registered)", _ratio(c3["MaleCNS-BANC"]["three_animal_noDNg100"]), S2)]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    for i, (lab, (v, lo, hi), col) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=col, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([v], [y], s=34, color=col, edgecolor=SURFACE, linewidth=0.8, zorder=3)
        ax.text(1.03, y, f"{v:.2f}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=8)
    ax.axvline(1.0, color=AXIS, lw=1)
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("agreement / ceiling (1 = as close as a screen is to itself)")
    ax.grid(axis="y", visible=False)
    sweep_note = "current sweep" if prim == "sweep" else "tuned current"
    ax.set_title(f"Agreement of matched screens. Blue: left vs right; green: count noise;\norange: across animals ({sweep_note}, "
                 f"181 types)", fontsize=8.5, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig2_agreement")
    plt.close(fig)


def fig3() -> None:
    """Share of one animal's hits that are hits in another, by cut, with the chance level (n_Y / N)."""
    plt = _plt()
    H = _j("posthoc_v6/H_posthoc.json")["pairs"]
    C = _j("thirdfly_v1/C_tests.json")
    cuts = ["0.3", "0.4", "0.5", "0.6"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.2), sharey=True)
    panels = [("Tuned current (first two animals only; post hoc)", [("MANC to MaleCNS (post hoc)", H["tuned_B1r_x_B2r"]["high|without_DNg100"], S1)]),
              ("Current sweep", [("MANC to MaleCNS (post hoc)", H["sweep_dx1_x_ms"]["high|without_DNg100"], S1)])]
    if isinstance(C.get("C4"), dict) and C["primary_procedure"] == "sweep":
        for name, col in (("MANC sweep list", S2), ("MaleCNS sweep list", S3)):
            key = "manc_banc_high_noDNg100" if name.startswith("MANC") else "mcns_banc_high_noDNg100"
            lab = "MANC to BANC (pre-registered)" if name.startswith("MANC") else "MaleCNS to BANC (pre-registered)"
            panels[1][1].append((lab, C["C4"][name][key], col))
    for ax, (title, series) in zip(axes, panels):
        for lab, blk, col in series:
            pts = [blk["cuts"][z]["overlap"]["point"] for z in cuts]
            rate = [p["rate_x_in_y"] if p["rate_x_in_y"] is not None else np.nan for p in pts]
            chance = [p["n_y"] / p["N"] for p in pts]
            x = [float(z) for z in cuts]
            ax.plot(x, rate, color=col, lw=2, marker="o", ms=5, label=lab)
            ax.plot(x, chance, color=col, lw=1, ls="--", alpha=0.8)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlabel("cut: a cell type is a hit if its score is at least")
        ax.set_xticks([0.3, 0.4, 0.5, 0.6])
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("share of the first animal's hits that are\nhits in the second (dashed: chance)")
    axes[1].legend(fontsize=7, frameon=False, loc="upper right")
    fig.tight_layout()
    _save(fig, "fig3_recurrence_by_cut")
    plt.close(fig)


def fig4() -> None:
    """Scores of every type that is a hit (>= 0.5) in at least one animal's primary-procedure screen, in all three, three-animal set."""
    plt = _plt()
    C = _j("thirdfly_v1/C_tests.json")
    ts = json.loads((RESEARCH / "gates_v6" / "TYPE_SETS_v6.json").read_text())["three_animal"]
    tab = pd.DataFrame(C["C5"]["driver_table"]).set_index("manc_type")
    prim = C["primary_procedure"]
    cols = ["MANC_sweep", "MaleCNS_sweep", "BANC_sweep"] if prim == "sweep" else ["B1r", "B2r", "BANC_tuned"]
    t = tab.loc[[x for x in tab.index if x in set(ts)], cols].astype(float)
    t = t[(t >= 0.5).any(axis=1)]
    t = t.loc[t.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(3.6, max(3.0, 0.13 * len(t) + 1.0)))
    im = ax.imshow(t.to_numpy(), aspect="auto", cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["MANC", "MaleCNS", "BANC"], fontsize=8)
    ax.set_yticks(range(len(t)))
    ax.set_yticklabels(t.index, fontsize=5.5)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.5)
    cb.set_label("rhythm score", fontsize=8)
    ax.set_title(f"Hits in any animal ({'current sweep' if prim == 'sweep' else 'tuned current'};\n{len(t)} types matched in all three)",
                 fontsize=8.5, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig4_hits_three_animals")
    plt.close(fig)


def fig5() -> None:
    """Stability under count noise in MANC (run 5) against the third animal's score (C8)."""
    plt = _plt()
    C = _j("thirdfly_v1/C_tests.json")
    S = pd.DataFrame(_j("replication_v1/S_tests.json")["per_type"]).set_index("manc_type")
    c8 = C["C8"]
    if not isinstance(c8, dict):
        return
    ts = c8["primary"]["types"]
    prim = C["primary_procedure"]
    col = "BANC_sweep" if prim == "sweep" else "BANC_tuned"
    tab = pd.DataFrame(C["C5"]["driver_table"]).set_index("manc_type")
    y = [float(tab.loc[t, col]) if t in tab.index else np.nan for t in ts]
    x = S.loc[ts, "mean_copy_score"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    ax.scatter(x, y, s=30, color=S1, edgecolor=SURFACE, linewidth=0.8, zorder=3)
    for t, xi, yi in zip(ts, x, y):
        if yi >= 0.1:  # the other types score below 0.1 in BANC (named in the legend text of the paper)
            ax.annotate(t, (xi, yi), xytext=(4, 3), textcoords="offset points", fontsize=7, color=INK2)
    ax.set_xlabel("MANC: mean score over 16 copies with\nresampled synapse counts (run 5)")
    ax.set_ylabel(f"BANC score ({'current sweep' if prim == 'sweep' else 'tuned current'})")
    p = c8["primary"].get("p_one_sided_permutation")
    r = c8["primary"].get("rho")
    ax.set_title(f"Does stability under count noise predict the third animal?\n12 types, Spearman {r:.2f}, one-sided p = {p:.3f}" if (r is not None and p is not None)
                 else "Stability against the third animal (rho undefined)", fontsize=8.5, color=INK, loc="left")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    fig.tight_layout()
    _save(fig, "fig5_stability_third_animal")
    plt.close(fig)


def fig6() -> None:
    """Part V: each DNb08 copy alone in MaleCNS at fixed currents (2-s runs, 16 seeds): share of seeds scoring >= 0.5."""
    plt = _plt()
    V = _j("thirdfly_v1/C_tests.json")["V"]["V2"]["table"]
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    for (pos, tab), col in zip(sorted(V.items(), key=lambda kv: int(kv[0])), (S1, S2, S3, S4)):
        cur = sorted((float(c), v) for c, v in tab.items())
        ax.plot([c for c, _ in cur], [v["frac_ge_0_5"] for _, v in cur], color=col, lw=1.8, marker="o", ms=3.5,
                label=f"DNb08 copy at position {pos}" + (" (authors' neuron)" if pos == "391" else ""))
    au = V.get("391", {}).get("250")
    if au:
        ax.scatter([250], [au["frac_ge_0_5"]], s=90, facecolor="none", edgecolor=INK, lw=1.2, zorder=4, label="authors' configuration (current 250)")
    ax.axhline(0.5, color=AXIS, lw=1, ls="--")
    ax.set_xscale("log", base=2)
    ax.set_xticks([4, 16, 64, 256, 1024])
    ax.set_xticklabels(["4", "16", "64", "256", "1,024"])
    ax.set_xlabel("stimulus current (fixed; log scale)")
    ax.set_ylabel("share of 16 runs with rhythm score >= 0.5")
    ax.set_ylim(-0.03, 1.05)
    ax.legend(fontsize=6.5, frameon=False, loc="upper left")
    ax.set_title("Single DNb08 neurons in our MaleCNS model, fixed currents", fontsize=8.5, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig6_dnb08_malecns_single")
    plt.close(fig)


FIGS = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig5": fig5, "fig6": fig6}

if __name__ == "__main__":
    for name in sys.argv[1:] or FIGS:
        FIGS[name]()
