"""Microscopic simulation engine of p4synth.

A system is a population of N units in four (hidden) roles; the microstate is the vector of the units' state variables v (public
unit order) followed by an internal copy of z (k values, a numerical mirror of L (v_c - b) that makes restarts bit-exact):

CORE units (the physical implementation of the causal state z in R^k): linear leaky units with a shared time constant tau_c. The
    true causal state is z := L (v_c - b) (L = pinv(E), L E = I). Each unit's ON-MANIFOLD potential is vhat_i = b_i + E_i . z;
    its off-manifold detail w_i = v_i - vhat_i (L w = 0) is a local, output-less component of the membrane state.
    synaptic output   o_i = outm_i g_i (vhat_i - theta_i)      (nominal gain 1, threshold theta_i = b_i; silence: outm_i = 0)
    population signal zh = L o                                 (read by the recurrent synapses W = E L, the quasi-static
                                                                interneuron layer computing F, the followers, the relays and
                                                                the readout)
    dynamics          tau_c dv_i/dt = -(v_i - b_i) + inm_i [E_i . zh + a_i E_F,i . tau_c F(zh, u) + sum_q (f_iq - 1) W_iq o_q]
                                      + a_i I_i(t)                                     (a_i = 1 / time-constant factor)
    so a time-constant factor scales the unit's integration of the latent drive and of currents, while the recurrent drive and the
    leak stay common. Every reader sees the core only through z and every unit shares the leak, so dz/dt = L dv/dt is a closed
    function of z, the input and the configuration for EVERY microstate and EVERY intervention (nominal: dz/dt = L E_F F(z, u) +
    L I / tau_c; silence, param and edge_scale add k x k terms; a kick on unit i is clipped on its on-manifold potential): equal
    z => equal futures.
GEN units (optional nuisance rhythm): Wilson-Cowan E-I pairs in voltage form, rate a = g sigma((v - theta)/s), driven by u,
    bias-balanced so v = 0 is the rest state for every parameter draw.
RELAY units (input relays): linear leaky units driven by the stimulus u and, weakly, by 1-2 core outputs; their graded outputs
    (v - b) feed the followers, so the input reaches the downstream population through a two-stage cascade. They never affect z or y.
FOL units (followers / downstream population): a sparse recurrent linear network (each reads 1-3 core outputs, the generator
    rates, one relay and 2-3 other followers' graded outputs v - b; spectral radius of the follower coupling <= 0.6). Followers never
    affect z or y. They are integrated after the core with the SAME RK4 stage inputs a joint RK4 would use (identical to a joint
    integration, much cheaper).

Readout y = G(zh, u) (algebraic). Observations x_i = h_i(.) per unit (rectified / expansive / saturating / linear / exponential)
of the unit's membrane state (core units: of b + g (v - b - dtheta), so the detail is observed).
Integration: classical RK4 with step h = dt / n_sub on the output grid (h <= h_max; refined by powers of 2 in output steps where a
time-constant factor < 1 or a gain factor > 1 is in force, integrate.step_refinement); every event time lies on the grid, so the right-hand
side is constant within a step and a counterfactual twin is bit-identical to its intervention trajectory up to and including the
first event's onset sample (outputs follow the pre-event rule: the sample at t_n uses the configuration in force before t_n).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from scipy import sparse as _sparse

from . import protocol as P

SIM_SOURCES = ("engine.py", "integrate.py", "latents.py", "tlatents.py", "tlatents2.py", "impl.py", "types.py", "system.py",
               "suite.py", "protocol.py", "controls.py")


def _code_hash() -> str:
    """sha256 of every source file that can change a simulated trajectory (the engine id changes whenever the code changes)."""
    import hashlib
    import os
    d = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for fn in SIM_SOURCES:
        with open(os.path.join(d, fn), "rb") as fh:
            h.update(fn.encode() + b"\0" + fh.read())
    return h.hexdigest()[:16]


ENGINE_ID = "p4synth-2.0+" + _code_hash()

CORE, GEN, FOL, RELAY = 0, 1, 2, 3

# observation kinds
OBS_LIN, OBS_RELU, OBS_RELUP, OBS_SAT, OBS_SOFTPLUS, OBS_EXP, OBS_SIG = range(7)
OBS_NAMES = {OBS_LIN: "linear (mixed sign)", OBS_RELU: "rectified linear", OBS_RELUP: "rectified power (expansive)",
             OBS_SAT: "rectified saturating (tanh)", OBS_SOFTPLUS: "softplus", OBS_EXP: "exponential (bump code)",
             OBS_SIG: "sigmoid rate"}

# Wilson-Cowan generator base parameters (found by a numerical search, scratch/wc_sweep.py): Hopf onset at u ~ 0.38, rhythm
# 11-13 Hz for u in [0.6, 1.4], oscillation up to u ~ 2.5; frequency scales as 1 / (time-constant factor).
WC_BASE = dict(tE=0.0195, tI=0.0277, wEE=8.4525, wEI=13.5427, wIE=10.2905, wII=1.8198, thE=2.7492, thI=5.1362,
               sE=0.8522, sI=1.4693, hE=4.6745, hI=2.2883)


def _sig(x):
    return 0.5 * (1.0 + np.tanh(0.5 * x))


def observe(kind: np.ndarray, v: np.ndarray, th: np.ndarray, s: np.ndarray, w: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Vectorised observation map h(v) per column (v: (T, n) or (n,))."""
    out = np.empty_like(v)
    for kd in np.unique(kind):
        c = kind == kd
        d = v[..., c] - th[c]
        if kd == OBS_LIN:
            out[..., c] = s[c] * d
        elif kd == OBS_RELU:
            out[..., c] = s[c] * np.maximum(d, 0.0)
        elif kd == OBS_RELUP:
            out[..., c] = s[c] * np.maximum(d, 0.0) ** p[c] / (w[c] ** (p[c] - 1.0))
        elif kd == OBS_SAT:
            out[..., c] = w[c] * np.tanh(s[c] * np.maximum(d, 0.0) / w[c])
        elif kd == OBS_SOFTPLUS:
            out[..., c] = s[c] * w[c] * np.logaddexp(0.0, d / w[c])
        elif kd == OBS_EXP:
            out[..., c] = s[c] * np.exp(np.clip(d / w[c], -60.0, 5.0))
        elif kd == OBS_SIG:
            out[..., c] = s[c] * _sig(d / w[c])
        else:  # pragma: no cover
            raise ValueError(kd)
    return out


