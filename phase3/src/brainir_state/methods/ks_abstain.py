"""Generic abstention rule shared by the ks_* methods (stated in notes/ks_methods.md).

Inputs: the method's own dimension curve (validation rollout NMSE per candidate k), the dimension-rule output and N_observed.
Abstain with "no compact state under current evidence" when
  (a) the selected k is not compact: k > max(1, N_observed / 5)  (the benchmark's compactness bound, also a sensible generic cap), or
  (b) the curve has not reached a plateau inside the ladder: the best k is the largest candidate AND the error still fell by more than
      the tolerance over the last step of the ladder, or
  (c) the state carries almost no predictive information: the best validation NMSE is >= 0.6 (60 % of the readout variance
      unexplained at the validation horizon).
"dimension unresolved in [a, b]" is reported (without a compact-state abstention) when the plausible range spans more than a factor 2.
"""

from __future__ import annotations

import numpy as np


def abstention(curve: list[dict], sel: dict, n_obs: int, forced: bool = False, err_key: str = "val_nmse",
               max_nmse: float = 0.6) -> dict:
    ks = [c["k"] for c in curve]
    errs = np.array([c[err_key] for c in curve], float)
    out = {"no_compact_state": False, "dimension_unresolved": None, "causal_equivalence_failed": False, "reason": ""}
    if forced or not ks:
        out["reason"] = "k forced by config" if forced else "no curve"
        return out
    reasons = []
    k = sel["k"]
    if k > max(1, n_obs / 5):
        reasons.append(f"selected k={k} exceeds N/5={n_obs / 5:.1f}")
    if sel["best_k"] == max(ks) and len(ks) > 1:
        i = ks.index(max(ks))
        if np.isfinite(errs[i - 1]) and errs[i - 1] - errs[i] > sel["tol"]:
            reasons.append("validation error still falling at the largest k (no plateau)")
    best = float(np.nanmin(errs)) if np.isfinite(errs).any() else float("inf")
    if best >= max_nmse:
        reasons.append(f"best validation NMSE {best:.2f} >= {max_nmse}: no predictive state found")
    if reasons:
        out["no_compact_state"] = True
        out["reason"] = "; ".join(reasons)
    else:
        lo, hi = sel["range"]
        if hi > 2 * max(1, lo):
            out["dimension_unresolved"] = [int(lo), int(hi)]
            out["reason"] = "plausible range spans more than a factor 2"
    return out
