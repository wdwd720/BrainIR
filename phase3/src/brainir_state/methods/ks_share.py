"""Multi-system latent training for the ks_* methods: one latent law f shared by several systems, system-specific encoders /
readouts / decoders (support sharing, goal4 section 17-19), and encoder-only adaptation with f frozen.

    z_{t+1} = f(z_t, u_t)                  shared dynamics module (Koopman: z K^T + u B^T + c with K = exp(J - R) stable;
                                           SINDy: z + Theta(z, u) (W * mask) + w0 with the E-SINDy support as mask)
    z_t = enc_s(q_t^s)                     per-system encoder on the system's own predictive coordinates q^s
    y_t = ro_s([z_t, u_t])                 per-system linear readout
    q^_t = dec_s(z_t)                      per-system decoder (anti-collapse, event handling)

Loss per system window (horizon curriculum): readout error / var(y) + lambda_lat latent consistency + lambda_rec reconstruction
+ lambda_norm normalisation (mean z ~ 0 and cov z ~ the reference covariance: every system must use the SAME region of latent space,
so a flexible f cannot represent unrelated systems in disjoint regions).
"""

from __future__ import annotations

import numpy as np

from . import ks_core as C


def _torch():
    import torch
    return torch


def stable_init(K, B, c):
    """Map a least-squares operator K into the stable parameterisation K = exp(J - R): A = log K (real part), J = skew part,
    R = the PSD part of -(A + A^T)/2; returns (S, L, B, c) with S - S^T = J and L L^T = R."""
    from scipy.linalg import logm
    k = K.shape[0]
    try:
        A = np.real(logm(K + 1e-9 * np.eye(k)))
        if not np.all(np.isfinite(A)):
            raise ValueError
    except Exception:
        A = K - np.eye(k)
    J = 0.5 * (A - A.T)
    Rs = -0.5 * (A + A.T)
    w, V = np.linalg.eigh(Rs)
    L = V * np.sqrt(np.clip(w, 0.0, None))[None, :]
    return 0.5 * J, L, B, c


def make_koopman_dyn(k, n_u, seed, init=None):
    torch = _torch()

    class KoopmanDyn(torch.nn.Module):
        def __init__(self):
            super().__init__()
            g = torch.Generator().manual_seed(seed)
            self.S = torch.nn.Parameter(0.01 * torch.randn(k, k, generator=g))
            self.L = torch.nn.Parameter(0.01 * torch.randn(k, k, generator=g))
            self.B = torch.nn.Parameter(torch.zeros(k, n_u))
            self.c = torch.nn.Parameter(torch.zeros(k))
            self.eps = 1e-4
            if init is not None:
                with torch.no_grad():
                    for par, val in zip((self.S, self.L, self.B, self.c), init):
                        par.copy_(torch.tensor(np.asarray(val).reshape(par.shape), dtype=torch.float32))

        def K(self):
            A = (self.S - self.S.T) - self.L @ self.L.T - self.eps * torch.eye(k)
            return torch.matrix_exp(A)

        def forward(self, z, u, K=None):
            K = self.K() if K is None else K
            return z @ K.T + u @ self.B.T + self.c

        def export(self):
            with torch.no_grad():
                return {"K": self.K().numpy().astype(np.float64), "B": self.B.numpy().astype(np.float64),
                        "c": self.c.numpy().astype(np.float64)}

    return KoopmanDyn()


