"""Protocol validation for synthetic systems.

Same schema and canonical form as `reference/protocol.py`, extended as allowed by protocol_spec.md:

- neuron states of synthetic systems are signed activations, so `r0` values may be negative (they must be finite);
- a stimulus value may be a scalar (scales the system's nominal input pattern) or a list of length input_dim;
- optional "noise_seed" (int >= 0): when present, every random realisation of the trajectory (process, private,
  observation and readout noise, hidden exogenous input) is drawn from (system seed, noise_seed) instead of the
  canonical protocol; it is part of the canonical form (and hence of the hash) only when present;
- the evaluator-only latent events `latent_set` {"t", "values": {i: v}} and `latent_impulse` {"t", "delta": {i: d}}
  are accepted (only when `allow_latent=True`; method-facing code paths never set it).

Every time is snapped to the output grid exactly as in the reference.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

MICRO_EVENTS = ("kick", "current", "silence", "edge_remove")
LATENT_EVENTS = ("latent_set", "latent_impulse")
PROTOCOL_VERSION = "p3-protocol-1"


class ProtocolError(ValueError):
    pass


def _snap(t: float, dt: float) -> float:
    return round(round(float(t) / dt) * dt, 9)


def _neuron(n, n_max: int | None) -> str:
    i = int(n)
    if i < 0 or (n_max is not None and i >= n_max):
        raise ProtocolError(f"neuron id {n!r} out of range")
    return str(i)


def _stim_value(s, input_dim: int | None):
    if isinstance(s, (list, tuple)):
        vals = [float(v) for v in s]
        if input_dim is not None and len(vals) != input_dim:
            raise ProtocolError(f"stimulus vector must have length input_dim={input_dim}")
        if any(not math.isfinite(v) or abs(v) > 10 for v in vals):
            raise ProtocolError("stimulus values must be finite and |value| <= 10")
        return vals
    v = float(s)
    if not math.isfinite(v) or abs(v) > 10:
        raise ProtocolError("stimulus scales must be finite and |scale| <= 10")
    return v


def validate(p: dict[str, Any], *, n: int | None = None, input_dim: int | None = None, k: int | None = None,
             allow_latent: bool = True) -> dict[str, Any]:
    """Check a protocol and return its canonical copy (times snapped, keys sorted, neuron ids as strings)."""
    if not isinstance(p, dict):
        raise ProtocolError("a protocol is a dict")
    q = copy.deepcopy(p)
    for key in ("system", "params_seed", "t_end", "dt"):
        if key not in q:
            raise ProtocolError(f"missing {key!r}")
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
        vals = {_neuron(key, n): float(v) for key, v in (r0.get("values") or {}).items()}
        if any(not math.isfinite(v) for v in vals.values()):
            raise ProtocolError("initial states must be finite")
        r0 = {"kind": "state", "values": dict(sorted(vals.items(), key=lambda kv: int(kv[0])))}
    else:
        r0 = {"kind": "zero"}
    q["r0"] = r0
    stim = q.get("stimulus") or [[0.0, 1.0]]
    stim = sorted(([_snap(t, dt), _stim_value(s, input_dim)] for t, s in stim), key=lambda x: x[0])
    if stim[0][0] != 0.0:
        stim = [[0.0, 0.0]] + stim
    q["stimulus"] = stim
    evs = []
    for e in q.get("events") or []:
        kind = e.get("kind")
        if kind in LATENT_EVENTS and not allow_latent:
            raise ProtocolError(f"latent event {kind!r} is evaluator-only")
        if kind not in MICRO_EVENTS + LATENT_EVENTS:
            raise ProtocolError(f"unknown event kind {kind!r}")
        if kind == "kick":
            ev = {"kind": kind, "t": _snap(e["t"], dt),
                  "delta": {_neuron(i, n): float(v) for i, v in sorted(e["delta"].items(), key=lambda kv: int(kv[0]))}}
        elif kind == "current":
            ev = {"kind": kind, "t0": _snap(e["t0"], dt), "t1": _snap(e["t1"], dt),
                  "targets": {_neuron(i, n): float(v) for i, v in sorted(e["targets"].items(), key=lambda kv: int(kv[0]))}}
            if ev["t1"] <= ev["t0"]:
                raise ProtocolError("current event needs t1 > t0")
        elif kind == "silence":
            ev = {"kind": kind, "t0": _snap(e["t0"], dt), "t1": None if e.get("t1") is None else _snap(e["t1"], dt),
                  "targets": sorted({int(_neuron(i, n)) for i in e["targets"]})}
        elif kind == "edge_remove":
            ev = {"kind": kind, "t0": _snap(e["t0"], dt), "t1": None if e.get("t1") is None else _snap(e["t1"], dt),
                  "edges": [list(x) for x in sorted({(int(_neuron(a, n)), int(_neuron(b, n))) for a, b in e["edges"]})]}
        else:
            field = "values" if kind == "latent_set" else "delta"
            items = {}
            for i, v in (e.get(field) or {}).items():
                ii = int(i)
                if ii < 0 or (k is not None and ii >= k):
                    raise ProtocolError(f"latent index {i!r} out of range")
                if not math.isfinite(float(v)):
                    raise ProtocolError("latent event values must be finite")
                items[str(ii)] = float(v)
            ev = {"kind": kind, "t": _snap(e["t"], dt), field: dict(sorted(items.items(), key=lambda kv: int(kv[0])))}
        for key in ("t", "t0", "t1"):
            if ev.get(key) is not None and not (0.0 <= ev[key] <= t_end):
                raise ProtocolError(f"event time {key}={ev[key]} outside [0, t_end]")
        evs.append(ev)
    q["events"] = sorted(evs, key=lambda ev: (ev.get("t", ev.get("t0")), ev["kind"], json.dumps(ev, sort_keys=True)))
    out = {key: q[key] for key in ("system", "params_seed", "weight_noise", "r0", "t_end", "dt", "stimulus", "events")}
    if q.get("noise_seed") is not None:
        ns = q["noise_seed"]
        if isinstance(ns, bool) or not isinstance(ns, (int, float)) or float(ns) != int(ns) or int(ns) < 0:
            raise ProtocolError("noise_seed must be an integer >= 0")
        out["noise_seed"] = int(ns)
    return out


def canonical_json(p: dict[str, Any], **kw) -> str:
    return json.dumps(validate(p, **kw), sort_keys=True, separators=(",", ":"))


def protocol_hash(p: dict[str, Any], *, system_hash: str = "", simulator: str = "") -> str:
    blob = json.dumps({"v": PROTOCOL_VERSION, "p": json.loads(canonical_json(p)), "system": system_hash, "sim": simulator},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def has_latent_events(p: dict[str, Any]) -> bool:
    return any(e.get("kind") in LATENT_EVENTS for e in p.get("events") or [])


def intervened_neurons(p: dict[str, Any]) -> set[int]:
    """Every neuron a microscopic event acts on (kicks, currents, silencing, both ends of removed edges)."""
    q = validate(p)
    out: set[int] = set()
    for e in q["events"]:
        if e["kind"] == "kick":
            out |= {int(i) for i in e["delta"]}
        elif e["kind"] == "current":
            out |= {int(i) for i in e["targets"]}
        elif e["kind"] == "silence":
            out |= set(e["targets"])
        elif e["kind"] == "edge_remove":
            out |= {int(x) for ed in e["edges"] for x in ed}
    return out
