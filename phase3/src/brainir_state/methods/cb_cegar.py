"""cb_cegar: counterexample-guided abstraction refinement and abstention wrapper (family E, method 3).

Wraps any registered state method (default: cb_psr, the fast closed-form base; config "base", e.g. cb_interchange) and treats held-out data and, when available, the budgeted
simulator as an EQUIVALENCE ORACLE for the fitted abstraction (phi, f, g).

Loop (round r, current dimension k):
  1. fit the base at k (round 0: the base's own dimension rule) on the fitting set F (train split + accepted probe data);
  2. search counterexamples on the ORACLE set O (validation trajectories never used for fitting parameters; fresh simulated probes use
     a seed stream disjoint from any training seed):
     T1 closure / microstate equivalence: sample states x_t of O; e_t = the model's multi-step readout residual from phi(x_t) (with
        the recorded input); r_t = the discarded microstate (top PCs of x_t minus their cross-fitted prediction from z_t). A
        counterexample is a pair of states with (nearly) equal z whose futures differ in a way r predicts; in aggregate: r_t
        predicts e_t beyond z_t. Statistic: cross-fitted (two folds by trajectory) fractional error reduction of e_t when r_t is
        added to (z_t, u_t) (ridge); VALIDATION by a permutation test (r permuted across trajectories, 200 permutations,
        p < alpha) and an effect-size floor (gain > eps). Random search (uniform states) and adversarial search (the direction v of
        r that best predicts e: the top singular direction of the ridge map, i.e. the counterexample pair direction x' = x + v).
     T2 history (Markov): the same with z at two lags instead of r.
     T3 interventions: on O's event trajectories (and on simulated kick / twin probe pairs when sim is given: random targets plus
        adversarial targets = the public units the model says matter most and least, amplitudes from the training kicks), the
        predicted event effect must beat "no effect": paired bootstrap over events of err(with events) - err(without events)
        [data], or the effect-error ratio sum ||d_pred - d_true||^2 / sum ||d_true||^2 [probes with twins]; validated if the CI
        lies above 0 (resp. above 1).
  3. refine: T1 or T2 validated -> k <- k + 1 (the new coordinate initialised on the counterexample direction v for linear-encoder
     bases: W <- orth([W; v])); T3 validated with probes -> add the probe trajectories (realisers of latent shifts, with twins) to F
     and refit. A refinement is ACCEPTED only if the oracle loss improves (otherwise the counterexample cannot be separated in the
     model class: stop). Symmetric MERGE: at the end, k - 1 replaces k if it passes T1 / T2 and its oracle loss is within the
     tolerance.
  4. stop when a round finds no validated counterexample, the probe budget is spent, or k reaches k_max = max(1, floor(N / 5)).
  5. abstain: T1 / T2 still validated at k_max (no plateau of k(eps)) -> "no compact state", dimension unresolved in [k_0, k_max];
     T3 still validated after refinement -> "causal equivalence failed" (observational state only).

The returned model is the base's StateModel (the last accepted refinement) with the counterexample log and the abstention decision in
info(); lift() / supports() are the base's.
"""

from __future__ import annotations

import copy
import dataclasses

import numpy as np

from ..api import StateMethod, StateModel, get_method, register
from ..data import Trajectory
from . import cb_core as C
from . import cb_psr as P


# ================================================================================================================ oracle tests
def _shift_events(events, t0, tmax):
    out = []
    for e in events:
        e2 = dict(e)
        if "t" in e2:
            if not (t0 - 1e-9 <= e2["t"] <= t0 + tmax):
                continue
            e2["t"] = round(e2["t"] - t0, 9)
        else:
            if e2.get("t1") is not None and e2["t1"] <= t0:
                continue
            if e2["t0"] > t0 + tmax:
                continue
            e2["t0"] = round(max(0.0, e2["t0"] - t0), 9)
            if e2.get("t1") is not None:
                e2["t1"] = round(e2["t1"] - t0, 9)
        out.append(e2)
    return out


