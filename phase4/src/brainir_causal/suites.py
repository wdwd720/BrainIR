"""Benchmark datasets of `causal_state_v1` (ORCHESTRATOR SIDE; benchmarks/causal_state_v1/PROTOCOL.md sections 2-4).

What this module fixes (frozen with the benchmark):

SEEDS. The dev tier uses the PUBLIC seed `DEV_SEED`; the `val` and `conf` synthetic tiers and every hidden protocol seed derive from
the SECRET salt (`data/phase4/hidden/salt.txt`, git-ignored), committed by sha256 in `benchmarks/causal_state_v1/hidden/
salt_commitment.json` before any method existed, by HMAC-SHA256: the val / conf tier seeds have 128 bits (`tier_seed`), the real
Level B / hidden parts get 128-bit stream seeds (`real_stream_seed`; the public real data keeps 0), and every public-range seed of a
SALTED tier (val, conf, real_levelb, real_levelc: their public parts included) is `salted_public_seed`, so nothing of them can be
regenerated from the public code (review F, M6). Development-policy protocols (dev tier, public real data, the real Level B
validation sets, D0 / D1 / validation data of every tier) draw parameter and noise seeds in [0, 10^9); held-out sets of the `val`
and `conf` tiers and the real hidden sets draw in [10^9, 2 x 10^9) (`hidden_seed`), which the simulation service refuses. The
intervention sequences of every NON-public pool come from a salted stream (`pool_seq_seed_of`; review F, minor 8). The
confirmation tier and the real hidden sets are generated only after the method lock (`require_lock`). Each planned trajectory
carries N_SPARE_SEEDS replacement parameter seeds of its own stream: a failed or non-finite simulation is never stored and is
replaced under the rule of `add_spares` (review H, M4; failures per family in the build summary).

PUBLIC FILES (review F, B1 / minor 7): whitelists (`PUBLIC_*_KEYS`, `PUBLIC_FUTURE_KEY`) for system records, rows, meta, info, pool
and lift files; truth (incl. the true latents of pool futures) only under <tier>/truth/; `assert_public_part` checks a built public
part file by file. Development dt = the nominal dt (review H, M3); the temporal-sampling OOD items are simulated at the nominal dt
and recorded at every second sample. Test items are grouped by IDENTITY CELL for resampling (review E, M2).

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
- D0 passive (split 'train'): 8 nominal trajectories over parameter draws 0-7, 16 stimulus schedules, 8 'obs.init' trajectories
  (each a RESTART from a sample time of one of the nominal trajectories, with its parameter draw; LOG P4-D36: an explicit initial
  state is a kick at t = 0 and never a development protocol), 8 weight-noise draws;
- D1 reference interventions (split 'train'): B_main = 200 (real full networks 120) intervention trajectories drawn uniformly over
  families_train x public targets x magnitude classes x onsets, each with its counterfactual twin (split 'twin', meta twin_of);
- public validation (split 'val' + twins): 20 % more of D0 and D1;
- tests (split 'test', each intervention item with its twin): per family 2 IDENTITY CELLS (a target set and a magnitude class) x 4
  STATES (new parameter draw, stimulus level and onset) = 8 items: in-family (families_train, public targets), target shift
  (families_train, hidden targets), family shift (families_heldout, public targets; role near / far), hidden-only (public targets);
  composition items also simulate each component alone (split 'component', meta component_of); Level C adds OOD (section 4.1) and
  robustness (section 4.2); 16 passive test trajectories;
- pools (P4-D14): 8 parameter draws x 15 source trajectories (split 'pool_src'; the first of each draw nominal, its 'init' sources
  restarts from it) x 5 sample times = 600 states, each a time point of
  a stored held-out trajectory (its history is that trajectory's past); futures (25 % of T) simulated from restarts of the stored
  microstate under the nominal input level (shared by every state), with no intervention and under one fixed sequence per supported
  event kind; stored as readouts, plus the observed microstate over the primary horizon and the simulated input for the
  no-intervention future only; 20 floor states (of 'init' sources) add the numerical-floor futures of review H, B1 (FLOOR_DOC: a
  repeat with a no-op breakpoint one sample after the restart; a restart from the float32-rounded state and the float64
  continuation); synthetic systems add truth-equivalent states (the generator's `equivalent_states`, 2 for each of 20 pool states;
  excluded from model pairing, reference only);
- lift cases: 16 states of the passive test trajectories (histories, restart keys).

OOD and ROBUSTNESS (Level C). 'altered initial conditions' = a state-carrier start from the full microstate of a same-draw nominal
trajectory with half the observed units displaced by twice the development kick maximum (`resolve_carrier_start`; LOG P4-D36);
'parameter spread' = `params_spread` 1.5; 'parameter noise' = `params_spread` 1.5 and 2.0 (hidden-range
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
import hmac
import json
import math
import os
import re
import shutil
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path, PurePosixPath

import numpy as np

from . import families as F
from . import protocol as P
# the public-policy sampler and the capability rules live in the PUBLIC module `sampling` (model workers and method rooms import
# it; this orchestrator module does not ship to them; review H round 3, NEW-3)
from .sampling import (EDGE_DEPTH_MAX, HIDDEN_SEED_BASE, HORIZON_FRACTIONS, INIT_T_FRAC, JITTER, MAG_CLASSES, MAG_MULT,  # noqa: F401
                       N_TARGETS_NEEDED, ONSET_FRAC, P_PERSIST, FamilySampler, Spec, _runs, _shift_events, class_value, feasible,
                       intervention_families, moderate_value, normalize_capability, per_unit_lists, public_seed_of, relative_events)

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
TIERS = ("dev", "val", "conf", "trap")         # "trap": review G's new trap systems (synthadapter.TRAP_TIER; hidden, after the lock)
HIDDEN_TIERS = ("val", "conf", "trap", "real_levelc")
LOCKED_TIERS = ("conf", "trap")                  # built only after the method lock
N_PER_TYPE = {"dev": 2, "val": 2, "conf": 3}
LEVEL_OF_TIER = {"dev": "B", "val": "B", "conf": "C", "trap": "C", "toy": "B", "toyC": "C"}

POOL_FUTURE_FRAC = 0.25

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
TIER_SEED_HEX = 32                      # 128-bit tier / stream seeds (review F, M6)
#: tiers whose every stream (and public-range seed) is salted: nothing of them is derivable from the public code (review F, M6 / minor 8)
SALTED_TIERS = ("val", "conf", "trap", "real_levelb", "real_levelc")
N_SPARE_SEEDS = 3                       # replacement parameter seeds per planned trajectory (failed simulations; review H, M4)

# ------------------------------------------------------------------ what PUBLIC files may hold (whitelists; review F, B1 / minor 7)
#: keys of a public system record (synthetic: the generator's pass-through keys are GENERATOR_PUBLIC_KEYS only)
PUBLIC_RECORD_KEYS = frozenset({"system_id", "kind", "mode", "dt", "t_end_default", "horizons_s", "targets_public", "edges_public",
                                "capability", "split", "cost_units", "public_graph", "n_units", "observed", "readout", "readout_dim",
                                "input_dim", "stimulus", "members", "obs_scale", "lineage"})
GENERATOR_PUBLIC_KEYS = ("n_units", "observed", "readout", "readout_dim", "input_dim", "stimulus", "obs_scale", "lineage")
PUBLIC_ROW_KEYS = frozenset({"key", "system_id", "split", "family", "protocol", "meta", "provenance", "info"})
PUBLIC_META_KEYS = frozenset({"role", "mclass", "target_set", "cell", "state", "store_key", "onset", "edges", "twin_of", "draw", "traj",
                              "source", "family_planned", "replaced"})
#: engine bookkeeping that may enter any dataset row (real engine: never the network, its size or the bundle; synthetic: never the
#: generator's engine string, which may name the type)
PUBLIC_INFO_KEYS = ("engine", "n_calls", "n_pieces", "success", "kicks_applied", "host")      # never "simulator" (LOG P4-D26)
#: synthetic rows never carry realized kick sizes: clipping reveals where a unit's admissible bound lies (review T, M1); the realized
#: sizes stay orchestrator side (meta of the non-public parts; LOG P4-D36)
SYNTHETIC_INFO_KEYS = ("n_calls", "n_pieces", "success", "host")
#: meta keys of the plan that never enter a dataset row (dependency bookkeeping; carriers hold microstates)
PLAN_ONLY_META = ("components", "carrier", "src_id", "restart_from", "carrier_from")
PUBLIC_MANIFEST_KEYS = frozenset({"format", "dataset_id", "systems", "part", "policy", "tier"})
PUBLIC_POOL_KEYS = frozenset({"states", "sequences", "level", "future_s", "policy", "equivalents", "floor_states", "floors"})
PUBLIC_POOL_STATE_KEYS = frozenset({"state_id", "key", "store_key", "index", "t", "draw", "params_seed", "weight_noise", "params_spread",
                                    "source"})
PUBLIC_LIFT_KEYS = frozenset({"case_id", "key", "store_key", "index", "t", "params_seed", "weight_noise", "stimulus"})
POOL_FUTURE_NAMES = ("none",) + tuple(k for k, _ in SEQ_KINDS) + ("floor", "r32", "cont")
PUBLIC_FUTURE_KEY = re.compile(r"^s\d+_(" + "|".join(POOL_FUTURE_NAMES) + r")_(y|x|u)$")
PUBLIC_TRAJ_ARRAYS = frozenset({"t", "x", "u", "y"})


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


def _hmac_hex(salt: str, *parts) -> str:
    """HMAC-SHA256 of the parts under the salt (hex)."""
    return hmac.new(salt.encode(), "|".join(str(p) for p in parts).encode(), hashlib.sha256).hexdigest()


def tier_seed(tier: str, *, salt: str | None = None) -> int:
    """The generator / stream seed of a synthetic tier: the PUBLIC `DEV_SEED` for dev, toy and toyC; for val and conf a 128-bit
    HMAC-SHA256(salt, tier) (review F, M6: a 32-bit seed is recoverable by brute force from public parameter seeds)."""
    if tier in ("dev", "toy", "toyC"):
        return DEV_SEED
    if tier not in TIERS:
        raise ValueError(f"unknown synthetic tier {tier!r}")
    return int(_hmac_hex(read_salt() if salt is None else salt, "synthetic-tier", tier)[:TIER_SEED_HEX], 16)


def real_stream_seed(level: str, *, salt: str | None = None) -> int:
    """The stream seed of a real part: 0 (public) for the public real data; a 128-bit HMAC-SHA256(salt, tier) for the Level B
    validation sets and the hidden test, so their protocols cannot be derived from the public code (their parameter seeds stay in the
    range each part's policy requires)."""
    if level == "public":
        return 0
    return int(_hmac_hex(read_salt() if salt is None else salt, "real-tier", REAL_TIERS[level])[:TIER_SEED_HEX], 16)


def hidden_seed(*parts, salt: str | None = None) -> int:
    """A parameter / noise seed in the hidden range [10^9, 2 x 10^9): HMAC-SHA256(salt, parts)."""
    s = read_salt() if salt is None else salt
    return HIDDEN_SEED_BASE + int(_hmac_hex(s, "hidden-seed", *parts)[:16], 16) % HIDDEN_SEED_BASE


def salted_public_seed(*parts, salt: str | None = None) -> int:
    """A PUBLIC-range seed [0, 10^9) that only the salt holder can derive: HMAC-SHA256(salt, parts) (public parts of the hidden tiers
    and the orchestrator-held public-policy sets; review F, M6)."""
    s = read_salt() if salt is None else salt
    return int(_hmac_hex(s, "public-seed", *parts)[:16], 16) % HIDDEN_SEED_BASE


def salted_stream_seed(*parts, salt: str | None = None) -> int:
    """A 128-bit stream seed from the salt (e.g. the evaluation pools' intervention sequences, review F minor 8); computed where the
    salt is and handed to remote builds as a number."""
    return int(_hmac_hex(read_salt() if salt is None else salt, "stream", *parts)[:TIER_SEED_HEX], 16)


def rng_of(*parts) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16], 16))


def seed_counter(hidden: bool, *parts, salted: bool = False):
    """A counter-based seed function: public-range seeds (unsalted, or `salted`: derivable only with the salt), or hidden-range seeds
    derived from the salt."""
    counter = [0]
    salt = read_salt() if (hidden or salted) else None

    def fn() -> int:
        counter[0] += 1
        if hidden:
            return hidden_seed(*parts, counter[0], salt=salt)
        if salted:
            return salted_public_seed(*parts, counter[0], salt=salt)
        return public_seed_of(*parts, counter[0])
    return fn


def seed_of_fn(hidden: bool, salted: bool):
    """A seed function of explicit parts with the same salting rule as `seed_counter`."""
    if hidden or salted:
        salt = read_salt()
        return (lambda *p: hidden_seed(*p, salt=salt)) if hidden else (lambda *p: salted_public_seed(*p, salt=salt))
    return public_seed_of


def locked() -> bool:
    return METHOD_LOCK.exists()


def require_lock(what: str) -> None:
    if not locked():
        raise PermissionError(f"{what} is generated only after the method lock (research/phase4/METHOD_LOCK.json is missing)")


# ================================================================================================================ capability


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


#: the keys under which a synthetic system's public record lists EVERY targetable unit: the generator's `targets`
#: (p4synth System.public_record) and the unit-test systems' `targetable`. A record with neither, with both disagreeing, or with an
#: empty set is refused: never a fallback to the observed units, which made the hidden targets = observed - public targets
#: (review F round 3b, NF-1)
TARGETABLE_KEYS = ("targets", "targetable")


def generator_targetable(pub: dict) -> list[int]:
    """The generator's targetable units of a synthetic public record (sorted, unique, within 0..n_units-1); ValueError otherwise."""
    sid = pub.get("system_id")
    vals = [sorted({int(u) for u in pub[k]}) for k in TARGETABLE_KEYS if pub.get(k) is not None]
    if not vals:
        raise ValueError(f"{sid}: the generator's public record lists no targetable units (keys {TARGETABLE_KEYS})")
    if any(v != vals[0] for v in vals[1:]):
        raise ValueError(f"{sid}: the generator's public record lists two different targetable sets")
    units = vals[0]
    if not units:
        raise ValueError(f"{sid}: the generator's targetable set is empty")
    n = pub.get("n_units")
    if n is not None and not all(0 <= u < int(n) for u in units):
        raise ValueError(f"{sid}: targetable units outside 0..{int(n) - 1}")
    return units