def make_poly_dyn(lib: C.PolyLibrary, W: np.ndarray, w0: np.ndarray, mask: np.ndarray):
    torch = _torch()

    class PolyDyn(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.idx = torch.tensor(lib.idx, dtype=torch.long)
            self.W = torch.nn.Parameter(torch.tensor(W, dtype=torch.float32))
            self.w0 = torch.nn.Parameter(torch.tensor(w0, dtype=torch.float32))
            self.register_buffer("mask", torch.tensor(mask, dtype=torch.float32))

        def forward(self, z, u, K=None):
            V = torch.cat([torch.ones_like(z[..., :1]), z, u], -1)
            th = V[..., self.idx[:, 0]]
            for d in range(1, self.idx.shape[1]):
                th = th * V[..., self.idx[:, d]]
            return z + th @ (self.W * self.mask) + self.w0

        def export(self):
            with torch.no_grad():
                return {"W": (self.W * self.mask).numpy().astype(np.float64), "w0": self.w0.numpy().astype(np.float64)}

    return PolyDyn()


def make_encoder(r, k, hidden, seed, init_lin=None):
    """Linear (+ residual tanh-MLP when hidden > 0) map q -> z."""
    torch = _torch()
    torch.manual_seed(seed)
    lin = torch.nn.Linear(r, k)
    if init_lin is not None:
        with torch.no_grad():
            lin.weight.copy_(torch.tensor(init_lin[0].T, dtype=torch.float32))
            lin.bias.copy_(torch.tensor(init_lin[1], dtype=torch.float32))
    if hidden <= 0:
        return torch.nn.ModuleDict({"lin": lin})
    mlp = torch.nn.Sequential(torch.nn.Linear(r, hidden), torch.nn.Tanh(), torch.nn.Linear(hidden, k))
    torch.nn.init.zeros_(mlp[2].weight)
    torch.nn.init.zeros_(mlp[2].bias)
    return torch.nn.ModuleDict({"lin": lin, "mlp": mlp})


def enc_apply(enc, q):
    z = enc["lin"](q)
    if "mlp" in enc:
        z = z + enc["mlp"](q)
    return z


def enc_export(enc):
    with _torch().no_grad():
        out = {"We": enc["lin"].weight.numpy().T.astype(np.float64), "be": enc["lin"].bias.numpy().astype(np.float64)}
        if "mlp" in enc:
            m = enc["mlp"]
            out["enc_mlp"] = [np.asarray(a, np.float64) for a in (m[0].weight.numpy().T, m[0].bias.numpy(), m[2].weight.numpy().T,
                                                                   m[2].bias.numpy())]
        return out


def make_decoder(k, r, hidden, seed):
    torch = _torch()
    torch.manual_seed(seed + 1)
    return torch.nn.Sequential(torch.nn.Linear(k, hidden), torch.nn.Tanh(), torch.nn.Linear(hidden, r))


def dec_export(dec):
    with _torch().no_grad():
        return [np.asarray(a, np.float64) for a in (dec[0].weight.numpy().T, dec[0].bias.numpy(), dec[2].weight.numpy().T, dec[2].bias.numpy())]


def train_latent(systems: list[dict], dyn, steps: int, seed: int, H: int, batch: int = 64, lr: float = 3e-3, lam_lat: float = 0.5,
                 lam_rec: float = 0.1, lam_norm: float = 0.0, train_dyn: bool = True, z_cov_target=None, h0: int = 8):
    """systems[i]: {"Qs": [np (T, r)], "trajs": [...], "prep": SystemPrep, "enc": ModuleDict, "dec": Module | None,
    "ro": nn.Linear(k + n_u, n_y), "train_enc": bool}. Trains in place. Returns the loss history (per 50 steps)."""
    torch = _torch()
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    data = []
    for s in systems:
        prep = s["prep"]
        data.append({"Q": [torch.tensor(Q, dtype=torch.float32) for Q in s["Qs"]],
                     "U": [torch.tensor(t.u, dtype=torch.float32) for t in s["trajs"]],
                     "Y": [torch.tensor((t.y - prep.y_mu) / prep.y_sd, dtype=torch.float32) for t in s["trajs"]],
                     "runs": [C.event_free_after(C.free_mask(t)) for t in s["trajs"]], "wins": {}})
    params = []
    if train_dyn:
        params += list(dyn.parameters())
    for s in systems:
        if s.get("train_enc", True):
            params += list(s["enc"].parameters())
        if s.get("dec") is not None:
            params += list(s["dec"].parameters())
        params += list(s["ro"].parameters())
    opt = torch.optim.Adam(params, lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, max(1, steps))
    zc = None if z_cov_target is None else torch.tensor(z_cov_target, dtype=torch.float32)
    hist = []
    for it in range(steps):
        si = it % len(systems)
        s, d = systems[si], data[si]
        frac = min(1.0, it / max(1, 0.6 * steps))
        h = int(round(h0 * (H / h0) ** frac)) if H > h0 else H
        if h not in d["wins"]:
            w = []
            for i, (Q, run) in enumerate(zip(d["Q"], d["runs"])):
                st = np.flatnonzero(run[: max(0, len(Q) - h)] >= h)
                w += [(i, int(x)) for x in st]
            d["wins"][h] = w
        wins = d["wins"][h]
        if not wins:
            continue
        sel = torch.randint(0, len(wins), (min(batch, len(wins)),), generator=g).tolist()
        q = torch.stack([d["Q"][wins[i][0]][wins[i][1]: wins[i][1] + h + 1] for i in sel])
        u = torch.stack([d["U"][wins[i][0]][wins[i][1]: wins[i][1] + h + 1] for i in sel])
        y = torch.stack([d["Y"][wins[i][0]][wins[i][1]: wins[i][1] + h + 1] for i in sel])
        zt = enc_apply(s["enc"], q)
        K = dyn.K() if hasattr(dyn, "K") else None
        z = zt[:, 0]
        zs = [z]
        for j in range(h):
            z = dyn(z, u[:, j], K)
            zs.append(z)
        zr = torch.stack(zs, 1)
        yp = s["ro"](torch.cat([zr, u], -1))
        k = zt.shape[-1]
        zf = zt.reshape(-1, k)
        zvar = zf.detach().var(0) + 1e-3
        loss = ((yp - y) ** 2).mean() + lam_lat * (((zr[:, 1:] - zt[:, 1:].detach()) ** 2) / zvar).mean()
        if s.get("dec") is not None:
            loss = loss + lam_rec * (((s["dec"](zr) - q) ** 2).mean() + ((s["dec"](zt[:, 0]) - q[:, 0]) ** 2).mean())
        if lam_norm > 0 and zc is not None:
            m = zf.mean(0)
            cv = (zf - m).T @ (zf - m) / max(1, len(zf) - 1)
            loss = loss + lam_norm * ((m ** 2).sum() + ((cv - zc) ** 2).sum())
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 5.0)
        opt.step()
        sched.step()
        if it % 50 == 0:
            hist.append(float(loss.detach()))
    return hist


def readout_export(ro, prep, k):
    with _torch().no_grad():
        W = ro.weight.numpy().astype(np.float64)
        b = ro.bias.numpy().astype(np.float64)
    return {"Cy": (W[:, :k] * prep.y_sd[:, None]).T, "Dy": (W[:, k:] * prep.y_sd[:, None]).T, "ey": b * prep.y_sd + prep.y_mu}


def make_fixed_linear_dyn(K, B, c):
    """Frozen linear latent law z K^T + u B^T + c (encoder-only adaptation)."""
    torch = _torch()

    class FixedDyn(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("Kf", torch.tensor(K, dtype=torch.float32))
            self.register_buffer("Bf", torch.tensor(B, dtype=torch.float32))
            self.register_buffer("cf", torch.tensor(c, dtype=torch.float32))

        def K(self):
            return self.Kf

        def forward(self, z, u, K=None):
            return z @ self.Kf.T + u @ self.Bf.T + self.cf

        def export(self):
            return {"K": np.asarray(K, np.float64), "B": np.asarray(B, np.float64), "c": np.asarray(c, np.float64)}

    return FixedDyn()
