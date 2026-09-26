"""Fitting helpers of the linear family: latent series, least-squares dynamics, stabilisation, prediction-error (multi-step)
refinement with an optional nonlinear closure, decoders, readouts, event operators, windowed validation scores and the
cross-validated dimension rule. Used by every lin_ method (see lin_core for the model)."""

from __future__ import annotations

import numpy as np

from .lin_core import LinStateModel, PTraj, SysPrep, fit_readout, readout_features, ridge_solve


# ================================================================================================================ latent series
def latent_series(enc: dict, tr: PTraj) -> np.ndarray:
    """Latent z_t for every sample of a prepared trajectory (causal encoder with lags; early samples pad with the first one)."""
    T = len(tr.xs)
    rec = enc.get("_rec")
    if rec is not None and T > 1:
        # recursive filter form (identical to the FIR up to its truncation): z_t = F z_{t-1} + Kx x_t + Ku u_{t-1} + b1
        D = tr.xs.astype(np.float64) @ rec["Kx"].T + rec["b1"]
        D[1:] += tr.us[:-1].astype(np.float64) @ rec["Ku"].T
        Z = np.empty((T, len(enc["b"])))
        L0 = min(T - 1, max(enc["lags"]))
        # start from the FIR value at the first sample (history padded with the first sample)
        z = np.tile(enc["b"], 1).astype(np.float64)
        for li, L in enumerate(enc["lags"]):
            z = z + enc["Hx"][li] @ tr.xs[0].astype(np.float64)
            if enc.get("Hu") is not None:
                z = z + enc["Hu"][li] @ tr.us[0].astype(np.float64)
        Z[0] = z
        F = rec["F"]
        for t in range(1, T):
            z = F @ z + D[t]
            Z[t] = z
        return Z
    Z = np.tile(enc["b"], (T, 1))
    idx = np.arange(T)
    for li, L in enumerate(enc["lags"]):
        ii = np.maximum(0, idx - L)
        Z += tr.xs[ii].astype(np.float64) @ enc["Hx"][li].T
        if enc.get("Hu") is not None:
            Z += tr.us[ii].astype(np.float64) @ enc["Hu"][li].T
    return Z


def static_encoder(W: np.ndarray, b: np.ndarray | None = None) -> dict:
    return {"lags": [0], "Hx": [np.asarray(W, np.float64)], "Hu": None, "b": np.zeros(W.shape[0]) if b is None else np.asarray(b, float)}


def burn_in(enc: dict) -> int:
    return int(max(enc["lags"])) if enc["lags"] else 0


# ================================================================================================================ dynamics
def transition_pairs(enc: dict, trajs: list[PTraj], stride: int = 1, max_pairs: int = 400000):
    """(Z_t, U_t, Z_{t+1}) over free transitions (after the encoder's burn-in)."""
    Zt, Ut, Zn = [], [], []
    b = burn_in(enc)
    tot = sum(int(t.keep[b:].sum()) for t in trajs)
    stride = max(stride, int(np.ceil(tot / max_pairs)))
    for t in trajs:
        Z = latent_series(enc, t)
        ii = np.flatnonzero(t.keep)
        ii = ii[ii >= b][::stride]
        Zt.append(Z[ii]); Ut.append(t.us[ii].astype(np.float64)); Zn.append(Z[ii + 1])
    return np.concatenate(Zt), np.concatenate(Ut), np.concatenate(Zn)


def fit_dynamics_ls(Zt, Ut, Zn, lam: float = 1e-6):
    """Least-squares z_{t+1} = A z_t + B u_t + c (ridge-regularised, intercept free)."""
    F = np.hstack([Zt, Ut, np.ones((len(Zt), 1))])
    W = ridge_solve(F, Zn, lam)
    k, nu = Zt.shape[1], Ut.shape[1]
    return W[:k].T.copy(), W[k:k + nu].T.copy(), W[-1].copy()


def stabilise(A: np.ndarray, rho_max: float = 1.0) -> np.ndarray:
    """Scale eigenvalues with |lambda| > rho_max back onto the circle of radius rho_max (real matrix preserved)."""
    w, V = np.linalg.eig(A)
    if np.all(np.abs(w) <= rho_max):
        return A
    w2 = np.where(np.abs(w) > rho_max, w / np.abs(w) * rho_max, w)
    try:
        A2 = (V @ np.diag(w2) @ np.linalg.inv(V)).real
        return A2 if np.isfinite(A2).all() else A
    except np.linalg.LinAlgError:
        return A


