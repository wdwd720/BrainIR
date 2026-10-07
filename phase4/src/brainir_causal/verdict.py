"""Per-system verdicts, the Phase 4 conclusion rule and the primary statistical family (benchmarks/causal_state_v1/PROTOCOL.md sections
9 and 11; goal5 sections 71, 92.51, 94).

VERDICT ITEMS (PROTOCOL 9) = the roles in / target / near / far / hidden (OOD and robustness items never enter a criterion); HELD-OUT
items = near / far / hidden (the family shift); the shortcut subset B = target / near / far / hidden. EE = the CLASS-BALANCED EE of
PROTOCOL 5.1 (`evaluate.ee_cb`), with the family-jackknife-t interval of `stats.class_balanced_estimate` for every EE quantity (A, C,
H and B alike: cells clustered in their families, classes with too few units merged; review E, N2 / M2). Criteria, on one system at
the primary horizon (the "upper CI" is the upper end of the two-sided 95 % interval, non-finite replicates counted against the claim):
    A intervention prediction   upper CI of EE (verdict items, abstentions as no effect) < 1 - delta_A AND the POINT EE of every
                                merged magnitude class (`EE_by_class`) < 1 - delta_A (review E round 3, M1: rule R3p; a model that
                                predicts only some classes cannot pass A)
    B shortcut                  upper CI of the paired EE_method - EE_idshortcut < 0 on the B subset
    C full-state                upper CI of the paired EE_method - EE_fullbound <= delta_C (verdict items)
    D mediation                 upper CI of SMS <= tau_SMS; FAILS when more than 1 % of the items are unusable (no usable prediction;
                                latent-missing items stay in the score, 5.3; review E, N3)
    E closure / microstate      upper CI of the LINEAR ICG_y <= tau_ICG AND the MEV is TESTABLE and its upper CI <= tau_MEV. An
                                untestable MEV does NOT satisfy E (reported "E untestable" with the matched / random distance ratio and
                                k; review E, B4); ICG fails like D on unusable items
    F dimension                 compact and stable (PROTOCOL 5.10: Level B over EXACTLY the 3 fit seeds, Level C over the 5 bootstrap
                                refits; a missing or failed fit is never admissible, and a self-reported range counts only when it
                                is tight, width <= 1: `dimension_status`, review E, N7 / N-new-5 / N-new-8); mechanism systems are
                                judged on stability only
    G false confidence          rate on the verdict items <= tau_FC (passes when no covered item has a detectable effect)
    H family generalisation     upper CI of EE on held-out items < 1 - delta_A and the POINT gap EE_heldout - EE_infamily <= delta_H
                                (the gap's CI is reported)
A criterion that does not bind (the calibration's power rule: D, the ICG part of E, the MEV part of E) is excluded from both
SUPPORTED and PARTIAL; a criterion whose inputs are missing (None) blocks SUPPORTED.
Categories, ordered SUPPORTED > PARTIAL > UNSUPPORTED in every aggregate (`category_rank`): "causal state supported" (every binding
criterion holds, AND the calibration makes D and at least one part of E bind: without a binding mediation / closure criterion the
category cannot be issued, review E round 3, N-new-2), "partially supported" (A holds and at least one binding criterion of D, E, H
holds; the failed, untestable and
missing criteria are named), "unsupported" (otherwise); a method's declared "no compact causal state" is recorded as such
("declared no compact causal state": correct on non-compressible types, a false alarm elsewhere) and ranks with "unsupported".
There is no "supported (E untested)" category.

Overall conclusion (`phase4_conclusion`): P_m = fraction of compressible confirmation systems SUPPORTED for the locked method, lower
bound = the one-sided 97.5 % Clopper-Pearson bound; P_m - P_t by a paired UNSTRATIFIED system bootstrap (one-sided 97.5 % lower
bound); rules of PROTOCOL 9. Primary family (`build_primary_family`): the 24 one-sided tests of PROTOCOL 11, Holm at alpha 0.05.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from . import stats as S
from .evalio import HELDOUT_KINDS, PRIMARY, SHORTCUT_KINDS, VERDICT_KINDS
from .evaluate import ee_cb, ee_cb_diff, false_confidence_units

SUPPORTED = "causal state supported"
PARTIAL = "partially supported"
UNSUPPORTED = "unsupported"
DECLARED = "declared no compact causal state"
CATEGORY_ORDER = (SUPPORTED, PARTIAL, UNSUPPORTED)
AT_LEAST_PARTIAL = (SUPPORTED, PARTIAL)
WORST_EE = 10.0
WORST_GAIN = 1.0


def category_rank(category: str) -> int:
    """SUPPORTED 2 > PARTIAL 1 > UNSUPPORTED 0; a declared "no compact causal state" ranks with UNSUPPORTED (0)."""
    return {SUPPORTED: 2, PARTIAL: 1}.get(category, 0)


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
    mev_binds: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> Tolerances:
        keys = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in keys})

    def as_dict(self) -> dict:
        return asdict(self)


def _upper(e) -> float:
    if not e:
        return float("nan")
    ci = e.get("ci95") if isinstance(e, dict) else getattr(e, "ci95", None)
    if not ci or ci[1] is None:
        return float("nan")
    return float(ci[1])


def _crit(passed, value=None, threshold=None, binding: bool = True, note: str | None = None) -> dict:
    return {"pass": None if passed is None else bool(passed), "value": value, "threshold": threshold, "binding": bool(binding),
            "note": note}


def _est_dict(e) -> dict | None:
    """A JSON-friendly {point, ci95, n_units, ...} of an Estimate (or pass a dict through)."""
    if e is None:
        return None
    if isinstance(e, dict):
        return e
    out = {"point": e.point, "ci95": e.ci95, "n_cells": e.n_units, "n_nonfinite_reps": e.n_nonfinite_reps,
           **({"n_charged": e.n_charged} if e.n_charged else {})}
    ex = getattr(e, "extra", None) or {}
    # the class-balanced interval's units (the family count), degrees of freedom and class merges (review E, N2 / N-new-4 / N-new-6:
    # reported with every CI and verdict)
    out.update({k: ex[k] for k in ("method", "jackknife_unit", "n_jackknife_units", "n_families_with_signal", "df", "classes_merged")
                if k in ex})
    return out


# ------------------------------------------------------------------------------------------------------------ per system
def mediation_closure_binding(tol) -> bool:
    """Review E round 3, N-new-2: "causal state supported" asserts MEDIATION and CLOSURE, so it can be issued only when the calibration
    makes the mediation criterion D bind AND at least one part of the closure criterion E (ICG_y or MEV) bind. Otherwise the best
    category is PARTIALLY SUPPORTED, and the calibration is NOT ATTAINABLE (`calibrate.common_percentile`)."""
    return bool(getattr(tol, "sms_binds", True) and (getattr(tol, "icg_binds", True) or getattr(tol, "mev_binds", True)))


#: review E round 3, M1 (rule R3p, adopted by the orchestrator; PROTOCOL 9): criterion A additionally requires the POINT EE of EVERY
#: merged magnitude class (`EE_by_class`) to be < 1 - delta_A, so a model that predicts only some classes (e.g. the strong items)
#: cannot pass A. Point values, because per-class intervals would rest on 3-6 families. The calibration's support rate uses the same
#: criterion A (`calibrate.supported_rate` -> `system_verdict` with this default), so a class that even the true state cannot predict
#: shows up as "not attainable", never silently
A_EVERY_CLASS = True


def system_verdict(m: dict, tol: Tolerances, *, compact_judged: bool = True, a_every_class: bool | None = None) -> dict:
    """Criteria A-H and the category for one system. m: see `collect_metrics` for the keys. SUPPORTED needs every binding criterion
    AND a binding mediation / closure criterion (`mediation_closure_binding`); `all_binding_criteria_hold` reports the conjunction
    itself (the calibration's support rate). a_every_class: the class condition of A (PROTOCOL 9, review E M1; default
    A_EVERY_CLASS = True; False reproduces the earlier rule for diagnosis only, never for a verdict)."""
    c: dict[str, dict] = {}
    ub = _upper(m.get("EE"))
    a_pass = bool(ub < 1 - tol.delta_A) if np.isfinite(ub) else None
    a_note = None if np.isfinite(ub) else "no usable verdict items (or too few families for an interval)"
    if (A_EVERY_CLASS if a_every_class is None else a_every_class) and a_pass is not False:
        per = m.get("EE_by_class") or {}
        bad = sorted(k for k, v in per.items() if not (np.isfinite(v.get("point", np.nan)) and v["point"] < 1 - tol.delta_A))
        if not per:
            a_pass, a_note = None, "per-class EE missing (class condition of A)"
        elif bad:
            a_pass, a_note = False, f"class condition of A: EE of {', '.join(bad)} not below {1 - tol.delta_A:.3g}"
    c["A"] = _crit(a_pass, m.get("EE"), 1 - tol.delta_A, note=a_note)
    b = m.get("EE_vs_idshortcut")
    ub = _upper(b)
    c["B"] = _crit(bool(ub < 0) if np.isfinite(ub) else None, b, 0.0, note=None if b else "no shortcut comparison")
    cc = m.get("EE_vs_fullbound")
    ub = _upper(cc)
    c["C"] = _crit(bool(ub <= tol.delta_C) if np.isfinite(ub) else None, cc, tol.delta_C, note=None if cc else "no full-state bound")
    sms = m.get("SMS")
    if sms is not None and sms.get("failed"):
        c["D"] = _crit(False, sms, tol.tau_SMS, binding=tol.sms_binds, note="more than 1 % of the items unusable")
    else:
        ub = _upper(sms)
        c["D"] = _crit(bool(ub <= tol.tau_SMS) if np.isfinite(ub) else None, sms, tol.tau_SMS, binding=tol.sms_binds,
                       note=None if np.isfinite(ub) else "SMS missing")
    # E: the linear ICG_y part and the MEV part
    icg = m.get("ICG_y")
    if icg is not None and icg.get("failed"):
        icg_pass, icg_note = False, "more than 1 % of the items unusable"
    else:
        ub_i = _upper(icg)
        icg_pass, icg_note = (bool(ub_i <= tol.tau_ICG), None) if np.isfinite(ub_i) else (None, "ICG_y missing")
    mev, mev_testable = m.get("MEV"), m.get("MEV_testable")
    if mev is None or mev_testable is None:
        mev_state, mev_pass, mev_note = "missing", None, "MEV missing"
    elif not mev_testable:
        mev_state, mev_pass = "untestable", False
        mev_note = (f"E untestable (matched / random latent distance ratio {m.get('MEV_rho', float('nan')):.3g}, "
                    f"k = {m.get('MEV_k')}): equivalence not established")
    else:
        ub_m = _upper(mev)
        mev_state, mev_pass, mev_note = "tested", (bool(ub_m <= tol.tau_MEV) if np.isfinite(ub_m) else False), None
    parts = ([icg_pass] if tol.icg_binds else []) + ([mev_pass] if tol.mev_binds else [])
    if not parts:
        e_pass, e_binding = None, False
    else:
        e_binding = True
        e_pass = False if any(p is False for p in parts) else (None if any(p is None for p in parts) else True)
    notes = [n for n, binds in ((icg_note, tol.icg_binds), (mev_note, tol.mev_binds)) if n and binds]
    c["E"] = _crit(e_pass, {"ICG_y": icg, "MEV": mev, "MEV_testable": mev_testable}, {"tau_ICG": tol.tau_ICG, "tau_MEV": tol.tau_MEV},
                   binding=e_binding, note="; ".join(notes) or None)
    c["E"].update({"icg_pass": icg_pass, "mev_pass": mev_pass, "mev_state": mev_state, "icg_binding": tol.icg_binds,
                   "mev_binding": tol.mev_binds})
    dim = m.get("dimension") or {}
    stable, compact = dim.get("stable"), dim.get("compact")
    if compact_judged:
        f_pass = None if (stable is None or compact is None) else (bool(compact) and bool(stable))
    else:
        f_pass = None if stable is None else bool(stable)
    c["F"] = _crit(f_pass, dim, None, note=(None if compact_judged else "compactness not judged (mechanism system)")
                   if f_pass is not None else "dimension stability not computed (needs the seeds' or refits' k)")
    fc = m.get("false_confidence") or {}
    rate, n_fc = fc.get("rate", float("nan")), fc.get("n", 0)
    c["G"] = _crit(True if n_fc == 0 else bool(np.isfinite(rate) and rate <= tol.tau_FC), fc, tol.tau_FC,
                   note="no covered item with a detectable effect" if n_fc == 0 else None)
    eh, ei, gap = m.get("EE_heldout"), m.get("EE_infamily"), m.get("EE_gap")
    ub = _upper(eh)
    gp = float((gap or {}).get("point", np.nan)) if gap else float((eh or {}).get("point", np.nan)) - float((ei or {}).get("point", np.nan))
    c["H"] = _crit(None if (not np.isfinite(ub) or not np.isfinite(gp)) else bool(ub < 1 - tol.delta_A and gp <= tol.delta_H),
                   {"EE_heldout": eh, "EE_infamily": ei, "gap": gap}, {"ee_max": 1 - tol.delta_A, "delta_H": tol.delta_H})
    out: dict = {"criteria": c}
    declared = bool(m.get("declared_no_compact", False))
    truth_nc = m.get("truth_noncompressible")
    if declared:
        out["category"] = DECLARED
        out["declaration_correct"] = None if truth_nc is None else bool(truth_nc)
        return out
    binding = {k: v for k, v in c.items() if v["binding"]}
    all_hold = all(v["pass"] is True for v in binding.values())
    mc = mediation_closure_binding(tol)
    if all_hold and mc:
        cat = SUPPORTED
    elif c["A"]["pass"] is True and any(c[k]["binding"] and c[k]["pass"] is True for k in ("D", "E", "H")):
        cat = PARTIAL
    else:
        cat = UNSUPPORTED
    out["category"] = cat
    out["all_binding_criteria_hold"] = bool(all_hold)
    if all_hold and not mc:
        out["supported_blocked"] = ("no binding mediation (D) and closure (E: ICG or MEV) criterion in the calibration: SUPPORTED "
                                    "cannot be issued (review E, N-new-2)")
    out["failed"] = sorted(k for k, v in binding.items() if v["pass"] is False)
    out["missing"] = sorted(k for k, v in binding.items() if v["pass"] is None)
    out["untestable"] = ["E"] if mev_state == "untestable" and tol.mev_binds else []
    out["not_binding"] = sorted(k for k, v in c.items() if not v["binding"])
    if truth_nc is True:
        out["missed_noncompressible"] = True
    return out


#: PROTOCOL 5.10 (review E, N7): criterion F needs the k of EXACTLY these fits
N_FIT_SEEDS_B = 3
N_REFITS_C = 5
#: review E round 3, N-new-5: a self-reported plausible range counts for stability only when it is TIGHT (hi - lo <= this) and contains
#: the modal k; k_true is 1-4 on this benchmark, so a wider range (e.g. 2-4) would call a factor-of-2 disagreement stable
MAX_K_RANGE_WIDTH = 1


def compact_limit_given_truth(limit: int | None, kind: str | None, k_true, d_draw) -> tuple[int | None, str | None]:
    """PROTOCOL 5.10: compact = k <= max(1, N_obs / 5) + the DRAW ALLOWANCE. Every trajectory has its own parameter draw, so a
    draw-closed state carries up to d_draw static coordinates (5.16); on a SYNTHETIC system the limit is therefore raised by the
    system's d_draw from its truth record (the true state [z, draw] is then compact exactly when k_true <= max(1, N_obs / 5), the
    compressibility condition; non-compressible types stay above it, their full rank exceeding the bound by at least 1.5x). Real
    systems and systems without a recorded d_draw keep the limit; mechanisms are never judged (None). Returns (limit, note)
    (LOG P4-D62)."""
    if limit is None or kind != "synthetic" or d_draw is None:
        return limit, None
    return int(limit) + int(d_draw), f"compactness limit {int(limit)} + draw allowance {int(d_draw)}"


def dimension_status(k_model: int | None, compact_limit: int | None, k_values: list | None = None,
                     k_range: tuple[int, int] | None = None, level: str = "C", n_required: int | None = None) -> dict:
    """PROTOCOL 5.10. compact = k <= compact_limit (None when not judged). STABILITY from the k of the level's fits. The ADMISSIBLE set
    is the reported range when it is tight (hi - lo <= MAX_K_RANGE_WIDTH) and contains the modal k, else {modal k} (a wide or
    excluding range is ignored and reported; review E round 3, N-new-5).
    - Level B, the N_FIT_SEEDS_B = 3 fit seeds: stable iff all three produced a k and every k is admissible.
    - Level C, the N_REFITS_C = 5 bootstrap refits: stable iff all five produced a k, the modal k occurs in at least 4 of 5, and every k
      is admissible (so the fifth refit may differ only within a tight range).
    k_values holds one entry per fit; None marks a MISSING OR FAILED fit, and fewer entries than the level requires count as missing.
    A missing or failed fit is never admissible (review E, N7; round 3, N-new-8: a crash cannot buy the one disagreement Level C
    allows), so a single seed or 1 of 5 refits cannot pass F. stable is None only when no fit was even attempted (k_values None or
    empty: F is then missing, which blocks SUPPORTED)."""
    out: dict = {"k": k_model, "compact": None if (compact_limit is None or k_model is None) else bool(k_model <= compact_limit),
                 "level": level}
    if not k_values:
        out["stable"] = None
        return out
    need = int(n_required) if n_required is not None else (N_FIT_SEEDS_B if level == "B" else N_REFITS_C)
    raw = list(k_values) + [None] * max(0, need - len(k_values))
    ks = [int(k) for k in raw if k is not None]
    n_missing = sum(1 for k in raw if k is None)
    out.update({"k_values": [None if k is None else int(k) for k in raw], "n_required": need, "n_missing": n_missing})
    if not ks:
        out.update({"stable": False, "unresolved": None, "note": f"no fit of the {need} required produced a k"})
        return out
    vals, cnt = np.unique(ks, return_counts=True)
    modal = int(vals[np.argmax(cnt)])
    tight = (k_range is not None and int(k_range[1]) - int(k_range[0]) <= MAX_K_RANGE_WIDTH
             and int(k_range[0]) <= modal <= int(k_range[1]))
    admissible = set(range(int(k_range[0]), int(k_range[1]) + 1)) if tight else {modal}
    all_admissible = n_missing == 0 and all(k in admissible for k in ks)
    if level == "B":
        stable = bool(all_admissible)
    else:
        stable = bool(all_admissible and cnt.max() >= int(np.ceil(0.8 * len(raw))))
    out.update({"modal_k": modal, "modal_count": int(cnt.max()), "stable": stable, "range_used": sorted(admissible) if tight else None})
    if k_range is not None and not tight:
        out["range_note"] = (f"reported range {list(k_range)} ignored for stability (wider than {MAX_K_RANGE_WIDTH} or excludes the "
                             f"modal k {modal}); every k must equal the modal k")
    if not stable:
        out["unresolved"] = [int(min(ks)), int(max(ks))]
        if n_missing:
            out["note"] = f"{n_missing} of {len(raw)} required fits missing or failed (counted as disagreeing)"
    return out


def ee_by_class(units: dict, kinds: tuple[str, ...] | None = VERDICT_KINDS, h: str = PRIMARY) -> dict:
    """The per-class ratios of the class-balanced EE on the items of `kinds` (`stats.class_values`: point values, the merged classes
    and their family counts): the merge pattern of the system (review E, N-new-6) and the input of the class condition of criterion A
    (M1, rule R3p)."""
    from .evaluate import _design_of, unit_indices
    idx = unit_indices(units, kinds, h)
    if not idx:
        return {}
    num = np.array([units[f"num_{h}"][j] for j in idx], float)
    den = np.array([units[f"den_{h}"][j] for j in idx], float)
    return S.class_values(num, den, _design_of(units, idx))


def collect_metrics(eff: dict, *, eff_idshortcut: dict | None = None, eff_fullbound: dict | None = None, mediation: dict | None = None,
                    closure: dict | None = None, micro: dict | None = None, calibration: dict | None = None,
                    dimension: dict | None = None, declared_no_compact: bool = False, truth_noncompressible: bool | None = None,
                    n_boot: int = S.N_BOOT, seed: int = 0, k: int | None = None, k_range: tuple[int, int] | None = None,
                    compact_limit: int | None = None, k_values: list[int] | None = None, level: str = "C") -> dict:
    """The verdict inputs of one system (PROTOCOL 9), computed from the per-item units of `evaluate.eval_effects` on the VERDICT items
    (class-balanced EE; the family-jackknife-t interval of `stats.class_balanced_estimate` for A, B, C and H alike, review E, N2 / M2;
    the `mode` arguments below are recorded only). `dimension` may be passed precomputed; otherwise it is
    computed by `dimension_status(k, compact_limit, k_values, k_range, level)` (k_values = the Level B seeds' or Level C refits' k).
    The Estimates with their replicates are kept under "_estimates" (for `primary_estimates`; strip before reporting)."""
    u = eff["_units"]
    ests: dict = {}
    ests["EE"] = ee_cb(u, PRIMARY, VERDICT_KINDS, "class", n_boot, seed)
    ests["EE_heldout"] = ee_cb(u, PRIMARY, HELDOUT_KINDS, "family_cell", n_boot, seed + 1)
    ests["EE_infamily"] = ee_cb(u, PRIMARY, ("in",), "class", n_boot, seed + 2)
    m: dict = {"EE": _est_dict(ests["EE"]), "EE_pooled": {k2: eff.get("EE_medium", {}).get(k2) for k2 in ("point", "ci95")},
               "EE_by_class": ee_by_class(u, VERDICT_KINDS),
               "EE_heldout": _est_dict(ests["EE_heldout"]) if np.isfinite(ests["EE_heldout"].point) else None,
               "EE_infamily": _est_dict(ests["EE_infamily"]) if np.isfinite(ests["EE_infamily"].point) else None}
    if m["EE_heldout"] is not None and m["EE_infamily"] is not None:
        r1, r2 = ests["EE_heldout"].reps, ests["EE_infamily"].reps
        gap = S.make_estimate(ests["EE_heldout"].point - ests["EE_infamily"].point, None if r1 is None or r2 is None else r1 - r2,
                              ests["EE_heldout"].n_units + ests["EE_infamily"].n_units)
        ests["EE_gap"] = gap
        m["EE_gap"] = _est_dict(gap)
    if eff_idshortcut is not None:
        ests["EE_vs_idshortcut"] = ee_cb_diff(u, eff_idshortcut["_units"], PRIMARY, SHORTCUT_KINDS, "family_cell", n_boot, seed + 3)
        m["EE_vs_idshortcut"] = _est_dict(ests["EE_vs_idshortcut"])
    if eff_fullbound is not None:
        ests["EE_vs_fullbound"] = ee_cb_diff(u, eff_fullbound["_units"], PRIMARY, VERDICT_KINDS, "class", n_boot, seed + 4)
        m["EE_vs_fullbound"] = _est_dict(ests["EE_vs_fullbound"])
    if mediation is not None and "SMS" in mediation:
        m["SMS"] = {k2: mediation["SMS"].get(k2) for k2 in ("point", "ci95", "failed") if k2 in mediation["SMS"]}
        m["SMS_n_unusable"] = mediation.get("n_unusable")
        e = (mediation.get("_estimates") or {}).get("SMS")
        if e is not None:
            ests["SMS"] = e
    if closure is not None and "ICG_y" in closure:
        m["ICG_y"] = {k2: closure["ICG_y"].get(k2) for k2 in ("point", "ci95", "failed") if k2 in closure["ICG_y"]}
        m["ICG_n_unusable"] = closure.get("n_unusable")
    if micro is not None:
        m["MEV"] = dict(micro.get("MEV") or {})
        m["MEV_testable"] = bool(micro.get("testable", False))
        m["MEV_rho"] = (micro.get("matched") or {}).get("median_dist_ratio")
        m["MEV_k"] = micro.get("k")
        m["MEV_untestable_reason"] = micro.get("untestable_reason")
    if calibration is not None and calibration.get("false_confidence_verdict") is not None:
        m["false_confidence"] = calibration["false_confidence_verdict"]
    else:
        m["false_confidence"] = false_confidence_units(u, VERDICT_KINDS, n_boot, seed + 5)
    m["dimension"] = dimension if dimension is not None else dimension_status(k, compact_limit, k_values, k_range, level)
    m["declared_no_compact"] = bool(declared_no_compact)
    m["truth_noncompressible"] = truth_noncompressible
    m["_estimates"] = ests
    return m


# ------------------------------------------------------------------------------------------------------------ conclusion
def phase4_conclusion(syn: dict | None, real: dict | None, n_boot: int = S.N_BOOT, seed: int = 0, *,
                      synthetic_capped_at_partial: bool = False) -> dict:
    """The Phase 4 conclusion rule (PROTOCOL 9, from Level C results only).

    syn = {"method": {sid: category}, "truestate": {sid: category}, "compressible": {sid: bool}, "method_same_items": {sid: category}
    (optional), "strata": {sid: type} (unused by the rule; reported)}; real = {"full": {sid: category}, "lineage": {sid: lineage}}
    (full networks only).
    ITEM SETS (review E, N5; PROTOCOL 7 / 9). ONE item set for the true state: its verdicts on the verdict items IT SUPPORTS, the item
    set of the calibration's 80 % target (`calibrate.true_state_categories`), so P_t and the attainability rule mean what the
    calibration measured. The method's P_m (the >= 0.5 part of the rule) uses its verdicts on ALL verdict items (abstentions scored as
    no effect). The paired difference P_m - P_t is computed on ONE item set: "method_same_items" = the method's verdicts on the true
    state's supported items (`calibrate.calibrate_from_inputs(extra_models=...)` + `calibrate.model_categories`); when the report
    cannot produce them, the all-items verdicts are used (a superset of the reference's items: conservative for the method), and
    "item_sets" says which was used.
    P_m: fraction of the compressible systems SUPPORTED, a compressible system without a method verdict counted as not supported; its
    lower bound = the one-sided 97.5 % Clopper-Pearson bound. P_t: fraction of the compressible systems on which the true state is
    SUPPORTED; for the ATTAINABILITY rule (P_t >= 0.5) a missing true-state verdict counts as not supported, for the paired
    difference it counts as supported (review E, N10: each charge goes against the SUPPORTED claim); both charged counts are
    reported. P_m - P_t: paired UNSTRATIFIED system bootstrap over all compressible systems, one-sided 97.5 % lower bound
    (non-finite replicates count against). synthetic_capped_at_partial: the calibration found the full verdict not attainable for the
    true state (PROTOCOL 7), so the synthetic part is at most PARTIAL."""
    out: dict = {}
    syn_status = "UNSUPPORTED"
    if syn:
        methods, truth = syn.get("method") or {}, syn.get("truestate") or {}
        comp = sorted(s for s, v in syn["compressible"].items() if v)
        nonc = sorted(s for s, v in syn["compressible"].items() if not v)
        ind_m = {s: float(methods.get(s) == SUPPORTED) for s in comp}                    # missing method verdict = not supported
        n_missing_m = sum(1 for s in comp if s not in methods)
        n_missing_t = sum(1 for s in comp if s not in truth)
        ind_t_att = {s: float(truth.get(s) == SUPPORTED) for s in comp}                   # missing = not supported (attainability)
        ind_t_diff = {s: (float(truth[s] == SUPPORTED) if s in truth else 1.0) for s in comp}   # missing = supported (difference)
        k_m, n = int(sum(ind_m.values())), len(comp)
        p_m = k_m / n if n else float("nan")
        lo_m = S.clopper_pearson_lower(k_m, n, 0.975)
        p_t = float(np.mean(list(ind_t_att.values()))) if comp else float("nan")
        p_t_observed = float(np.mean([float(truth[s] == SUPPORTED) for s in comp if s in truth])) if n_missing_t < n else float("nan")
        same = syn.get("method_same_items")
        ind_d = {s: float(same.get(s) == SUPPORTED) for s in comp} if same is not None else ind_m     # missing = not supported
        n_missing_same = sum(1 for s in comp if s not in same) if same is not None else None
        d = S.paired_system_boot(ind_d, ind_t_diff, None, n_boot, seed) if comp else S.Estimate(float("nan"), [float("nan")] * 2, 0)
        lo_d = S.one_sided_lower(d.reps, 0.975) if d.reps is not None else float("nan")
        nc_frac = float(np.mean([methods.get(s) == DECLARED for s in nonc])) if nonc else float("nan")
        at_least_partial = float(np.mean([methods.get(s) in AT_LEAST_PARTIAL for s in comp])) if comp else float("nan")
        attainable = bool(np.isfinite(p_t) and p_t >= 0.5)
        sup = (attainable and np.isfinite(lo_m) and lo_m >= 0.5 and np.isfinite(lo_d) and lo_d >= -0.2 and np.isfinite(nc_frac)
               and nc_frac >= 2 / 3 and not synthetic_capped_at_partial)
        if sup:
            syn_status = "SUPPORTED"
        elif (np.isfinite(lo_m) and lo_m >= 0.2) or (np.isfinite(at_least_partial) and at_least_partial >= 0.5):
            syn_status = "PARTIAL"
        out["synthetic"] = {"status": syn_status, "P_m": p_m, "P_m_lower_cp975": lo_m, "n_supported": k_m, "n_compressible": n,
                            "P_t": p_t, "P_t_observed_systems": p_t_observed,
                            "P_m_minus_P_t": {"point": d.point, "lower_975": lo_d, "n_systems": d.n_units},
                            "P_m_same_items": (float(np.mean(list(ind_d.values()))) if same is not None and comp else None),
                            "charged": {"method_verdict_missing": n_missing_m, "truestate_verdict_missing": n_missing_t,
                                        "method_same_items_missing": n_missing_same},
                            "item_sets": {"P_m": "all verdict items", "P_t": "the verdict items the true-state reference supports",
                                          "P_m_minus_P_t": ("both on the verdict items the true-state reference supports" if same is not None
                                                            else "method on all verdict items (superset; conservative), true state on "
                                                                 "the items it supports")},
                            "noncompressible_declared_fraction": nc_frac, "n_noncompressible": len(nonc),
                            "at_least_partial_fraction": at_least_partial, "criteria_attainable_with_true_state": attainable,
                            "capped_at_partial_by_calibration": bool(synthetic_capped_at_partial),
                            "note": "the true-state reference has a fixed k: its dimension criterion is stable by construction"}
    real_status = "UNSUPPORTED"
    if real:
        cats = real.get("full") or {}
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
#: PROTOCOL 11: (claim, statistic) of the six hypotheses; every statistic is lower-is-better, tested one-sided against its margin
HYPOTHESES = {
    "H1": ("effects predicted better than no effect", "class-balanced EE of M"),
    "H2": ("better than the intervention-ID shortcut on held-out families and targets", "EE_M - EE_ID on the B subset"),
    "H3": ("near the full-state bound", "EE_M - EE_FB"),
    "H4": ("intervention effects mediated by the state", "SMS of M"),
    "H5": ("held-out families predicted better than no effect", "class-balanced EE of M on held-out items"),
    "H6": ("not worse than the strongest baseline", "EE_M - EE_S"),
}
#: the worst admissible value of each statistic, charged for a failed or missing system (review E, M7)
WORST = {"H1": WORST_EE, "H2": WORST_EE, "H3": WORST_EE, "H4": WORST_GAIN, "H5": WORST_EE, "H6": WORST_EE}


def primary_thresholds(margins: dict, level: str = "system") -> dict:
    """The null boundary of every hypothesis (H0: statistic >= threshold), pre-registered numbers.
    - level "system" (the per-network tests (b): per-system statistics): the per-system calibration margins delta_A, delta_C, tau_SMS.
    - level "suite" (the suite tests (a): MEANS over systems; review E, N9): H3 and H4 use the SUITE margins of
      `calibrate.suite_margins` (delta_C_suite, tau_SMS_suite: the p-th percentile, over resampled suites of the confirmation size, of
      the true-state reference's one-sided 95 % upper bound of its MEAN), because a percentile of per-system upper bounds is a lenient
      boundary for a mean (a larger margin makes H3 / H4 easier to reject). H1 / H5 keep 1 - delta_A: there a larger margin makes the
      test STRICTER (it demands a larger improvement over no effect), so the per-system delta_A is conservative for a mean.
    delta_NI is a NUMBER fixed at the method lock (0.2 x the strongest baseline's median class-balanced EE on the validation suite)."""
    if level == "suite":
        missing = [k for k in ("delta_C_suite", "tau_SMS_suite") if margins.get(k) is None]
        if missing:
            raise ValueError(f"the suite-level tests need the suite margins {missing} (calibrate.suite_margins; review E, N9)")
        h3, h4 = float(margins["delta_C_suite"]), float(margins["tau_SMS_suite"])
    else:
        h3, h4 = float(margins["delta_C"]), float(margins["tau_SMS"])
    return {"H1": 1.0 - float(margins["delta_A"]), "H2": 0.0, "H3": h3, "H4": h4, "H5": 1.0 - float(margins["delta_A"]),
            "H6": float(margins["delta_NI"])}


def primary_estimates(eff_m: dict, *, eff_id: dict | None = None, eff_fb: dict | None = None, eff_s: dict | None = None,
                      mediation: dict | None = None, n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """The six statistics of ONE system (a real full network: identity-cell bootstrap Estimates with replicates) from the method's and
    the comparators' `eval_effects` results and the method's `eval_mediation` result. Missing inputs give None (the test stays in the
    family with p = 1)."""
    u = eff_m["_units"]
    out: dict = {"H1": ee_cb(u, PRIMARY, VERDICT_KINDS, "class", n_boot, seed),
                 "H5": ee_cb(u, PRIMARY, HELDOUT_KINDS, "family_cell", n_boot, seed + 1)}
    out["H2"] = ee_cb_diff(u, eff_id["_units"], PRIMARY, SHORTCUT_KINDS, "family_cell", n_boot, seed + 2) if eff_id else None
    out["H3"] = ee_cb_diff(u, eff_fb["_units"], PRIMARY, VERDICT_KINDS, "class", n_boot, seed + 3) if eff_fb else None
    out["H6"] = ee_cb_diff(u, eff_s["_units"], PRIMARY, VERDICT_KINDS, "class", n_boot, seed + 4) if eff_s else None
    sms = (mediation or {}).get("SMS") or {}
    if sms.get("failed"):
        out["H4"] = S.Estimate(WORST_GAIN, [WORST_GAIN, WORST_GAIN], 0, np.full(n_boot, WORST_GAIN))
    else:
        out["H4"] = ((mediation or {}).get("_estimates") or {}).get("SMS")
    return out


def _test_row(est, threshold: float, alpha: float) -> dict:
    if est is None or est.reps is None or not np.isfinite(est.point):
        return {"p": 1.0, "point": getattr(est, "point", float("nan")), "threshold": threshold, "upper_one_sided": float("nan"),
                "note": "not computable (stays in the family with p = 1)"}
    return {"p": S.boot_pvalue(est.reps, threshold, "less"), "point": est.point, "threshold": threshold,
            "upper_one_sided": S.one_sided_upper(est.reps, 1.0 - alpha), "n_units": est.n_units,
            "n_nonfinite_reps": est.n_nonfinite_reps, "n_charged": est.n_charged}


def build_primary_family(suite: dict | None, networks: dict[str, dict], margins: dict, *, n_boot: int = S.N_BOOT, seed: int = 0,
                         alpha: float = S.ALPHA) -> dict:
    """The PRIMARY FAMILY of PROTOCOL 11: 6 hypotheses x ((a) the confirmation suite + (b) each real full network) = 24 one-sided tests
    at alpha 0.05 with Holm's step-down procedure.

    suite = {"systems": [the compressible confirmation systems], "values": {"H1": {sid: value}, ..., "H6": {sid: value}}}: per-system
    values of each statistic (differences formed per system); the statistic is their mean over the systems, with a paired
    UNSTRATIFIED system bootstrap; a missing or non-finite system value is charged the worst admissible value (EE 10, SMS +1) and
    counted. networks = {network id: `primary_estimates(...)`} (family-jackknife-t Estimates). margins: see `primary_thresholds` (the
    suite tests use the suite margins, the network tests the per-system margins; review E, N9). The class merges of every system's
    class-balanced statistics differ between systems (review E, N-new-6): suite["merges"] = {sid: {class: merged into}} is reported
    with the suite rows when given. A hypothesis H is rejected when its Holm-adjusted one-sided p <= alpha; every row reports the
    one-sided 95 % upper bound."""
    thr = primary_thresholds(margins, "system")
    thr_suite = primary_thresholds(margins, "suite") if suite is not None else None
    rows: dict[str, dict] = {}
    if suite is not None:
        systems = list(suite.get("systems") or [])
        for i, h in enumerate(HYPOTHESES):
            vals, charged = {}, 0
            for s in systems:
                v = (suite.get("values") or {}).get(h, {}).get(s)
                if v is None or not np.isfinite(float(v)):
                    v, charged = WORST[h], charged + 1
                vals[s] = float(v)
            est = S.stratified_system_boot(vals, None, np.mean, n_boot, seed + 101 * i) if vals else None
            if est is not None:
                est.n_charged = charged
            rows[f"suite:{h}"] = {**_test_row(est, thr_suite[h], alpha), "claim": HYPOTHESES[h][0], "statistic": HYPOTHESES[h][1],
                                  "dataset": "confirmation suite", "n_systems": len(vals)}
            if h in ("H1", "H2", "H3", "H5", "H6") and suite.get("merges") is not None:
                pats: dict[str, int] = {}
                for s in systems:
                    key = ", ".join(f"{a}->{b}" for a, b in sorted(((suite["merges"] or {}).get(s) or {}).items())) or "none"
                    pats[key] = pats.get(key, 0) + 1
                rows[f"suite:{h}"]["class_merge_patterns"] = pats
    for net, ests in sorted(networks.items()):
        for h in HYPOTHESES:
            rows[f"{net}:{h}"] = {**_test_row((ests or {}).get(h), thr[h], alpha), "claim": HYPOTHESES[h][0],
                                  "statistic": HYPOTHESES[h][1], "dataset": net}
    hl = S.holm({k: v["p"] for k, v in rows.items()}, alpha)
    for k, v in rows.items():
        v["p_holm"] = hl["adjusted"][k]
        v["reject_holm"] = hl["reject"][k]
    return {"tests": rows, "alpha": alpha, "m": hl["m"], "n_rejected": int(sum(hl["reject"].values())), "thresholds": thr,
            "thresholds_suite": thr_suite, "expected_m": 6 * (1 + 3)}


def primary_family(tests: dict[str, dict], alpha: float = S.ALPHA) -> dict:
    """Generic one-sided family: tests = {name: {"diff": Estimate (lower is better), "margin": float, "kind": "noninferiority" |
    "superiority"}}; one-sided bootstrap p-values (the same convention as `build_primary_family`), Holm across the family; a test
    that cannot be computed stays in the family with p = 1."""
    ps, rows = {}, {}
    for name, t in tests.items():
        diff = t.get("diff")
        margin = float(t.get("margin", 0.0)) if t.get("kind", "noninferiority") == "noninferiority" else 0.0
        r = S.noninferiority(diff, margin, alpha) if diff is not None else {"p": 1.0, "note": "not computable", "margin": margin}
        ps[name] = r["p"]
        rows[name] = r
    h = S.holm(ps, alpha)
    for name in rows:
        rows[name]["p_holm"] = h["adjusted"][name]
        rows[name]["reject_holm"] = h["reject"][name]
    return {"tests": rows, "alpha": alpha, "m": h["m"]}
