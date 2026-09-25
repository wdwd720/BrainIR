"""Observation maps: how a Model's coordinates are carried by neurons (E), read back by synapses (D), and recorded.

`make_implementation(model, spec, rng)` builds an Implementation from a spec dict:

    n_core        neurons carrying the latent z
    code          dense | sparse | redundant | distributed | rotation | identity      (z -> core neurons)
    phi           identity | tanh | logistic | mixed                                    (activation, per neuron)
    mixed_sign    bool: signed tuning (else non-negative tuning + positive baselines)
    core_gain     per-latent-coordinate gain (weakly represented coordinates for the non-Markov trap)
    causal_frac   fraction of core neurons that feed the population signal (the rest only carry it: E != 0, D = 0)
    blocks        per auxiliary block: {"n": own neurons, "code": dense|sparse|ramp, "gain", "mix": gain of mixing into
                  the core neurons (0 = none)}
    obs_noise     observation noise sd relative to each neuron's typical modulation
    priv_noise    private noise (stationary sd relative to modulation)
    frac_unobserved  fraction of latent/nuisance neurons not recorded
    lam           leak / manifold attraction rate (1/s)
"""

from __future__ import annotations

import numpy as np

from .core import PHI_ID, PHI_LOGI, PHI_TANH, Implementation, Phi

PHI_CODES = {"identity": PHI_ID, "tanh": PHI_TANH, "logistic": PHI_LOGI}


def _core_matrix(rng, code, n, k, mixed_sign):
    if code == "identity":
        assert n == k
        return np.eye(k)
    if code == "rotation":
        assert n == k
        Q, _ = np.linalg.qr(rng.standard_normal((k, k)))
        return Q * np.sqrt(k) * 0.5
    if code == "dense":
        G = rng.standard_normal((n, k))
        if not mixed_sign:
            G = np.abs(G) + 0.1
    elif code == "sparse":
        G = np.zeros((n, k))
        for i in range(n):
            m = 1 if (rng.random() < 0.7 or k == 1) else 2
            cols = rng.choice(k, m, replace=False) if i >= k else [i % k]
            for c in cols:
                G[i, c] = rng.uniform(0.5, 1.5) * (rng.choice([-1, 1]) if mixed_sign else 1)
    elif code == "redundant":
        G = np.zeros((n, k))
        groups = np.array_split(rng.permutation(n), k)
        for c, grp in enumerate(groups):
            w = rng.uniform(0.8, 1.2) * (rng.choice([-1, 1]) if mixed_sign else 1)
            G[grp, c] = w * (1 + 0.05 * rng.standard_normal(len(grp)))
    elif code == "distributed":
        G = rng.choice([-1.0, 1.0], size=(n, k)) * rng.uniform(0.8, 1.2, (n, k))
    else:
        raise ValueError(code)
    norms = np.linalg.norm(G, axis=1, keepdims=True)
    return G / np.maximum(norms, 1e-9) * rng.uniform(0.6, 1.4, (n, 1))


def _left_inverse(E, supports):
    """D with D E = I and D[c, j] = 0 for j outside supports[c] (least-norm per row)."""
    N, K = E.shape
    D = np.zeros((K, N))
    for c in range(K):
        S = np.asarray(sorted(supports[c]))
        Es = E[S]
        cols = np.flatnonzero(np.abs(Es).sum(0) > 0)
        if c not in cols:
            raise ValueError(f"coordinate {c} not carried by its support")
        M = Es[:, cols]
        if np.linalg.matrix_rank(M) < len(cols):
            raise ValueError(f"support of coordinate {c} is rank deficient")
        P = np.linalg.pinv(M)
        D[c, S] = P[list(cols).index(c)]
    return D


