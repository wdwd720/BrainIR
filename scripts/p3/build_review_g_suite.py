"""Build the review G suite: NEW adversarial trap families designed by an oracle-free reviewer and unknown to the method developers
(goal4 section 69 review G; research/phase3/REVIEW_PLAN.md).

    uv run --project phase3 python scripts/p3/build_review_g_suite.py [--workers 8] [--copy]

--copy stores the reviewer's deliverables in research/phase3/review_g/:
- p3synth/, a copy of the locked generator with review_g.py added; the reviewer changed no existing file (checked);
- tests/test_review_g.py;
- REVIEW_G_TRAPS.md.

The suite is built with the generator's own builder on the review G catalogue:
- tier "heldout" scale, seed derived from the benchmark salt;
- public part -> data/phase3/synthetic/review_g/public, truth -> data/phase3/synthetic/review_g/truth;
- then the microstate pools of PROTOCOL.md section 3.3 and the non-finite screen, as for the main suites.

The record (seed, counts) goes to research/phase3/review_g/suite_record.json. It is answer-bearing for the review G systems and
never enters a room. The suite is outside the frozen benchmark: it is review material, not part of state_discovery_v1.
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
ROOM = Path(r"C:\Dev\BrainIR_p3reviewG")
DEST = ROOT / "research" / "phase3" / "review_g"
DATA = ROOT / "data" / "phase3" / "synthetic" / "review_g"
MICRO_DRAWS, MICRO_TRAJ, MICRO_STATES = 4, 8, 4


def _pool_system(args):
    """Pool trajectories and restarts for one review G system (same design as build_synthetic_suites._pool_system)."""
    seed, sid, future_s = args
    sys.path.insert(0, str(DEST))
    from p3synth.core import seed_from
    from p3synth.review_g import build_review_g
    from p3synth.suite import TEST_PARAMS, Planner
    systems = {s.system_id: s for s in build_review_g(seed, "heldout")}
    s = systems[sid]
    pl = Planner(s, seed_from("pool", seed, "review_g"), "heldout", 1.0)
    rng = np.random.default_rng(seed_from("pool-rng", seed, "review_g", sid) % (2**32))
    dt = 0.01
    rows, restarts = [], []
    for ps in TEST_PARAMS[:MICRO_DRAWS]:
        common_noise = int(rng.integers(0, 2**31))
        for j in range(MICRO_TRAJ):
            fam = "init_heldout" if j % 2 == 0 else "stim"
            p = pl.make("test", fam) if fam == "init_heldout" else pl.make("train", "stim")
            p = dict(p, params_seed=int(ps), events=[], weight_noise=None, noise_seed=int(rng.integers(0, 2**31)))
            out = s.simulate(p, full=True)
            rows.append({"protocol": p, "arrays": {k: out[k] for k in ("t", "x", "u", "y")}, "z": out["z"], "group": int(ps)})
            for i in sorted(rng.choice(np.arange(int(round(1.0 / dt)), len(out["t"]) - 1), MICRO_STATES, replace=False)):
                vals = {str(n): float(v) for n, v in enumerate(out["x_full"][i])}
                base = {"system": sid, "params_seed": int(ps), "weight_noise": None, "t_end": future_s, "dt": dt,
                        "stimulus": [[0.0, 1.0 if s.input_dim == 1 else [1.0] * s.input_dim]], "events": [],
                        "r0": {"kind": "state", "values": vals}}
                fut = s.simulate(dict(base, noise_seed=common_noise))
                flo = s.simulate(dict(base, noise_seed=common_noise + 1))
                restarts.append({"row": len(rows) - 1, "index": int(i), "group": int(ps), "future": fut["y"], "floor": flo["y"],
                                 "z_state": out["z"][i]})
    return sid, rows, restarts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--copy", action="store_true")
    args = ap.parse_args(argv)
    if args.copy:
        if DEST.exists():
            shutil.rmtree(DEST)
        (DEST / "tests").mkdir(parents=True)
        shutil.copytree(ROOM / "p3synth", DEST / "p3synth", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(ROOM / "tests" / "test_review_g.py", DEST / "tests" / "test_review_g.py")
        shutil.copy2(ROOM / "REVIEW_G_TRAPS.md", DEST / "REVIEW_G_TRAPS.md")
        locked = ROOT / "benchmarks" / "state_discovery_v1" / "generator" / "p3synth"
        changed = [p.name for p in locked.glob("*.py") if (DEST / "p3synth" / p.name).read_bytes() != p.read_bytes()]
        if changed:
            raise SystemExit(f"the reviewer changed existing generator files: {changed}")
    sys.path.insert(0, str(DEST))
    sys.path.insert(1, str(ROOT / "phase3" / "src"))
    from p3synth.review_g import build_review_g_suite
    salt = (ROOT / "data" / "phase3" / "hidden" / "salt.txt").read_text(encoding="utf-8").strip()
    seed = int(hashlib.sha256(f"{salt}|synthetic|review_g".encode()).hexdigest()[:8], 16)
    pub, truth = DATA / "public", DATA / "truth"
    if pub.exists() or truth.exists():
        raise SystemExit(f"{DATA} exists; remove it to rebuild")
    info = build_review_g_suite(pub, truth, seed, tier="heldout", workers=args.workers)
    # pools
    from brainir_state import data as D
    ds = D.Dataset(pub)
    items, micro_meta, fut, flo, pool_latents = [], [], [], [], {}
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for sid, rows, restarts in ex.map(_pool_system, [(seed, s, 1.0) for s in sorted(ds.systems)]):
            keys = []
            for r in rows:
                key = "pool" + hashlib.sha256(json.dumps({"s": sid, "p": r["protocol"], "tier": "review_g"}, sort_keys=True).encode()).hexdigest()[:16]
                keys.append(key)
                items.append(({"key": key, "system_id": sid, "split": "pool", "family": "H_micro", "protocol": r["protocol"],
                               "info": {"group": r["group"]}}, r["arrays"]))
                pool_latents[key] = r["z"]
            for rs in restarts:
                micro_meta.append({"key": keys[rs["row"]], "index": rs["index"], "group": rs["group"], "system_id": sid})
                fut.append(rs["future"])
                flo.append(rs["floor"])
    D.append_rows(pub, items)
    man = json.loads((pub / "manifest.json").read_text(encoding="utf-8"))
    man["splits"] = sorted(set(man.get("splits", [])) | {"pool"})
    (pub / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    np.savez_compressed(pub / "micro_futures.npz", **{f"future_{i}": f for i, f in enumerate(fut)}, **{f"floor_{i}": f for i, f in enumerate(flo)})
    (pub / "micro_index.json").write_text(json.dumps(micro_meta) + "\n", encoding="utf-8")
    (truth / "pools").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(truth / "pools" / "pool_latents.npz", **pool_latents)
    # non-finite screen (same rule as build_synthetic_suites --screen)
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    import build_synthetic_suites as B
    B.paths = lambda tier: (pub, truth)                  # noqa: E731  (screen this suite's directories)
    screen = B.screen_nonfinite("review_g")
    rec = {"seed": seed, "tier": "heldout (review G catalogue)", **info, "n_pool_trajectories": len(items), "n_restarts": len(micro_meta),
           "screen": screen, "public_dir": "$DATA/phase3/synthetic/review_g/public", "truth_dir": "$DATA/phase3/synthetic/review_g/truth"}
    (DEST / "suite_record.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "seed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
