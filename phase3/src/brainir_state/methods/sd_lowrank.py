"""sd_lowrank: unit-space low-rank RNN (tournament family G, companion of sd_shared).

Unit dynamics (rate form; every microscopic intervention acts on the model's own units):

    tau dx/dt = -x + phi(M N^T x + W un + b + I(t))              x in R^N (the observed units, raw units), rank R = k
    phi       = relu (non-negative data) or phi_i(a) = g_i tanh(a / g_i) (signed data; per-unit gain g_i)
    y         = G(z, un)                                        small MLP readout of the latent

The latent state is z = N^T x (R-dimensional) and is EXACTLY closed when no unit is silenced / no edge removed:

    tau dz/dt = -z + N^T phi(M z + W un + b + I)

so encoding is a projection, and the rollout integrates the R-dimensional law. Interventions (native, in unit space):
    kick dx_j            z += N_j dx_j        (with relu, dx_j is clipped so that x_j + dx_j >= 0, x_j from the steady-state
                                                estimate xhat = phi(M z + W un + b))
    current I_j          enters the pre-activation of unit j (exact in the latent law)
    silence S            units in S lose their input (decay with tau from xhat_S) and their output (removed from N^T x):
                         z = z_eff + N_S a_S, tau dz_eff/dt = -z_eff + sum_{i not in S} N_i phi_i(M z_eff + ...),  tau da/dt = -a
    edge_remove post<-pre   the pre-activation of post loses (M_post . N_pre) a_pre, a_pre an auxiliary copy of unit pre's rate
                         (tau da/dt = -a + phi_pre(...)), started at xhat_pre
With a uniform tau the rank R is the latent dimension. R is chosen by the same generic rule as sd_shared (smallest R whose
validation score is within the plateau tolerance of the best).
"""

from __future__ import annotations

import time

import numpy as np

from ..api import StateMethod, StateModel, register
from .sd_core import SysData, batch_windows, choose_dimension, parse_events, dense_events, se_mean, set_threads, window_starts
from .sd_shared import input_only_val

EVENT_KINDS = ("kick", "current", "silence", "edge_remove")
ABSTAIN_RATIO = 0.7


# ------------------------------------------------------------------------------------------------------------ torch model
def _build(sd: SysData, R: int, hidden_g: int, seed: int, tau0: float, relu: bool, cgain0: float = 1.0):
    import torch
    nn = torch.nn
    torch.manual_seed(seed)
    N = sd.N
    Xa = np.concatenate([sd.X[i][::2] for i in sd.train_idx if sd.finite[i]]).astype(np.float64)
    mu = Xa.mean(0)
    Xc = Xa - mu
    _, s, Vt = np.linalg.svd(Xc, full_matrices=False)
    V = Vt[:R] if Vt.shape[0] >= R else np.vstack([Vt, np.random.default_rng(seed).standard_normal((R - Vt.shape[0], N)) * 0.1])
    lam = np.sqrt((s[:R] ** 2) / len(Xc)) if len(s) >= R else np.ones(R)
    lam = np.concatenate([lam, np.ones(R - len(lam))]) if len(lam) < R else lam
    lam = np.maximum(lam, 1e-3)
    # N^T x = whitened PC scores (+ offset absorbed in b); M N^T ~ projection on the leading PCs
    Nm = (V / lam[:, None]).T                     # N x R
    Mm = (V * lam[:, None]).T                     # N x R
    b0 = mu - Mm @ (Nm.T @ mu)
    g0 = 2.0 * Xa.std(0) + np.abs(mu) + 1e-2

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.M = nn.Parameter(torch.tensor(Mm, dtype=torch.float32))
            self.Nn = nn.Parameter(torch.tensor(Nm, dtype=torch.float32))
            self.W = nn.Parameter(torch.zeros(N, sd.n_u))
            self.b = nn.Parameter(torch.tensor(b0, dtype=torch.float32))
            self.lg = nn.Parameter(torch.tensor(np.log(g0), dtype=torch.float32))
            self.ltau = nn.Parameter(torch.tensor(np.log(tau0), dtype=torch.float32))
            self.lcg = nn.Parameter(torch.tensor(np.log(cgain0), dtype=torch.float32))   # current -> pre-activation gain
            self.g_lin = nn.Linear(R + sd.n_u, sd.n_y)
            self.g_l1 = nn.Linear(R + sd.n_u, hidden_g)
            self.g_l2 = nn.Linear(hidden_g, sd.n_y)
            with torch.no_grad():
                self.g_l2.weight.mul_(0.1)
                self.g_l2.bias.zero_()

        def phi(self, a):
            if relu:
                return torch.relu(a)
            g = torch.exp(self.lg)
            return g * torch.tanh(a / g)

        def G(self, z, un):
            a = torch.cat([z, un], -1)
            return self.g_lin(a) + self.g_l2(torch.tanh(self.g_l1(a)))

    return Net()


