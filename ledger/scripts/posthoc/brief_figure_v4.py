"""The brief's one figure (RUN4_PROMPT section 8; PREREG v4 Part F): agreement across the two sides and across the two flies for the
wiring, the simulation and each fix, with ceilings marked. Every number is read from a locked run 4 file:
  - wiring: `reliability_v2/WIRING_A4.json` (two-hop signed and unsigned summaries, full Spearman; deterministic, ceiling 1);
  - simulation, unfixed and each fix: `reliability_v2/C.json` (primary type set; seeds 0..7; cross-half Spearman rho_x and matched
    ceiling c; left-right = mean over the two flies, cross-fly = mean of the two same-side pairs).
Writes results/run4/fig_agreement.png and fig_agreement.json (the plotted numbers).

    uv run --project ledger --no-sync --with matplotlib==3.9.2 python ledger/scripts/posthoc/brief_figure_v4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402

REL2 = RESEARCH / "reliability_v2"
OUT = RESEARCH / "results" / "run4"
FIX_LABEL = {"unfixed": "model", "1": "1 dose sweep", "2": "2 pooled read-out", "3a": "3a floor 1", "3b": "3b floor 3",
             "4": "4 symmetrised", "5a": "5a pooled (side)", "5b": "5b pooled (both)", "6": "6 input-norm.", "7": "7 consensus",
             "8": "8 all", "9": "9 combined"}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def rows() -> list[dict]:
    w = json.loads((REL2 / "WIRING_A4.json").read_text())["summaries_S1_S7_full_spearman"]
    out = []
    for key, name in (("S2_twohop_signed", "wiring: two-hop signed"), ("S3_twohop_abs", "wiring: two-hop unsigned")):
        lr = _mean([w["MANC-L vs MANC-R"][key]["spearman"], w["MaleCNS-L vs MaleCNS-R"][key]["spearman"]])
        cf = _mean([w["MANC-L vs MaleCNS-L"][key]["spearman"], w["MANC-R vs MaleCNS-R"][key]["spearman"]])
        out.append({"label": name, "left_right": lr, "left_right_ceiling": 1.0, "cross_fly": cf, "cross_fly_ceiling": 1.0, "kind": "wiring"})
    c = json.loads((REL2 / "C.json").read_text())["primary"]
    for fix in ["unfixed", "1", "2", "3a", "3b", "4", "5a", "5b", "6", "7", "8", "9"]:
        r = c.get(fix) or {}
        if "left_right" not in r:
            out.append({"label": FIX_LABEL[fix], "kind": "fix", "note": r.get("note", "not screened")})
            continue
        lr, cf = r["left_right"], r.get("cross_fly", {})
        out.append({"label": FIX_LABEL[fix], "kind": "model" if fix == "unfixed" else "fix", "passes": r.get("passes"),
                    "left_right": lr.get("rho_x_mean"), "left_right_ceiling": lr.get("c_mean"),
                    "cross_fly": cf.get("rho_x_mean"), "cross_fly_ceiling": cf.get("c_mean")})
    return out


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rs = rows()
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    xs = list(range(len(rs)))
    for x, r in zip(xs, rs):
        for key, dx, color, marker in (("left_right", -0.13, "#1f77b4", "o"), ("cross_fly", 0.13, "#d62728", "s")):
            v, c = r.get(key), r.get(f"{key}_ceiling")
            if v is None:
                continue
            ax.plot(x + dx, v, marker=marker, color=color, ms=7, zorder=3)
            if c is not None and r["kind"] != "wiring":
                ax.hlines(c, x + dx - 0.1, x + dx + 0.1, color=color, lw=2, zorder=2)
        if r.get("note"):
            ax.text(x, 0.02, "not\nscreened", ha="center", va="bottom", fontsize=7, color="0.4")
    ax.set_xticks(xs)
    ax.set_xticklabels([r["label"] for r in rs], rotation=40, ha="right", fontsize=8)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Spearman agreement of type scores")
    ax.plot([], [], "o", color="#1f77b4", label="left vs right (mean of two flies)")
    ax.plot([], [], "s", color="#d62728", label="MANC vs MaleCNS (same side, mean of two sides)")
    ax.hlines([], 0, 0, color="0.3", lw=2, label="matched ceiling (split-half; wiring is deterministic: 1)")
    ax.legend(fontsize=7, loc="upper right", frameon=False)
    ax.set_title("Agreement across sides and flies: wiring, the model, and each fix (primary types, seeds 0-7)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_agreement.png", dpi=160)
    with open(OUT / "fig_agreement.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"source": ["reliability_v2/WIRING_A4.json", "reliability_v2/C.json"], "rows": rs}, indent=1) + "\n")
    print("wrote results/run4/fig_agreement.png")


if __name__ == "__main__":
    main()
