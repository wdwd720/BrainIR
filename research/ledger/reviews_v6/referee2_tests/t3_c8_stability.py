"""t3. C8: does "stability under count noise predicts the third animal" survive treating noise-level BANC scores as ties?

Reads: replication_v1/S_tests.json (predictor, locked), pertype_v1/B1r.csv, the BANC sweep and tuned replicate tables,
gates_v6/TYPE_SETS_v6.json (the frozen 12 types). Post hoc sensitivity analyses of a pre-registered test; no words.
First reproduces the locked rho 0.571 and p 0.0286 with the rulebook's seed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from _common import AG, LEDGER, SETS, jload, screens, show, ts

S = screens()
pt = pd.DataFrame(jload("replication_v1/S_tests.json")["per_type"]).set_index("manc_type")
b1r = pd.read_csv(LEDGER / "pertype_v1" / "B1r.csv").set_index("manc_type")
types = [t for t in SETS["C8"]["primary"] if t in set(S["BS"]["type"]) and t in pt.index]
x = pt.loc[types, "mean_copy_score"].to_numpy(float)
y_sw = ts(S["BS"], types).reindex(types).to_numpy(float)
y_tu = ts(S["BT"], types).reindex(types).to_numpy(float)
NP = 100_000


def perm_p(xv, yv, seed=20261604):
    rho = AG.spearman(xv, yv)
    if not np.isfinite(rho):
        return {"rho": None, "p": None}
    rng = np.random.default_rng(seed)
    perm = np.array([AG.spearman(xv, rng.permutation(yv)) for _ in range(NP)])
    ge = np.sum(np.where(np.isnan(perm), True, perm >= rho - 1e-12))
    return {"rho": round(float(rho), 3), "p_one_sided": round(float((1 + ge) / (1 + NP)), 4)}


show("the 12 types", [{"type": t, "mean_copy_score (MANC copies)": round(a, 3), "B1r": round(float(b1r.loc[t, "score"]), 3),
                       "n_usable_B1r": int(b1r.loc[t, "n_usable"]), "BANC_sweep": round(b, 3), "BANC_tuned": round(c, 3)}
                      for t, a, b, c in sorted(zip(types, x, y_sw, y_tu), key=lambda r: -r[2])])
out = {"locked (reproduced)": perm_p(x, y_sw)}
for cut in (0.05, 0.10):
    out[f"BANC scores below {cut} tied at 0"] = perm_p(x, np.where(y_sw < cut, 0.0, y_sw))
bands = np.where(y_sw >= 0.5, 2, np.where(y_sw < 0.05, 0, 1)).astype(float)
out["BANC score as its rulebook band (non-driver < 0.05 / indeterminate / driver >= 0.5)"] = perm_p(x, bands)
out["outcome = the tuned BANC screen (the procedure that failed B4)"] = perm_p(x, y_tu)
out["outcome = tuned, below 0.05 tied at 0"] = perm_p(x, np.where(y_tu < 0.05, 0.0, y_tu))
show("rho and one-sided permutation p (100,000 permutations, seed 20261604)", out)
loo = {t: round(float(AG.spearman(np.delete(x, i), np.delete(y_sw, i))), 3) for i, t in enumerate(types)}
show("leave-one-type-out rho (sweep outcome)", loo)
show("number of BANC sweep scores below 0.05 / 0.07 / 0.10", {c: int((y_sw < c).sum()) for c in (0.05, 0.07, 0.10)})