# ================================================================================================================ windows
def free_windows(tr: PTraj, H: int, starts: np.ndarray, b: int = 0) -> list[int]:
    """Start indices i0 (in `starts`) whose rollout window [i0, i0 + H] has only free transitions and no structural event
    (silence / edge removal) active before i0."""
    out = []
    n = len(tr.xs)
    blocked_from = n
    for e in tr.events:
        if e["kind"] in ("silence", "edge_remove") and e.get("t1") is None:
            blocked_from = min(blocked_from, int(round(e["t0"] / tr.dt)))
    for i0 in starts:
        i0 = int(i0)
        if i0 < b or i0 + H >= n or i0 + H > blocked_from:
            continue
        if tr.keep[i0: i0 + H].all():
            out.append(i0)
    return out


def score_windows(model: LinStateModel, sid: str, P: SysPrep, trajs: list[PTraj], horizons: list[int], starts: np.ndarray,
                  scale: np.ndarray) -> dict[str, float]:
    """Per-trajectory mean over windows and horizons of the readout NMSE of event-free rollouts (the evaluator's A metric, on
    training-side data). Returns {traj key: score}."""
    H = max(horizons)
    enc = model.sys[sid]["enc"]
    b = burn_in(enc)
    out = {}
    for tr in trajs:
        ws = free_windows(tr, H, starts, b)
        if not ws:
            continue
        idx = np.array(ws)
        Z0 = model.encode_batch(sid, tr.xs.astype(np.float64), tr.us.astype(np.float64), idx)
        Us = np.stack([tr.us[i: i + H + 1] for i in ws]).astype(np.float64)
        Z = model.rollout_batch(sid, Z0, Us)
        Yp = model.readout_s(sid, Z, Us)
        Yt = np.stack([tr.y[i: i + H + 1] for i in ws])
        err = (Yp - Yt) ** 2 / scale
        err = np.where(np.isfinite(err), err, 1e6)
        vals = [float(err[:, 1: h + 1].mean()) for h in horizons]
        out[tr.key] = float(np.mean(np.minimum(vals, 1e6)))
    return out


