"""Build causal_state_v1 datasets ON MODAL, one system per container, directly into the Phase 4 volumes (ORCHESTRATOR SIDE).

    uv run --no-sync --project phase4 python scripts/p4/build_on_modal.py real --level public [--systems a,b] [--download]
    uv run --no-sync --project phase4 python scripts/p4/build_on_modal.py real --level B
    uv run --no-sync --project phase4 python scripts/p4/build_on_modal.py synthetic --tier dev [--generator-dir DIR] [--download-public]
    uv run --no-sync --project phase4 python scripts/p4/build_on_modal.py download-tier-public --tier dev [--streams 6]
    uv run --no-sync --project phase4 python scripts/p4/build_on_modal.py stage-local --tier toy      # upload a LOCALLY built tier
    uv run --no-sync --project phase4 python scripts/p4/build_on_modal.py download --volume fit --dir data/real/real_public/public/<sid>
        --dest data/phase4/real/real_public/public/<sid>

Why remote: the local disk cannot hold the datasets (tens to hundreds of GB for realistic synthetic tiers) and the uplink is slow;
the containers write the sets where the evaluation and the fits read them. Protocols are PLANNED HERE (`suites.plan_remote_job`:
hidden-range seeds come from the salt, which never leaves this machine); each container (class 'build': 16 cores, host-gated for
bit-reproducible simulation) simulates, writes its system's parts (public parts -> fit volume, held-out parts / truth / onset states
-> eval volume), publishes its store records (public real records -> store volume; everything else -> eval volume store) and returns a
sha256 manifest. Level C sets and the confirmation tier refuse to plan before the method lock. Records of every run go to
research/phase4/REAL_DATA_BUILD.json (real) or research/phase4/SYNTHETIC_DATA_BUILD.json (synthetic) and to MODAL_RUNS.md by the
caller.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402
from brainir_causal.synthadapter import TRAP_CATALOG_REL as SA_TRAP_REL  # noqa: E402

REAL_RECORD = ROOT / "research" / "phase4" / "REAL_DATA_BUILD.json"
SYN_RECORD = ROOT / "research" / "phase4" / "SYNTHETIC_DATA_BUILD.json"
REAL_INTERNAL = ROOT / "benchmarks" / "causal_state_v1" / "hidden" / "real_systems_internal.json"
LOCAL_REAL = ROOT / "data" / "phase4" / "real"
LOCAL_SUITES = ROOT / "data" / "phase4" / "suites"


def _append_record(path: Path, rec: dict) -> None:
    runs = json.loads(path.read_text(encoding="utf-8"))["runs"] if path.exists() else []
    runs.append(rec)
    path.write_text(json.dumps({"runs": runs}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")


def _summ(res: dict) -> dict:
    """Per-system summary of a build result (without the full manifest)."""
    if not isinstance(res, dict) or "result" not in res:
        return {"error": str(res)[:2000]}
    r = res["result"]
    parts = {d: {**p["counts"], "first_errors": p.get("errors", [])[:3]} for d, p in (r.get("parts") or {}).items()}
    man = r.get("manifest") or {}
    return {"parts": parts, "onset_states": r.get("onset_states"), "published": r.get("published"), "wall_s": r.get("wall_s"),
            "n_files": {k: len(v) for k, v in man.items()}, "bytes": {k: int(sum(x[1] for x in v.values())) for k, v in man.items()},
            "manifest_sha256": hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest(),
            "container_wall_s": res.get("container_wall_s"), "peak_container_mb": res.get("peak_container_mb")}


#: a system whose previous build took longer than this goes to the 32-core class with a 32-process pool; the pool size does not change
#: what is built (every trajectory is simulated from its own spec and seed; the build manifests are compared across rebuilds)
XL_SECONDS = 600.0
XL_WORKERS = 32


def previous_build_seconds(tier: str) -> dict[str, float]:
    """{system: container wall seconds} of each system's most recent SUCCESSFUL recorded build of the tier (a failed or partial build
    contributes nothing; empty if none)."""
    if not SYN_RECORD.exists():
        return {}
    out: dict[str, float] = {}
    for r in reversed(json.loads(SYN_RECORD.read_text(encoding="utf-8")).get("runs", [])):
        if r.get("what") != f"synthetic tier {tier}" or not isinstance(r.get("systems"), dict):
            continue
        for s, v in r["systems"].items():
            if s not in out and isinstance(v, dict) and "error" not in v and (v.get("container_wall_s") or v.get("wall_s")):
                out[s] = float(v.get("container_wall_s") or v.get("wall_s"))
    return out


def run_builds(jobs: list[dict], *, extra_dirs: dict | None, label: str, timeout_s: float = 10 * 3600,
               previous_s: dict[str, float] | None = None) -> tuple[dict, dict, list]:
    """Submit one build job per system; returns ({sid: raw result}, cost summary, manifests). Systems whose previous build took longer
    than XL_SECONDS run on the 32-core class (`build_xl`, XL_WORKERS processes); both classes run at once, each queue longest first."""
    from concurrent.futures import ThreadPoolExecutor as _TPE

    from brainir_causal.p4modal.app import Backend
    prev = previous_s or {}
    order = sorted(range(len(jobs)), key=lambda i: -prev.get(jobs[i]["sid"], 0.0))
    # LOCAL execution (P4_BACKEND=local; LOCAL_EXECUTION_PLAN.md): ONE queue with the planned worker count (the machine runs one
    # memory-heavy job at a time: no 32-worker class and no second queue); the builds are the same, only their pool size differs
    local = __import__("os").environ.get("P4_BACKEND") == "local"
    xl = [] if local else [i for i in order if prev.get(jobs[i]["sid"], 0.0) > XL_SECONDS]
    std = [i for i in order if i not in set(xl)]
    for i in xl:
        jobs[i] = dict(jobs[i], workers=XL_WORKERS)
    res: list = [None] * len(jobs)
    with Backend(classes=["build", "build_xl", "util"], extra_dirs=extra_dirs, app_name="brainir-p4-build") as be:
        def submit(idx: list[int], cls: str):
            if not idx:
                return
            got = be.call("brainir_causal.suites:build_system_job", [[jobs[i]] for i in idx], cls=cls, timeout_s=timeout_s, threads=1,
                          eager=True, reload=["fit", "eval", "store"], commit=["fit", "eval", "store"])
            for i, r in zip(idx, got):
                res[i] = r
        with _TPE(2) as ex:
            for f in [ex.submit(submit, xl, "build_xl"), ex.submit(submit, std, "build")]:
                f.result()
        cost = be.cost_summary()
    out = {}
    for j, r in zip(jobs, res):
        out[j["sid"]] = r if isinstance(r, dict) else {"error": repr(r)[:2000]}
    print(f"builds: {len(xl)} systems on build_xl ({XL_WORKERS} workers), {len(std)} on build", flush=True)
    return out, cost, [label]


def upload_small(volume: str, local_files: dict[str, Path], dest: str) -> dict:
    """Upload small tier-level files ({relative name: local path}) to /<volume>/<dest>/ (one tar, extracted in Modal)."""
    import shutil
    import tempfile

    from brainir_causal.p4modal.app import Backend
    tmp = Path(tempfile.mkdtemp(prefix="p4up_", dir=str(ROOT / "data" / "phase4")))
    try:
        for rel, p in local_files.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, tmp / rel)
        with Backend(classes=["util"], app_name="brainir-p4-util") as be:
            # MERGE: the destination (e.g. data/suites/<tier>) holds every system's parts; replacing it would delete them (a one-system
            # build did exactly that on 2026-09-27, LOG 12.2)
            return be.upload_dir(volume, tmp, dest, replace=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================================================================ commands
def cmd_real(args) -> int:
    from brainir_causal.systems import load_real_internal
    sids = sorted(load_real_internal())
    if args.systems:
        sids = [s for s in sids if s in set(args.systems.split(","))]
    t0 = time.time()
    jobs = [SU.plan_remote_job("real", s, level=args.level, workers=args.workers) for s in sids]
    print(f"planned {len(jobs)} real systems (level {args.level}) in {time.time() - t0:.0f} s; "
          f"specs per system: {[sum(len(p['specs']) for p in j['parts']) for j in jobs]}", flush=True)
    # the internal records the evaluation reads (hidden targets: eval volume only)
    up = upload_small("eval", {"real_systems_internal.json": REAL_INTERNAL}, "data/real")
    t1 = time.time()
    results, cost, _ = run_builds(jobs, extra_dirs=None, label=f"real-{args.level}")
    summ = {s: _summ(r) for s, r in results.items()}
    rec = {"what": f"real level {args.level}", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": summ,
           "wall_s": round(time.time() - t1, 1), "plan_s": round(t1 - t0, 1), "modal_cost_approx": cost, "internal_upload": up,
           "volume_layout": {"public": SU.remote_dirs(SU.REAL_TIERS[args.level], kind="real"), "store": (
               SU.REMOTE["store"] if args.level == "public" else SU.REMOTE["eval_store"])}}
    # full manifests (sha256 per file) kept next to the record for later verification of downloads
    man_dir = ROOT / "research" / "phase4" / "build_manifests"
    man_dir.mkdir(parents=True, exist_ok=True)
    for s, r in results.items():
        if isinstance(r, dict) and "result" in r:
            (man_dir / f"real_{args.level}_{SU._safe(s)}.json").write_text(json.dumps(r["result"].get("manifest") or {}, indent=0) + "\n",
                                                                           encoding="utf-8", newline="\n")
    _append_record(REAL_RECORD, rec)
    # a store record that differs from the one already on the volume (same key) is a reproducibility failure (suites.publish_store)
    bad = {s: v for s, v in summ.items() if "error" in v or any(p.get("errors") for p in (v.get("parts") or {}).values())
           or (v.get("published") or {}).get("mismatch")}
    print(json.dumps({"systems": len(summ), "failed_or_with_errors": sorted(bad), "wall_s": rec["wall_s"],
                      "store": {s: v.get("published") for s, v in summ.items()},
                      "usd_approx": cost.get("usd_approx_total")}, indent=1), flush=True)
    if args.download and args.level == "public":
        cmd_download_real_public(sids)
    return 0 if not bad else 1


def cmd_download_real_public(sids: list[str]) -> dict:
    """Download the public real data (the clean room's real systems) into data/phase4/real/real_public/public/<sid>."""
    from brainir_causal.p4modal.app import Backend
    out = {}
    with Backend(classes=["util"], app_name="brainir-p4-util") as be:
        def one(s):
            return s, be.download_dir("fit", f"data/real/real_public/public/{SU._safe(s)}",
                                      LOCAL_REAL / "real_public" / "public" / SU._safe(s))
        with ThreadPoolExecutor(max_workers=4) as ex:
            for s, r in ex.map(one, sids):
                out[s] = r
                print(f"downloaded {s}: {r['n_files']} files, {r['bytes'] / 1e6:.0f} MB in {r['download_s']} s", flush=True)
    _append_record(REAL_RECORD, {"what": "download real public", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "downloads": out})
    return out


#: the reference platform of every generator computation (LOG P4-D32): the pinned sandbox image (bit-identical to the Modal containers)
PLAN_IMAGE = "brainir-p4-sandbox:1"
PLAN_IMAGE_RECORD = ROOT / "docker" / "p4sandbox" / "image.json"


def plan_image_id() -> str:
    """The sandbox image BY ID (a tag is mutable; review H round 3, NEW-4): the id recorded in docker/p4sandbox/image.json, which the
    local image of that tag must carry."""
    import subprocess
    rec = json.loads(PLAN_IMAGE_RECORD.read_text(encoding="utf-8"))
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", PLAN_IMAGE], capture_output=True, text=True)
    local = r.stdout.strip()
    if r.returncode != 0 or local != rec["id"]:
        raise SystemExit(f"the local {PLAN_IMAGE} is {local or 'missing'}, not the recorded {rec['id']} (docker/p4sandbox/image.json)")
    return rec["id"]


def plan_on_reference_platform(tier: str, systems: str, workers: int) -> tuple[list[dict], Path]:
    """Run scripts/p4/plan_synthetic.py in the pinned image (network off; repository read-only; the salt read-only for the salted
    streams; output into data/phase4/suites/<tier>/_plan); returns (jobs, plan directory)."""
    import subprocess
    out = SU.tier_dirs(tier, LOCAL_SUITES)["base"] / "_plan"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    mounts = [(ROOT / "phase4" / "src", "/repo/phase4/src", "ro"), (ROOT / "scripts" / "p4" / "plan_synthetic.py", "/repo/scripts/p4/plan_synthetic.py", "ro"),
              (ROOT / SU.GENERATOR_REL, SU.GENERATOR_CONTAINER, "ro"), (ROOT / "benchmarks" / "causal_state_v1" / "public", "/repo/benchmarks/causal_state_v1/public", "ro"),
              (ROOT / "benchmarks" / "causal_state_v1" / "hidden", "/repo/benchmarks/causal_state_v1/hidden", "ro"),
              (ROOT / "data" / "phase4" / "hidden", "/repo/data/phase4/hidden", "ro"), (out, "/out", "rw")]
    lock = ROOT / "research" / "phase4" / "METHOD_LOCK.json"
    if lock.exists():               # the lock-guarded tiers (conf, trap) plan only after the lock, and the planner checks it there
        mounts.append((lock, "/repo/research/phase4/METHOD_LOCK.json", "ro"))
    if tier == "trap":              # review G's catalog (outside the frozen generator; synthadapter.TRAP_CATALOG_REL)
        mounts.append((ROOT / Path(SA_TRAP_REL).parent, "/repo/" + str(Path(SA_TRAP_REL).parent.as_posix()), "ro"))
    from brainir_causal.p4modal.images import CPU_PINS
    cmd = ["docker", "run", "--rm", "--network", "none", "--pull", "never", "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
           "-e", "MKL_NUM_THREADS=1", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/repo/phase4/src"]
    for k, v in CPU_PINS.items():           # the numerics pins of the service and Modal containers (review H round 3, NEW-4)
        cmd += ["-e", f"{k}={v}"]
    for src, dst, mode in mounts:
        cmd += ["-v", f"{src}:{dst}:{mode}"]
    cmd += [plan_image_id(), "python", "/repo/scripts/p4/plan_synthetic.py", "--tier", tier, "--out", "/out", "--workers", str(workers)]
    if systems:
        cmd += ["--systems", systems]
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if r.returncode != 0:
        raise SystemExit(f"planning on the reference platform failed:\n{r.stdout[-2000:]}\n{r.stderr[-4000:]}")
    return json.loads((out / "jobs.json").read_text(encoding="utf-8")), out


def _generator_stamp() -> str:
    return hashlib.sha256((ROOT / "research" / "phase4" / "GENERATOR_DELIVERY_SHA256.txt").read_bytes()).hexdigest()


def _plan_or_reuse(args) -> tuple[list[dict], Path]:
    """The tier's plan: reused (--reuse-plan) when a FULL plan of this tier with the same generator delivery and worker count exists,
    filtered to --systems; otherwise planned on the reference platform (a full plan when reuse is asked for, so later batches reuse it).
    Execution only: a plan is a deterministic function of (generator, tier, seed, workers) (LOCAL_EXECUTION_PLAN.md section 7)."""
    out = SU.tier_dirs(args.tier, LOCAL_SUITES)["base"] / "_plan"
    stamp = {"generator": _generator_stamp(), "tier": args.tier, "workers": int(args.workers)}
    sf = out / "plan_stamp.json"
    want = [x for x in args.systems.split(",") if x]
    if getattr(args, "reuse_plan", False) and sf.exists() and json.loads(sf.read_text(encoding="utf-8")) == stamp:
        jobs = json.loads((out / "jobs.json").read_text(encoding="utf-8"))
        print(f"reusing the plan in {out.relative_to(ROOT)} ({len(jobs)} systems)", flush=True)
    else:
        jobs, out = plan_on_reference_platform(args.tier, "" if getattr(args, "reuse_plan", False) else args.systems, args.workers)
        if getattr(args, "reuse_plan", False):
            sf.write_text(json.dumps(stamp) + "\n", encoding="utf-8", newline="\n")
    if want:
        missing = sorted(set(want) - {j["sid"] for j in jobs})
        if missing:
            raise SystemExit(f"systems not in the {args.tier} plan: {missing}")
        jobs = [j for j in jobs if j["sid"] in set(want)]
    return jobs, out


def cmd_synthetic(args) -> int:
    if args.generator_dir or args.generator_package != "p4synth":
        raise SystemExit("official builds plan with the hash-locked generator on the reference platform (no --generator-dir)")
    t0 = time.time()
    if args.tier in ("toy", "toyC"):
        seed = SU.tier_seed(args.tier)
        pubs, ints, truths = SU.synthetic_tier_records(args.tier, seed, None)
        sids = sorted(pubs) if not args.systems else [s for s in sorted(pubs) if s in set(args.systems.split(","))]
        jobs = [SU.plan_remote_job("synthetic", s, tier=args.tier, generator=None, workers=args.workers) for s in sids]
    else:
        jobs, plan_dir = _plan_or_reuse(args)
        if getattr(args, "plan_only", False):
            print(json.dumps({"tier": args.tier, "planned": sorted(j["sid"] for j in jobs), "plan_dir": str(plan_dir)}), flush=True)
            return 0
        ints = json.loads((plan_dir / "internal_records.json").read_text(encoding="utf-8"))
        truths = json.loads((plan_dir / "systems_truth.json").read_text(encoding="utf-8"))
    # tier-level files (internal records: hidden targets; truth summaries): kept locally (small; the tournament driver lists the
    # tier's systems from them) and uploaded to the eval volume
    base = SU.tier_dirs(args.tier, LOCAL_SUITES)["base"]
    (base / "truth").mkdir(parents=True, exist_ok=True)
    (base / "internal_records.json").write_text(json.dumps(ints, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (base / "truth" / "systems_truth.json").write_text(json.dumps(truths, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8",
                                                       newline="\n")
    up = upload_small("eval", {"internal_records.json": base / "internal_records.json",
                               "truth/systems_truth.json": base / "truth" / "systems_truth.json"}, f"data/suites/{args.tier}")
    extra = None if args.tier in ("toy", "toyC") else {SU.GENERATOR_REL: SU.GENERATOR_CONTAINER}
    if args.tier == "trap":         # review G's catalog, baked like the generator (root-only in iso images)
        d = Path(SA_TRAP_REL).parent.as_posix()
        extra[d] = f"/repo/{d}"
    t1 = time.time()
    prev = previous_build_seconds(args.tier)
    if args.xl_all:                 # every system on the 32-core class (wall time first; the pool size does not change what is built)
        prev = {j["sid"]: max(prev.get(j["sid"], 0.0), XL_SECONDS + 1.0) for j in jobs}
    results, cost, _ = run_builds(jobs, extra_dirs=extra, label=f"synthetic-{args.tier}", previous_s=prev)
    summ = {s: _summ(r) for s, r in results.items()}
    # full manifests (sha256 per file of every part) kept next to the record: the benchmark lock hashes them (LOG P4-D33)
    man_dir = ROOT / "research" / "phase4" / "build_manifests"
    man_dir.mkdir(parents=True, exist_ok=True)
    for s, r in results.items():
        if isinstance(r, dict) and "result" in r:
            (man_dir / f"syn_{args.tier}_{SU._safe(s)}.json").write_text(json.dumps(r["result"].get("manifest") or {}, indent=0) + "\n",
                                                                          encoding="utf-8", newline="\n")
    rec = {"what": f"synthetic tier {args.tier}", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "systems": summ,
           "wall_s": round(time.time() - t1, 1), "plan_s": round(t1 - t0, 1), "modal_cost_approx": cost, "tier_files_upload": up}
    _append_record(SYN_RECORD, rec)
    bad = {s: v for s, v in summ.items() if "error" in v}
    print(json.dumps({"systems": len(summ), "failed": sorted(bad), "wall_s": rec["wall_s"], "usd_approx": cost.get("usd_approx_total")},
                     indent=1), flush=True)
    return 0 if not bad else 1


def cmd_download_tier_public(args) -> int:
    """Download the PUBLIC part of the dev tier (the only synthetic material that may enter a room) into
    data/phase4/suites/dev/public/<system>, one system per stream (parallel), each checked against the container's sha256."""
    from brainir_causal.p4modal.app import Backend
    if args.tier != "dev":
        raise SystemExit("only the dev tier's public part is ever downloaded (the other tiers stay on the volumes)")
    base = SU.tier_dirs(args.tier, LOCAL_SUITES)
    sids = sorted(json.loads((base["base"] / "internal_records.json").read_text(encoding="utf-8")))
    if args.systems:
        sids = [s for s in sids if s in set(args.systems.split(","))]
    out, t0 = {}, time.time()
    with Backend(classes=["util"], app_name="brainir-p4-util") as be:
        def one(s):
            return s, be.download_dir("fit", f"data/suites/{args.tier}/public/{SU._safe(s)}", base["public"] / SU._safe(s))
        with ThreadPoolExecutor(max_workers=int(args.streams)) as ex:
            for s, r in ex.map(one, sids):
                out[s] = r
                print(f"downloaded {s}: {r['n_files']} files, {r['bytes'] / 1e6:.0f} MB in {r['download_s']} s", flush=True)
    _append_record(SYN_RECORD, {"what": f"download {args.tier} public part", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "wall_s": round(time.time() - t0, 1), "downloads": out})
    print(json.dumps({"systems": len(out), "bytes": sum(v["bytes"] for v in out.values()), "wall_s": round(time.time() - t0, 1)}))
    return 0


def cmd_stage_local(args) -> int:
    """Upload a LOCALLY built synthetic tier (e.g. the toy tier of the smoke tests): onset states computed from the local store, the
    public part to the fit volume, the eval / truth parts and tier files to the eval volume."""
    from brainir_causal.p4modal.app import Backend
    dirs = SU.tier_dirs(args.tier, LOCAL_SUITES)
    sids = sorted(json.loads((dirs["base"] / "internal_records.json").read_text(encoding="utf-8")))
    onset = {s: SU.write_onset_states(s, dirs, SU.STORE) for s in sids}
    out = {"onset_states": onset}
    with Backend(classes=["util"], app_name="brainir-p4-util") as be:
        out["public"] = be.upload_dir("fit", dirs["public"], f"data/suites/{args.tier}/public")
        out["eval"] = be.upload_dir("eval", dirs["base"], f"data/suites/{args.tier}",
                                    files=[q for q in dirs["base"].rglob("*") if q.is_file() and dirs["public"] not in q.parents])
    _append_record(SYN_RECORD, {"what": f"stage local tier {args.tier}", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "systems": sids, "uploads": {k: (v if k == "onset_states" else {kk: vv for kk, vv in v.items() if kk != "sha256"})
                                                             for k, v in out.items()}})
    print(json.dumps({"systems": sids, "public_files": out["public"]["n_files"], "eval_files": out["eval"]["n_files"]}, indent=1))
    return 0


def cmd_download(args) -> int:
    from brainir_causal.p4modal.app import Backend
    with Backend(classes=["util"], app_name="brainir-p4-util") as be:
        r = be.download_dir(args.volume, args.dir, Path(args.dest))
    print(json.dumps(r, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("real")
    r.add_argument("--level", required=True, choices=("public", "B", "C"))
    r.add_argument("--systems", default="")
    r.add_argument("--workers", type=int, default=16)
    r.add_argument("--download", action="store_true")
    s = sub.add_parser("synthetic")
    s.add_argument("--tier", required=True, choices=("dev", "val", "conf", "trap", "toy", "toyC"))
    s.add_argument("--systems", default="")
    s.add_argument("--workers", type=int, default=16)
    s.add_argument("--generator-dir", default="")
    s.add_argument("--generator-package", default="p4synth")
    s.add_argument("--xl-all", action="store_true", help="every system on the 32-core build class (longest first by previous time)")
    s.add_argument("--reuse-plan", action="store_true", help="plan the whole tier once and reuse it for later --systems batches")
    s.add_argument("--plan-only", action="store_true", help="plan (or reuse the plan) and print the system ids; build nothing")
    dl = sub.add_parser("download-tier-public")
    dl.add_argument("--tier", required=True, choices=("dev",))
    dl.add_argument("--systems", default="")
    dl.add_argument("--streams", type=int, default=6)
    st = sub.add_parser("stage-local")
    st.add_argument("--tier", required=True)
    d = sub.add_parser("download")
    d.add_argument("--volume", required=True, choices=("fit", "eval", "store"))
    d.add_argument("--dir", required=True)
    d.add_argument("--dest", required=True)
    args = ap.parse_args(argv)
    return {"real": cmd_real, "synthetic": cmd_synthetic, "stage-local": cmd_stage_local, "download": cmd_download,
            "download-tier-public": cmd_download_tier_public}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
