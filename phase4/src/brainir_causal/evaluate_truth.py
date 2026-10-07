"""Synthetic ground-truth metrics (benchmarks/causal_state_v1/PROTOCOL.md section 5.16). SYNTHETIC SYSTEMS ONLY.

Truth comes from the synthetic generator's adapter (`brainir_causal.synthadapter`: `system.truth()`, `true_state(micro)`,
`obs_shortcut_state(micro)`, `true_latent_effect(micro, event)`). The dataset builder attaches it to the evaluation inputs
(`StateSample.z_true / z_obs`, `TestItem.z_true / z_obs / dz_true`); `attach_truth` does that from the full microstates in
`meta["micro"]` when the builder did not. The model never sees any of it.

- LATENT RECOVERY: min(R^2 of z_true from z, R^2 of z from [z_true, draw]), cross-fitted by source trajectory (2 folds x 5 repeats)
  with the linear + random-feature ridge regressor (PROTOCOL 5.3 capacity rule); R^2 = 1 - SSE / SST over standardised target
  coordinates. A z that misses content fails the first direction, a z that carries extra content (e.g. nuisance) fails the second.
  `draw` = the source trajectory's effective draw parameters (the generator's draw_effective; every trajectory has its own parameter
  draw, so a history-based state may carry static coordinates identifying it: LOG P4-D43); without them the second direction uses
  z_true alone and says so. R^2 of z from z_true alone is always reported.
- z_obs CAPTURE (trap types): the EXPOSED causal variable = the part of z_true not predictable from z_obs (cross-fitted residual);
  reported as the R^2 of the exposed variable from z (a model that learned only the observational shortcut scores about 0).
- DIMENSION: k CONSISTENT with the truth, k_true <= k <= k_true + d_draw (the generator's effective draw dimension; 0 when it
  does not report one; LOG P4-D43), with k = k_true reported beside; k_true within the reported range; correct "no compact causal
  state" on non-compressible types (truth k == "none"), or a false alarm elsewhere.
- TRUE READ-IN ACCURACY: for verdict items whose first event is instantaneous and acts at the onset, each model quantity against the
  truth of ITS OWN definition (review H, N4: the exact jump and what one sample later shows differ by a median 4 %, up to 15 %):
  headline ("next_sample", every model with rollouts): the rollout difference one sample after the onset, z_int[1] - z_base[1],
  against the true latent difference item - twin one sample after the onset (`dz_true_next`; the quantity the lift miss measures);
  beside it ("exact", models whose read_in returns dz): read_in(z0, event)["dz"] against the exact true latent effect of the event
  (`dz_true`). Truth is mapped into model coordinates by the affine map z ~ z_true fitted on states that SPAN the true state: the
  held-out samples, every item's onset state (with the model's onset encoding) and the pool states; when those states do not span it
  (numerical rank of the centred z_true below its dimension) the score is "unidentifiable" (review H round 3b, NEW-5). R^2 over
  items, the relative error and the median cosine similarity. Reported, not binding.
"""

from __future__ import annotations

import numpy as np

from .evalio import StateSample, TestItem
from .evaluate import Prediction
from .evaluate_mediation import REPEATS, fold_masks, n_rff, rff_raw, ridge_cv_fit_predict, standardise
from .fresh import as_fresh, safe_call


def attach_truth(system, items: list[TestItem] | None = None, samples: list[StateSample] | None = None) -> None:
    """Fill z_true / z_obs / dz_true of items from the full microstate at the onset in meta["state"] (the adapter's name for it, as
    returned by simulate(protocol, full=True)["state"]; "micro" is accepted as an alias), using the adapter object `system`:
    true_state(state), obs_shortcut_state(state), true_latent_effect(state, event).
    dz_true uses the TRUE (simulated) first event (`TestItem.true_events` when the model was told other events: amplitude / timing
    jitter; review H, minor 6), and only when that event is instantaneous and acts AT the onset (a jittered event acting later meets
    another microstate than the onset state, so its dz_true is left undefined)."""
    for it in items or []:
        micro = it.meta.get("state", it.meta.get("micro"))
        if micro is None:
            continue
        if it.z_true is None:
            it.z_true = np.asarray(system.true_state(micro), float)
        if it.z_obs is None:
            zo = system.obs_shortcut_state(micro)
            it.z_obs = None if zo is None else np.asarray(zo, float)
        evs = it.true_events if it.true_events is not None else it.events
        first = min(evs, key=lambda e: float(e.get("t", e.get("t0", 0.0)))) if evs else None
        if it.dz_true is None and first is not None and "t" in first and abs(float(first["t"])) <= 1e-9 + 1e-6 * it.dt:
            it.dz_true = np.asarray(system.true_latent_effect(micro, first), float)


