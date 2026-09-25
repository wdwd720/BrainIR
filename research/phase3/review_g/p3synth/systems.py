"""System catalogue: every family (1-20), every trap (A-L), implementation groups and unrelated pairs.

`catalog()` lists SystemDefs (internal names are truth-only); `build_system(defn, suite_seed)` instantiates one.
The suite seed changes every random draw (latent centres, embeddings, ids) but never the TYPE of any system.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import blocks as B
from . import latents as L
from .core import Model, SyntheticSystem, seed_from
from .embeddings import make_implementation

FAMILIES = {
    1: "linear stable state-space", 2: "harmonic oscillator", 3: "nonlinear oscillator", 4: "damped oscillator",
    5: "limit-cycle oscillator", 6: "bistable switch", 7: "leaky integrator", 8: "perfect integrator",
    9: "gated integrator", 10: "winner-take-all", 11: "negative feedback controller", 12: "coupled slow/fast",
    13: "latent + irrelevant nuisance neurons", 14: "redundant microscopic realisation",
    15: "multiple implementations of one latent dynamic", 16: "non-Markov projection trap", 17: "output-only shortcut trap",
    18: "time-index shortcut trap", 19: "hidden exogenous-variable trap", 20: "high-dimensional, no small abstraction",
}
TRAPS = {
    "A": "high-variance nuisance that does not cause the output", "B": "neuron copying the readout",
    "C": "clock neuron tracking time", "D": "neuron copying the stimulus", "E": "many microstates for one causal state",
    "F": "hysteresis (same output, different hidden state)", "G": "non-Markov compression",
    "H": "parameter-draw encoding", "I": "multiple limit cycles", "J": "transient vs limit cycle",
    "K": "bifurcation (dimension changes with input regime)", "L": "distributed computation",
}


@dataclass
class SystemDef:
    name: str                              # internal (truth-only) name
    family_no: int
    latent_key: str                        # systems with the same latent_key share ONE Latent object
    latent: Callable[[int], L.Latent]      # seed -> Latent
    spec: dict
    blocks: Callable[[np.random.Generator, L.Latent], list] = lambda rng, lat: []
    trap: str | None = None
    group: str | None = None               # implementation group (shared latent dynamics)
    pair: str | None = None                # unrelated-pair id
    impl_key: str | None = None            # systems with the same impl_key share the implementation draw
    t_end: float = 4.0
    stim_mode: str = "varied"              # "time_locked": nominal-style stimulus timing dominates the training set
    notes: str = ""
    extra: dict = field(default_factory=dict)


def _nuis(m=3, sd=3.0, stim=0.0):
    return lambda rng, lat: [B.NuisanceOU(rng, m=m, sd=sd, n_u=lat.n_u, stim_gain=stim)]


def catalog() -> list[SystemDef]:
    S = SystemDef
    d = []
    # ---------------------------------------------------------------- 1 linear stable (several k)
    d.append(S("linear_k1", 1, "linear_k1", lambda s: L.LinearStable(s, k=1),
               dict(n_core=10, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05)))
    d.append(S("linear_k3", 1, "linear_k3", lambda s: L.LinearStable(s, k=3, osc=1),
               dict(n_core=40, code="sparse", phi="logistic", mixed_sign=False, obs_noise=0.05, frac_unobserved=0.2)))
    d.append(S("linear_k6", 1, "linear_k6", lambda s: L.LinearStable(s, k=6, n_u=2, n_y=2, osc=2),
               dict(n_core=150, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.1, lam=40.0)))
    # ---------------------------------------------------------------- 2-5 oscillators
    d.append(S("harmonic", 2, "harmonic", lambda s: L.Harmonic(s),
               dict(n_core=30, code="redundant", phi="identity", mixed_sign=False, obs_noise=0.05)))
    d.append(S("duffing", 3, "duffing", lambda s: L.Duffing(s),
               dict(n_core=60, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.05)))
    d.append(S("damped", 4, "damped", lambda s: L.Damped(s),
               dict(n_core=25, code="sparse", phi="identity", mixed_sign=True, obs_noise=0.1)))
    d.append(S("hopf", 5, "hopf", lambda s: L.Hopf(s),
               dict(n_core=50, code="dense", phi="logistic", mixed_sign=False, obs_noise=0.05)))
    d.append(S("vanderpol", 5, "vanderpol", lambda s: L.VanDerPol(s),
               dict(n_core=80, code="distributed", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=10, gain=1.0, mix=0.3)]), blocks=_nuis(m=2, sd=0.7)))
    # ---------------------------------------------------------------- 6-12
    d.append(S("bistable_1d", 6, "bistable_1d", lambda s: L.Bistable1D(s),
               dict(n_core=20, code="redundant", phi="tanh", mixed_sign=True, obs_noise=0.05)))
    d.append(S("toggle", 6, "toggle", lambda s: L.Toggle(s),
               dict(n_core=45, code="sparse", phi="logistic", mixed_sign=False, obs_noise=0.05)))
    d.append(S("leaky", 7, "leaky", lambda s: L.Leaky(s),
               dict(n_core=15, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05)))
    d.append(S("perfect_1d", 8, "perfect_1d", lambda s: L.Perfect(s, k=1),
               dict(n_core=35, code="dense", phi="identity", mixed_sign=False, obs_noise=0.05)))
    d.append(S("perfect_2d", 8, "perfect_2d", lambda s: L.Perfect(s, k=2),
               dict(n_core=70, code="sparse", phi="tanh", mixed_sign=True, obs_noise=0.05, frac_unobserved=0.3)))
    d.append(S("gated", 9, "gated", lambda s: L.Gated(s),
               dict(n_core=40, code="dense", phi="logistic", mixed_sign=False, obs_noise=0.05)))
    d.append(S("wta", 10, "wta", lambda s: L.WTA(s),
               dict(n_core=90, code="sparse", phi="logistic", mixed_sign=False, obs_noise=0.05, causal_frac=0.6)))
    d.append(S("controller", 11, "controller", lambda s: L.Controller(s),
               dict(n_core=50, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.05)))
    d.append(S("slow_fast", 12, "slow_fast", lambda s: L.FHN(s),
               dict(n_core=60, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05, frac_unobserved=0.25, lam=40.0)))
    # ---------------------------------------------------------------- 13 nuisance (trap A)
    d.append(S("nuisance_ou", 13, "nuisance_ou", lambda s: L.Damped(s),
               dict(n_core=30, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=40, gain=1.0, mix=0.5)]), blocks=_nuis(m=3, sd=3.0), trap="A"))
    d.append(S("nuisance_rhythm", 13, "nuisance_rhythm", lambda s: L.Leaky(s),
               dict(n_core=60, code="sparse", phi="tanh", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=60, gain=1.0, mix=0.0), dict(n=80, gain=1.0, mix=0.3)]),
               blocks=lambda rng, lat: [B.NuisanceOsc(rng, R=2.5), B.NuisanceOU(rng, m=4, sd=2.5, n_u=1, stim_gain=3.0)],
               trap="A", notes="stimulus-driven nuisance: correlates with u (and hence y) without causing y"))
    # ---------------------------------------------------------------- 14 redundant (trap E)
    d.append(S("redundant_switch", 14, "redundant_switch", lambda s: L.Bistable1D(s),
               dict(n_core=120, code="redundant", phi="identity", mixed_sign=False, obs_noise=0.05,
                    blocks=[dict(n=0, mix=1.0)]),
               blocks=lambda rng, lat: [B.Persistent(rng, m=3, amp=1.0, diffusion=0.02)], trap="E"))
    d.append(S("redundant_integrator", 14, "redundant_integrator", lambda s: L.Perfect(s, k=1),
               dict(n_core=80, code="redundant", phi="tanh", mixed_sign=True, obs_noise=0.05, blocks=[dict(n=0, mix=1.0)]),
               blocks=lambda rng, lat: [B.Persistent(rng, m=2, amp=1.0, diffusion=0.02)], trap="E"))
    # ---------------------------------------------------------------- 15 implementation groups
    grpA = [dict(n_core=16, code="dense", phi="identity", mixed_sign=True, obs_noise=0.03, lam=25.0),
            dict(n_core=100, code="sparse", phi="logistic", mixed_sign=False, obs_noise=0.05, frac_unobserved=0.3, lam=35.0,
                 blocks=[dict(n=20, gain=1.0, mix=0.0)]),
            dict(n_core=60, code="redundant", phi="tanh", mixed_sign=True, obs_noise=0.2, lam=50.0),
            dict(n_core=200, code="distributed", phi="identity", mixed_sign=True, obs_noise=0.1, causal_frac=0.5, lam=20.0,
                 blocks=[dict(n=40, gain=1.0, mix=0.4)])]
    grpA_blocks = [lambda rng, lat: [], _nuis(m=2, sd=1.5), lambda rng, lat: [],
                   lambda rng, lat: [B.NuisanceOsc(rng, R=1.5, f0=3.1)]]
    for i, (sp, bl) in enumerate(zip(grpA, grpA_blocks)):
        d.append(S(f"groupA_impl{i}", 15, "groupA_hopf", lambda s: L.Hopf(s), sp, blocks=bl, group="A"))
    grpB = [dict(n_core=20, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05, lam=30.0),
            dict(n_core=90, code="sparse", phi="tanh", mixed_sign=True, obs_noise=0.05, lam=45.0,
                 blocks=[dict(n=30, gain=1.0, mix=0.2)]),
            dict(n_core=300, code="distributed", phi="logistic", mixed_sign=True, obs_noise=0.1, frac_unobserved=0.25, lam=25.0)]
    grpB_blocks = [lambda rng, lat: [], _nuis(m=3, sd=1.0), lambda rng, lat: []]
    for i, (sp, bl) in enumerate(zip(grpB, grpB_blocks)):
        d.append(S(f"groupB_impl{i}", 15, "groupB_gated", lambda s: L.Gated(s), sp, blocks=bl, group="B"))
    # ---------------------------------------------------------------- 16-19
    d.append(S("nonmarkov", 16, "nonmarkov", lambda s: L.Damped(s, center_override={"zeta": 0.1}),
               dict(n_core=40, code="dense", phi="identity", mixed_sign=True, obs_noise=0.1, core_gain=[1.0, 0.06]), trap="G",
               notes="z2 (velocity) is represented ~17x more weakly than z1; x is effectively 1-D"))
    d.append(S("output_shortcut", 17, "output_shortcut", lambda s: L.LinearStable(s, k=3, osc=1),
               dict(n_core=40, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=4, gain=2.5, mix=0.0)]),
               blocks=lambda rng, lat: [B.ReadoutCopy(n_y=lat.n_y, tau=0.01)], trap="B"))
    d.append(S("time_index", 18, "time_index", lambda s: L.Leaky(s, tau_range=(0.5, 0.8)),
               dict(n_core=25, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=6, code="ramp")]),
               blocks=lambda rng, lat: [B.Clock()], trap="C", stim_mode="time_locked"))
    d.append(S("hidden_exogenous", 19, "hidden_exogenous", lambda s: L.ExoDriven(s),
               dict(n_core=40, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05)))
    d.append(S("highdim_chaotic", 20, "highdim_chaotic", lambda s: L.RandomRNN(s, N=200, g=3.0),
               dict(n_core=200, code="identity", phi="identity", mixed_sign=True, obs_noise=0.05, lam=30.0)))
    d.append(S("highdim_linear", 20, "highdim_linear", lambda s: L.HighDimLinear(s, N=60),
               dict(n_core=60, code="rotation", phi="identity", mixed_sign=True, obs_noise=0.05, lam=30.0)))
    # ---------------------------------------------------------------- remaining traps
    d.append(S("stimulus_copy", 7, "stimulus_copy", lambda s: L.Leaky(s, tau_range=(0.25, 0.4)),
               dict(n_core=20, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=3, gain=2.0, mix=0.0)]),
               blocks=lambda rng, lat: [B.StimCopy(n_u=lat.n_u, tau=0.02)], trap="D"))
    d.append(S("hysteresis", 6, "hysteresis", lambda s: L.Hysteresis(s),
               dict(n_core=40, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.05, core_gain=[0.4, 1.0]), trap="F",
               notes="memory z1 weakly represented relative to the output variable z2"))
    d.append(S("parameter_trap", 7, "parameter_trap", lambda s: L.SetPoint(s),
               dict(n_core=25, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=4, gain=2.0, mix=0.0)]),
               blocks=lambda rng, lat: [B.ParamReport("setpoint", tau=0.05)], trap="H"))
    d.append(S("multicycle_planar", 5, "multicycle_planar", lambda s: L.MultiCycle(s),
               dict(n_core=50, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05), trap="I"))
    d.append(S("multicycle_switch", 5, "multicycle_switch", lambda s: L.CycleSwitch(s),
               dict(n_core=80, code="sparse", phi="logistic", mixed_sign=False, obs_noise=0.05, core_gain=[1.0, 1.0, 0.3]),
               trap="I", notes="cycle-selecting switch z3 weakly represented"))
    d.append(S("transient_cycle", 5, "transient_cycle", lambda s: L.SubHopf(s),
               dict(n_core=45, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.05), trap="J"))
    d.append(S("bifurcation", 12, "bifurcation", lambda s: L.Rayleigh(s),
               dict(n_core=50, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05), trap="K"))
    d.append(S("distributed", 1, "distributed", lambda s: L.LinearStable(s, k=4, osc=2),
               dict(n_core=200, code="distributed", phi="identity", mixed_sign=True, obs_noise=0.3, priv_noise=0.1,
                    blocks=[dict(n=0, mix=1.0)]),
               blocks=lambda rng, lat: [B.NuisanceOU(rng, m=6, sd=1.0)], trap="L"))
    # ---------------------------------------------------------------- unrelated pairs (identical implementations)
    pair_specs = {
        "P1": (lambda s: L.Damped(s, center_override={"f0": 1.0}), lambda s: L.Hopf(s, center_override={"f0": 1.0}),
               dict(n_core=40, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05)),
        "P2": (lambda s: L.Leaky(s), lambda s: L.Bistable1D(s),
               dict(n_core=20, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.05)),
        "P3": (lambda s: L.Harmonic(s, center_override={"f0": 1.0}), lambda s: L.LinearStable(s, k=2, osc=0),
               dict(n_core=30, code="sparse", phi="logistic", mixed_sign=False, obs_noise=0.05)),
    }
    fam = {"P1": (4, 5), "P2": (7, 6), "P3": (2, 1)}
    for pid, (la, lb, sp) in pair_specs.items():
        d.append(S(f"pair{pid}_a", fam[pid][0], f"pair{pid}_a", la, sp, pair=pid, impl_key=f"pair{pid}"))
        d.append(S(f"pair{pid}_b", fam[pid][1], f"pair{pid}_b", lb, sp, pair=pid, impl_key=f"pair{pid}"))
    return d


def system_id_for(name: str, suite_seed: int, tier: str) -> str:
    return "syn-" + hashlib.sha256(f"p3synth|{tier}|{suite_seed}|{name}".encode()).hexdigest()[:10]


def coord_scale(model: Model, t_end: float) -> np.ndarray:
    sc = [model.latent.amp] * model.k
    for blk in model.blocks:
        if isinstance(blk, B.NuisanceOU):
            sc += list(blk.sd)
        elif isinstance(blk, B.NuisanceOsc):
            sc += [blk.R] * 2
        elif isinstance(blk, B.Clock):
            sc += [t_end / 2]
        elif isinstance(blk, B.Persistent):
            sc += [blk.amp] * blk.dim
        else:
            sc += [model.latent.amp] * blk.dim
    return np.asarray(sc, float)


def build_system(defn: SystemDef, suite_seed: int, tier: str = "dev", latent_cache: dict | None = None) -> SyntheticSystem:
    latent_cache = latent_cache if latent_cache is not None else {}
    if defn.latent_key not in latent_cache:
        latent_cache[defn.latent_key] = defn.latent(seed_from("latent", suite_seed, defn.latent_key) % (2 ** 31))
    lat = latent_cache[defn.latent_key]
    sseed = seed_from("system", suite_seed, tier, defn.name) % (2 ** 31)
    rng_blocks = np.random.default_rng([sseed, 11])
    model = Model(lat, defn.blocks(rng_blocks, lat))
    impl_key = defn.impl_key or defn.name
    rng_impl = np.random.default_rng([seed_from("impl", suite_seed, tier, impl_key) % (2 ** 31), 13])
    scale = coord_scale(model, defn.t_end)
    if defn.pair:  # identical implementation for both members of a pair
        scale = np.ones_like(scale)
    impl = make_implementation(model, defn.spec, rng_impl, coord_scale=scale)
    sid = system_id_for(defn.name, suite_seed, tier)
    meta = {"name": defn.name, "family_no": defn.family_no, "family": FAMILIES[defn.family_no], "trap": defn.trap,
            "group": defn.group, "pair": defn.pair, "latent_key": defn.latent_key, "t_end": defn.t_end,
            "stim_mode": defn.stim_mode, "notes": defn.notes, "impl_key": impl_key}
    return SyntheticSystem(sid, model, impl, seed=sseed, meta=meta)


def build_all(suite_seed: int = 0, tier: str = "dev", names: list[str] | None = None) -> list[SyntheticSystem]:
    cache: dict = {}
    return [build_system(dd, suite_seed, tier, cache) for dd in catalog() if names is None or dd.name in names]


def get_system(name: str, suite_seed: int = 0, tier: str = "dev") -> SyntheticSystem:
    return build_all(suite_seed, tier, [name])[0]
