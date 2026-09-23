"""Build (and verify by simulation) the synthetic mechanism-discovery suite.

    uv run python scripts/build_synthetic_suite.py [--root data/synthetic/mechanisms_v1] [--workers 6] [--only FAMILY ...] \
        [--salt SECRET] [--anonymize] [--no-audit]

Public instances go to <root>/instances/<name>/ (bundle format); ground truth to <root>/truth/<name>.json. Instances whose
simulated truth check fails (intact or a sufficient set does not pass the criterion in >= 80 % of parameter draws) are
regenerated with the next background seed up to 4 times, then dropped. Everything truth-derived (the build report with
verification statistics, essential flags, the salt, the truth audit) is written under <root>/truth/ ONLY; the suite root holds
just SUITE_INFO.json (counts). With --anonymize, instance names are opaque salted hashes (the family and complications are
recorded in the truth file's `spec`), so nothing public hints at the planted mechanism. The truth-completeness audit
(brainir.discovery.suite_audit) then records unplanted sufficient sets. The suite root is git-ignored (regenerable).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

from brainir.discovery.suite_audit import audit_suite
from brainir.discovery.synthetic import SUITE_ID, build_instance, default_specs, export_instance, verify_instance

ROOT = Path(__file__).resolve().parents[1]


def _one(args) -> dict:
    spec, root, retries, salt = args
    t0 = time.time()
    attempts = []
    for k in range(retries + 1):
        sp = replace(spec, seed=spec.seed + 100 * k) if k else spec
        inst = build_instance(sp)
        ver = verify_instance(inst)
        attempts.append({"seed": sp.seed, "intact_pass": ver["intact_pass"], "alternatives": [a["keep_only_pass"] for a in ver["alternatives"]],
                         "verified": ver["verified"]})
        if ver["verified"]:
            rec = export_instance(inst, ver, Path(root), salt=salt or "synthetic")
            rec.update(attempts=attempts, wall_s=round(time.time() - t0, 1), essential=ver["essential"], necessary=ver["necessary_within_core"],
                       family=sp.family, complications=list(sp.complications))
            return rec
    return {"instance": spec.label, "verified": False, "attempts": attempts, "wall_s": round(time.time() - t0, 1), "family": spec.family}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT / "data" / "synthetic" / "mechanisms_v1")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these families")
    ap.add_argument("--max-n", type=int, default=None, help="skip instances larger than this (quick builds)")
    ap.add_argument("--salt", default=None, help="secret salt: shifts every background seed so the evaluation suite cannot be regenerated "
                                                 "(and its truth recovered) from the public library code; stored under truth/ only")
    ap.add_argument("--anonymize", action="store_true", help="opaque instance names (requires --salt)")
    ap.add_argument("--no-audit", action="store_true", help="skip the truth-completeness audit")
    args = ap.parse_args(argv)
    if args.anonymize and not args.salt:
        ap.error("--anonymize requires --salt")
    specs = default_specs()
    (args.root / "truth").mkdir(parents=True, exist_ok=True)
    if args.salt:
        offset = int(hashlib.sha256(args.salt.encode()).hexdigest()[:8], 16) % 900_000 + 100_000
        specs = [replace(s, seed=s.seed + offset) for s in specs]
        (args.root / "truth" / "SALT.txt").write_text(args.salt + "\n", encoding="utf-8", newline="\n")
    if args.only:
        specs = [s for s in specs if s.family in set(args.only)]
    if args.max_n:
        specs = [s for s in specs if s.n_total <= args.max_n]
    if args.anonymize:
        specs = [replace(s, name="h" + hashlib.sha256(f"{args.salt}|{s.label}".encode()).hexdigest()[:12]) for s in specs]
    t0 = time.time()
    jobs = [(s, str(args.root), args.retries, args.salt) for s in specs]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            recs = list(ex.map(_one, jobs))
    else:
        recs = [_one(j) for j in jobs]
    ok = [r for r in recs if r.get("verified")]
    bad = [r for r in recs if not r.get("verified")]
    report = {"suite": SUITE_ID, "n_specs": len(specs), "n_verified": len(ok), "n_dropped": len(bad), "wall_s": round(time.time() - t0, 1),
              "anonymized": bool(args.anonymize), "instances": recs}
    if not args.no_audit and ok:
        report["truth_audit"] = audit_suite(args.root, workers=args.workers)
    (args.root / "truth" / "BUILD_REPORT.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    (args.root / "SUITE_INFO.json").write_text(json.dumps({"suite": SUITE_ID, "n_instances": len(ok), "anonymized": bool(args.anonymize)}, indent=1)
                                               + "\n", encoding="utf-8", newline="\n")
    for r in recs:
        print(f"{'OK ' if r.get('verified') else 'DROP'} {r['instance']:60s} {r.get('family', ''):30s} attempts={len(r['attempts'])} {r['wall_s']}s")
    print(f"{len(ok)} verified, {len(bad)} dropped, {report['wall_s']} s; audit: {report.get('truth_audit', {}).get('n_unplanted_found')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