def _crossfit_r2(X: np.ndarray, Y: np.ndarray, groups: np.ndarray, seed: int, repeats: int = REPEATS) -> float:
    """Cross-fitted R^2 of Y from X (linear + random features, ridge penalty by an inner split by group)."""
    X = np.asarray(X, float)
    Y = np.asarray(Y, float)
    Y = Y[:, None] if Y.ndim == 1 else Y
    if len(X) < 8 or len(np.unique(groups)) < 4:
        return float("nan")
    Ys = standardise(Y)                      # target coordinates that do not vary are dropped (never divided by a tiny sd)
    if Ys.shape[1] == 0:
        return float("nan")
    nf = n_rff(len(X))
    sse = np.zeros(Ys.shape[1])
    sst = np.zeros(Ys.shape[1])
    n_ok = 0
    for rep in range(repeats):
        fm = fold_masks(groups, rep, seed)
        if fm is None:
            break
        Xs = standardise(X)
        feats = np.hstack([Xs, rff_raw(Xs, nf, np.random.default_rng(seed + 31 + rep))])
        pred = np.zeros_like(Ys)
        ok = True
        for tr_m in fm:
            if tr_m.sum() < 4 or (~tr_m).sum() < 4:
                ok = False
                break
            pred[~tr_m] = ridge_cv_fit_predict(feats[tr_m], Ys[tr_m], feats[~tr_m], groups[tr_m], seed=seed + rep)
        if not ok:
            continue
        sse += ((pred - Ys) ** 2).sum(0)
        sst += ((Ys - Ys.mean(0)) ** 2).sum(0)
        n_ok += 1
    if n_ok == 0 or sst.sum() <= 0:
        return float("nan")
    return float(1.0 - sse.sum() / sst.sum())


def _crossfit_residual(X: np.ndarray, Y: np.ndarray, groups: np.ndarray, seed: int) -> np.ndarray:
    """Cross-fitted residual of Y after predicting it from X (one 2-fold split)."""
    Y = np.asarray(Y, float)
    Y = Y[:, None] if Y.ndim == 1 else Y
    fm = fold_masks(groups, 0, seed)
    if fm is None:
        return Y - Y.mean(0)
    Xs = standardise(np.asarray(X, float))
    feats = np.hstack([Xs, rff_raw(Xs, n_rff(len(Xs)), np.random.default_rng(seed + 77))])
    res = np.zeros_like(Y)
    for tr_m in fm:
        res[~tr_m] = Y[~tr_m] - ridge_cv_fit_predict(feats[tr_m], Y[tr_m], feats[~tr_m], groups[tr_m], seed=seed)
    return res


def encode_samples(model, sid: str, samples: list[StateSample]) -> tuple[np.ndarray | None, int]:
    F = as_fresh(model)
    Z, n_fail = [], 0
    for s in samples:
        z, err = safe_call(F.encode, sid, s.x_hist, s.u_hist, s.dt)
        if err or z is None or not np.isfinite(np.asarray(z, float)).all():
            n_fail += 1
            continue
        Z.append(np.asarray(z, float).reshape(-1))
    return (np.stack(Z) if Z and not n_fail else None), n_fail