def eval_grid(P: SysPrep):
    """Validation horizons and start times from the trajectory length: horizons T/16, T/8, T/4; starts every T/16 from T/8."""
    T = P.T_len
    horizons = sorted({max(1, T // 16), max(1, T // 8), max(1, T // 4)})
    starts = np.arange(T // 8, T - max(horizons), max(1, T // 16))
    return horizons, starts


def y_scale(P: SysPrep, trajs: list[PTraj]) -> np.ndarray:
    Y = np.concatenate([t.y for t in trajs])
    v = Y.var(0)
    return np.maximum(v, max(1e-6, 1e-3 * float(v.max()) if v.size else 1e-6))


# ================================================================================================================ selection rules
def one_se_rule(scores: dict[int, dict[str, float]], rel_tol: float = 0.05, equiv_tol: float = 0.01) -> tuple[int, int, dict]:
    """Smallest k whose paired excess over the best k (per-trajectory units) is within max(one standard error, equiv_tol x best)
    AND within rel_tol x best (practical-equivalence form of the one-standard-error rule). Returns (k_selected, k_best, curve)."""
    ks = sorted(scores)
    keys = sorted(set.intersection(*[set(scores[k]) for k in ks])) if ks else []
    if not keys:
        k0 = ks[0] if ks else 1
        return k0, k0, {}
    M = np.array([[scores[k][u] for u in keys] for k in ks])
    means = M.mean(1)
    kb = int(np.argmin(means))
    curve = {}
    sel = ks[kb]
    for i, k in enumerate(ks):
        d = M[i] - M[kb]
        se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
        curve[k] = {"score": float(means[i]), "excess": float(d.mean()), "se": se}
    for i, k in enumerate(ks):
        c = curve[k]
        if c["excess"] <= max(c["se"], equiv_tol * means[kb]) and c["excess"] <= rel_tol * means[kb] + 1e-12:
            sel = k
            break
    return sel, ks[kb], curve


def k_range_from_curve(curve: dict, k_sel: int, k_best: int, rel_tol: float = 0.05) -> tuple[int, int]:
    """Plausible range: every k whose paired excess over the best is within 2 SE and within 2 x rel_tol (contiguous around k_sel)."""
    ks = sorted(curve)
    ok = [k for k in ks if curve[k]["excess"] <= 2 * curve[k]["se"] + 1e-12 and curve[k]["excess"] <= 2 * rel_tol * curve[k_best]["score"] + 1e-12]
    lo = min([k_sel] + [k for k in ok if k <= k_sel])
    hi = k_sel
    for k in ks:
        if k > k_sel and k in ok:
            hi = k
        elif k > k_sel:
            break
    lo_c = k_sel
    for k in sorted([k for k in ks if k < k_sel], reverse=True):
        if k in ok:
            lo_c = k
        else:
            break
    return int(min(lo, lo_c)), int(max(hi, k_best if k_best <= hi else hi))


# ================================================================================================================ decoder / readout
def fit_decoder(enc: dict, trajs: list[PTraj], lam: float = 1e-6, max_rows: int = 200000):
    """xs ~ C z + d by least squares; returns C (N, k), d (N,), residual variance per neuron (N,)."""
    Zs, Xs = [], []
    tot = sum(len(t.xs) for t in trajs)
    stride = max(1, tot // max_rows)
    b = burn_in(enc)
    for t in trajs:
        Z = latent_series(enc, t)
        Zs.append(Z[b::stride]); Xs.append(t.xs[b::stride].astype(np.float64))
    Z, X = np.concatenate(Zs), np.concatenate(Xs)
    W = ridge_solve(np.hstack([Z, np.ones((len(Z), 1))]), X, lam)
    C, d = W[:-1].T.copy(), W[-1].copy()
    res = X - Z @ C.T - d
    return C, d, np.maximum(res.var(0), 1e-6)


def readout_data(enc: dict, trajs: list[PTraj], max_rows: int = 200000):
    Zs, Us, Ys = [], [], []
    tot = sum(len(t.xs) for t in trajs)
    stride = max(1, tot // max_rows)
    b = burn_in(enc)
    for t in trajs:
        Z = latent_series(enc, t)
        Zs.append(Z[b::stride]); Us.append(t.us[b::stride].astype(np.float64)); Ys.append(t.y[b::stride])
    return np.concatenate(Zs), np.concatenate(Us), np.concatenate(Ys)


# ================================================================================================================ PEM refinement
def pem_refine(model: LinStateModel, sids: list[str], preps: dict[str, SysPrep], trajs_by: dict[str, list[PTraj]], H: int,
               steps: int = 300, lr: float = 3e-3, batch: int = 256, seed: int = 0, w_lat: float = 1.0, w_y: float = 1.0,
               train_nl: bool = False, train_readout: bool = True, time_budget_s: float = 600.0, rho_max: float = 1.0,
               freeze_dyn: bool = False) -> dict:
    """Prediction-error refinement of the transition (and readout) by minimising multi-step errors over horizons 1..H of
    (i) the latent (against the encoder applied to the true future microstate, normalised by the latent variance) and
    (ii) the readout (normalised by the readout variance). Encoders stay fixed. Systems in `sids` that point to the same
    dynamics dict share its parameters (shared-f fits). freeze_dyn: only readouts are trained (adaptation)."""
    import time as _time

    import torch
    t_start = _time.time()
    n_threads = torch.get_num_threads()
    torch.set_num_threads(1)                      # tiny matrices: threading only adds overhead
    try:
        return _pem_refine(model, sids, preps, trajs_by, H, steps, lr, batch, seed, w_lat, w_y, train_nl, train_readout,
                           time_budget_s, rho_max, freeze_dyn, t_start)
    finally:
        torch.set_num_threads(n_threads)


def _pem_refine(model, sids, preps, trajs_by, H, steps, lr, batch, seed, w_lat, w_y, train_nl, train_readout, time_budget_s,
                rho_max, freeze_dyn, t_start):
    import time as _time

    import torch
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    # windows per system
    data = {}
    hold = {}
    for sid in sids:
        enc = model.sys[sid]["enc"]
        b = burn_in(enc)
        Z0, U, Zf, Yf, HO = [], [], [], [], []
        tl = trajs_by[sid]
        ho_set = set(rng.permutation(len(tl))[: max(1, len(tl) // 5)].tolist()) if len(tl) >= 5 else set()
        for ti, t in enumerate(tl):
            n = len(t.xs)
            if n <= H + b + 1:
                continue
            Z = latent_series(enc, t)
            # candidate starts: free windows only
            ok = np.convolve(t.keep.astype(float), np.ones(H), "valid") >= H - 0.5      # keep[i: i+H] all true
            cand = np.flatnonzero(ok)
            cand = cand[cand >= b]
            if len(cand) == 0:
                continue
            m = min(len(cand), max(4, int(np.ceil(4000 / max(1, len(trajs_by[sid]))))))
            sel = np.sort(rng.choice(cand, size=m, replace=False))
            for i in sel:
                Z0.append(Z[i]); U.append(t.us[i: i + H]); Zf.append(Z[i + 1: i + H + 1]); Yf.append(t.y[i + 1: i + H + 1])
                HO.append(ti in ho_set)
        if not Z0:
            continue
        s = model.sys[sid]
        Z0 = np.stack(Z0); U = np.stack(U).astype(np.float64); Zf = np.stack(Zf); Yf = np.stack(Yf)
        HO = np.array(HO, bool)
        if HO.all() or not HO.any():
            HO = np.zeros(len(Z0), bool)
        hold[sid] = torch.as_tensor(np.flatnonzero(HO))
        trn_idx = np.flatnonzero(~HO)
        zvar = Zf.reshape(-1, Zf.shape[-1]).var(0).sum() + 1e-9
        yv = Yf.reshape(-1, Yf.shape[-1]).var(0)
        yv = np.maximum(yv, max(1e-6, 1e-3 * yv.max()))
        data[sid] = {k_: torch.tensor(v, dtype=torch.float64) for k_, v in (("Z0", Z0), ("U", U), ("Zf", Zf), ("Yf", Yf))}
        data[sid]["zvar"] = float(zvar)
        data[sid]["yv"] = torch.tensor(yv, dtype=torch.float64)
        data[sid]["trn"] = trn_idx
    if not data:
        return {"steps": 0}
    # parameters: dynamics dicts (dedup by identity), per-system B and readout
    dyn_ids = {}
    params = []
    P_dyn = {}
    for sid in data:
        d = model.dyn[sid]
        if id(d) not in dyn_ids:
            dyn_ids[id(d)] = d
            pd = {"A": torch.tensor(d["A"], requires_grad=not freeze_dyn), "c": torch.tensor(d["c"], requires_grad=not freeze_dyn)}
            if train_nl and d.get("nl") is not None:
                for kk in ("W1", "b1", "W2", "b2"):
                    pd[kk] = torch.tensor(d["nl"][kk], requires_grad=not freeze_dyn)
            P_dyn[id(d)] = pd
            if not freeze_dyn:
                params += [v for v in pd.values()]
    P_sys = {}
    shared_B = {}
    for sid in data:
        s = model.sys[sid]
        key = id(model.dyn[sid])
        if s.get("B_shared") and key in shared_B:
            ps = {"B": shared_B[key]}              # one input map for all systems of a shared transition
        else:
            ps = {"B": torch.tensor(s["Bs"], requires_grad=not freeze_dyn or s.get("B_free", False))}
            if not freeze_dyn or s.get("B_free", False):
                params.append(ps["B"])
            if s.get("B_shared"):
                shared_B[key] = ps["B"]
        ro = s["ro"]
        ps["G"] = torch.tensor(ro["G"], requires_grad=train_readout)
        ps["h"] = torch.tensor(ro["h"], requires_grad=train_readout)
        if train_readout:
            params += [ps["G"], ps["h"]]
        P_sys[sid] = ps
    if not params:
        return {"steps": 0}
    opt = torch.optim.Adam(params, lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)

    def features(ro, Z, Us):
        parts = [Z, Us]
        if ro.get("kind") == "quad":
            zm = torch.tensor(ro["zm"]); zs = torch.tensor(ro["zs"])
            Zn = (Z - zm) / zs
            iu = np.triu_indices(Z.shape[-1])
            parts.append((Zn[..., :, None] * Zn[..., None, :])[..., iu[0], iu[1]])
        elif ro.get("kind") == "rff":
            zm = torch.tensor(ro["zm"]); zs = torch.tensor(ro["zs"])
            parts.append(torch.cos(((Z - zm) / zs) @ torch.tensor(ro["Wf"]) + torch.tensor(ro["bf"])))
        return torch.cat(parts, -1)

    nl_const = {}

    def nl_t(pd, nl, Z, Us):
        key = id(nl)
        if key not in nl_const:
            nl_const[key] = (torch.tensor(nl["zm"]), torch.tensor(nl["zs"]), torch.tensor(nl["scale"]))
        zm, zs, sc = nl_const[key]
        zin = torch.cat([(Z - zm) / zs, Us], -1)
        h = torch.tanh(zin @ pd["W1"] + pd["b1"])
        return (h @ pd["W2"] + pd["b2"]) * sc

    hist = []
    sids_d = list(data)

    def total_loss(which: str):
        loss = 0.0
        for sid in sids_d:
            D = data[sid]
            if which == "train":
                tr_i = D["trn"]
                bi = torch.as_tensor(tr_i[rng.integers(0, len(tr_i), min(batch, len(tr_i)))])
            else:
                bi = hold[sid]
                if len(bi) == 0:
                    continue
            loss = loss + sys_loss(sid, D, bi)
        return loss / len(sids_d)

    def sys_loss(sid, D, bi):
        z = D["Z0"][bi]
        U = D["U"][bi]
        dd = model.dyn[sid]
        pd = P_dyn[id(dd)]
        ps = P_sys[sid]
        preds = []
        for h in range(H):
            zn = z @ pd["A"].T + U[:, h] @ ps["B"].T + pd["c"]
            if train_nl and dd.get("nl") is not None:
                zn = zn + nl_t(pd, dd["nl"], z, U[:, h])
            elif dd.get("nl") is not None:
                zn = zn + torch.tensor(_nl_np(dd["nl"], z.detach().numpy(), U[:, h].numpy()))
            z = zn
            preds.append(z)
        Zp = torch.stack(preds, 1)
        l_lat = ((Zp - D["Zf"][bi]) ** 2).sum(-1).mean() / D["zvar"]
        ro = model.sys[sid]["ro"]
        Yp = features(ro, Zp, U[:, :H]) @ ps["G"] + ps["h"]
        l_y = (((Yp - D["Yf"][bi]) ** 2) / D["yv"]).mean()
        return w_lat * l_lat + w_y * l_y

    has_hold = any(len(hold.get(s_, [])) for s_ in sids_d)

    def snapshot():
        return [p.detach().clone() for p in params]

    def holdout_value():
        with torch.no_grad():
            v = total_loss("hold")
        return float(v) if has_hold else np.nan

    best_v = holdout_value()
    v0 = best_v
    best_it = 0
    best_p = snapshot()
    for it in range(steps):
        loss = total_loss("train")
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 10.0)
        opt.step(); sched.step()
        hist.append(float(loss.detach()))
        if has_hold and ((it + 1) % 20 == 0 or it == steps - 1):
            v = holdout_value()
            if np.isfinite(v) and v < best_v:
                best_v, best_p, best_it = v, snapshot(), it
            elif it - best_it >= 120:            # early stop: no held-out improvement for 120 steps
                break
        if _time.time() - t_start > time_budget_s:
            break
    if has_hold:
        with torch.no_grad():
            for p, b in zip(params, best_p):
                p.copy_(b)
    # write back
    for idd, pd in P_dyn.items():
        d = dyn_ids[idd]
        if not freeze_dyn:
            d["A"] = stabilise(pd["A"].detach().numpy().copy(), rho_max)
            d["c"] = pd["c"].detach().numpy().copy()
            if train_nl and d.get("nl") is not None:
                for kk in ("W1", "b1", "W2", "b2"):
                    d["nl"][kk] = pd[kk].detach().numpy().copy()
    for sid, ps in P_sys.items():
        s = model.sys[sid]
        if not freeze_dyn or s.get("B_free", False):
            s["Bs"] = ps["B"].detach().numpy().copy()
        if train_readout:
            s["ro"]["G"] = ps["G"].detach().numpy().copy()
            s["ro"]["h"] = ps["h"].detach().numpy().copy()
    return {"steps": len(hist), "loss_first": hist[0] if hist else np.nan, "loss_last": hist[-1] if hist else np.nan,
            "holdout_before": v0, "holdout_after": best_v, "seconds": _time.time() - t_start}


def _nl_np(nl, Z, Us):
    Zin = np.hstack([(Z - nl["zm"]) / nl["zs"], Us])
    h = np.tanh(Zin @ nl["W1"] + nl["b1"])
    return (h @ nl["W2"] + nl["b2"]) * nl["scale"]


# ================================================================================================================ events
def fit_event_operators(model: LinStateModel, sid: str, P: SysPrep, trajs: list[PTraj], seed: int = 0) -> dict:
    """Event operators of one system, all derived from the encoder / decoder / read-in structure plus a few SYSTEM-LEVEL
    scalars estimated on the system's training intervention trajectories:
    - K: instantaneous encoder gain (static part of the encoder; for history encoders the GLS projection through the decoder);
    - R: read-in map of off-manifold microstate onto the next latent (ridge regression of the one-step latent residual on the
      decoder residual xs - C z - d over free transitions);
    - gamma: current gain (raw rate change per step per unit current), fitted on training current trajectories;
    - silence: decoupled level r = w * (training mean) + (1 - w) * rest and relaxation alpha, both fitted on the training silence
      trajectories' silenced neurons (observed);
    - edge removal: coupling J = C_eff R_eff (decoder x read-in of the latent dynamics), low-rank factored."""
    s = model.sys[sid]
    enc = s["enc"]
    C, d = s["C"], s["d"]
    k = C.shape[1]
    ev = {"kinds": ("kick", "current", "silence", "edge_remove")}
    # instantaneous gain
    if enc.get("_rec") is None:
        # static / history encoders: the change of the encoding when the offset is present over the encoder's whole (short)
        # window, sum_l H_l (= H_0 for a static encoder). For history encoders the lag-0 block alone contains derivative-like
        # weights (x_t - x_{t-l}) that cancel on smooth data, so a step offset through it looks like a huge velocity
        # (real:net3:mech:362044b4: kick effect error 7.6 with H_0, 1.2 with the sum)
        K = np.sum(enc["Hx"], axis=0)
    else:
        # filter encoders: GLS projection through the decoder (a kick is a real state change, not measurement noise)
        Dinv = 1.0 / s["xres"]
        M = C.T @ (C * Dinv[:, None])
        K = np.linalg.solve(M + 1e-8 * np.trace(M) / k * np.eye(k), (C * Dinv[:, None]).T)
    ev["K"] = K
    ev["Kc"] = K
    # read-in of off-manifold microstate (free transitions)
    dyn = model.dyn[sid]
    b = burn_in(enc)
    E, Rz = [], []
    rng = np.random.default_rng(seed)
    for t in trajs:
        Z = latent_series(enc, t)
        ii = np.flatnonzero(t.keep)
        ii = ii[ii >= b]
        if len(ii) > 400:
            ii = np.sort(rng.choice(ii, 400, replace=False))
        pred = Z[ii] @ dyn["A"].T + t.us[ii].astype(np.float64) @ s["Bs"].T + dyn["c"]
        if dyn.get("nl") is not None:
            pred = pred + _nl_np(dyn["nl"], Z[ii], t.us[ii].astype(np.float64))
        Rz.append(Z[ii + 1] - pred)
        E.append(t.xs[ii].astype(np.float64) - Z[ii] @ C.T - d)
    E, Rz = np.concatenate(E), np.concatenate(Rz)
    # valid domain of the latent: the training range widened by 50 % on each side; rollouts are clipped to it (a linear model is
    # only trusted near its data; at small dt a persistent intervention push would otherwise integrate without bound)
    Zall = np.concatenate([latent_series(enc, t)[b::max(1, len(t.xs) // 200)] for t in trajs])
    lo, hi = Zall.min(0), Zall.max(0)
    s["zbox"] = (lo - 0.5 * (hi - lo), hi + 0.5 * (hi - lo))
    # ridge penalty by a 2-fold split
    n = len(E)
    half = rng.permutation(n) < n // 2
    best, best_err = None, np.inf
    for lam in (1e-3, 1e-2, 1e-1, 1.0, 10.0):
        err = 0.0
        for a in (half, ~half):
            W = np.linalg.solve(E[a].T @ E[a] + lam * a.sum() * np.eye(E.shape[1]), E[a].T @ Rz[a])
            err += float(((E[~a] @ W - Rz[~a]) ** 2).sum())
        if err < best_err:
            best, best_err = lam, err
    base_err = float((Rz ** 2).sum())
    Rm = np.linalg.solve(E.T @ E + best * n * np.eye(E.shape[1]), E.T @ Rz).T      # (k, N)
    ev["R"] = Rm
    ev["R_gain"] = float(1 - best_err / max(base_err, 1e-12))
    # silence: decoupled level and relaxation, fitted on training silences
    rest_s = (P.rest - P.mx) / P.sx
    mean_s = np.zeros(P.n_x)                      # training mean in standardised units
    lv, mv, rv, fr = [], [], [], []
    for t in trajs:
        for e in t.events:
            if e["kind"] != "silence":
                continue
            a = int(round(e["t0"] / P.dt))
            bb = len(t.xs) if e.get("t1") is None else int(round(e["t1"] / P.dt))
            if bb - a < 10:
                continue
            w = max(3, (bb - a) // 3)
            for nrn in e["targets"]:
                if int(nrn) not in P.col:
                    continue
                c_ = P.col[int(nrn)]
                lev = float(t.xs[a + w: bb, c_].mean())
                lv.append(lev); mv.append(mean_s[c_]); rv.append(rest_s[c_])
                x0, x1 = float(t.xs[a, c_]), float(t.xs[min(a + 1, bb - 1), c_])
                if abs(lev - x0) > 0.2:
                    fr.append((x1 - x0) / (lev - x0))
    if lv:
        lv, mv, rv = map(np.asarray, (lv, mv, rv))
        dm = mv - rv
        wgt = float(np.clip((dm @ (lv - rv)) / max(dm @ dm, 1e-12), 0.0, 1.0)) if (dm @ dm) > 1e-12 else 1.0
        alpha = float(np.clip(np.median(fr), 0.02, 1.0)) if fr else 0.25
    else:
        wgt, alpha = 1.0, 0.25
    ev["r_sil"] = wgt * mean_s + (1 - wgt) * rest_s
    ev["sil_w"], ev["alpha_sil"] = wgt, alpha
    # edge removal coupling: J[post, pre] = C[post] . R[:, pre] (decoder x read-in), acting through the encoder gain
    ev["Jp"], ev["Jq"] = C.copy(), ev["R"].T.copy()
    ev["Jref"] = ev["r_sil"].copy()
    s["ev"] = ev
    # system-level scales calibrated on the system's own training interventions (the model's event-free rollout serves as
    # counterfactual): current gain, kick efficacy, silencing relaxation and coupling-removal scales (the latter reused for
    # edge removal, since silencing a neuron removes all its couplings)
    ev["gamma"], ev["kick_scale"], ev["rel_scale"], ev["cpl_scale"] = 0.0, 1.0, 1.0, 1.0
    ev["gamma"] = fit_current_gain(model, sid, P, trajs)
    ev["kick_scale"] = calibrate_scales(model, sid, P, trajs, "kick", [{"kick_scale": 1.0}], {"kick_scale": 0.0})[0]
    rel, cpl = calibrate_scales(model, sid, P, trajs, "silence", [{"rel_scale": 1.0, "cpl_scale": 0.0}, {"rel_scale": 0.0, "cpl_scale": 1.0}],
                                {"rel_scale": 0.0, "cpl_scale": 0.0})
    ev["rel_scale"], ev["cpl_scale"] = rel, cpl
    return ev


def persistent_kick_map(model: LinStateModel, sid: str, P: SysPrep, trajs: list[PTraj], h: int, max_rows: int = 20000,
                        seed: int = 0) -> np.ndarray:
    """Persistent-effect map of a microstate offset: Phi_h = ridge regression of z_{t+h} on [xs_t, u binned over t..t+h, 1]
    (free windows; penalty by 2-fold CV), mapped back to an instantaneous latent offset through the model's own h-step
    propagation: K_h = argmin ||A^h K_h - Phi_h||^2 + lam ||K_h - K||^2 (lam = 1e-3 tr(A^h'A^h) / k). Directions of the microstate
    whose effect on the latent does not persist (fast off-manifold relaxation, measurement noise) get no lasting effect."""
    s, dyn = model.sys[sid], model.dyn[sid]
    enc = s["enc"]
    b = burn_in(enc)
    K = s["ev"]["K"] if s.get("ev", {}).get("K") is not None else enc["Hx"][enc["lags"].index(0)]
    k = K.shape[0]
    rng = np.random.default_rng(seed)
    nb = int(min(4, h))
    edges = np.linspace(0, h, nb + 1).astype(int)
    X, Y = [], []
    per = max(20, max_rows // max(1, len(trajs)))
    for t in trajs:
        n = len(t.xs)
        ok = np.convolve(t.keep.astype(float), np.ones(h), "valid") >= h - 0.5
        ii = np.flatnonzero(ok)
        ii = ii[(ii >= b) & (ii + h < n)]
        if len(ii) == 0:
            continue
        if len(ii) > per:
            ii = np.sort(rng.choice(ii, per, replace=False))
        Z = latent_series(enc, t)
        Ub = [t.us[ii[:, None] + np.arange(edges[j], max(edges[j] + 1, edges[j + 1]))[None, :]].astype(np.float64).mean(1) for j in range(nb)]
        X.append(np.hstack([t.xs[ii].astype(np.float64)] + Ub)); Y.append(Z[ii + h])
    X, Y = np.concatenate(X), np.concatenate(Y)
    N = P.n_x
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    n = len(Xs)
    half = rng.permutation(n) < n // 2
    best, be = 1e-2, np.inf
    for lam in (1e-4, 1e-3, 1e-2, 1e-1, 1.0):
        err = 0.0
        for a in (half, ~half):
            W = np.linalg.solve(Xs[a].T @ Xs[a] + lam * a.sum() * np.eye(Xs.shape[1]), Xs[a].T @ (Y[a] - Y[a].mean(0)))
            err += float(((Xs[~a] @ W - (Y[~a] - Y[a].mean(0))) ** 2).sum())
        if err < be:
            best, be = lam, err
    W = np.linalg.solve(Xs.T @ Xs + best * n * np.eye(Xs.shape[1]), Xs.T @ (Y - Y.mean(0)))
    Phi = (W[:N] / sd[:N, None]).T                                  # (k, N): d z_{t+h} / d xs_t
    Ah = np.linalg.matrix_power(dyn["A"], h)
    G = Ah.T @ Ah
    lam = 1e-3 * np.trace(G) / k + 1e-12
    return np.linalg.solve(G + lam * np.eye(k), Ah.T @ Phi + lam * K)


def calibrate_scales(model: LinStateModel, sid: str, P: SysPrep, trajs: list[PTraj], kind: str, components: list[dict],
                     off: dict, lo: float = 0.0, hi: float = 1.2, prior: float = 1.0) -> list[float]:
    """Least-squares scales of event-operator components on the training trajectories whose events are all of `kind`:
    y_true - y_off ~ sum_i s_i (y_i - y_off), where y_off is the rollout with every component off and y_i with only component i
    on (effects of small interventions add). Ridge-shrunk towards `prior` (weight: 5 % of the response energy), clipped to
    [lo, hi]. Without calibration data the prior is returned."""
    s = model.sys[sid]
    ev = s["ev"]
    saved = {k: ev.get(k) for c in components for k in c}
    box = s.pop("zbox", None)            # calibration needs the model's linear response: no domain clip
    rows, tg = [], []
    for t in trajs:
        evs = [e for e in t.events if e["kind"] == kind]
        if not evs or len(evs) != len(t.events):
            continue
        t_ev = min(e.get("t", e.get("t0")) for e in evs)
        i0 = int(round(t_ev / P.dt))
        # with a true counterfactual twin the target is the true effect (window T/16); otherwise the model's event-free
        # rollout is the counterfactual and a short window (T/40) keeps the model's own drift small against the effect
        twin = t.twin_y is not None
        H = max(2, P.T_len // 16) if twin else max(2, int(P.T_len * float(s.get("calib_frac", 1 / 40))))
        if i0 + H >= len(t.xs) or i0 < burn_in(s["enc"]):
            continue
        z0 = model.encode_batch(sid, t.xs.astype(np.float64), t.us.astype(np.float64), np.array([i0]))[0]
        shifted = []
        for e in evs:
            e2 = dict(e)
            for key in ("t", "t0", "t1"):
                if e2.get(key) is not None:
                    e2[key] = round(max(0.0, e2[key] - i0 * P.dt), 9)
            shifted.append(e2)
        u_raw = t.us[i0: i0 + H + 1].astype(np.float64) * s["su"] + s["mu"]
        ev.update(off)
        y_off = model.rollout(sid, z0, u_raw, shifted, P.dt)["y"]
        cols = []
        for c in components:
            ev.update(off); ev.update(c)
            cols.append(((model.rollout(sid, z0, u_raw, shifted, P.dt)["y"] - y_off)[1:] / P.sy).ravel())
        rows.append(np.stack(cols, 1))
        base = t.twin_y[i0 + 1: i0 + H + 1] if twin else y_off[1:]
        tg.append(((t.y[i0 + 1: i0 + H + 1] - base) / P.sy).ravel())
    ev.update(saved)
    if box is not None:
        s["zbox"] = box
    if not rows:
        return [prior] * len(components)
    X, y = np.concatenate(rows), np.concatenate(tg)
    if not (np.isfinite(X).all() and np.isfinite(y).all()):
        return [prior] * len(components)
    G = X.T @ X
    lam = 0.05 * np.trace(G) / len(G) + 1e-12
    sc = np.linalg.solve(G + lam * np.eye(len(G)), X.T @ y + lam * prior)
    return [float(np.clip(v, lo, hi)) for v in sc]


def fit_current_gain(model: LinStateModel, sid: str, P: SysPrep, trajs: list[PTraj]) -> float:
    """Scalar current gain: least squares over the post-onset windows of the training current trajectories (the predicted
    effect is linear in gamma: rollout(gamma) = rollout(0) + gamma * response)."""
    s = model.sys[sid]
    box = s.pop("zbox", None)            # calibration needs the model's linear response: no domain clip
    num, den = 0.0, 0.0
    H = max(1, P.T_len // 8)
    for t in trajs:
        cur = [e for e in t.events if e["kind"] == "current"]
        if not cur or len(t.events) != len(cur):
            continue
        i0 = int(round(min(e["t0"] for e in cur) / P.dt))
        if i0 + H >= len(t.xs) or i0 < burn_in(s["enc"]):
            continue
        z0 = model.encode_batch(sid, t.xs.astype(np.float64), t.us.astype(np.float64), np.array([i0]))[0]
        ev = [dict(e, t0=round(e["t0"] - i0 * P.dt, 9), t1=round(e["t1"] - i0 * P.dt, 9)) for e in cur]
        u_raw = t.us[i0: i0 + H + 1].astype(np.float64) * s["su"] + s["mu"]
        s["ev"]["gamma"] = 0.0
        y0 = model.rollout(sid, z0, u_raw, [], P.dt)["y"]
        s["ev"]["gamma"] = 1.0
        y1 = model.rollout(sid, z0, u_raw, ev, P.dt)["y"]
        r = (y1 - y0)[1:] / P.sy
        base = t.twin_y[i0 + 1: i0 + H + 1] if t.twin_y is not None else y0[1:]
        tgt = (t.y[i0 + 1: i0 + H + 1] - base) / P.sy
        num += float((r * tgt).sum()); den += float((r * r).sum())
    s["ev"]["gamma"] = 0.0
    if box is not None:
        s["zbox"] = box
    # a positive injected current raises its target's input: the gain is non-negative
    return float(max(0.0, num / den)) if den > 1e-12 else 0.0
