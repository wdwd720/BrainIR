"""Plan a synthetic tier ON THE REFERENCE PLATFORM (Linux, the pinned stack of the Modal containers and of the local sandbox image;
ORCHESTRATOR SIDE; LOG P4-D32).

    (inside the image, started by build_on_modal.py synthetic)  python /repo/scripts/p4/plan_synthetic.py --tier dev --out /out

Why: the synthetic generator's system construction and capability probes are bit-identical across Linux environments (local
Docker = Modal on 50 / 50 dev content hashes) but not on the Windows host (11 / 50), so every generator computation of an official
build (content hashes in the internal records, capability records, pool states of the plan) runs where the build simulates. The
image sees the repository read-only (phase4/src, the generator, the salt for the salted streams of orchestrator-held parts) and
writes only to --out: jobs.json (one `suites.plan_remote_job` per system; the generator paths are the container paths, which are
the same in the image and on Modal), internal_records.json and systems_truth.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/repo/phase4/src")

from brainir_causal import suites as SU  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=("dev", "val", "conf", "trap"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--systems", default="")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)
    from brainir_causal.p4modal.gate import reference_platform_problems
    bad = reference_platform_problems()     # Linux, a gated host, the CPU pins, the pinned stack (review H round 3, NEW-4)
    if bad:
        raise SystemExit("plan_synthetic.py runs on the reference platform only (the sandbox image; see build_on_modal.py): "
                         + "; ".join(bad))
    t0 = time.time()
    gen = (SU.GENERATOR_CONTAINER, "p4synth")
    seed = SU.tier_seed(args.tier)
    pubs, ints, truths = SU.synthetic_tier_records(args.tier, seed, gen)
    sids = sorted(pubs) if not args.systems else [s for s in sorted(pubs) if s in set(args.systems.split(","))]
    jobs = [SU.plan_remote_job("synthetic", s, tier=args.tier, generator=gen, workers=args.workers) for s in sids]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8", newline="\n")
    (args.out / "internal_records.json").write_text(json.dumps(ints, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (args.out / "systems_truth.json").write_text(json.dumps(truths, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8",
                                                 newline="\n")
    print(json.dumps({"tier": args.tier, "systems": len(sids), "plan_s": round(time.time() - t0, 1)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
