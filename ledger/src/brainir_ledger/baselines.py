"""Arm S: anatomical baselines, no simulation (PREREG section 3.5). Prediction side; pure functions of the network.

All sums run over a group's members j (the excitatory members of a type, the same groups as A1/B1). ``C`` = observed unsigned
counts (floor 5, autapses removed), ``W`` = signed counts (paper signs), both post x pre; MN = the read-out motor neurons.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp

BASELINES = ["S1_direct_mn", "S2_twohop_signed", "S3_twohop_abs", "S4_total_out", "S5_out_partners", "S6_premotor", "S7_n_members",
             "S8_informed"]


def compute(C: sp.csr_matrix, W: sp.csr_matrix, mn: np.ndarray, groups: dict[str, list[int]], core_positions: list[int]) -> pd.DataFrame:
    C = sp.csr_matrix(C, dtype=np.float64)
    W = sp.csr_matrix(W, dtype=np.float64)
    A = abs(W)
    n = C.shape[0]
    mn = np.asarray(mn, bool)
    mn_row = mn.astype(np.float64)
    # premotor: non-MN neurons with at least one (floor-5) connection onto an MN
    onto_mn = np.asarray(C[mn, :].sum(axis=0)).ravel()
    premotor = (onto_mn > 0) & ~mn
    core = np.zeros(n, bool)
    core[list(core_positions)] = True
    wt_mn = W.T @ mn_row     # (W^T 1_MN)[k] = sum_m W[m, k]
    at_mn = A.T @ mn_row
    rows = []
    for t, members in sorted(groups.items()):
        idx = np.asarray(members, dtype=np.int64)
        col_c = np.asarray(C[:, idx].sum(axis=1)).ravel()       # synapses from the group onto each neuron
        col_w = np.asarray(W[:, idx].sum(axis=1)).ravel()
        col_a = np.asarray(A[:, idx].sum(axis=1)).ravel()
        rows.append({"manc_type": t,
                     "S1_direct_mn": float(col_c[mn].sum()),
                     "S2_twohop_signed": float(wt_mn @ col_w),
                     "S3_twohop_abs": float(at_mn @ col_a),
                     "S4_total_out": float(col_c.sum()),
                     "S5_out_partners": int((col_c > 0).sum()),
                     "S6_premotor": float(col_c[premotor].sum()),
                     "S7_n_members": int(len(idx)),
                     "S8_informed": float(col_c[core].sum())})
    return pd.DataFrame(rows)[["manc_type", *BASELINES]]
