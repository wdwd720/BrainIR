"""Precompute the k-independent reference controls (full-state ceiling, input-only, readout-history, persistence) of a synthetic suite
into the tournament's reference cache (orchestrator convenience; calls the frozen brainir_state.suite_eval.reference_results).

    uv run --project phase3 python scripts/p3/precompute_refs.py --suite heldout [--workers 2] [--pilot-first]
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))


def _one(args):
    tier, sid = args
    from brainir_state.suite_eval import SuiteData, limit_threads, reference_results
    from tournament import OUT, suite_spec
    limit_threads(2)
    spec = suite_spec(tier)
    sd = SuiteData(spec["public_dir"], kind="synthetic", truth_dir=spec["truth_dir"])
    reference_results(sd, sid, 1, OUT / "_refcache" / tier)
    return sid


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="heldout")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--pilot-first", action="store_true")
    args = ap.parse_args(argv)
    from tournament import PILOT, suite_spec
    spec = suite_spec(args.suite)
    truth = json.loads((Path(spec["truth_dir"]) / "truth.json").read_text(encoding="utf-8"))
    sids = sorted(truth["systems"])
    if args.pilot_first:
        sids = sorted(sids, key=lambda s: (truth["systems"][s]["name"] not in PILOT, s))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for sid in ex.map(_one, [(args.suite, s) for s in sids]):
            print("done", sid, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
