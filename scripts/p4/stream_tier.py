"""STREAMED pre-freeze pipeline of a synthetic tier, batch by batch (ORCHESTRATOR SIDE, Windows host; the user's directives of
2026-09-28: no Modal, minimal local disk and RAM; research/phase4/LOCAL_EXECUTION_PLAN.md sections 3 and 7).

    uv run --no-sync --project phase4 python scripts/p4/stream_tier.py --tier dev --batch-size 10 [--only-batch K] [--stages ...]

For each batch of systems (sorted system ids of the reused tier plan), in order, one memory-heavy job at a time:
  build   linux_driver --local: build_on_modal.py synthetic --reuse-plan --systems <batch> (fresh directories; build manifests)
  crit11  calibration_check_suite.py --stats-cache (per-system statistics; the suite comparison runs once all are cached)   [dev]
  calib   calibrate.py --split --pack --resume-dir (per (system, reference) fits and per-system assemblies, cached)              [dev]
  mde     active_mde.py run --systems <batch> --out research/phase4/mde_batches/<tier>_b<K>.json (merged later: active_mde merge) [dev]
  push    remote_store.py push --evict: public part -> tiers/<tier>/public/<sid> (dev: the public bucket; every other tier: held-out),
          eval and truth parts -> held-out; the local copies are deleted only after every file verified remotely
  evict_store  delete the batch's build records from the local eval store (LOG P4-D73): a system's build publishes ~1-6 GB of full
          records (restart sources, cache), 50-150 GB per tier, more than the disk or the bucket quota holds; they are a deterministic
          function of the plan and the generator (the build manifests pin every built file), so a later stage that needs them rebuilds
          the system (~10 min, as fast as a download at the uplink's ~3 MB/s). Runs only after every other stage of the batch succeeded.
Disk guard: a build starts only with >= --min-free-gb free on the volumes' drive (a batch's records peak at ~6 GB per system).
State (which stage of which batch is done) is kept in research/phase4/stream_state_<tier>.json, so the run resumes after any stop.
The official outputs are written by the aggregate steps once every batch is done: calibration_check_suite.py (suite comparison),
calibrate.py without --systems (benchmark calibration from the cached fits), active_mde.py merge."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UV = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe" / "uv.exe")
UVX = str(Path(UV).with_name("uvx.exe"))
VOL = Path(r"C:\Dev\BrainIR_p4run\vol")
STAGES_DEV = ("build", "crit11", "calib", "mde", "push", "evict_store")
STAGES_OTHER = ("build", "push", "evict_store")


def evict_store(tier: str, batch: list[str], since: float, log: Path) -> int:
    """Delete the records the batch's builds published to the local eval store (index shards build_<tier>_<sid>_*.jsonl written at or
    after `since`, the batch's build start) and those shards; returns 0. Shards of earlier builds (e.g. fetched Modal indexes) stay."""
    import shutil
    store = VOL / "eval" / "store"
    n_rec = n_bytes = n_sh = 0
    for sid in batch:
        for sh in sorted((store / "index_shards").glob(f"build_{tier}_{sid}_*.jsonl")):
            if sh.stat().st_mtime < since - 5:
                continue
            for line in sh.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                k = json.loads(line)["key"]
                p = store / "rec" / k[:2] / f"{k}.npz"
                if p.exists():
                    n_bytes += p.stat().st_size
                    p.unlink()
                    n_rec += 1
            sh.unlink()
            n_sh += 1
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"evicted {n_rec} records ({n_bytes / 2**30:.2f} GB) and {n_sh} index shards of {batch}; free "
                 f"{shutil.disk_usage(VOL).free / 2**30:.1f} GB\n")
    return 0