def state_samples(model: StateModel, sid: str, trajs: list[Trajectory], horizon_s: float, lags_s: tuple, n_per: int, rng,
                  yscale: np.ndarray):
    """Rows (traj, z_t, z_{t-lag1}, z_{t-lag2}, u_t, x_t, e_t) at random event-free times of the oracle trajectories; e_t = the model's
    readout residual at 4 horizons up to horizon_s (normalised)."""
    rows = []
    for ti, tr in enumerate(trajs):
        dt = tr.dt
        n = int(round(horizon_s / dt))
        l1, l2 = (int(round(v / dt)) for v in lags_s)
        ev_t = [e.get("t", e.get("t0")) for e in tr.events()]
        lo, hi = max(l2, len(tr.t) // 8), len(tr.t) - n - 1
        if hi <= lo:
            continue
        hs = np.unique(np.round(np.linspace(n / 4, n, 4)).astype(int))
        for i in np.sort(rng.integers(lo, hi, n_per)):
            t0 = tr.t[i]
            if any(t0 - 1e-9 <= te <= t0 + horizon_s for te in ev_t):
                continue
            z = np.asarray(model.encode(sid, tr.x[: i + 1], tr.u[: i + 1], dt), float)
            zl1 = np.asarray(model.encode(sid, tr.x[: i - l1 + 1], tr.u[: i - l1 + 1], dt), float)
            zl2 = np.asarray(model.encode(sid, tr.x[: i - l2 + 1], tr.u[: i - l2 + 1], dt), float)
            yp = np.asarray(model.rollout(sid, z, tr.u[i: i + n + 1], [], dt)["y"], float)
            e = ((tr.y[i + hs] - yp[hs]) / np.sqrt(yscale)).ravel()
            rows.append({"traj": ti, "z": z, "zl": np.r_[zl1, zl2], "u": tr.u[i].astype(float), "x": tr.x[i].astype(float), "e": e})
    return rows


def _ridge_cv(Xa, Y, groups, lam_grid=(1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)):
    """Two-fold (by group) cross-fitted ridge predictions with the penalty chosen on the other fold; returns predictions."""
    u = np.unique(groups)
    fold = np.isin(groups, u[::2])
    pred = np.zeros_like(Y)
    for tr_m in (fold, ~fold):
        if tr_m.sum() < 5 or (~tr_m).sum() < 5:
            return None
        Xtr, Ytr = Xa[tr_m], Y[tr_m]
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        A = (Xtr - mu) / sd
        B = (Xa[~tr_m] - mu) / sd
        ym = Ytr.mean(0)
        best, be = None, np.inf
        n = len(A)
        idx = np.arange(n)
        half = idx % 2 == 0
        for lam in lam_grid:
            W = np.linalg.solve(A[half].T @ A[half] + lam * half.sum() * np.eye(A.shape[1]), A[half].T @ (Ytr[half] - ym))
            err = float(np.mean((A[~half] @ W + ym - Ytr[~half]) ** 2))
            if err < be:
                best, be = lam, err
        W = np.linalg.solve(A.T @ A + best * n * np.eye(A.shape[1]), A.T @ (Ytr - ym))
        pred[~tr_m] = B @ W + ym
    return pred


def closure_test(rows, pca_mean, pca_comps, which: str, n_perm: int, rng, alpha: float, eps: float) -> dict:
    """T1 (which='micro') / T2 (which='history'): does the discarded microstate (resp. latent history) predict the model's future
    residual beyond (z, u)? Cross-fitted gain + permutation test across trajectories. Also returns the adversarial direction."""
    if len(rows) < 30:
        return {"n": len(rows), "validated": False, "note": "too few states"}
    g = np.array([r["traj"] for r in rows])
    Z = np.stack([r["z"] for r in rows]); U = np.stack([r["u"] for r in rows]); E = np.stack([r["e"] for r in rows])
    X = np.stack([r["x"] for r in rows])
    base = np.hstack([Z, U])
    if which == "micro":
        PC = (X - pca_mean) @ pca_comps[:5].T
        pr = _ridge_cv(base, PC, g)
        if pr is None:
            return {"n": len(rows), "validated": False, "note": "folds too small"}
        R = (PC - pr) / (PC.std(0) + 1e-9)
    else:
        R = np.stack([r["zl"] for r in rows])
    p0 = _ridge_cv(base, E, g)
    p1 = _ridge_cv(np.hstack([base, R]), E, g)
    if p0 is None or p1 is None:
        return {"n": len(rows), "validated": False, "note": "folds too small"}
    e0 = float(np.mean((E - p0) ** 2))
    e1 = float(np.mean((E - p1) ** 2))
    gain = (e0 - e1) / max(e0, 1e-12)
    # permutation null: residual rows shuffled across trajectories (breaks the state-residual link, keeps marginals)
    null = []
    for _ in range(n_perm):
        perm = rng.permutation(len(R))
        pp = _ridge_cv(np.hstack([base, R[perm]]), E, g)
        null.append((e0 - float(np.mean((E - pp) ** 2))) / max(e0, 1e-12))
    null = np.array(null)
    pval = float((1 + (null >= gain).sum()) / (1 + len(null)))
    # adversarial counterexample direction: top right-singular vector of the ridge map residual -> model error
    v = None
    if which == "micro":
        Rs = R - R.mean(0)
        Es = E - p0
        Wm = np.linalg.lstsq(np.hstack([Rs, np.ones((len(Rs), 1))]), Es, rcond=None)[0][:-1]
        uu, ss, _ = np.linalg.svd(Wm, full_matrices=False)
        v_pc = uu[:, 0] * (PC.std(0) + 1e-9)            # in PC coordinates
        v = v_pc @ pca_comps[:5]                         # microstate direction (standardised later by the caller)
    return {"n": len(rows), "gain": gain, "p": pval, "null95": float(np.quantile(null, 0.95)),
            "validated": bool(pval < alpha and gain > eps), "direction": v}


def event_test(model: StateModel, sid: str, trajs, horizon_s: float, yscale, rng, n_boot: int = 1000) -> dict:
    """T3 on recorded event trajectories (no twins): paired error of the model's rollout WITH the events vs WITHOUT them over the
    window after the first event. Validated counterexample: the CI of (with - without) lies above 0 (the modelled effect hurts)."""
    d = []
    for tr in trajs:
        evs = tr.events()
        if not evs:
            continue
        kinds = {e["kind"] for e in evs}
        if not all(model.supports(sid, kk) for kk in kinds):
            continue
        dt = tr.dt
        t_ev = min(e.get("t", e.get("t0")) for e in evs)
        i = int(round(t_ev / dt))
        n = int(round(horizon_s / dt))
        if i + n >= len(tr.t) or i < 1:
            continue
        z = np.asarray(model.encode(sid, tr.x[: i + 1], tr.u[: i + 1], dt), float)
        ev = _shift_events(evs, tr.t[i], horizon_s)
        yw = np.asarray(model.rollout(sid, z, tr.u[i: i + n + 1], ev, dt)["y"], float)[1:]
        yo = np.asarray(model.rollout(sid, z, tr.u[i: i + n + 1], [], dt)["y"], float)[1:]
        yt = tr.y[i + 1: i + n + 1]
        d.append(float(np.mean((yw - yt) ** 2 / yscale) - np.mean((yo - yt) ** 2 / yscale)))
    if len(d) < 3:
        return {"n": len(d), "validated": False}
    d = np.array(d)
    b = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    lo, hi = float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
    return {"n": len(d), "mean": float(d.mean()), "ci95": [lo, hi], "validated": bool(lo > 0)}


def probe_effect_test(model: StateModel, sid: str, pairs, horizon_s: float, yscale, rng, n_boot: int = 1000) -> dict:
    """T3 with simulated (probe, twin) pairs: effect-error ratio sum ||d_pred - d_true||^2 / sum ||d_true||^2 (1 = no effect)."""
    num, den = [], []
    for tr, tw in pairs:
        evs = tr.events()
        dt = tr.dt
        t_ev = min(e.get("t", e.get("t0")) for e in evs)
        i = int(round(t_ev / dt))
        n = int(round(horizon_s / dt))
        if i + n >= len(tr.t):
            continue
        z = np.asarray(model.encode(sid, tr.x[: i + 1], tr.u[: i + 1], dt), float)
        ev = _shift_events(evs, tr.t[i], horizon_s)
        yw = np.asarray(model.rollout(sid, z, tr.u[i: i + n + 1], ev, dt)["y"], float)[1:]
        yo = np.asarray(model.rollout(sid, z, tr.u[i: i + n + 1], [], dt)["y"], float)[1:]
        dp = (yw - yo) / np.sqrt(yscale)
        dtr = (tr.y[i + 1: i + n + 1] - tw.y[i + 1: i + n + 1]) / np.sqrt(yscale)
        num.append(float(((dp - dtr) ** 2).sum()))
        den.append(float((dtr ** 2).sum()))
    if len(num) < 3 or sum(den) <= 0:
        return {"n": len(num), "validated": False}
    num, den = np.array(num), np.array(den)
    b = []
    for _ in range(n_boot):
        s = rng.integers(0, len(num), len(num))
        if den[s].sum() > 0:
            b.append(num[s].sum() / den[s].sum())
    lo, hi = float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
    return {"n": len(num), "ratio": float(num.sum() / den.sum()), "ci95": [lo, hi], "validated": bool(lo > 1.0)}


def oracle_loss(model: StateModel, sid: str, trajs, horizon_s: float, yscale, n_starts: int = 4) -> float:
    """Mean multi-step readout NMSE on the oracle trajectories (events applied)."""
    errs = []
    for tr in trajs:
        dt = tr.dt
        n = int(round(horizon_s / dt))
        if len(tr.t) <= n + 2:
            continue
        for i in np.linspace(len(tr.t) // 8, len(tr.t) - n - 1, n_starts).astype(int):
            z = np.asarray(model.encode(sid, tr.x[: i + 1], tr.u[: i + 1], dt), float)
            ev = _shift_events(tr.events(), tr.t[i], horizon_s)
            if not all(model.supports(sid, e["kind"]) for e in ev):
                ev = []
            yp = np.asarray(model.rollout(sid, z, tr.u[i: i + n + 1], ev, dt)["y"], float)[1:]
            errs.append(float(np.mean((yp - tr.y[i + 1: i + n + 1]) ** 2 / yscale)))
    return float(np.mean(errs)) if errs else float("nan")


# ================================================================================================================ simulator probes
def _to_traj(rec: dict, proto: dict, sid: str, key: str, family: str) -> Trajectory:
    return Trajectory(key=key, system_id=sid, split="train", family=family, protocol=proto, t=np.asarray(rec["t"], float),
                      x=np.asarray(rec["x"], np.float32), u=np.asarray(rec["u"], np.float32), y=np.asarray(rec["y"], np.float32))


def design_kick_probes(model: StateModel, sid: str, system: dict, train, n_pairs: int, rng, round_i: int) -> list[tuple[dict, dict]]:
    """(kick protocol, twin protocol) pairs within the public policy: rest start, a training parameter draw, the nominal stimulus
    schedule of a training trajectory, ONE single-unit kick on a public target, shared noise seed. Targets: half random, half
    adversarial (the public units with the largest and the smallest encoder weight, for linear-encoder bases)."""
    tg = [int(n) for n in system.get("targets_public") or []]
    if not tg:
        return []
    noms = [tr for tr in train if not tr.events() and (tr.protocol.get("r0") or {}).get("kind", "zero") == "zero"]
    if not noms:
        return []
    kicks = [abs(float(v)) for tr in train for e in tr.events() if e["kind"] == "kick" for v in e["delta"].values()]
    amp = float(np.median(kicks)) if kicks else 1.0
    W = model.unit_maps(sid)[0] if hasattr(model, "unit_maps") and sid in getattr(model, "sys", {}) else None
    col = {int(n): i for i, n in enumerate(system["observed"])}
    ranked = tg
    if W is not None:
        wn = np.array([np.linalg.norm(W[:, col[n]]) if n in col else 0.0 for n in tg])
        ranked = [tg[i] for i in np.argsort(-wn)]
    out = []
    seeds = [int(tr.protocol.get("params_seed", 0)) for tr in noms]
    for j in range(n_pairs):
        base = copy.deepcopy(noms[int(rng.integers(0, len(noms)))].protocol)
        base["params_seed"] = int(seeds[int(rng.integers(0, len(seeds)))])
        base["r0"] = {"kind": "zero"}
        base["weight_noise"] = None
        base["events"] = []
        # a disjoint seed stream for the oracle (never a training seed)
        base["noise_seed"] = int(7_000_000 + 1000 * round_i + j)
        if j % 3 == 0 or W is None:
            n = tg[int(rng.integers(0, len(tg)))]
        elif j % 3 == 1:
            n = ranked[int(rng.integers(0, max(1, len(ranked) // 4)))]
        else:
            n = ranked[-1 - int(rng.integers(0, max(1, len(ranked) // 4)))]
        T = float(base.get("t_end", 4.0))
        t = round(float(rng.uniform(0.3 * T, 0.6 * T)), 3)
        sgn = 1.0 if rng.uniform() < 0.5 else -1.0
        kick = dict(base, events=[{"kind": "kick", "t": t, "delta": {str(n): sgn * amp}}])
        out.append((kick, base))
    return out


def run_probes(sim, sid: str, designs, round_i: int):
    """Simulate designs; returns [(kicked Trajectory, twin Trajectory)], number of trajectories charged."""
    protos = [p for pair in designs for p in pair]
    if not protos:
        return [], 0
    try:
        res = sim.run(protos)
    except Exception:
        return [], 0
    pairs = []
    for j in range(0, len(res) - 1, 2):
        a, b = res[j], res[j + 1]
        if a.get("ok") and b.get("ok") and np.all(np.isfinite(a["x"])) and np.all(np.isfinite(b["x"])):
            ka = f"cegar{round_i}_{j}"
            pairs.append((_to_traj(a, protos[j], sid, ka, "cegar_kick"), _to_traj(b, protos[j + 1], sid, ka + "t", "cegar_twin")))
    return pairs, len(protos)


# ================================================================================================================ wrapper model
class CegarModel(StateModel):
    """The base model plus the counterexample log / abstention decision (delegates everything else)."""

    def __init__(self, base: StateModel, meta: dict):
        self.base = base
        self.meta = meta
        self.k = dict(getattr(base, "k", {}))

    def encode(self, system_id, x_hist, u_hist, dt):
        return self.base.encode(system_id, x_hist, u_hist, dt)

    def rollout(self, system_id, z0, u_future, events, dt):
        return self.base.rollout(system_id, z0, u_future, events, dt)

    def readout(self, system_id, z, u):
        return self.base.readout(system_id, z, u)

    def supports(self, system_id, event_kind):
        return self.base.supports(system_id, event_kind)

    def lift(self, system_id, x, z, delta_z, n_candidates=3):
        return self.base.lift(system_id, x, z, delta_z, n_candidates)

    def info(self):
        inf = dict(self.base.info())
        inf.update(self.meta)
        return inf


DEFAULTS = {"base": "cb_psr", "max_rounds": 4, "alpha": 0.01, "eps": 0.05, "n_perm": 199, "probe_pairs": 16,
            "sim_budget": 200, "n_states": 40, "loss_tol": 0.05}


def _yscale(train):
    Y = np.concatenate([t.y for t in train]).astype(np.float64)
    v = Y.var(0)
    return np.maximum(v, max(1e-12, 1e-3 * float(v.max())))


@register
class CBCegar(StateMethod):
    name = "cb_cegar"
    version = "1"
    default_config = dict(DEFAULTS)
    supported_sharing = ("auto", "independent")
    supports_adaptation = False

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        cfg = dict(DEFAULTS)
        cfg.update({k_: v for k_, v in (config or {}).items() if k_ in DEFAULTS})
        config = dict(config or {})
        if config.get("sharing") not in (None, "auto", "independent"):
            raise NotImplementedError("cb_cegar supports sharing='independent' only")
        if config.get("adapt_from") is not None:
            raise NotImplementedError("cb_cegar does not support encoder-only adaptation")
        if len({t.system_id for t in train}) != 1:
            raise NotImplementedError("cb_cegar fits one system at a time")
        t0 = C.now()
        sid = train[0].system_id
        system = systems[sid]
        rng = np.random.default_rng(seed + 5)
        base_m = get_method(cfg["base"])
        base_cfg = {k_: v for k_, v in config.items() if k_ not in DEFAULTS and k_ not in ("k",)}
        fit_set, oracle = P.split_train_val(train, seed)
        # inside the loop the base never sees the oracle: its own validation split is carved out of the fitting set
        fit_set = [dataclasses.replace(t, split="train") for t in fit_set]
        n_inner = max(1, len(fit_set) // 5)
        inner = set(np.random.default_rng(seed + 17).permutation(len(fit_set))[:n_inner].tolist())
        fit_set = [dataclasses.replace(t, split="val") if i in inner else t for i, t in enumerate(fit_set)]
        yscale = _yscale(fit_set)
        N = len(system["observed"])
        k_max = max(1, int(N // 5)) if system.get("mode") != "mech" else N
        T_s = float(np.median([t.t[-1] for t in train]))
        horizon = T_s / 8.0                                   # oracle horizon: 1/8 of a trajectory (generic)
        lags = (horizon / 20.0, horizon / 10.0)
        pca_x = np.concatenate([t.x for t in fit_set]).astype(np.float64)
        pca_mean = pca_x.mean(0)
        _, _, Vt = np.linalg.svd(pca_x[:: max(1, len(pca_x) // 20000)] - pca_mean, full_matrices=False)
        pca_comps = Vt[: min(10, Vt.shape[0])]
        log, probes, sim_used = [], [], 0

        def fit_base(k=None, extra=(), W_init=None, final=False):
            c = dict(base_cfg)
            if k is not None:
                c["k"] = int(k)
            if W_init is not None:
                c["W_init"] = W_init
            data = list(fit_set) + list(extra)
            if final:          # the final refit uses every trajectory (the oracle as the base's validation split)
                data = [dataclasses.replace(t, split="train") for t in fit_set] + list(extra) + list(oracle)
            return base_m.fit(data, systems={sid: system}, config=c, sim=None, seed=seed)

        forced_k = config.get("k")
        model = fit_base(forced_k)
        k0 = int(model.info()["k"][sid])
        abst0 = dict((model.info().get("abstain") or {}).get(sid, {}))     # the base's own (unforced) decision
        changed = False
        k = k0
        cur_loss = oracle_loss(model, sid, oracle, horizon, yscale)
        extra: list = []
        abst_closure = False
        abst_causal = False
        for rnd in range(cfg["max_rounds"]):
            rows = state_samples(model, sid, oracle, horizon, lags, cfg["n_states"], rng, yscale)
            t1 = closure_test(rows, pca_mean, pca_comps, "micro", cfg["n_perm"], rng, cfg["alpha"], cfg["eps"])
            t2 = closure_test(rows, pca_mean, pca_comps, "history", cfg["n_perm"], rng, cfg["alpha"], cfg["eps"])
            t3 = event_test(model, sid, oracle, horizon, yscale, rng)
            t3p = {"validated": False}
            if sim is not None and sim_used + 2 * cfg["probe_pairs"] <= cfg["sim_budget"]:
                designs = design_kick_probes(model, sid, system, fit_set, cfg["probe_pairs"], rng, rnd)
                new, used = run_probes(sim, sid, designs, rnd)
                sim_used += used
                if new:
                    probes += new
                    t3p = probe_effect_test(model, sid, new, horizon, yscale, rng)
            entry = {"round": rnd, "k": k, "oracle_loss": cur_loss,
                     "T1_closure": {kk: v for kk, v in t1.items() if kk != "direction"},
                     "T2_history": t2, "T3_events": t3, "T3_probes": t3p, "sim_used": sim_used}
            log.append(entry)
            closure_cex = t1.get("validated") or t2.get("validated")
            causal_cex = t3.get("validated") or t3p.get("validated")
            if not closure_cex and not causal_cex:
                entry["action"] = "no validated counterexample: stop"
                break
            if forced_k is not None:
                entry["action"] = "k forced: report only"
                abst_closure = bool(closure_cex)
                abst_causal = bool(causal_cex)
                break
            accepted = False
            if closure_cex and k + 1 <= k_max:
                W_init = None
                Wb = getattr(model, "sys", {}).get(sid, {}).get("W") if hasattr(model, "sys") else None
                if Wb is not None and t1.get("direction") is not None and Wb.shape[1] == len(t1["direction"]):
                    prep = model.sys[sid]["prep"]
                    v = (t1["direction"]) / prep.s
                    v = v - Wb.T @ (Wb @ v)
                    if np.linalg.norm(v) > 1e-9:
                        W_init = np.vstack([Wb, v / np.linalg.norm(v)])
                cand = fit_base(k + 1, extra, W_init)
                cl = oracle_loss(cand, sid, oracle, horizon, yscale)
                entry["refine_k"] = {"k_new": k + 1, "oracle_loss": cl}
                if cl < cur_loss * (1 - cfg["loss_tol"]):
                    model, k, cur_loss, accepted = cand, k + 1, cl, True
            if causal_cex and probes and not accepted:
                extra = [t for pr in probes for t in pr]
                cand = fit_base(k, extra)
                cl = oracle_loss(cand, sid, oracle, horizon, yscale)
                t3n = probe_effect_test(cand, sid, probes, horizon, yscale, rng)
                entry["refine_data"] = {"n_probe_traj": len(extra), "oracle_loss": cl, "T3_probes_after": t3n}
                if cl <= cur_loss * (1 + cfg["loss_tol"]) and not t3n.get("validated"):
                    model, cur_loss, accepted = cand, cl, True
            entry["action"] = "refined" if accepted else "counterexample not separable in the model class"
            changed = changed or accepted
            if not accepted:
                abst_closure = bool(closure_cex)
                abst_causal = bool(causal_cex)
                break
            if k >= k_max and closure_cex:
                abst_closure = True
        # symmetric merge: a smaller k that passes the closure tests with an oracle loss within tolerance replaces k
        if forced_k is None and k > 1 and not abst_closure:
            cand = fit_base(k - 1, extra)
            cl = oracle_loss(cand, sid, oracle, horizon, yscale)
            rows = state_samples(cand, sid, oracle, horizon, lags, cfg["n_states"], rng, yscale)
            t1 = closure_test(rows, pca_mean, pca_comps, "micro", cfg["n_perm"], rng, cfg["alpha"], cfg["eps"])
            merge = {"k_new": k - 1, "oracle_loss": cl, "T1": {kk: v for kk, v in t1.items() if kk != "direction"}}
            if cl <= cur_loss * (1 + cfg["loss_tol"]) and not t1.get("validated"):
                model, k, cur_loss = cand, k - 1, cl
                merge["accepted"] = True
                changed = True
            log.append({"merge": merge})
        # final refit on all data: without an accepted refinement / merge the base with its OWN rule (cegar then only certifies it);
        # otherwise the base at the refined k
        if changed or forced_k is not None:
            model = fit_base(k, extra, None, final=True)
        else:
            model = fit_base(None, extra, None, final=True)
            k = int(model.info()["k"][sid])
        binfo = model.info()
        babst = dict((binfo.get("abstain") or {}).get(sid, {}))
        if forced_k is None:
            fin = (binfo.get("abstain") or {}).get(sid, {})
            babst["no_compact_state"] = bool(abst0.get("no_compact_state") or (not changed and fin.get("no_compact_state")))
            babst["reason"] = "; ".join(r for r in (abst0.get("reason"), fin.get("reason")) if r)
        no_compact = bool(babst.get("no_compact_state")) or (abst_closure and k >= k_max) or             (k > max(1, N / 5) and system.get("mode") != "mech")
        reason = [babst.get("reason", "")] if babst.get("reason") else []
        if abst_closure:
            reason.append(f"closure counterexamples persist at k={k} (k_max={k_max})")
        if abst_causal:
            reason.append("intervention counterexamples persist after refinement")
        abst = {"no_compact_state": bool(no_compact and forced_k is None),
                "dimension_unresolved": [int(k0), int(max(k, k_max))] if no_compact else None,
                "causal_equivalence_failed": bool(abst_causal or babst.get("causal_equivalence_failed")),
                "reason": "; ".join(r for r in reason if r)}
        tc = dict(binfo.get("train_cost") or {})
        tc.update({"cpu_s": C.now() - t0, "sim_calls": int(sim_used)})
        meta = {"k": {sid: int(k)}, "abstain": {sid: abst}, "train_cost": tc,
                "k_range": {sid: [int(min(k0, k)), int(max(k0, k))] if not no_compact else abst["dimension_unresolved"]},
                "cegar": {"log": _jsonable(log), "base": cfg["base"], "k0": k0, "k_final": k, "k_max": k_max,
                          "n_probe_pairs": len(probes), "refined": bool(changed)}}
        return CegarModel(model, meta)


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items() if not isinstance(v, np.ndarray)}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o
