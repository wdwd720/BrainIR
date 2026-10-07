# Vendored verbatim from ref/protocol.py (reference protocol validation, format p4-protocol-1); tests check it stays identical.
"""Experiment protocols, version 2 (format `p4-protocol-1`; research/phase4/INTERFACES.md section 1).

A protocol is a JSON-serialisable description of ONE simulated trajectory of one system:

    {"system": "<system id>",
     "params_seed": int,                                   # draw of the system's physical parameters (per trajectory)
     "params_spread": float,                               # in [0, 3], default 1.0 = the nominal parameter distribution; it
                                                           # multiplies the standard deviations of the parameter draw (OOD tests)
     "weight_noise": {"sd": float, "seed": int} | null,    # multiplicative structural noise, fixed for the whole trajectory
     "process_noise": {"sd": float, "seed": int} | null,   # additive noise on the unit states during integration, only where the
                                                           # system's capability["process_noise"]["supported"] (real: never)
     "r0": {"kind": "rest"}                                # the system's rest state (default)
         | {"kind": "state", "values": {"<unit>": value}}  # explicit initial microstate (units not listed = rest value)
         | {"kind": "restart", "key": "<store key>", "t": t},   # the full microstate of a stored trajectory at its time t
     "t_end": float, "dt": float,                          # duration and output sampling (s)
     "stimulus": [[t, value], ...],                        # piecewise-constant exogenous input u (float, or list when n_u > 1)
     "events": [event, ...],                               # interventions (EVENT_KINDS)
     "obs_noise": {"sd": float, "seed": int} | null}       # additive noise on the returned observed x and y only

Events (times in seconds, snapped to the output grid; `t1: null` = until the end of the trajectory; units are the system's public
unit ids, non-negative integers):

    {"kind": "kick", "t": t, "delta": {"<unit>": d}}                          instantaneous state offset (clipped by the system)
    {"kind": "current", "t0": a, "t1": b | null, "targets": {"<unit>": I}}    additive input current during [a, b)
    {"kind": "current_seq", "t0": a, "seg": s, "targets": {"<unit>": [I_1, ..., I_m]}}
                                                                              piecewise-constant current, I_j on [a+(j-1)s, a+js)
    {"kind": "silence", "t0": a, "t1": b | null, "targets": [units]}          remove all synapses of the targets during the window
    {"kind": "edge_scale", "t0": a, "t1": b | null, "edges": [[post, pre], ...], "factor": f}
                                                                              multiply the listed weights by f in [0, 2]
    {"kind": "param", "t0": a, "t1": b | null, "targets": {"<unit>": {"gain": g, "threshold": d, "tau": c}}}
                                                                              gain x g, time constant x c, threshold + d
    {"kind": "latent_set", "t": t, "z": [..]}      SYNTHETIC TRUTH ONLY (evaluator): set the true causal state
    {"kind": "latent_kick", "t": t, "dz": [..]}    SYNTHETIC TRUTH ONLY (evaluator): shift the true causal state

`validate()` returns the canonical copy: times snapped to the grid (`round(round(t / dt) * dt, 9)`), keys in a fixed order, unit ids as
strings in dicts (sorted numerically), unordered lists sorted and de-duplicated, events sorted by (start time, kind, content). Unknown
keys are errors; `params_spread` (default 1.0) and `process_noise` (default null) are always present in the canonical form, because
they change trajectories. `protocol_hash()` is the content key of a trajectory; `microstate_protocol()` drops the observation noise,
which does not change the simulated microstate (the store keys microstates by it, so noisy repeats never re-simulate).

A trajectory record samples the state BEFORE an instantaneous event at its time t; the jump appears between t and t + dt.

Public functions (stable names): validate(p, allow_truth=False), canonical_json, protocol_hash(p, system_hash, simulator),
microstate_protocol, breakpoints, intervened_units, has_interventions, semantics(event) ('instantaneous' | 'finite' | 'persistent'),
event_start / event_end(event, t_end, dt), seq_boundaries(event, dt), counterfactual(p) (the no-intervention twin, keeping the
breakpoints), from_format1(p) (the earlier format-1 protocol -> this one), snap(t, dt); constants FORMAT, EVENT_KINDS, TRUTH_KINDS, TOP_KEYS.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

FORMAT = "p4-protocol-1"
EVENT_KINDS = ("kick", "current", "current_seq", "silence", "edge_scale", "param")
TRUTH_KINDS = ("latent_set", "latent_kick")
R0_KINDS = ("rest", "state", "restart")
PARAM_FIELDS = ("gain", "threshold", "tau")
TOP_KEYS = ("system", "params_seed", "params_spread", "weight_noise", "process_noise", "r0", "t_end", "dt", "stimulus", "events",
            "obs_noise")
PARAMS_SPREAD_RANGE = (0.0, 3.0)
_EVENT_KEYS = {
    "kick": ("kind", "t", "delta"),
    "current": ("kind", "t0", "t1", "targets"),
    "current_seq": ("kind", "t0", "seg", "targets"),
    "silence": ("kind", "t0", "t1", "targets"),
    "edge_scale": ("kind", "t0", "t1", "edges", "factor"),
    "param": ("kind", "t0", "t1", "targets"),
    "latent_set": ("kind", "t", "z"),
    "latent_kick": ("kind", "t", "dz"),
}
DT_RANGE = (1e-4, 0.05)
T_END_MAX = 20.0
MAX_ABS_STIM = 10.0
MIN_SEG_STEPS = 5
FACTOR_RANGE = (0.0, 2.0)


class ProtocolError(ValueError):
    pass


def snap(t: float, dt: float) -> float:
    """A time on the output grid (the same rounding as protocol format 1)."""
    return round(round(float(t) / dt) * dt, 9)


def _finite(x: Any, what: str) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError) as e:
        raise ProtocolError(f"{what} must be a number, got {x!r}") from e
    if not math.isfinite(v):
        raise ProtocolError(f"{what} must be finite, got {v}")
    return v


def _unit(n: Any, what: str) -> int:
    try:
        f = float(n)
    except (TypeError, ValueError) as e:
        raise ProtocolError(f"{what}: unit id {n!r} is not an integer") from e
    if not math.isfinite(f) or f != int(f) or int(f) < 0:
        raise ProtocolError(f"{what}: unit id {n!r} must be a non-negative integer")
    return int(f)


def _nonneg_int(x: Any, what: str) -> int:
    v = _finite(x, what)
    if v != int(v) or v < 0:
        raise ProtocolError(f"{what} must be a non-negative integer, got {x!r}")
    return int(v)


def _check_keys(d: dict, allowed: tuple[str, ...], what: str) -> None:
    extra = sorted(set(d) - set(allowed))
    if extra:
        raise ProtocolError(f"{what}: unknown key(s) {extra}; allowed {list(allowed)}")


def _unit_dict(d: Any, what: str, value=None) -> dict[str, Any]:
    if not isinstance(d, dict) or not d:
        raise ProtocolError(f"{what} must be a non-empty dict unit -> value")
    out = {}
    for k, v in d.items():
        u = _unit(k, what)
        if str(u) in out:
            raise ProtocolError(f"{what}: unit {u} given twice")
        out[str(u)] = value(v) if value else _finite(v, f"{what}[{u}]")
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def _noise(d: Any, what: str, sd_max: float) -> dict | None:
    if d is None:
        return None
    if not isinstance(d, dict):
        raise ProtocolError(f"{what} must be null or {{'sd', 'seed'}}")
    _check_keys(d, ("sd", "seed"), what)
    if "sd" not in d or "seed" not in d:
        raise ProtocolError(f"{what} needs 'sd' and 'seed'")
    sd = _finite(d["sd"], f"{what}.sd")
    if not (0.0 <= sd <= sd_max):
        raise ProtocolError(f"{what}.sd must be in [0, {sd_max}]")
    return {"sd": sd, "seed": _nonneg_int(d["seed"], f"{what}.seed")}


def _time(e: dict, key: str, dt: float, t_end: float, what: str, optional: bool = False) -> float | None:
    if key not in e:
        raise ProtocolError(f"{what}: missing {key!r}")
    if e[key] is None:
        if optional:
            return None
        raise ProtocolError(f"{what}: {key!r} may not be null")
    t = snap(_finite(e[key], f"{what}.{key}"), dt)
    if not (0.0 <= t <= t_end + 1e-12):
        raise ProtocolError(f"{what}: {key}={t} outside [0, t_end={t_end}]")
    return t


def _event(e: Any, dt: float, t_end: float, allow_truth: bool, idx: int) -> dict:
    ev = _event_body(e, dt, t_end, allow_truth, idx)
    start = ev.get("t", ev.get("t0"))
    if start is not None and start > t_end - dt + 1e-12:
        # an event starting at the last sample (or later) never acts on the recorded trajectory (early numerics review, minor 4)
        raise ProtocolError(f"events[{idx}]: starts at {start} s, at or after the last step (t_end - dt = {t_end - dt:g} s); it would never act")
    return ev


def _event_body(e: Any, dt: float, t_end: float, allow_truth: bool, idx: int) -> dict:
    what = f"events[{idx}]"
    if not isinstance(e, dict):
        raise ProtocolError(f"{what} must be a dict")
    k = e.get("kind")
    if k in TRUTH_KINDS:
        if not allow_truth:
            raise ProtocolError(f"{what}: {k!r} is a synthetic truth event (evaluator only)")
    elif k not in EVENT_KINDS:
        raise ProtocolError(f"{what}: unknown event kind {k!r}; allowed {list(EVENT_KINDS)}")
    _check_keys(e, _EVENT_KEYS[k], f"{what} ({k})")
    if k == "kick":
        return {"kind": k, "t": _time(e, "t", dt, t_end, what), "delta": _unit_dict(e.get("delta"), f"{what}.delta")}
    if k in ("latent_set", "latent_kick"):
        field = "z" if k == "latent_set" else "dz"
        vec = e.get(field)
        if not isinstance(vec, (list, tuple)) or not vec:
            raise ProtocolError(f"{what}: {field!r} must be a non-empty list")
        return {"kind": k, "t": _time(e, "t", dt, t_end, what), field: [_finite(v, f"{what}.{field}") for v in vec]}
    if k == "current_seq":
        t0 = _time(e, "t0", dt, t_end, what)
        seg = snap(_finite(e.get("seg"), f"{what}.seg"), dt)
        if seg < MIN_SEG_STEPS * dt - 1e-12:
            raise ProtocolError(f"{what}: seg must be >= {MIN_SEG_STEPS} dt ({MIN_SEG_STEPS * dt:g} s)")
        tg = e.get("targets")
        if not isinstance(tg, dict) or not tg:
            raise ProtocolError(f"{what}.targets must be a non-empty dict unit -> list of currents")
        vals = {}
        m = None
        for u, lst in tg.items():
            uu = _unit(u, f"{what}.targets")
            if not isinstance(lst, (list, tuple)) or not lst:
                raise ProtocolError(f"{what}.targets[{uu}] must be a non-empty list")
            if m is None:
                m = len(lst)
            elif len(lst) != m:
                raise ProtocolError(f"{what}: every target needs the same number of segments")
            if str(uu) in vals:
                raise ProtocolError(f"{what}.targets: unit {uu} given twice")
            vals[str(uu)] = [_finite(v, f"{what}.targets[{uu}]") for v in lst]
        end = snap(t0 + m * seg, dt)
        if end > t_end + 1e-9:
            raise ProtocolError(f"{what}: the sequence ends at {end} s, after t_end={t_end}")
        return {"kind": k, "t0": t0, "seg": seg, "targets": dict(sorted(vals.items(), key=lambda kv: int(kv[0])))}
    t0 = _time(e, "t0", dt, t_end, what)
    t1 = _time(e, "t1", dt, t_end, what, optional=True)
    if t1 is not None and t1 <= t0:
        raise ProtocolError(f"{what}: needs t1 > t0 (after snapping to the grid), got t0={t0}, t1={t1}")
    if k == "current":
        return {"kind": k, "t0": t0, "t1": t1, "targets": _unit_dict(e.get("targets"), f"{what}.targets")}
    if k == "silence":
        tg = e.get("targets")
        if not isinstance(tg, (list, tuple)) or not tg:
            raise ProtocolError(f"{what}.targets must be a non-empty list of units")
        return {"kind": k, "t0": t0, "t1": t1, "targets": sorted({_unit(n, f"{what}.targets") for n in tg})}
    if k == "edge_scale":
        ed = e.get("edges")
        if not isinstance(ed, (list, tuple)) or not ed:
            raise ProtocolError(f"{what}.edges must be a non-empty list of [post, pre]")
        pairs = set()
        for x in ed:
            if not isinstance(x, (list, tuple)) or len(x) != 2:
                raise ProtocolError(f"{what}.edges: each edge is [post, pre]")
            pairs.add((_unit(x[0], f"{what}.edges"), _unit(x[1], f"{what}.edges")))
        f = _finite(e.get("factor"), f"{what}.factor")
        if not (FACTOR_RANGE[0] <= f <= FACTOR_RANGE[1]):
            raise ProtocolError(f"{what}.factor must be in {list(FACTOR_RANGE)}")
        return {"kind": k, "t0": t0, "t1": t1, "edges": [list(p) for p in sorted(pairs)], "factor": f}
    # param

    def _pvals(v):
        if not isinstance(v, dict) or not v:
            raise ProtocolError(f"{what}.targets: each target needs a dict with some of {list(PARAM_FIELDS)}")
        _check_keys(v, PARAM_FIELDS, f"{what}.targets[...]")
        out = {}
        for fld in PARAM_FIELDS:
            if fld in v:
                x = _finite(v[fld], f"{what}.{fld}")
                if fld in ("gain", "tau") and x <= 0:
                    raise ProtocolError(f"{what}.{fld} must be > 0 (a multiplicative factor)")
                out[fld] = x
        return out

    return {"kind": k, "t0": t0, "t1": t1, "targets": _unit_dict(e.get("targets"), f"{what}.targets", value=_pvals)}


def _stimulus(stim: Any, dt: float, t_end: float) -> list:
    if stim is None:
        stim = [[0.0, 1.0]]
    if not isinstance(stim, (list, tuple)) or not stim:
        raise ProtocolError("stimulus must be a non-empty list of [t, value]")
    width = None
    rows = {}
    for i, row in enumerate(stim):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ProtocolError(f"stimulus[{i}] must be [t, value]")
        t = snap(_finite(row[0], f"stimulus[{i}].t"), dt)
        if not (0.0 <= t <= t_end + 1e-12):
            raise ProtocolError(f"stimulus[{i}]: time {t} outside [0, t_end]")
        v = row[1]
        if isinstance(v, (list, tuple)):
            if not v:
                raise ProtocolError(f"stimulus[{i}]: empty value list")
            val = [_finite(x, f"stimulus[{i}]") for x in v]
            w = len(val)
        else:
            val = _finite(v, f"stimulus[{i}]")
            w = 0
        if width is None:
            width = w
        elif w != width:
            raise ProtocolError("stimulus values must all be scalars or all lists of the same length")
        if any(abs(x) > MAX_ABS_STIM for x in (val if isinstance(val, list) else [val])):
            raise ProtocolError(f"stimulus values must satisfy |value| <= {MAX_ABS_STIM}")
        rows[t] = val            # a later row at the same time replaces an earlier one
    out = [[t, rows[t]] for t in sorted(rows)]
    if out[0][0] != 0.0:
        out = [[0.0, [0.0] * width if width else 0.0]] + out
    return out


def _r0(r0: Any, dt: float) -> dict:
    if r0 is None:
        return {"kind": "rest"}
    if not isinstance(r0, dict):
        raise ProtocolError("r0 must be a dict")
    k = r0.get("kind")
    if k == "zero":                     # format-1 spelling
        k = "rest"
    if k not in R0_KINDS:
        raise ProtocolError(f"r0.kind must be one of {list(R0_KINDS)}")
    if k == "rest":
        _check_keys(r0, ("kind",), "r0")
        return {"kind": "rest"}
    if k == "state":
        _check_keys(r0, ("kind", "values"), "r0")
        vals = r0.get("values") or {}
        if not isinstance(vals, dict):
            raise ProtocolError("r0.values must be a dict unit -> value")
        return {"kind": "state", "values": {str(_unit(u, "r0.values")): _finite(v, "r0.values") for u, v in
                                            sorted(vals.items(), key=lambda kv: _unit(kv[0], "r0.values"))}}
    _check_keys(r0, ("kind", "key", "t"), "r0")
    key = r0.get("key")
    if not isinstance(key, str) or not (16 <= len(key) <= 128) or any(c not in "0123456789abcdef" for c in key):
        raise ProtocolError("r0.key must be a lowercase hex store key")
    t = _finite(r0.get("t"), "r0.t")
    if t < 0:
        raise ProtocolError("r0.t must be >= 0")
    return {"kind": "restart", "key": key, "t": round(t, 9)}


def validate(p: Any, *, allow_truth: bool = False) -> dict[str, Any]:
    """Check a protocol and return its canonical copy (raises ProtocolError)."""
    if not isinstance(p, dict):
        raise ProtocolError("a protocol is a dict")
    q = copy.deepcopy(p)
    _check_keys(q, TOP_KEYS, "protocol")
    for k in ("system", "params_seed", "t_end", "dt"):
        if k not in q:
            raise ProtocolError(f"missing {k!r}")
    if not isinstance(q["system"], str) or not q["system"]:
        raise ProtocolError("system must be a non-empty string")
    dt = _finite(q["dt"], "dt")
    if not (DT_RANGE[0] <= dt <= DT_RANGE[1]):
        raise ProtocolError(f"dt must be in [{DT_RANGE[0]}, {DT_RANGE[1]}] s")
    t_end = snap(_finite(q["t_end"], "t_end"), dt)
    if not (dt * 10 - 1e-12 <= t_end <= T_END_MAX):
        raise ProtocolError(f"t_end must be in [10 dt, {T_END_MAX} s]")
    evs = q.get("events") or []
    if not isinstance(evs, (list, tuple)):
        raise ProtocolError("events must be a list")
    events = [_event(e, dt, t_end, allow_truth, i) for i, e in enumerate(evs)]
    events.sort(key=lambda ev: (ev.get("t", ev.get("t0")), ev["kind"], json.dumps(ev, sort_keys=True)))
    spread = _finite(q.get("params_spread", 1.0), "params_spread")
    if not (PARAMS_SPREAD_RANGE[0] <= spread <= PARAMS_SPREAD_RANGE[1]):
        raise ProtocolError(f"params_spread must be in {list(PARAMS_SPREAD_RANGE)}")
    out = {"system": q["system"], "params_seed": _nonneg_int(q["params_seed"], "params_seed"), "params_spread": spread,
           "weight_noise": _noise(q.get("weight_noise"), "weight_noise", 1.0),
           "process_noise": _noise(q.get("process_noise"), "process_noise", 10.0), "r0": _r0(q.get("r0"), dt), "t_end": t_end, "dt": dt,
           "stimulus": _stimulus(q.get("stimulus"), dt, t_end), "events": events,
           "obs_noise": _noise(q.get("obs_noise"), "obs_noise", 10.0)}
    return {k: out[k] for k in TOP_KEYS}


def canonical_json(p: dict[str, Any], *, allow_truth: bool = False) -> str:
    return json.dumps(validate(p, allow_truth=allow_truth), sort_keys=True, separators=(",", ":"))


def protocol_hash(p: dict[str, Any], *, system_hash: str = "", simulator: str = "", allow_truth: bool = False) -> str:
    """Content key of a trajectory: the canonical protocol, the system's content hash and the engine / simulator versions (together
    they cover system, simulator version, initial state, parameters, input, intervention, seeds, dt and duration)."""
    blob = json.dumps({"v": FORMAT, "p": json.loads(canonical_json(p, allow_truth=allow_truth)), "system": system_hash, "sim": simulator},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def microstate_protocol(p: dict[str, Any], *, allow_truth: bool = False) -> dict[str, Any]:
    """The canonical protocol without observation noise (the simulated microstate does not depend on it)."""
    q = validate(p, allow_truth=allow_truth)
    q["obs_noise"] = None
    return q


def seq_boundaries(e: dict, dt: float) -> list[float]:
    """Segment boundaries t0, t0 + seg, ..., t0 + m seg of a (canonical) current_seq event."""
    m = len(next(iter(e["targets"].values())))
    return [snap(e["t0"] + j * e["seg"], dt) for j in range(m + 1)]


def event_start(e: dict) -> float:
    return float(e["t"] if "t" in e else e["t0"])


def event_end(e: dict, t_end: float, dt: float) -> float:
    """End of an event's window (instantaneous events: t + dt, i.e. one output step; persistent: t_end)."""
    if e["kind"] in ("kick",) + TRUTH_KINDS:
        return float(e["t"]) + dt
    if e["kind"] == "current_seq":
        return seq_boundaries(e, dt)[-1]
    return float(t_end if e.get("t1") is None else e["t1"])


