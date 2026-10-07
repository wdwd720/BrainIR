"""Post-lock ABLATION study of the locked method (goal5 sections 87-89; SELF_AUDIT_PLAN Q20 / Q21). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/ablations_p4.py run --method NAME --tier conf --real C [--seeds 0]
        [--levelc-run DIR] [--fullstate-baseline NAME] [--phase3-baseline frozen_brainir_state_v1] [--run-id ID]
    uv run --no-sync --project phase4 python scripts/p4/ablations_p4.py run --method p3stand.refstand:p3stand_ref --tier dev
        --methods-dir scripts/p4/standin_methods --fullstate-baseline p3stand.refstand:p3stand_fullstate --run-id dry1   # DRY RUN
    uv run --no-sync --project phase4 python scripts/p4/ablations_p4.py summarize --run-id ID [--tier ...]

CONTRACT (brainir_causal.api; p4post.declare). The method declares in info()["ablation_switches"] every name of
api.ABLATION_SWITCHES (honoured, or not applicable with a reason) and applies config["ablate"]; info()["ablated"] repeats the applied
list. The study runs ONE fit per declared-honoured switch and system (plus the full method) and FAILS LOUDLY (exit 3, nothing
summarised) on a switch that is neither honoured nor declared not applicable, on a declaration without a reason, and on an ablated fit
whose info()["ablated"] differs from the requested switch.

DESIGN.
1. Full fits (reused from the Level C run when given: the same fits the confirmatory evaluation used) and, in the SAME wave,
   speculative ablated fits for every switch of the vocabulary except active_design (a switch later found not applicable is
   discarded, never evaluated): one wave of fits instead of two (the declarations are only known from a fitted model).
2. THE CRITICAL ABLATION (interventional_training, goal5 section 88) is enforced at the DATA level as well: the trusted driver hands the
   worker the passive records only (every record with events and every twin dropped; `isojob.fit_passive` records counts and a digest
   of the kept keys), so the ablation holds whatever the method's own switch does; the method's switch is set too.
3. active_design is loop-level (own designer vs the benchmark's random designer at the same budgets): read from the Level C loops
   (PROTOCOL 5.17) when the method declares it honoured; not refitted here.
4. Every honoured ablated fit, the full fits (unless reused), the Phase 3 baseline (frozen_brainir_state_v1: "should approximately
   recover the Phase 3-style regime", section 88) and the Level B best full-state baseline (section 89) are evaluated with the
   benchmark's unchanged evaluation (all families) in model workers.
5. Statistics (p4post.pairstats, PROTOCOL 11): per switch and metric, the paired suite difference ablated - full over the compressible
   synthetic systems (unstratified system bootstrap; a missing value on either side charged NEUTRALLY, so a crashed fit is no evidence
   either way) and per real network the paired identity-cell EE difference; one-sided p for "the ablation is worse", Holm across
   switches per metric (descriptive, labelled). Missing values are always charged AGAINST the claim under test and counted.
   Q20 (critical, section 88): PASS when removing interventional training worsens the verdict EE significantly (suite one-sided
   p <= 0.05, i.e. the one-sided 95 % lower bound of mean(EE_ablated - EE_full) > 0; a missing ablated value neutral, a missing value
   of the full method at its worst); otherwise "Phase 4's core hypothesis fails"; NOT TESTABLE without compressible synthetic systems.
   Q21 (critical, section 89; the operationalisation fixed here before the lock): DIRECT predicts = suite mean EE of the no-bottleneck
   variant has a one-sided 95 % upper bound < 1 - delta_A; COMPACT predicts = the same for the locked method AND mean(EE_M - EE_direct)
   has a one-sided 95 % upper bound < delta_C_suite (suite means charge a missing value at its worst; in the difference a missing
   value of the locked method is at its worst, a missing direct value neutral). Report "intervention outcomes are predictable, but compact causal abstraction
   unsupported" when DIRECT predicts and COMPACT does not; "the compact state suffices" when both; "not predictable even without the
   bottleneck (excitation / data; goal5 94 B)" when DIRECT does not. The same with the Level B full-state baseline in place of the
   direct variant is reported beside.
Outputs: <out>/ABLATIONS.json, ABLATIONS.md (post-lock: research/phase4/postlock/ablations/<run>/, ANSWER-BEARING), bulky fits and
evaluations under C:/Dev/BrainIR_p4run/postlock/ablations/<run>/. Hidden runs are logged START / DONE.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p4"))
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from p4post import common as C  # noqa: E402
from p4post import declare as D  # noqa: E402
from p4post import execute as X  # noqa: E402
from p4post import pairstats as PS  # noqa: E402

STUDY = "ablations"
FULL = "full"
SUMMARY_METRICS = ("EE", "EE_heldout", "EE_target", "post_nmse", "obs_nmse", "SMS", "ICG_y", "MEV", "lift_success", "lift_consistency",
                   "false_confidence", "coverage", "k")


def variant_of(switch: str) -> str:
    return f"abl_{switch}"


def _systems_kinds(systems: dict) -> tuple[list, list]:
    syn = sorted(s for s, d in systems.items() if d["kind"] == "synthetic")
    real = sorted(s for s, d in systems.items() if d["kind"] == "real")
    return syn, real


def _compressible(run: Path, variant: str, syn: list[str], seed: int) -> list[str]:
    """Synthetic systems whose truth is compressible (the evaluation output's truth summary; a system without it counts)."""
    out = []
    for s in syn:
        ev = X.load_eval(run, variant, s, seed)
        if ev is None or not ev.get("truth_noncompressible"):
            out.append(s)
    return out


def cmd_run(args) -> int:
    t0 = time.time()
    real_level = args.real or None
    extra_methods = {"phase3": args.phase3_baseline, "fullstate_baseline": args.fullstate_baseline}
    extra_methods = {k: v for k, v in extra_methods.items() if v}
    g = C.guard(args.tier, real_level, what="the ablation study", dry_run_on_val=args.dry_run_on_val,
                methods=[args.method] + list(extra_methods.values()), methods_dir=args.methods_dir)
    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%S")
    rd = C.RunDirs(STUDY, run_id, g["hidden"])
    methods_dir = Path(args.methods_dir) if args.methods_dir else C.LOCKED_METHODS
    if not g["hidden"] and not args.methods_dir:
        raise SystemExit("a dry run needs --methods-dir (the locked package exists only after the lock)")
    mdir = rd.run / "methods"
    mhash = C.snapshot_methods(methods_dir, mdir)
    systems = C.resolve_systems(args.tier, real_level, [s for s in (args.systems or "").split(",") if s] or None)
    syn, real = _systems_kinds(systems)
    seeds = [int(s) for s in args.seeds.split(",") if s]
    switches = [s for s in D.ABLATION_SWITCHES if s != "active_design"] if args.switches == "all" else [s for s in args.switches.split(",") if s]
    unknown = [s for s in switches if s not in D.ABLATION_SWITCHES]
    if unknown:
        raise SystemExit(f"unknown switches {unknown}")
    record = {"study": STUDY, "run_id": run_id, "created_utc": C.utc(), **C.run_marks(g, args.tier, real_level), "hidden": g["hidden"],
              "lock": g["lock"], "method": args.method, "methods_dir": str(methods_dir), "method_hashes": mhash, "systems": sorted(systems),
              "seeds": seeds, "switches_requested": switches, "extra_methods": extra_methods, "levelc_run": args.levelc_run,
              "max_containers": args.max_containers, "modal": {}}
    C.dump_json(record, rd.out / "RUN.json")
    synthetic = bool(syn)
    packed = not args.unpacked
    classes = X.classes_for(bool(real), packed)
    if g["hidden"]:
        record["ledger"] = C.ledger_claim(STUDY, run_id, new_run_reason=args.new_run_reason)
    with C.HiddenRunLog(g["hidden"], STUDY, run_id, f"{args.method} on {args.tier}/{real_level}: {len(systems)} systems"):
        with C.backend(classes, synthetic=synthetic, app_name="brainir-p4-post-ablations", max_containers=args.max_containers) as be:
            key = be.methods_key(mdir)
            devices = X.describe(be, [args.method] + list(extra_methods.values()), key, packed=packed)
            record["devices"] = devices
            if any(str(d).startswith("error") for d in devices.values()):
                raise SystemExit(f"method description failed: {devices}")
            if any(d == "cuda" for d in devices.values()):
                raise SystemExit("GPU methods: add the iso GPU class to the backend (not needed for the dry run)")
            # ---- wave 1: full fits (or reuse) + speculative ablated fits + comparators
            fit_specs = []
            for sid, sysd in systems.items():
                for seed in seeds:
                    reused = _reuse_full(args, rd.run, sid, seed)
                    # --large-fits, or a reused Level C model above the inline limit: the method's fits go straight to the unpacked
                    # volume-writing tier (p4post.execute: the packed tier would return them as too large)
                    large = bool(args.large_fits) or (reused and X.model_path(rd.run, FULL, sid, seed).stat().st_size > C.INLINE_MAX)
                    if not reused:
                        fit_specs.append({"variant": FULL, "method": args.method, "sid": sid, "sysd": sysd, "seed": seed, "config": {},
                                          "large": large})
                    for sw in switches:
                        fit_specs.append({"variant": variant_of(sw), "method": args.method, "sid": sid, "sysd": sysd, "seed": seed,
                                          "config": {"ablate": [sw]}, "passive": sw == "interventional_training", "large": large})
                    for label, m in extra_methods.items():
                        if not _reuse_baseline(args, rd.run, label, m, sid, seed):
                            fit_specs.append({"variant": label, "method": m, "sid": sid, "sysd": sysd, "seed": seed, "config": {}})
            tf = time.time()
            fits = X.run_fits(be, fit_specs, key=key, run=rd.run, timeout_s=args.timeout, devices=devices, refit=args.refit, packed=packed)
            record["modal"]["fits_wall_s"] = X.wall(tf)
            record["n_fits"] = len(fit_specs)
            record["n_fit_failures_all"] = sum(1 for v in fits.values() if not v.get("ok"))
            # ---- the contract: declarations of the full fits, application of every honoured switch. A CONTRACT violation stops the
            # study (exit 3); a fit that CRASHED is a method failure: recorded, its system charged in the statistics (never dropped)
            decls, problems, failures = {}, [], []
            for sid in systems:
                side = X.fit_side(rd.run, FULL, sid, seeds[0])
                if side is None:
                    failures.append({"system": sid, "variant": FULL, "error": (X.fit_error(rd.run, FULL, sid, seeds[0]) or "")[:500]})
                    continue
                try:
                    decls[sid] = D.check_declaration(side.get("info"), f"{args.method} on {sid}")
                except D.AblationContractError as e:
                    problems.append(str(e))
            if not decls and not problems:
                problems.append("no full fit succeeded: the declarations cannot be checked")
            plan = D.switch_plan(decls) if decls else {}
            eval_specs = []
            if not problems:
                for sid, sysd in systems.items():
                    for seed in seeds:
                        if sid in decls:
                            eval_specs.append({"variant": FULL, "sid": sid, "sysd": sysd, "seed": seed})
                        for label in extra_methods:
                            eval_specs.append({"variant": label, "sid": sid, "sysd": sysd, "seed": seed})
                        for sw in switches:
                            if sid not in decls or decls[sid][sw]["status"] != D.HONOURED:
                                continue
                            side = X.fit_side(rd.run, variant_of(sw), sid, seed)
                            if side is None:
                                failures.append({"system": sid, "variant": variant_of(sw),
                                                 "error": (X.fit_error(rd.run, variant_of(sw), sid, seed) or "")[:500]})
                                continue
                            try:
                                D.check_applied(side.get("info"), [sw], decls[sid], f"{args.method} ablate={sw} on {sid}")
                            except D.AblationContractError as e:
                                problems.append(str(e))
                                continue
                            if sw == "interventional_training" and (side.get("passive_view") or {}).get("n_kept_with_events", 1) != 0:
                                problems.append(f"{sid}: the passive-only data rule was not applied to the interventional_training fit")
                                continue
                            eval_specs.append({"variant": variant_of(sw), "sid": sid, "sysd": sysd, "seed": seed})
            record["declarations"] = decls
            record["switch_plan"] = plan
            record["contract_problems"] = problems
            record["fit_failures"] = failures
            # speculative fits of switches a system declared NOT APPLICABLE are discarded (never evaluated), whatever their outcome
            disc = [(sid, sw, bool((fits.get((variant_of(sw), sid, seeds[0])) or {}).get("ok")))
                    for sid in decls for sw in switches if decls[sid][sw]["status"] == D.NOT_APPLICABLE]
            record["discarded_speculative_fits"] = {"n": len(disc), "n_failed": sum(1 for d in disc if not d[2]),
                                                    "switches": sorted({d[1] for d in disc})}
            relevant = [k for k in fits if not (k[1] in decls and k[0].startswith("abl_") and
                                                decls[k[1]].get(k[0][4:], {}).get("status") == D.NOT_APPLICABLE)]
            record["n_fit_failures"] = sum(1 for k in relevant if not fits[k].get("ok"))
            if problems:
                record["status"] = "FAILED: ablation contract"
                record["wall_s"] = X.wall(t0)
                record["modal"]["cost"] = be.cost_summary()
                C.dump_json(record, rd.out / "RUN.json")
                print("ABLATION CONTRACT VIOLATED:\n  " + "\n  ".join(problems[:40]), flush=True)
                return 3
            # ---- wave 2: evaluations
            te = time.time()
            evals = X.run_evals(be, eval_specs, key=key, run=rd.run, lift=not args.no_lift, n_boot=args.n_boot, refit=args.refit,
                                packed=packed)
            record["modal"]["evals_wall_s"] = X.wall(te)
            record["n_evals"] = len(eval_specs)
            record["n_eval_failures"] = sum(1 for v in evals.values() if not v.get("ok"))
            record["modal"]["cost"] = be.cost_summary()
    record["status"] = "complete"
    record["wall_s"] = X.wall(t0)
    C.dump_json(record, rd.out / "RUN.json")
    summary = summarize(rd, record)
    print(json.dumps({"run": run_id, "wall_s": record["wall_s"], "fits": record["n_fits"], "fit_failures": record["n_fit_failures"],
                      "evals": record["n_evals"], "eval_failures": record["n_eval_failures"],
                      "usd": (record["modal"].get("cost") or {}).get("usd_approx_total"), "Q20": summary["Q20"]["status"],
                      "Q21": summary["Q21"]["report"]}, indent=1), flush=True)
    return 0


def _reuse_full(args, run: Path, sid: str, seed: int) -> bool:
    """Copy the Level C run's primary fit (fit__<sid>__s<seed>: model bytes and side record) and, for seed 0, its evaluation
    (eval__<sid>) into this run: the SAME fit the confirmatory evaluation scored. False when the Level C run lacks them."""
    if not args.levelc_run:
        return False
    import pickle
    from p4post.levelc_io import LevelCStore
    st = LevelCStore(args.levelc_run)
    mp, side = st.fit_model(sid, seed), st.fit_side(sid, seed)
    if mp is None or side is None:
        return False
    X.model_path(run, FULL, sid, seed).write_bytes(mp.read_bytes())
    C.dump_json(dict(side, variant=FULL, reused_from=f"{args.levelc_run}:fit__{sid}__s{seed}"), X.model_path(run, FULL, sid, seed).with_suffix(".json"))
    ev = st.method_eval(sid) if seed == 0 else None
    if ev is not None:
        # the confirmatory evaluation of the same model; when the Level C run has not evaluated it yet, this study evaluates the same
        # model bytes itself (the evaluation is deterministic given the model, the items and the seed), so it never waits for it
        with open(X._paths(run, FULL, sid, seed, "evals").with_suffix(".pkl"), "wb") as fh:
            pickle.dump(ev, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return True


def _reuse_baseline(args, run: Path, label: str, method: str, sid: str, seed: int) -> bool:
    """A comparator (Phase 3 baseline, full-state baseline) evaluated in the Level C run is reused (bfit / beval of that name)."""
    if not args.levelc_run or seed != 0:
        return False
    import pickle
    from p4post.levelc_io import LevelCStore, safe
    st = LevelCStore(args.levelc_run)
    ev, side = st.baseline_eval(sid, method), st.baseline_side(sid, method)
    mp = st.model_path(f"bfit__{safe(sid)}__{safe(method)}")
    if ev is None or side is None or not mp.exists():
        return False
    X.model_path(run, label, sid, seed).write_bytes(mp.read_bytes())
    C.dump_json(dict(side, variant=label, reused_from=f"{args.levelc_run}:bfit__{sid}__{method}"), X.model_path(run, label, sid, seed).with_suffix(".json"))
    with open(X._paths(run, label, sid, seed, "evals").with_suffix(".pkl"), "wb") as fh:
        pickle.dump(ev, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return True


# ================================================================================================================ summary
_METRICS: dict = {}          # (run, variant, sid, seed) -> {metric: value}: each evaluation file is read once per summary, not per metric


def _vals(run: Path, variant: str, sids: list[str], seed: int, metric: str) -> dict:
    out = {}
    for s in sids:
        key = (str(run), variant, s, seed)
        got = _METRICS.get(key)
        if got is None or metric not in got:
            res = (X.load_eval(run, variant, s, seed) or {}).get("result")
            got = {m: PS.metric(res, m) for m in set(SUMMARY_METRICS) | {metric}}
            _METRICS[key] = got
        out[s] = got[metric]
    return out


def summarize(rd: C.RunDirs, record: dict, n_boot: int = PS.N_BOOT) -> dict:
    run, seed = rd.run, int(record["seeds"][0])
    systems = C.resolve_systems(record["tier"], record.get("real_level"), record["systems"])
    syn, real = _systems_kinds(systems)
    comp = _compressible(run, FULL, syn, seed)
    full_networks = [s for s in real if ":full" in s] or real
    mg = C.margins()
    tol, suite_m = mg["tolerances"], mg["suite"]
    decls = record.get("declarations") or {}
    honoured = [sw for sw in record["switches_requested"] if decls and all(d[sw]["status"] == D.HONOURED for d in decls.values())]
    partly = [sw for sw in record["switches_requested"] if decls and sw not in honoured and any(d[sw]["status"] == D.HONOURED for d in decls.values())]
    out: dict = {**C.marks_of(record), "run_id": record["run_id"], "method": record["method"], "tier": record["tier"],
                 "real_level": record.get("real_level"),
                 "n_systems": len(systems), "compressible": comp, "full_networks": full_networks, "seed": seed, "margins": mg,
                 "switches": {}, "not_applicable": {}, "descriptive_note": "per-switch tests are descriptive (Holm across switches per "
                                                                        "metric reported); Q20 / Q21 are the pre-registered critical tests"}
    for sw in record["switches_requested"]:
        if sw not in honoured and sw not in partly:
            out["not_applicable"][sw] = sorted({d[sw]["reason"] for d in decls.values()}) if decls else []
    base = {m: _vals(run, FULL, syn + real, seed, m) for m in SUMMARY_METRICS}
    pvals: dict[str, dict] = {m: {} for m in SUMMARY_METRICS}
    for sw in honoured + partly:
        v = variant_of(sw)
        row = {"honoured_on": sorted(s for s, d in decls.items() if d[sw]["status"] == D.HONOURED), "metrics": {}, "networks": {}}
        for m in SUMMARY_METRICS:
            direction, worst, desc = PS.METRICS[m]
            av = _vals(run, v, syn + real, seed, m)
            if direction == "none":
                row["metrics"][m] = {"full": {s: base[m].get(s) for s in comp}, "ablated": {s: av.get(s) for s in comp}}
                continue
            sp = PS.suite_paired(av, base[m], comp, worst=worst, direction=direction, n_boot=n_boot, seed=17,
                                 missing_a="neutral", missing_b="neutral") if comp else None
            row["metrics"][m] = {"suite_paired_ablated_minus_full": sp, "description": desc}
            if sp and sp.get("point") is not None:
                pvals[m][sw] = sp["p_a_worse"]
        for net in real:
            row["networks"][net] = PS.system_ee_diff((X.load_eval(run, v, net, seed) or {}).get("result"),
                                                     (X.load_eval(run, FULL, net, seed) or {}).get("result"), n_boot=n_boot, seed=23)
        out["switches"][sw] = row
    for m, ps in pvals.items():
        if ps:
            h = PS.holm(ps)
            for sw in ps:
                out["switches"][sw]["metrics"][m]["suite_paired_ablated_minus_full"]["p_holm_across_switches"] = h["adjusted"][sw]
    out["Q20"] = q20(run, comp, full_networks, seed, honoured + partly, n_boot)
    out["Q21"] = q21(run, comp, full_networks, seed, honoured + partly, tol, suite_m, record, n_boot)
    out["phase3_regime"] = phase3_regime(run, comp, seed, honoured + partly, record, n_boot)
    C.dump_json(PS.strip_private(out), rd.out / "ABLATIONS.json")
    (rd.out / "ABLATIONS.md").write_text(render_md(out), encoding="utf-8", newline="\n")
    return out


def q20(run: Path, comp: list, nets: list, seed: int, avail: list, n_boot: int) -> dict:
    sw = "interventional_training"
    if sw not in avail:
        return {"status": "NOT TESTABLE", "reason": "the method does not honour interventional_training on every system (contract)"}
    a = _vals(run, variant_of(sw), comp, seed, "EE")
    b = _vals(run, FULL, comp, seed, "EE")
    # charges AGAINST the claim under test ("the ablation is worse"): a crashed / missing ablated value is neutral (no evidence), a
    # missing value of the full method is its worst value
    sp = PS.suite_paired(a, b, comp, worst=10.0, direction="lower", n_boot=n_boot, seed=31, missing_a="neutral",
                         missing_b="worst") if comp else None
    nets_rows = {n: PS.system_ee_diff((X.load_eval(run, variant_of(sw), n, seed) or {}).get("result"),
                                      (X.load_eval(run, FULL, n, seed) or {}).get("result"), n_boot=n_boot, seed=37) for n in nets}
    if sp is None or sp.get("p_a_worse") is None:
        return {"status": "NOT TESTABLE", "reason": "no compressible synthetic system (the suite test needs them)", "suite": sp,
                "real_full_networks": nets_rows}
    passed = sp["p_a_worse"] <= PS.ALPHA
    return {"status": "PASS" if passed else "FAIL", "rule": "removing interventional training worsens the verdict EE significantly "
            "(paired suite difference EE_ablated - EE_full, unstratified system bootstrap, one-sided p <= 0.05; a missing ablated "
            "value is charged neutrally, a missing full-method value at its worst)",
            "suite": sp, "real_full_networks": nets_rows,
            "consequence_if_fail": "Phase 4's core hypothesis fails (goal5 section 88)"}


def q21(run: Path, comp: list, nets: list, seed: int, avail: list, tol: dict, suite_m: dict, record: dict, n_boot: int) -> dict:
    sw = "state_bottleneck"
    if sw not in avail:
        return {"report": "NOT TESTABLE", "reason": "the method does not honour state_bottleneck on every system (contract)"}
    thr_pred = 1.0 - float(tol["delta_A"])
    thr_near = float(suite_m["delta_C_suite"])
    m = _vals(run, FULL, comp, seed, "EE")

    def arm(variant: str) -> dict:
        d = _vals(run, variant, comp, seed, "EE")
        sd = PS.suite_mean(d, comp, worst=10.0, n_boot=n_boot, seed=41)
        sm = PS.suite_mean(m, comp, worst=10.0, n_boot=n_boot, seed=43)
        # a missing value of the locked method counts against "compact near direct" (worst); a missing direct value is neutral
        diff = PS.suite_paired(m, d, comp, worst=10.0, direction="lower", n_boot=n_boot, seed=47, missing_a="worst", missing_b="neutral")
        direct = bool(sd.get("upper95") is not None and sd["upper95"] < thr_pred)
        compact = bool(sm.get("upper95") is not None and sm["upper95"] < thr_pred and diff.get("upper95") is not None
                       and diff["upper95"] < thr_near)
        if direct and not compact:
            rep = "intervention outcomes are predictable, but compact causal abstraction unsupported"
        elif direct and compact:
            rep = "the compact state suffices (the bottleneck costs less than delta_C_suite)"
        else:
            rep = "outcomes not predictable even without the bottleneck (attributed to excitation / data; goal5 section 94 B)"
        nets_rows = {n: {"EE_direct": PS.metric((X.load_eval(run, variant, n, seed) or {}).get("result"), "EE"),
                         "EE_M_minus_direct": PS.system_ee_diff((X.load_eval(run, FULL, n, seed) or {}).get("result"),
                                                                (X.load_eval(run, variant, n, seed) or {}).get("result"), n_boot=n_boot,
                                                                seed=53)} for n in nets}
        return {"direct_predicts": direct, "compact_predicts_near_direct": compact, "report": rep, "EE_direct_suite": sd,
                "EE_M_suite": sm, "EE_M_minus_direct_suite": diff, "real_full_networks": nets_rows}
    out = {"thresholds": {"predicts": f"one-sided 95 % upper bound of the suite mean EE < 1 - delta_A = {thr_pred:.4g}",
                          "near": f"one-sided 95 % upper bound of mean(EE_M - EE_direct) < delta_C_suite = {thr_near:.4g}"},
           "direct_variant": arm(variant_of(sw))}
    out["report"] = out["direct_variant"]["report"]
    if record.get("extra_methods", {}).get("fullstate_baseline"):
        out["levelb_fullstate_baseline"] = {"method": record["extra_methods"]["fullstate_baseline"], **arm("fullstate_baseline")}
    return out


def phase3_regime(run: Path, comp: list, seed: int, avail: list, record: dict, n_boot: int) -> dict:
    """Section 88: the passive-only ablation 'should approximately recover the Phase 3-style regime': EE of the ablated method vs the
    frozen Phase 3 method (descriptive)."""
    if "interventional_training" not in avail or not record.get("extra_methods", {}).get("phase3"):
        return {"note": "not run"}
    a = _vals(run, variant_of("interventional_training"), comp, seed, "EE")
    b = _vals(run, "phase3", comp, seed, "EE")
    return {"phase3_method": record["extra_methods"]["phase3"], "EE_ablated_minus_phase3": PS.suite_paired(a, b, comp, worst=10.0,
                                                                                                      n_boot=n_boot, seed=59),
            "EE_ablated": PS.suite_mean(a, comp, worst=10.0, n_boot=n_boot), "EE_phase3": PS.suite_mean(b, comp, worst=10.0, n_boot=n_boot)}


def _fmt(x, nd=3) -> str:
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}g}"
    return str(x)


def render_md(s: dict) -> str:
    L = [f"# Ablations of `{s['method']}` ({s['tier']}{' + real ' + str(s['real_level']) if s.get('real_level') else ''}; run {s['run_id']})", ""]
    L += C.dry_banner(s)
    L += [
         f"{s['n_systems']} systems; {len(s['compressible'])} compressible synthetic systems enter the suite statistics; tolerances "
         f"{'calibrated' if s['margins']['calibrated'] else 'PROVISIONAL (no calibration yet)'}.", "",
         "## Critical ablations", "",
         f"- **Q20 interventional training** (goal5 88): **{s['Q20']['status']}**. " + (
             f"Suite mean EE_ablated - EE_full = {_fmt((s['Q20'].get('suite') or {}).get('point'))} "
             f"(one-sided 95 % lower bound {_fmt((s['Q20'].get('suite') or {}).get('lower95'))}, p = {_fmt((s['Q20'].get('suite') or {}).get('p_a_worse'))})."
             if s["Q20"].get("suite") else s["Q20"].get("reason", "")),
         f"- **Q21 state bottleneck** (goal5 89): **{s['Q21'].get('report')}**.", ""]
    L += ["## Per switch (suite paired difference ablated - full; positive = the ablation is worse for lower-is-better metrics)", "",
          "| switch | EE | EE held-out | SMS | ICG_y | MEV | lift success | false confidence | Holm p (EE) |", "|---|---|---|---|---|---|---|---|---|"]
    for sw, row in s["switches"].items():
        def cell(m):
            sp = (row["metrics"].get(m) or {}).get("suite_paired_ablated_minus_full") or {}
            if sp.get("point") is None:
                return "-"
            return f"{_fmt(sp['point'])} [{_fmt((sp.get('ci95') or [None, None])[0])}, {_fmt((sp.get('ci95') or [None, None])[1])}]"
        hp = ((row["metrics"].get("EE") or {}).get("suite_paired_ablated_minus_full") or {}).get("p_holm_across_switches")
        L.append(f"| {sw} | {cell('EE')} | {cell('EE_heldout')} | {cell('SMS')} | {cell('ICG_y')} | {cell('MEV')} | {cell('lift_success')} | "
                 f"{cell('false_confidence')} | {_fmt(hp)} |")
    if s["not_applicable"]:
        L += ["", "Declared not applicable: " + "; ".join(f"{k} ({'; '.join(v)})" for k, v in s["not_applicable"].items())]
    L += ["", "Descriptive: per-switch rows are not part of the primary family; Holm across switches is reported per metric."]
    return "\n".join(L) + "\n"


def cmd_summarize(args) -> int:
    rec = None
    for root in (C.OUT_ROOT, C.DRY_ROOT):
        p = root / STUDY / args.run_id / "RUN.json"
        if p.exists():
            rec = C.load_json(p)
            break
    if rec is None:
        raise SystemExit(f"no run {args.run_id}")
    rd = C.RunDirs(STUDY, args.run_id, bool(rec.get("hidden")))
    s = summarize(rd, rec)
    print(json.dumps({"Q20": s["Q20"]["status"], "Q21": s["Q21"].get("report")}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--method", required=True)
    r.add_argument("--tier", default=None)
    r.add_argument("--real", default=None, choices=[None, "public", "C"])
    r.add_argument("--systems", default="")
    r.add_argument("--methods-dir", default=None)
    r.add_argument("--seeds", default="0")
    r.add_argument("--switches", default="all")
    r.add_argument("--run-id", default=None)
    r.add_argument("--levelc-run", default=None)
    r.add_argument("--fullstate-baseline", default=None)
    r.add_argument("--phase3-baseline", default="frozen_brainir_state_v1")
    r.add_argument("--max-containers", type=int, default=40)
    r.add_argument("--dry-run-on-val", action="store_true", help="BEFORE the lock only: a stand-in dry run on the Level B val tier")
    r.add_argument("--unpacked", action="store_true", help="unpacked iso classes (one job per container) instead of the packed ones")
    r.add_argument("--new-run-reason", default=None, help="a logged reason for a second official run (goal5 section 70)")
    r.add_argument("--timeout", type=float, default=3600)
    r.add_argument("--n-boot", type=int, default=2000)
    r.add_argument("--no-lift", action="store_true")
    r.add_argument("--refit", action="store_true")
    r.add_argument("--large-fits", action="store_true", help="the method's models exceed the 1.5 MB inline limit: fit on the unpacked "
                   "volume-writing tier directly")
    s = sub.add_parser("summarize")
    s.add_argument("--run-id", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "run":
        if args.phase3_baseline in ("", "none"):
            args.phase3_baseline = None
        return cmd_run(args)
    return cmd_summarize(args)


if __name__ == "__main__":
    raise SystemExit(main())
