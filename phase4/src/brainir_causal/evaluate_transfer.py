"""Leave-one-intervention-out, leave-one-implementation-out and shared dynamics (benchmarks/causal_state_v1/PROTOCOL.md sections
5.13-5.14; goal5 sections 55-59).

Item-level inputs: the evaluator scores every test intervention item as (num, den) of the effect error EE (PROTOCOL 5.1; EE of a set =
sum num / sum den). Comparisons here are PAIRED on the items both fits were scored on (`stats.boot_ratio_diff`, items resampled as
clusters; lower is better).

5.13 LEAVE-ONE-INTERVENTION-OUT
    `loio_datasets(records, sysrec)`     {family: training records without that family's intervention items (and their twins)} for
                                         every TRAINED intervention family present in the records
    `loio_summary(full, loio)`           per family: EE of the full fit and of the fit without the family on that family's test items,
                                         the paired gap EE_loio - EE_full with its CI (the generalisation cost of never having seen the
                                         family)

5.14 LEAVE-ONE-IMPLEMENTATION-OUT AND SHARED DYNAMICS
    `limpo_subsample(records, frac, seed)`   25 % of a held-out implementation's training data (intervention items with their twins, and
                                         passive records, each subsampled; at least one of each)
    `limpo_comparison(adapted, scratch)` encoder / read-in adaptation of a frozen shared transition (config adapt_from) against a
                                         from-scratch fit on the same limited data, on unseen interventions of the held-out
                                         implementation: paired EE difference adapted - scratch; beats = upper CI < 0, worse = lower CI
                                         > 0
    `sharing_comparison(...)`            models B (shared dynamics, separate encoders / read-ins), C (partially shared), D (shared latent
                                         causal model) against A (independent) on the systems of one group. A shared model WINS
                                         (goal5 section 56) when, in EVERY system of the group:
                                           - held-out intervention EE is non-inferior: upper CI of the paired difference <= max(0.05,
                                             0.2 x EE_A);
                                           - mediation is non-inferior: upper CI of its SMS <= upper CI of A's SMS + 0.05 (gain units);
                                         AND it has fewer parameters than the independent models together, AND transfer holds:
                                         adaptation beats scratch for at least half of the held-out implementations and is worse for none.
                                         Verdict per shared model: "supported" / "rejected" / "untestable" (a missing part).
    `sharing_gate(within)`               HARD GATE (goal5 section 57): sharing is INTERPRETED only when every system involved has the
                                         within-system verdict "causal state supported"; otherwise the verdict is "prerequisite failed"
                                         and nothing about alignment is interpreted.
Unrelated system pairs (the sharing nulls) face the same rule; their correct verdict is "rejected".
"""

from __future__ import annotations

import numpy as np

from . import families as F
from .evaluate_stability import intervention_items
from .stats import N_BOOT, boot_ratio_diff

SUPPORTED = "causal state supported"
EE_MARGIN_REL, EE_MARGIN_MIN = 0.2, 0.05
SMS_MARGIN = 0.05


def _get(rec, name, default=None):
    return rec.get(name, default) if isinstance(rec, dict) else getattr(rec, name, default)


# ------------------------------------------------------------------------------------------------------------ 5.13
def item_family(rec, sysrec: dict | None = None) -> str:
    fam = _get(rec, "family") or ""
    if fam:
        return str(fam)
    try:
        return F.family_of(_get(rec, "protocol"), sysrec)
    except Exception:  # noqa: BLE001
        return "other"


def loio_datasets(records: list, sysrec: dict | None = None, families: list[str] | None = None) -> dict[str, list]:
    """{family: records minus that family's intervention items (with their twins)}; families default to every intervention family
    of the records (in sysrec's families_train when a split record is given)."""
    items, passive = intervention_items(records)
    fam_of = [item_family(it[0], sysrec) for it in items]
    trained = set(((sysrec or {}).get("split") or {}).get("families_train") or []) or None
    fams = families if families is not None else sorted({f for f in fam_of if trained is None or f in trained})
    out = {}
    for f in fams:
        keep = [x for it, fi in zip(items, fam_of) if fi != f for x in it]
        if len(keep) == sum(len(it) for it in items):
            continue                      # the family has no item in the training data: nothing to leave out
        out[f] = list(passive) + keep
    return out


