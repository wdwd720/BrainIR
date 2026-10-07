"""Fast, exact and bit-for-bit restartable integration of a p4synth system (see engine.py for the model).

The joint classical RK4 of the full microstate is computed in exactly equivalent pieces:

1. a python-float RK4 loop over the small nonlinear part Y = [z (k) | v_g]: z = L (v_c - b) is the causal state (carried as an
   internal variable of the microstate), v_g the generator. Every synaptic output of a core unit is computed from its on-manifold
   potential b_i + E_i z, every input to the core is read through L and every core unit relaxes with the same leak 1 / tau_c, so
   the z-field is the exact projection of the core field under EVERY configuration (nominal or intervened: silence, param,
   scaled core-core edges); per segment it is a closed k-dimensional field built from k x k matrices. RK4 commutes with the
   projection.
2. per segment, a vectorised linear RK4 recursion (absolute states, elementwise arithmetic, common leak) for all core units, using
   the recorded stage values of z, zh and F; relays and followers likewise after the loop.

Bit-exact restarts: the loop arithmetic of z depends only on z, the input and the segment's configuration; the linear recursions
carry absolute states (v_{s+1} = R (v_s - b) + beta_s + b), so a restart from a recorded state repeats the same floating-point
operations; all post-hoc products are explicit elementwise sums (no shape-dependent BLAS kernels); process noise is a counter-based
stream keyed by (seed, absolute output step, substep, unit), the absolute step being r0["t"] / dt for restarts.
Output samples follow the pre-event rule: the sample at t_n is computed with the configuration in force just before t_n (that of
the step [t_{n-1}, t_n); the nominal configuration at n = 0), so no event is visible at its onset sample.
The whole scheme is verified against an independent brute-force RK4 of the full microstate (p4synth.reference).
"""

from __future__ import annotations

import gc
import math

import numpy as np

from . import protocol as P
from .engine import CORE, FOL, GEN, KICK_REFINE, RELAY, ENGINE_ID, Draw, Plan, Spec, breakpoints_steps, make_plan, observe
from .latents import ew_matmul

_COMBOS: dict = {}


def _spmm(W: np.ndarray, X: np.ndarray) -> np.ndarray:
    """X (..., m) @ W.T for a sparse W (n, m) through a CSR product: every output element is the sum over W's nonzeros of one row
    in fixed order, independent of the number of rows of X (bit-exact restarts)."""
    from scipy import sparse as _sparse
    m = X.shape[-1]
    out = (_sparse.csr_matrix(W) @ np.ascontiguousarray(X.reshape(-1, m)).T).T
    return np.ascontiguousarray(out).reshape(X.shape[:-1] + (W.shape[0],))


def _combos(n: int):
    """Unrolled RK4 list combinations for an n-dimensional python-float state (code-generated once per n)."""
    if n not in _COMBOS:
        idx = range(n)
        src = ("def add(Y, K, c):\n    return [" + ", ".join(f"Y[{i}] + c * K[{i}]" for i in idx) + "]\n"
               "def fin(Y, a, b, c, d, h6):\n    return [" +
               ", ".join(f"Y[{i}] + h6 * (a[{i}] + 2.0 * (b[{i}] + c[{i}]) + d[{i}])" for i in idx) + "]\n")
        ns: dict = {}
        exec(src, ns)
        _COMBOS[n] = (ns["add"], ns["fin"])
    return _COMBOS[n]


def _gen_fn(gg, gth, gis, gitau, gI, gconst, gW):
    """Code-generated right-hand side of the Wilson-Cowan generator units for one segment configuration (constants inlined):
    a_i = g_i sigma((v_i - th_i) / s_i); dv_i = (c_i + sum_j W_ij a_j - v_i + I_i) / tau_i."""
    n = len(gg)
    vs = ", ".join(f"v{i}" for i in range(n))
    lines = ["def gen(vg):", f"    {vs}{',' if n == 1 else ''} = vg"]
    for i in range(n):
        lines.append(f"    a{i} = {gg[i]!r} * (0.5 + 0.5 * tanh({0.5 * gis[i]!r} * (v{i} - {gth[i]!r})))")
    for i in range(n):
        terms = " + ".join(f"{gW[i][j]!r} * a{j}" for j in range(n) if gW[i][j] != 0.0) or "0.0"
        lines.append(f"    d{i} = ({gconst[i]!r} + {terms} - v{i} + {gI[i]!r}) * {gitau[i]!r}")
    lines.append("    return [" + ", ".join(f"d{i}" for i in range(n)) + "], [" + ", ".join(f"a{i}" for i in range(n)) + "]")
    ns = {"tanh": math.tanh}
    exec("\n".join(lines), ns)
    return ns["gen"]


# ------------------------------------------------------------------------------------------------------------------ helpers


def clip_kick(v: float, d: float, lo: float, hi: float) -> float:
    """The admissible-range clipping of a kick (shared by simulate, the reference integrator and true_latent_effect). A kick never
    moves a unit against its own sign: a unit that its dynamics carried outside [lo, hi] (possible for nuisance units driven by a
    kicked relay, say) is not pulled back by a kick pointing further out (realized offset 0)."""
    return min(max(v + d, min(lo, v)), max(hi, v))


def core_kick(z: np.ndarray, E_row: np.ndarray, L_col: np.ndarray, b_i: float, d: float, lo: float, hi: float):
    """A kick d on core unit i at causal state z: the admissible range acts on the unit's on-manifold potential
    vhat = b_i + E_i . z (a function of z only). Returns (applied offset, new z, clipped?)."""
    vh = b_i + float(E_row @ z)
    new = clip_kick(vh, d, lo, hi)
    deff = new - vh
    return deff, z + L_col * deff, new != vh + d


