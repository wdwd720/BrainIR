"""Build the synthetic cross-connectome pair suite (public instances + separate truth) with simulation-verified truth.

    uv run python scripts/build_pair_suite.py --out data/synthetic/pairs_v1 --salt <secret> [--max-n 200] [--only pair__ei_...]

Same conventions as build_synthetic_suite.py: unverifiable specs are retried with shifted seeds, then dropped; the salt is kept in
truth/SALT.txt (never in the public files); BUILD_REPORT.json lists what was built.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from brainir.discovery.synthetic_pairs import PAIR_SUITE_ID, build_pair, default_pair_specs, export_pair, verify_pair


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic/pairs_v1"))
    ap.add_argument("--salt", default="synthetic-pairs")
    ap.add_argument("--max-n", type=int, default=None, help="skip specs whose larger network exceeds this size")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--seeds", type=int, default=4, help="verification parameter seeds per network")
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "truth").mkdir(exist_ok=True)
    (args.out / "truth" / "SALT.txt").write_text(args.salt + "\n", encoding="utf-8", newline="\n")
    report = {"suite": PAIR_SUITE_ID, "built": [], "dropped": []}
    t0 = time.time()
    for spec in default_pair_specs():
        if args.max_n is not None and max(spec.n_total_a, spec.n_total_b) > args.max_n:
            continue
        if args.only and spec.label not in set(args.only):
            continue
        done = False
        for attempt in range(args.retries + 1):
            s = spec if attempt == 0 else replace(spec, seed=spec.seed + 100_000 * attempt, name=None)
            t1 = time.time()
            pair = build_pair(s)
            ver = verify_pair(pair, seeds=list(range(args.seeds)))
            if ver["verified"]:
                rec = export_pair(pair, ver, args.out, salt=args.salt)
                rec["seconds"] = round(time.time() - t1, 1)
                rec["spec"] = s.label
                report["built"].append(rec)
                print(f"built {s.label} ({rec['seconds']} s)", flush=True)
                done = True
                break
            print(f"  not verified: {s.label} (a {ver['a']['intact_pass']:.2f}, b {ver['b']['intact_pass']:.2f})", flush=True)
        if not done:
            report["dropped"].append(spec.label)
    report["seconds"] = round(time.time() - t0, 1)
    (args.out / "BUILD_REPORT.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(report['built'])} built, {len(report['dropped'])} dropped in {report['seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