def synthetic_records(pub: dict, *, tier: str, seed: int, rotation: dict, system_hash: str, engine_id: str) -> tuple[dict, dict]:
    """(public record, internal record) of a synthetic system from the generator's public record (which lists every targetable
    unit and scalable edge): targets / edges partitioned, capability normalised, split added. The public record never lists the
    hidden targets or edges (nor the full targetable set)."""
    sid = pub["system_id"]
    t_end, dt = float(pub["t_end_default"]), float(pub["dt"])
    cap = normalize_capability(pub.get("capability"), t_end=t_end, dt=dt, input_dim=int(pub.get("input_dim", 1)))
    targetable = generator_targetable(pub)            # the generator's set, never the observed units (review F round 3b, NF-1)
    edges = sorted([int(a), int(b)] for a, b in (pub.get("edges") or []))
    t_pub, t_hid = partition(targetable, "targets", tier, seed, sid)
    e_pub, e_hid = partition(edges, "edges", tier, seed, sid)
    split = rotation_split_record(rotation, cap)
    base = {k: pub[k] for k in GENERATOR_PUBLIC_KEYS if k in pub}           # a WHITELIST of pass-through keys (review F, minor 7)
    public = {**base, "system_id": sid, "kind": "synthetic", "dt": dt, "t_end_default": t_end, "horizons_s": horizons_s(t_end),
              "targets_public": t_pub, "edges_public": e_pub, "capability": cap, "split": split,
              "cost_units": int(pub.get("cost_units", 1)), "public_graph": pub.get("public_graph")}
    assert_public_record(public)
    internal = {**public, "targets_heldout": t_hid, "edges_heldout": e_hid, "targetable": targetable, "edges": edges,
                "system_hash": system_hash, "engine": engine_id, "tier": tier}
    return public, internal


def assert_public_record(rec: dict) -> None:
    """A public system record holds only whitelisted keys (review F, minor 7), and its capability holds no per-unit field (review T,
    M1: per-unit vectors reveal unit roles; the declared per-unit fields are the record's observed / readout / target / member / edge
    lists and its public graph)."""
    extra = sorted(set(rec) - PUBLIC_RECORD_KEYS)
    if extra:
        raise AssertionError(f"public record of {rec.get('system_id')} has non-public keys {extra}")
    pu = per_unit_lists(rec.get("capability") or {})
    if pu:
        raise AssertionError(f"public record of {rec.get('system_id')} carries per-unit capability fields {pu}")


# ================================================================================================================ protocol sampler


# ================================================================================================================ set designs
def _spec(p: dict, info: dict, split: str, role: str, *, twin: bool, cell: str = "", state: int = 0, **meta) -> Spec:
    m = {k: v for k, v in {**meta, "onset": info.get("onset"), "edges": info.get("edges"), "components": info.get("components")}.items()
         if v is not None}
    return Spec(protocol=p, split=split, role=role, family=info["family"], mclass=info.get("mclass", "na"),
                target_set=tuple(info.get("targets") or ()), cell=cell, state=state, twin=twin, meta=m)


def init_spec(sampler: FamilySampler, src: str, split: str, role: str, *, src_seed: int = 0, **meta) -> Spec:
    """An 'obs.init' trajectory (LOG P4-D36): a RESTART from a sample time of the nominal passive trajectory `src` (a `src_id` of the
    same plan), with the source's parameter draw, weight noise and spread and the nominal stimulus schedule of its own. Planned as a
    placeholder protocol (r0 rest) plus meta['restart_from'] = {"src", "t_frac"}; `run_specs` completes it after the source is
    simulated (r0 = {"kind": "restart", "key": <the source's store key>, "t": <a sample time>}). Genuinely passive initial-condition
    variability: the concatenation of the source's schedule and this one is a trajectory from rest under a stimulus schedule.
    `src_seed`: the source's planned parameter seed (the placeholder's, so the plan shows the right seed range)."""
    p = sampler.base(params_seed=int(src_seed))
    return _spec(p, {"family": "obs.init"}, split, role, twin=False, restart_from={"src": src, "t_frac": sampler.init_t_frac()}, **meta)


def design_passive(sampler: FamilySampler, counts: dict[str, int], split: str, role: str, *, seed_parts: tuple,
                   seed_of=public_seed_of) -> list[Spec]:
    """Passive trajectories: 'obs.nominal' of the training data cycles over parameter draws 0-7 (labelled obs.param by
    `family_of` when the system names a different nominal draw); other families draw seeds from the sampler. `seed_of`: the seed
    function of explicit parts (salted on the hidden tiers, `seed_of_fn`)."""
    out = []
    n_nom = int(counts.get("obs.nominal", 0))
    nom_seed: dict[str, int] = {}
    for fam, n in counts.items():
        for j in range(n):
            if fam == "obs.nominal":
                ps = j % 8 if split == "train" else seed_of(*seed_parts, fam, j)
                nom_seed[f"{split}:nominal:{j}"] = int(ps)
                out.append(_spec(sampler.base(params_seed=ps), {"family": fam}, split, role, twin=False, src_id=f"{split}:nominal:{j}"))
            elif fam == "obs.init":
                if n_nom < 1 or fam != "obs.init" or not nom_seed:
                    raise ValueError("obs.init needs nominal passive trajectories planned before it in the same set")
                src = f"{split}:nominal:{j % n_nom}"
                out.append(init_spec(sampler, src, split, role, src_seed=nom_seed[src]))
            else:
                out.append(_spec(sampler.obs(fam), {"family": fam}, split, role, twin=False))
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
    out += design_passive_tests(s_pub, seed_fn)
    if level == "C":
        out += design_ood(s_pub, sysrec, edges_pub, seed_fn)
        out += design_robust(s_pub, sysrec, edges_pub, seed_fn)
    return out


def design_passive_tests(s: FamilySampler, seed_fn) -> list[Spec]:
    """N_PASSIVE_TEST passive test trajectories cycling over obs.nominal, obs.stim, obs.init, obs.stim; each obs.init restarts from
    the nominal trajectory two positions before it (LOG P4-D36)."""
    out: list[Spec] = []
    for j in range(N_PASSIVE_TEST):
        fam = ("obs.nominal", "obs.stim", "obs.init", "obs.stim")[j % 4]
        if fam == "obs.nominal":
            out.append(_spec(s.base(params_seed=seed_fn()), {"family": fam}, "test", "passive", twin=False, src_id=f"passive:{j}"))
        elif fam == "obs.init":
            out.append(init_spec(s, f"passive:{j - 2}", "test", "passive", src_seed=out[j - 2].protocol["params_seed"]))
        else:
            out.append(_spec(s.obs(fam, params_seed=seed_fn()), {"family": fam}, "test", "passive", twin=False))
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
        # altered initial conditions (off-pool microstates; LOG P4-D36): the full microstate of a nominal trajectory of the same draw
        # at a random time with half the observed units displaced by twice the development kick maximum (random signs, clipped to the
        # admissible range), started through a state carrier (P4-D31); never an explicit r0 'state'
        src = f"oodinit:{j}"
        src_spec = _spec(s.base(params_seed=seed_fn()), {"family": "obs.nominal"}, "aux", "ood_src", twin=False, src_id=src)
        out.append(src_spec)
        p, info = s.make(fam, params_seed=int(src_spec.protocol["params_seed"]))
        obs_units = [int(u) for u in (sysrec.get("observed") or s.targets)]
        k = max(1, round(0.5 * len(obs_units)))
        chosen = sorted(int(u) for u in s.rng.choice(obs_units, size=min(k, len(obs_units)), replace=False))
        dmax = 2.0 * float(s.cap["kick"]["max"])
        disp = {str(u): round(s.sign() * dmax, 6) for u in chosen}
        out.append(_spec(p, info, "test", "ood:initial_condition", twin=True, cell=f"ood_init|{fam}", state=j,
                         carrier_from={"src": src, "t_frac": round(float(s.rng.uniform(0.3, 0.8)), 6), "displace": disp}))
        # temporal sampling (review H, M3): stimulus and events on the 2 dt grid, SIMULATED at the nominal dt, every second sample kept
        # (meta subsample 2; `run_specs` records the told protocol at 2 dt), so only the sampling changes
        dt2 = 2.0 * s.dt
        t2 = round(math.floor(s.T / dt2 + 1e-9) * dt2, 9)
        s2 = FamilySampler({**sysrec, "dt": dt2}, s.rng, seed_fn, targets=s.targets, edges=edges, t_end=t2)
        p, info = s2.make(fam, params_seed=seed_fn())
        p = dict(p, dt=s.dt, t_end=t2)
        out.append(_spec(p, info, "test", "ood:sampling", twin=True, cell=f"ood_dt|{fam}", state=j, subsample=2))
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


#: STATE CARRIERS (LOG P4-D31). The public protocol format sets UNIT values only (r0 'state'; internal variables start at rest), but
#: orchestrator-held truth simulations of synthetic systems must start from a generator's FULL microstate (pool sources from
#: `pool_states`, truth-equivalent states from `equivalent_states`). A carrier is a one-sample store record holding that microstate at
#: an absolute time t; the simulation then starts from it through an ordinary r0 'restart' (same system, full state: the existing
#: restart checks apply), so every protocol stays in the frozen format and names its start by a content-addressed key.
CARRIER_FORMAT = "p4-carrier-1"


def carrier_key(system_hash: str, t: float, state) -> str:
    """Store key of the carrier of a full microstate of one system at absolute time t (its own hash domain, never a protocol key)."""
    v = np.ascontiguousarray(np.asarray(state, dtype=np.float64).ravel())
    h = hashlib.sha256(f"{CARRIER_FORMAT}|{system_hash}|{float(t)!r}|{v.size}|".encode())
    h.update(v.tobytes())
    return h.hexdigest()


def carrier_r0(system_hash: str, t: float, state) -> tuple[dict, dict]:
    """(r0, carrier) for a start from a FULL microstate at absolute time t: r0 = a restart from the carrier at t; carrier = {"key",
    "t", "state"} (to be stored with `put_carrier` before the simulation)."""
    v = [float(x) for x in np.asarray(state, dtype=np.float64).ravel()]
    key = carrier_key(system_hash, t, v)
    return {"kind": "restart", "key": key, "t": float(t)}, {"key": key, "t": float(t), "state": v}


def put_carrier(store_root: Path | str, sid: str, system_hash: str, carrier: dict) -> None:
    """Store a carrier record (idempotent; its key is re-derived and checked)."""
    from .store import TrajectoryStore
    store = TrajectoryStore(store_root)
    v = np.asarray(carrier["state"], dtype=np.float64).ravel()
    if carrier_key(system_hash, carrier["t"], v) != carrier["key"]:
        raise ValueError("state carrier: key does not match its content")
    if store.has(carrier["key"]):
        return
    rec = {"t": np.array([float(carrier["t"])], dtype=np.float64), "state": v[None, :],
           "info": {"system_id": sid, "system_hash": system_hash, "carrier": CARRIER_FORMAT, "success": True}}
    store.put(carrier["key"], rec, {"system_id": sid, "system_hash": system_hash, "role": "state_carrier"})


def put_real_carrier(store_root: Path | str, sid: str, system_hash: str, t: float, neurons, rates) -> str:
    """Store the carrier of a REAL network microstate (sparse: neuron ids and their rates, the engine's restart format) at absolute
    time t and return its key (idempotent; rates are stored as float32 like every real record)."""
    from .store import TrajectoryStore
    nz = np.ascontiguousarray(np.asarray(neurons, dtype=np.int32).ravel())
    rt = np.ascontiguousarray(np.asarray(rates, dtype=np.float32).ravel())
    if nz.shape != rt.shape:
        raise ValueError("real carrier: neurons and rates differ in length")
    h = hashlib.sha256(f"{CARRIER_FORMAT}|real|{system_hash}|{float(t)!r}|{nz.size}|".encode())
    h.update(nz.tobytes())
    h.update(rt.tobytes())
    key = h.hexdigest()
    store = TrajectoryStore(store_root)
    if not store.has(key):
        rec = {"t": np.array([float(t)], dtype=np.float64), "neurons": nz, "rates": rt[None, :],
               "info": {"system_id": sid, "system_hash": system_hash, "carrier": CARRIER_FORMAT, "success": True}}
        store.put(key, rec, {"system_id": sid, "system_hash": system_hash, "role": "state_carrier"})
    return key


