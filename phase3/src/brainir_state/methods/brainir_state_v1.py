"""brainir_state_v1: the composer's state-discovery method (tournament family H). Mathematical definition: notes/brainir_state_v1.md.

Composition (every component is imported from the developer that built it; no other developer's file is modified):

    encoder      z_t = (f_t - mean f) C_k                    f_t = [x~_t, x~_{t-l1}, ...] (standardised microstate, optional causal
                                                             delays); C = predictive basis: reduced-rank ridge regression of the
                                                             future readout and future microstate PCs on f_t, future inputs
                                                             partialled out (ks_core.predictive_basis)
    transition   z_{t+1} = z_t + Theta(z_t, u_t) Xi          sparse polynomial law (monomials of degree <= p, u at most linearly),
                                                             integral-form STLSQ, E-SINDy bagging over trajectories (ks_sindy)
    readout      y_t = ridge on monomials of (z_t, u_t) of degree 1 or 2
    events       kicks through the encoder (optionally microscopically propagated first, config kick_readin); currents / silencing / edge removal as per-step microstate increments of a ridge estimate of the
                 microscopic coupling, mapped through the encoder; one gain per event kind calibrated on the training event
                 trajectories (ks_core.KSModel). supports() is False for kinds without training events, with gain 0 or without a
                 read-in (the evaluator then scores an abstention)
    dimension    ascending k sweep scored by held-out rollout error on trajectory folds; k = the smallest k within
                 tol_k = max(0.1 e*, 0.005, SE_k) of the best (the plateau tolerance of the nn family, nn_fit.select_k), range
                 [smallest k within 2 tol, smallest k within tol / 2]; deterministic candidate list (base grid 1-6, 8;
                 continued to 10, 12, 16 only while the error still falls); no wall-clock dependence
    abstention   ks_abstain.abstention on ks_sindy's own statistics (k > N/5, no plateau, best validation NMSE >= 0.6) + the nn
                 family's input floor (validation error > 0.5 x that of an input-only ridge readout) + dimension_unresolved when
                 the candidate list is exhausted while the error still falls
    sharing      ks_sindy's shared polynomial law, returned only if it is non-inferior (20 % margin, one-sided 95 %) on every system
                 and has fewer transition parameters; otherwise the independent models (verdict 'unsupported')

Ablation switches: config={"ablate": [...]}, names in ABLATIONS (each removes one component; the model stays valid).
"""

from __future__ import annotations

import math

import numpy as np

from ..api import StateMethod, register
from . import ks_core as C
from .ks_abstain import abstention as ks_abstention
from .ks_sindy import KSSindy, SindyModel, build_system, lag_grid, make_basis

#: ablation switch -> what it removes
ABLATIONS = {
    "nn_dim_rule": "plateau tolerance max(0.1 e*, 0.005) -> ks_sindy's paired log-error rule (tol = max(SE, log 1.05))",
    "draw_folds": "configuration (delays, degree, threshold, readout degree) chosen on parameter-draw folds -> on trajectory folds",
    "delays": "causal delay features in the encoder -> the current microstate only",
    "esindy": "E-SINDy bagging (support = inclusion probability >= 0.6) -> one STLSQ fit",
    "sparsity": "sequential thresholding (threshold grid) -> plain ridge least squares on the full library (threshold 0)",
    "event_calibration": "per-kind event gains and silencing mechanism calibrated on training events -> raw mechanisms (gain 1)",
    "domain_clip": "latent rollouts confined to the widened training box -> unconstrained rollouts",
    "abstention": "abstention rules -> never abstain",
    "sharing": "shared-law fit and encoder-only adaptation -> independent fits (config sharing='shared' / adapt_from ignored)",
    "grid_extension": "k sweep continued past 8 (10, 12, 16) while the error still falls -> the base grid (1-6, 8) only",
    "input_floor": "input-floor abstention (latent explains < half of what the input leaves) -> ks_sindy's abstention rules only",
    "nested_selection": "configuration per k chosen on validation units disjoint from those comparing k -> on the same units",
    "oscillation_check": "k >= 2 when the data oscillate under constant input -> no minimum k",
    "fold_repeats": "dimension sweep scored on 2 random trajectory splits (units pooled) -> on one split",
    "sharing_test": "internal non-inferiority test of the shared law -> the shared law is always returned under sharing='shared'",
}


EVENT_KINDS = ("kick", "current", "silence", "edge_remove")
#: how events that act on neurons outside the observed population are handled (reported per system in info()["events"])
UNOBSERVED_POLICY = ("no read-in: the model has no encoder column or coupling estimate for neurons outside x, so the part of an "
                     "event acting on unobserved neurons (kick / current / silence targets, edges with an unobserved end) is "
                     "predicted to have NO effect; events on observed neurons in the same protocol are modelled as usual. supports() "
                     "is per kind, so such pairs are not abstained on; the evaluator scores them apart from the verdict")


