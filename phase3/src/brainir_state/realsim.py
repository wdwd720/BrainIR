"""Real-circuit trajectory engine (ORCHESTRATOR SIDE: never copied into the method clean room; methods reach it only through the
budgeted simulation service, which enforces the public intervention families).

A *system* is a public bundle network, either intact ("full") or reduced to a candidate mechanism by keep-only ("mech"), with a
fixed observed population (the encoder's input x), readout population (y) and stimulus neurons (u). A protocol
(`brainir_state.protocol`) is integrated by composing the FROZEN Phase 1 simulator (`brainir.sim.model.simulate`) piece by
piece: the right-hand side is constant between breakpoints (stimulus steps, event edges), so each piece is one frozen call
started from the previous piece's final state, with its own input currents and structural intervention. Kicks are applied at
piece boundaries. Weight noise is applied ONCE to the base matrix, so every piece sees the same perturbed weights.
"""

from __future__ import annotations

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

ENGINE_VERSION = "p3-realsim-1"
ACTIVE_HZ = 0.01


@dataclass(frozen=True)
class RealSystem:
    """One physical system built from a public bundle network."""
    system_id: str
    network: str
    mode: str                                   # "full" | "mech"
    keep: tuple[int, ...] = ()                  # mechanism members (mode "mech")
    observed: tuple[int, ...] = ()              # encoder input population (never readout or stimulus neurons)
    readout: tuple[int, ...] = ()               # readout population (y)
    stimulus: tuple[int, ...] = ()              # stimulus neurons (u)
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    def content(self) -> dict:
        return {"system_id": self.system_id, "network": self.network, "mode": self.mode, "keep": list(self.keep),
                "observed": list(self.observed), "readout": list(self.readout), "stimulus": list(self.stimulus)}

    def content_hash(self, bundle_sha: str) -> str:
        return hashlib.sha256(json.dumps({"bundle": bundle_sha, **self.content()}, sort_keys=True).encode()).hexdigest()


class RealEngine:
    """Integrates protocols on the systems of one public bundle network (one DiscoveryProblem, cached parameters)."""

    def __init__(self, bundle: Path | str, network: str):
        self.problem = DiscoveryProblem.from_bundle(bundle, network)
        man = json.loads((Path(bundle) / "manifest.json").read_text(encoding="utf-8"))
        self.bundle_sha = man.get("bundle_sha256", "")
        self._params: dict[int, object] = {}
        self._W = sp.csr_matrix(self.problem.W, dtype=np.float64)
        self.nominal_current = float(self.problem.stim_current)

    # ---------------------------------------------------------------- parameters and weights
    def params(self, seed: int):
        if seed not in self._params:
            if len(self._params) > 64:
                self._params.clear()
            self._params[seed] = sample_neuron_params(self.problem.model_cfg, self.problem.n, seed=int(seed), sizes=self.problem.sizes)
        return self._params[seed]

    def base_weights(self, weight_noise: dict | None) -> sp.csr_matrix:
        if not weight_noise or float(weight_noise["sd"]) <= 0:
            return self._W
        return apply_intervention(self._W, Intervention(weight_noise_sd=float(weight_noise["sd"]), weight_noise_seed=int(weight_noise["seed"])))

    # ---------------------------------------------------------------- integration
    def run(self, system: RealSystem, proto: dict) -> dict:
        """Integrate one protocol. Returns the full microstate on the output grid, stored sparsely (only neurons that are ever
        non-zero), plus the input, readout and bookkeeping."""
        q = P.validate(proto)
        if q["system"] != system.system_id:
            raise P.ProtocolError(f"protocol is for {q['system']!r}, not {system.system_id!r}")
        n, dt, t_end = self.problem.n, q["dt"], q["t_end"]
        cfg0 = dataclasses.replace(self.problem.model_cfg, dt_out=dt)
        params = self.params(q["params_seed"])
        W0 = self.base_weights(q["weight_noise"])
        grid = np.round(np.arange(0.0, t_end + dt / 2, dt), 9)
        grid = grid[grid <= t_end + 1e-12]
        R = np.zeros((len(grid), n), dtype=np.float64)
        r = np.zeros(n)
        if q["r0"]["kind"] == "state":
            for k, v in q["r0"]["values"].items():
                r[int(k)] = v
        R[0] = r
        bps = P.breakpoints(q)
        stim_idx = list(system.stimulus)
        u = np.zeros((len(grid), max(1, len(stim_idx))), dtype=np.float64)
        n_calls, ok = 0, True
        kicks_applied: list[dict] = []
        for a, b in zip(bps[:-1], bps[1:]):
            ia, ib = int(round(a / dt)), int(round(b / dt))
            # the sample at a kick's time is the PRE-kick state (x_t is what an encoder sees before the intervention); the
            # kick acts immediately after it, so the jump appears between t and t + dt
            R[ia] = r
            for e in q["events"]:
                if e["kind"] == "kick" and abs(e["t"] - a) < 1e-9:
                    requested, applied = {}, {}
                    for k, d in e["delta"].items():
                        before = r[int(k)]
                        r[int(k)] = max(0.0, before + d)
                        # rates are clipped at 0: the APPLIED offset differs from the requested one when before + d < 0
                        requested[k] = float(d)
                        applied[k] = float(d) if before + d >= 0.0 else float(-before)
                    kicks_applied.append({"t": float(e["t"]), "requested": requested, "applied": applied})
            if ib <= ia:
                continue
            scale = [s for t, s in q["stimulus"] if t <= a + 1e-9][-1]
            cur = np.zeros(n)
            for i in stim_idx:
                cur[i] += scale * self.nominal_current
            silence: set[int] = set()
            removed: list[tuple[int, int]] = []
            for e in q["events"]:
                if e["kind"] == "current" and e["t0"] <= a + 1e-9 and b <= e["t1"] + 1e-9:
                    for k, I in e["targets"].items():
                        cur[int(k)] += I
                elif e["kind"] in ("silence", "edge_remove") and e["t0"] <= a + 1e-9 and (e["t1"] is None or b <= e["t1"] + 1e-9):
                    if e["kind"] == "silence":
                        silence |= set(e["targets"])
                    else:
                        removed += [(int(p), int(q_)) for p, q_ in e["edges"]]
            W = W0
            if removed:
                W = W0.tolil(copy=True)
                for p_, q_ in removed:
                    W[p_, q_] = 0.0
                W = W.tocsr()
            iv = Intervention(silence=tuple(sorted(silence)), keep_only=tuple(system.keep) if system.mode == "mech" else None,
                              always_keep=tuple(sorted(set(system.stimulus) | set(system.readout))) if system.mode == "mech" else ())
            nz = np.flatnonzero(cur)
            stim = Stimulus(tuple(int(i) for i in nz), tuple(float(cur[i]) for i in nz) or (0.0,), pulse_start=0.0, pulse_end=b - a + dt)
            cfg = dataclasses.replace(cfg0, t_end=round(b - a, 9))
            tr = simulate(W, params, cfg, stim, iv, r0=r)
            n_calls += 1
            ok &= bool(tr.info.get("success", True)) and "non_finite_samples" not in tr.info
            seg = tr.r[: ib - ia + 1]
            R[ia + 1: ib + 1] = seg[1:]
            r = seg[-1].copy()
            if stim_idx:
                u[ia:ib, :] = scale * self.nominal_current
        if stim_idx:
            u[-1, :] = u[-2, :] if len(u) > 1 else u[-1, :]
        nonzero = np.flatnonzero(np.abs(R).max(axis=0) > 0)
        info = {"engine": ENGINE_VERSION, "simulator": MODEL_ID, "n_calls": n_calls, "success": bool(ok), "n": int(n),
                "bundle_sha256": self.bundle_sha, "network": self.problem.name}
        if kicks_applied:
            # benchmark version 3 (pre-lock review D, M1): the applied (clipped) kick offsets, next to the requested ones. The
            # event dicts are unchanged (methods keep seeing the requested offsets, as in the public data); the simulated rates
            # are bitwise identical to engine p3-realsim-1 without this record, so ENGINE_VERSION (a store-key input) is unchanged
            info["kicks_applied"] = kicks_applied
        return {"t": grid, "neurons": nonzero.astype(np.int32), "rates": R[:, nonzero].astype(np.float32), "u": u.astype(np.float32),
                "info": info}


