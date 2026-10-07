"""The 25 system types and their variants: latent dynamics + physical implementation + truth description.

`build_type(t, variant, grng, irng, group_key, impl_key, impl_index)` returns {"latent", "impl" (kwargs of impl.implement),
"info" (truth description), "dt", "t_end"}. `grng` seeds everything that must be shared by an implementation group (latent
structure, readout); `irng` seeds the implementation (units, observation maps, generator, followers).
"""

from __future__ import annotations

import math

import numpy as np

from .latents import random_readout
from .tlatents import lat_rk4
from .tlatents import (FHN, PerfectInt, Bistable, Controller, FastSlow, GatedMemory, HiddenMode, Hopf, HopfSlow, LeakyInt,
                       LinearSSM, Ring, ShearHopf, WTA)
from .tlatents2 import (Adaptation, Aliased, BurstOnset, Confounded, Context, LowVarTrap, MultiWell, SlowModes,
                        Slaved, SubHopf, Transient3)

TYPE_NAMES = {
    1: "linear controlled state-space model", 2: "nonlinear controlled oscillator", 3: "leaky integrator with interventions",
    4: "perfect integrator", 5: "gated memory", 6: "bistable switch", 7: "winner-take-all", 8: "negative feedback controller",
    9: "coupled fast / slow state", 10: "hidden discrete mode + continuous state", 11: "redundant physical implementation",
    12: "multiple microscopic circuits implementing the same z-dynamics", 13: "latent state embedded through a nonlinear population code",
    14: "irrelevant high-variance nuisance units", 15: "intervention-sensitive low-variance state",
    16: "hidden parameter / context state", 17: "partial observability requiring delay / history", 18: "multiple attractors",
    19: "transient dynamics + steady-state dynamics", 20: "genuinely high-dimensional system (no compact causal state)",
    21: "observationally compressible but interventionally non-compressible", 22: "readout prediction easy but causal state hard",
    23: "intervention confounding", 24: "redundant low-level intervention realisations", 25: "same immediate readout, different causal state",
}

VARIANTS = {
    1: ["osc2", "chain3", "mixed4"], 2: ["hopf", "fhn", "shear"], 3: ["small", "twotau", "large"], 4: ["small", "signed", "plane"],
    5: ["onset", "level", "trap"], 6: ["small", "adapt", "hidden"], 7: ["wta3", "wta4", "hyst3"], 8: ["pi", "pid", "setpoint"],
    9: ["burst", "relay", "slaved"], 10: ["osc", "gain", "trap"], 11: ["r3", "r6", "r12"], 12: ["impl"], 13: ["ring", "torus", "sigcode"],
    14: ["ratio10", "ratio100", "ratio1000"], 15: ["easy", "medium", "hard", "osc"], 16: ["latch", "drift", "init"],
    17: ["osc", "chain3", "adapt"], 18: ["wells4", "subhopf", "wells_trap"], 19: ["adapt", "transient3", "burst"],
    20: ["lin", "sat"], 21: ["m1", "m2"], 22: ["rho0.3", "rho0.1", "rho0.04"],
    23: ["exact", "near", "third"], 24: ["impl"], 25: ["visible_s", "hidden_s", "hard"],
}

GROUP_TYPES = (11, 12, 24)

KICKLIKE = ["kick.1", "kick.2", "kick.g", "kick.hi", "pulse.1", "pulse.2", "pulse.g", "pulse.hi", "act.1", "inh.1", "seq.train",
            "seq.prbs", "seq.pp", "seq.chirp", "comp.seq", "comp.sim"]
READING = ["sil.1", "sil.2", "sil.g", "sil.1p", "param.1", "edge.w", "edge.rm"]


def pop(n, dims, **kw):
    d = {"n": int(n), "dims": list(dims)}
    d.update(kw)
    return d


def autoscale(lat):
    """z_scale := the passive amplitude of each latent dimension under the nominal input (nominal draw); dimensions that the
    passive input barely moves (< 10 % of the declared operational scale) and declared trap dimensions keep the declared scale."""
    if getattr(lat, "_scaled", False):
        return lat
    lvl = [1.0] * lat.n_u if lat.n_u > 1 else 1.0
    off = [0.0] * lat.n_u if lat.n_u > 1 else 0.0
    Z = lat_rk4(lat, lat.nominal(), [[0.0, off], [0.1, lvl]], t_end=2.0, dt=1e-3)
    amp = np.abs(Z).max(axis=0)
    decl = np.broadcast_to(np.asarray(lat.z_scale, float), (lat.k,)).copy()
    zs = np.where(amp < 0.1 * decl, decl, np.maximum(amp, 0.05))
    for d in lat.fixed_scale_dims:
        zs[d] = decl[d]
    lat.z_scale = tuple(float(a) for a in zs)
    lat.passive_amp = tuple(float(a) for a in amp)
    lat._scaled = True
    return lat


N_Y_RANGE = (9, 20)        # readout dimension: one distribution for every type (uniform integer, both ends included)