# ------------------------------------------------------------------------------------------------------------------ static spec
@dataclass
class Spec:
    """Static definition of one system (structure, nominal values and parameter-draw spreads). All arrays in role-local order;
    `perm` maps public unit id -> (role, local index)."""
    name: str
    k: int
    n_u: int
    latent: Any                           # latents.Latent instance
    group_key: str                        # z-level parameter draws are seeded by (group_key, params_seed)
    impl_key: str                         # implementation-level draws by (impl_key, params_seed)
    role: np.ndarray                      # (N,) role of public unit u
    loc: np.ndarray                       # (N,) local index of public unit u within its role
    # core
    E: np.ndarray                         # (Nc, k) nominal embedding
    L: np.ndarray                         # (k, Nc) left inverse, L E = I
    b: np.ndarray                         # (Nc,) rest potentials
    tau_c: float
    tau_c_sd: float
    # generator (Ng = 2 * n_pairs, order E0, I0, E1, I1, ...)
    gen: dict = field(default_factory=dict)   # keys: tau (Ng), W (Ng,Ng), th (Ng), s (Ng), h (Ng, n_u), tau_sd
    # followers
    tau_f: np.ndarray = None              # (Nf,)
    tau_f_sd: float = 0.2
    b_f: np.ndarray = None                # (Nf,)
    W_fc: np.ndarray = None               # (Nf, Nc) (sparse content, stored dense)
    W_fg: np.ndarray = None               # (Nf, Ng)
    B_f: np.ndarray = None                # (Nf, n_u)
    fol_in_sd: float = 0.25               # log-sd of follower input weights across draws
    # relays
    tau_r: np.ndarray = None              # (Nr,)
    b_r: np.ndarray = None                # (Nr,)
    B_r: np.ndarray = None                # (Nr, n_u)
    W_fr: np.ndarray = None               # (Nf, Nr) follower <- relay (graded relay output v - b)
    W_ff: np.ndarray = None               # (Nf, Nf) layer-B follower <- layer-A follower (graded output v - b_f)
    fol_layer: np.ndarray = None          # (Nf,) 0 = layer A, 1 = layer B
    W_rc: np.ndarray = None               # (Nr, Nc) relay <- core synaptic output (weak)
    # observation per public unit
    obs_kind: np.ndarray = None
    obs_th: np.ndarray = None
    obs_s: np.ndarray = None
    obs_w: np.ndarray = None
    obs_p: np.ndarray = None
    observed: list = None
    # admissible ranges per public unit (state variable)
    lo: np.ndarray = None
    hi: np.ndarray = None
    h_max: float = 1e-3                   # largest internal RK4 step (s)
    kick_strong: float = float("inf")     # internal size above which a core kick refines the step afterwards (3 x moderate)
    noise_scale: np.ndarray = None        # (N,) process-noise scale per unit (state units / sqrt(s) at sd = 1)

    @property
    def N(self) -> int:
        return int(self.role.size)

    @property
    def Nc(self) -> int:
        return int(self.E.shape[0])

    @property
    def Ng(self) -> int:
        return int(len(self.gen.get("tau", [])))

    @property
    def Nf(self) -> int:
        return 0 if self.tau_f is None else int(self.tau_f.size)

    @property
    def Nr(self) -> int:
        return 0 if self.tau_r is None else int(self.tau_r.size)

    @property
    def rest(self) -> np.ndarray:
        """Rest microstate (public order): core at b (z = 0), generator at 0, followers at b_f; independent of the draw."""
        v = np.zeros(self.N)
        v[self.units_of(CORE)] = self.b
        if self.Nf:
            v[self.units_of(FOL)] = self.b_f
        if self.Nr:
            v[self.units_of(RELAY)] = self.b_r
        return v

    def units_of(self, role: int) -> np.ndarray:
        """Public ids of the units of a role, in local order."""
        ids = np.nonzero(self.role == role)[0]
        return ids[np.argsort(self.loc[ids])]


