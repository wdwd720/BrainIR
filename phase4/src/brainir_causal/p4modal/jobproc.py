"""Fresh-interpreter entry point of every subprocess job in a Phase 4 Modal container (container side).

    python -m brainir_causal.p4modal.jobproc <job.json> <result.pkl>

job.json: {"target": "module:function", "args": [...], "kwargs": {...}, "threads": int}. The function's return value is pickled as
{"result": value}. Guarded jobs get their guard from sitecustomize (brainir_causal/p4modal/site) BEFORE this module runs, so the
target's imports and everything it does are already inside the sandbox.
"""

from __future__ import annotations

import importlib
import json
import pickle
import sys
from pathlib import Path


def limit_threads(n: int) -> None:
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(int(n))
    except Exception:  # noqa: BLE001 - threadpoolctl missing: the environment variables still apply
        pass
    try:
        import torch
        torch.set_num_threads(int(n))
    except Exception:  # noqa: BLE001
        pass


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    job_file, out_file = argv[0], argv[1]
    job = json.loads(Path(job_file).read_text(encoding="utf-8"))
    if job.get("threads"):
        limit_threads(int(job["threads"]))
    mod, _, fn = job["target"].partition(":")
    f = getattr(importlib.import_module(mod), fn)
    res = f(*job.get("args", []), **job.get("kwargs", {}))
    with open(out_file, "wb") as fh:
        pickle.dump({"result": res}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
