"""Item-level evaluation of a causal state model (benchmarks/causal_state_v1/PROTOCOL.md sections 5.1, 5.2, 5.8, 5.9, 5.12).

Families are computed and reported SEPARATELY; nothing is collapsed into one score.

Flow: `predict_items` runs the model once per item on FRESH copies (`brainir_causal.fresh`): `intervention_effect` for intervention
items (the model's counterfactual API, so its own abstention and uncertainty are respected), `encode` + `rollout` for passive items,
and `encode` for the latent at the onset. The scorers below only read these predictions, so every family scores the same outputs.

5.1 intervention effect (all readouts in units of the pooled public training sd, so the floor is FLOOR_FRAC = 0.05):
    e_i(t) = y_i(t) - y_twin_i(t);  e-hat_i(t) = y-hat_int(t) - y-hat_base(t);  window rows 1..m_h
    num_i = sum ||e-hat_i - e_i||^2,  den_i = max(sum ||e_i||^2, m_h n_y f^2),  EE(h) = sum_i min(num_i, 10 den_i) / sum_i den_i
    abstained items are scored as predicting NO effect (e-hat = 0, so num_i = sum ||e_i||^2 <= den_i); a non-finite or failed
    prediction counts as the cap (num_i = 10 den_i) and is never dropped; both are counted. CIs: cluster bootstrap (item groups).
    Detectability ES_i = RMS(e_i over the PRIMARY window) / f; classes below / weak / moderate / strong (evalio.DETECT_CLASSES).
    Sign accuracy: per readout dimension whose true window mean effect exceeds the floor, the sign of the time-integrated predicted
    effect must match (a zero prediction is wrong); reported over covered items and over all items (abstained = wrong).
    Absolute effect RMSE in readout units; post-intervention trajectory NMSE (capped at 10 per item; abstained items use the
    model's no-intervention prediction).
5.2 observational prediction: window NMSE of the passive rollout per horizon, capped at 10 per window, averaged per resampling group
    (a source trajectory with its several onsets), CI by resampling groups.
5.8 composition: EE on comp.* items (the family breakdown of 5.1) and composition consistency (predicted non-additivity against
    the true non-additivity, from the true single-component futures `item.components`), descriptive.
5.9 abstention and calibration: coverage (per detectability class, shift kind and OOD / robustness category), EE over covered items,
    FALSE-CONFIDENCE rate (covered items with a detectable true effect, ES >= 1, whose EE_i > 1 or whose dominant readout effect has
    a confidently wrong sign), 90 % interval coverage of the model's y_sd per horizon (no y_sd = zero-width intervals: confident
    everywhere), Brier scores of p_detectable and p_sign_pos (a model that reports neither is scored with its implied 0/1 claims; an
    abstained item without explicit probabilities counts as p = 0.5).
5.12 OOD / robustness / validity: EE and NMSE per "ood:<category>" / "robust:<condition>" shift relative to in-distribution items;
    the AUC of the model's validity score for detecting items with EE_i > 1 (higher score = more trustworthy; constant scores give
    0.5); the ratio of mean predicted sd (OOD / in-distribution) against the ratio of realised RMS errors.

Resolutions of protocol-draft ambiguities (documented for the orchestrator):
- "EE, abstentions as no effect" uses the primary horizon for verdicts; every horizon is reported.
- Sign detectability threshold: |window mean of the true effect| > f in a dimension (the floor applied to the time average).
- The false-confidence "confidently wrong sign" is judged on the item's dominant readout dimension (largest |true integral| among
  detectable dimensions): the predicted window mean exceeds the floor in magnitude with the opposite sign.
- Interval coverage uses y_sd of the INTERVENED prediction (from intervention_effect's "y_sd", else uncertainty()["y_sd"]).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from . import stats as S
from .evalio import DETECT_CLASSES, HORIZON_FRACTIONS, ITEM_CAP, PRIMARY, EvalSystem, TestItem, detect_class
from .fresh import Fresh, as_fresh, safe_call

Z90 = 1.6448536269514722


# ------------------------------------------------------------------------------------------------------------ predictions
@dataclass
class Prediction:
    item_id: str
    y_int: np.ndarray | None = None      # (H+1, n_y) predicted readout under the events (passive: the rollout)
    y_base: np.ndarray | None = None     # (H+1, n_y) predicted readout without the events (None for passive items)
    abstain: bool = False
    y_sd: np.ndarray | None = None       # (H+1, n_y) predictive sd of y_int, if reported
    uncertainty: dict = field(default_factory=dict)
    validity: dict = field(default_factory=dict)
    z0: np.ndarray | None = None         # the model's latent at the onset
    z_int: np.ndarray | None = None      # (H+1, k) latent trajectory under the events, if the model returned it
    z_base: np.ndarray | None = None     # (H+1, k) latent trajectory without the events
    error: str | None = None             # message of a failed model call (scored as non-finite)
    encode_error: str | None = None      # a failed separate encode (the latent at the onset is then missing)


def _as2d(a, n_y: int | None = None) -> np.ndarray | None:
    if a is None:
        return None
    v = np.asarray(a, dtype=np.float64)
    if v.ndim == 1:
        v = v[:, None] if n_y in (None, 1) else v[None, :]
    return v


def predict_items(model, sysc: EvalSystem, items: list[TestItem]) -> dict[str, Prediction]:
    """Run the model on every item (fresh copies). Never raises for model errors: they are recorded in Prediction.error."""
    F = as_fresh(model)
    sid = sysc.system_id
    out: dict[str, Prediction] = {}
    support_cache: dict[str, bool] = {}

    def supports(kind: str) -> bool:
        if kind not in support_cache:
            r, err = safe_call(F.supports, sid, kind)
            support_cache[kind] = bool(r) if err is None else False
        return support_cache[kind]

    for it in items:
        p = Prediction(item_id=it.item_id)
        z0, err = safe_call(F.encode, sid, it.x_hist, it.u_hist, it.dt)
        if err is None:
            try:
                p.z0 = np.asarray(z0, np.float64).reshape(-1)
            except (TypeError, ValueError) as exc:
                err = f"encode returned an unusable value: {exc}"
        if it.is_passive:
            if err is None:
                r, err = safe_call(F.rollout, sid, p.z0, it.u_future, [], it.dt)
                if err is None:
                    p.y_int = _as2d(r.get("y"), sysc.n_y)
                    p.y_sd = _as2d(r.get("y_sd"), sysc.n_y)
            p.error = err
        else:
            r, err2 = safe_call(F.intervention_effect, sid, it.x_hist, it.u_hist, it.u_future, list(it.events), it.dt)
            if err2 is None and isinstance(r, dict):
                p.y_int, p.y_base = _as2d(r.get("y_int"), sysc.n_y), _as2d(r.get("y_base"), sysc.n_y)
                p.abstain = bool(r.get("abstain", False)) or not all(supports(e["kind"]) for e in it.events)
                unc = r.get("uncertainty") or {}
                p.uncertainty = dict(unc) if isinstance(unc, dict) else {}
                sd = r.get("y_sd", p.uncertainty.get("y_sd"))
                p.y_sd = _as2d(sd, sysc.n_y)
                p.validity = dict(r.get("validity") or {})
                zi, zb = r.get("z_int"), r.get("z_base")
                p.z_int = None if zi is None else np.atleast_2d(np.asarray(zi, np.float64))
                p.z_base = None if zb is None else np.atleast_2d(np.asarray(zb, np.float64))
            else:
                p.error = err2 or "intervention_effect returned no dict"
                p.abstain = not all(supports(e["kind"]) for e in it.events)
            # the separate encode only provides the latent at the onset (mediation, truth metrics); its failure does not change the
            # effect prediction, which intervention_effect made on its own copy
            p.encode_error = err
        out[it.item_id] = p
    return out


# ------------------------------------------------------------------------------------------------------------ helpers
def _rows(a: np.ndarray | None, m: int) -> np.ndarray | None:
    """Rows 1..m of a future array, or None when it is missing / too short / non-finite."""
    if a is None or len(a) <= m:
        return None
    r = a[1: m + 1]
    return r if np.isfinite(r).all() else None


@dataclass
class ItemScore:
    item_id: str
    group: str
    family: str
    shift: str
    magnitude_class: str
    abstain: bool
    covered: bool
    failed: bool                     # non-finite / failed / wrong-shaped prediction (scored as the cap)
    num: dict[str, float]            # horizon -> capped numerator
    den: dict[str, float]            # horizon -> denominator
    raw_sq: dict[str, float]         # horizon -> uncapped squared effect error (readout units^2), for the absolute RMSE
    n_cells: dict[str, int]          # horizon -> m_h * n_y
    post_nmse: dict[str, float]      # horizon -> capped post-intervention trajectory NMSE
    es: float                        # detectability at the primary horizon
    dclass: str
    sign_hits: int = 0
    sign_total: int = 0
    wrong_sign_confident: bool = False
    ee_i: float = float("nan")       # num/den at the primary horizon
    pred_mean_effect: np.ndarray | None = None   # (n_y,) predicted window-mean effect (standardised), primary horizon
    pred_es: float = 0.0             # the PREDICTED effect's detectability, RMS(e-hat over the primary window) / floor
    true_mean_effect: np.ndarray | None = None


def score_item(sysc: EvalSystem, it: TestItem, p: Prediction, horizons=tuple(HORIZON_FRACTIONS)) -> ItemScore | None:
    """Score one intervention item (see the module docstring). None for passive items."""
    if it.is_passive:
        return None
    sd, f = sysc.y_sd, sysc.floor_frac
    yt, yw = it.y_future / sd, it.y_twin / sd
    n_y = yt.shape[1]
    covered = not p.abstain and p.error is None
    failed = False
    num, den, raw, cells, post = {}, {}, {}, {}, {}
    for h in horizons:
        m = sysc.horizon_steps(h, it.dt)
        if len(yt) <= m:
            continue
        e = yt[1: m + 1] - yw[1: m + 1]
        d = float(max((e ** 2).sum(), m * n_y * f ** 2))
        yi, yb = _rows(p.y_int, m), _rows(p.y_base, m)
        if p.abstain:
            # an abstention (the model's own flag, or an event kind it does not support) is scored as predicting no effect even
            # when its call also failed; its trajectory prediction is its no-intervention rollout, when available
            ehat = np.zeros_like(e)
            traj = yb / sd if yb is not None and yb.shape == e.shape else None
        elif yi is not None and yb is not None and yi.shape == e.shape and yb.shape == e.shape:
            ehat = (yi - yb) / sd
            traj = yi / sd
        else:
            ehat, traj = None, None
        if ehat is None:
            failed = True
            nm, rq = ITEM_CAP * d, float("inf")
        else:
            rq = float(((ehat - e) ** 2).sum())
            nm = min(rq, ITEM_CAP * d)
        num[h], den[h], raw[h], cells[h] = float(nm), d, rq * sd ** 2, m * n_y
        if traj is None:
            post[h] = ITEM_CAP
        else:
            v = float(np.mean((traj - yt[1: m + 1]) ** 2))
            post[h] = ITEM_CAP if not np.isfinite(v) else min(v, ITEM_CAP)
    mp = sysc.horizon_steps(PRIMARY, it.dt)
    es, sh, stot, wrong, pm, tm, pes = float("nan"), 0, 0, False, None, None, 0.0
    if len(yt) > mp:
        e = yt[1: mp + 1] - yw[1: mp + 1]
        es = float(np.sqrt(np.mean(e ** 2)) / f)
        tm = e.mean(0)
        yi, yb = _rows(p.y_int, mp), _rows(p.y_base, mp)
        if covered and yi is not None and yb is not None and yi.shape == e.shape and yb.shape == e.shape:
            pm = ((yi - yb) / sd).mean(0)
            pes = float(np.sqrt(np.mean(((yi - yb) / sd) ** 2)) / f)
        else:
            pm = np.zeros(n_y)
        det = np.abs(tm) > f
        stot = int(det.sum())
        sh = int(np.sum(det & (np.sign(pm) == np.sign(tm)) & (pm != 0)))
        if det.any() and covered:
            d_star = int(np.argmax(np.where(det, np.abs(tm), -1.0)))
            wrong = bool(abs(pm[d_star]) > f and np.sign(pm[d_star]) != np.sign(tm[d_star]))
    ee_i = num[PRIMARY] / den[PRIMARY] if PRIMARY in num and den[PRIMARY] > 0 else float("nan")
    return ItemScore(item_id=it.item_id, group=it.group, family=it.family, shift=it.shift, magnitude_class=it.magnitude_class,
                     abstain=bool(p.abstain), covered=covered, failed=failed, num=num, den=den, raw_sq=raw, n_cells=cells, post_nmse=post,
                     es=es, dclass=detect_class(es), sign_hits=sh, sign_total=stot, wrong_sign_confident=wrong, ee_i=float(ee_i),
                     pred_mean_effect=pm, true_mean_effect=tm, pred_es=pes)


def score_items(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction]) -> list[ItemScore]:
    out = []
    for it in items:
        if it.is_passive or it.item_id not in preds:
            continue
        s = score_item(sysc, it, preds[it.item_id])
        if s is not None:
            out.append(s)
    return out


def _ee(scores: list[ItemScore], h: str, n_boot: int, seed: int) -> dict:
    rows = [s for s in scores if h in s.num]
    if not rows:
        return {"point": float("nan"), "ci95": [float("nan")] * 2, "n_items": 0}
    est = S.boot_ratio([s.num[h] for s in rows], [s.den[h] for s in rows], [s.group for s in rows], n_boot, seed)
    return {"point": est.point, "ci95": est.ci95, "n_items": len(rows), "n_clusters": est.n_units,
            "n_failed": int(sum(s.failed for s in rows)), "n_abstained": int(sum(s.abstain for s in rows)),
            "n_capped": int(sum(s.num[h] >= ITEM_CAP * s.den[h] * (1 - 1e-12) for s in rows))}


def _breakdown(scores: list[ItemScore], key, h: str, n_boot: int, seed: int) -> dict:
    by = defaultdict(list)
    for s in scores:
        by[key(s)].append(s)
    return {k: _ee(v, h, n_boot, seed) for k, v in sorted(by.items())}


# ------------------------------------------------------------------------------------------------------------ 5.1
def eval_effects(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """5.1: EE per horizon with breakdowns, absolute effect RMSE, sign accuracy, post-intervention NMSE. The result keeps per-item
    units under "_units" for paired comparisons (strip before reporting)."""
    sc = score_items(sysc, items, preds)
    res: dict = {"n_items": len(sc), "n_abstained": int(sum(s.abstain for s in sc)), "n_failed": int(sum(s.failed for s in sc)),
                 "n_errors": int(sum(preds[s.item_id].error is not None for s in sc)), "floor": sysc.floor, "item_cap": ITEM_CAP}
    for h in HORIZON_FRACTIONS:
        res[f"EE_{h}"] = _ee(sc, h, n_boot, seed)
        rows = [s for s in sc if h in s.num and np.isfinite(s.raw_sq[h])]
        cells = sum(s.n_cells[h] for s in rows)
        res[f"abs_effect_rmse_{h}"] = float(np.sqrt(sum(s.raw_sq[h] for s in rows) / cells)) if cells else float("nan")
        pn = [s for s in sc if h in s.post_nmse]
        if pn:
            e = S.boot_mean([s.post_nmse[h] for s in pn], [s.group for s in pn], n_boot, seed)
            res[f"post_nmse_{h}"] = {"point": e.point, "ci95": e.ci95, "n_items": len(pn)}
    h = PRIMARY
    res["by_family"] = _breakdown(sc, lambda s: s.family, h, n_boot, seed)
    res["by_shift_kind"] = _breakdown(sc, lambda s: s.shift.split(":", 1)[0], h, n_boot, seed)
    res["by_shift"] = _breakdown(sc, lambda s: s.shift, h, n_boot, seed)
    res["by_magnitude_class"] = _breakdown(sc, lambda s: s.magnitude_class, h, n_boot, seed)
    res["by_detectability"] = _breakdown(sc, lambda s: s.dclass, h, n_boot, seed)
    hits_cov = sum(s.sign_hits for s in sc if s.covered)
    tot_cov = sum(s.sign_total for s in sc if s.covered)
    hits_all, tot_all = sum(s.sign_hits for s in sc), sum(s.sign_total for s in sc)
    res["sign_accuracy"] = {"covered": hits_cov / tot_cov if tot_cov else float("nan"), "n_covered_dims": tot_cov,
                            "all": hits_all / tot_all if tot_all else float("nan"), "n_all_dims": tot_all}
    res["detectability_counts"] = {name: int(sum(s.dclass == name for s in sc)) for name, _, _ in DETECT_CLASSES}
    res["_units"] = {"item": [s.item_id for s in sc], "group": [s.group for s in sc], "family": [s.family for s in sc],
                     "shift": [s.shift for s in sc], "abstain": [s.abstain for s in sc], "failed": [s.failed for s in sc],
                     **{f"num_{hh}": [s.num.get(hh, float("nan")) for s in sc] for hh in HORIZON_FRACTIONS},
                     **{f"den_{hh}": [s.den.get(hh, float("nan")) for s in sc] for hh in HORIZON_FRACTIONS},
                     "es": [s.es for s in sc], "dclass": [s.dclass for s in sc]}
    res["_scores"] = sc
    return res


def paired_ee_diff(units_a: dict, units_b: dict, h: str = PRIMARY, subset=None, n_boot: int = S.N_BOOT, seed: int = 0) -> S.Estimate:
    """Paired EE_a - EE_b on the items both scored (the same denominators: den depends on the truth only). subset(item_index_dict)
    -> bool selects items (e.g. held-out families)."""
    ia = {it: j for j, it in enumerate(units_a["item"])}
    ib = {it: j for j, it in enumerate(units_b["item"])}
    common = [it for it in units_a["item"] if it in ib]
    if subset is not None:
        common = [it for it in common if subset({k: units_a[k][ia[it]] for k in ("family", "shift", "dclass", "group")})]
    na = np.array([units_a[f"num_{h}"][ia[i]] for i in common], float)
    nb = np.array([units_b[f"num_{h}"][ib[i]] for i in common], float)
    den = np.array([units_a[f"den_{h}"][ia[i]] for i in common], float)
    grp = [units_a["group"][ia[i]] for i in common]
    ok = np.isfinite(na) & np.isfinite(nb) & np.isfinite(den)
    return S.boot_ratio_diff(na[ok], den[ok], nb[ok], den[ok], np.asarray(grp)[ok], n_boot, seed)


# ------------------------------------------------------------------------------------------------------------ 5.2
def eval_observational(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], n_boot: int = S.N_BOOT,
                       seed: int = 0) -> dict:
    """5.2: passive multi-horizon readout NMSE (capped at 10 per window), averaged per group, CI by resampling groups."""
    passive = [it for it in items if it.is_passive and it.item_id in preds]
    res: dict = {"n_windows": len(passive)}
    for h in HORIZON_FRACTIONS:
        per_group: dict[str, list[float]] = defaultdict(list)
        n_cap = n_fail = 0
        for it in passive:
            m = sysc.horizon_steps(h, it.dt)
            if len(it.y_future) <= m:
                continue
            p = preds[it.item_id]
            yp = _rows(p.y_int, m)
            if yp is None or p.error is not None or yp.shape != it.y_future[1: m + 1].shape:
                v, n_fail = ITEM_CAP, n_fail + 1
            else:
                v = float(np.mean(((yp - it.y_future[1: m + 1]) / sysc.y_sd) ** 2))
                if not np.isfinite(v) or v > ITEM_CAP:
                    v, n_cap = ITEM_CAP, n_cap + 1
            per_group[it.group].append(v)
        if per_group:
            g = sorted(per_group)
            e = S.boot_mean([float(np.mean(per_group[k])) for k in g], None, n_boot, seed)
            res[f"obs_nmse_{h}"] = {"point": e.point, "ci95": e.ci95, "n_groups": len(g), "n_capped": n_cap, "n_failed": n_fail}
            res.setdefault("_units", {})[f"obs_nmse_{h}"] = {k: float(np.mean(per_group[k])) for k in g}
    return res


# ------------------------------------------------------------------------------------------------------------ 5.8
def eval_composition(model, sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], eff: dict | None = None,
                     n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """5.8: EE on comp.* items and the composition consistency of the model's predicted non-additivity (descriptive)."""
    F = as_fresh(model)
    comp = [it for it in items if not it.is_passive and it.family.startswith("comp.") and it.item_id in preds]
    res: dict = {"n_items": len(comp)}
    eff = eff if eff is not None else eval_effects(sysc, items, preds, n_boot, seed)
    res["EE_by_family"] = {k: v for k, v in eff.get("by_family", {}).items() if k.startswith("comp.")}
    m = sysc.horizon_steps(PRIMARY)
    num = den = mag_na = mag_ab = 0.0
    n_ok = 0
    for it in comp:
        c = it.components or {}
        if not ("a" in c and "b" in c) or len(it.y_future) <= m:
            continue
        p = preds[it.item_id]
        yi, yb = _rows(p.y_int, m), _rows(p.y_base, m)
        if p.error or p.abstain or yi is None or yb is None:
            continue
        pa, ea = safe_call(F.intervention_effect, sysc.system_id, it.x_hist, it.u_hist, it.u_future, list(c["a"]["events"]), it.dt)
        pb, eb = safe_call(F.intervention_effect, sysc.system_id, it.x_hist, it.u_hist, it.u_future, list(c["b"]["events"]), it.dt)
        if ea or eb:
            continue
        sd = sysc.y_sd
        e_ab = (it.y_future[1: m + 1] - it.y_twin[1: m + 1]) / sd
        e_a = (np.asarray(c["a"]["y_future"], float)[1: m + 1] - it.y_twin[1: m + 1]) / sd
        e_b = (np.asarray(c["b"]["y_future"], float)[1: m + 1] - it.y_twin[1: m + 1]) / sd
        eh_ab = (yi - yb) / sd
        ya, yab = _rows(_as2d(pa.get("y_int"), sysc.n_y), m), _rows(_as2d(pa.get("y_base"), sysc.n_y), m)
        yb2, ybb = _rows(_as2d(pb.get("y_int"), sysc.n_y), m), _rows(_as2d(pb.get("y_base"), sysc.n_y), m)
        if any(v is None or v.shape != e_ab.shape for v in (ya, yab, yb2, ybb)):
            continue
        na_true = e_ab - e_a - e_b
        na_pred = eh_ab - (ya - yab) / sd - (yb2 - ybb) / sd
        num += float(((na_pred - na_true) ** 2).sum())
        den += float(max((na_true ** 2).sum(), m * sysc.n_y * sysc.floor_frac ** 2))
        mag_na += float((na_true ** 2).sum())
        mag_ab += float((e_ab ** 2).sum())
        n_ok += 1
    res["consistency"] = {"n": n_ok, "nonadditivity_error": num / den if den > 0 else float("nan"),
                          "true_nonadditive_share": mag_na / mag_ab if mag_ab > 0 else float("nan")}
    return res