def semantics(e: dict) -> str:
    """'instantaneous' | 'finite' | 'persistent' (goal5 section 43)."""
    if e["kind"] in ("kick",) + TRUTH_KINDS:
        return "instantaneous"
    if e["kind"] == "current_seq":
        return "finite"
    return "persistent" if e.get("t1") is None else "finite"


def breakpoints(p: dict[str, Any], *, allow_truth: bool = False) -> list[float]:
    """Times at which the right-hand side changes (stimulus steps, event starts / ends, kicks, sequence segment boundaries),
    including 0 and t_end."""
    q = validate(p, allow_truth=allow_truth)
    dt = q["dt"]
    ts = {0.0, q["t_end"]}
    ts.update(t for t, _ in q["stimulus"])
    for e in q["events"]:
        for key in ("t", "t0", "t1"):
            if e.get(key) is not None:
                ts.add(e[key])
        if e["kind"] == "current_seq":
            ts.update(seq_boundaries(e, dt))
    return sorted(t for t in ts if 0.0 <= t <= q["t_end"])


def intervened_units(p: dict[str, Any], *, allow_truth: bool = False) -> set[int]:
    """Every unit an event acts on (kicks, currents, sequences, silencing, both ends of scaled edges, parameter changes)."""
    q = validate(p, allow_truth=allow_truth)
    out: set[int] = set()
    for e in q["events"]:
        k = e["kind"]
        if k == "kick":
            out |= {int(n) for n in e["delta"]}
        elif k in ("current", "current_seq", "param") or k == "silence":
            out |= {int(n) for n in e["targets"]}
        elif k == "edge_scale":
            out |= {int(x) for ed in e["edges"] for x in ed}
    return out


