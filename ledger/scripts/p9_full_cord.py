"""PREREG v3 P9.1 "full cord accepted": run 2's G3 v2 items 1-3 and 5 recomputed exactly as `g3v2_evaluate.py` does (imported,
never re-run, because it writes into the frozen gates_v2/), on the stored DNg100 runs; item 5 also on P7's regression jobs (the B3
procedure on DNg100 through run 3's runner). Writes research/ledger/gates_v3/P9_FULL_CORD.json once. DNg100 only; no hemilineage.

    uv run --project ledger --no-sync python ledger/scripts/p9_full_cord.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
import g3v2_evaluate as GE  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import legs as L  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402


def item5(rs: list[dict]) -> dict:
    acc384 = sum(1 for r in rs if r.get("usable") and abs(float(r.get("current") or 0) - 384.0) < 1e-6)
    front = [r["extras"]["legs"]["front"]["score"] for r in rs if r.get("usable")]
    fm = float(np.mean(front)) if front else None
    return {"n": len(rs), "accepted_at_384": acc384, "front_pair_mean_score": fm,
            "pass": bool(len(rs) == 16 and acc384 >= 14 and fm is not None and fm >= 0.5)}


def main() -> None:
    g3, res = GE.load_g3(data_dir() / "calibration" / "GHA_g3v2" / "results.pkl", "g3v2|")
    it5 = [r for r in res if r["key"].startswith("g3v2item5|")]
    ours = {leg: np.array([r["extras"]["legs"][leg]["score"] for r in g3]) for leg in L.LEGS}
    per_leg = {leg: {"frac_ge_0_5": float((ours[leg] >= 0.5).mean()), "median": float(np.median(ours[leg])),
                     "authors_frac_ge_0_5": GE.G1.AUTH_FRAC[leg], "authors_median": GE.G1.AUTH_MED[leg], "mean": float(ours[leg].mean())}
               for leg in L.LEGS}
    c1 = all(v["frac_ge_0_5"] >= 0.10 for v in per_leg.values())
    c2 = all(abs(v["frac_ge_0_5"] - v["authors_frac_ge_0_5"]) <= 0.25 and abs(v["median"] - v["authors_median"]) <= 0.30 for v in per_leg.values())
    c3 = (per_leg["T3L"]["mean"] + per_leg["T3R"]["mean"]) / 2 < (per_leg["T1L"]["mean"] + per_leg["T1R"]["mean"]) / 2
    p7 = [r for r in read_log(data_dir() / "calibration" / "GHA_p7-run3" / "results.pkl") if r["key"].startswith("p7reg|DNg100|")]
    rep2 = RESEARCH / "gates_v2" / "G3v2_REPORT.json"
    out = {"what": "PREREG v3 P9.1: run 2's G3 v2 items 1-3 and 5 on the build used (unchanged since run 2)",
           "item1_every_leg_rhythmic": c1, "item2_per_leg_agreement": c2, "item3_hind_weaker": c3,
           "item5_stored_g3v2": item5(it5), "item5_p7_regression_run3_runner": item5(p7), "per_leg": per_leg,
           "run2_report": {"file": "gates_v2/G3v2_REPORT.json", "sha256": hashlib.sha256(rep2.read_bytes()).hexdigest(),
                           "criteria": json.loads(rep2.read_text())["criteria"]}}
    out["pass"] = bool(c1 and c2 and c3 and out["item5_stored_g3v2"]["pass"] and out["item5_p7_regression_run3_runner"]["pass"])
    p = RESEARCH / "gates_v3" / "P9_FULL_CORD.json"
    with open(p, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("per_leg",)}, default=float))


if __name__ == "__main__":
    main()
