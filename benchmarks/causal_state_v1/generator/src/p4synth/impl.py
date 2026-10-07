"""Physical implementation builder: turns a latent model into a population of units (Spec) with observation maps.

Design knobs (all seeded):
- core populations: each population loads on a subset of the latent dimensions with an embedding style (dense random mixing,
  sparse single-dimension tuning, redundant clones, ring / bump code), tuning amplitude kappa, rest potentials b, observation map
  and observed / targetable fractions;
- optional Wilson-Cowan rhythm generator pairs (nuisance rhythm driven by the input);
- relays (read the stimulus and, weakly, a few core outputs) and followers in two layers (layer A reads core outputs, the
  generator and the relays; layer B additionally reads layer-A followers): the downstream nuisance population;
- a random permutation of the public unit order (roles are never public); one system-wide admissible range and process-noise
  scale; the public scalable edges list, for every targetable unit, two of its actual inputs chosen at random (role-blind).
"""

from __future__ import annotations

import math

import numpy as np

from .engine import (CORE, FOL, GEN, RELAY, OBS_EXP, OBS_LIN, OBS_RELU, OBS_RELUP, OBS_SAT, OBS_SIG, OBS_SOFTPLUS, WC_BASE, Spec)

OBS_CODES = {"lin": OBS_LIN, "relu": OBS_RELU, "relup": OBS_RELUP, "sat": OBS_SAT, "softplus": OBS_SOFTPLUS, "exp": OBS_EXP,
             "sig": OBS_SIG}
FF_RADIUS = 0.6                 # spectral radius bound of the follower-follower coupling (stable for every gain <= 1.9 / 0.6)
RANGE = (-500.0, 500.0)         # the admissible range of every unit of every system (state units)
NOISE_SD = 100.0                # process-noise sd per sqrt(s) at sd = 1, every unit of every system


