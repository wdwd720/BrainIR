"""causal_state_v1 Level B tournament driver (ORCHESTRATOR SIDE; benchmarks/causal_state_v1/PROTOCOL.md section 10).

    uv run --no-sync --project phase4 python scripts/p4/tournament.py run --round r1 --stage pilot --methods m1,m2 [--baselines b1]
        [--room C:/Dev/BrainIR_p4clean] [--backend local] [--parallel 4] [--eval-workers 4] [--seeds 0] [--systems s1,s2]
        [--loops --designers own,random,fixed --loop-seeds 0,1,2 --budget 200] [--no-lift] [--timeout 3600] [--tier val]
    uv run --no-sync --project phase4 python scripts/p4/tournament.py decide --round r1 [--finalists 3] [--carried BASELINE]
    uv run --no-sync --project phase4 python scripts/p4/tournament.py feedback --rounds r1,r2 --out <file.md>
    uv run --no-sync --project phase4 python scripts/p4/tournament.py simserver --round r1 --tier val [--budget 100000]

run:
1. snapshots the room's methods package (<room>/src/brainir_causal/methods) into C:/Dev/BrainIR_p4run/<round>/methods with sha256
   hashes (the orchestrator never imports the room directly);
2. systems of the stage: 'pilot' = public/pilot_subset.json (synthetic ids resolved from hidden/pilot_subset_resolved.json + the real
   mechanisms); 'medium' = every validation system + every real mechanism; 'finalists' / 'full' = every validation and real system;
3. fits every method on every system and seed in the sandbox (`brainir_causal.runner fit`, FIT guard; the main-comparison data D0 +
   D1 of PROTOCOL 4);
4. evaluates every model in guarded worker processes (`harness.evaluate_job`: every metric family, the cached references, the
   verdict with the calibrated tolerances (provisional ones before the calibration exists, flagged), the selection values);
5. optionally (finalists / full) runs the experiment loops of PROTOCOL 5.17 through a round simulation service and evaluates the
   checkpoints (EE, SMS, dimension truth, lift);
6. writes research/phase4/tournament/<round>/ (ANSWER-BEARING for held-out data: never into a room): per method <method>.json
   (per-system public views, verdicts, selection values) and the round report; appends a row to research/phase4/LEVELB_LOG.md.
decide: eligibility and ranking (`select.rank`), the halving decision (`select.halve`) and the developer-facing aggregate.
simserver: the round's simulation service for experiment loops (validation and real systems; the synthetic generator registered in
every worker).

Backends: 'local' (process pools; the development machine). Modal runs go through `brainir_causal.p4modal.app.Backend`
(`run_methods` with target brainir_causal.runner:fit_job / brainir_causal.harness:evaluate_job; payloads built by `modal_payloads`);
the data must first be staged on the fit (public) and eval (held-out) volumes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import feedback as FB  # noqa: E402
from brainir_causal import select as SEL  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402

ROOM = Path("C:/Dev/BrainIR_p4clean")
RUN = Path("C:/Dev/BrainIR_p4run")
OUT = ROOT / "research" / "phase4" / "tournament"
BENCH = ROOT / "benchmarks" / "causal_state_v1"
LOG = ROOT / "research" / "phase4" / "LEVELB_LOG.md"
GENERATOR = BENCH / "generator"
GENERATOR_PKG = "p4synth"


# ================================================================================================================ helpers
def snapshot_methods(round_dir: Path, room: Path) -> tuple[Path, dict]:
    src = room / "src" / "brainir_causal" / "methods"
    dst = round_dir / "methods"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    hashes = {p.relative_to(dst).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dst.rglob("*.py"))}
    return dst, hashes


def stage_systems(stage: str, tier: str, systems: list[str] | None, *, suites_root: Path = SU.SUITES,
                  real_root: Path = SU.REAL_SETS, include_real: bool = True) -> dict[str, dict]:
    """{system id: {"kind", "heldout_root", "heldout_tier", "public_root", "public_tier", "internal_path"}} of a stage."""
    syn_dirs = SU.tier_dirs(tier, suites_root)
    syn_int = syn_dirs["base"] / "internal_records.json"
    syn_ids = sorted(json.loads(syn_int.read_text(encoding="utf-8"))) if syn_int.exists() else []
    real_int = BENCH / "hidden" / "real_systems_internal.json"
    real_ids = sorted(json.loads(real_int.read_text(encoding="utf-8"))) if (include_real and real_int.exists()) else []
    if stage == "pilot":
        pil = json.loads((BENCH / "public" / "pilot_subset.json").read_text(encoding="utf-8"))
        syn_sel = pil.get("synthetic") or []
        real_sel = pil.get("real") or []
    elif stage == "medium":
        syn_sel, real_sel = syn_ids, [s for s in real_ids if ":m" in s]
    else:
        syn_sel, real_sel = syn_ids, real_ids
    out = {}
    for s in syn_sel:
        out[s] = {"kind": "synthetic", "heldout_root": str(suites_root), "heldout_tier": tier, "public_root": str(suites_root),
                  "public_tier": tier, "internal_path": str(syn_int)}
    for s in real_sel:
        out[s] = {"kind": "real", "heldout_root": str(real_root), "heldout_tier": SU.REAL_TIERS["B"], "public_root": str(real_root),
                  "public_tier": SU.REAL_TIERS["public"], "internal_path": str(real_int)}
    if systems:
        out = {s: v for s, v in out.items() if s in set(systems)}
    return out


def _fit_cmd(mdir: Path, method: str, sysd: dict, sid: str, out: Path, seed: int, config: dict | None = None) -> list[str]:
    data = str(Path(sysd["public_root"]) / sysd["public_tier"] / "public" / SU._safe(sid))
    cmd = [sys.executable, "-m", "brainir_causal.runner", "fit", "--method-dir", str(mdir), "--method", method, "--data", data,
           "--systems", sid, "--out", str(out), "--seed", str(seed)]
    if config:
        cmd += ["--config", json.dumps(config)]
    return cmd


def run_fit(cmd: list[str], out: Path, timeout: float) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", P4_FIT_THREADS=os.environ.get("P4_FIT_THREADS", "3"))
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(ROOT))
        ok = p.returncode == 0 and out.exists()
        rec = {"ok": ok, "wall_s": round(time.time() - t0, 1), "returncode": p.returncode}
        if not ok:
            rec["error"] = (p.stderr or p.stdout)[-3000:]
    except subprocess.TimeoutExpired:
        rec = {"ok": False, "wall_s": round(time.time() - t0, 1), "error": f"timeout after {timeout} s"}
    (out.parent / (out.stem + ".fitlog.json")).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    return rec


_EVAL_READY = {}


def _eval_init(method_dir: str) -> None:
    """Worker initialiser: thread limits and the EVAL guard (method frames may read only the method snapshot)."""
    try:
        import threadpoolctl
        threadpoolctl.threadpool_limits(2)
    except Exception:  # noqa: BLE001, S110
        pass
    from brainir_causal.runguard import install_eval_guard, preimport
    preimport(method_dir)            # the stack loads shared objects through ctypes, which the guard refuses in method frames
    install_eval_guard([method_dir], allowed=[method_dir])
    _EVAL_READY["method_dir"] = method_dir


def _eval_one(job: dict) -> dict:
    from brainir_causal.harness import evaluate_job
    try:
        return evaluate_job(job)
    except Exception as e:  # noqa: BLE001 - recorded per job
        import traceback
        return {"sid": job.get("sid"), "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]}


def modal_payloads(fit_jobs: list[dict], methods_key: str) -> list[dict]:
    """Payloads of E4's Backend.run_methods for fits (target brainir_causal.runner:fit_job, guard 'fit'); fit_jobs carry CONTAINER
    paths of the staged public data ({"method", "data": [...], "sid", "seed", "out_rel"}). Submit them with cls 'fit_s' (host-gated,
    <= 16 cores: the AVX-512 gate refuses far more often on large hosts) or, for neural methods, the round's ONE GPU class (default
    gpu_rtx6000, fallback gpu_b200): all official fits of one evaluation run on one platform (the fit records carry the device)."""
    return [{"target": "brainir_causal.runner:fit_job", "guard": "fit", "methods_key": methods_key,
             "args": ["$METHODS", j["method"], j["data"], [j["sid"]], f"$JOB/{j['out_rel']}"], "kwargs": {"seed": int(j["seed"])},
             "allowed": list(j["data"]), "outputs": [j["out_rel"], j["out_rel"].replace(".pkl", ".json")], "threads": 3,
             "timeout_s": float(j.get("timeout_s", 3600))} for j in fit_jobs]


# ================================================================================================================ run
def cmd_run(args) -> int:
    t_start = time.time()
    methods = [m for m in args.methods.split(",") if m]
    baselines = [m for m in (args.baselines or "").split(",") if m]
    round_dir = Path(args.run_root) / args.round
    round_dir.mkdir(parents=True, exist_ok=True)
    mdir, mhash = snapshot_methods(round_dir, Path(args.room))
    systems = stage_systems(args.stage, args.tier, [s for s in (args.systems or "").split(",") if s] or None,
                            suites_root=Path(args.suites_root), real_root=Path(args.real_root), include_real=not args.no_real)
    seeds = [int(s) for s in args.seeds.split(",") if s]
    design = {"stage": args.stage, "tier": args.tier, "systems": sorted(systems), "seeds": seeds, "lift": not args.no_lift,
              "loops": bool(args.loops), "benchmark": "causal_state_v1"}
    out_dir = Path(args.out_root) / args.round
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_cache = Path(args.run_root) / "refcache"
    report = {"round": args.round, "suite": args.tier, "design": design, "methods": methods, "baselines": baselines,
              "method_hashes": mhash, "results": {}}
    fit_jobs = []
    for m in methods:
        for sid, sd in systems.items():
            for seed in seeds:
                out = round_dir / m / "fits" / f"{SU._safe(sid)}_s{seed}.pkl"
                if out.exists() and not args.refit:
                    continue
                fit_jobs.append((_fit_cmd(mdir, m, sd, sid, out, seed), out))
    print(f"[{args.round}] {len(fit_jobs)} fits on {len(systems)} systems", flush=True)
    # the toy tiers are built into the adapter; every other synthetic tier needs the hash-locked generator
    gen = None if args.tier in ("toy", "toyC") else [str(GENERATOR), GENERATOR_PKG]
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        fit_recs = list(ex.map(lambda j: run_fit(j[0], j[1], args.timeout), fit_jobs))
    n_fit_fail = sum(1 for r in fit_recs if not r["ok"])
    eval_jobs, owners = [], []
    for m in methods:
        for sid, sd in systems.items():
            for seed in seeds:
                mp = round_dir / m / "fits" / f"{SU._safe(sid)}_s{seed}.pkl"
                if not mp.exists():
                    continue
                ev_out = round_dir / m / "evals" / f"{SU._safe(sid)}_s{seed}.pkl"
                ev_out.parent.mkdir(parents=True, exist_ok=True)
                eval_jobs.append({"sid": sid, "method_dir": str(mdir), "model_path": str(mp), "heldout_root": sd["heldout_root"],
                                  "heldout_tier": sd["heldout_tier"], "public_root": sd["public_root"], "public_tier": sd["public_tier"],
                                  "store_root": str(args.store_root), "ref_cache": str(ref_cache / sd["heldout_tier"]),
                                  "internal_path": sd["internal_path"], "generator": gen if sd["kind"] == "synthetic" else None,
                                  "lift": not args.no_lift, "n_boot": args.n_boot, "seed": seed, "fit_side": str(mp.with_suffix(".json")),
                                  "out": str(ev_out)})
                owners.append((m, sid, seed))
    print(f"[{args.round}] {len(eval_jobs)} evaluations", flush=True)
    ev_recs = []
    if eval_jobs:
        with ProcessPoolExecutor(max_workers=max(1, args.eval_workers), initializer=_eval_init, initargs=(str(mdir),)) as ex:
            ev_recs = list(ex.map(_eval_one, eval_jobs))
    import pickle
    for m in methods:
        per_sys, n_eval_fail = {}, 0
        for (mm, sid, seed), job, rec in zip(owners, eval_jobs, ev_recs):
            if mm != m or seed != seeds[0]:
                continue
            if "error" in rec or not Path(job["out"]).exists():
                n_eval_fail += 1
                per_sys[sid] = {"kind": systems[sid]["kind"], "error": rec.get("error", "no output")}
                continue
            with open(job["out"], "rb") as fh:
                ev = pickle.load(fh)
            from brainir_causal.harness import public_view
            per_sys[sid] = {"kind": ev["kind"], "verdict": public_view(ev["verdict"]), "selection": ev["selection"],
                            "result": public_view(ev["result"])}
        n_fits = sum(1 for (fm, fo) in [(j[1].parent.parent.name, j[1]) for j in fit_jobs] if fm == m)
        report["results"][m] = {"per_system": per_sys, "n_fit_failures": sum(1 for j, r in zip(fit_jobs, fit_recs)
                                                                               if j[1].parent.parent.name == m and not r["ok"]),
                                "n_fits": n_fits, "n_eval_failures": n_eval_fail}
        from brainir_causal.harness import dump
        dump(report["results"][m], out_dir / f"{m}.json")
    report["n_fit_failures"], report["wall_s"] = n_fit_fail, round(time.time() - t_start, 1)
    if args.loops:
        report["loops"] = run_loops(args, methods, systems, mdir, round_dir)
    from brainir_causal.harness import dump
    dump({k: v for k, v in report.items() if k != "results"}, out_dir / "ROUND.json")
    if args.tier not in ("dev", "toy", "toyC") and not args.no_log:
        if not LOG.exists():
            LOG.write_text("# Level B evaluation log (causal_state_v1; PROTOCOL.md section 10)\n\n| time (UTC) | round | stage | tier | methods "
                           "| systems | result dir |\n|---|---|---|---|---|---|---|\n", encoding="utf-8", newline="\n")
        with open(LOG, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {args.round} | {args.stage} | {args.tier} | {', '.join(methods)} | "
                     f"{len(systems)} | research/phase4/tournament/{args.round}/ |\n")
    print(json.dumps({"round": args.round, "fit_failures": n_fit_fail, "wall_s": report["wall_s"]}), flush=True)
    return 0


def run_loops(args, methods: list[str], systems: dict, mdir: Path, round_dir: Path) -> dict:
    """PROTOCOL 5.17 loops: needs a running round simulation service (`simserver`) whose queue is <round_dir>/sim/simq."""
    simq = round_dir / "sim" / "simq"
    designers = [d for d in args.designers.split(",") if d]
    lseeds = [int(s) for s in args.loop_seeds.split(",") if s]
    jobs = []
    for m in methods:
        for sid, sd in systems.items():
            data = str(Path(sd["public_root"]) / sd["public_tier"] / "public" / SU._safe(sid))
            budget = args.budget if not (sd["kind"] == "real" and ":full" in sid) else min(args.budget, 100)
            for d in designers:
                for s in lseeds:
                    out = round_dir / m / "loops" / f"{SU._safe(sid)}_{d}_s{s}"
                    cmd = [sys.executable, "-m", "brainir_causal.runner", "loop", "--method-dir", str(mdir), "--method", m, "--designer", d,
                           "--data", data, "--system", sid, "--budget", str(budget), "--sim-queue", str(simq), "--out", str(out), "--seed", str(s)]
                    jobs.append((cmd, out / "loop_record.json"))
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        recs = list(ex.map(lambda j: run_fit(j[0], j[1], args.timeout * 4), jobs))
    return {"n_loops": len(jobs), "n_failed": sum(1 for r in recs if not r["ok"]), "designers": designers, "loop_seeds": lseeds}


# ================================================================================================================ decide / feedback
def cmd_decide(args) -> int:
    out_dir = Path(args.out_root) / args.round
    rnd = json.loads((out_dir / "ROUND.json").read_text(encoding="utf-8"))
    cands, strata = {}, {}
    for m in rnd["methods"]:
        r = json.loads((out_dir / f"{m}.json").read_text(encoding="utf-8"))
        cands[m] = {sid: v.get("selection") or {} for sid, v in (r.get("per_system") or {}).items()}
        for sid, v in (r.get("per_system") or {}).items():
            strata[sid] = v.get("kind", "synthetic")
    rk = SEL.rank(cands, strata)
    decision = SEL.halve(rk["order"], set(rnd.get("baselines") or []), carried_baseline=args.carried, finalists=args.finalists)
    rep = {"round": args.round, "suite": rnd.get("suite"), "eligibility": rk["eligibility"], "order": rk["order"], "decision": decision,
           "pairwise": {a: {b: {k: v for k, v in c.items() if k != "details"} for b, c in row.items()} for a, row in rk["pairwise"].items()}}
    (out_dir / "DECISION.json").write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    full = {"round": args.round, "suite": rnd.get("suite"), "eligibility": rk["eligibility"], "order": rk["order"],
            "results": {m: json.loads((out_dir / f"{m}.json").read_text(encoding="utf-8")) for m in rnd["methods"]}}
    agg = FB.aggregate(full)
    FB.dump_json(agg, out_dir / "AGGREGATE_developer_facing.json")
    print(json.dumps({"order": rk["order"], "keep": decision["keep"]}, indent=1))
    return 0


def cmd_feedback(args) -> int:
    aggs = [json.loads((Path(args.out_root) / r / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8")) for r in args.rounds.split(",") if r]
    FB.write_markdown(aggs, args.out)
    print(f"wrote {args.out}")
    return 0


# ================================================================================================================ simulation service
def _gen_init(gen_dir: str, pkg: str) -> None:
    from brainir_causal.synthadapter import register_generator
    register_generator(gen_dir, pkg)


def cmd_simserver(args) -> int:
    """The round's simulation service for experiment loops (validation-tier and real systems)."""
    from brainir_causal.simservice import SimServer
    from brainir_causal.synthadapter import register_generator
    systems = {}
    syn_int = SU.tier_dirs(args.tier, Path(args.suites_root))["base"] / "internal_records.json"
    if syn_int.exists():
        systems.update(json.loads(syn_int.read_text(encoding="utf-8")))
    real_int = BENCH / "hidden" / "real_systems_internal.json"
    if real_int.exists():
        systems.update(json.loads(real_int.read_text(encoding="utf-8")))
    register_generator(str(GENERATOR), GENERATOR_PKG)
    pool = ProcessPoolExecutor(max_workers=args.workers, initializer=_gen_init, initargs=(str(GENERATOR), GENERATOR_PKG))
    room = RUN / args.round / "sim"
    SimServer(room, systems, SU.STORE, bundle=ROOT / "benchmarks" / "dng100" / "public_blind", default_budget=args.budget,
              workers=args.workers, ledger_dir=RUN / args.round / "sim_ledger", pool=pool).serve_forever()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--round", required=True)
    r.add_argument("--stage", choices=("pilot", "medium", "finalists", "full"), default="pilot")
    r.add_argument("--methods", required=True)
    r.add_argument("--baselines", default="")
    r.add_argument("--room", default=str(ROOM))
    r.add_argument("--tier", default="val")
    r.add_argument("--suites-root", default=str(SU.SUITES))
    r.add_argument("--real-root", default=str(SU.REAL_SETS))
    r.add_argument("--systems", default="")
    r.add_argument("--seeds", default="0")
    r.add_argument("--parallel", type=int, default=4)
    r.add_argument("--eval-workers", type=int, default=4)
    r.add_argument("--timeout", type=float, default=3600.0)
    r.add_argument("--n-boot", type=int, default=2000)
    r.add_argument("--no-lift", action="store_true")
    r.add_argument("--no-real", action="store_true")
    r.add_argument("--refit", action="store_true")
    r.add_argument("--store-root", default=str(SU.STORE))
    r.add_argument("--no-log", action="store_true", help="smoke runs: no LEVELB_LOG row")
    r.add_argument("--out-root", default=str(OUT), help="where the round results go (default research/phase4/tournament)")
    r.add_argument("--run-root", default=str(RUN))
    r.add_argument("--loops", action="store_true")
    r.add_argument("--designers", default="own,random,uniform,magnitude_sweep,greedy_error,structural,passive,fixed")
    r.add_argument("--loop-seeds", default="0,1,2")
    r.add_argument("--budget", type=int, default=200)
    d = sub.add_parser("decide")
    d.add_argument("--round", required=True)
    d.add_argument("--finalists", type=int, default=None)
    d.add_argument("--carried", default=None)
    d.add_argument("--out-root", default=str(OUT))
    f = sub.add_parser("feedback")
    f.add_argument("--rounds", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--out-root", default=str(OUT))
    s = sub.add_parser("simserver")
    s.add_argument("--round", required=True)
    s.add_argument("--tier", default="val")
    s.add_argument("--suites-root", default=str(SU.SUITES))
    s.add_argument("--budget", type=int, default=10**7)
    s.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    return {"run": cmd_run, "decide": cmd_decide, "feedback": cmd_feedback, "simserver": cmd_simserver}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
