"""Validation of the benchmark references on the synthetic DEV tier (ORCHESTRATOR SIDE; research/phase4/REFERENCE_LEARNER_V2.md).

    validate_system(sid, tier_root, tier="dev", public_root=None, overrides=None, n_boot=500, variant="v2", names=None) -> JSON row
    tier_overview(tier_root, tier="dev") -> the systems and whether their truth carries the effective draw

DESCRIPTIVE and dev-only: it never feeds the calibration. For one compressible dev system it loads the data exactly as the calibration
does (`suites.load_eval_inputs`: public D0 + D1 with their truth, the evaluation items, the held-out histories registered with their
truth / readouts), fits TRUE-STATE, FULL-STATE, OBS-SHORTCUT (where the system defines z_obs) and ID-SHORTCUT (NO-EFFECT = the
FULL-STATE's passive predictions), and scores every reference with the frozen evaluator (`evaluate.evaluate_items`) on one COMMON item
set: the verdict items whose every event targets units intervened in training with that kind (`event_coverage` / `covered`: the
model-free form of the references' `covers` rule, so candidate learners with and without that rule are scored on the same items).
The v1 comparison of research/phase4/REFERENCE_LEARNER_V2.md ran the previous learner through the same function from a temporary
module (removed after the run). Reported per reference: the class-balanced and pooled EE at the primary horizon (with the identity-cell CI), EE per shift
kind, the short / long-horizon EE, abstentions, fit seconds; for trap systems also the EE of TRUE-STATE and OBS-SHORTCUT on the items of
the EXPOSING families. `names` chooses the references (default: TRUE-STATE, FULL-STATE, OBS-SHORTCUT, ID-SHORTCUT); a name may be a
z-only reference ('true_state_zonly', 'obs_shortcut_zonly') or carry a one-step mode ('full_state@two_stage': the same reference
fitted with LearnerConfig.one_step_mode = 'two_stage'), so the variants of one system are scored on the same items in one job.
"""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path


def event_coverage(records: list, observed: list[int]) -> dict:
    """{(kind, field) -> set of observed units} intervened in the training records: kick, current (incl. current_seq), silence, edge
    (the post-synaptic unit), param:<field>. The model-free version of the references' `covers` rule, so that every candidate learner
    is scored on the SAME items."""
    obs = {int(u) for u in observed}
    cov: dict = {}
    for r in records:
        prot = r.protocol if hasattr(r, "protocol") else r["protocol"]
        for e in prot.get("events") or []:
            k = e["kind"]
            if k == "kick":
                cov.setdefault("kick", set()).update(int(n) for n in e["delta"] if int(n) in obs)
            elif k in ("current", "current_seq"):
                cov.setdefault("current", set()).update(int(n) for n in e["targets"] if int(n) in obs)
            elif k == "silence":
                cov.setdefault("silence", set()).update(int(n) for n in e["targets"] if int(n) in obs)
            elif k == "edge_scale":
                cov.setdefault("edge", set()).update(int(p_) for p_, _ in e["edges"] if int(p_) in obs)
            elif k == "param":
                for n, d in e["targets"].items():
                    for fld in d:
                        if int(n) in obs:
                            cov.setdefault(f"param:{fld}", set()).add(int(n))
    return cov


def _event_ok(e: dict, cov: dict, obs: set[int]) -> bool:
    k = e.get("kind")
    if k == "kick":
        return all(int(n) in cov.get("kick", ()) for n in e["delta"])
    if k in ("current", "current_seq"):
        return all(int(n) in cov.get("current", ()) for n in e["targets"])
    if k == "silence":
        return all(int(n) in cov.get("silence", ()) for n in e["targets"])
    if k == "edge_scale":
        return all(int(p_) in cov.get("edge", ()) and int(q) in obs for p_, q in e["edges"])
    if k == "param":
        return all(int(n) in cov.get(f"param:{fld}", ()) for n, d in e["targets"].items() for fld in d)
    return True


