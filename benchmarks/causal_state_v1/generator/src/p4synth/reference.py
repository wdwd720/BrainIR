"""Brute-force reference integrator: classical RK4 of the FULL microstate (every unit, public order) with a direct transcription of
the unit equations of engine.py (z is recomputed from the units, L (v_c - b), at every stage; no internal variable is used).
Slow; used only to verify the fast structured integrator (p4synth.integrate) and for convergence tests."""

from __future__ import annotations

import math

import numpy as np

from .engine import CORE, FOL, GEN, RELAY, Draw, Spec, breakpoints_steps, make_plan
from .integrate import clip_kick, counter_normals, initial_state, rate_factor, step_refinement


def simulate_reference(spec: Spec, draw: Draw, q: dict, *, nsub: int | None = None, restart_state=None,
                       process_noise: dict | None = None) -> np.ndarray:
    """Returns the full microstate at the output samples, (T, N)."""
    dt = float(q["dt"])
    pl = make_plan(q, spec)
    T = pl.T
    steps = T - 1
    if nsub is None:
        nsub = max(1, int(math.ceil(dt / spec.h_max - 1e-9)))
    h = dt / nsub
    N = spec.N
    role, loc = spec.role, spec.loc
    core_ids, gen_ids, fol_ids = spec.units_of(CORE), spec.units_of(GEN), spec.units_of(FOL)
    relay_ids = spec.units_of(RELAY)
    L, b, E1, tauc = spec.L, spec.b, draw.E, draw.tau_c
    Wcore = E1 @ L
    x, _ = initial_state(spec, q, restart_state)
    nsub_n = step_refinement(pl, steps, nsub, spec.role)  # the same configuration-based substep rule as the fast integrator
    step0 = int(round(float(q["r0"]["t"]) / dt)) if q["r0"]["kind"] == "restart" else 0
    use_noise = process_noise is not None and float(process_noise.get("sd", 0.0)) > 0
    out = np.empty((T, N))

    def cfg(n):
        g = np.ones(N)
        d = np.zeros(N)
        tf = np.ones(N)
        inm = np.ones(N)
        outm = np.ones(N)
        I = np.zeros(N)
        for u, a in pl.gain.items():
            g[u] = a[n]
        for u, a in pl.thr.items():
            d[u] = a[n]
        for u, a in pl.tauf.items():
            tf[u] = a[n]
        for u, a in pl.in_off.items():
            inm[u] = 0.0 if a[n] else 1.0
        for u, a in pl.out_off.items():
            outm[u] = 0.0 if a[n] else 1.0
        for u, a in pl.I.items():
            I[u] = a[n]
        ef = [(post, pre, fac) for post, pre, fac, act in pl.edges if act[n]]
        return g, d, tf, inm, outm, I, ef, pl.u[n]

    def rhs(v, c):
        g, d, tf, inm, outm, I, ef, u = c
        dv = np.zeros(N)
        # core: synaptic outputs from the on-manifold potentials b + E z (z = L (v_c - b)); the unit's own potential leaks with
        # tau_c; the time-constant factor scales the unit's integration of its on-manifold potential and of its input
        vc = v[core_ids]
        z = L @ (vc - b)
        Ez = E1 @ z
        oc = g[core_ids] * (Ez - d[core_ids]) * outm[core_ids]
        zh = L @ oc
        F = np.asarray(draw.f(list(zh), [float(a) for a in u]))

        a = rate_factor(tf[core_ids])     # rate factor: scales the unit's integration of the latent drive and of currents
        inp = inm[core_ids] * (E1 @ zh + a * (draw.EF @ (tauc * F)))
        for post, pre, fac in ef:
            if role[post] == CORE and role[pre] == CORE:
                p, qq = loc[post], loc[pre]
                inp[p] += inm[post] * (fac - 1.0) * Wcore[p, qq] * oc[qq]
        inp += a * I[core_ids]
        dv[core_ids] = (-(vc - b) + inp) / tauc
        # generator
        ag = np.zeros(0)
        if spec.Ng:
            vg = v[gen_ids]
            th = np.asarray(spec.gen["th"]) + d[gen_ids]
            ag = g[gen_ids] * 0.5 * (1 + np.tanh(0.5 * (vg - th) / np.asarray(spec.gen["s"]))) * outm[gen_ids]
            W = draw.gen_W.copy()
            for post, pre, fac in ef:
                if role[post] == GEN and role[pre] == GEN:
                    W[loc[post], loc[pre]] *= fac
            ginp = inm[gen_ids] * (W @ ag - draw.gen_W @ draw.gen_a0 + draw.gen_h @ u) + I[gen_ids]
            dv[gen_ids] = (-vg + ginp) / (draw.gen_tau * tf[gen_ids])
        # relays (stimulus and weak core outputs)
        orl = np.zeros(0)
        if spec.Nr:
            vr = v[relay_ids]
            Wrc = draw.W_rc.copy()
            for post, pre, fac in ef:
                if role[post] == RELAY and role[pre] == CORE:
                    Wrc[loc[post], loc[pre]] *= fac
            rinp = inm[relay_ids] * (draw.B_r @ u + Wrc @ oc) + I[relay_ids]
            dv[relay_ids] = (-(vr - spec.b_r) + rinp) / (draw.tau_r * tf[relay_ids])
            orl = g[relay_ids] * (vr - spec.b_r - d[relay_ids]) * outm[relay_ids]
        # followers (layer B also reads the graded outputs of layer-A followers)
        if spec.Nf:
            Wfc = draw.W_fc.copy()
            Wfg = draw.W_fg.copy() if spec.Ng else None
            Wfr = draw.W_fr.copy() if spec.Nr else None
            Wff = draw.W_ff.copy()
            for post, pre, fac in ef:
                if role[post] == FOL:
                    if role[pre] == CORE:
                        Wfc[loc[post], loc[pre]] *= fac
                    elif role[pre] == GEN:
                        Wfg[loc[post], loc[pre]] *= fac
                    elif role[pre] == RELAY:
                        Wfr[loc[post], loc[pre]] *= fac
                    elif role[pre] == FOL:
                        Wff[loc[post], loc[pre]] *= fac
            vf = v[fol_ids]
            ofl = g[fol_ids] * (vf - spec.b_f - d[fol_ids]) * outm[fol_ids]
            finp = Wfc @ oc + draw.B_f @ u + Wff @ ofl
            if spec.Ng:
                finp += Wfg @ ag - draw.W_fg @ draw.gen_a0
            if spec.Nr:
                finp += Wfr @ orl
            finp = inm[fol_ids] * finp + I[fol_ids]
            dv[fol_ids] = (-(vf - spec.b_f) + finp) / (draw.tau_f * tf[fol_ids])
        return dv

    for n in range(steps):
        out[n] = x
        if n in pl.latent:
            for kind, vec in pl.latent[n]:
                z = L @ (x[core_ids] - b)
                dz = vec - z if kind == "set" else vec
                x = x.copy()
                x[core_ids] += spec.E @ dz
        if n in pl.kicks:
            x = x.copy()
            for u, dd in pl.kicks[n]:
                if role[u] == CORE:          # the admissible range acts on the on-manifold potential b_i + E_i z
                    c = loc[u]
                    vh = b[c] + float(spec.E[c] @ (L @ (x[core_ids] - b)))
                    x[u] += clip_kick(vh, dd, spec.lo[u], spec.hi[u]) - vh
                else:
                    x[u] = clip_kick(x[u], dd, spec.lo[u], spec.hi[u])
        c = cfg(n)
        m = int(nsub_n[n])
        hn = dt / m
        if use_noise:
            nz = counter_normals(int(process_noise["seed"]), step0 + n, 1, m, N) * (float(process_noise["sd"]) * math.sqrt(hn)) \
                * spec.noise_scale[None, :]
        for j in range(m):
            k1 = rhs(x, c)
            k2 = rhs(x + 0.5 * hn * k1, c)
            k3 = rhs(x + 0.5 * hn * k2, c)
            k4 = rhs(x + hn * k3, c)
            x = x + hn / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
            if use_noise:
                x = x + nz[j]
    out[steps] = x
    return out
