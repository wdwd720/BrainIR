"""Native lift and multiple lifts (benchmarks/causal_state_v1/PROTOCOL.md section 5.7; goal5 sections 15-16, 72).

For each LIFT CASE c (a held-out PASSIVE protocol P_c and a time t_c; built by `brainir_causal.suites`) the evaluator requests latent
shifts delta_z in the model's WHITENED latent coordinates and asks the model for up to 3 DISTINCT physical interventions realising each
shift (`CausalStateModel.lift`). Every candidate is simulated from the exact microstate (the protocol P_c plus the lift's events at
t_c) together with its counterfactual twin (the same protocol without the lift's events, with the lift's breakpoints kept as no-op
stimulus steps: `protocol.counterfactual`), and scored at the COMPLETION sample j of the lift (one sample after the last instantaneous
event; the end of the last finite event):

- latent miss       ||W (dz_achieved - dz)|| / ||W dz||, dz_achieved = phi(lifted history to j) - phi(twin history to j), W the
                    whitening of the model's latent covariance (so the miss is relative to the requested alpha latent sd);
- cost              `accounting.experiment_cost` magnitude of the lift's events (kicks |delta| x dt, currents |I| x duration, ...) and
                    the number of targets;
- future consistency (primary, EFFECT form)  FC = sum_t ||(y_do - y_nolift) - (y_lift - y_twin)||^2 / max(sum_t ||y_lift - y_twin||^2,
                    n_t n_y f^2) over the primary horizon after j, where y_do / y_nolift are the model's rollouts from phi(twin history)
                    + dz and from phi(twin history) (no events), and f is the system's effect floor. The RAW form (the literal reading
                    of the protocol sentence: the model's do-rollout against the lifted simulation, same denominator) is reported
                    beside; the effect form is used for success because the model's passive prediction error is scored elsewhere
                    (PROTOCOL 5.2) and would otherwise be counted twice;
- multiple-lift consistency  for pairs of DISTINCT lifts of one request: the RMS divergence of their simulated readout futures over a
                    common window (J = the latest completion sample of the request's distinct lifts, J+1 ... J+n_h) divided by the
                    mean RMS lifted effect (lifted - twin over the same window, floored at f). ADJUSTED (the reading of "residual
                    after regressing the divergence on the difference of achieved shifts" that is not confounded by the request
                    magnitude): per pair, the RMS of (y_a - y_b) - (e_a - e_b) over the window, where e_a is the model's own predicted
                    effect of lift a's ACHIEVED shift (rollouts from the twin's encoding at a's completion sample with and without
                    dz_achieved_a), over the same effect scale; 0 when two lifts that realised the same latent shift have the same
                    future. The pooled-regression intercept (pair ratio against the whitened distance of the achieved shifts, slope
                    >= 0) is reported as a secondary number: across pairs it is confounded by the request magnitude (larger requests
                    have both larger divergences and larger achieved-shift differences). Also the INVARIANCE RATIO: mean
                    same-request divergence / mean divergence of lifts of DIFFERENT requests of the same case;
- duplicate realisations  identical event sets are dropped before simulation; a lift whose achieved microstate change (observed x, or
                    the full microstate when the simulator returns it) has cosine > 0.99 with an earlier distinct lift of the same
                    request is ONE realisation: it counts for miss / FC / success, not for consistency or the true-shift spread;
- untestable        no request with two distinct simulated lifts -> consistency "untestable" (never a perfect score);
- success           per lift: miss <= 0.5 and FC <= 0.5. Per request: at least one successful lift (the primary success rate, over
                    ALL requests, unsupported or invalid ones counting as failures); also the share of requests with >= 2 successful
                    distinct lifts;
- uncertainty       when a candidate reports "dz_sd" (model coordinates): the share of latent coordinates whose achieved shift lies
                    within predicted_dz +- 1.645 dz_sd (nominal 90 %), and the rank correlation of the reported sd (whitened norm)
                    with the realised miss;
- synthetic truth   when the simulator returns the TRUE causal state "z": the relative spread of the true shift across the distinct
                    lifts of one request (mean pairwise distance / mean norm).

A model whose class does not override `CausalStateModel.lift` (or returns nothing) FAILS every request (success 0); nothing is
simulated for it. Lifts must be valid protocol events of the system (the protocol validator plus an optional `validator` callback of
the harness that applies the system's capability); persistent events are refused (a latent SHIFT must complete), and a lift must
complete early enough for a full primary-horizon window inside the case protocol.

Simulation goes through a batch callback `simulate_many(protocols, full=False) -> [record]` (records with t, x, u, y and, when full,
optional "z" (true causal state) and "state" (the full microstate)); the harness implements it with the store / engines / synthetic
adapter. All model calls run on fresh copies (`brainir_causal.fresh`). Reference models (`brainir_causal.refs`) may receive the
simulated TRUE state of lifted histories through their `register_truth` hook (evaluator-side, references only).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass

import numpy as np

from . import protocol as P
from .accounting import experiment_cost
from .api import CausalStateModel
from .fresh import Fresh, as_fresh, safe_call
from .stats import N_BOOT, Estimate, boot_mean, boot_stat

COS_MAX = 0.99
MISS_MAX = 0.5
FC_MAX = 0.5
FC_CAP = 10.0
Z90 = 1.6448536269514722


@dataclass(frozen=True)
class LiftConfig:
    n_lifts: int = 3
    alphas: tuple[float, ...] = (0.5, 1.0)
    n_principal: int = 2
    n_random: int = 1
    miss_max: float = MISS_MAX
    fc_max: float = FC_MAX
    cos_max: float = COS_MAX
    n_boot: int = N_BOOT
    seed: int = 0
    eig_floor: float = 1e-8            # whitening eigenvalue floor x the largest eigenvalue (as PROTOCOL 5.5)


DEFAULT_LIFT = LiftConfig()


# ------------------------------------------------------------------------------------------------------------ helpers
def lift_supported(model) -> bool:
    """True when the model's class overrides CausalStateModel.lift (the default returns [])."""
    m = model.get() if isinstance(model, Fresh) else model
    meth = getattr(type(m), "lift", None)
    return meth is not None and meth is not CausalStateModel.lift


