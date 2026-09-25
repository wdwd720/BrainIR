"""Verification helpers (truth-level; used by tests and by the accuracy / timing report).

reference_coords(system, protocol): integrates the CLAIMED coordinate dynamics dc/dt = F(c, u) directly in c-space with
scipy's DOP853 (rtol 1e-10), independently of the neuron-level simulator, for noise-free protocols without events.
"""

from __future__ import annotations

import json
import time

import numpy as np
from scipy.integrate import solve_ivp

from .core import _stimulus_steps
from .protocol import validate


def coords_to_r0(system, c0, params_seed=0):
    """r0 (all neurons) that places the population exactly at coordinates c0 (on the manifold)."""
    im = system.impl
    x0 = im.phi.fwd(im.b + im.E @ np.asarray(c0, float))
    return {"kind": "state", "values": {str(i): float(v) for i, v in enumerate(x0)}}


def full_rest_coords(system, params_seed=0):
    th = system.model.latent.draw(params_seed)
    return system.model.rest(th)


def protocol(system, *, t_end=3.0, dt=0.01, stimulus=None, events=None, params_seed=0, c0=None, weight_noise=None):
    p = {"system": system.system_id, "params_seed": params_seed, "weight_noise": weight_noise, "r0": {"kind": "zero"},
         "t_end": t_end, "dt": dt, "stimulus": stimulus if stimulus is not None else [[0.0, 0.0]], "events": events or []}
    if c0 is not None:
        p["r0"] = coords_to_r0(system, c0, params_seed)
    return p


def reference_coords(system, p, rtol=1e-10, atol=1e-12, A=None):
    """Integrate dc/dt = F(c, u) (or A F(c) - lam (I - A) c for weight noise) segment by segment on the output grid."""
    q = validate(p, n=system.n, input_dim=system.input_dim, k=system.k)
    m, im = system.model, system.impl
    th = m.latent.draw(q["params_seed"])
    dt, n_steps = q["dt"], int(round(q["t_end"] / q["dt"]))
    u = _stimulus_steps(q["stimulus"], n_steps, dt, m.n_u, np.asarray(m.latent.input_pattern, float))
    v0 = im.b + im.E @ m.rest(th)
    if q["r0"]["kind"] == "state":
        x0 = im.phi.fwd(v0)
        for j, val in q["r0"]["values"].items():
            x0[int(j)] = val
        v0 = im.phi.inv(im.phi.clip(x0))
    D = system.synaptic_readout(q["weight_noise"])
    c = D @ (v0 - im.b)
    Aeff = D @ im.E
    lam = im.lam
    out = np.empty((n_steps + 1, m.K))
    out[0] = c
    exo = np.zeros(m.n_exo) if m.n_exo else None
    wn = q["weight_noise"] is not None and q["weight_noise"]["sd"] > 0
    for i in range(n_steps):
        ui = u[i]
        if wn:
            fun = lambda t, cc: Aeff @ m.F(cc, ui, exo, th) - lam * (cc - Aeff @ cc)
        else:
            fun = lambda t, cc: m.F(cc, ui, exo, th)
        sol = solve_ivp(fun, (0.0, dt), c, method="DOP853", rtol=rtol, atol=atol)
        c = sol.y[:, -1]
        out[i + 1] = c
    return out


def one_step_residual(system, out, p, n_check=60, rng=None):
    """Integrate the CLAIMED latent f for one output step from recorded samples and compare with the next sample.
    Valid only for noise-free, event-free stretches of systems whose latent does not read auxiliary coordinates."""
    q = validate(p, n=system.n, input_dim=system.input_dim, k=system.k)
    lat = system.model.latent
    th = lat.draw(q["params_seed"])
    dt, n_steps = q["dt"], int(round(q["t_end"] / q["dt"]))
    u = _stimulus_steps(q["stimulus"], n_steps, dt, lat.n_u, np.asarray(lat.input_pattern, float))
    rng = rng or np.random.default_rng(0)
    idx = rng.choice(n_steps, min(n_check, n_steps), replace=False)
    z = out["z"]
    exo = np.zeros(lat.n_exo) if lat.n_exo else None
    errs = []
    for i in idx:
        sol = solve_ivp(lambda t, zz: lat.f(zz, u[i], exo, th), (0, dt), z[i], method="DOP853", rtol=1e-11, atol=1e-12)
        errs.append(np.abs(sol.y[:, -1] - z[i + 1]).max())
    return float(np.max(errs))


def accuracy_report(systems, seed=0, t_end=3.0):
    """Max |z_xspace - z_reference| for a noise-free protocol with a random initial state and random stimulus."""
    rep = {}
    for s in systems:
        rng = np.random.default_rng(seed)
        th = s.model.latent.draw(0)
        z0 = s.model.latent.sample_init(rng, th)
        c0 = np.concatenate([z0] + [np.asarray(b.init(rng, z0, th, s.model), float) for b in s.model.blocks])
        amp = s.model.latent.channels[0][1]
        stim = [[0.0, 0.0], [0.5, 0.8 * amp], [0.8, 0.0], [1.6, -0.5 * amp], [2.0, 0.0]] if s.input_dim == 1 else \
            [[0.0, [0.0] * s.input_dim], [0.5, [0.8 * a for _, a in s.model.latent.channels]], [1.0, [0.0] * s.input_dim]]
        p = protocol(s, t_end=t_end, stimulus=stim, c0=c0)
        out = s.simulate(p, noise=False)
        ref = reference_coords(s, p)
        sc = max(1.0, float(np.abs(ref).max()))
        rep[s.meta["name"]] = {"max_abs_err_z": float(np.abs(out["z"] - ref[:, : s.k]).max()),
                               "max_abs_err_all_coords": float(np.abs(out["info"]["truth"]["coords"] - ref).max()),
                               "scale": sc, "h": out["info"]["truth"]["h"]}
    return rep


def timing_report(systems, n_rep=3, t_end=4.0):
    rep = {}
    for s in systems:
        p = protocol(s, t_end=t_end, stimulus=s.model.latent.nominal_stimulus(t_end),
                     events=[{"kind": "kick", "t": 1.0, "delta": {"0": 0.1}}])
        s.simulate(p)
        ts = []
        for _ in range(n_rep):
            t0 = time.perf_counter()
            s.simulate(p)
            ts.append(time.perf_counter() - t0)
        rep[s.meta["name"]] = {"seconds_per_traj": float(np.median(ts)), "t_end": t_end, "n": s.n, "K": s.model.K,
                               "h": s.h_max, "sim_seconds_per_second": float(np.median(ts) / t_end)}
    return rep


if __name__ == "__main__":
    from .systems import build_all

    systems = build_all(0, "dev")
    print(json.dumps({"accuracy": accuracy_report(systems), "timing": timing_report(systems)}, indent=1))