class BrainIRModel(SindyModel):
    """The executable model: SindyModel's encoder / law / readout / event operators, plus
    - honest event support: supports(sid, kind) is True only for kinds whose effect was calibrated on the system's own training
      events with a gain > 0 and whose read-in exists (current: a nonzero current gain; edge removal: a positive coupling gain);
      everything else is abstained on;
    - OPTIONAL (config kick_readin=True; off by default, see the notes): an intervention-calibrated kick read-in: the kick is propagated through the estimated microscopic map, dx <- P_h dx with
      P_h = stab(I + A)^h, before it is encoded; h in {0, m, 3m} (0 = the encoder's observational weights) and the kick gain are
      chosen jointly on the training kick trajectories (units that the encoder reads but that do not drive the network decay
      instead of moving the latent)."""

    READIN_STEPS = (0, 1, 3)                 # multiples of the integral window m

    def supports(self, sid, kind):
        sup = self.sys[sid].get("supported")
        return bool(sup.get(kind, False)) if sup is not None else kind in self.event_kinds

    def info(self):
        out = dict(self._info)
        out["events"] = {sid: {kind: {"supported": self.supports(sid, kind), "gain": float((S.get("gain") or {}).get(
            {"edge_remove": "edge"}.get(kind, kind), 1.0)), "calibrated": bool((S.get("calibrated") or {}).get(kind, False))}
            for kind in EVENT_KINDS} | {"kick_readin_steps": int(S.get("kick_h", 0)), "unobserved_targets": UNOBSERVED_POLICY}
            for sid, S in self.sys.items()}
        return out

    def rollout(self, sid, z0, u_future, events, dt):
        P = self.sys[sid].get("kick_P")
        if P is not None and events:
            col = self.sys[sid]["prep"].col
            obs = self.sys[sid]["prep"].observed
            ev2 = []
            for e in events:
                if e["kind"] == "kick":
                    dx = np.zeros(len(obs))
                    for k, v in e["delta"].items():
                        if int(k) in col:
                            dx[col[int(k)]] += float(v)
                    dxp = P @ dx
                    e = {**e, "delta": {str(obs[i]): float(dxp[i]) for i in np.flatnonzero(dxp)}}
                ev2.append(e)
            events = ev2
        return super().rollout(sid, z0, u_future, events, dt)

    def _rollout_grid(self, sid, z0, u_future, events, dt):
        """ks_core.KSModel._rollout_grid with one change (pre-lock review B): a non-finite latent is NOT replaced by a finite value; once
        the state is non-finite the rest of the rollout is NaN, so the evaluator counts the failure."""
        S = self.sys[sid]
        prep, micro = S["prep"], S["micro"]
        u_future = np.asarray(u_future, np.float64)
        n = len(u_future) - 1
        g = C.compile_events(events, n, dt, prep.col, prep.N) if events else None
        z = np.asarray(z0, np.float64).copy()
        Z = np.full((n + 1, len(z)), np.nan)
        Z[0] = z
        lo, hi = S.get("z_lo"), S.get("z_hi")
        mode = S.get("silence_mode", "drive")
        gain = S.get("gain") or {}
        gk, gc, gs, ge = (gain.get(x, 1.0) for x in ("kick", "current", "silence", "edge"))
        for j in range(n):
            if not np.all(np.isfinite(z)):
                break                                            # the remaining rows stay NaN
            if g is not None and j in g.kick:
                z = self._apply_dq(sid, z, gk * self.dx_to_dq(sid, g.kick[j]))
            cont = g is not None and g.any_cont[j]
            if cont:
                xh = self._decode_x(sid, z)
                dx = np.zeros_like(xh)
                if g.cur[j].any():
                    dx += gc * micro.event_dx(xh, g.cur[j], None, None)
                if mode == "drive" and g.sil[j] is not None:
                    dx += gs * micro.event_dx(xh, None, g.sil[j], None)
                if g.edges[j] is not None:
                    dx += ge * micro.event_dx(xh, None, None, g.edges[j])
            z = self._step(sid, z, u_future[j])
            if cont:
                if dx.any():
                    z = self._apply_dq(sid, z, self.dx_to_dq(sid, dx))
                if mode == "clamp" and g.sil[j] is not None:
                    xh = self._decode_x(sid, z)
                    d = np.zeros_like(xh)
                    d[g.sil[j]] = prep.rest[g.sil[j]] - xh[g.sil[j]]
                    z = self._apply_dq(sid, z, gs * self.dx_to_dq(sid, d))
            if lo is not None and np.all(np.isfinite(z)):
                z = np.clip(z, lo, hi)
            Z[j + 1] = z if np.all(np.isfinite(z)) else np.nan
        return {"z": Z, "y": self._readout(sid, Z, u_future[: n + 1])}

    def _readout(self, sid, Z, U):
        Y = super()._readout(sid, np.nan_to_num(Z), U)
        Y[~np.all(np.isfinite(Z), axis=1)] = np.nan              # a non-finite latent gives a non-finite readout
        return Y

    def clip_activity(self, sid, trajs) -> dict:
        """How often the latent box was active on open-loop rollouts of the given (validation) trajectories: fraction of model steps at
        which some coordinate sits on the box boundary (no state is kept in the object)."""
        S = self.sys[sid]
        lo, hi = S.get("z_lo"), S.get("z_hi")
        if lo is None:
            return {"active_frac": 0.0, "rollouts_touching": 0, "n_rollouts": 0, "nonfinite_rollouts": 0}
        from ..evaluate import shift_events
        act, tot, touch, nonfin, nroll = 0, 0, 0, 0, 0
        for tr in trajs:
            T = len(tr.t)
            H = T // 4
            for i0 in np.linspace(T // 8, T // 2, 4).astype(int):
                if i0 + H >= T:
                    continue
                z0 = self.encode(sid, tr.x[: i0 + 1], tr.u[: i0 + 1], tr.dt)
                Z = self._rollout_grid(sid, z0, tr.u[i0: i0 + H + 1], shift_events(tr.events(), float(tr.t[i0]), H * tr.dt), tr.dt)["z"]
                nroll += 1
                fin = np.all(np.isfinite(Z), axis=1)
                nonfin += int(not fin.all())
                on = (np.isclose(Z[fin], lo) | np.isclose(Z[fin], hi)).any(1)
                act += int(on.sum())
                tot += int(fin.sum())
                touch += int(on.any())
        return {"active_frac": act / tot if tot else 0.0, "rollouts_touching": touch, "n_rollouts": nroll, "nonfinite_rollouts": nonfin}

    def choose_silence_mode(self, sid, trajs, scale):           # called by ks_sindy's shared / adapted fits
        return self.calibrate(sid, trajs, scale)

    def calibrate(self, sid, trajs, scale, readin=False, calibrate=True):
        """Per-kind event calibration on the TRAINING event trajectories (ks_core.KSModel.calibrate_events, extended by the kick
        read-in choice), then the support table."""
        S = self.sys[sid]
        by_kind = {k: [t for t in trajs if t.events() and {e["kind"] for e in t.events()} == {k}] for k in ("kick", "current", "silence")}
        S["calibrated"] = {"kick": bool(by_kind["kick"]), "current": bool(by_kind["current"]), "silence": bool(by_kind["silence"]),
                           "edge_remove": bool(by_kind["silence"])}
        S["kick_P"], S["kick_h"] = None, 0
        report = {}
        if not calibrate:
            S["gain"] = {"kick": 1.0, "current": 1.0, "silence": 1.0, "edge": 1.0}
            S["silence_mode"] = "drive"
            S["calibrated"] = {k: False for k in EVENT_KINDS}
            report["chosen"] = "ablated"
        else:
            report = self.calibrate_events(sid, trajs, scale)      # kicks with the encoder read-in (h = 0), currents, silencing
            if readin and by_kind["kick"]:
                m = max(1, int(S["prep"].T) // 100)                   # the integral window of the law
                M = C.stabilise(np.eye(S["prep"].N) + S["micro"].A, 1.0)
                res = {(0, g): v for g, v in report["kick"].items()}
                for mult in self.READIN_STEPS[1:]:
                    P = np.linalg.matrix_power(M, mult * m)
                    S["kick_P"] = P
                    for g in self.GAIN_GRID:
                        S["gain"]["kick"] = g
                        res[(mult * m, g)] = float(C.event_effect_units(self, sid, by_kind["kick"], scale).mean())
                best = min(res, key=lambda key: (res[key], key[0]))          # ties: the shorter read-in
                h, g = best
                S["kick_h"], S["gain"]["kick"] = int(h), float(g)
                S["kick_P"] = np.linalg.matrix_power(M, h) if h > 0 else None
                report["kick_readin"] = {f"h{h_}:g{g_}": v for (h_, g_), v in res.items()}
        cal, gain = S["calibrated"], S["gain"]
        gamma = float(getattr(S["micro"], "gamma", 0.0))
        if calibrate:
            S["supported"] = {"kick": cal["kick"] and gain["kick"] > 0,
                              "current": cal["current"] and gain["current"] > 0 and np.isfinite(gamma) and gamma != 0.0,
                              "silence": cal["silence"] and gain["silence"] > 0,
                              "edge_remove": cal["silence"] and gain["edge"] > 0}
        else:                                                   # raw mechanisms: supported where the read-in exists
            S["supported"] = {"kick": True, "current": bool(np.isfinite(gamma) and gamma != 0.0), "silence": True,
                              "edge_remove": float(getattr(S["micro"], "reliability", 0.0)) > 0}
        report["supported"] = dict(S["supported"])
        return report


def _input_features(u: np.ndarray, u_mu: np.ndarray, u_sd: np.ndarray, lags=(1, 4, 16, 64)) -> np.ndarray:
    U = (np.asarray(u, np.float64) - u_mu) / u_sd
    lagged = [U] + [np.concatenate([np.repeat(U[:1], L, 0), U[:-L]]) for L in lags if L < len(U)]
    on = np.cumsum(np.abs(np.asarray(u)).sum(1) > 1e-6) > 0
    return np.hstack(lagged + [on[:, None].astype(float), np.ones((len(U), 1))])


def input_floor(sid: str, trs: list, entry: dict, folds: list) -> float:
    """Input-only floor of the abstention rule (the nn family's nn_fit.input_floor on this method's folds): validation NMSE (readout
    variance of the fold's training data, the evaluator's floored normaliser) of a ridge map from the input, its lags (1, 4, 16, 64
    model steps) and an onset flag to the readout, averaged over the trajectory folds."""
    errs = []
    for fi, va in folds:
        prep = C.SystemPrep(sid, fi, entry)
        X = np.concatenate([_input_features(t.u, prep.u_mu, prep.u_sd) for t in fi])
        Y = np.concatenate([t.y for t in fi]).astype(np.float64)
        if any(_input_features(t.u, prep.u_mu, prep.u_sd).shape[1] != X.shape[1] for t in va):
            continue
        W = np.linalg.solve(X.T @ X + 1e-3 * len(X) * np.eye(X.shape[1]), X.T @ (Y - prep.y_mu))
        Xv = np.concatenate([_input_features(t.u, prep.u_mu, prep.u_sd) for t in va])
        Yv = np.concatenate([t.y for t in va]).astype(np.float64)
        errs.append(float(np.mean((Xv @ W + prep.y_mu - Yv) ** 2 / prep.y_var)))
    return float(np.mean(errs)) if errs else float("inf")


def _COMPLEXITY(c):                        # (delays?, degree, -threshold): simpler configurations first
    return (len(c[0]) > 0, c[1], -c[2])


def nested_curve(units: dict, halves: np.ndarray, rel_tol: float = 0.05, nested: bool = True) -> tuple[dict, dict]:
    """Per k, validation errors on units whose configuration (delays, degree, threshold) was chosen on DISJOINT units: the validation
    trajectories of every fold are split into two halves; the configuration chosen on one half (simplest within log(1 + rel_tol)
    of the best mean log(NMSE + 0.01)) supplies the errors of the other half (cross-nested). Returns ({k: per-unit errors},
    {k: configuration chosen on all units, for reporting}). nested=False: the best configuration on all units (not nested)."""
    by_k: dict = {}
    for key, v in units.items():
        by_k.setdefault(key[0], {})[key[1:]] = np.asarray(v, float)

    def pick(confs, mask):
        scores = {c: float(C.log_units(u[mask]).mean()) for c, u in confs.items()}
        best = min(scores.values())
        ok = [c for c, s in scores.items() if s <= best + math.log1p(rel_tol) + 1e-12]
        return min(ok, key=lambda c: (_COMPLEXITY(c), scores[c]))
    E, conf = {}, {}
    for k, confs in by_k.items():
        n = {len(u) for u in confs.values()}
        full = np.ones(next(iter(n)), bool)
        conf[k] = pick(confs, full) if nested else min(confs, key=lambda c: float(C.log_units(confs[c]).mean()))
        if not nested or len(n) != 1 or len(halves) != next(iter(n)) or len(set(halves.tolist())) < 2:
            E[k] = confs[conf[k]]
            continue
        e = np.empty(len(halves))
        for h in (0, 1):
            c = pick(confs, halves != h)                      # chosen on the other half
            e[halves == h] = confs[c][halves == h]
        E[k] = e
    return E, conf


def plateau_select(ks: list[int], E: dict, k_min: int = 1, halves: np.ndarray | None = None) -> dict:
    """Dimension rule (pre-lock review D / G). e* = the CROSS-FITTED best error: the best k is chosen on one half of the units and its
    error is taken on the other half (and vice versa), so a noise dip at one k cannot set the reference (winner's curse); without
    halves, e* = the smallest mean error. tol = max(0.1 e*, 0.005) (no variance term); k = the smallest candidate k >= k_min with
    mean e_k <= e* + tol (else the best k >= k_min). Range from validation uncertainty: with d_k = e_k - e_{k_best} paired over units
    and its standard error, lo = the smallest k >= k_min whose one-sided 95 % LOWER bound of d_k is <= tol (not shown worse than the
    tolerance), hi = the smallest k whose UPPER bound is <= tol (shown within it; else k_best); lo <= k <= hi."""
    means = {k: float(np.mean(E[k])) for k in ks}
    kb = min(ks, key=lambda k: means[k])
    e_best = means[kb]
    n = {len(E[k]) for k in ks}
    if halves is not None and len(n) == 1 and len(halves) == next(iter(n)) and len(set(np.asarray(halves).tolist())) == 2:
        h = np.asarray(halves)
        parts = []
        for side in (0, 1):
            kb_side = min(ks, key=lambda k: float(np.mean(np.asarray(E[k])[h != side])))    # chosen on the other half
            parts.append(np.asarray(E[kb_side])[h == side])
        e_best = float(np.mean(np.concatenate(parts)))
    tol = max(0.1 * e_best, 0.005)
    cand = [k for k in ks if k >= k_min] or ks
    k_sel = next((k for k in cand if means[k] <= e_best + tol), min(cand, key=lambda k: means[k]))

    def bounds(k):
        a, b = np.asarray(E[k]), np.asarray(E[kb])
        if len(a) != len(b) or len(a) < 2:
            return means[k] - e_best, means[k] - e_best
        d = a - b
        se = float(d.std(ddof=1) / math.sqrt(len(d)))
        return float(d.mean() - 1.645 * se), float(d.mean() + 1.645 * se)
    lo = next((k for k in cand if bounds(k)[0] <= tol), k_sel)
    hi = next((k for k in cand if bounds(k)[1] <= tol), max(kb, k_sel))
    return {"k": int(k_sel), "range": [int(min(lo, k_sel)), int(max(hi, k_sel))], "tol": float(tol), "best_k": int(kb),
            "best_err": e_best, "means": means, "rule": "plateau", "k_min": int(k_min)}


def sustained_oscillation(prep, trajs, min_frac: float = 0.25) -> dict:
    """Does the (training) data show a sustained oscillation under a CONSTANT input? For every trajectory the longest stretch with
    constant u (>= T/4 samples; its first quarter dropped as transient) is examined on the leading principal component of the
    standardised microstate: oscillating = its autocorrelation has a trough <= -0.3 followed by a peak >= 0.3 within half the stretch,
    and the amplitude does not decay (sd of the second half >= 0.5 x sd of the first half). The data are flagged when >= min_frac
    of the examined stretches (at least 2) oscillate. A 1-D autonomous flow cannot oscillate, so a flag sets k_min = 2."""
    X = np.concatenate([prep.xs(t.x) for t in trajs])
    Xc = X - X.mean(0)
    v = np.linalg.svd(Xc[:: max(1, len(Xc) // 20000)], full_matrices=False)[2][0]
    n_seg, n_osc = 0, 0
    for tr in trajs:
        u = np.asarray(tr.u, float)
        same = np.r_[True, np.all(np.abs(np.diff(u, axis=0)) < 1e-9, axis=1)]
        best, start, i0 = (0, 0), 0, 0
        for i in range(1, len(same) + 1):
            if i == len(same) or not same[i]:
                if i - start > best[0]:
                    best = (i - start, start)
                start = i
        L, i0 = best
        if L < max(16, len(tr.t) // 4):
            continue
        s = (prep.xs(tr.x[i0 + L // 4: i0 + L]) - X.mean(0)) @ v
        s = s - s.mean()
        if s.std() < 1e-9:
            continue
        n_seg += 1
        ac = np.correlate(s, s, "full")[len(s) - 1:] / (s @ s)
        ac = ac[: len(s) // 2]
        if len(ac) < 4:
            continue
        j = int(np.argmin(ac))
        h = len(s) // 2
        if ac[j] <= -0.3 and j + 1 < len(ac) and ac[j + 1:].max() >= 0.3 and s[h:].std() >= 0.5 * s[:h].std():
            n_osc += 1
    flag = n_seg >= 2 and n_osc >= min_frac * n_seg
    return {"flag": bool(flag), "n_stretches": n_seg, "n_oscillating": n_osc}


def persistence_units(trajs: list, scale) -> np.ndarray:
    """Persistence floor on the validation windows of ks_core.val_rollout_error (y held at y(t0); same starts, horizon, cap)."""
    out = []
    for tr in trajs:
        T = len(tr.t)
        H = T // 4
        e = [min(2.0, float(np.mean((tr.y[i0] - tr.y[i0 + 1: i0 + H + 1]) ** 2 / scale)))
             for i0 in np.linspace(T // 8, T // 2, 4).astype(int) if i0 + H < T]
        if e:
            out.append(float(np.mean(e)))
    return np.asarray(out)


def _ks_select(ks: list[int], units: list[np.ndarray], rel_tol: float) -> dict:
    sel = C.select_dimension_paired(ks, units, rel_tol)       # exactly ks_sindy's rule (and its tolerance record)
    sel["rule"] = "ks"
    return sel


@register
class BrainIRStateV1(StateMethod):
    name = "brainir_state_v1"
    version = "1"
    default_config = {"k_grid": (1, 2, 3, 4, 5, 6, 8), "k_ext": (10, 12, 16), "floor_ratio": 0.5, "share_margin": 0.2,
                      "deg_grid": (1, 2, 3), "thr_grid": (0.0, 0.05, 0.2),
                      "lag_fracs": ((0.01, 0.025), (0.01, 0.025, 0.05, 0.1)), "rel_tol": 0.05, "max_val": 16, "n_folds": 2,
                      "ensemble": 24, "incl_thr": 0.6, "max_terms": 60, "max_nmse_abstain": 0.6, "kick_readin": False, "n_fold_repeats": 2,
                      "lam_norm": 0.1, "share_steps": 600, "share_starts": 4, "share_probe_steps": 120, "ablate": ()}
    supported_sharing = ("auto", "independent", "shared")
    supports_adaptation = True

    # ------------------------------------------------------------------------------------------------------------ fit
    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        C.set_threads(3)
        C.seed_all(seed)
        cfg = {**self.default_config, **(config or {})}
        abl = set(cfg.get("ablate") or ())
        unknown = abl - set(ABLATIONS)
        if unknown:
            raise ValueError(f"brainir_state_v1: unknown ablation(s) {sorted(unknown)}; known: {sorted(ABLATIONS)}")
        sharing = cfg.get("sharing", "auto") or "auto"
        if sharing not in self.supported_sharing:
            raise NotImplementedError(f"brainir_state_v1: sharing mode {sharing!r} not supported")
        if cfg.get("adapt_from") is not None and "sharing" not in abl:
            return self._adapt(train, systems, cfg, seed)
        if "delays" in abl:
            cfg["lag_fracs"] = ()
        if "sparsity" in abl:
            cfg["thr_grid"] = (0.0,)
        if "esindy" in abl:
            cfg["ensemble"] = 0
        timer = C.Timer()
        model = BrainIRModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}, "esindy": {},
                "ablate": sorted(abl), "method": self.name}
        tables = {}
        n_tr = 0
        sids = sorted({t.system_id for t in train})
        for sid in sids:
            S, row, table = self._fit_system(model, sid, [t for t in train if t.system_id == sid], systems[sid], cfg, abl, seed,
                                             info)
            tables[sid] = table
            n_tr += row["n_traj"]
        if sharing == "shared" and len(model.sys) > 1 and "sharing" not in abl:
            ok, detail = True, None
            if "sharing_test" not in abl:
                ok, detail = self._sharing_test(train, systems, cfg, abl, seed, dict(model.k))
            if ok:
                KSSindy._share(self, model, train, systems, cfg, seed, info, tables)    # final shared fit on all trajectories
                if "domain_clip" in abl:
                    for S in model.sys.values():
                        S["z_lo"] = S["z_hi"] = None
                info["sharing"].update({"verdict": "supported" if detail is not None else None, "test": detail})
            else:                                       # the held-out evidence does not support one law: independent models
                info["sharing"] = {"mode": "independent", "verdict": "unsupported", "test": detail,
                                   "note": "shared law not non-inferior on held-out trajectories of every system; independent models"}
        elif sharing == "shared" and len(model.sys) > 1:
            info["sharing"] = {"mode": "independent", "verdict": None, "note": "sharing ablated: independent fits returned"}
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr}
        info["lipschitz_bound"] = None
        model._info = info
        return model

    def _fit_system(self, model, sid, trs_all, entry, cfg, abl, seed, info):
        trs = C.decimate(trs_all)
        T = int(np.median([len(t.t) for t in trs]))
        m = max(1, T // 100)
        forced = cfg.get("k")
        k_grid = [int(forced)] if forced else sorted(int(k) for k in cfg["k_grid"])
        k_ext = [] if (forced or "grid_extension" in abl) else sorted(int(k) for k in cfg["k_ext"])
        r_max = max(k_grid + k_ext)
        folds = C.cv_folds(trs, cfg["n_folds"], seed, cfg["max_val"])
        traj_folds = [(a, b) for kind, a, b in folds if kind == "traj"]
        # the dimension is scored on several random trajectory splits (units pooled; paired across k), so that k does not hinge
        # on one split of the fit's seed; the splits derive deterministically from the seed
        n_rep = 1 if "fold_repeats" in abl else max(1, int(cfg["n_fold_repeats"]))
        for r in range(1, n_rep):
            traj_folds += [(a, b) for kind, a, b in C.cv_folds(trs, cfg["n_folds"], seed + 7919 * r, cfg["max_val"]) if kind == "traj"]
        draw_folds = [(a, b) for kind, a, b in folds if kind == "draw"]
        if "draw_folds" in abl or not draw_folds:
            draw_folds = traj_folds
        units = {"traj": {}, "draw": {}}
        cache = {}

        def fold_parts(kind, i, fi, lags):
            key = (kind, i, lags)
            if key not in cache:
                prep = C.SystemPrep(sid, fi, entry)
                micro = C.MicroModel(prep, fi, seed=seed)
                cache[key] = (prep, micro, make_basis(prep, fi, lags, r_max, seed))
            return cache[key]

        def score(kind, fold_list, k):
            for i, (fi, va) in enumerate(fold_list):
                for lags in lag_grid(T, cfg):
                    prep, micro, basis = fold_parts(kind, i, fi, lags)
                    if k > basis["C"].shape[1]:
                        continue
                    for deg in cfg["deg_grid"]:
                        if C.PolyLibrary(k, prep.n_u, deg).n_terms > cfg["max_terms"]:
                            continue
                        for thr in cfg["thr_grid"]:
                            model.sys[sid] = build_system(prep, micro, fi, lags, basis, k, deg, thr, m, seed)
                            e = C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True)
                            units[kind].setdefault((k, lags, deg, thr), []).extend(e.tolist())

        # stage 1: ascending k on trajectory folds (the dimension). The budget is deterministic (the candidate list: base grid, then
        # the extension grid only while the error still falls); nothing depends on wall-clock time
        nested = "nested_selection" not in abl
        halves = np.concatenate([np.arange(len(va)) % 2 for _, va in traj_folds])
        osc = sustained_oscillation(C.SystemPrep(sid, trs, entry), trs) if not forced else {"flag": False}
        k_min = 2 if (osc["flag"] and "oscillation_check" not in abl) else 1

        def current():
            E_, conf_ = nested_curve(units["traj"], halves, cfg["rel_tol"], nested)
            ks_ = sorted(E_)
            return ks_, E_, conf_, plateau_select(ks_, E_, k_min, halves if nested else None)
        status = "complete"
        for k in k_grid:
            score("traj", traj_folds, k)
        # grid extension: beyond the base grid only while the last candidate is the best and improved by more than the tolerance
        for j, k in enumerate(k_ext):
            kk, E_, _, sel_now = current()
            if len(kk) < 2 or kk[-1] < max(k_grid):
                break
            if sel_now["best_k"] != kk[-1] or np.mean(E_[kk[-2]]) - np.mean(E_[kk[-1]]) <= sel_now["tol"]:
                break
            n_before = len(units["traj"])
            score("traj", traj_folds, k)
            if len(units["traj"]) == n_before:           # k beyond the basis dimension
                break
            if j == len(k_ext) - 1:
                kk, E_, _, sel_now = current()
                if sel_now["best_k"] == kk[-1] and np.mean(E_[kk[-2]]) - np.mean(E_[kk[-1]]) > sel_now["tol"]:
                    status = "exhausted"                 # the whole candidate list used while the error still fell
        ks, E, conf, sel_pl = current()
        kunits = [E[k] for k in ks]
        sel_ks = _ks_select(ks, kunits, cfg["rel_tol"])
        sel = sel_ks if "nn_dim_rule" in abl else sel_pl
        if "nn_dim_rule" in abl and sel["k"] < k_min:
            sel = {**sel, "k": next((k for k in ks if k >= k_min), sel["k"])}
        k_sel = int(sel["k"])
        # stage 2: configuration at the selected k on parameter-draw folds (generalisation to unseen draws)
        score("draw", draw_folds, k_sel)
        sub = {key: v for key, v in units["draw"].items() if key[0] == k_sel}
        best = C.table_from_units(sub, _COMPLEXITY, cfg["rel_tol"])[k_sel]
        best["lags"], best["deg"], best["thr"] = best.pop("conf")
        # readout degree on the same folds at the selected configuration
        ro_err = {}
        for rd in (1, 2):
            e = []
            for i, (fi, va) in enumerate(draw_folds):
                prep, micro, basis = fold_parts("draw", i, fi, best["lags"])
                model.sys[sid] = build_system(prep, micro, fi, best["lags"], basis, k_sel, best["deg"], best["thr"], m, seed, ro_deg=rd)
                e += C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True).tolist()
            ro_err[rd] = float(np.mean(e))
        ro_deg = min(ro_err, key=ro_err.get)
        # persistence floor on the same validation units (y held at y(t0)); the fold's own readout normaliser
        pers = np.concatenate([persistence_units(va, C.SystemPrep(sid, fi, entry).y_var) for fi, va in traj_folds])
        cache.clear()
        # final E-SINDy fit on all trajectories (train + val)
        prep_f = C.SystemPrep(sid, trs, entry)
        micro_f = C.MicroModel(prep_f, trs, seed=seed)
        basis_f = make_basis(prep_f, trs, best["lags"], r_max, seed)
        S = build_system(prep_f, micro_f, trs, best["lags"], basis_f, k_sel, best["deg"], best["thr"], m, seed, ro_deg=ro_deg,
                         ensemble=cfg["ensemble"], incl_thr=cfg["incl_thr"])
        if "domain_clip" in abl:
            S["z_lo"] = S["z_hi"] = None
        model.sys[sid] = S
        model.k[sid] = k_sel
        calib = model.calibrate(sid, trs, prep_f.y_var, readin=bool(cfg["kick_readin"]), calibrate="event_calibration" not in abl)
        curve = [{"k": k, "val_nmse": float(np.mean(E[k])), "lags": conf[k][0], "deg": conf[k][1], "thr": conf[k][2],
                  "units": [float(v) for v in E[k]]} for k in ks]
        e_k = float(np.mean(E[k_sel]))
        if "abstention" in abl:
            ab = {"no_compact_state": False, "dimension_unresolved": None, "causal_equivalence_failed": False, "reason": "ablated"}
        else:
            # ks_sindy's abstention on ks_sindy's own statistics (its tolerance and best k; held-out S7 0.967), with the selected k
            # for the compactness test; the range-width "dimension unresolved" flag is not used
            ab = ks_abstention(curve, {**sel_ks, "k": k_sel}, prep_f.N, forced=bool(forced), max_nmse=cfg["max_nmse_abstain"])
            if ab["dimension_unresolved"] is not None:
                ab["dimension_unresolved"], ab["reason"] = None, ""
            # input floor (the nn family's rule, held-out S7 0.978): the latent explains less than half of what the input leaves
            if not forced and "input_floor" not in abl:
                floor = input_floor(sid, trs, entry, traj_folds)
                if e_k > cfg["floor_ratio"] * floor:
                    ab["no_compact_state"] = True
                    msg = f"latent explains too little beyond the input (val {e_k:.3f} > {cfg['floor_ratio']} x input floor {floor:.3f})"
                    ab["reason"] = (ab["reason"] + "; " if ab["reason"] else "") + msg
            if status == "exhausted" and not forced and not ab["no_compact_state"]:
                ab["dimension_unresolved"] = [int(sel["range"][0]), None]
                ab["reason"] = (ab["reason"] + "; " if ab["reason"] else "") + "candidate list exhausted while the error still fell"
        # checks reported per system (pre-lock reviews B / E)
        ek = np.asarray(E[k_sel])
        pm = float(np.mean(pers)) if len(pers) else float("nan")
        beats = None
        if len(pers) == len(ek) and len(ek) > 1:
            d = ek - pers
            beats = bool(d.mean() + 1.645 * d.std(ddof=1) / math.sqrt(len(d)) < 0)
        val_trs = [t for t in trs if t.split == "val"] or trs[: max(1, len(trs) // 5)]
        info.setdefault("checks", {})[sid] = {
            "oscillation": {**osc, "k_min": k_min},
            "persistence": {"model_val_nmse": e_k, "persistence_val_nmse": pm, "static": bool(np.isfinite(pm) and pm < 0.01),
                            "beats_persistence": beats},
            "latent_clip_on_validation": model.clip_activity(sid, val_trs)}
        info["k"][sid] = k_sel
        info["k_range"][sid] = [int(sel["range"][0]), int(sel["range"][1])]
        info["dim_curve"][sid] = curve
        info["abstain"][sid] = ab
        info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
        info["n_params"]["readout"][sid] = S["n_params"]["readout"]
        info["n_params"]["transition"] += S["n_params"]["transition"]
        info["config"][sid] = {"lags": best["lags"], "deg": best["deg"], "thr": best["thr"], "ro_deg": ro_deg, "m": m,
                               "silence_mode": S["silence_mode"], "event_calibration": calib, "gamma": micro_f.gamma,
                               "micro_r2": micro_f.r2, "sweep_status": status, "nested_selection": nested,
                               "k_plateau_rule": {"k": sel_pl["k"], "range": sel_pl["range"], "tol": sel_pl["tol"]},
                               "k_ks_rule": {"k": sel_ks["k"], "range": sel_ks["range"]}, "dim_rule": sel["rule"]}
        info["esindy"][sid] = {"terms": S["lib"].names, "n_active": int((np.abs(S["W"]) > 0).sum()),
                               "inclusion": S["incl"].tolist() if S["incl"] is not None else None}
        return S, {"n_traj": len(trs)}, {k: {"deg": conf[k][1], "thr": conf[k][2]} for k in ks}

    # ------------------------------------------------------------------------------------------------ sharing test
    def _sharing_test(self, train, systems, cfg, abl, seed, k_ind):
        """Held-out sharing test (pre-lock review H). Per system, held-out trajectories = its 'val' split (or every 5th trajectory if
        fewer than 3). On the remaining trajectories: independent models at each system's selected k (configuration re-chosen) and the
        shared law (ks_sindy's shared fit); both are compared on the held-out trajectories only. Supported iff, for EVERY system, the
        one-sided 95 % upper bound of the paired per-trajectory difference of rollout NMSE (shared - independent; ks_core.val_rollout_error,
        capped at 2) is <= margin x the independent error, and the shared law has fewer transition parameters than the independent
        laws together."""
        margin = cfg["share_margin"]
        sids = sorted({t.system_id for t in train})
        held, fitp = {}, []
        for sid in sids:
            trs = [t for t in train if t.system_id == sid]
            h = [t for t in trs if t.split == "val"]
            if len(h) < 3:
                h = trs[4::5]
            hk = {id(t) for t in h}
            held[sid] = h
            fitp += [t for t in trs if id(t) not in hk]
        tmp = BrainIRModel()
        tinfo = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                 "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}, "esindy": {}}
        ttab = {}
        for sid in sids:
            _, _, ttab[sid] = self._fit_system(tmp, sid, [t for t in fitp if t.system_id == sid], systems[sid],
                                               {**cfg, "k": int(k_ind[sid])}, abl | {"abstention"}, seed, tinfo)
        indep_sys, n_in = dict(tmp.sys), int(tinfo["n_params"]["transition"])
        KSSindy._share(self, tmp, fitp, systems, {k: v for k, v in cfg.items() if k != "k"}, seed, tinfo, ttab)
        n_sh = int(tinfo["n_params"]["transition"])
        shared_sys = dict(tmp.sys)
        detail, ok = {}, True
        for sid in sids:
            trs = C.decimate(held[sid])
            scale = shared_sys[sid]["prep"].y_var
            e_sh = C.val_rollout_error(tmp, sid, trs, scale=scale, return_units=True)
            tmp.sys[sid] = indep_sys[sid]
            e_in = C.val_rollout_error(tmp, sid, trs, scale=scale, return_units=True)
            tmp.sys[sid] = shared_sys[sid]
            d = e_sh - e_in
            up = float(d.mean() + 1.645 * d.std(ddof=1) / math.sqrt(len(d))) if len(d) > 1 else float(d.mean())
            ok_s = bool(len(d) > 0 and up <= margin * float(e_in.mean()))
            detail[sid] = {"shared": float(e_sh.mean()), "independent": float(e_in.mean()), "diff_upper95": up, "ok": ok_s,
                           "n_heldout": len(trs)}
            ok = ok and ok_s
        detail["transition_params"] = {"shared": n_sh, "independent": n_in}
        return bool(ok and n_sh < n_in), detail

    # ------------------------------------------------------------------------------------------------ adaptation
    def _adapt(self, train, systems, cfg, seed):
        """Encoder-only adaptation (ks_sindy): the polynomial law of `adapt_from` is frozen; per-system linear encoders (multi-start)
        and ridge readouts are fitted; events calibrated on the new system's training events (as in a normal fit)."""
        m = KSSindy._adapt(self, train, systems, cfg, seed)
        out = BrainIRModel()
        out.sys, out.k, out._info = m.sys, m.k, m._info
        for sid in out.sys:                                   # the honest support table and the kick read-in for the new systems
            trs = C.decimate([t for t in train if t.system_id == sid])
            out.calibrate(sid, trs, out.sys[sid]["prep"].y_var)
        out._info["method"] = self.name
        return out

    # KSSindy's sharing helpers are reused as unbound functions (they only read cfg / seed)
    _fit_encoders = KSSindy._fit_encoders
