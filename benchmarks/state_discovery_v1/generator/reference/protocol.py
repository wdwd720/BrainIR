"""Experiment protocols for state discovery (shared by the simulation service, the benchmark generators and methods).

A protocol is a JSON-serialisable description of ONE trajectory of a physical system:

    {"system": "<system id>",                          # e.g. "real:<network>:full", "real:<network>:mech:<hash>", "syn:<id>"
     "params_seed": int,                               # draw of the per-neuron model parameters
     "weight_noise": {"sd": float, "seed": int} | null,  # structural parameter perturbation, fixed for the whole trajectory
     "r0": {"kind": "zero"} | {"kind": "state", "values": {"<neuron>": rate, ...}},
     "t_end": float, "dt": float,                       # duration and output sampling (s)
     "stimulus": [[t_start, scale], ...],               # piecewise-constant multiplier of the nominal stimulus current
     "events": [event, ...]}

Events (times in seconds, neurons are the system's public neuron ids = positions in its bundle network):
    {"kind": "kick", "t": t, "delta": {"<neuron>": d_rate}}              instantaneous rate offset (result clipped at 0)
    {"kind": "current", "t0": a, "t1": b, "targets": {"<neuron>": I}}    extra input current during [a, b)
    {"kind": "silence", "t0": a, "t1": b | null, "targets": [neurons]}   remove the neurons' synapses during [a, b)
    {"kind": "edge_remove", "t0": a, "t1": b | null, "edges": [[post, pre], ...]}

Every time is snapped to the output grid. `canonical()` gives the form that defines the content hash of a trajectory.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

EVENT_KINDS = ("kick", "current", "silence", "edge_remove")
PROTOCOL_VERSION = "p3-protocol-1"


class ProtocolError(ValueError):
    pass


def _snap(t: float, dt: float) -> float:
    return round(round(float(t) / dt) * dt, 9)


def validate(p: dict[str, Any]) -> dict[str, Any]:
    """Check a protocol and return its canonical copy (times snapped to the grid, keys sorted, neuron ids as strings)."""
    if not isinstance(p, dict):
        raise ProtocolError("a protocol is a dict")
    q = copy.deepcopy(p)
    for k in ("system", "params_seed", "t_end", "dt"):
        if k not in q:
            raise ProtocolError(f"missing {k!r}")
    dt = float(q["dt"])
    if not (1e-4 <= dt <= 0.05):
        raise ProtocolError("dt must be in [0.1 ms, 50 ms]")
    t_end = _snap(q["t_end"], dt)
    if not (dt * 10 <= t_end <= 20.0):
        raise ProtocolError("t_end must be in [10 dt, 20 s]")
    q["t_end"], q["dt"] = t_end, dt
    q["params_seed"] = int(q["params_seed"])
    wn = q.get("weight_noise")
    if wn is not None:
        if float(wn.get("sd", 0)) < 0 or float(wn.get("sd", 0)) > 1.0:
            raise ProtocolError("weight_noise.sd must be in [0, 1]")
        q["weight_noise"] = {"sd": float(wn["sd"]), "seed": int(wn["seed"])}
    else:
        q["weight_noise"] = None
    r0 = q.get("r0") or {"kind": "zero"}
    if r0.get("kind") not in ("zero", "state"):
        raise ProtocolError("r0.kind must be 'zero' or 'state'")
    if r0["kind"] == "state":
        vals = {str(int(k)): float(v) for k, v in (r0.get("values") or {}).items()}
        if any((not math.isfinite(v)) or v < 0 for v in vals.values()):
            raise ProtocolError("initial rates must be finite and >= 0")
        r0 = {"kind": "state", "values": dict(sorted(vals.items(), key=lambda kv: int(kv[0])))}
    q["r0"] = r0
    stim = q.get("stimulus") or [[0.0, 1.0]]
    stim = sorted(([_snap(t, dt), float(s)] for t, s in stim), key=lambda x: x[0])
    if stim[0][0] != 0.0:
        stim = [[0.0, 0.0]] + stim
    if any(not math.isfinite(s) or abs(s) > 10 for _, s in stim):
        raise ProtocolError("stimulus scales must be finite and |scale| <= 10")
    q["stimulus"] = stim
    evs = []
    for e in q.get("events") or []:
        k = e.get("kind")
        if k not in EVENT_KINDS:
            raise ProtocolError(f"unknown event kind {k!r}")
        if k == "kick":
            ev = {"kind": k, "t": _snap(e["t"], dt), "delta": {str(int(n)): float(v) for n, v in sorted(e["delta"].items(), key=lambda kv: int(kv[0]))}}
        elif k == "current":
            ev = {"kind": k, "t0": _snap(e["t0"], dt), "t1": _snap(e["t1"], dt),
                  "targets": {str(int(n)): float(v) for n, v in sorted(e["targets"].items(), key=lambda kv: int(kv[0]))}}
            if ev["t1"] <= ev["t0"]:
                raise ProtocolError("current event needs t1 > t0")
        elif k == "silence":
            ev = {"kind": k, "t0": _snap(e["t0"], dt), "t1": None if e.get("t1") is None else _snap(e["t1"], dt),
                  "targets": sorted({int(n) for n in e["targets"]})}
        else:
            ev = {"kind": k, "t0": _snap(e["t0"], dt), "t1": None if e.get("t1") is None else _snap(e["t1"], dt),
                  "edges": sorted({(int(a), int(b)) for a, b in e["edges"]})}
            ev["edges"] = [list(x) for x in ev["edges"]]
        for key in ("t", "t0", "t1"):
            if ev.get(key) is not None and not (0.0 <= ev[key] <= t_end):
                raise ProtocolError(f"event time {key}={ev[key]} outside [0, t_end]")
        evs.append(ev)
    q["events"] = sorted(evs, key=lambda ev: (ev.get("t", ev.get("t0")), ev["kind"], json.dumps(ev, sort_keys=True)))
    return {k: q[k] for k in ("system", "params_seed", "weight_noise", "r0", "t_end", "dt", "stimulus", "events")}


def canonical_json(p: dict[str, Any]) -> str:
    return json.dumps(validate(p), sort_keys=True, separators=(",", ":"))


def protocol_hash(p: dict[str, Any], *, system_hash: str = "", simulator: str = "") -> str:
    """Content key of a trajectory: the canonical protocol plus the system's content hash and the simulator version."""
    blob = json.dumps({"v": PROTOCOL_VERSION, "p": json.loads(canonical_json(p)), "system": system_hash, "sim": simulator},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def breakpoints(p: dict[str, Any]) -> list[float]:
    """Times at which the right-hand side changes (stimulus steps, event starts / ends, kicks), including 0 and t_end."""
    q = validate(p)
    ts = {0.0, q["t_end"]}
    ts.update(t for t, _ in q["stimulus"])
    for e in q["events"]:
        for key in ("t", "t0", "t1"):
            if e.get(key) is not None:
                ts.add(e[key])
    return sorted(t for t in ts if 0.0 <= t <= q["t_end"])


def intervened_neurons(p: dict[str, Any]) -> set[int]:
    """Every neuron an event acts on (kicks, currents, silencing, both ends of removed edges)."""
    q = validate(p)
    out: set[int] = set()
    for e in q["events"]:
        if e["kind"] == "kick":
            out |= {int(n) for n in e["delta"]}
        elif e["kind"] == "current":
            out |= {int(n) for n in e["targets"]}
        elif e["kind"] == "silence":
            out |= set(e["targets"])
        else:
            out |= {int(x) for ed in e["edges"] for x in ed}
    return out
