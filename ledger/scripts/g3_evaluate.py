"""Gate G3, criteria 1-4 (PREREG section 9; thresholds committed in 8782b73 before this evaluation was run).

    uv run --project ledger --no-sync python ledger/scripts/g3_evaluate.py

Input: the G3 campaign (`calibrate_dng100.py g3 --n 64`: both DNg100 at 380, T = 2 s, seeds 0..63) and the authors' per-leg
tables (`authors.FILES` full_scores_alllegs / full_nmns_alllegs). Output: research/ledger/gates/G3_REPORT.{json,md}.
Criterion 5 (the B3 procedure on the DNg100 type) is evaluated from the B3 arm itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import authors as AU  # noqa: E402
from brainir_ledger import legs as L  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

AUTH_FRAC = {"T1L": 0.734, "T1R": 0.578, "T2L": 0.469, "T2R": 0.789, "T3L": 0.164, "T3R": 0.781}
AUTH_MED = {"T1L": 0.887, "T1R": 0.687, "T2L": 0.452, "T2R": 0.936, "T3L": 0.215, "T3R": 0.716}


def main() -> None:
    res = [r for r in read_log(data_dir() / "calibration" / "g3_v1" / "results.pkl") if "error" not in r]
    res.sort(key=lambda r: int(r["key"].rsplit("s", 1)[1]))
    files = AU.fetch()
    a_sc = pd.read_csv(files["full_scores_alllegs"], index_col=0)
    a_nm = pd.read_csv(files["full_nmns_alllegs"], index_col=0)
    # recompute the authors' numbers from their pinned files (the constants above must match)
    for leg in L.LEGS:
        assert abs(float((a_sc[leg] >= 0.5).mean()) - AUTH_FRAC[leg]) < 1e-3 and abs(float(a_sc[leg].median()) - AUTH_MED[leg]) < 1e-3
    ours = {leg: np.array([r["extras"]["legs"][leg]["score"] for r in res]) for leg in L.LEGS}
    nact = {leg: np.array([r["extras"]["legs"][leg]["n_active"] for r in res]) for leg in L.LEGS}
    per_leg = {leg: {"frac_ge_0_5": float((ours[leg] >= 0.5).mean()), "median": float(np.median(ours[leg])),
                     "mean": float(ours[leg].mean()), "median_active_mns": float(np.median(nact[leg])),
                     "authors_frac_ge_0_5": AUTH_FRAC[leg], "authors_median": AUTH_MED[leg],
                     "authors_mean": float(a_sc[leg].mean()), "authors_median_active_mns": float(a_nm[leg].median())} for leg in L.LEGS}
    c1 = all(v["frac_ge_0_5"] >= 0.10 for v in per_leg.values())
    c2 = all(abs(v["frac_ge_0_5"] - v["authors_frac_ge_0_5"]) <= 0.25 and abs(v["median"] - v["authors_median"]) <= 0.30
             for v in per_leg.values())
    hind = (per_leg["T3L"]["mean"] + per_leg["T3R"]["mean"]) / 2
    front = (per_leg["T1L"]["mean"] + per_leg["T1R"]["mean"]) / 2
    c3 = hind < front
    # coupling with leg signal v1 (E1 copies): columns 0..5 of leg_signals are v1 in LEGS order
    sig = [L.unpack_traces(r["extras"]["leg_signals"]) for r in res]
    pairs = {}
    for a, b in L.REPORTED_PAIRS:
        ia, ib = L.LEGS.index(a), L.LEGS.index(b)
        elig = [i for i, r in enumerate(res) if r["extras"]["legs"][a]["score"] >= 0.5 and r["extras"]["legs"][b]["score"] >= 0.5]
        pairs[f"{a}-{b}"] = L.coupling([sig[i][:, ia] for i in elig], [sig[i][:, ib] for i in elig], n_null=1000, seed=20261123)
    c4 = not any(v["coupled"] for v in pairs.values())
    out = {"gate": "G3", "config": {"stimulus": "both DNg100 at 380", "t_end": 2.0, "seeds": "0..63", "n": len(res)},
           "per_leg": per_leg, "hind_mean": hind, "front_mean": front, "coupling_v1": pairs,
           "criteria": {"1_every_leg_rhythmic": c1, "2_per_leg_agreement": c2, "3_hind_weaker": c3, "4_no_coupling": c4},
           "pass_1_to_4": bool(c1 and c2 and c3 and c4)}
    d = RESEARCH / "gates"
    d.mkdir(parents=True, exist_ok=True)
    (d / "G3_REPORT.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    md = ["# Gate G3: full nerve cord, two-sided DNg100 (authors' configuration)", "",
          "Both DNg100 at 380, T = 2 s, seeds 0..63, `manc_v1.2.3` full cord = the authors' matrix (LOG L10). Thresholds: PREREG section 9 "
          "(committed in 8782b73 before this run was evaluated).", "",
          "| leg | frac >= 0.5 (ours / authors) | median score (ours / authors) | median active MNs (ours / authors) |", "|---|---|---|---|"]
    for leg, v in per_leg.items():
        md.append(f"| {leg} | {v['frac_ge_0_5']:.3f} / {v['authors_frac_ge_0_5']:.3f} | {v['median']:.3f} / {v['authors_median']:.3f} | "
                  f"{v['median_active_mns']:.0f} / {v['authors_median_active_mns']:.0f} |")
    md += ["", f"Hind mean score {hind:.3f} vs front {front:.3f}.", "", "Coupling (leg signal v1, PREREG 4.7):", "",
           "| pair | n | R | null mean R | p | coupled |", "|---|---|---|---|---|---|"]
    for k, v in pairs.items():
        md.append(f"| {k} | {v['n']} | {v['R'] if v['R'] is None else round(v['R'], 3)} | "
                  f"{v['null_mean_R'] if v['null_mean_R'] is None else round(v['null_mean_R'], 3)} | {v['p']} | {v['coupled']} |")
    md += ["", "Criteria: " + ", ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in out["criteria"].items()),
           f"**G3 items 1-4: {'PASS' if out['pass_1_to_4'] else 'FAIL'}.** Item 5 is checked on the B3 arm."]
    (d / "G3_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