def covered(events: list, cov: dict, observed: list[int]) -> bool:
    """Every event targets units intervened in training with its kind (`event_coverage`)."""
    obs = {int(u) for u in observed}
    return all(_event_ok(e, cov, obs) for e in events)


def _jsonable(o):
    return json.loads(json.dumps(o, default=lambda v: v.item() if hasattr(v, "item") else str(v)))


def tier_overview(tier_root: str, tier: str = "dev", n_sample: int = 20) -> list[dict]:
    """The systems of a tier with their truth summary (type, k, trap) and, from up to n_sample truth trajectories each, whether the
    truth store carries the effective draw ('draw') and its dimension."""
    import numpy as np

    from . import calibrate as CAL
    from .suites import tier_dirs
    if tier != "dev":
        raise ValueError("reference validation runs on the dev tier only")
    root = Path(tier_root)
    tdir = tier_dirs(tier, root)["truth"]
    out = []
    for sid, summ in sorted(CAL.system_truth_summaries(root, tier).items()):
        files = sorted((tdir / sid.replace(":", "_") / "traj").glob("*.npz"))
        n_draw, dims = 0, set()
        for f in files[:n_sample]:
            with np.load(f) as z:
                if "draw" in z.files:
                    n_draw += 1
                    dims.add(int(np.asarray(z["draw"]).size))
        out.append({"sid": sid, "type": summ.get("type"), "k": summ.get("k"), "k_true": CAL.compressible(summ), "trap": summ.get("trap"),
                    "n_truth_files": len(files), "n_sampled": min(n_sample, len(files)), "n_with_draw": n_draw,
                    "draw_dims": sorted(dims), "summary_keys": sorted(summ)})
    return _jsonable(out)