# ------------------------------------------------------------------------------------------------------------ 5.9
def _interval_coverage(items_scored: list[tuple[TestItem, Prediction]], sysc: EvalSystem, h: str) -> tuple[float, int]:
    hit = tot = 0
    for it, p in items_scored:
        m = sysc.horizon_steps(h, it.dt)
        if len(it.y_future) <= m:
            continue
        yi = _rows(p.y_int, m) if not p.abstain else _rows(p.y_base, m)
        if yi is None or yi.shape != it.y_future[1: m + 1].shape:
            tot += it.y_future[1: m + 1].size
            continue
        sd = _rows(p.y_sd, m) if p.y_sd is not None else None
        sd = np.zeros_like(yi) if sd is None or sd.shape != yi.shape else np.maximum(sd, 0.0)
        hit += int(np.sum(np.abs(yi - it.y_future[1: m + 1]) <= Z90 * sd))
        tot += yi.size
    return (hit / tot if tot else float("nan")), tot


def eval_calibration(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], eff: dict | None = None,
                     n_boot: int = S.N_BOOT, seed: int = 0) -> dict:
    """5.9: coverage, conditional accuracy, false confidence, interval calibration and Brier scores."""
    eff = eff if eff is not None else eval_effects(sysc, items, preds, n_boot, seed)
    sc: list[ItemScore] = eff["_scores"]
    by_id = {it.item_id: it for it in items}
    res: dict = {"n_items": len(sc)}
    cov = np.array([s.covered for s in sc], float)
    res["coverage"] = float(cov.mean()) if len(cov) else float("nan")
    for name, keyf in (("by_detectability", lambda s: s.dclass), ("by_shift_kind", lambda s: s.shift.split(":", 1)[0]),
                       ("by_shift", lambda s: s.shift)):
        g = defaultdict(list)
        for s in sc:
            g[keyf(s)].append(s.covered)
        res[f"coverage_{name}"] = {k: {"coverage": float(np.mean(v)), "n": len(v)} for k, v in sorted(g.items())}
    res["abstention_rate_by_detectability"] = {k: 1.0 - v["coverage"] for k, v in res["coverage_by_detectability"].items()}
    covd = [s for s in sc if s.covered]
    res["EE_covered"] = _ee(covd, PRIMARY, n_boot, seed)
    det_cov = [s for s in covd if np.isfinite(s.es) and s.es >= 1.0]
    if det_cov:
        ind = np.array([(s.ee_i > 1.0) or s.wrong_sign_confident for s in det_cov], float)
        e = S.boot_mean(ind, [s.group for s in det_cov], n_boot, seed)
        res["false_confidence"] = {"rate": e.point, "ci95": e.ci95, "n": len(det_cov),
                                   "n_worse_than_no_effect": int(sum(s.ee_i > 1.0 for s in det_cov)),
                                   "n_wrong_sign": int(sum(s.wrong_sign_confident for s in det_cov))}
    else:
        res["false_confidence"] = {"rate": float("nan"), "ci95": [float("nan")] * 2, "n": 0}
    pairs = [(by_id[s.item_id], preds[s.item_id]) for s in sc]
    res["interval_coverage_90"] = {}
    for h in HORIZON_FRACTIONS:
        c, n = _interval_coverage(pairs, sysc, h)
        res["interval_coverage_90"][h] = {"coverage": c, "calibration_error": abs(c - 0.9) if np.isfinite(c) else float("nan"),
                                          "n_cells": n}
    res["reports_uncertainty"] = bool(any(p.y_sd is not None for _, p in pairs))
    # Brier scores
    f = sysc.floor_frac
    bd, bs = [], []
    for s in sc:
        p = preds[s.item_id]
        unc = p.uncertainty or {}
        outcome_det = float(np.isfinite(s.es) and s.es >= 1.0)
        if "p_detectable" in unc and unc["p_detectable"] is not None and np.isfinite(float(unc["p_detectable"])):
            pd = float(np.clip(float(unc["p_detectable"]), 0.0, 1.0))
        elif p.abstain or p.error is not None:
            pd = 0.5
        else:
            pd = float(s.pred_es >= 1.0)              # the implied claim, on the scale of the outcome (ES >= 1)
        bd.append((pd - outcome_det) ** 2)
        if s.true_mean_effect is not None:
            tm = s.true_mean_effect
            det = np.abs(tm) > f
            ps = unc.get("p_sign_pos")
            for d in np.flatnonzero(det):
                if ps is not None and np.size(ps) == tm.size and np.isfinite(np.asarray(ps, float)[d]):
                    q = float(np.clip(np.asarray(ps, float)[d], 0.0, 1.0))
                elif p.abstain or p.error is not None:
                    q = 0.5
                else:
                    pm = s.pred_mean_effect[d] if s.pred_mean_effect is not None else 0.0
                    q = 1.0 if pm > 0 else (0.0 if pm < 0 else 0.5)
                bs.append((q - float(tm[d] > 0)) ** 2)
    res["brier_detectable"] = {"score": float(np.mean(bd)) if bd else float("nan"), "n": len(bd)}
    res["brier_sign"] = {"score": float(np.mean(bs)) if bs else float("nan"), "n": len(bs)}
    return res


