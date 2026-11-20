"""G3 v2 item 4' PREVIEW (PREREG v2 P2), computed BEFORE the v2 freeze; this preview decides item 4'. PREDICTION SIDE,
simulations only: run 1's stored G3 runs (`data/ledger/calibration/g3_v1/results.pkl`: both DNg100 at 380, T = 2 s, seeds
0..63) against the authors' run 33195857 traces (their Zenodo file, cached), with `g3v2_evaluate.item4p` (seed 20261202,
10,000 permutations). No fly data.

    uv run --project ledger --no-sync python ledger/scripts/g3v2_preview.py   # -> research/ledger/gates_v2/G3v2_PREVIEW.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import g3v2_evaluate as E  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402


def main() -> None:
    from brainir import paths

    src = data_dir() / "calibration" / "g3_v1" / "results.pkl"
    member = f"simulations/DNg100_Stim_fullManc/hyak/run_id={E.RUN}/ckpt/DNg100_Stim_fullManc_Rs.npz"
    auth = paths.data_root() / "raw" / "external" / "pugliese_2026_zenodo" / "DNg100_Stim_fullManc" / member
    g3, _ = E.load_g3(src, "g3|")
    pairs, k, c4p, variants = E.item4p(g3)
    out = {"what": "G3 v2 item 4' preview (PREREG v2 P2); decides item 4'",
           "inputs": {"g3_v1_results": "$DATA/ledger/calibration/g3_v1/results.pkl", "g3_v1_results_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                      "n_runs": len(g3), "authors_traces": f"$DATA/raw/external/pugliese_2026_zenodo/DNg100_Stim_fullManc/{member}",
                      "authors_traces_sha256": hashlib.sha256(auth.read_bytes()).hexdigest()},
           "perm_seed": E.PERM_SEED, "n_perm": E.N_PERM, "pairs": pairs, "k_evaluable": k,
           "governing_rule": "k >= 3 and every evaluable pair p >= 0.01 (no multiplicity correction)",
           "item4p_pass": c4p, "variants_reported": variants}
    d = RESEARCH / "gates_v2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "G3v2_PREVIEW.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"item4p_pass": c4p, "k": k, "variants": variants}))
    for kk, v in pairs.items():
        print(kk, {x: (round(y, 4) if isinstance(y, float) else y) for x, y in v.items()})


if __name__ == "__main__":
    main()
