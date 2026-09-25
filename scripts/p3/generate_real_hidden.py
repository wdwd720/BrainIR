"""state_discovery_v1 Level C: generate the REAL HIDDEN TEST (orchestrator; run ONLY after research/phase3/METHOD_LOCK.json exists).

    uv run --project phase3 python scripts/p3/generate_real_hidden.py [--workers 12] [--per-family 30]

Locked with the benchmark (its hash is in BENCHMARK_LOCK.json) and run once after the method lock. Seeds derive from the secret salt
(data/phase3/hidden/salt.txt, committed by sha256 before development). Produces data/phase3/real_hidden/ (never in any clean room):
    test trajectories of every hidden family of PROTOCOL.md section 3, a counterfactual twin (no events) for every intervention
    trajectory, and the H_micro pools: states sampled from pool trajectories, each restarted from its FULL microstate under the
    common nominal input for 250 ms (the future readout the evaluator compares), plus a numerical-floor twin per state (the same
    restart split at an extra breakpoint).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from brainir_state import data as D
from brainir_state import protocol as P
from brainir_state.realgen import HIDDEN_FAMILIES, INTERVENTION_FAMILIES, Sampler, counterfactual, family_protocol, hidden_seed, micro_pool_protocols
from brainir_state.realsim import RealEngine, RealSystem, dense
from brainir_state.store import TrajectoryStore

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "benchmarks" / "dng100" / "public_blind"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
DATA = ROOT / "data" / "phase3"
MICRO_STATES_PER_TRAJ, MICRO_FUTURE_S = 4, 0.25


def _sys(d: dict) -> RealSystem:
    return RealSystem(system_id=d["system_id"], network=d["network"], mode=d["mode"], keep=tuple(d["keep"]), observed=tuple(d["observed"]),
                      readout=tuple(d["readout"]), stimulus=tuple(d["stimulus"]))


_ENG: dict = {}


def _engine(net):
    if net not in _ENG:
        _ENG[net] = RealEngine(BUNDLE, net)
    return _ENG[net]


def _run(args):
    d, proto = args
    key, rec, _ = TrajectoryStore(DATA / "store").get_or_run(_engine(d["network"]), _sys(d), proto, d["system_hash"], meta={"source": "hidden"})
    return key, rec


def _micro_future(args):
    """Restart one sampled FULL microstate under the common input; also the numerical-floor twin (extra breakpoint)."""
    d, state, seed, t_s = args
    s = _sys(d)
    vals = {str(int(n)): float(v) for n, v in state.items() if v > 0}
    base = {"system": d["system_id"], "params_seed": seed, "t_end": MICRO_FUTURE_S, "dt": 0.001, "stimulus": [[0.0, 1.0]],
            "r0": {"kind": "state", "values": vals}}
    rec = _engine(d["network"]).run(s, base)
    twin = _engine(d["network"]).run(s, dict(base, stimulus=[[0.0, 1.0], [round(MICRO_FUTURE_S / 2 + 0.0005, 3), 1.0]]))
    return dense(rec, list(s.readout)), dense(twin, list(s.readout))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--per-family", type=int, default=30)
    args = ap.parse_args(argv)
    if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists():
        raise SystemExit("refusing: the Level C hidden test is generated only after research/phase3/METHOD_LOCK.json exists")
    salt = (DATA / "hidden" / "salt.txt").read_text(encoding="utf-8").strip()
    commit = json.loads((BENCH / "hidden" / "salt_commitment.json").read_text(encoding="utf-8"))["sha256_of_salt"]
    if hashlib.sha256(salt.encode()).hexdigest() != commit:
        raise SystemExit("salt does not match its commitment")
    systems = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    public = json.loads((BENCH / "public" / "systems_public.json").read_text(encoding="utf-8"))
    pub_ds = D.Dataset(DATA / "real_public")
    jobs, meta = [], []
    for sid, d in systems.items():
        A, B = d["targets_public"], d["targets_heldout"]
        s = _sys(d)
        pool = []   # state pool for init_state from PUBLIC nominal trajectories of this system (observed neurons only)
        for tr in list(pub_ds.iter(system_id=sid, split="train", family="nominal"))[:10]:
            for i in range(300, len(tr.t), 400):
                pool.append({str(n): float(v) for n, v in zip(d["observed"], tr.x[i]) if v > 0})
        n_fam = args.per_family if d["mode"] == "full" else max(10, args.per_family // 2)
        for fam in HIDDEN_FAMILIES:
            if fam in ("H_kick_B", "H_pulse_B", "H_silence1_B") and not B:
                continue
            for j in range(n_fam):
                seed = hidden_seed(salt, sid, fam, j)
                rng = np.random.default_rng(seed % (2**32))
                smp = Sampler(s, rng, seed_fn=lambda sd=seed: sd, state_pool=pool)
                proto = P.validate(family_protocol(fam, smp, A, B))
                jobs.append((d, proto)); meta.append({"system_id": sid, "family": fam, "role": "test", "pair": f"{fam}:{j}"})
                if fam in INTERVENTION_FAMILIES:
                    jobs.append((d, P.validate(counterfactual(proto)))); meta.append({"system_id": sid, "family": fam, "role": "twin", "pair": f"{fam}:{j}"})
        for p in micro_pool_protocols(s, salt, A, pool):
            g = p.pop("group")
            jobs.append((d, P.validate(p))); meta.append({"system_id": sid, "family": "H_micro", "role": "pool", "group": g,
                                                            "params_seed": p["params_seed"]})
    print(f"{len(systems)} systems; {len(jobs)} hidden trajectories", flush=True)
    items, micro_jobs, micro_meta = [], [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for (key, rec), m, (d, proto) in zip(ex.map(_run, jobs, chunksize=4), meta, jobs):
            arr = {"t": rec["t"], "x": dense(rec, d["observed"]), "u": rec["u"], "y": dense(rec, d["readout"])}
            items.append(({"key": key, "system_id": m["system_id"], "split": m["role"], "family": m["family"], "protocol": proto,
                           "info": {k: v for k, v in m.items() if k not in ("system_id", "family", "role")}}, arr))
            if m["family"] == "H_micro":
                rng = np.random.default_rng(int(key[:8], 16))
                for i in sorted(rng.choice(np.arange(300, len(rec["t"]) - 1), MICRO_STATES_PER_TRAJ, replace=False)):
                    full = {int(n): float(v) for n, v in zip(rec["neurons"], rec["rates"][i])}
                    micro_jobs.append((d, full, m["params_seed"], float(rec["t"][i])))
                    micro_meta.append({"key": key, "index": int(i), "group": m["group"], "system_id": m["system_id"]})
        futures = list(ex.map(_micro_future, micro_jobs, chunksize=4))
    manifest = {"dataset_id": "state_discovery_v1/real_hidden", "version": "1", "dt": 0.001,
                "systems": {sid: {k: v for k, v in public[sid].items() if k not in ("local_graph", "signs")} | {"kind": "real"} for sid in public},
                "splits": ["test", "twin", "pool"], "families": list(HIDDEN_FAMILIES) + ["H_micro"]}
    D.write_dataset(DATA / "real_hidden", manifest, items)
    # per restart (readout dimensions differ between networks): future_<i>, floor_<i> (brainir_state.harness._micro_files)
    np.savez_compressed(DATA / "real_hidden" / "micro_futures.npz", **{f"future_{i}": f for i, (f, _) in enumerate(futures)},
                        **{f"floor_{i}": t for i, (_, t) in enumerate(futures)})
    (DATA / "real_hidden" / "micro_index.json").write_text(json.dumps(micro_meta) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} hidden trajectories and {len(futures)} microstate restarts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
