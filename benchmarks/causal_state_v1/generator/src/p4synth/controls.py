"""Per-system margin of the non-compressible controls (types 20 / 21; review round 3, B4).

The benchmark calls a state compact when k <= q = max(1, floor(N_obs / 5)). The margin of a system is the rank needed for 90 % of
its moderate single-unit readout responses to be reproduced within the floor f_s = 0.05 sd(y), divided by q. At construction it
is computed from the linearised causal dynamics (SlowModes: dz/dt = A z + b s(u), A = Q Lambda Q^T; the 'sat' variant linearised
at the state), responses along the nominal trajectory, the readout linearised along it — no simulation beyond one nominal
trajectory — and a draw whose margin is below MARGIN_BUILD at any horizon is rejected (the suite redraws the system). The test
suite checks the same quantity from simulated responses (>= 1.5 per system)."""

from __future__ import annotations

import math

import numpy as np

from .engine import CORE

MARGIN_ACCEPT = 1.5           # construction: a control is accepted only with a SIMULATED margin >= 1.5 at both horizons
MARGIN_SCREEN = 1.3           # surrogate pre-screen (its error vs simulation is up to ~30 %): below it the draw is not simulated
MARGIN_BUILD = 1.7            # construction threshold (the tested bound is 1.5; the surrogate is linearised, error up to ~15 %)
HORIZONS = (0.25, 1.0)        # s: the benchmark's primary horizon (12.5 % of t_end) and a long horizon
PROBE_PULSE = 0.05


def _psi_prime(ro, a):
    out = np.empty_like(a)
    for j, kd in enumerate(ro.kinds):
        w = ro.width[j]
        x = a[..., j]
        if kd == "lin":
            out[..., j] = 1.0
        elif kd == "relu":
            out[..., j] = (x > 0).astype(float)
        elif kd == "relu2":
            out[..., j] = 2.0 * np.maximum(x, 0.0)
        elif kd == "softplus":
            out[..., j] = 1.0 / (1.0 + np.exp(-np.clip(x / w, -60, 60)))
        else:
            s = 1.0 / (1.0 + np.exp(-np.clip(x / w, -60, 60)))
            out[..., j] = s * (1.0 - s) / w
    return out


def rank_needed(M: np.ndarray, n_t: int, fs: float, q: int) -> dict:
    """Rows of M = responses (n_t samples x n_y, flattened). The rank for 90 % of the rows within 1 f_s (RMS), the rank-q
    residuals."""
    U, sv, _ = np.linalg.svd(M, full_matrices=False)
    tot = np.sum(M ** 2, axis=1)
    cum = np.concatenate([np.zeros((M.shape[0], 1)), np.cumsum((U * sv) ** 2, axis=1)], axis=1)

    def resid(r):                           # RMS residual of every row after the best rank-r basis (from the SVD, no reconstruction)
        return np.sqrt(np.maximum(tot - cum[:, min(r, cum.shape[1] - 1)], 0.0) / M.shape[1]) / fs

    need = next((r for r in range(q, len(sv) + 1) if np.percentile(resid(r), 90) < 1.0), len(sv))
    rq = resid(q)
    return {"need": int(need), "bound": int(q), "ratio": need / q, "resid_median": float(np.median(rq)),
            "frac_gt_fs": float(np.mean(rq > 1.0))}