def set_readout(lat, rng, n_y=None, kinds=("relu", "softplus", "lin"), n_silent=None, scale=12.0, bias=(-0.6, 0.1), sparse=False,
                input_gain=True):
    """The readout dimension and the number of silent channels are drawn from ONE distribution for every type (n_y uniform in
    N_Y_RANGE, 0 - n_y // 4 silent channels), so readout_dim reveals nothing about the type; the type chooses only the channel kinds.
    input_gain: the readout units receive the stimulus as a multiplicative, expansive near-threshold gain input
    (latents.input_gain_factor); False only for type 1, whose readout is defined to be linear."""
    autoscale(lat)
    n_y = int(rng.integers(N_Y_RANGE[0], N_Y_RANGE[1] + 1))
    n_silent = int(rng.integers(0, n_y // 4 + 1))
    nf = lat.features(np.zeros((1, lat.k)), np.zeros((1, lat.n_u)), lat.nominal()).shape[1]
    fs = list(lat.z_scale) + [1.0] * (nf - lat.k)
    lat.ro = random_readout(rng, nf, n_y, kinds=kinds, n_silent=n_silent, scale=scale, bias=bias, sparse=sparse, n_u=lat.n_u,
                            feat_scale=fs[:nf], input_gain=input_gain)
    return lat


def size_small(irng, **kw):
    """The small regime: a mechanism-like circuit of 4-5 core units only (no nuisance populations; k = 1 only: the compactness rule
    k <= max(1, N_obs / 5)); unit counts are kept."""
    base = dict(gen_pairs=0, n_fol=0, fol_obs_frac=0.0, fol_target_frac=0.0, relay_obs_frac=0.0, relay_target_frac=0.0, n_relay=0,
                tau_c=float(irng.uniform(0.015, 0.03)), size_class="small")
    base.update(kw)
    base["n_fol"] = 0
    return base


def size_medium(irng, gen=True, **kw):
    """Standard systems: the unit counts given here are only relative population sizes; suite.apply_size rescales them to the
    system's size draw (one distribution for every type)."""
    base = dict(gen_pairs=1 if gen else 0, gen_freq=float(irng.uniform(8.5, 15.0)), n_fol=int(irng.integers(20, 45)),
                fol_obs_frac=0.85, fol_target_frac=0.25, tau_c=float(irng.uniform(0.012, 0.03)), size_class="std")
    base.update(kw)
    return base


size_large = size_medium


def _info(t, v, lat, **kw):
    d = {"type": t, "type_name": TYPE_NAMES[t], "variant": v, "k": lat.k, "trap": None, "trap_grade": None, "z_obs": None,
         "z_obs_fails_because": None, "exposing_families": [], "exposed_directions": None, "implementation_group": None,
         "observability": "every latent dimension is carried by observed core units (possibly through a nonlinear observation map)",
         "controllability": "every latent dimension is moved by kicks / currents on targetable core units",
         "expected_verdict": f"compact causal state, k = {lat.k}", "description": (lat.__doc__ or "").strip()}
    d.update(kw)
    return d


def _passive_bound(lat):
    """Declared bound on the hidden residual zres over passive trajectories (fraction of its operational scale), valid for every
    parameter draw with params_spread <= 2 and every passive input schedule within 0.55-1.45 (steps and multi-step schedules; measured
    over 60 draws per spread, scratch/bounds.py, with a margin of about 20 %): exactly 0 for the structural traps (numerically
    < 1e-6), eps * 1.5 for driven low-variance states, the slaving lag for slaved variables (proportional to tau2 / tau1)."""
    name = lat.name
    if name == "lowvar_trap":
        return max(1e-6, 1.5 * lat.eps)
    if name == "slaved":
        rho = lat.params["rho"][0]
        return {0.3: 0.54, 0.1: 0.31, 0.04: 0.16}.get(rho, 0.54)
    if name == "confounded":
        return max(1e-6, 0.6 * lat.delta)
    if name == "gated_memory":
        return 0.1           # the closed gate's sigmoid tail
    if name == "fast_slow":
        return 0.18          # the fast variable's lag behind h(S) at input steps
    return 1e-6


def _trap(t, v, lat, label, grade, zobs, why, fams, directions, **kw):
    return _info(t, v, lat, trap=label, trap_grade=grade, z_obs=zobs, z_obs_fails_because=why, exposing_families=fams,
                 exposed_directions=directions, passive_residual_bound=_passive_bound(lat), **kw)


# ============================================================================================================================
# Internal RK4 step per variant: the largest of 1 / 0.5 ms for which halving the step changes y by < 5e-4 of the readout floor
# (0.05 sd(y)) over 2 s with interventions (addendum requirement 1 asks for < 1e-3; scratch measurement in SYNTHETIC_BENCHMARK.md)
H_MAX = {(1, "*"): 5e-4, (2, "*"): 5e-4, (2, "fhn"): 2.5e-4, (5, "onset"): 5e-4, (7, "*"): 5e-4, (9, "burst"): 2.5e-4,
         (11, "*"): 5e-4, (12, "*"): 5e-4, (13, "torus"): 5e-4, (13, "ring"): 5e-4, (15, "osc"): 5e-4, (16, "latch"): 2.5e-4,
         (17, "*"): 5e-4, (18, "*"): 5e-4, (18, "subhopf"): 2.5e-4, (18, "wells4"): 2.5e-4, (19, "burst"): 5e-4, (20, "*"): 5e-4, (21, "*"): 5e-4,
         (22, "rho0.04"): 5e-4, (24, "*"): 5e-4}
DT, T_END = 0.001, 2.0      # the same output step and default duration for every system (no public field depends on the type)


def build_type(t: int, v: str, grng, irng, *, group_key: str, impl_key: str, impl_index: int = 0, decoy: bool = False,
               size: dict | None = None) -> dict:
    fn = globals()[f"_t{t:02d}"]
    out = fn(v, grng, irng, impl_index=impl_index, decoy=decoy, size=size or {})
    out["dt"], out["t_end"] = DT, T_END
    out["impl"]["h_max"] = H_MAX.get((t, v), H_MAX.get((t, "*"), 1e-3))
    return out


# 1 ---------------------------------------------------------------------------------------------------------------------------
def _t01(v, g, r, **_):
    if v == "osc2":
        lat = LinearSSM(g, modes=[("c", 9.0, 4.0)])
        set_readout(lat, g, 6, kinds=("lin",), n_silent=1, input_gain=False)
        impl = size_medium(r, pops=[pop(30, [0, 1], embed="dense", obs="relu", base=(-6, 4))])
    elif v == "chain3":
        lat = LinearSSM(g, modes=[("r", 0.04), ("r", 0.08), ("r", 0.16)], chain=[3.0, 3.0])
        set_readout(lat, g, 5, kinds=("lin",), input_gain=False)
        impl = size_medium(r, gen=False, pops=[pop(36, [0, 1, 2], embed="sparse", obs="softplus", base=(-4, 2))])
    else:
        lat = LinearSSM(g, modes=[("c", 6.0, 6.0), ("r", 0.06), ("r", 0.3)])
        set_readout(lat, g, 8, kinds=("lin",), n_silent=2, input_gain=False)
        impl = size_large(r, pops=[pop(60, [0, 1, 2, 3], embed="dense", obs="relu", base=(-8, 3))])
    return {"latent": lat, "impl": impl, "info": _info(1, v, lat)}


# 2 ---------------------------------------------------------------------------------------------------------------------------
def _t02(v, g, r, **_):
    if v == "hopf":
        lat = Hopf(g, freq=float(g.uniform(8.5, 12.0)))
        set_readout(lat, g, 6, kinds=("relu", "softplus"))
        impl = size_medium(r, gen=False, pops=[pop(30, [0, 1], obs=("relu", "relup"), base=(-7, 2))], n_fol=40)
        extra = {}
    elif v == "fhn":
        lat = FHN(g)
        set_readout(lat, g, 5, kinds=("softplus",), n_silent=1)
        impl = size_medium(r, gen=False, pops=[pop(24, [0, 1], embed="sparse", obs="relup", base=(-6, 2))], n_fol=30, h_max=5e-4)
        extra = {}
    else:
        lat = ShearHopf(g, freq=float(g.uniform(7.0, 10.0)))
        set_readout(lat, g, 8, kinds=("relu", "lin"), n_silent=1)
        impl = size_large(r, pops=[pop(50, [0, 1], obs="sat", base=(-4, 4))], gen_freq=float(r.uniform(13, 16)))
        extra = {}
    return {"latent": lat, "impl": impl, "info": _info(2, v, lat, notes="intervention effects are phase dependent", **extra)}


# 3 ---------------------------------------------------------------------------------------------------------------------------
def _t03(v, g, r, **_):
    if v == "small":
        lat = LeakyInt(g, taus=(float(g.uniform(0.2, 0.4)),), gains=(1.0,))
        set_readout(lat, g, 9, kinds=("relu", "softplus"), n_silent=3)
        impl = size_small(r, pops=[pop(4, [0], obs="relu", base=(1.0, 5.0), target_frac=1.0)])
    elif v == "twotau":
        lat = LeakyInt(g, taus=(0.06, 0.5), gains=(1.0, 1.0))
        set_readout(lat, g, 6, kinds=("relu", "lin"))
        impl = size_medium(r, pops=[pop(28, [0, 1], obs=("relu", "relup"), base=(-7, 2))])
    else:
        lat = LeakyInt(g, taus=(float(g.uniform(0.15, 0.3)),), gains=(1.0,))
        set_readout(lat, g, 12, kinds=("softplus", "relu"), n_silent=2)
        impl = size_large(r, pops=[pop(80, [0], embed="dense", obs="relu", base=(-8, 2))])
    return {"latent": lat, "impl": impl, "info": _info(3, v, lat)}


# 4 ---------------------------------------------------------------------------------------------------------------------------
def _t04(v, g, r, **_):
    if v == "small":
        lat = PerfectInt(g, k=1, beta=0.5)
        set_readout(lat, g, 9, kinds=("relu", "softplus"), n_silent=2)
        impl = size_small(r, pops=[pop(5, [0], obs="relu", base=(1.0, 4.0), target_frac=0.8)], n_fol=2)
    elif v == "signed":
        lat = PerfectInt(g, k=1, beta=1.5, mode="signed", u0=0.8)
        set_readout(lat, g, 6, kinds=("relu", "lin"))
        impl = size_medium(r, pops=[pop(24, [0], obs="softplus", base=(-5, 2))])
    else:
        lat = PerfectInt(g, k=2, beta=0.4, mode="plane", u0=1.0)
        set_readout(lat, g, 6, kinds=("relu", "softplus"))
        impl = size_medium(r, pops=[pop(30, [0, 1], obs=("relu", "relup"), base=(-7, 2))])
    return {"latent": lat, "impl": impl, "info": _info(4, v, lat, notes="memory is perfect while the input is off; kick effects persist")}


# 5 ---------------------------------------------------------------------------------------------------------------------------
def _t05(v, g, r, **_):
    pops = [pop(16, [0, 1], obs=("relu", "relup"), base=(-6, 2), tag="gate"), pop(16, [2], embed="sparse", obs="relu", base=(-3, 2), tag="memory"),
            pop(8, [0, 1, 2], obs=("relu", "relup"), base=(-6, 2), tag="mixed")]
    if v == "onset":
        lat = GatedMemory(g, mode="onset", th=0.3)
        info = _info(5, v, lat, notes="the gate opens at input onsets (s - a transient); gate-unit perturbations open it at other times")
    elif v == "level":
        lat = GatedMemory(g, mode="level", th=1.05)
        info = _info(5, v, lat, notes="the gate opens while the input level exceeds th ~ 1.05; below it the memory holds")
    else:
        lat = GatedMemory(g, mode="onset", th=1.35, trap=True)
        lat.params["w"] = (0.04, 0.1, "log")
        info = _trap(5, v, lat, "gate never opens passively", "medium", "z_obs = (s, a): buffer and adaptation; m stays 0",
                     "under passive input the gate threshold is never reached (s - a < 1.1 < th for u <= 1.4), so the memory m has "
                     "no passive variance; kicks / currents on gate units (s up, a down) open the gate and write the buffer into m, "
                     "and kicks on memory units set m directly - both persist for seconds and move the readout",
                     KICKLIKE + ["sil.1", "param.1"], "memory dimension m (index 2)")
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    lat.ro.R[:, 2] *= 2.0
    impl = size_medium(r, pops=pops)
    return {"latent": lat, "impl": impl, "info": info}


# 6 ---------------------------------------------------------------------------------------------------------------------------
def _t06(v, g, r, **_):
    if v == "small":
        lat = Bistable(g)
        set_readout(lat, g, 9, kinds=("relu", "softplus"), n_silent=3)
        impl = size_small(r, pops=[pop(5, [0], obs="relu", base=(0.5, 3.0), target_frac=0.8)], n_fol=2)
        info = _info(6, v, lat, notes="the input flips the switch above u_c ~ 0.8; pulses flip it depending on the state")
    elif v == "adapt":
        lat = Bistable(g, adapt=True)
        lat.params.update({"beta": (1.6, 0.1, "log"), "gamma": (3.0, 0.15, "log")})
        set_readout(lat, g, 6, kinds=("relu", "softplus"))
        impl = size_medium(r, pops=[pop(28, [0, 1], obs=("relu", "relup"), base=(-6, 2))])
        info = _info(6, v, lat)
    else:
        lat = Bistable(g, hidden=True)
        set_readout(lat, g, 6, kinds=("relu", "softplus"))
        impl = size_medium(r, pops=[pop(22, [0], obs=("relu", "relup"), base=(-6, 2)), pop(10, [1], obs="relu", base=(-3, 2),
                                                                                    tag="hidden_switch")])
        info = _trap(6, v, lat, "hidden bistable switch", "medium", "z_obs = z1 (visible switch)",
                     "the second switch z2 receives no input and rests in its lower well in every passive trajectory (zero passive "
                     "variance); a strong kick / pulse on its units flips it, which persistently lowers z1's threshold and multiplies "
                     "the readout gain by up to 2.5", KICKLIKE, "hidden switch z2 (index 1)")
    return {"latent": lat, "impl": impl, "info": info}


# 7 ---------------------------------------------------------------------------------------------------------------------------
def _t07(v, g, r, **_):
    if v == "wta3":
        lat = WTA(g, m=3)
        impl = size_medium(r, pops=[pop(36, [0, 1, 2], embed="sparse", obs="relu", base=(-4, 1))])
    elif v == "wta4":
        lat = WTA(g, m=4)
        impl = size_large(r, pops=[pop(64, [0, 1, 2, 3], embed="sparse", obs="relu", base=(-5, 1))])
    else:
        lat = WTA(g, m=3, alpha=1.3, beta=2.0)
        impl = size_medium(r, pops=[pop(36, [0, 1, 2], embed="sparse", obs="relup", base=(-4, 1))])
    set_readout(lat, g, 6, kinds=("relu",), n_silent=1)
    return {"latent": lat, "impl": impl, "info": _info(7, v, lat, notes="the winner depends on the state at the time of a perturbation")}


# 8 ---------------------------------------------------------------------------------------------------------------------------
def _t08(v, g, r, **_):
    if v in ("pi", "pid"):
        lat = Controller(g, mode=v)
        impl = size_medium(r, pops=[pop(30, list(range(lat.k)), obs=("relu", "relup"), base=(-6, 2))])
        info = _info(8, v, lat, notes="perfect adaptation: the plant returns to its set point after input steps and perturbations")
    else:
        lat = Controller(g, mode="setpoint")
        impl = size_medium(r, pops=[pop(24, [0, 1], obs=("relu", "relup"), base=(-6, 2)),
                                    pop(10, [2], obs="relu", base=(-3, 2), tag="setpoint")])
        info = _trap(8, v, lat, "silent set-point memory", "medium", "z_obs = (p, c): plant and integral controller",
                     "the reference r is a memory state (tau ~ 10 s) that no input moves: it is 0 in every passive trajectory; a "
                     "perturbation of its units shifts the regulated level of the plant for seconds", KICKLIKE + ["sil.1", "param.1"],
                     "set point r (index 2)")
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    lat.ro.R[:, 0] *= 2.0
    return {"latent": lat, "impl": impl, "info": info}


# 9 ---------------------------------------------------------------------------------------------------------------------------
def _t09(v, g, r, **_):
    if v == "burst":
        lat = FastSlow(g, mode="burst")
        impl = size_medium(r, gen=False, pops=[pop(32, [0, 1, 2], obs="relu", base=(-5, 2))], h_max=5e-4)
        info = _info(9, v, lat)
    elif v == "relay":
        lat = FastSlow(g, mode="relay")
        impl = size_medium(r, pops=[pop(28, [0, 1], obs=("relu", "relup"), base=(-6, 2))])
        info = _info(9, v, lat)
    else:
        lat = FastSlow(g, mode="slaved")
        impl = size_medium(r, pops=[pop(20, [0], obs=("relu", "relup"), base=(-6, 2)), pop(12, [1], obs="relu", base=(-3, 2),
                                                                                    tag="fast")])
        info = _trap(9, v, lat, "fast variable slaved to the slow manifold", "easy", "z_obs = S (slow variable)",
                     "passively the fast variable sits on F = h(S) (tau_F ~ 8 ms), so S alone predicts passive data; perturbations of "
                     "the fast units displace F from h(S), which feeds back into S and leaves lasting shifts",
                     KICKLIKE, "fast variable F (index 1)")
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    return {"latent": lat, "impl": impl, "info": info}


# 10 --------------------------------------------------------------------------------------------------------------------------
def _t10(v, g, r, **_):
    pops = [pop(30, [0, 1], obs=("relu", "relup"), base=(-6, 2)), pop(8, [2], obs="relu", base=(-2, 2), obs_frac=0.0, target_frac=0.0,
                                                           tag="mode_hidden")]
    if v == "osc":
        lat = HiddenMode(g, mode1="osc", th_up=0.6)
        info = _info(10, v, lat, observability="the mode is carried only by hidden (unobserved, non-targetable) units; it is "
                     "inferable from the observed dynamics (oscillation vs relaxation)",
                     controllability="the mode switches when x1 crosses th_up / th_dn (perturbations of x1 units)")
    elif v == "gain":
        lat = HiddenMode(g, mode1="gain", th_up=0.7)
        info = _info(10, v, lat, observability="the mode is carried only by hidden units; inferable from the input gain")
    else:
        lat = HiddenMode(g, mode1="osc", th_up=2.0, trap=True)
        # passive x1 <= g0 * 1.45 < 1.8 for every draw up to params_spread 2 (tight spreads); strong perturbations of x1 (above
        # th_up for ~40 ms) switch the mode on
        lat.params.update({"th_up": (2.0, 0.02, "lin"), "g0": (1.0, 0.05, "log"), "s_up": (150.0, 0.1, "log"),
                           "tau": (0.1, 0.1, "log")})
        info = _trap(10, v, lat, "hidden mode never switched passively", "hard", "z_obs = (x1, x2)",
                     "passive inputs (0.55-1.45) keep x1 <= 1.45 g0 < 1.8 < th_up = 2.0, so the hidden mode stays 0 in every passive "
                     "trajectory; a perturbation that drives x1 above th_up switches the mode on, and the continuous state then "
                     "oscillates for the rest of the trajectory", KICKLIKE, "hidden mode m (index 2), reachable only through x1")
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    lat.ro.R[:, 2] = 0.0
    impl = size_medium(r, pops=pops)
    return {"latent": lat, "impl": impl, "info": info}


# 11 --------------------------------------------------------------------------------------------------------------------------
def _t11(v, g, r, impl_index=0, **_):
    lat = Hopf(g, freq=9.5, lam=15.0, uc=0.45)
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    R = [3, 6, 12][impl_index % 3]
    n = {3: 36, 6: 48, 12: 72}[R]
    impl = size_medium(r, gen=(impl_index % 2 == 0), pops=[pop(n, [0, 1], embed="clones", clone=R, obs=("relu", "relup"), base=(-6, 2))],
                       n_fol=int(r.integers(20, 40)))
    info = _info(11, f"r{R}", lat, notes=f"each latent direction is carried by clone groups of {R} units with identical loadings; "
                 "single-unit interventions have 1/R-scaled effects, silencing one unit is largely compensated",
                 redundancy=R)
    return {"latent": lat, "impl": impl, "info": info}


# 12 --------------------------------------------------------------------------------------------------------------------------
def _t12(v, g, r, impl_index=0, decoy=False, **_):
    if decoy:
        lat = HopfSlow(g, freq=8.5, tau3=0.12, lam=25.0)
    else:
        lat = HopfSlow(g, freq=12.0, tau3=0.25)
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    j = impl_index % 4
    if j == 0:
        impl = size_medium(r, pops=[pop(36, [0, 1, 2], embed="dense", obs=("relu", "relup"), base=(-7, 2))], n_fol=30, tau_c=0.02)
        style = "dense random mixing, rectified"
    elif j == 1:
        impl = size_medium(r, gen=False, pops=[pop(60, [0, 1, 2], embed="sparse", obs="relup", base=(-4, 1))],
                           n_fol=60, tau_c=0.015)
        style = "sparse tuning, expansive"
    elif j == 2:
        impl = size_medium(r, pops=[pop(15, [0, 1, 2], embed="dense", obs="sat", base=(-2, 4))], n_fol=10, tau_c=0.03)
        style = "small dense population, saturating"
    else:
        impl = size_large(r, pops=[pop(48, [0, 1, 2], embed="clones", clone=4, obs="softplus", base=(-4, 2))], tau_c=0.025)
        style = "redundant clones of 4, softplus, large nuisance population"
    info = _info(12, "decoy" if decoy else f"impl{j}", lat, implementation_style=style,
                 notes="implementations of one group share the latent dynamics, readout and parameter draws; the decoy has "
                       "different dynamics with a similar look" if not decoy else "DECOY: unrelated dynamics (different frequency, "
                       "build-up time and damping) implemented like the group members; must not be judged equivalent")
    return {"latent": lat, "impl": impl, "info": info}


# 13 --------------------------------------------------------------------------------------------------------------------------
def _t13(v, g, r, **_):
    if v == "ring":
        lat = Ring(g, n_rings=1, freqs=(float(g.uniform(9, 11)),), pins=(6.0,))
        impl = size_medium(r, gen=False, pops=[pop(40, [0, 1], embed="ring", obs="exp", base=(-2, 2), kappa=(8, 12))], n_fol=30)
        note = "bump (von Mises-like) code of a ring attractor: x_i = A exp((kappa cos(th - phi_i) - kappa)/w)"
    elif v == "torus":
        lat = Ring(g, n_rings=2, freqs=(10.0, 7.0), pins=(6.0, 5.0))
        impl = size_large(r, gen=False, pops=[pop(30, [0, 1], embed="ring", obs="exp", base=(-2, 2), kappa=(8, 12)),
                                              pop(30, [2, 3], embed="ring", obs="exp", base=(-2, 2), kappa=(8, 12)),
                                              pop(30, [0, 1, 2, 3], embed="dense", obs="exp", base=(-2, 2), kappa=(8, 12))])
        note = "two rings (torus): single-ring bump units and conjunctive units"
    else:
        lat = LinearSSM(g, modes=[("c", 7.0, 5.0)])
        impl = size_medium(r, pops=[pop(36, [0, 1], embed="dense", obs="sat", base=(-2, 6))])
        note = "monotone saturating (rectified tanh) tuning with heterogeneous thresholds"
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    return {"latent": lat, "impl": impl, "info": _info(13, v, lat, notes=note)}


# 14 --------------------------------------------------------------------------------------------------------------------------
def _t14(v, g, r, **_):
    # core_scale: amplitude of the (tonically active, weakly tuned) causal core relative to the normalised nuisance units
    if v == "ratio10":
        lat = LinearSSM(g, modes=[("c", 5.0, 5.0)])
        cs = 0.3
    elif v == "ratio100":
        lat = LeakyInt(g, taus=(0.2,), gains=(1.0,))
        cs = 0.1
    else:
        lat = PerfectInt(g, k=1, beta=0.5)
        cs = 0.03
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    impl = size_large(r, pops=[pop(24, list(range(lat.k)), obs="relu", base=(2.0, 6.0))], core_scale=cs,
                      fol_u_w=(3.0, 15.0), fol_gen_w=(4.0, 12.0), fol_core_w=0.2, gen_pairs=2, gen_scale=1.5)
    info = _info(14, v, lat, notes="the causal core has small tuning amplitude; follower / generator units with large variance "
                 "(input-locked and rhythmic) dominate the observed variance but never influence z or y",
                 nuisance_variance_ratio=v.replace("ratio", ""))
    return {"latent": lat, "impl": impl, "info": info}


# 15 --------------------------------------------------------------------------------------------------------------------------
def _t15(v, g, r, **_):
    if v == "easy":
        lat = LowVarTrap(g, eps=0.25)
        pops = [pop(16, [0], obs=("relu", "relup"), base=(-6, 2)), pop(20, [1], obs="relu", base=(-3, 2), target_frac=0.8, tag="hidden"),
                pop(8, [0, 1], obs=("relu", "relup"), base=(-6, 2))]
        grade = "easy (eps = 0.25, 20 exposed units, 80 % targetable)"
    elif v == "medium":
        lat = LowVarTrap(g, eps=0.05)
        pops = [pop(20, [0], obs=("relu", "relup"), base=(-6, 2)), pop(10, [1], obs="relu", base=(-3, 2), obs_frac=0.8, target_frac=0.5,
                                                            tag="hidden"), pop(6, [0, 1], obs=("relu", "relup"), base=(-6, 2))]
        grade = "medium (eps = 0.05, 10 exposed units, 50 % targetable)"
    elif v == "hard":
        lat = LowVarTrap(g, eps=0.0)
        pops = [pop(24, [0], obs=("relu", "relup"), base=(-6, 2)), pop(6, [1], obs="relu", base=(-3, 2), obs_frac=0.5, target_frac=0.34,
                                                            kappa=(3, 6), tag="hidden"), pop(4, [0, 1], obs=("relu", "relup"), base=(-6, 2))]
        grade = "hard (eps = 0: zero passive variance, 6 weak exposed units, 34 % targetable)"
    else:
        lat = LowVarTrap(g, eps=0.0, osc=True)
        pops = [pop(24, [0, 1], obs=("relu", "relup"), base=(-6, 2)), pop(10, [2], obs="relu", base=(-3, 2), target_frac=0.5, tag="hidden")]
        grade = "medium (oscillator task; eps = 0)"
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    info = _trap(15, v, lat, "intervention-sensitive low-variance state", grade, "z_obs = task state (all dims but the last)",
                 "the hidden slow state z2 (tau ~ 0.8 s) is driven by the input only with strength eps, so its passive variance is "
                 "eps^2 of its operational range; it sets the task's input gain and offset and enters the readout directly and "
                 "multiplicatively, so perturbations of its units change the readout for ~1 s", KICKLIKE + READING,
                 "hidden gain state (last index)")
    return {"latent": lat, "impl": size_medium(r, pops=pops), "info": info}


# 16 --------------------------------------------------------------------------------------------------------------------------
def _t16(v, g, r, **_):
    if v == "latch":
        lat = Context(g, mode="latch")
        impl = size_medium(r, gen=False, pops=[pop(36, [0, 1, 2], obs=("relu", "relup"), base=(-6, 2))])
        info = _info(16, v, lat, notes="the context (peak input level) sets the rhythm frequency of the task oscillator")
        out = {}
    elif v == "drift":
        lat = Context(g, mode="drift")
        impl = size_medium(r, pops=[pop(30, [0, 1], obs=("relu", "relup"), base=(-6, 2))])
        info = _info(16, v, lat, notes="slow context (tau_c ~ 3 s) that tracks the task and sets its input gain")
        out = {}
    else:
        lat = Context(g, mode="init")
        impl = size_medium(r, pops=[pop(20, [0], obs=("relu", "relup"), base=(-6, 2)), pop(12, [1], obs="relu", base=(-3, 2),
                                                                                tag="context")])
        info = _trap(16, v, lat, "context memory set only by initial conditions / interventions", "easy",
                     "z_obs = z1 (task)", "the context c is a perfect memory with no passive drive: it is 0 in passive trajectories "
                     "from rest (initial-condition changes reveal it); it sets the task gain and offset for the whole trajectory",
                     KICKLIKE + ["sil.1p", "param.1"], "context c (index 1)")
        out = {}
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    out.update({"latent": lat, "impl": impl, "info": info})
    return out


# 17 --------------------------------------------------------------------------------------------------------------------------
def _t17(v, g, r, **_):
    if v == "osc":
        lat = LinearSSM(g, modes=[("c", 7.0, 3.0)])
        pops = [pop(24, [0], obs=("relu", "relup"), base=(-6, 2), tag="seen"), pop(12, [1], obs="relu", obs_frac=0.0, tag="unseen")]
        hidden = "z2"
    elif v == "chain3":
        lat = LinearSSM(g, modes=[("r", 0.05), ("r", 0.1), ("r", 0.2)], chain=[3.0, 3.0])
        pops = [pop(24, [2], obs=("relu", "relup"), base=(-6, 2), tag="seen"), pop(16, [0, 1], obs="relu", obs_frac=0.0,
                                                                        tag="unseen")]
        hidden = "z1, z2 (upstream of the observed z3)"
    else:
        lat = Adaptation(g, tau_a=0.3)
        pops = [pop(24, [0], obs=("relu", "relup"), base=(-6, 2), tag="seen"), pop(12, [1], obs="relu", obs_frac=0.0, tag="unseen")]
        hidden = "adaptation a"
    set_readout(lat, g, 6, kinds=("relu", "lin"))
    impl = size_medium(r, pops=pops, fol_tags=["seen"])
    info = _info(17, v, lat, observability=f"observed units (and the followers) carry only part of z; {hidden} is carried by "
                 "unobserved (partly targetable) units and must be inferred from the history of the observed units",
                 notes="delay / history needed")
    return {"latent": lat, "impl": impl, "info": info}


# 18 --------------------------------------------------------------------------------------------------------------------------
def _t18(v, g, r, **_):
    if v == "wells4":
        lat = MultiWell(g, trap=False)
        impl = size_medium(r, pops=[pop(30, [0, 1], obs=("relu", "relup"), base=(-6, 2))])
        info = _info(18, v, lat, notes="four wells; the input tilts the landscape; perturbations move between basins")
    elif v == "subhopf":
        lat = SubHopf(g, freq=float(g.uniform(7, 10)))
        impl = size_medium(r, gen=False, pops=[pop(30, [0, 1], obs=("relu", "relup"), base=(-6, 2))])
        info = _info(18, v, lat, notes="rest and a large limit cycle coexist; perturbations can start / stop the rhythm")
    else:
        lat = MultiWell(g, trap=True)
        impl = size_medium(r, pops=[pop(20, [0], obs=("relu", "relup"), base=(-6, 2)), pop(12, [1], obs="relu", base=(-3, 2),
                                                                                tag="unvisited")])
        info = _trap(18, v, lat, "passively unvisited attractors", "medium", "z_obs = z1",
                     "the landscape is symmetric in z2 and the input acts along z1 only, so every passive trajectory keeps z2 = 0 "
                     "exactly; perturbations of the z2 units reach the wells at (0, +-1), which persist and change the readout",
                     KICKLIKE + ["sil.1", "param.1"], "z2 (index 1)")
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    return {"latent": lat, "impl": impl, "info": info}


# 19 --------------------------------------------------------------------------------------------------------------------------
def _t19(v, g, r, **_):
    if v == "adapt":
        lat = Adaptation(g)
        impl = size_medium(r, pops=[pop(28, [0, 1], obs=("relu", "relup"), base=(-6, 2))])
    elif v == "transient3":
        lat = Transient3(g)
        impl = size_medium(r, pops=[pop(32, [0, 1, 2], obs=("relu", "relup"), base=(-6, 2))])
    else:
        lat = BurstOnset(g)
        impl = size_large(r, gen=False, pops=[pop(48, [0, 1, 2, 3], obs=("relu", "relup"), base=(-7, 2))])
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    info = _info(19, v, lat, notes="intervention effects differ between the onset transient and the steady state")
    return {"latent": lat, "impl": impl, "info": info}


# 20 --------------------------------------------------------------------------------------------------------------------------
def _k_full(size):
    """k of the non-compressible controls: ~0.72 x the expected number of observed units (the benchmark calls a state compact when
    k <= max(1, N_obs / 5); implement() caps N_obs at 5 k / 3, so k >= 3 x the compactness bound)."""
    n_obs = size.get("p_obs", 0.8) * size.get("N", 100)
    return int(max(12, math.ceil(0.72 * n_obs)))


def _t20(v, g, r, size=None, **_):
    kk = _k_full(size or {})
    lat = SlowModes(g, k=kk, input_modes=None, sat_c=3.0 if v == "sat" else None)
    set_readout(lat, g, kinds=("lin", "lin", "softplus"))
    impl = size_medium(r, gen=False, pops=[pop(int(math.ceil(1.3 * kk)), list(range(kk)), obs="relu", base=(-5, 2),
                                               min_n=int(math.ceil(1.25 * kk)))], max_obs=int(5 * kk // 3))
    info = _info(20, v, lat, k="none", k_full=kk, expected_verdict="no compact causal state (the state needs all "
                 f"{kk} dimensions; k >= 3 x N_obs / 5)",
                 notes="near-normal slow modes (decay 0.25-1.2 s, frequencies 0.4-18 Hz), every mode driven by the input, "
                       "excited by single units and read out comparably (flat Hankel spectrum)")
    return {"latent": lat, "impl": impl, "info": info}


# 21 --------------------------------------------------------------------------------------------------------------------------
def _t21(v, g, r, size=None, **_):
    kk = _k_full(size or {})
    m = {"m1": 1, "m2": 2}[v]
    lat = SlowModes(g, k=kk, input_modes=m)
    set_readout(lat, g, kinds=("lin", "lin", "softplus"))
    impl = size_medium(r, gen=False, pops=[pop(int(math.ceil(1.3 * kk)), list(range(kk)), obs="relu", base=(-5, 2),
                                               min_n=int(math.ceil(1.25 * kk)))], max_obs=int(5 * kk // 3))
    info = _trap(21, v, lat, "observationally compressible, interventionally non-compressible", "control",
                 f"z_obs = the {m}-dimensional passive mode subspace (Q[:, :{m}]^T z)",
                 f"the input loads only {m} of {kk} modes, so passive trajectories from rest (and restarts from nominal passive "
                 f"trajectories) stay exactly in an {m}-dimensional subspace; the readout reads every mode and single-unit "
                 "interventions excite all of them comparably", KICKLIKE + READING, f"all {kk - m} non-passive modes", k="none",
                 k_full=kk, expected_verdict=f"no compact causal state under interventions (k = {kk} >= 3 x N_obs / 5), although "
                                             f"a {m}-dimensional passive description exists")
    return {"latent": lat, "impl": impl, "info": info}


# 22 --------------------------------------------------------------------------------------------------------------------------
def _t22(v, g, r, **_):
    rho = float(v.replace("rho", ""))
    lat = Slaved(g, rho=rho)
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    lat.ro.R[:, 1] *= 2.5
    pops = [pop(20, [0], obs=("relu", "relup"), base=(-6, 2)), pop(14, [1], obs="relu", base=(-3, 2), tag="slaved")]
    grade = {0.3: "easy", 0.1: "medium", 0.04: "hard"}[rho]
    info = _trap(22, v, lat, "slaved (adiabatically aliased) variable", f"{grade} (tau2 / tau1 = {rho})", "z_obs = z1",
                 "z2 relaxes to h(z1) within tau2 = rho tau1, so passive data satisfy z2 = h(z1) and z1 alone predicts them (the "
                 "readout, dominated by z2, looks like a function of the input history); perturbations of z2's units break "
                 "z2 = h(z1), and the deviation feeds back into z1 (lasting shift)", KICKLIKE + READING, "z2 - h(z1)")
    return {"latent": lat, "impl": size_medium(r, pops=pops), "info": info}


# 23 --------------------------------------------------------------------------------------------------------------------------
def _t23(v, g, r, **_):
    if v == "exact":
        lat = Confounded(g, delta=0.0)
        grade = "hard (exact passive aliasing a = c)"
    elif v == "near":
        lat = Confounded(g, delta=0.05)
        grade = "medium (filters differ by 5 %)"
    else:
        lat = Confounded(g, delta=0.0, third=True)
        grade = "hard (exact aliasing + an independent visible state)"
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    pops = [pop(14, [0], obs=("relu", "relup"), base=(-6, 2), tag="a"), pop(14, [1], obs=("relu", "relup"), base=(-6, 2), tag="c"),
            pop(8, list(range(lat.k)), obs=("relu", "relup"), base=(-6, 2))]
    impl = size_medium(r, pops=pops, fol_core_w=1.5, fol_obs_frac=0.95)
    info = _trap(23, v, lat, "intervention confounding (common-cause aliasing)", grade, "z_obs = (a + c)/2 (common mode)"
                 + (" and b" if lat.k == 3 else ""),
                 "a and c are driven by the same input through the same filter, so the input confounds them: passive data never "
                 "separate them (a = c). Interventions on a- or c-units separate them; their couplings, nonlinearity and readout "
                 "weights differ, so effects depend on which one was hit. Many follower units read them and correlate strongly "
                 "with the readout without any causal effect", KICKLIKE + READING, "a - c")
    return {"latent": lat, "impl": impl, "info": info}


# 24 --------------------------------------------------------------------------------------------------------------------------
def _t24(v, g, r, impl_index=0, **_):
    lat = LinearSSM(g, modes=[("c", 8.0, 5.0), ("r", 0.25)])
    set_readout(lat, g, 6, kinds=("relu", "softplus", "lin"))
    R = [4, 8, 2][impl_index % 3]
    impl = size_medium(r, pops=[pop(12 * R if R < 8 else 64, [0, 1, 2], embed="clones", clone=R, obs=("relu", "relup"), base=(-6, 2))])
    info = _info(24, f"clones{R}", lat, redundancy=R,
                 notes=f"clone groups of {R} units share identical loadings (identical columns of L): a kick or current on any "
                       "member realises the same dz, and pulses realise the same dz as kicks; equivalence classes in "
                       "'realisation_classes'")
    return {"latent": lat, "impl": impl, "info": info}


# 25 --------------------------------------------------------------------------------------------------------------------------
def _t25(v, g, r, **_):
    lat = Aliased(g)
    set_readout(lat, g, 6, kinds=("relu", "softplus"))
    if v == "visible_s":
        pops = [pop(16, [0], obs=("relu", "relup"), base=(-6, 2)), pop(14, [1], obs="relu", base=(-3, 2), tag="p"),
                pop(10, [2], obs="relu", base=(-3, 2), tag="s")]
        grade = "easy (switch units observed)"
    elif v == "hidden_s":
        pops = [pop(16, [0], obs=("relu", "relup"), base=(-6, 2)), pop(14, [1], obs="relu", base=(-3, 2), tag="p"),
                pop(10, [2], obs="relu", base=(-3, 2), obs_frac=0.0, tag="s")]
        grade = "medium (switch units unobserved)"
    else:
        pops = [pop(20, [0], obs=("relu", "relup"), base=(-6, 2)), pop(6, [1], obs="relu", base=(-3, 2), target_frac=0.34, kappa=(4, 8), tag="p"),
                pop(6, [2], obs="relu", base=(-3, 2), obs_frac=0.0, target_frac=0.34, tag="s")]
        grade = "hard (switch unobserved, few weak p / s targets)"
    impl = size_medium(r, pops=pops, fol_tags=["core", "p"] if v != "visible_s" else None)
    info = _trap(25, v, lat, "same immediate readout, different causal state", grade, "z_obs = a",
                 "states that differ only in the hidden switch s have identical readout and identical passive futures (p = 0 "
                 "passively), so passive data cannot distinguish them; a perturbation of the p units moves the readout in "
                 "opposite directions for s = 0 and s = 1, and strong perturbations of the s units flip s invisibly",
                 KICKLIKE + ["sil.1", "param.1"], "switch s (index 2), exposed through p (index 1)")
    return {"latent": lat, "impl": impl, "info": info}
