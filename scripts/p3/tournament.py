"""state_discovery_v1 Level B tournament (orchestrator; PROTOCOL.md section 9). Also used for the Level B confirmation (--suite final).

    uv run --project phase3 python scripts/p3/tournament.py --round r1 --methods m1,m2 [--suite heldout] [--parallel 5]
                                                            [--eval-workers 6] [--g-systems 8] [--skip-shared] [--systems s1,s2]

1. snapshots the clean room's methods package (C:\\Dev\\BrainIR_p3clean\\src\\brainir_state\\methods) into
   C:\\Dev\\BrainIR_p3run\\<round>\\methods (hashes recorded) - the orchestrator never imports the room directly;
2. fits every method on every system of the suite in the sandbox (seed 0); seeds 1 and 2 on the first --g-systems compressible
   systems (G); shared fits on the implementation groups and unrelated pairs, and leave-one-implementation-out fits (I);
3. evaluates every model on the suite's held-out material in guarded worker processes; references per system are cached;
4. computes verdicts with the calibrated tolerances and the aggregate profile S1-S8 of PROTOCOL.md section 9;
5. writes research/phase3/tournament/<round>/ (per-method results are ANSWER-BEARING for the synthetic suite: never copied into a
   room) and a developer-facing aggregate (profiles and verdict counts only), and appends a row to research/phase3/LEVELB_LOG.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
from brainir_state.evaluate_cross import loio_comparison, n_params, sharing_comparison, sharing_verdict  # noqa: E402
from brainir_state.evaluate_synth import abstention_row, abstention_summary  # noqa: E402
from brainir_state.harness import key_a, key_c, key_d, verdict  # noqa: E402
from brainir_state.suite_eval import SuiteData, dump, evaluate_models, reference_results, reproducibility_jobs, run_fits  # noqa: E402

ROOM = Path(r"C:\Dev\BrainIR_p3clean")
RUN = Path(r"C:\Dev\BrainIR_p3run")
DATA = ROOT / "data" / "phase3"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
OUT = ROOT / "research" / "phase3" / "tournament"
# the round-1 pilot subset of PROTOCOL.md section 9 (catalogue names; fixed before any candidate existed)
PILOT = ("linear_k3", "damped", "hopf", "bistable_1d", "leaky", "perfect_2d", "gated", "wta", "slow_fast", "nuisance_ou", "nonmarkov",
         "output_shortcut", "time_index", "hidden_exogenous", "highdim_chaotic", "multicycle_planar")


def suite_spec(tier: str) -> dict:
    rec = json.loads((BENCH / "hidden" / "synthetic_suites.json").read_text(encoding="utf-8"))[tier]
    pub = DATA / "synthetic_dev" if tier == "dev" else DATA / "synthetic" / tier / "public"
    truth = DATA / "synthetic_truth" / "dev" if tier == "dev" else DATA / "synthetic" / tier / "truth"
    return {"public_dir": str(pub), "truth_dir": str(truth), "kind": "synthetic", "tier": tier, "suite_seed": int(rec["seed"])}


def snapshot_methods(round_dir: Path, room: Path = ROOM) -> tuple[Path, dict]:
    src = room / "src" / "brainir_state" / "methods"
    dst = round_dir / "methods"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    hashes = {p.relative_to(dst).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dst.rglob("*.py"))}
    return dst, hashes


def limited_view(sd: SuiteData, sid: str, root: Path, every: int = 4) -> Path:
    """Fit view with 25 % of one system's training trajectories (leave-one-implementation-out adaptation data)."""
    if (root / "manifest.json").exists():
        return root
    (root / "traj").mkdir(parents=True, exist_ok=True)
    rows = [r for r in sd.pub.select(system_id=sid) if r["split"] == "train"][::every]
    import os
    for r in rows:
        src, dst = sd.public_dir / "traj" / f"{r['key']}.npz", root / "traj" / f"{r['key']}.npz"
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
    man = dict(sd.pub.manifest)
    man["systems"] = {sid: sd.pub.systems[sid]}
    man["splits"] = ["train"]
    (root / "index.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8", newline="\n")
    (root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return root


def med(v):
    v = np.array([x for x in v if x is not None and np.isfinite(x)], float)
    return float(np.median(v)) if len(v) else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True)
    ap.add_argument("--methods", required=True)
    ap.add_argument("--suite", default="heldout")
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--eval-workers", type=int, default=6)
    ap.add_argument("--g-systems", type=int, default=8)
    ap.add_argument("--skip-shared", action="store_true")
    ap.add_argument("--systems", default="")
    ap.add_argument("--pilot", action="store_true", help="round 1: the pilot subset, seed 0, no G / shared fits")
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--room", default=str(ROOM), help="the clean room whose methods package is snapshotted")
    ap.add_argument("--sim-budget", type=int, default=250, help="simulations per fit through the suite's simulation service (0: no simulator)")
    args = ap.parse_args(argv)
    from brainir_state.suite_eval import limit_threads
    limit_threads(4)          # references are fitted in this process; fits and evaluations run in their own processes
    t_start = time.time()
    methods = [m for m in args.methods.split(",") if m]
    round_dir = RUN / args.round
    round_dir.mkdir(parents=True, exist_ok=True)
    mdir, mhash = snapshot_methods(round_dir, Path(args.room))
    spec = suite_spec(args.suite)
    sd = SuiteData(spec["public_dir"], kind="synthetic", truth_dir=spec["truth_dir"])
    view = sd.fit_view(round_dir / f"fitview_{args.suite}")
    simq, sim_proc = None, None
    if args.sim_budget > 0:
        import subprocess
        sysfile = BENCH / "hidden" / f"simservice_systems_{args.suite}.json"
        if not sysfile.exists():
            subprocess.run([sys.executable, str(ROOT / "scripts" / "p3" / "simservice_systems.py"), "--suite", args.suite], check=True)
        simroot = round_dir / "sim"
        simq = simroot / "simq"
        sim_proc = subprocess.Popen([sys.executable, "-m", "brainir_state.simservice", "--clean", str(simroot), "--systems", str(sysfile),
                                     "--bundle", str(ROOT / "benchmarks" / "dng100" / "public_blind"), "--store", str(DATA / "store"),
                                     "--budget", str(args.sim_budget), "--workers", "4"],
                                    stdout=open(round_dir / "simservice.log", "a"), stderr=subprocess.STDOUT)
    taus = json.loads((BENCH / "public" / "tolerances.json").read_text(encoding="utf-8"))
    truth = sd.truth
    sids = [s for s in (args.systems.split(",") if args.systems else sd.systems) if s]
    if args.pilot:
        sids = sorted(s for s in sids if truth["systems"][s]["name"] in PILOT)
        args.g_systems, args.skip_shared = 0, True
    compressible = [s for s in sids if truth["systems"][s]["k"] != "none"]
    groups = [g for g in truth["suite"]["implementation_groups"].values() if set(g) <= set(sids)]
    pairs = [p for p in truth["suite"]["unrelated_pairs"] if set(p) <= set(sids)]
    out_dir = OUT / args.round
    report = {"round": args.round, "suite": args.suite, "methods": methods, "method_hashes": mhash, "tolerances": taus, "results": {}}
    for m in methods:
        mroot = round_dir / m
        jobs = [dict(method_dir=mdir, method=m, datasets=[view], systems=[s], out=mroot / "indep" / f"{s}_s0.pkl", seed=0,
                     timeout_s=args.timeout, sim_queue=simq) for s in sids]
        for seed in (1, 2):
            jobs += [dict(method_dir=mdir, method=m, datasets=[view], systems=[s], out=mroot / "indep" / f"{s}_s{seed}.pkl", seed=seed,
                          timeout_s=args.timeout, sim_queue=simq) for s in compressible[: args.g_systems]]
        shared_sets = [] if args.skip_shared else [("group", g) for g in groups] + [("pair", p) for p in pairs]
        for kind, members in shared_sets:
            tag = hashlib.sha256("+".join(sorted(members)).encode()).hexdigest()[:8]
            jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=list(members), out=mroot / "shared" / f"{kind}_{tag}.pkl",
                             config={"sharing": "shared"}, seed=0, timeout_s=args.timeout * 2, sim_queue=simq))
            if kind == "group":
                for held in members:
                    others = [s for s in members if s != held]
                    jobs.append(dict(method_dir=mdir, method=m, datasets=[view], systems=others,
                                     out=mroot / "loio" / f"{tag}_without_{held}.pkl", config={"sharing": "shared"}, seed=0,
                                     timeout_s=args.timeout * 2, sim_queue=simq))
        print(f"[{m}] {len(jobs)} fits", flush=True)
        fit_recs = run_fits(jobs, parallel=args.parallel)
        # leave-one-implementation-out adaptation (needs the shared-on-others models)
        loio_jobs = []
        if not args.skip_shared:
            for g in groups:
                tag = hashlib.sha256("+".join(sorted(g)).encode()).hexdigest()[:8]
                for held in g:
                    base = mroot / "loio" / f"{tag}_without_{held}.pkl"
                    lv = limited_view(sd, held, round_dir / f"limited_{args.suite}_{held}")
                    if base.exists():
                        loio_jobs.append(dict(method_dir=mdir, method=m, datasets=[lv], systems=[held], out=mroot / "loio" / f"{tag}_adapt_{held}.pkl",
                                              adapt_from=base, seed=0, timeout_s=args.timeout))
                    loio_jobs.append(dict(method_dir=mdir, method=m, datasets=[lv], systems=[held], out=mroot / "loio" / f"{tag}_scratch_{held}.pkl",
                                          seed=0, timeout_s=args.timeout))
            fit_recs += run_fits(loio_jobs, parallel=args.parallel)
        n_fail = sum(1 for r in fit_recs if "error" in r)
        # ---- evaluation
        ev_jobs = []
        for s in sids:
            p = mroot / "indep" / f"{s}_s0.pkl"
            if p.exists():
                ev_jobs.append({"suite": spec, "sid": s, "method_dir": str(mdir), "model_path": str(p), "lift": True, "tag": "indep_s0"})
        for s in compressible[: args.g_systems]:
            for seed in (1, 2):
                p = mroot / "indep" / f"{s}_s{seed}.pkl"
                if p.exists():
                    ev_jobs.append({"suite": spec, "sid": s, "method_dir": str(mdir), "model_path": str(p), "lift": False, "tag": f"indep_s{seed}"})
        for p in sorted((mroot / "shared").glob("*.pkl")) + sorted((mroot / "loio").glob("*_adapt_*.pkl")) + sorted((mroot / "loio").glob("*_scratch_*.pkl")):
            side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
            for s in side["systems"]:
                ev_jobs.append({"suite": spec, "sid": s, "method_dir": str(mdir), "model_path": str(p), "lift": False, "tag": p.parent.name + ":" + p.stem})
        evs = evaluate_models(ev_jobs, workers=args.eval_workers)
        by = {(e["sid"], j["tag"]): e for e, j in zip(evs, ev_jobs)}
        # ---- per-system verdicts and K / L
        cfg = sd.cfg
        per_sys, l_rows = {}, []
        for s in sids:
            e = by.get((s, "indep_s0"))
            tr = truth["systems"][s]
            if e is None or "error" in e:
                per_sys[s] = {"error": (e or {}).get("error", "fit failed"), "trap": tr.get("trap")}
                l_rows.append(abstention_row(tr, None, None))
                continue
            k = e.get("k")
            refs = reference_results(sd, s, int(k) if k else 1, OUT / "_refcache" / args.suite)
            ab = ((e.get("info") or {}).get("abstain") or {}).get(s)
            v = verdict(e["res"], refs, taus, len(sd.sysinfo(s)["observed"]), k, "synthetic", cfg, abstain=ab)
            per_sys[s] = {"k": k, "k_true": tr["k"], "trap": tr.get("trap"), "verdict": v, "K": e.get("K"), "K_dim": e.get("K_dim"),
                          "lift": e.get("lift"), "A_over_full": (v["A"] / v["A_full"]) if v["A_full"] else None,
                          "eval_wall_s": e.get("eval_wall_s")}
            l_rows.append(abstention_row(tr, ab, v))
        # ---- G (latent alignment across seeds, fitted on public validation data, measured on held-out data)
        g_jobs = []
        for s in compressible[: args.g_systems]:
            paths = [mroot / "indep" / f"{s}_s{seed}.pkl" for seed in (0, 1, 2)]
            if all(p_.exists() for p_ in paths):
                g_jobs.append({"suite": spec, "sid": s, "method_dir": str(mdir), "model_paths": [str(p_) for p_ in paths]})
        g_out = {r["sid"]: r for r in reproducibility_jobs(g_jobs, workers=args.eval_workers)} if g_jobs else {}
        g_rows = {}
        for s in compressible[: args.g_systems]:
            ks = [by.get((s, f"indep_s{seed}"), {}).get("k") for seed in (0, 1, 2)]
            a = [((by.get((s, f"indep_s{seed}"), {}).get("res") or {}).get("A_B") or {}).get(key_a(cfg), {}).get("mean") for seed in (0, 1, 2)]
            kr = [((by.get((s, f"indep_s{seed}"), {}).get("K") or {}).get("r2_true_from_model_rff")) for seed in (0, 1, 2)]
            g = (g_out.get(s) or {}).get("G") or {}
            g_rows[s] = {"k": ks, "A": a, "K_r2": kr, "cca_mean": g.get("cca_mean"), "r2_min_mean": g.get("r2_min_mean"),
                         "prediction_disagreement_nmse": g.get("prediction_disagreement_nmse"), "error": (g_out.get(s) or {}).get("error")}
        # ---- I (groups) and sharing nulls (pairs)
        i_rows = []
        if not args.skip_shared:
            for kind, members in [("group", g) for g in groups] + [("pair", p) for p in pairs]:
                tag = hashlib.sha256("+".join(sorted(members)).encode()).hexdigest()[:8]
                sh = {s: by.get((s, f"shared:{kind}_{tag}")) for s in members}
                ind = {s: by.get((s, "indep_s0")) for s in members}
                if any(v_ is None or "error" in v_ for v_ in list(sh.values()) + list(ind.values())):
                    i_rows.append({"kind": kind, "members": members, "verdict": "untestable", "reason": "missing fit or evaluation"})
                    continue
                shared_res = {s: {"A": sh[s]["res"]["A_B"], "C": sh[s]["res"].get("C_heldout") or {}} for s in members}
                indep_res = {s: {"A": ind[s]["res"]["A_B"], "C": ind[s]["res"].get("C_heldout") or {}} for s in members}
                p_sh = {"encoder": 0, "readout": 0, "transition": 0, "total": 0, "reported": False}
                info_sh = sh[members[0]].get("info") or {}
                npar = info_sh.get("n_params") or {}
                if npar:
                    enc = sum(int((npar.get("encoder") or {}).get(s, 0)) for s in members)
                    ro = sum(int((npar.get("readout") or {}).get(s, 0)) for s in members)
                    trn = int(npar.get("transition", 0) or 0)
                    p_sh = {"encoder": enc, "readout": ro, "transition": trn, "total": enc + ro + trn, "reported": True}
                p_in = {"encoder": 0, "readout": 0, "transition": 0, "total": 0, "reported": True}
                for s in members:
                    np_s = (ind[s].get("info") or {}).get("n_params") or {}
                    if not np_s:
                        p_in["reported"] = False
                        continue
                    for kk in ("encoder", "readout"):
                        p_in[kk] += int((np_s.get(kk) or {}).get(s, 0))
                    p_in["transition"] += int(np_s.get("transition", 0) or 0)
                p_in["total"] = p_in["encoder"] + p_in["readout"] + p_in["transition"]
                comp = sharing_comparison(shared_res, indep_res, p_sh, p_in, taus["tau_A"], a_key=key_a(cfg),
                                          c_key=f"C_w{int(round(cfg.primary_c_window_s * 1000))}ms")
                loio = []
                if kind == "group":
                    for held in members:
                        ad, sc = by.get((held, f"loio:{tag}_adapt_{held}")), by.get((held, f"loio:{tag}_scratch_{held}"))
                        if ad and sc and "error" not in ad and "error" not in sc:
                            loio.append(loio_comparison({"A": ad["res"]["A_B"], "C": ad["res"].get("C_heldout") or {}},
                                                        {"A": sc["res"]["A_B"], "C": sc["res"].get("C_heldout") or {}}, a_key=key_a(cfg),
                                                        c_key=f"C_w{int(round(cfg.primary_c_window_s * 1000))}ms"))
                vd = sharing_verdict(comp, loio if kind == "group" else [{"adapted_beats_scratch": True, "adapted_worse": False}])
                expected = "supported" if kind == "group" else "rejected"
                i_rows.append({"kind": kind, "members": members, "verdict": vd, "expected": expected, "correct": vd == expected,
                               "comparison": {k_: v_ for k_, v_ in comp.items() if k_ != "per_system"},
                               "per_system": {s: {"A_diff": r["A_diff"], "C_diff": r["C_diff"], "A_noninferior": r["A_noninferior"],
                                                  "C_noninferior": r["C_noninferior"]} for s, r in comp["per_system"].items()},
                               "loio": loio})
        # ---- aggregate profile S1-S8
        comp_ok = [s for s in compressible if "verdict" in per_sys.get(s, {})]
        lsum = abstention_summary(l_rows)
        prof = {"S1_A_over_full": med([per_sys[s]["A_over_full"] for s in comp_ok]),
                "S2_C_heldout": med([per_sys[s]["verdict"]["C"] for s in comp_ok]),
                "S3_D_micro_gain": med([per_sys[s]["verdict"]["D_micro_gain"] for s in comp_ok]),
                "S4_E_ratio": med([per_sys[s]["verdict"]["E_ratio"] for s in comp_ok]),
                "S5_K_r2_rff": med([(per_sys[s].get("K") or {}).get("r2_true_from_model_rff") for s in comp_ok]),
                "S6_dim_rate": float(np.mean([bool((per_sys[s].get("K_dim") or {}).get("in_range")) for s in comp_ok])) if comp_ok else float("nan"),
                "S7_abstention": float(np.nanmean([lsum["abstention_recall"], 1 - lsum["false_alarm_rate"]])),
                "S8_sharing_correct": float(np.mean([r.get("correct", False) for r in i_rows])) if i_rows else float("nan")}
        verdict_counts = {}
        for s in comp_ok:
            vv = per_sys[s]["verdict"]["verdict"]
            verdict_counts[vv] = verdict_counts.get(vv, 0) + 1
        fit_times = [r.get("fit_wall_s") for r in fit_recs if r.get("fit_wall_s") is not None]
        report["results"][m] = {"profile": prof, "verdict_counts_compressible": verdict_counts, "abstention": lsum, "n_fits": len(fit_recs),
                                "n_fit_failures": n_fail, "eligible": n_fail <= 0.1 * len(fit_recs), "fit_wall_s_median": med(fit_times),
                                "fit_wall_s_total": float(np.nansum(fit_times)) if fit_times else 0.0,
                                "per_system": per_sys, "G": g_rows, "I": i_rows}
        dump(report["results"][m], out_dir / f"{m}.json")
        print(f"[{m}] profile {json.dumps(prof)} verdicts {verdict_counts} failures {n_fail}", flush=True)
    if sim_proc is not None:
        sim_proc.terminate()
    # ---- ranks (PROTOCOL section 9)
    elig = [m for m in methods if report["results"][m]["eligible"]]
    better_low = {"S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio"}
    ranks = {m: [] for m in elig}
    for key in ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff", "S6_dim_rate", "S7_abstention", "S8_sharing_correct"):
        vals = {m: report["results"][m]["profile"][key] for m in elig}
        order = sorted(elig, key=lambda m: (np.inf if not np.isfinite(vals[m]) else (vals[m] if key in better_low else -vals[m])))
        for r, m in enumerate(order):
            ranks[m].append(r + 1)
    report["mean_rank"] = {m: float(np.mean(v)) for m, v in ranks.items()}
    report["wall_s"] = round(time.time() - t_start, 1)
    dump({k: v for k, v in report.items() if k != "results"} | {"profiles": {m: report["results"][m]["profile"] for m in methods},
                                                                "verdict_counts": {m: report["results"][m]["verdict_counts_compressible"] for m in methods},
                                                                "eligible": {m: report["results"][m]["eligible"] for m in methods}},
         out_dir / "AGGREGATE_developer_facing.json")
    log = ROOT / "research" / "phase3" / "LEVELB_LOG.md"
    if args.suite == "dev":       # development-suite runs (pipeline checks) are not Level B evaluations
        print(json.dumps(report["mean_rank"], indent=1))
        return 0
    if not log.exists():
        log.write_text("# Level B evaluation log (synthetic heldout / final; PROTOCOL.md sections 9-10)\n\n| time (UTC) | round | suite | methods | "
                       "result file |\n|---|---|---|---|---|\n", encoding="utf-8", newline="\n")
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | {args.round} | {args.suite} | {', '.join(methods)} | "
                 f"research/phase3/tournament/{args.round}/ |\n")
    print(json.dumps(report["mean_rank"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
