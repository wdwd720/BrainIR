"""Evaluation worker process in a Modal container: runs ONE frozen worker function and pickles its result.

    python -m p3modal.evaljob {eval|repro|refs} <job.json> <result.pkl>
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path


def main() -> int:
    kind, job_file, out_file = sys.argv[1:4]
    job = json.loads(Path(job_file).read_text(encoding="utf-8"))
    from brainir_state.suite_eval import evaluate_model_job, limit_threads, reproducibility_job
    limit_threads(3)
    if kind == "eval":
        res = evaluate_model_job(job)
    elif kind == "repro":
        res = reproducibility_job(job)
    elif kind == "call":
        import importlib
        sys.path.insert(0, "/repo/scripts/p3")
        fn = getattr(importlib.import_module(job["module"]), job["func"])
        res = {"result": fn(*job["args"])}
    elif kind == "refs":
        from brainir_state.suite_eval import SuiteData, reference_results
        spec = job["suite"]
        sd = SuiteData(spec["public_dir"], kind=spec["kind"], truth_dir=spec.get("truth_dir"))
        reference_results(sd, job["sid"], int(job["k"]), Path(job["cache_dir"]), seed=int(job.get("seed", 0)))
        res = {"ok": True}
    else:
        raise SystemExit(f"unknown kind {kind}")
    with open(out_file, "wb") as fh:
        pickle.dump(res, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
