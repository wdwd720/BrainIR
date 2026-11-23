"""Figures of PREPRINT_v1 after its four reviews (RUN6_PROMPT section 8: up to six, drawn by script from locked files, plain axis
labels and full legends). Successor of `paper_figures_v6.py`, which LOCK_posthoc_v6 and LOCK_thirdfly_v1 hash and which stays as locked.
Inputs: `pertype_v1/` (LOCK_pertype_v1), `reliability_v2/` (LOCK_reliability_v2), `replication_v1/` (LOCK_replication_v1),
`posthoc_v6/` (LOCK_posthoc_v6), `thirdfly_v1/` (LOCK_thirdfly_v1), `paper_posthoc_v1/` (LOCK_paper_posthoc_v1).
Output: `paper/figures_v1/*.svg|png`.

    uv run --project ledger --no-sync --with matplotlib==3.9.2 python ledger/scripts/posthoc/paper_figures_preprint_v1.py
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
    zero = int(((w["L"] < 0.005) & (w["R"] < 0.005)).sum())
    fig, ax = plt.subplots(figsize=(4.4, 4.2))
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1, zorder=1)
    ax.axvline(0.5, color=MUTED, lw=0.8, ls="--", zorder=1)
    ax.axhline(0.5, color=MUTED, lw=0.8, ls="--", zorder=1)
    ax.scatter(w["L"], w["R"], s=16, color=S1, alpha=0.75, edgecolor=SURFACE, linewidth=0.6, zorder=2)
    for t in ("DNg100", "DNb08"):
        if t in w.index:
            ax.annotate(t, (w.loc[t, "L"], w.loc[t, "R"]), xytext=(w.loc[t, "L"] - 0.30, w.loc[t, "R"] + 0.06), fontsize=8, color=INK,
                        arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.6})
    nl = int(((w["L"] >= 0.5)).sum())
    nr = int(((w["R"] >= 0.5)).sum())
    nb = int(((w["L"] >= 0.5) & (w["R"] >= 0.5)).sum())
    ax.annotate(f"{zero} types score\n0 on both sides", (0.0, 0.0), xytext=(0.10, 0.16), fontsize=7.5, color=INK2,
                arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.6})
    ax.text(0.98, 0.03, f"hits (dashed lines: 0.5):\nleft {nl}, right {nr}, both {nb}", ha="right", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("left copy: mean rhythm score (128 draws)")
    ax.set_ylabel("right copy: mean rhythm score (128 draws)")
    ax.set_title(f"Authors' single-neuron screen (MANC): {len(w)} cell types\nwith one copy on each side", fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig1_left_right_authors")
    plt.close(fig)


def fig2() -> None:
    """Agreement as a fraction of the ceiling, in three labelled groups (95 % intervals over cell types)."""
    plt = _plt()
    A0 = _j("reliability_v2/A0.json")["A0"]["primary_one_member_each_side"]
    A = _j("reliability_v2/A.json")["six_agreements_primary_homolog_consistent"]
    N = _j("reliability_v2/NOISE.json")["primary_homolog_consistent"]
    C = _j("thirdfly_v1/C_tests.json")
    c1 = C["C1"]["label_consistent_noDNg100"]
    c2 = C["C2"]["label_consistent_noDNg100"]
    sw, tu = C["C3"]["sweep"], C["C3"]["tuned"]
    k = "three_animal_noDNg100"
    groups = [
        ("A. Left copy vs right copy", S1, [
            ("Authors' screen, MANC (both legs read out)", _ratio(A0)),
            ("Our one-sided screens, MANC (current-setting)", _ratio(A["MANC-L vs MANC-R"])),
            ("Our one-sided screens, MaleCNS (current-setting)", _ratio(A["MaleCNS-L vs MaleCNS-R"])),
            ("Our one-sided screens, BANC (current-setting) *", _ratio(c1))]),
        ("B. Resampled synapse counts", S3, [
            ("MANC: resampled vs resampled (paired design)", _ratio(N["poisson"]["copy_vs_copy"])),
            ("MANC: left vs right, same design", _ratio(N["observed_left_right_paired_design"])),
            ("BANC: resampled vs resampled (cross-half) *", _ratio(c2["copy_vs_copy"])),
            ("BANC: left vs right, same design *", _ratio(c2["observed_left_right"]))]),
        ("C. Different animals (181 types)", S2, [
            ("MANC vs MaleCNS, current sweep (post hoc)", _ratio(sw["MANC-MaleCNS (reference, post hoc)"][k])),
            ("MANC vs BANC, current sweep *", _ratio(sw["MANC-BANC"][k])),
            ("MaleCNS vs BANC, current sweep *", _ratio(sw["MaleCNS-BANC"][k])),
            ("MANC vs MaleCNS, current-setting (post hoc)", _ratio(tu["MANC-MaleCNS (reference, post hoc)"][k])),
            ("MANC vs BANC, current-setting (beside the test)", _ratio(tu["MANC-BANC"][k])),
            ("MaleCNS vs BANC, current-setting (beside the test)", _ratio(tu["MaleCNS-BANC"][k]))]),
    ]
    rows, ylab, heads = [], [], []
    y = 0
    for title, col, items in groups:
        heads.append((y, title))
        y += 1
        for lab, val in items:
            rows.append((y, val, col))
            ylab.append((y, lab))
            y += 1
        y += 0.4
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    for yy, (v, lo, hi), col in rows:
        ax.plot([lo, hi], [yy, yy], color=col, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([v], [yy], s=34, color=col, edgecolor=SURFACE, linewidth=0.8, zorder=3)
        ax.text(1.03, yy, f"{v:.2f}", va="center", fontsize=8, color=INK2)
    ticks = sorted([(t, l, False) for t, l in ylab] + [(t, l, True) for t, l in heads])
    ax.set_yticks([t for t, _, _ in ticks])
    ax.set_yticklabels([l for _, l, _ in ticks], fontsize=7.5)
    for lab, (_, _, bold) in zip(ax.get_yticklabels(), ticks):
        if bold:
            lab.set_fontweight("bold")
            lab.set_color(INK)
            lab.set_fontsize(8)
    ax.invert_yaxis()
    ax.axvline(1.0, color=AXIS, lw=1)
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("agreement as a fraction of the ceiling")
    ax.grid(axis="y", visible=False)
    ax.set_title("Agreement between screens (dot: estimate; bar: 95 % interval)", fontsize=8.5, color=INK, loc="left")
    fig.text(0.01, 0.006, "* pre-registered test of the third animal (BANC)", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "fig2_agreement")
    plt.close(fig)


def fig3() -> None:
    """Share of one animal's hits that are hits in another, by cut, with the chance level (n_Y / N)."""
    plt = _plt()
    H = _j("posthoc_v6/H_posthoc.json")["pairs"]
    C = _j("thirdfly_v1/C_tests.json")["C4"]
    cuts = ["0.3", "0.4", "0.5", "0.6"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5), sharey=True)
    panels = [("Current-setting procedure (post hoc)",
               [("MANC hits in MaleCNS (post hoc)", H["tuned_B1r_x_B2r"]["high|without_DNg100"], S1, (0, (4, 2)))]),
              ("Current sweep",
               [("MANC hits in MaleCNS (post hoc)", H["sweep_dx1_x_ms"]["high|without_DNg100"], S1, (0, (4, 2))),
                ("MANC hits in BANC *", C["MANC sweep list"]["manc_banc_high_noDNg100"], S2, (0, (1, 1.5))),
                ("MaleCNS hits in BANC *", C["MaleCNS sweep list"]["mcns_banc_high_noDNg100"], S3, (0, (6, 2, 1, 2))),
                ("authors' whole-type screen's hits in BANC *",
                 C["A1 (the authors' list; 16-replicate halves under either procedure)"]["manc_banc_high_noDNg100"], S4, (0, (2, 3)))])]
    for ax, (title, series) in zip(axes, panels):
        for lab, blk, col, dash in series:
            pts = [blk["cuts"][z]["overlap"]["point"] for z in cuts]
            rate = [p["rate_x_in_y"] if p["rate_x_in_y"] is not None else np.nan for p in pts]
            chance = [p["n_y"] / p["N"] for p in pts]
            x = [float(z) for z in cuts]
            ax.plot(x, rate, color=col, lw=2, marker="o", ms=5, label=lab)
            ax.plot(x, chance, color=col, lw=1, ls=dash, alpha=0.9)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlabel("threshold: a cell type is a hit if its score is at least")
        ax.set_xticks([0.3, 0.4, 0.5, 0.6])
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("share of one animal's hits that are hits\nin the other (thin line: chance)")
    axes[0].legend(fontsize=6.8, frameon=False, loc="upper right")
    axes[1].legend(fontsize=6.8, frameon=False, loc="upper right")
    fig.text(0.01, 0.005, "* pre-registered (third animal). High-confidence matches; DNg100 left out.", fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "fig3_recurrence_by_cut")
    plt.close(fig)