def sh(cmd: list[str], log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n=== {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {' '.join(cmd)}\n")
        fh.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode


def driver(script: str, args: list[str], *, workers: int, mem_gb: float, cpus: int) -> list[str]:
    return [UV, "run", "--no-sync", "--project", "phase4", "python", "scripts/p4/linux_driver.py", "run", "--local", "--workers",
            str(workers), "--memory-gb", str(mem_gb), "--cpus", str(cpus), script, *args]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=("dev", "val"))
    ap.add_argument("--batch-size", type=int, default=3)
    ap.add_argument("--min-free-gb", type=float, default=22.0, help="start a build only with this much free disk on the volumes' drive")
    ap.add_argument("--only-batch", type=int, default=None)
    ap.add_argument("--build-workers", type=int, default=6)
    ap.add_argument("--jobs", type=int, default=1, help="local backend payloads at once for calib / mde (1: the 2026-09-29 reap, LOG P4-D74)")
    ap.add_argument("--job-mem-gb", type=float, default=6.0, help="container memory cap of the calib / mde driver")
    args = ap.parse_args(argv)
    plan = ROOT / "data" / "phase4" / "suites" / args.tier / "_plan" / "jobs.json"
    if not plan.exists():
        raise SystemExit(f"no reusable plan at {plan}: run build_on_modal.py synthetic --tier {args.tier} --reuse-plan --plan-only first")
    sids = sorted(j["sid"] for j in json.loads(plan.read_text(encoding="utf-8")))
    batches = [sids[i: i + args.batch_size] for i in range(0, len(sids), args.batch_size)]
    state_p = ROOT / "research" / "phase4" / f"stream_state_{args.tier}.json"
    state = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {}
    stages = STAGES_DEV if args.tier == "dev" else STAGES_OTHER
    logs = ROOT / "data" / "phase4" / "stream_logs"
    truth = json.loads((ROOT / "data" / "phase4" / "suites" / args.tier / "truth" / "systems_truth.json").read_text(encoding="utf-8"))
    for k, batch in enumerate(batches):
        if args.only_batch is not None and k != args.only_batch:
            continue
        done = state.setdefault(str(k), {"systems": batch, "done": []})
        for st in stages:
            if st in done["done"]:
                continue
            csv = ",".join(batch)
            comp = ",".join(s for s in batch if str((truth.get(s) or {}).get("k")) not in ("none", "None", ""))
            log = logs / f"{args.tier}_b{k}_{st}.log"
            t0 = time.time()
            if st == "build":
                import shutil
                free_gb = shutil.disk_usage(VOL).free / 2**30
                if free_gb < args.min_free_gb:
                    print(f"batch {k}: only {free_gb:.1f} GB free on the volumes' drive (< {args.min_free_gb}); stopping", flush=True)
                    state_p.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")
                    return 3
                done["build_started"] = time.time()
                state_p.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")
                rc = sh(driver("scripts/p4/build_on_modal.py", ["synthetic", "--tier", args.tier, "--workers", str(args.build_workers),
                                                                  "--reuse-plan", "--systems", csv], workers=1, mem_gb=6, cpus=8), log)
            elif st == "crit11":
                rc = sh(driver("scripts/p4/calibration_check_suite.py", ["--tier", args.tier, "--root", f"/fitvol/data/suites/{args.tier}/public",
                                                                           "--stats-cache", f"research/phase4/crit11_cache/{args.tier}"],
                               workers=1, mem_gb=4, cpus=4), log)
                rc = 0 if rc in (0, 2) else rc                    # 2 = cached, the suite comparison waits for the other batches
            elif st == "calib":
                rc = 0 if not comp else sh(driver("scripts/p4/calibrate.py", ["--tier", args.tier, "--backend", "modal", "--split", "--pack",
                                                                               "--pack-cls", "pack_xl", "--resume-dir", f"data/phase4/calibration_resume_{args.tier}",
                                                                               "--systems", comp, "--out", f"data/phase4/calib_batches/{args.tier}_b{k}.json"],
                                                  workers=args.jobs, mem_gb=args.job_mem_gb, cpus=12), log)
            elif st == "mde":
                rc = sh(driver("scripts/p4/active_mde.py", ["run", "--systems", csv, "--out", f"research/phase4/mde_batches/{args.tier}_b{k}.json",
                                                            "--run-id", f"mde-{args.tier}-b{k}", "--cls", "eval_xl", "--containers", "1",
                                                            "--workers", str(min(args.jobs, 2)), "--threads", "2", "--mem-budget-gb", "4",
                                                            "--summary-local"], workers=1, mem_gb=args.job_mem_gb, cpus=12), log)
            elif st == "push":
                rc = 0
                parts = {"public": ("fit", "public"), "eval": ("eval", "eval"), "truth": ("eval", "truth")}
                for s in batch:
                    for part, (vol, sub) in parts.items():
                        d = VOL / vol / "data" / "suites" / args.tier / sub / s
                        if not d.is_dir():
                            continue
                        r = sh([UVX, "--from", "huggingface_hub", "python", "scripts/p4/remote_store.py", "push", "--prefix",
                                f"tiers/{args.tier}/{part}/{s}", "--local", str(d), "--evict"], log)
                        rc = rc or r
            elif st == "evict_store":
                rc = evict_store(args.tier, batch, float(done["build_started"]), log)
            else:
                raise SystemExit(f"unknown stage {st}")
            print(f"batch {k} {st}: rc {rc} in {time.time() - t0:.0f} s (log {log.relative_to(ROOT)})", flush=True)
            if rc != 0:
                state_p.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")
                return rc
            done["done"].append(st)
            state_p.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
