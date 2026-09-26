"""sd_shared: multi-encoder shared-dynamics state model (family G of the tournament: shared cross-implementation state models).

Per system s an implementation-specific linear encoder E_s / decoder D_s / input map A_s / readout g_s; ONE latent transition law
F shared by all systems of a fit (sharing='shared'), one per system ('independent'), or one shared law plus a per-system linear
correction ('partial'). See sd_latent for the equations and the event semantics, and notes/sd_shared.md for the objective, the
dimension, abstention and sharing rules.

config keys (besides the evaluator keys k / sharing / adapt_from):
    kmax            largest k tried by the dimension rule (default min(8, N))
    n_iter          training iterations per candidate (default 300)
    hidden_f        width of the transition MLP (default 64)
    verdict         compute the sharing verdict for shared / partial fits (default True)
    share_delta     non-inferiority margin of the sharing verdict (relative validation score, default 0.2 = the evaluator's margin)
    time_budget_s   soft wall-clock budget of the whole fit (default 1100 s per system, 2200 s for multi-system fits)
"""

from __future__ import annotations

import time

import numpy as np

from ..api import StateMethod, StateModel, register
from .sd_core import SysData, choose_dimension, parse_events, set_threads
from .sd_latent import Trainer, calibrate_event_gain, encode_hist_np, set_event_model, readout_np, rollout_np, val_score

ALPHA_GRID = (1.0, 0.5, 0.3, 0.2, 0.1)

EVENT_KINDS = ("kick", "current", "silence", "edge_remove")
ABSTAIN_RATIO = 0.7
MICRO_UNEXPLAINED = 0.7        # dimension_unresolved when the latent leaves > 70 % of the leading-PC microstate error


# ------------------------------------------------------------------------------------------------------------ model
class SDSharedModel(StateModel):
    """Executable model: numpy blocks (one per transition law) exported from sd_latent.Trainer."""

    def __init__(self, blocks: list[dict], info: dict):
        self.blocks = blocks
        self.where = {}
        for b, P in enumerate(blocks):
            for s, ps in enumerate(P["systems"]):
                self.where[ps["sid"]] = (b, s)
        self.cols = {sid: {int(n): i for i, n in enumerate(self.blocks[b]["systems"][s]["obs"])} for sid, (b, s) in self.where.items()}
        self.k = {sid: int(self.blocks[b]["k"]) for sid, (b, s) in self.where.items()}
        self._info = info

    def _bs(self, sid):
        if sid not in self.where:
            raise KeyError(f"system {sid!r} is not part of this model")
        return self.where[sid]

    def encode(self, system_id, x_hist, u_hist, dt):
        b, s = self._bs(system_id)
        return encode_hist_np(self.blocks[b], s, x_hist, u_hist, dt)

    def rollout(self, system_id, z0, u_future, events, dt):
        b, s = self._bs(system_id)
        P = self.blocks[b]
        u_future = np.asarray(u_future, np.float64)
        H = len(u_future) - 1
        parsed = parse_events(events, dt, self.cols[system_id], H + 1)
        Z = rollout_np(P, s, np.asarray(z0, np.float64), u_future, parsed, dt, H)
        return {"z": Z, "y": readout_np(P, s, Z, u_future)}

    def readout(self, system_id, z, u):
        b, s = self._bs(system_id)
        z, u = np.atleast_2d(np.asarray(z, np.float64)), np.atleast_2d(np.asarray(u, np.float64))
        return readout_np(self.blocks[b], s, z, u)

    def supports(self, system_id, event_kind):
        return system_id in self.where and event_kind in EVENT_KINDS

    def info(self):
        return self._info

    def transition_law(self, system_id) -> dict:
        b, _ = self._bs(system_id)
        return {"Tc": self.blocks[b]["Tc"], "F": self.blocks[b]["F"], "shared": self.blocks[b]["shared"]}