def fig4() -> None:
    """Types that are hits (>= 0.5) in at least two animals under the current sweep, scores under both procedures (post hoc table)."""
    plt = _plt()
    from matplotlib.patches import Rectangle  # noqa: PLC0415

    t = pd.read_csv(RESEARCH / "paper_posthoc_v1" / "THREE_ANIMAL_SCORES.csv", dtype={"manc_type": str}).set_index("manc_type")
    P = _j("paper_posthoc_v1/PAPER_POSTHOC.json")
    sel = t[t["n_animals_hit_sweep"] >= 2].copy()
    sel["m"] = sel[["MANC_sweep", "MaleCNS_sweep", "BANC_sweep"]].mean(axis=1)
    sel = sel.sort_values(["n_animals_hit_sweep", "m"], ascending=[False, False])
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 0.26 * len(sel) + 1.6), sharey=True)
    for ax, proc, name in ((axes[0], "sweep", "current sweep"), (axes[1], "current_setting", "current-setting procedure")):
        cols = [f"{a}_{proc}" for a in ("MANC", "MaleCNS", "BANC")]
        m = sel[cols].to_numpy(float)
        ax.imshow(m, aspect="auto", cmap="Blues", vmin=0, vmax=1.25)
        for i in range(m.shape[0]):
            for j in range(3):
                hit = m[i, j] >= 0.5
                ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=6.8, color=INK if not hit else "#ffffff",
                        fontweight="bold" if hit else "normal")
                if hit:
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=INK, lw=1.0))
        ax.set_xticks(range(3))
        ax.set_xticklabels(["MANC", "MaleCNS", "BANC"], fontsize=8)
        ax.xaxis.tick_top()
        ax.set_title(name, fontsize=8.5, color=INK, pad=18)
        ax.grid(False)
        ax.set_yticks(range(len(sel)))
        ax.set_yticklabels(sel.index, fontsize=7)
    n4 = P["sweep"]["with_DNg100"]["hit_in_all_three"]
    fig.suptitle(f"{len(sel)} of 182 types are sweep hits in at least two animals; {n4} in all three "
                 f"(boxed, bold: score >= 0.5; post hoc)", fontsize=8.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    _save(fig, "fig4_hits_three_animals")
    plt.close(fig)


def fig5() -> None:
    """Stability under count noise in MANC (the earlier analysis) against the third animal's score (C8): values and ranks."""
    plt = _plt()
    from scipy.stats import rankdata  # noqa: PLC0415

    C = _j("thirdfly_v1/C_tests.json")
    S = pd.DataFrame(_j("replication_v1/S_tests.json")["per_type"]).set_index("manc_type")
    c8 = C["C8"]
    ts = c8["primary"]["types"]
    tab = pd.DataFrame(C["C5"]["driver_table"]).set_index("manc_type")
    y = np.array([float(tab.loc[t, "BANC_sweep"]) for t in ts])
    x = S.loc[ts, "mean_copy_score"].to_numpy(float)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.5))
    ax = axes[0]
    ax.scatter(x, y, s=30, color=S1, edgecolor=SURFACE, linewidth=0.8, zorder=3)
    for t, xi, yi in zip(ts, x, y):
        if yi >= 0.1:
            ax.annotate(t, (xi, yi), xytext=(4, 3), textcoords="offset points", fontsize=7, color=INK2)
    ax.set_xlabel("MANC: mean score over 16 networks\nwith resampled synapse counts")
    ax.set_ylabel("BANC score (current sweep)")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("Scores (10 of 12 BANC scores below 0.07)", fontsize=8.5, color=INK, loc="left")
    ax = axes[1]
    rx, ry = rankdata(x), rankdata(y)
    ax.scatter(rx, ry, s=30, color=S1, edgecolor=SURFACE, linewidth=0.8, zorder=3)
    for t, xi, yi in zip(ts, rx, ry):
        ax.annotate(t, (xi, yi), xytext=(4, 2), textcoords="offset points", fontsize=6.3, color=INK2)
    ax.set_xlabel("rank of the MANC stability score")
    ax.set_ylabel("rank of the BANC score")
    ax.set_xlim(0, 14.5)
    ax.set_ylim(0, 13.5)
    r, p = c8["primary"]["rho"], c8["primary"]["p_one_sided_permutation"]
    ax.set_title(f"Ranks (the test): Spearman {r:.2f}, p = {p:.3f}", fontsize=8.5, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig5_stability_third_animal")
    plt.close(fig)


def fig6() -> None:
    """Part V: each DNb08 copy alone in MaleCNS at fixed currents (2-s runs, 16 draws): share of draws scoring >= 0.5."""
    plt = _plt()
    V = _j("thirdfly_v1/C_tests.json")["V"]["V2"]["table"]
    fig, ax = plt.subplots(figsize=(5.4, 3.3))
    for i, ((pos, tab), col) in enumerate(zip(sorted(V.items(), key=lambda kv: int(kv[0])), (S1, S2, S3, S4)), start=1):
        cur = sorted((float(c), v) for c, v in tab.items())
        ax.plot([c for c, _ in cur], [v["frac_ge_0_5"] for _, v in cur], color=col, lw=1.8, marker="o", ms=3.5,
                label=f"copy {i} (position {pos})" + (", the authors' neuron" if pos == "391" else ""))
    au = V.get("391", {}).get("250")
    if au:
        ax.scatter([250], [au["frac_ge_0_5"]], s=90, facecolor="none", edgecolor=INK, lw=1.2, zorder=4, label="the authors' configuration (current 250)")
    ax.axhline(0.5, color=AXIS, lw=1, ls="--")
    ax.set_xscale("log", base=2)
    ax.set_xticks([4, 16, 64, 256, 1024])
    ax.set_xticklabels(["4", "16", "64", "256", "1,024"])
    ax.set_xlabel("stimulus current (fixed; log scale)")
    ax.set_ylabel("share of 16 draws with rhythm score >= 0.5")
    ax.set_ylim(-0.03, 1.05)
    ax.legend(fontsize=6.5, frameon=False, loc="upper left")
    ax.set_title("Single DNb08 neurons in our MaleCNS model, at fixed currents", fontsize=8.5, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "fig6_dnb08_malecns_single")
    plt.close(fig)


FIGS = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig5": fig5, "fig6": fig6}

if __name__ == "__main__":
    for name in sys.argv[1:] or FIGS:
        FIGS[name]()
