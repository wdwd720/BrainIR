"""build_suite(tier, seed, n_per_type): deterministic suites of opaque synthetic systems."""

from __future__ import annotations

try:
    from threadpoolctl import threadpool_limits as _threadpool_limits
except Exception:  # pragma: no cover
    _threadpool_limits = None

import hashlib
import math

import numpy as np

from .engine import CORE, _rng
from .impl import implement
from .system import SyntheticSystem
from .types import GROUP_TYPES, TYPE_NAMES, VARIANTS, build_type

DEFAULT_N = {"dev": 2, "val": 2, "conf": 3}


def _h(*keys) -> str:
    return hashlib.sha256(repr(keys).encode()).hexdigest()


def realisation_classes(spec) -> list[list[int]]:
    """Groups of core units with identical columns of L (a kick / current on any member realises the same dz)."""
    core = spec.units_of(CORE)
    cols = spec.L.T
    seen, out = set(), []
    for i in range(len(core)):
        if i in seen:
            continue
        grp = [j for j in range(len(core)) if j not in seen and np.allclose(cols[j], cols[i], rtol=1e-9, atol=1e-12)]
        seen |= set(grp)
        if len(grp) > 1:
            out.append(sorted(int(core[j]) for j in grp))
    return out


SIZE_N = (40, 160)          # units per standard system: log-uniform, the same distribution for every type


def draw_size(tier: str, seed: int, t: int, j: int) -> dict:
    """The size of one standard system, drawn from ONE distribution for every type (so n_units, n_observed and the targetable
    fraction reveal neither the type nor k): units N, core fraction, observed / targetable probability of every unit, generator pairs
    and the share of layer-B followers."""
    r = _rng("size", tier, int(seed), int(t), int(j))
    while True:          # expected observed units N p_obs <= NOBS_MAX for EVERY type (review round 3, B4: the controls' margin
        N = int(round(math.exp(r.uniform(math.log(SIZE_N[0]), math.log(SIZE_N[1])))))    # over N_obs / 5 saturates in larger
        p_obs = float(r.uniform(0.6, 0.95))                                                  # systems; a common truncation)
        if N * p_obs <= NOBS_MAX:
            break
    return {"N": N, "core_frac": float(r.uniform(0.45, 0.8)), "p_obs": p_obs, "p_tg": float(r.uniform(0.35, 0.65)),
            "gen_pairs": 1 + int(r.random() < 0.35), "fol_b": float(r.uniform(0.25, 0.45))}


NOBS_MAX = 115


