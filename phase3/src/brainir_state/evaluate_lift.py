"""Latent-intervention lifting (goal4 sections 13-14; PROTOCOL.md section 4 "latent-intervention lifting").

For a state model with `lift()`: at a sampled time t_i of a held-out trajectory (protocol P), request a latent shift delta_z; the
model proposes up to 3 DISTINCT microscopic interventions (kicks / currents at t_i). The evaluator applies each in the simulator
(P plus the lifted events, continued for the future horizon), and also runs the counterfactual twin (P without them). It measures

- achieved shift: z_after(lift) - z_after(twin), re-encoded from the SIMULATED microstate, against the requested delta_z
  (relative error ||achieved - delta_z|| / ||delta_z||), measured when the lift has finished acting (1 sample after a kick, at the end
  of a current pulse);
- latent-model fidelity after do(z := z + delta_z): the model's rollout from z + delta_z vs the simulator's readout after the lift
  (NMSE over the future window), next to the model's rollout from the unshifted z vs the twin;
- implementation invariance (goal4 section 14): divergence of the simulated futures across distinct lifts of the SAME delta_z, against
  the divergence across lifts of DIFFERENT delta_z of the same norm (ratio small = the future depends on the abstract state, not the
  microscopic realisation);
- for synthetic systems with truth: the TRUE latent shift produced by each lift (spread across lifts of one delta_z).

`simulate(protocol) -> {"t","x","u","y", optional "z"}` is supplied by the orchestrator (the synthetic generator or the real engine).
"""

from __future__ import annotations

import numpy as np

from .api import StateModel
from .evaluate import EvalConfig, _nmse, boot_mean

LIFT_KINDS = ("kick", "current")


def _end_of_lift(events: list[dict]) -> float:
    ends = []
    for e in events:
        ends.append(e["t"] if e["kind"] == "kick" else e.get("t1", e.get("t0", 0.0)))
    return max(ends) if ends else 0.0


def _shift_to(events: list[dict], t0: float) -> list[dict]:
    out = []
    for e in events:
        e2 = dict(e)
        if "t" in e2:
            e2["t"] = round(e2["t"] + t0, 6)
        if "t0" in e2:
            e2["t0"] = round(e2["t0"] + t0, 6)
        if e2.get("t1") is not None:
            e2["t1"] = round(e2["t1"] + t0, 6)
        out.append(e2)
    return out


def eval_lifting(model: StateModel, sid: str, cases: list[dict], simulate, scale: np.ndarray, cfg: EvalConfig = EvalConfig(),
                 future_s: float = 0.25, shift_sd: float = 0.5, n_lifts: int = 3, seed: int = 0) -> dict:
    """cases: [{"protocol": P (a held-out protocol without events), "t": t_i}] ; the evaluator draws delta_z = shift_sd x sd(z) along
    two random directions per case (two different shifts of equal norm, for the invariance ratio)."""
    rng = np.random.default_rng(seed)
    ach, fid_lift, fid_twin, same_div, diff_div, true_spread = [], [], [], [], [], []
    n_req = n_ok = 0
    zsd = None
    for c in cases:
        P, ti = c["protocol"], float(c["t"])
        dt = float(P["dt"])
        base = simulate(dict(P, t_end=round(ti + future_s + 2 * dt, 6)))
        i = int(round(ti / dt))
        z_now = np.asarray(model.encode(sid, base["x"][: i + 1], base["u"][: i + 1], dt), float)
        if zsd is None:
            zs = np.stack([np.asarray(model.encode(sid, base["x"][: j + 1], base["u"][: j + 1], dt), float)
                           for j in range(max(1, i // 2), i + 1, max(1, i // 20))])
            zsd = zs.std(0) + 1e-9
        dirs = rng.standard_normal((2, len(z_now)))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        futures = []
        for d in dirs:
            dz = shift_sd * zsd * d
            n_req += 1
            lifts = model.lift(sid, base["x"][i], z_now, dz, n_candidates=n_lifts) or []
            lifts = [lf for lf in lifts if lf and all(e.get("kind") in LIFT_KINDS for e in lf)]
            if not lifts:
                futures.append([])
                continue
            n_ok += 1
            fs, true_d = [], []
            for lf in lifts[:n_lifts]:
                ev = _shift_to(lf, ti)
                t_end_lift = _end_of_lift(ev)
                j = int(round(t_end_lift / dt)) + 1
                n_f = int(round(future_s / dt))
                P2 = dict(P, events=list(P.get("events") or []) + ev, t_end=round(t_end_lift + future_s + 2 * dt, 6))
                sim = simulate(P2)
                twin = simulate(dict(P, t_end=P2["t_end"]))
                z_l = np.asarray(model.encode(sid, sim["x"][: j + 1], sim["u"][: j + 1], dt), float)
                z_t = np.asarray(model.encode(sid, twin["x"][: j + 1], twin["u"][: j + 1], dt), float)
                ach.append(float(np.linalg.norm((z_l - z_t) - dz) / (np.linalg.norm(dz) + 1e-12)))
                u_f = sim["u"][j: j + n_f + 1]
                y_model_l = np.asarray(model.rollout(sid, z_t + dz, u_f, [], dt)["y"], float)[1:]
                y_model_t = np.asarray(model.rollout(sid, z_t, u_f, [], dt)["y"], float)[1:]
                fid_lift.append(_nmse(y_model_l, sim["y"][j + 1: j + n_f + 1], scale))
                fid_twin.append(_nmse(y_model_t, twin["y"][j + 1: j + n_f + 1], scale))
                fs.append(sim["y"][j + 1: j + n_f + 1].astype(np.float64))
                if "z" in sim and "z" in twin:
                    true_d.append(np.asarray(sim["z"][j], float) - np.asarray(twin["z"][j], float))
            if len(true_d) >= 2:
                # relative spread of the TRUE latent shift across distinct lifts of one requested shift
                pair = [np.linalg.norm(true_d[a] - true_d[b]) for a in range(len(true_d)) for b in range(a + 1, len(true_d))]
                true_spread.append(float(np.mean(pair) / (np.mean([np.linalg.norm(v) for v in true_d]) + 1e-12)))
            futures.append(fs)
        for fs in futures:
            for a in range(len(fs)):
                for b in range(a + 1, len(fs)):
                    same_div.append(_nmse(fs[a], fs[b], scale))
        if len(futures) == 2 and futures[0] and futures[1]:
            for fa in futures[0]:
                for fb in futures[1]:
                    diff_div.append(_nmse(fa, fb, scale))
    res = {"n_requested": n_req, "n_lifted": n_ok, "supported": n_ok > 0}
    if not ach:
        return res
    res["achieved_shift_rel_error"] = dict(zip(("mean", "ci95"), boot_mean(np.array(ach), cfg.n_boot, cfg.seed)))
    res["model_nmse_after_lift"] = dict(zip(("mean", "ci95"), boot_mean(np.array(fid_lift), cfg.n_boot, cfg.seed)))
    res["model_nmse_twin"] = dict(zip(("mean", "ci95"), boot_mean(np.array(fid_twin), cfg.n_boot, cfg.seed)))
    if same_div and diff_div:
        res["future_div_same_shift"] = float(np.mean(same_div))
        res["future_div_different_shift"] = float(np.mean(diff_div))
        res["implementation_invariance_ratio"] = float(np.mean(same_div) / max(np.mean(diff_div), 1e-12))
    if true_spread:
        res["true_latent_shift_spread_rel"] = float(np.mean(true_spread))
    return res
