"""TRUSTED custom jobs inside the ISOLATED Modal classes (CONTAINER SIDE), run through the iso "call" role of
`brainir_causal.isolation.run_iso_payload`: the container driver (root) locks the container down, builds the public code directory,
extracts the method snapshot into a private per-job directory and calls the function named by the payload's target (a module file of
/repo/scripts/p4: scripts/p4/p4post_iso.py, which forwards here) with the job's `LinuxUidTransport` and the models as OPAQUE BYTES; every
worker uid is killed and its IPC objects removed afterwards. Packed classes run the same job in a slot of their own
(`isolation.run_iso_packed`). Method code runs only in model workers (`isolation.RemoteFresh`, `isolation.WorkerClient`,
`isolation.fit_records`); worker replies come back through the SAFE codec and nothing a worker produced is unpickled here.

ROLES (job keys beside the standard evaluation job of `harness.system_context`):
  fit_passive     THE CRITICAL ABLATION's data rule (goal5 section 88): the fit data minus every record with events and every twin,
                  with the ablate config -> isolation.fit_records. The side record lists the kept / dropped counts, the kept
                  families and a digest of the kept keys (so the audit can verify that no interventional record reached the fit).
  predict_detail  intervention items of a standard or custom tier (optional filters: roles, item_ids, max_items): predictions in
                  phase A (histories up to the onset only), the standard scoring (evaluate.eval_effects / eval_calibration /
                  eval_ood) with its per-item units, per-item rows (EE_i, ES_i, detectability class, abstention, validity in_domain /
                  score, uncertainty keys, API completeness, predicted sd and realised error), an API probe of the raw counterfactual
                  output (`api_probe`) and, with "closure", phase C (evaluate_mediation.eval_closure: the predicted latent trajectory
                  against re-encoded true futures).
  encodings       encodings of the public training histories and of the pool histories (phase A): eigenvalues, participation
                  ratio, whether the whitening floor binds (self-audit Q5).
  readin_probe    ONE fixed instantaneous event applied at the onset states of many items: the model's read-in dz (read_in, else
                  the two-sample rollout difference) against the generator's true latent effect (synthetic only; Q7).
  memo_probe      leakage probes on RAW workers (no fresh-process guard; Q4 a / b): an item's encoding in a fresh process vs after
                  the same process encoded the item's history EXTENDED by its true future; a prediction in a fresh process vs after
                  decoy encodings. The probes' outputs are never scores.
  lift_jitter     the native lift evaluated in separate RemoteFresh instances: standard simulation, candidate amplitudes jittered by
                  U(0.9, 1.1), and the long horizon; success rates, the magnitudes of every simulated candidate against the capability
                  bounds and the development range (Q8), the multiple-lift divergence at the long vs the medium horizon (Q9).
"""

from __future__ import annotations

import hashlib
import time

import numpy as np

VERSION = "p4post-isojob-2"
EIG_FLOOR = 1e-6
STRONG_MULT = 3.0            # the development range of amplitude classes: up to 3 x the moderate magnitude (suites.MAG_MULT strong)


# ================================================================================================================ helpers
def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def _inputs(job: dict):
    from brainir_causal import harness as H
    inputs, internal, ctx, truth_obj = H.system_context(job)
    if truth_obj is not None:
        H.attach_states(inputs["items"], ctx.store, inputs.get("truth_dir"))
    return inputs, internal, ctx, truth_obj


def _hash_order(item_id: str) -> str:
    return hashlib.sha256(item_id.encode()).hexdigest()


def select_items(items: list, job: dict) -> list:
    """Intervention items, optionally filtered by role (shift or shift kind), item ids, and a deterministic subsample."""
    its = [it for it in items if not it.is_passive]
    roles = job.get("roles")
    if roles:
        rs = set(roles)
        its = [it for it in its if it.shift in rs or str(it.shift).split(":", 1)[0] in rs]
    ids = job.get("item_ids")
    if ids:
        s = set(ids)
        its = [it for it in its if it.item_id in s]
    mx = job.get("max_items")
    if mx and len(its) > int(mx):
        keep = set(sorted((it.item_id for it in its), key=_hash_order)[: int(mx)])
        its = [it for it in its if it.item_id in keep]
    return its