def kicks_applied(spec, q: dict, pl, Zs: np.ndarray, V: np.ndarray) -> list[dict]:
    """The REALIZED size of every requested kick (after the admissible-range clipping), one entry per kick event of the protocol in
    the order of the canonical (validated) protocol, which is the order the kicks are applied in: [{"t": t, "event_index": index in
    the canonical events, "units": {unit: realized offset}, "requested": {unit: requested offset}}]. Recomputed from the pre-event samples with the integrator's own operations
    (latent events first, then the kicks of the step in protocol order, each seeing the previous ones): a core kick is clipped on the
    unit's on-manifold potential b_i + E_i z, any other unit's on its state variable."""
    if not pl.kicks:
        return []
    role, loc, L, b = spec.role, spec.loc, spec.L, spec.b
    E1 = spec.E
    real: dict[int, list[float]] = {}
    for n, lst in pl.kicks.items():
        z = np.array(Zs[n], dtype=float)
        for kind, vv in pl.latent.get(n, []):
            z = vv.copy() if kind == "set" else z + vv
        vals: dict[int, float] = {}
        out_n = []
        for unit, d in lst:
            lo, hi = spec.lo[unit], spec.hi[unit]
            if role[unit] == CORE:
                c = loc[unit]
                deff, z, _ = core_kick(z, E1[c], L[:, c], b[c], d, lo, hi)
            else:
                old = vals.get(unit, float(V[n, unit]))
                new = clip_kick(old, d, lo, hi)
                vals[unit] = new
                deff = new - old
            out_n.append(float(deff))
        real[n] = out_n
    cur: dict[int, int] = {}
    res = []
    dt, T = q["dt"], pl.T
    for j, e in enumerate(q["events"]):
        if e["kind"] != "kick":
            continue
        n = min(int(round(e["t"] / dt)), T - 1)
        i = cur.get(n, 0)
        units = {}
        for a in e["delta"]:
            units[int(a)] = real[n][i]
            i += 1
        cur[n] = i
        res.append({"t": float(e["t"]), "event_index": j, "units": units,
                    "requested": {int(a): float(d) for a, d in e["delta"].items()}})
    return res


_M1, _M2, _M3 = np.uint64(0x9E3779B97F4A7C15), np.uint64(0xBF58476D1CE4E5B9), np.uint64(0x94D049BB133111EB)


def _splitmix(x: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        z = x + _M1
        z = (z ^ (z >> np.uint64(30))) * _M2
        z = (z ^ (z >> np.uint64(27))) * _M3
        return z ^ (z >> np.uint64(31))


def counter_normals(seed: int, step0: int, steps: int, nsub: int, n: int) -> np.ndarray:
    """Standard normals keyed by (seed, absolute output step, substep, unit): a counter-based stream (SplitMix64 hashes, Box-Muller),
    shape (steps * nsub, n). Any split of a trajectory or restart at absolute step s reproduces the same numbers."""
    with np.errstate(over="ignore"):
        s = np.arange(steps, dtype=np.uint64) + np.uint64(step0)
        h0 = _splitmix(np.array([np.uint64(seed & 0xFFFFFFFFFFFFFFFF)], dtype=np.uint64))
        h1 = _splitmix(h0 ^ s)                                                     # (steps,)
        j = np.arange(nsub, dtype=np.uint64)
        u = np.arange(n, dtype=np.uint64)
        lane = (j[:, None] << np.uint64(32)) | u[None, :]                          # (nsub, n)
        h2 = _splitmix(h1[:, None, None] ^ _splitmix(lane)[None, :, :])
        a = _splitmix(h2 ^ np.uint64(0xD1B54A32D192ED03))
    u1 = ((h2 >> np.uint64(11)).astype(np.float64) + 1.0) * (1.0 / 9007199254740992.0)     # (0, 1]
    u2 = (a >> np.uint64(11)).astype(np.float64) * (1.0 / 9007199254740992.0)             # [0, 1)
    return (np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * math.pi * u2)).reshape(steps * nsub, n)


def _rk4_lin_coef(x):
    """RK4 applied to e' = lam e + g (x = h lam): e+ = R e + h (c1 g1 + c2 g2 + c3 g3 + g4 / 6)."""
    R = 1.0 + x + x * x / 2.0 + x ** 3 / 6.0 + x ** 4 / 24.0
    c1 = (1.0 + x + x * x / 2.0 + x ** 3 / 4.0) / 6.0
    c2 = (2.0 + x + x * x / 2.0) / 6.0
    c3 = (2.0 + x) / 6.0
    return R, c1, c2, c3


def lin_pass(v0, b, lam, G, h, nsub, s0=0, events=None, noise=None, stages=False):
    """RK4 of tau v' = -(v - b) + ... written as e' = lam e + g with e = v - b, for the substeps s0 .. s0 + S - 1 (global substep
    indices; S = G.shape[0]). Carries ABSOLUTE states (e = v - b recomputed every substep) so restarts are bit-exact.
    lam (n,) or (S, n); G (S, 4, n) stage inputs; events {global substep: [("add", vec) | ("kick", j, d, lo, hi)]} applied before
    that substep; noise (S, n) added after each substep. Returns (values at every substep start BEFORE events (S, n), values at the
    substep starts AFTER events (S, n), final values (n,), stage states (S, 4, n) or None)."""
    S, _, n = G.shape
    if np.ndim(h):                                  # a step per substep (refined segments, see _step_refinement)
        h = np.asarray(h, float)[:, None]
        lam = np.broadcast_to(lam, (S, n))
    x = h * lam
    R, c1, c2, c3 = _rk4_lin_coef(x)
    beta = h * (c1 * G[:, 0] + c2 * G[:, 1] + c3 * G[:, 2] + G[:, 3] / 6.0)
    if noise is not None:
        beta = beta + noise
    per_step = np.ndim(R) == 2
    pre = np.empty((S, n))
    post = np.empty((S, n))
    v = np.array(v0, dtype=float)
    ev = events or {}
    for s in range(S):
        pre[s] = v
        gs = s0 + s
        if gs in ev:
            v = v.copy()
            for item in ev[gs]:
                if item[0] == "add":
                    v += item[1]
                else:
                    _, j, d, lo, hi = item
                    v[j] = clip_kick(v[j], d, lo, hi)
        post[s] = v
        e = v - b
        v = (R[s] if per_step else R) * e + beta[s] + b
    if not stages:
        return pre, post, v, None
    lamv = lam if per_step else np.broadcast_to(lam, (S, n))
    e1 = post - b
    k1 = lamv * e1 + G[:, 0]
    e2 = e1 + 0.5 * h * k1
    k2 = lamv * e2 + G[:, 1]
    e3 = e1 + 0.5 * h * k2
    k3 = lamv * e3 + G[:, 2]
    e4 = e1 + h * k3
    return pre, post, v, np.stack([e1, e2, e3, e4], axis=1)


