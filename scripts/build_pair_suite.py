"""Build the synthetic cross-connectome pair suite (public instances + separate truth) with simulation-verified truth.

    uv run python scripts/build_pair_suite.py --out data/synthetic/pairs_v1 --salt <secret> [--max-n 200] [--only <label> ...] \
        [--anonymize] [--seed-offset N] [--design v1|v2] [--secret-offset] [--no-audit]

Same conventions as build_synthetic_suite.py: unverifiable specs are retried with shifted seeds, then dropped; the salt, the build
report and the truth audit are written under truth/ only (the root holds SUITE_INFO.json with counts); --anonymize gives opaque
instance names (family and flags are recorded in the truth file's `spec`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from brainir.discovery.suite_audit import audit_suite
from brainir.discovery.synthetic_pairs import (PAIR_SUITE_ID, PAIR_SUITE_ID_V2, build_pair, default_pair_specs, export_pair, hard_pair_specs,
                                               verify_pair)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/synthetic/pairs_v1"))
    ap.add_argument("--salt", default="synthetic-pairs")
    ap.add_argument("--max-n", type=int, default=None, help="skip specs whose larger network exceeds this size")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--seeds", type=int, default=4, help="verification parameter seeds per network")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--seed-offset", type=int, default=0, help="shift every spec seed (a fresh held-out draw of the same design)")
    ap.add_argument("--anonymize", action="store_true")
    ap.add_argument("--design", choices=("v1", "v2"), default="v1", help="v1 = default_pair_specs; v2 = hard_pair_specs (review E)")
    ap.add_argument("--secret-offset", action="store_true",
                    help="derive a 40-bit seed offset from the salt, so no draw of the suite can be regenerated without the secret")
    ap.add_argument("--no-audit", action="store_true")
    ap.add_argument("--workers", type=int, default=3, help="audit workers")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "truth").mkdir(exist_ok=True)
    (args.out / "truth" / "SALT.txt").write_text(args.salt + "\n", encoding="utf-8", newline="\n")
    suite_id = PAIR_SUITE_ID_V2 if args.design == "v2" else PAIR_SUITE_ID
    offset = int(args.seed_offset)
    if args.secret_offset:
        offset += int(hashlib.sha256(f"seed-offset|{args.salt}".encode()).hexdigest()[:10], 16)
    report: dict = {"suite": suite_id, "design": args.design, "built": [], "dropped": [], "anonymized": bool(args.anonymize),
                    "seed_offset": offset}
    t0 = time.time()
    for spec in (hard_pair_specs() if args.design == "v2" else default_pair_specs()):
        if args.max_n is not None and max(spec.n_total_a, spec.n_total_b) > args.max_n:
            continue
        if args.only and spec.label not in set(args.only):
            continue
        spec = replace(spec, seed=spec.seed + offset)
        done = False
        for attempt in range(args.retries + 1):
            s = spec if attempt == 0 else replace(spec, seed=spec.seed + 100_000 * attempt)
            label = s.label
            if args.anonymize:
                s = replace(s, name="p" + hashlib.sha256(f"{args.salt}|{label}".encode()).hexdigest()[:12])
            t1 = time.time()
            pair = build_pair(s)
            ver = verify_pair(pair, seeds=list(range(args.seeds)))
            if ver["verified"]:
                rec = export_pair(pair, ver, args.out, salt=args.salt, suite_id=suite_id)
                rec["seconds"] = round(time.time() - t1, 1)
                rec["spec"] = label
                report["built"].append(rec)
                print(f"built {s.label} ({rec['seconds']} s)", flush=True)
                done = True
                break
            print(f"  not verified: {label} (a {ver['a']['intact_pass']:.2f}, b {ver['b']['intact_pass']:.2f})", flush=True)
        if not done:
            report["dropped"].append(spec.label)
    if not args.no_audit and report["built"]:
        report["truth_audit"] = audit_suite(args.out, workers=args.workers)
    report["seconds"] = round(time.time() - t0, 1)
    (args.out / "truth" / "BUILD_REPORT.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    (args.out / "SUITE_INFO.json").write_text(json.dumps({"suite": suite_id, "n_instances": len(report["built"]),
                                                          "anonymized": bool(args.anonymize)}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(report['built'])} built, {len(report['dropped'])} dropped in {report['seconds']} s; "
          f"audit: {report.get('truth_audit', {}).get('n_unplanted_found')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
