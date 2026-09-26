"""Per-system verdicts, the Phase 4 conclusion rule and the primary statistical family (benchmarks/causal_state_v1/PROTOCOL.md sections
9 and 11; goal5 sections 71, 92.51, 94).

Criteria (all on the hidden test items of one system, primary horizon):
    A intervention prediction   upper CI of EE (all items, abstentions as no effect) < 1 - delta_A
    B shortcut                  upper CI of the paired EE_method - EE_idshortcut < 0 on target-shift and held-out-family items
    C full-state                upper CI of the paired EE_method - EE_fullbound <= delta_C
    D mediation                 upper CI of SMS <= tau_SMS (binding only if the calibration's power rule admits it)
    E closure / microstate      upper CI of ICG_y <= tau_ICG (binding only if admitted) AND upper CI of MEV <= tau_MEV
                                (MEV untestable -> E untested, a category of its own)
    F dimension                 compact (full and synthetic systems; mechanisms are not judged on compactness) and stable
    G false confidence          rate <= tau_FC (a model with no covered detectable item makes no confident claim: passes)
    H family generalisation     upper CI of EE on held-out-family items < 1 - delta_A and EE_heldout - EE_infamily <= delta_H
Categories: "causal state supported" (every binding criterion holds); "causal state supported (microstate equivalence untestable)"
(every binding criterion holds except that E could not be tested; never merged with the first); "partially supported" (A holds and at
least one binding criterion of D, E, H holds); "unsupported" (otherwise); "declared no compact causal state" (the method's own
abstention, recorded as such and never converted into a verdict it did not claim; correct on non-compressible types, a false alarm
elsewhere). A criterion whose inputs are missing is "untested" (None) and blocks "supported".

RESOLUTIONS (documented for the orchestrator):
- held-out-family items = shift kinds near, far and hidden (hidden-only families); in-family items = shift kind "in"; the B subset =
  target, near, far and hidden;
- H's second part compares POINT estimates (as written in the protocol);
- P_m counts only "causal state supported" (the E-untested category is reported beside, not merged);
- real part: "SUPPORTED (E untested)" counts as at least PARTIAL, not as SUPPORTED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from . import stats as S
from .evaluate import paired_ee_diff

SUPPORTED = "causal state supported"
SUPPORTED_E_UNTESTED = "causal state supported (microstate equivalence untestable)"
PARTIAL = "partially supported"
UNSUPPORTED = "unsupported"
DECLARED = "declared no compact causal state"
AT_LEAST_PARTIAL = (SUPPORTED, SUPPORTED_E_UNTESTED, PARTIAL)
HELDOUT_KINDS = ("near", "far", "hidden")
SHORTCUT_KINDS = ("target", "near", "far", "hidden")


@dataclass
class Tolerances:
    delta_A: float
    delta_C: float
    tau_SMS: float
    tau_ICG: float
    tau_MEV: float
    delta_H: float
    tau_FC: float = 0.2
    sms_binds: bool = True
    icg_binds: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> Tolerances:
        keys = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in keys})

    def as_dict(self) -> dict:
        return asdict(self)


def _upper(e: dict | None) -> float:
    if not e:
        return float("nan")
    ci = e.get("ci95") or [float("nan"), float("nan")]
    return float(ci[1]) if ci[1] is not None else float("nan")


def _crit(passed, value=None, threshold=None, binding: bool = True, note: str | None = None) -> dict:
    return {"pass": None if passed is None else bool(passed), "value": value, "threshold": threshold, "binding": bool(binding),
            "note": note}


def system_verdict(m: dict, tol: Tolerances, *, compact_judged: bool = True) -> dict:
    """Criteria A-H and the category for one system. m: see `collect_metrics` for the keys."""
    c: dict[str, dict] = {}
    ub = _upper(m.get("EE"))
    # a missing or non-finite EE means no usable test item (every scored item has a finite, capped EE): a missing input, not a failure
    c["A"] = _crit(bool(ub < 1 - tol.delta_A) if np.isfinite(ub) else None, m.get("EE"), 1 - tol.delta_A,
                   note=None if np.isfinite(ub) else "no usable test items")
    b = m.get("EE_vs_idshortcut")
    ub = _upper(b)
    c["B"] = _crit(None if b is None or not np.isfinite(ub) else ub < 0, b, 0.0, note=None if b else "no shortcut comparison")
    cc = m.get("EE_vs_fullbound")
    ub = _upper(cc)
    c["C"] = _crit(None if cc is None or not np.isfinite(ub) else ub <= tol.delta_C, cc, tol.delta_C)
    sms = m.get("SMS")
    ub = _upper(sms)
    c["D"] = _crit(None if sms is None or not np.isfinite(ub) else ub <= tol.tau_SMS, sms, tol.tau_SMS, binding=tol.sms_binds)
    icg, mev = m.get("ICG_y"), m.get("MEV")
    ub_i, ub_m = _upper(icg), _upper(mev)
    icg_pass = None if icg is None or not np.isfinite(ub_i) else bool(ub_i <= tol.tau_ICG)
    # MEV states: "missing" (no microstate result: a missing input), "untestable" (the 5.5 rules), else pass / fail (a testable
    # result with a non-finite MEV, e.g. failed encodings on the pool, is a failure of the model)
    mev_testable = m.get("MEV_testable")
    if mev is None or mev_testable is None:
        mev_state, mev_pass = "missing", None
    elif not mev_testable:
        mev_state, mev_pass = "untestable", None
    else:
        mev_state, mev_pass = "tested", (bool(ub_m <= tol.tau_MEV) if np.isfinite(ub_m) else False)
    parts = [mev_pass] + ([icg_pass] if tol.icg_binds else [])
    if any(p is False for p in parts):
        e_pass, e_note = False, None
    elif mev_state == "missing" or (tol.icg_binds and icg_pass is None):
        e_pass, e_note = None, "inputs missing"
    elif mev_state == "untestable":
        e_pass, e_note = None, "microstate equivalence untestable"
    else:
        e_pass, e_note = True, None
    c["E"] = _crit(e_pass, {"ICG_y": icg, "MEV": mev, "MEV_testable": mev_testable}, {"tau_ICG": tol.tau_ICG, "tau_MEV": tol.tau_MEV},
                   note=e_note)
    c["E"]["icg_pass"], c["E"]["mev_pass"], c["E"]["mev_state"], c["E"]["icg_binding"] = icg_pass, mev_pass, mev_state, tol.icg_binds
    dim = m.get("dimension") or {}
    stable, compact = dim.get("stable"), dim.get("compact")
    if compact_judged:
        f_pass = None if (stable is None or compact is None) else (bool(compact) and bool(stable))
    else:
        f_pass = None if stable is None else bool(stable)
    c["F"] = _crit(f_pass, dim, None, note=None if compact_judged else "compactness not judged (mechanism system)")
    fc = m.get("false_confidence") or {}
    rate, n_fc = fc.get("rate", float("nan")), fc.get("n", 0)
    c["G"] = _crit(True if n_fc == 0 else (np.isfinite(rate) and rate <= tol.tau_FC), fc, tol.tau_FC,
                   note="no covered item with a detectable effect" if n_fc == 0 else None)
    eh, ei = m.get("EE_heldout"), m.get("EE_infamily")
    ub = _upper(eh)
    gap = float((eh or {}).get("point", np.nan)) - float((ei or {}).get("point", np.nan))
    # held-out and in-family items are both needed (the gap): either missing is a missing input
    h_pass = None if (not np.isfinite(ub) or not np.isfinite(gap)) else bool(ub < 1 - tol.delta_A and gap <= tol.delta_H)
    c["H"] = _crit(h_pass, {"EE_heldout": eh, "EE_infamily": ei}, {"ee_max": 1 - tol.delta_A, "delta_H": tol.delta_H})
    out = {"criteria": c}
    declared = bool(m.get("declared_no_compact", False))
    truth_nc = m.get("truth_noncompressible")
    if declared:
        out["category"] = DECLARED
        out["declaration_correct"] = None if truth_nc is None else bool(truth_nc)
        return out
    binding = {k: v for k, v in c.items() if v["binding"]}
    others_ok = all(v["pass"] is True for k, v in binding.items() if k != "E")
    if others_ok and binding["E"]["pass"] is True:
        cat = SUPPORTED
    elif others_ok and binding["E"]["pass"] is None and binding["E"]["note"] == "microstate equivalence untestable":
        cat = SUPPORTED_E_UNTESTED
    elif c["A"]["pass"] is True and any(c[k]["binding"] and c[k]["pass"] is True for k in ("D", "E", "H")):
        cat = PARTIAL
    else:
        cat = UNSUPPORTED
    out["category"] = cat
    if truth_nc is True:
        out["missed_noncompressible"] = True
    return out


# ------------------------------------------------------------------------------------------------------------ inputs
def _subset_ee(units: dict, kinds: tuple[str, ...], n_boot: int, seed: int) -> dict | None:
    sel = [i for i, s in enumerate(units["shift"]) if s.split(":", 1)[0] in kinds]
    if not sel:
        return None
    est = S.boot_ratio([units["num_medium"][i] for i in sel], [units["den_medium"][i] for i in sel], [units["group"][i] for i in sel],
                       n_boot, seed)
    return {"point": est.point, "ci95": est.ci95, "n_items": len(sel)}


def collect_metrics(eff: dict, *, eff_idshortcut: dict | None = None, eff_fullbound: dict | None = None, mediation: dict | None = None,
                    closure: dict | None = None, micro: dict | None = None, calibration: dict | None = None,
                    dimension: dict | None = None, declared_no_compact: bool = False, truth_noncompressible: bool | None = None,
                    n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """Assemble the verdict inputs of one system from this package's metric results (primary horizon)."""
    u = eff["_units"]
    m: dict = {"EE": {k: eff["EE_medium"][k] for k in ("point", "ci95")}}
    m["EE_heldout"] = _subset_ee(u, HELDOUT_KINDS, n_boot, seed)
    m["EE_infamily"] = _subset_ee(u, ("in",), n_boot, seed)
    if eff_idshortcut is not None:
        est = paired_ee_diff(u, eff_idshortcut["_units"], "medium", lambda r: r["shift"].split(":", 1)[0] in SHORTCUT_KINDS,
                             n_boot, seed)
        m["EE_vs_idshortcut"] = {"point": est.point, "ci95": est.ci95, "n_units": est.n_units}
    if eff_fullbound is not None:
        est = paired_ee_diff(u, eff_fullbound["_units"], "medium", None, n_boot, seed)
        m["EE_vs_fullbound"] = {"point": est.point, "ci95": est.ci95, "n_units": est.n_units}
    if mediation is not None and "SMS" in mediation:
        m["SMS"] = {k: mediation["SMS"][k] for k in ("point", "ci95")}
    if closure is not None and "ICG_y" in closure:
        m["ICG_y"] = {k: closure["ICG_y"][k] for k in ("point", "ci95")}
    if micro is not None:
        m["MEV"] = dict(micro.get("MEV") or {})
        m["MEV_testable"] = bool(micro.get("testable", False))
    if calibration is not None:
        m["false_confidence"] = calibration.get("false_confidence")
    if dimension is not None:
        m["dimension"] = dimension
    m["declared_no_compact"] = bool(declared_no_compact)
    m["truth_noncompressible"] = truth_noncompressible
    return m