# ------------------------------------------------------------------------------------------------------------ 5.12
def _auc(score_bad: np.ndarray, score_good: np.ndarray) -> float:
    """P(score of a bad item < score of a good item) + 0.5 P(tie): the validity score as a detector of bad items."""
    if len(score_bad) == 0 or len(score_good) == 0:
        return float("nan")
    allv = np.concatenate([score_bad, score_good])
    from scipy.stats import rankdata
    r = rankdata(allv)
    rb = r[: len(score_bad)].sum()
    # Mann-Whitney U of "good above bad"
    u_bad_low = len(score_bad) * len(score_good) + len(score_bad) * (len(score_bad) + 1) / 2 - rb
    return float(u_bad_low / (len(score_bad) * len(score_good)))


def eval_ood(sysc: EvalSystem, items: list[TestItem], preds: dict[str, Prediction], eff: dict | None = None, n_boot: int = S.N_BOOT,
             seed: int = 0) -> dict:
    """5.12: per OOD / robustness shift EE and NMSE relative to in-distribution, validity AUC, uncertainty ratio."""
    eff = eff if eff is not None else eval_effects(sysc, items, preds, n_boot, seed)
    sc: list[ItemScore] = eff["_scores"]
    h = PRIMARY
    ind = [s for s in sc if s.shift == "in"]
    ee_in = _ee(ind, h, n_boot, seed)
    res: dict = {"EE_in": ee_in, "categories": {}}
    cats = sorted({s.shift for s in sc if s.shift.split(":", 1)[0] in ("ood", "robust")})
    for c in cats:
        rows = [s for s in sc if s.shift == c]
        e = _ee(rows, h, n_boot, seed)
        pn = [s.post_nmse[h] for s in rows if h in s.post_nmse]
        res["categories"][c] = {"EE": e, "EE_ratio_to_in": (e["point"] / ee_in["point"] if ee_in["point"] and np.isfinite(ee_in["point"])
                                                            else float("nan")),
                                "post_nmse": float(np.mean(pn)) if pn else float("nan"), "n_items": len(rows)}
    # validity AUC over every scored item with a finite validity score
    good, bad = [], []
    for s in sc:
        v = preds[s.item_id].validity or {}
        score = v.get("score")
        if score is None or not np.isfinite(float(score)) or not np.isfinite(s.ee_i):
            continue
        (bad if s.ee_i > 1.0 else good).append(float(score))
    res["validity_auc"] = {"auc": _auc(np.array(bad), np.array(good)), "n_bad": len(bad), "n_good": len(good)}
    # uncertainty ratio
    by_id = {it.item_id: it for it in items}

    def mean_sd_and_rmse(rows):
        sds, errs = [], []
        for s in rows:
            it, p = by_id[s.item_id], preds[s.item_id]
            m = sysc.horizon_steps(h, it.dt)
            yi = _rows(p.y_int, m)
            if yi is None or yi.shape != it.y_future[1: m + 1].shape:
                continue
            errs.append(float(np.mean(((yi - it.y_future[1: m + 1]) / sysc.y_sd) ** 2)))
            sd = _rows(p.y_sd, m) if p.y_sd is not None else None
            if sd is not None and sd.shape == yi.shape:
                sds.append(float(np.mean(sd / sysc.y_sd)))
        return (float(np.mean(sds)) if sds else float("nan")), (float(np.sqrt(np.mean(errs))) if errs else float("nan"))

    sd_in, err_in = mean_sd_and_rmse(ind)
    ood_rows = [s for s in sc if s.shift.split(":", 1)[0] in ("ood", "robust")]
    sd_o, err_o = mean_sd_and_rmse(ood_rows)
    res["uncertainty_ratio"] = {"sd_ratio": sd_o / sd_in if sd_in and np.isfinite(sd_in) and sd_in > 0 else float("nan"),
                                "error_ratio": err_o / err_in if err_in and np.isfinite(err_in) and err_in > 0 else float("nan"),
                                "sd_in": sd_in, "sd_ood": sd_o, "rmse_in": err_in, "rmse_ood": err_o}
    return res


