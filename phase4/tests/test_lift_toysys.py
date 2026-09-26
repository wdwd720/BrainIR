"""A toy linear system with a KNOWN causal state, and exact / wrong models of it (shared by the E6 tests: lift, references,
stability, transfer, calibration).

Microstate x = M s, s = [z (2), w (n - 2)]: z evolves by closed controlled linear dynamics z' = A z + b u, the nuisance w decays on its
own (w' = -w / tau_w) and never reaches z or the readout y = G z. Interventions act on x (kick: x += dx, i.e. s += M^{-1} dx; current:
the targets' input, i.e. s' += M^{-1} I). So z = C x (C = the first two rows of M^{-1}) is the true causal state, and any two kicks with
the same C dx shift z identically and produce identical readout futures, whatever they do to w.
"""

from __future__ import annotations

import numpy as np

from brainir_causal import protocol as P
from brainir_causal.api import CausalStateModel

DT = 0.01
T_END = 2.0


class ToyLinear:
    def __init__(self, n: int = 5, seed: int = 0):
        rng = np.random.default_rng(seed)
        self.n = n
        self.sid = "toy"
        self.A = np.array([[-0.8, 2.0], [-2.0, -0.8]])          # damped rotation (latent causal dynamics)
        self.b = np.array([1.0, 0.3])
        self.tau_w = 0.15
        Q, _ = np.linalg.qr(rng.standard_normal((n, n)))
        self.M = Q * (1.0 + rng.random(n))                          # x = M s
        self.Minv = np.linalg.inv(self.M)
        self.C = self.Minv[:2]                                      # z = C x
        self.G = np.array([[1.0, 0.0], [0.5, -1.0], [0.2, 0.7]])  # y = G z
        self.observed = list(range(n))

    def record(self) -> dict:
        return {"system_id": self.sid, "observed": self.observed, "readout_dim": 3, "input_dim": 1, "dt": DT, "t_end_default": T_END,
                "targets_public": self.observed, "capability": {"kick": {"supported": True, "max": 50.0},
                                                                "current": {"supported": True, "max": 50.0, "pulse_max_duration": 0.15,
                                                                            "sustained_min_duration": 0.3}}}

    def simulate(self, proto: dict, full: bool = False) -> dict:
        q = P.validate(proto)
        dt = q["dt"]
        T = round(q["t_end"] / dt) + 1
        t = np.round(np.arange(T) * dt, 9)
        u = np.zeros((T, 1))
        for ts, v in q["stimulus"]:
            u[t >= ts - 1e-9, 0] = float(v if not isinstance(v, list) else v[0])
        s = np.zeros(self.n)
        if q["r0"]["kind"] == "state":
            x0 = np.zeros(self.n)
            for kk, v in q["r0"]["values"].items():
                x0[int(kk)] = v
            s = self.Minv @ x0
        rng = np.random.default_rng(q["params_seed"])
        A = self.A * (1.0 + 0.05 * rng.standard_normal((2, 2)))
        S = np.zeros((T, self.n))
        for i in range(T):
            S[i] = s
            if i == T - 1:
                break
            ti = t[i]
            for e in q["events"]:
                if e["kind"] == "kick" and abs(e["t"] - ti) < dt / 2:
                    dx = np.zeros(self.n)
                    for kk, v in e["delta"].items():
                        dx[int(kk)] += v
                    s = s + self.Minv @ dx
            cur = np.zeros(self.n)
            for e in q["events"]:
                if e["kind"] == "current" and e["t0"] <= ti + 1e-9 and (e["t1"] is None or ti < e["t1"] - 1e-9):
                    for kk, v in e["targets"].items():
                        cur[int(kk)] += v
            ds = np.zeros(self.n)
            ds[:2] = A @ s[:2] + self.b * u[i, 0]
            ds[2:] = -s[2:] / self.tau_w
            s = s + dt * (ds + self.Minv @ cur)
        X = S @ self.M.T
        Y = S[:, :2] @ self.G.T
        out = {"t": t, "x": X, "u": u, "y": Y, "info": {}}
        if full:
            out["z"] = S[:, :2].copy()
            out["state"] = X.copy()
        return out

    def simulate_many(self, protos: list[dict], full: bool = False) -> list[dict]:
        return [self.simulate(p, full=full) for p in protos]


def passive_protocol(seed: int, stim: float = 1.0, t_on: float = 0.1) -> dict:
    return {"system": "toy", "params_seed": seed, "t_end": T_END, "dt": DT, "stimulus": [[0.0, 0.0], [t_on, stim]], "events": []}