def _arrays(units: dict, keys: list) -> tuple[np.ndarray, np.ndarray]:
    return (np.array([float(units[k][0]) for k in keys]), np.array([float(units[k][1]) for k in keys]))


def paired_ee(units_a: dict, units_b: dict, n_boot: int = N_BOOT, seed: int = 0, groups: dict | None = None) -> dict:
    """EE_a - EE_b on the common items: units = {item: (num, den)}; groups = {item: cluster id} (optional)."""
    keys = sorted(set(units_a) & set(units_b))
    if not keys:
        return {"diff": float("nan"), "ci95": [float("nan")] * 2, "n": 0, "ee_a": float("nan"), "ee_b": float("nan")}
    na, da = _arrays(units_a, keys)
    nb, db = _arrays(units_b, keys)
    g = [groups.get(k, k) for k in keys] if groups else None
    e = boot_ratio_diff(na, da, nb, db, groups=g, n_boot=n_boot, seed=seed)
    return {"diff": e.point, "ci95": e.ci95, "n": len(keys), "ee_a": float(na.sum() / da.sum()) if da.sum() > 0 else float("nan"),
            "ee_b": float(nb.sum() / db.sum()) if db.sum() > 0 else float("nan"), "_reps": e.reps}


def loio_summary(full_units: dict, loio_units: dict[str, dict], item_families: dict[str, str], n_boot: int = N_BOOT,
                 seed: int = 0) -> dict:
    """full_units: {item: (num, den)} of the full fit on the test items; loio_units: {family: {item: (num, den)}} of the fit without
    that family; item_families: {item: family}. Per family: EE_full, EE_loio and the paired gap EE_loio - EE_full on that family's
    items."""
    out = {}
    for fam, units in loio_units.items():
        items = [k for k, f in item_families.items() if f == fam and k in units and k in full_units]
        if not items:
            out[fam] = {"n": 0, "note": "no test item of this family"}
            continue
        d = paired_ee({k: units[k] for k in items}, {k: full_units[k] for k in items}, n_boot, seed)
        d.pop("_reps", None)
        out[fam] = {"ee_loio": d["ee_a"], "ee_full": d["ee_b"], "gap": d["diff"], "gap_ci95": d["ci95"], "n": d["n"]}
    gaps = [v["gap"] for v in out.values() if v.get("n") and np.isfinite(v["gap"])]
    return {"per_family": out, "mean_gap": float(np.mean(gaps)) if gaps else float("nan"), "n_families": len(gaps)}


# ------------------------------------------------------------------------------------------------------------ 5.14
def limpo_subsample(records: list, frac: float = 0.25, seed: int = 0) -> list:
    """frac of a held-out implementation's training data: intervention items (with their twins) and passive records, each subsampled
    without replacement (at least one of each kind when available)."""
    items, passive = intervention_items(records)
    rng = np.random.default_rng(seed)
    ni = max(1, round(frac * len(items))) if items else 0
    npv = max(1, round(frac * len(passive))) if passive else 0
    pick_i = sorted(rng.permutation(len(items))[:ni].tolist())
    pick_p = sorted(rng.permutation(len(passive))[:npv].tolist())
    return [passive[i] for i in pick_p] + [x for i in pick_i for x in items[i]]


