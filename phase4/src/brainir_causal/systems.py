"""The Phase 4 REAL systems (ORCHESTRATOR SIDE), their capability and split records (research/phase4/INTERFACES.md section 3;
benchmarks/causal_state_v1/PROTOCOL.md sections 2-3).

The ten real systems are the ten public real systems of the previous benchmark (three full networks of the public tier-A bundle
and seven keep-only candidate mechanisms regenerated from public evidence), RE-ANONYMISED: networks -> letters A-C and the
mechanisms of a network -> m1, m2, ... by a SECRET random permutation drawn once (`secrets`); the map to the previous ids exists only
in `benchmarks/causal_state_v1/hidden/real_name_map.json`. Populations are unchanged: observed (x), readout (y), stimulus (u),
public targets (development interventions) and hidden targets (Level B / C only; mechanisms, as before, have all members public and
no hidden targets). Unit ids are the positions in the public bundle network (as before).

Files (`build_real_systems(write=True)`, or `python -m brainir_causal.systems --write`):
    benchmarks/causal_state_v1/public/systems_real_public.json    public records (no hidden targets, no network / dataset names,
                                                                  no previous ids); may enter a clean room
    benchmarks/causal_state_v1/hidden/real_systems_internal.json  + bundle network, keep set, hidden targets, content hash
    benchmarks/causal_state_v1/hidden/real_name_map.json          Phase 4 id -> previous id (answer-adjacent; never public)

Capability of every real system (`REAL_CAPABILITY`; magnitudes follow PROTOCOL.md section 3: classes 0.1 / 0.3 / 1 / 3 x the
moderate magnitude m_s; the development maximum is the strong class 3 m_s; `*.hi` = 1.5-3 x the development maximum):
    kick         m_s = 50/3 Hz, development max 50 Hz (as before), hi range [75, 150] Hz
    current      m_s = 20, development max 60 (input units, as before), hi range [90, 180]; a current lasting <= 0.15 s is a PULSE,
                 one lasting >= 0.3 s (or persistent) is SUSTAINED; durations in between are unclassified ('other')
    current_seq  segments >= 5 dt, amplitudes as current
    silence      any unit (the policy restricts targets); edge_scale factor in [0, 2], m_s = 0.3 (weakening depth 1 - f)
    param        gain / threshold / tau; m_s: gain 0.3 (|g - 1|), threshold 1.0 (input units), tau 0.3 (|c - 1|)
    init         r0 'state' on observed units with rates <= 200 Hz; r0 'restart' from own / public trajectories
    stimulus     nominal level 1.0 (onset <= 0.15 s); development range [0.55, 1.45] or 0
    params       public seeds < 10^9; no nominal draw (every trajectory draws its parameters; 'obs.param' never occurs);
                 params_spread 1.0 only in development (other spreads are OOD test conditions)
    noise        weight noise sd <= 0.1; observation noise sd <= 0.5 x obs_scale in development; process noise NOT supported (the
                 frozen integrator is deterministic; the engine refuses it)
    timing       dt = 1 ms only (the nominal dt: coarser sampling is a Level C OOD condition, review H M3), t_end <= 4 s in
                 development
obs_scale: pooled standard deviation of the observed values (x resp. y) over the system's public nominal training trajectories of
the previous benchmark's public real data (the same engine produces bit-identical trajectories for those protocols).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path

import numpy as np

from . import families as F
from .realsim import ENGINE_VERSION, RealEngine, RealSystem

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "causal_state_v1"
PUBLIC_REAL = BENCH / "public" / "systems_real_public.json"
INTERNAL_REAL = BENCH / "hidden" / "real_systems_internal.json"
NAME_MAP = BENCH / "hidden" / "real_name_map.json"
def _public_bundle() -> Path:
    """The previous benchmark's public tier-A bundle: the unique benchmarks/*/public_blind with a manifest (found, not named: this
    file enters the review room; early review F, F-M1)."""
    found = sorted(p for p in (ROOT / "benchmarks").glob("*/public_blind") if (p / "manifest.json").is_file())
    return found[0] if len(found) == 1 else ROOT / "benchmarks" / "_public_bundle_not_unique_" / "public_blind"


BUNDLE = _public_bundle()
P3_INTERNAL = ROOT / "benchmarks" / "state_discovery_v1" / "hidden" / "systems_internal.json"
P3_PUBLIC_DATA = ROOT / "data" / "phase3" / "real_public"

DT, T_END_DEFAULT = 0.001, 2.0
HORIZON_FRACTIONS = {"short": 0.025, "medium": 0.125, "long": 0.5}      # PROTOCOL.md section 4 (medium = primary)
PUBLIC_SEED_MAX = 10**9
COST_UNITS = {"full": 10, "mech": 3}                                   # simulation budget units per trajectory

REAL_CAPABILITY = {
    "kick": {"supported": True, "moderate": 50.0 / 3.0, "max": 50.0, "hi_range": [75.0, 150.0]},
    "current": {"supported": True, "moderate": 20.0, "max": 60.0, "hi_range": [90.0, 180.0], "pulse_max_duration": 0.15,
                "sustained_min_duration": 0.3},
    "current_seq": {"supported": True, "moderate": 20.0, "max": 60.0, "min_seg_steps": 5},
    "silence": {"supported": True},
    "edge_scale": {"supported": True, "moderate": 0.3, "factor_range": [0.0, 2.0]},
    "param": {"supported": True, "fields": ["gain", "threshold", "tau"], "moderate": {"gain": 0.3, "threshold": 1.0, "tau": 0.3}},
    "init": {"state": False, "restart": True, "units": "observed", "max_value": 200.0},     # r0 'state' = a kick at t = 0 (LOG P4-D36)
    "stimulus": {"channels": 1, "nominal_level": 1.0, "max_onset": 0.15, "range": [0.55, 1.45], "allow_zero": True},
    "params": {"public_seed_max": PUBLIC_SEED_MAX, "nominal_seed": None, "dev_spread": 1.0, "spread_range": [0.0, 3.0]},
    "process_noise": {"supported": False},
    "weight_noise": {"max_sd": 0.1},
    "obs_noise": {"max_sd": 0.5},
    "timing": {"dt_allowed": [0.001], "t_end_max": 4.0},
    "latent": {"supported": False},
}


def real_split() -> dict:
    """The real split record (PROTOCOL.md section 3): trained families on public targets; every other supported family held out;
    the hidden-only families never simulatable in development."""
    train = list(F.REAL_TRAIN)
    return F.split_record(train, F.supported_families(REAL_CAPABILITY), rotation=None)


# ------------------------------------------------------------------------------------------------ anonymisation
def _name_map(p3: dict, create: bool) -> dict:
    """{phase4 id: previous id}; drawn once with `secrets` (not reproducible from code), then read from the hidden file."""
    if NAME_MAP.exists():
        m = json.loads(NAME_MAP.read_text(encoding="utf-8"))["map"]
        if sorted(m.values()) != sorted(p3):
            raise RuntimeError("real_name_map.json does not cover the previous systems exactly")
        return m
    if not create:
        raise FileNotFoundError(NAME_MAP)
    rng = secrets.SystemRandom()
    nets = sorted({d["network"] for d in p3.values()})
    letters = ["A", "B", "C", "D", "E", "F"][: len(nets)]
    rng.shuffle(letters)
    net_letter = dict(zip(nets, letters))
    m: dict[str, str] = {}
    for net in nets:
        full = [sid for sid, d in p3.items() if d["network"] == net and d["mode"] == "full"]
        mechs = [sid for sid, d in p3.items() if d["network"] == net and d["mode"] == "mech"]
        rng.shuffle(mechs)
        for sid in full:
            m[f"real:{net_letter[net]}:full"] = sid
        for j, sid in enumerate(mechs, start=1):
            m[f"real:{net_letter[net]}:m{j}"] = sid
    NAME_MAP.parent.mkdir(parents=True, exist_ok=True)
    NAME_MAP.write_text(json.dumps({"note": "Phase 4 real system id -> previous benchmark id; drawn with secrets.SystemRandom; "
                                            "ANSWER-ADJACENT (links to earlier hidden results); never into a room",
                                    "map": dict(sorted(m.items()))}, indent=1) + "\n", encoding="utf-8", newline="\n")
    return m


def _obs_scale(p3_id: str) -> dict:
    idx = [json.loads(line) for line in (P3_PUBLIC_DATA / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    xs, ys = [], []
    for r in idx:
        if r["system_id"] == p3_id and r["split"] == "train" and r["family"] == "nominal":
            with np.load(P3_PUBLIC_DATA / "traj" / f"{r['key']}.npz") as z:
                xs.append(z["x"].astype(np.float64).ravel())
                ys.append(z["y"].astype(np.float64).ravel())
    if not xs:
        raise RuntimeError(f"no public nominal training trajectories for {p3_id}")
    return {"x": float(f"{np.concatenate(xs).std():.6g}"), "y": float(f"{np.concatenate(ys).std():.6g}"), "n_trajectories": len(xs)}


def public_graph(engine: RealEngine, s: RealSystem) -> dict:
    """The public connectivity summary (same construction as the previous benchmark): the signed synapse counts among the system's
    observed, readout, stimulus and member units, and their signs."""
    nodes = sorted(set(s.observed) | set(s.readout) | set(s.stimulus) | set(s.keep))
    W = engine.problem.W.tocsr()
    sub = W[nodes][:, nodes].tocoo()
    return {"nodes": nodes,
            "edges_post_pre_signed_count": [[nodes[i], nodes[j], float(v)] for i, j, v in zip(sub.row, sub.col, sub.data)],
            "signs": {str(n): int(engine.problem.signs[n]) for n in nodes}}


def build_real_systems(write: bool = False, create_map: bool = False) -> tuple[dict, dict]:
    """(public records, internal records), keyed by the Phase 4 system id."""
    p3 = json.loads(P3_INTERNAL.read_text(encoding="utf-8"))
    m = _name_map(p3, create=create_map)
    bundle_sha = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))["bundle_sha256"]
    engines: dict[str, RealEngine] = {}
    public, internal = {}, {}
    split = real_split()
    for sid in sorted(m):
        d = p3[m[sid]]
        net = d["network"]
        if net not in engines:
            engines[net] = RealEngine(BUNDLE, net)
        s = RealSystem(system_id=sid, network=net, mode=d["mode"], keep=tuple(d["keep"]), observed=tuple(d["observed"]),
                       readout=tuple(d["readout"]), stimulus=tuple(d["stimulus"]))
        dur = T_END_DEFAULT
        rec = {"system_id": sid, "kind": "real", "mode": d["mode"], "dt": DT, "t_end_default": dur,
               "horizons_s": {k: round(v * dur, 9) for k, v in HORIZON_FRACTIONS.items()},
               "n_units": None, "observed": list(d["observed"]), "readout": list(d["readout"]), "readout_dim": len(d["readout"]),
               "stimulus": list(d["stimulus"]), "input_dim": max(1, len(d["stimulus"])), "members": list(d["keep"]),
               "targets_public": sorted(int(x) for x in d["targets_public"]), "edges_public": [],
               "obs_scale": _obs_scale(m[sid]), "capability": json.loads(json.dumps(REAL_CAPABILITY)), "split": split,
               "cost_units": COST_UNITS[d["mode"]], "public_graph": public_graph(engines[net], s)}
        from .suites import assert_public_record
        assert_public_record(rec)                    # whitelisted keys, no per-unit capability field (review T, M1)
        public[sid] = rec
        internal[sid] = {**rec, "network": net, "keep": list(d["keep"]), "targets_heldout": sorted(int(x) for x in d["targets_heldout"]),
                         "system_hash": s.content_hash(bundle_sha), "engine": ENGINE_VERSION,
                         "meta": {"n_network": int(engines[net].problem.n)}}
    if write:
        PUBLIC_REAL.parent.mkdir(parents=True, exist_ok=True)
        INTERNAL_REAL.parent.mkdir(parents=True, exist_ok=True)
        PUBLIC_REAL.write_text(json.dumps(public, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        INTERNAL_REAL.write_text(json.dumps(internal, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return public, internal


# ------------------------------------------------------------------------------------------------ access
def load_real_public() -> dict:
    return json.loads(PUBLIC_REAL.read_text(encoding="utf-8"))


def load_real_internal() -> dict:
    return json.loads(INTERNAL_REAL.read_text(encoding="utf-8"))


def real_system(rec: dict) -> RealSystem:
    """The engine's system object of an INTERNAL record."""
    return RealSystem.from_record(rec)


def public_view(internal_rec: dict) -> dict:
    """The public part of an internal record (what may enter a room)."""
    drop = {"network", "keep", "targets_heldout", "system_hash", "engine", "meta"}
    return {k: v for k, v in internal_rec.items() if k not in drop}


def records_hash(records: dict) -> str:
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--create-map", action="store_true", help="draw the secret name map if it does not exist yet")
    args = ap.parse_args(argv)
    public, internal = build_real_systems(write=args.write, create_map=args.create_map)
    for sid, r in public.items():
        print(sid, r["mode"], len(r["observed"]), r["readout_dim"], len(r["targets_public"]), len(internal[sid]["targets_heldout"]),
              r["obs_scale"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