# ------------------------------------------------------------------------------------------------------------ parameter counts
def _count_block(P: dict) -> dict:
    def n_lin(p):
        return int(p[0].size + p[1].size)
    tr = sum(n_lin(F["Wz"]) + F["Wv"].size + F["W3"].size for F in P["F"])
    enc, ro = {}, {}
    for ps in P["systems"]:
        r = int(ps.get("r_basis", ps["E"].shape[1]))
        # encoder C (k x r) and decoder B (r x k) in the signal subspace, input map, current gain, decoder offset
        e = 2 * ps["E"].shape[0] * r + ps["A"].size + 1 + ps["dbias"].size
        if P["shared"] == "partial":
            tr += ps["L"].size
        enc[ps["sid"]] = int(e)
        ro[ps["sid"]] = int(sum(n_lin(ps["G"][k]) for k in ("lin", "l1", "l2")))
    return {"encoder": enc, "transition": int(tr), "readout": ro}


def _merge_counts(blocks: list[dict]) -> dict:
    out = {"encoder": {}, "transition": 0, "readout": {}}
    for P in blocks:
        c = _count_block(P)
        out["encoder"].update(c["encoder"])
        out["readout"].update(c["readout"])
        out["transition"] += c["transition"]
    return out


# ------------------------------------------------------------------------------------------------------------ input-only control
def input_only_val(sd: SysData, horizon_s: float) -> float:
    """Validation NMSE of a ridge predictor of y_t from the input history alone (lags 0..~0.2 s): the no-state control used by
    the abstention rule."""
    lags = sorted({0} | {max(1, int(round(t / sd.dt))) for t in (0.01, 0.02, 0.05, 0.1, 0.2)})

    def feats(U):
        T = len(U)
        F = [U[np.clip(np.arange(T) - L, 0, T - 1)] for L in lags]
        on = np.cumsum(np.abs(U).sum(1) > 1e-9) > 0
        first = np.argmax(on) if on.any() else T
        tso = np.clip((np.arange(T) - first) * sd.dt, 0, 1.0) * on
        return np.hstack(F + [tso[:, None], np.ones((T, 1))])

    A = np.concatenate([feats(sd.U[i]) for i in sd.train_idx if sd.finite[i]])
    Y = np.concatenate([sd.Y[i] for i in sd.train_idx if sd.finite[i]])
    mu, s = A.mean(0), A.std(0) + 1e-9
    s[-1] = 1.0
    mu[-1] = 0.0
    An = (A - mu) / s
    W = np.linalg.solve(An.T @ An + 1e-2 * len(An) * np.eye(An.shape[1]), An.T @ Y)
    idx = sd.val_idx if len(sd.val_idx) else sd.train_idx
    errs = []
    for i in idx:
        if not sd.finite[i]:
            continue
        P = ((feats(sd.U[i]) - mu) / s) @ W
        errs.append(float(np.mean((P - sd.Y[i]) ** 2 / sd.y_var)))
    return float(np.mean(errs)) if errs else float("nan")