def design_pool_sources(s: FamilySampler, sysrec: dict, edges: list, *, hidden: bool, parts: tuple, pool_state_fn=None,
                        salted: bool = False, system_hash: str | None = None) -> list[Spec]:
    """POOL_DRAWS parameter draws x POOL_TRAJ source trajectories per draw (P4-D14: 8 x 15): the first source of every draw is a
    NOMINAL passive trajectory; the others cycle over POOL_SOURCES: a start from a generator pool state (synthetic systems whose
    generator provides `pool_states`; otherwise a restart from the draw's nominal source), a stimulus change, a restart from the
    draw's nominal source ('init'; LOG P4-D36) and two trained single interventions. States of one draw are compared with each other
    only.
    Sources of kind 'init' carry the nominal input and no event after their stimulus onset: the pool's float64 continuations (the
    numerical floor (b), review H B1) are read from them. A generator pool state is a FULL microstate: its source starts from it
    through a state carrier (`carrier_r0`; meta 'carrier', stored by `build_system` before the simulation; needs `system_hash`)."""
    out = []
    fams = _in_family(s, sysrec, edges)
    if pool_state_fn is not None and not system_hash:
        raise ValueError("pool sources from generator pool states need the system hash (state carriers)")
    salt = read_salt() if (hidden or salted) else None
    n_gen = POOL_DRAWS * sum(1 for j in range(1, POOL_TRAJ) if POOL_SOURCES[j % len(POOL_SOURCES)] == "pool_state")
    gen_states = []
    if pool_state_fn is not None:
        try:
            gen_states = list(pool_state_fn(n_gen, rng_of("pool-states-gen", *parts)))
        except Exception:  # noqa: BLE001 - a generator without usable pool states falls back to initial-state changes
            gen_states = []
    gi = 0
    for g in range(POOL_DRAWS):
        if hidden:
            ps = hidden_seed("pool", *parts, g, salt=salt)
        elif salted:
            ps = salted_public_seed("pool", *parts, g, salt=salt)
        else:
            ps = public_seed_of("pool", *parts, g)
        for j in range(POOL_TRAJ):
            src = "nominal" if j == 0 else POOL_SOURCES[j % len(POOL_SOURCES)]
            carrier = None
            meta = {"draw": g, "traj": j}
            if src == "nominal":
                # the draw's nominal passive source (LOG P4-D36): the restart source of its 'init' trajectories
                p = s.base(params_seed=ps)
                meta["src_id"] = f"pool:{g}"
            elif src == "pool_state" and gen_states:
                p = s.obs("obs.stim" if (j // len(POOL_SOURCES)) % 2 else "obs.nominal", params_seed=ps)
                p["r0"], carrier = carrier_r0(system_hash, 0.0, gen_states[gi % len(gen_states)])
                gi += 1
            elif src in ("pool_state", "init"):
                # a restart from the draw's nominal source (never an explicit r0 'state'; the float64 continuation of floor (b) stays
                # available: nominal input, no event after the stimulus onset)
                src = "init"
                p = s.base(params_seed=ps)
                meta["restart_from"] = {"src": f"pool:{g}", "t_frac": s.init_t_frac()}
            elif src == "stim" or not fams:
                p, src = s.obs("obs.stim", params_seed=ps), "stim"
            else:
                p, _ = s.make(fams[(g + j) % len(fams)], params_seed=ps)
            p["params_seed"] = int(ps)
            meta["source"] = src
            if carrier is not None:
                meta["carrier"] = carrier
            out.append(Spec(protocol=p, split="pool_src", role="pool_src", meta=meta))
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
    out += design_passive_tests(s, seed_fn)
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
    salted = tier in SALTED_TIERS
    specs: list[Spec] = []
    if "public" in sets:
        rng = rng_of("plan", tier, seed, sid)
        s_pub = FamilySampler(pub, rng, seed_counter(False, "pub", tier, seed, sid, salted=salted), targets=pub["targets_public"],
                              edges=edges_pub)
        n1 = B_MAIN[kind]
        fams = intervention_families(pub["split"])
        seed_of = seed_of_fn(False, salted)
        specs += design_passive(s_pub, D0_DESIGN, "train", "d0", seed_parts=("d0", tier, seed, sid), seed_of=seed_of)
        specs += design_interventions(s_pub, fams, n1, "train", "d1", edges=edges_pub)
        specs += design_passive(s_pub, {f: max(1, round(VAL_FRACTION * n)) for f, n in D0_DESIGN.items()}, "val", "d0",
                                seed_parts=("val", tier, seed, sid), seed_of=seed_of)
        specs += design_interventions(s_pub, fams, round(VAL_FRACTION * n1), "val", "d1", edges=edges_pub)
    if "tests" in sets or "pool_src" in sets:
        public_only = policy == "public"
        tag = "test-public" if public_only else "test"
        hid = (tier in HIDDEN_TIERS) and not public_only
        tseed = seed_counter(hid, tag, tier, seed, sid, salted=salted and not hid)
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
                                         pool_state_fn=None if public_only else pool_state_fn, salted=salted and not hid,
                                         system_hash=internal.get("system_hash"))
    add_spares(specs, tier=tier, seed=seed, sid=sid, policy=policy, salted=salted)
    return specs


def add_spares(specs: list[Spec], *, tier: str, seed: int, sid: str, policy: str, salted: bool) -> None:
    """N_SPARE_SEEDS replacement parameter seeds per planned trajectory (pool sources excluded: their draw structure is fixed), from a
    counter-based stream with the planned seed's salting and range (hidden range for hidden-range seeds). The logged rule (review H,
    M4): a trajectory whose simulation fails (an error, `success` false or non-finite values; the store refuses such records) is
    simulated again with its next spare seed, twin and components included; `meta['replaced']` records the attempt, the build summary
    counts failures per family; a trajectory whose spares are exhausted is dropped and counted."""
    hid_fn, pub_fn = None, seed_of_fn(False, salted)
    for i, sp in enumerate(specs):
        if sp.split == "pool_src" or sp.meta.get("restart_from") or sp.meta.get("carrier_from"):
            continue                      # fixed draw structure / the parameter draw is the restart source's (LOG P4-D36)
        if int(sp.protocol["params_seed"]) >= HIDDEN_SEED_BASE:
            hid_fn = hid_fn or seed_of_fn(True, False)
            fn = hid_fn
        else:
            fn = pub_fn
        sp.spares = [int(fn("spare", tier, seed, sid, policy, i, k)) for k in range(N_SPARE_SEEDS)]


# ================================================================================================================ simulation
def dataset_key(protocol: dict, system_hash: str, engine: str, obs_scale: dict | None = None) -> str:
    """Content key of a trajectory record (the full protocol, including observation noise). A NOISY record's observed arrays also
    depend on the system's `obs_scale`, which then enters the key (review H, minor 9: a changed scale never reuses stale files)."""
    on = protocol.get("obs_noise")
    if on is not None and float(on.get("sd", 0.0)) > 0 and obs_scale:
        system_hash = f"{system_hash}|obs_scale={json.dumps(obs_scale, sort_keys=True)}"
    return P.protocol_hash(protocol, system_hash=system_hash, simulator=engine)


def restart_index(src: dict, t: float) -> int:
    """The sample index of an r0 'restart' time in its source record; refuses a time that is not a sample time within 1e-6 dt (review
    H, M6: the real engine's rule, also for synthetic restarts)."""
    ts = np.asarray(src["t"], dtype=np.float64)
    dt_src = float(ts[1] - ts[0]) if len(ts) > 1 else 0.0
    i = round(float(t) / dt_src) if dt_src > 0 else 0
    if not (0 <= i < len(ts)) or abs(ts[i] - float(t)) > 1e-12 + 1e-6 * dt_src:
        raise P.ProtocolError(f"r0.t={t} is not a sample time of the restart source")
    return i


def restart_source_problems(store_root, system_id: str, system_hash: str, keys, *, need_state: bool) -> list[str]:
    """Why some of `keys` are not usable restart sources of this system: every key must name a record of the store at `store_root` (or of
    the first of several store roots that holds it) whose info names this system (id and, where recorded, content hash) and, for
    synthetic systems, holds the full state. Reads only each record's info (and its member list). The builder calls it for every
    restart source of a part; `verify_system_restart_sources` re-runs it on built parts (LOG P4-D50)."""
    from .store import TrajectoryStore
    stores = [TrajectoryStore(r) for r in (store_root if isinstance(store_root, (list, tuple)) else [store_root])]
    out = []
    for k in dict.fromkeys(str(k) for k in keys if k):
        p = next((s.path(k) for s in stores if s.path(k).exists()), stores[0].path(k))
        if not p.exists():
            out.append(f"{k[:12]}: not in the store")
            continue
        with np.load(p, allow_pickle=False) as z:
            info = json.loads(str(z["info"])) if "info" in z.files else {}
            full = ("state" in z.files) or ("neurons" in z.files)
        if info.get("system_id") not in (None, system_id):
            out.append(f"{k[:12]}: a record of {info.get('system_id')}")
        if system_hash and info.get("system_hash") not in (None, system_hash):
            out.append(f"{k[:12]}: system hash {str(info.get('system_hash'))[:12]}, not {system_hash[:12]}")
        if need_state and not full:
            out.append(f"{k[:12]}: stored without its full state")
    return out


def part_restart_keys(part_dir: Path | str) -> list[str]:
    """Every restart source a BUILT part refers to: its rows' restart keys (resolved to store keys through the part's rows), its lift
    cases and its pool states."""
    d = Path(part_dir)
    rows = [json.loads(x) for x in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()] \
        if (d / "index.jsonl").exists() else []
    by_key = {r["key"]: (r.get("meta") or {}).get("store_key") or r["key"] for r in rows}
    keys = [by_key.get(str(r["protocol"]["r0"]["key"]), str(r["protocol"]["r0"]["key"])) for r in rows
            if (r["protocol"].get("r0") or {}).get("kind") == "restart"]
    if (d / "lift_cases.json").exists():
        keys += [c["store_key"] for c in json.loads((d / "lift_cases.json").read_text(encoding="utf-8"))]
    if (d / "pools" / "pool.json").exists():
        keys += [s.get("store_key") for s in json.loads((d / "pools" / "pool.json").read_text(encoding="utf-8")).get("states") or []]
    return [k for k in keys if k]


def verify_system_restart_sources(tier: str, sid: str, roots: dict | None = None) -> dict:
    """The build-time restart-source check on one system's BUILT parts (inside a volume container; default roots = REMOTE): the public
    part under the fit volume, the other parts under the eval volume, records looked up in the eval store then the store volume.
    Returns {"sid", "system_hash", "parts": {dest: {"n_keys", "problems"}}}."""
    roots = dict(roots or REMOTE)
    rec = json.loads((Path(roots["eval"]) / "suites" / tier / "internal_records.json").read_text(encoding="utf-8"))[sid]
    stores = [roots["eval_store"], roots["store"]]
    out = {"sid": sid, "system_hash": rec.get("system_hash"), "parts": {}}
    for dest, _sets, _pol in TIER_PARTS.get(tier, ()):
        base = Path(roots["fit"] if dest == "public" else roots["eval"]) / "suites" / tier / dest / _safe(sid)
        if not base.exists():
            out["parts"][dest] = {"n_keys": 0, "problems": ["part not found"]}
            continue
        keys = part_restart_keys(base)
        bad = restart_source_problems(stores, sid, str(rec.get("system_hash") or ""), keys, need_state=rec.get("kind") == "synthetic")
        out["parts"][dest] = {"n_keys": len(set(keys)), "problems": bad[:20], "n_problems": len(bad)}
    return out


def check_restart_source(src: dict | None, system_id: str, system_hash: str) -> None:
    """A synthetic restart source must be a stored record of the SAME system with its full state (review H, M6)."""
    if src is None or "state" not in src:
        raise P.ProtocolError("restart source missing or stored without its full state")
    info = src.get("info") or {}
    if info.get("system_hash") != system_hash or info.get("system_id") not in (None, system_id):
        raise P.ProtocolError("r0 'restart' must come from a trajectory of the same system")


def read_through_store(root: Path | str, read_roots=()):
    """A writable local store that also READS records from other stores (e.g. volume stores in an evaluation container): `get` /
    `has` fall back to the read roots in order, `put` writes locally only (never into a shared volume store)."""
    from .store import TrajectoryStore

    class ReadThroughStore(TrajectoryStore):
        def __init__(self, root_, roots):
            super().__init__(root_)
            self.read_roots = [Path(r) for r in roots]

        def _src(self, key: str):
            p = self.path(key)
            if p.exists():
                return p
            for r in self.read_roots:
                q = r / "rec" / key[:2] / f"{key}.npz"
                if q.exists():
                    return q
            return None

        def has(self, key: str) -> bool:
            return self._src(key) is not None

        def get(self, key: str):
            p = self._src(key)
            if p is None:
                return None
            with np.load(p, allow_pickle=False) as z:
                rec = {k: z[k] for k in z.files if k != "info"}
                rec["info"] = json.loads(str(z["info"])) if "info" in z.files else {}
            return rec
    return ReadThroughStore(root, list(read_roots or ()))


class SimContext:
    """How to simulate one system (orchestrator side): a synthetic adapter system or a real engine + system, through the store
    (`read_roots`: further stores read-only, e.g. the volume stores inside an evaluation container)."""

    def __init__(self, internal: dict, *, store_root: Path | str = STORE, synthetic_system=None, bundle: Path | None = None,
                 read_roots=()):
        from .store import TrajectoryStore
        self.rec = internal
        self.sid = internal["system_id"]
        self.kind = internal["kind"]
        self.store = read_through_store(store_root, read_roots) if read_roots else TrajectoryStore(store_root)
        self.syn = synthetic_system
        if self.kind == "synthetic":
            if synthetic_system is None:
                raise ValueError("a synthetic context needs its generator system")
            self.system_hash, self.engine_id = synthetic_system.content_hash(), synthetic_system.engine_id
            want = internal.get("system_hash")
            if want and self.system_hash != want:
                # the generator constructed the system differently in this process (BLAS threads or platform): every store key and
                # every restart from a stored record would silently refer to another system (LOG P4-D50)
                raise RuntimeError(f"{self.sid}: this process computes the system's content hash as {self.system_hash[:12]}, its record "
                                   f"says {str(want)[:12]}: construct synthetic systems at the reference numerics (one BLAS thread, the "
                                   "reference platform)")
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
        still read from the store); a stored record is still reused. meta {"restart_round": "float32"} (with no_store): a synthetic
        restart starts from the float32-ROUNDED source state (the numerical floor (b) of the pools; real restarts always do, their
        stored rates being float32). Restarts are checked (a sample time of the source within 1e-6 dt; a source of the same system:
        review H, M6); failed or non-finite simulations raise `store.InvalidRecord` and are never stored (review H, M4)."""
        from .store import check_record
        q = P.validate(protocol)
        meta = dict(meta or {})
        no_store = bool(meta.pop("no_store", False))
        round32 = meta.pop("restart_round", None) == "float32"
        if self.kind == "synthetic":
            from .p4modal.gate import require_admissible
            require_admissible("synthetic simulation")          # the same host gate as real systems (review H, N6)
            skey = self.store_key(q)

            def compute():
                restart = None
                if q["r0"]["kind"] == "restart":
                    src = self.store.get(q["r0"]["key"])
                    check_restart_source(src, self.sid, self.system_hash)
                    restart = np.asarray(src["state"][restart_index(src, q["r0"]["t"])], dtype=np.float64)
                    if round32:
                        restart = restart.astype(np.float32).astype(np.float64)
                rec = self.syn.simulate(P.microstate_protocol(q), full=True, restart_state=restart)
                if "state" not in rec:
                    raise RuntimeError("the generator returned no full state (restarts impossible)")
                rec["info"] = {**(rec.get("info") or {}), "system_id": self.sid, "system_hash": self.system_hash, "engine": self.engine_id}
                return rec
            if no_store:
                rec = (None if round32 else self.store.get(skey)) or compute()
                check_record(rec)
            else:
                skey, rec, _ = self.store.get_or_compute(skey, compute, {"system_id": self.sid, "system_hash": self.system_hash,
                                                                          "protocol": P.microstate_protocol(q), **meta})
            if "state" not in rec:
                raise RuntimeError(f"store record {skey[:12]} has no full state (it was stored without full=True)")
            from .synthadapter import observe_synthetic
            obs = observe_synthetic(rec, self.rec, q)
            truth = {k: np.asarray(rec[k], np.float64) for k in ("z", "z_obs") if k in rec}
            if hasattr(self.syn, "draw_effective"):            # the trajectory's effective draw parameters (LOG P4-D43), truth only
                truth["draw"] = np.asarray(self.syn.draw_effective(P.microstate_protocol(q)), np.float64).reshape(-1)
            clean = np.asarray(rec["y"], np.float32)
        else:
            from .realsim import dense, observe
            if no_store:
                skey = self.store_key(q)
                rec = self.store.get(skey) or self.engine.run(self.real, q, store=self.store)
                check_record(rec)
            else:
                skey, rec, _ = self.store.get_or_run(self.engine, self.real, q, self.system_hash, meta=meta)
            obs = observe(rec, self.real, q, self.rec.get("obs_scale"))
            truth = {}
            clean = dense(rec, list(self.real.readout))
        if not (np.isfinite(obs["x"]).all() and np.isfinite(obs["y"]).all()):
            raise P.ProtocolError("non-finite observed values")          # e.g. observation noise on a non-finite scale
        if q["obs_noise"] is not None and float(q["obs_noise"]["sd"]) > 0:
            truth["y_clean"] = clean
        return {"key": dataset_key(q, self.system_hash, self.engine_id, self.rec.get("obs_scale")), "store_key": skey, "t": obs["t"],
                "x": obs["x"], "u": obs["u"], "y": obs["y"], "truth": truth, "info": dict(rec.get("info") or {})}


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
            if not (np.isfinite(np.asarray(r["x"], np.float64)).all() and np.isfinite(np.asarray(r["y"], np.float64)).all()):
                out[j] = {"error": "InvalidRecord: non-finite observed values"}
                continue
            out[j] = {"key": dataset_key(q, rec["system_hash"], engine, rec.get("obs_scale")), "store_key": skey, "t": np.asarray(r["t"]),
                      "x": np.asarray(r["x"]), "u": np.asarray(r["u"]), "y": np.asarray(r["y"]), "truth": {},
                      "info": {"remote": True, "computed": r.get("computed"), "sim_wall_s": r.get("sim_wall_s"), "host": r.get("host")}}
        for j, y in clean.items():
            if out[j] is not None and "error" not in out[j]:
                out[j]["truth"]["y_clean"] = y
        return [o if o is not None else {"error": "no result"} for o in out]
    return run


# ================================================================================================================ writers
def dataset_info(info: dict, kind: str) -> dict:
    """The engine bookkeeping a dataset row may carry (a WHITELIST; review F, minor 7): never the network, its size, the bundle hash or
    the system id; synthetic rows never the generator's engine string (it may name the type)."""
    keys = SYNTHETIC_INFO_KEYS if kind == "synthetic" else PUBLIC_INFO_KEYS
    return {k: info[k] for k in keys if info.get(k) is not None}


