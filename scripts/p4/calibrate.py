"""causal_state_v1: the PRE-REGISTERED calibration of the verdict tolerances (benchmarks/causal_state_v1/PROTOCOL.md section 7).
ORCHESTRATOR SIDE; the logic is `brainir_causal.calibrate` (module docstring: references, tolerances, power rules, records).

    uv run --no-sync --project phase4 python scripts/p4/calibrate.py [--tier dev] [--root data/phase4/suites]
                                      [--backend local|modal] [--workers 4] [--cls eval_s] [--remote-root /evalvol/suites]
                                      [--systems a,b] [--out FILE] [--n-boot 2000]

Runs on the synthetic DEV tier only (the script refuses any other tier), on every compressible dev system (integer k in the tier's
truth summaries). Local backend: a process pool, 2 threads per worker. Modal backend: one `eval_s` container call per system
(`brainir_causal.p4modal.app.Backend.call`); the tier must already be staged at --remote-root on the eval volume. A crashed worker
(an infrastructure failure) is retried ONCE and recorded; a Python error inside a system's calibration is a scientific failure, is not
retried, and stops the script. Writes benchmarks/causal_state_v1/calibration.json and public/tolerances.json (or --out for smoke
runs, which never touch the benchmark).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import calibrate as CAL  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "phase4" / "suites"


def _local_one(args: tuple) -> dict:
    sid, root, tier, n_boot = args
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(2)
    except Exception:  # noqa: BLE001
        pass
    try:
        return CAL.calibrate_system(sid, root, tier, n_boot=n_boot)
    except Exception as exc:  # noqa: BLE001
        import traceback
        return {"sid": sid, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-4000:]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="dev")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--backend", choices=("local", "modal"), default="local")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cls", default="eval_s", help="Modal worker class")
    ap.add_argument("--remote-root", default="/evalvol/suites", help="the tier root inside the Modal containers")
    ap.add_argument("--systems", default=None, help="comma list (smoke runs only; the calibration uses every compressible system)")
    ap.add_argument("--out", type=Path, default=None, help="write here instead of the benchmark (smoke runs)")
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args(argv)
    if args.tier != "dev" and not args.tier.startswith("toy"):
        raise SystemExit("the calibration runs on the synthetic DEV tier only (PROTOCOL section 7)")
    if args.systems and args.out is None:
        raise SystemExit("--systems is for smoke runs: give --out so the benchmark files are not written from a subset")
    summaries = CAL.system_truth_summaries(args.root, args.tier)
    sids = sorted(s for s, t in summaries.items() if CAL.compressible(t) is not None)
    if args.systems:
        sids = [s for s in sids if s in set(args.systems.split(","))]
    if not sids:
        raise SystemExit(f"no compressible system in {args.root}/{args.tier} (truth/systems_truth.json): build the tier first")
    print(f"calibrating on {len(sids)} compressible {args.tier} systems ({args.backend})", flush=True)
    t0 = time.time()
    retried = []
    if args.backend == "modal":
        from brainir_causal.p4modal.app import Backend
        with Backend(classes=[args.cls]) as be:
            res = be.call("brainir_causal.calibrate:calibrate_system", [[s, args.remote_root, args.tier, args.n_boot] for s in sids],
                          cls=args.cls, threads=2, reload=["eval"])
            rows = []
            crashed = []
            for i, r in enumerate(res):
                if isinstance(r, BaseException) or "result" not in (r or {}):
                    crashed.append(i)
                    rows.append(r)
                else:
                    rows.append(r["result"])
            if crashed:
                print(f"retrying {len(crashed)} crashed systems once", flush=True)
                again = be.call("brainir_causal.calibrate:calibrate_system", [[sids[i], args.remote_root, args.tier, args.n_boot] for i in crashed],
                                cls=args.cls, threads=2, reload=["eval"])
                for i, r in zip(crashed, again):
                    ok = not isinstance(r, BaseException) and "result" in (r or {})
                    retried.append({"sid": sids[i], "first_error": str(rows[i])[:500], "retry_ok": ok})
                    rows[i] = r["result"] if ok else {"sid": sids[i], "error": str(r)[:2000]}
            cost = be.cost_summary()
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            rows = list(ex.map(_local_one, [(s, str(args.root), args.tier, args.n_boot) for s in sids]))
        cost = None
    bad = [r for r in rows if not isinstance(r, dict) or r.get("error")]
    if bad:
        raise SystemExit(f"{len(bad)} calibration systems failed: {json.dumps(bad[0], default=str)[:3000]}")
    rec = CAL.tolerances_from_rows(rows)
    rec.update({"protocol_section": "PROTOCOL.md section 7 (causal_state_v1)", "tier": args.tier, "backend": args.backend,
                "systems": sids, "per_system": rows, "infrastructure_retries": retried, "code_sha256": CAL.code_hashes(),
                "seconds": round(time.time() - t0, 1), "modal_cost": cost, "truth_summaries": summaries,
                "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    CAL.write_outputs(rec, args.out)
    print(json.dumps({k: rec[k] for k in ("tolerances", "tolerances_ci95_over_systems", "n_systems", "n_trap_systems")}, indent=1, default=str))
    print(json.dumps({"power": {k: {kk: vv for kk, vv in v.items() if kk in ("pass_rate", "binds", "gap")} for k, v in rec["power"].items()
                                if k in ("SMS", "ICG_y")}, "verdicts": rec["verdicts_under_calibrated_tolerances"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