def apply_size(impl: dict, sz: dict, k: int, compressible: bool) -> dict:
    """Rescale a type's relative population sizes to the size draw: core populations keep their proportions (and minimum sizes),
    followers fill the rest; every unit without a type-specific observation / target rule is observed with p_obs and targetable
    with p_tg, whatever its role. Small-regime systems keep their unit counts but follow the same observation / target rule."""
    impl = dict(impl)
    pops = [dict(p) for p in impl["pops"]]
    p_obs, p_tg = sz["p_obs"], sz["p_tg"]
    if impl.get("size_class") == "small":
        for p in pops:
            p.setdefault("obs_frac", p_obs)
            p.setdefault("target_frac", p_tg)
        impl.update(pops=pops, fol_obs_frac=p_obs, fol_target_frac=p_tg, obs_all=p_obs, tg_all=p_tg)
        return impl
    N = sz["N"]
    nmin = [max(int(p.get("min_n", 0)), len(p["dims"]) + 2, 2 * int(p.get("clone", 1)), 3) for p in pops]
    Nc0 = sum(p["n"] for p in pops)
    Nc_t = max(sum(nmin), int(round(sz["core_frac"] * N)))
    for p, m in zip(pops, nmin):
        n_ = max(m, int(round(p["n"] * Nc_t / Nc0)))
        if p.get("clone", 1) > 1:
            n_ = max(2 * p["clone"], (n_ // p["clone"]) * p["clone"])
        p["n"] = int(n_)
        p.setdefault("obs_frac", p_obs)
        p.setdefault("target_frac", p_tg)
    Nc = sum(p["n"] for p in pops)
    if impl.get("gen_pairs", 0):
        impl["gen_pairs"] = sz["gen_pairs"]
    ng = 2 * impl.get("gen_pairs", 0)
    nf = max(4, N - Nc - ng - 3)
    nr = min(4, max(2, nf // 10))
    nf = max(4, N - Nc - ng - nr)
    impl.update(pops=pops, n_fol=int(nf), n_relay=int(nr), fol_obs_frac=p_obs, fol_target_frac=p_tg, relay_obs_frac=p_obs,
                relay_target_frac=p_tg, gen_obs=p_obs, gen_target=p_tg, fol_layer_b=sz["fol_b"], obs_all=p_obs, tg_all=p_tg)
    if compressible:
        impl["min_obs"] = 5 * int(k)
    return impl


def build_system(tier: str, seed: int, t: int, j: int, n: int) -> SyntheticSystem:
    """One system; constructed with single-threaded BLAS so the result (and its content hash) does not depend on the thread count
    of the environment (review round 3, B6)."""
    if _threadpool_limits is None:  # pragma: no cover
        return _build_system(tier, seed, t, j, n)
    with _threadpool_limits(limits=1):
        return _build_system(tier, seed, t, j, n)


def _build_system(tier: str, seed: int, t: int, j: int, n: int) -> SyntheticSystem:
    """Types 20 / 21 (non-compressible controls): a draw is ACCEPTED only when its SIMULATED margin (controls.simulated_margin:
    the rank needed for 90 % of its moderate single-unit readout responses within the floor, over the benchmark bound
    max(1, N_obs / 5)) is >= controls.MARGIN_ACCEPT at the primary (0.25 s) AND the long (1 s) horizon (review v3.3, N8), on every
    tier and seed; otherwise the latent / implementation is redrawn deterministically (attempt-salted keys; the size draw is
    kept, so the size distribution stays the same for every type). The linearised surrogate only pre-screens (draws below
    controls.MARGIN_SCREEN are not simulated). After MAX_ATTEMPTS the size is redrawn as well (never needed on the tested seeds).
    The achieved margins are in info["control_margin"] / truth()["control_margin"]."""
    if t not in (20, 21):
        return _build_attempt(tier, seed, t, j, n, 0)
    from .controls import MARGIN_ACCEPT, MARGIN_SCREEN, cached_simulated_margin, surrogate_margin
    tried = []
    for att in range(3 * MAX_ATTEMPTS):
        s = _build_attempt(tier, seed, t, j, n, att, resize=att >= MAX_ATTEMPTS)
        sur = surrogate_margin(s)
        worst_s = min(v["ratio"] for v in sur.values())
        rec = {"attempt": att, "surrogate": {str(h): round(v["ratio"], 3) for h, v in sur.items()}}
        if worst_s < MARGIN_SCREEN:
            tried.append(dict(rec, rejected="surrogate"))
            continue
        sim = cached_simulated_margin(s)
        rec["simulated"] = {str(h): v for h, v in sim.items()}
        ok = all(v["ratio"] >= MARGIN_ACCEPT for v in sim.values())
        if ok:
            s.info["control_margin"] = {"primary": round(sim[0.25]["ratio"], 4), "1s": round(sim[1.0]["ratio"], 4),
                                        "bound": sim[0.25]["bound"], "need_primary": sim[0.25]["need"], "need_1s": sim[1.0]["need"],
                                        "attempt": att, "rejected_attempts": tried, "criterion": f"simulated margin >= {MARGIN_ACCEPT} "
                                        "at 0.25 s and 1 s (controls.simulated_margin)"}
            return s
        tried.append(dict(rec, rejected="simulated"))
    raise RuntimeError(f"no type-{t} draw with a simulated control margin >= {MARGIN_ACCEPT} for {tier}:{seed}:{j}")


MAX_ATTEMPTS = 10


def _build_attempt(tier: str, seed: int, t: int, j: int, n: int, att: int, resize: bool = False) -> SyntheticSystem:
    variants = VARIANTS[t]
    off = int(_h("variant", tier, seed, t)[:8], 16) % len(variants)
    variant = variants[(off + j) % len(variants)]
    decoy = (t == 12 and n >= 3 and j == n - 1)
    if t in GROUP_TYPES:
        gkey = f"{tier}:{seed}:T{t}:" + ("decoy" if decoy else "group")
    else:
        gkey = f"{tier}:{seed}:T{t}:{j}"
    ikey = f"{tier}:{seed}:T{t}:{j}:impl"
    if att:
        gkey, ikey = gkey + f":a{att}", ikey + f":a{att}"
    grng, irng = _rng("group", gkey), _rng("impl", ikey)
    sz = draw_size(tier, seed, t, j) if not resize else draw_size(tier, seed, t, j * 1000 + att)
    b = build_type(t, variant, grng, irng, group_key=gkey, impl_key=ikey, impl_index=j, decoy=decoy, size=sz)
    sid = "syn-" + _h("id", tier, seed, t, j, "p4synth")[:12]
    compressible = b["info"].get("k") != "none"
    impl = apply_size(b["impl"], sz, b["latent"].k, compressible)
    spec, meta = implement(b["latent"], irng, name=sid, group_key=gkey, impl_key=ikey, **impl)
    info = dict(b["info"])
    info["tier"] = tier
    info["suite_seed"] = seed
    info["index_in_type"] = j
    if t in GROUP_TYPES:
        info["implementation_group"] = "grp-" + _h("group", gkey)[:10]
    info["realisation_classes"] = realisation_classes(spec)
    return SyntheticSystem(spec, meta, info, system_id=sid, dt=b["dt"], t_end_default=b["t_end"])


def build_suite(tier: str, seed: int, n_per_type: int | None = None) -> dict[str, SyntheticSystem]:
    """Deterministic in (tier, seed). Returns {system_id: SyntheticSystem} sorted by the opaque id."""
    n = int(n_per_type) if n_per_type is not None else DEFAULT_N.get(tier, 1)
    systems = {}
    for t in sorted(TYPE_NAMES):
        for j in range(n):
            s = build_system(tier, int(seed), t, j, n)
            systems[s.system_id] = s
    # unrelated-but-similar pairs: implementation groups of types 11 / 12 / 24 and the type-12 decoy
    groups = {}
    for sid, s in systems.items():
        g = s.info.get("implementation_group")
        if g:
            groups.setdefault(g, []).append(sid)
    for sid, s in systems.items():
        g = s.info.get("implementation_group")
        if g:
            s.info["group_members"] = sorted(x for x in groups[g] if x != sid)
            s.info["unrelated_systems"] = sorted(x for gg, xs in groups.items() if gg != g for x in xs
                                                 if systems[x].info["type"] in (11, 12) and s.info["type"] in (11, 12))
    return dict(sorted(systems.items()))
