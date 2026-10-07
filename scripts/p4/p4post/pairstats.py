"""Paired statistics of the post-lock studies (benchmarks/causal_state_v1/PROTOCOL.md section 11; the conventions of
`brainir_causal.verdict.build_primary_family`).

UNITS. Synthetic: the system instance; a suite statistic is the MEAN over systems of a per-system value (a paired difference is
formed per system first), with an UNSTRATIFIED system bootstrap (`stats.stratified_system_boot`, 2,000 resamples). Within a system:
the identity cell (the class-balanced EE's family-jackknife-t interval, `evaluate.ee_cb` / `ee_cb_diff`); real networks are
reported per system. Never time steps.
FAILURES. A missing or non-finite per-system value is charged the worst admissible value of its metric (EE 10, SMS / ICG / gains +1,
MEV 10, success rates 0, ...) and counted (never dropped). Non-finite replicates count against the claim.
ONE-SIDED. p = (1 + count on the null side) / (1 + B) (`stats.boot_pvalue`); bounds are one-sided 95 % bounds; Holm within a
declared family (`stats.holm`). Everything a study labels "descriptive" is not multiplicity-corrected.
"""

from __future__ import annotations

import math

import numpy as np

from brainir_causal import evaluate as EV
from brainir_causal import stats as S
from brainir_causal.evalio import HELDOUT_KINDS, PRIMARY, SHORTCUT_KINDS, VERDICT_KINDS

ALPHA = S.ALPHA
N_BOOT = S.N_BOOT

#: per-system metrics read from a FULL evaluation result (harness.evaluate_job(...)["result"], private units included):
#: name -> (direction, worst admissible value, description)
METRICS = {
    "EE": ("lower", 10.0, "class-balanced EE on the verdict items (PROTOCOL 5.1 / 9 A)"),
    "EE_heldout": ("lower", 10.0, "class-balanced EE on held-out families (near / far / hidden; 9 H)"),
    "EE_infamily": ("lower", 10.0, "class-balanced EE on in-family items"),
    "EE_target": ("lower", 10.0, "class-balanced EE on target-shift items"),
    "EE_shortcut": ("lower", 10.0, "class-balanced EE on the shortcut subset B (target / near / far / hidden)"),
    "EE_pooled": ("lower", 10.0, "pooled EE at the primary horizon (descriptive)"),
    "post_nmse": ("lower", 10.0, "post-intervention trajectory NMSE at the primary horizon"),
    "obs_nmse": ("lower", 10.0, "passive rollout NMSE at the primary horizon (5.2)"),
    "SMS": ("lower", 1.0, "state mediation score (5.3)"),
    "SMS_x_res": ("lower", 1.0, "SMS with the residual microstate alone"),
    "SMS_id": ("lower", 1.0, "SMS with the intervention-ID features alone"),
    "ICG_y": ("lower", 1.0, "interventional closure gap, linear (5.4)"),
    "MEV": ("lower", 10.0, "microstate equivalence ratio (5.5; untestable = missing)"),
    "lift_success": ("higher", 0.0, "native lift success rate over all requests (5.7)"),
    "lift_consistency": ("lower", 10.0, "multiple-lift consistency, adjusted (5.7; untestable = missing)"),
    "false_confidence": ("lower", 1.0, "false-confidence rate on the verdict items (5.9 / 9 G)"),
    "coverage": ("higher", 0.0, "share of intervention items not abstained (descriptive)"),
    "interval_coverage90": ("higher", 0.0, "90 % interval coverage of y_sd at the primary horizon (descriptive)"),
    "k": ("none", float("nan"), "the model's latent dimension (descriptive)"),
}