def kicks_applied_from_record(record: dict, proto: dict) -> list[dict]:
    """The applied kick offsets of a protocol, reconstructed from a stored record (for records stored before the engine recorded
    them): the sample at a kick's time holds the PRE-kick rates, so the applied offset is d if r_pre + d >= 0, else -r_pre. The
    stored rates are float32, so the reconstruction is exact up to float32 rounding of r_pre (flagged "source": "record"). With
    several kicks on one neuron at the same time the later ones would see the earlier ones' result; the protocol generators never
    produce that, and such a case is flagged "ambiguous"."""
    q = P.validate(proto)
    dt = q["dt"]
    pos = {int(n): i for i, n in enumerate(record["neurons"])}
    out, seen = [], {}
    for e in q.get("events") or []:
        if e["kind"] != "kick":
            continue
        i = int(round(e["t"] / dt))
        requested, applied = {}, {}
        for k, d in e["delta"].items():
            j = pos.get(int(k))
            pre = float(record["rates"][i, j]) if (j is not None and i < len(record["rates"])) else 0.0
            requested[k] = float(d)
            applied[k] = float(d) if pre + d >= 0.0 else float(-pre)
            seen[(i, int(k))] = seen.get((i, int(k)), 0) + 1
        out.append({"t": float(e["t"]), "requested": requested, "applied": applied, "source": "record"})
    if any(c > 1 for c in seen.values()):
        for rec in out:
            rec["ambiguous"] = True
    return out


def dense(record: dict, neurons: list[int] | tuple[int, ...]) -> np.ndarray:
    """Rates of the given neurons (T x len(neurons)) from a sparse record; neurons never active are zero columns."""
    pos = {int(n): i for i, n in enumerate(record["neurons"])}
    out = np.zeros((len(record["t"]), len(neurons)), dtype=np.float32)
    for j, n in enumerate(neurons):
        i = pos.get(int(n))
        if i is not None:
            out[:, j] = record["rates"][:, i]
    return out
