"""Determinism gate of tuner v2 (PREREG v2 P1): 100 random jobs per arm (B1r, B2r; seed 20261205), re-run as a separate GitHub
campaign `det` and compared by digest with the main campaigns. PREDICTION SIDE. A new file, so the frozen `gha.py` (P4b) is
not amended: it registers the builder and hands over to `gha.py`'s command line.

    uv run --project ledger --no-sync python ledger/scripts/gha_det.py pack det --k 1 --chunk-jobs 50
    uv run --project ledger --no-sync python ledger/scripts/gha.py publish det
    uv run --project ledger --no-sync python ledger/scripts/gha.py collect det --wait
    uv run --project ledger --no-sync python ledger/scripts/gha_det.py compare   # -> research/ledger/gates_v2/DETERMINISM_v2.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha as G  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

DET_SEED, N_PER_ARM = 20261205, 100


def build_det(k):
    AR, MC, (fl, g1), (net2, g2) = G._nets()
    rng = np.random.default_rng(DET_SEED)
    out = []
    for arm, net, groups in (("B1r", fl, g1), ("B2r", net2, g2)):
        jobs = G._v2_jobs(arm, groups, k, AR, MC)
        pick = sorted(int(i) for i in rng.choice(len(jobs), N_PER_ARM, replace=False))
        out.append(({"W": net.W, "sizes": net.sizes, "readout": net.readout}, [jobs[i] for i in pick]))
    return out, "arms"


def compare() -> None:
    det = {r["key"]: r for r in read_log(data_dir() / "arms" / "GHA_det" / "results.pkl")}
    main = {}
    for name in ("b1r", "b2r"):
        main.update({r["key"]: r for r in read_log(data_dir() / "arms" / f"GHA_{name}" / "results.pkl")})
    rows = {"compared": 0, "identical": 0, "different": [], "missing_in_main": [], "errors": []}
    for key, r in sorted(det.items()):
        if "error" in r:
            rows["errors"].append(key)
            continue
        m = main.get(key)
        if m is None:
            rows["missing_in_main"].append(key)
            continue
        rows["compared"] += 1
        if m.get("digest") == r.get("digest"):
            rows["identical"] += 1
        else:
            rows["different"].append(key)
    rows["by_arm"] = {a: sum(1 for k in det if k.startswith(f"{a}|")) for a in ("B1r", "B2r")}
    rows["pass"] = rows["compared"] == 2 * N_PER_ARM and rows["identical"] == rows["compared"] and not rows["errors"]
    rows["rule"] = "PREREG v2 P1: 100 random jobs per arm (seed 20261205) re-run; identical digests"
    (RESEARCH / "gates_v2" / "DETERMINISM_v2.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in rows.items()}))


G.BUILDERS["det"] = build_det

if __name__ == "__main__":
    if sys.argv[1:2] == ["compare"]:
        compare()
    else:
        G.main()