def _is_reference(model) -> bool:
    m = model.get() if isinstance(model, Fresh) else model
    return type(m).__module__ == "brainir_causal.refs" and hasattr(m, "register_truth")


def shift_events(events: list[dict], t0: float) -> list[dict]:
    """Events with times relative to t0 -> absolute times (t, t0, t1 shifted; current_seq keeps its seg)."""
    out = []
    for e in events:
        e2 = copy.deepcopy(e)
        for key in ("t", "t0"):
            if key in e2 and e2[key] is not None:
                e2[key] = float(e2[key]) + float(t0)
        if e2.get("t1") is not None:
            e2["t1"] = float(e2["t1"]) + float(t0)
        out.append(e2)
    return out


def completion_index(events: list[dict], dt: float) -> int | None:
    """The first sample at which every (canonical, absolute-time) event has fully acted: one sample after an instantaneous event,
    the end sample of a finite event; None when an event is persistent (t1 null) — a persistent change never completes a shift."""
    js = []
    for e in events:
        if P.semantics(e) == "persistent":
            return None
        if P.semantics(e) == "instantaneous":
            js.append(round(float(e["t"]) / dt) + 1)
        elif e["kind"] == "current_seq":
            js.append(round(P.seq_boundaries(e, dt)[-1] / dt))
        else:
            js.append(round(float(e["t1"]) / dt))
    return max(js) if js else None