def dimension_status(k_model: int | None, compact_limit: int | None, k_refits: list[int] | None = None,
                     k_range: tuple[int, int] | None = None) -> dict:
    """PROTOCOL 5.10: compact = k <= compact_limit (None when not judged); stable = the modal k occurs in >= 4 of 5 refits and every
    refit k lies in the reported range (without a range: equals the modal k); None when no refits exist."""
    out: dict = {"k": k_model, "compact": None if (compact_limit is None or k_model is None) else bool(k_model <= compact_limit)}
    if not k_refits:
        out["stable"] = None
        return out
    ks = [int(k) for k in k_refits]
    vals, cnt = np.unique(ks, return_counts=True)
    modal = int(vals[np.argmax(cnt)])
    need = int(np.ceil(0.8 * len(ks)))
    in_range = all(k_range[0] <= k <= k_range[1] for k in ks) if k_range is not None else all(k == modal for k in ks)
    out.update({"k_refits": ks, "modal_k": modal, "modal_count": int(cnt.max()), "stable": bool(cnt.max() >= need and in_range)})
    if not out["stable"]:
        out["unresolved"] = [int(min(ks)), int(max(ks))]
    return out


# ------------------------------------------------------------------------------------------------------------ conclusion
def phase4_conclusion(syn: dict | None, real: dict | None, n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """The Phase 4 conclusion rule (PROTOCOL section 9, from Level C results only).

    syn = {"method": {sid: category}, "truestate": {sid: category}, "strata": {sid: type}, "compressible": {sid: bool}}
    real = {"full": {sid: category}, "lineage": {sid: lineage}} (full networks only; mechanisms are reported beside)."""
    out: dict = {}
    syn_status = "UNSUPPORTED"
    if syn:
        comp = [s for s, v in syn["compressible"].items() if v and s in syn["method"]]
        nonc = [s for s, v in syn["compressible"].items() if not v and s in syn["method"]]
        strata = syn.get("strata") or {}
        pm = {s: float(syn["method"][s] == SUPPORTED) for s in comp}
        pt = {s: float(syn["truestate"].get(s) == SUPPORTED) for s in comp if s in (syn.get("truestate") or {})}
        e_pm = S.stratified_system_boot(pm, strata, np.mean, n_boot, seed)
        e_pt = S.stratified_system_boot(pt, strata, np.mean, n_boot, seed + 1) if pt else S.Estimate(float("nan"), [float("nan")] * 2, 0)
        e_d = S.paired_system_boot(pm, pt, strata, n_boot, seed + 2) if pt else S.Estimate(float("nan"), [float("nan")] * 2, 0)
        nc_frac = float(np.mean([syn["method"][s] == DECLARED for s in nonc])) if nonc else float("nan")
        at_least_partial = float(np.mean([syn["method"][s] in AT_LEAST_PARTIAL for s in comp])) if comp else float("nan")
        attainable = bool(np.isfinite(e_pt.point) and e_pt.point >= 0.5)
        sup = (attainable and e_pm.ci95[0] >= 0.5 and np.isfinite(e_d.ci95[0]) and e_d.ci95[0] >= -0.2
               and np.isfinite(nc_frac) and nc_frac >= 2 / 3)
        if sup:
            syn_status = "SUPPORTED"
        elif (np.isfinite(e_pm.ci95[0]) and e_pm.ci95[0] >= 0.2) or (np.isfinite(at_least_partial) and at_least_partial >= 0.5):
            syn_status = "PARTIAL"
        out["synthetic"] = {"status": syn_status, "P_m": e_pm.as_dict(), "P_t": e_pt.as_dict(), "P_m_minus_P_t": e_d.as_dict(),
                            "noncompressible_declared_fraction": nc_frac, "at_least_partial_fraction": at_least_partial,
                            "criteria_attainable_with_true_state": attainable, "n_compressible": len(comp), "n_noncompressible": len(nonc),
                            "supported_e_untested_fraction": (float(np.mean([syn["method"][s] == SUPPORTED_E_UNTESTED for s in comp]))
                                                              if comp else float("nan"))}
    real_status = "UNSUPPORTED"
    if real:
        cats = real["full"]
        if cats and all(v == SUPPORTED for v in cats.values()):
            real_status = "SUPPORTED"
        elif cats and (any(v == SUPPORTED for v in cats.values()) or all(v in AT_LEAST_PARTIAL for v in cats.values())):
            real_status = "PARTIAL"
        by_lin: dict[str, list[str]] = {}
        for s, v in cats.items():
            by_lin.setdefault(str((real.get("lineage") or {}).get(s)), []).append(v)
        out["real"] = {"status": real_status, "full_networks": dict(cats), "by_lineage": by_lin}
    both = syn_status == "SUPPORTED" and real_status == "SUPPORTED"
    any_partial = syn_status in ("SUPPORTED", "PARTIAL") or real_status in ("SUPPORTED", "PARTIAL")
    out["phase4"] = ("compact causal state supported" if both else "partially supported" if any_partial else "unsupported")
    return out


def diagnose(s: dict) -> list[str]:
    """goal5 section 94 diagnosis from summary facts (each key optional, True / False / None)."""
    d = []
    if s.get("fullstate_predicts") and not s.get("compact_predicts"):
        d.append("A: full state predicts interventions, compact state cannot -> abstraction problem")
    if s.get("fullstate_predicts") is False:
        d.append("B: even the full state cannot predict -> simulator / data / excitation problem")
    if s.get("active_equals_random"):
        d.append("C: random design performs as well as active design -> experiment-design component unnecessary")
    if s.get("simple_linear_wins"):
        d.append("D: a simple controlled linear model wins -> use the simple model")
    if s.get("synthetic_ok") and s.get("real_ok") is False:
        d.append("E: compact state works on synthetic but not real systems -> distribution / model mismatch")
    if s.get("high_dimensional_needed"):
        d.append("F: intervention effects require a high-dimensional state -> report high-dimensional causal dynamics")
    if s.get("readin_not_invariant"):
        d.append("G: intervention operators are not invariant -> the causal state definition needs revision")
    return d


# ------------------------------------------------------------------------------------------------------------ primary family
def primary_family(tests: dict[str, dict], alpha: float = S.ALPHA) -> dict:
    """PROTOCOL section 11: tests = {name: {"diff": Estimate (method - baseline, lower is better), "margin": float, "kind":
    "noninferiority" | "superiority"}}. One-sided bootstrap p-values, Holm across the family; a test that cannot be computed stays
    in the family with p = 1."""
    ps, rows = {}, {}
    for name, t in tests.items():
        diff = t.get("diff")
        margin = float(t.get("margin", 0.0)) if t.get("kind", "noninferiority") == "noninferiority" else 0.0
        if diff is None or not np.isfinite(getattr(diff, "point", np.nan)):
            ps[name] = 1.0
            rows[name] = {"p": 1.0, "note": "not computable", "margin": margin}
            continue
        r = S.noninferiority(diff, margin)
        ps[name] = r["p"]
        rows[name] = r
    h = S.holm(ps, alpha)
    for name in rows:
        rows[name]["p_holm"] = h["adjusted"][name]
        rows[name]["reject_holm"] = h["reject"][name]
    return {"tests": rows, "alpha": alpha, "m": h["m"]}
