"""Real-circuit trajectory engine, version 2 (ORCHESTRATOR SIDE: never copied into a method room; developers reach it only through
the budgeted simulation service, which enforces the public policy).

A system is a public bundle network, either intact ("full") or reduced to a candidate mechanism by keep-only ("mech"), with a fixed
observed population (x), readout population (y) and stimulus neurons (u). A protocol (`brainir_causal.protocol`, format
p4-protocol-1) is integrated by composing the FROZEN Phase 1 simulator (`brainir.sim.model.simulate`) piece by piece, exactly like
the Phase 3 engine (phase3 `brainir_state.realsim`): the right-hand side is constant between breakpoints (stimulus steps, event
edges, current-sequence segment boundaries), so each piece is one frozen call started from the previous piece's final state, with
its own input currents, structural intervention and neuron parameters. Kicks are applied at piece boundaries (rates clipped at 0).
Weight noise is applied ONCE to the base matrix. `params_spread` scales the standard deviations of the parameter draw (a copy of the
model configuration handed to the frozen sampler); `process_noise` is refused (the frozen integrator is deterministic). On protocols
expressible in both formats (kick, current, silence, edge removal =
edge_scale with factor 0) the rates are bit-identical to the Phase 3 engine (tested).

New in version 2:
- `current_seq`: the segment value in force is added to the targets' input current on each piece;
- `edge_scale`: the listed weights of the (noised) count matrix are multiplied by the factor while active (factor 0 = removal, set
  to exactly 0 as in Phase 3; several active scalings of one edge multiply);
- `param`: per-neuron parameter changes while active: gain a *= g, time constant tau *= c, threshold theta += d (input units),
  applied to the sampled, size-scaled parameters of the trajectory's draw;
- r0 `restart`: the full microstate of a stored trajectory at its sample time (stored rates are float32, so a restart starts from
  the float32-rounded state; the continuation follows the original trajectory up to that rounding, which strongly recurrent or
  oscillatory systems amplify: about 0.2 % of the trajectory's scale after 0.3 s on the largest mechanism, tested);
- observation noise is NOT part of the simulated record: `observe()` adds it to the returned observed arrays only (seeded, sd
  relative to the system's public observation scale), so the stored microstate never depends on it.
"""

from __future__ import annotations

import bisect
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from brainir.discovery.problem import DiscoveryProblem
from brainir.sim.model import MODEL_ID, Intervention, Stimulus, apply_intervention, sample_neuron_params, simulate

from . import protocol as P

ENGINE_VERSION = "p4-realsim-1"
ACTIVE_HZ = 0.01
MAX_INIT_RATE = 1000.0