def _unit_vectors(rng, n, k):
    v = rng.standard_normal((n, k))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def core_population(rng, n, k, dims, embed="dense", kappa=(6.0, 14.0), z_scale=None, clone=1, dim_weights=None,
                    ring_dims=None):
    """Rows of E (n, k) for one population loading on `dims`."""
    zs = np.ones(k) if z_scale is None else np.asarray(z_scale, float)
    dims = list(dims)
    kap = rng.uniform(*kappa, n)
    E = np.zeros((n, k))
    if embed == "dense":
        base = _unit_vectors(rng, n, len(dims))
        E[:, dims] = base
    elif embed == "sparse":
        order = np.arange(n) % len(dims)
        rng.shuffle(order)
        sgn = rng.choice([-1.0, 1.0], n)
        for i in range(n):
            E[i, dims[order[i]]] = sgn[i]
            # small mixing so the code is not perfectly axis aligned
            others = [d for d in dims if d != dims[order[i]]]
            for d in others:
                E[i, d] = 0.15 * rng.standard_normal()
    elif embed == "clones":
        nb = max(1, n // clone)
        base = _unit_vectors(rng, nb, len(dims))
        rows = np.repeat(base, clone, axis=0)[:n]
        if rows.shape[0] < n:
            rows = np.vstack([rows, _unit_vectors(rng, n - rows.shape[0], len(dims))])
        E[:, dims] = rows
        kap = np.repeat(rng.uniform(*kappa, nb), clone)[:n]
        if kap.size < n:
            kap = np.concatenate([kap, rng.uniform(*kappa, n - kap.size)])
    elif embed == "ring":
        a, bdim = ring_dims if ring_dims is not None else dims[:2]
        ph = rng.uniform(0, 2 * np.pi, n)
        E[:, a] = np.cos(ph)
        E[:, bdim] = np.sin(ph)
    else:
        raise ValueError(embed)
    if dim_weights is not None:
        E = E * np.asarray(dim_weights, float)[None, :]
    E = E * kap[:, None] / zs[None, :]
    return E, kap


def implement(latent, rng, *, name, group_key, impl_key, pops, gen_pairs=1, gen_freq=12.0, gen_scale=1.0, gen_obs=True,
              gen_target=True, n_fol=30, fol_in=(1, 3), fol_core_w=0.8, fol_gen_w=(3.0, 10.0), fol_u_w=(4.0, 14.0),
              fol_base=(-10.0, -2.0), fol_obs=("relup", "relup", "relu"), fol_obs_frac=0.9, fol_target_frac=0.25, fol_scale=1.0, tau_c=0.02,
              tau_c_sd=0.12, tau_f=(0.015, 0.045), h_max=1e-3, n_u=None, fol_input_channel=0, gen_input_channel=0,
              fol_tags=None, n_relay=None, relay_obs_frac=0.5, relay_target_frac=0.3, relay_tau=(0.03, 0.06), core_scale=1.0,
              X0=20.0, fol_layer_b=None, fol_ff_w=(0.15, 0.4), relay_core_w=0.15, min_obs=0, max_obs=None, size_class="std",
              obs_all=None, tg_all=None):
    """Build a Spec. `pops`: list of dicts {n, dims, embed, kappa, base (lo, hi), obs, obs_frac, target_frac, clone,
    dim_weights, tag, hidden}."""
    k = latent.k
    n_u = latent.n_u if n_u is None else n_u
    zs = np.asarray(latent.z_scale, float)
    E_rows, kaps, bs, obs_k, obs_frac, tgt_frac, tags, hid = [], [], [], [], [], [], [], []
    for p in pops:
        E, kap = core_population(rng, p["n"], k, p.get("dims", range(k)), p.get("embed", "dense"), p.get("kappa", (6.0, 14.0)),
                                 zs, p.get("clone", 1), p.get("dim_weights"), p.get("ring_dims"))
        E_rows.append(E)
        kaps.append(kap)
        lo, hi = p.get("base", (-4.0, 6.0))
        bs.append(rng.uniform(lo, hi, p["n"]))
        ob = p.get("obs", "relu")
        obs_k += [ob if isinstance(ob, str) else ob[int(rng.integers(0, len(ob)))] for _ in range(p["n"])]
        of, tf = p.get("obs_frac", 1.0), p.get("target_frac", 0.7)
        obs_frac += [of] * p["n"]
        tgt_frac += [tf] * p["n"]
        tags += [p.get("tag", "core")] * p["n"]
        hid += [bool(p.get("hidden", of == 0.0))] * p["n"]
    E = np.vstack(E_rows)
    kap = np.concatenate(kaps)
    b = np.concatenate(bs)
    Nc = E.shape[0]
    if np.linalg.matrix_rank(E) < k:
        raise ValueError(f"{name}: embedding has rank < k")
    L = np.linalg.pinv(E)
    # ---- generator
    Ng = 2 * gen_pairs
    gen = {}
    if Ng:
        fac = 12.5 / gen_freq
        tau = []
        th, s = [], []
        W = np.zeros((Ng, Ng))
        h = np.zeros((Ng, n_u))
        for pi in range(gen_pairs):
            jf = fac * math.exp(0.04 * rng.standard_normal())
            e, i = 2 * pi, 2 * pi + 1
            tau += [WC_BASE["tE"] * jf, WC_BASE["tI"] * jf]
            th += [WC_BASE["thE"], WC_BASE["thI"]]
            s += [WC_BASE["sE"], WC_BASE["sI"]]
            W[e, e], W[e, i], W[i, e], W[i, i] = WC_BASE["wEE"], -WC_BASE["wEI"], WC_BASE["wIE"], -WC_BASE["wII"]
            h[e, gen_input_channel], h[i, gen_input_channel] = WC_BASE["hE"], WC_BASE["hI"]
        if gen_pairs > 1:     # weak excitatory coupling between the pairs' E units
            for a in range(gen_pairs):
                for c in range(gen_pairs):
                    if a != c:
                        W[2 * a, 2 * c] = 0.6
        gen = {"tau": np.array(tau), "W": W, "th": np.array(th), "s": np.array(s), "h": h, "tau_sd": 0.1, "h_sd": 0.12}
    # ---- followers: read core outputs, the generator and the relays, and 2-3 other followers (a sparse, stable recurrent nuisance
    # network; its spectral radius is kept below FF_RADIUS)
    Nf = int(n_fol)
    tauf = bf = Wfc = Wfg = Bf = Wff = None
    fol_layer = None
    if Nf:
        tauf = np.exp(rng.uniform(math.log(tau_f[0]), math.log(tau_f[1]), Nf))
        bf = rng.uniform(*fol_base, Nf)
        Wfc = np.zeros((Nf, Nc))
        pool = np.arange(Nc) if fol_tags is None else np.array([c for c in range(Nc) if tags[c] in fol_tags])
        for j in range(Nf):
            m = int(rng.integers(fol_in[0], fol_in[1] + 1))
            if m <= 0 or pool.size == 0:
                continue
            src = rng.choice(pool, size=min(m, pool.size), replace=False)
            Wfc[j, src] = fol_core_w * rng.choice([-1.0, 1.0], src.size) * rng.uniform(0.5, 1.5, src.size) / math.sqrt(src.size)
        Wfg = np.zeros((Nf, max(Ng, 0)))
        if Ng:
            for j in range(Nf):
                pi = int(rng.integers(0, gen_pairs))
                w = rng.uniform(*fol_gen_w)
                if rng.random() < 0.7:
                    Wfg[j, 2 * pi] = w
                else:
                    Wfg[j, 2 * pi + 1] = w
        Bf = np.zeros((Nf, n_u))          # followers receive the stimulus only through the relays
        Wff = np.zeros((Nf, Nf))
        if Nf >= 3:
            for j in range(Nf):
                others = np.delete(np.arange(Nf), j)
                src = rng.choice(others, size=min(int(rng.integers(2, 4)), others.size), replace=False)
                Wff[j, src] = rng.choice([-1.0, 1.0], src.size) * rng.uniform(*fol_ff_w, src.size)
            rad = float(np.max(np.abs(np.linalg.eigvals(Wff))))
            if rad > FF_RADIUS:
                Wff *= FF_RADIUS / rad
    # ---- relays (input cascade: u -> relay (tau_r) -> follower (tau_f)); relays also read 1-2 core outputs weakly
    Nr = (min(4, max(2, Nf // 10)) if Nf else 0) if n_relay is None else int(n_relay)
    taur = br = Br = Wfr = Wrc = None
    if Nr:
        taur = np.exp(rng.uniform(math.log(relay_tau[0]), math.log(relay_tau[1]), Nr))
        br = np.zeros(Nr)
        Br = np.zeros((Nr, n_u))
        Br[:, fol_input_channel] = rng.uniform(0.8, 1.2, Nr)
        Wfr = np.zeros((Nf, Nr))
        for j in range(Nf):
            Wfr[j, int(rng.integers(0, Nr))] = rng.uniform(*fol_u_w)
        Wrc = np.zeros((Nr, Nc))
        cpool = np.arange(Nc) if fol_tags is None else np.array([c for c in range(Nc) if tags[c] in fol_tags])
        for r in range(Nr):
            src = rng.choice(cpool, size=min(2, cpool.size), replace=False)
            Wrc[r, src] = relay_core_w * rng.choice([-1.0, 1.0], src.size) / (kap[src] + 1e-9)
    # ---- units, observation, admissible ranges
    roles = [CORE] * Nc + [GEN] * Ng + [FOL] * Nf + [RELAY] * Nr
    locs = list(range(Nc)) + list(range(Ng)) + list(range(Nf)) + list(range(Nr))
    N = len(roles)
    perm = rng.permutation(N)                     # perm[position in role order] = public id
    role = np.empty(N, int)
    loc = np.empty(N, int)
    role[perm] = roles
    loc[perm] = locs
    obs_kind = np.empty(N, int)
    obs_th = np.zeros(N)
    obs_s = np.ones(N)
    obs_w = np.ones(N)
    obs_p = np.ones(N)
    observed_flag = np.zeros(N, bool)
    target_flag = np.zeros(N, bool)
    hidden_flag = np.zeros(N, bool)
    unit_tag = [""] * N
    unit_dims = [[] for _ in range(N)]
    for c in range(Nc):
        u = perm[c]
        kd = obs_k[c]
        obs_kind[u] = OBS_CODES[kd]
        if kd == "lin":
            obs_th[u] = b[c]
        elif kd == "relup":
            obs_p[u] = 2.0
            obs_w[u] = kap[c]
        elif kd == "sat":
            obs_w[u] = 1.2 * kap[c]
        elif kd == "softplus":
            obs_w[u] = 0.3 * kap[c]
        elif kd == "exp":
            obs_th[u] = b[c] + kap[c]          # peak of the bump at maximal drive
            obs_w[u] = 0.35 * kap[c]
            obs_s[u] = 2.0 * kap[c]
        observed_flag[u] = rng.random() < obs_frac[c]
        target_flag[u] = rng.random() < tgt_frac[c]
        hidden_flag[u] = hid[c]
        unit_tag[u] = tags[c]
        unit_dims[u] = [int(d) for d in np.nonzero(np.abs(E[c]) > 1e-12)[0]]
    for g in range(Ng):
        u = perm[Nc + g]
        obs_kind[u] = OBS_SIG
        obs_th[u] = gen["th"][g]
        obs_w[u] = gen["s"][g]
        obs_s[u] = gen_scale
        observed_flag[u] = gen_obs if isinstance(gen_obs, bool) else rng.random() < gen_obs
        target_flag[u] = gen_target if isinstance(gen_target, bool) else rng.random() < gen_target
        unit_tag[u] = "gen"
    for j in range(Nf):
        u = perm[Nc + Ng + j]
        obs_kind[u] = OBS_CODES[fol_obs if isinstance(fol_obs, str) else fol_obs[int(rng.integers(0, len(fol_obs)))]]
        obs_s[u] = fol_scale
        if obs_kind[u] == OBS_RELUP:
            obs_p[u], obs_w[u] = 2.0, 8.0
        elif obs_kind[u] == OBS_SAT:
            obs_w[u] = 15.0
        elif obs_kind[u] == OBS_SOFTPLUS:
            obs_w[u] = 2.0
        elif obs_kind[u] == OBS_LIN:
            obs_th[u] = bf[j]
        observed_flag[u] = rng.random() < fol_obs_frac
        target_flag[u] = rng.random() < fol_target_frac
        unit_tag[u] = "fol"
    for j in range(Nr):
        u = perm[Nc + Ng + Nf + j]
        obs_kind[u] = OBS_RELU
        obs_s[u] = 10.0
        observed_flag[u] = rng.random() < relay_obs_frac
        target_flag[u] = rng.random() < relay_target_frac
        unit_tag[u] = "relay"
    # every non-hidden core population keeps >= 1 observed and >= 2 targetable units; observed-count bounds (compactness rule
    # k <= N_obs / 5 for compressible systems; N_obs <= 5 k_full / 3 for the non-compressible controls)
    for t_ in sorted(set(tags)):
        members = [perm[c] for c in range(Nc) if tags[c] == t_ and not hid[c]]
        if not members:
            continue
        if not observed_flag[members].any() and any(obs_frac[c] > 0 for c in range(Nc) if tags[c] == t_):
            observed_flag[members[int(rng.integers(0, len(members)))]] = True
        tg_m = [u for u in members if target_flag[u]]
        if len(tg_m) < min(2, len(members)) and any(tgt_frac[c] > 0 for c in range(Nc) if tags[c] == t_):
            cand = [u for u in members if not target_flag[u]]
            for u in rng.choice(cand, size=min(len(cand), 2 - len(tg_m)), replace=False):
                target_flag[u] = True
    # the overall observed / targetable counts follow the system's drawn fractions whatever the type-specific populations are
    # (units unobserved or non-targetable by design keep their flags; every population keeps >= 1 observed and >= 2 targetable)
    never_obs = {perm[c] for c in range(Nc) if obs_frac[c] == 0.0}
    never_tg = {perm[c] for c in range(Nc) if tgt_frac[c] == 0.0}
    tag_of = {perm[c]: tags[c] for c in range(Nc)}

    def _match(flags, frac, never, keep_min):
        if frac is None:
            return
        want = int(round(frac * N))
        order = list(rng.permutation(N))
        for u in order:
            have = int(flags.sum())
            if have == want:
                break
            if have < want and not flags[u] and u not in never:
                flags[u] = True
            elif have > want and flags[u]:
                t_ = tag_of.get(u)
                if t_ is not None and sum(flags[v] for v in tag_of if tag_of[v] == t_) <= keep_min:
                    continue
                flags[u] = False

    _match(observed_flag, obs_all, never_obs, 1)
    _match(target_flag, tg_all, never_tg, 2)
    free = [u for u in range(N) if not hidden_flag[u]]
    while observed_flag.sum() < min_obs:
        cand = [u for u in free if not observed_flag[u]]
        if not cand:
            break
        observed_flag[cand[int(rng.integers(0, len(cand)))]] = True
    if max_obs is not None:
        while observed_flag.sum() > max_obs:
            cand = np.nonzero(observed_flag)[0]
            observed_flag[cand[int(rng.integers(0, cand.size))]] = False
    if not observed_flag.any():
        observed_flag[perm[0]] = True
    # ---- gain normalisation (homeostatic): each unit's expected peak activity ~ X0 * role scale * lognormal(0.35)
    ch = fol_input_channel
    for u in range(N):
        r, i = role[u], loc[u]
        if r == CORE:
            d = b[i] + kap[i] - (obs_th[u] if obs_kind[u] in (OBS_LIN,) else 0.0)
            d = max(d, 0.3 * kap[i]) if obs_kind[u] != OBS_LIN else kap[i]
            scale = core_scale
        elif r == FOL:
            d = bf[i] + (Wfr[i] @ Br[:, ch] if Nr else 0.0) + (0.8 * Wfg[i].max() if Ng else 0.0) \
                + 0.7 * float(np.abs(Wfc[i]) @ kap)
            d = max(d, 1.0)
            scale = fol_scale
        elif r == RELAY:
            d = float(Br[i, ch])
            scale = fol_scale
        else:
            d = 1.0
            scale = gen_scale
        X = X0 * scale * math.exp(0.35 * rng.standard_normal())
        kd = obs_kind[u]
        if kd in (OBS_RELU, OBS_LIN):
            obs_s[u] = X / d
        elif kd == OBS_RELUP:
            obs_s[u] = X * obs_w[u] / d ** 2
        elif kd == OBS_SAT:
            obs_w[u] = X
            obs_s[u] = 1.5 * X / d
        elif kd == OBS_SOFTPLUS:
            obs_s[u] = X / max(d, obs_w[u])
        else:                   # exponential bump codes and sigmoid rates peak at s
            obs_s[u] = X
    # ---- one admissible range and process-noise scale for every unit of every system (per-unit or per-system values would reveal
    # roles or the type)
    lo = np.full(N, RANGE[0])
    hi = np.full(N, RANGE[1])
    nscale = np.full(N, NOISE_SD)
    spec = Spec(name=name, k=k, n_u=n_u, latent=latent, group_key=group_key, impl_key=impl_key, role=role, loc=loc, E=E, L=L, b=b,
                tau_c=tau_c, tau_c_sd=tau_c_sd, gen=gen, tau_f=tauf, b_f=bf, W_fc=Wfc, W_fg=Wfg if Ng else None, B_f=Bf,
                tau_r=taur, b_r=br, B_r=Br, W_fr=Wfr, W_ff=Wff, fol_layer=fol_layer, W_rc=Wrc,
                obs_kind=obs_kind, obs_th=obs_th, obs_s=obs_s, obs_w=obs_w, obs_p=obs_p,
                observed=[int(u) for u in np.nonzero(observed_flag)[0]], lo=lo, hi=hi, h_max=h_max, noise_scale=nscale)
    meta = {"targetable": [int(u) for u in np.nonzero(target_flag)[0]], "unit_tag": unit_tag, "unit_dims": unit_dims,
            "kappa": {int(perm[c]): float(kap[c]) for c in range(Nc)}, "size_class": size_class}
    meta["edges"] = public_edges(spec, meta["targetable"], rng)
    return spec, meta


def unit_inputs(spec: Spec, u: int, recurrent_only: bool = False) -> list[int]:
    """Public ids of the units with a synapse onto unit u (including an autapse where the unit has one). recurrent_only: only the
    inputs from the unit's own population (core <- core, generator <- generator, follower <- follower; relays: their core inputs)."""
    r, i = spec.role[u], spec.loc[u]
    core_ids, gen_ids = spec.units_of(CORE), spec.units_of(GEN)
    fol_ids, relay_ids = spec.units_of(FOL), spec.units_of(RELAY)
    if r == CORE:
        return [int(x) for x in core_ids]                         # dense recurrent synapses W = E L
    if r == GEN:
        return [int(gen_ids[j]) for j in np.nonzero(spec.gen["W"][i])[0]]
    if r == RELAY:
        return [int(core_ids[c]) for c in np.nonzero(spec.W_rc[i])[0]] if spec.W_rc is not None else []
    rec = [int(fol_ids[q]) for q in np.nonzero(spec.W_ff[i])[0]] if spec.W_ff is not None else []
    if recurrent_only and rec:
        return rec
    src = [int(core_ids[c]) for c in np.nonzero(spec.W_fc[i])[0]]
    if spec.W_fg is not None:
        src += [int(gen_ids[g]) for g in np.nonzero(spec.W_fg[i])[0]]
    if spec.W_fr is not None:
        src += [int(relay_ids[q]) for q in np.nonzero(spec.W_fr[i])[0]]
    return src + rec


def public_edges(spec: Spec, targetable, rng, per_post=2) -> list:
    """Scalable synapses: for every targetable unit, `per_post` of its recurrent inputs (from its own population) chosen at random.
    Every population is recurrent with a comparable in-degree, so the listed in- and out-degrees do not reveal roles."""
    edges = []
    for p in sorted(int(u) for u in targetable):
        src = unit_inputs(spec, p, recurrent_only=True)
        if not src:
            continue
        for q in rng.choice(src, size=min(per_post, len(src)), replace=False):
            edges.append([p, int(q)])
    return sorted(edges)
