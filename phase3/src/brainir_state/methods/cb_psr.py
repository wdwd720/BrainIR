"""cb_psr: microstate predictive-state representation by reduced-rank regression (family E, method 2).

Mathematics
-----------
For every training sample time t (event-free future window) collect the standardised microstate xs_t, the future-feature vector
Phi_t = [y_{t+h}, P x_{t+h}]_{h in hs} (readout and top microstate PCs at log-spaced horizons hs up to H = a quarter of a
trajectory) and the future-input features U_t (current input and the input along the window). The predictive state of x is
E[Phi | x, U]; with the inputs partialled out (Frisch-Waugh / oblique projection, as in subspace identification)

    Phi~ = Phi - Pi_U Phi,   X~ = X - Pi_U X,    B = argmin ||Phi~ - X~ B||^2 + lam n ||B||^2,

and the rank-k predictive state is the reduced-rank solution B_k = B V_k V_k^T (V: right singular vectors of X~ B). The encoder is
the orthonormal basis W of range(B V_k): z = W xs. The probe bank is the set of recorded inputs plus the training interventions:
post-kick / post-current states enter as ordinary samples (their futures are the interventional futures).

Dimension rule (generic, pre-registered): with e(k) the held-out (validation trajectories) error of the rank-k predictor as a fraction
of the residualised future variance and s_i^2 the fraction of that variance carried by singular direction i on training data,
    k_val = smallest k with e(k) <= min_k e(k) + 0.01,   k_sv = #{i : s_i^2 >= 0.01},   k_rule = max(1, min(k_val, k_sv)),
    k = the smallest of k_rule, k_rule + 1, k_rule + 2 whose complete model (encoder, transition, readout, events) has a validation
    rollout error within 10 % (+0.002) of the best of the three (model-based step: dynamics may need a weakly predictive dimension).
Abstention: no spectral gap up to k (max_{i<=k} s_i^2 / s_{i+1}^2 < 4), or k > max(1, N/5) (not judged on keep-only mechanism
systems, manifest mode 'mech'), or no predictable future at all (e(1) > 0.9) -> "no compact state". Reported range: [min(k, k_val),
max(k, k_val)] (the conservative spectral count and the cross-validated plateau), extended to the next gap when abstaining.

Transition: two-stage regression (the next predictive state regressed on the current one and the input): z_{t+1} - z_t = ridge on
[z, u, RFF(z, u)], hyper-parameters (ridge, RFF bandwidth) chosen by validation ROLLOUT error. Readout: ridge on the same
features. Events through the structural operators of cb_core (kick exact through W; silencing / edge removal through f, W and the
unit leak kappa estimated from the silenced units' own traces; current gain g by least squares on the training current windows).
"""

from __future__ import annotations

import numpy as np

from ..api import StateMethod, register
from . import cb_core as C


