"""Synthetic ground-truth metrics (benchmarks/causal_state_v1/PROTOCOL.md section 5.16). SYNTHETIC SYSTEMS ONLY.

Truth comes from the synthetic generator's adapter (`brainir_causal.synthadapter`: `system.truth()`, `true_state(micro)`,
`obs_shortcut_state(micro)`, `true_latent_effect(micro, event)`). The dataset builder attaches it to the evaluation inputs
(`StateSample.z_true / z_obs`, `TestItem.z_true / z_obs / dz_true`); `attach_truth` does that from the full microstates in
`meta["micro"]` when the builder did not. The model never sees any of it.

- LATENT RECOVERY: min(R^2 of z_true from z, R^2 of z from z_true), cross-fitted by source trajectory (2 folds x 5 repeats) with the
  linear + random-feature ridge regressor (PROTOCOL 5.3 capacity rule); R^2 = 1 - SSE / SST over standardised target coordinates.
  A z that misses content fails the first direction, a z that carries extra content (e.g. nuisance) fails the second.
- z_obs CAPTURE (trap types): the EXPOSED causal variable = the part of z_true not predictable from z_obs (cross-fitted residual);
  reported as the R^2 of the exposed variable from z (a model that learned only the observational shortcut scores about 0).
- DIMENSION: k = k_true; k_true within the reported range; correct "no compact causal state" on non-compressible types (truth
  k == "none"), or a false alarm elsewhere.
- TRUE READ-IN ACCURACY: for items whose first event is instantaneous and carries `dz_true`, the model's read-in dz (read_in(z0,
  event)["dz"]; if the model returns no dz, its rollout difference one sample after the onset) against dz_true mapped into model
  coordinates by the affine map z ~ z_true fitted on the state samples; R^2 over items and the median cosine similarity.
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
    true_state(state), obs_shortcut_state(state), true_latent_effect(state, event)."""
    for it in items or []:
        micro = it.meta.get("state", it.meta.get("micro"))
        if micro is None:
            continue
        if it.z_true is None:
            it.z_true = np.asarray(system.true_state(micro), float)
        if it.z_obs is None:
            zo = system.obs_shortcut_state(micro)
            it.z_obs = None if zo is None else np.asarray(zo, float)
        if it.dz_true is None and it.events and "t" in it.events[0]:
            it.dz_true = np.asarray(system.true_latent_effect(micro, it.events[0]), float)


def _crossfit_r2(X: np.ndarray, Y: np.ndarray, groups: np.ndarray, seed: int, repeats: int = REPEATS) -> float:
    """Cross-fitted R^2 of Y from X (linear + random features, ridge penalty by an inner split by group)."""
    X = np.asarray(X, float)
    Y = np.asarray(Y, float)
    Y = Y[:, None] if Y.ndim == 1 else Y
    if len(X) < 8 or len(np.unique(groups)) < 4:
        return float("nan")
    Ys = standardise(Y)
    live = Y.std(0) > 1e-12
    if not live.any():
        return float("nan")
    Ys = Ys[:, live]
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
    res = {"n": len(samples), "r2_true_from_z": r_true_from_z, "r2_z_from_true": r_z_from_true,
           "recovery": float(np.nanmin([r_true_from_z, r_z_from_true])) if np.isfinite([r_true_from_z, r_z_from_true]).any()
           else float("nan")}
    if all(s.z_obs is not None for s in samples):
        ZO = np.stack([np.asarray(s.z_obs, float).reshape(-1) for s in samples])
        exposed = _crossfit_residual(ZO, ZT, g, seed + 2)
        res["exposed_variance_share"] = float(exposed.var(0).sum() / max(ZT.var(0).sum(), 1e-12))
        res["zobs_capture_r2_exposed_from_z"] = _crossfit_r2(Z, exposed, g, seed + 3)
        res["r2_zobs_from_z"] = _crossfit_r2(Z, ZO, g, seed + 4)
    return res


def eval_dimension_truth(k_model: int | None, k_range: tuple[int, int] | None, truth: dict, declared_no_compact: bool) -> dict:
    """k = k_true, k_true within the range, and the correctness of a declared "no compact causal state"."""
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
        out["k_true_in_range"] = (bool(k_range[0] <= int(kt) <= k_range[1]) if k_range is not None else None)
    return out


def eval_readin_truth(model, sid: str, items: list[TestItem], preds: dict[str, Prediction], samples: list[StateSample]) -> dict:
    """True read-in accuracy for instantaneous first events with dz_true (see the module docstring)."""
    F = as_fresh(model)
    use = [it for it in items if it.dz_true is not None and it.events and "t" in it.events[0] and it.item_id in preds
           and preds[it.item_id].z0 is not None]
    if len(use) < 5 or len(samples) < 8:
        return {"note": "too few items or samples", "n": len(use)}
    Z, _ = encode_samples(F, sid, samples)
    if Z is None:
        return {"note": "failed encodings"}
    ZT = np.stack([np.asarray(s.z_true, float).reshape(-1) for s in samples])
    A1 = np.hstack([ZT, np.ones((len(ZT), 1))])
    M = np.linalg.lstsq(A1, Z, rcond=None)[0][:-1]          # (k_true, k_model): z ~ z_true @ M + b
    dz_map, dz_mod, src = [], [], {"read_in": 0, "rollout": 0}
    for it in use:
        p = preds[it.item_id]
        ev = dict(it.events[0])
        r, err = safe_call(F.read_in, sid, p.z0, ev)
        dz = None
        if err is None and isinstance(r, dict) and r.get("dz") is not None:
            dz = np.asarray(r["dz"], float).reshape(-1)
            src["read_in"] += 1
        elif p.z_int is not None and p.z_base is not None and len(p.z_int) > 1 and len(p.z_base) > 1:
            dz = np.asarray(p.z_int[1] - p.z_base[1], float).reshape(-1)
            src["rollout"] += 1
        if dz is None or dz.shape[0] != M.shape[1] or not np.isfinite(dz).all():
            continue
        dz_mod.append(dz)
        dz_map.append(np.asarray(it.dz_true, float).reshape(-1) @ M)
    if len(dz_mod) < 5:
        return {"note": "too few usable read-ins", "n": len(dz_mod), "source": src}
    Dm, Dt = np.stack(dz_mod), np.stack(dz_map)
    sse = float(((Dm - Dt) ** 2).sum())
    sst = float(((Dt - Dt.mean(0)) ** 2).sum())
    cos = [float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))) for a, b in zip(Dm, Dt)
           if np.linalg.norm(a) > 1e-12 and np.linalg.norm(b) > 1e-12]
    return {"n": len(dz_mod), "r2": 1.0 - sse / sst if sst > 0 else float("nan"),
            "relative_error": sse / max(float((Dt ** 2).sum()), 1e-12), "median_cosine": float(np.median(cos)) if cos else float("nan"),
            "source": src}