# ------------------------------------------------------------------------------------------------------------ convenience
def strip_private(res):
    """Copy of a result without the private per-unit payloads ("_units", "_scores")."""
    if isinstance(res, dict):
        return {k: strip_private(v) for k, v in res.items() if not str(k).startswith("_")}
    if isinstance(res, list):
        return [strip_private(v) for v in res]
    return res


def evaluate_items(model, sysc: EvalSystem, items: list[TestItem], *, composition: bool = True, n_boot: int = S.N_BOOT,
                   seed: int = 0, preds: dict[str, Prediction] | None = None) -> dict:
    """Every item-level family of this module on one system: predictions once, then 5.1, 5.2, 5.8, 5.9, 5.12."""
    F = as_fresh(model)
    preds = preds if preds is not None else predict_items(F, sysc, items)
    eff = eval_effects(sysc, items, preds, n_boot, seed)
    out = {"effects": eff, "observational": eval_observational(sysc, items, preds, n_boot, seed),
           "calibration": eval_calibration(sysc, items, preds, eff, n_boot, seed),
           "ood": eval_ood(sysc, items, preds, eff, n_boot, seed)}
    if composition:
        out["composition"] = eval_composition(F, sysc, items, preds, eff, n_boot, seed)
    out["_preds"] = preds
    return out


__all__ = [
    "Fresh",
    "ItemScore",
    "Prediction",
    "eval_calibration",
    "eval_composition",
    "eval_effects",
    "eval_observational",
    "eval_ood",
    "evaluate_items",
    "paired_ee_diff",
    "predict_items",
    "score_item",
    "score_items",
    "strip_private",
]