def assert_public_row(row: dict) -> None:
    """A row of a PUBLIC set holds only whitelisted keys, meta fields and info fields (review F, B1 / minor 7)."""
    bad = sorted(set(row) - PUBLIC_ROW_KEYS)
    bad += [f"meta.{k}" for k in sorted(set(row.get("meta") or {}) - PUBLIC_META_KEYS)]
    bad += [f"info.{k}" for k in sorted(set(row.get("info") or {}) - set(PUBLIC_INFO_KEYS))]
    if bad:
        raise AssertionError(f"public row {str(row.get('key'))[:12]} carries non-public fields {bad}")
    if int(row["protocol"]["params_seed"]) >= HIDDEN_SEED_BASE:
        raise AssertionError("public row with a hidden-range parameter seed")


class SetWriter:
    """Incremental writer of one system's experiment set in the p4-dataset-1 layout (manifest.json, index.jsonl, traj/<key>.npz),
    readable with `brainir_causal.data.ExperimentSet.load`. `public`: every row and the manifest are checked against the whitelists."""

    def __init__(self, root: Path, sid: str, pub: dict, dataset_id: str, *, public: bool = False):
        self.root, self.sid, self.pub, self.dataset_id, self.public = Path(root), sid, pub, dataset_id, public
        (self.root / "traj").mkdir(parents=True, exist_ok=True)
        self.index = self.root / "index.jsonl"
        self.index.write_text("", encoding="utf-8")
        self.n = 0

    def add(self, tr) -> None:
        row = tr.row()
        if self.public:
            assert_public_row(row)
        p = self.root / "traj" / f"{tr.key}.npz"
        if not p.exists():
            tmp = p.with_name(p.stem + ".tmp.npz")
            np.savez_compressed(tmp, t=np.asarray(tr.t, np.float64), x=np.asarray(tr.x, np.float32), u=np.asarray(tr.u, np.float32),
                                y=np.asarray(tr.y, np.float32))
            tmp.replace(p)
        with open(self.index, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        self.n += 1

    def close(self, extra: dict | None = None) -> None:
        from .data import DATASET_FORMAT
        man = {"format": DATASET_FORMAT, "dataset_id": self.dataset_id, "systems": {self.sid: self.pub}, **(extra or {})}
        if self.public:
            bad = sorted(set(man) - PUBLIC_MANIFEST_KEYS)
            if bad:
                raise AssertionError(f"public manifest of {self.sid} carries non-public fields {bad}")
            assert_public_record(self.pub)
        (self.root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _family_label(protocol: dict, pub: dict) -> str:
    try:
        return F.family_of(protocol, pub)
    except Exception:  # noqa: BLE001
        return "other"


def _jobs_of(sp: Spec, sid: str, proto: dict | None = None) -> list[tuple[str, dict, dict, str]]:
    """The simulation jobs of one planned trajectory (with `proto`, e.g. a replaced parameter seed, instead of the planned protocol):
    itself, its twin, its composition components ((sid, protocol, meta, kind))."""
    proto = sp.protocol if proto is None else proto
    jobs = [(sid, proto, {"role": sp.role, "split": sp.split}, "item")]
    if sp.twin:
        jobs.append((sid, P.counterfactual(proto), {"role": sp.role, "split": "twin"}, "twin"))
    comps = sp.meta.get("components")
    if comps:
        for part in ("a", "b"):
            jobs.append((sid, dict(proto, events=comps[part]), {"role": sp.role, "split": "component", "component": part}, part))
    return jobs


def subsampled(r: dict, k: int) -> dict:
    """Every k-th sample of a simulated result (observed arrays and truth arrays)."""
    out = dict(r)
    for a in ("t", "x", "u", "y"):
        out[a] = np.asarray(r[a])[::k]
    out["truth"] = {n: np.asarray(v)[::k] for n, v in (r.get("truth") or {}).items()}
    return out


def told_protocol(q: dict, k: int) -> dict:
    """The protocol the MODEL is told for a trajectory simulated at dt and kept at every k-th sample: dt x k (its stimulus and events
    lie on the k dt grid by construction; review H, M3)."""
    return P.validate(dict(q, dt=round(float(q["dt"]) * k, 12)))


def _dependency(sp: Spec) -> dict | None:
    return sp.meta.get("restart_from") or sp.meta.get("carrier_from")


def resolve_restart(sp: Spec, src_key: str, src_proto: dict) -> Spec:
    """The planned 'obs.init' / pool 'init' trajectory completed from its simulated nominal source (LOG P4-D36): r0 = a restart from
    the source's store key at the sample time nearest t_frac x its duration, and the source's parameter draw, weight noise and
    spread."""
    dep = sp.meta["restart_from"]
    dt = float(src_proto["dt"])
    t_r = min(P.snap(float(dep["t_frac"]) * float(src_proto["t_end"]), dt), P.snap(float(src_proto["t_end"]) - dt, dt))
    q = json.loads(json.dumps(sp.protocol))
    q["r0"] = {"kind": "restart", "key": str(src_key), "t": float(t_r)}
    q["params_seed"] = int(src_proto["params_seed"])
    q["weight_noise"] = src_proto.get("weight_noise")
    if src_proto.get("params_spread") is not None:
        q["params_spread"] = src_proto["params_spread"]
    return Spec(**{**sp.__dict__, "protocol": q, "spares": []})


def onset_mismatch(proto: dict, model_events, item: dict, twin: dict) -> str | None:
    """None if an intervention item and its twin agree in x and y up to AND including the onset sample (the earliest start of the
    simulated and the told events), on the simulated arrays; else the reason (PROTOCOL_V2 section 1: the sample at an event's time is
    the pre-event state; review H, N1)."""
    q = P.validate(proto)
    evs = list(q["events"])
    if model_events:
        evs += list(P.validate(dict(q, events=model_events))["events"])
    if not evs:
        return None
    i0 = round(min(P.event_start(e) for e in evs) / float(q["dt"]))
    for a in ("x", "y"):
        u, v = np.asarray(item[a]), np.asarray(twin[a])
        n = min(i0 + 1, len(u), len(v))
        if not np.array_equal(u[:n], v[:n]):
            bad = int(np.flatnonzero(np.any(u[:n].reshape(n, -1) != v[:n].reshape(n, -1), axis=1))[0])
            return f"{a} differs from the twin at sample {bad} (onset sample {i0})"
    return None


def _realized_kick(ent: dict, unit) -> float | None:
    """The realized size of the kick on `unit` in one `kicks_applied` entry: the real engine's map "applied" or the synthetic
    generator's map "units" (review H round 3c, NEW-7), keyed by the unit id as str or int; None when the entry does not report it."""
    got = ent.get("applied")
    if got is None:
        got = ent.get("units")
    if not isinstance(got, dict):
        return None
    keys = [unit, str(unit)]
    try:
        keys += [int(unit), str(int(unit))]
    except (TypeError, ValueError):
        pass
    for k in keys:
        if k in got:
            return float(got[k])
    return None


def realized_kick_class(sp: Spec, proto: dict, info: dict, cap: dict) -> dict | None:
    """The magnitude class of a kick item's REALIZED size (review H, N5; LOG P4-D36). None when the item has no kick class or the
    simulation reports nothing about its kicks. From `kicks_applied` ([{"t", "requested": {unit: d}, "applied": {unit: a}}], the real
    engine's field; the synthetic generator reports [{"t", "event_index", "units": {unit: a}, "requested": {unit: d}}], unit keys str or
    int; `_realized_kick`): unclipped kicks keep the planned class; a clipped item takes the class nearest on a log scale to the median
    realized |kick| / m_s over its kicked units (m_s = the capability's moderate kick; the planned 'hi' class is kept while that median
    stays inside hi_range). A simulation that reports its kicks without a realized size for some kicked unit, or only reports THAT
    kicks were clipped (a synthetic generator's `clipped_kicks` [[unit, step], ...]), gives {"unknown": True}: the planned class is
    kept and the item is flagged (never silently read as unclipped)."""
    if sp.mclass in ("na", "") or not sp.family.startswith("kick"):
        return None
    kicks = [e for e in P.validate(proto)["events"] if e["kind"] == "kick"]
    if not kicks:
        return None
    applied = info.get("kicks_applied")
    if applied:
        req, got = [], []
        for e in kicks:
            ents = [a for a in applied if abs(float(a.get("t", -1.0)) - float(e["t"])) < 1e-9]    # several kick events may share a time
            for u, d in e["delta"].items():
                a = next((v for v in (_realized_kick(ent, u) for ent in ents) if v is not None), None)
                if a is None:
                    return {"requested_class": sp.mclass, "mclass": sp.mclass, "unknown": True}
                req.append(abs(float(d)))
                got.append(abs(a))
        req_a, got_a = np.asarray(req), np.asarray(got)
        clipped = int(np.sum(np.abs(req_a - got_a) > 1e-9 * np.maximum(1.0, req_a)))
        out = {"requested_class": sp.mclass, "clipped": clipped, "n": int(req_a.size),
               "median_ratio": float(np.median(got_a / np.maximum(req_a, 1e-300)))}
        if not clipped:
            return {**out, "mclass": sp.mclass}
        m_s = float(cap["kick"]["moderate"])
        m = float(np.median(got_a)) / m_s
        if sp.mclass == "hi" and m >= float(cap["kick"]["hi_range"][0]) / m_s:
            return {**out, "mclass": "hi"}
        dist = {c: abs(math.log(max(m, 1e-12)) - math.log(MAG_MULT[c])) for c in MAG_CLASSES}
        return {**out, "mclass": min(MAG_CLASSES, key=lambda c: (dist[c], MAG_CLASSES.index(c)))}
    clipped_list = info.get("clipped_kicks")
    if clipped_list:
        units = {int(u) for e in kicks for u in e["delta"]}
        if any(int(c[0]) in units for c in clipped_list):
            return {"requested_class": sp.mclass, "mclass": sp.mclass, "unknown": True}
    return None


def _constant_after(a, i0: int) -> bool:
    z = np.asarray(a)[max(0, int(i0)):]
    return bool(z.size) and bool(np.all(z == z[:1]))


def run_specs(specs: list[Spec], pub: dict, run, sink, *, provenance: str = "benchmark", chunk: int = CHUNK, public: bool = False,
              resolver=None, policy_check=None) -> dict:
    """Simulate planned trajectories in chunks and hand every record to `sink(record, truth)`. A planned trajectory is written only
    when ALL its jobs succeed (item, twin, composition components): a failure (an error, `success` false or non-finite values: the
    store refuses such records) re-simulates the whole group with the spec's next spare parameter seed (`add_spares`, the logged rule
    of review H, M4; meta['replaced'] = {"attempt": k}); a group whose spares are exhausted is dropped. Twins carry meta twin_of =
    their item's key and components component_of. Specs with meta['subsample'] = k (the temporal-sampling OOD items) are simulated at
    the nominal dt and recorded at every k-th sample with the told protocol (dt x k; meta sim_dt). Returns counts, errors and the
    failures per family.

    DEPENDENT trajectories (LOG P4-D36) are simulated after the others: meta['restart_from'] (an 'obs.init' / pool 'init' restart from
    a nominal source of the same plan, `resolve_restart`) or meta['carrier_from'] (a state-carrier start derived from a source;
    `resolver(spec, source store key, source protocol) -> Spec`, given by `build_system`). A dependent whose source was dropped is
    dropped too; dependents have no spares. `policy_check(protocol, allowed_restart_keys)` (public and public-policy parts) checks
    every completed protocol.

    CHECKS and LABELS: an intervention item whose x or y differs from its twin's at or before the onset sample aborts the build
    (`onset_mismatch`; review H, N1). A kick item's magnitude class is its REALIZED class (`realized_kick_class`; review H, N5): in
    non-public parts meta['mclass'] = the realized class with 'mclass_requested' and 'kick_realized' beside it; in public parts only
    real systems are relabelled (their realized sizes are public already in info.kicks_applied) and no key is added. Counts: kick
    clipping per family, and test items whose futures are constant from the onset (quiescent regimes; kept, counted)."""
    from .data import Trajectory
    errors: list[dict] = []
    counters = {"ok": 0, "replaced": 0, "dropped": 0}
    fails_by_family: dict[str, int] = {}
    kick_stats: dict[str, dict[str, int]] = {}
    constant_items: dict[str, int] = {}
    sources: dict[str, tuple[str, dict]] = {}
    cap = normalize_capability(pub.get("capability"), t_end=float(pub["t_end_default"]), dt=float(pub["dt"]),
                               input_dim=int(pub.get("input_dim", 1)))
    relabel_ok = (pub.get("kind") == "real") or not public

    def stage(todo: list[Spec]) -> None:
        pending = [(sp, 0) for sp in todo]          # (spec, attempt): 0 = the planned seed, k >= 1 = spare seed k - 1
        while pending:
            retry = []
            i = 0
            while i < len(pending):
                batch, groups = [], []
                while i < len(pending) and len(batch) < chunk:
                    sp, att = pending[i]
                    proto = sp.protocol if att == 0 else dict(sp.protocol, params_seed=int(sp.spares[att - 1]))
                    js = _jobs_of(sp, pub["system_id"], proto)
                    groups.append((sp, att, proto, len(batch), [j[3] for j in js]))
                    batch += [j[:3] for j in js]
                    i += 1
                res = run(batch)
                for sp, att, proto, start, whats in groups:
                    rs = res[start: start + len(whats)]
                    bad = [(w, r) for w, r in zip(whats, rs) if "error" in r]
                    if bad:
                        fam = sp.family or _family_label(proto, pub)
                        fails_by_family[fam] = fails_by_family.get(fam, 0) + 1
                        errors.extend({"role": sp.role, "family": fam, "what": w, "attempt": att, "error": r["error"]} for w, r in bad)
                        if att < len(sp.spares):
                            retry.append((sp, att + 1))
                        else:
                            counters["dropped"] += 1
                        continue
                    by = dict(zip(whats, rs))
                    if "twin" in by:
                        why = onset_mismatch(proto, sp.meta.get("model_events"), by["item"], by["twin"])
                        if why:
                            raise RuntimeError(f"{pub['system_id']}: {sp.family or 'item'} ({sp.role}) {why}: the sample at an event's "
                                               "time must be the pre-event state (PROTOCOL_V2 section 1; review H, N1)")
                    counters["replaced"] += int(att > 0)
                    if sp.meta.get("src_id"):
                        sources[str(sp.meta["src_id"])] = (by["item"]["store_key"], proto)
                    kr = realized_kick_class(sp, proto, by["item"].get("info") or {}, cap)
                    mclass = sp.mclass
                    if kr is not None:
                        st = kick_stats.setdefault(sp.family, {"items": 0, "clipped": 0, "relabelled": 0, "unknown": 0})
                        st["items"] += 1
                        st["clipped"] += int(bool(kr.get("clipped")))
                        st["unknown"] += int(bool(kr.get("unknown")))
                        if relabel_ok and kr["mclass"] != sp.mclass:
                            mclass = kr["mclass"]
                            st["relabelled"] += 1
                    if sp.split == "test":
                        q0 = P.validate(proto)
                        onset = (min(P.event_start(e) for e in q0["events"]) if q0["events"] else PASSIVE_ONSETS[0] * float(q0["t_end"]))
                        i0 = round(onset / float(q0["dt"]))
                        if all(_constant_after(r[a], i0) for r in rs for a in ("x", "y")):
                            key = f"{sp.role}|{sp.family}"
                            constant_items[key] = constant_items.get(key, 0) + 1
                    parent = rs[0]["key"]
                    k_sub = int(sp.meta.get("subsample") or 1)
                    for what, r in zip(whats, rs):
                        meta = {k: v for k, v in sp.meta.items() if k not in PLAN_ONLY_META}
                        meta.update({"role": sp.role, "mclass": mclass, "target_set": list(sp.target_set), "cell": sp.cell,
                                     "state": sp.state, "store_key": r["store_key"]})
                        if kr is not None and not public:
                            meta["mclass_requested"] = sp.mclass
                            meta["kick_realized"] = {k: v for k, v in kr.items() if k not in ("mclass", "requested_class")}
                        if att > 0:
                            meta["replaced"] = {"attempt": att}
                        if what == "item" and sp.meta.get("components"):
                            meta["component_families"] = sp.meta["components"].get("families")
                        split, pw = sp.split, proto
                        if what == "twin":
                            split, meta["twin_of"] = "twin", parent
                            pw = P.counterfactual(proto)
                            meta.pop("model_events", None)
                        elif what in ("a", "b"):
                            split, meta["component_of"], meta["component"] = "component", parent, what
                            pw = dict(proto, events=sp.meta["components"][what])
                            meta.pop("model_events", None)
                        q = P.validate(pw)
                        if k_sub > 1:
                            r = subsampled(r, k_sub)
                            meta["sim_dt"] = float(q["dt"])
                            q = told_protocol(q, k_sub)
                        fam = _family_label(q, pub)
                        if what == "item" and sp.family and fam != sp.family:
                            meta["family_planned"] = sp.family
                        tr = Trajectory(key=r["key"], system_id=pub["system_id"], split=split, family=fam, protocol=q, t=r["t"], x=r["x"],
                                        u=r["u"], y=r["y"], meta=meta, provenance=provenance,
                                        info=dataset_info(r.get("info") or {}, pub["kind"]))
                        sink(tr, r.get("truth") or {})
                        counters["ok"] += 1
            pending = retry

    stage([sp for sp in specs if _dependency(sp) is None])
    resolved: list[Spec] = []
    for sp in specs:
        dep = _dependency(sp)
        if dep is None:
            continue
        src = sources.get(str(dep["src"]))
        if src is None:
            counters["dropped"] += 1
            errors.append({"role": sp.role, "family": sp.family, "what": "item", "attempt": 0,
                           "error": f"restart source {dep['src']} unavailable (dropped)"})
            continue
        if sp.meta.get("restart_from"):
            sp2 = resolve_restart(sp, src[0], src[1])
        else:
            if resolver is None:
                raise RuntimeError("carrier-started trajectories need the builder's resolver")
            sp2 = resolver(sp, src[0], src[1])
        if policy_check is not None:
            policy_check(sp2.protocol, {src[0]})
            if sp2.twin:
                policy_check(P.counterfactual(sp2.protocol), {src[0]})
        resolved.append(sp2)
    stage(resolved)
    return {"ok": counters["ok"], "errors": errors, "failures_by_family": fails_by_family, "replaced": counters["replaced"],
            "dropped": counters["dropped"], "kick_clipping": kick_stats, "constant_future_items": constant_items}


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
                        "weight_noise": r.get("weight_noise"), "params_spread": r.get("params_spread"), "source": r.get("source")})
    return out


