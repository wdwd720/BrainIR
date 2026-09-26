"""Baselines of the nn family (declared as baselines, PROTOCOL.md section 9; methods review II.4 rows 9, 12, 15).

nn_aelin          autoencoder + linear latent dynamics: MLP encoder (residual on a linear map), z' = z + A z + B u + c, MLP readout
                  and decoder, trained with the same multi-horizon objective and dimension rule as nn_closed.
nn_rssm           recurrent state-space model (PlaNet / Dreamer style, own implementation): deterministic GRU state h (dim 32) and a
                  Gaussian stochastic state s (dim k_nominal); prior p(s | h), filtering posterior q(s | h, x_t); the encoder filters
                  the causal x / u history over a burn-in window. The carried state is (h, s): the reported k is the EFFECTIVE
                  dimension dim(h) + dim(s) (info()["k_nominal"] = dim(s)). A history model, not a closed k_nominal-dim state.
nn_seqbottleneck  z = phi(x_t) in R^k (the bottleneck); a GRU decoder (hidden 64) initialised from z receives the future inputs and
                  event codes and emits y. The decoder carries state beyond z: a NON-CLOSED baseline for predictive sufficiency (1)
                  and compression (5) only. Its reported z path is a learned projection of the decoder state.

Events enter every baseline through the linear part of its observation encoder (no per-neuron parameters): kick code W d~, current
code W c~, silencing code W (m * (rest - x^)) with x^ decoded from the carried state.
"""

from __future__ import annotations

import copy
import math
import time

import numpy as np
import torch
import torch.nn as nn

from ..api import StateMethod, StateModel, register
from . import nn_core as C
from . import nn_fit as F
from .nn_closed import NNClosed


# ------------------------------------------------------------------------------------------------------------ nn_aelin
class NNAELin(NNClosed):
    name = "nn_aelin"
    version = "1"
    default_config = dict(C.DEFAULTS, enc="mlp", f_class="linear", use_J=False)
    model_name = "nn_aelin"


register(NNAELin)


# ------------------------------------------------------------------------------------------------------------ sequence baselines
class SeqNet(nn.Module):
    """Shared container: observation embedding (linear, x~ -> E), decoder (-> x~), readout, and a GRU core. Subclasses define the
    carried state."""

    def __init__(self, n_x, n_u, n_y, E, Hd):
        super().__init__()
        self.n_x, self.n_u, self.n_y, self.E, self.Hd = n_x, n_u, n_y, E, Hd

    def ev_codes(self, W, kick, cur, sil, xh, rest):
        """Event code (B, 3E) through the linear observation map W (E, n_x)."""
        B = xh.shape[0]
        z = xh.new_zeros(B, self.E)
        c = [kick @ W.T if kick is not None else z, cur @ W.T if cur is not None else z,
             (sil * (rest - xh)) @ W.T if sil is not None else z]
        return torch.cat(c, -1)


class RSSMNet(SeqNet):
    def __init__(self, n_x, n_u, n_y, k, E=32, Hd=32, hidden=64):
        super().__init__(n_x, n_u, n_y, E, Hd)
        self.k = k
        self.emb = nn.Linear(n_x, E)
        self.gru = nn.GRUCell(k + n_u + 3 * E, Hd)
        self.prior = nn.Linear(Hd, 2 * k)
        self.post = nn.Sequential(nn.Linear(Hd + E, hidden), nn.SiLU(), nn.Linear(hidden, 2 * k))
        self.ro = C.mlp(Hd + k + n_u, n_y, hidden, 2)
        self.dec = C.mlp(Hd + k, n_x, hidden, 1)

    def init_state(self, B):
        return torch.zeros(B, self.Hd), torch.zeros(B, self.k)

    def advance(self, h, s, u, ev):
        return self.gru(torch.cat([s, u, ev], -1), h)

    def prior_ms(self, h):
        m, lv = self.prior(h).chunk(2, -1)
        return m, lv.clamp(-8, 4)

    def post_ms(self, h, x):
        m, lv = self.post(torch.cat([h, self.emb(x)], -1)).chunk(2, -1)
        return m, lv.clamp(-8, 4)

    def readout(self, h, s, u):
        return self.ro(torch.cat([h, s, u], -1))

    def decode(self, h, s):
        return self.dec(torch.cat([h, s], -1))