def validate_system(sid: str, tier_root: str, tier: str = "dev", public_root: str | None = None, overrides: dict | None = None,
                    n_boot: int = 500, variant: str = "v2", names: list[str] | None = None) -> dict:
    from . import calibrate as CAL
    from . import refs as R
    if variant != "v2":
        raise ValueError("only the current learner (v2) is available (the v1 comparison module was temporary)")
    from .evaluate import evaluate_items
    from .suites import load_eval_inputs, tier_dirs
    if tier != "dev":
        raise ValueError("reference validation runs on the dev tier only")
    t0 = time.time()
    root = Path(tier_root)
    dirs = tier_dirs(tier, root)
    summary = CAL.system_truth_summaries(root, tier).get(sid, {})
    k_true = CAL.compressible(summary)
    if k_true is None:
        return {"sid": sid, "type": summary.get("type"), "skipped": "not compressible"}
    inp = load_eval_inputs(sid, heldout_dirs=dirs, public_dirs=tier_dirs(tier, Path(public_root)) if public_root else None)
    tdir = dirs["truth"] / sid.replace(":", "_")
    tdir = tdir if tdir.exists() else None
    pset, held = inp["public"], inp["heldout"]
    train = [pset.load(r) for r in pset.rows if r.get("split") in ("train", "twin")]
    z, zo, dr = {}, {}, {}
    for r in train:
        tr = CAL._truth_arrays(tdir, r.key)
        if "z" in tr:
            z[r.key] = tr["z"]
        if "z_obs" in tr:
            zo[r.key] = tr["z_obs"]
        if "draw" in tr:
            dr[r.key] = tr["draw"]
    truth = {"z": z if len(z) == len(train) else None, "z_obs": zo if len(zo) == len(train) else None,
             "draw": dr if len(dr) == len(train) else None}
    cfg = R.LearnerConfig(**{"threads": 4, **(overrides or {})})
    cov = event_coverage(train, inp["record"]["observed"])
    models, fit_s, errors = {}, {}, {}
    for label in (names or ("true_state", "full_state", "obs_shortcut", "id_shortcut")):
        name, _, mode = str(label).partition("@")
        if name.startswith("obs_shortcut") and truth["z_obs"] is None:
            continue
        cfg_l = dataclasses.replace(cfg, one_step_mode=mode) if mode else cfg
        t1 = time.time()
        try:
            models[label] = R.fit_reference(name, sid, train, inp["record"], k=int(k_true), truth=truth, cfg=cfg_l)
        except Exception as exc:  # noqa: BLE001 - recorded
            errors[label] = f"{type(exc).__name__}: {str(exc)[:300]}"
        fit_s[label] = round(time.time() - t1, 1)
    if "full_state" in models:
        models["no_effect"] = R.NoEffectModel(models["full_state"])
    for rr in held.rows:
        rec = held.load(rr)
        tr = CAL._truth_arrays(tdir, rec.key)
        dt = float(rec.protocol["dt"])
        for label, m in models.items():
            key = {"true_state": "z", "obs_shortcut": "z_obs"}.get(label.partition("@")[0].replace("_zonly", ""))
            if key and tr.get(key) is not None and hasattr(m, "register_truth"):
                m.register_truth(rec.x, rec.u, tr[key], dt, draw=tr.get("draw"))
            if label.startswith("id_shortcut"):
                m.register_readout(rec.x, rec.u, rec.y)
    verdict = [it for it in inp["items"] if CAL.is_verdict_item(it)]
    items = [it for it in verdict if covered(it.events, cov, inp["record"]["observed"])]
    exposing = set(summary.get("exposing_families") or [])
    d0 = next(iter(truth["draw"].values())) if truth["draw"] else None
    out = {"sid": sid, "variant": variant, "type": summary.get("type"), "k_true": int(k_true), "trap": summary.get("trap"), "n_train": len(train),
           "n_verdict": len(verdict), "n_items": len(items), "fit_s": fit_s, "errors": errors, "models": {},
           "draw_dim": None if d0 is None else len(d0), "n_obs": len(inp["record"]["observed"])}
    for name, m in models.items():
        try:
            eff = evaluate_items(m, inp["system"], items, composition=False, n_boot=n_boot, seed=0)["effects"]
        except Exception as exc:  # noqa: BLE001
            out["models"][name] = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
            continue
        row = {"EE_cb": eff.get("EE_cb_medium"), "EE": (eff.get("EE_medium") or {}).get("point"), "n_abstained": eff.get("n_abstained"),
               "EE_short": (eff.get("EE_short") or {}).get("point"), "EE_long": (eff.get("EE_long") or {}).get("point"),
               "EE_cb_short": (eff.get("EE_cb_short") or {}).get("point"),
               "by_shift": {k: (v.get("point"), v.get("n_items")) for k, v in (eff.get("by_shift_kind") or {}).items()},
               "by_class": {k: (v.get("point"), v.get("n_items")) for k, v in (eff.get("by_magnitude_class") or {}).items()}}
        if exposing and name.partition("@")[0].replace("_zonly", "") in ("true_state", "obs_shortcut"):
            fam = eff.get("by_family") or {}
            num = den = 0.0
            for f_, v in fam.items():
                if f_ in exposing and v.get("n_items"):
                    num += float(v["point"]) * v["n_items"]
                    den += v["n_items"]
            row["EE_exposing_mean"] = num / den if den else None
            row["n_exposing"] = int(den)
        try:
            info = m.info()
            row["fit_notes"] = {k: v for k, v in (info.get("fit_notes") or {}).items()
                                if k in ("effect_beta_at", "kinds_seen", "n_kick_units", "n_seen_unit_channels", "twin_pairs",
                                         "static_context", "one_step_mode", "paired_post_onset")}
            row["k_info"] = {k: info.get(k) for k in ("k", "k_dynamic", "k_context", "draw_context", "n_registered_without_draw",
                                                      "n_probe_encodes") if k in info}
        except Exception as exc:  # noqa: BLE001 - descriptive extras only
            row["fit_notes_error"] = type(exc).__name__
        out["models"][name] = row
    out["seconds"] = round(time.time() - t0, 1)
    return _jsonable(out)