def pool_future_protocol(pub: dict, st: dict, seq_events: list[dict], level: float, *, floor: bool = False) -> dict:
    """The restart of one pool state under one sequence, with the nominal input level held constant. floor=True: the repeat run of
    the numerical floor (a) (review H, B1): a no-op stimulus breakpoint ONE SAMPLE after the restart, so the integrator restarts
    inside the primary horizon."""
    T = round(POOL_FUTURE_FRAC * float(pub["t_end_default"]), 9)
    dt = float(pub["dt"])
    n_u = int(pub.get("input_dim", 1))
    val = float(level) if n_u == 1 else [float(level)] * n_u
    stim = [[0.0, val]]
    if floor:
        stim.append([P.snap(dt, dt), val])
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
#: what the numerical-floor futures of a pool are (pool.json 'floors'; review H, B1): the evaluator computes both floors in its own units
FLOOR_DOC = {
    "floor": "(a) the no-intervention future repeated with a no-op stimulus breakpoint one sample after the restart (compare with 'none')",
    "r32": "(b) the no-intervention future restarted from the float32-ROUNDED stored state (real systems: identical to 'none', whose "
           "restart is from the float32 stored rates)",
    "cont": "(b) the float64 CONTINUATION: the source trajectory's own readout over the future window (compare with 'r32'); floor "
            "states come from 'init' sources (nominal input, no event after the stimulus onset), so source and future share the input",
}


def pool_seq_seed_of(tier: str, sid: str, dest: str, policy: str) -> int:
    """The salted seed of the intervention sequences of a NON-public pool (review F, minor 8); needs the salt."""
    return salted_stream_seed("pool-seq", tier, sid, dest, policy)


def floor_state_indices(states: list[dict], n: int | None = None) -> list[int]:
    """The floor states (POOL_FLOOR_STATES by default): states of 'init' pool sources (continuation-capable), taken round-robin over
    the parameter draws."""
    n = POOL_FLOOR_STATES if n is None else int(n)
    by_draw: dict[str, list[int]] = {}
    for si, st in enumerate(states):
        if st.get("source") == "init":
            by_draw.setdefault(str(st["draw"]), []).append(si)
    out: list[int] = []
    queues = [by_draw[d] for d in sorted(by_draw, key=lambda d: (len(d), d))]
    j = 0
    while len(out) < n and any(j < len(q) for q in queues):
        out += [q[j] for q in queues if j < len(q)][: n - len(out)]
        j += 1
    return sorted(out)


def continuation_future(ddir: Path, st: dict, n_future: int) -> np.ndarray | None:
    """The float64 continuation of a pool state: its source trajectory's readout from the state's sample over n_future + 1 samples."""
    p = ddir / "traj" / f"{st['key']}.npz"
    if not p.exists():
        return None
    with np.load(p) as z:
        y = np.asarray(z["y"], np.float32)
    i = int(st["index"])
    return y[i: i + n_future + 1].copy() if i + n_future < len(y) else None


def assert_public_part(ddir: Path | str) -> dict:
    """File-by-file check of one system's PUBLIC part against the whitelists (review F, B1 / minor 7): only manifest.json, index.jsonl,
    traj/<key>.npz (arrays t, x, u, y), pools/futures.npz (keys s<i>_<none | kinds | floor | r32 | cont>_<y | x | u>), pools/pool.json
    and lift_cases.json; whitelisted manifest, record, row, meta, info, pool and lift keys. Raises AssertionError; returns counts."""
    d = Path(ddir)
    allowed_top = {"manifest.json", "index.jsonl", "lift_cases.json"}
    n_files = 0
    for f in d.rglob("*"):
        if not f.is_file():
            continue
        n_files += 1
        rel = f.relative_to(d).as_posix()
        if "/" not in rel:
            if rel not in allowed_top:
                raise AssertionError(f"unexpected file {rel} in a public part")
        elif rel.startswith("traj/"):
            if not rel.endswith(".npz") or rel.count("/") != 1:
                raise AssertionError(f"unexpected file {rel} in a public part")
            with np.load(f, allow_pickle=False) as z:
                if set(z.files) - PUBLIC_TRAJ_ARRAYS:
                    raise AssertionError(f"{rel} holds non-public arrays {sorted(set(z.files) - PUBLIC_TRAJ_ARRAYS)}")
        elif rel not in ("pools/futures.npz", "pools/pool.json"):
            raise AssertionError(f"unexpected file {rel} in a public part")
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    if set(man) - PUBLIC_MANIFEST_KEYS:
        raise AssertionError(f"public manifest carries {sorted(set(man) - PUBLIC_MANIFEST_KEYS)}")
    for rec in man["systems"].values():
        assert_public_record(rec)
    n_rows = 0
    for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            assert_public_row(json.loads(line))
            n_rows += 1
    n_fut = 0
    if (d / "pools" / "futures.npz").exists():
        with np.load(d / "pools" / "futures.npz", allow_pickle=False) as z:
            bad = [k for k in z.files if not PUBLIC_FUTURE_KEY.match(k)]
            n_fut = len(z.files)
        if bad:
            raise AssertionError(f"public futures.npz holds non-public arrays {bad[:5]}")
        pool = json.loads((d / "pools" / "pool.json").read_text(encoding="utf-8"))
        if set(pool) - PUBLIC_POOL_KEYS or pool.get("equivalents"):
            raise AssertionError(f"public pool.json carries {sorted(set(pool) - PUBLIC_POOL_KEYS)} / equivalents")
        for st in pool["states"]:
            if set(st) - PUBLIC_POOL_STATE_KEYS:
                raise AssertionError(f"public pool state carries {sorted(set(st) - PUBLIC_POOL_STATE_KEYS)}")
    if (d / "lift_cases.json").exists():
        for c in json.loads((d / "lift_cases.json").read_text(encoding="utf-8")):
            if set(c) - PUBLIC_LIFT_KEYS:
                raise AssertionError(f"public lift case carries {sorted(set(c) - PUBLIC_LIFT_KEYS)}")
    return {"files": n_files, "rows": n_rows, "future_arrays": n_fut}


def _unit_bounds(truth_system, n: int, cap: dict) -> tuple[np.ndarray, np.ndarray]:
    """Per-unit admissible bounds of a synthetic system for displaced carrier states: the generator's own (orchestrator side) per-unit
    range where it provides one, else the system-wide range of the record's capability."""
    raw = None
    if truth_system is not None:
        try:
            raw = (truth_system.capability() or {}).get("admissible_range")
        except Exception:  # noqa: BLE001 - fall back to the record's range
            raw = None
    src = raw if raw is not None else cap.get("admissible_range")
    if isinstance(src, dict):
        lo, hi = src.get("lo"), src.get("hi")
    elif isinstance(src, (list, tuple)) and len(src) == 2:
        lo, hi = src
    else:
        lo, hi = -np.inf, np.inf
    lo_a = np.full(n, float(lo)) if not isinstance(lo, (list, tuple)) else np.asarray(lo, dtype=np.float64)
    hi_a = np.full(n, float(hi)) if not isinstance(hi, (list, tuple)) else np.asarray(hi, dtype=np.float64)
    return lo_a, hi_a