def has_interventions(p: dict[str, Any], *, allow_truth: bool = False) -> bool:
    """True when the protocol carries at least one intervention event (an 'experiment' in the budget accounting)."""
    return bool(validate(p, allow_truth=allow_truth)["events"])


def counterfactual(p: dict[str, Any], *, allow_truth: bool = False) -> dict[str, Any]:
    """The same trajectory without its events (the no-intervention twin): same parameters, noise, initial state and input. The twin
    keeps the intervened run's BREAKPOINTS as no-op stimulus steps (the value in force at each event time), so its piecewise
    integration is identical to the intervened run's up to the first event."""
    q = validate(p, allow_truth=allow_truth)
    times = set(breakpoints(q, allow_truth=allow_truth)) - {0.0, q["t_end"]}
    stim = [list(r) for r in q["stimulus"]]
    have = {t for t, _ in stim}
    for t in sorted(times):
        if t not in have:
            in_force = [s for ts, s in stim if ts <= t + 1e-9]
            stim.append([t, copy.deepcopy(in_force[-1])])
    q["stimulus"] = sorted(stim, key=lambda r: r[0])
    q["events"] = []
    return validate(q)


def from_format1(p: dict[str, Any]) -> dict[str, Any]:
    """Translate an earlier format-1 protocol (p3-protocol-1) into format 2 (edge_remove -> edge_scale with factor 0; r0 'zero' ->
    'rest'). Used for compatibility tests with the earlier frozen engine."""
    q = copy.deepcopy(p)
    evs = []
    for e in q.get("events") or []:
        if e.get("kind") == "edge_remove":
            evs.append({"kind": "edge_scale", "t0": e["t0"], "t1": e.get("t1"), "edges": e["edges"], "factor": 0.0})
        else:
            evs.append(e)
    q["events"] = evs
    if (q.get("r0") or {}).get("kind") == "zero":
        q["r0"] = {"kind": "rest"}
    return validate({k: v for k, v in q.items() if k in TOP_KEYS})
