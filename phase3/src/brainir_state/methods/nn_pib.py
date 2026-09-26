"""nn_pred_bottleneck: predictive information bottleneck on the closed latent model of nn_core.

Stochastic encoder q(z | x_t) = N(phi(x_t), diag s^2(x_t)) with prior N(0, I). Objective per window (z_0 drawn from q):

    L = E_q[ sum_h ||g(f^h(z_0), u) - y_{t+h}||^2 ]                (future readout under the future inputs)
      + lam_lat sum_h ||f^h(z_0) - sg(phi(x_{t+h}))||^2 / Var      (future latent under the future inputs)
      + lam_x recon + beta * KL(q(z | x_t) || N(0, I))               (rate: I(z; x) upper bound)

i.e. the Lagrangian of  min I(x_t; z_t)  s.t. z_t predicts (y_{t+1:t+H}, z_{t+1:t+H}) given u_{t:t+H}. Dimensions whose average KL
collapses to the prior carry no information and are pruned.

Dimension rule (generic): fit at k_max = min(12, max(4, N_obs)) for beta in (0.001, 0.003, 0.01, 0.03); record the validation score
e(beta) and the number of ACTIVE dimensions a(beta) = #{i : mean_val KL_i > 0.1 nat}. beta* = the largest beta with
e(beta) <= min e + tol (tol as in nn_fit); k = a(beta*). The final model is refitted at k = a(beta*) with beta*. Reported range: the
active counts of all betas within the tolerance band. Abstention: "no compact state" if a(beta*) = k_max (every dimension is
still used at the tolerance-selected rate) or if the latent explains less than half of the input-only floor (nn_fit.abstention).
"""

from __future__ import annotations

import time

import numpy as np
import torch

from ..api import register
from . import nn_core as C
from . import nn_fit as F
from .nn_closed import NNClosed, _meta

BETAS = (0.001, 0.003, 0.01, 0.03)
KL_ACTIVE = 0.1


def active_kl(net: C.NNNet, sid: str, d: C.SysData) -> np.ndarray:
    """Mean KL per latent dimension on the validation grid points."""
    idx = [i for i, s in enumerate(d.split) if s == "val"] or list(range(len(d.X)))
    A = torch.cat([C.feat_rows(d, i, torch.arange(len(d.X[i]))) for i in idx])
    enc = net.head(sid).enc
    with torch.no_grad():
        mu = enc(A)
        lv = enc.logv(A).clamp(-12.0, 4.0)
        kl = 0.5 * (mu ** 2 + lv.exp() - 1.0 - lv)
    return kl.mean(0).numpy()


class NNPredBottleneck(NNClosed):
    name = "nn_pred_bottleneck"
    version = "1"
    default_config = dict(C.DEFAULTS, stochastic=True, lam_norm=0.0, beta=0.01)
    model_name = "nn_pred_bottleneck"

    def _fit_joint(self, train, systems, cfg, seed, sids, sharing, t_budget, log=None):
        if cfg.get("k"):
            return super()._fit_joint(train, systems, cfg, seed, sids, sharing, t_budget, log)
        t0 = time.time()
        prep = F.prepare([t for t in train if t.system_id in sids], systems, cfg, log=log)
        n_min = min(prep["norms"][s].n_x for s in sids)
        k_max = int(min(12, max(4, n_min)))
        curve, act, fits = {}, {}, {}
        per_fit = None
        for b in BETAS:
            remaining = t_budget - (time.time() - t0)
            if per_fit is not None and remaining < 2.3 * per_fit:       # keep time for the final refit
                break
            tb = time.time()
            net, _, per = F.fit_k(prep, sids, k_max, dict(cfg, beta=b, iters=cfg.get("sweep_iters", cfg["iters"])), seed, sharing, deadline=time.time() + max(30.0, remaining / 2))
            per_fit = max(per_fit or 0.0, time.time() - tb)
            curve[b] = np.concatenate([per[s] for s in sids])
            kl = np.max([active_kl(net, s, prep["datas"][s]) for s in sids], axis=0)
            act[b] = int(max(1, (kl > KL_ACTIVE).sum()))
            fits[b] = (net, per, kl)
            if log:
                log(f"beta={b}: val {float(np.mean(curve[b])):.4f} active {act[b]} kl {np.round(np.sort(kl)[::-1], 2).tolist()}")
        means = {b: float(np.mean(v)) for b, v in curve.items()}
        b_best = min(means, key=means.get)
        tol = F.tolerance(curve, b_best)
        ok = [b for b in curve if means[b] <= means[b_best] + tol[b]]
        b_sel = max(ok)
        k = act[b_sel]
        band = [b for b in curve if means[b] <= means[b_best] + 2 * tol[b]]
        rng = [int(min(act[b] for b in band)), int(max(act[b] for b in ok))]
        remaining = t_budget - (time.time() - t0)
        cfg_f = dict(cfg, beta=b_sel)
        if k == k_max:
            net, per = fits[b_sel][0], fits[b_sel][1]
        else:
            net, _, per = F.fit_k(prep, sids, k, cfg_f, seed, sharing, deadline=time.time() + max(30.0, remaining - 10.0))
        status = "no_plateau" if k == k_max else "plateau"
        sel = {"k": k, "range": rng, "means": {k: float(np.mean(np.concatenate([per[s] for s in sids])))}}
        abst = {s: F.abstention(sel, status, prep["floor"][s], prep["norms"][s].n_x) for s in sids}
        for s in sids:
            if k == k_max:
                abst[s]["reason"] = (abst[s]["reason"] + "; " if abst[s]["reason"] else "") + "all bottleneck dimensions active at k_max"
        model = C.NNStateModel(net, {s: prep["norms"][s] for s in sids}, k, {})
        model.meta = _meta(self.model_name, net, sids, k, sel, {}, status, abst, sharing, time.time() - t0, cfg,
                           extra={"stride": {s: prep["norms"][s].stride for s in sids},
                                  "val_nmse": {s: float(np.mean(per[s])) for s in sids},
                                  "input_floor": {s: float(prep["floor"][s]) for s in sids},
                                  "beta_curve": [{"beta": b, "val_nmse": means[b], "active": act[b]} for b in sorted(curve)],
                                  "beta": b_sel, "k_max": k_max,
                                  "dimension_rule": "active KL dims (> 0.1 nat) at the largest beta within tolerance of the best val"})
        return model


register(NNPredBottleneck)