def resolve_carrier_start(sp: Spec, src_key: str, src_proto: dict, *, pub: dict, internal: dict, store_root: Path | str,
                          truth_system=None) -> Spec:
    """An OOD 'altered initial condition' item completed from its simulated nominal source (LOG P4-D36): the source's FULL microstate
    at the sample time nearest t_frac x its duration, the planned displacements added on the listed observed units (synthetic: state
    units, clipped to the unit's admissible range; real: rates in Hz, clipped to [0, the engine's maximum initial rate]), stored as a
    state carrier (P4-D31); r0 = a restart from the carrier, with the source's parameter draw, weight noise and spread."""
    from .store import TrajectoryStore
    dep = sp.meta["carrier_from"]
    store = TrajectoryStore(store_root)
    rec = store.get(src_key)
    if rec is None:
        raise RuntimeError(f"carrier source {src_key[:12]} is not in the build store")
    dt = float(src_proto["dt"])
    t_c = min(P.snap(float(dep["t_frac"]) * float(src_proto["t_end"]), dt), P.snap(float(src_proto["t_end"]) - dt, dt))
    disp = {int(u): float(v) for u, v in dep["displace"].items()}
    sid = pub["system_id"]
    if pub["kind"] == "synthetic":
        i = restart_index(rec, t_c)
        v = np.asarray(rec["state"][i], dtype=np.float64).copy()
        lo, hi = _unit_bounds(truth_system, v.size, pub.get("capability") or {})
        for u, d in disp.items():
            v[u] = float(np.clip(v[u] + d, lo[u] if u < lo.size else -np.inf, hi[u] if u < hi.size else np.inf))
        sys_hash = truth_system.content_hash() if truth_system is not None else str(internal["system_hash"])
        r0, car = carrier_r0(sys_hash, t_c, v)
        put_carrier(store_root, sid, sys_hash, car)
    else:
        from .realsim import MAX_INIT_RATE
        ts = np.asarray(rec["t"], dtype=np.float64)
        i = round(t_c / (ts[1] - ts[0])) if len(ts) > 1 else 0
        state = {int(n): float(r) for n, r in zip(np.asarray(rec["neurons"]), np.asarray(rec["rates"][i], dtype=np.float64))}
        for u, d in disp.items():
            state[u] = float(np.clip(state.get(u, 0.0) + d, 0.0, MAX_INIT_RATE))
        nz = sorted(n for n, r in state.items() if r != 0.0)
        key = put_real_carrier(store_root, sid, str(internal["system_hash"]), t_c, nz, [state[n] for n in nz])
        r0 = {"kind": "restart", "key": key, "t": float(t_c)}
    q = json.loads(json.dumps(sp.protocol))
    q["r0"] = r0
    q["params_seed"] = int(src_proto["params_seed"])
    q["weight_noise"] = src_proto.get("weight_noise")
    if src_proto.get("params_spread") is not None:
        q["params_spread"] = src_proto["params_spread"]
    return Spec(**{**sp.__dict__, "protocol": q, "spares": []})


