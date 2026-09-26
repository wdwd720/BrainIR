"""Benchmark datasets of `causal_state_v1` (ORCHESTRATOR SIDE; benchmarks/causal_state_v1/PROTOCOL.md sections 2-4).

What this module fixes (frozen with the benchmark):

SEEDS. The dev tier uses the PUBLIC seed `DEV_SEED`; the `val` and `conf` synthetic tiers and every hidden protocol seed derive from
the SECRET salt (`data/phase4/hidden/salt.txt`, git-ignored), committed by sha256 in `benchmarks/causal_state_v1/hidden/
salt_commitment.json` before any method existed. Development-policy protocols (dev tier, public real data, the real Level B
validation sets, D0 / D1 / validation data of every tier) draw parameter and noise seeds in [0, 10^9); held-out sets of the `val`
and `conf` tiers and the real hidden sets draw in [10^9, 2 x 10^9) (`hidden_seed`), which the simulation service refuses. The
confirmation tier and the real hidden sets are generated only after the method lock (`require_lock`).

ROTATIONS (synthetic; PROTOCOL section 3). `assign_rotations` walks through the types in a seeded order (and each type's systems in a
seeded order) along ONE seeded cycle of R1-R4, so the four rotations are used equally often over the suite (up to one) and the
systems of a type (at most four) get distinct rotations. A rotation whose trained families the system cannot produce is skipped for
the next producible one of the cycle not yet used by its type; if none fits, the rotation with the most producible trained families
is used with its trained set reduced to them (`reduced: true` in the split record).

TARGETS. Synthetic: a seeded half (rounded up, at least one) of the targetable units is public, the rest hidden; the same for the
scalable edges. Real: the partition of `brainir_causal.systems`. Public records never list hidden targets / edges.

MAGNITUDES (PROTOCOL section 3). Classes below / weak / moderate / strong = 0.1 / 0.3 / 1 / 3 x the capability's moderate magnitude
m_s of the kind, each jittered by a factor U(0.8, 1.25) (the classes stay disjoint); the development maximum is the strong class
(`capability[kind]["max"]`); `*.hi` families draw from `hi_range`. Edge scalings: weakening depth 1 - factor with m_s =
capability["edge_scale"]["moderate"] (depth capped at 0.95 for `edge.w`; `edge.rm` = factor 0). Parameter changes: |gain - 1|,
|tau - 1| and |threshold| with the per-field moderate values. Silencing has no magnitude (class "na").

TIMING. Horizons are 2.5 / 12.5 (PRIMARY) / 50 % of the default duration T. Intervention onsets lie in [0.15 T, 0.5 T] (so the long
horizon remains); pulses last U(max(5 dt, 0.1 D_p), D_p); sustained currents U(D_s, 2.5 D_s) or persist (probability 0.3); temporary
windows (silencing, edge and parameter changes) U(D_p, min(3 D_s, 0.4 T)), persistent with probability 0.3 (never `sil.1`, always
`sil.1p`). Patterns (`seq.*`) are `current_seq` events on one target starting at the onset.

SETS PER SYSTEM (PROTOCOL section 4):
- D0 passive (split 'train'): 8 nominal trajectories over parameter draws 0-7, 16 stimulus schedules, 8 initial-condition changes,
  8 weight-noise draws;
- D1 reference interventions (split 'train'): B_main = 200 (real full networks 120) intervention trajectories drawn uniformly over
  families_train x public targets x magnitude classes x onsets, each with its counterfactual twin (split 'twin', meta twin_of);
- public validation (split 'val' + twins): 20 % more of D0 and D1;
- tests (split 'test', each intervention item with its twin): per family 2 IDENTITY CELLS (a target set and a magnitude class) x 4
  STATES (new parameter draw, stimulus level and onset) = 8 items: in-family (families_train, public targets), target shift
  (families_train, hidden targets), family shift (families_heldout, public targets; role near / far), hidden-only (public targets);
  composition items also simulate each component alone (split 'component', meta component_of); Level C adds OOD (section 4.1) and
  robustness (section 4.2); 16 passive test trajectories;
- pools (P4-D14): 8 parameter draws x 15 source trajectories (split 'pool_src') x 5 sample times = 600 states, each a time point of
  a stored held-out trajectory (its history is that trajectory's past); futures (25 % of T) simulated from restarts of the stored
  microstate under the nominal input level (shared by every state), with no intervention and under one fixed sequence per supported
  event kind; stored as readouts, plus the observed microstate over the primary horizon for the no-intervention future only; 20
  states repeat the no-intervention future with a no-op breakpoint (numerical floor); synthetic systems add truth-equivalent states
  (the generator's `equivalent_states`, 2 for each of 20 pool states; excluded from model pairing, reference only);
- lift cases: 16 states of the passive test trajectories (histories, restart keys).

OOD and ROBUSTNESS (Level C). 'parameter spread' = `params_spread` 1.5; 'parameter noise' = `params_spread` 1.5 and 2.0 (hidden-range
draws); 'process noise' only where capability['process_noise']['supported']. While the protocol format lacks these fields the
builder falls back to documented PROXIES (weight noise at 1.5x the development maximum) and marks the items meta['proxy'] = true.
Robustness items whose simulated events differ from what the model is told (amplitude / timing jitter) keep the told events in
meta['model_events']; `TestItem.events` get the told events and `true_events` the simulated ones. Items with observation noise keep
the noise-free readout in the truth store (`y_clean`), and `TestItem` futures use it (the model's history stays noisy).

Datasets are written INCREMENTALLY (chunks of simulated jobs; per system sub-directories in the p4-dataset-1 layout of
`brainir_causal.data`), so real full networks never hold a whole set in memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import families as F
from . import protocol as P

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "causal_state_v1"
DATA = ROOT / "data" / "phase4"
SALT_FILE = DATA / "hidden" / "salt.txt"
COMMITMENT = BENCH / "hidden" / "salt_commitment.json"
METHOD_LOCK = ROOT / "research" / "phase4" / "METHOD_LOCK.json"
SUITES = DATA / "suites"
REAL_SETS = DATA / "real"
STORE = DATA / "store"

DEV_SEED = 20260926
HIDDEN_SEED_BASE = 10**9
TIERS = ("dev", "val", "conf")
HIDDEN_TIERS = ("val", "conf", "real_hidden")
N_PER_TYPE = {"dev": 2, "val": 2, "conf": 3}
LEVEL_OF_TIER = {"dev": "B", "val": "B", "conf": "C", "toy": "B", "toyC": "C"}

MAG_MULT = {"below": 0.1, "weak": 0.3, "moderate": 1.0, "strong": 3.0}
MAG_CLASSES = tuple(MAG_MULT)
JITTER = (0.8, 1.25)
ONSET_FRAC = (0.15, 0.5)
HORIZON_FRACTIONS = {"short": 0.025, "medium": 0.125, "long": 0.5}
POOL_FUTURE_FRAC = 0.25
EDGE_DEPTH_MAX = 0.95
P_PERSIST = 0.3

D0_DESIGN = {"obs.nominal": 8, "obs.stim": 16, "obs.init": 8, "obs.wnoise": 8}
B_MAIN = {"synthetic": 200, "full": 120, "mech": 200}
VAL_FRACTION = 0.2
CELLS_PER_FAMILY, STATES_PER_CELL = 2, 4
N_PASSIVE_TEST = 16
PASSIVE_ONSETS = (0.2, 0.3, 0.4, 0.5)
POOL_DRAWS, POOL_TRAJ, POOL_STATES = 8, 15, 5
POOL_SOURCES = ("pool_state", "stim", "init", "intervention", "intervention")
POOL_FLOOR_STATES = 20
N_LIFT_CASES = 16
N_TRUTH_SAMPLES = 12
ITEMS_PER_CATEGORY = 8
PARAMS_SPREAD_OOD = 1.5
PARAMS_NOISE_LEVELS = (1.5, 2.0)
PROCESS_NOISE_LEVELS = (0.05, 0.1)
CHUNK = 192
SEQ_KINDS = (("kick", "kick.1"), ("current", "pulse.1"), ("current_seq", "seq.train"), ("silence", "sil.1"), ("edge_scale", "edge.w"),
             ("param", "param.1"))


def protocol_has(field_name: str) -> bool:
    """Whether the protocol format knows an optional top-level field (params_spread / process_noise)."""
    return field_name in P.TOP_KEYS


# ================================================================================================================ seeds / salt / lock
def read_salt() -> str:
    """The secret salt, verified against its commitment (raises when missing or not matching)."""
    salt = SALT_FILE.read_text(encoding="utf-8").strip()
    commit = json.loads(COMMITMENT.read_text(encoding="utf-8"))["sha256_of_salt"]
    if hashlib.sha256(salt.encode()).hexdigest() != commit:
        raise RuntimeError("the salt does not match its commitment")
    return salt


def tier_seed(tier: str) -> int:
    if tier in ("dev", "toy", "toyC"):
        return DEV_SEED
    if tier not in TIERS:
        raise ValueError(f"unknown synthetic tier {tier!r}")
    return int(hashlib.sha256(f"{read_salt()}|synthetic|{tier}".encode()).hexdigest()[:8], 16)


def hidden_seed(*parts, salt: str | None = None) -> int:
    """A parameter / noise seed in the hidden range [10^9, 2 x 10^9), derived from the salt and the parts."""
    s = read_salt() if salt is None else salt
    h = hashlib.sha256((s + "|" + "|".join(str(p) for p in parts)).encode()).hexdigest()
    return HIDDEN_SEED_BASE + int(h[:12], 16) % HIDDEN_SEED_BASE


def public_seed_of(*parts) -> int:
    """A deterministic PUBLIC-range seed from the parts (no salt)."""
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12], 16) % HIDDEN_SEED_BASE


def rng_of(*parts) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16))


def seed_counter(hidden: bool, *parts):
    """A counter-based seed function: public-range seeds, or hidden-range seeds derived from the salt."""
    counter = [0]
    salt = read_salt() if hidden else None

    def fn() -> int:
        counter[0] += 1
        return hidden_seed(*parts, counter[0], salt=salt) if hidden else public_seed_of(*parts, counter[0])
    return fn


def locked() -> bool:
    return METHOD_LOCK.exists()


def require_lock(what: str) -> None:
    if not locked():
        raise PermissionError(f"{what} is generated only after the method lock (research/phase4/METHOD_LOCK.json is missing)")


# ================================================================================================================ capability
def normalize_capability(cap: dict | None, *, t_end: float, dt: float, input_dim: int = 1) -> dict:
    """The capability record with every threshold the family rules and the samplers need; an explicit value always wins."""
    c = json.loads(json.dumps(cap or {}))
    for kind in ("kick", "current", "current_seq"):
        k = c.setdefault(kind, {})
        k.setdefault("supported", kind != "current_seq" or bool(c.get("current", {}).get("supported")))
        if "moderate" not in k and "max" in k:
            k["moderate"] = float(k["max"]) / 3.0
        k.setdefault("moderate", 1.0)
        k.setdefault("max", 3.0 * float(k["moderate"]))
        k.setdefault("hi_range", [1.5 * float(k["max"]), 3.0 * float(k["max"])])
    cur = c["current"]
    cur.setdefault("pulse_max_duration", round(0.075 * t_end, 9))
    cur.setdefault("sustained_min_duration", max(float(cur["pulse_max_duration"]), round(0.15 * t_end, 9)))
    c["current_seq"].setdefault("min_seg_steps", P.MIN_SEG_STEPS)
    c.setdefault("silence", {}).setdefault("supported", False)
    e = c.setdefault("edge_scale", {})
    e.setdefault("supported", False)
    e.setdefault("moderate", 0.3)
    e.setdefault("max", min(EDGE_DEPTH_MAX, 3.0 * float(e["moderate"])))     # weakening DEPTH (1 - factor), development maximum
    e.setdefault("factor_range", [0.0, 2.0])
    pm = c.setdefault("param", {})
    pm.setdefault("supported", False)
    pm.setdefault("fields", ["gain", "threshold", "tau"])
    mod = pm.setdefault("moderate", {})
    for fld, v in (("gain", 0.3), ("threshold", 1.0), ("tau", 0.3)):
        mod.setdefault(fld, v)
    init = c.setdefault("init", {})
    init.setdefault("state", True)
    init.setdefault("restart", True)
    init.setdefault("units", "observed")
    st = c.setdefault("stimulus", {})
    st.setdefault("channels", int(input_dim))
    st.setdefault("nominal_level", 1.0)
    st.setdefault("max_onset", round(0.075 * t_end, 9))
    st.setdefault("range", [0.55, 1.45])
    st.setdefault("allow_zero", True)
    pr = c.setdefault("params", {})
    pr.setdefault("public_seed_max", HIDDEN_SEED_BASE)
    pr.setdefault("nominal_seed", None)
    c.setdefault("weight_noise", {}).setdefault("max_sd", 0.1)
    c.setdefault("obs_noise", {}).setdefault("max_sd", 0.5)
    tm = c.setdefault("timing", {})
    tm.setdefault("dt_allowed", [float(dt)])
    tm.setdefault("t_end_max", 2.0 * float(t_end))
    c.setdefault("latent", {}).setdefault("supported", False)
    c.setdefault("process_noise", {}).setdefault("supported", False)
    return c


def moderate_value(cap: dict, kind: str, fld: str | None = None) -> float:
    if kind == "param":
        return float(cap["param"]["moderate"][fld])
    return float(cap[kind]["moderate"])


def class_value(cap: dict, kind: str, mclass: str, rng: np.random.Generator, fld: str | None = None) -> float:
    """A positive magnitude of class `mclass` for this kind (and parameter field). The strong class is jittered DOWNWARD only
    (U(0.8, 1.0)), so it never exceeds the development maximum 3 m_s (which would make it a `*.hi` family)."""
    if mclass == "hi":
        lo, hi = cap[kind]["hi_range"]
        return float(rng.uniform(lo, hi))
    jit = rng.uniform(JITTER[0], 1.0) if mclass == "strong" else rng.uniform(*JITTER)
    v = float(MAG_MULT[mclass] * moderate_value(cap, kind, fld) * jit)
    mx = cap.get(kind, {}).get("max") if kind != "param" else None
    return min(v, float(mx)) if mx is not None else v


# ================================================================================================================ rotations / targets
def assign_rotations(systems: dict[str, dict], seed: int) -> dict[str, dict]:
    """{system_id: {"rotation", "reduced", "families_train"}} for systems {sid: {"type": label, "capability": cap}}: within a type the
    systems get distinct rotations of a seeded permutation of R1-R4 whose starting point cycles across types (balanced counts)."""
    rots = sorted(F.ROTATIONS)
    cycle = [rots[i] for i in rng_of("rotations", seed).permutation(len(rots))]
    by_type: dict[str, list[str]] = {}
    for sid in sorted(systems):
        by_type.setdefault(str(systems[sid]["type"]), []).append(sid)
    types = sorted(by_type)
    types = [types[i] for i in rng_of("rotation-types", seed).permutation(len(types))]
    out: dict[str, dict] = {}
    pos = 0
    for typ in types:
        sids = [by_type[typ][i] for i in rng_of("rotation-order", seed, typ).permutation(len(by_type[typ]))]
        used: set[str] = set()
        for sid in sids:
            sup = set(F.supported_families(systems[sid]["capability"]))
            order = [cycle[(pos + m) % len(cycle)] for m in range(len(cycle))]
            pos += 1
            fits = [r for r in order if set(F.ROTATIONS[r]) <= sup]
            pick = next((r for r in fits if r not in used), fits[0] if fits else None)
            if pick is not None:
                out[sid] = {"rotation": pick, "reduced": False, "families_train": list(F.ROTATIONS[pick])}
            else:
                best = max(order, key=lambda r: (len(set(F.ROTATIONS[r]) & sup), -order.index(r)))
                pick = best
                out[sid] = {"rotation": best, "reduced": True, "families_train": [f for f in F.ROTATIONS[best] if f in sup]}
            used.add(pick)
    return out


def rotation_split_record(rot: dict, capability: dict) -> dict:
    """The split record of a synthetic system from its rotation assignment (reduced rotations keep the rotation's name)."""
    rec = F.split_record(list(F.OBS) + list(rot["families_train"]), F.supported_families(capability), rotation=rot["rotation"])
    rec["reduced"] = bool(rot.get("reduced"))
    return rec


def partition(items: list, *key, frac: float = 0.5) -> tuple[list, list]:
    """(public, hidden): a seeded half (rounded up; at least one public) of the sorted items."""
    its = sorted(items, key=lambda v: json.dumps(v))
    if not its:
        return [], []
    perm = [its[i] for i in rng_of("partition", *key).permutation(len(its))]
    n_pub = max(1, math.ceil(frac * len(its)))
    return sorted(perm[:n_pub], key=lambda v: json.dumps(v)), sorted(perm[n_pub:], key=lambda v: json.dumps(v))


# ================================================================================================================ system records
def horizons_s(t_end: float) -> dict:
    return {k: round(v * float(t_end), 9) for k, v in HORIZON_FRACTIONS.items()}


def synthetic_records(pub: dict, *, tier: str, seed: int, rotation: dict, system_hash: str, engine_id: str) -> tuple[dict, dict]:
    """(public record, internal record) of a synthetic system from the generator's public record (which lists every targetable
    unit and scalable edge): targets / edges partitioned, capability normalised, split added. The public record never lists the
    hidden targets or edges (nor the full targetable set)."""
    sid = pub["system_id"]
    t_end, dt = float(pub["t_end_default"]), float(pub["dt"])
    cap = normalize_capability(pub.get("capability"), t_end=t_end, dt=dt, input_dim=int(pub.get("input_dim", 1)))
    targetable = sorted(int(u) for u in (pub.get("targetable") or pub.get("observed") or []))
    edges = sorted([int(a), int(b)] for a, b in (pub.get("edges") or []))
    t_pub, t_hid = partition(targetable, "targets", tier, seed, sid)
    e_pub, e_hid = partition(edges, "edges", tier, seed, sid)
    split = rotation_split_record(rotation, cap)
    base = {k: v for k, v in pub.items() if k not in ("targetable", "edges", "capability", "split")}
    public = {**base, "system_id": sid, "kind": "synthetic", "dt": dt, "t_end_default": t_end, "horizons_s": horizons_s(t_end),
              "targets_public": t_pub, "edges_public": e_pub, "capability": cap, "split": split,
              "cost_units": int(pub.get("cost_units", 1)), "public_graph": pub.get("public_graph")}
    internal = {**public, "targets_heldout": t_hid, "edges_heldout": e_hid, "targetable": targetable, "edges": edges,
                "system_hash": system_hash, "engine": engine_id, "tier": tier}
    return public, internal


# ================================================================================================================ protocol sampler
def _shift_events(events: list[dict], shift: float) -> list[dict]:
    out = []
    for e in events:
        e2 = json.loads(json.dumps(e))
        for key in ("t", "t0", "t1"):
            if e2.get(key) is not None:
                e2[key] = round(float(e2[key]) + shift, 9)
        out.append(e2)
    return out


def relative_events(events: list[dict], onset: float) -> list[dict]:
    """Events with times relative to the onset (time 0 = the onset sample)."""
    return _shift_events(events, -float(onset))


@dataclass
class Spec:
    """One planned trajectory: its protocol and its role in the benchmark."""
    protocol: dict
    split: str                              # train | val | twin | test | pool_src | component
    role: str = ""                          # d0 | d1 | in | target | near | far | hidden | ood:<cat> | robust:<cond> | passive | pool_src
    family: str = ""                        # the planned family (the stored label is always families.family_of)
    mclass: str = "na"
    target_set: tuple = ()
    cell: str = ""                          # identity cell of test items
    state: int = 0
    twin: bool = False                      # simulate the counterfactual twin too
    meta: dict = field(default_factory=dict)


def _runs(on: list[bool]) -> tuple[list[int], list[int], list[int]]:
    starts, lengths = [], []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            starts.append(i)
            lengths.append(j - i)
            i = j
        else:
            i += 1
    gaps = [starts[k + 1] - (starts[k] + lengths[k]) for k in range(len(starts) - 1)]
    return starts, lengths, gaps


class FamilySampler:
    """Protocols of every vocabulary family for one system (capability-aware; deterministic given the rng)."""

    def __init__(self, sysrec: dict, rng: np.random.Generator, seed_fn, *, targets: list[int], edges: list | None = None,
                 onset_frac: tuple[float, float] = ONSET_FRAC, stim_range: tuple[float, float] | None = None, t_end: float | None = None):
        self.rec = sysrec
        self.rng = rng
        self.seed_fn = seed_fn
        self.targets = sorted(int(t) for t in targets)
        self.edges = [list(map(int, e)) for e in (edges or [])]
        self.T = float(sysrec["t_end_default"] if t_end is None else t_end)
        self.dt = float(sysrec["dt"])
        self.cap = normalize_capability(sysrec.get("capability"), t_end=float(sysrec["t_end_default"]), dt=self.dt,
                                        input_dim=int(sysrec.get("input_dim", 1)))
        self.n_u = int(sysrec.get("input_dim", 1))
        self.onset_frac = onset_frac
        st = self.cap["stimulus"]
        self.stim_range = tuple(stim_range or st["range"])
        lev = st["nominal_level"]
        self.level = float(lev[0]) if isinstance(lev, (list, tuple)) else float(lev)

    # ------------------------------------------------------------------ basics
    def snap(self, t: float) -> float:
        return P.snap(t, self.dt)

    def horizon(self, name: str) -> float:
        return HORIZON_FRACTIONS[name] * float(self.rec["t_end_default"])

    def value(self, level) -> float | list:
        if self.n_u == 1:
            return float(level[0]) if isinstance(level, (list, tuple)) else float(level)
        if isinstance(level, (list, tuple)):
            return [float(v) for v in level]
        return [float(level)] * self.n_u

    def base(self, *, level=None, t_on: float | None = None, params_seed: int | None = None) -> dict:
        max_on = float(self.cap["stimulus"]["max_onset"])
        t_on = self.snap(self.rng.uniform(self.dt, max(self.dt, max_on))) if t_on is None else self.snap(t_on)
        lev = self.level if level is None else level
        return {"system": self.rec["system_id"], "params_seed": int(self.seed_fn() if params_seed is None else params_seed),
                "weight_noise": None, "r0": {"kind": "rest"}, "t_end": self.T, "dt": self.dt,
                "stimulus": [[0.0, self.value(0.0)], [t_on, self.value(lev)]], "events": [], "obs_noise": None}

    def onset(self, lo: float | None = None, hi: float | None = None) -> float:
        a = self.onset_frac[0] * self.T if lo is None else lo
        b = self.onset_frac[1] * self.T if hi is None else hi
        return self.snap(self.rng.uniform(a, b))

    def pick_targets(self, n: int, pool: list[int] | None = None) -> list[int]:
        pool = self.targets if pool is None else pool
        if len(pool) < n:
            raise ValueError(f"needs {n} targets, the system has {len(pool)}")
        return sorted(int(x) for x in self.rng.choice(pool, size=n, replace=False))

    def sign(self, p_pos: float = 0.5) -> float:
        return 1.0 if self.rng.random() < p_pos else -1.0

    def d_pulse(self) -> float:
        return float(self.cap["current"]["pulse_max_duration"])

    def d_sustain(self) -> float:
        return float(self.cap["current"]["sustained_min_duration"])

    def pulse_duration(self) -> float:
        dp = self.d_pulse()
        lo = max(5 * self.dt, 0.1 * dp)
        return max(self.dt, self.snap(self.rng.uniform(lo, max(lo, dp))))

    def window_duration(self) -> float:
        lo = self.d_pulse()
        hi = max(lo, min(3.0 * self.d_sustain(), 0.4 * self.T))
        return max(self.dt, self.snap(self.rng.uniform(lo, hi)))

    def end_or_none(self, t0: float, dur: float, p_persist: float = P_PERSIST) -> float | None:
        if self.rng.random() < p_persist:
            return None
        return min(self.T, self.snap(t0 + dur))

    def initial_state(self, scale: float = 1.0) -> dict:
        init = self.cap["init"]
        units = list(self.rec.get("observed") or self.targets)
        lo = float(init.get("min_value", 0.0)) * scale
        hi = float(init.get("max_value", 1.0)) * scale
        k = max(1, round(0.5 * len(units)))
        chosen = self.rng.choice(units, size=min(k, len(units)), replace=False)
        return {"kind": "state", "values": {str(int(u)): round(float(self.rng.uniform(lo, hi)), 4) for u in chosen}}

    # ------------------------------------------------------------------ observational families
    def obs(self, family: str, *, params_seed: int | None = None) -> dict:
        if family in ("obs.nominal", "obs.param"):
            return self.base(params_seed=params_seed)
        if family == "obs.stim":
            lo, hi = self.stim_range
            p = self.base(level=float(self.rng.uniform(lo, hi)), params_seed=params_seed)
            if self.rng.random() < 0.5:
                p["stimulus"].append([self.snap(self.rng.uniform(0.3, 0.6) * self.T), self.value(float(self.rng.uniform(lo, hi)))])
            if self.rng.random() < 0.4:
                p["stimulus"].append([self.snap(self.rng.uniform(0.62, 0.9) * self.T), self.value(0.0)])
            p["stimulus"] = sorted(p["stimulus"], key=lambda r: r[0])
            if F.is_nominal_stimulus(P.validate(p)["stimulus"], {"capability": self.cap}):
                p["stimulus"].append([self.snap(0.5 * self.T), self.value(lo)])
            return p
        if family == "obs.init":
            p = self.base(params_seed=params_seed)
            p["r0"] = self.initial_state()
            return p
        if family == "obs.wnoise":
            p = self.base(params_seed=params_seed)
            p["weight_noise"] = {"sd": round(float(self.rng.uniform(0.02, float(self.cap["weight_noise"]["max_sd"]))), 4),
                                 "seed": int(self.seed_fn())}
            return p
        raise ValueError(family)

    # ------------------------------------------------------------------ single-event families
    def event(self, family: str, t0: float, targets: list[int], mclass: str, edges: list | None = None) -> dict:
        cap = self.cap
        if family in ("kick.1", "kick.2", "kick.g", "kick.hi"):
            return {"kind": "kick", "t": t0, "delta": {str(u): round(self.sign() * class_value(cap, "kick", mclass, self.rng), 6)
                                                        for u in targets}}
        if family in ("pulse.1", "pulse.2", "pulse.g", "pulse.hi"):
            s = self.sign(0.75)
            return {"kind": "current", "t0": t0, "t1": min(self.T, self.snap(t0 + self.pulse_duration())),
                    "targets": {str(u): round(s * class_value(cap, "current", mclass, self.rng), 6) for u in targets}}
        if family in ("act.1", "inh.1"):
            s = 1.0 if family == "act.1" else -1.0
            dur = self.snap(self.rng.uniform(self.d_sustain(), 2.5 * self.d_sustain()))
            t1 = self.end_or_none(t0, dur)
            if t1 is not None and t1 - t0 < self.d_sustain() - 1e-9:
                t1 = None
            return {"kind": "current", "t0": t0, "t1": t1,
                    "targets": {str(u): round(s * class_value(cap, "current", mclass, self.rng), 6) for u in targets}}
        if family in ("sil.1", "sil.2", "sil.g", "sil.1p"):
            if family == "sil.1p":
                t1 = None
            elif family == "sil.1":
                t1 = min(self.T, self.snap(t0 + self.window_duration()))
            else:
                t1 = self.end_or_none(t0, self.window_duration())
            return {"kind": "silence", "t0": t0, "t1": t1, "targets": [int(u) for u in targets]}
        if family in ("edge.w", "edge.rm"):
            if family == "edge.rm":
                f = 0.0
            else:
                depth = min(EDGE_DEPTH_MAX, class_value(cap, "edge_scale", mclass if mclass in MAG_MULT else "moderate", self.rng))
                f = round(1.0 - depth, 6)
            return {"kind": "edge_scale", "t0": t0, "t1": self.end_or_none(t0, self.window_duration()), "edges": [list(e) for e in edges],
                    "factor": f}
        if family == "param.1":
            fields = list(cap["param"]["fields"])
            fld = fields[int(self.rng.integers(len(fields)))]
            v = class_value(cap, "param", mclass, self.rng, fld)
            change = {fld: round(max(0.05, 1.0 + self.sign() * v), 6)} if fld in ("gain", "tau") else {fld: round(self.sign() * v, 6)}
            return {"kind": "param", "t0": t0, "t1": self.end_or_none(t0, self.window_duration()), "targets": {str(targets[0]): change}}
        raise ValueError(family)

    # ------------------------------------------------------------------ patterns
    def sequence(self, family: str, t0: float, target: int, mclass: str) -> dict:
        min_seg = int(self.cap["current_seq"].get("min_seg_steps", P.MIN_SEG_STEPS))
        seg = self.snap(max(min_seg * self.dt, self.d_pulse() / 4.0))
        amp = round(class_value(self.cap, "current", mclass, self.rng), 6)
        if family == "seq.train":
            on, off, n = int(self.rng.integers(1, 3)), int(self.rng.integers(2, 4)), int(self.rng.integers(3, 6))
            vals = ([amp] * on + [0.0] * off) * n
            vals = vals[: len(vals) - off]
        elif family == "seq.pp":
            on1, gap, on2 = int(self.rng.integers(1, 3)), int(self.rng.integers(3, 8)), int(self.rng.integers(1, 3))
            vals = [amp] * on1 + [0.0] * gap + [amp] * on2
        elif family == "seq.prbs":
            vals = [amp, 0.0, amp, amp, 0.0, 0.0, amp]
            for _ in range(200):
                m = int(self.rng.integers(12, 25))
                bits = self.rng.random(m) < 0.5
                bits[0] = True
                cand = [amp if b else 0.0 for b in bits]
                while cand and cand[-1] == 0.0:
                    cand.pop()
                st, ln, gp = _runs([v != 0.0 for v in cand])
                if len(st) >= 3 and not (len(set(ln)) == 1 and len(set(gp)) == 1):
                    vals = cand
                    break
        elif family == "seq.chirp":
            m = int(self.rng.integers(20, 41))
            f0, f1 = 1.0 / (m * seg), 6.0 / (m * seg)
            tt = np.arange(m) * seg
            ph = 2 * np.pi * (f0 * tt + 0.5 * (f1 - f0) / (m * seg) * tt ** 2)
            vals = [round(float(amp * math.sin(p_)), 6) for p_ in ph]
            if len({round(v, 12) for v in vals}) < 3:
                vals = [round(amp * (j % 3 - 1), 6) for j in range(m)]
        else:
            raise ValueError(family)
        span = seg * len(vals)
        if t0 + span > self.T - self.dt:
            # too long for the window: shortest segments first, then trailing segments dropped; the family must survive
            seg = self.snap(min_seg * self.dt)
            max_len = int((self.T - self.dt - t0) / seg)
            if len(vals) > max_len:
                vals = vals[:max_len]
                while vals and vals[-1] == 0.0:
                    vals.pop()
            span = seg * len(vals)
            if not vals or t0 + span > self.T:
                raise ValueError(f"{family} does not fit into the window")
            st, ln, gp = _runs([v != 0.0 for v in vals])
            ok = {"seq.train": len(st) >= 3 and len(set(ln)) == 1 and len(set(gp)) == 1, "seq.pp": len(st) == 2,
                  "seq.prbs": len(st) >= 3 and not (len(set(ln)) == 1 and len(set(gp)) == 1),
                  "seq.chirp": len({round(v, 12) for v in vals}) >= 3}[family]
            if not ok:
                raise ValueError(f"{family} does not fit into the window")
        return {"kind": "current_seq", "t0": t0, "seg": seg, "targets": {str(int(target)): [float(v) for v in vals]}}

    def composition(self, family: str, t0: float, targets: list[int]) -> tuple[list[dict], dict]:
        """Two different single interventions: `comp.seq` = b starts after a ended; `comp.sim` = b overlaps a. Returns the events and
        the components {"a": [...], "b": [...], "families": [fa, fb]} (absolute times)."""
        kinds = [f for k, f in (("kick", "kick.1"), ("current", "pulse.1"), ("silence", "sil.1"), ("param", "param.1"))
                 if self.cap.get(k, {}).get("supported")]
        if len(kinds) < 2:
            raise ValueError("composition needs two supported kinds")
        fa, fb = [kinds[i] for i in self.rng.choice(len(kinds), size=2, replace=False)]
        if family == "comp.sim" and fa == "kick.1":
            fa, fb = fb, fa                                  # the first (windowed) component must be able to overlap the second
        ta = targets[0]
        tb = targets[1] if len(targets) > 1 else targets[0]
        ea = self.event(fa, t0, [ta], "moderate")
        if ea["kind"] != "kick" and ea.get("t1") is None:
            ea["t1"] = min(self.T, self.snap(t0 + self.window_duration()))
        end_a = t0 + self.dt if ea["kind"] == "kick" else float(ea["t1"])
        if family == "comp.seq":
            tb0 = self.snap(end_a + self.rng.uniform(self.dt, max(2 * self.dt, self.d_pulse())))
        else:
            tb0 = self.snap(t0 + self.rng.uniform(0.0, max(self.dt, 0.8 * (end_a - t0))))
            tb0 = min(tb0, self.snap(end_a - self.dt))
        tb0 = min(max(t0, tb0), self.snap(self.T - 2 * self.dt))
        eb = self.event(fb, tb0, [tb], "moderate")
        if eb["kind"] != "kick" and eb.get("t1") is None:
            eb["t1"] = min(self.T, self.snap(eb["t0"] + self.window_duration()))
        return [ea, eb], {"a": [ea], "b": [eb], "families": [fa, fb]}

    # ------------------------------------------------------------------ one protocol of a family
    def make(self, family: str, *, targets: list[int] | None = None, edges: list | None = None, mclass: str | None = None,
             onset: float | None = None, params_seed: int | None = None, level=None) -> tuple[dict, dict]:
        """(protocol, spec info) of one trajectory of `family`; interventions start at `onset`. Explicit `targets` / `edges` are
        used exactly (identity cells)."""
        if family in F.OBS:
            return self.obs(family, params_seed=params_seed), {"family": family, "targets": (), "mclass": "na", "onset": None}
        p = self.base(level=self.level if level is None else level, params_seed=params_seed)
        t0 = self.onset() if onset is None else self.snap(onset)
        if family in ("edge.w", "edge.rm"):
            if edges is None:
                if not self.edges:
                    raise ValueError("no scalable edges")
                k = min(len(self.edges), int(self.rng.integers(1, 3)))
                edges = [list(self.edges[i]) for i in sorted(self.rng.choice(len(self.edges), size=k, replace=False))]
            mc = "na" if family == "edge.rm" else (mclass or "moderate")
            p["events"] = [self.event(family, t0, [], mc, edges=edges)]
            return p, {"family": family, "targets": tuple(sorted({int(x) for e in edges for x in e})), "edges": edges, "mclass": mc,
                       "onset": t0}
        n_t = {"kick.2": 2, "pulse.2": 2, "sil.2": 2, "kick.g": int(self.rng.integers(3, 5)), "pulse.g": int(self.rng.integers(3, 5)),
               "sil.g": int(self.rng.integers(3, 5))}.get(family, 1)
        tg = sorted(int(t) for t in targets) if targets is not None else self.pick_targets(n_t)
        mc = "hi" if family in ("kick.hi", "pulse.hi") else ("na" if family.startswith("sil.") else (mclass or "moderate"))
        if family in F.SEQ:
            p["events"] = [self.sequence(family, t0, tg[0], "moderate" if mc in ("na",) else mc)]
        elif family in F.COMP:
            p["events"], comp = self.composition(family, t0, tg)
            return p, {"family": family, "targets": tuple(tg), "mclass": "na", "onset": t0, "components": comp}
        else:
            p["events"] = [self.event(family, t0, tg, mc)]
        return p, {"family": family, "targets": tuple(tg), "mclass": mc, "onset": t0}


# ================================================================================================================ set designs
def _spec(p: dict, info: dict, split: str, role: str, *, twin: bool, cell: str = "", state: int = 0, **meta) -> Spec:
    m = {k: v for k, v in {**meta, "onset": info.get("onset"), "edges": info.get("edges"), "components": info.get("components")}.items()
         if v is not None}
    return Spec(protocol=p, split=split, role=role, family=info["family"], mclass=info.get("mclass", "na"),
                target_set=tuple(info.get("targets") or ()), cell=cell, state=state, twin=twin, meta=m)


def intervention_families(split: dict) -> list[str]:
    return [f for f in split["families_train"] if f in F.INTERVENTION_FAMILIES]


N_TARGETS_NEEDED = {"kick.2": 2, "pulse.2": 2, "sil.2": 2, "kick.g": 3, "pulse.g": 3, "sil.g": 3}


def feasible(family: str, targets: list[int], edges: list) -> bool:
    if family in ("edge.w", "edge.rm"):
        return bool(edges)
    return len(targets) >= N_TARGETS_NEEDED.get(family, 1)


def design_passive(sampler: FamilySampler, counts: dict[str, int], split: str, role: str, *, seed_parts: tuple) -> list[Spec]:
    """Passive trajectories: 'obs.nominal' of the training data cycles over parameter draws 0-7 (labelled obs.param by
    `family_of` when the system names a different nominal draw); other families draw seeds from the sampler."""
    out = []
    for fam, n in counts.items():
        for j in range(n):
            if fam == "obs.nominal":
                ps = j % 8 if split == "train" else public_seed_of(*seed_parts, fam, j)
                p = sampler.base(params_seed=ps)
            else:
                p = sampler.obs(fam)
            out.append(_spec(p, {"family": fam}, split, role, twin=False))
    return out


def design_interventions(sampler: FamilySampler, families: list[str], n: int, split: str, role: str, *, edges: list) -> list[Spec]:
    """n intervention trajectories uniformly over families x targets x magnitude classes x onsets (each with a twin)."""
    fams = [f for f in families if feasible(f, sampler.targets, edges)]
    out: list[Spec] = []
    if not fams:
        return out
    for j in range(n):
        fam = fams[j % len(fams)]
        mc = MAG_CLASSES[int(sampler.rng.integers(len(MAG_CLASSES)))]
        p, info = sampler.make(fam, mclass=mc)
        out.append(_spec(p, info, split, role, twin=True))
    return out


def design_cells(sampler: FamilySampler, family: str, role: str, *, targets: list[int], edges: list, seed_fn,
                 cells: int = CELLS_PER_FAMILY, states: int = STATES_PER_CELL, tag: str = "") -> list[Spec]:
    """Test items of one family: `cells` identity cells (target set x magnitude class) x `states` distinct states."""
    if family in F.COMP:
        if not targets:
            return []
    elif not feasible(family, targets, edges):
        return []
    out = []
    n_t = min(2, len(targets)) if family in F.COMP else N_TARGETS_NEEDED.get(family, 1)
    for c in range(cells):
        mc = "moderate" if c == 0 else ("weak" if sampler.rng.random() < 0.5 else "strong")
        tg = sampler.pick_targets(n_t, targets) if family not in ("edge.w", "edge.rm") else None
        ed = None
        if family in ("edge.w", "edge.rm"):
            k = min(len(edges), 1 + (c % 2))
            ed = [list(edges[i]) for i in sorted(sampler.rng.choice(len(edges), size=k, replace=False))]
        for s in range(states):
            lo, hi = sampler.stim_range
            try:
                p, info = sampler.make(family, targets=tg, edges=ed, mclass=mc, params_seed=seed_fn(), level=float(sampler.rng.uniform(lo, hi)))
            except ValueError:
                return out
            out.append(_spec(p, info, "test", role, twin=True, cell=f"{family}|c{c}{tag}", state=s))
    return out


def design_tests(s_pub: FamilySampler, s_hid: FamilySampler | None, sysrec: dict, level: str, *, edges_pub: list, edges_hid: list,
                 seed_fn) -> list[Spec]:
    """Every test item of one system (Level B: in-family, target shift, family shift, hidden-only, passive; Level C adds OOD and
    robustness)."""
    split = sysrec["split"]
    out: list[Spec] = []
    for fam in intervention_families(split):
        out += design_cells(s_pub, fam, "in", targets=s_pub.targets, edges=edges_pub, seed_fn=seed_fn)
        if s_hid is not None:
            if fam in ("edge.w", "edge.rm"):
                if edges_hid:
                    out += design_cells(s_hid, fam, "target", targets=s_hid.targets or s_pub.targets, edges=edges_hid, seed_fn=seed_fn,
                                        tag="|hid")
            elif s_hid.targets:
                out += design_cells(s_hid, fam, "target", targets=s_hid.targets, edges=edges_hid, seed_fn=seed_fn, tag="|hid")
    for fam in [f for f in split.get("families_heldout") or [] if f in F.INTERVENTION_FAMILIES]:
        out += design_cells(s_pub, fam, F.shift_kind(fam, split["families_train"]), targets=s_pub.targets, edges=edges_pub, seed_fn=seed_fn)
    for fam in split.get("hidden_only") or []:
        try:
            out += design_cells(s_pub, fam, "hidden", targets=s_pub.targets, edges=edges_pub, seed_fn=seed_fn)
        except ValueError:
            continue
    for j in range(N_PASSIVE_TEST):
        fam = ("obs.nominal", "obs.stim", "obs.init", "obs.stim")[j % 4]
        p = s_pub.obs(fam, params_seed=seed_fn())
        out.append(_spec(p, {"family": fam}, "test", "passive", twin=False))
    if level == "C":
        out += design_ood(s_pub, sysrec, edges_pub, seed_fn)
        out += design_robust(s_pub, sysrec, edges_pub, seed_fn)
    return out


def _in_family(sampler: FamilySampler, sysrec: dict, edges: list) -> list[str]:
    fams = [f for f in intervention_families(sysrec["split"]) if feasible(f, sampler.targets, edges)]
    return fams or [f for f in ("kick.1", "pulse.1", "sil.1") if sampler.cap.get({"kick.1": "kick", "pulse.1": "current",
                                                                                   "sil.1": "silence"}[f], {}).get("supported")][:1]


def _spread(p: dict, value: float, seed_fn) -> bool:
    """Set the protocol's parameter spread; False (and a documented weight-noise proxy) when the format has no such field."""
    if protocol_has("params_spread"):
        p["params_spread"] = float(value)
        return True
    p["weight_noise"] = {"sd": round(1.5 * 0.1, 4), "seed": int(seed_fn())}
    return False


def design_ood(s: FamilySampler, sysrec: dict, edges: list, seed_fn) -> list[Spec]:
    """PROTOCOL 4.1 (Level C). Composition = the hidden-only items (not duplicated here)."""
    fams = _in_family(s, sysrec, edges)
    out: list[Spec] = []
    lo, hi = s.stim_range
    for j in range(ITEMS_PER_CATEGORY):
        fam = fams[j % len(fams)]
        p, info = s.make(fam, params_seed=seed_fn(), level=(0.5 * lo if j % 2 == 0 else 1.5 * hi))
        out.append(_spec(p, info, "test", "ood:input_amplitude", twin=True, cell=f"ood_amp|{fam}", state=j))
        p, info = s.make(fam, params_seed=seed_fn())
        exact = _spread(p, PARAMS_SPREAD_OOD, seed_fn)
        out.append(_spec(p, info, "test", "ood:param_spread", twin=True, cell=f"ood_spread|{fam}", state=j,
                         **({} if exact else {"proxy": True})))
        on = s.snap(s.rng.uniform(0.02, 0.12) * s.T) if j % 2 == 0 else s.snap(s.rng.uniform(0.52, 0.6) * s.T)
        p, info = s.make(fam, params_seed=seed_fn(), onset=on)
        out.append(_spec(p, info, "test", "ood:timing", twin=True, cell=f"ood_timing|{fam}", state=j))
        p, info = s.make(fam, params_seed=seed_fn())
        p["r0"] = s.initial_state(scale=2.0)
        out.append(_spec(p, info, "test", "ood:initial_condition", twin=True, cell=f"ood_init|{fam}", state=j))
        s2 = FamilySampler({**sysrec, "dt": 2.0 * s.dt}, s.rng, seed_fn, targets=s.targets, edges=edges)
        p, info = s2.make(fam, params_seed=seed_fn())
        out.append(_spec(p, info, "test", "ood:sampling", twin=True, cell=f"ood_dt|{fam}", state=j))
    return out


def _jitter_events(events: list[dict], s: FamilySampler, amp: bool) -> list[dict]:
    out = json.loads(json.dumps(events))
    for e in out:
        if amp:
            f = float(s.rng.uniform(0.8, 1.2))
            if e["kind"] == "kick":
                e["delta"] = {u: round(v * f, 6) for u, v in e["delta"].items()}
            elif e["kind"] == "current":
                e["targets"] = {u: round(v * f, 6) for u, v in e["targets"].items()}
            elif e["kind"] == "current_seq":
                e["targets"] = {u: [round(v * f, 6) for v in lst] for u, lst in e["targets"].items()}
            elif e["kind"] == "edge_scale" and e["factor"] > 0:
                e["factor"] = round(min(2.0, max(0.0, 1.0 - (1.0 - e["factor"]) * f)), 6)
            elif e["kind"] == "param":
                e["targets"] = {u: {k: (round(1.0 + (x - 1.0) * f, 6) if k in ("gain", "tau") else round(x * f, 6)) for k, x in v.items()}
                                for u, v in e["targets"].items()}
        else:
            sh = int(s.rng.choice([-2, -1, 1, 2])) * s.dt
            for key in ("t", "t0", "t1"):
                if e.get(key) is not None:
                    e[key] = round(min(s.T, max(0.0, float(e[key]) + sh)), 9)
    return out


def design_robust(s: FamilySampler, sysrec: dict, edges: list, seed_fn) -> list[Spec]:
    """PROTOCOL 4.2 (Level C)."""
    fams = _in_family(s, sysrec, edges)
    pn_ok = bool(s.cap.get("process_noise", {}).get("supported")) and protocol_has("process_noise")
    pn_levels = s.cap.get("process_noise", {}).get("levels") or list(PROCESS_NOISE_LEVELS)
    out: list[Spec] = []
    for j in range(ITEMS_PER_CATEGORY):
        fam = fams[j % len(fams)]
        for lv in PARAMS_NOISE_LEVELS:
            p, info = s.make(fam, params_seed=seed_fn())
            exact = _spread(p, lv, seed_fn)
            out.append(_spec(p, info, "test", f"robust:param_noise_{lv}", twin=True, cell=f"rb_param{lv}|{fam}", state=j,
                             **({} if exact else {"proxy": True})))
        for sd in (0.05, 0.1):
            p, info = s.make(fam, params_seed=seed_fn())
            p["weight_noise"] = {"sd": sd, "seed": int(seed_fn())}
            out.append(_spec(p, info, "test", f"robust:weight_noise_{sd}", twin=True, cell=f"rb_wn{sd}|{fam}", state=j))
        if pn_ok:
            for sd in pn_levels:
                p, info = s.make(fam, params_seed=seed_fn())
                p["process_noise"] = {"sd": float(sd), "seed": int(seed_fn())}
                out.append(_spec(p, info, "test", f"robust:process_noise_{sd}", twin=True, cell=f"rb_proc{sd}|{fam}", state=j))
        for sd in (0.05, 0.1):
            p, info = s.make(fam, params_seed=seed_fn())
            p["obs_noise"] = {"sd": sd, "seed": int(seed_fn())}
            out.append(_spec(p, info, "test", f"robust:obs_noise_{sd}", twin=True, cell=f"rb_on{sd}|{fam}", state=j))
        for cond, amp in (("amplitude_jitter", True), ("timing_jitter", False)):
            p, info = s.make(fam, params_seed=seed_fn())
            told = p["events"]
            p["events"] = _jitter_events(told, s, amp)
            try:
                P.validate(p)
            except P.ProtocolError:
                p["events"] = told
            out.append(_spec(p, info, "test", f"robust:{cond}", twin=True, cell=f"rb_{cond}|{fam}", state=j, model_events=told))
    return out


def state_r0(state) -> dict:
    """r0 of an explicit full microstate vector (synthetic generators: indices of the full state, zeros omitted)."""
    v = np.asarray(state, dtype=np.float64).ravel()
    return {"kind": "state", "values": {str(i): float(x) for i, x in enumerate(v) if x != 0.0}}


def design_pool_sources(s: FamilySampler, sysrec: dict, edges: list, *, hidden: bool, parts: tuple, pool_state_fn=None) -> list[Spec]:
    """POOL_DRAWS parameter draws x POOL_TRAJ source trajectories per draw (P4-D14: 8 x 15), cycling over POOL_SOURCES: a start from a
    generator pool state (synthetic systems whose generator provides `pool_states`; otherwise an initial-state change), a stimulus
    change, an initial-state change and two trained single interventions. States of one draw are compared with each other only."""
    out = []
    fams = _in_family(s, sysrec, edges)
    salt = read_salt() if hidden else None
    n_gen = POOL_DRAWS * sum(1 for j in range(POOL_TRAJ) if POOL_SOURCES[j % len(POOL_SOURCES)] == "pool_state")
    gen_states = []
    if pool_state_fn is not None:
        try:
            gen_states = list(pool_state_fn(n_gen, rng_of("pool-states-gen", *parts)))
        except Exception:  # noqa: BLE001 - a generator without usable pool states falls back to initial-state changes
            gen_states = []
    gi = 0
    for g in range(POOL_DRAWS):
        ps = hidden_seed("pool", *parts, g, salt=salt) if hidden else public_seed_of("pool", *parts, g)
        for j in range(POOL_TRAJ):
            src = POOL_SOURCES[j % len(POOL_SOURCES)]
            if src == "pool_state" and gen_states:
                p = s.obs("obs.stim" if (j // len(POOL_SOURCES)) % 2 else "obs.nominal", params_seed=ps)
                p["r0"] = state_r0(gen_states[gi % len(gen_states)])
                gi += 1
            elif src in ("pool_state", "init"):
                p, src = s.obs("obs.init", params_seed=ps), "init"
            elif src == "stim" or not fams:
                p, src = s.obs("obs.stim", params_seed=ps), "stim"
            else:
                p, _ = s.make(fams[(g + j) % len(fams)], params_seed=ps)
            p["params_seed"] = int(ps)
            out.append(Spec(protocol=p, split="pool_src", role="pool_src", meta={"draw": g, "traj": j, "source": src}))
    return out


def pool_sequences(sysrec: dict, rng: np.random.Generator, targets: list[int], edges: list, families_allowed=None) -> dict[str, dict]:
    """The fixed intervention sequences of the pool: one per supported event kind, moderate magnitude, starting at time 0 of the
    future and ending within the primary horizon."""
    if not targets:
        return {}
    Tf = POOL_FUTURE_FRAC * float(sysrec["t_end_default"])
    ss = FamilySampler(sysrec, rng, lambda: 0, targets=targets, edges=edges, t_end=Tf)
    cap = ss.cap
    med = ss.snap(min(Tf, ss.horizon("medium")))
    tg = [int(rng.choice(targets))]
    seqs: dict[str, dict] = {}
    for kind, fam in SEQ_KINDS:
        if not cap.get(kind, {}).get("supported"):
            continue
        try:
            if fam == "seq.train":
                ev = ss.sequence(fam, 0.0, tg[0], "moderate")
            elif fam == "edge.w":
                if not edges:
                    continue
                ev = ss.event(fam, 0.0, [], "moderate", edges=[list(edges[int(rng.integers(len(edges)))])])
            else:
                ev = ss.event(fam, 0.0, tg, "moderate")
            if ev["kind"] in ("silence", "param", "edge_scale", "current") and (ev.get("t1") is None or ev["t1"] > med):
                ev["t1"] = med if ev["kind"] != "current" or ev.get("t1") is None else min(ev["t1"], med)
            P.validate({"system": sysrec["system_id"], "params_seed": 0, "t_end": round(Tf, 9), "dt": ss.dt, "events": [ev]})
        except (ValueError, P.ProtocolError):
            continue
        if families_allowed is not None:
            from .families import family_of
            if family_of({"system": sysrec["system_id"], "params_seed": 0, "t_end": round(Tf, 9), "dt": ss.dt, "events": [ev]},
                         sysrec) not in set(families_allowed):
                continue
        seqs[kind] = {"events": [ev], "family": fam, "kind": kind}
    return seqs


def design_public_tests(s: FamilySampler, sysrec: dict, edges: list, seed_fn) -> list[Spec]:
    """The PUBLIC evaluation subset (policy 'public'): in-family items (families_train on public targets / edges, development
    magnitudes, public seeds; each with its twin) and passive test trajectories. Everything is simulatable under the public policy."""
    out: list[Spec] = []
    for fam in intervention_families(sysrec["split"]):
        out += design_cells(s, fam, "in", targets=s.targets, edges=edges, seed_fn=seed_fn)
    for j in range(N_PASSIVE_TEST):
        fam = ("obs.nominal", "obs.stim", "obs.init", "obs.stim")[j % 4]
        out.append(_spec(s.obs(fam, params_seed=seed_fn()), {"family": fam}, "test", "passive", twin=False))
    return out


def plan_system(pub: dict, internal: dict, *, tier: str, seed: int, level: str, sets: tuple[str, ...], pool_state_fn=None,
                policy: str = "full") -> list[Spec]:
    """Every planned base trajectory of one system (deterministic in (tier, seed, system id, policy)). `sets` among: public (D0, D1,
    validation), tests, pool_src. policy 'full' = the Level B / C design of `design_tests` (hidden-range seeds on the hidden tiers);
    policy 'public' = only what the system's public policy can simulate (`design_public_tests`; public seeds; pool sources without
    generator starts). Twins and composition components are added by `run_specs`."""
    sid = pub["system_id"]
    kind = "mech" if pub.get("mode") == "mech" else ("full" if pub["kind"] == "real" else "synthetic")
    edges_pub = [list(e) for e in pub.get("edges_public") or []]
    edges_hid = [list(e) for e in internal.get("edges_heldout") or []]
    specs: list[Spec] = []
    if "public" in sets:
        rng = rng_of("plan", tier, seed, sid)
        s_pub = FamilySampler(pub, rng, seed_counter(False, "pub", tier, seed, sid), targets=pub["targets_public"], edges=edges_pub)
        n1 = B_MAIN[kind]
        fams = intervention_families(pub["split"])
        specs += design_passive(s_pub, D0_DESIGN, "train", "d0", seed_parts=("d0", tier, seed, sid))
        specs += design_interventions(s_pub, fams, n1, "train", "d1", edges=edges_pub)
        specs += design_passive(s_pub, {f: max(1, round(VAL_FRACTION * n)) for f, n in D0_DESIGN.items()}, "val", "d0",
                                seed_parts=("val", tier, seed, sid))
        specs += design_interventions(s_pub, fams, round(VAL_FRACTION * n1), "val", "d1", edges=edges_pub)
    if "tests" in sets or "pool_src" in sets:
        public_only = policy == "public"
        tag = "test-public" if public_only else "test"
        hid = (tier in HIDDEN_TIERS) and not public_only
        tseed = seed_counter(hid, tag, tier, seed, sid)
        rng_t = rng_of(tag, tier, seed, sid)
        # outside the public policy, systems without public edges (real systems: edge families are never trained) test edge families
        # on the strongest edges of their public connectivity summary
        edges_t = edges_pub if public_only else (edges_pub or _graph_edges(pub))
        s_tp = FamilySampler(pub, rng_t, tseed, targets=pub["targets_public"], edges=edges_t)
        if "tests" in sets:
            if public_only:
                specs += design_public_tests(s_tp, pub, edges_t, tseed)
            else:
                hid_targets = internal.get("targets_heldout") or []
                s_th = FamilySampler(pub, rng_t, tseed, targets=hid_targets, edges=edges_hid) if (hid_targets or edges_hid) else None
                specs += design_tests(s_tp, s_th, pub, level, edges_pub=edges_t, edges_hid=edges_hid, seed_fn=tseed)
        if "pool_src" in sets:
            s_pool = FamilySampler(pub, rng_of(f"{tag}-pool-src", tier, seed, sid), tseed, targets=pub["targets_public"], edges=edges_t)
            specs += design_pool_sources(s_pool, pub, edges_t, hidden=hid, parts=(tag, tier, seed, sid),
                                         pool_state_fn=None if public_only else pool_state_fn)
    return specs


# ================================================================================================================ simulation
def dataset_key(protocol: dict, system_hash: str, engine: str) -> str:
    """Content key of a trajectory record (the full protocol, including observation noise)."""
    return P.protocol_hash(protocol, system_hash=system_hash, simulator=engine)


class SimContext:
    """How to simulate one system (orchestrator side): a synthetic adapter system or a real engine + system, through the store."""

    def __init__(self, internal: dict, *, store_root: Path | str = STORE, synthetic_system=None, bundle: Path | None = None):
        from .store import TrajectoryStore
        self.rec = internal
        self.sid = internal["system_id"]
        self.kind = internal["kind"]
        self.store = TrajectoryStore(store_root)
        self.syn = synthetic_system
        if self.kind == "synthetic":
            if synthetic_system is None:
                raise ValueError("a synthetic context needs its generator system")
            self.system_hash, self.engine_id = synthetic_system.content_hash(), synthetic_system.engine_id
        else:
            from brainir.sim.model import MODEL_ID

            from .realsim import ENGINE_VERSION, RealEngine
            from .systems import BUNDLE, real_system
            self.real = real_system(internal)
            self.engine = RealEngine(bundle or BUNDLE, internal["network"])
            self.system_hash = internal["system_hash"]
            self.engine_id = f"{ENGINE_VERSION}|{MODEL_ID}"

    def store_key(self, protocol: dict) -> str:
        return self.store.key(protocol, self.system_hash, self.engine_id)

    def run(self, protocol: dict, meta: dict | None = None) -> dict:
        """Simulate (or fetch) one protocol: {"key", "store_key", "t", "x", "u", "y", "truth": {...}, "info"}. The observed arrays
        carry the protocol's observation noise; truth['y_clean'] is the noise-free readout (only when they differ). meta
        {"no_store": True}: simulate without writing the record to the store (pool futures: never restarted from; restart SOURCES are
        still read from the store); a stored record is still reused."""
        q = P.validate(protocol)
        no_store = bool((meta or {}).get("no_store"))
        if self.kind == "synthetic":
            skey = self.store_key(q)

            def compute():
                restart = None
                if q["r0"]["kind"] == "restart":
                    src = self.store.get(q["r0"]["key"])
                    if src is None or "state" not in src:
                        raise P.ProtocolError("restart source missing or stored without its full state")
                    t = np.asarray(src["t"], float)
                    restart = np.asarray(src["state"][round(q["r0"]["t"] / (t[1] - t[0]))], dtype=np.float64)
                rec = self.syn.simulate(P.microstate_protocol(q), full=True, restart_state=restart)
                if "state" not in rec:
                    raise RuntimeError("the generator returned no full state (restarts impossible)")
                return rec
            if no_store:
                rec = self.store.get(skey) or compute()
            else:
                skey, rec, _ = self.store.get_or_compute(skey, compute, {"system_id": self.sid, "system_hash": self.system_hash,
                                                                          "protocol": P.microstate_protocol(q), **(meta or {})})
            if "state" not in rec:
                raise RuntimeError(f"store record {skey[:12]} has no full state (it was stored without full=True)")
            from .synthadapter import observe_synthetic
            obs = observe_synthetic(rec, self.rec, q)
            truth = {k: np.asarray(rec[k], np.float64) for k in ("z", "z_obs") if k in rec}
            clean = np.asarray(rec["y"], np.float32)
        else:
            from .realsim import dense, observe
            if no_store:
                skey = self.store_key(q)
                rec = self.store.get(skey) or self.engine.run(self.real, q, store=self.store)
            else:
                skey, rec, _ = self.store.get_or_run(self.engine, self.real, q, self.system_hash, meta=meta)
            obs = observe(rec, self.real, q, self.rec.get("obs_scale"))
            truth = {}
            clean = dense(rec, list(self.real.readout))
        if q["obs_noise"] is not None and float(q["obs_noise"]["sd"]) > 0:
            truth["y_clean"] = clean
        return {"key": dataset_key(q, self.system_hash, self.engine_id), "store_key": skey, "t": obs["t"], "x": obs["x"], "u": obs["u"],
                "y": obs["y"], "truth": truth, "info": dict(rec.get("info") or {})}


_WORKER: dict = {}


def _worker_init(gen: tuple | None, store_root: str, tier: str, seed: int, internals: dict) -> None:
    try:
        import threadpoolctl
        threadpoolctl.threadpool_limits(1)
    except Exception:  # noqa: BLE001, S110 - thread limits are an optimisation only
        pass
    _WORKER.clear()
    _WORKER.update(gen=gen, store_root=store_root, tier=tier, seed=seed, internals=internals, ctx={})
    if gen is not None:
        from .synthadapter import register_generator
        register_generator(gen[0], gen[1])


def _ctx(sid: str) -> SimContext:
    c = _WORKER["ctx"].get(sid)
    if c is None:
        rec = _WORKER["internals"][sid]
        syn = None
        if rec["kind"] == "synthetic":
            from .synthadapter import suite_systems
            syn = suite_systems(rec.get("tier", _WORKER["tier"]), int(rec.get("tier_seed", _WORKER["seed"])))[sid]
        c = SimContext(rec, store_root=_WORKER["store_root"], synthetic_system=syn)
        _WORKER["ctx"][sid] = c
    return c


def _worker_run(job: tuple) -> dict:
    sid, protocol, meta = job
    try:
        return _ctx(sid).run(protocol, meta)
    except Exception as e:  # noqa: BLE001 - reported per job, never silently dropped
        return {"error": f"{type(e).__name__}: {e}"}


class LocalBackend:
    """Process-pool simulation through the content-addressed store (one BLAS thread per worker)."""

    def __init__(self, internals: dict, *, tier: str, seed: int, generator: tuple | None = None, store_root: Path | str = STORE,
                 workers: int = 4):
        self.args = (generator, str(store_root), tier, int(seed), internals)
        self.workers = max(1, int(workers))
        self._ex = None

    def run(self, jobs: list[tuple[str, dict, dict]]) -> list[dict]:
        if not jobs:
            return []
        if self.workers == 1:
            if not _WORKER or _WORKER.get("internals") is not self.args[4]:
                _worker_init(*self.args)
            return [_worker_run(j) for j in jobs]
        if self._ex is None:
            self._ex = ProcessPoolExecutor(max_workers=self.workers, initializer=_worker_init, initargs=self.args)
        return list(self._ex.map(_worker_run, jobs, chunksize=max(1, len(jobs) // (8 * self.workers))))

    def close(self) -> None:
        if self._ex is not None:
            self._ex.shutdown()
            self._ex = None


def modal_runner(backend, internals: dict, *, store: str = "store", batch: int = 8, cls: str | None = None):
    """A `run(jobs)` for the builders that simulates REAL systems on Modal through E4's Backend (`brainir_causal.p4modal.app`):
    observed-mode results only (full records stay on the volume store, fetched on demand with `backend.fetch`), host-gated 'sim' /
    'sim_eval' classes (<= 16 cores). Restart sources are read from the same volume store, so a build must use one store end to end
    ('store' for public / development data, 'eval' for hidden data). Protocols with observation noise are also simulated without it
    (the same microstate, served from the volume cache) to get the noise-free readout (truth['y_clean']). The store key each result
    carries is checked against the locally computed one."""
    from brainir.sim.model import MODEL_ID

    from .realsim import ENGINE_VERSION
    from .store import TrajectoryStore
    engine = f"{ENGINE_VERSION}|{MODEL_ID}"

    def run(jobs: list[tuple[str, dict, dict]]) -> list[dict]:
        items, owners = [], []
        for j, (sid, protocol, meta) in enumerate(jobs):
            rec = internals[sid]
            if rec.get("kind") != "real":
                raise ValueError("modal_runner simulates real systems only (synthetic systems run through LocalBackend)")
            q = P.validate(protocol)
            items.append({"sysdef": rec, "protocol": q, "meta": {"role": (meta or {}).get("role")}})
            owners.append((j, False))
            if q["obs_noise"] is not None and float(q["obs_noise"]["sd"]) > 0:
                items.append({"sysdef": rec, "protocol": {**q, "obs_noise": None}, "meta": {"clean_of": j}})
                owners.append((j, True))
        res = backend.simulate(items, mode="observed", store=store, batch=batch, cls=cls)
        out: list[dict | None] = [None] * len(jobs)
        clean: dict[int, object] = {}
        for (j, is_clean), r in zip(owners, res):
            if isinstance(r, BaseException) or not isinstance(r, dict):
                if not is_clean:
                    out[j] = {"error": f"{type(r).__name__}: {r}"[:500]}
                continue
            if is_clean:
                clean[j] = np.asarray(r["y"], np.float32)
                continue
            sid, protocol, _ = jobs[j]
            rec = internals[sid]
            q = P.validate(protocol)
            skey = TrajectoryStore.key(q, rec["system_hash"], engine)
            if r.get("key") and r["key"] != skey:
                out[j] = {"error": f"remote store key {str(r['key'])[:12]} != local {skey[:12]}"}
                continue
            out[j] = {"key": dataset_key(q, rec["system_hash"], engine), "store_key": skey, "t": np.asarray(r["t"]), "x": np.asarray(r["x"]),
                      "u": np.asarray(r["u"]), "y": np.asarray(r["y"]), "truth": {},
                      "info": {"remote": True, "computed": r.get("computed"), "sim_wall_s": r.get("sim_wall_s")}}
        for j, y in clean.items():
            if out[j] is not None and "error" not in out[j]:
                out[j]["truth"]["y_clean"] = y
        return [o if o is not None else {"error": "no result"} for o in out]
    return run


# ================================================================================================================ writers
class SetWriter:
    """Incremental writer of one system's experiment set in the p4-dataset-1 layout (manifest.json, index.jsonl, traj/<key>.npz),
    readable with `brainir_causal.data.ExperimentSet.load`."""

    def __init__(self, root: Path, sid: str, pub: dict, dataset_id: str):
        self.root, self.sid, self.pub, self.dataset_id = Path(root), sid, pub, dataset_id
        (self.root / "traj").mkdir(parents=True, exist_ok=True)
        self.index = self.root / "index.jsonl"
        self.index.write_text("", encoding="utf-8")
        self.n = 0

    def add(self, tr) -> None:
        p = self.root / "traj" / f"{tr.key}.npz"
        if not p.exists():
            tmp = p.with_name(p.stem + ".tmp.npz")
            np.savez_compressed(tmp, t=np.asarray(tr.t, np.float64), x=np.asarray(tr.x, np.float32), u=np.asarray(tr.u, np.float32),
                                y=np.asarray(tr.y, np.float32))
            tmp.replace(p)
        with open(self.index, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(tr.row(), sort_keys=True) + "\n")
        self.n += 1

    def close(self, extra: dict | None = None) -> None:
        from .data import DATASET_FORMAT
        man = {"format": DATASET_FORMAT, "dataset_id": self.dataset_id, "systems": {self.sid: self.pub}, **(extra or {})}
        (self.root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _family_label(protocol: dict, pub: dict) -> str:
    try:
        return F.family_of(protocol, pub)
    except Exception:  # noqa: BLE001
        return "other"


def _jobs_of(sp: Spec, sid: str) -> list[tuple[str, dict, dict, str]]:
    """The simulation jobs of one planned trajectory: itself, its twin, its composition components ((sid, protocol, meta, kind))."""
    jobs = [(sid, sp.protocol, {"role": sp.role, "split": sp.split}, "item")]
    if sp.twin:
        jobs.append((sid, P.counterfactual(sp.protocol), {"role": sp.role, "split": "twin"}, "twin"))
    comps = sp.meta.get("components")
    if comps:
        for part in ("a", "b"):
            jobs.append((sid, dict(sp.protocol, events=comps[part]), {"role": sp.role, "split": "component", "component": part}, part))
    return jobs


def run_specs(specs: list[Spec], pub: dict, run, sink, *, provenance: str = "benchmark", chunk: int = CHUNK) -> dict:
    """Simulate planned trajectories in chunks and hand every record to `sink(record, truth)`. Twins carry meta twin_of = their item's
    key and components component_of; the twin / components of a failed item are dropped with it. Returns counts and errors."""
    from .data import Trajectory
    errors, n_ok = [], 0
    i = 0
    while i < len(specs):
        batch, owners = [], []
        while i < len(specs) and len(batch) < chunk:
            for j in _jobs_of(specs[i], pub["system_id"]):
                batch.append(j[:3])
                owners.append((specs[i], j[3]))
            i += 1
        res = run(batch)
        item_key: dict[int, str | None] = {}
        for (sp, what), r in zip(owners, res):
            if what == "item":
                item_key[id(sp)] = None if "error" in r else r["key"]
            if "error" in r:
                errors.append({"role": sp.role, "what": what, "error": r["error"]})
                continue
            parent = item_key.get(id(sp))
            if what != "item" and parent is None:
                continue
            meta = {k: v for k, v in sp.meta.items() if k != "components"}
            meta.update({"role": sp.role, "mclass": sp.mclass, "target_set": list(sp.target_set), "cell": sp.cell, "state": sp.state,
                         "store_key": r["store_key"]})
            if what == "item" and sp.meta.get("components"):
                meta["component_families"] = sp.meta["components"].get("families")
            split = sp.split
            proto = sp.protocol
            if what == "twin":
                split, meta["twin_of"] = "twin", parent
                proto = P.counterfactual(sp.protocol)
                meta.pop("model_events", None)
            elif what in ("a", "b"):
                split, meta["component_of"], meta["component"] = "component", parent, what
                proto = dict(sp.protocol, events=sp.meta["components"][what])
                meta.pop("model_events", None)
            fam = _family_label(proto, pub)
            if what == "item" and sp.family and fam != sp.family:
                meta["family_planned"] = sp.family
            q = P.validate(proto)
            tr = Trajectory(key=r["key"], system_id=pub["system_id"], split=split, family=fam, protocol=q, t=r["t"], x=r["x"], u=r["u"],
                            y=r["y"], meta=meta, provenance=provenance, info=r.get("info") or {})
            sink(tr, r.get("truth") or {})
            n_ok += 1
    return {"ok": n_ok, "errors": errors}


def write_truth_one(root: Path, key: str, arrs: dict) -> None:
    arrs = {k: np.asarray(v) for k, v in (arrs or {}).items() if v is not None}
    if arrs:
        (root / "traj").mkdir(parents=True, exist_ok=True)
        np.savez_compressed(root / "traj" / f"{key}.npz", **arrs)


# ================================================================================================================ pools / lift cases
def pick_pool_states(src: list[dict], rng: np.random.Generator) -> list[dict]:
    """POOL_STATES states per pool source trajectory (light metadata dicts) at random samples in [0.2 T, 0.7 T]."""
    out = []
    for r in src:
        n = r["n"]
        lo, hi = int(0.2 * (n - 1)), int(0.7 * (n - 1))
        idx = sorted(rng.choice(np.arange(lo, max(lo + 1, hi)), size=min(POOL_STATES, max(1, hi - lo)), replace=False))
        for i in idx:
            out.append({"state_id": f"{r['key'][:16]}@{int(i)}", "key": r["key"], "store_key": r["store_key"], "index": int(i),
                        "t": float(r["t"][i]), "draw": str(r["draw"]), "params_seed": int(r["params_seed"]),
                        "weight_noise": r.get("weight_noise"), "params_spread": r.get("params_spread")})
    return out


def pool_future_protocol(pub: dict, st: dict, seq_events: list[dict], level: float, *, floor: bool = False) -> dict:
    """The restart of one pool state under one sequence, with the nominal input level held constant."""
    T = round(POOL_FUTURE_FRAC * float(pub["t_end_default"]), 9)
    dt = float(pub["dt"])
    n_u = int(pub.get("input_dim", 1))
    val = float(level) if n_u == 1 else [float(level)] * n_u
    stim = [[0.0, val]]
    if floor:
        stim.append([P.snap(T / 2 + dt, dt), val])
    p = {"system": pub["system_id"], "params_seed": int(st["params_seed"]), "weight_noise": st.get("weight_noise"),
         "r0": {"kind": "restart", "key": st["store_key"], "t": st["t"]}, "t_end": T, "dt": dt, "stimulus": stim,
         "events": json.loads(json.dumps(seq_events)), "obs_noise": None}
    if st.get("params_spread") is not None and protocol_has("params_spread"):
        p["params_spread"] = st["params_spread"]
    return p


def pick_lift_cases(src: list[dict], rng: np.random.Generator) -> list[dict]:
    out = []
    for j in range(N_LIFT_CASES):
        if not src:
            break
        r = src[j % len(src)]
        n = r["n"]
        i = int(rng.integers(int(0.2 * (n - 1)), max(int(0.2 * (n - 1)) + 1, int(0.5 * (n - 1)))))
        out.append({"case_id": f"lift{j:02d}", "key": r["key"], "store_key": r["store_key"], "index": i, "t": float(r["t"][i]),
                    "params_seed": int(r["params_seed"]), "weight_noise": r.get("weight_noise"), "stimulus": r["stimulus"]})
    return out


# ================================================================================================================ build one system
def _safe(sid: str) -> str:
    return sid.replace(":", "_")


def tier_dirs(tier: str, root: Path = SUITES) -> dict[str, Path]:
    """<root>/<tier>/public (the fit data; for the dev tier and the public real data ALSO the public evaluation subset: everything
    in it is simulatable under the public policy, so a room builder may copy it wholesale), <tier>/eval (orchestrator-held evaluation
    sets) and <tier>/truth (synthetic truth; never public)."""
    base = root / tier
    return {"base": base, "public": base / "public", "eval": base / "eval", "truth": base / "truth"}


def _graph_edges(pub: dict, n: int = 16) -> list:
    """The n strongest non-autapse edges (by |signed synapse count|) of the public connectivity summary whose ends are observed or
    public-target units (real systems; deterministic)."""
    g = pub.get("public_graph") or {}
    ok = {int(u) for u in (pub.get("observed") or [])} | {int(u) for u in (pub.get("targets_public") or [])}
    e = [r for r in (g.get("edges_post_pre_signed_count") or []) if int(r[0]) != int(r[1]) and int(r[0]) in ok and int(r[1]) in ok]
    e = sorted(e, key=lambda r: (-abs(float(r[2])), int(r[0]), int(r[1])))[:n]
    return [[int(a), int(b)] for a, b, _ in e]


def assert_public_policy(q: dict, pub: dict, allowed_restart_keys=()) -> None:
    """Every protocol of a public set (and of a public-policy evaluation set) must pass the simulation service's public policy."""
    from .simservice import check_public
    why = check_public(P.validate(q), pub, allowed_restart_keys=set(allowed_restart_keys))
    if why:
        raise AssertionError(f"public-policy violation in a public set of {pub['system_id']}: {why}")


N_EQUIV_STATES, N_EQUIV_PER_STATE = 20, 2


def build_system(pub: dict, internal: dict, *, tier: str, seed: int, level: str, run, dirs: dict[str, Path], dest: str = "eval",
                 sets=("tests", "pool_src"), policy: str = "full", with_truth: bool = True, truth_system=None,
                 store_root: Path | str = STORE) -> dict:
    """Plan, simulate and write one part of one system into dirs[dest]/<system>: records (D0 / D1 / validation and / or tests,
    twins, components, pool sources), pools (futures NPZ + JSON; under policy 'full', synthetic systems also get truth-equivalent
    states from the generator's `equivalent_states`) and lift cases. A PUBLIC part (dest 'public') or a public-policy part (policy
    'public') is checked protocol by protocol against the public policy (`assert_public_policy`): a violation aborts the build.
    `truth_system` = the generator's system object (synthetic only)."""
    sid = pub["system_id"]
    if dest == "public" and policy != "public" and set(sets) & {"tests", "pool_src"}:
        raise ValueError("a public part may only hold public-policy evaluation sets")
    check = dest == "public" or policy == "public"
    pool_state_fn = getattr(truth_system, "pool_states", None) if truth_system is not None else None
    specs = plan_system(pub, internal, tier=tier, seed=seed, level=level, sets=tuple(sets), pool_state_fn=pool_state_fn, policy=policy)
    if check:
        for sp in specs:
            assert_public_policy(sp.protocol, pub)
            if sp.twin:
                assert_public_policy(P.counterfactual(sp.protocol), pub)
            if sp.meta.get("components"):
                raise AssertionError("composition items are never public-policy items")
    ddir, tdir = dirs[dest] / _safe(sid), dirs["truth"] / _safe(sid)
    writer = SetWriter(ddir, sid, pub, f"{tier}:{sid}:{dest}")
    pool_src_meta: list[dict] = []
    lift_src: list[dict] = []

    def sink(tr, truth):
        writer.add(tr)
        if with_truth:
            write_truth_one(tdir, tr.key, truth)
        light = {"key": tr.key, "store_key": tr.meta["store_key"], "n": len(tr.t), "t": np.asarray(tr.t), "params_seed":
                 tr.protocol["params_seed"], "weight_noise": tr.protocol.get("weight_noise"), "stimulus": tr.protocol["stimulus"],
                 "params_spread": tr.protocol.get("params_spread")}
        if tr.split == "pool_src":
            pool_src_meta.append({**light, "draw": tr.meta.get("draw")})
        elif tr.split == "test" and tr.meta.get("role") == "passive":
            lift_src.append(light)

    res = run_specs(specs, pub, run, sink)
    errors = list(res["errors"])
    out = {"counts": {"planned": len(specs), "records": res["ok"], "errors": len(errors)}, "errors": errors[:50]}
    if "pool_src" in sets and pool_src_meta:
        rng = rng_of("pool-states", tier, seed, sid, policy)
        states = pick_pool_states(pool_src_meta, rng)
        targets = pub.get("targets_public") or internal.get("targetable") or []
        edges = [list(e) for e in (pub.get("edges_public") or [])] or ([] if policy == "public" else _graph_edges(pub))
        allowed = list(pub["split"]["families_train"]) if policy == "public" else None
        seqs = pool_sequences(pub, rng_of("pool-seq", tier, seed, sid), targets, edges, families_allowed=allowed)
        level_nom = FamilySampler(pub, rng, lambda: 0, targets=targets).level
        src_keys = {st["store_key"] for st in states}
        jobs, owners = [], []
        for si, st in enumerate(states):
            for name, sq in [("none", {"events": []})] + list(seqs.items()):
                p = pool_future_protocol(pub, st, sq["events"], level_nom)
                if check:
                    assert_public_policy(p, pub, allowed_restart_keys=src_keys)
                jobs.append((sid, p, {"role": "pool_future", "split": "pool", "no_store": True}))
                owners.append((si, name))
            if si < POOL_FLOOR_STATES:
                jobs.append((sid, pool_future_protocol(pub, st, [], level_nom, floor=True), {"role": "pool_floor", "split": "pool", "no_store": True}))
                owners.append((si, "floor"))
        equivs: list[dict] = []
        eq_fn = getattr(truth_system, "equivalent_states", None) if (truth_system is not None and policy != "public") else None
        if eq_fn is not None:
            from .store import TrajectoryStore
            store = TrajectoryStore(store_root)
            for si, st in enumerate(states[:N_EQUIV_STATES]):
                src = store.get(st["store_key"])
                if src is None or "state" not in src:
                    continue
                try:
                    eqs = list(eq_fn(np.asarray(src["state"][st["index"]], np.float64), N_EQUIV_PER_STATE, rng_of("equiv", tier, seed, sid, si)))
                except Exception as e:  # noqa: BLE001 - recorded, never silently dropped
                    errors.append({"role": "equivalent_states", "what": st["state_id"], "error": f"{type(e).__name__}: {e}"})
                    continue
                for j, vec in enumerate(eqs):
                    equivs.append({"of": st["state_id"], "si": si, "j": j, "r0": state_r0(vec)})
            for eq in equivs:
                st = states[eq["si"]]
                for name, sq in [("none", {"events": []})] + list(seqs.items()):
                    p = pool_future_protocol(pub, st, sq["events"], level_nom)
                    p["r0"] = eq["r0"]
                    jobs.append((sid, p, {"role": "pool_equiv", "split": "pool", "no_store": True}))
                    owners.append((f"e{eq['si']}_{eq['j']}", name))
        arrays: dict[str, np.ndarray] = {}
        n_med = round(HORIZON_FRACTIONS["medium"] * float(pub["t_end_default"]) / float(pub["dt"]))
        for c in range(0, len(jobs), CHUNK):
            for (si, name), r in zip(owners[c: c + CHUNK], run(jobs[c: c + CHUNK])):
                if "error" in r:
                    errors.append({"role": "pool_future", "what": name, "error": r["error"]})
                    continue
                tag = si if isinstance(si, str) else f"s{si}"
                arrays[f"{tag}_{name}_y"] = np.asarray(r["y"], np.float32)
                if name == "none":
                    # P4-D14: the observed microstate only for the no-intervention future, over the primary horizon
                    arrays[f"{tag}_none_x"] = np.asarray(r["x"], np.float32)[: n_med + 1]
                    if isinstance(si, str):
                        arrays[f"{tag}_none_u"] = np.asarray(r["u"], np.float32)[:1]
                if with_truth and r.get("truth", {}).get("z") is not None:
                    arrays[f"{tag}_{name}_z"] = np.asarray(r["truth"]["z"], np.float32)
        (ddir / "pools").mkdir(parents=True, exist_ok=True)
        np.savez_compressed(ddir / "pools" / "futures.npz", **arrays)
        (ddir / "pools" / "pool.json").write_text(json.dumps({"states": states, "sequences": seqs, "level": level_nom,
                                                              "future_s": POOL_FUTURE_FRAC * float(pub["t_end_default"]), "policy": policy,
                                                              "equivalents": [{k: v for k, v in e.items() if k != "r0"} for e in equivs]},
                                                             indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        out["counts"]["pool_states"] = len(states)
        out["counts"]["pool_equivalents"] = len(equivs)
        out["counts"]["pool_sequences"] = sorted(seqs)
        out["counts"]["pool_bytes"] = int(sum((ddir / "pools" / f).stat().st_size for f in ("futures.npz", "pool.json")))
    if "tests" in sets:
        (ddir / "lift_cases.json").write_text(json.dumps(pick_lift_cases(lift_src, rng_of("lift", tier, seed, sid, policy)), indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
    writer.close({"part": dest, "policy": policy, "tier": tier})
    out["counts"]["errors"] = len(errors)
    out["errors"] = errors[:50]
    return out


# ================================================================================================================ evaluation inputs
def _truth_arrays(truth_dir: Path | None, key: str) -> dict:
    if truth_dir is None:
        return {}
    p = truth_dir / "traj" / f"{key}.npz"
    if not p.exists():
        return {}
    with np.load(p) as z:
        return {k: z[k] for k in z.files}


def eval_system_from_public(pub: dict, public_set) -> object:
    """The evaluator's per-system constants (normalisers) from the system's PUBLIC training records."""
    from .evalio import make_eval_system
    rows = [r for r in public_set.rows if r.get("split") == "train"] if hasattr(public_set, "rows") else None
    if rows is not None:
        train = [public_set.load(r) for r in rows]
    else:
        train = [r for r in public_set.records if r.split == "train"]
    compact = not (pub["kind"] == "real" and pub.get("mode") == "mech")
    return make_eval_system(pub["system_id"], pub["kind"], float(pub["dt"]), float(pub["t_end_default"]), [r.x for r in train],
                            [r.y for r in train], int(pub.get("input_dim", 1)), lineage=pub.get("lineage"), compact=compact)


def items_from_set(pub: dict, held, truth_dir: Path | None = None, *, horizon: str = "long", roles: tuple[str, ...] | None = None) -> list:
    """evalio.TestItem objects of one system (from a lazily loaded held-out set): intervention items with their twins (and
    composition components) and passive windows at the fixed onsets. Futures use the NOISE-FREE readout where the truth store has
    it. `roles` restricts to some roles (e.g. ('in', 'passive'))."""
    from .data import LazyExperimentSet
    from .evalio import TestItem
    if not isinstance(held, LazyExperimentSet):
        raise TypeError("items_from_set needs a lazily loaded set (ExperimentSet.load(dir, lazy=True))")
    T = float(pub["t_end_default"])
    rows = held.rows
    twins = {r["meta"].get("twin_of"): r for r in rows if r.get("split") == "twin" and (r.get("meta") or {}).get("twin_of")}
    comps: dict[str, dict] = {}
    for r in rows:
        m = r.get("meta") or {}
        if r.get("split") == "component" and m.get("component_of"):
            comps.setdefault(m["component_of"], {})[m.get("component")] = r
    items = []
    for row in rows:
        if row.get("split") != "test":
            continue
        role = (row.get("meta") or {}).get("role", "in")
        if roles is not None and role not in roles:
            continue
        r = held.load(row)
        dt = float(r.protocol["dt"])
        H = round(HORIZON_FRACTIONS[horizon] * T / dt)
        tr = _truth_arrays(truth_dir, r.key)
        y_true = np.asarray(tr.get("y_clean", r.y), np.float64)
        zt = tr.get("z")
        zo = tr.get("z_obs")
        if not r.protocol.get("events"):
            for j, fr in enumerate(PASSIVE_ONSETS):
                i0 = round(fr * T / dt)
                h = min(H, len(r.t) - 1 - i0)
                if h < 1:
                    continue
                items.append(TestItem(item_id=f"{r.key[:20]}@p{j}", system_id=r.system_id, dt=dt, x_hist=r.x[: i0 + 1], u_hist=r.u[: i0 + 1],
                                      u_future=r.u[i0: i0 + h + 1], events=[], y_future=y_true[i0: i0 + h + 1], y_twin=None, family=r.family,
                                      shift="passive", onset=float(r.t[i0]), group=r.key, x_future=r.x[i0: i0 + h + 1],
                                      z_true=(zt[i0] if zt is not None else None), z_obs=(zo[i0] if zo is not None else None),
                                      meta={"key": r.key, "store_key": r.meta.get("store_key")}))
            continue
        trow = twins.get(r.key)
        if trow is None:
            continue
        tw = held.load(trow)
        told = r.meta.get("model_events") or r.protocol["events"]
        onset = min(min(P.event_start(e) for e in r.protocol["events"]), min(P.event_start(e) for e in P.validate(
            dict(r.protocol, events=told))["events"]))
        i0 = round(onset / dt)
        h = min(H, len(r.t) - 1 - i0)
        if h < 1:
            continue
        ttw = _truth_arrays(truth_dir, tw.key)
        ytw = np.asarray(ttw.get("y_clean", tw.y), np.float64)
        t0 = float(r.t[i0])
        comp_d = None
        if r.key in comps and {"a", "b"} <= set(comps[r.key]):
            comp_d = {}
            for part, crow in comps[r.key].items():
                cr = held.load(crow)
                cy = np.asarray(_truth_arrays(truth_dir, cr.key).get("y_clean", cr.y), np.float64)
                comp_d[part] = {"events": relative_events(P.validate(cr.protocol)["events"], t0), "y_future": cy[i0: i0 + h + 1]}
        # dz_true (the exact true latent effect of the first instantaneous event) is left to evaluate_truth.attach_truth, which
        # computes it with the generator from meta["state"] (harness.attach_states)
        dz = None
        told_rel = relative_events(P.validate(dict(r.protocol, events=told))["events"], t0)
        items.append(TestItem(item_id=r.key[:24], system_id=r.system_id, dt=dt, x_hist=r.x[: i0 + 1], u_hist=r.u[: i0 + 1],
                              u_future=r.u[i0: i0 + h + 1], events=told_rel, y_future=y_true[i0: i0 + h + 1], y_twin=ytw[i0: i0 + h + 1],
                              family=r.family, shift=role, magnitude_class=r.meta.get("mclass", "na"),
                              target_set=tuple(int(u) for u in r.meta.get("target_set") or ()), onset=t0, group=r.key,
                              x_future=r.x[i0: i0 + h + 1], x_twin_future=tw.x[i0: i0 + h + 1],
                              true_events=(relative_events(r.protocol["events"], t0) if r.meta.get("model_events") else None),
                              components=comp_d, z_true=(zt[i0] if zt is not None else None), z_obs=(zo[i0] if zo is not None else None),
                              dz_true=dz, meta={"key": r.key, "twin": tw.key, "cell": r.meta.get("cell"), "proxy": bool(r.meta.get("proxy")),
                                                "store_key": r.meta.get("store_key"), "twin_store_key": tw.meta.get("store_key"),
                                                "params_seed": r.protocol["params_seed"]}))
    return items


def pool_from_files(pub: dict, held, hdir: Path, truth_dir: Path | None = None):
    """evalio.Pool of one system."""
    from .evalio import Pool, PoolState
    jpath = hdir / "pools" / "pool.json"
    if not jpath.exists():
        return None
    meta = json.loads(jpath.read_text(encoding="utf-8"))
    by_key = {r["key"]: r for r in held.rows}
    dt = float(pub["dt"])
    n_u = int(pub.get("input_dim", 1))
    fut_T = round(float(meta["future_s"]) / dt)
    u_future = np.full((fut_T + 1, n_u), float(meta["level"]))
    seqs = {"none": {"events": [], "u_future": u_future, "family": "none", "kind": "none"}}
    for name, sq in meta["sequences"].items():
        seqs[name] = {"events": sq["events"], "u_future": u_future, "family": sq["family"], "kind": sq["kind"]}
    with np.load(hdir / "pools" / "futures.npz") as z:
        arr = {k: z[k] for k in z.files}
    states, floors = [], []
    cache: dict[str, object] = {}
    for si, st in enumerate(meta["states"]):
        row = by_key.get(st["key"])
        if row is None or f"s{si}_none_y" not in arr:
            continue
        if st["key"] not in cache:
            cache[st["key"]] = held.load(row)
        r = cache[st["key"]]
        i = int(st["index"])
        futures = {name: arr[f"s{si}_{name}_y"].astype(np.float64) for name in seqs if f"s{si}_{name}_y" in arr}
        xfut = {name: arr[f"s{si}_{name}_x"].astype(np.float64) for name in seqs if f"s{si}_{name}_x" in arr}
        fd = None
        if f"s{si}_floor_y" in arr:
            fd = float(np.sqrt(np.mean((arr[f"s{si}_floor_y"].astype(np.float64) - futures["none"]) ** 2)))
            floors.append(fd)
        tr = _truth_arrays(truth_dir, r.key)
        has_eq = any(e["si"] == si for e in meta.get("equivalents") or [])
        states.append(PoolState(state_id=st["state_id"], x_hist=r.x[: i + 1], u_hist=r.u[: i + 1], y_now=np.asarray(r.y[i], np.float64),
                                traj=r.key, draw=str(st["draw"]), futures=futures, x_futures=xfut,
                                z_true=(tr["z"][i] if "z" in tr else None), z_obs=(tr["z_obs"][i] if "z_obs" in tr else None),
                                equiv_class=(st["state_id"] if has_eq else None), floor_div=fd,
                                meta={"store_key": st["store_key"], "t": st["t"], "params_seed": st["params_seed"]}))
    # truth-equivalent states (synthetic): same TRUE causal state as their source pool state; no history exists, so x_hist is the
    # single observed sample at the state and meta['truth_only'] marks them: never matched by a model's latent (reference only)
    for e in meta.get("equivalents") or []:
        tag = f"e{e['si']}_{e['j']}"
        if f"{tag}_none_y" not in arr:
            continue
        src = meta["states"][e["si"]]
        futures = {name: arr[f"{tag}_{name}_y"].astype(np.float64) for name in seqs if f"{tag}_{name}_y" in arr}
        xfut = {name: arr[f"{tag}_{name}_x"].astype(np.float64) for name in seqs if f"{tag}_{name}_x" in arr}
        x0 = arr[f"{tag}_none_x"][:1].astype(np.float64)
        u0 = arr[f"{tag}_none_u"][:1].astype(np.float64) if f"{tag}_none_u" in arr else u_future[:1]
        z0 = arr[f"{tag}_none_z"][0].astype(np.float64) if f"{tag}_none_z" in arr else None
        states.append(PoolState(state_id=f"{src['state_id']}~eq{e['j']}", x_hist=x0, u_hist=u0, y_now=futures["none"][0], traj=f"equiv:{src['key']}",
                                draw=str(src["draw"]), futures=futures, x_futures=xfut, z_true=z0, equiv_class=src["state_id"],
                                meta={"truth_only": True, "equiv_of": src["state_id"]}))
    return Pool(system_id=pub["system_id"], dt=dt, states=states, sequences=seqs, floor_div=(float(np.mean(floors)) if floors else None),
                meta={"future_s": float(meta["future_s"]), "n_truth_only": sum(1 for s in states if s.meta.get("truth_only")),
                      "x_futures": "no-intervention future only, over the primary horizon (P4-D14)"})


def truth_samples(pub: dict, held, truth_dir: Path | None) -> list:
    """evalio.StateSample list (synthetic latent recovery): N_TRUTH_SAMPLES encoding points per passive test trajectory."""
    from .evalio import StateSample
    if truth_dir is None:
        return []
    out = []
    for row in held.rows:
        if row.get("split") != "test" or (row.get("protocol") or {}).get("events"):
            continue
        tr = _truth_arrays(truth_dir, row["key"])
        if "z" not in tr:
            continue
        r = held.load(row)
        n = len(r.t)
        for i in np.linspace(int(0.1 * (n - 1)), n - 2, N_TRUTH_SAMPLES).astype(int):
            out.append(StateSample(sample_id=f"{r.key[:16]}@{int(i)}", x_hist=r.x[: i + 1], u_hist=r.u[: i + 1], dt=float(r.protocol["dt"]),
                                   group=r.key, z_true=tr["z"][i], z_obs=(tr["z_obs"][i] if "z_obs" in tr else None)))
    return out


def load_eval_inputs(sid: str, *, heldout_dirs: dict[str, Path], public_dirs: dict[str, Path] | None = None, part: str = "eval",
                     roles: tuple[str, ...] | None = None) -> dict:
    """Everything the evaluator needs for one system: {"record", "system" (EvalSystem), "public" (lazy set), "items", "pool",
    "samples", "lift_cases", "heldout" (the lazy evaluation set)}. `heldout_dirs` = tier_dirs() of the tier holding the evaluation
    sets, `part` = its 'eval' (orchestrator-held) or 'public' (the public evaluation subset of the dev tier / public real data);
    `public_dirs` = tier_dirs() of the tier holding the public training data (the same tier for synthetic systems; the public real
    tier for real systems)."""
    from .data import ExperimentSet
    pd = (public_dirs or heldout_dirs)["public"] / _safe(sid)
    hd = heldout_dirs[part] / _safe(sid)
    td = heldout_dirs["truth"] / _safe(sid)
    pub_set = ExperimentSet.load(pd, lazy=True)
    held = ExperimentSet.load(hd, lazy=True)
    pub = held.systems.get(sid) or pub_set.systems[sid]
    truth_dir = td if td.exists() else None
    lc = hd / "lift_cases.json"
    return {"record": pub, "system": eval_system_from_public(pub, pub_set), "public": pub_set, "heldout": held,
            "items": items_from_set(pub, held, truth_dir, roles=roles), "pool": pool_from_files(pub, held, hd, truth_dir),
            "samples": truth_samples(pub, held, truth_dir),
            "lift_cases": json.loads(lc.read_text(encoding="utf-8")) if lc.exists() else []}


# ================================================================================================================ tier builds
def _synthetic_systems(tier: str, seed: int, generator: tuple | None) -> dict:
    from .synthadapter import register_generator, suite_systems
    if generator is not None:
        register_generator(generator[0], generator[1])
    return suite_systems(tier if tier != "toyC" else "toy", int(seed))


def synthetic_tier_records(tier: str, seed: int, generator: tuple | None = None) -> tuple[dict, dict, dict]:
    """(public records, internal records, truth summaries) of a synthetic tier (rotations assigned, targets partitioned)."""
    systems = _synthetic_systems(tier, seed, generator)
    info, truths = {}, {}
    for sid, s in systems.items():
        pr = s.public_record()
        tr = s.truth() or {}
        truths[sid] = {k: v for k, v in tr.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
        info[sid] = {"type": tr.get("type", sid), "capability": normalize_capability(pr.get("capability"), t_end=float(pr["t_end_default"]),
                                                                                      dt=float(pr["dt"]), input_dim=int(pr.get("input_dim", 1)))}
    rots = assign_rotations(info, seed)
    pubs, ints = {}, {}
    for sid, s in systems.items():
        pubs[sid], ints[sid] = synthetic_records(s.public_record(), tier=tier, seed=seed, rotation=rots[sid], system_hash=s.content_hash(),
                                                 engine_id=s.engine_id)
        ints[sid]["tier"] = tier if tier != "toyC" else "toy"
        ints[sid]["tier_seed"] = int(seed)
        ints[sid]["suite_seed"] = int(seed)          # the simulation service's name for it
    return pubs, ints, truths


#: the parts of each build: (dest, sets, policy). The dev tier's public part and the public real data are the only material that may
#: enter a room; every protocol in them passes the public policy (asserted at build time).
TIER_PARTS = {
    "dev": (("public", ("public", "tests", "pool_src"), "public"), ("eval", ("tests", "pool_src"), "full")),
    "toy": (("public", ("public", "tests", "pool_src"), "public"), ("eval", ("tests", "pool_src"), "full")),
    "toyC": (("public", ("public",), "public"), ("eval", ("tests", "pool_src"), "full")),
    "val": (("public", ("public",), "public"), ("eval", ("tests", "pool_src"), "full")),
    "conf": (("public", ("public",), "public"), ("eval", ("tests", "pool_src"), "full")),
}
REAL_PARTS = {
    "public": (("public", ("public", "tests", "pool_src"), "public"),),
    "B": (("eval", ("tests", "pool_src"), "public"),),
    "C": (("eval", ("tests", "pool_src"), "full"),),
}


def build_tier(tier: str, *, generator: tuple | None = None, workers: int = 4, systems: list[str] | None = None, root: Path = SUITES,
               store_root: Path = STORE, run=None, parts=None) -> dict:
    """Build a synthetic tier: 'dev' / 'val' (before development), 'conf' (after the lock only); 'toy' / 'toyC' = the adapter's toy
    systems (tests). Parts per tier: TIER_PARTS."""
    if tier == "conf":
        require_lock("the confirmation tier")
    seed = tier_seed(tier)
    pubs, ints, truths = synthetic_tier_records(tier, seed, generator)
    objs = _synthetic_systems(tier, seed, generator)
    sids = sorted(pubs) if not systems else [s for s in sorted(pubs) if s in set(systems)]
    level = LEVEL_OF_TIER.get(tier, "B")
    dirs = tier_dirs(tier, root)
    backend = LocalBackend(ints, tier=tier, seed=seed, generator=generator, store_root=store_root, workers=workers) if run is None else None
    runner = run or backend.run
    summary = {"tier": tier, "level": level, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": {}}
    try:
        for sid in sids:
            summary["systems"][sid] = {}
            for dest, sets, policy in (parts or TIER_PARTS[tier]):
                built = build_system(pubs[sid], ints[sid], tier=tier, seed=seed, level=level, run=runner, dirs=dirs, dest=dest, sets=sets,
                                     policy=policy, truth_system=objs[sid], store_root=store_root)
                summary["systems"][sid][dest] = built["counts"]
                if built["errors"]:
                    summary["systems"][sid][dest]["first_errors"] = built["errors"][:5]
    finally:
        if backend is not None:
            backend.close()
    dirs["base"].mkdir(parents=True, exist_ok=True)
    dirs["truth"].mkdir(parents=True, exist_ok=True)
    (dirs["base"] / "internal_records.json").write_text(json.dumps(ints, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (dirs["truth"] / "systems_truth.json").write_text(json.dumps(truths, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8",
                                                      newline="\n")
    (dirs["base"] / "build_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return summary


REAL_TIERS = {"public": "real_public", "B": "real_levelb", "C": "real_hidden"}


def build_real(level: str, *, workers: int = 4, systems: list[str] | None = None, root: Path = REAL_SETS, store_root: Path = STORE,
               run=None) -> dict:
    """Real systems: level 'public' (D0 / D1 / validation and the public evaluation subset: the public development data), 'B' (the
    Level B validation sets, drawn under the PUBLIC policy with public seeds; orchestrator-held) or 'C' (the hidden test with every
    shift, OOD and robustness set; after the lock only; hidden-range seeds from the salt)."""
    from .systems import load_real_internal, public_view
    if level == "C":
        require_lock("the real hidden test")
    internals = load_real_internal()
    sids = sorted(internals) if not systems else [s for s in sorted(internals) if s in set(systems)]
    tier = REAL_TIERS[level]
    backend = LocalBackend(internals, tier=tier, seed=0, generator=None, store_root=store_root, workers=workers) if run is None else None
    runner = run or backend.run
    out = {"level": level, "tier": tier, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": {}}
    dirs = tier_dirs(tier, root)
    try:
        for sid in sids:
            out["systems"][sid] = {}
            for dest, sets, policy in REAL_PARTS[level]:
                built = build_system(public_view(internals[sid]), internals[sid], tier=tier, seed=0, level=("C" if level == "C" else "B"),
                                     run=runner, dirs=dirs, dest=dest, sets=sets, policy=policy, with_truth=True, store_root=store_root)
                out["systems"][sid][dest] = built["counts"]
                if built["errors"]:
                    out["systems"][sid][dest]["first_errors"] = built["errors"][:5]
    finally:
        if backend is not None:
            backend.close()
    dirs["base"].mkdir(parents=True, exist_ok=True)
    (dirs["base"] / "build_summary.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return out


def plan_counts(pub: dict, internal: dict, *, tier: str, seed: int, level: str, sets=("public", "tests", "pool_src"),
                policy: str = "full") -> dict:
    """Planned trajectory counts per role (no simulation), for cost estimates."""
    specs = plan_system(pub, internal, tier=tier, seed=seed, level=level, sets=tuple(sets), policy=policy)
    counts: dict[str, int] = {}
    total = 0
    for sp in specs:
        n = 1 + int(sp.twin) + (2 if sp.meta.get("components") else 0)
        counts[sp.role.split(":")[0]] = counts.get(sp.role.split(":")[0], 0) + n
        total += n
    if "pool_src" in sets:
        kinds = [k for k, _ in SEQ_KINDS if (pub.get("capability") or {}).get(k, {}).get("supported")]
        if policy == "public":
            train = set(pub["split"]["families_train"])
            kinds = [k for k, f in SEQ_KINDS if k in kinds and f in train]
        counts["pool_futures"] = POOL_DRAWS * POOL_TRAJ * POOL_STATES * (1 + len(kinds)) + POOL_FLOOR_STATES
        total += counts["pool_futures"]
    counts["total_trajectories"] = total
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build causal_state_v1 datasets (orchestrator side).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("synthetic")
    b.add_argument("--tier", required=True, choices=("dev", "val", "conf", "toy", "toyC"))
    b.add_argument("--generator-dir", default="")
    b.add_argument("--generator-package", default="p4synth")
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--systems", default="")
    r = sub.add_parser("real")
    r.add_argument("--level", required=True, choices=("public", "B", "C"))
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--systems", default="")
    args = ap.parse_args(argv)
    sel = [x for x in args.systems.split(",") if x] or None
    if args.cmd == "synthetic":
        gen = (args.generator_dir, args.generator_package) if args.generator_dir else None
        s = build_tier(args.tier, generator=gen, workers=args.workers, systems=sel)
    else:
        s = build_real(args.level, workers=args.workers, systems=sel)
    print(json.dumps(s, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