@dataclass(frozen=True)
class RealSystem:
    """One physical system built from a public bundle network (the fields the engine needs)."""
    system_id: str
    network: str
    mode: str                                   # "full" | "mech"
    keep: tuple[int, ...] = ()                  # mechanism members (mode "mech")
    observed: tuple[int, ...] = ()              # encoder input population
    readout: tuple[int, ...] = ()               # readout population (y)
    stimulus: tuple[int, ...] = ()              # stimulus neurons (u)
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    def content(self) -> dict:
        return {"system_id": self.system_id, "network": self.network, "mode": self.mode, "keep": list(self.keep),
                "observed": list(self.observed), "readout": list(self.readout), "stimulus": list(self.stimulus)}

    def content_hash(self, bundle_sha: str) -> str:
        return hashlib.sha256(json.dumps({"engine": ENGINE_VERSION, "bundle": bundle_sha, **self.content()}, sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_record(cls, d: dict) -> RealSystem:
        return cls(system_id=d["system_id"], network=d["network"], mode=d["mode"], keep=tuple(int(x) for x in d.get("keep", [])),
                   observed=tuple(int(x) for x in d["observed"]), readout=tuple(int(x) for x in d["readout"]),
                   stimulus=tuple(int(x) for x in d["stimulus"]))


def _active(e: dict, a: float, b: float) -> bool:
    """Whether a windowed event acts on the whole piece [a, b) (the Phase 3 rule)."""
    return e["t0"] <= a + 1e-9 and (e["t1"] is None or b <= e["t1"] + 1e-9)


class RealEngine:
    """Integrates protocols on the systems of one public bundle network (one DiscoveryProblem, cached parameter draws)."""

    def __init__(self, bundle: Path | str, network: str):
        self.problem = DiscoveryProblem.from_bundle(bundle, network)
        man = json.loads((Path(bundle) / "manifest.json").read_text(encoding="utf-8"))
        self.bundle_sha = man.get("bundle_sha256", "")
        self._params: dict[tuple[int, float], object] = {}
        self._W = sp.csr_matrix(self.problem.W, dtype=np.float64)
        self.nominal_current = float(self.problem.stim_current)

    # ---------------------------------------------------------------- parameters and weights
    def params(self, seed: int, spread: float = 1.0):
        """The per-neuron parameter draw of a trajectory. spread != 1 scales the standard deviations of the four truncated normals
        (tau, a, theta, r_max) of a copy of the model configuration handed to the FROZEN sampler (spread 1.0 = the frozen
        configuration itself, so draws are bit-identical to the unscaled sampler)."""
        key = (int(seed), float(spread))
        if key not in self._params:
            if len(self._params) > 64:
                self._params.clear()
            cfg = self.problem.model_cfg
            if float(spread) != 1.0:
                cfg = dataclasses.replace(cfg, tau_sd=cfg.tau_sd * spread, a_sd=cfg.a_sd * spread, theta_sd=cfg.theta_sd * spread,
                                          r_max_sd=cfg.r_max_sd * spread)
            self._params[key] = sample_neuron_params(cfg, self.problem.n, seed=int(seed), sizes=self.problem.sizes)
        return self._params[key]

    def base_weights(self, weight_noise: dict | None) -> sp.csr_matrix:
        if not weight_noise or float(weight_noise["sd"]) <= 0:
            return self._W
        return apply_intervention(self._W, Intervention(weight_noise_sd=float(weight_noise["sd"]), weight_noise_seed=int(weight_noise["seed"])))

    # ---------------------------------------------------------------- initial state
    def _initial_state(self, system: RealSystem, q: dict, store) -> np.ndarray:
        n = self.problem.n
        r = np.zeros(n)
        r0 = q["r0"]
        if r0["kind"] == "state":
            for k, v in r0["values"].items():
                i = int(k)
                if not (0 <= i < n):
                    raise P.ProtocolError(f"r0.values: unit {i} outside the network (size {n})")
                if not (0.0 <= float(v) <= MAX_INIT_RATE):
                    raise P.ProtocolError(f"r0.values: rates must be in [0, {MAX_INIT_RATE}] Hz")
                r[i] = float(v)
        elif r0["kind"] == "restart":
            if store is None:
                raise P.ProtocolError("r0 'restart' needs the trajectory store")
            rec = store.get(r0["key"])
            if rec is None:
                raise P.ProtocolError(f"r0.key {r0['key'][:12]}... is not in the store")
            info = rec.get("info") or {}
            if info.get("system_id") not in (None, system.system_id) or info.get("network") not in (None, self.problem.name):
                raise P.ProtocolError("r0 'restart' must come from a trajectory of the same system")
            if "neurons" not in rec:
                raise P.ProtocolError("r0 'restart' needs a record with the full microstate")
            t = np.asarray(rec["t"], dtype=np.float64)
            dt_src = float(t[1] - t[0]) if len(t) > 1 else 0.0
            i = int(round(r0["t"] / dt_src)) if dt_src > 0 else 0
            if not (0 <= i < len(t)) or abs(t[i] - r0["t"]) > 1e-9 + 1e-6 * dt_src:
                raise P.ProtocolError(f"r0.t={r0['t']} is not a sample time of the stored trajectory")
            r[np.asarray(rec["neurons"], dtype=np.int64)] = np.asarray(rec["rates"][i], dtype=np.float64)
        return r

    # ---------------------------------------------------------------- integration
    def run(self, system: RealSystem, proto: dict, store=None) -> dict:
        """Integrate one protocol. Returns the full microstate on the output grid, stored sparsely (only neurons that are ever
        non-zero), plus the input and bookkeeping. Observation noise is NOT applied here (see `observe`)."""
        q = P.validate(proto)
        if q["system"] != system.system_id:
            raise P.ProtocolError(f"protocol is for {q['system']!r}, not {system.system_id!r}")
        n, dt, t_end = self.problem.n, q["dt"], q["t_end"]
        cfg0 = dataclasses.replace(self.problem.model_cfg, dt_out=dt)
        if q["process_noise"] is not None:
            raise P.ProtocolError("process noise is not supported by the real engine (the frozen integrator is deterministic)")
        params0 = self.params(q["params_seed"], q["params_spread"])
        W0 = self.base_weights(q["weight_noise"])
        grid = np.round(np.arange(0.0, t_end + dt / 2, dt), 9)
        grid = grid[grid <= t_end + 1e-12]
        R = np.zeros((len(grid), n), dtype=np.float64)
        r = self._initial_state(system, q, store)
        R[0] = r
        bps = P.breakpoints(q)
        stim_idx = list(system.stimulus)
        stim_vals = q["stimulus"]
        width = len(stim_vals[0][1]) if isinstance(stim_vals[0][1], list) else 0
        if width and width != len(stim_idx):
            raise P.ProtocolError(f"stimulus has {width} channels, the system has {len(stim_idx)} stimulus neurons")
        u = np.zeros((len(grid), max(1, len(stim_idx))), dtype=np.float64)
        seq_bounds = {id(e): P.seq_boundaries(e, dt) for e in q["events"] if e["kind"] == "current_seq"}
        for e in q["events"]:
            for key in ("delta", "targets"):
                units = e.get(key)
                if units is None:
                    continue
                for k in units:
                    if not (0 <= int(k) < n):
                        raise P.ProtocolError(f"{e['kind']}: unit {k} outside the network (size {n})")
            for ed in e.get("edges") or []:
                if not all(0 <= int(x) < n for x in ed):
                    raise P.ProtocolError(f"edge_scale: edge {ed} outside the network (size {n})")
        n_calls, ok, n_pieces = 0, True, 0
        kicks_applied: list[dict] = []
        for a, b in zip(bps[:-1], bps[1:]):
            ia, ib = int(round(a / dt)), int(round(b / dt))
            # the sample at a kick's time is the PRE-kick state (x_t is what an encoder sees before the intervention); the kick acts
            # immediately after it, so the jump appears between t and t + dt
            R[ia] = r
            for e in q["events"]:
                if e["kind"] == "kick" and abs(e["t"] - a) < 1e-9:
                    requested, applied = {}, {}
                    for k, d in e["delta"].items():
                        before = r[int(k)]
                        r[int(k)] = max(0.0, before + d)
                        requested[k] = float(d)
                        applied[k] = float(d) if before + d >= 0.0 else float(-before)
                    kicks_applied.append({"t": float(e["t"]), "requested": requested, "applied": applied})
            if ib <= ia:
                continue
            scale = [s for t, s in stim_vals if t <= a + 1e-9][-1]
            cur = np.zeros(n)
            if width:
                for i, s in zip(stim_idx, scale):
                    cur[i] += s * self.nominal_current
            else:
                for i in stim_idx:
                    cur[i] += scale * self.nominal_current
            silence: set[int] = set()
            scaled: list[tuple[int, int, float]] = []
            pchanges: list[tuple[int, dict]] = []
            for e in q["events"]:
                k = e["kind"]
                if k == "current" and _active(e, a, b):
                    for kk, I in e["targets"].items():
                        cur[int(kk)] += I
                elif k == "current_seq":
                    bnd = seq_bounds[id(e)]
                    if bnd[0] <= a + 1e-9 and b <= bnd[-1] + 1e-9:
                        j = bisect.bisect_right(bnd, a + 1e-9) - 1
                        for kk, lst in e["targets"].items():
                            cur[int(kk)] += lst[j]
                elif k == "silence" and _active(e, a, b):
                    silence |= set(e["targets"])
                elif k == "edge_scale" and _active(e, a, b):
                    scaled += [(int(p_), int(q_), float(e["factor"])) for p_, q_ in e["edges"]]
                elif k == "param" and _active(e, a, b):
                    pchanges += [(int(kk), v) for kk, v in e["targets"].items()]
            W = W0
            if scaled:
                W = W0.tolil(copy=True)
                for p_, q_, f in scaled:
                    if f == 0.0:
                        W[p_, q_] = 0.0                  # exactly the Phase 3 removal
                    else:
                        W[p_, q_] = W[p_, q_] * f
                W = W.tocsr()
            params = params0
            if pchanges:
                a_ = params0.a.copy()
                th = params0.theta.copy()
                tau = params0.tau.copy()
                for i, v in pchanges:
                    if "gain" in v:
                        a_[i] *= float(v["gain"])
                    if "threshold" in v:
                        th[i] += float(v["threshold"])
                    if "tau" in v:
                        tau[i] *= float(v["tau"])
                params = dataclasses.replace(params0, a=a_, theta=th, tau=tau)
                params.validate()
            iv = Intervention(silence=tuple(sorted(silence)), keep_only=tuple(system.keep) if system.mode == "mech" else None,
                              always_keep=tuple(sorted(set(system.stimulus) | set(system.readout))) if system.mode == "mech" else ())
            nz = np.flatnonzero(cur)
            stim = Stimulus(tuple(int(i) for i in nz), tuple(float(cur[i]) for i in nz) or (0.0,), pulse_start=0.0, pulse_end=b - a + dt)
            cfg = dataclasses.replace(cfg0, t_end=round(b - a, 9))
            tr = simulate(W, params, cfg, stim, iv, r0=r)
            n_calls += 1
            n_pieces += 1
            ok &= bool(tr.info.get("success", True)) and "non_finite_samples" not in tr.info
            seg = tr.r[: ib - ia + 1]
            R[ia + 1: ib + 1] = seg[1:]
            r = seg[-1].copy()
            if stim_idx:
                u[ia:ib, :] = (np.asarray(scale, dtype=np.float64) if width else scale) * self.nominal_current
        if stim_idx:
            u[-1, :] = u[-2, :] if len(u) > 1 else u[-1, :]
        nonzero = np.flatnonzero(np.abs(R).max(axis=0) > 0)
        info = {"engine": ENGINE_VERSION, "simulator": MODEL_ID, "n_calls": n_calls, "n_pieces": n_pieces, "success": bool(ok), "n": int(n),
                "bundle_sha256": self.bundle_sha, "network": self.problem.name, "system_id": system.system_id}
        if kicks_applied:
            info["kicks_applied"] = kicks_applied
        return {"t": grid, "neurons": nonzero.astype(np.int32), "rates": R[:, nonzero].astype(np.float32), "u": u.astype(np.float32),
                "info": info}


def dense(record: dict, neurons: list[int] | tuple[int, ...]) -> np.ndarray:
    """Rates of the given neurons (T x len(neurons)) from a sparse record; neurons never active are zero columns."""
    pos = {int(n): i for i, n in enumerate(record["neurons"])}
    out = np.zeros((len(record["t"]), len(neurons)), dtype=np.float32)
    for j, n in enumerate(neurons):
        i = pos.get(int(n))
        if i is not None:
            out[:, j] = record["rates"][:, i]
    return out


def observe(record: dict, system: RealSystem, proto: dict, obs_scale: dict | None = None) -> dict:
    """The observed arrays {t, x, u, y} of a record; observation noise (if the protocol asks for it) is added here, seeded by
    obs_noise.seed, with standard deviation obs_noise.sd x obs_scale['x'] (resp. ['y']). x and y are float32."""
    q = P.validate(proto)
    x = dense(record, list(system.observed))
    y = dense(record, list(system.readout))
    on = q["obs_noise"]
    if on is not None and float(on["sd"]) > 0:
        sc = obs_scale or {}
        if "x" not in sc or "y" not in sc:
            raise P.ProtocolError("observation noise needs the system's obs_scale")
        rng = np.random.default_rng(int(on["seed"]))
        x = (x.astype(np.float64) + float(on["sd"]) * float(sc["x"]) * rng.standard_normal(x.shape)).astype(np.float32)
        y = (y.astype(np.float64) + float(on["sd"]) * float(sc["y"]) * rng.standard_normal(y.shape)).astype(np.float32)
    return {"t": np.asarray(record["t"], dtype=np.float64), "x": x, "u": np.asarray(record["u"], dtype=np.float32), "y": y}