# ------------------------------------------------------------------------------------------------------------------ draws
def _rng(*keys) -> np.random.Generator:
    import hashlib
    h = hashlib.sha256(repr(keys).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


@dataclass
class Draw:
    """The system compiled for one parameter draw (and weight-noise draw)."""
    spec: Spec
    P: dict                   # latent parameters
    f: Callable               # latent vector field f(z, u) -> (k,)
    E: np.ndarray             # (Nc, k) identity-feedback embedding (calibrated; W = E L cancels the leak on the manifold)
    EF: np.ndarray            # (Nc, k) interneuron-pathway projection of tau_c F (structural weight noise acts here)
    tau_c: float
    gen_tau: np.ndarray
    gen_W: np.ndarray
    gen_h: np.ndarray
    gen_a0: np.ndarray        # nominal rest output (bias balance)
    tau_f: np.ndarray
    W_fc: np.ndarray
    W_fg: np.ndarray
    B_f: np.ndarray
    W_fc_sp: Any = None       # sparse copy of W_fc (followers read 1-4 core units each)
    tau_r: np.ndarray = None
    B_r: np.ndarray = None
    W_fr: np.ndarray = None
    W_ff: np.ndarray = None
    W_rc: np.ndarray = None


NOMINAL_SEED = 0
KICK_REFINE_STEPS = 100    # output steps (100 ms at dt = 1 ms) of refined integration after a large core kick (its transient)
KICK_REFINE = 8            # substep multiplier in that window (review v3.3, C1: the fast transient a +-9 m_s jump starts)


def compile_draw(spec: Spec, params_seed: int, spread: float = 1.0, weight_noise: dict | None = None) -> Draw:
    nominal = int(params_seed) == NOMINAL_SEED
    s = 0.0 if nominal else float(spread)
    rz = _rng("z", spec.group_key, int(params_seed))
    ri = _rng("impl", spec.impl_key, int(params_seed))
    Pz = spec.latent.draw(rz, s)
    f = spec.latent.field(Pz)
    tau_c = spec.tau_c * math.exp(s * spec.tau_c_sd * ri.standard_normal())
    E = spec.E.copy()
    EF = E
    gen_tau = gen_W = gen_h = gen_a0 = None
    Ng = spec.Ng
    if Ng:
        g = spec.gen
        fac = math.exp(s * g.get("tau_sd", 0.1) * ri.standard_normal())          # one factor per system: rhythm frequency
        gen_tau = np.asarray(g["tau"], float) * fac * np.exp(s * 0.03 * ri.standard_normal(Ng))
        gen_W = np.asarray(g["W"], float) * np.exp(s * 0.05 * ri.standard_normal((Ng, Ng)))
        gen_h = np.asarray(g["h"], float) * math.exp(s * g.get("h_sd", 0.15) * ri.standard_normal())
        gen_a0 = _sig((0.0 - np.asarray(g["th"])) / np.asarray(g["s"]))
    tau_f = W_fc = W_fg = B_f = None
    if spec.Nf:
        tau_f = spec.tau_f * np.exp(s * spec.tau_f_sd * ri.standard_normal(spec.Nf))
        gin = np.exp(s * spec.fol_in_sd * ri.standard_normal(spec.Nf))
        W_fc = spec.W_fc * gin[:, None]
        W_fg = spec.W_fg * gin[:, None] if spec.W_fg is not None else None
        B_f = spec.B_f * np.exp(s * spec.fol_in_sd * ri.standard_normal(spec.Nf))[:, None]
    tau_r = B_r = W_fr = W_rc = None
    if spec.Nr:
        tau_r = spec.tau_r * np.exp(s * 0.15 * ri.standard_normal(spec.Nr))
        B_r = spec.B_r * np.exp(s * 0.1 * ri.standard_normal(spec.Nr))[:, None]
        W_fr = spec.W_fr * np.exp(s * spec.fol_in_sd * ri.standard_normal(spec.Nf))[:, None] if spec.Nf else None
        W_rc = spec.W_rc.copy() if spec.W_rc is not None else np.zeros((spec.Nr, spec.Nc))
    W_ff = spec.W_ff.copy() if (spec.Nf and spec.W_ff is not None) else (np.zeros((spec.Nf, spec.Nf)) if spec.Nf else None)
    if weight_noise is not None and float(weight_noise.get("sd", 0.0)) > 0:
        rw = _rng("wnoise", spec.impl_key, int(weight_noise["seed"]))
        sd = float(weight_noise["sd"])
        # multiplicative structural noise, fixed for the trajectory (1 + sd * xi, clipped at 0 so no synapse changes sign)
        mult = lambda shape: np.maximum(1.0 + sd * rw.standard_normal(shape), 0.0)  # noqa: E731
        EF = E * mult(E.shape)
        Qp = spec.latent.passive_basis() if hasattr(spec.latent, "passive_basis") else None
        if Qp is not None:
            # latents with an exactly invariant passive subspace S (type 21): the synaptic noise acts on the causal dynamics only
            # within S, M_F = I + P_S (M_F - I) P_S (its off-manifold part, seen in x only, is kept). S stays invariant and the
            # silent block keeps its nominal (stable) dynamics, so rounding in the silent directions cannot grow either
            PS = Qp @ Qp.T
            I_k = np.eye(spec.k)
            MF = spec.L @ EF
            EF = (EF - E @ MF) + E @ (I_k + PS @ (MF - I_k) @ PS)
        if Ng:
            gen_W = gen_W * mult(gen_W.shape)
        if spec.Nf:
            W_fc = W_fc * mult(W_fc.shape)
            if W_fg is not None:
                W_fg = W_fg * mult(W_fg.shape)
            if W_fr is not None:
                W_fr = W_fr * mult(W_fr.shape)
            if W_ff is not None:
                W_ff = W_ff * mult(W_ff.shape)
        if W_rc is not None:
            W_rc = W_rc * mult(W_rc.shape)
    W_fc_sp = _sparse.csr_matrix(W_fc) if W_fc is not None else None
    return Draw(spec=spec, P=Pz, f=f, E=E, EF=EF, tau_c=tau_c, gen_tau=gen_tau, gen_W=gen_W, gen_h=gen_h, gen_a0=gen_a0, W_fc_sp=W_fc_sp,
                tau_f=tau_f, W_fc=W_fc, W_fg=W_fg, B_f=B_f, tau_r=tau_r, B_r=B_r, W_fr=W_fr, W_ff=W_ff, W_rc=W_rc)


# ------------------------------------------------------------------------------------------------------------------ events
@dataclass
class Plan:
    """Per-step intervention configuration on the output grid (steps = T - 1)."""
    T: int
    u: np.ndarray                               # (T, n_u) input in force on [t_n, t_n+1)
    I: dict = field(default_factory=dict)       # public unit -> (T,) current
    in_off: dict = field(default_factory=dict)  # unit -> (T,) bool: synaptic inputs removed (silence)
    out_off: dict = field(default_factory=dict)  # unit -> (T,) bool: outputs removed (silence)
    gain: dict = field(default_factory=dict)    # unit -> (T,) multiplicative gain
    thr: dict = field(default_factory=dict)     # unit -> (T,) additive threshold
    tauf: dict = field(default_factory=dict)    # unit -> (T,) time-constant factor
    edges: list = field(default_factory=list)   # (post, pre, factor, (T,) bool active)
    kicks: dict = field(default_factory=dict)   # step -> list of (unit, delta)
    latent: dict = field(default_factory=dict)  # step -> list of ("set", z) / ("kick", dz)
    kick_refine: Any = None                     # (T,) bool: steps inside the refinement window after a beyond-strong core kick


def _idx(t: float, dt: float) -> int:
    return int(round(t / dt))


def make_plan(q: dict, spec: Spec) -> Plan:
    """Translate a canonical protocol into per-step arrays (events snapped to the grid by validate)."""
    dt, t_end = q["dt"], q["t_end"]
    T = _idx(t_end, dt) + 1
    n_u = spec.n_u
    u = np.zeros((T, n_u))
    for t, val in q["stimulus"]:
        vv = np.asarray(val, float).reshape(-1)
        if vv.size == 1 and n_u > 1:
            vv = np.repeat(vv, n_u)
        if vv.size != n_u:
            raise P.ProtocolError(f"stimulus has {vv.size} channels, the system has {n_u}")
        u[_idx(t, dt):] = vv
    pl = Plan(T=T, u=u)
    N = spec.N

    def unit(x) -> int:
        n = int(x)
        if not 0 <= n < N:
            raise P.ProtocolError(f"unit {n} does not exist (n_units = {N})")
        return n

    def window(e) -> tuple[int, int]:
        a = _idx(e["t0"], dt)
        b = T - 1 if e.get("t1") is None else _idx(e["t1"], dt)
        return a, max(a, min(b, T - 1))

    for e in q["events"]:
        k = e["kind"]
        if k == "kick":
            n = min(_idx(e["t"], dt), T - 1)
            pl.kicks.setdefault(n, []).extend((unit(a), float(d)) for a, d in e["delta"].items())
            if any(spec.role[unit(a)] == CORE and abs(float(d)) >= spec.kick_strong * (1.0 - 1e-9) for a, d in e["delta"].items()):
                if pl.kick_refine is None:
                    pl.kick_refine = np.zeros(T, bool)
                pl.kick_refine[n:n + KICK_REFINE_STEPS] = True
        elif k in ("latent_set", "latent_kick"):
            n = min(_idx(e["t"], dt), T - 1)
            vec = np.asarray(e["z"] if k == "latent_set" else e["dz"], float)
            pl.latent.setdefault(n, []).append(("set" if k == "latent_set" else "kick", vec))
            if k == "latent_kick":                     # truth-level jumps are refined like large microscopic kicks, so a kick
                if pl.kick_refine is None:             # and its latent_kick realisation stay step-for-step comparable
                    pl.kick_refine = np.zeros(T, bool)
                pl.kick_refine[n:n + KICK_REFINE_STEPS] = True
        elif k == "current":
            a, b = window(e)
            for x, I in e["targets"].items():
                arr = pl.I.setdefault(unit(x), np.zeros(T))
                arr[a:b] += float(I)
        elif k == "current_seq":
            a = _idx(e["t0"], dt)
            m = _idx(e["seg"], dt)
            for x, lst in e["targets"].items():
                arr = pl.I.setdefault(unit(x), np.zeros(T))
                for j, I in enumerate(lst):
                    arr[min(a + j * m, T - 1):min(a + (j + 1) * m, T - 1)] += float(I)
        elif k == "silence":
            a, b = window(e)
            for x in e["targets"]:
                for dct in (pl.in_off, pl.out_off):
                    arr = dct.setdefault(unit(x), np.zeros(T, bool))
                    arr[a:b] = True
        elif k == "edge_scale":
            a, b = window(e)
            act = np.zeros(T, bool)
            act[a:b] = True
            for post, pre in e["edges"]:
                pl.edges.append((unit(post), unit(pre), float(e["factor"]), act))
        elif k == "param":
            a, b = window(e)
            for x, fl in e["targets"].items():
                n = unit(x)
                if "gain" in fl:
                    pl.gain.setdefault(n, np.ones(T))[a:b] *= float(fl["gain"])
                if "threshold" in fl:
                    pl.thr.setdefault(n, np.zeros(T))[a:b] += float(fl["threshold"])
                if "tau" in fl:
                    pl.tauf.setdefault(n, np.ones(T))[a:b] *= float(fl["tau"])
    return pl


def breakpoints_steps(pl: Plan) -> list[int]:
    """Step indices at which the per-step configuration changes (segment starts)."""
    T = pl.T
    ch = np.zeros(T, bool)
    ch[0] = True
    ch[1:] |= np.any(pl.u[1:] != pl.u[:-1], axis=1)
    for dct in (pl.I, pl.gain, pl.thr, pl.tauf):
        for arr in dct.values():
            ch[1:] |= arr[1:] != arr[:-1]
    for dct in (pl.in_off, pl.out_off):
        for arr in dct.values():
            ch[1:] |= arr[1:] != arr[:-1]
    for _, _, _, act in pl.edges:
        ch[1:] |= act[1:] != act[:-1]
    if pl.kick_refine is not None:                 # the refinement window after a beyond-strong kick has its own substep count
        kr = pl.kick_refine
        ch[1:] |= kr[1:] != kr[:-1]
    return [int(i) for i in np.nonzero(ch[:T - 1])[0]]


