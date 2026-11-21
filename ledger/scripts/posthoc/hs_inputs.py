"""Input hashes of the wiring-baseline tables (Stage 2 review, minor finding 4): the H-S tables' provenance records the network name
and size only, so this records, once, the SHA-256 of every input they are a function of: the full-cord matrix (canonical CSR arrays),
the size vector, the motor-neuron positions and pools (motor map file), the unit list, the members of every unit's primary group, and
of every H-S predicted.csv. Writes gates_v3/HS_INPUTS.json once.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/hs_inputs.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE.parent))
import gha3  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import groups_h1 as GH  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> None:
    fc = N.full_cord()
    W = sp.csr_matrix(fc.W, dtype=np.float64)
    W.sum_duplicates()
    W.sort_indices()
    groups = gha3._unit_groups(fc, "primary")
    out = {"W_csr_sha256": h(W.indptr.astype(np.int64).tobytes() + W.indices.astype(np.int64).tobytes() + W.data.tobytes()),
           "W_shape": list(W.shape), "W_nnz": int(W.nnz),
           "sizes_sha256": h(np.asarray(fc.sizes, dtype=np.float64).tobytes()),
           "motor_map_sha256": h((RESEARCH / "motor_map" / "MOTOR_MAP_v1.csv").read_bytes()),
           "mn_positions_sha256": h(json.dumps(GH.mn_positions(GH.load_motor_map())).encode()),
           "units_sha256": h((RESEARCH / "hl_units" / "UNITS_v1.csv").read_bytes()),
           "primary_groups_sha256": h(json.dumps(groups, sort_keys=True).encode()),
           "tables": {a: h((RESEARCH / "predictions_h1" / a / "predicted.csv").read_bytes()) for a in GH.HS_ARMS}}
    with open(RESEARCH / "gates_v3" / "HS_INPUTS.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "tables"}))


if __name__ == "__main__":
    main()
