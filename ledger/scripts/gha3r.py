"""Reliability study campaigns (PREREG v3 Part R; RUN3_PROMPT section 8): builders for R3 (weight noise) and R4 (left vs right),
registered with the frozen `gha.py` through `gha3.py`. Both simulate descending-neuron types on the MANC front-leg network with
B1r's procedure (run 2's tuner v2, K = 1, B1 screen), seeds 0..3, and refuse before the tag `ledger-prereg-v3` (hard limit 2).

    uv run --project ledger --no-sync python ledger/scripts/gha3r.py pack r3-51-run3 --chunk-jobs 160 --k 51   # sigma 5 %, noise seed 1
    uv run --project ledger --no-sync python ledger/scripts/gha3r.py pack r4-run3 --chunk-jobs 160
    uv run --project ledger --no-sync python ledger/scripts/gha3.py publish3 r3-51-run3 ; ... collect3 ...
R3 networks: every nonzero count times max(1 + sigma z, 0.01), z ~ Normal(0, 1) from `default_rng(noise seed)` in canonical CSR
order (the same z for every sigma of a noise seed); signs kept. k encodes sigma (percent) and the noise seed: 51, 52, 53, 101, ...
R4: side = soma side, else the root side of the authors' full-cord node table (by bodyId); left members with the 72 left front-leg
motor neurons as read-out, right members with the 72 right ones; types with members on both sides only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha3  # noqa: E402  (registers run 3's builders; its main is used for pack)

from brainir.compute.backend import Shared  # noqa: E402

G = gha3.G
R_SEEDS = [0, 1, 2, 3]
SIGMAS = (5, 10, 20)
NOISE_SEEDS = (1, 2, 3)


def noisy(W, sigma: float, noise_seed: int) -> sp.csr_matrix:
    A = sp.csr_matrix(W, copy=True, dtype=np.float64)
    A.sum_duplicates()
    A.sort_indices()
    z = np.random.default_rng(int(noise_seed)).normal(size=A.nnz)
    A.data = A.data * np.maximum(1.0 + sigma * z, 0.01)
    return A


def build_r3(k):
    gha3.require_freeze("R3")
    sigma_pct, nseed = divmod(int(k), 10)
    if sigma_pct not in SIGMAS or nseed not in NOISE_SEEDS:
        raise SystemExit(f"--k {k}: sigma {sigma_pct} % / noise seed {nseed} not in the plan")
    AR, MC, (fl, g1), _ = G._nets()
    arm = f"R3-s{sigma_pct}-n{nseed}"
    jobs = G._v2_jobs(arm, g1, 1, AR, MC, seeds=R_SEEDS)
    return [({"W": noisy(fl.W, sigma_pct / 100.0, nseed), "sizes": fl.sizes, "readout": fl.readout}, jobs)], "reliability"


def sides(fl) -> np.ndarray:
    from brainir_ledger import networks as N  # noqa: PLC0415

    root = N.full_cord().table.set_index("bodyId")["rootSide"]
    soma = fl.table["somaSide"]
    return np.where(soma.isin(["LHS", "RHS"]), soma, fl.table["bodyId"].map(root)).astype(object)


def r4_groups(fl, g1) -> dict[str, dict[str, list[int]]]:
    s = sides(fl)
    out = {"L": {}, "R": {}}
    for t, m in sorted(g1.items()):
        left, right = [i for i in m if s[i] == "LHS"], [i for i in m if s[i] == "RHS"]
        if left and right:
            out["L"][t], out["R"][t] = left, right
    return out


def build_r4(k=None):
    gha3.require_freeze("R4")
    AR, MC, (fl, g1), _ = G._nets()
    mn_side = fl.table["somaSide"].to_numpy()
    shared = {"W": fl.W, "sizes": fl.sizes, "readout_L": fl.readout & (mn_side == "LHS"), "readout_R": fl.readout & (mn_side == "RHS")}
    jobs = []
    for side, groups in r4_groups(fl, g1).items():
        jobs += [dict(j, readout=Shared(f"readout_{side}")) for j in G._v2_jobs(f"R4{side}", groups, 1, AR, MC, seeds=R_SEEDS)]
    return [(shared, jobs)], "reliability"


R_BUILDERS = {"r3": build_r3, "r4": build_r4}
G.BUILDERS.update(R_BUILDERS)
gha3.V3_BUILDERS.update(R_BUILDERS)  # published with publish3 (run 3's runner passes group_v2 jobs to run 2's entry point)

if __name__ == "__main__":
    G.main()
