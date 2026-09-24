"""Truth-completeness audit of a synthetic suite (see brainir.discovery.suite_audit): record unplanted sufficient sets in truth/.

    uv run python scripts/audit_suite_truth.py --suite data/synthetic/mechanisms_v1 [--backend modal] [--instances ...]

Rewrites truth/<instance>.json (alternatives_positions gains the unplanted sets; unplanted_alternatives_positions and
alternatives_audit record them) and writes truth/AUDIT_REPORT.json. Truth stays private: nothing is written to instances/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from brainir.discovery.remote import get_discovery_backend as get_backend
from brainir.discovery.suite_audit import audit_suite


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--instances", nargs="*", default=None)
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--containers", type=int, default=100)
    args = ap.parse_args(argv)
    t0 = time.time()
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=3600, max_containers=args.containers) if args.backend == "modal" else None
    rep = audit_suite(args.suite, backend=backend, workers=args.workers, instances=args.instances)
    rep["wall_s"] = round(time.time() - t0, 1)
    if backend is not None and backend.last_stats:
        rep["backend"] = backend.last_stats.to_dict()
    (args.suite / "truth" / "AUDIT_REPORT.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "backend"}, indent=1))
    return 0 if not rep["n_failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
