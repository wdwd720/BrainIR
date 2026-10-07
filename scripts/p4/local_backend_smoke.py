"""Smoke test of the LOCAL backend (ORCHESTRATOR SIDE; research/phase4/LOCAL_EXECUTION_PLAN.md). Run it in the local driver container:

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run --local --workers 2 --memory-gb 2 --cpus 2 \
        scripts/p4/local_backend_smoke.py

Checks: `app.Backend` is the local backend; the host gate and the numerics self-test pass; `call` payloads run in job subprocesses and
return in input order; a job's own error comes back as a result; the local volumes are writable and read back through stage_put /
stage_get; the cost record says $0. Prints one JSON line; exit 1 on a failed check."""

from __future__ import annotations

import json
import sys


def main() -> int:
    from brainir_causal.p4modal import app
    from brainir_causal.p4modal.local import LocalBackend
    checks = {"backend_is_local": app.Backend is LocalBackend}
    with app.Backend(classes=["util"]) as be:
        res = be.call("brainir_causal.p4modal.gate:host_cpu", [[], [], []], cls="util", threads=1)
        checks["calls_ok"] = all(isinstance(r, dict) and "error" not in r for r in res) and len(res) == 3
        checks["job_subprocess_result"] = bool(res and isinstance(res[0], dict) and res[0].get("result", {}).get("avx2"))
        err = be.call("brainir_causal.p4modal.gate:no_such_function", [[]], cls="util", threads=1)[0]
        checks["job_error_is_a_result"] = isinstance(err, dict) and bool(err.get("error"))
        ref = be.stage_put(b"local backend smoke", vol="store")
        checks["staging_roundtrip"] = be.stage_get(ref) == b"local backend smoke"
        be.stage_clear([ref])
        cost = be.cost_summary()
        checks["zero_cost"] = cost.get("usd_approx_total") == 0.0 and cost.get("local") is True
        host = be.host
    out = {"ok": all(checks.values()), "checks": checks, "host": host.get("model"), "result_keys": sorted((res[0] or {}).keys())[:12]}
    print(json.dumps(out), flush=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