class LRTrainer:
    def __init__(self, sd: SysData, R: int, *, hidden_g: int = 32, seed: int = 0, cfg: dict | None = None):
        import torch
        self.torch = torch
        self.sd, self.R, self.seed = sd, R, seed
        self.cfg = dict(LR_TRAIN)
        self.cfg.update(cfg or {})
        self.relu = sd.nonneg
        tau0 = float(np.clip(0.3 * sd.timescale(), 2 * sd.dt, 1.0))
        from .sd_core import current_gain
        g, _ = current_gain(sd)
        cg0 = float(np.clip(g * tau0, 1e-3, 1e3)) if g else 1.0     # dx/dt ~ c I / tau at onset (linear regime)
        self.net = _build(sd, R, hidden_g, seed, tau0, self.relu, cg0)
        self.u_mu = torch.tensor(sd.u_mu, dtype=torch.float32)
        self.u_sd = torch.tensor(sd.u_sd, dtype=torch.float32)
        from .sd_core import graph_prior
        gp = graph_prior(sd) if self.cfg.get("graph_prior", 0.1) else None
        self.gp = None if gp is None else (torch.tensor(gp[0]), torch.tensor(gp[1]))
        xsd = sd.sd.copy()
        self.x_w = torch.tensor(1.0 / np.maximum(xsd, np.median(xsd)) ** 2, dtype=torch.float32)
        self.log = []

    def rollout_units(self, x, u, kick, cur, sil, has):
        """Unit-space Euler rollout from the TRUE x0 (teacher start); returns x_hat (B, H+1, N)."""
        torch = self.torch
        net = self.net
        dt = self.sd.dt
        tau = torch.exp(net.ltau)
        un = (u - self.u_mu) / self.u_sd
        drive = un @ net.W.T + net.b
        xh = x[:, 0]
        out = [xh]
        H = x.shape[1] - 1
        for j in range(H):
            if has:
                xh = xh + kick[:, j]
                if self.relu:
                    xh = torch.relu(xh)
                keep = 1.0 - sil[:, j]
                z = (xh * keep) @ net.Nn
                h = z @ net.M.T + drive[:, j] + torch.exp(net.lcg) * cur[:, j]
                xh = xh + dt / tau * (-xh + keep * net.phi(h))
            else:
                h = (xh @ net.Nn) @ net.M.T + drive[:, j]
                xh = xh + dt / tau * (-xh + net.phi(h))
            out.append(xh)
        return torch.stack(out, 1), un

    def losses(self, starts, H):
        torch = self.torch
        sd = self.sd
        x, u, y, kick, cur, sil, has = batch_windows(sd, starts, H)
        x, u, y = torch.tensor(x), torch.tensor(u), torch.tensor(y)
        kick, cur, sil = torch.tensor(kick), torch.tensor(cur), torch.tensor(sil)
        xh, un = self.rollout_units(x, u, kick, cur, sil, has)
        L_x = (((xh[:, 1:] - x[:, 1:]) ** 2) * self.x_w).mean()
        z = xh @ self.net.Nn
        yh = self.net.G(z, un)
        yt = (y - torch.tensor(sd.y_mu, dtype=torch.float32)) / torch.tensor(sd.y_sd, dtype=torch.float32)
        L_y = ((yh - yt) ** 2).mean()
        loss = L_y + self.cfg["w_x"] * L_x
        parts = {"y": float(L_y.detach()), "x": float(L_x.detach())}
        if self.gp is not None:
            # structural prior (public local graph): Dale's law on outgoing weights and no coupling where the graph has no edge
            sign, A = self.gp
            J = self.net.M @ self.net.Nn.T
            scale = (J.detach().abs() * A).sum() / A.sum().clamp(min=1.0) + 1e-6
            L_g = (torch.relu(-sign[None, :] * J) ** 2 * (sign[None, :] != 0)).mean() / scale ** 2 + ((J * (1 - A)) ** 2).mean() / scale ** 2
            loss = loss + self.cfg.get("graph_prior", 0.1) * L_g
            parts["g"] = float(L_g.detach())
        return loss, parts

    def fit(self, n_iter=None, time_limit=None):
        torch = self.torch
        c = self.cfg
        n_iter = n_iter or c["n_iter"]
        sd = self.sd
        H_max = max(4, int(round(c["horizon_s"] / sd.dt)))
        H_max = min(H_max, min(len(sd.X[i]) for i in sd.train_idx) - 2)
        params = list(self.net.parameters())
        opt = torch.optim.Adam(params, lr=c["lr"])
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=c["lr"], total_steps=n_iter, pct_start=0.1)
        rng = np.random.default_rng(self.seed + 5)
        cache = {}
        t0 = time.time()
        for it in range(n_iter):
            frac = it / max(1, n_iter - 1)
            H = int(max(2, round(H_max * min(1.0, c["h_min_frac"] + frac / c["curriculum"]))))
            if H not in cache:
                cache[H] = window_starts(sd, sd.train_idx, H)
            st = cache[H]
            b = [st[j] for j in rng.integers(0, len(st), c["batch"])]
            loss, parts = self.losses(b, H)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            with torch.no_grad():
                self.net.ltau.clamp_(min=float(np.log(1.5 * sd.dt)))
            if it % 100 == 0 or it == n_iter - 1:
                self.log.append({"it": it, "H": H, "loss": float(loss.detach()), **parts})
            if time_limit is not None and time.time() - t0 > time_limit:
                self.log.append({"stopped_at": it})
                break
        return self

    def export(self) -> dict:
        net = self.net
        g = lambda p: p.detach().numpy().astype(np.float64)
        sd = self.sd
        return {"sid": sd.sid, "obs": sd.obs, "R": self.R, "M": g(net.M), "N": g(net.Nn), "W": g(net.W), "b": g(net.b),
                "gain": np.exp(g(net.lg)), "tau": float(np.exp(g(net.ltau))), "cgain": float(np.exp(g(net.lcg))), "relu": self.relu, "u_mu": sd.u_mu, "u_sd": sd.u_sd,
                "y_mu": sd.y_mu, "y_sd": sd.y_sd, "dt": sd.dt,
                "G": {"lin": (g(net.g_lin.weight), g(net.g_lin.bias)), "l1": (g(net.g_l1.weight), g(net.g_l1.bias)),
                      "l2": (g(net.g_l2.weight), g(net.g_l2.bias))}}