def limpo_comparison(adapted_units: dict, scratch_units: dict, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    d = paired_ee(adapted_units, scratch_units, n_boot, seed)
    d.pop("_reps", None)
    lo, hi = d["ci95"]
    beats = bool(d["n"] and np.isfinite(hi) and hi < 0)
    worse = bool(d["n"] and np.isfinite(lo) and lo > 0)
    return {**d, "adapted_beats_scratch": beats, "adapted_worse": worse}


def sharing_gate(within_verdicts: dict[str, str]) -> dict:
    """HARD GATE: every system must be 'causal state supported' within-system."""
    bad = {s: v for s, v in within_verdicts.items() if str(v).strip().lower() != SUPPORTED}
    return {"passed": not bad and bool(within_verdicts), "failing_systems": bad,
            "note": None if not bad else "prerequisite failed: sharing is not interpreted"}


def sharing_comparison(ee_units: dict[str, dict[str, dict]], sms: dict[str, dict[str, dict]], params: dict[str, int | None],
                       transfer: list[dict] | None, within_verdicts: dict[str, str] | None = None, n_boot: int = N_BOOT,
                       seed: int = 0) -> dict:
    """ee_units: {model: {system: {item: (num, den)}}} on held-out intervention items, models 'A' (independent) and any of 'B', 'C',
    'D'; sms: {model: {system: {"point", "ci95"}}}; params: {model: total parameter count over the group's systems (A: the independent
    models together), None = not reported}; transfer: limpo_comparison rows for the group's held-out implementations (None = not
    run / the method cannot adapt); within_verdicts: {system: within-system verdict} for the HARD GATE (None = not applied, e.g. the
    synthetic development analysis)."""
    gate = sharing_gate(within_verdicts) if within_verdicts is not None else {"passed": True, "note": "gate not applied"}
    out: dict = {"gate": gate, "models": {}}
    if "A" not in ee_units:
        out["error"] = "no independent (A) model"
        return out
    systems = sorted(ee_units["A"])
    if transfer is None or not transfer:
        transfer_ok = None
    else:
        transfer_ok = bool(sum(t["adapted_beats_scratch"] for t in transfer) * 2 >= len(transfer) and not any(t["adapted_worse"] for t in transfer))
    for m in ("B", "C", "D"):
        if m not in ee_units:
            continue
        per, ok_ee, ok_sms, missing = {}, True, True, []
        for sid in systems:
            ua, um = ee_units["A"].get(sid) or {}, ee_units[m].get(sid) or {}
            d = paired_ee(um, ua, n_boot, seed)
            d.pop("_reps", None)
            margin = max(EE_MARGIN_MIN, EE_MARGIN_REL * d["ee_b"]) if np.isfinite(d["ee_b"]) else EE_MARGIN_MIN
            ee_ok = bool(d["n"] and np.isfinite(d["ci95"][1]) and d["ci95"][1] <= margin)
            sa, sm = (sms.get("A") or {}).get(sid), (sms.get(m) or {}).get(sid)
            if sa is None or sm is None:
                sms_ok = None
                missing.append(f"SMS {sid}")
            else:
                ua_, um_ = float(sa["ci95"][1]), float(sm["ci95"][1])
                sms_ok = bool(np.isfinite(ua_) and np.isfinite(um_) and um_ <= ua_ + SMS_MARGIN)
            if not d["n"]:
                missing.append(f"EE {sid}")
            per[sid] = {"ee_diff": d, "ee_margin": margin, "ee_noninferior": ee_ok, "sms_noninferior": sms_ok}
            ok_ee &= ee_ok
            ok_sms &= bool(sms_ok)
        pa, pm = params.get("A"), params.get(m)
        fewer = None if (pa is None or pm is None) else bool(pm < pa)
        if missing or fewer is None or transfer_ok is None:
            verdict = "untestable"
        else:
            verdict = "supported" if (ok_ee and ok_sms and fewer and transfer_ok) else "rejected"
        if not gate["passed"]:
            verdict = "prerequisite failed"
        out["models"][m] = {"per_system": per, "ee_noninferior_all": ok_ee, "sms_noninferior_all": ok_sms, "fewer_parameters": fewer,
                            "transfer_ok": transfer_ok, "params": pm, "params_independent": pa, "missing": missing, "verdict": verdict}
    return out