def step_refinement(pl: Plan, steps: int, nsub: int, role=None) -> np.ndarray:
    """Substeps per output step: nsub, times 2^ceil(log2(a)) in steps where some CORE unit's rate factor a = min(1 / f, 2) > 1 is
    in force (time-constant factor f < 1: the latent drive is integrated up to twice as fast), times 2^ceil(2 log2(g)) where some
    core unit's gain factor g > 1 is in force (gain increases can drive the state into the steep confinement); at most 8. Nuisance
    units made faster only change the observed x of nuisance units, not z or y, and do not refine the step. It depends only on the
    configuration of the step, so a restart repeats the same arithmetic."""
    amax = np.ones(steps)
    gmax = np.ones(steps)
    for u_, a in pl.tauf.items():
        if role is None or role[u_] == CORE:
            amax = np.maximum(amax, rate_factor(a[:steps]))
    for u_, a in pl.gain.items():
        if role is None or role[u_] == CORE:
            gmax = np.maximum(gmax, a[:steps])
    m = np.ones(steps, dtype=np.int64)
    fast = amax > 1.0
    if np.any(fast):
        m[fast] = 2 ** np.ceil(np.log2(amax[fast]) - 1e-9).astype(np.int64)
    strong = gmax > 1.0
    if np.any(strong):
        m[strong] *= 2 ** np.ceil(3.0 * np.log2(gmax[strong]) - 1e-9).astype(np.int64)
    if np.any(m > 1):          # keep the refinement for CONFIG_TAIL steps after a refined window ends (its relaxation transient)
        md = m.copy()
        for j in range(1, CONFIG_TAIL + 1):
            md[j:] = np.maximum(md[j:], m[:-j])
        # and halve the step for CONFIG_LONG_TAIL steps more: a gain / time-constant window can push the state far out, where the
        # free relaxation afterwards is stiffer (types 20 / 21 at params_spread 2)
        last = np.nonzero(m > 1)[0]
        refined = np.zeros(steps, bool)
        ends = last[np.r_[np.diff(last) > 1, True]]              # last step of every refined window
        for e_ in ends:
            refined[e_ + 1:e_ + 1 + CONFIG_LONG_TAIL] = True
        md[refined & (md < 2)] = 2
        m = md
    if getattr(pl, "kick_refine", None) is not None:          # steps after a large core kick (kick.hi and strong classes)
        m[pl.kick_refine[:steps]] *= KICK_REFINE
    return nsub * np.maximum(m, 1)


CONFIG_TAIL = 30           # output steps of refinement kept after a gain / time-constant window (review v3.3, C2)
CONFIG_LONG_TAIL = 500     # output steps at (at least) half the step after such a window (its far-out relaxation)


def initial_state(spec: Spec, q: dict, restart_state=None):
    """(unit states (N,), internal z (k,)) of the initial microstate."""
    N, k = spec.N, spec.k
    core = spec.units_of(CORE)
    if restart_state is not None:
        s = np.array(restart_state, dtype=float).reshape(-1)
        if s.size not in (N, N + k):
            raise P.ProtocolError(f"restart_state has {s.size} entries; the microstate has {N + k} ({N} units + {k} internal)")
        if not np.all(np.isfinite(s)):
            raise P.ProtocolError("restart_state must be finite")
        x0 = s[:N].copy()
        zu = spec.L @ (x0[core] - spec.b)
        if s.size == N + k:
            z0 = s[N:].copy()
            # the internal copy is a numerical mirror of L (v_core - b); if the units were changed (or rounded), trust the units
            if np.abs(z0 - zu).max() > 1e-9 * max(1.0, float(np.abs(zu).max())):
                z0 = zu
        else:
            z0 = zu
        return x0, z0
    x0 = spec.rest.copy()
    r0 = q["r0"]
    if r0["kind"] == "state":
        for u, val in r0["values"].items():
            n = int(u)
            if not 0 <= n < N:
                raise P.ProtocolError(f"r0: unit {n} does not exist")
            x0[n] = min(max(float(val), spec.lo[n]), spec.hi[n])
    elif r0["kind"] == "restart":
        raise P.ProtocolError("r0 kind 'restart' must be resolved to restart_state by the caller")
    return x0, spec.L @ (x0[core] - spec.b)


RATE_CAP = 2.0          # a core unit made faster integrates its drive at most twice as fast (it cannot outrun the population it reads)


def rate_factor(c):
    """The rate factor a of a core unit under a time-constant factor c: a = min(1 / c, RATE_CAP)."""
    return np.minimum(1.0 / np.asarray(c, float), RATE_CAP)


def core_config(spec: Spec, pl: Plan):
    """Per-step configuration of the core units: output gain gm = gain * (not out_off), threshold shift dth, input mask inm,
    rate factor a = 1 / tau factor (T, Nc) each, and the active core-core edges [(post loc, pre loc, factor, (T,) active)]."""
    T, Nc = pl.T, spec.Nc
    role, loc = spec.role, spec.loc
    gm = np.ones((T, Nc))
    dth = np.zeros((T, Nc))
    inm = np.ones((T, Nc))
    ar = np.ones((T, Nc))
    for u_, a in pl.gain.items():
        if role[u_] == CORE:
            gm[:, loc[u_]] *= a
    for u_, a in pl.out_off.items():
        if role[u_] == CORE:
            gm[a, loc[u_]] = 0.0
    for u_, a in pl.thr.items():
        if role[u_] == CORE:
            dth[:, loc[u_]] = a
    for u_, a in pl.in_off.items():
        if role[u_] == CORE:
            inm[a, loc[u_]] = 0.0
    for u_, a in pl.tauf.items():
        if role[u_] == CORE:
            ar[:, loc[u_]] = rate_factor(a)
    edges = [(int(loc[post]), int(loc[pre]), float(fac), act) for post, pre, fac, act in pl.edges
             if role[post] == CORE and role[pre] == CORE and fac != 1.0]
    return gm, dth, inm, ar, edges


