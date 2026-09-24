"""Build an adversarial trap suite (third-party generator, brainir.discovery.adversarial; review G) with simulation-verified truth.

    uv run python scripts/build_adversarial_suite.py --out data/synthetic/adversarial_heldout --salt <secret> --anonymize --secret-offset \
        [--sizes 60 150 1500] [--n-per-trap 1] [--workers 3]

Every spec of ``adversarial_specs(n_per_trap, sizes, seed0)`` is built with ``build_verified`` (re-drawn seeds until the trap's
defining properties verify) and exported with ``export_adversarial`` (node orders main, order1). With --secret-offset, seed0 is a
40-bit number derived from the secret salt, so no instance can be regenerated without the secret; with --anonymize, instance names
are opaque salted hashes (the trap, variant and seed are recorded only in the truth). Truth, the salt and the build report are
written under truth/ only; the suite root holds SUITE_INFO.json with counts.
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

from brainir.discovery.adversarial import SUITE_ID, adversarial_specs, build_verified, export_adversarial


def _build(args) -> dict:
    spec, root, salt, max_tries = args
    t0 = time.time()
    try:
        inst, ver, used = build_verified(spec, max_tries=max_tries)
        rec = export_adversarial(inst, ver, Path(root), salt=salt)
        return {"ok": True, "instance": rec["instance"], "trap": rec["trap"], "variant": rec["variant"], "n": spec.n_total,
                "seed": int(used.seed), "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001 - an unverifiable spec is dropped and reported
        return {"ok": False, "trap": spec.trap, "variant": spec.family, "n": spec.n_total, "seed": int(spec.seed), "error": f"{type(e).__name__}: {e}"[:300]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--salt", required=True)
    ap.add_argument("--sizes", nargs="+", type=int, default=[60, 150, 1500])
    ap.add_argument("--n-per-trap", type=int, default=1)
    ap.add_argument("--anonymize", action="store_true")
    ap.add_argument("--secret-offset", action="store_true")
    ap.add_argument("--max-tries", type=int, default=8)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)
    seed0 = int(hashlib.sha256(f"adversarial-seed|{args.salt}".encode()).hexdigest()[:10], 16) if args.secret_offset else 0
    specs = adversarial_specs(n_per_trap=args.n_per_trap, sizes=tuple(args.sizes), seed0=seed0)
    if args.anonymize:
        specs = [replace(s, name="a" + hashlib.sha256(f"{args.salt}|{s.label}".encode()).hexdigest()[:12]) for s in specs]
    (args.out / "truth").mkdir(parents=True, exist_ok=True)
    (args.out / "truth" / "SALT.txt").write_text(args.salt + "\n", encoding="utf-8", newline="\n")
    t0 = time.time()
    jobs = [(s, str(args.out), args.salt, args.max_tries) for s in specs]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            results = list(ex.map(_build, jobs))
    else:
        results = [_build(j) for j in jobs]
    built = [r for r in results if r["ok"]]
    dropped = [r for r in results if not r["ok"]]
    report = {"suite": SUITE_ID, "seed0": seed0, "sizes": args.sizes, "n_per_trap": args.n_per_trap, "anonymized": bool(args.anonymize),
              "built": built, "dropped": dropped, "seconds": round(time.time() - t0, 1)}
    (args.out / "truth" / "BUILD_REPORT.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    (args.out / "SUITE_INFO.json").write_text(json.dumps({"suite": SUITE_ID, "n_instances": len(built), "anonymized": bool(args.anonymize)},
                                                         indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(built)} built, {len(dropped)} dropped in {report['seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
