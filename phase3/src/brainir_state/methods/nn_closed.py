"""nn_closed: closed latent dynamics, "encode once, roll out" (family F1 of the methods review; tournament families D / F).

    z_t = phi_s(x_t [, causal lags])     f: linear | residual MLP | latent ODE (fixed-step RK4)     y_t = g_s(z_t, u_t)

trained with the multi-horizon open-loop readout loss plus latent self-consistency f^h(phi(x_t)) ~ sg(phi(x_{t+h})), a low-weight
reconstruction of x, latent normalisation and noise injection (nn_core). k is chosen by the plateau rule of nn_fit over an
ascending k-sweep; abstention by nn_fit.abstention. Sharing: 'independent', 'shared' (one f, system-specific encoders / readouts),
'partial' (shared f plus a small system-specific residual transition), 'auto' (shared if non-inferior on validation); encoder-only
adaptation with a frozen f ('adapt_from'). See notes/nn_closed.md.
"""

from __future__ import annotations

import copy
import time

import numpy as np
import torch

from ..api import StateMethod, StateModel, register
from . import nn_core as C
from . import nn_fit as F


def _budget(systems: dict, sids: list, cfg: dict) -> float:
    """Time budget (s) for the whole fit, below the contract's limits (20 min synthetic system, 40 min real full / shared)."""
    if cfg.get("time_budget_s"):
        return float(cfg["time_budget_s"])
    big = len(sids) > 1 or any((systems.get(s) or {}).get("kind") == "real" and (systems.get(s) or {}).get("mode") == "full" for s in sids)
    return 2100.0 if big else 1000.0


class MultiModel(StateModel):
    """Independent per-system models behind one StateModel (sharing='independent' on several systems)."""

    def __init__(self, models: dict, meta: dict):
        self.models = models
        self.k = {s: m.k[s] for s, m in models.items()}
        self.meta = meta

    def encode(self, system_id, x_hist, u_hist, dt):
        return self.models[system_id].encode(system_id, x_hist, u_hist, dt)

    def rollout(self, system_id, z0, u_future, events, dt):
        return self.models[system_id].rollout(system_id, z0, u_future, events, dt)

    def readout(self, system_id, z, u):
        return self.models[system_id].readout(system_id, z, u)

    def supports(self, system_id, event_kind):
        return self.models[system_id].supports(system_id, event_kind)

    def lift(self, system_id, x, z, delta_z, n_candidates=3):
        return self.models[system_id].lift(system_id, x, z, delta_z, n_candidates)

    def info(self):
        return dict(self.meta)


def _meta(name, net: C.NNNet, sids, k, sel, curve, status, abst, sharing, t_fit, cfg, extra=None):
    enc = {s: C.n_params(net.head(s).enc) + C.n_params(net.head(s).dec_lin) + C.n_params(net.head(s).dec)
           + (3 if net.head(s).gain_mode == "scalar" else 3 * int(net.head(s).G_cur.numel())) for s in sids}
    ro = {s: C.n_params(net.head(s).ro_lin) + (C.n_params(net.head(s).ro) if net.head(s).ro is not None else 0) for s in sids}
    fkeys = sorted({net.f_of[s] for s in sids})
    tr = int(sum(sum(p.numel() for p in net.fs[kk].parameters()) for kk in fkeys))
    meta = {"k": {s: int(k) for s in sids},
            "k_range": {s: list(sel["range"]) if sel else [int(k), int(k)] for s in sids},
            "abstain": {s: abst.get(s, {"no_compact_state": False, "dimension_unresolved": None, "causal_equivalence_failed": False,
                                        "reason": ""}) for s in sids},
            "n_params": {"encoder": enc, "transition": tr, "readout": ro},
            "sharing": {"mode": sharing, "verdict": None},
            "train_cost": {"cpu_s": float(t_fit), "sim_calls": 0, "threads": 3},
            "lipschitz_bound": C.lipschitz_bound(net),
            "method": name, "closed": True, "f_class": cfg["f_class"], "encoder": cfg["enc"],
            "dimension_rule": "smallest k with val error <= best + max(0.1 best, 0.005, SE); plateau stop (nn_fit)",
            "dimension_curve": {s: [{"k": int(kk), "val_nmse": float(np.mean(v))} for kk, v in sorted(curve.items())] for s in sids} if curve else {},
            "sweep_status": status,
            "stride": {s: int(net_stride) for s, net_stride in (extra or {}).get("stride", {}).items()}}
    if extra:
        meta.update({kk: v for kk, v in extra.items() if kk != "stride"})
    return meta