def _f(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def units_of(res: dict | None) -> dict | None:
    return ((((res or {}).get("items") or {}).get("effects") or {}).get("_units")) or None


def metric(res: dict | None, name: str, n_boot: int = 200, seed: int = 0) -> float | None:
    """One per-system metric of a full evaluation result (None when missing / failed / untestable)."""
    if not res or res.get("error"):
        return None
    items = res.get("items") or {}
    eff = items.get("effects") or {}
    u = eff.get("_units")
    kinds = {"EE": VERDICT_KINDS, "EE_heldout": HELDOUT_KINDS, "EE_infamily": ("in",), "EE_target": ("target",),
             "EE_shortcut": SHORTCUT_KINDS}
    if name in kinds:
        if not u:
            return None
        return _f(EV.ee_cb(u, PRIMARY, kinds[name], "class", n_boot, seed).point)
    if name == "EE_pooled":
        return _f((eff.get(f"EE_{PRIMARY}") or {}).get("point"))
    if name == "post_nmse":
        return _f((eff.get(f"post_nmse_{PRIMARY}") or {}).get("point"))
    if name == "obs_nmse":
        return _f(((items.get("observational") or {}).get(f"obs_nmse_{PRIMARY}") or {}).get("point"))
    if name in ("SMS", "SMS_x_res", "SMS_id"):
        m = (res.get("mediation") or {}).get(name) or {}
        return 1.0 if m.get("failed") else _f(m.get("point"))
    if name == "ICG_y":
        c = (res.get("closure") or {}).get("ICG_y") or {}
        return 1.0 if c.get("failed") else _f(c.get("point"))
    if name == "MEV":
        mi = res.get("micro") or {}
        return _f((mi.get("MEV") or {}).get("point")) if mi.get("testable") else None
    if name == "lift_success":
        lf = res.get("lift") or {}
        return _f(lf.get("success_rate")) if "success_rate" in lf else None
    if name == "lift_consistency":
        cons = (res.get("lift") or {}).get("consistency") or {}
        adj = cons.get("adjusted")
        return _f(adj.get("point")) if isinstance(adj, dict) and cons.get("testable", True) else None
    if name == "false_confidence":
        cal = items.get("calibration") or {}
        return _f((cal.get("false_confidence_verdict") or {}).get("rate"))
    if name == "coverage":
        return _f((items.get("calibration") or {}).get("coverage"))
    if name == "interval_coverage90":
        return _f((((items.get("calibration") or {}).get("interval_coverage_90") or {}).get(PRIMARY) or {}).get("coverage"))
    if name == "k":
        return _f(res.get("k"))
    raise KeyError(name)


def suite_paired(a: dict, b: dict, systems: list[str], *, worst: float, direction: str = "lower", n_boot: int = N_BOOT,
                 seed: int = 0, missing_a: str = "worst", missing_b: str = "worst") -> dict:
    """Mean over `systems` of the per-system difference a - b (paired, UNSTRATIFIED system bootstrap). A missing / non-finite value
    is charged (and counted), never dropped: 'worst' = the metric's worst admissible value, 'neutral' = the other side's value (a
    difference of 0: no evidence either way). Callers choose the charge that counts AGAINST the claim under test (e.g. an ablated fit
    that crashed must not make the ablation look harmful). direction 'lower' (lower is better): 'a worse than b' = difference > 0."""
    diffs, ca, cb = {}, 0, 0
    for s in systems:
        va, vb = _f(a.get(s)), _f(b.get(s))
        if va is None:
            ca += 1
            va = vb if (missing_a == "neutral" and vb is not None) else float(worst)
        if vb is None:
            cb += 1
            vb = va if missing_b == "neutral" else float(worst)
        diffs[s] = va - vb
    if not diffs:
        return {"point": None, "n": 0}
    est = S.stratified_system_boot(diffs, None, np.mean, n_boot, seed)
    worse_alt = "greater" if direction == "lower" else "less"
    better_alt = "less" if direction == "lower" else "greater"
    return {"point": _f(est.point), "ci95": [_f(x) for x in est.ci95], "n": len(diffs), "n_charged_a": ca, "n_charged_b": cb,
            "lower95": _f(S.one_sided_lower(est.reps, 0.95)), "upper95": _f(S.one_sided_upper(est.reps, 0.95)),
            "p_a_worse": S.boot_pvalue(est.reps, 0.0, worse_alt), "p_a_better": S.boot_pvalue(est.reps, 0.0, better_alt),
            "direction": direction, "per_system": {s: _f(v) for s, v in diffs.items()}}


def suite_mean(vals: dict, systems: list[str], *, worst: float, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Mean over systems of one per-system value (unstratified system bootstrap; missing values charged `worst`)."""
    v, charged = {}, 0
    for s in systems:
        x = _f(vals.get(s))
        if x is None:
            x, charged = float(worst), charged + 1
        v[s] = x
    if not v:
        return {"point": None, "n": 0}
    est = S.stratified_system_boot(v, None, np.mean, n_boot, seed)
    return {"point": _f(est.point), "ci95": [_f(x) for x in est.ci95], "n": len(v), "n_charged": charged,
            "lower95": _f(S.one_sided_lower(est.reps, 0.95)), "upper95": _f(S.one_sided_upper(est.reps, 0.95)), "_reps": est.reps}


def system_ee_diff(res_a: dict | None, res_b: dict | None, kinds=VERDICT_KINDS, *, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Per-system PAIRED class-balanced EE_a - EE_b (identity cells; `evaluate.ee_cb_diff`; an item b did not score is charged the
    cap for b). Missing a: charged (reported, no estimate)."""
    ua, ub = units_of(res_a), units_of(res_b)
    if ua is None or ub is None:
        return {"point": None, "note": "missing evaluation units", "missing_a": ua is None, "missing_b": ub is None}
    est = EV.ee_cb_diff(ua, ub, PRIMARY, kinds, "class", n_boot, seed)
    if est.reps is None or not np.isfinite(est.point):
        return {"point": None, "note": "not computable", "n_cells": int(est.n_units or 0)}
    return {"point": _f(est.point), "ci95": [_f(x) for x in est.ci95], "lower95": _f(S.one_sided_lower(est.reps, 0.95)),
            "upper95": _f(S.one_sided_upper(est.reps, 0.95)), "p_a_worse": S.boot_pvalue(est.reps, 0.0, "greater"),
            "p_a_better": S.boot_pvalue(est.reps, 0.0, "less"), "n_cells": int(est.n_units or 0), "n_charged_b": int(est.n_charged or 0)}


def holm(pvals: dict[str, float], alpha: float = ALPHA) -> dict:
    return S.holm(pvals, alpha)


def strip_private(o):
    if isinstance(o, dict):
        return {k: strip_private(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip_private(v) for v in o]
    return o
