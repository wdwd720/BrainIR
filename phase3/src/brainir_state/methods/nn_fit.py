"""Fitting, dimension sweep, abstention and sharing for the nn family (closed latent models built from nn_core).

Dimension rule (pre-registered, generic; PROTOCOL.md section 9):
    For k in the ascending candidate list K = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32) (truncated at k_max =
    min(32, max(8, N_obs))), fit a model from scratch (full schedule) and record its validation score e(k) = mean over validation
    units (trajectory, start point; 4 start points per trajectory) of the open-loop readout NMSE over the training horizon (events
    included). With e* = min_k e(k) and the paired per-unit differences d_k = e(k) - e(k*), the tolerance is
    tol = max(0.1 e*, 0.005, SE(d_k)). The selected k is the smallest k with
    e(k) <= e* + tol. The sweep stops early once two consecutive candidates fail to improve the best score by more than tol
    (plateau), or when the fit time budget is used up.
    Reported range: [smallest k with e(k) <= e* + 2 tol, smallest k with e(k) <= e* + tol / 2].

Abstention rule (per system):
    - "no compact state": the plateau is not reached (the best k is the largest candidate tried and it still improved on the
      previous candidate by more than tol), or e(k_sel) > 0.5 * e_floor, where e_floor is the validation score of the input-only
      floor (a readout from the input alone; about 1 for unpredictable readouts), i.e. the latent explains less than half of the
      readout variance left by the input over the horizon;
    - "dimension unresolved [a, b]": the sweep hit the time budget before a plateau.
"""

from __future__ import annotations

import math
import time

import numpy as np
import torch

from . import nn_core as C

K_CANDIDATES = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32)


# ------------------------------------------------------------------------------------------------------------ preparation
def group_trajs(train) -> dict:
    by = {}
    for tr in train:
        by.setdefault(tr.system_id, []).append(tr)
    return by


HISTORY_LAGS = (1, 2, 4, 8, 16)


def resolve_lags(cfg: dict, stride: int, dt: float):
    """History lags of the encoder in internal steps: an explicit tuple, 'none', or 'auto' (decided by history_rule)."""
    lg = cfg.get("lags", "auto")
    if isinstance(lg, (tuple, list)):
        return tuple(int(v) for v in lg)
    if lg in ("none", "auto_none", None):
        return ()
    if lg == "short":
        return (1, 2, 4)
    if lg == "auto":
        return "auto"
    raise ValueError(f"unknown lags {lg!r}")


