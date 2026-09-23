"""Build (and verify by simulation) the synthetic mechanism-discovery suite.

    uv run python scripts/build_synthetic_suite.py [--root data/synthetic/mechanisms_v1] [--workers 6] [--only FAMILY ...]

Public instances go to <root>/instances/<label>/ (bundle format); ground truth to <root>/truth/<label>.json. Instances whose
simulated truth check fails (intact or a sufficient set does not pass the criterion in >= 80 % of parameter draws) are
regenerated with the next background seed up to 4 times, then dropped and listed in <root>/BUILD_REPORT.json. The suite
root is git-ignored (regenerable); BUILD_REPORT.json records every instance's bundle hash and verification statistics.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

from brainir.discovery.synthetic import SUITE_ID, build_instance, default_specs, export_instance, verify_instance

ROOT = Path(__file__).resolve().parents[1]


def _one(args) -> dict:
    spec, root, retries = args
    t0 = time.time()
    attempts = []
    for k in range(retries + 1):
        sp = replace(spec, seed=spec.seed + 100 * k) if k else spec
        inst = build_instance(sp)
        ver = verify_instance(inst)
        attempts.append({"seed": sp.seed, "intact_pass": ver["intact_pass"], "alternatives": [a["keep_only_pass"] for a in ver["alternatives"]],
                         "verified": ver["verified"]})
        if ver["verified"]:
            rec = export_instance(inst, ver, Path(root))
            rec.update(attempts=attempts, wall_s=round(time.time() - t0, 1), essential=ver["essential"], necessary=ver["necessary_within_core"])
            return rec
    return {"instance": spec.label, "verified": False, "attempts": attempts, "wall_s": round(time.time() - t0, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT / "data" / "synthetic" / "mechanisms_v1")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these families")
    ap.add_argument("--max-n", type=int, default=None, help="skip instances larger than this (quick builds)")
    ap.add_argument("--salt", default=None, help="secret salt: shifts every background seed so the evaluation suite cannot be regenerated "
                                                 "(and its truth recovered) from the public library code; stored under truth/ only")
    args = ap.parse_args(argv)
    specs = default_specs()
    if args.salt:
        import hashlib
        offset = int(hashlib.sha256(args.salt.encode()).hexdigest()[:8], 16) % 900_000 + 100_000
        specs = [replace(s, seed=s.seed + offset) for s in specs]
        (args.root / "truth").mkdir(parents=True, exist_ok=True)
        (args.root / "truth" / "SALT.txt").write_text(args.salt + "\n", encoding="utf-8", newline="\n")
    if args.only:
        specs = [s for s in specs if s.family in set(args.only)]
    if args.max_n:
        specs = [s for s in specs if s.n_total <= args.max_n]
    args.root.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    jobs = [(s, str(args.root), args.retries) for s in specs]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            recs = list(ex.map(_one, jobs))
    else:
        recs = [_one(j) for j in jobs]
    ok = [r for r in recs if r.get("verified")]
    bad = [r for r in recs if not r.get("verified")]
    report = {"suite": SUITE_ID, "n_specs": len(specs), "n_verified": len(ok), "n_dropped": len(bad), "wall_s": round(time.time() - t0, 1),
              "instances": recs}
    (args.root / "BUILD_REPORT.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    for r in recs:
        print(f"{'OK ' if r.get('verified') else 'DROP'} {r['instance']:60s} n={r.get('n', '-'):>5} attempts={len(r['attempts'])} {r['wall_s']}s")
    print(f"{len(ok)} verified, {len(bad)} dropped, {report['wall_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