def split_train_val(train: list, seed: int, draw_holdout: bool = True):
    """Fitting / validation split (finite blow-up trajectories are left out, cb_core.drop_blowups). The given 'val' trajectories
    validate; in addition, when the training trajectories come from a
    few parameter draws (4 <= #draws <= n/3, params_seed in the protocol), every trajectory of a seeded quarter of the draws is moved
    to validation, so that model selection measures generalisation to NEW parameter draws (which the hidden tests hold out).
    Without a 'val' split, a seeded fifth of the trajectories validates."""
    train = C.drop_blowups(train)
    tr = [t for t in train if t.split != "val"]
    va = [t for t in train if t.split == "val"]
    if not va:
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(train))
        nv = max(1, len(train) // 5)
        va = [train[i] for i in sorted(idx[:nv])]
        tr = [train[i] for i in sorted(idx[nv:])]
    if draw_holdout:
        draws = sorted({int(t.protocol.get("params_seed", 0)) for t in tr})
        if 4 <= len(draws) <= len(tr) / 3:
            rng = np.random.default_rng(seed + 29)
            held = set(rng.permutation(draws)[: max(1, len(draws) // 4)].tolist())
            va = va + [t for t in tr if int(t.protocol.get("params_seed", 0)) in held]
            tr = [t for t in tr if int(t.protocol.get("params_seed", 0)) not in held]
    return tr, va


def pcs_of(bins, n=10):
    X = np.concatenate([b.xs for b in bins])
    X = X[:: max(1, len(X) // 20000)]
    _, _, Vt = np.linalg.svd(X - X.mean(0), full_matrices=False)
    return Vt[: min(n, Vt.shape[0])]


def psr_spectrum(btr, bva, H, lams=(1e-4, 1e-3, 1e-2, 1e-1), w_x=0.3, kmax=30):
    """RRR fits on training bins for a ridge grid; the one with the lowest held-out error at its best rank."""
    pcs = pcs_of(btr)
    D = C.future_design(btr, H, pcs=pcs)
    Dv = C.future_design(bva, H, pcs=pcs, stride_s=4)
    N = D[0].shape[1]
    kmax = min(N, kmax)
    best = None
    for lam in lams:
        fit = C.rrr_fit(D[0], D[1], D[2], lam, w_x, D[5], len(D[4]))
        e = C.rrr_predict_err(fit, Dv[0], Dv[1], Dv[2], kmax)
        if best is None or e.min() < best["err"].min():
            best = {"lam": lam, "err": e, "fit": fit}
    best["sv2"] = best["fit"]["sv"] ** 2 / max(best["fit"]["tot"], 1e-12)
    best["pcs"], best["H"] = pcs, H
    return best


def prepare_history(trs, vas, system, stride, seed=0, gain_min=0.10):
    """Encoder input choice (generic rule): x_t alone, or x_t plus causal exponential filters at 1/100 and 1/20 of a trajectory
    (history of the observed units; the readout units' own state, which x_t may not determine, is a filtered function of their
    inputs). History is used iff it reduces the minimum held-out predictive-state error by at least `gain_min` (relative).
    Returns (prep, btr, bva, spec, info)."""
    prep = C.Prep.fit(trs, system, stride)
    btr = [C.bin_traj(t, prep) for t in trs]
    bva = [C.bin_traj(t, prep) for t in vas]
    H = max(2, min(b.M for b in btr) // 4)
    spec = psr_spectrum(btr, bva, H)
    M = min(b.M for b in btr)
    taus = (max(1, M // 100), max(2, M // 20))
    prep_h = C.Prep(**{**prep.__dict__, "taus": taus})
    btr_h = [C.bin_traj(t, prep_h) for t in trs]
    bva_h = [C.bin_traj(t, prep_h) for t in vas]
    spec_h = psr_spectrum(btr_h, bva_h, H)
    e0, e1 = float(np.nanmin(spec["err"])), float(np.nanmin(spec_h["err"]))
    info = {"err_min_x": e0, "err_min_hist": e1, "taus_steps": list(taus)}
    if e1 < (1 - gain_min) * e0:
        info["history"] = True
        return prep_h, btr_h, bva_h, spec_h, info
    info["history"] = False
    return prep, btr, bva, spec, info


def psr_rank_rule(err: np.ndarray, sv2: np.ndarray, N: int, tol: float = 0.01, sv_min: float = 0.01, gap_min: float = 4.0,
                  compact_applies: bool = True):
    """The generic dimension / abstention rule of the module docstring. `gap` = the largest ratio s_i^2 / s_{i+1}^2 among the
    first k directions (a spectral gap at or before k); compactness (k <= N/5) is not judged on keep-only mechanism systems."""
    e = np.asarray(err, float)
    k_val = int(np.flatnonzero(e[1:] <= e[1:].min() + tol)[0]) + 1
    k_sv = int((sv2 >= sv_min).sum())
    k = max(1, min(k_val, k_sv))
    sv = np.r_[sv2, 0.0]
    ratios = sv[:-1] / np.maximum(sv[1:], 1e-12)
    gap = float(ratios[:k].max()) if k <= len(ratios) else float(ratios.max())
    k_gap = next((i + 1 for i in range(k - 1, min(len(ratios), 40)) if ratios[i] >= gap_min and sv[i] >= sv_min / 10), None)
    compact_limit = max(1, N / 5) if compact_applies else np.inf
    no_pred = bool(e[1] > 0.9 and e.min() > 0.8)
    abstain = bool(gap < gap_min or k > compact_limit or no_pred)
    reason = []
    if gap < gap_min:
        reason.append(f"no spectral gap up to k={k} (largest ratio {gap:.2f} < {gap_min})")
    if k > compact_limit:
        reason.append(f"k={k} > N/5")
    if no_pred:
        reason.append("no predictable future from the microstate")
    k_hi = k_gap if k_gap is not None else min(N, len(sv2))
    return {"k": k, "k_val": k_val, "k_sv": k_sv, "gap": gap, "k_range": [min(k, k_val), int(max(k, k_val, k_hi if abstain else k))],
            "abstain": abstain, "reason": "; ".join(reason)}


# ---------------------------------------------------------------------------------------------------------- two-stage regression
def _pairs(bins, W):
    Z0, U0, Z1 = [], [], []
    for b in bins:
        z = b.xs @ W.T
        free = ~b.ev_bins
        idx = np.flatnonzero(free)
        Z0.append(z[idx]); U0.append(b.u[idx]); Z1.append(z[idx + 1])
    return np.concatenate(Z0), np.concatenate(U0), np.concatenate(Z1)


def fit_transition_readout(model: C.CBModel, sid: str, btr, bva, W, H, seed, n_rff=200, refit_bins=None):
    """Two-stage regression transition + readout, ridge / bandwidth chosen by validation rollout error of the readout."""
    rng = np.random.default_rng(seed + 11)
    Z0, U0, Z1 = _pairs(btr, W)
    Zall = np.concatenate([b.xs @ W.T for b in btr])
    Uall = np.concatenate([b.u for b in btr])
    Yall = np.concatenate([b.y for b in btr])
    feat_mu = np.r_[Zall.mean(0), Uall.mean(0)]
    feat_sd = np.r_[Zall.std(0) + 1e-9, Uall.std(0) + 1e-9]
    k, nu = W.shape[0], Uall.shape[1]
    base = rng.standard_normal((k + nu, n_rff))
    phase = rng.uniform(0, 2 * np.pi, n_rff)
    sz = float(np.sqrt(np.mean(Zall.var(0))) + 1e-9)
    zmax = np.abs(Zall).max(0)
    cands = []
    # linear candidate: RFF weights forced to zero (penalty on the random features -> infinity)
    for gamma in (0.0, 0.1, 0.5, 2.0):
        R = {"W": base * np.sqrt(2 * max(gamma, 1e-6) / (k + nu)), "b": phase, "mu": feat_mu, "sd": feat_sd, "n": n_rff}
        F0 = np.hstack([Z0, U0, np.ones((len(Z0), 1)), C.rff_apply(R, np.hstack([Z0, U0]))])
        Fy = np.hstack([Zall, Uall, np.ones((len(Zall), 1)), C.rff_apply(R, np.hstack([Zall, Uall]))])
        pen = np.r_[np.full(k + nu, 1e-3), 0.0, np.full(n_rff, 1e8 if gamma == 0.0 else 1.0)]
        for lam in ((1e-6,) if gamma == 0.0 else (1e-5, 1e-4, 1e-3, 1e-2)):
            Bt = C.ridge_solve(F0, (Z1 - Z0) / sz, lam, pen)
            By = C.ridge_solve(Fy, Yall, lam, pen)
            _install(model, sid, W, Bt, By, R, sz, k, nu, zmax)
            # validation rollouts over TWICE the training horizon: long-horizon instability is penalised
            err = rollout_error(model, sid, bva, min(2 * H, min(b.M for b in bva) - 2), with_events=False)
            cands.append((err, gamma, lam, Bt, By, R))
    errs = np.array([c[0] for c in cands])
    lin_err = cands[0][0]
    # prefer the linear transition unless a nonlinear one is clearly better (10 %)
    best = cands[0] if np.nanmin(errs) > 0.9 * lin_err else cands[int(np.nanargmin(errs))]
    err, gamma, lam, Bt, By, R = best
    if refit_bins is not None:
        # final refit with the selected hyper-parameters on every trajectory (validation draws included)
        Z0, U0, Z1 = _pairs(refit_bins, W)
        Zall = np.concatenate([b.xs @ W.T for b in refit_bins])
        Uall = np.concatenate([b.u for b in refit_bins])
        Yall = np.concatenate([b.y for b in refit_bins])
        pen = np.r_[np.full(k + nu, 1e-3), 0.0, np.full(n_rff, 1e8 if gamma == 0.0 else 1.0)]
        Bt = C.ridge_solve(np.hstack([Z0, U0, np.ones((len(Z0), 1)), C.rff_apply(R, np.hstack([Z0, U0]))]), (Z1 - Z0) / sz, lam, pen)
        By = C.ridge_solve(np.hstack([Zall, Uall, np.ones((len(Zall), 1)), C.rff_apply(R, np.hstack([Zall, Uall]))]), Yall, lam, pen)
        zmax = np.maximum(zmax, np.abs(Zall).max(0))
    _install(model, sid, W, Bt, By, R, sz, k, nu, zmax)
    return {"val_rollout_nmse": err, "gamma": gamma, "lam": lam, "n_rff": n_rff}


def _install(model: C.CBModel, sid, W, Bt, By, R, sz, k, nu, zmax):
    S = model.sys[sid]
    S["W"] = W
    Bt = Bt * sz
    model.trans = {"A": Bt[:k].T.copy(), "b": Bt[k + nu].copy(), "sz": sz, "mlp": [], "rff": R, "Wf": Bt[k + nu + 1:].copy()}
    S["B"] = Bt[k: k + nu].T.copy()
    S["ro"] = {"C": By[:k].T.copy(), "D": By[k: k + nu].T.copy(), "e": By[k + nu].copy(), "mlp": [], "rff": R, "Wr": By[k + nu + 1:].copy()}
    S["zlim"] = 2.0 * zmax + 1e-6


def rollout_error(model: C.CBModel, sid: str, bins, H: int, n_starts: int = 4, with_events: bool = True) -> float:
    """Mean normalised readout NMSE of internal-grid rollouts of H steps from several start points of each binned trajectory
    (events applied through the model's event operators)."""
    errs = []
    for b in bins:
        if b.M <= H + 1:
            continue
        starts = np.linspace(b.M // 8, b.M - H - 1, n_starts).astype(int)
        for m0 in starts:
            z = model.sys[sid]["W"] @ b.xs[m0]
            Zs = _rollout_binned(model, sid, z, b, m0, H, with_events)
            yp = _readout_n(model, sid, Zs[1:], b.u[m0 + 1: m0 + H + 1])
            errs.append(float(np.mean((yp - b.y[m0 + 1: m0 + H + 1]) ** 2)))
    return float(np.mean(errs)) if errs else float("nan")


def _readout_n(model, sid, Z, us):
    S = model.sys[sid]
    R = S["ro"]
    yn = Z @ R["C"].T + us @ R["D"].T + R["e"]
    if R.get("mlp"):
        yn = yn + C.mlp_np(R["mlp"], np.concatenate([Z / model.trans["sz"], us], -1))
    if R.get("rff") is not None:
        yn = yn + C.rff_apply(R["rff"], np.concatenate([Z, us], -1)) @ R["Wr"]
    return yn


def binned_events(b: C.Binned, m0: int, H: int, N: int) -> dict:
    """Events of a binned trajectory window [m0, m0 + H) in the rollout_events format."""
    ev = {"kick": {}, "cur": None, "sil": None, "edges": []}
    for m, c, d in b.kicks:
        if m0 <= m < m0 + H:
            ev["kick"].setdefault(m - m0, np.zeros(N))[c] += d
    for a, e, c, v in b.cur:
        lo, hi = max(a, m0), min(e, m0 + H)
        if lo < hi:
            if ev["cur"] is None:
                ev["cur"] = np.zeros((H, N))
            ev["cur"][lo - m0: hi - m0, c] += v
    for a, e, c in b.sil:
        lo, hi = max(a, m0), min(e, m0 + H)
        if lo < hi:
            if ev["sil"] is None:
                ev["sil"] = np.zeros((H, N))
            ev["sil"][lo - m0: hi - m0, c] = 1.0
    for a, e, i, j in b.edges:
        act = np.zeros(H, bool)
        lo, hi = max(a, m0), min(e, m0 + H)
        if lo < hi:
            act[lo - m0: hi - m0] = True
            ev["edges"].append((act, i, j))
    return ev


def _rollout_binned(model, sid, z, b, m0, H, with_events=True):
    n = model.sys[sid]["prep"].n_units
    ev = binned_events(b, m0, H, n) if with_events else {"kick": {}, "cur": None, "sil": None, "edges": []}
    Z = [z.copy()]
    for m in range(H):
        z = model.step(sid, z, b.u[m0 + m], m, ev)
        Z.append(z.copy())
    return np.stack(Z)


# ---------------------------------------------------------------------------------------------------------- event parameters
def fit_event_params(model: C.CBModel, sid: str, bins):
    """kappa and the silenced baseline from the silenced units' own traces (cb_core.fit_unit_leak); the scalar current gain g by
    least squares on the one-step latent residuals r_m = z_{m+1} - f(z_m, u_m) of the training current windows (r = g W I / s)."""
    S = model.sys[sid]
    W, p = S["W"], S["prep"]
    leak = C.fit_unit_leak(bins, p, W)
    Wu = model.unit_maps(sid)[0]
    S["base_s"] = C.base_state(p, leak)
    num = den = 0.0
    n = 0
    for b in bins:
        if not b.cur:
            continue
        z = b.xs @ W.T
        ev = binned_events(b, 0, b.M, p.n_units)
        for m in range(b.M):
            if m in ev["kick"] or (ev["sil"] is not None and ev["sil"][m].any()):
                continue
            c = ev["cur"][m] if ev["cur"] is not None else None
            if c is None or not c.any():
                continue
            r = z[m + 1] - model.f(sid, z[m], b.u[m])
            wc = Wu @ c                 # (g is fitted on the unbounded response; the range bound applies in rollouts)
            num += float(r @ wc)
            den += float(wc @ wc)
            n += 1
    g = float(max(0.0, num / den)) if den > 0 and n >= 3 else 0.0
    model.ev = {"kappa": leak["kappa"], "g_cur": g, "alpha": {"kick": 1.0, "current": 1.0, "silence": 1.0}}
    C.install_ranges(model, sid)
    H = max(2, min(b.M for b in bins) // 4)
    alpha, rep = C.select_event_gains(model, sid, bins, H, _rollout_binned)
    return {"leak": leak, "g_cur": g, "n_current_steps": n, "alpha": alpha}


# ---------------------------------------------------------------------------------------------------------- the method
def fit_psr_model(train, systems, config, seed, k_force=None):
    t0 = C.now()
    if len({t.system_id for t in train}) != 1:
        raise NotImplementedError("cb_psr fits one system at a time (sharing='independent')")
    sid = train[0].system_id
    trs, vas = split_train_val(train, seed)
    stride = C.choose_stride(train)
    prep, btr, bva, spec, hinfo = prepare_history(trs, vas, systems[sid], stride, seed)
    H = max(2, min(b.M for b in btr) // 4)
    N = prep.n_units
    rule = psr_rank_rule(spec["err"], spec["sv2"], N, compact_applies=systems[sid].get("mode") != "mech")
    ball = btr + bva
    sel = []
    if k_force:
        k = int(k_force)
    elif config.get("k_offset") is not None:
        k = max(1, min(N, rule["k"] + int(config["k_offset"])))
    else:
        k, sel = select_k(prep, sid, btr, bva, H, seed, spec, rule, N)
    # refit on all training trajectories (train + val) with the selected ridge, then the rank-k encoder
    D = C.future_design(ball, H, pcs=spec["pcs"])
    fit = C.rrr_fit(D[0], D[1], D[2], spec["lam"], 0.3, D[5], len(D[4]))
    W = C.rrr_encoder(fit, k)
    if config.get("W_init") is not None and np.asarray(config["W_init"]).shape == W.shape:
        q, _ = np.linalg.qr(np.asarray(config["W_init"], float).T)
        W = q[:, :k].T.copy()
    model, (tinfo, einfo) = _build(prep, sid, W, btr, bva, H, seed, ball, refit=True)
    return model, sid, {"rule": rule, "spec": spec, "trans": tinfo, "events": einfo, "cpu_s": C.now() - t0, "N": N, "H": H,
                        "k_selection": sel, "history": hinfo}


def select_k(prep, sid, btr, bva, H, seed, spec, rule, N):
    """Model-based step of the dimension rule: complete models (train-only encoder) at k_rule, +1, +2; the smallest k whose
    validation rollout error (events applied) is within 10 % (+0.002) of the best."""
    sel = []
    cands = [kk for kk in range(rule["k"], rule["k"] + 3) if kk <= len(spec["sv2"])]
    for kk in cands:
        m_, _ = _build(prep, sid, C.rrr_encoder(spec["fit"], kk), btr, bva, H, seed, btr)
        sel.append({"k": kk, "val_rollout": rollout_error(m_, sid, bva, H)})
    errs = np.array([c["val_rollout"] for c in sel])
    ok = np.flatnonzero(errs <= np.nanmin(errs) * 1.10 + 0.002) if np.isfinite(errs).any() else []
    k = int(sel[int(ok[0])]["k"]) if len(ok) else rule["k"]
    return k, sel


def _build(prep, sid, W, btr, bva, H, seed, ev_bins, refit=False):
    k = W.shape[0]
    model = C.CBModel()
    model.sys[sid] = {"prep": prep, "W": W, "base_s": prep.rest_s.copy()}
    model.k[sid] = k
    model.ev = {"kappa": 0.0, "g_cur": 0.0}
    tinfo = fit_transition_readout(model, sid, btr, bva, W, H, seed, refit_bins=(btr + bva) if refit else None)
    C.install_latent_box(model, sid, btr + bva)
    einfo = fit_event_params(model, sid, ev_bins)
    return model, (tinfo, einfo)


@register
class CBPSR(StateMethod):
    name = "cb_psr"
    version = "1"
    default_config = {}
    supported_sharing = ("auto", "independent")
    supports_adaptation = False

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        config = dict(config or {})
        if config.get("sharing") not in (None, "auto", "independent"):
            raise NotImplementedError("cb_psr supports sharing='independent' only")
        if config.get("adapt_from") is not None:
            raise NotImplementedError("cb_psr does not support encoder-only adaptation")
        model, sid, meta = fit_psr_model(train, systems, config, seed, k_force=config.get("k"))
        rule = meta["rule"]
        k = model.k[sid]
        T = model.trans
        n_tr = int(T["A"].size + T["b"].size + T["Wf"].size + model.sys[sid]["B"].size)
        R = model.sys[sid]["ro"]
        n_ro = int(R["C"].size + R["D"].size + R["e"].size + R["Wr"].size)
        abst = {"no_compact_state": bool(rule["abstain"]) and not config.get("k"),
                "dimension_unresolved": rule["k_range"] if rule["abstain"] else None,
                "causal_equivalence_failed": False, "reason": rule["reason"]}
        kr = [min(rule["k_range"][0], k), max(rule["k_range"][1], k)]
        model.meta = {"k": {sid: k}, "k_range": {sid: kr if not config.get("k") else [k, k]}, "abstain": {sid: abst},
                      "n_params": {"encoder": {sid: int(model.sys[sid]["W"].size)}, "transition": n_tr,
                                   "readout": {sid: n_ro}, "events": 4},
                      "sharing": {"mode": "independent", "verdict": None},
                      "train_cost": {"cpu_s": meta["cpu_s"], "sim_calls": 0},
                      "lipschitz_bound": 1.0,       # orthonormal linear encoder in standardised units
                      "curve": {sid: {"rrr_val_err": [float(v) for v in meta["spec"]["err"][:16]],
                                      "rrr_sv2": [float(v) for v in meta["spec"]["sv2"][:16]], "rule": rule,
                                      "k_selection": meta["k_selection"], "history": meta["history"]}},
                      "dimension_rule": "k_rule = max(1, min(k_val, k_sv)); k = smallest of k_rule..k_rule+2 with validation rollout error "
                                           "<= 1.1 min + 0.002; abstain without spectral gap (max ratio up to k_rule < 4) or k > N/5"}
        return model