def seg_matrices(spec: Spec, draw: Draw, gm, dth, inm, ar, edges_n, Irow):
    """k x k matrices of the closed z-field of one configuration (rows gm, dth, inm, ar of one step; edges_n = [(p, q, factor)]):
    zh = Ao z + co;  dz/dt = (K z + M1 zh + tau_c M2 F(zh, u) + cc) / tau_c."""
    L, E, EF = spec.L, draw.E, draw.EF
    k = spec.k
    Ik = np.eye(k)
    So = np.nonzero((gm != 1.0) | (dth != 0.0))[0]
    Ao = Ik + (L[:, So] * (gm[So] - 1.0)) @ E[So]
    co = -(L[:, So] @ (gm[So] * dth[So]))
    Si = np.nonzero(inm != 1.0)[0]
    M1 = Ik + (L[:, Si] * (inm[Si] - 1.0)) @ E[Si]                 # recurrent drive E zh (not scaled by the rate factor)
    al = ar * inm
    Sf = np.nonzero(al != 1.0)[0]
    M2 = L @ EF + (L[:, Sf] * (al[Sf] - 1.0)) @ EF[Sf]             # latent drive tau_c F, scaled by the rate factor a
    K = -Ik
    cc = L @ (ar * Irow)                                           # currents, scaled by the rate factor a
    for p, qq, fac in edges_n:
        w = float(E[p] @ L[:, qq]) * (fac - 1.0) * inm[p] * gm[qq]
        K = K + w * np.outer(L[:, p], E[qq])
        cc = cc - w * dth[qq] * L[:, p]
    return Ao, co, K, M1, M2, cc


def simulate(spec: Spec, draw: Draw, q: dict, *, full: bool = False, restart_state=None, nsub: int | None = None,
             process_noise: dict | None = None) -> dict:
    """Simulate one canonical protocol q (validated, truth events allowed) with the compiled draw. Never raises on numerical
    failure: info["success"] is False when anything is non-finite."""
    gc_on = gc.isenabled()
    gc.disable()          # the loop allocates many short-lived lists (freed by reference counting); cyclic GC passes over a large
    try:                  # host heap would otherwise dominate the CPU time
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            out = _simulate(spec, draw, q, full=full, restart_state=restart_state, nsub=nsub, process_noise=process_noise)
    except (OverflowError, ZeroDivisionError, FloatingPointError, ValueError) as exc:     # pragma: no cover - defensive
        if isinstance(exc, P.ProtocolError):
            raise
        T = int(round(q["t_end"] / q["dt"])) + 1
        nan = lambda *s: np.full(s, np.nan)  # noqa: E731
        out = {"t": np.round(np.arange(T) * q["dt"], 9), "x": nan(T, len(spec.observed)), "u": nan(T, spec.n_u),
               "y": nan(T, spec.latent.ro.n_y), "info": {"engine": ENGINE_ID, "success": False, "error": repr(exc)}}
        if full:
            out.update(state=nan(T, spec.N + spec.k), z=nan(T, spec.k))
        return out
    finally:
        if gc_on:
            gc.enable()
    ok = bool(np.all(np.isfinite(out["x"])) and np.all(np.isfinite(out["y"])))
    if full:
        ok = ok and bool(np.all(np.isfinite(out["state"])))
    out["info"]["success"] = ok
    return out