def make_implementation(model, spec: dict, rng: np.random.Generator, coord_scale: np.ndarray | None = None) -> Implementation:
    k, K = model.k, model.K
    spec = dict(spec)
    n_core = int(spec.get("n_core", 20))
    code = spec.get("code", "dense")
    mixed = bool(spec.get("mixed_sign", True))
    phi_kind = spec.get("phi", "identity")
    lam = float(spec.get("lam", 30.0))
    blocks_spec = list(spec.get("blocks", [{}] * len(model.blocks)))
    assert len(blocks_spec) == len(model.blocks)
    if coord_scale is None:
        coord_scale = np.ones(K)

    # ---- neurons and E
    n_blocks = [int(bs.get("n", 0)) for bs in blocks_spec]
    N = n_core + sum(n_blocks)
    E = np.zeros((N, K))
    roles = ["latent"] * n_core
    E[:n_core, :k] = _core_matrix(rng, code, n_core, k, mixed)
    gain = np.asarray(spec.get("core_gain", 1.0), float) * np.ones(k)
    E[:n_core, :k] *= gain
    # a neuron's typical modulation: row norm weighted by the coordinates' typical amplitude
    off = n_core
    ramp_rows = []
    for blk, bs, nb in zip(model.blocks, blocks_spec, n_blocks):
        sl = blk.sl
        g = float(bs.get("gain", 1.0))
        bcode = bs.get("code", "dense")
        rows = np.arange(off, off + nb)
        if nb:
            if bcode == "ramp":
                E[rows, sl.start] = rng.uniform(1.5, 3.0, nb)
                ramp_rows += list(rows)
            elif bcode == "sparse" or blk.dim == 1:
                for r in rows:
                    E[r, sl.start + rng.integers(blk.dim)] = g * rng.uniform(0.6, 1.4) * (rng.choice([-1, 1]) if mixed else 1)
                if blk.dim > 1:  # make sure every block coordinate is carried
                    for c in range(blk.dim):
                        E[rows[c % nb], sl] = 0.0
                        E[rows[c % nb], sl.start + c] = g * rng.uniform(0.6, 1.4)
            else:
                G = rng.standard_normal((nb, blk.dim))
                if not mixed:
                    G = np.abs(G) + 0.1
                E[rows, sl] = g * G / np.linalg.norm(G, axis=1, keepdims=True) * rng.uniform(0.6, 1.4, (nb, 1))
        mix = float(bs.get("mix", 0.0))
        if mix:
            G = rng.standard_normal((n_core, blk.dim)) * mix / np.sqrt(blk.dim)
            E[:n_core, sl] += G
        roles += [blk.role] * nb
        off += nb

    # ---- supports and D
    causal_frac = float(spec.get("causal_frac", 1.0))
    core = np.arange(n_core)
    for _ in range(50):
        causal = np.sort(rng.choice(n_core, max(k + 2, int(round(causal_frac * n_core))), replace=False)) \
            if causal_frac < 1 else core
        causal = causal if len(causal) <= n_core else core
        supports = [set(causal.tolist())] * k
        off = n_core
        for blk, nb in zip(model.blocks, n_blocks):
            own = list(range(off, off + nb)) if nb else causal.tolist()
            supports += [set(own)] * blk.dim
            off += nb
        try:
            D = _left_inverse(E, supports)
            break
        except ValueError:
            continue
    else:
        raise ValueError("could not build a decodable implementation")
    for j in core:
        if j not in set(causal.tolist()):
            roles[j] = "latent_carrier"

    # ---- activations, baselines
    modulation = np.linalg.norm(E * coord_scale, axis=1)
    kinds = np.zeros(N, int)
    scales = np.ones(N)
    b = np.zeros(N)
    for i in range(N):
        pk = phi_kind if phi_kind != "mixed" else rng.choice(["identity", "tanh", "logistic"])
        if i in ramp_rows:
            pk = "logistic"
        kinds[i] = PHI_CODES[pk]
        mod = max(modulation[i], 1e-3)
        if pk == "identity":
            b[i] = rng.normal(0, 0.3) * mod if mixed else rng.uniform(0.8, 1.5) * mod
        elif pk == "tanh":
            scales[i] = mod / rng.uniform(0.7, 1.4)
            b[i] = rng.normal(0, 0.3) * scales[i]
        else:
            scales[i] = rng.uniform(0.5, 2.0)
            b[i] = rng.uniform(-1.0, 0.5)
            if i in ramp_rows:
                b[i] = -E[i].sum() * rng.uniform(0.3, 3.5)  # staggered onset times (clock value)
    # the latent/nuisance embedding is in v units; logistic neurons get v-modulation ~ 1.5-3 (strongly nonlinear)
    for i in range(N):
        if kinds[i] == PHI_LOGI and i not in ramp_rows:
            s = rng.uniform(1.5, 3.0) / max(modulation[i], 1e-3)
            E[i] *= s
            D[:, i] /= s
    phi = Phi(kinds, scales)

    # typical recorded modulation (for noise levels)
    xmod = np.where(kinds == PHI_ID, modulation, np.where(kinds == PHI_TANH, np.minimum(modulation, scales), 0.25 * scales))
    obs_sigma = float(spec.get("obs_noise", 0.05)) * xmod
    vmod = np.linalg.norm(E * coord_scale, axis=1)
    sigma_priv = float(spec.get("priv_noise", 0.05)) * vmod * np.sqrt(2 * lam)
    # private noise leaks into the population signal through D; bound that leak to half the latent's own process noise
    lat_sigma = float(np.mean(np.atleast_1d(model.latent.center.get("sigma", 0.03))))
    leak = np.sqrt((D[:k] ** 2 * sigma_priv ** 2).sum(1)).max()
    if leak > 0.5 * lat_sigma:
        sigma_priv = sigma_priv * (0.5 * lat_sigma / leak)

    # ---- observation
    frac_unobs = float(spec.get("frac_unobserved", 0.0))
    unobservable_roles = {"latent", "latent_carrier", "nuisance", "null_code"}
    cand = [i for i in range(N) if roles[i] in unobservable_roles]
    for _ in range(100):
        hidden = set(rng.choice(cand, int(round(frac_unobs * len(cand))), replace=False).tolist()) if frac_unobs else set()
        obs = [i for i in range(N) if i not in hidden]
        if np.linalg.matrix_rank(E[obs][:, :k]) == k:
            break

    # ---- permutation of neuron ids
    perm = rng.permutation(N) if spec.get("permute", True) else np.arange(N)  # new id of old neuron i = perm[i]
    inv = np.argsort(perm)
    E, b, D = E[inv], b[inv], D[:, inv]
    phi = Phi(kinds[inv], scales[inv])
    roles = [roles[i] for i in inv]
    observed = sorted(int(perm[i]) for i in obs)
    impl = Implementation(E=E, D=D, b=b, lam=lam, phi=phi, sigma_priv=sigma_priv[inv], obs_sigma=obs_sigma[inv],
                          observed=observed, roles=roles, spec=spec)
    impl.check()
    return impl
