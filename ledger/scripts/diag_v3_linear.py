"""The linearised full-cord model (PREREG v3 P3, arm H-S-lin), wiring only: A = diag(a) Wb with the model's mean size-scaled gains
`a` (`mean_neuron_params`) and its own coupling (`scaled_weights`: b = 0.03 for both signs). Reports the largest eigenvalue moduli
of A (stability of the fixed point x = (I - A)^-1 (a * s)) and checks that I - A factorises and solves (residual) for one allowed
right-hand side (the DNg100 pair). No simulation and no hemilineage group.

    uv run --project ledger --no-sync python ledger/scripts/diag_v3_linear.py   # -> research/ledger/diag_v3/LINEAR_DIAG.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir.sim.model import ModelConfig, mean_neuron_params, scaled_weights  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import groups_h1 as GH  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402


def main() -> None:
    fc = N.full_cord()
    t0 = time.time()
    A = GH.linear_operator(fc.W, fc.sizes)
    vals = eigs(A, k=4, which="LM", return_eigenvectors=False, maxiter=5000, tol=1e-8)
    mods = sorted((float(abs(v)) for v in vals), reverse=True)
    dng = [int(i) for i in fc.table.index[fc.table["type"] == "DNg100"]]
    lu, info = GH.linear_factor(fc.W, fc.sizes)
    a = mean_neuron_params(ModelConfig(), fc.n, fc.sizes).a
    s = np.zeros(fc.n)
    s[dng] = 1.0
    x = lu.solve(a * s)
    res = float(np.linalg.norm((sp.identity(fc.n, format="csr") - A) @ x - a * s) / np.linalg.norm(a * s))
    out = {"what": "linearised full-cord model A = diag(a) * b * W (mean size-scaled gains, b = 0.03); wiring only",
           "n": fc.n, "nnz_W": int(fc.W.nnz), "largest_eigenvalue_moduli": [round(m, 4) for m in mods],
           "spectral_radius": round(mods[0], 4), "fixed_point_stable": mods[0] < 1.0,
           "lu": info, "dng100_test_relative_residual": res, "seconds": round(time.time() - t0, 1),
           "consequence": "x = (I - A)^-1 (a * s) exists (I - A is invertible) but is an unstable fixed point of the linear dynamics "
                          "when the spectral radius exceeds 1; H-S-lin is computed anyway as the prompt's 'steady state of the "
                          "linearised model' (PREREG v3 P3)"}
    d = RESEARCH / "diag_v3"
    d.mkdir(parents=True, exist_ok=True)
    (d / "LINEAR_DIAG.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
