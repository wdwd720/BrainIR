"""Level B execution profile (research/phase4/LEVEL_B_EXECUTION.md; fork P1). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/profile_level_b.py --room <stand-in room> --systems s1,s2 [--tier val]
        [--gpu-classes rtx6000,b200,h100,h200,l40s] [--out research/phase4/LEVEL_B_PROFILE.json]

FITS ONLY (public training data; nothing held out is touched). For each profiled system:
  - the GPU stand-in (a method declaring device 'cuda') fitted once per GPU class, UNPACKED (iso_gpu_<class>) -> fit wall, the
    worker-measured training seconds, the device the worker actually used (CUDA must be usable inside a scrubbed-environment iso
    worker), container cost;
  - the same GPU stand-in fitted 4 x at once on ONE GPU in the packed class iso_pack_gpu_rtx6000 (4 slots) -> packing speed-up;
  - the CPU stand-ins fitted on iso_fit_s (unpacked) and 8 at once on iso_pack_fit (packed) -> CPU fit wall per class and packing
    speed-up, peak container memory.
Writes the JSON profile (timings, costs, devices; no metric of any model) and prints a table.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p4"))

from brainir_causal import suites as SU  # noqa: E402


def _paths(sid: str, tier: str) -> dict:
    import tournament as T
    kind = "real" if sid.startswith("real:") else "synthetic"
    return T.modal_system_paths(sid, kind, tier)


def fit_payload(method: str, sid: str, tier: str, key: str, seed: int = 0) -> dict:
    return {"role": "fit", "job": {"method": method, "systems": [sid], "data": [_paths(sid, tier)["fit_data"]], "seed": seed, "config": {},
                                   "threads": 3, "timeout_s": 3600}, "methods_key": key, "reload": ["fit"]}


def summarise(r) -> dict:
    if not isinstance(r, dict):
        return {"error": repr(r)[:300]}
    if r.get("error"):
        return {"error": str(r["error"])[:300]}
    side = r.get("side") or {}
    tc = ((side.get("info") or {}).get("train_cost") or {})
    return {"job_wall_s": side.get("job_wall_s"), "container_wall_s": r.get("container_wall_s"), "peak_container_mb": r.get("peak_container_mb"),
            "device": tc.get("device"), "gpu_name": tc.get("gpu_name"), "train_s": tc.get("train_s"),
            "slot": ((r.get("iso") or {}).get("pack") or {}).get("slot")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--systems", required=True)
    ap.add_argument("--tier", default="val")
    ap.add_argument("--gpu-method", default="p1_standin_torch_gpu")
    ap.add_argument("--cpu-methods", default="p1_standin_fullstate,frozen_brainir_state_v1")
    ap.add_argument("--gpu-classes", default="rtx6000,b200,h100,h200,l40s")
    ap.add_argument("--out", default=str(ROOT / "research" / "phase4" / "LEVEL_B_PROFILE.json"))
    ap.add_argument("--gpu-only", action="store_true", help="skip the CPU part (the Level B comparison rounds measure it)")
    args = ap.parse_args(argv)
    from brainir_causal.p4modal.app import CLASSES, Backend, usd_per_s
    sids = [s for s in args.systems.split(",") if s]
    gpus = [g for g in args.gpu_classes.split(",") if g]
    cpu_methods = [m for m in args.cpu_methods.split(",") if m]
    unpacked_gpu = [f"iso_gpu_{g}" for g in gpus]
    classes = sorted(set(unpacked_gpu) | {"iso_pack_gpu_rtx6000"} | (set() if args.gpu_only else {"iso_fit_s", "iso_pack_fit"}))
    synthetic = any(not s.startswith("real:") for s in sids)
    extra = {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER} if synthetic else None
    mdir = Path(args.room) / "src" / "brainir_causal" / "methods"
    rep = {"what": "Level B execution profile (fits on public data only)", "tier": args.tier, "systems": sids,
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "gpu": {}, "gpu_packed": {}, "cpu": {}}
    t0 = time.time()
    from concurrent.futures import ThreadPoolExecutor
    with Backend(classes=classes, extra_dirs=extra, app_name="brainir-p4-p1-profile") as be:
        key = be.methods_key(mdir)

        def gpu_unpacked(cls):
            t = time.time()
            res = be.run_iso([fit_payload(args.gpu_method, s, args.tier, key) for s in sids], cls, f"profile:{cls}")
            return cls, {"wall_s": round(time.time() - t, 1), "jobs": {s: summarise(r) for s, r in zip(sids, res)},
                         "usd_per_s": usd_per_s(cls)}

        def gpu_packed():
            cls = "iso_pack_gpu_rtx6000"
            pl = [fit_payload(args.gpu_method, sids[0], args.tier, key, seed=s) for s in range(CLASSES[cls]["slots"])]
            t = time.time()
            res = be.run_iso_packed(pl, cls, expected_s=[1.0] * len(pl), label="profile:gpu-packed")
            return {"class": cls, "n_jobs": len(pl), "system": sids[0], "wall_s": round(time.time() - t, 1),
                    "jobs": [summarise(r) for r in res], "usd_per_s": usd_per_s(cls)}

        def cpu_profile(cls):
            pl, tags = [], []
            reps = 1 if not CLASSES[cls].get("slots") else max(1, CLASSES[cls]["slots"] // max(1, len(sids) * len(cpu_methods)))
            for m in cpu_methods:
                for s in sids:
                    for seed in range(reps):
                        pl.append(fit_payload(m, s, args.tier, key, seed=seed))
                        tags.append((m, s, seed))
            t = time.time()
            res = (be.run_iso_packed(pl, cls, expected_s=[1.0] * len(pl), label=f"profile:{cls}") if CLASSES[cls].get("slots")
                   else be.run_iso(pl, cls, f"profile:{cls}"))
            return cls, {"wall_s": round(time.time() - t, 1), "n_jobs": len(pl),
                         "jobs": [{"method": m, "system": s, "seed": sd, **summarise(r)} for (m, s, sd), r in zip(tags, res)],
                         "usd_per_s": usd_per_s(cls)}

        def save():                       # incremental: an interrupted profile keeps what finished
            Path(args.out).write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        # bounded concurrency on the orchestrator (the shared host ran out of socket buffers with many concurrent Modal clients)
        with ThreadPoolExecutor(max_workers=3) as ex:
            fg = [ex.submit(gpu_unpacked, c) for c in unpacked_gpu]
            fp = ex.submit(gpu_packed)
            fc = [] if args.gpu_only else [ex.submit(cpu_profile, c) for c in ("iso_fit_s", "iso_pack_fit")]
            for f in fg:
                c, v = f.result()
                rep["gpu"][c] = v
                save()
            rep["gpu_packed"] = fp.result()
            save()
            for f in fc:
                c, v = f.result()
                rep["cpu"][c] = v
                save()
        rep["modal_cost"] = be.cost_summary()
    rep["wall_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"{'class':24s} {'system':22s} {'job_wall_s':>10s} {'train_s':>8s} device")
    for c, v in rep["gpu"].items():
        for s, j in v["jobs"].items():
            print(f"{c:24s} {s:22s} {str(j.get('job_wall_s')):>10s} {str(j.get('train_s')):>8s} {j.get('device')} {j.get('gpu_name') or j.get('error', '')}")
    gp = rep["gpu_packed"]
    print(f"packed GPU ({gp['class']}, {gp['n_jobs']} fits on one GPU): wall {gp['wall_s']} s; per-fit job walls "
          f"{[j.get('job_wall_s') for j in gp['jobs']]}")
    for c, v in rep["cpu"].items():
        print(f"{c}: {v['n_jobs']} fits in {v['wall_s']} s; job walls {[j.get('job_wall_s') for j in v['jobs']]}")
    print("cost", (rep.get("modal_cost") or {}).get("usd_approx_total"), "wall", rep["wall_s"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