class NNClosed(StateMethod):
    name = "nn_closed"
    version = "1"
    default_config = dict(C.DEFAULTS)
    supported_sharing = ("auto", "independent", "shared", "partial")
    supports_adaptation = True
    model_name = "nn_closed"

    # ---- one group of systems fitted jointly (a single system, or shared dynamics)
    def _fit_joint(self, train, systems, cfg, seed, sids, sharing, t_budget, log=None):
        t0 = time.time()
        prep = F.prepare([t for t in train if t.system_id in sids], systems, cfg, log=log)
        abst, curve, sel, status = {}, {}, None, "forced"
        if cfg.get("k"):
            k = int(cfg["k"])
            net, _, per = F.fit_k(prep, sids, k, cfg, seed, sharing, deadline=t0 + t_budget, log=log)
            curve = {k: np.mean([per[s] for s in sids], axis=0) if len({len(per[s]) for s in sids}) == 1 else np.concatenate(list(per.values()))}
        else:
            if cfg.get("sweep", "independent") == "paired":
                sel, net, per, status = F.sweep_paired(prep, sids, cfg, seed, sharing, t_budget=0.85 * (t_budget - (time.time() - t0)),
                                                       log=log)
                k = sel["k"]
                curve = {st["k_to"]: [st["val_grown"]] for st in sel["steps"]}
            else:
                sel, fits, curve, status = F.sweep(prep, sids, cfg, seed, sharing, t_budget=0.9 * (t_budget - (time.time() - t0)), log=log)
                k = sel["k"]
                net, per = fits[k]
                sel["steps"] = []
            if cfg.get("refine_iters", 0) > 0 and t_budget - (time.time() - t0) > 90:
                per = F.refine(net, prep, sids, cfg, seed, deadline=t0 + t_budget - 10, log=log)
            for s in sids:
                abst[s] = F.abstention(sel, status, prep["floor"][s], prep["norms"][s].n_x)
        model = C.NNStateModel(net, {s: prep["norms"][s] for s in sids}, k, {})
        model.meta = _meta(self.model_name, net, sids, k, sel, curve, status, abst, sharing, time.time() - t0, cfg,
                           extra={"stride": {s: prep["norms"][s].stride for s in sids},
                                  "val_nmse": {s: float(np.mean(per[s])) for s in sids},
                                  "input_floor": {s: float(prep["floor"][s]) for s in sids},
                                  "sweep_steps": sel["steps"] if sel else []})
        return model

    def _adapt(self, train, systems, cfg, seed, base, t_budget, log=None):
        """Encoder-only adaptation: new heads for the systems in train, the transition law of `base` frozen."""
        t0 = time.time()
        sids = sorted({t.system_id for t in train})
        base_net = base.net if isinstance(base, C.NNStateModel) else None
        if base_net is None:
            raise NotImplementedError("adapt_from must be an nn_closed / nn_pred_bottleneck model")
        k = int(next(iter(base.k.values())))
        fkey = sorted(base_net.fs)[0]
        frozen = {"shared": copy.deepcopy(base_net.fs[fkey])}
        prep = F.prepare(train, systems, cfg, log=log)
        net, _, per = F.fit_k(prep, sids, k, cfg, seed, "shared", deadline=t0 + t_budget, frozen_f=frozen, log=log)
        model = C.NNStateModel(net, {s: prep["norms"][s] for s in sids}, k, {})
        model.meta = _meta(self.model_name, net, sids, k, None, {}, "adapted", {}, "adapted", time.time() - t0, cfg,
                           extra={"stride": {s: prep["norms"][s].stride for s in sids},
                                  "val_nmse": {s: float(np.mean(per[s])) for s in sids}})
        model.meta["train_cost"]["adaptation"] = True
        return model

    def fit(self, train, *, systems, config=None, sim=None, seed=0, log=None):
        C.set_threads(3)
        cfg = {**C.DEFAULTS, **self.default_config, **(config or {})}
        sharing = cfg.get("sharing") or "auto"
        systems = systems or {}
        sids = sorted({t.system_id for t in train})
        t_budget = _budget(systems, sids, cfg)
        C.seed_all(seed)
        if cfg.get("adapt_from") is not None:
            return self._adapt(train, systems, cfg, seed, cfg["adapt_from"], t_budget, log)
        if len(sids) == 1:
            return self._fit_joint(train, systems, cfg, seed, sids, "independent", t_budget, log)
        if sharing in ("shared", "partial"):
            m = self._fit_joint(train, systems, cfg, seed, sids, "shared", t_budget, log)
            m.meta["sharing"] = {"mode": sharing, "verdict": None}
            return m
        # independent models (and, for 'auto', the shared model with a validation comparison)
        per_budget = t_budget / (len(sids) + (1 if sharing == "auto" else 0))
        models = {s: self._fit_joint(train, systems, cfg, seed, [s], "independent", per_budget, log) for s in sids}
        indep = MultiModel(models, {})
        meta = {key: {} for key in ("k", "k_range", "abstain")}
        for s, m in models.items():
            for key in meta:
                meta[key][s] = m.meta[key][s]
        meta["n_params"] = {"encoder": {s: models[s].meta["n_params"]["encoder"][s] for s in sids},
                            "transition": int(sum(m.meta["n_params"]["transition"] for m in models.values())),
                            "readout": {s: models[s].meta["n_params"]["readout"][s] for s in sids}}
        meta["train_cost"] = {"cpu_s": float(sum(m.meta["train_cost"]["cpu_s"] for m in models.values())), "sim_calls": 0}
        meta["sharing"] = {"mode": "independent", "verdict": None}
        meta["val_nmse"] = {s: models[s].meta["val_nmse"][s] for s in sids}
        meta["lipschitz_bound"] = max(m.meta["lipschitz_bound"] for m in models.values())
        indep.meta = meta
        if sharing == "independent":
            return indep
        # auto: shared f at the largest independent k; supported if non-inferior on validation for every system
        k = max(meta["k"][s] for s in sids)
        cfg2 = dict(cfg, k=k)
        shared = self._fit_joint(train, systems, cfg2, seed, sids, "shared", per_budget, log)
        ok = all(shared.meta["val_nmse"][s] <= meta["val_nmse"][s] * 1.1 + 0.005 for s in sids)
        fewer = shared.meta["n_params"]["transition"] < meta["n_params"]["transition"]
        verdict = "supported" if ok and fewer else "rejected"
        chosen = shared if verdict == "supported" else indep
        chosen.meta["sharing"] = {"mode": "shared" if verdict == "supported" else "independent", "verdict": verdict,
                                  "val_shared": shared.meta["val_nmse"], "val_independent": meta["val_nmse"]}
        return chosen


register(NNClosed)
