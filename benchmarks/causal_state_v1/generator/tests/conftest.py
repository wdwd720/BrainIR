"""Shared fixtures: dev suites of several suite seeds (the benchmark's development tier is build_suite("dev", 20260926)) and one
representative system per type. P4_TEST_SEEDS (comma-separated) overrides the seeds."""

import os
import sys

import numpy as np
import pytest

ROOM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOM, "src"), ROOM):
    if p not in sys.path:
        sys.path.insert(0, p)

_CACHE = os.path.join(ROOM, "scratch", ".p4cache")      # control margins are deterministic: cached across test processes
if os.access(os.path.dirname(_CACHE), os.W_OK):
    os.environ.setdefault("P4SYNTH_CACHE_DIR", _CACHE)

from p4synth import build_suite  # noqa: E402
from p4synth.engine import CORE  # noqa: E402

TYPES = list(range(1, 26))
SEEDS = [int(a) for a in os.environ.get("P4_TEST_SEEDS", "20260926,0,7").split(",")]
_SUITES: dict = {}


def get_suite(seed: int):
    if seed not in _SUITES:
        _SUITES[seed] = build_suite("dev", seed)
    return _SUITES[seed]


@pytest.fixture(scope="session", params=SEEDS, ids=lambda s: f"seed{s}")
def suite(request):
    return get_suite(request.param)


@pytest.fixture(scope="session")
def by_type(suite):
    out = {}
    for sid, s in suite.items():
        out.setdefault(s.info["type"], []).append(s)
    return out


def one_per_type(suite):
    seen = {}
    for sid, s in suite.items():
        seen.setdefault(s.info["type"], s)
    return [seen[t] for t in sorted(seen)]


def mid_state(s, frac=0.5, **kw):
    """A typical microstate: the nominal trajectory at frac * t_end (nominal draw)."""
    o = s.simulate(s.base_protocol(**kw), full=True)
    return o["state"][int(round(frac * s.t_end_default / s.dt))]


def const_input(s, level=1.0):
    return [[0.0, [level] * s.input_dim if s.input_dim > 1 else level]]


def probe_protocols(s, t0=0.02, horizon=0.3, rng=None):
    """Intervention sequences (one per event kind the system supports) on its targetable core units, from a restart at t = 0."""
    rng = rng or np.random.default_rng(0)
    cap = s.capability()
    tg = s.core_targets()
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    u = int(tg[0])
    v = int(tg[len(tg) // 2])
    evs = [[],
           [{"kind": "kick", "t": t0, "delta": {str(u): 2 * mk}}],
           [{"kind": "kick", "t": t0, "delta": {str(u): -2 * mk, str(v): mk}}],
           [{"kind": "current", "t0": t0, "t1": t0 + 0.05, "targets": {str(v): 2 * mc}}],
           [{"kind": "current_seq", "t0": t0, "seg": 0.01, "targets": {str(u): [mc, 0, mc, 0, -mc]}}],
           [{"kind": "silence", "t0": t0, "t1": t0 + 0.1, "targets": [u]}],
           [{"kind": "silence", "t0": t0, "t1": None, "targets": [int(x) for x in tg[:3]]}],
           [{"kind": "current", "t0": t0, "t1": None, "targets": {str(v): -mc}}],
           [{"kind": "param", "t0": t0, "t1": t0 + 0.1, "targets": {str(v): {"gain": 1.5, "threshold": 1.0, "tau": 1.5}}}]]
    ce = [e for e in s.edges if s.spec.role[e[0]] == CORE and s.spec.role[e[1]] == CORE]
    if ce:
        evs.append([{"kind": "edge_scale", "t0": t0, "t1": t0 + 0.1, "edges": [ce[0]], "factor": 0.0}])
    base = s.base_protocol(t_end=horizon, stimulus=const_input(s))
    return [dict(base, events=e) for e in evs]


def f_s(s):
    """The benchmark's effect floor: 0.05 x the sd of y on a nominal trajectory."""
    y = s.simulate(s.base_protocol())["y"]
    return 0.05 * float(np.sqrt(np.mean(np.var(y, axis=0)))) + 1e-12