class SeqBNNet(SeqNet):
    def __init__(self, n_x, n_u, n_y, k, E=None, Hd=64, hidden=64):
        E = k
        super().__init__(n_x, n_u, n_y, E, Hd)
        self.k = k
        self.enc = C.Encoder(n_x, n_x, k, "mlp", 128)
        self.init = nn.Linear(k, Hd)
        self.gru = nn.GRUCell(n_u + 3 * E, Hd)
        self.proj = nn.Linear(Hd, k)
        self.ro = C.mlp(Hd + n_u, n_y, hidden, 2)
        self.dec = nn.Linear(k, n_x)

    def h0(self, z):
        return torch.tanh(self.init(z))


def _kl(m1, lv1, m2, lv2):
    return 0.5 * (lv2 - lv1 + (lv1.exp() + (m1 - m2) ** 2) / lv2.exp() - 1.0)


class _SeqFitter:
    """Training / validation loops shared by the two sequence baselines."""

    kind = "rssm"

    def __init__(self, norm, d, cfg, k, seed):
        self.norm, self.d, self.cfg, self.k = norm, d, cfg, k
        self.rest = torch.tensor(norm.rest, dtype=torch.float32)
        torch.manual_seed(seed)
        if self.kind == "rssm":
            self.net = RSSMNet(norm.n_x, norm.n_u, norm.n_y, k, Hd=cfg["rssm_hidden"])
        else:
            self.net = SeqBNNet(norm.n_x, norm.n_u, norm.n_y, k, Hd=cfg["seq_hidden"])
            X = np.concatenate([x.numpy() for x in d.X])
            head = C.Head(norm.n_x, norm.n_x, norm.n_u, norm.n_y, k, "mlp", 64, None)
            head.init_pca(X[:: max(1, len(X) // 20000)].astype(np.float64))
            self.net.enc.lin.load_state_dict(head.enc.lin.state_dict())
        T = min(len(x) for x in d.X)
        self.Lb = int(cfg["burn_in"]) if self.kind == "rssm" else 0
        self.H = int(max(4, min(cfg["max_horizon"], round(cfg["horizon_frac"] * T), T - self.Lb - 3)))
        self.tr = [i for i, s in enumerate(d.split) if s != "val"] or list(range(len(d.X)))
        self.va = [i for i, s in enumerate(d.split) if s == "val"] or self.tr[:1]

    # --- run a window: burn-in (posterior) over Lb steps, then open loop over H steps; returns y predictions and aux losses
    def run(self, tis, j0s, H, train=True, gen=None):
        d, net = self.d, self.net
        L = self.Lb + H
        ev, _ = C.dense_events([d.EV[t] for t in tis], j0s, L, self.norm.n_x)
        U = torch.stack([d.U[t][j: j + L] for t, j in zip(tis, j0s)], 1)
        Ui = torch.stack([d.Ui[t][j: j + L + 1] for t, j in zip(tis, j0s)], 1)
        X = torch.stack([d.X[t][j: j + L + 1] for t, j in zip(tis, j0s)], 1)
        B = len(tis)
        ys, xs, zs, kl = [], [], [], 0.0
        if self.kind == "rssm":
            h, s = net.init_state(B)
            m, lv = net.post_ms(h, X[0])
            s = m + (torch.exp(0.5 * lv) * torch.randn(m.shape, generator=gen) if train else 0.0)
            for j in range(L + 1):
                if j > 0:
                    xh = net.decode(h, s)
                    e = net.ev_codes(net.emb.weight, ev["kick"][j - 1] if "kick" in ev else None, ev["current"][j - 1] if "current" in ev else None,
                                     ev["silence"][j - 1] if "silence" in ev else None, xh, self.rest)
                    h = net.advance(h, s, U[j - 1], e)
                    pm, plv = net.prior_ms(h)
                    if j <= self.Lb:
                        m, lv = net.post_ms(h, X[j])
                        kl = kl + torch.clamp(_kl(m, lv, pm, plv).sum(-1).mean(), min=self.cfg["free_nats"])
                        s = m + (torch.exp(0.5 * lv) * torch.randn(m.shape, generator=gen) if train else 0.0)
                    else:
                        s = pm
                ys.append(net.readout(h, s, Ui[j])); xs.append(net.decode(h, s))
            Y = torch.stack(ys)
            return Y[self.Lb:], torch.stack(xs), kl / max(1, self.Lb), None
        # sequence bottleneck
        A0 = X[0] + (self.cfg["sigma_in"] * torch.randn(X[0].shape, generator=gen) if train and self.cfg["sigma_in"] > 0 else 0.0)
        z = net.enc(A0)
        h = net.h0(z)
        for j in range(H + 1):
            if j > 0:
                xh = net.dec(net.proj(h))
                e = net.ev_codes(net.enc.W0(), ev["kick"][j - 1] if "kick" in ev else None, ev["current"][j - 1] if "current" in ev else None,
                                 ev["silence"][j - 1] if "silence" in ev else None, xh, self.rest)
                h = net.gru(torch.cat([U[j - 1], e], -1), h)
            ys.append(net.ro(torch.cat([h, Ui[j]], -1))); zs.append(net.proj(h))
        with torch.no_grad():
            zt = net.enc(X)
            var = zt.reshape(-1, self.k).var(0) + 1e-4
        Z = torch.stack(zs)
        lat = (((Z - zt) ** 2) / var).mean()
        lx = ((net.dec(Z) - X) ** 2).mean()
        ze = net.enc(X[0])
        lnorm = (ze.mean(0) ** 2).sum() + ((ze.var(0) - 1.0) ** 2).sum()
        return torch.stack(ys), None, None, (lat, lx, lnorm)

    def loss(self, tis, j0s, H, gen):
        d = self.d
        Y = torch.stack([d.Y[t][j: j + self.Lb + H + 1] for t, j in zip(tis, j0s)], 1)
        X = torch.stack([d.X[t][j: j + self.Lb + H + 1] for t, j in zip(tis, j0s)], 1)
        yp, xp, kl, aux = self.run(tis, j0s, H, True, gen)
        ly = ((yp - Y[self.Lb:]) ** 2).mean()
        if self.kind == "rssm":
            return ly + self.cfg["lam_x"] * ((xp - X) ** 2).mean() + self.cfg["beta_rssm"] * kl, ly
        lat, lx, lnorm = aux
        return ly + self.cfg["lam_lat"] * lat + self.cfg["lam_x"] * lx + self.cfg["lam_norm"] * lnorm, ly

    def val(self):
        out = []
        with torch.no_grad():
            for t in self.va:
                T = len(self.d.X[t])
                hi = T - self.Lb - self.H - 1
                if hi <= 0:
                    continue
                j0s = list(np.linspace(0, hi, self.cfg["val_starts"]).astype(int))
                yp, _, _, _ = self.run([t] * len(j0s), j0s, self.H, train=False)
                Y = torch.stack([self.d.Y[t][j + self.Lb: j + self.Lb + self.H + 1] for j in j0s], 1)
                out.append(float(((yp[1:] - Y[1:]) ** 2).mean()))
        return np.array(out)

    def fit(self, deadline=None, seed=0):
        cfg = self.cfg
        gen = torch.Generator().manual_seed(seed)
        rng = np.random.default_rng(seed)
        opt = torch.optim.AdamW(self.net.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
        iters = int(cfg["iters"])
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg["lr"], total_steps=iters, pct_start=0.1)
        best, best_state = np.inf, None
        for it in range(iters):
            frac = min(1.0, it / max(1, 0.4 * iters))
            H = int(max(2, round(self.H * (0.125 + 0.875 * frac))))
            tis, j0s = C._sample_windows(self.d, rng, cfg["batch"], self.Lb + H, 0, cfg["ev_frac"], self.tr)
            if self.Lb:   # event-centred windows (the first ones): move the start back so the event falls after the burn-in
                n_ev = int(round(cfg["batch"] * cfg["ev_frac"])) if self.d.ev_starts else 0
                j0s = [max(0, j - self.Lb) if b < n_ev else j for b, j in enumerate(j0s)]
            self.net.train()
            loss, _ = self.loss(tis, j0s, H, gen)
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
            opt.step(); sched.step()
            if (it + 1) % cfg["eval_every"] == 0 or it == iters - 1 or (deadline and time.time() > deadline):
                self.net.eval()
                sc = float(self.val().mean())
                if np.isfinite(sc) and sc < best:
                    best, best_state = sc, copy.deepcopy(self.net.state_dict())
                if deadline and time.time() > deadline:
                    break
        if best_state is not None:
            self.net.load_state_dict(best_state)
        self.net.eval()
        return self.val()


class RSSMFitter(_SeqFitter):
    kind = "rssm"


class SeqBNFitter(_SeqFitter):
    kind = "seq"


class SeqStateModel(StateModel):
    """Executable model of a sequence baseline (RSSM or sequence bottleneck), one system."""

    def __init__(self, kind, net, norm, Lb, k_nominal, meta):
        self.kind, self.net, self.norm, self.Lb, self.k_nominal = kind, net, norm, Lb, k_nominal
        sid = norm.sid
        self.k = {sid: (net.Hd + k_nominal) if kind == "rssm" else k_nominal}
        self.meta = meta
        self.rest = torch.tensor(norm.rest, dtype=torch.float32)
        net.eval()

    def _x(self, x):
        return torch.tensor((np.asarray(x, np.float64) - self.norm.mu_x) / self.norm.sd_x, dtype=torch.float32)

    def _u(self, u):
        return torch.tensor((np.asarray(u, np.float64) - self.norm.mu_u) / self.norm.sd_u, dtype=torch.float32)

    def encode(self, system_id, x_hist, u_hist, dt):
        nm, net = self.norm, self.net
        with torch.no_grad():
            if self.kind == "seq":
                return net.enc(self._x(x_hist[-1])[None])[0].numpy().astype(np.float64)
            s_ = nm.stride
            i = len(x_hist) - 1
            idx = [j for j in range(i - self.Lb * s_, i + 1, s_) if j >= 0]
            h, s = net.init_state(1)
            for n, j in enumerate(idx):
                if n > 0:
                    ug = self._u(np.asarray(u_hist[idx[n - 1]: j]).mean(0))[None]
                    h = net.advance(h, s, ug, torch.zeros(1, 3 * net.E))
                m, _ = net.post_ms(h, self._x(x_hist[j])[None])
                s = m
            return torch.cat([h, s], -1)[0].numpy().astype(np.float64)

    def _step_codes(self, evd, j, xh, W):
        return self.net.ev_codes(W, evd["kick"][j] if "kick" in evd else None, evd["current"][j] if "current" in evd else None,
                                 evd["silence"][j] if "silence" in evd else None, xh, self.rest)

    def rollout(self, system_id, z0, u_future, events, dt):
        nm, net = self.norm, self.net
        s_ = nm.stride
        u_future = np.asarray(u_future, np.float64)
        H = len(u_future) - 1
        n = int(math.ceil(H / s_)) if H > 0 else 0
        need = n * s_ + 1
        uf = u_future if len(u_future) >= need else np.vstack([u_future, np.repeat(u_future[-1:], need - len(u_future), 0)])
        ug = self._u(C._grid_u(uf, s_, n + 1))
        uig = self._u(uf[:: s_][: n + 1])
        evd, _ = C.dense_events([C._grid_events(events, nm, n + 1, dt, s_)], [0], max(1, n), nm.n_x)
        z0 = torch.tensor(np.asarray(z0, np.float64), dtype=torch.float32)[None]
        ys, zs = [], []
        with torch.no_grad():
            if self.kind == "rssm":
                h, s = z0[:, : net.Hd], z0[:, net.Hd:]
                for j in range(n + 1):
                    if j > 0:
                        e = self._step_codes(evd, j - 1, net.decode(h, s), net.emb.weight)
                        h = net.advance(h, s, ug[j - 1][None], e)
                        s = net.prior_ms(h)[0]
                    ys.append(net.readout(h, s, uig[j][None])); zs.append(torch.cat([h, s], -1))
            else:
                h = net.h0(z0)
                for j in range(n + 1):
                    if j > 0:
                        e = self._step_codes(evd, j - 1, net.dec(net.proj(h)), net.enc.W0())
                        h = net.gru(torch.cat([ug[j - 1][None], e], -1), h)
                    ys.append(net.ro(torch.cat([h, uig[j][None]], -1))); zs.append(net.proj(h) if j > 0 else z0)
        Yg = torch.cat(ys).numpy().astype(np.float64) * nm.sd_y + nm.mu_y
        Zg = torch.cat(zs).numpy().astype(np.float64)
        tt = np.arange(H + 1) / s_
        j = np.minimum(np.floor(tt).astype(int), max(0, len(Zg) - 2))
        w = (tt - j)[:, None] if len(Zg) > 1 else np.zeros((H + 1, 1))
        jn = np.minimum(j + 1, len(Zg) - 1)
        Z = Zg[j] * (1 - w) + Zg[jn] * w
        Y = np.maximum(Yg[j] * (1 - w) + Yg[jn] * w, nm.y_min)
        return {"z": Z, "y": Y}

    def readout(self, system_id, z, u):
        nm, net = self.norm, self.net
        z = np.asarray(z, np.float64)
        shp = z.shape[:-1]
        zt = torch.tensor(z.reshape(-1, z.shape[-1]), dtype=torch.float32)
        ut = self._u(np.asarray(u, np.float64).reshape(-1, nm.n_u))
        with torch.no_grad():
            if self.kind == "rssm":
                y = net.readout(zt[:, : net.Hd], zt[:, net.Hd:], ut)
            else:
                y = net.ro(torch.cat([net.h0(zt), ut], -1))
        y = np.maximum(y.numpy().astype(np.float64) * nm.sd_y + nm.mu_y, nm.y_min)
        return y.reshape(shp + (nm.n_y,))

    def supports(self, system_id, event_kind):
        return event_kind in ("kick", "current", "silence")

    def info(self):
        return dict(self.meta)


SEQ_DEFAULTS = dict(C.DEFAULTS, rssm_hidden=32, seq_hidden=64, burn_in=20, free_nats=1.0, beta_rssm=0.1, sigma_in=0.1)


class _SeqMethod(StateMethod):
    version = "1"
    supported_sharing = ("auto", "independent")
    supports_adaptation = False
    fitter = RSSMFitter
    kind = "rssm"
    k_grid = (1, 2, 3, 4, 6, 8, 12, 16)

    def fit(self, train, *, systems, config=None, sim=None, seed=0, log=None):
        C.set_threads(3)
        cfg = {**SEQ_DEFAULTS, **(config or {})}
        if cfg.get("adapt_from") is not None:
            raise NotImplementedError(f"{self.name} does not support encoder-only adaptation")
        sids = sorted({t.system_id for t in train})
        if len(sids) != 1:
            if cfg.get("sharing") in ("shared", "partial"):
                raise NotImplementedError(f"{self.name} fits independent models only")
            from .nn_closed import MultiModel
            models = {s: self.fit([t for t in train if t.system_id == s], systems=systems, config=config, seed=seed, log=log) for s in sids}
            meta = {key: {s: m.meta[key][s] for s, m in models.items()} for key in ("k", "k_range", "abstain")}
            meta["n_params"] = {"encoder": {s: m.meta["n_params"]["encoder"][s] for s, m in models.items()},
                                "transition": int(sum(m.meta["n_params"]["transition"] for m in models.values())),
                                "readout": {s: m.meta["n_params"]["readout"][s] for s, m in models.items()}}
            meta["sharing"] = {"mode": "independent", "verdict": None}
            meta["train_cost"] = {"cpu_s": float(sum(m.meta["train_cost"]["cpu_s"] for m in models.values())), "sim_calls": 0}
            return MultiModel(models, meta)
        sid = sids[0]
        t0 = time.time()
        C.seed_all(seed)
        cfg_p = dict(cfg, use_J=False, lags="none")
        prep = F.prepare(train, systems or {}, cfg_p, log=log)
        norm, d = prep["norms"][sid], prep["datas"][sid]
        t_budget = float(cfg.get("time_budget_s") or (1950.0 if (systems or {}).get(sid, {}).get("mode") == "full" else 900.0))
        fits, curve, status, per_fit = {}, {}, "plateau", None
        grid = [int(cfg["k"])] if cfg.get("k") else [k for k in self.k_grid if k <= max(4, min(16, norm.n_x))]
        for k in grid:
            remaining = t_budget - (time.time() - t0)
            if per_fit is not None and remaining < 1.3 * per_fit:
                status = "time"
                break
            tk = time.time()
            ft = self.fitter(norm, d, cfg, k, seed * 1000 + k)
            sc = ft.fit(deadline=time.time() + max(30.0, remaining - 5.0), seed=seed * 1000 + k)
            per_fit = max(per_fit or 0.0, time.time() - tk)
            curve[k], fits[k] = sc, ft
            if log:
                log(f"{self.name} k={k}: val {float(np.mean(sc)):.4f} ({time.time() - tk:.0f}s)")
            if not cfg.get("k") and F.plateau_reached(curve):
                break
        else:
            if not cfg.get("k"):
                status = "plateau" if F._flat_end(curve) else "no_plateau"
        sel = F.select_k(curve)
        k = sel["k"]
        ft = fits[k]
        abst = F.abstention(sel, status if not cfg.get("k") else "forced", prep["floor"][sid], norm.n_x)
        net = ft.net
        n_enc = sum(p.numel() for n_, p in net.named_parameters() if n_.startswith(("emb", "post", "enc", "dec", "init")))
        n_ro = sum(p.numel() for n_, p in net.named_parameters() if n_.startswith("ro"))
        n_tr = sum(p.numel() for n_, p in net.named_parameters() if n_.startswith(("gru", "prior", "proj")))
        k_eff = (net.Hd + k) if self.kind == "rssm" else net.Hd
        rng_ = [int(v) + (net.Hd if self.kind == "rssm" else 0) for v in sel["range"]]
        meta = {"k": {sid: int(net.Hd + k) if self.kind == "rssm" else int(k)},
                "k_range": {sid: rng_ if self.kind == "rssm" else [int(v) for v in sel["range"]]},
                "k_nominal": {sid: int(k)}, "k_effective": {sid: int(k_eff)},
                "abstain": {sid: abst}, "n_params": {"encoder": {sid: int(n_enc)}, "transition": int(n_tr), "readout": {sid: int(n_ro)}},
                "sharing": {"mode": "independent", "verdict": None},
                "train_cost": {"cpu_s": float(time.time() - t0), "sim_calls": 0, "threads": 3},
                "lipschitz_bound": None, "closed": self.kind == "rssm", "baseline": True, "method": self.name,
                "dimension_curve": {sid: [{"k": int(kk), "val_nmse": float(np.mean(v))} for kk, v in sorted(curve.items())]},
                "val_nmse": {sid: float(np.mean(curve[k]))}, "input_floor": {sid: float(prep["floor"][sid])}}
        if self.kind == "rssm":
            meta["note"] = ("k = k_effective = dim(h) + dim(s); the deterministic GRU state h is carried between steps and counted. "
                            "k_nominal = dim(s).")
        else:
            meta["note"] = ("NON-CLOSED baseline: the GRU decoder (hidden 64) carries state beyond z; k is the bottleneck dimension "
                            "of the encoder only (k_effective = decoder hidden size). Not a closure test.")
            meta["abstain"][sid]["causal_equivalence_failed"] = True
            meta["abstain"][sid]["reason"] = (meta["abstain"][sid]["reason"] + "; " if meta["abstain"][sid]["reason"] else "") + \
                "non-closed decoder: z is not a Markov state"
        return SeqStateModel(self.kind, net, norm, ft.Lb, k, meta)


class NNRSSM(_SeqMethod):
    name = "nn_rssm"
    fitter = RSSMFitter
    kind = "rssm"
    k_grid = (1, 2, 4, 8, 16)


class NNSeqBottleneck(_SeqMethod):
    name = "nn_seqbottleneck"
    fitter = SeqBNFitter
    kind = "seq"


register(NNRSSM)
register(NNSeqBottleneck)