def _simulate(spec: Spec, draw: Draw, q: dict, *, full: bool, restart_state, nsub, process_noise) -> dict:
    dt = float(q["dt"])
    pl: Plan = make_plan(q, spec)
    T = pl.T
    steps = T - 1
    if nsub is None:
        nsub = max(1, int(math.ceil(dt / spec.h_max - 1e-9)))
    h = dt / nsub
    nsub_n = step_refinement(pl, steps, nsub, spec.role)   # substeps per output step (refined where a core unit is made faster)
    off = np.concatenate([[0], np.cumsum(nsub_n)]).astype(np.int64)
    ns = int(off[-1])
    hs = np.repeat(dt / nsub_n, nsub_n)                    # the step of every substep
    k, N = spec.k, spec.N
    role, loc = spec.role, spec.loc
    Nc, Ng, Nf, Nr = spec.Nc, spec.Ng, spec.Nf, spec.Nr
    core_ids, gen_ids, fol_ids, relay_ids = spec.units_of(CORE), spec.units_of(GEN), spec.units_of(FOL), spec.units_of(RELAY)
    L, b = spec.L, spec.b
    E1, EF = draw.E, draw.EF                   # identity-feedback embedding (calibrated) / interneuron projection (weight noise)
    tauc = draw.tau_c
    itc = 1.0 / tauc
    MF = L @ EF
    wn = not np.allclose(MF, np.eye(k), atol=1e-13)
    MF_l = MF.tolist()
    f = draw.f
    vec = bool(getattr(spec.latent, "vector", False))
    x0, z0 = initial_state(spec, q, restart_state)
    step0 = int(round(float(q["r0"]["t"]) / dt)) if q["r0"]["kind"] == "restart" else 0

    def arr(dct, u, default):
        a = dct.get(int(u))
        return np.full(T, default) if a is None else a

    # ---- per-step core currents and configuration
    I_core = np.zeros((T, Nc))
    for u_, a in pl.I.items():
        if role[u_] == CORE:
            I_core[:, loc[u_]] = a
    gmC, dthC, inmC, arC, cedges = core_config(spec, pl)
    nonnom = np.any((gmC != 1.0) | (dthC != 0.0) | (inmC != 1.0) | (arC != 1.0), axis=1)
    for _, _, _, act in cedges:
        nonnom |= act

    # ---- process noise (counter-based, public unit order)
    noise = None
    if process_noise is not None and float(process_noise.get("sd", 0.0)) > 0:
        noise = np.empty((ns, N))
        sdp = float(process_noise["sd"])
        n_ = 0
        while n_ < steps:                                  # runs of equal substep counts; keyed by (seed, step, substep, unit)
            n2 = n_ + 1
            while n2 < steps and nsub_n[n2] == nsub_n[n_]:
                n2 += 1
            m_ = int(nsub_n[n_])
            xi = counter_normals(int(process_noise["seed"]), step0 + n_, n2 - n_, m_, N)
            noise[off[n_]:off[n2]] = xi * (sdp * math.sqrt(dt / m_)) * spec.noise_scale[None, :]
            n_ = n2
        nz_core = noise[:, core_ids]
        nz_z = ew_matmul(nz_core, L.T)                     # z-projection of the core noise
        nz_gen = noise[:, gen_ids]

    # ---- generator constants
    if Ng:
        gW0 = draw.gen_W
        cb = gW0 @ draw.gen_a0
        g_th = np.asarray(spec.gen["th"], float)
        g_s = np.asarray(spec.gen["s"], float)

    # ---- segments: configuration changes, kicks and latent events all start a segment
    bset = set(breakpoints_steps(pl)) | {n for n in pl.kicks if n < steps} | {n for n in pl.latent if n < steps} | {0}
    bset |= {int(n) for n in np.nonzero(np.diff(nsub_n) != 0)[0] + 1}      # every change of the substep count starts a segment
    segs = sorted(n for n in bset if n < steps) + [steps]

    # ---- storage
    Zs = np.empty((T, k))
    VG = np.empty((T, Ng))
    Vc = np.empty((T, Nc))
    ZH_st = np.empty((ns, 4, k))
    Z_st = np.empty((ns, 4, k))
    F_st = np.empty((ns, 4, k))
    AG_st = np.empty((ns, 4, Ng))
    need_oc = Nf > 0
    Oc_st = np.empty((ns, 4, Nc)) if need_oc else None
    fol_events, relay_events = {}, {}
    clipped = []
    En_nom = spec.E
    rk = range(k)
    z = np.array(z0, dtype=float)
    vc = np.array(x0[core_ids], dtype=float)
    vg = np.array(x0[gen_ids], dtype=float)
    lamc = np.full(Nc, -itc)

    for si in range(len(segs) - 1):
        n0, n1 = segs[si], segs[si + 1]
        # ---- the sample at n0 (before its events)
        Zs[n0] = z
        VG[n0] = vg
        Vc[n0] = vc
        # ---- instantaneous events at t_n0
        if n0 in pl.latent:
            for kind, vv in pl.latent[n0]:
                if vv.size != k:
                    raise P.ProtocolError(f"latent event needs a vector of length k = {k}")
                dz = (vv - z) if kind == "set" else vv
                z = z + dz
                vc = vc + En_nom @ dz
        if n0 in pl.kicks:
            for unit, d in pl.kicks[n0]:
                r, c = role[unit], loc[unit]
                lo, hi = spec.lo[unit], spec.hi[unit]
                if r == CORE:
                    deff, z, clp = core_kick(z, E1[c], L[:, c], b[c], d, lo, hi)
                    if clp:
                        clipped.append((int(unit), n0))
                    vc = vc.copy()
                    vc[c] = vc[c] + deff
                elif r == GEN:
                    old = float(vg[c])
                    new = clip_kick(old, d, lo, hi)
                    if new != old + d:
                        clipped.append((int(unit), n0))
                    vg = vg.copy()
                    vg[c] = new
                elif r == FOL:
                    fol_events.setdefault(int(off[n0]), []).append(("kick", c, d, lo, hi))
                else:
                    relay_events.setdefault(int(off[n0]), []).append(("kick", c, d, lo, hi))
        u = [float(a) for a in pl.u[n0]]
        special = bool(nonnom[n0])
        Irow = I_core[n0]
        if special:
            gm_r, dth_r, inm_r, ar_r = gmC[n0], dthC[n0], inmC[n0], arC[n0]
            edg = [(p, qq, fac) for p, qq, fac, act in cedges if act[n0]]
            Ao, co, Kz, M1, M2, cc = seg_matrices(spec, draw, gm_r, dth_r, inm_r, ar_r, edg, Irow)
            M2t = tauc * M2
            Ao_l, co_l, K_l, M1_l, M2t_l, cc_l = (a.tolist() for a in (Ao, co, Kz, M1, M2t, cc))
        else:
            LIN = ew_matmul(Irow[None, :], L.T)[0]
            LIN_l = LIN.tolist()
            has_li = bool(np.any(LIN != 0))
        # ---- generator configuration
        gen = None
        if Ng:
            gu = gen_ids
            gg = np.array([arr(pl.gain, x, 1.0)[n0] for x in gu]) * ~np.array([arr(pl.out_off, x, False)[n0] for x in gu], bool)
            ginm = (~np.array([arr(pl.in_off, x, False)[n0] for x in gu], bool)).astype(float)
            gth = g_th + np.array([arr(pl.thr, x, 0.0)[n0] for x in gu])
            gitau = 1.0 / (draw.gen_tau * np.array([arr(pl.tauf, x, 1.0)[n0] for x in gu]))
            gI = np.array([arr(pl.I, x, 0.0)[n0] for x in gu])
            gWs = gW0.copy()
            for post, pre, fac, act in pl.edges:
                if act[n0] and role[post] == GEN and role[pre] == GEN:
                    gWs[loc[post], loc[pre]] *= fac
            ghu = draw.gen_h @ np.asarray(u)
            g_const = ginm * (ghu - cb)
            gWm = gWs * ginm[:, None]
            gis = 1.0 / g_s
            if not vec:
                gen = _gen_fn(gg.tolist(), gth.tolist(), gis.tolist(), gitau.tolist(), gI.tolist(), g_const.tolist(), gWm.tolist())
        s0i = k

        # ---- right-hand sides (records per stage: zh, F, [z in special segments], generator rates)
        if vec:
            uarr = u
            if not special:
                LIt_v = LIN * itc

            def rhs(Yv):
                zz = Yv[:k]
                if special:
                    zh = Ao @ zz + co
                    F = np.asarray(f(zh, uarr), dtype=float)
                    dz = (Kz @ zz + M1 @ zh + M2t @ F + cc) * itc
                    rec = (zh, F, zz)
                else:
                    zh = zz
                    F = np.asarray(f(zz, uarr), dtype=float)
                    dz = (MF @ F if wn else F) + LIt_v
                    rec = (zh, F)
                if Ng:
                    vgg = Yv[s0i:]
                    a = gg * (0.5 + 0.5 * np.tanh(0.5 * (vgg - gth) * gis))
                    dg = (g_const + gWm @ a - vgg + gI) * gitau
                    return np.concatenate((dz, dg)), np.concatenate(rec + (a,))
                return dz, np.concatenate(rec)
        else:
            if special:
                def rhs_core(Yv):
                    zz = Yv[:k]
                    zh = [co_l[i] + sum(Ao_l[i][j] * zz[j] for j in rk) for i in rk]
                    F = f(zh, u)
                    dz = [(sum(K_l[i][j] * zz[j] + M1_l[i][j] * zh[j] + M2t_l[i][j] * F[j] for j in rk) + cc_l[i]) * itc
                          for i in rk]
                    return zh + F + list(zz), dz
            elif wn:
                LIt = [a * itc for a in LIN_l]

                def rhs_core(Yv):
                    zz = Yv[:k]
                    F = f(zz, u)
                    return list(zz) + F, [sum(MF_l[i][j] * F[j] for j in rk) + LIt[i] for i in rk]
            else:
                LIt = [a * itc for a in LIN_l]

                def rhs_core(Yv):
                    zz = Yv[:k]
                    F = f(zz, u)
                    if has_li:
                        return list(zz) + F, [F[i] + LIt[i] for i in rk]
                    return list(zz) + F, F
            if Ng:
                def rhs(Yv):
                    rec, dcore = rhs_core(Yv)
                    dg, a = gen(Yv[s0i:])
                    return dcore + dg, rec + a
            else:
                def rhs(Yv):
                    rec, dcore = rhs_core(Yv)
                    return dcore, rec

        # ---- the RK4 loop over this segment (substeps of this segment: nsg = nsub_n[n0], step h = dt / nsg)
        nsg = int(nsub_n[n0])
        h = dt / nsg
        h2, h6 = 0.5 * h, h / 6.0
        Y0 = np.concatenate([z, vg])
        dimY = Y0.size
        dimR = (3 if special else 2) * k + Ng
        a0, a1 = int(off[n0]), int(off[n1])
        nss = a1 - a0
        Rseg = np.empty((nss * 4, dimR))
        if vec:
            Y = Y0
        else:
            Y = Y0.tolist()
            add, fin = _combos(dimY)
            rec = []
        for n in range(n0, n1):
            if n > n0:
                Zs[n] = Y[:k]
                VG[n] = Y[s0i:]
            for j in range(nsg):
                gs = int(off[n]) + j
                if vec:
                    d1, r1 = rhs(Y)
                    d2, r2 = rhs(Y + h2 * d1)
                    d3, r3 = rhs(Y + h2 * d2)
                    d4, r4 = rhs(Y + h * d3)
                    Y = Y + h6 * (d1 + 2.0 * (d2 + d3) + d4)
                    s4 = 4 * (gs - a0)
                    Rseg[s4] = r1
                    Rseg[s4 + 1] = r2
                    Rseg[s4 + 2] = r3
                    Rseg[s4 + 3] = r4
                    if noise is not None:
                        Y = Y + np.concatenate([nz_z[gs], nz_gen[gs]])
                else:
                    d1, r1 = rhs(Y)
                    d2, r2 = rhs(add(Y, d1, h2))
                    d3, r3 = rhs(add(Y, d2, h2))
                    d4, r4 = rhs(add(Y, d3, h))
                    Y = fin(Y, d1, d2, d3, d4, h6)
                    rec.extend((r1, r2, r3, r4))
                    if noise is not None:
                        Y = add(Y, np.concatenate([nz_z[gs], nz_gen[gs]]).tolist(), 1.0)
        if not vec:
            Rseg = np.asarray(rec, dtype=float).reshape(nss * 4, dimR)
        Y = np.asarray(Y, dtype=float)
        z = Y[:k].copy()
        vg = Y[s0i:].copy()
        Rseg = Rseg.reshape(nss, 4, dimR)
        ZH_st[a0:a1] = Rseg[..., :k]
        F_st[a0:a1] = Rseg[..., k:2 * k]
        if special:
            Z_st[a0:a1] = Rseg[..., 2 * k:3 * k]
            AG_st[a0:a1] = Rseg[..., 3 * k:]
        else:
            Z_st[a0:a1] = Rseg[..., :k]
            AG_st[a0:a1] = Rseg[..., 2 * k:]
        # ---- all core units: linear recursion over the segment (common leak 1 / tau_c), stage inputs from z, zh and F
        Ez = ew_matmul(Z_st[a0:a1], E1.T)                                          # on-manifold potentials - b (nss, 4, Nc)
        Irep = np.repeat(I_core[n0:n1], nsg, axis=0)[:, None, :]
        if special:
            oc = gm_r * (Ez - dth_r)                                              # synaptic outputs
            inp = ew_matmul(ZH_st[a0:a1], E1.T) + ar_r * ew_matmul(tauc * F_st[a0:a1], EF.T)
            for p, qq, fac in edg:
                inp[..., p] += (fac - 1.0) * float(E1[p] @ L[:, qq]) * oc[..., qq]
            Gc = (inm_r * inp + ar_r * Irep) * itc
        else:
            oc = Ez
            Gc = (Ez + ew_matmul(tauc * F_st[a0:a1], EF.T) + Irep) * itc
        nzC = nz_core[a0:a1] if noise is not None else None
        prer, _, vend, _ = lin_pass(vc, b, lamc, Gc, h, nsg, s0=a0, noise=nzC)
        for n in range(n0 + 1, n1):
            Vc[n] = prer[int(off[n]) - a0]
        vc = vend
        if need_oc:
            Oc_st[a0:a1] = oc
    Zs[steps] = z
    VG[steps] = vg
    Vc[steps] = vc

    V = np.empty((T, N))
    V[:, core_ids] = Vc
    if Ng:
        V[:, gen_ids] = VG
    step_of = np.repeat(np.arange(steps), nsub_n)

    def layer_pass(rid, sel, ids, bvec, tau0, inp, events, stages):
        """Post-hoc RK4 pass of a linear leaky layer (units of role rid with local indices sel, public ids ids):
        tau dv = -(v - b) + in (v) * inp + I."""
        pos = {int(l_): i_ for i_, l_ in enumerate(sel)}
        for u_, a in pl.in_off.items():
            if role[u_] == rid and int(loc[u_]) in pos:
                inp[a[step_of], :, pos[int(loc[u_])]] = 0.0
        for u_, a in pl.I.items():
            if role[u_] == rid and int(loc[u_]) in pos:
                inp[:, :, pos[int(loc[u_])]] += a[step_of][:, None]
        tf = tau0
        if any(role[u_] == rid and int(loc[u_]) in pos for u_ in pl.tauf):
            tf = np.broadcast_to(tau0, (ns, ids.size)).copy()
            for u_, a in pl.tauf.items():
                if role[u_] == rid and int(loc[u_]) in pos:
                    i_ = pos[int(loc[u_])]
                    tf[:, i_] = tau0[i_] * a[step_of]
        G = inp / (tf[:, None, :] if tf.ndim == 2 else tf[None, None, :])
        nz = noise[:, ids] if noise is not None else None
        ev = {}
        for s_, lst in events.items():
            sub = [("kick", pos[c], d, lo, hi) for _, c, d, lo, hi in lst if c in pos]
            if sub:
                ev[s_] = sub
        pre, post, vend, st = lin_pass(x0[ids], bvec, -1.0 / tf, G, hs, nsub, events=ev, noise=nz, stages=stages)
        V[:steps, ids] = pre[off[:steps]]
        V[steps, ids] = vend
        for s_, lst in ev.items():
            n = int(step_of[s_])
            for _, c, d, lo, hi in lst:
                if clip_kick(V[n, ids[c]], d, lo, hi) != V[n, ids[c]] + d:
                    clipped.append((int(ids[c]), n))
        return st

    def graded_out(rid, sel, e_st):
        """Graded synaptic output g (v - b - dtheta) (0 while silenced) of the units of role rid with local indices sel."""
        pos = {int(l_): i_ for i_, l_ in enumerate(sel)}
        g_ = np.ones((ns, len(sel)))
        d_ = np.zeros((ns, len(sel)))
        for u_, a in pl.gain.items():
            if role[u_] == rid and int(loc[u_]) in pos:
                g_[:, pos[int(loc[u_])]] = a[step_of]
        for u_, a in pl.out_off.items():
            if role[u_] == rid and int(loc[u_]) in pos:
                g_[a[step_of], pos[int(loc[u_])]] = 0.0
        for u_, a in pl.thr.items():
            if role[u_] == rid and int(loc[u_]) in pos:
                d_[:, pos[int(loc[u_])]] = a[step_of]
        return g_[:, None, :] * (e_st - d_[:, None, :])

    def edge_extra(inp, post_role, sel_post, pre_role, W, src_st, sel_pre=None):
        """Scaled synapses (edge_scale) from units of pre_role onto units of post_role: inp += (f - 1) w src."""
        pp = {int(l_): i_ for i_, l_ in enumerate(sel_post)}
        qp = None if sel_pre is None else {int(l_): i_ for i_, l_ in enumerate(sel_pre)}
        for post, pre, fac, act in pl.edges:
            if role[post] != post_role or role[pre] != pre_role or fac == 1.0 or int(loc[post]) not in pp:
                continue
            if qp is not None and int(loc[pre]) not in qp:
                continue
            a_s = act[step_of]
            if not a_s.any():
                continue
            j_ = pp[int(loc[post])]
            q_ = int(loc[pre]) if qp is None else qp[int(loc[pre])]
            w = W[int(loc[post]), int(loc[pre])]
            if w != 0.0:
                inp[a_s, :, j_] += (fac - 1.0) * w * src_st[a_s][..., q_]

    # ---- relays: tau_r dv = -(v - b_r) + B_r u + W_rc o_core + I ; graded output g (v - b_r - d) to the followers
    OR_st = None
    if Nr:
        rsel = np.arange(Nr)
        inp_r = np.repeat(ew_matmul(pl.u, draw.B_r.T)[step_of][:, None, :], 4, axis=1)
        if draw.W_rc is not None and np.any(draw.W_rc != 0):
            inp_r = inp_r + _spmm(draw.W_rc, Oc_st)
            edge_extra(inp_r, RELAY, rsel, CORE, draw.W_rc, Oc_st)
        eR_st = layer_pass(RELAY, rsel, relay_ids, spec.b_r, draw.tau_r, inp_r, relay_events, stages=Nf > 0)
        if Nf:
            OR_st = graded_out(RELAY, rsel, eR_st)

    # ---- followers: a recurrent linear network (coupled through graded outputs g (v - b_f - d)), integrated jointly by the exact
    # RK4 recursion of a linear system, e+ = R(hA) e + h [c1(hA) G1 + c2(hA) G2 + c3(hA) G3 + G4 / 6], with the recorded stage
    # values of their external inputs (core outputs, generator rates, relays); one set of matrices per configuration
    if Nf:
        inp = np.ascontiguousarray((draw.W_fc_sp @ Oc_st.reshape(-1, Nc).T).T).reshape(ns, 4, Nf)     # (ns, 4, Nf)
        if Ng:
            inp += ew_matmul(AG_st, draw.W_fg.T) - (draw.W_fg @ draw.gen_a0)[None, None, :]
        if OR_st is not None:
            inp += ew_matmul(OR_st, draw.W_fr.T)
        inp += ew_matmul(pl.u, draw.B_f.T)[step_of][:, None, :]
        fsel = np.arange(Nf)
        edge_extra(inp, FOL, fsel, CORE, draw.W_fc, Oc_st)
        if Ng:
            edge_extra(inp, FOL, fsel, GEN, draw.W_fg, AG_st)
        if OR_st is not None:
            edge_extra(inp, FOL, fsel, RELAY, draw.W_fr, OR_st)
        inm_f = np.ones((ns, Nf))
        for u_, a in pl.in_off.items():
            if role[u_] == FOL:
                inm_f[a[step_of], loc[u_]] = 0.0
        tf = np.broadcast_to(draw.tau_f, (ns, Nf)).copy()
        for u_, a in pl.tauf.items():
            if role[u_] == FOL:
                tf[:, loc[u_]] = draw.tau_f[loc[u_]] * a[step_of]
        Iext = np.zeros((ns, Nf))
        for u_, a in pl.I.items():
            if role[u_] == FOL:
                Iext[:, loc[u_]] = a[step_of]
        G = (inm_f[:, None, :] * inp + Iext[:, None, :]) / tf[:, None, :]
        gq = np.ones((ns, Nf))
        dq = np.zeros((ns, Nf))
        for u_, a in pl.gain.items():
            if role[u_] == FOL:
                gq[:, loc[u_]] = a[step_of]
        for u_, a in pl.out_off.items():
            if role[u_] == FOL:
                gq[a[step_of], loc[u_]] = 0.0
        for u_, a in pl.thr.items():
            if role[u_] == FOL:
                dq[:, loc[u_]] = a[step_of]
        coup = inm_f / tf
        ffe = [(int(loc[post]), int(loc[pre]), fac, act[step_of]) for post, pre, fac, act in pl.edges
               if role[post] == FOL and role[pre] == FOL and fac != 1.0 and draw.W_ff[loc[post], loc[pre]] != 0.0]
        chg = np.zeros(ns, bool)
        chg[0] = True
        for arr_ in (tf, coup, gq, dq):
            chg[1:] |= np.any(arr_[1:] != arr_[:-1], axis=1)
        for _, _, _, a_s in ffe:
            chg[1:] |= a_s[1:] != a_s[:-1]
        chg[1:] |= hs[1:] != hs[:-1]
        mats: dict = {}
        IN = np.eye(Nf)

        def fol_mats(s):
            Wk = draw.W_ff.copy()
            for p_, q_, fac, a_s in ffe:
                if a_s[s]:
                    Wk[p_, q_] *= fac
            hh = float(hs[s])
            key = (tf[s].tobytes(), coup[s].tobytes(), gq[s].tobytes(), dq[s].tobytes(), Wk.tobytes(), hh)
            if key not in mats:
                A = np.diag(-1.0 / tf[s]) + (coup[s][:, None] * Wk) * gq[s][None, :]
                c0 = -coup[s] * (Wk @ (gq[s] * dq[s]))
                X = hh * A
                X2 = X @ X
                X3 = X2 @ X
                R = IN + X + X2 / 2.0 + X3 / 6.0 + (X3 @ X) / 24.0
                C1 = (IN + X + X2 / 2.0 + X3 / 4.0) / 6.0
                C2 = (2.0 * IN + X + X2 / 2.0) / 6.0
                C3 = (2.0 * IN + X) / 6.0
                cb = hh * ((C1 + C2 + C3 + IN / 6.0) @ c0)
                mats[key] = (R, hh * C1, hh * C2, hh * C3, cb)
            return mats[key]

        nzF = noise[:, fol_ids] if noise is not None else None
        bF = spec.b_f
        v = x0[fol_ids].astype(float).copy()
        preF = np.empty((ns, Nf))
        G4 = G[:, 3] * (hs / 6.0)[:, None]
        for s in range(ns):
            if chg[s]:
                R, hC1, hC2, hC3, cb = fol_mats(s)
            preF[s] = v
            if s in fol_events:
                v = v.copy()
                for _, c, d, lo, hi in fol_events[s]:
                    v[c] = clip_kick(v[c], d, lo, hi)
            v = R @ (v - bF) + (hC1 @ G[s, 0] + hC2 @ G[s, 1] + hC3 @ G[s, 2] + G4[s] + cb) + bF
            if nzF is not None:
                v = v + nzF[s]
        V[:steps, fol_ids] = preF[off[:steps]]
        V[steps, fol_ids] = v
        for s_, lst in fol_events.items():
            n = int(step_of[s_])
            for _, c, d, lo, hi in lst:
                if clip_kick(V[n, fol_ids[c]], d, lo, hi) != V[n, fol_ids[c]] + d:
                    clipped.append((int(fol_ids[c]), n))

    # ---- algebraic outputs at the samples: pre-event rule (configuration of the step that ENDS at t_n; nominal at n = 0)
    cfg_idx = np.arange(T) - 1
    pre0 = cfg_idx < 0
    cfg_idx[pre0] = 0

    def cfgv(a, default):
        v_ = a[cfg_idx].astype(float) if a.dtype == bool else a[cfg_idx].copy()
        v_[pre0] = default
        return v_

    ZH = Zs.copy()
    cfg_units = sorted({loc[u_] for dct in (pl.gain, pl.thr, pl.out_off) for u_ in dct if role[u_] == CORE})
    for c in cfg_units:
        gmv = cfgv(gmC[:, c], 1.0)
        dthv = cfgv(dthC[:, c], 0.0)
        if np.all(gmv == 1.0) and np.all(dthv == 0.0):
            continue
        ez = ew_matmul(Zs, E1[c:c + 1].T)[:, 0]
        diff = gmv * (ez - dthv) - ez
        ZH = ZH + diff[:, None] * L[:, c][None, :]
    U = pl.u
    Y_out = spec.latent.readout(ZH, U, draw.P)

    # observations (param gain / threshold act on the unit's output; pre-event rule)
    Xall = np.empty((T, N))
    gainA = np.ones((T, N))
    thrA = np.zeros((T, N))
    for u_, a in pl.gain.items():
        gainA[:, u_] = cfgv(a, 1.0)
    for u_, a in pl.thr.items():
        thrA[:, u_] = cfgv(a, 0.0)
    c = core_ids
    vin = b[None, :] + gainA[:, c] * (V[:, c] - b[None, :] - thrA[:, c])
    Xall[:, c] = observe(spec.obs_kind[c], vin, spec.obs_th[c], spec.obs_s[c], spec.obs_w[c], spec.obs_p[c])
    for ids in (gen_ids, fol_ids, relay_ids):
        if ids.size:
            Xall[:, ids] = gainA[:, ids] * observe(spec.obs_kind[ids], V[:, ids] - thrA[:, ids], spec.obs_th[ids], spec.obs_s[ids],
                                                   spec.obs_w[ids], spec.obs_p[ids])
    t = np.round(np.arange(T) * dt, 9)
    out = {"t": t, "x": Xall[:, spec.observed], "u": U.copy(), "y": Y_out, "info": {"engine": ENGINE_ID}}
    if full:
        out["info"].update({"n_sub": nsub, "h": dt / nsub, "n_sub_max": int(nsub_n.max()) if steps else nsub, "clipped_kicks": clipped,
                            "noise_step0": step0, "kicks_applied": kicks_applied(spec, q, pl, Zs, V)})
        out["state"] = np.hstack([V, Zs])
        out["z"] = Zs
        zo = spec.latent.zobs(Zs)
        if zo is not None:
            out["z_obs"] = zo
        out["zh"] = ZH
        out["x_all"] = Xall
    return out