def eval_latent_recovery(model, sid: str, samples: list[StateSample], seed: int = 0) -> dict:
    """Latent recovery and z_obs capture on held-out state samples (see the module docstring)."""
    if len(samples) < 8:
        return {"note": "too few samples", "n": len(samples)}
    Z, n_fail = encode_samples(model, sid, samples)
    if Z is None:
        return {"note": "failed or non-finite encodings", "n_failed": n_fail, "recovery": float("nan")}
    ZT = np.stack([np.asarray(s.z_true, float).reshape(-1) for s in samples])
    g = np.array([s.group for s in samples])
    r_true_from_z = _crossfit_r2(Z, ZT, g, seed)
    r_z_from_true = _crossfit_r2(ZT, Z, g, seed + 1)
    has_draw = all(s.draw is not None and np.size(s.draw) > 0 for s in samples)
    r_rev = r_z_from_true
    if has_draw:
        D = np.stack([np.asarray(s.draw, float).reshape(-1) for s in samples])
        r_rev = _crossfit_r2(np.hstack([ZT, D]), Z, g, seed + 5)
    res = {"n": len(samples), "r2_true_from_z": r_true_from_z, "r2_z_from_true": r_z_from_true,
           "r2_z_from_true_and_draw": (r_rev if has_draw else None), "reverse_uses_draw": bool(has_draw),
           "recovery": float(np.nanmin([r_true_from_z, r_rev])) if np.isfinite([r_true_from_z, r_rev]).any() else float("nan")}
    if all(s.z_obs is not None for s in samples):
        ZO = np.stack([np.asarray(s.z_obs, float).reshape(-1) for s in samples])
        exposed = _crossfit_residual(ZO, ZT, g, seed + 2)
        res["exposed_variance_share"] = float(exposed.var(0).sum() / max(ZT.var(0).sum(), 1e-12))
        res["zobs_capture_r2_exposed_from_z"] = _crossfit_r2(Z, exposed, g, seed + 3)
        res["r2_zobs_from_z"] = _crossfit_r2(Z, ZO, g, seed + 4)
    return res


def eval_dimension_truth(k_model: int | None, k_range: tuple[int, int] | None, truth: dict, declared_no_compact: bool) -> dict:
    """k consistent with k_true (k_true <= k <= k_true + d_draw), k = k_true, k_true within the range, and the correctness of a declared
    "no compact causal state"."""
    kt = truth.get("k")
    noncompressible = kt in ("none", None) or truth.get("compressible") is False
    out = {"k_true": kt, "k_model": k_model, "noncompressible": bool(noncompressible), "declared_no_compact": bool(declared_no_compact)}
    if noncompressible:
        out["abstention_correct"] = bool(declared_no_compact)
        out["k_correct"] = None
    else:
        out["abstention_correct"] = None
        out["false_alarm"] = bool(declared_no_compact)
        out["k_correct"] = (k_model is not None and int(k_model) == int(kt)) if not declared_no_compact else False
        d_draw = int(truth.get("d_draw") or 0)
        out["d_draw"] = d_draw
        out["k_consistent"] = (k_model is not None and int(kt) <= int(k_model) <= int(kt) + d_draw) if not declared_no_compact else False
        out["k_true_in_range"] = (bool(k_range[0] <= int(kt) <= k_range[1]) if k_range is not None else None)
    return out


def _dz_scores(dz_mod: list, dz_map: list) -> dict:
    """R^2 over items, relative error and median cosine of model dz against truth mapped into model coordinates (>= 5 items)."""
    if len(dz_mod) < 5:
        return {"note": "too few usable items", "n": len(dz_mod)}
    Dm, Dt = np.stack(dz_mod), np.stack(dz_map)
    sse = float(((Dm - Dt) ** 2).sum())
    sst = float(((Dt - Dt.mean(0)) ** 2).sum())
    cos = [float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))) for a, b in zip(Dm, Dt)
           if np.linalg.norm(a) > 1e-12 and np.linalg.norm(b) > 1e-12]
    return {"n": len(dz_mod), "r2": 1.0 - sse / sst if sst > 0 else float("nan"),
            "relative_error": sse / max(float((Dt ** 2).sum()), 1e-12), "median_cosine": float(np.median(cos)) if cos else float("nan")}


def _acts_at_onset(it: TestItem) -> bool:
    e = it.events[0] if it.events else None
    return e is not None and "t" in e and abs(float(e["t"])) <= 1e-9 + 1e-6 * float(it.dt)


def _truth_map(zt_list: list, z_list: list, tol: float = 1e-8) -> tuple[np.ndarray | None, int, int]:
    """The linear part M of the affine least-squares map z ~ z_true @ M + b over the given pairs, or None when the true states do not
    span their own space (numerical rank of the centred z_true below its dimension: the map, hence every mapped effect, is then not
    identifiable; review H round 3b, NEW-5). Returns (M, rank, dimension)."""
    ZT = np.stack([np.asarray(a, float).reshape(-1) for a in zt_list])
    Z = np.stack([np.asarray(a, float).reshape(-1) for a in z_list])
    d = ZT.shape[1]
    sv = np.linalg.svd(ZT - ZT.mean(0), compute_uv=False)
    rank = int((sv > (sv[0] if sv.size and sv[0] > 0 else 1.0) * tol).sum()) if sv.size else 0
    if rank < d or len(ZT) <= d + 1:
        return None, rank, d
    A1 = np.hstack([ZT, np.ones((len(ZT), 1))])
    return np.linalg.lstsq(A1, Z, rcond=None)[0][:-1], rank, d


