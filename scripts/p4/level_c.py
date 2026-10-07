"""causal_state_v1 LEVEL C driver (ORCHESTRATOR SIDE; benchmarks/causal_state_v1/PROTOCOL.md sections 4, 5, 9, 11, 12; goal5 69-77).
Design, guards, dry-run numbers and the projected post-lock wall time: research/phase4/LEVEL_C_DRIVER.md. Library: levelc_lib.py;
container-side functions: levelc_remote.py (iso role "call").

    # before the lock (never touches hidden data)
    uv run --no-sync --project phase4 python scripts/p4/level_c.py plan --dry-run-dev [--sample smoke|ten|full]
    uv run --no-sync --project phase4 python scripts/p4/level_c.py run --dry-run-dev --run-id D1 [--sample smoke] [--max-containers 7]
    uv run --no-sync --project phase4 python scripts/p4/level_c.py claims --dry-run-dev --run-id D1
    uv run --no-sync --project phase4 python scripts/p4/level_c.py report --dry-run-dev --run-id D1
    uv run --no-sync --project phase4 python scripts/p4/level_c.py project --dry-run-dev --run-id D1 [--target official]
    uv run --no-sync --project phase4 python scripts/p4/level_c.py prewarm                 # build every Modal image of the run
    uv run --no-sync --project phase4 python scripts/p4/level_c.py trap-probe              # the trap tier's image path, DUMMY catalog
    uv run --no-sync --project phase4 python scripts/p4/level_c.py fixed-from-levelb --round <final round>   # LEVEL_B_FIXED.json
    # a long run survives a dead Modal client (exit 75): `run ... --auto-resume 3` relaunches it with the same run id (bounded)
    # after the lock (each refuses unless the method lock verifies; START / DONE rows in research/phase4/HIDDEN_EVALUATIONS.md)
    uv run --no-sync --project phase4 python scripts/p4/level_c.py run --official --run-id C1
    uv run --no-sync --project phase4 python scripts/p4/level_c.py claims --official --run-id C1

A dry run maps the confirmation tier to the DEV tier, the real Level C sets to the real PUBLIC evaluation subset, and uses the toyC
tier (built here: the Level C design with OOD and robustness items, the adapter's toy systems) for the Level C design path; the
locked method is played by the stand-in `levelc_standin_pca` (scripts/p4/levelc_standin) and the baselines / the 5.14 method by the
frozen earlier method. Official runs run the LOCKED method (phase4/src/brainir_causal/methods) with the Level B-fixed choices of
research/phase4/LEVEL_B_FIXED.json, on the confirmation tier, review G's trap tier and the real Level C sets. A dry run has no trap
tier (it is salted and built after the lock): `--trap-standins` marks dev systems as the trap set (the trap plan and Stage D's trap
section on stand-in results), and `trap-probe` checks the images' catalog path with a DUMMY catalog.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import levelc_lib as L  # noqa: E402

from brainir_causal import suites as SU  # noqa: E402

DRY_ROOT = L.RUN_BASE / "levelc_dry"
SMOKE_TYPES = (11, 12, 21, 23)          # an implementation group (11) with its unrelated null (12), a non-compressible trap type, a trap
SMOKE_REAL = ("real:A:full", "real:A:m1")
DRY_CLASSES = ["iso_pack_fit", "iso_pack_eval", "iso_pack_loop", "pack_xl", "build", "util"]
#: unpacked runs (one job per container): the classes and their in-flight caps (containers)
UNPACKED_CAPS = {"iso_fit_s": 8, "iso_eval_l": 10, "iso_loop": 8, "eval_l": 4, "build": 2, "util": 1}


# ================================================================================================================ helpers
def run_dir(args) -> Path:
    return (L.RUN_ROOT if args.official else DRY_ROOT) / args.run_id


def mode_of(args) -> L.Mode:
    if args.official == args.dry_run_dev:
        raise SystemExit("give exactly one of --official / --dry-run-dev")
    return L.Mode.official() if args.official else L.Mode.dry(toy=not args.no_toy)


def toy_meta(tier: str = "toyC") -> tuple[dict, dict, dict]:
    """(public records, internal records, truth summaries) of the toy tier (public seed; no generator), also written locally."""
    seed = SU.tier_seed(tier)
    pubs, ints, truths = SU.synthetic_tier_records(tier, seed, None)
    base = SU.tier_dirs(tier, SU.SUITES)["base"]
    (base / "truth").mkdir(parents=True, exist_ok=True)
    (base / "internal_records.json").write_text(json.dumps(ints, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (base / "truth" / "systems_truth.json").write_text(json.dumps(truths, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8",
                                                       newline="\n")
    return pubs, ints, truths


def sample_systems(specs: dict, sample: str) -> list[str] | None:
    """The systems of a dry-run sample: 'smoke' / 'ten' = one implementation group with its unrelated null, a non-compressible trap
    type, a trap type, one real full network, one real mechanism and the toy systems (about 10 % of the full job list with 'ten');
    'full' = everything."""
    if sample == "full":
        return None
    syn = {s: v for s, v in specs.items() if v["kind"] == "synthetic" and v["cls"] == "syn"}
    pick: list[str] = []
    for t in SMOKE_TYPES:
        cands = sorted(s for s, v in syn.items() if v.get("type") == t)
        if t == 11:
            pick += cands                                   # the whole group
        elif cands:
            pick.append(cands[0])
    pick += [s for s in SMOKE_REAL if s in specs]
    pick += sorted(s for s, v in specs.items() if v["cls"] == "toy")
    return pick


def describe(be, methods: list[str], key: str, cls: str = "iso_pack_fit") -> dict:
    payloads = [{"role": "describe", "job": {"method": m}, "methods_key": key, "reload": ["fit"]} for m in methods]
    res = (be.run_iso_packed(payloads, cls, label="describe") if cls.startswith("iso_pack")
           else be.run_iso(payloads, cls, label="describe"))
    out = {}
    for m, r in zip(methods, res):
        d = (r or {}).get("describe") if isinstance(r, dict) else None
        if not isinstance(d, dict):
            raise SystemExit(f"describe {m} failed: {r!r}"[:2000])
        out[m] = d
    return out


def build_the_plan(args, specs: dict, *, method: str, limpo_method: str, baselines: list[str], fixed: dict, described: dict,
                   build_jobs: dict) -> L.Plan:
    plan = L.Plan(run_id=args.run_id, mode=mode_of(args), specs=specs, method=method, limpo_method=limpo_method, baselines=baselines,
                  fixed=fixed, described=described, build_jobs=build_jobs,
                  class_map=(dict(L.UNPACKED) if getattr(args, "unpacked", False) else {}))
    if args.sample == "smoke":
        plan.loop_seeds, plan.budget = (0,), 25
    if args.loop_seeds:
        plan.loop_seeds = tuple(int(x) for x in args.loop_seeds.split(","))
    if args.budget:
        plan.budget = int(args.budget)
    if args.designers:
        plan.designers = tuple(d for d in args.designers.split(",") if d)
    if getattr(args, "no_loops", False):
        plan.designers = ()                      # a staged run: the loops come in a later invocation with the same run id
    return L.build_plan(plan)


def trap_standins_of(args) -> list[str]:
    return [s.strip() for s in (getattr(args, "trap_standins", "") or "").split(",") if s.strip()]


def dry_setup(args) -> tuple[dict, dict, dict]:
    """(specs, build jobs of the toy tier, toy public records) of a dry run."""
    mode = mode_of(args)
    tm = None
    build_jobs = {}
    if mode.toy_tier:
        _pubs, ints, truths = toy_meta(mode.toy_tier)
        tm = (ints, truths)
        for sid in sorted(ints):
            build_jobs[sid] = SU.plan_remote_job("synthetic", sid, tier=mode.toy_tier, generator=None, workers=8)
    specs = L.system_specs(mode, toy_meta=tm, trap_standins=trap_standins_of(args) or None)
    keep = [s.strip() for s in args.systems.split(",") if s.strip()] if args.systems else sample_systems(specs, args.sample)
    if keep is not None:
        missing = sorted(set(trap_standins_of(args)) - set(keep))
        if missing:
            raise SystemExit(f"trap stand-ins not among the run's systems: {missing}")
        specs = {s: v for s, v in specs.items() if s in set(keep)}
    build_jobs = {s: j for s, j in build_jobs.items() if s in specs}
    return specs, build_jobs, tm


def run_classes(args) -> list[str]:
    return list(UNPACKED_CAPS) if getattr(args, "unpacked", False) else list(DRY_CLASSES)


def caps_for(args) -> dict:
    from brainir_causal.p4modal.app import CLASSES
    if getattr(args, "unpacked", False):
        caps = dict(UNPACKED_CAPS)
        if args.caps:
            caps.update({k: int(v) for k, v in json.loads(args.caps).items()})
        return caps
    caps = {c: int(args.max_containers) * int(CLASSES[c].get("slots") or 1) for c in DRY_CLASSES if c in CLASSES}
    if args.caps:
        caps.update({k: int(v) for k, v in json.loads(args.caps).items()})
    return caps


# ================================================================================================================ commands
def cmd_plan(args) -> int:
    """Print the job graph of a run (counts per stage and class, expected slot-hours, the list-schedule makespan with the default
    durations). No Modal call; with --official the lock must verify."""
    mode = mode_of(args)
    if mode.name == "official":
        guard = L.official_guard()
        specs = L.system_specs(mode)
        build_jobs = {s: {} for s in specs}
        method = json.loads(L.METHOD_LOCK.read_text(encoding="utf-8"))["method"]
        fixed = json.loads(L.LEVEL_B_FIXED.read_text(encoding="utf-8"))
        baselines = sorted({fixed["strongest_baseline"], L.FROZEN_V1} | {c.split(":", 1)[1] for k in ("full_state_bound", "id_comparator")
                                                                        for c in _choices(fixed, k) if c.startswith("baseline:")})
        described = {m: {"device": "cpu", "has_designer": True, "supported_sharing": ["auto", "independent", "shared", "partial"],
                         "supports_adaptation": True} for m in {method, *baselines}}
        limpo = method
        print(json.dumps({"guard": guard}, indent=1))
    else:
        specs, build_jobs, _ = dry_setup(args)
        method, limpo, baselines = L.STANDIN_METHOD, L.FROZEN_V1, [L.FROZEN_V1]
        described = {L.STANDIN_METHOD: {"device": "cpu", "has_designer": True, "supported_sharing": ["auto", "independent"],
                                        "supports_adaptation": False},
                     L.FROZEN_V1: {"device": "cpu", "has_designer": False, "supported_sharing": ["auto", "independent", "shared"],
                                   "supports_adaptation": True}}
        fixed = L.dry_fixed(L.FROZEN_V1, None, None)
    plan = build_the_plan(args, specs, method=method, limpo_method=limpo, baselines=baselines, fixed=fixed, described=described,
                          build_jobs=build_jobs)
    summary = plan_summary(plan)
    print(json.dumps(summary, indent=1))
    return 0


def _choices(fixed: dict, key: str) -> list[str]:
    v = fixed.get(key) or {}
    if isinstance(v, str):
        return [v]
    return [v.get("default")] + list((v.get("per_system") or {}).values())


def static_jobs(plan: L.Plan) -> dict:
    """plan.jobs plus the checkpoint jobs every loop will create (for counting and projection)."""
    from brainir_causal.loop import CHECKPOINTS, CHECKPOINTS_FULL
    jobs = dict(plan.jobs)
    for jid, j in plan.jobs.items():
        if j.stage != "loop":
            continue
        sp = plan.specs[j.sid]
        cps = CHECKPOINTS_FULL if (sp["kind"] == "real" and sp["cls"] == "full") else CHECKPOINTS
        for b in [c for c in cps if c <= int(j.meta["budget"])] or [int(j.meta["budget"])]:
            cid = f"ckpt__{L.safe(j.sid)}__{j.meta['designer']}__l{j.meta['loop_seed']}__b{b}"
            jobs[cid] = L.Job(cid, "ckpt", "iso", L.CLASS_OF["ckpt"], j.sid, [jid], expected_s=plan.expected("ckpt", sp))
    return jobs


def plan_summary(plan: L.Plan, durations: dict | None = None) -> dict:
    jobs = static_jobs(plan)
    by_stage: dict = {}
    for j in jobs.values():
        d = by_stage.setdefault(j.stage, {"n": 0, "expected_slot_h": 0.0, "class": j.cls})
        d["n"] += 1
        d["expected_slot_h"] += (durations or {}).get(j.id, j.expected_s) / 3600
    for d in by_stage.values():
        d["expected_slot_h"] = round(d["expected_slot_h"], 1)
    return {"run_id": plan.run_id, "mode": plan.mode.name, "n_systems": len(plan.specs), "n_jobs": len(jobs),
            "systems": {k: sum(1 for v in plan.specs.values() if v["cls"] == k) for k in ("syn", "toy", "mech", "full")},
            "groups": [g["id"] + f" ({g['kind']}: {', '.join(g['members'])})" for g in plan.groups], "by_stage": by_stage,
            "method": plan.method, "limpo_method": plan.limpo_method, "baselines": plan.baselines,
            "loops": {"designers": list(plan.designers), "loop_seeds": list(plan.loop_seeds), "budget": plan.budget},
            "time_limits": {"scale": plan.time_limit_scale, "factor": L.TIME_LIMIT_FACTOR, "floor_s": L.TIME_LIMIT_FLOOR_S}}


def cmd_prewarm(args) -> int:
    """Build every Modal image the run uses (no job; allowed before the lock)."""
    from brainir_causal.p4modal.app import Backend
    t0 = time.time()
    extra, _sha = L.stage_remote_module()
    with Backend(classes=DRY_CLASSES + list(UNPACKED_CAPS) + ["iso_pack_gpu_rtx6000"], extra_dirs=extra,
                 app_name="brainir-p4-levelc-prewarm") as be:
        print(f"images ready (app {be.app_id}) in {time.time() - t0:.0f} s")
    return 0


def combined_methods(rd: Path) -> Path:
    """<run dir>/methods_snapshot: the Level C stand-in package and P3's stand-in package side by side (one methods snapshot)."""
    import shutil
    dst = rd / "methods_snapshot"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(L.STANDIN_METHODS, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(L.P3_STANDIN_METHODS / "p3stand", dst / "p3stand", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def cmd_self_audit_config(args) -> int:
    """research/phase4/SELF_AUDIT_CONFIG.json BEFORE the lock (the lock hashes it): roles from LEVEL_B_FIXED.json and the final round's
    baseline names (--role name=baseline), the official Level C run id, the summary paths."""
    if L.METHOD_LOCK.exists():
        raise SystemExit("the method is already locked: SELF_AUDIT_CONFIG.json is written BEFORE the lock")
    fixed = json.loads(L.LEVEL_B_FIXED.read_text(encoding="utf-8"))
    roles = dict(x.split("=", 1) for x in args.role if "=" in x)
    unknown = sorted(set(roles) - set(L.SELF_AUDIT_ROLES))
    if unknown:
        raise SystemExit(f"unknown roles {unknown}; roles: {L.SELF_AUDIT_ROLES}")
    cfg = L.self_audit_config(method=args.method, fixed=fixed, roles=roles, run_id=args.run_id, designer=args.designer or None)
    out = Path(args.out) if args.out else L.SELF_AUDIT_CONFIG
    out.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(cfg, indent=1))
    return 0


def exit_client_died(e: BaseException, rd: Path, *, official_run_id: str | None = None) -> None:
    """The process's Modal client died (levelc_lib.CLIENT_DEAD_PATTERNS; the executor recorded the calls in flight in
    interruptions.jsonl): log it (official runs: an INTERRUPTED row of the hidden-evaluation log) and leave AT ONCE with
    EXIT_CLIENT_DIED, without stopping the app through the dead client (it would raise again or hang; Modal stops the ephemeral app
    when the client is gone). `--auto-resume` relaunches the run on this exit code."""
    msg = f"{type(e).__name__}: {e}"[:500]
    if official_run_id:
        L.log_hidden("INTERRUPTED", official_run_id, "Level C run: the driver's Modal client died (resumable; nothing is recomputed)",
                     {"error": msg, "run_dir": str(rd)})
    print(f"[levelc] exiting with {L.EXIT_CLIENT_DIED} (Modal client died): {msg}", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(L.EXIT_CLIENT_DIED)


def strip_supervisor_args(argv: list[str]) -> list[str]:
    """argv without the supervisor's own options (--auto-resume N, --resume-wait-s S; also their --opt=value forms)."""
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("--auto-resume", "--resume-wait-s"):
            skip = True
            continue
        if a.startswith(("--auto-resume=", "--resume-wait-s=")):
            continue
        out.append(a)
    return out


def supervise(argv: list[str], n: int, wait_s: float, *, call=subprocess.call, sleep=time.sleep) -> int:
    """Run `level_c.py <argv without the supervisor options>` in a child process and relaunch it, at most n times, when it exits with
    EXIT_CLIENT_DIED (its Modal client died: the same run id resumes, finished jobs are never recomputed). Any other exit code ends the
    supervision and is returned. This process holds no Modal client."""
    child = [sys.executable, str(Path(__file__).resolve()), *strip_supervisor_args(argv)]
    rc = 0
    for attempt in range(n + 1):
        rc = call(child)
        if rc != L.EXIT_CLIENT_DIED:
            return rc
        if attempt == n:
            print(f"[levelc supervise] the Modal client died again; the relaunch bound ({n}) is reached", flush=True)
            return rc
        print(f"[levelc supervise] the driver's Modal client died (exit {rc}); relaunch {attempt + 1} of {n} in {wait_s:.0f} s",
              flush=True)
        sleep(wait_s)
    return rc


def upload_toy_tier(be, tier: str) -> dict:
    base = SU.tier_dirs(tier, SU.SUITES)["base"]
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="p4lc_", dir=str(ROOT / "data" / "phase4")))
    try:
        (tmp / "truth").mkdir()
        shutil.copyfile(base / "internal_records.json", tmp / "internal_records.json")
        shutil.copyfile(base / "truth" / "systems_truth.json", tmp / "truth" / "systems_truth.json")
        # MERGE (replace=False): data/suites/<tier> also holds the systems' eval / truth parts, which replace=True would delete
        return be.upload_dir("eval", tmp, f"data/suites/{tier}", replace=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_run(args) -> int:
    from brainir_causal.p4modal.app import Backend
    mode = mode_of(args)
    if not args.max_containers:
        args.max_containers = 25 if mode.name == "official" else 7
    rd = run_dir(args)
    rd.mkdir(parents=True, exist_ok=True)
    store = L.RunStore(rd)
    t_start = time.time()
    if mode.name == "official":
        return run_official(args, rd, store)
    specs, build_jobs, _tm = dry_setup(args)
    method, limpo, baselines = L.STANDIN_METHOD, L.FROZEN_V1, [L.FROZEN_V1]
    mdir = L.STANDIN_METHODS
    if args.with_audit_roles:
        # the self-audit's comparator roles, played by P3's stand-ins (so the dry run shows their fits and evaluations are produced)
        mdir = combined_methods(rd)
        baselines += sorted(set(L.DRY_ROLE_BASELINES.values()))
    print(f"[levelc dry {args.run_id}] {len(specs)} systems: {sorted(specs)}", flush=True)
    extra, remote_sha = L.stage_remote_module()
    with Backend(classes=run_classes(args), max_containers=int(args.max_containers), extra_dirs=extra,
                 app_name="brainir-p4-levelc-dry", verbose=False) as be:
        print(f"[levelc dry {args.run_id}] app {be.app_id} ready after {time.time() - t_start:.0f} s", flush=True)
        key = be.methods_key(mdir)
        if build_jobs:
            print(f"[levelc dry {args.run_id}] toy tier files -> eval volume: {upload_toy_tier(be, mode.toy_tier)['n_files']} files", flush=True)
        described = describe(be, [method, *baselines], key, cls="iso_fit_s" if args.unpacked else "iso_pack_fit")
        print(f"[levelc dry {args.run_id}] described: {json.dumps(described)}", flush=True)
        fixed = L.dry_fixed(L.FROZEN_V1, None, None)
        plan = build_the_plan(args, specs, method=method, limpo_method=limpo, baselines=baselines, fixed=fixed, described=described,
                              build_jobs=build_jobs)
        plan.methods_key, plan.run_dir = key, rd
        (rd / "plan.json").write_text(json.dumps(plan_summary(plan), indent=1) + "\n", encoding="utf-8", newline="\n")
        (rd / "run.json").write_text(json.dumps({"run_id": args.run_id, "mode": "dry", "sample": args.sample, "systems": sorted(specs),
                                                 "method": method, "baselines": baselines, "limpo_method": limpo, "methods_key": key,
                                                 "described": described, "started_utc": L.now_utc(), "app_id": be.app_id,
                                                 "max_containers": int(args.max_containers), "caps": caps_for(args),
                                                 "unpacked": bool(args.unpacked), "levelc_remote_sha256": remote_sha,
                                                 "trap_standins": trap_standins_of(args)}, indent=1) + "\n",
                                     encoding="utf-8", newline="\n")
        plan.time_limit_scale = float(args.time_limit_scale or 1.0)
        ex = L.Executor(be, plan, store, caps=caps_for(args), dry=True, progress_s=float(args.progress_s),
                        time_limits=not args.no_time_limits, retry_timeouts=args.retry_timeouts)
        try:
            status = ex.run()
        except L.ClientDied as e:
            exit_client_died(e, rd)
    counts: dict = {}
    for s in status.values():
        counts[s] = counts.get(s, 0) + 1
    rec = {"run_id": args.run_id, "finished_utc": L.now_utc(), "wall_s": round(time.time() - t_start, 1), "status_counts": counts}
    (rd / "finished.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec, indent=1))
    return 0


def run_official(args, rd: Path, store: L.RunStore) -> int:
    """Stage A (the confirmation tier and the real Level C sets, generated from the salt after the lock) streamed into Stages B and C.
    Guarded; logged START / DONE; registered in the ledger (run once)."""
    import build_on_modal as BOM

    from brainir_causal.p4modal.app import Backend
    guard = L.official_guard()
    resumed = L.ledger_has(args.run_id, "levelc_run")          # the same run id again: a resume (infrastructure), never a new run
    L.ledger_claim(args.run_id, "levelc_run", new_run_reason=args.new_run_reason)
    lock = json.loads(L.METHOD_LOCK.read_text(encoding="utf-8"))
    fixed = json.loads(L.LEVEL_B_FIXED.read_text(encoding="utf-8"))
    method = lock["method"]
    if not L.SELF_AUDIT_CONFIG.exists():
        raise SystemExit("research/phase4/SELF_AUDIT_CONFIG.json (written before the lock: `level_c.py self-audit-config`) is missing")
    audit = json.loads(L.SELF_AUDIT_CONFIG.read_text(encoding="utf-8"))
    baselines = sorted({fixed["strongest_baseline"], L.FROZEN_V1} | {c.split(":", 1)[1] for k in ("full_state_bound", "id_comparator")
                                                                    for c in _choices(fixed, k) if c.startswith("baseline:")}
                       | set(L.role_baselines(audit)) | {b for b in (args.baselines or "").split(",") if b})
    L.log_hidden("RESUME" if resumed else "START", args.run_id,
                 "Level C run: Stage A (confirmation tier + review G's trap tier + real Level C sets) streamed into Stages B-C",
                 {"guard": guard, "method": method, "baselines": baselines, "fixed_sha256": L.sha256_file(L.LEVEL_B_FIXED)})
    t0 = time.time()
    # Stage A planning: the confirmation tier and review G's trap tier on the reference platform (salt read-only in the pinned image;
    # the trap planner also mounts the lock-hashed catalog), the real Level C sets here
    build_jobs: dict = {}
    # the plans are deterministic (salted streams, reference platform), so a resumed run re-plans and the executor skips finished builds
    for tier in ("conf", L.TRAP_TIER):
        jobs, plan_dir = BOM.plan_on_reference_platform(tier, "", 16)
        ints = json.loads((plan_dir / "internal_records.json").read_text(encoding="utf-8"))
        truths = json.loads((plan_dir / "systems_truth.json").read_text(encoding="utf-8"))
        base = SU.tier_dirs(tier, SU.SUITES)["base"]
        (base / "truth").mkdir(parents=True, exist_ok=True)
        (base / "internal_records.json").write_text(json.dumps(ints, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (base / "truth" / "systems_truth.json").write_text(json.dumps(truths, indent=1, sort_keys=True, default=str) + "\n",
                                                           encoding="utf-8", newline="\n")
        BOM.upload_small("eval", {"internal_records.json": base / "internal_records.json",
                                  "truth/systems_truth.json": base / "truth" / "systems_truth.json"}, f"data/suites/{tier}")
        clash = sorted(set(build_jobs) & {j["sid"] for j in jobs})
        if clash:
            raise SystemExit(f"system ids of the {tier} tier clash with another tier's: {clash}")
        build_jobs.update({j["sid"]: j for j in jobs})
    from brainir_causal.systems import load_real_internal
    for sid in sorted(load_real_internal()):
        build_jobs[sid] = SU.plan_remote_job("real", sid, level="C", workers=16)
    BOM.upload_small("eval", {"real_systems_internal.json": BOM.REAL_INTERNAL}, "data/real")
    specs = L.system_specs(L.Mode.official())
    classes = sorted(set(L.CLASS_OF.values()) | {"util", L.GPU_PACKED})
    # review G's catalog (hash checked against the lock by official_guard) baked root-only where synthadapter resolves it in a container
    extra, _remote_sha = L.stage_remote_module(trap_catalog=ROOT / L.TRAP_CATALOG_REL)
    lk = json.loads(L.METHOD_LOCK.read_text(encoding="utf-8"))
    locked = ((lk.get("inputs_sha256") or {}).get("scripts/p4/levelc_remote.py")
              or (lk.get("afterlock_drivers_sha256") or {}).get("scripts/p4/levelc_remote.py"))
    if locked and locked != L.sha256_file(ROOT / "scripts" / "p4" / "levelc_remote.py"):
        raise SystemExit("levelc_remote.py differs from the method lock's hash")
    with Backend(classes=classes, max_containers=int(args.max_containers), extra_dirs=extra, app_name="brainir-p4-levelc",
                 verbose=False) as be:
        key = be.methods_key(L.LOCKED_METHODS)
        described = describe(be, sorted({method, *baselines}), key)
        plan = L.Plan(run_id=args.run_id, mode=L.Mode.official(), specs=specs, method=method, limpo_method=method, baselines=baselines,
                      fixed=fixed, described=described, build_jobs=build_jobs)
        L.build_plan(plan)
        plan.methods_key, plan.run_dir = key, rd
        # the locked method's cost against the dry-run profile: LEVEL_B_FIXED.json "time_limit_scale" when the orchestrator fixed
        # it before the lock, else 3 (the projection's x3 scenario); --time-limit-scale overrides (recorded in plan.json)
        plan.time_limit_scale = float(args.time_limit_scale or fixed.get("time_limit_scale") or 3.0)
        (rd / "plan.json").write_text(json.dumps(plan_summary(plan), indent=1) + "\n", encoding="utf-8", newline="\n")
        ex = L.Executor(be, plan, store, caps=caps_for(args), dry=False, progress_s=float(args.progress_s),
                        time_limits=not args.no_time_limits, retry_timeouts=args.retry_timeouts)
        try:
            status = ex.run()
        except L.ClientDied as e:
            exit_client_died(e, rd, official_run_id=args.run_id)
    finalize_builds(plan, store)
    counts: dict = {}
    for s in status.values():
        counts[s] = counts.get(s, 0) + 1
    L.log_hidden("DONE", args.run_id, "Level C run: Stages A-C", {"wall_s": round(time.time() - t0, 1), "status_counts": counts,
                                                                    "run_dir": str(rd)})
    return 0


def finalize_builds(plan: L.Plan, store: L.RunStore) -> None:
    """Build manifests (research/phase4/build_manifests/syn_<tier>_<sid>.json for the conf and trap tiers, real_C_<sid>.json) and build
    records of Stage A."""
    import build_on_modal as BOM
    man_dir = ROOT / "research" / "phase4" / "build_manifests"
    man_dir.mkdir(parents=True, exist_ok=True)
    syn: dict = {}
    real = {}
    for sid in plan.build_jobs:
        r = store.get(f"build__{L.safe(sid)}")
        res = L.unwrap(r) if isinstance(r, dict) else None
        summ = BOM._summ({"result": res} if isinstance(res, dict) and "manifest" in res else (r if isinstance(r, dict) else {"error": str(r)}))
        sp = plan.specs.get(sid, {})
        is_real = sp.get("kind") == "real"
        tier = sp.get("tier") or plan.mode.syn_tier
        if is_real:
            real[sid] = summ
        else:
            syn.setdefault(tier, {})[sid] = summ
        if isinstance(res, dict) and "manifest" in res:
            name = f"real_C_{SU._safe(sid)}.json" if is_real else f"syn_{tier}_{SU._safe(sid)}.json"
            (man_dir / name).write_text(json.dumps(res.get("manifest") or {}, indent=0) + "\n", encoding="utf-8", newline="\n")
    for tier, systems in sorted(syn.items()):
        BOM._append_record(BOM.SYN_RECORD, {"what": f"synthetic tier {tier} (Level C run {plan.run_id})", "created_utc": L.now_utc(),
                                            "systems": systems})
    if real:
        BOM._append_record(BOM.REAL_RECORD, {"what": f"real level C (Level C run {plan.run_id})", "created_utc": L.now_utc(), "systems": real})


def load_plan(args) -> tuple[L.Plan, L.RunStore]:
    """Rebuild a run's plan from run.json and its results (no Modal call)."""
    rd = run_dir(args)
    store = L.RunStore(rd)
    run = json.loads((rd / "run.json").read_text(encoding="utf-8"))
    mode = mode_of(args)
    if mode.name == "official":
        L.official_guard()
        specs = L.system_specs(mode)
        fixed = json.loads(L.LEVEL_B_FIXED.read_text(encoding="utf-8"))
        build_jobs = {s: {} for s in specs}
    else:
        tm = None
        if mode.toy_tier:
            _p, ints, truths = toy_meta(mode.toy_tier)
            tm = (ints, truths)
        # the trap stand-ins of the run (run.json), or --trap-standins at claims time (a report variant: claims_traps/)
        traps = trap_standins_of(args) or list(run.get("trap_standins") or [])
        specs = {s: v for s, v in L.system_specs(mode, toy_meta=tm, trap_standins=traps or None).items() if s in set(run["systems"])}
        build_jobs = {s: {} for s, v in specs.items() if v["cls"] == "toy"}
        fixed = None
    args.sample = run.get("sample", args.sample)
    plan = L.Plan(run_id=args.run_id, mode=mode, specs=specs, method=run["method"], limpo_method=run["limpo_method"],
                  baselines=run["baselines"], fixed=fixed or {}, described=run["described"], build_jobs=build_jobs,
                  class_map=(dict(L.UNPACKED) if run.get("unpacked") else {}))
    if args.sample == "smoke":
        plan.loop_seeds, plan.budget = (0,), 25
    L.build_plan(plan)
    for jid, j in list(plan.jobs.items()):
        if j.stage == "loop":
            r = store.get(jid)
            if r is not None and not L.job_error(r):
                for nj in L.collect_resume(j, r, plan, store):
                    plan.jobs.setdefault(nj.id, nj)
    if fixed is None:
        plan.fixed = L.dry_fixed(L.FROZEN_V1, store, plan)
    return plan, store


def cmd_claims(args) -> int:
    plan, store = load_plan(args)
    official = plan.mode.name == "official"
    if official:
        L.ledger_claim(args.run_id, "levelc_claims", new_run_reason=args.new_run_reason)
        L.log_hidden("START", args.run_id, "Level C Stage D (claims)", {"run_dir": str(store.dir)})
    t0 = time.time()
    calp = Path(args.calibration) if args.calibration else None
    if official and calp is not None and calp.resolve() != (L.BENCH / "calibration.json").resolve():
        raise SystemExit("an official Stage D uses the benchmark's calibration.json (hashed by the benchmark lock), nothing else")
    bundle = L.stage_d(plan, store, tolerances_path=Path(args.tolerances) if args.tolerances else None, calibration_path=calp,
                       n_boot=int(args.n_boot), levelb_round=Path(args.levelb_round) if args.levelb_round else None)
    # dry-run report variants get their own directories: a claims-time trap stand-in set, a stand-in calibration record
    name = "claims" + ("_traps" if trap_standins_of(args) else "") + ("_calstandin" if calp is not None else "")
    out = (L.OUT_ROOT / args.run_id) if official else (store.dir / name)
    out.mkdir(parents=True, exist_ok=True)
    (out / "RESULTS.json").write_text(json.dumps(bundle, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    claims = {k: bundle[k] for k in ("run_id", "mode", "method", "tolerances", "tolerances_calibrated", "synthetic_capped_at_partial",
                                     "level_b_fixed", "conclusion", "real_by_lineage", "primary_family", "margins", "sensitivity",
                                     "charged")}
    claims["categories"] = {s: L.category_of(v) for s, v in bundle["per_system"].items()}
    (out / "CLAIMS.json").write_text(json.dumps(claims, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    for name, key in (("LOOPS_SUMMARY.json", "loops_summary"), ("SHARING_SUMMARY.json", "sharing")):      # self-audit Q10 / Q18 inputs
        (out / name).write_text(json.dumps((bundle.get("self_audit_inputs") or {}).get(key), indent=1, default=str) + "\n",
                                encoding="utf-8", newline="\n")
    (out / "TRAPS.json").write_text(json.dumps(bundle.get("trap_evaluation"), indent=1, default=str) + "\n", encoding="utf-8",
                                    newline="\n")                   # review G's trap tier (criterion 33; descriptive)
    if official:
        L.log_hidden("DONE", args.run_id, "Level C Stage D (claims)", {"out": str(out.relative_to(ROOT)), "wall_s": round(time.time() - t0, 1),
                                                                       "phase4": (bundle.get("conclusion") or {}).get("phase4")})
    print(json.dumps({"out": str(out), "phase4": (bundle.get("conclusion") or {}).get("phase4"), "categories": claims["categories"],
                      "traps": ((bundle.get("trap_evaluation") or {}).get("summary") or {}).get("counts"),
                      "stage_d_wall_s": bundle.get("stage_d_wall_s")}, indent=1, default=str))
    return 0


def cmd_diag_stability(args) -> int:
    """DRY-RUN DIAGNOSTIC of the 5.11 stability job (bounded): for each system (default the two real mechanism systems of dry run S3),
    one iso "call" `levelc_remote.stability_diag` on the dry run's own stored models (restart cost, shared-uid kills, the digest-rule
    replay, and the fixed orchestration instrumented per model / per call / per pair). Bounded twice: the container stops at
    --deadline-s, and this client leaves at --wall-s whatever happens. Writes <dry run>/STABILITY_DIAG.json."""
    import threading

    from brainir_causal.p4modal.app import Backend
    if args.official:
        raise SystemExit("diag-stability is a dry-run diagnostic")
    plan, store = load_plan(args)
    run = json.loads((store.dir / "run.json").read_text(encoding="utf-8"))
    sids = [s.strip() for s in (args.systems or "real:A:m1,real:C:m2").split(",") if s.strip()]
    t0 = time.time()
    extra, remote_sha = L.stage_remote_module()
    cls = "iso_eval_l" if args.unpacked else "iso_pack_eval"
    rec: dict = {"utc": L.now_utc(), "run_id": args.run_id, "systems": sids, "class": cls, "levelc_remote_sha256": remote_sha,
                 "deadline_s": args.deadline_s, "wall_s_limit": args.wall_s, "call_timeout_s": args.call_timeout_s}
    out_path = store.dir / "STABILITY_DIAG.json"

    def write(extra_fields: dict) -> None:
        out_path.write_text(json.dumps({**rec, **extra_fields}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")

    with Backend(classes=[cls], max_containers=len(sids), extra_dirs=extra, app_name="brainir-p4-levelc-diag", verbose=False) as be:
        rec["app_id"] = be.app_id
        store.be = be
        key = be.methods_key(L.STANDIN_METHODS if not (store.dir / "methods_snapshot").exists() else store.dir / "methods_snapshot")
        if run.get("methods_key") and key != run["methods_key"]:
            raise SystemExit(f"the methods snapshot {key} differs from the run's {run['methods_key']}")
        plan.methods_key = key
        payloads = []
        for sid in sids:
            j = plan.jobs[f"stability__{L.safe(sid)}"]
            p = L.payload_for(j, plan, store)
            if p is None:
                raise SystemExit(f"{sid}: the run holds fewer than 2 of its stability models")
            p = dict(p, target=f"{L.REMOTE_MODULE}:stability_diag")
            p["job"] = dict(p["job"], deadline_s=float(args.deadline_s), n_restart_probes=5, call_timeout_s=float(args.call_timeout_s))
            L.assert_dry_payloads([p])
            payloads.append(p)
        print(f"[diag] app {be.app_id}: {len(payloads)} stability_diag calls on {cls} ({time.time() - t0:.0f} s)", flush=True)
        box: dict = {}

        def work() -> None:
            try:
                box["res"] = (be.run_iso(payloads, cls, label="diag-stability") if args.unpacked
                              else be.run_iso_packed(payloads, cls, label="diag-stability"))
            except BaseException as e:  # noqa: BLE001 - reported
                box["err"] = f"{type(e).__name__}: {e}"
        th = threading.Thread(target=work, daemon=True)
        th.start()
        th.join(max(60.0, float(args.wall_s) - (time.time() - t0)))
        if th.is_alive():
            write({"error": f"the client wall ({args.wall_s} s) was reached; the calls were abandoned", "wall_s": round(time.time() - t0, 1)})
            print(f"[diag] wall reached; partial record {out_path}", flush=True)
            sys.stdout.flush()
            os._exit(3)
    res = box.get("res") or []
    out = {sid: (L.unwrap(r) if isinstance(r, dict) else {"error": repr(r)[:2000]}) for sid, r in zip(sids, res)}
    write({"results": out, "error": box.get("err"), "wall_s": round(time.time() - t0, 1)})
    for sid, r in out.items():
        if not isinstance(r, dict) or "restart" not in r:
            print(f"[diag] {sid}: {str(r)[:1500]}", flush=True)
            continue
        print(json.dumps({"sid": sid, "restart": r.get("restart", {}).get("restart_s_mean"), "kill": r.get("kill", {}).get("shared_uid_kills_idle_worker"),
                          "digest_replay": r.get("digest_replay"), "models_completed": r.get("models_completed"),
                          "per_model_wall": {m: v.get("wall_s") for m, v in (r.get("per_model") or {}).items()},
                          "projection_all_models_s": r.get("projection_all_models_s"), "wall_s": r.get("wall_s")}, default=str), flush=True)
    return 0 if not box.get("err") else 1


def cmd_trap_probe(args) -> int:
    """DRY check (before the lock) of the trap tier's container path: a Level C iso image with the DUMMY catalog baked where official
    runs bake review G's (levelc_lib.TRAP_CATALOG_CONTAINER); one iso "call" (`levelc_remote.trap_probe`) reports the catalog as
    synthadapter resolves it (sha256 = the dummy's, root-only, unreadable by a worker uid) and the systems it builds for a PUBLIC seed.
    Never review G's catalog, never a salted seed."""
    import hashlib

    from brainir_causal.p4modal.app import Backend
    if args.catalog and Path(args.catalog).resolve() == (ROOT / L.TRAP_CATALOG_REL).resolve():
        raise SystemExit("trap-probe runs the DUMMY catalog only (review G's catalog enters official runs, after the lock)")
    catalog = Path(args.catalog) if args.catalog else L.DUMMY_TRAP_CATALOG
    t0 = time.time()
    extra, remote_sha = L.stage_remote_module(trap_catalog=catalog)
    cls = "iso_eval_l" if args.unpacked else "iso_pack_eval"
    payload = {"role": "call", "target": f"{L.REMOTE_MODULE}:trap_probe", "models": {}, "reload": [],
               "job": {"generator": [SU.GENERATOR_CONTAINER, "p4synth"], "seed": int(args.seed), "worker_uid": 10001}}
    with Backend(classes=[cls], max_containers=1, extra_dirs=extra, app_name="brainir-p4-levelc-trapprobe", verbose=False) as be:
        res = (be.run_iso([payload], cls, label="trap-probe") if args.unpacked
               else be.run_iso_packed([payload], cls, label="trap-probe"))[0]
        app_id = be.app_id
    out = L.unwrap(res) if isinstance(res, dict) else {"error": repr(res)[:2000]}
    want = hashlib.sha256(catalog.read_bytes()).hexdigest()          # the bytes as baked (the probe hashes the file it finds)
    checks = {"catalog_is_the_baked_file": isinstance(out, dict) and out.get("catalog_sha256") == want,
              "catalog_path_is_the_official_container_path": isinstance(out, dict) and out.get("catalog_path") ==
              f"{L.TRAP_CATALOG_CONTAINER}/{Path(L.TRAP_CATALOG_REL).name}",
              "root_only": isinstance(out, dict) and out.get("root_only") is True,
              "worker_read_denied": isinstance(out, dict) and out.get("worker_read_denied") is True,
              "systems_built": isinstance(out, dict) and int(out.get("n_systems") or 0) > 0,
              "single_threaded_wrappers": isinstance(out, dict) and all(v.get("single_threaded") for v in (out.get("systems") or {}).values())}
    rec = {"utc": L.now_utc(), "app_id": app_id, "class": cls, "catalog": str(catalog.relative_to(ROOT)) if catalog.is_relative_to(ROOT)
           else str(catalog), "seed": int(args.seed), "levelc_remote_sha256": remote_sha, "wall_s": round(time.time() - t0, 1),
           "checks": checks, "all_ok": all(checks.values()), "probe": out,
           "iso_result": {k: v for k, v in res.items() if k not in ("result",)} if isinstance(res, dict) else None}
    DRY_ROOT.mkdir(parents=True, exist_ok=True)
    (DRY_ROOT / "TRAP_PROBE.json").write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("app_id", "class", "catalog", "wall_s", "checks", "all_ok")}, indent=1))
    return 0 if rec["all_ok"] else 1


def stage_report(rows: list[dict]) -> dict:
    """Per stage: counts by status, job wall seconds (mean / median / p95 / max), container seconds and approximate cost."""
    by: dict = {}
    for r in rows:
        d = by.setdefault(r["stage"], {"n": 0, "status": {}, "wall": [], "container_s": 0.0, "usd": 0.0, "errors": []})
        d["n"] += 1
        d["status"][r["status"]] = d["status"].get(r["status"], 0) + 1
        if r.get("wall_s") is not None and r["status"] == "ok":
            d["wall"].append(float(r["wall_s"]))
        d["container_s"] += float(r.get("container_wall_s") or 0.0)
        d["usd"] += float(r.get("usd_approx") or 0.0)
        if r["status"] != "ok" and len(d["errors"]) < 3:
            d["errors"].append(f"{r['id']}: {str(r.get('error'))[:300]}")
    out = {}
    for st, d in sorted(by.items()):
        w = sorted(d["wall"])
        out[st] = {"n": d["n"], "status": d["status"], "wall_mean_s": round(statistics.mean(w), 1) if w else None,
                   "wall_median_s": round(statistics.median(w), 1) if w else None,
                   "wall_p95_s": round(w[min(len(w) - 1, int(0.95 * len(w)))], 1) if w else None, "wall_max_s": round(w[-1], 1) if w else None,
                   "container_h": round(d["container_s"] / 3600, 2), "usd_approx": round(d["usd"], 2), "first_errors": d["errors"]}
    return out


def cmd_report(args) -> int:
    rd = run_dir(args)
    store = L.RunStore(rd)
    rows = store.rows()
    rep = {"run_id": args.run_id, "stages": stage_report(rows), "n_rows": len(rows),
           "usd_approx_total": round(sum(float(r.get("usd_approx") or 0.0) for r in rows), 2)}
    fin = rd / "finished.json"
    if fin.exists():
        rep["finished"] = json.loads(fin.read_text(encoding="utf-8"))
    (rd / "REPORT.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rep, indent=1))
    return 0


def cmd_project(args) -> int:
    """Projected wall time of a FULL job list from a finished run's measured job wall times (per stage and system class; the median
    and, for the pessimistic line, the p95), as a longest-first list schedule over the packed classes' slots:
    - capacities: the 100-container workspace split over the packed classes (fit 15, eval 45, loop 35, trusted 5; x their slots), and
      the same with HALF the workspace (the post-lock ablation / counterexample drivers run concurrently: CRITICAL_PATH_PLAN L3-L7);
    - Stage A: every build job takes --build-s (default: the val tier's measured build wall, 1,728 s) and, with packed classes, every
      later job waits for every build (P1's freshness rule);
    - SCENARIOS for the locked method's unknown costs: its fits (every fit stage) and loops scaled by x1, x3, x10 of the stand-in's;
      evaluations keep their measured times (the harness dominates them)."""
    plan_src, store = load_plan(args)
    every = L.system_specs(L.Mode.dry(toy=True), toy_meta=toy_meta("toyC")[1:])      # class of every dry-run system (all runs' rows)
    meas: dict = {}
    rows = list(store.rows())
    for other in [x for x in (args.also_runs or "").split(",") if x]:           # measured rows of other dry runs (e.g. the dev systems)
        rows += L.RunStore((L.RUN_ROOT if args.official else DRY_ROOT) / other).rows()
    for r in rows:
        if r.get("status") == "ok" and r.get("wall_s") is not None and r.get("sid") in every and r.get("error") is None:
            meas.setdefault((r["stage"], every[r["sid"]]["cls"]), []).append(float(r["wall_s"]))
            meas.setdefault((r["stage"], "*"), []).append(float(r["wall_s"]))
    if args.target == "official":
        specs = synthetic_official_specs(plan_src, n_traps=int(args.n_traps))
    else:
        a2 = argparse.Namespace(**{**vars(args), "sample": "full", "systems": ""})
        specs, _bj, _ = dry_setup(a2)
    fake = L.Plan(run_id="projection", mode=plan_src.mode, specs=specs, method=plan_src.method, limpo_method=plan_src.limpo_method,
                  baselines=plan_src.baselines, fixed=plan_src.fixed, described=plan_src.described,
                  build_jobs={s: {} for s, v in specs.items() if args.target == "official" or v["cls"] == "toy"})
    L.build_plan(fake)
    jobs = static_jobs(fake)
    src_budget = {c: measured_loop_budget(plan_src, c) for c in ("syn", "mech", "full", "toy")}
    method_stages = set(L.FIT_STAGES) | {"loop"}
    caps_full = {"iso_pack_fit": 15 * 8, "iso_pack_eval": 45 * 8, "iso_pack_loop": 35 * 8, "pack_xl": 5 * 8, "build": 100, L.GPU_PACKED: 4 * 4}
    caps_half = {k: max(1, v // 2) for k, v in caps_full.items()}
    cls_of = {jid: j.cls for jid, j in jobs.items()}
    deps = {jid: list(j.deps) + list(j.soft) for jid, j in jobs.items()}
    from brainir_causal.p4modal.app import CLASSES, usd_per_s
    out = {"source_run": args.run_id, "target": args.target, "n_jobs": len(jobs), "n_systems": len(specs),
           "jobs_by_stage": {st: sum(1 for j in jobs.values() if j.stage == st) for st in sorted({j.stage for j in jobs.values()})},
           "capacity_slots_100": caps_full, "build_s": float(args.build_s), "scenarios": {}}
    for q, label in ((0.5, "median"), (0.95, "p95")):
        base = {}
        for jid, j in jobs.items():
            cls = specs[j.sid]["cls"] if j.sid in specs else "syn"
            if j.stage == "build":
                base[jid] = float(args.build_s)
                continue
            vals = meas.get((j.stage, cls)) or meas.get((j.stage, "*"))
            if vals:
                v = sorted(vals)
                base[jid] = v[min(len(v) - 1, int(q * len(v)))]
                if j.stage == "loop":
                    base[jid] *= int(j.meta.get("budget", L.BUDGET)) / max(1, src_budget.get(cls) or plan_src.budget)
            else:
                base[jid] = j.expected_s
        for scale in (1, 3, 10):
            dur = {jid: d * (scale if jobs[jid].stage in method_stages else 1) for jid, d in base.items()}
            slot_s = sum(dur.values())
            usd = sum(d * usd_per_s(cls_of[jid]) / max(1, int(CLASSES[cls_of[jid]].get("slots") or 1)) for jid, d in dur.items())
            full, half = L.simulate_makespan(dur, deps, caps_full, cls_of), L.simulate_makespan(dur, deps, caps_half, cls_of)
            if full["unscheduled"] or half["unscheduled"]:
                raise SystemExit(f"projection: {full['unscheduled']} / {half['unscheduled']} jobs never scheduled (a class without slots)")
            out["scenarios"][f"{label}_x{scale}"] = {
                "makespan_100_containers_h": round(full["makespan_s"] / 3600, 2),
                "makespan_50_containers_h": round(half["makespan_s"] / 3600, 2),
                "slot_hours": round(slot_s / 3600, 1), "usd_approx": round(usd, 0),
                "slot_hours_by_stage": {st: round(sum(d for jid, d in dur.items() if jobs[jid].stage == st) / 3600, 1)
                                        for st in sorted({j.stage for j in jobs.values()})}}
    out["measured"] = {f"{k[0]}|{k[1]}": {"n": len(v), "median_s": round(statistics.median(v), 1), "max_s": round(max(v), 1)}
                       for k, v in sorted(meas.items())}
    out["source_loop_budgets"] = src_budget
    out["note"] = ("durations: the dry run's stand-in jobs (the stand-in method refits at the checkpoint budgets only; the frozen v1 as "
                   "baseline and 5.14 method); the locked method's fit / loop costs come from Level B (scenarios x3, x10)")
    (store.dir / f"PROJECTION_{args.target}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in out.items() if k != "measured"}, indent=1))
    return 0


def measured_loop_budget(plan: L.Plan, cls: str) -> int:
    """The loop budget the source run used for systems of class `cls`."""
    return min(plan.budget, L.BUDGET_FULL) if cls == "full" else plan.budget


def measured_budget(plan: L.Plan, job: L.Job) -> int:
    sp = plan.specs.get(job.sid) or {}
    return L.budget_of(sp, plan) if sp else plan.budget


def synthetic_official_specs(plan_src: L.Plan, n_traps: int = 16) -> dict:
    """A stand-in of the official system set for the projection (no hidden data): 75 confirmation systems modelled on the dev tier's
    systems (3 per type, groups of 3), n_traps trap systems (review G's contract: 12-20; clones of the dev tier's trap-type systems,
    set "trap": the verdict stages only) and the 10 real systems."""
    specs = {}
    dev = L.system_specs(L.Mode.dry(toy=False))
    by_type: dict = {}
    for sid, v in sorted(dev.items()):
        if v["kind"] == "real":
            specs[sid] = v
        else:
            by_type.setdefault(v.get("type"), []).append(sid)
    for _t, sids in sorted(by_type.items(), key=lambda kv: str(kv[0])):
        clones = [(sids[0], 0), (sids[-1], 0), (sids[0], 1)]            # 3 per type (conf); a group keeps all three members
        for src, j in clones:
            v = dev[src]
            nid = f"{src}~c{j}"
            specs[nid] = {**v, "sid": nid, "unrelated": [f"{u}~c0" for u in v.get("unrelated") or []]}
    pool = sorted(s for s, v in dev.items() if v["kind"] == "synthetic" and (v.get("trap") or str(v.get("k_true")) == "none"))
    for i in range(int(n_traps) if pool else 0):
        src = pool[i % len(pool)]
        nid = f"{src}~g{i}"
        specs[nid] = {**dev[src], "sid": nid, "set": "trap", "group": None, "group_members": [], "unrelated": []}
    return specs


def cmd_fixed(args) -> int:
    fixed = L.fixed_from_levelb(Path(args.round_dir) if args.round_dir else ROOT / "research" / "phase4" / "tournament" / args.round,
                                strongest=args.strongest or None)
    if L.METHOD_LOCK.exists():
        raise SystemExit("the method is already locked: LEVEL_B_FIXED.json is written BEFORE the lock (and hashed by it)")
    L.LEVEL_B_FIXED.write_text(json.dumps(fixed, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(fixed, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, run_id: bool = True):
        p.add_argument("--official", action="store_true")
        p.add_argument("--dry-run-dev", action="store_true")
        p.add_argument("--no-toy", action="store_true")
        p.add_argument("--sample", choices=("smoke", "ten", "full"), default="full")
        p.add_argument("--systems", default="")
        p.add_argument("--loop-seeds", default="")
        p.add_argument("--budget", type=int, default=0)
        p.add_argument("--designers", default="")
        p.add_argument("--no-loops", action="store_true", help="no experiment loops in this invocation (a later one adds them)")
        p.add_argument("--trap-standins", default="", help="DRY RUN: dev systems (comma list) run as the trap set (the verdict "
                                                           "stages only; Stage D's trap section); claims: a report variant (claims_traps/)")
        if run_id:
            p.add_argument("--run-id", required=True)
    p = sub.add_parser("plan")
    common(p, run_id=False)
    p.add_argument("--run-id", default="plan")
    r = sub.add_parser("run")
    common(r)
    r.add_argument("--max-containers", type=int, default=0,
                   help="containers per class (default: 7 for a dry run, 25 for an official run = the whole workspace)")
    r.add_argument("--caps", default="")
    r.add_argument("--progress-s", type=float, default=120.0)
    r.add_argument("--baselines", default="")
    r.add_argument("--new-run-reason", default=None)
    r.add_argument("--resume", action="store_true")
    r.add_argument("--with-audit-roles", action="store_true", help="dry run: the self-audit comparator roles as stand-in baselines")
    r.add_argument("--auto-resume", type=int, default=0, help="relaunch the run (same run id) at most N times when its Modal client "
                                                              "dies (exit 75); a supervisor process without a Modal client")
    r.add_argument("--resume-wait-s", type=float, default=120.0, help="pause before a relaunch (socket buffers recover)")
    r.add_argument("--time-limit-scale", type=float, default=0.0,
                   help="scale of the per-job time limits (levelc_lib.time_limit_s); default 1 (dry) or LEVEL_B_FIXED's / 3 (official)")
    r.add_argument("--no-time-limits", action="store_true", help="no per-job time limits (never for an official run's record)")
    r.add_argument("--retry-timeouts", action="store_true", help="a resume also re-runs jobs whose two attempts hit the time limit")
    r.add_argument("--unpacked", action="store_true",
                   help="every job kind on its unpacked iso class (one job per container). SMALL MODELS ONLY: a block_network container "
                        "cannot move a function input or output above 2 MiB (model bytes, checkpoint files, evaluation results); the "
                        "packed classes (the default) keep the driver's network and run each worker in its own no-network namespace")
    c = sub.add_parser("claims")
    common(c)
    c.add_argument("--tolerances", default=None)
    c.add_argument("--n-boot", type=int, default=2000)
    c.add_argument("--new-run-reason", default=None)
    c.add_argument("--levelb-round", default=None, help="the FINAL Level B round directory (the Level B -> Level C drop)")
    c.add_argument("--calibration", default=None, help="the calibration record (default: the benchmark's calibration.json); a DRY "
                                                       "run may give a stand-in record to exercise the sensitivity table")
    rp = sub.add_parser("report")
    common(rp)
    pj = sub.add_parser("project")
    common(pj)
    pj.add_argument("--target", choices=("official", "dry-full"), default="official")
    pj.add_argument("--build-s", type=float, default=1728.0, help="Stage A build job wall (s); default: the val tier build")
    pj.add_argument("--also-runs", default="", help="other dry runs whose measured job times are pooled (comma list)")
    pj.add_argument("--n-traps", type=int, default=16, help="stand-in trap systems of the official projection (review G: 12-20)")
    sub.add_parser("prewarm")
    dg = sub.add_parser("diag-stability")
    common(dg)
    dg.add_argument("--deadline-s", type=float, default=2100.0, help="the container-side deadline of each diagnostic call")
    dg.add_argument("--wall-s", type=float, default=2700.0, help="this client's hard wall (it leaves, whatever happens)")
    dg.add_argument("--call-timeout-s", type=float, default=300.0, help="per model call (a hung call surfaces as a worker timeout)")
    dg.add_argument("--unpacked", action="store_true")
    tp = sub.add_parser("trap-probe")
    tp.add_argument("--seed", type=int, default=7, help="a PUBLIC seed for the dummy catalog's systems")
    tp.add_argument("--catalog", default="", help="a dummy catalog file named review_g.py (default: levelc_lib.DUMMY_TRAP_CATALOG)")
    tp.add_argument("--unpacked", action="store_true", help="the unpacked iso class (iso_eval_l) instead of iso_pack_eval")
    sa = sub.add_parser("self-audit-config")
    sa.add_argument("--method", required=True, help="the locked method's name")
    sa.add_argument("--run-id", default="C1", help="the OFFICIAL Level C run id the self-audit will read")
    sa.add_argument("--role", action="append", default=[], help="role=baseline name (id_baseline, input_only, readout_history, linear_controlled)")
    sa.add_argument("--designer", default="")
    sa.add_argument("--out", default="")
    f = sub.add_parser("fixed-from-levelb")
    f.add_argument("--round", default="")
    f.add_argument("--round-dir", default="")
    f.add_argument("--strongest", default="")
    argv = list(sys.argv[1:] if argv is None else argv)
    args = ap.parse_args(argv)
    if args.cmd == "run" and int(args.auto_resume) > 0:
        return supervise(argv, int(args.auto_resume), float(args.resume_wait_s))
    return {"plan": cmd_plan, "run": cmd_run, "claims": cmd_claims, "report": cmd_report, "project": cmd_project, "prewarm": cmd_prewarm,
            "fixed-from-levelb": cmd_fixed, "self-audit-config": cmd_self_audit_config, "trap-probe": cmd_trap_probe,
            "diag-stability": cmd_diag_stability}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