def history_rule(d: C.SysData, lags: tuple = HISTORY_LAGS, rel: float = 0.1, abs_tol: float = 0.005):
    """Generic rule for the encoder's causal history window, decided BEFORE the dimension sweep from training / validation data:
    ridge-predict the standardised readout at 0 and T/16 internal steps ahead from [x~_j, u~_j] vs [x~_j, x~_{j-l} (l in lags), u~_j]
    (fit on train, scored on val). Use the lags if the history improves the validation NMSE by more than rel x the no-history NMSE
    + abs_tol, i.e. if the readout depends on microstate history that a single sample does not reveal (e.g. downstream neurons that
    integrate their inputs). Returns (lags, scores)."""
    tr = [i for i, s in enumerate(d.split) if s != "val"] or list(range(len(d.X)))
    va = [i for i, s in enumerate(d.split) if s == "val"] or tr
    T = min(len(x) for x in d.X)
    lags = tuple(l for l in lags if l < T // 8)
    if not lags:
        return (), {}
    hs = (0, max(1, T // 16))
    rng = np.random.default_rng(0)

    def mats(ids, use, h):
        dd = C.SysData(sid=d.sid, A=None, X=d.X, U=d.U, Ui=d.Ui, Y=d.Y, EV=d.EV, split=d.split, lags=use)
        F, Y = [], []
        for i in ids:
            n = len(d.X[i])
            js = np.arange(max(lags), n - h, max(1, n // 60))
            F.append(np.hstack([C.feat_rows(dd, i, js).numpy(), d.U[i][js].numpy(), np.ones((len(js), 1))]))
            Y.append(d.Y[i][js + h].numpy())
        return np.concatenate(F).astype(np.float64), np.concatenate(Y).astype(np.float64)

    out = {}
    for use in ((), lags):
        errs = []
        for h in hs:
            Ft, Yt = mats(tr, use, h)
            Fv, Yv = mats(va, use, h)
            if len(Ft) > 20000:
                sel = rng.choice(len(Ft), 20000, replace=False)
                Ft, Yt = Ft[sel], Yt[sel]
            mu, sd = Ft.mean(0), Ft.std(0) + 1e-6
            A = (Ft - mu) / sd
            W = np.linalg.solve(A.T @ A + 1e-2 * len(A) * np.eye(A.shape[1]), A.T @ (Yt - Yt.mean(0)))
            errs.append(float(np.mean((((Fv - mu) / sd) @ W + Yt.mean(0) - Yv) ** 2)))
        out["history" if use else "none"] = float(np.mean(errs))
    use_hist = out["history"] < out["none"] * (1 - rel) - abs_tol
    return (tuple(lags) if use_hist else ()), out


def prepare(train, systems: dict, cfg: dict, log=None) -> dict:
    """Norms, compiled data and effective couplings for every system of the fit."""
    by = group_trajs(train)
    prep = {"norms": {}, "datas": {}, "J": {}, "floor": {}}
    for sid, trs in by.items():
        entry = systems.get(sid, {}) if systems else {}
        observed = entry.get("observed") or list(range(trs[0].x.shape[1]))
        stride = int(cfg.get("stride") or C.choose_stride(trs))
        lags = resolve_lags(cfg, stride, trs[0].dt)
        fit_trs = [t for t in trs if t.split != "val"] or trs
        norm = C.fit_norm(sid, fit_trs, observed, stride, () if lags == "auto" else lags)
        d = C.compile_system(sid, trs, norm)
        if lags == "auto":
            lags, hist_scores = history_rule(d)
            prep.setdefault("history", {})[sid] = hist_scores
            norm.lags, d.lags = tuple(lags), tuple(lags)
        prep["norms"][sid], prep["datas"][sid] = norm, d
        J = None
        if cfg.get("use_J", True):
            gm = C.graph_mask_from_entry(entry, norm)
            J = C.estimate_coupling(_train_only(d), gm)
            prep.setdefault("leak", {})[sid] = C.estimate_coupling.last_leak
        prep["J"][sid] = J
        prep["floor"][sid] = input_floor(d)
        if log:
            log(f"prep {sid}: n_x {norm.n_x} n_y {norm.n_y} stride {stride} lags {lags} trajs {len(trs)} floor {prep['floor'][sid]:.3f}")
    return prep


def _train_only(d: C.SysData) -> C.SysData:
    idx = [i for i, s in enumerate(d.split) if s != "val"] or list(range(len(d.X)))
    return C.SysData(sid=d.sid, A=None, X=[d.X[i] for i in idx], U=[d.U[i] for i in idx], Ui=[d.Ui[i] for i in idx],
                     Y=[d.Y[i] for i in idx], EV=[d.EV[i] for i in idx], split=[d.split[i] for i in idx], lags=d.lags)


def input_floor(d: C.SysData) -> float:
    """Validation NMSE of the best instantaneous ridge map from the input (and its step history) to the readout: the input-only
    floor used by the abstention rule."""
    tr = [i for i, s in enumerate(d.split) if s != "val"] or list(range(len(d.X)))
    va = [i for i, s in enumerate(d.split) if s == "val"] or tr

    def feats(i):
        U = d.Ui[i].numpy().astype(np.float64)
        lagged = [U] + [np.concatenate([np.repeat(U[:1], L, 0), U[:-L]]) for L in (1, 4, 16, 64) if L < len(U)]
        on = np.cumsum(np.abs(U).sum(1) > 1e-6) > 0
        return np.hstack(lagged + [on[:, None].astype(float), np.ones((len(U), 1))])

    Xtr = np.concatenate([feats(i) for i in tr]); Ytr = np.concatenate([d.Y[i].numpy() for i in tr])
    W = np.linalg.solve(Xtr.T @ Xtr + 1e-3 * len(Xtr) * np.eye(Xtr.shape[1]), Xtr.T @ Ytr)
    Xva = np.concatenate([feats(i) for i in va]); Yva = np.concatenate([d.Y[i].numpy() for i in va])
    return float(np.mean((Xva @ W - Yva) ** 2))


# ------------------------------------------------------------------------------------------------------------ building
def build_net(prep: dict, sids: list, k: int, cfg: dict, sharing: str = "independent", frozen_f: dict | None = None) -> C.NNNet:
    heads, fs, f_of, rest, lag_max = {}, {}, {}, {}, {}
    for sid in sids:
        nm = prep["norms"][sid]
        n_feat = nm.n_x * (1 + len(nm.lags))
        heads[sid] = C.Head(n_feat, nm.n_x, nm.n_u, nm.n_y, k, cfg["enc"], cfg["hidden"], prep["J"].get(sid), cfg.get("readout", "mlp"),
                            stochastic=bool(cfg.get("stochastic", False)), gain_mode=cfg.get("gain_mode", "matrix"),
                            gain_init={"cur": cfg.get("g_cur0", 0.0), "so": 0.0, "J": cfg.get("g_J0", 0.0)},
                            silence_obs=bool(cfg.get("silence_obs", False)), private=bool(cfg.get("private_route", False)),
                            leak=float(prep.get("leak", {}).get(sid, 0.0)))
        init = cfg.get("enc_init", "pca")
        if init == "pca":
            d = prep["datas"][sid]
            X = np.concatenate([d.X[i].numpy() for i, s in enumerate(d.split) if s != "val"] or [x.numpy() for x in d.X])
            heads[sid].init_pca(X[:: max(1, len(X) // 20000)].astype(np.float64))
        elif init == "rrr":
            heads[sid].init_matrix(rrr_directions(prep["datas"][sid], k))
        rest[sid] = nm.rest
        lag_max[sid] = max(nm.lags or (0,))
    n_u = {prep["norms"][s].n_u for s in sids}
    if frozen_f is not None:
        fs = {key: f for key, f in frozen_f.items()}
        only = list(fs)[0]
        for sid in sids:
            f_of[sid] = only
        for f in fs.values():
            for p in f.parameters():
                p.requires_grad_(False)
    elif sharing in ("shared", "partial") and len(sids) > 1:
        if len(n_u) != 1:
            raise NotImplementedError("shared dynamics need a common input dimension")
        fs["shared"] = C.Transition(k, n_u.pop(), cfg["f_class"], cfg["hidden"])
        for sid in sids:
            f_of[sid] = "shared"
    else:
        for i, sid in enumerate(sids):
            key = f"f{i}"
            fs[key] = C.Transition(k, prep["norms"][sid].n_u, cfg["f_class"], cfg["hidden"])
            f_of[sid] = key
    return C.NNNet(heads, fs, f_of, rest, lag_max)


def grow_into(old: C.NNNet, new: C.NNNet, k_old: int, k_new: int) -> None:
    """Initialise a k_new-dimensional net from a trained k_old-dimensional one (nested sweep). Every axis whose size is k (+ a fixed
    trailing block, e.g. the input columns of [z, u]) is mapped index-wise; the entries of the new latent dimensions are zero (so the
    new dimensions are constant under f and ignored by the readout / decoder: the grown net predicts exactly like the old one),
    except the encoder rows, which keep their (PCA) initialisation."""
    so, sn = old.state_dict(), new.state_dict()
    out = {}
    for name, tn in sn.items():
        to = so.get(name)
        if to is None:
            continue
        if to.shape == tn.shape:
            out[name] = to.clone()
            continue
        keep_init = ".enc.lin." in name or ".enc.logv." in name
        res = tn.clone() if keep_init else torch.zeros_like(tn)
        idx_o, idx_n, ok = [], [], True
        for a, b in zip(to.shape, tn.shape):
            if a == b:
                idx_o.append(torch.arange(a)); idx_n.append(torch.arange(b))
                continue
            extra = a - k_old
            if extra < 0 or b - k_new != extra:
                ok = False
                break
            idx_o.append(torch.arange(a)); idx_n.append(torch.cat([torch.arange(k_old), torch.arange(k_new, k_new + extra)]).long())
        if not ok:
            continue
        res[torch.meshgrid(*idx_n, indexing="ij")] = to[torch.meshgrid(*idx_o, indexing="ij")]
        out[name] = res
    new.load_state_dict(out, strict=False)


def rrr_directions(d: C.SysData, k: int, n_h: int = 5, lam: float = 1e-2) -> np.ndarray:
    """Predictive encoder initialisation: reduced-rank ridge regression of the future readout (standardised y at n_h horizons from 0 to
    T/4 internal steps) on the current encoder features; the top directions of the fitted values, completed by the top principal
    components of the features' residual (after removing those directions) when k exceeds their rank. Returns W (k, F) with
    unit-variance, uncorrelated projections on the training data."""
    tr = [i for i, s in enumerate(d.split) if s != "val"] or list(range(len(d.X)))
    T = min(len(x) for x in d.X)
    hs = np.unique(np.linspace(0, max(1, T // 4), n_h).astype(int))
    F, Y = [], []
    for i in tr:
        n = len(d.X[i])
        js = np.arange(0, n - hs[-1], max(1, n // 80))
        F.append(C.feat_rows(d, i, js).numpy())
        Y.append(np.hstack([d.Y[i][js + h].numpy() for h in hs]))
    F, Y = np.concatenate(F).astype(np.float64), np.concatenate(Y).astype(np.float64)
    mu = F.mean(0)
    Fc, Yc = F - mu, Y - Y.mean(0)
    B = np.linalg.solve(Fc.T @ Fc + lam * len(Fc) * np.eye(Fc.shape[1]) * (Fc.var(0).mean() + 1e-12), Fc.T @ Yc)
    _, sv, Vt = np.linalg.svd(Fc @ B, full_matrices=False)
    r = int(min(k, (sv > 1e-6 * max(sv[0], 1e-12)).sum()))
    dirs = [B @ Vt[:r].T] if r else []                       # (F, r)
    if r < k:
        P = np.hstack(dirs) if dirs else np.zeros((Fc.shape[1], 0))
        R = Fc - (Fc @ P) @ np.linalg.pinv(P) if P.shape[1] else Fc
        _, _, Vr = np.linalg.svd(R[:: max(1, len(R) // 20000)], full_matrices=False)
        dirs.append(Vr[: k - r].T)
    D = np.hstack(dirs)[:, :k]                                # (F, k)
    Z = Fc @ D                                                # whiten the projections on the training data
    C_ = np.cov(Z.T) + 1e-9 * np.eye(k) if k > 1 else np.atleast_2d(Z.var() + 1e-9)
    w, V = np.linalg.eigh(np.atleast_2d(C_))
    Wh = V @ np.diag(1.0 / np.sqrt(np.maximum(w, 1e-12))) @ V.T
    W = (D @ Wh).T                                            # (k, F)
    return W, mu


def fit_k(prep: dict, sids: list, k: int, cfg: dict, seed: int, sharing: str = "independent", deadline: float | None = None,
          frozen_f: dict | None = None, log=None, init_from: tuple | None = None, train_seed: int | None = None):
    """Fit one k. init_from = (net, k_old): warm start from a trained model with k_old <= k (k_old = k: continued training),
    validated before training. train_seed: seed of the training batches (paired comparisons use the same one)."""
    torch.manual_seed(int(seed) * 1000 + int(k))
    net = build_net(prep, sids, k, cfg, sharing, frozen_f)
    if init_from is not None:
        grow_into(init_from[0], net, init_from[1], k)
        cfg = dict(cfg, eval_initial=True, no_curriculum=True, lr=cfg["lr"] * 0.5,
                   grow_from=init_from[1] if init_from[1] < k else None)
    datas = {s: prep["datas"][s] for s in sids}
    res = C.train_net(net, datas, cfg, seed=int(train_seed) if train_seed is not None else int(seed) * 1000 + int(k), deadline=deadline,
                      log=log)
    per = {}
    for s in sids:
        inf = res["info"][s]
        per[s] = C.val_score(net, s, datas[s], inf["H"], cfg["val_starts"], inf["lag_max"], inf["va"])
    return net, res, per


# ------------------------------------------------------------------------------------------------------------ dimension rule
def tolerance(curve: dict, k_best: int) -> dict:
    """Per-candidate tolerance of the plateau rule (see the module docstring)."""
    e_best = float(np.mean(curve[k_best]))
    out = {}
    for k, v in curve.items():
        a, b = np.asarray(v), np.asarray(curve[k_best])
        n = min(len(a), len(b))
        se = float(np.std(a[:n] - b[:n], ddof=1) / math.sqrt(n)) if n > 1 else 0.0
        out[k] = max(0.1 * e_best, 0.005, se)
    return out


def select_k(curve: dict) -> dict:
    """curve: {k: per-trajectory validation scores}. Returns k, range and the tolerance used."""
    ks = sorted(curve)
    means = {k: float(np.mean(curve[k])) for k in ks}
    k_best = min(ks, key=lambda k: means[k])
    tol = tolerance(curve, k_best)
    e_best = means[k_best]
    k_sel = next(k for k in ks if means[k] <= e_best + tol[k])
    lo = next(k for k in ks if means[k] <= e_best + 2 * tol[k])
    hi = next(k for k in ks if means[k] <= e_best + 0.5 * tol[k])
    return {"k": k_sel, "k_best": k_best, "range": [int(lo), int(max(hi, k_sel))], "means": means, "tol": tol[k_sel], "e_best": e_best}


def plateau_reached(curve: dict) -> bool:
    """True once the two largest candidates tried both fail to improve the best score of the smaller candidates by more than tol."""
    ks = sorted(curve)
    if len(ks) < 3:
        return False
    means = {k: float(np.mean(curve[k])) for k in ks}
    prev_best = min(means[k] for k in ks[:-2])
    k_best = min(ks, key=lambda k: means[k])
    tol = tolerance(curve, k_best)
    return all(means[k] > prev_best - tol[k] for k in ks[-2:])


def sweep(prep: dict, sids: list, cfg: dict, seed: int, sharing: str = "independent", t_budget: float = 1000.0,
          k_max: int | None = None, frozen_f: dict | None = None, log=None):
    """Ascending k-sweep with the plateau stop. Returns (selection, {k: (net, per-system scores)}, curve, status)."""
    t0 = time.time()
    n_min = min(prep["norms"][s].n_x for s in sids)
    k_max = k_max or int(min(32, max(8, n_min)))
    cands = [k for k in K_CANDIDATES if k <= k_max]
    fits, curve, status, per_fit = {}, {}, "plateau", None
    for k in cands:
        el = time.time() - t0
        remaining = t_budget - el
        if curve and per_fit is not None and remaining < 1.3 * per_fit:
            # out of time: "unresolved" only if the error was still falling at the last candidate tried
            ks = sorted(curve)
            status = "time"
            if len(ks) >= 2:
                m = {kk: float(np.mean(curve[kk])) for kk in ks}
                k_b = min(ks, key=lambda kk: m[kk])
                if m[ks[-1]] >= min(m[kk] for kk in ks[:-1]) - tolerance(curve, k_b)[ks[-1]]:
                    status = "time_flat"
            break
        tk = time.time()
        prev = max(fits) if (fits and cfg.get("nested", False)) else None
        net, res, per = fit_k(prep, sids, k, dict(cfg, iters=cfg.get("sweep_iters", cfg["iters"])), seed, sharing,
                              deadline=time.time() + max(30.0, remaining - 5.0), frozen_f=frozen_f, log=None,
                              init_from=(fits[prev][0], prev) if prev is not None else None)
        per_fit = max(per_fit or 0.0, time.time() - tk)
        sc = np.mean([per[s] for s in sids], axis=0) if len({len(per[s]) for s in sids}) == 1 else np.concatenate([per[s] for s in sids])
        curve[k] = sc
        fits[k] = (net, per)
        if log:
            log(f"k={k}: val {float(np.mean(sc)):.4f} ({time.time() - tk:.0f}s)")
        if plateau_reached(curve):
            status = "plateau"
            break
    else:
        status = "plateau" if plateau_reached(curve) or len(curve) >= len(cands) and _flat_end(curve) else "no_plateau"
    sel = select_k(curve)
    return sel, fits, curve, status


def refine(net: C.NNNet, prep: dict, sids: list, cfg: dict, seed: int, deadline: float | None = None, log=None) -> dict:
    """Continue training a sweep model (new optimiser schedule at a lower rate); keeps the starting weights if they validate better."""
    datas = {s: prep["datas"][s] for s in sids}
    c = dict(cfg, iters=cfg.get("refine_iters", 150), lr=cfg["lr"] * 0.5, eval_initial=True)
    C.train_net(net, datas, c, seed=int(seed) * 1000 + 777, deadline=deadline, log=log)
    per = {}
    for s in sids:
        T = min(len(x) for x in datas[s].X)
        lag_max = net.lag_max.get(s, 0)
        H = int(max(4, min(cfg["max_horizon"], round(cfg["horizon_frac"] * T), T - lag_max - 3)))
        va = [i for i, sp in enumerate(datas[s].split) if sp == "val"] or [0]
        per[s] = C.val_score(net, s, datas[s], H, cfg["val_starts"], lag_max, va)
    return per


def _flat_end(curve: dict) -> bool:
    ks = sorted(curve)
    if len(ks) < 2:
        return True
    means = {k: float(np.mean(curve[k])) for k in ks}
    k_best = min(ks, key=lambda k: means[k])
    tol = tolerance(curve, k_best)
    return means[ks[-2]] - means[ks[-1]] <= tol[ks[-1]]


def abstention(sel: dict, status: str, floor: float, n_obs: int) -> dict:
    no_compact = False
    reasons = []
    if status == "no_plateau":
        no_compact = True
        reasons.append("validation error still falling at the largest candidate k (no plateau)")
    if sel["means"][sel["k"]] > 0.5 * floor:
        no_compact = True
        reasons.append(f"latent explains too little beyond the input (val {sel['means'][sel['k']]:.3f} vs input floor {floor:.3f})")
    unresolved = [int(sel["range"][0]), None] if status == "time" else None
    return {"no_compact_state": bool(no_compact), "dimension_unresolved": unresolved, "causal_equivalence_failed": False,
            "reason": "; ".join(reasons) if reasons else ("time budget reached before a plateau" if status == "time" else
                                                          "time budget reached; last candidate did not improve" if status == "time_flat" else "")}


def _score(per: dict, sids: list) -> np.ndarray:
    return np.mean([per[s] for s in sids], axis=0) if len({len(per[s]) for s in sids}) == 1 else np.concatenate([per[s] for s in sids])


def sweep_paired(prep: dict, sids: list, cfg: dict, seed: int, sharing: str = "independent", t_budget: float = 1000.0,
                 k_max: int | None = None, log=None):
    """Nested dimension sweep with an equal-compute paired control (the dimension rule of nn_closed).

    Start: a full fit at the smallest candidate. For each next candidate k' (ascending K), from the current model (dimension k) train
    A = the model grown to k' and B = the same k-model, for the same number of iterations with the same batches. The gain
    d = e_B - e_A (per validation trajectory) measures what the extra dimensions add beyond the extra training. k' is accepted
    (A becomes the current model) if mean(d) > tol = max(0.05 mean(e_B), 0.002, SE(d)); otherwise B becomes the current model. The
    sweep stops after two consecutive rejections (plateau), at k_max (no plateau if the last step was accepted) or at the time
    budget. Range: [largest k accepted with d > 2 tol (else the first candidate), smallest rejected k' with d > tol / 2 (else k)]."""
    t0 = time.time()
    n_min = min(prep["norms"][s].n_x for s in sids)
    k_max = k_max or int(min(32, max(8, n_min)))
    cands = [k for k in K_CANDIDATES if k <= k_max]
    k = cands[0]
    net, _, per = fit_k(prep, sids, k, cfg, seed, sharing, deadline=t0 + t_budget)
    e = _score(per, sids)
    steps, fails, status, t_step = [], 0, "plateau", None
    lo, hi_weak = k, None
    if log:
        log(f"k={k}: val {float(np.mean(e)):.4f} ({time.time() - t0:.0f}s)")
    c_step = dict(cfg, iters=cfg.get("sweep_iters", cfg["iters"]))
    for k2 in cands[1:]:
        remaining = t_budget - (time.time() - t0)
        if t_step is not None and remaining < 1.2 * t_step + 60:
            status = "time"
            break
        ts = time.time()
        tseed = int(seed) * 1000 + 500 + k2
        dl = time.time() + max(30.0, (remaining - 10.0) / 2)
        netA, _, perA = fit_k(prep, sids, k2, c_step, seed, sharing, deadline=dl, init_from=(net, k), train_seed=tseed)
        dl = time.time() + max(30.0, (remaining - 10.0) / 2)
        netB, _, perB = fit_k(prep, sids, k, c_step, seed, sharing, deadline=dl, init_from=(net, k), train_seed=tseed)
        eA, eB = _score(perA, sids), _score(perB, sids)
        n = min(len(eA), len(eB))
        dd = eB[:n] - eA[:n]
        se = float(np.std(dd, ddof=1) / np.sqrt(n)) if n > 1 else 0.0
        tol = max(0.05 * float(np.mean(eB)), 0.002, se)
        gain = float(np.mean(dd))
        acc = gain > tol
        steps.append({"k_from": int(k), "k_to": int(k2), "val_grown": float(np.mean(eA)), "val_control": float(np.mean(eB)),
                      "gain": gain, "tol": tol, "accepted": bool(acc)})
        t_step = time.time() - ts
        if log:
            log(f"k {k}->{k2}: grown {np.mean(eA):.4f} control {np.mean(eB):.4f} gain {gain:.4f} tol {tol:.4f} "
                f"{'ACCEPT' if acc else 'reject'} ({t_step:.0f}s)")
        if acc:
            if gain > 2 * tol:
                lo = k2
            net, k, per, e, fails = netA, k2, perA, eA, 0
        else:
            if gain > 0.5 * tol and hi_weak is None:
                hi_weak = k2
            net, per, e, fails = netB, perB, eB, fails + 1
            if fails >= 2:
                status = "plateau"
                break
    else:
        status = "no_plateau" if fails == 0 and len(cands) > 1 else "plateau"
    sel = {"k": int(k), "range": [int(min(lo, k)), int(hi_weak if hi_weak is not None else k)], "means": {int(k): float(np.mean(e))},
           "tol": steps[-1]["tol"] if steps else 0.0, "steps": steps}
    return sel, net, per, status