def simulated_margin(s, horizons=HORIZONS) -> dict:
    """{horizon: rank_needed(...)} from SIMULATED readout responses (public units): every moderate single-unit kick and 50 ms
    pulse on the targetable core units from the nominal state at 0.4 t_end, every kick from the state at 0.8 t_end, constant
    nominal input, minus the twin."""
    cap = s.capability()
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    nom = s.simulate(s.base_protocol())
    fs = 0.05 * max(float(np.sqrt(np.mean(np.var(nom["y"], axis=0)))), 1e-12)
    o = s.simulate(s.base_protocol(), full=True)
    T = o["state"].shape[0]
    lvl = [1.0] * s.input_dim if s.input_dim > 1 else 1.0
    Hm = max(horizons)
    base = s.base_protocol(t_end=Hm, stimulus=[[0.0, lvl]])
    tg = [u for u in s.targetable if s.spec.role[u] == CORE]
    rows = []
    for f_, kinds in ((0.4, ("kick", "pulse")), (0.8, ("kick",))):
        st = o["state"][int(f_ * (T - 1))]
        tw = s.simulate(base, restart_state=st)["y"]
        for u in tg:
            for kd in kinds:
                ev = ({"kind": "kick", "t": 0.0, "delta": {str(u): mk}} if kd == "kick" else
                      {"kind": "current", "t0": 0.0, "t1": PROBE_PULSE, "targets": {str(u): mc}})
                rows.append((s.simulate(dict(base, events=[ev]), restart_state=st)["y"] - tw)[1:])
    q = max(1, len(s.observed) // 5)
    out = {}
    for H in horizons:
        n_t = int(round(H / s.dt))
        M = np.array([r[:n_t].ravel() for r in rows])
        out[H] = rank_needed(M, n_t, fs, q)
    return out


def surrogate_margin(s) -> dict:
    """{horizon: rank_needed(...)} from the linearised dynamics (internal units; nominal draw, constant nominal input)."""
    sp = s.spec
    lat = sp.latent
    P0 = lat.nominal()
    A = lat.Q @ lat.Lam(P0) @ lat.Q.T
    nom = s._simulate_internal(s.base_protocol(), full=True)
    fs = 0.05 * max(float(np.sqrt(np.mean(np.var(nom["y"], axis=0)))), 1e-9)
    T = nom["z"].shape[0]
    Z = s._simulate_internal(s.base_protocol(t_end=3.0), full=True)["z"]     # long enough for the long horizon from 0.8 t_end
    lam, V = np.linalg.eig(A)
    Vi = np.linalg.inv(V)
    dt = s.dt
    ro = lat.ro
    gain = ro.gain * float(P0.get("ro_gain", 1.0))
    tg = [u for u in s.targetable if sp.role[u] == CORE]
    Lt = sp.L[:, [sp.loc[u] for u in tg]]
    n_obs = len(s.observed)
    q = max(1, n_obs // 5)
    out = {}
    nH = int(round(max(HORIZONS) / dt))
    tt = np.arange(1, nH + 1) * dt
    ek = np.exp(np.outer(tt, lam))                                      # (nH, k) modal propagators
    D = PROBE_PULSE
    ld = np.where(np.abs(lam) > 1e-12, lam, 1e-12)
    ep = np.where(tt[:, None] <= D, (np.exp(np.outer(tt, lam)) - 1.0) / ld,
                  np.exp(np.outer(np.maximum(tt - D, 0.0), lam)) * (np.exp(ld * D) - 1.0) / ld)
    RV = ro.R @ V                                                        # readout of the modes
    ck = Vi @ Lt                                                         # modal coefficients of the unit kicks
    cp = Vi @ (Lt / sp.tau_c)                                            # of the unit pulses (per unit current)
    resp = {}
    for f_, kinds in ((0.4, ("kick", "pulse")), (0.8, ("kick",))):
        i0 = int(f_ * (T - 1))
        zt = Z[i0 + 1:i0 + 1 + nH]
        nz = zt.shape[0]
        a = zt @ ro.R.T + ro.c[None, :] + ro.d[:, 0][None, :] * 1.0
        J = _psi_prime(ro, a) * gain[None, :]                            # (nz, n_y): d y_j / d a_j along the twin trajectory
        for kd in kinds:
            C = ck if kd == "kick" else cp
            E_ = ek if kd == "kick" else ep
            dA = np.real(np.einsum("jn,tn,nu->utj", RV, E_[:nz], C))      # (n_targets, nz, n_y): R dz per unit magnitude
            dY = dA * J[None, :, :]
            resp[(f_, kd)] = dY
    # moderate magnitudes: median readout ES = 8 over the primary horizon (as the capability probe)
    nP = int(round(HORIZONS[0] / dt))
    mag = {}
    for kd in ("kick", "pulse"):
        es = np.sqrt(np.mean(resp[(0.4, kd)][:, :nP] ** 2, axis=(1, 2))) / fs
        mag[kd] = 8.0 / max(float(np.median(es)), 1e-300)
    for H in HORIZONS:
        n_t = int(round(H / dt))
        rows = [resp[key][:, :n_t] * mag[key[1]] for key in resp]
        M = np.concatenate([r.reshape(r.shape[0], -1) for r in rows])
        out[H] = rank_needed(M, n_t, fs, q)
    return out


def cached_simulated_margin(s) -> dict:
    """simulated_margin(s), cached on disk when P4SYNTH_CACHE_DIR is set (key: construction hash, public-unit factors and engine id;
    the result is deterministic, the cache only saves time when test processes rebuild the same suites)."""
    import hashlib
    import json
    import os
    d = os.environ.get("P4SYNTH_CACHE_DIR")
    key = None
    if d:
        from .engine import ENGINE_ID
        key = hashlib.sha256((s.construction_hash() + repr(sorted(s.units().items())) + ENGINE_ID).encode()).hexdigest()[:32]
        f = os.path.join(d, f"margin_{key}.json")
        if os.path.exists(f):
            try:
                return {float(h): v for h, v in json.load(open(f)).items()}
            except Exception:
                pass
    out = simulated_margin(s)
    if d:
        try:
            os.makedirs(d, exist_ok=True)
            json.dump({str(h): v for h, v in out.items()}, open(os.path.join(d, f"margin_{key}.json"), "w"))
        except OSError:
            pass
    return out
