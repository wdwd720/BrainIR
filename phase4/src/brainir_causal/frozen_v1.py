"""Frozen baseline: BrainIR State v1 (the locked earlier state-discovery method, observational / predictive training) run
UNCHANGED through the causal-state API (goal5 section 20).

The earlier method is imported from its own package (`brainir_state`) and never modified or tuned: its default configuration is
used, only the evaluator keys `k`, `sharing` and `adapt_from` are passed through, it gets no simulator and no designer (it has
none). `verify_sources()` checks the imported source files against the LF sha256 hashes recorded when that method was locked (the
tournament driver calls it before any fit; a mismatch refuses to run).

Data and events are translated, never re-interpreted:
- records -> the earlier `Trajectory` objects (same arrays, key, system id, split and family label);
- events: kick -> kick; current (finite or persistent) -> current; current_seq -> one current event per non-zero segment;
  silence -> silence; edge_scale with factor 0 -> edge_remove. edge_scale with another factor and param have no counterpart in
  the earlier protocol: training records that contain them are left out of the earlier method's training data (it could not use
  them), and predictions for them are ABSTAINED on (never a silent "no effect");
- supports(kind) is the earlier model's own per-kind support (edge_scale -> its edge_remove support; param -> False);
- lift: the earlier method has no native lift, so it returns [] (it fails every native-lift case).
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
from pathlib import Path

import numpy as np

from .api import CausalStateMethod, CausalStateModel, register

#: LF sha256 of the earlier method's source files as locked (its method lock and its benchmark lock)
V1_SOURCES = {
    "brainir_state/__init__.py": "8908e218744633289b1d0baff5effefb22291facce29b822f779edbbad32f2ff",
    "brainir_state/api.py": "cb68f9fedd1ab50deb13a669d2d0b744848b96d67f40847611885d1f0108a815",
    "brainir_state/data.py": "bf10de9d7de763f51e9de570f6b561c2b7915b812ab760df1d41ba16279453d0",
    "brainir_state/evaluate.py": "c41ae275ba7745e69a792a97f0fbcc9217c8a8febbcc4ea9e230670712aa99b6",
    "brainir_state/methods/__init__.py": "be4feb6c4a55f414a8c3e6d7ca4f6cc477fb5dd6ad8d95bd200d393e1544e258",
    "brainir_state/methods/brainir_state_v1.py": "d99368194959936a63f72d8d79a262abcec0d0d59ab6af87ad202d8dc5ba18c6",
    "brainir_state/methods/ks_core.py": "9c93e4a37795a384b3f7b09ffecb77c025413935a9cfee19ba9259902e4f55c2",
    "brainir_state/methods/ks_sindy.py": "c8d058d3a5b1ba56371014d0b9c580e57e986e8358874ed7173ae71c09c02fe9",
    "brainir_state/methods/ks_abstain.py": "cee29d05f23bacb1b195af22f99987bf05b29451dffb9776fa16c92bfb6db0a7",
    "brainir_state/methods/ks_share.py": "5cd0871c43981c784ca52644ccdba373a68e26369569ce5a07c336c0cc365934",
}
V1_METHOD = "brainir_state_v1"
MAPPABLE = ("kick", "current", "current_seq", "silence", "edge_scale")


def _pkg_root() -> Path:
    spec = importlib.util.find_spec("brainir_state")
    if spec is None or not spec.origin:
        raise ImportError("the earlier method's package brainir_state is not importable")
    return Path(spec.origin).resolve().parent.parent


def verify_sources() -> dict:
    """{relative path: 'ok' | 'MISMATCH' | 'missing'}; raises RuntimeError on any difference."""
    root = _pkg_root()
    out = {}
    for rel, want in V1_SOURCES.items():
        p = root / rel
        if not p.exists():
            out[rel] = "missing"
            continue
        got = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        out[rel] = "ok" if got == want else "MISMATCH"
    bad = {k: v for k, v in out.items() if v != "ok"}
    if bad:
        raise RuntimeError(f"the earlier method's sources differ from their lock: {bad}")
    return out


def map_event(e: dict, dt: float) -> list[dict] | None:
    """One event of the causal-state protocol -> events of the earlier protocol, or None if it has no counterpart."""
    k = e["kind"]
    if k == "kick":
        return [{"kind": "kick", "t": float(e["t"]), "delta": dict(e["delta"])}]
    if k == "current":
        return [{"kind": "current", "t0": float(e["t0"]), "t1": None if e.get("t1") is None else float(e["t1"]),
                 "targets": dict(e["targets"])}]
    if k == "current_seq":
        out = []
        t0, seg = float(e["t0"]), float(e["seg"])
        for unit, vals in e["targets"].items():
            for j, v in enumerate(vals):
                if float(v) != 0.0:
                    out.append({"kind": "current", "t0": t0 + j * seg, "t1": t0 + (j + 1) * seg, "targets": {str(unit): float(v)}})
        return out
    if k == "silence":
        return [{"kind": "silence", "t0": float(e["t0"]), "t1": None if e.get("t1") is None else float(e["t1"]),
                 "targets": list(e["targets"])}]
    if k == "edge_scale" and float(e.get("factor", 1.0)) == 0.0:
        return [{"kind": "edge_remove", "t0": float(e["t0"]), "t1": None if e.get("t1") is None else float(e["t1"]),
                 "edges": [list(x) for x in e["edges"]]}]
    return None


def map_events(events: list[dict], dt: float) -> list[dict] | None:
    out = []
    for e in events or []:
        m = map_event(e, dt)
        if m is None:
            return None
        out += m
    return out


class FrozenV1Model(CausalStateModel):
    """The earlier model behind the causal-state API."""

    def __init__(self, inner, dropped: dict):
        self.inner = inner
        self.k = dict(getattr(inner, "k", {}) or {})
        self._dropped = dict(dropped)

    def encode(self, system_id, x_hist, u_hist, dt):
        return np.asarray(self.inner.encode(system_id, x_hist, u_hist, dt), float)

    def rollout(self, system_id, z0, u_future, events, dt):
        ev = map_events(events, dt)
        if ev is None:
            raise ValueError("event kind without a counterpart in the earlier method (abstained via intervention_effect)")
        r = self.inner.rollout(system_id, z0, u_future, ev, dt)
        return {"z": np.asarray(r["z"], float), "y": np.asarray(r["y"], float)}

    def readout(self, system_id, z, u):
        return np.asarray(self.inner.readout(system_id, z, u), float)

    def supports(self, system_id, event_kind):
        if event_kind == "current_seq":
            return bool(self.inner.supports(system_id, "current"))
        if event_kind == "edge_scale":
            return bool(self.inner.supports(system_id, "edge_remove"))
        if event_kind in ("kick", "current", "silence"):
            return bool(self.inner.supports(system_id, event_kind))
        return False

    def intervention_effect(self, system_id, x_hist, u_hist, u_future, events, dt):
        z0 = self.encode(system_id, x_hist, u_hist, dt)
        r0 = self.rollout(system_id, z0, u_future, [], dt)
        ev = map_events(events, dt)
        abstain = ev is None or not all(self.supports(system_id, e["kind"]) for e in events)
        if ev is None:
            r1 = r0
        else:
            r1 = self.inner.rollout(system_id, z0, u_future, ev, dt)
            r1 = {"z": np.asarray(r1["z"], float), "y": np.asarray(r1["y"], float)}
        out = {"y_int": r1["y"], "y_base": r0["y"], "z_int": r1["z"], "z_base": r0["z"], "abstain": bool(abstain),
               "validity": self.validity(system_id, x_hist, u_hist, events)}
        out["effect"] = out["y_int"] - out["y_base"]
        return out

    def lift(self, system_id, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        return []

    def info(self):
        inf = dict(self.inner.info() or {})
        inf["method"] = "frozen_brainir_state_v1"
        inf["method_version"] = "1 (frozen)"
        inf["frozen_baseline"] = {"dropped_training_records": self._dropped,
                                  "untranslatable_kinds": ["param", "edge_scale with factor != 0"], "native_lift": False}
        return inf


@register
class FrozenV1Baseline(CausalStateMethod):
    """The earlier locked method as a frozen baseline (never tuned)."""
    name = "frozen_brainir_state_v1"
    version = "1-frozen"
    default_config: dict = {}
    supported_sharing = ("auto", "independent", "shared")
    supports_adaptation = True

    def fit(self, data, *, systems, config=None, seed=0):
        v1 = importlib.import_module("brainir_state.methods.brainir_state_v1")
        pdata = importlib.import_module("brainir_state.data")
        cfg = {k: v for k, v in (config or {}).items() if k in ("k", "sharing", "adapt_from")}
        if cfg.get("adapt_from") is not None:
            cfg["adapt_from"] = cfg["adapt_from"].inner
        train, dropped = [], {}
        for tr in data:
            ev = map_events(tr.events(), tr.dt)
            if ev is None:
                dropped[tr.system_id] = dropped.get(tr.system_id, 0) + 1
                continue
            proto = {**tr.protocol, "events": ev}
            train.append(pdata.Trajectory(key=tr.key, system_id=tr.system_id, split=tr.split, family=tr.family, protocol=proto,
                                          t=tr.t, x=tr.x, u=tr.u, y=tr.y, info=dict(tr.info or {})))
        sysdefs = {sid: {**rec, "observed": list(rec["observed"]), "input_dim": int(rec["input_dim"])} for sid, rec in systems.items()}
        method = v1.BrainIRStateV1()
        inner = method.fit(train, systems=sysdefs, config=cfg, sim=None, seed=seed)
        return FrozenV1Model(inner, dropped)