def build_system(pub: dict, internal: dict, *, tier: str, seed: int, level: str, run, dirs: dict[str, Path], dest: str = "eval",
                 sets=("tests", "pool_src"), policy: str = "full", with_truth: bool = True, truth_system=None,
                 store_root: Path | str = STORE, specs: list | None = None, pool_seq_seed: int | None = None) -> dict:
    """Plan, simulate and write one part of one system into dirs[dest]/<system> (cleared first: no stale files, review H minor 9):
    records (D0 / D1 / validation and / or tests, twins, components, pool sources), pools (futures NPZ + JSON; under policy 'full',
    synthetic systems also get truth-equivalent states from the generator's `equivalent_states`) and lift cases. A PUBLIC part (dest
    'public') or a public-policy part (policy 'public') is checked protocol by protocol against the public policy
    (`assert_public_policy`): a violation aborts the build; a public part is also checked file by file against the whitelists
    (`assert_public_part`).
    TRUTH never enters the part: record truth goes to truth/<system>/traj/, the true latents of the pool futures to
    truth/<system>/pools/<part>_futures_truth.npz (review F, B1).
    POOL SEQUENCES: a public part draws them from the public stream; every other part from a SALTED stream (`pool_seq_seed`, computed
    where the salt is: `pool_seq_seed_of`; review F, minor 8). POOL INPUT: the simulated u of each no-intervention future is stored
    (`s<i>_none_u`; review H, minor 2). FLOORS (review H, B1): for POOL_FLOOR_STATES states of 'init' sources, futures 'floor',
    'r32' and 'cont' (FLOOR_DOC).
    `truth_system` = the generator's system object (synthetic only). `specs`: the part's plan made elsewhere (remote builds plan
    LOCALLY, where the salt is, and pass the plan to the container: `plan_remote_job`); default: plan here."""
    sid = pub["system_id"]
    if dest == "public" and policy != "public" and set(sets) & {"tests", "pool_src"}:
        raise ValueError("a public part may only hold public-policy evaluation sets")
    if truth_system is not None and internal.get("system_hash") and truth_system.content_hash() != internal["system_hash"]:
        # the plan and the build computed the generator's system differently: they ran on different numerical platforms (P4-D32)
        raise RuntimeError(f"{sid}: the planned system hash differs from the building process's; plan on the reference platform")
    public_part = dest == "public"
    check = public_part or policy == "public"
    pool_state_fn = getattr(truth_system, "pool_states", None) if truth_system is not None else None
    if specs is None:
        specs = plan_system(pub, internal, tier=tier, seed=seed, level=level, sets=tuple(sets), pool_state_fn=pool_state_fn, policy=policy)
    if check:
        for sp in specs:
            assert_public_policy(sp.protocol, pub)
            if sp.twin:
                assert_public_policy(P.counterfactual(sp.protocol), pub)
            if sp.meta.get("components"):
                raise AssertionError("composition items are never public-policy items")
    if "pool_src" in sets and not public_part and pool_seq_seed is None:
        pool_seq_seed = pool_seq_seed_of(tier, sid, dest, policy)          # local builds (the salt is here)
    ddir, tdir = dirs[dest] / _safe(sid), dirs["truth"] / _safe(sid)
    if ddir.exists():
        shutil.rmtree(ddir)
    writer = SetWriter(ddir, sid, pub, f"{tier}:{sid}:{dest}", public=public_part)
    pool_src_meta: list[dict] = []
    lift_src: list[dict] = []
    row_store_key: dict[str, str] = {}          # row key -> store key (restart keys naming a row of the part resolve through it)
    restart_keys: list[str] = []                # every restart key the part's rows use (checked at the end, LOG P4-D50)
    equivs: list[dict] = []                     # truth-equivalent states (their carrier restarts are checked at the end)

    def sink(tr, truth):
        writer.add(tr)
        row_store_key[str(tr.key)] = str(tr.meta["store_key"])
        r0 = tr.protocol.get("r0") or {}
        if r0.get("kind") == "restart":
            restart_keys.append(str(r0["key"]))
        if with_truth:
            write_truth_one(tdir, tr.key, truth)
        light = {"key": tr.key, "store_key": tr.meta["store_key"], "n": len(tr.t), "t": np.asarray(tr.t), "params_seed":
                 tr.protocol["params_seed"], "weight_noise": tr.protocol.get("weight_noise"), "stimulus": tr.protocol["stimulus"],
                 "params_spread": tr.protocol.get("params_spread")}
        if tr.split == "pool_src":
            pool_src_meta.append({**light, "draw": tr.meta.get("draw"), "source": tr.meta.get("source")})
        elif tr.split == "test" and tr.meta.get("role") == "passive":
            lift_src.append(light)

    carriers = [sp.meta["carrier"] for sp in specs if sp.meta.get("carrier")]
    if carriers or any(sp.meta.get("carrier_from") for sp in specs):
        if public_part or policy == "public":
            raise AssertionError("state carriers (full microstates) never enter a public or public-policy part")
        for car in carriers:
            put_carrier(store_root, sid, str(internal["system_hash"]), car)

    def resolve_carrier(sp: Spec, src_key: str, src_proto: dict) -> Spec:
        return resolve_carrier_start(sp, src_key, src_proto, pub=pub, internal=internal, store_root=store_root,
                                     truth_system=truth_system)

    def policy_check(q: dict, keys: set) -> None:
        assert_public_policy(q, pub, allowed_restart_keys=keys)

    res = run_specs(specs, pub, run, sink, public=public_part, resolver=resolve_carrier, policy_check=policy_check if check else None)
    errors = list(res["errors"])
    out = {"counts": {"planned": len(specs), "records": res["ok"], "errors": len(errors), "replaced": res["replaced"],
                      "dropped": res["dropped"], "failures_by_family": res["failures_by_family"],
                      "kick_clipping": res["kick_clipping"], "constant_future_items": res["constant_future_items"]},
           "errors": errors[:50]}
    if "pool_src" in sets and pool_src_meta:
        rng = rng_of("pool-states", tier, seed, sid, policy)
        states = pick_pool_states(pool_src_meta, rng)
        targets = pub.get("targets_public") or internal.get("targetable") or []
        edges = [list(e) for e in (pub.get("edges_public") or [])] or ([] if policy == "public" else _graph_edges(pub))
        allowed = list(pub["split"]["families_train"]) if policy == "public" else None
        seq_rng = rng_of("pool-seq", tier, seed, sid) if public_part else np.random.default_rng(int(pool_seq_seed))
        seqs = pool_sequences(pub, seq_rng, targets, edges, families_allowed=allowed)
        level_nom = FamilySampler(pub, rng, lambda: 0, targets=targets).level
        src_keys = {st["store_key"] for st in states}
        floor_idx = floor_state_indices(states)
        synthetic = pub["kind"] == "synthetic"
        jobs, owners = [], []
        for si, st in enumerate(states):
            for name, sq in [("none", {"events": []})] + list(seqs.items()):
                p = pool_future_protocol(pub, st, sq["events"], level_nom)
                if check:
                    assert_public_policy(p, pub, allowed_restart_keys=src_keys)
                jobs.append((sid, p, {"role": "pool_future", "split": "pool", "no_store": True}))
                owners.append((si, name))
        for si in floor_idx:
            p = pool_future_protocol(pub, states[si], [], level_nom, floor=True)
            if check:
                assert_public_policy(p, pub, allowed_restart_keys=src_keys)
            jobs.append((sid, p, {"role": "pool_floor", "split": "pool", "no_store": True}))
            owners.append((si, "floor"))
            if synthetic:
                jobs.append((sid, pool_future_protocol(pub, states[si], [], level_nom),
                             {"role": "pool_floor32", "split": "pool", "no_store": True, "restart_round": "float32"}))
                owners.append((si, "r32"))
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
                    r0, car = carrier_r0(str(internal["system_hash"]), float(st["t"]), vec)
                    put_carrier(store_root, sid, str(internal["system_hash"]), car)
                    equivs.append({"of": st["state_id"], "si": si, "j": j, "r0": r0})
            for eq in equivs:
                st = states[eq["si"]]
                for name, sq in [("none", {"events": []})] + list(seqs.items()):
                    p = pool_future_protocol(pub, st, sq["events"], level_nom)
                    p["r0"] = eq["r0"]
                    jobs.append((sid, p, {"role": "pool_equiv", "split": "pool", "no_store": True}))
                    owners.append((f"e{eq['si']}_{eq['j']}", name))
        arrays: dict[str, np.ndarray] = {}
        truth_arrays: dict[str, np.ndarray] = {}
        n_med = round(HORIZON_FRACTIONS["medium"] * float(pub["t_end_default"]) / float(pub["dt"]))
        n_fut = round(POOL_FUTURE_FRAC * float(pub["t_end_default"]) / float(pub["dt"]))
        for c in range(0, len(jobs), CHUNK):
            for (si, name), r in zip(owners[c: c + CHUNK], run(jobs[c: c + CHUNK])):
                if "error" in r:
                    errors.append({"role": "pool_future", "what": name, "error": r["error"]})
                    continue
                tag = si if isinstance(si, str) else f"s{si}"
                arrays[f"{tag}_{name}_y"] = np.asarray(r["y"], np.float32)
                if name == "none":
                    # P4-D14: the observed microstate only for the no-intervention future, over the primary horizon; the SIMULATED input
                    arrays[f"{tag}_none_x"] = np.asarray(r["x"], np.float32)[: n_med + 1]
                    arrays[f"{tag}_none_u"] = np.asarray(r["u"], np.float32)
                if with_truth and r.get("truth", {}).get("z") is not None:
                    truth_arrays[f"{tag}_{name}_z"] = np.asarray(r["truth"]["z"], np.float32)
        for si in floor_idx:
            if not synthetic and f"s{si}_none_y" in arrays:
                arrays[f"s{si}_r32_y"] = arrays[f"s{si}_none_y"]
            cont = continuation_future(ddir, states[si], n_fut)
            if cont is not None:
                arrays[f"s{si}_cont_y"] = cont
        if public_part:
            bad = [k for k in arrays if not PUBLIC_FUTURE_KEY.match(k)]
            if bad:
                raise AssertionError(f"non-public arrays {bad[:5]} in the public pool futures of {sid}")
        (ddir / "pools").mkdir(parents=True, exist_ok=True)
        np.savez_compressed(ddir / "pools" / "futures.npz", **arrays)
        if truth_arrays:
            (tdir / "pools").mkdir(parents=True, exist_ok=True)
            np.savez_compressed(tdir / "pools" / f"{dest}_futures_truth.npz", **truth_arrays)
        (ddir / "pools" / "pool.json").write_text(json.dumps({"states": states, "sequences": seqs, "level": level_nom,
                                                              "future_s": POOL_FUTURE_FRAC * float(pub["t_end_default"]), "policy": policy,
                                                              "equivalents": [{k: v for k, v in e.items() if k != "r0"} for e in equivs],
                                                              "floor_states": [states[si]["state_id"] for si in floor_idx],
                                                              "floors": FLOOR_DOC},
                                                             indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        out["counts"]["pool_states"] = len(states)
        out["counts"]["pool_equivalents"] = len(equivs)
        out["counts"]["pool_sequences"] = sorted(seqs)
        out["counts"]["pool_floor_states"] = len(floor_idx)
        out["counts"]["pool_bytes"] = int(sum((ddir / "pools" / f).stat().st_size for f in ("futures.npz", "pool.json")))
    lift_cases: list[dict] = []
    if "tests" in sets:
        lift_cases = pick_lift_cases(lift_src, rng_of("lift", tier, seed, sid, policy))
        (ddir / "lift_cases.json").write_text(json.dumps(lift_cases, indent=1) + "\n", encoding="utf-8", newline="\n")
    # every restart source of the part (rows' restarts, lift cases, pool states, truth-equivalent states) must be a stored record of THIS
    # system with its full state: evaluations and the service restart from these records (LOG P4-D50: a validation system's lift
    # cases were refused at evaluation time)
    pool_keys: list[str] = []
    if (ddir / "pools" / "pool.json").exists():
        pj = json.loads((ddir / "pools" / "pool.json").read_text(encoding="utf-8"))
        pool_keys = [s.get("store_key") for s in pj.get("states") or []]
    eq_keys = [(e.get("r0") or {}).get("key") for e in equivs if (e.get("r0") or {}).get("kind") == "restart"]
    keys = [row_store_key.get(k, k) for k in restart_keys] + [c["store_key"] for c in lift_cases] + pool_keys + eq_keys
    bad = restart_source_problems(store_root, sid, str(internal.get("system_hash") or ""), keys, need_state=truth_system is not None)
    if bad:
        raise RuntimeError(f"{sid} ({dest}): {len(bad)} restart sources are not records of this system: {bad[:5]}")
    writer.close({"part": dest, "policy": policy, "tier": tier})
    if public_part:
        out["counts"]["public_check"] = assert_public_part(ddir)
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


def own(a) -> np.ndarray | None:
    """A read-only float64 COPY that owns its memory (review F, minor 2: a view of a stored trajectory would hand a model the whole
    trajectory, future included, through `.base`)."""
    if a is None:
        return None
    b = np.array(a, dtype=np.float64, copy=True)
    b.setflags(write=False)
    return b


def identity_cell(family: str, target_set, edges, mclass: str) -> str:
    """The IDENTITY CELL of a test item (review E, M2; PROTOCOL 5.1): family x target set (edge set for edge families) x magnitude
    class; the resampling unit within a system (the family is recorded too, for two-stage resampling)."""
    tg = sorted(int(u) for u in (target_set or ()))
    ed = sorted([int(a), int(b)] for a, b in (edges or ())) if edges else None
    return json.dumps([family, tg, ed, mclass], separators=(",", ":"))


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
    it. `roles` restricts to some roles (e.g. ('in', 'passive')). Every array is the item's own read-only copy (review F, minor 2).
    GROUP (the resampling unit): intervention items = their IDENTITY CELL (`identity_cell`, review E M2; meta['identity_cell'] and
    `family` for two-stage resampling), passive windows = their trajectory. Horizons use the item's own dt (the temporal-sampling
    items are recorded at 2 dt)."""
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
                items.append(TestItem(item_id=f"{r.key[:20]}@p{j}", system_id=r.system_id, dt=dt, x_hist=own(r.x[: i0 + 1]),
                                      u_hist=own(r.u[: i0 + 1]), u_future=own(r.u[i0: i0 + h + 1]), events=[],
                                      y_future=own(y_true[i0: i0 + h + 1]), y_twin=None, family=r.family, shift="passive",
                                      onset=float(r.t[i0]), group=r.key, x_future=own(r.x[i0: i0 + h + 1]),
                                      z_true=(own(zt[i0]) if zt is not None else None), z_obs=(own(zo[i0]) if zo is not None else None),
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
                comp_d[part] = {"events": relative_events(P.validate(cr.protocol)["events"], t0), "y_future": own(cy[i0: i0 + h + 1])}
        # dz_true (the exact true latent effect of the first instantaneous event) is left to evaluate_truth.attach_truth, which
        # computes it with the generator from meta["state"] (harness.attach_states); dz_true_next (the true latent difference item -
        # twin one sample after the onset: what a rollout difference and the lift miss measure; review H, N4) comes from the truth
        # store's z series of the item and its twin
        dz = None
        ztw = ttw.get("z")
        dz_next = (own(np.asarray(zt[i0 + 1], np.float64) - np.asarray(ztw[i0 + 1], np.float64))
                   if zt is not None and ztw is not None and len(zt) > i0 + 1 and len(ztw) > i0 + 1 else None)
        told_rel = relative_events(P.validate(dict(r.protocol, events=told))["events"], t0)
        mclass = r.meta.get("mclass", "na")
        cell = identity_cell(r.family, r.meta.get("target_set"), r.meta.get("edges") if r.family in ("edge.w", "edge.rm") else None, mclass)
        items.append(TestItem(item_id=r.key[:24], system_id=r.system_id, dt=dt, x_hist=own(r.x[: i0 + 1]), u_hist=own(r.u[: i0 + 1]),
                              u_future=own(r.u[i0: i0 + h + 1]), events=told_rel, y_future=own(y_true[i0: i0 + h + 1]),
                              y_twin=own(ytw[i0: i0 + h + 1]), family=r.family, shift=role, magnitude_class=mclass,
                              target_set=tuple(int(u) for u in r.meta.get("target_set") or ()), onset=t0, group=f"cell:{cell}",
                              x_future=own(r.x[i0: i0 + h + 1]), x_twin_future=own(tw.x[i0: i0 + h + 1]),
                              true_events=(relative_events(r.protocol["events"], t0) if r.meta.get("model_events") else None),
                              components=comp_d, z_true=(own(zt[i0]) if zt is not None else None),
                              z_obs=(own(zo[i0]) if zo is not None else None),
                              dz_true=dz, dz_true_next=dz_next,
                              meta={"key": r.key, "twin": tw.key, "cell": r.meta.get("cell"), "identity_cell": cell,
                                                "proxy": bool(r.meta.get("proxy")), "store_key": r.meta.get("store_key"),
                                                "twin_store_key": tw.meta.get("store_key"), "params_seed": r.protocol["params_seed"]}))
    return items


def pool_from_files(pub: dict, held, hdir: Path, truth_dir: Path | None = None, *, part: str | None = None):
    """evalio.Pool of one system. The sequences' common future input is the SIMULATED input of the no-intervention futures (review
    H, minor 2; identical for every state, checked). NUMERICAL FLOOR (review H, B1; PROTOCOL 5.5): each floor state carries
    `PoolState.floor_futures` = {"noop": [the no-intervention future, its repeat with a no-op breakpoint one sample after the
    restart], "f32": [the float64 continuation, the restart from the float32-rounded stored state]} (readout arrays (H+1, n_y), row 0
    = the state's sample); the evaluator computes both floors in its own units. `floor_div` is not produced (None: the old raw-unit
    RMS is retired). Truth-equivalent states read their true latent from truth/<system>/pools/<part>_futures_truth.npz (F-B1)."""
    from .evalio import Pool, PoolState
    jpath = hdir / "pools" / "pool.json"
    if not jpath.exists():
        return None
    part = part or hdir.parent.name
    meta = json.loads(jpath.read_text(encoding="utf-8"))
    by_key = {r["key"]: r for r in held.rows}
    dt = float(pub["dt"])
    n_u = int(pub.get("input_dim", 1))
    fut_T = round(float(meta["future_s"]) / dt)
    with np.load(hdir / "pools" / "futures.npz") as z:
        arr = {k: z[k] for k in z.files}
    ztruth: dict[str, np.ndarray] = {}
    if truth_dir is not None and (truth_dir / "pools" / f"{part}_futures_truth.npz").exists():
        with np.load(truth_dir / "pools" / f"{part}_futures_truth.npz") as z:
            ztruth = {k: z[k] for k in z.files}
    u_keys = [k for k in arr if k.startswith("s") and k.endswith("_none_u")]
    if u_keys:
        u_future = np.asarray(arr[u_keys[0]], np.float64).reshape(fut_T + 1, -1)
        for k in u_keys[1:]:
            if not np.array_equal(np.asarray(arr[k], np.float64).reshape(u_future.shape), u_future):
                raise ValueError(f"pool of {pub['system_id']}: the no-intervention futures do not share their input ({k})")
    else:                                                    # pools built before review H: the nominal level
        u_future = np.full((fut_T + 1, n_u), float(meta["level"]))
    u_future.setflags(write=False)
    seqs = {"none": {"events": [], "u_future": u_future, "family": "none", "kind": "none"}}
    for name, sq in meta["sequences"].items():
        seqs[name] = {"events": sq["events"], "u_future": u_future, "family": sq["family"], "kind": sq["kind"]}
    states = []
    cache: dict[str, object] = {}
    floor_ids = set(meta.get("floor_states") or [])
    for si, st in enumerate(meta["states"]):
        row = by_key.get(st["key"])
        if row is None or f"s{si}_none_y" not in arr:
            continue
        if st["key"] not in cache:
            cache[st["key"]] = held.load(row)
        r = cache[st["key"]]
        i = int(st["index"])
        futures = {name: own(arr[f"s{si}_{name}_y"]) for name in seqs if f"s{si}_{name}_y" in arr}
        xfut = {name: own(arr[f"s{si}_{name}_x"]) for name in seqs if f"s{si}_{name}_x" in arr}
        smeta = {"store_key": st["store_key"], "t": st["t"], "params_seed": st["params_seed"]}
        ff = {}
        if f"s{si}_floor_y" in arr:
            ff["noop"] = [futures["none"], own(arr[f"s{si}_floor_y"])]
        if f"s{si}_cont_y" in arr and f"s{si}_r32_y" in arr:
            ff["f32"] = [own(arr[f"s{si}_cont_y"]), own(arr[f"s{si}_r32_y"])]
        tr = _truth_arrays(truth_dir, r.key)
        has_eq = any(e["si"] == si for e in meta.get("equivalents") or [])
        states.append(PoolState(state_id=st["state_id"], x_hist=own(r.x[: i + 1]), u_hist=own(r.u[: i + 1]), y_now=own(r.y[i]),
                                traj=r.key, draw=str(st["draw"]), futures=futures, x_futures=xfut,
                                z_true=(own(tr["z"][i]) if "z" in tr else None), z_obs=(own(tr["z_obs"][i]) if "z_obs" in tr else None),
                                equiv_class=(st["state_id"] if has_eq else None), floor_div=None, floor_futures=(ff or None),
                                meta=smeta))
    # truth-equivalent states (synthetic): same TRUE causal state as their source pool state; no history exists, so x_hist is the
    # single observed sample at the state and meta['truth_only'] marks them: never matched by a model's latent (reference only)
    for e in meta.get("equivalents") or []:
        tag = f"e{e['si']}_{e['j']}"
        if f"{tag}_none_y" not in arr:
            continue
        src = meta["states"][e["si"]]
        futures = {name: own(arr[f"{tag}_{name}_y"]) for name in seqs if f"{tag}_{name}_y" in arr}
        xfut = {name: own(arr[f"{tag}_{name}_x"]) for name in seqs if f"{tag}_{name}_x" in arr}
        x0 = own(arr[f"{tag}_none_x"][:1])
        u0 = own(arr[f"{tag}_none_u"][:1]) if f"{tag}_none_u" in arr else u_future[:1]
        z0 = own(ztruth[f"{tag}_none_z"][0]) if f"{tag}_none_z" in ztruth else None
        states.append(PoolState(state_id=f"{src['state_id']}~eq{e['j']}", x_hist=x0, u_hist=u0, y_now=futures["none"][0], traj=f"equiv:{src['key']}",
                                draw=str(src["draw"]), futures=futures, x_futures=xfut, z_true=z0, equiv_class=src["state_id"],
                                meta={"truth_only": True, "equiv_of": src["state_id"]}))
    return Pool(system_id=pub["system_id"], dt=dt, states=states, sequences=seqs, floor_div=None,
                meta={"future_s": float(meta["future_s"]), "n_truth_only": sum(1 for s in states if s.meta.get("truth_only")),
                      "x_futures": "no-intervention future only, over the primary horizon (P4-D14)",
                      "floor_states": sorted(floor_ids), "floors": meta.get("floors") or {}})


def truth_samples(pub: dict, held, truth_dir: Path | None) -> list:
    """evalio.StateSample list (synthetic latent recovery): N_TRUTH_SAMPLES encoding points per passive test trajectory (own
    read-only copies)."""
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
            out.append(StateSample(sample_id=f"{r.key[:16]}@{int(i)}", x_hist=own(r.x[: i + 1]), u_hist=own(r.u[: i + 1]),
                                   dt=float(r.protocol["dt"]), group=r.key, z_true=own(tr["z"][i]),
                                   z_obs=(own(tr["z_obs"][i]) if "z_obs" in tr else None),
                                   draw=(own(np.asarray(tr["draw"]).reshape(-1)) if "draw" in tr else None)))
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
            "items": items_from_set(pub, held, truth_dir, roles=roles), "pool": pool_from_files(pub, held, hd, truth_dir, part=part),
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
    "trap": (("public", ("public",), "public"), ("eval", ("tests", "pool_src"), "full")),
}
REAL_PARTS = {
    "public": (("public", ("public", "tests", "pool_src"), "public"),),
    "B": (("eval", ("tests", "pool_src"), "public"),),
    "C": (("eval", ("tests", "pool_src"), "full"),),
}


def build_tier(tier: str, *, generator: tuple | None = None, workers: int = 4, systems: list[str] | None = None, root: Path = SUITES,
               store_root: Path = STORE, run=None, parts=None) -> dict:
    """Build a synthetic tier: 'dev' / 'val' (before development), 'conf' and 'trap' (after the lock only); 'toy' / 'toyC' = the
    adapter's toy systems (tests). Parts per tier: TIER_PARTS."""
    if tier in LOCKED_TIERS:
        require_lock(f"the {tier} tier")
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


REAL_TIERS = {"public": "real_public", "B": "real_levelb", "C": "real_levelc"}