def eval_readin_truth(model, sid: str, items: list[TestItem], preds: dict[str, Prediction], samples: list[StateSample],
                      pool=None) -> dict:
    """True read-in accuracy for instantaneous first events acting at the onset (module docstring): the headline compares the rollout
    difference one sample after the onset with `dz_true_next` ("next_sample"); "exact" compares a read-in dz with `dz_true`. The map
    z_true -> model coordinates is fitted on states that SPAN the true state: the held-out samples, every item's onset state (the
    model's own onset encoding z0) and the pool states when given; "unidentifiable" when they do not span it (NEW-5)."""
    F = as_fresh(model)
    # verdict items whose told events are the simulated ones (robustness items with amplitude / timing jitter are excluded)
    use = [it for it in items if it.is_verdict() and it.true_events is None and _acts_at_onset(it)
           and (it.dz_true is not None or it.dz_true_next is not None) and it.item_id in preds and preds[it.item_id].z0 is not None]
    if len(use) < 5:
        return {"note": "too few items", "n": len(use)}
    Z, n_fail = encode_samples(F, sid, samples) if samples else (np.zeros((0, 0)), 0)
    if Z is None:
        return {"note": "failed encodings", "n_failed": n_fail}
    zt_fit = [s.z_true for s in samples]
    z_fit = list(Z)
    for it in items:                                          # onset states of every item with its model encoding and truth
        p = preds.get(it.item_id)
        if it.z_true is not None and p is not None and p.z0 is not None and np.isfinite(np.asarray(p.z0, float)).all():
            zt_fit.append(it.z_true)
            z_fit.append(np.asarray(p.z0, float).reshape(-1))
    if pool is not None and getattr(pool, "states", None):
        extra = [StateSample(sample_id=st.state_id, x_hist=st.x_hist, u_hist=st.u_hist, dt=float(pool.dt), group=st.traj, z_true=st.z_true)
                 for st in pool.states if st.z_true is not None]
        Zp, _ = encode_samples(F, sid, extra) if extra else (None, 0)
        if Zp is not None:
            zt_fit += [s.z_true for s in extra]
            z_fit += list(Zp)
    if len(zt_fit) < 8:
        return {"note": "too few fitting states", "n_states": len(zt_fit)}
    if len({np.asarray(a).size for a in z_fit}) != 1:
        return {"note": "encodings of different sizes"}
    M, rank, dim = _truth_map(zt_fit, z_fit)
    if M is None:
        return {"note": "unidentifiable: the fitting states do not span the true state", "rank": rank, "dim": dim, "n_states": len(zt_fit)}
    nxt_mod, nxt_map, ex_mod, ex_map = [], [], [], []
    for it in use:
        p = preds[it.item_id]
        if it.dz_true_next is not None and p.z_int is not None and p.z_base is not None and len(p.z_int) > 1 and len(p.z_base) > 1:
            d = np.asarray(p.z_int[1] - p.z_base[1], float).reshape(-1)
            if d.shape[0] == M.shape[1] and np.isfinite(d).all():
                nxt_mod.append(d)
                nxt_map.append(np.asarray(it.dz_true_next, float).reshape(-1) @ M)
        if it.dz_true is not None:
            r, err = safe_call(F.read_in, sid, p.z0, dict(it.events[0]))
            if err is None and isinstance(r, dict) and r.get("dz") is not None:
                d = np.asarray(r["dz"], float).reshape(-1)
                if d.shape[0] == M.shape[1] and np.isfinite(d).all():
                    ex_mod.append(d)
                    ex_map.append(np.asarray(it.dz_true, float).reshape(-1) @ M)
    return {"definition": "next_sample", **_dz_scores(nxt_mod, nxt_map), "exact": _dz_scores(ex_mod, ex_map),
            "map": {"n_states": len(zt_fit), "rank": rank, "dim": dim}}