def canonical_events(events: list[dict]) -> str:
    return json.dumps(sorted(json.dumps(e, sort_keys=True, default=str) for e in events))


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two achieved microstate changes; two zero changes are identical, one zero change is unrelated."""
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= 1e-12 and nb <= 1e-12:
        return 1.0
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(a @ b / (na * nb))


def latent_whitening(Z: np.ndarray, eig_floor: float = 1e-8) -> dict:
    """Whitening of latent samples Z (n, k): mean, covariance eigen-decomposition (floor eig_floor x max), C^{1/2} and C^{-1/2}."""
    Z = np.atleast_2d(np.asarray(Z, float))
    mu = Z.mean(0)
    k = Z.shape[1]
    C = np.atleast_2d(np.cov((Z - mu).T)) if len(Z) > 1 else np.eye(k)
    w, V = np.linalg.eigh(C)
    order = np.argsort(w)[::-1]
    w, V = w[order], V[:, order]
    w = np.maximum(w, eig_floor * max(float(w.max()), 1e-300))
    return {"mu": mu, "evals": w, "evecs": V, "sqrt": V @ np.diag(np.sqrt(w)) @ V.T, "isqrt": V @ np.diag(1.0 / np.sqrt(w)) @ V.T, "k": k}


def encodings_for_whitening(fresh: Fresh, sid: str, trajs: list, n_times: int = 8, t_min_frac: float = 0.1) -> np.ndarray:
    """Encodings of each trajectory at n_times evenly spaced samples (from t_min_frac of its length); rows that fail are skipped."""
    Z = []
    for tr in trajs:
        x, u = np.asarray(_get(tr, "x")), np.asarray(_get(tr, "u"))
        T = len(x)
        dt = float(_dt(tr))
        for i in np.unique(np.linspace(max(1, int(t_min_frac * T)), T - 1, n_times).astype(int)):
            z, err = safe_call(fresh.encode, sid, x[: i + 1], u[: i + 1], dt)
            if err is None and z is not None and np.all(np.isfinite(z)):
                Z.append(np.asarray(z, float))
    return np.stack(Z) if Z else np.zeros((0, 0))


def requested_shifts(whit: dict, cfg: LiftConfig, rng: np.random.Generator) -> list[dict]:
    """The requests of one case: alpha x (principal directions and random unit directions of the whitened space), mapped back to
    model coordinates. k = 1: the directions +1 and -1 only (a random sign would coincide with one of them)."""
    k = int(whit["k"])
    dirs: list[tuple[str, np.ndarray]] = []
    if k == 1:
        dirs = [("pc1+", np.array([1.0])), ("pc1-", np.array([-1.0]))]
    else:
        for i in range(min(cfg.n_principal, k)):
            e = np.zeros(k)
            e[i] = 1.0
            dirs.append((f"pc{i + 1}", e))
        for r in range(cfg.n_random):
            v = rng.standard_normal(k)
            dirs.append((f"rand{r + 1}", v / np.linalg.norm(v)))
    out = []
    V, sw = whit["evecs"], np.sqrt(whit["evals"])
    for name, v in dirs:
        for a in cfg.alphas:
            # whitened coordinates in the eigenbasis: w = diag(1/sqrt(l)) V^T (z - mu); a unit step along v there is V diag(sqrt(l)) v
            dz = V @ (sw * (a * v))
            out.append({"direction": name, "alpha": float(a), "dz": dz})
    return out


def _get(rec, name):
    return rec[name] if isinstance(rec, dict) else getattr(rec, name)


def _dt(rec) -> float:
    t = np.asarray(_get(rec, "t"), float)
    if len(t) > 1:
        return float(t[1] - t[0])
    return float(_get(rec, "protocol")["dt"])


def _wnorm(whit: dict, v: np.ndarray) -> float:
    return float(np.linalg.norm(whit["isqrt"] @ np.asarray(v, float)))


def _effect_error(pred_eff: np.ndarray, true_eff: np.ndarray, floor: float) -> tuple[float, float]:
    num = float(np.sum((pred_eff - true_eff) ** 2))
    den = float(max(np.sum(true_eff ** 2), true_eff.size * floor ** 2))
    return num, den


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import spearmanr
    if len(a) < 3 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def _est(e: Estimate) -> dict:
    return e.as_dict()


# ------------------------------------------------------------------------------------------------------------ evaluation
def eval_native_lift(model, sid: str, cases: list[dict], simulate_many, *, horizon_s: float, floor: float,
                     whitening: dict | None = None, whiten_trajs: list | None = None, validator=None, constraints: dict | None = None,
                     truth: bool = False, cfg: LiftConfig = DEFAULT_LIFT) -> dict:
    """PROTOCOL 5.7 on one system. cases: [{"protocol": passive held-out protocol (no events), "t": t_c, optional "id"}].
    simulate_many(protocols, full=False) -> records; horizon_s: the primary horizon; floor: the system's effect floor f_s;
    whitening: a precomputed `latent_whitening` (else computed from `whiten_trajs` (public training data), else from the cases' own
    histories); validator(events_abs, protocol) -> None | reason (the system's capability); constraints: passed to model.lift;
    truth: request "z" / "state" from the simulator (synthetic systems)."""
    fresh = as_fresh(model)
    rng = np.random.default_rng(cfg.seed)
    res: dict = {"supported": lift_supported(fresh), "n_cases": len(cases)}
    counts = {"n_candidates": 0, "n_invalid": 0, "n_persistent": 0, "n_duplicate_events": 0, "n_too_late": 0, "n_simulated": 0,
              "n_near_identical": 0, "n_distinct": 0, "n_lift_errors": 0}
    invalid_reasons: dict[str, int] = {}
    if not cases:
        return {**res, **counts, "n_requests": 0, "reason": "no lift cases"}
    for c in cases:
        if (c["protocol"].get("events") or []):
            raise ValueError("lift cases must be PASSIVE protocols (their twins drop every event)")
    if not res["supported"]:
        # nothing is simulated for a model without lift(): every planned request fails
        k0, _ = safe_call(fresh.k, sid)
        k0 = int(k0) if k0 else (int(whitening["k"]) if whitening else 2)
        n_dirs0 = 2 if k0 == 1 else min(cfg.n_principal, k0) + cfg.n_random
        return {**res, **counts, "k": k0, "n_requests": len(cases) * n_dirs0 * len(cfg.alphas), "success_rate": 0.0,
                "success_rate_ci95": [0.0, 0.0], "lift_success_rate": 0.0,
                "reason": "lift() is not implemented (the CausalStateModel default): every request fails",
                "consistency": {"testable": False, "reason": "no lift"}}
    # pass 0: base runs (the histories)
    bases = simulate_many([dict(c["protocol"]) for c in cases], full=truth)
    if _is_reference(fresh):
        for b in bases:
            if b.get("z") is not None:
                fresh.get().register_truth(b["x"], b["u"], b["z"])
    # whitening of the model's latent space
    if whitening is None:
        Zw = encodings_for_whitening(fresh, sid, whiten_trajs if whiten_trajs else bases)
        if Zw.size == 0:
            return {**res, **counts, "supported": False, "n_requests": 0, "success_rate": 0.0,
                    "reason": "the model's encoder failed on every whitening sample"}
        whitening = latent_whitening(Zw, cfg.eig_floor)
    res["k"] = int(whitening["k"])
    # pass 1: requests and candidate lifts
    reqs, jobs = [], []
    for ci, (c, base) in enumerate(zip(cases, bases)):
        Pc = P.validate(c["protocol"])
        dt = float(Pc["dt"])
        ic = round(float(c["t"]) / dt)
        n_total = round(Pc["t_end"] / dt)
        n_h = max(1, round(horizon_s / dt))
        xh, uh = np.asarray(base["x"])[: ic + 1], np.asarray(base["u"])[: ic + 1]
        for rq in requested_shifts(whitening, cfg, rng):
            ri = len(reqs)
            r = {"case": ci, "direction": rq["direction"], "alpha": rq["alpha"], "dz": rq["dz"], "lifts": [], "t": float(c["t"]),
                 "dt": dt, "n_h": n_h}
            reqs.append(r)
            raw, err = safe_call(fresh.lift, sid, xh, uh, rq["dz"], cfg.n_lifts, constraints)
            if err is not None:
                counts["n_lift_errors"] += 1
                invalid_reasons["lift() raised"] = invalid_reasons.get("lift() raised", 0) + 1
                continue
            seen: set[str] = set()
            for cand in list(raw or [])[: cfg.n_lifts]:
                counts["n_candidates"] += 1
                reason = None
                evs = (cand or {}).get("events") if isinstance(cand, dict) else None
                if not evs:
                    reason = "no events"
                else:
                    try:
                        ev_abs = shift_events(evs, float(c["t"]))
                        Pl = P.validate(dict(Pc, events=ev_abs))
                        ev_abs = [e for e in Pl["events"]]
                    except (P.ProtocolError, KeyError, TypeError, ValueError) as exc:
                        reason = f"invalid events: {str(exc)[:80]}"
                if reason is None and any(e["kind"] not in P.EVENT_KINDS for e in ev_abs):
                    reason = "truth-only event kind"
                if reason is None and any(P.event_start(e) < float(c["t"]) - dt / 2 for e in ev_abs):
                    reason = "event before the case time"
                if reason is None and validator is not None:
                    reason = validator(ev_abs, Pl)
                if reason is None:
                    j = completion_index(ev_abs, dt)
                    if j is None:
                        counts["n_persistent"] += 1
                        reason = "persistent event (a shift must complete)"
                    elif j <= ic:
                        reason = "lift acts before the case time"
                    elif j + n_h > n_total:
                        counts["n_too_late"] += 1
                        reason = "completes too late for a full horizon window"
                if reason is not None:
                    counts["n_invalid"] += 1
                    invalid_reasons[reason.split(":")[0]] = invalid_reasons.get(reason.split(":")[0], 0) + 1
                    continue
                key = canonical_events(ev_abs)
                if key in seen:
                    counts["n_duplicate_events"] += 1
                    continue
                seen.add(key)
                twin = P.counterfactual(Pl)
                pdz = cand.get("predicted_dz")
                sd = cand.get("dz_sd")
                r["lifts"].append({"events": ev_abs, "j": j, "protocol": Pl, "twin": twin, "cost": experiment_cost(Pl),
                                   "predicted_dz": None if pdz is None else np.asarray(pdz, float),
                                   "dz_sd": None if sd is None else np.asarray(sd, float), "job": len(jobs)})
                jobs.append((ri, len(r["lifts"]) - 1))
    # pass 2: simulation (lifted runs and their twins; identical twins simulated once)
    protos, index = [], {}
    for ri, li in jobs:
        lf = reqs[ri]["lifts"][li]
        for which in ("protocol", "twin"):
            kk = P.canonical_json(lf[which])
            if kk not in index:
                index[kk] = len(protos)
                protos.append(lf[which])
            lf[which + "_idx"] = index[kk]
    sims = simulate_many(protos, full=truth) if protos else []
    counts["n_simulated"] = len(protos)
    if _is_reference(fresh):
        for s in sims:
            if s.get("z") is not None:
                fresh.get().register_truth(s["x"], s["u"], s["z"])
    # pass 3: scores
    lift_rows, pair_rows, diff_rows, spread_rows, unc_cov, unc_sd, unc_miss = [], [], [], [], [], [], []
    req_success = np.zeros(len(reqs))
    req_success2 = np.zeros(len(reqs))
    for ri, r in enumerate(reqs):
        dt, n_h = r["dt"], r["n_h"]
        recs = []
        for lf in r["lifts"]:
            sim, tw = sims[lf["protocol_idx"]], sims[lf["twin_idx"]]
            j = lf["j"]
            zl, e1 = safe_call(fresh.encode, sid, np.asarray(sim["x"])[: j + 1], np.asarray(sim["u"])[: j + 1], dt)
            zt, e2 = safe_call(fresh.encode, sid, np.asarray(tw["x"])[: j + 1], np.asarray(tw["u"])[: j + 1], dt)
            ok = e1 is None and e2 is None and np.all(np.isfinite(zl)) and np.all(np.isfinite(zt))
            if ok:
                dz_ach = np.asarray(zl, float) - np.asarray(zt, float)
                miss = _wnorm(whitening, dz_ach - r["dz"]) / max(_wnorm(whitening, r["dz"]), 1e-12)
                u_f = np.asarray(tw["u"])[j: j + n_h + 1]
                ydo, e3 = safe_call(fresh.rollout, sid, np.asarray(zt, float) + r["dz"], u_f, [], dt)
                yno, e4 = safe_call(fresh.rollout, sid, np.asarray(zt, float), u_f, [], dt)
                y_l = np.asarray(sim["y"], float)[j + 1: j + n_h + 1]
                y_t = np.asarray(tw["y"], float)[j + 1: j + n_h + 1]
                true_eff = y_l - y_t
                if e3 is None and e4 is None:
                    yd = np.asarray(ydo["y"], float)[1: n_h + 1]
                    yn = np.asarray(yno["y"], float)[1: n_h + 1]
                    num, den = _effect_error(yd - yn, true_eff, floor)
                    fc = min(num / den, FC_CAP) if np.isfinite(num) else FC_CAP
                    num_raw = float(np.sum((yd - y_l) ** 2))
                    fc_raw = min(num_raw / den, FC_CAP) if np.isfinite(num_raw) else FC_CAP
                else:
                    fc = fc_raw = FC_CAP
            else:
                dz_ach, miss, fc, fc_raw = None, float("inf"), FC_CAP, FC_CAP
            success = bool(ok and miss <= cfg.miss_max and fc <= cfg.fc_max)
            micro_key = next((kk for kk in ("state", "micro") if sim.get(kk) is not None and tw.get(kk) is not None), "x")
            dx = np.asarray(sim[micro_key], float)[j] - np.asarray(tw[micro_key], float)[j]
            distinct = all(_cos(dx, q["dx"]) <= cfg.cos_max for q in recs if q["distinct"])
            counts["n_distinct" if distinct else "n_near_identical"] += 1
            true_dz = None
            if sim.get("z") is not None and tw.get("z") is not None:
                true_dz = np.asarray(sim["z"], float)[j] - np.asarray(tw["z"], float)[j]
            rec = {"sim": sim, "twin": tw, "j": j, "dx": dx, "distinct": distinct, "dz_ach": dz_ach, "success": success, "true_dz": true_dz,
                   "zt": np.asarray(zt, float) if ok else None}
            recs.append(rec)
            lift_rows.append({"req": ri, "miss": float(min(miss, FC_CAP)), "fc": float(fc), "fc_raw": float(fc_raw), "success": success,
                              "cost": float(lf["cost"]["magnitude_total"]), "n_targets": len(lf["cost"]["targets"]),
                              "kinds": sorted({e["kind"] for e in lf["events"]}), "distinct": distinct})
            if ok and lf["dz_sd"] is not None and lf["predicted_dz"] is not None and len(lf["dz_sd"]) == len(dz_ach):
                inside = np.abs(dz_ach - lf["predicted_dz"]) <= Z90 * np.maximum(lf["dz_sd"], 0.0)
                unc_cov.append(float(np.mean(inside)))
                unc_sd.append(_wnorm(whitening, lf["dz_sd"]))
                unc_miss.append(float(miss))
        succ = [q for q in recs if q["success"]]
        req_success[ri] = 1.0 if succ else 0.0
        req_success2[ri] = 1.0 if sum(1 for q in succ if q["distinct"]) >= 2 else 0.0
        r["recs"] = [q for q in recs if q["distinct"]]
        dist = r["recs"]
        if len(dist) >= 2:
            J = max(q["j"] for q in dist)
            fut = []
            for q in dist:
                y_l = np.asarray(q["sim"]["y"], float)[J + 1: J + n_h + 1]
                y_t = np.asarray(q["twin"]["y"], float)[J + 1: J + n_h + 1]
                fut.append((y_l, float(np.sqrt(np.mean((y_l - y_t) ** 2)))))
            eff = max(float(np.mean([f[1] for f in fut])), floor)

            def pred_window(q, J=J, n_h=n_h, dt=dt, fut=fut):
                """The model's predicted effect of this lift's ACHIEVED shift over the common window (rollouts from the twin's
                encoding at the lift's own completion sample)."""
                if q["dz_ach"] is None or q["zt"] is None:
                    return None
                off = J - q["j"]
                u_f = np.asarray(q["twin"]["u"], float)[q["j"]: J + n_h + 1]
                r1, e1 = safe_call(fresh.rollout, sid, q["zt"] + q["dz_ach"], u_f, [], dt)
                r0, e0 = safe_call(fresh.rollout, sid, q["zt"], u_f, [], dt)
                if e1 is not None or e0 is not None:
                    return None
                pe = (np.asarray(r1["y"], float) - np.asarray(r0["y"], float))[off + 1: off + n_h + 1]
                return pe if pe.shape == fut[0][0].shape and np.all(np.isfinite(pe)) else None

            pes = [pred_window(q) for q in dist]
            for a in range(len(dist)):
                for b in range(a + 1, len(dist)):
                    div = float(np.sqrt(np.mean((fut[a][0] - fut[b][0]) ** 2)))
                    dshift = (_wnorm(whitening, dist[a]["dz_ach"] - dist[b]["dz_ach"])
                              if dist[a]["dz_ach"] is not None and dist[b]["dz_ach"] is not None else float("nan"))
                    resid = float("nan")
                    if pes[a] is not None and pes[b] is not None:
                        resid = float(np.sqrt(np.mean(((fut[a][0] - fut[b][0]) - (pes[a] - pes[b])) ** 2))) / eff
                    pair_rows.append({"req": ri, "ratio": div / eff, "dshift": dshift, "resid": resid})
            tds = [q["true_dz"] for q in dist if q["true_dz"] is not None]
            if len(tds) >= 2:
                pd = [np.linalg.norm(tds[a] - tds[b]) for a in range(len(tds)) for b in range(a + 1, len(tds))]
                spread_rows.append({"req": ri, "spread": float(np.mean(pd) / (np.mean([np.linalg.norm(v) for v in tds]) + 1e-12))})
    # different-request divergence within a case (the invariance null)
    by_case: dict[int, list[int]] = {}
    for ri, r in enumerate(reqs):
        by_case.setdefault(r["case"], []).append(ri)
    for ci, ris in by_case.items():
        for a_i in range(len(ris)):
            for b_i in range(a_i + 1, len(ris)):
                ra, rb = reqs[ris[a_i]], reqs[ris[b_i]]
                if not ra.get("recs") or not rb.get("recs"):
                    continue
                J = max(q["j"] for q in ra["recs"] + rb["recs"])
                n_h = ra["n_h"]
                for qa in ra["recs"]:
                    for qb in rb["recs"]:
                        ya = np.asarray(qa["sim"]["y"], float)[J + 1: J + n_h + 1]
                        yb = np.asarray(qb["sim"]["y"], float)[J + 1: J + n_h + 1]
                        ea = np.asarray(qa["twin"]["y"], float)[J + 1: J + n_h + 1]
                        eb = np.asarray(qb["twin"]["y"], float)[J + 1: J + n_h + 1]
                        eff = max(0.5 * (np.sqrt(np.mean((ya - ea) ** 2)) + np.sqrt(np.mean((yb - eb) ** 2))), floor)
                        diff_rows.append({"case": ci, "ratio": float(np.sqrt(np.mean((ya - yb) ** 2)) / eff)})
    # aggregates
    res.update(counts)
    res["n_requests"] = len(reqs)
    res["invalid_reasons"] = invalid_reasons
    res["rollout_isolation"] = "trusted-reference" if fresh.trusted else "fresh-copy"
    sr = boot_mean(req_success, groups=[r["case"] for r in reqs], n_boot=cfg.n_boot, seed=cfg.seed) if len(reqs) else None
    res["success_rate"] = float(req_success.mean()) if len(reqs) else 0.0
    res["success_rate_ci95"] = sr.ci95 if sr is not None else [0.0, 0.0]
    res["success_rate_two_distinct"] = float(req_success2.mean()) if len(reqs) else 0.0
    res["_units"] = {"request_success": {f"{reqs[i]['case']}:{reqs[i]['direction']}:{reqs[i]['alpha']}": float(req_success[i])
                                         for i in range(len(reqs))}}
    if lift_rows:
        g = [row["req"] for row in lift_rows]
        res["lift_success_rate"] = float(np.mean([row["success"] for row in lift_rows]))
        res["miss"] = _est(boot_mean([row["miss"] for row in lift_rows], g, cfg.n_boot, cfg.seed))
        res["future_consistency"] = _est(boot_mean([row["fc"] for row in lift_rows], g, cfg.n_boot, cfg.seed))
        res["future_consistency_raw"] = _est(boot_mean([row["fc_raw"] for row in lift_rows], g, cfg.n_boot, cfg.seed))
        res["cost_mean"] = float(np.mean([row["cost"] for row in lift_rows]))
        res["n_targets_mean"] = float(np.mean([row["n_targets"] for row in lift_rows]))
        kinds: dict[str, int] = {}
        for row in lift_rows:
            for kd in row["kinds"]:
                kinds[kd] = kinds.get(kd, 0) + 1
        res["lift_kinds"] = kinds
    else:
        res["lift_success_rate"] = 0.0
        res["reason"] = "no candidate lift could be simulated"
    # multiple-lift consistency
    if pair_rows:
        ratios = np.array([p["ratio"] for p in pair_rows], float)
        g = [p["req"] for p in pair_rows]
        cons = {"testable": True, "n_pairs": len(pair_rows), "n_requests": len(set(g)),
                "raw": _est(boot_mean(np.minimum(ratios, FC_CAP), g, cfg.n_boot, cfg.seed))}
        res_ = np.array([p["resid"] for p in pair_rows], float)
        okr = np.isfinite(res_)
        if okr.any():
            # ADJUSTED (primary): the part of the future divergence NOT explained by the pair's different achieved shifts under the
            # model's own dynamics (0 when two lifts that realised the same latent shift have the same future)
            cons["adjusted"] = _est(boot_mean(np.minimum(res_[okr], FC_CAP), np.array(g)[okr], cfg.n_boot, cfg.seed))
        else:
            cons["adjusted"] = {"point": float("nan"), "ci95": [float("nan")] * 2, "n_units": 0,
                                "note": "no pair with encodable achieved shifts and model rollouts"}
        ds = np.array([p["dshift"] for p in pair_rows], float)
        okd = np.isfinite(ds)
        if okd.sum() >= 3:
            rows = np.column_stack([np.minimum(ratios[okd], FC_CAP), ds[okd]])

            def adj(rw: np.ndarray, w: np.ndarray) -> float:
                if w.sum() <= 0:
                    return float("nan")
                x, yv = rw[:, 1], rw[:, 0]
                mx, my = np.average(x, weights=w), np.average(yv, weights=w)
                vx = np.average((x - mx) ** 2, weights=w)
                slope = max(0.0, np.average((x - mx) * (yv - my), weights=w) / vx) if vx > 1e-12 else 0.0
                return float(max(0.0, my - slope * mx))

            gg = np.array(g)[okd]
            e = boot_stat(rows, adj, groups=gg, n_boot=cfg.n_boot, seed=cfg.seed)
            cons["adjusted_pooled_regression"] = {**_est(e), "note": "intercept of the pooled pair ratio vs achieved-shift distance "
                                                  "(slope >= 0); confounded by request magnitude, secondary"}
        else:
            cons["adjusted_pooled_regression"] = {"point": float("nan"), "ci95": [float("nan")] * 2, "n_units": int(okd.sum()),
                                                  "note": "fewer than 3 pairs with achieved shifts"}
        if diff_rows:
            same, diff = float(np.mean(np.minimum(ratios, FC_CAP))), float(np.mean([d["ratio"] for d in diff_rows]))
            cons["invariance_ratio"] = {"testable": True, "ratio": same / max(diff, 1e-12), "same_request": same, "different_request": diff,
                                        "n_different_pairs": len(diff_rows)}
        else:
            cons["invariance_ratio"] = {"testable": False, "reason": "no case with distinct lifts of two requests"}
        res["consistency"] = cons
    else:
        res["consistency"] = {"testable": False, "reason": "no request with two distinct simulated lifts (untestable, never a perfect score)"}
    if spread_rows:
        res["true_shift_spread"] = _est(boot_mean([s["spread"] for s in spread_rows], [s["req"] for s in spread_rows], cfg.n_boot, cfg.seed))
    if unc_cov:
        res["uncertainty"] = {"n": len(unc_cov), "coverage90": float(np.mean(unc_cov)),
                              "rank_corr_sd_miss": _spearman(np.array(unc_sd), np.array(unc_miss))}
    else:
        res["uncertainty"] = {"n": 0, "note": "no lift reported dz_sd"}
    return res