def build_real(level: str, *, workers: int = 4, systems: list[str] | None = None, root: Path = REAL_SETS, store_root: Path = STORE,
               run=None) -> dict:
    """Real systems: level 'public' (D0 / D1 / validation and the public evaluation subset: the public development data), 'B' (the
    Level B validation sets, drawn under the PUBLIC policy with public-range seeds from SALTED streams; orchestrator-held) or 'C'
    (the hidden test with every shift, OOD and robustness set; after the lock only; hidden-range seeds from the salt). Stream seed:
    `real_stream_seed` (0 for the public data, salted otherwise)."""
    from .systems import load_real_internal, public_view
    if level == "C":
        require_lock("the real hidden test")
    internals = load_real_internal()
    sids = sorted(internals) if not systems else [s for s in sorted(internals) if s in set(systems)]
    tier = REAL_TIERS[level]
    seed = real_stream_seed(level)
    backend = LocalBackend(internals, tier=tier, seed=0, generator=None, store_root=store_root, workers=workers) if run is None else None
    runner = run or backend.run
    out = {"level": level, "tier": tier, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": {}}
    dirs = tier_dirs(tier, root)
    try:
        for sid in sids:
            out["systems"][sid] = {}
            for dest, sets, policy in REAL_PARTS[level]:
                built = build_system(public_view(internals[sid]), internals[sid], tier=tier, seed=seed, level=("C" if level == "C" else "B"),
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


# ================================================================================================================ remote builds (Modal)
#: container paths of the Phase 4 volumes (brainir_causal.p4modal.app): PUBLIC parts on the FIT volume; orchestrator-held parts,
#: truth, onset states and every NON-public store record (synthetic records carry the true state; held-out real records) on the EVAL
#: volume; the store records of the PUBLIC real data on the STORE volume (restart sources of the simulation service's remote path)
REMOTE = {"fit": "/fitvol/data", "eval": "/evalvol/data", "eval_store": "/evalvol/store", "store": "/storevol/store"}
GENERATOR_CONTAINER = "/repo/benchmarks/causal_state_v1/generator/src"
GENERATOR_REL = "benchmarks/causal_state_v1/generator/src"


def spec_to_dict(sp: Spec) -> dict:
    d = asdict(sp)
    d["target_set"] = [int(u) if isinstance(u, (int, np.integer)) else u for u in sp.target_set]
    return json.loads(json.dumps(d, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def spec_from_dict(d: dict) -> Spec:
    return Spec(**{**d, "target_set": tuple(d.get("target_set") or ())})


def remote_dirs(tier: str, *, kind: str) -> dict[str, str]:
    """Container paths of a tier's parts: {"base", "public", "eval", "truth"} (POSIX strings). Real tiers live under <volume>/real,
    synthetic tiers under <volume>/suites."""
    sub = "real" if kind == "real" else "suites"
    pub = PurePosixPath(REMOTE["fit"]) / sub / tier
    ev = PurePosixPath(REMOTE["eval"]) / sub / tier
    return {"base": str(ev), "public": str(pub / "public"), "eval": str(ev / "eval"), "truth": str(ev / "truth")}


def write_onset_states(sid: str, dirs: dict[str, Path], store_root: Path | str) -> dict:
    """truth/<system>/onset_states.npz: the full microstate at the onset of every intervention test item of the system's built parts
    (synthetic truth: `harness.attach_states` reads it, so an evaluation never needs the store records). The onset is the one
    `items_from_set` uses (earliest start of the true and the told events)."""
    from .data import ExperimentSet
    from .store import TrajectoryStore
    store = TrajectoryStore(store_root)
    out: dict[str, np.ndarray] = {}
    missing = 0
    for part in ("eval", "public"):
        d = Path(dirs[part]) / _safe(sid)
        if not (d / "index.jsonl").exists():
            continue
        held = ExperimentSet.load(d, lazy=True)
        for row in held.rows:
            q = row.get("protocol") or {}
            if row.get("split") != "test" or not q.get("events"):
                continue
            meta = row.get("meta") or {}
            rec = store.get(meta["store_key"]) if meta.get("store_key") else None
            if rec is None or "state" not in rec:
                missing += 1
                continue
            told = meta.get("model_events") or q["events"]
            onset = min(min(P.event_start(e) for e in q["events"]), min(P.event_start(e) for e in P.validate(dict(q, events=told))["events"]))
            t = np.asarray(rec["t"], float)
            i = round((onset - t[0]) / (t[1] - t[0]))
            if 0 <= i < len(rec["state"]):
                out[row["key"]] = np.asarray(rec["state"][i], np.float64)
    tdir = Path(dirs["truth"]) / _safe(sid)
    tdir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(tdir / "onset_states.npz", **out)
    return {"n": len(out), "missing_records": missing}


def _same_arrays(a: Path, b: Path) -> tuple[bool, bool]:
    """(the two store records hold bit-identical arrays, the second one's info carries a host fingerprint)."""
    with np.load(a, allow_pickle=False) as za, np.load(b, allow_pickle=False) as zb:
        fa, fb = set(za.files) - {"info"}, set(zb.files) - {"info"}
        same = fa == fb and all(za[k].dtype == zb[k].dtype and np.array_equal(za[k], zb[k]) for k in fa)
        has_host = "info" in zb.files and "host" in json.loads(str(zb["info"]))
    return same, has_host


def publish_store(local_root: Path | str, dest_root: Path | str, *, source: str = "remote-build") -> dict:
    """Copy the records of a local (container) store into a VOLUME store (same layout as brainir_causal.store and
    p4modal.remote.VolumeStore): records not yet present are written atomically; the index lines go to ONE new shard file, so
    concurrent publishers never write the same file. A record ALREADY present is compared array by array with the new one (a free
    bit-identity check across builds and hosts): identical arrays keep the present file unless it lacks the host fingerprint (review
    H, M5; then the new record replaces it: 'upgraded'); differing arrays are 'mismatch' (listed, never overwritten). The caller
    commits the volume."""
    local, dest = Path(local_root), Path(dest_root)
    n_new = n_skip = n_upg = 0
    mismatch: list[str] = []
    shard_lines = []
    idx = {}
    if (local / "index.jsonl").exists():
        for line in (local / "index.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                idx[r["key"]] = r
            except (json.JSONDecodeError, KeyError):
                continue
    for p in sorted((local / "rec").rglob("*.npz")):
        key = p.stem
        tgt = dest / "rec" / key[:2] / f"{key}.npz"
        if tgt.exists():
            same, has_host = _same_arrays(p, tgt)
            if not same:
                mismatch.append(key)
                continue
            if has_host:
                n_skip += 1
                continue
            n_upg += 1
        else:
            n_new += 1
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tmp = tgt.with_name(f"{key}.{uuid.uuid4().hex[:8]}.tmp")
        shutil.copyfile(p, tmp)
        os.replace(tmp, tgt)
        shard_lines.append(json.dumps({**idx.get(key, {"key": key}), "published_by": source}, sort_keys=True))
    if shard_lines:
        shard = dest / "index_shards" / f"{source}_{uuid.uuid4().hex[:12]}.jsonl"
        shard.parent.mkdir(parents=True, exist_ok=True)
        shard.write_text("\n".join(shard_lines) + "\n", encoding="utf-8", newline="\n")
    return {"new": n_new, "present": n_skip, "upgraded": n_upg, "mismatch": len(mismatch), "mismatch_keys": mismatch[:50]}


def file_manifest(d: Path | str) -> dict:
    """{relative path: [sha256, bytes]} of every file under d."""
    d = Path(d)
    out = {}
    if not d.exists():
        return out
    for p in sorted(q for q in d.rglob("*") if q.is_file()):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        out[p.relative_to(d).as_posix()] = [h.hexdigest(), p.stat().st_size]
    return out


def build_system_job(job: dict) -> dict:
    """Build ONE system's parts inside a (Modal) container from a LOCALLY planned job (`plan_remote_job`): simulate in a process pool
    of `workers` through a container-local store, write the sets into the job's directories (volume paths), write the synthetic onset
    states, publish the store records to the job's volume store, and return counts, errors and a file manifest (sha256)."""
    t0 = time.time()
    sid, kind = job["sid"], job["kind"]
    dirs = {k: Path(v) for k, v in job["dirs"].items()}
    store_root = Path(job.get("store_root") or f"/tmp/p4build/{_safe(sid)}/store")
    gen = tuple(job["generator"]) if job.get("generator") else None
    internal, pub = job["internal"], job["pub"]
    truth_obj = None
    if kind == "synthetic":
        truth_obj = _synthetic_systems(internal["tier"], int(internal["tier_seed"]), gen)[sid]
    backend = LocalBackend({sid: internal}, tier=job["tier"], seed=int(job["seed"]), generator=gen, store_root=store_root,
                           workers=int(job.get("workers", 4)))
    parts_out = {}
    try:
        for part in job["parts"]:
            built = build_system(pub, internal, tier=job["tier"], seed=int(job["seed"]), level=job["level"], run=backend.run, dirs=dirs,
                                 dest=part["dest"], sets=tuple(part["sets"]), policy=part["policy"],
                                 with_truth=bool(job.get("with_truth", True)), truth_system=truth_obj, store_root=store_root,
                                 specs=[spec_from_dict(d) for d in part["specs"]], pool_seq_seed=part.get("pool_seq_seed"))
            parts_out[part["dest"]] = built
    finally:
        backend.close()
    onset = write_onset_states(sid, dirs, store_root) if kind == "synthetic" else None
    published = publish_store(store_root, job["publish_store"], source=f"build_{job['tier']}_{_safe(sid)}") if job.get("publish_store") else None
    manifest = {p["dest"]: file_manifest(dirs[p["dest"]] / _safe(sid)) for p in job["parts"]}
    manifest["truth"] = file_manifest(dirs["truth"] / _safe(sid))
    if job.get("cleanup_store", True):
        shutil.rmtree(store_root, ignore_errors=True)
    return {"sid": sid, "tier": job["tier"], "parts": parts_out, "onset_states": onset, "published": published, "manifest": manifest,
            "wall_s": round(time.time() - t0, 1), "workers": int(job.get("workers", 4))}


def plan_remote_job(kind: str, sid: str, *, level: str | None = None, tier: str | None = None, generator: tuple | None = None,
                    workers: int = 16, container_generator: str | None = GENERATOR_CONTAINER) -> dict:
    """The job of `build_system_job` for one system, planned HERE (where the salt is: hidden-range and salted seeds are derived
    locally and only the resulting protocols, spare seeds and stream seeds travel; the job's `seed` of a salted tier is secret: never
    record it). kind 'real' with level 'public' | 'B' | 'C' (C only after the method lock); kind 'synthetic' with
    tier 'dev' | 'val' | 'conf' (conf only after the lock) | 'toy' | 'toyC' and the LOCAL generator (dir, package)."""
    if kind == "real":
        from .systems import load_real_internal, public_view
        if level == "C":
            require_lock("the real hidden test")
        internal = load_real_internal()[sid]
        pub = public_view(internal)
        tier_name, seed, lev = REAL_TIERS[level], real_stream_seed(level), ("C" if level == "C" else "B")
        parts_def = REAL_PARTS[level]
        pool_fn = None
        publish = REMOTE["store"] if level == "public" else REMOTE["eval_store"]
        gen_c = None
    else:
        if tier in LOCKED_TIERS:
            require_lock(f"the {tier} tier")
        seed = tier_seed(tier)
        pubs, ints, _ = synthetic_tier_records(tier, seed, generator)
        pub, internal = pubs[sid], ints[sid]
        tier_name, lev = tier, LEVEL_OF_TIER.get(tier, "B")
        parts_def = TIER_PARTS[tier]
        pool_fn = getattr(_synthetic_systems(tier, seed, generator)[sid], "pool_states", None)
        publish = REMOTE["eval_store"]
        gen_c = None if tier in ("toy", "toyC") else [container_generator, (generator or (None, "p4synth"))[1]]
    parts = []
    for dest, sets, policy in parts_def:
        specs = plan_system(pub, internal, tier=tier_name, seed=seed, level=lev, sets=tuple(sets), pool_state_fn=pool_fn, policy=policy)
        part = {"dest": dest, "sets": list(sets), "policy": policy, "specs": [spec_to_dict(s) for s in specs]}
        if "pool_src" in sets and dest != "public":
            part["pool_seq_seed"] = pool_seq_seed_of(tier_name, sid, dest, policy)       # salted here; the container has no salt
        parts.append(part)
    return {"sid": sid, "kind": kind, "tier": tier_name, "seed": int(seed), "level": lev, "pub": pub, "internal": internal, "parts": parts,
            "dirs": remote_dirs(tier_name, kind=kind), "store_root": f"/tmp/p4build/{_safe(sid)}/store", "workers": int(workers),
            "generator": gen_c, "publish_store": publish, "with_truth": True}


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
    b.add_argument("--tier", required=True, choices=("dev", "val", "conf", "trap", "toy", "toyC"))
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


def host_summary(root: str) -> dict:
    """The host fingerprints of the rows of one built system directory (index.jsonl; review H N6, M5): rows, rows with a fingerprint,
    rows whose fingerprint is admissible (`p4modal.gate`: flagged admissible, AVX2 present, no AVX-512F) and the distinct
    (vendor, model, machine, os) descriptions. Works on local copies and, through a Modal call, on volume directories."""
    p = Path(root) / "index.jsonl"
    if not p.exists():
        return {"_missing": True}
    rows = with_host = adm = 0
    bad: list[str] = []
    cpus: dict[str, int] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        rows += 1
        h = (r.get("info") or {}).get("host")
        if not isinstance(h, dict):
            bad.append(str(r.get("key")))
            continue
        with_host += 1
        cpu = h.get("cpu") or {}
        ok = h.get("admissible") is True and cpu.get("avx2") is True and cpu.get("avx512f") is False
        adm += int(ok)
        if not ok:
            bad.append(str(r.get("key")))
        k = f"{cpu.get('vendor')}|{cpu.get('model')}|{h.get('machine')}|{h.get('os')}"
        cpus[k] = cpus.get(k, 0) + 1
    return {"rows": rows, "with_host": with_host, "admissible": adm, "not_admissible_or_missing": bad[:10], "hosts": cpus}


def hash_tree(root: str, *, max_files: int = 2_000_000) -> dict:
    """{relative POSIX path: [sha256, bytes]} of every file under `root` (a volume directory inside a Modal container; the freeze's
    dataset manifests). Text files are hashed as stored (datasets are written with LF)."""
    base = Path(root)
    out: dict[str, list] = {}
    if not base.is_dir():
        return {"_missing": True}
    for p in sorted(base.rglob("*")):
        if p.is_file() and not p.is_symlink():
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 22), b""):
                    h.update(chunk)
            out[p.relative_to(base).as_posix()] = [h.hexdigest(), p.stat().st_size]
            if len(out) > max_files:
                raise RuntimeError("too many files")
    return out