# ------------------------------------------------------------------------------------------------------------ method
@register
class SDShared(StateMethod):
    name = "sd_shared"
    version = "1.0"
    default_config = {"kmax": 8, "n_iter": 300, "hidden_f": 64, "hidden_g": 32, "verdict": True, "share_delta": 0.2,
                      "adapt_restarts": 8, "adapt_iter": 300}
    supported_sharing = ("auto", "independent", "shared", "partial")
    supports_adaptation = True

    # ------------------------------------------------------------------------------------------------- helpers
    def _prep(self, train, systems, seed):
        by = {}
        for t in train:
            by.setdefault(t.system_id, []).append(t)
        sids = sorted(by)
        return [SysData(sid, by[sid], systems[sid], seed=seed) for sid in sids]

    def _cfg(self, config):
        c = dict(self.default_config)
        c.update(config or {})
        return c

    def _horizon(self, sd: SysData) -> float:
        """Primary validation horizon: 25 % of the trajectory length (1 s of 4 s synthetic, 0.5 s of 2 s real), at most 1 s."""
        T = min(len(x) for x in sd.X) * sd.dt
        return float(min(1.0, 0.25 * T))

    def _train_cfg(self, sd: SysData, c: dict) -> dict:
        """Training horizon (rollout windows) = the primary validation horizon (at most 0.25 s when dt <= 5 ms, for cost); the
        predictive-encoder lags are 0.1 / 0.25 / 0.5 / 1 x the validation horizon."""
        hz = self._horizon(sd)
        return {"horizon_s": hz if sd.dt >= 0.005 else min(hz, 0.25), "pred_horizon_s": hz}

    def _fit_one(self, sd: SysData, k: int, c: dict, seed: int, time_limit=None) -> tuple[dict, dict, Trainer]:
        tr = Trainer([sd], k, shared="independent", hidden_f=c["hidden_f"], hidden_g=c["hidden_g"], seed=seed, cfg=self._train_cfg(sd, c))
        tr.fit(n_iter=c["n_iter"], time_limit=time_limit)
        P = tr.export()
        v = val_score(P, 0, sd, sd.val_idx if len(sd.val_idx) else sd.train_idx, self._horizon(sd))
        return P, v, tr

    def _sweep(self, sd: SysData, c: dict, seed: int, deadline: float) -> dict:
        """Dimension rule: fit k = 1, 2, ... ; stop when two consecutive k do not improve on the best by the tolerance, at kmax,
        or at the time budget. Returns the curve, the selected k, the models."""
        kmax = int(min(c.get("kmax", 8), sd.N))
        curve, models = [], {}
        for k in range(1, kmax + 1):
            left = deadline - time.time()
            if k > 1 and left < 60:
                break
            P, v, _ = self._fit_one(sd, k, c, seed, time_limit=max(30.0, left / 2))
            models[k] = (P, v)
            curve.append({"k": k, "score": v["score"], "se": v["se"], "y": v["y"], "x": v["x"], "per": v["per_traj"]})
            ksel, diag = choose_dimension(curve)
            if len(curve) >= 3 and all(cc["k"] not in diag["acceptable"] for cc in curve[-2:]) and diag["best_k"] < curve[-2]["k"]:
                break
        ksel, diag = choose_dimension(curve)
        within = diag.get("acceptable") or [ksel]
        for cc in curve:
            cc.pop("per", None)
        return {"curve": curve, "k": ksel, "diag": diag, "models": models, "k_range": [int(min(within)), int(max(within))] if within else None,
                "kmax": kmax, "k_tried": [cc["k"] for cc in curve]}

    def _abstain(self, sd: SysData, sweep: dict, y_io: float) -> dict:
        """Abstention rule (training / validation data only):
        - no_compact_state: the selected model's validation readout NMSE over the primary horizon is > 0.3 AND more than
          ABSTAIN_RATIO (0.7) x the input-only control's (the state explains < 30 % of what the input alone leaves unexplained);
        - dimension_unresolved [k, N]: the curve never flattened up to kmax (the best k is the largest tried and still improving),
          or the selected latent leaves > 70 % of the open-loop NMSE of the leading microstate PCs (it does not capture the dominant
          microscopic dynamics; calibrated on the public dev suite, see notes)."""
        k = sweep["k"]
        v = sweep["models"][k][1]
        diag = sweep["diag"]
        no_compact = bool(np.isfinite(v["y"]) and v["y"] > 0.3 and (not np.isfinite(y_io) or v["y"] > ABSTAIN_RATIO * y_io))
        unresolved = None
        reason = []
        if not diag.get("plateau_reached", True) and sweep["k_tried"] and max(sweep["k_tried"]) >= sweep["kmax"] and sweep["kmax"] < sd.N:
            unresolved = [int(k), int(sd.N)]
            reason.append(f"validation score still improving at kmax={sweep['kmax']}")
        if np.isfinite(v["x"]) and v["x"] > MICRO_UNEXPLAINED:
            unresolved = [int(k), int(sd.N)]
            reason.append(f"the latent predicts < {1 - MICRO_UNEXPLAINED:.0%} of the leading microstate PCs over the horizon "
                          f"(validation x-NMSE {v['x']:.2f})")
        if no_compact:
            reason.insert(0, f"validation readout NMSE {v['y']:.3f} vs input-only {y_io:.3f}: no compact predictive state")
        return {"no_compact_state": no_compact, "dimension_unresolved": unresolved, "causal_equivalence_failed": False,
                "reason": "; ".join(reason), "val_y_nmse": float(v["y"]), "input_only_val_nmse": float(y_io)}

    def _choose_alpha(self, blocks: list[dict], sds: list[SysData], c: dict) -> dict:
        """Encoder filter gain per system: the largest alpha in ALPHA_GRID (alpha = 1: instantaneous projection) whose validation
        score is within the plateau tolerance of the best alpha (same tolerance as the dimension rule)."""
        by_sid = {sd.sid: sd for sd in sds}
        out = {}
        for P in blocks:
            for s, ps in enumerate(P["systems"]):
                sd = by_sid.get(ps["sid"])
                if sd is None:
                    continue
                grid = [1.0] if c.get("alpha") is not None else list(ALPHA_GRID)
                if c.get("alpha") is not None:
                    ps["alpha"] = float(c["alpha"])
                    out[ps["sid"]] = {"alpha": ps["alpha"], "forced": True, "event_model": set_event_model(P, s, c.get("silence_mode", "split"), c.get("event_map", "pinvDraw"))}
                    continue
                idx = sd.val_idx if len(sd.val_idx) else sd.train_idx
                ro = self._choose_readout(P, s, sd, idx)
                rows = []
                grid = sorted(grid, reverse=True)            # index 0 = alpha 1 (no filtering), then more filtering
                for j, a in enumerate(grid):
                    v = val_score(P, s, sd, idx, self._horizon(sd), alpha=a)
                    rows.append({"k": j, "alpha": a, "score": v["score"], "se": v["se"], "per": v["per_traj"]})
                # same paired rule as the dimension: the smallest index (largest alpha, least filtering) that is acceptable
                jsel, _ = choose_dimension(rows)
                ps["alpha"] = float(grid[int(jsel)])
                for r in rows:
                    r.pop("per", None)
                evm = set_event_model(P, s, c.get("silence_mode", "split"), c.get("event_map", "pinvDraw"))
                evm["gain"] = calibrate_event_gain(P, s, sd, self._horizon(sd)) if c.get("event_gain", True) else {"beta": 1.0}
                out[ps["sid"]] = {"alpha": ps["alpha"], "curve": rows, "readout": ro, "event_model": evm}
        return out

    def _choose_readout(self, P: dict, s: int, sd: SysData, idx) -> dict:
        """Readout parsimony: a ridge-linear readout of (z, un) fitted on the training encodings replaces the MLP readout unless
        the MLP is clearly better on validation (same paired rule as the dimension). Linear readouts extrapolate more safely to
        held-out states."""
        ps = P["systems"][s]
        Z, U, Y = [], [], []
        for i in sd.train_idx:
            if not sd.finite[i]:
                continue
            Z.append(sd.xs(sd.X[i][::2]) @ ps["E"].T)
            U.append((np.asarray(sd.U[i][::2], np.float64) - ps["u_mu"]) / ps["u_sd"])
            Y.append((np.asarray(sd.Y[i][::2], np.float64) - ps["y_mu"]) / ps["y_sd"])
        A = np.hstack([np.concatenate(Z), np.concatenate(U)])
        Yt = np.concatenate(Y)
        mu = A.mean(0)
        G = (A - mu).T @ (A - mu)
        W = np.linalg.solve(G + 1e-3 * np.trace(G) / len(G) * np.eye(len(G)), (A - mu).T @ (Yt - Yt.mean(0)))
        lin = (W.T, Yt.mean(0) - mu @ W)
        hz = self._horizon(sd)
        v_mlp = val_score(P, s, sd, idx, hz)
        G_mlp = ps["G"]
        ps["G"] = {"lin": lin, "l1": (np.zeros_like(G_mlp["l1"][0]), np.zeros_like(G_mlp["l1"][1])),
                   "l2": (np.zeros_like(G_mlp["l2"][0]), np.zeros_like(G_mlp["l2"][1]))}
        v_lin = val_score(P, s, sd, idx, hz)
        rows = [{"k": 1, "score": v_lin["score"], "se": v_lin["se"], "per": v_lin["per_traj"]},
                {"k": 2, "score": v_mlp["score"], "se": v_mlp["se"], "per": v_mlp["per_traj"]}]
        ksel, _ = choose_dimension(rows)
        if ksel != 1:
            ps["G"] = G_mlp
        return {"chosen": "linear" if ksel == 1 else "mlp", "val_linear": v_lin["score"], "val_mlp": v_mlp["score"]}

    # ------------------------------------------------------------------------------------------------- fit
    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        set_threads(int((config or {}).get("threads", 1)))
        t_start = time.time()
        c = self._cfg(config)
        sds = self._prep(train, systems, seed)
        if c.get("adapt_from") is not None:
            return self._adapt(sds, c, seed, t_start)
        sharing = c.get("sharing", "auto") or "auto"
        if sharing not in self.supported_sharing:
            raise NotImplementedError(sharing)
        budget = float(c.get("time_budget_s", 1100.0 if len(sds) == 1 else 2200.0))
        deadline = t_start + budget
        # 1) per-system dimension sweeps (independent laws)
        sweeps, abst, y_io = {}, {}, {}
        per_budget = (budget * (0.5 if len(sds) > 1 and sharing != "independent" else 1.0)) / len(sds)
        for sd in sds:
            y_io[sd.sid] = input_only_val(sd, self._horizon(sd))
            if c.get("k") is not None:
                P, v, _ = self._fit_one(sd, int(c["k"]), c, seed, time_limit=per_budget)
                sweeps[sd.sid] = {"curve": [{"k": int(c["k"]), "score": v["score"], "se": v["se"], "y": v["y"], "x": v["x"]}], "k": int(c["k"]),
                                  "diag": {"plateau_reached": True, "forced": True}, "models": {int(c["k"]): (P, v)},
                                  "k_range": [int(c["k"])] * 2, "kmax": int(c["k"]), "k_tried": [int(c["k"])]}
            else:
                sweeps[sd.sid] = self._sweep(sd, c, seed, min(deadline, time.time() + per_budget))
            abst[sd.sid] = self._abstain(sd, sweeps[sd.sid], y_io[sd.sid])
        indep_blocks = [sweeps[sd.sid]["models"][sweeps[sd.sid]["k"]][0] for sd in sds]
        info = {"k": {sd.sid: int(sweeps[sd.sid]["k"]) for sd in sds}, "k_range": {sd.sid: sweeps[sd.sid]["k_range"] for sd in sds},
                "abstain": abst, "dimension_curve": {sd.sid: sweeps[sd.sid]["curve"] for sd in sds},
                "dimension_rule": "smallest k with validation score <= best + max(SE_best, 5% best, 0.002); score = open-loop NMSE of y "
                                  "+ NMSE of the leading microstate PCs over the primary horizon (25% of the trajectory, <= 1 s)",
                "lipschitz_bound": None}
        if len(sds) == 1 or sharing == "independent":
            blocks = indep_blocks
            info["sharing"] = {"mode": "independent" if len(sds) > 1 else "single", "verdict": None}
        else:
            blocks, sh_info = self._fit_shared(sds, sweeps, c, seed, deadline, mode=("partial" if sharing == "partial" else "shared"))
            info["sharing"] = sh_info
            if sharing == "auto" and sh_info.get("verdict") != "supported":
                blocks = indep_blocks
                info["sharing"]["mode"] = "independent (auto: sharing not supported)"
            info["k"] = {sd.sid: int(blocks[0]["k"]) if len(blocks) == 1 else info["k"][sd.sid] for sd in sds}
        info["encoder_filter"] = self._choose_alpha(blocks, sds, c)
        info["n_params"] = _merge_counts(blocks)
        info["train_cost"] = {"cpu_s": float(time.process_time()), "sim_calls": 0, "wall_s": float(time.time() - t_start)}
        return SDSharedModel(blocks, info)

    # ------------------------------------------------------------------------------------------------- shared fit + verdict
    def _fit_shared(self, sds: list[SysData], sweeps: dict, c: dict, seed: int, deadline: float, mode: str = "shared"):
        # common dimension: the lower median of the per-system choices (one noisy upward choice must not inflate the shared
        # latent; a shared law that really needs more dimensions fails the non-inferiority test and is reported unsupported)
        ks = sorted(sweeps[sd.sid]["k"] for sd in sds)
        k = int(c["k"]) if c.get("k") is not None else int(ks[(len(ks) - 1) // 2])
        # independent references at the common k (capacity-matched: same transition architecture per system)
        indep = {}
        for sd in sds:
            if k in sweeps[sd.sid]["models"]:
                indep[sd.sid] = sweeps[sd.sid]["models"][k]
            else:
                P, v, _ = self._fit_one(sd, k, c, seed, time_limit=max(60.0, (deadline - time.time()) / (3 * len(sds))))
                indep[sd.sid] = (P, v)
        # anchor = the system whose independent model validates best; its law initialises the shared law
        anchor = min(sds, key=lambda sd: indep[sd.sid][1]["score"])
        tr = Trainer(sds, k, shared=mode, hidden_f=c["hidden_f"], hidden_g=c["hidden_g"], seed=seed, cfg=self._train_cfg(sds[0], c))
        a_idx = sds.index(anchor)
        tr.load_F(indep[anchor.sid][0]["F"][0], 0)
        tr.load_system(indep[anchor.sid][0]["systems"][0], a_idx)
        # other systems: encoder-only restarts against the frozen anchor law, keep the best (orientation of the latent is not
        # identifiable from one system alone)
        for s, sd in enumerate(sds):
            if s == a_idx:
                continue
            self._best_encoder_start(tr, s, c, seed)
        n_iter = int(c["n_iter"])
        left = deadline - time.time()
        tr.fit(n_iter=n_iter, time_limit=max(60.0, 0.6 * left))
        P = tr.export()
        per = {}
        ok_all = True
        for s, sd in enumerate(sds):
            vi = indep[sd.sid][1]
            vs = val_score(P, s, sd, sd.val_idx if len(sd.val_idx) else sd.train_idx, self._horizon(sd))
            d = np.array(vs["per_traj"]) - np.array(vi["per_traj"])
            dm = float(d.mean()) if len(d) else float("nan")
            dse = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
            upper = dm + 1.645 * dse
            ok = bool(np.isfinite(upper) and upper <= c["share_delta"] * vi["score"])
            per[sd.sid] = {"val_shared": vs["score"], "val_independent": vi["score"], "diff": dm, "diff_upper95": upper,
                           "margin": c["share_delta"] * vi["score"], "noninferior": ok}
            ok_all = ok_all and ok
        n_sh = _count_block(P)["transition"]
        n_in = sum(_count_block(indep[sd.sid][0])["transition"] for sd in sds)
        fewer = n_sh < n_in
        verdict = "supported" if (ok_all and fewer) else "unsupported"
        info = {"mode": mode, "verdict": verdict, "k_common": k, "anchor": anchor.sid, "per_system": per,
                "transition_params_shared": int(n_sh), "transition_params_independent": int(n_in),
                "rule": f"shared law non-inferior to capacity-matched independent laws on validation data for every system "
                        f"(one-sided 95% upper bound of the paired per-trajectory score difference <= {c['share_delta']} x independent "
                        f"score) and fewer transition parameters"}
        return [P], info

    def _best_encoder_start(self, tr: Trainer, s: int, c: dict, seed: int) -> None:
        """Encoder-only restarts for system s with the transition law frozen: PCA initialisation under several orthogonal
        transforms (sign flips / random rotations), short adaptation each, keep the lowest training loss."""
        sd = tr.systems[s]
        k = tr.k
        rng = np.random.default_rng(seed + 1000 + s)
        n_rest = int(c.get("adapt_restarts", 8))
        rots = [np.eye(k)]
        if k == 1:
            rots.append(-np.eye(1))
        elif k == 2:
            # the orientation group O(2): rotations by multiples of 90 degrees, with and without reflection
            for ang in (np.pi / 2, np.pi, 3 * np.pi / 2):
                rots.append(np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]]))
            F = np.diag([1.0, -1.0])
            for R in list(rots):
                rots.append(R @ F)
        while len(rots) < n_rest:
            R, _ = np.linalg.qr(rng.standard_normal((k, k)))
            if len(rots) % 2:
                R[:, 0] *= -1.0
            rots.append(R)
        rots = rots[:max(n_rest, 2 if k == 1 else 1)]
        best, best_state = np.inf, None
        n_short = max(40, int(c.get("adapt_iter", 300)) // 4)
        for R in rots:
            ini = tr.init_for(s, rot=R)
            tr.set_encoder(s, ini["E"], ini["D"], ini["dbias"])
            tr.fit(n_iter=n_short, train_params="encoders", systems_idx=[s])
            L = tr.train_loss(s)
            if L < best:
                best = L
                best_state = {n: p.detach().clone() for n, p in tr.net.named_parameters()}
        if best_state is not None:
            with tr.torch.no_grad():
                for n, p in tr.net.named_parameters():
                    p.copy_(best_state[n])

    # ------------------------------------------------------------------------------------------------- adaptation
    def _adapt(self, sds: list[SysData], c: dict, seed: int, t_start: float):
        """Encoder-only adaptation: the transition law of adapt_from is frozen; for every new system fit encoder, decoder, input
        map, current gain and readout (several orientation restarts, then a full encoder-only fit)."""
        src = c["adapt_from"]
        if not isinstance(src, SDSharedModel):
            raise NotImplementedError("adapt_from must be an sd_shared model")
        b0 = src.blocks[0]
        k = int(b0["k"])
        blocks, info_abst, vals = [], {}, {}
        for sd in sds:
            # the frozen law already fixes the latent gauge: no per-system whitening (an implementation need not visit the latent
            # space with the same distribution as the ones the law was fitted on)
            tcfg = dict(self._train_cfg(sd, c), w_white=float(c.get("adapt_white", 0.0)))
            tr = Trainer([sd], k, shared="independent", hidden_f=c["hidden_f"], hidden_g=c["hidden_g"], Tc=b0["Tc"], seed=seed,
                         cfg=tcfg)
            tr.load_F(b0["F"][0], 0)
            self._best_encoder_start(tr, 0, c, seed)
            tr.fit(n_iter=int(c.get("adapt_iter", 300)), train_params="encoders")
            P = tr.export()
            P["F"] = [b0["F"][0]]          # exactly the frozen law
            blocks.append(P)
            v = val_score(P, 0, sd, sd.val_idx if len(sd.val_idx) else sd.train_idx, self._horizon(sd))
            vals[sd.sid] = {"val_score": v["score"], "val_y": v["y"]}
            y_io = input_only_val(sd, self._horizon(sd))
            info_abst[sd.sid] = {"no_compact_state": bool(v["y"] > 0.3 and v["y"] > ABSTAIN_RATIO * y_io), "dimension_unresolved": None,
                                 "causal_equivalence_failed": False, "reason": "adapted encoder (frozen transition law)"}
        filt = self._choose_alpha(blocks, sds, c)
        info = {"k": {sd.sid: k for sd in sds}, "k_range": {sd.sid: [k, k] for sd in sds}, "abstain": info_abst, "encoder_filter": filt,
                "sharing": {"mode": "adapted (transition law frozen)", "verdict": None, "adapt_validation": vals},
                "n_params": _merge_counts(blocks),
                "train_cost": {"cpu_s": float(time.time() - t_start), "sim_calls": 0, "adapted_params": "encoder/decoder/input map/gain/readout"},
                "lipschitz_bound": None}
        return SDSharedModel(blocks, info)
