"""Post-lock ADVERSARIAL COUNTEREXAMPLE SEARCH (goal5 sections 84, 91; SELF_AUDIT_PLAN Q19). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/counterexamples_p4.py run --method NAME --tier conf [--real C]
        --fits-from <dir with <sid>_s<seed>.pkl fits> [--budget 50] [--rounds 20,15,15] [--run-id ID]
    uv run --no-sync --project phase4 python scripts/p4/counterexamples_p4.py run --method p3stand.refstand:p3stand_ref --tier dev
        --methods-dir scripts/p4/standin_methods --fits-from C:/Dev/BrainIR_p4run/postlock/ablations/dry1/full --run-id dry1   # DRY RUN

QUESTION (Q19): can an adversarial search break the locked model immediately? A COUNTEREXAMPLE is an intervention with a DETECTABLE
true effect (ES_i >= 1, PROTOCOL 5.1), inside the model's CLAIMED validity domain (validity()["in_domain"] true; a model that reports
no validity claims everything), NOT abstained, whose prediction is worse than predicting no effect (EE_i > 1 at the primary horizon;
a failed prediction is scored as the cap and counts). PASS (fixed before the lock): a counterexample is found on at most 50 % of the
compressible confirmation systems within 50 evaluations per system (real systems are reported beside).

SEARCH (per system, budget 50 simulated candidates, all systems in parallel): round 1 = 20 random genomes over the system's supported
intervention families (trained, held-out, hidden-only), targets / edges (public + held-out), magnitude 0.1-3 x moderate (the
development range), onset 10-60 % of the duration, stimulus level, trajectory draw (`p4post.itemsets`); rounds 2-3 = 15 each,
EVOLUTIONARY: children of the 5 fittest candidates so far (fitness = EE_i on eligible candidates, 0.5 min(EE_i, 1) otherwise; mutation
of family / targets / log-magnitude / onset / level / draw). Gradient-free by design: the model is a black box in its workers.
Each round: the candidates are PLANNED here (hidden-range seeds from the salt post-lock), BUILT on Modal by the benchmark's builder
into a custom tier (simulation with twins, truth, onset states), and EVALUATED by `p4post.isojob.predict_detail` (the benchmark's item
scoring in model workers, per-item validity).
Outputs: <out>/COUNTEREXAMPLES.json / .md (post-lock: research/phase4/postlock/counterexamples/<run>/, ANSWER-BEARING).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p4"))
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from p4post import common as C  # noqa: E402
from p4post import execute as X  # noqa: E402
from p4post import itemsets as IS  # noqa: E402

STUDY = "counterexamples"
N_ELITE = 5
PASS_SHARE = 0.5


def is_counterexample(row: dict) -> bool:
    es, ee = row.get("es"), row.get("ee_i")
    in_dom = row.get("validity_in_domain")
    return bool(es is not None and es >= 1.0 and not row.get("abstain") and (in_dom is None or in_dom) and ee is not None and ee > 1.0)


def eligible(row: dict) -> bool:
    es, in_dom = row.get("es"), row.get("validity_in_domain")
    return bool(es is not None and es >= 1.0 and not row.get("abstain") and (in_dom is None or in_dom))


def fitness(row: dict | None) -> float:
    if row is None:
        return -1.0
    ee = row.get("ee_i")
    ee = 10.0 if ee is None else float(ee)
    return ee if eligible(row) else 0.5 * min(ee, 1.0)


def cmd_run(args) -> int:
    t0 = time.time()
    real_level = args.real or None
    g = C.guard(args.tier, real_level, what="the counterexample search", dry_run_on_val=args.dry_run_on_val, methods=[args.method],
                methods_dir=args.methods_dir)
    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%S")
    rd = C.RunDirs(STUDY, run_id, g["hidden"])
    methods_dir = Path(args.methods_dir) if args.methods_dir else C.LOCKED_METHODS
    mhash = C.snapshot_methods(methods_dir, rd.run / "methods")
    systems = C.resolve_systems(args.tier, real_level, [s for s in (args.systems or "").split(",") if s] or None)
    seed = int(args.seed)
    rounds = [int(x) for x in args.rounds.split(",") if x]
    if sum(rounds) != int(args.budget):
        raise SystemExit(f"rounds {rounds} do not sum to the budget {args.budget}")
    from p4post.levelc_io import model_source
    if not (args.fits_from or args.levelc_run):
        raise SystemExit("give --levelc-run (post-lock: the Level C fits) or --fits-from (dry runs)")
    models = {s: model_source(s, seed, fits_from=args.fits_from, levelc_run=args.levelc_run) for s in systems}
    missing = sorted(s for s, p in models.items() if p is None)
    if missing:
        raise SystemExit(f"no fitted model for {len(missing)} systems (e.g. {missing[:3]}) under {args.fits_from}")
    recs = C.plan_records(args.tier, real_level, sorted(systems))
    excl = [f for f in (args.exclude_families or "").split(",") if f]
    fams = {s: IS.search_families(recs[s]["pub"], recs[s]["internal"], exclude=excl) for s in systems}
    rng = {s: np.random.default_rng(IS._h("ce", run_id, s)) for s in systems}
    seed_fns = {s: IS.seed_function(g["hidden"], "ce", run_id, s) for s in systems}
    record = {"study": STUDY, "run_id": run_id, "created_utc": C.utc(), **C.run_marks(g, args.tier, real_level), "hidden": g["hidden"],
              "lock": g["lock"], "method": args.method, "method_hashes": mhash, "fits_from": str(args.fits_from), "levelc_run": args.levelc_run, "seed": seed,
              "budget": int(args.budget), "rounds": rounds, "systems": sorted(systems), "families": fams, "exclude_families": excl,
              "modal": {"rounds": []}}
    C.dump_json(record, rd.out / "RUN.json")
    pop: dict[str, list[dict]] = {s: [] for s in systems}           # evaluated candidates: {"genome", "row" | None, "round"}
    synthetic = any(d["kind"] == "synthetic" for d in systems.values())
    real = any(d["kind"] == "real" for d in systems.values())
    packed = not args.unpacked
    classes = ["build", X.PACK_EVAL] if packed else sorted({"build", "iso_eval_s"} | ({"iso_eval_l"} if real else set()))
    if g["hidden"]:
        record["ledger"] = C.ledger_claim(STUDY, run_id, new_run_reason=args.new_run_reason)
    costs: list[dict] = []
    ctx = {"systems": systems, "recs": recs, "fams": fams, "rng": rng, "seed_fns": seed_fns, "models": models, "seed": seed, "pop": pop,
           "args": args, "run_id": run_id, "packed": packed, "rd": rd, "hidden": g["hidden"]}
    with C.HiddenRunLog(g["hidden"], STUDY, run_id, f"{args.method} on {args.tier}/{real_level}: {len(systems)} systems x {args.budget}"):
        for r, n in enumerate(rounds, start=1):
            # a NEW app per round: packed evaluation containers reload the volumes once, when they start, so they must start after
            # this round's build committed its item set (p4post.execute, packed-class rules); a warm container of the previous round
            # would not see it
            with C.backend(classes, synthetic=synthetic, app_name=f"brainir-p4-post-ce-r{r}", max_containers=args.max_containers) as be:
                rec_r = run_round(be, r, n, ctx)
                costs.append(be.cost_summary())
            rec_r["app_id"] = costs[-1].get("app_id")
            record["modal"]["rounds"].append(rec_r)
            C.dump_json(record, rd.out / "RUN.json")
            C.dump_json({s: [{"genome": q["genome"], "row": q["row"], "round": q["round"]} for q in v] for s, v in pop.items()},
                        rd.run / "population.json")
            print(f"[ce {run_id}] round {r}: {rec_r['n_candidates']} candidates, build {rec_r['build_s']} s, eval {rec_r['eval_s']} s, "
                  f"build errors {len(rec_r['build_errors'])}, eval errors {len(rec_r['eval_errors'])}", flush=True)
    record["modal"]["cost"] = {"usd_approx_total": round(sum(float(c.get("usd_approx_total") or 0.0) for c in costs), 4),
                               "app_ids": [c.get("app_id") for c in costs], "per_round": costs}
    record["wall_s"] = X.wall(t0)
    record["status"] = "complete"
    C.dump_json(record, rd.out / "RUN.json")
    summ = summarize(rd, record, pop)
    print(json.dumps({"run": run_id, "wall_s": record["wall_s"], "Q19": summ["Q19"]["status"], "share_found": summ["Q19"].get("share_found"),
                      "usd": (record["modal"].get("cost") or {}).get("usd_approx_total")}, indent=1), flush=True)
    return 0


def run_round(be, r: int, n: int, ctx: dict) -> dict:
    """One search round: plan n candidates per system (round 1 random, later rounds children of the elite), build them on Modal
    (one build container per system, into the round's custom tier), evaluate them (`p4post_iso:predict_detail`, packed)."""
    systems, recs, fams, rng, seed_fns = ctx["systems"], ctx["recs"], ctx["fams"], ctx["rng"], ctx["seed_fns"]
    pop, args, rd = ctx["pop"], ctx["args"], ctx["rd"]
    tr = time.time()
    key = be.methods_key(rd.run / "methods")                  # uploaded before this round's packed containers start
    tier_r = C.custom_tier("ce", ctx["run_id"], f"r{r}", hidden=ctx["hidden"])
    cands: dict[str, list[dict]] = {}
    for s in systems:
        pub, internal = recs[s]["pub"], recs[s]["internal"]
        if r == 1 or not pop[s]:
            gs = [IS.random_genome(pub, internal, fams[s], rng[s], seed_fns[s], f"r{r}c{j}") for j in range(n)]
        else:
            elite = sorted(pop[s], key=lambda q: -fitness(q["row"]))[:N_ELITE]
            gs = [IS.mutate(elite[j % len(elite)]["genome"], pub, internal, fams[s], rng[s], seed_fns[s], f"r{r}c{j}") for j in range(n)]
        cands[s] = gs
    jobs, owners, plan_err = [], [], {}
    for s, gs in cands.items():
        specs = []
        for gg in gs:
            try:
                specs.append(IS.realize(gg, recs[s]["pub"], recs[s]["internal"], role=f"ce:r{r}"))
            except Exception as e:  # noqa: BLE001 - an unrealisable genome is recorded, never silently dropped
                plan_err.setdefault(s, []).append(f"{gg['cid']}: {type(e).__name__}: {str(e)[:120]}")
        jobs.append([IS.build_job(s, systems[s]["kind"], tier_r, recs[s]["pub"], recs[s]["internal"], specs, workers=args.build_workers)])
        owners.append(s)
    tb = time.time()
    bres = be.call("brainir_causal.suites:build_system_job", jobs, cls="build", timeout_s=4 * 3600, threads=1, eager=True,
                   reload=["fit", "eval", "store"], commit=["fit", "eval", "store"])
    build_s = X.wall(tb)
    build_err, sim_err = {}, {}
    for s, br in zip(owners, bres):
        val, err = C.call_result(br)
        if err is not None:
            build_err[s] = err[-1500:]
        elif (val.get("parts") or {}).get("eval", {}).get("errors"):
            e = val["parts"]["eval"]["errors"]
            sim_err[s] = f"{len(e)} simulation errors (first: {str(e[0])[:300]})"
    specs_e = []
    for s, sysd in systems.items():
        if s in build_err:
            continue
        job = C.eval_job(s, sysd, lift=False, n_boot=args.n_boot, seed=ctx["seed"], heldout_tier=tier_r,
                         heldout_root=C.custom_heldout_root(sysd), part="eval")
        job.update({"row_meta_keys": ["p4post"], "with_events": True, "n_probe": 0, "call_timeout_s": 900})
        specs_e.append({"sid": s, "sysd": sysd, "job": job, "model_path": ctx["models"][s]})
    te = time.time()
    eres = X.run_custom(be, "predict_detail", specs_e, key=key, packed=ctx["packed"], label=f"ce-eval-r{r}",
                        done_dir=rd.run / "_done" / f"r{r}")
    eval_s = X.wall(te)
    eval_err = {}
    evaluated = set()
    for sp, (val, err) in zip(specs_e, eres):
        s = sp["sid"]
        evaluated.add(s)
        rows = {}
        if val is not None:
            for row in val.get("items") or []:
                cid = ((row.get("meta") or {}).get("p4post") or {}).get("cid")
                if cid:
                    rows[cid] = row
        else:
            eval_err[s] = str(err)[:1500]
        for gg in cands[s]:
            pop[s].append({"genome": gg, "row": rows.get(gg["cid"]), "round": r})
    for s in systems:
        if s not in evaluated:
            for gg in cands[s]:
                pop[s].append({"genome": gg, "row": None, "round": r})
    return {"round": r, "tier": tier_r, "n_candidates": sum(len(v) for v in cands.values()), "build_s": build_s, "eval_s": eval_s,
            "round_s": X.wall(tr), "build_errors": build_err, "simulation_errors": sim_err, "eval_errors": eval_err, "plan_errors": plan_err}


def summarize(rd: C.RunDirs, record: dict, pop: dict | None = None) -> dict:
    if pop is None:
        pop = C.load_json(rd.run / "population.json", {})
    systems = C.resolve_systems(record["tier"], record.get("real_level"), record["systems"])
    truth = C.load_json(C.SU.tier_dirs(record["tier"], C.SU.SUITES)["base"] / "truth" / "systems_truth.json", {}) if record.get("tier") else {}
    per = {}
    for s, lst in pop.items():
        rows = [q for q in lst]
        evaluated = [q for q in rows if q["row"] is not None]
        found_idx = next((i + 1 for i, q in enumerate(rows) if q["row"] is not None and is_counterexample(q["row"])), None)
        ces = [q for q in evaluated if is_counterexample(q["row"])]
        best = max(evaluated, key=lambda q: fitness(q["row"])) if evaluated else None
        noncomp = str((truth.get(s) or {}).get("k")) == "none"
        per[s] = {"kind": systems[s]["kind"], "noncompressible": noncomp, "n_planned": len(rows), "n_evaluated": len(evaluated),
                  "n_eligible": sum(1 for q in evaluated if eligible(q["row"])), "n_counterexamples": len(ces), "found": bool(ces),
                  "first_found_at": found_idx,
                  "found_by_round": {r: any(is_counterexample(q["row"]) for q in evaluated if q["round"] <= r) for r in range(1, len(record["rounds"]) + 1)},
                  "best": None if best is None else {"genome": best["genome"], "ee_i": best["row"].get("ee_i"), "es": best["row"].get("es"),
                                                     "family": best["row"].get("family"), "abstain": best["row"].get("abstain"),
                                                     "in_domain": best["row"].get("validity_in_domain"),
                                                     "counterexample": is_counterexample(best["row"])},
                  "families_of_counterexamples": sorted({q["row"].get("family") for q in ces})}
    comp = [s for s, v in per.items() if v["kind"] == "synthetic" and not v["noncompressible"]]
    found = [s for s in comp if per[s]["found"]]
    under_budget = [s for s in comp if per[s]["n_evaluated"] < record["budget"]]
    share = len(found) / len(comp) if comp else None
    q19 = {"status": ("PASS" if share is not None and share <= PASS_SHARE else ("FAIL" if share is not None else "NOT TESTABLE")),
           "rule": f"a counterexample found on at most {PASS_SHARE:.0%} of the compressible confirmation systems within {record['budget']} "
                   "evaluations per system", "share_found": share, "n_systems": len(comp), "n_found": len(found),
           "systems_with_fewer_evaluations": under_budget,
           "note": "systems with fewer evaluated candidates than the budget (build / evaluation failures) are listed: their search was "
                   "weaker than specified, which favours the model"}
    real = {s: v for s, v in per.items() if v["kind"] == "real"}
    out = {**C.marks_of(record), "run_id": record["run_id"], "method": record["method"], "tier": record["tier"],
           "real_level": record.get("real_level"),
           "budget": record["budget"], "rounds": record["rounds"], "Q19": q19, "per_system": per,
           "real_systems": {s: {"found": v["found"], "n_counterexamples": v["n_counterexamples"]} for s, v in real.items()}}
    C.dump_json(out, rd.out / "COUNTEREXAMPLES.json")
    L = [f"# Counterexample search: `{record['method']}` ({record['tier']}; run {record['run_id']})", ""] + C.dry_banner(record) + [
         f"**Q19: {q19['status']}** - counterexamples on {q19['n_found']} of {q19['n_systems']} compressible systems "
         f"(share {q19['share_found'] if share is None else f'{share:.2f}'}; pass rule <= {PASS_SHARE:.0%}); budget {record['budget']} "
         f"per system in rounds {record['rounds']}.", "", "| system | evaluated | eligible | counterexamples | first at | best EE_i |",
         "|---|---|---|---|---|---|"]
    for s, v in sorted(per.items()):
        L.append(f"| {s} | {v['n_evaluated']} | {v['n_eligible']} | {v['n_counterexamples']} | {v['first_found_at'] or '-'} | "
                 f"{'-' if not v['best'] or v['best']['ee_i'] is None else round(v['best']['ee_i'], 3)} |")
    (rd.out / "COUNTEREXAMPLES.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--method", required=True)
    r.add_argument("--tier", default=None)
    r.add_argument("--real", default=None, choices=[None, "public", "C"])
    r.add_argument("--systems", default="")
    r.add_argument("--methods-dir", default=None)
    r.add_argument("--fits-from", default=None, help="a directory of the studies' layout with fits/<sid>_s<seed>.pkl (dry runs)")
    r.add_argument("--levelc-run", default=None, help="the Level C run directory (post-lock: its primary fits fit__<sid>__s<seed>)")
    r.add_argument("--seed", default="0")
    r.add_argument("--budget", type=int, default=50)
    r.add_argument("--rounds", default="20,15,15")
    r.add_argument("--run-id", default=None)
    r.add_argument("--n-boot", type=int, default=200)
    r.add_argument("--build-workers", type=int, default=16)
    r.add_argument("--max-containers", type=int, default=40)
    r.add_argument("--dry-run-on-val", action="store_true", help="BEFORE the lock only: a stand-in dry run on the Level B val tier")
    r.add_argument("--exclude-families", default="", help="families left out of the search (recorded; e.g. kinds a generator under revision cannot build)")
    r.add_argument("--unpacked", action="store_true")
    r.add_argument("--new-run-reason", default=None)
    s = sub.add_parser("summarize")
    s.add_argument("--run-id", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    for root in (C.OUT_ROOT, C.DRY_ROOT):
        p = root / STUDY / args.run_id / "RUN.json"
        if p.exists():
            rec = C.load_json(p)
            print(json.dumps(summarize(C.RunDirs(STUDY, args.run_id, bool(rec.get("hidden"))), rec)["Q19"], indent=1))
            return 0
    raise SystemExit(f"no run {args.run_id}")


if __name__ == "__main__":
    raise SystemExit(main())
