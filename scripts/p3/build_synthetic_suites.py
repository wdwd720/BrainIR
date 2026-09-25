"""state_discovery_v1: build the synthetic suites (orchestrator; before method development).

    uv run --project phase3 python scripts/p3/build_synthetic_suites.py [--tiers dev,heldout,final] [--workers 14] [--copy-generator]
    uv run --project phase3 python scripts/p3/build_synthetic_suites.py --screen dev,heldout,final    (step 5, after building)

1. --copy-generator: copies the oracle-free author's generator (C:\\Dev\\BrainIR_p3bench: p3synth/, tests/, SYNTHETIC_BENCHMARK.md,
   reports/, pyproject.toml) into benchmarks/state_discovery_v1/generator/ (hash-locked with the benchmark; never in a clean room);
2. builds the suites with the generator's own builder: dev with the PUBLIC seed DEV_SEED, heldout and final with seeds derived from
   the benchmark's secret salt (data/phase3/hidden/salt.txt, committed by sha256). Public part -> data/phase3/synthetic/<tier>/public
   (dev: data/phase3/synthetic_dev, which is what the clean room receives), truth -> data/phase3/synthetic/<tier>/truth;
3. adds the microstate-equivalence pools (split "pool", family "H_micro"): per system, MICRO_DRAWS held-out parameter draws x
   MICRO_TRAJ pool trajectories (held-out-region initial states, random inputs); MICRO_STATES states per trajectory are restarted
   from their FULL microstate (all neurons, noise-free recorded state) under the common nominal input for SYNTH_CFG.micro_future_s,
   all restarts of one draw with ONE shared noise_seed (so futures differ only through the state); the numerical / noise floor is the
   same restart with another noise_seed. Pool truth (latents of pool trajectories and the true latent at every restart state) goes to
   the truth directory;
5. --screen: removes diverged simulations (non-finite values) with their counterfactual partners and restarts, recording the counts;
6. writes benchmarks/state_discovery_v1/hidden/synthetic_suites.json (seeds of every tier, dataset ids, counts) and
   benchmarks/state_discovery_v1/public/synthetic_dev_suite.json (the dev seed and dataset id only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH_ROOM = Path(r"C:\Dev\BrainIR_p3bench")
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
GEN = BENCH / "generator"
DATA = ROOT / "data" / "phase3"
DEV_SEED = 20260924
MICRO_DRAWS, MICRO_TRAJ, MICRO_STATES = 4, 8, 4
GEN_ITEMS = ("p3synth", "tests", "reference", "SYNTHETIC_BENCHMARK.md", "reports", "pyproject.toml", "protocol_spec.md", "data_format.md",
             "CONTRACT.md")


def copy_generator() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    for item in GEN_ITEMS:
        src, dst = BENCH_ROOM / item, GEN / item
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
        else:
            shutil.copy2(src, dst)


def tier_seed(tier: str) -> int:
    if tier == "dev":
        return DEV_SEED
    salt = (DATA / "hidden" / "salt.txt").read_text(encoding="utf-8").strip()
    return int(hashlib.sha256(f"{salt}|synthetic|{tier}".encode()).hexdigest()[:8], 16)


def paths(tier: str) -> tuple[Path, Path]:
    if tier == "dev":
        return DATA / "synthetic_dev", DATA / "synthetic_truth" / "dev"
    return DATA / "synthetic" / tier / "public", DATA / "synthetic" / tier / "truth"


# ------------------------------------------------------------------------------------------------------------ pools
def _pool_system(args):
    """Pool trajectories and restarts for one system (worker)."""
    tier, seed, sid, future_s = args
    sys.path.insert(0, str(GEN))
    from p3synth.core import seed_from
    from p3synth.suite import TEST_PARAMS, Planner
    from p3synth.systems import build_all
    systems = {s.system_id: s for s in build_all(seed, tier)}
    s = systems[sid]
    pl = Planner(s, seed_from("pool", seed, tier), tier, 1.0)
    rng = np.random.default_rng(seed_from("pool-rng", seed, tier, sid) % (2**32))
    dt = 0.01
    rows, restarts = [], []
    for g, ps in enumerate(TEST_PARAMS[:MICRO_DRAWS]):
        common_noise = int(rng.integers(0, 2**31))
        for j in range(MICRO_TRAJ):
            fam = "init_heldout" if j % 2 == 0 else "stim"
            p = pl.make("test", fam) if fam == "init_heldout" else pl.make("train", "stim")
            p = dict(p, params_seed=int(ps), events=[], weight_noise=None, noise_seed=int(rng.integers(0, 2**31)))
            out = s.simulate(p, full=True)
            rows.append({"protocol": p, "arrays": {k: out[k] for k in ("t", "x", "u", "y")}, "z": out["z"], "group": int(ps)})
            idxs = sorted(rng.choice(np.arange(int(round(1.0 / dt)), len(out["t"]) - 1), MICRO_STATES, replace=False))
            for i in idxs:
                vals = {str(n): float(v) for n, v in enumerate(out["x_full"][i])}
                base = {"system": sid, "params_seed": int(ps), "weight_noise": None, "t_end": future_s, "dt": dt,
                        "stimulus": [[0.0, 1.0 if s.input_dim == 1 else [1.0] * s.input_dim]], "events": [],
                        "r0": {"kind": "state", "values": vals}}
                fut = s.simulate(dict(base, noise_seed=common_noise))
                flo = s.simulate(dict(base, noise_seed=common_noise + 1))
                restarts.append({"row": len(rows) - 1, "index": int(i), "group": int(ps), "future": fut["y"], "floor": flo["y"],
                                 "z_state": out["z"][i], "z_future": fut["z"]})
    return sid, rows, restarts


def add_pools(tier: str, seed: int, workers: int, future_s: float) -> dict:
    sys.path.insert(0, str(ROOT / "phase3" / "src"))
    from brainir_state import data as D
    pub, truth = paths(tier)
    ds = D.Dataset(pub)
    sids = sorted(ds.systems)
    items, micro_meta, fut, flo = [], [], [], []
    z_states, pool_latents = [], {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for sid, rows, restarts in ex.map(_pool_system, [(tier, seed, sid, future_s) for sid in sids]):
            keys = []
            for r in rows:
                key = "pool" + hashlib.sha256(json.dumps({"s": sid, "p": r["protocol"], "tier": tier}, sort_keys=True).encode()).hexdigest()[:16]
                keys.append(key)
                items.append(({"key": key, "system_id": sid, "split": "pool", "family": "H_micro", "protocol": r["protocol"],
                               "info": {"group": r["group"]}}, r["arrays"]))
                pool_latents[key] = r["z"]
            for rs in restarts:
                micro_meta.append({"key": keys[rs["row"]], "index": rs["index"], "group": rs["group"], "system_id": sid})
                fut.append(rs["future"])
                flo.append(rs["floor"])
                z_states.append({"key": keys[rs["row"]], "index": rs["index"], "z": np.asarray(rs["z_state"]).tolist()})
    D.append_rows(pub, items)
    man = json.loads((pub / "manifest.json").read_text(encoding="utf-8"))
    man["splits"] = sorted(set(man.get("splits", [])) | {"pool"})
    man.setdefault("families", {})["H_micro"] = ("microstate-equivalence pools: states of these trajectories are restarted by the evaluator "
                                                 "from their full microstate under a common input (micro_index.json, micro_futures.npz)")
    (pub / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    # ragged futures (different readout dims per system): store per restart in an object-free way
    np.savez_compressed(pub / "micro_futures.npz", **{f"future_{i}": f for i, f in enumerate(fut)}, **{f"floor_{i}": f for i, f in enumerate(flo)})
    (pub / "micro_index.json").write_text(json.dumps(micro_meta) + "\n", encoding="utf-8")
    (truth / "pools").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(truth / "pools" / "pool_latents.npz", **pool_latents)
    (truth / "pools" / "restart_states.json").write_text(json.dumps(z_states) + "\n", encoding="utf-8")
    return {"n_pool_trajectories": len(items), "n_restarts": len(micro_meta)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="dev,heldout,final")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--copy-generator", action="store_true")
    args = ap.parse_args(argv)
    if args.copy_generator:
        copy_generator()
    sys.path.insert(0, str(GEN))
    from p3synth.suite import build_suite
    record_path = BENCH / "hidden" / "synthetic_suites.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
    for tier in [t for t in args.tiers.split(",") if t]:
        seed = tier_seed(tier)
        pub, truth = paths(tier)
        if pub.exists() or truth.exists():
            raise SystemExit(f"{pub} or {truth} exists; remove it first to rebuild tier {tier}")
        info = build_suite(pub, truth, seed, tier, workers=args.workers)
        pools = add_pools(tier, seed, args.workers, future_s=1.0)
        record[tier] = {"seed": seed, **{k: v for k, v in info.items()}, **pools, "public_dir": "$DATA/" + pub.relative_to(DATA.parent).as_posix(),
                        "truth_dir": "$DATA/" + truth.relative_to(DATA.parent).as_posix()}
        print(tier, json.dumps(record[tier]), flush=True)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")
    if "dev" in record:
        (BENCH / "public").mkdir(parents=True, exist_ok=True)
        (BENCH / "public" / "synthetic_dev_suite.json").write_text(json.dumps({"tier": "dev", "seed": record["dev"]["seed"],
                                                                               "dataset_id": record["dev"].get("dataset_id")}, indent=1) + "\n",
                                                                   encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__" and "--screen" not in sys.argv:
    raise SystemExit(main())


# ------------------------------------------------------------------------------------------------------------ non-finite screen
def screen_nonfinite(tier: str) -> dict:
    """Remove trajectories whose simulation diverged (non-finite x, u or y), their counterfactual partners, and pool restarts with
    non-finite futures. Divergent simulations carry no usable state information; the counts are recorded, nothing else is changed."""
    pub, _ = paths(tier)
    rows = [json.loads(line) for line in (pub / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = set()
    for r in rows:
        with np.load(pub / "traj" / f"{r['key']}.npz") as z:
            if not all(np.isfinite(z[k]).all() for k in ("x", "u", "y")):
                bad.add(r["key"])
    pairs = {}
    for r in rows:
        pr = (r.get("info") or {}).get("pair")
        if pr:
            pairs.setdefault(pr, []).append(r["key"])
    for keys in pairs.values():
        if any(k in bad for k in keys):
            bad.update(keys)
    dropped = {}
    keep = []
    for r in rows:
        if r["key"] in bad:
            dropped[f"{r['split']}:{r['family']}"] = dropped.get(f"{r['split']}:{r['family']}", 0) + 1
            (pub / "traj" / f"{r['key']}.npz").unlink(missing_ok=True)
        else:
            keep.append(r)
    (pub / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in keep), encoding="utf-8", newline="\n")
    n_restart_drop = 0
    if (pub / "micro_index.json").exists():
        idx = json.loads((pub / "micro_index.json").read_text(encoding="utf-8"))
        with np.load(pub / "micro_futures.npz") as z:
            fut = [z[f"future_{i}"] for i in range(len(idx))]
            flo = [z[f"floor_{i}"] for i in range(len(idx))]
        sel = [i for i, m in enumerate(idx) if m["key"] not in bad and np.isfinite(fut[i]).all() and np.isfinite(flo[i]).all()]
        n_restart_drop = len(idx) - len(sel)
        np.savez_compressed(pub / "micro_futures.npz", **{f"future_{j}": fut[i] for j, i in enumerate(sel)},
                            **{f"floor_{j}": flo[i] for j, i in enumerate(sel)})
        (pub / "micro_index.json").write_text(json.dumps([idx[i] for i in sel]) + "\n", encoding="utf-8")
    return {"dropped_nonfinite_trajectories": dropped, "n_dropped": sum(dropped.values()), "dropped_restarts": n_restart_drop}


def _screen_main(tiers: list[str]) -> None:
    record_path = BENCH / "hidden" / "synthetic_suites.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    for tier in tiers:
        record[tier]["screen"] = screen_nonfinite(tier)
        print(tier, json.dumps(record[tier]["screen"]), flush=True)
    record_path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__" and "--screen" in sys.argv:
    _screen_main([t for t in sys.argv[sys.argv.index("--screen") + 1].split(",") if t])