LR_TRAIN = {"n_iter": 300, "batch": 96, "lr": 5e-3, "horizon_s": 1.0, "h_min_frac": 0.1, "curriculum": 0.6, "w_x": 1.0,
            "graph_prior": 0.1}


# ------------------------------------------------------------------------------------------------------------ numpy engine
def _phi(P, a, idx=None):
    if P["relu"]:
        return np.maximum(a, 0.0)
    g = P["gain"] if idx is None else P["gain"][idx]
    return g * np.tanh(a / g)


def _G(P, z, un):
    a = np.concatenate([z, un], -1)
    G = P["G"]
    return a @ G["lin"][0].T + G["lin"][1] + np.tanh(a @ G["l1"][0].T + G["l1"][1]) @ G["l2"][0].T + G["l2"][1]


def lr_readout(P, z, u):
    un = (np.asarray(u, np.float64) - P["u_mu"]) / P["u_sd"]
    return _G(P, z, un) * P["y_sd"] + P["y_mu"]


def lr_rollout(P: dict, z0, u_future, parsed: list, dt: float, H: int):
    """Latent rollout with auxiliary unit variables for silenced units and presynaptic units of removed edges."""
    M, Nm, W, b, tau = P["M"], P["N"], P["W"], P["b"], P["tau"]
    un = (np.asarray(u_future, np.float64) - P["u_mu"]) / P["u_sd"]
    drive = un @ W.T + b
    Nn = M.shape[0]
    z = np.asarray(z0, np.float64).copy()
    zs = [z.copy()]
    has = bool(parsed)
    if has:
        kick, cur, sil, edges = dense_events(parsed, 0, H, Nn)
        cur = cur * P.get("cgain", 1.0)
    aux: dict[int, float] = {}          # silenced units: decaying rate a_j (their contribution N_j a_j is inside z)
    pre_aux: dict[int, float] = {}      # presynaptic units of removed edges: rate copies
    a_dt = dt / tau
    for j in range(H):
        if not has:
            h = M @ z + drive[j]
            z = z + a_dt * (-z + Nm.T @ _phi(P, h))
            zs.append(z.copy())
            continue
        S = np.flatnonzero(sil[j] > 0)
        # units leaving silence: their decayed rate simply stays in z (they rejoin the population)
        for u_ in list(aux):
            if u_ not in set(S.tolist()):
                aux.pop(u_)
        z_eff = z - sum((Nm[u_] * a for u_, a in aux.items()), np.zeros_like(z))
        h = M @ z_eff + drive[j] + cur[j]
        xhat = _phi(P, h)
        for u_ in S:
            if int(u_) not in aux:           # onset: split the unit's current rate estimate out of the population
                aux[int(u_)] = float(xhat[u_])
                z_eff = z_eff - Nm[u_] * aux[int(u_)]
        if S.size:
            h = M @ z_eff + drive[j] + cur[j]
        if kick[j].any():
            dk = kick[j].copy()
            if P["relu"]:
                dk = np.maximum(dk, -np.maximum(xhat, 0.0))
            for u_ in np.flatnonzero(dk):
                if int(u_) in aux:
                    aux[int(u_)] = max(0.0, aux[int(u_)] + dk[u_]) if P["relu"] else aux[int(u_)] + dk[u_]
                    dk[u_] = 0.0
            z_eff = z_eff + Nm.T @ dk
            h = M @ z_eff + drive[j] + cur[j]
        if edges is not None and edges[j]:
            for post, pre in edges[j]:
                if pre not in pre_aux:
                    pre_aux[pre] = float(_phi(P, h[pre:pre + 1], [pre])[0]) if not P["relu"] else float(max(h[pre], 0.0))
                h[post] -= float(M[post] @ Nm[pre]) * pre_aux[pre]
            for pre in list(pre_aux):
                hp = M[pre] @ z_eff + drive[j][pre] + cur[j][pre]
                target = float(max(hp, 0.0)) if P["relu"] else float(_phi(P, np.array([hp]), [pre])[0])
                pre_aux[pre] += a_dt * (-pre_aux[pre] + target)
        else:
            pre_aux.clear()
        r = _phi(P, h)
        if S.size:
            r[S] = 0.0
        z_eff = z_eff + a_dt * (-z_eff + Nm.T @ r)
        for u_ in aux:
            aux[u_] *= (1.0 - a_dt)
        z = z_eff + sum((Nm[u_] * a for u_, a in aux.items()), np.zeros_like(z_eff))
        if not np.all(np.isfinite(z)):
            z = np.nan_to_num(z, nan=0.0, posinf=1e6, neginf=-1e6)
        zs.append(z.copy())
    return np.stack(zs)