def _remote(blob: bytes, tr, job: dict):
    from brainir_causal import isolation as I
    return I.RemoteFresh(blob, tr, threads=int(job.get("threads", 2)), call_timeout_s=float(job.get("call_timeout_s", 900)))


def _jsonable_events(events) -> list:
    import json
    return json.loads(json.dumps(list(events or []), default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def sd_and_error(sysc, it, p) -> tuple[float | None, float | None]:
    """(mean predicted sd, realised RMS error) of the intervened prediction over the primary window, in readout-sd units (the
    per-item quantities of evaluate.eval_ood's uncertainty ratio); None when missing."""
    from brainir_causal.evalio import PRIMARY
    m = sysc.horizon_steps(PRIMARY, it.dt)
    yi = p.y_int if not p.abstain else p.y_base
    if yi is None or len(yi) <= m or len(it.y_future) <= m:
        return None, None
    a = np.asarray(yi, float)[1: m + 1]
    b = np.asarray(it.y_future, float)[1: m + 1]
    if a.shape != b.shape or not np.isfinite(a).all():
        return None, None
    err = float(np.sqrt(np.mean(((a - b) / sysc.y_sd) ** 2)))
    sd = None
    if p.y_sd is not None and len(p.y_sd) > m:
        s_ = np.asarray(p.y_sd, float)[1: m + 1]
        if s_.shape == a.shape and np.isfinite(s_).all():
            sd = float(np.mean(np.maximum(s_, 0.0) / sysc.y_sd))
    return sd, err


def item_row(s, p, it, meta: dict | None, with_events: bool = False, sysc=None) -> dict:
    """One scored intervention item (evaluate.ItemScore + evaluate.Prediction + the TestItem)."""
    v = p.validity or {}
    unc = p.uncertainty or {}
    zi = p.z_int
    sd, err = sd_and_error(sysc, it, p) if sysc is not None else (None, None)
    row = {"item": s.item_id, "family": s.family, "shift": s.shift, "mclass": s.magnitude_class, "cell": s.cell, "dclass": s.dclass,
           "es": _f(s.es), "ee_i": _f(s.ee_i), "num": {h: _f(x) for h, x in s.num.items()}, "den": {h: _f(x) for h, x in s.den.items()},
           "post_nmse": {h: _f(x) for h, x in s.post_nmse.items()}, "abstain": bool(s.abstain), "covered": bool(s.covered),
           "failed": bool(s.failed), "error": (str(p.error)[:200] if p.error else None), "fc_eligible": bool(s.fc_eligible),
           "fc": bool(s.fc), "pred_es": _f(s.pred_es), "wrong_sign": bool(s.wrong_sign_confident), "sign_hits": int(s.sign_hits),
           "sign_total": int(s.sign_total),
           "validity_in_domain": (bool(v["in_domain"]) if isinstance(v.get("in_domain"), (bool, np.bool_)) else None),
           "validity_score": _f(v.get("score")), "validity_reasons": [str(x)[:120] for x in (v.get("reasons") or [])][:3],
           "has_validity": bool(v), "has_y_int": p.y_int is not None, "has_y_base": p.y_base is not None, "has_y_sd": p.y_sd is not None,
           "uncertainty_keys": sorted(str(k) for k in unc), "p_detectable": _f(unc.get("p_detectable")),
           "has_z_int": zi is not None, "has_z_base": p.z_base is not None,
           "z_shape": list(np.shape(zi)) if zi is not None else None,
           "z_finite": bool(np.isfinite(np.asarray(zi, float)).all()) if zi is not None else None,
           "onset": _f(it.onset), "target_set": [int(u) for u in (it.target_set or ())], "meta": meta or {},
           "pred_sd": sd, "rmse": err}
    if with_events:
        row["events"] = _jsonable_events(it.events)
    return row


def api_probe(rf, sysc, items: list, n: int) -> dict:
    """The raw counterfactual output of the first n items (goal5 section 90: predicted future under the intervention, uncertainty,
    validity, latent trajectory, effect relative to no intervention): keys present, shapes, effect == y_int - y_base, and what the
    separate uncertainty() / validity() methods return. Histories up to the onset only (phase A)."""
    sid = sysc.system_id
    out = {"n": 0, "keys": {}, "effect_consistent": 0, "effect_present": 0, "shape_ok_y": 0, "shape_ok_z": 0, "abstain_flag": 0,
           "validity_keys": {}, "uncertainty_keys": {}, "uncertainty_method": {}, "validity_method": {}, "errors": []}
    for it in items[: max(0, int(n))]:
        H1 = len(it.u_future)
        try:
            raw = rf.intervention_effect(sid, it.x_hist, it.u_hist, it.u_future, list(it.events), it.dt)
        except Exception as e:  # noqa: BLE001 - recorded
            out["errors"].append(f"intervention_effect: {type(e).__name__}: {str(e)[:160]}")
            continue
        out["n"] += 1
        if not isinstance(raw, dict):
            out["errors"].append("intervention_effect returned no dict")
            continue
        for k in raw:
            out["keys"][str(k)] = out["keys"].get(str(k), 0) + 1
        yi, yb = raw.get("y_int"), raw.get("y_base")
        if yi is not None and yb is not None and np.shape(yi) == np.shape(yb) and len(np.shape(yi)) >= 1 and np.shape(yi)[0] == H1:
            out["shape_ok_y"] += 1
            if raw.get("effect") is not None:
                out["effect_present"] += 1
                e = np.asarray(raw["effect"], float) - (np.asarray(yi, float) - np.asarray(yb, float))
                if np.shape(raw["effect"]) == np.shape(yi) and np.nanmax(np.abs(e)) <= 1e-9 * max(1.0, float(np.nanmax(np.abs(yi)))):
                    out["effect_consistent"] += 1
        zi, zb = raw.get("z_int"), raw.get("z_base")
        if zi is not None and zb is not None and np.shape(zi) == np.shape(zb) and np.ndim(zi) == 2 and np.shape(zi)[0] == H1:
            out["shape_ok_z"] += 1
        if isinstance(raw.get("abstain"), (bool, np.bool_)):
            out["abstain_flag"] += 1
        for k in (raw.get("validity") or {}):
            out["validity_keys"][str(k)] = out["validity_keys"].get(str(k), 0) + 1
        for k in (raw.get("uncertainty") or {}):
            out["uncertainty_keys"][str(k)] = out["uncertainty_keys"].get(str(k), 0) + 1
        for name, call in (("uncertainty_method", lambda: rf.uncertainty(sid, it.x_hist, it.u_hist, it.u_future, list(it.events), it.dt)),
                           ("validity_method", lambda: rf.validity(sid, it.x_hist, it.u_hist, list(it.events)))):
            try:
                r = call()
                for k in (r or {}):
                    out[name][str(k)] = out[name].get(str(k), 0) + 1
            except Exception as e:  # noqa: BLE001
                out["errors"].append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
    out["errors"] = out["errors"][:20]
    return out


# ================================================================================================================ fit roles
def fit_passive(job: dict, tr) -> dict:
    """isolation.fit_job with the passive-only data rule (module docstring)."""
    from brainir_causal import isolation as I
    from brainir_causal.runner import load_records
    t0 = time.time()
    recs, sysinfo = load_records(list(job["data"]), list(job["systems"]), {"train"})
    keep = [r for r in recs if not (r.protocol.get("events") or []) and not (r.meta or {}).get("twin_of")]
    if not keep:
        raise ValueError("no passive training records")
    keys = sorted(r.key for r in keep)
    out = I.fit_records(tr, method=job["method"], records=keep, systems=sysinfo, config=job.get("config"), seed=int(job.get("seed", 0)),
                        threads=int(job.get("threads", 3)), timeout_s=float(job.get("timeout_s", 4 * 3600)))
    side = out["side"]
    side.update({"systems": list(job["systems"]), "seed": int(job.get("seed", 0)), "config": dict(job.get("config") or {}),
                 "adapted": False, "splits": "train (passive only)", "bootstrap": None, "n_train": len(keep),
                 "job_wall_s": round(time.time() - t0, 2),
                 "passive_view": {"n_all": len(recs), "n_kept": len(keep), "n_dropped_events_or_twins": len(recs) - len(keep),
                                  "n_kept_with_events": sum(1 for r in keep if r.protocol.get("events")),
                                  "families_kept": sorted({str(r.family) for r in keep}),
                                  "keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest()},
                 "isolation": {"transport": getattr(tr, "kind", "?"), "worker": {k: v for k, v in out["worker"].items() if k != "stderr_tail"}}})
    return {"model": out["model"], "side": side}


# ================================================================================================================ eval roles
def predict_detail(job: dict, tr, blob: bytes) -> dict:
    from brainir_causal import evaluate as EV
    t0 = time.time()
    inputs, internal, ctx, truth_obj = _inputs(job)
    sysc, sid = inputs["system"], job["sid"]
    items = select_items(inputs["items"], job)
    by_id = {it.item_id: it for it in items}
    n_boot, seed = int(job.get("n_boot", 2000)), int(job.get("seed", 0))
    rf = _remote(blob, tr, job)
    closure, probe, info = None, None, {}
    try:
        info = rf.info() or {}
        preds = EV.predict_items(rf, sysc, items)
        probe = api_probe(rf, sysc, items, int(job.get("n_probe", 12)))
        if job.get("closure"):
            from brainir_causal import evaluate_mediation as EM
            rf.set_phase("C")
            try:
                closure = EM.eval_closure(rf, sysc, items, preds, n_boot=n_boot, seed=seed)
            except Exception as e:  # noqa: BLE001 - recorded
                closure = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    finally:
        iso = rf.close()
    eff = EV.eval_effects(sysc, items, preds, n_boot, seed)
    cal = EV.eval_calibration(sysc, items, preds, eff, n_boot, seed)
    ood = EV.eval_ood(sysc, items, preds, eff, n_boot, seed)
    row_meta: dict = {}
    keys = list(job.get("row_meta_keys") or [])
    if keys:
        for r in inputs["heldout"].rows:
            if r.get("split") == "test":
                row_meta[r["key"][:24]] = {k: (r.get("meta") or {}).get(k) for k in keys}
    rows = [item_row(s, preds[s.item_id], by_id[s.item_id], row_meta.get(s.item_id), bool(job.get("with_events")), sysc)
            for s in eff["_scores"]]
    return {"sid": sid, "kind": internal.get("kind"), "n_items": len(items), "n_scored": len(rows),
            "info": {k: info.get(k) for k in ("k", "k_range", "abstain", "history", "validity_domain", "ablated", "method")},
            "effects": {**EV.strip_private(eff), "_units": eff.get("_units")}, "calibration": EV.strip_private(cal),
            "ood": EV.strip_private(ood), "closure": EV.strip_private(closure) if closure else None, "items": rows, "api_probe": probe,
            "isolation": iso, "wall_s": round(time.time() - t0, 2)}


def _eig(Z: np.ndarray) -> np.ndarray:
    Z = np.asarray(Z, float)
    if Z.ndim != 2 or len(Z) < 3:
        return np.array([])
    C = np.atleast_2d(np.cov((Z - Z.mean(0)).T)) if Z.shape[1] > 1 else np.array([[float(np.var(Z[:, 0]))]])
    return np.sort(np.linalg.eigvalsh(C))[::-1]


def participation_ratio(lam: np.ndarray) -> float | None:
    lam = np.maximum(np.asarray(lam, float), 0.0)
    if lam.size == 0 or lam.sum() <= 0:
        return None
    return float(lam.sum() ** 2 / np.sum(lam ** 2))


def encodings(job: dict, tr, blob: bytes) -> dict:
    from brainir_causal import harness as H
    from brainir_causal.fresh import safe_call
    inputs, internal, ctx, truth_obj = _inputs(job)
    sid = job["sid"]
    pool = inputs.get("pool")
    hists = H.whiten_histories(inputs)
    n_pool_max = int(job.get("max_pool", 400))
    rf = _remote(blob, tr, job)
    zp, zq, nfail = [], [], 0
    try:
        info = rf.info() or {}
        for xh, uh, dt in hists:
            z, err = safe_call(rf.encode, sid, xh, uh, dt)
            if err is None and z is not None and np.all(np.isfinite(z)):
                zp.append(np.asarray(z, float).reshape(-1))
            else:
                nfail += 1
        for st in (pool.states[:n_pool_max] if pool is not None else []):
            z, err = safe_call(rf.encode, sid, st.x_hist, st.u_hist, pool.dt)
            if err is None and z is not None and np.all(np.isfinite(z)):
                zq.append(np.asarray(z, float).reshape(-1))
            else:
                nfail += 1
    finally:
        iso = rf.close()
    lam_pub = _eig(np.stack(zp)) if len(zp) >= 3 else np.array([])
    lam_pool = _eig(np.stack(zq)) if len(zq) >= 3 else np.array([])
    k = (info.get("k") or {}).get(sid)
    binds = bool(lam_pub.size and lam_pub.max() > 0 and lam_pub.min() < EIG_FLOOR * lam_pub.max())
    return {"sid": sid, "k": k, "n_public": len(zp), "n_pool": len(zq), "n_failed": nfail, "eig_public": lam_pub.tolist(),
            "eig_pool": lam_pool.tolist(), "pr_pool": participation_ratio(lam_pool), "pr_public": participation_ratio(lam_pub),
            "floor_binds": binds, "isolation": iso}


def _share(D: np.ndarray, W: np.ndarray | None = None) -> float | None:
    """State-dependence share of effects D (n, d) in coordinates whitened by W: 1 - ||mean||^2 / mean ||d||^2 (0 = identical effect
    at every state)."""
    D = np.asarray(D, float)
    if D.ndim != 2 or len(D) < 3:
        return None
    if W is not None:
        D = D @ W
    m2 = float(np.mean(np.sum(D ** 2, axis=1)))
    if m2 <= 1e-300:
        return None
    return float(1.0 - float(np.sum(D.mean(0) ** 2)) / m2)


def readin_probe(job: dict, tr, blob: bytes) -> dict:
    from brainir_causal.evaluate_micro import whitener
    from brainir_causal.fresh import safe_call
    inputs, internal, ctx, truth_obj = _inputs(job)
    sid = job["sid"]
    if truth_obj is None:
        return {"sid": sid, "testable": False, "reason": "no synthetic truth (real system)"}
    items = [it for it in inputs["items"] if not it.is_passive and it.meta.get("state") is not None]
    kick = next((it for it in items if it.events and it.events[0].get("kind") == "kick" and it.events[0].get("delta")), None)
    if kick is None:
        return {"sid": sid, "testable": False, "reason": "no kick item (no instantaneous event with a true latent effect)"}
    unit, val = next(iter(kick.events[0]["delta"].items()))
    ev = {"kind": "kick", "t": 0.0, "delta": {str(unit): float(val)}}
    states = sorted(items, key=lambda it: _hash_order(it.item_id))[: int(job.get("max_states", 32))]
    samples = list(inputs.get("samples") or [])[: int(job.get("max_samples", 96))]
    rf = _remote(blob, tr, job)
    dzm, dzt, src, n_fail = [], [], {"read_in": 0, "rollout": 0}, 0
    Zs, ZT = [], []
    try:
        for it in states:
            z0, err = safe_call(rf.encode, sid, it.x_hist, it.u_hist, it.dt)
            if err is not None or z0 is None or not np.all(np.isfinite(z0)):
                n_fail += 1
                continue
            z0 = np.asarray(z0, float).reshape(-1)
            r, err = safe_call(rf.read_in, sid, z0, ev)
            dz = None
            if err is None and isinstance(r, dict) and r.get("dz") is not None:
                dz = np.asarray(r["dz"], float).reshape(-1)
                src["read_in"] += 1
            else:
                u2 = np.asarray(it.u_future, float)[:2]
                r1, e1 = safe_call(rf.rollout, sid, z0, u2, [ev], it.dt)
                r0, e0 = safe_call(rf.rollout, sid, z0, u2, [], it.dt)
                if e1 is None and e0 is None:
                    dz = np.asarray(r1["z"], float)[1] - np.asarray(r0["z"], float)[1]
                    src["rollout"] += 1
            if dz is None or not np.all(np.isfinite(dz)):
                n_fail += 1
                continue
            try:
                t = np.asarray(truth_obj.true_latent_effect(it.meta["state"], ev), float).reshape(-1)
            except Exception:  # noqa: BLE001
                n_fail += 1
                continue
            dzm.append(dz)
            dzt.append(t)
        for s in samples:
            z, err = safe_call(rf.encode, sid, s.x_hist, s.u_hist, s.dt)
            if err is None and z is not None and np.all(np.isfinite(z)):
                Zs.append(np.asarray(z, float).reshape(-1))
                ZT.append(np.asarray(s.z_true, float).reshape(-1))
    finally:
        iso = rf.close()
    out = {"sid": sid, "testable": len(dzm) >= 5, "event": ev, "n_states": len(dzm), "n_failed": n_fail, "source": src,
           "isolation": iso}
    if len(dzm) < 5:
        out["reason"] = "fewer than 5 usable states"
        return out
    Dm, Dt = np.stack(dzm), np.stack(dzt)
    Wm = whitener(np.stack(Zs))[1] if len(Zs) >= 8 else None
    Wt = whitener(np.stack(ZT))[1] if len(ZT) >= 8 else None
    out["model_share"] = _share(Dm, Wm)
    out["truth_share"] = _share(Dt, Wt)
    if len(Zs) >= 8:
        A1 = np.hstack([np.stack(ZT), np.ones((len(ZT), 1))])
        M = np.linalg.lstsq(A1, np.stack(Zs), rcond=None)[0][:-1]
        out["truth_mapped_share"] = _share(Dt @ M, Wm)
    out["whitened"] = {"model": Wm is not None, "truth": Wt is not None, "n_samples": len(Zs)}
    return out


def memo_probe(job: dict, tr, blob: bytes) -> dict:
    """Self-audit Q4 a / b on raw workers (module docstring)."""
    from brainir_causal import isolation as I
    inputs, internal, ctx, truth_obj = _inputs(job)
    sid = job["sid"]
    items = [it for it in select_items(inputs["items"], {"max_items": int(job.get("n_items", 6)) * 4})
             if it.x_future is not None and len(it.x_future) > 2][: int(job.get("n_items", 6))]
    decoys = [it for it in select_items(inputs["items"], {}) if it.x_future is not None][: int(job.get("n_decoys", 8)) + len(items)]

    def worker():
        w = I.WorkerClient(tr, "probe", method_dir=getattr(tr, "method_dir_in_worker", None), threads=int(job.get("threads", 2)),
                           call_timeout_s=float(job.get("call_timeout_s", 900)))
        w.request("load_model", timeout=600, blob=blob)
        return w

    def enc(w, x, u, dt):
        return np.asarray(w.request("call", name="encode", args=[sid, x, u, dt], kwargs={}), float)

    def pred(w, it):
        r = w.request("call", name="intervention_effect", args=[sid, it.x_hist, it.u_hist, it.u_future, list(it.events), it.dt], kwargs={})
        return {k: np.asarray(r[k], float) for k in ("y_int", "y_base") if isinstance(r, dict) and r.get(k) is not None}

    a_rows, b_rows, errors = [], [], []
    for it in items:
        try:
            w1 = worker()
            z_fresh = enc(w1, it.x_hist, it.u_hist, it.dt)
            z_again = enc(w1, it.x_hist, it.u_hist, it.dt)
            w1.close()
            w2 = worker()
            x_long = np.vstack([it.x_hist, it.x_future[1:]])
            u_long = np.vstack([np.asarray(it.u_hist, float).reshape(len(it.u_hist), -1),
                                np.asarray(it.u_future, float).reshape(len(it.u_future), -1)[1:]])
            enc(w2, x_long, u_long, it.dt)
            z_after = enc(w2, it.x_hist, it.u_hist, it.dt)
            w2.close()
            a_rows.append({"item": it.item_id, "same_process_repeat_equal": bool(np.array_equal(z_fresh, z_again)),
                           "after_future_equal": bool(np.array_equal(z_fresh, z_after)),
                           "max_abs_diff": float(np.max(np.abs(z_fresh - z_after))) if z_fresh.shape == z_after.shape else None})
            w3 = worker()
            p_fresh = pred(w3, it)
            w3.close()
            w4 = worker()
            for d in [d for d in decoys if d.item_id != it.item_id][: int(job.get("n_decoys", 8))]:
                enc(w4, np.vstack([d.x_hist, d.x_future[1:]]), np.vstack([np.asarray(d.u_hist, float).reshape(len(d.u_hist), -1),
                                                                            np.asarray(d.u_future, float).reshape(len(d.u_future), -1)[1:]]), d.dt)
            p_after = pred(w4, it)
            w4.close()
            same = bool(p_fresh.keys() == p_after.keys() and all(np.array_equal(p_fresh[k], p_after[k]) for k in p_fresh))
            b_rows.append({"item": it.item_id, "after_decoys_equal": same})
        except Exception as e:  # noqa: BLE001 - recorded (a failing probe is not a pass)
            errors.append(f"{it.item_id}: {type(e).__name__}: {str(e)[:200]}")
        finally:
            # only the probe role's uid of THIS job (its slot in a packed container): never another slot's workers
            I.kill_uids([I.role_uid("probe", getattr(tr, "slot", None))])
    return {"sid": sid, "a": a_rows, "b": b_rows, "errors": errors[:10],
            "a_all_equal": bool(a_rows) and all(r["after_future_equal"] and r["same_process_repeat_equal"] for r in a_rows),
            "b_all_equal": bool(b_rows) and all(r["after_decoys_equal"] for r in b_rows)}


def jitter_amplitudes(events: list[dict], rng: np.random.Generator, lo: float = 0.9, hi: float = 1.1) -> list[dict]:
    """Every event's magnitude multiplied by U(lo, hi) (one factor per event; edge scaling: the depth 1 - f; parameters: the change)."""
    import json
    out = json.loads(json.dumps(events))
    for e in out:
        f = float(rng.uniform(lo, hi))
        k = e.get("kind")
        if k == "kick":
            e["delta"] = {u: float(v) * f for u, v in e["delta"].items()}
        elif k == "current":
            e["targets"] = {u: float(v) * f for u, v in e["targets"].items()}
        elif k == "current_seq":
            e["targets"] = {u: [float(v) * f for v in lst] for u, lst in e["targets"].items()}
        elif k == "edge_scale" and float(e.get("factor", 1.0)) > 0:
            e["factor"] = float(min(2.0, max(0.0, 1.0 - (1.0 - float(e["factor"])) * f)))
        elif k == "param":
            e["targets"] = {u: {kk: (1.0 + (float(x) - 1.0) * f if kk in ("gain", "tau") else float(x) * f) for kk, x in v.items()}
                            for u, v in e["targets"].items()}
    return out


def magnitude_flags(events: list[dict], cap: dict) -> dict:
    """Per candidate: any event magnitude at the capability's clipping bound (>= 0.999 max) or beyond the development range (> 3 x the
    moderate magnitude, the strong class maximum)."""
    sat = beyond = False
    for e in events or []:
        k = e.get("kind")
        kind = {"kick": "kick", "current": "current", "current_seq": "current"}.get(k)
        if kind is None:
            continue
        c = cap.get(kind) or {}
        mx, mod = c.get("max"), c.get("moderate")
        vals = []
        if k == "kick":
            vals = [abs(float(v)) for v in e["delta"].values()]
        elif k == "current":
            vals = [abs(float(v)) for v in e["targets"].values()]
        else:
            vals = [abs(float(v)) for lst in e["targets"].values() for v in lst]
        for v in vals:
            if mx is not None and v >= 0.999 * float(mx):
                sat = True
            if mod is not None and v > STRONG_MULT * float(mod) * (1 + 1e-9):
                beyond = True
    return {"saturating": sat, "beyond_dev": beyond}


def lift_jitter(job: dict, tr, blob: bytes) -> dict:
    from brainir_causal import harness as H
    from brainir_causal.sampling import normalize_capability
    from brainir_causal.evaluate_lift import LiftConfig, encodings_from_histories, eval_native_lift
    inputs, internal, ctx, truth_obj = _inputs(job)
    sysc, sid = inputs["system"], job["sid"]
    pub = inputs["record"]
    cap = normalize_capability(pub.get("capability"), t_end=float(pub["t_end_default"]), dt=float(pub["dt"]),
                                  input_dim=int(pub.get("input_dim", 1)))
    cases = H.lift_cases_for(inputs)
    hists = H.whiten_histories(inputs)
    base = H.simulate_many_for(ctx)
    n_boot, seed = int(job.get("n_boot", 2000)), int(job.get("seed", 0))
    seen: list = []
    rng = np.random.default_rng(int(job.get("jitter_seed", 8)))

    def rec_sim(protos, full=False):
        seen.extend(list(q.get("events") or []) for q in protos if q.get("events"))
        return base(protos, full=full)

    def jit_sim(protos, full=False):
        return base([dict(q, events=jitter_amplitudes(q["events"], rng)) if q.get("events") else q for q in protos], full=full)

    def one(sim, horizon: str = "medium"):
        rf = _remote(blob, tr, job)
        try:
            zpub = None
            try:
                zpub = encodings_from_histories(rf, sid, hists)
            except Exception:  # noqa: BLE001
                zpub = None
            rf.set_phase("lift")
            wkw = {"whiten_z": zpub} if zpub is not None and len(zpub) else {"whiten_histories": hists}
            res = eval_native_lift(rf, sid, cases, sim, horizon_s=sysc.horizon_s(horizon), floor=sysc.floor,
                                   validator=H.lift_validator(internal) if internal else None, truth=bool(sysc.kind == "synthetic"),
                                   cfg=LiftConfig(n_boot=n_boot, seed=seed), **wkw)
        finally:
            iso = rf.close()
        return res, iso

    r0, iso0 = one(rec_sim)
    r1, iso1 = one(jit_sim)
    r2, iso2 = one(base, "long") if job.get("long_horizon", True) else ({}, None)
    flags = [magnitude_flags(evs, cap) for evs in seen]
    s0, s1 = _f(r0.get("success_rate")), _f(r1.get("success_rate"))

    def cons_raw(r):
        c = (r or {}).get("consistency") or {}
        return _f((c.get("raw") or {}).get("point")) if c.get("testable") else None
    c_med, c_long = cons_raw(r0), cons_raw(r2)
    out = {"sid": sid, "supported": bool(r0.get("supported", True)), "n_requests": r0.get("n_requests"), "success_rate": s0,
           "success_rate_jitter": s1, "relative_drop": (1.0 - s1 / s0) if (s0 and s1 is not None and s0 > 0) else None,
           "n_candidates_simulated": len(seen), "share_saturating": float(np.mean([f["saturating"] for f in flags])) if flags else None,
           "share_beyond_dev": float(np.mean([f["beyond_dev"] for f in flags])) if flags else None,
           "share_saturating_or_beyond": float(np.mean([f["saturating"] or f["beyond_dev"] for f in flags])) if flags else None,
           "consistency_medium": c_med, "consistency_long": c_long,
           "consistency_long_over_medium": (c_long / c_med) if (c_med and c_long is not None and c_med > 0) else None,
           "n_requests_long": (r2 or {}).get("n_requests"), "success_rate_long": _f((r2 or {}).get("success_rate")),
           "exact_per_lift": None, "isolation": {"standard": iso0, "jitter": iso1, "long": iso2}}
    lifts = r0.get("per_lift")                        # the evaluator's per-lift records (evaluate_lift.eval_native_lift, LOG P4-D50)
    if isinstance(lifts, list):
        succ = [lf for lf in lifts if lf.get("success")]
        fl = [magnitude_flags(lf.get("raw_events") or [], cap) for lf in succ]
        known = [lf for lf in succ if lf.get("clipped") is not None or lf.get("beyond_dev_range") is not None]
        out["exact_per_lift"] = {"n_successful": len(succ),
                                 "share_saturating_or_beyond": float(np.mean([f["saturating"] or f["beyond_dev"] for f in fl])) if fl else None,
                                 # the simulator's realized kick clipping or a magnitude beyond the development range of ANY kind
                                 "share_clipped_or_beyond_dev": (float(np.mean([bool(lf.get("clipped")) or bool(lf.get("beyond_dev_range"))
                                                                               for lf in known])) if known else None),
                                 "n_known_clipping_or_range": len(known)}
    return out


FIT_ROLES = {"fit_passive": fit_passive}
EVAL_ROLES = {"predict_detail": predict_detail, "encodings": encodings, "readin_probe": readin_probe, "memo_probe": memo_probe,
              "lift_jitter": lift_jitter}