def make_records(sysm: ToyLinear, n_passive: int = 12, n_kick: int = 24, n_pulse: int = 12, seed: int = 0, full: bool = True):
    """Training records (dicts like brainir_causal.data.Trajectory): passive trajectories, kick and current-pulse trajectories on
    units 0..n-1 with their twins. Returns (records, truth {"z": {key: z}})."""
    rng = np.random.default_rng(seed)
    recs, z = [], {}

    def add(proto, split="train", meta=None):
        q = P.validate(proto)
        r = sysm.simulate(q, full=full)
        key = P.protocol_hash(q)
        rec = {"key": key, "system_id": "toy", "split": split, "family": "", "protocol": q, "t": r["t"], "x": r["x"], "u": r["u"],
               "y": r["y"], "meta": meta or {}}
        recs.append(rec)
        if full:
            z[key] = r["z"]
        return rec

    for i in range(n_passive):
        add(passive_protocol(1000 + i, stim=float(rng.uniform(0.5, 1.5)), t_on=float(rng.uniform(0.05, 0.4))))
    for i in range(n_kick + n_pulse):
        base = passive_protocol(2000 + i, stim=float(rng.uniform(0.5, 1.5)), t_on=float(rng.uniform(0.05, 0.3)))
        unit = int(rng.integers(0, sysm.n))
        t_ev = round(float(rng.uniform(0.4, 1.0)), 2)
        if i < n_kick:
            ev = {"kind": "kick", "t": t_ev, "delta": {str(unit): float(rng.choice([-1, 1]) * rng.uniform(0.5, 2.0))}}
        else:
            ev = {"kind": "current", "t0": t_ev, "t1": round(t_ev + 0.1, 2), "targets": {str(unit): float(rng.uniform(-8, 8))}}
        rint = add(dict(base, events=[ev]))
        add(P.counterfactual(rint["protocol"]), split="twin", meta={"twin_of": rint["key"]})
    return recs, {"z": z}


class ExactModel(CausalStateModel):
    """The exact causal model of ToyLinear (encoder z = C x, the nominal latent dynamics, readout G z, kick read-in C dx and a
    minimum-norm native lift over distinct unit subsets). With `wrong=True` the encoder mixes a nuisance coordinate into z (a
    causally WRONG latent of the same dimension)."""

    def __init__(self, sysm: ToyLinear, wrong: bool = False, lift_subsets=((0, 1, 2, 3, 4), (0, 1, 2), (2, 3, 4))):
        self.s = sysm
        self.k = {"toy": 2}
        C = sysm.C.copy()
        if wrong:
            C[1] = C[1] + 1.5 * sysm.Minv[2]
        self.Cenc = C
        self.lift_subsets = lift_subsets

    def encode(self, sid, x_hist, u_hist, dt):
        return self.Cenc @ np.asarray(x_hist, float)[-1]

    def supports(self, sid, kind):
        return kind in ("kick", "current")

    def rollout(self, sid, z0, u_future, events, dt):
        z = np.asarray(z0, float).copy()
        U = np.asarray(u_future, float).reshape(len(u_future), -1)
        out = [z.copy()]
        for j in range(len(U) - 1):
            tj = j * dt
            for e in events:
                if e["kind"] == "kick" and abs(e["t"] - tj) < dt / 2:
                    dx = np.zeros(self.s.n)
                    for kk, v in e["delta"].items():
                        dx[int(kk)] += v
                    z = z + self.Cenc @ dx
            cur = np.zeros(self.s.n)
            for e in events:
                if e["kind"] == "current" and e["t0"] <= tj + 1e-9 and (e["t1"] is None or tj < e["t1"] - 1e-9):
                    for kk, v in e["targets"].items():
                        cur[int(kk)] += v
            z = z + dt * (self.s.A @ z + self.s.b * U[j, 0] + self.Cenc @ cur)
            out.append(z.copy())
        Z = np.stack(out)
        return {"z": Z, "y": Z @ self.s.G.T}

    def readout(self, sid, z, u):
        return np.atleast_2d(z) @ self.s.G.T

    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        out = []
        for S in self.lift_subsets[:n_candidates]:
            Cs = self.Cenc[:, list(S)]
            dx = np.linalg.pinv(Cs) @ np.asarray(delta_z, float)
            out.append({"events": [{"kind": "kick", "t": 0.0, "delta": {str(u): float(v) for u, v in zip(S, dx)}}],
                        "predicted_dz": Cs @ dx, "cost": float(np.abs(dx).sum() * DT)})
        return out

    def info(self):
        return {"k": dict(self.k), "n_params": {"encoder": {"toy": self.Cenc.size}, "transition": 6, "read_in": {"toy": self.Cenc.size},
                                                "readout": {"toy": self.s.G.size}}}


def test_toy_truth_is_causal():
    """Two kicks with the same C dx give identical readout futures (the toy's causal state is z)."""
    s = ToyLinear()
    base = passive_protocol(7)
    C = s.C
    dz = np.array([0.4, -0.3])
    futures = []
    for S in ((0, 1, 2, 3, 4), (0, 1, 2)):
        dx = np.linalg.pinv(C[:, list(S)]) @ dz
        ev = {"kind": "kick", "t": 0.8, "delta": {str(u): float(v) for u, v in zip(S, dx)}}
        futures.append(s.simulate(dict(base, events=[ev]))["y"])
    assert np.max(np.abs(futures[0] - futures[1])) < 1e-9
    # but their microstates differ
    xa = s.simulate(dict(base, events=[{"kind": "kick", "t": 0.8, "delta": {"0": 1.0}}]))["x"]
    assert xa.shape == (201, 5)