def lr_val_score(P: dict, sd: SysData, idx, horizon_s: float, n_starts: int = 4, pcs=None) -> dict:
    """As sd_latent.val_score: open-loop y NMSE (latent rollout from z0 = N^T x0) + NMSE of the leading PCs of the standardised x,
    reconstructed as the steady-state unit estimate xhat = phi(M z + W un + b)."""
    from .sd_latent import _shift_parsed
    dt = sd.dt
    Hh = max(1, int(round(horizon_s / dt)))
    m, V, lam = pcs if pcs is not None else sd.pca(min(10, sd.N))
    per_y, per_x = [], []
    for i in idx:
        if not sd.finite[i]:
            continue
        X, U, Y = sd.X[i], sd.U[i], sd.Y[i]
        T = len(X)
        H = min(Hh, T - 2)
        ey, ex = [], []
        for t0 in np.unique(np.linspace(max(1, T // 8), max(2, T - H - 1), n_starts).astype(int)):
            if t0 + H >= T:
                continue
            z0 = np.asarray(X[t0], np.float64) @ P["N"]
            Z = lr_rollout(P, z0, U[t0: t0 + H + 1], _shift_parsed(sd.EV[i], t0), dt, H)
            yp = lr_readout(P, Z, U[t0: t0 + H + 1])
            ey.append(float(np.mean((yp[1:] - Y[t0 + 1: t0 + H + 1]) ** 2 / sd.y_var)))
            un = (U[t0 + 1: t0 + H + 1] - P["u_mu"]) / P["u_sd"]
            xh = _phi(P, Z[1:] @ P["M"].T + un @ P["W"].T + P["b"])
            xs_h, xt = sd.xs(xh), sd.xs(X[t0 + 1: t0 + H + 1])
            num = (((xs_h - xt) @ V.T) ** 2).sum(1).mean()
            den = (((xt - m) @ V.T) ** 2).sum(1).mean() + 1e-9
            ex.append(float(num / max(den, lam.sum() * 0.1)))
        if ey:
            per_y.append(float(np.mean(ey)))
            per_x.append(float(np.mean(ex)))
    tot = [a + b for a, b in zip(per_y, per_x)]
    t_m, t_se = se_mean(tot)
    return {"y": se_mean(per_y)[0], "x": se_mean(per_x)[0], "score": t_m, "se": t_se, "per_traj": tot}


# ------------------------------------------------------------------------------------------------------------ model
class SDLowRankModel(StateModel):
    def __init__(self, params: dict[str, dict], info: dict):
        self.params = params
        self.cols = {sid: {int(n): i for i, n in enumerate(P["obs"])} for sid, P in params.items()}
        self.k = {sid: int(P["R"]) for sid, P in params.items()}
        self._info = info

    def encode(self, system_id, x_hist, u_hist, dt):
        return np.asarray(x_hist, np.float64)[-1] @ self.params[system_id]["N"]

    def rollout(self, system_id, z0, u_future, events, dt):
        P = self.params[system_id]
        u_future = np.asarray(u_future, np.float64)
        H = len(u_future) - 1
        parsed = parse_events(events, dt, self.cols[system_id], H + 1)
        Z = lr_rollout(P, z0, u_future, parsed, dt, H)
        return {"z": Z, "y": lr_readout(P, Z, u_future)}

    def readout(self, system_id, z, u):
        return lr_readout(self.params[system_id], np.atleast_2d(np.asarray(z, np.float64)), np.atleast_2d(np.asarray(u, np.float64)))

    def supports(self, system_id, event_kind):
        return system_id in self.params and event_kind in EVENT_KINDS

    def info(self):
        return self._info

    def connectivity(self, system_id) -> np.ndarray:
        """The fitted unit coupling J = M N^T (rank R)."""
        P = self.params[system_id]
        return P["M"] @ P["N"].T


def _n_params(P: dict) -> dict:
    G = P["G"]
    ro = sum(int(G[k][0].size + G[k][1].size) for k in ("lin", "l1", "l2"))
    return {"encoder": int(P["N"].size), "transition": int(P["M"].size + P["N"].size + P["W"].size + P["b"].size + P["gain"].size + 2),
            "readout": ro}


# ------------------------------------------------------------------------------------------------------------ method
@register
class SDLowRank(StateMethod):
    name = "sd_lowrank"
    version = "1.0"
    default_config = {"kmax": 8, "n_iter": 300, "hidden_g": 32}
    supported_sharing = ("auto", "independent")
    supports_adaptation = False

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        set_threads(int((config or {}).get("threads", 1)))
        t_start = time.time()
        c = dict(self.default_config)
        c.update(config or {})
        if c.get("sharing") not in (None, "auto", "independent"):
            raise NotImplementedError("sd_lowrank fits unit-space models per system (use sd_shared for shared laws)")
        if c.get("adapt_from") is not None:
            raise NotImplementedError("sd_lowrank has no system-independent transition law to freeze")
        by = {}
        for t in train:
            by.setdefault(t.system_id, []).append(t)
        params, info = {}, {"k": {}, "k_range": {}, "abstain": {}, "dimension_curve": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                            "sharing": {"mode": "independent", "verdict": None}, "lipschitz_bound": None,
                            "dimension_rule": "smallest rank R with validation score <= best + max(SE_best, 5% best, 0.002)"}
        budget = float(c.get("time_budget_s", 1100.0)) / max(1, len(by))
        for sid in sorted(by):
            sd = SysData(sid, by[sid], systems[sid], seed=seed)
            T = min(len(x) for x in sd.X) * sd.dt
            hz = float(min(1.0, 0.25 * T))
            tcfg = {"horizon_s": hz if sd.dt >= 0.005 else min(hz, 0.25), "graph_prior": float(c.get("graph_prior", 0.1))}
            deadline = time.time() + budget
            curve, models = [], {}
            ks = [int(c["k"])] if c.get("k") is not None else list(range(1, int(min(c["kmax"], sd.N)) + 1))
            for R in ks:
                left = deadline - time.time()
                if models and left < 60:
                    break
                tr = LRTrainer(sd, R, hidden_g=c["hidden_g"], seed=seed, cfg=tcfg).fit(n_iter=int(c["n_iter"]), time_limit=max(30.0, left / 2))
                P = tr.export()
                v = lr_val_score(P, sd, sd.val_idx if len(sd.val_idx) else sd.train_idx, hz)
                models[R] = (P, v)
                curve.append({"k": R, "score": v["score"], "se": v["se"], "y": v["y"], "x": v["x"], "per": v["per_traj"]})
                if c.get("k") is None and len(curve) >= 3:
                    _, dg = choose_dimension(curve)
                    if all(cc["k"] not in dg["acceptable"] for cc in curve[-2:]) and dg["best_k"] < curve[-2]["k"]:
                        break
            ksel, diag = choose_dimension(curve)
            within = diag.get("acceptable") or [ksel]
            for cc in curve:
                cc.pop("per", None)
            P, v = models[ksel]
            params[sid] = P
            y_io = input_only_val(sd, hz)
            no_compact = bool(v["y"] > 0.3 and v["y"] > ABSTAIN_RATIO * y_io)
            kmax = max(ks)
            unresolved = [int(ksel), int(sd.N)] if (c.get("k") is None and not diag.get("plateau_reached", True) and kmax < sd.N) else None
            if np.isfinite(v["x"]) and v["x"] > 0.7:          # as sd_shared: the latent misses the dominant microstate dynamics
                unresolved = [int(ksel), int(sd.N)]
            info["k"][sid] = int(ksel)
            info["k_range"][sid] = [int(min(within)), int(max(within))]
            info["dimension_curve"][sid] = curve
            info["abstain"][sid] = {"no_compact_state": no_compact, "dimension_unresolved": unresolved, "causal_equivalence_failed": False,
                                    "reason": (f"val y NMSE {v['y']:.3f} vs input-only {y_io:.3f}" if no_compact else "") +
                                              ("; rank curve still improving at kmax" if unresolved else ""),
                                    "val_y_nmse": float(v["y"]), "input_only_val_nmse": float(y_io), "tau": P["tau"]}
            npar = _n_params(P)
            info["n_params"]["encoder"][sid] = npar["encoder"]
            info["n_params"]["readout"][sid] = npar["readout"]
            info["n_params"]["transition"] += npar["transition"]
        info["train_cost"] = {"cpu_s": float(time.time() - t_start), "sim_calls": 0}
        return SDLowRankModel(params, info)
