"""causal_state_v1: the PRE-REGISTERED calibration of the verdict tolerances (benchmarks/causal_state_v1/PROTOCOL.md section 7).
ORCHESTRATOR SIDE; the logic is `brainir_causal.calibrate` (module docstring: references, tolerances, power rules, records).

    uv run --no-sync --project phase4 python scripts/p4/calibrate.py [--tier dev] [--root data/phase4/suites]
                                      [--backend local|modal] [--workers 4] [--cls eval_s] [--remote-root /evalvol/data/suites]
                                      [--systems a,b] [--out FILE] [--n-boot 2000]

Runs on the synthetic DEV tier only (the script refuses any other tier), on every compressible dev system (integer k in the tier's
truth summaries). The rules (supported items, common percentile, Fisher power rule, power table, CI-end verdicts) are those of
PROTOCOL section 7 (`brainir_causal.calibrate.calibrate_rows`). Local backend: a process pool, 2 threads per worker. Modal backend:
one `eval_s` container call per system (`brainir_causal.p4modal.app.Backend.call`); the tier must already be staged at --remote-root
on the eval volume. A crashed worker (an infrastructure failure) is retried ONCE and recorded; a Python error inside a system's
calibration is a scientific failure, is not retried, and stops the script. Writes benchmarks/causal_state_v1/calibration.json and
public/tolerances.json (or --out for smoke runs, which never touch the benchmark).
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


#: relative cost of one reference's fit (the MLP learners dominate; ID-SHORTCUT is a lookup), for the longest-first order of wave 1
FIT_WEIGHT = {"full_state": 3.0, "true_state": 2.0, "true_state_missing": 2.0, "obs_shortcut": 2.0, "random_k": 1.5, "pca_k": 1.5,
              "id_shortcut": 0.1}


def run_split(args, sids: list[str], summaries: dict) -> tuple[list, dict]:
    """The SPLIT calibration on Modal (research/phase4/LEVEL_B_EXECUTION.md): wave 1 = every (system, reference) fit job
    (`calibrate.calibrate_system_fit_job`), packed on --pack-cls, longest first; wave 2 = every system's assembly
    (`calibrate.calibrate_system_assemble_from_file`: the fit records travel as a job input file), packed, largest first. Both waves are
    idempotent with --resume-dir. Packed jobs never commit; nothing is uploaded between the waves (the models travel in the payloads)."""
    import pickle as _pickle

    from brainir_causal.p4modal.app import Backend
    size = {s: float((summaries.get(s, {}) or {}).get("n_units") or (summaries.get(s, {}) or {}).get("N_obs") or 1.0) for s in sids}
    names = CAL.calib_fit_names()
    specs = [(s, n) for s in sids for n in names]
    rd = args.resume_dir
    with Backend(classes=[args.pack_cls]) as be:
        fit_res = be.call_packed("brainir_causal.calibrate:calibrate_system_fit_job",
                                 [[s, n, args.remote_root, args.tier, None, None, args.remote_public_root] for s, n in specs],
                                 cls=args.pack_cls, threads=2, reload=["fit", "eval"], expected_s=[size[s] * FIT_WEIGHT.get(n, 1.0) for s, n in specs],
                                 keys=[f"calfit|{args.tier}|{s}|{n}" for s, n in specs], done_dir=(rd / "fits") if rd else None,
                                 label="calibration fits")
        jobs: dict = {s: {} for s in sids}
        bad = []
        for (s, n), r in zip(specs, fit_res):
            rec = r.get("result") if isinstance(r, dict) else None
            if not isinstance(rec, dict):
                bad.append({"sid": s, "name": n, "error": str((r or {}).get("error") if isinstance(r, dict) else r)[:1500]})
                continue
            jobs[s][n] = rec
        if bad:
            raise SystemExit(f"{len(bad)} calibration fit jobs failed (infrastructure or code): {json.dumps(bad[0])[:2000]}")
        payloads = [{"kind": "call", "target": "brainir_causal.calibrate:calibrate_system_assemble_from_file",
                     "args": [s, "$JOB/fits.pkl", args.remote_root, args.tier, args.n_boot, 0, None, None, args.remote_public_root],
                     "inputs": {"fits.pkl": _pickle.dumps(jobs[s], protocol=_pickle.HIGHEST_PROTOCOL)}, "threads": 2,
                     "timeout_s": 7200, "reload": ["fit", "eval"]} for s in sids]
        asm = be.run_packed(payloads, args.pack_cls, expected_s=[size[s] for s in sids], keys=[f"calasm|{args.tier}|{s}" for s in sids],
                            done_dir=(rd / "assembly") if rd else None, label="calibration assembly")
        rows = [r["result"] if (isinstance(r, dict) and "result" in r) else {"sid": s, "error": str(r)[:2000]} for s, r in zip(sids, asm)]
        cost = be.cost_summary()
    return rows, cost


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="dev")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--backend", choices=("local", "modal"), default="local")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cls", default="eval_s", help="Modal worker class")
    ap.add_argument("--remote-root", default="/evalvol/data/suites", help="the tier root (eval / truth parts) inside the Modal containers")
    ap.add_argument("--remote-public-root", default="/fitvol/data/suites",
                    help="the root of the tier's PUBLIC part inside the Modal containers (remote-build layout: the fit volume)")
    ap.add_argument("--systems", default=None, help="comma list (smoke runs only; the calibration uses every compressible system)")
    ap.add_argument("--out", type=Path, default=None, help="write here instead of the benchmark (smoke runs)")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--pack", action="store_true",
                    help="Modal: several systems per large container (Backend.call_packed on --cls, longest-first, resumable); the "
                         "results are bit-identical to the unpacked per-container path (research/phase4/LEVEL_B_EXECUTION.md)")
    ap.add_argument("--pack-cls", default="pack_xl", help="the packed trusted class for --pack")
    ap.add_argument("--resume-dir", type=Path, default=None, help="idempotent per-system result store for --pack (resume a round)")
    ap.add_argument("--split", action="store_true",
                    help="Modal, with --pack: wave 1 = every (system, reference) fit job, wave 2 = each system's assembly (evaluations "
                         "+ row); bit-identical to the unsplit path (calibrate.calibrate_system_assemble, test_calibrate_split)")
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
    if args.backend == "modal" and args.pack and args.split:
        rows, cost = run_split(args, sids, summaries)
    elif args.backend == "modal" and args.pack:
        # PACKED: several systems per large container, longest expected first (larger systems first), idempotent per-system store.
        # call_packed runs the SAME calibrate_system in the SAME kind of subprocess as `call`, so results are bit-identical.
        from brainir_causal.p4modal.app import Backend
        weight = {s: float((summaries.get(s, {}) or {}).get("n_units") or (summaries.get(s, {}) or {}).get("N_obs") or 1.0) for s in sids}
        with Backend(classes=[args.pack_cls]) as be:
            res = be.call_packed("brainir_causal.calibrate:calibrate_system",
                                 [[s, args.remote_root, args.tier, args.n_boot, 0, None, None, args.remote_public_root] for s in sids],
                                 cls=args.pack_cls, threads=2, reload=["fit", "eval"], expected_s=[weight[s] for s in sids],
                                 keys=[f"cal|{args.tier}|{s}" for s in sids], done_dir=args.resume_dir)
            rows = [r["result"] if (isinstance(r, dict) and "result" in r) else {"sid": s, "error": str(r)[:2000]}
                    for s, r in zip(sids, res)]
            cost = be.cost_summary()
    elif args.backend == "modal":
        from brainir_causal.p4modal.app import Backend
        with Backend(classes=[args.cls]) as be:
            res = be.call("brainir_causal.calibrate:calibrate_system",
                          [[s, args.remote_root, args.tier, args.n_boot, 0, None, None, args.remote_public_root] for s in sids],
                          cls=args.cls, threads=2, reload=["fit", "eval"])
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
                again = be.call("brainir_causal.calibrate:calibrate_system",
                                [[sids[i], args.remote_root, args.tier, args.n_boot, 0, None, None, args.remote_public_root] for i in crashed],
                                cls=args.cls, threads=2, reload=["fit", "eval"])
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
    rec = CAL.calibrate_rows(rows)
    rec.update({"protocol_section": "PROTOCOL.md section 7 (causal_state_v1)", "tier": args.tier, "backend": args.backend,
                "systems": sids, "per_system": rows, "infrastructure_retries": retried, "code_sha256": CAL.code_hashes(),
                "seconds": round(time.time() - t0, 1), "modal_cost": cost, "truth_summaries": summaries,
                "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    CAL.write_outputs(rec, args.out)
    print(json.dumps({k: rec[k] for k in ("tolerances", "tolerances_ci95_over_systems", "n_systems", "n_trap_systems",
                                          "true_state_supported_rate")}, indent=1, default=str))
    print(json.dumps({"percentile": {k: rec["percentile"][k] for k in ("chosen_p", "attainable", "note")},
                      "binding": {k: rec["power_rule"][k] for k in ("sms_binds", "icg_binds", "mev_binds")},
                      "power_table_detects": {c: v.get("detects") for c, v in rec["power_table"].items()},
                      "verdicts": rec["verdicts_under_calibrated_tolerances"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
