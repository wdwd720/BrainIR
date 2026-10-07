"""Post-lock COUNTERFACTUAL API evaluation (goal5 section 90). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/counterfactual_p4.py run --method NAME --tier conf [--real C] --fits-from DIR
        [--run-id ID]
    uv run --no-sync --project phase4 python scripts/p4/counterfactual_p4.py run --method p3stand.refstand:p3stand_ref --tier dev
        --methods-dir scripts/p4/standin_methods --fits-from C:/Dev/BrainIR_p4run/postlock/ablations/dry1/full --run-id dry1   # DRY RUN

"For observed x_t and candidate intervention a: return predicted y_future under a, uncertainty, validity, latent trajectory, effect
relative to no intervention. Evaluate against simulator." The candidate interventions are the tier's held-out intervention items
(every role: verdict, OOD and robustness items), whose true futures and twins the benchmark simulated. `p4post.isojob.predict_detail`
calls the model's `intervention_effect` on each item in model workers (histories up to the onset only), scores it with the
benchmark's evaluator, probes the RAW output of the first N_PROBE items, and in phase C re-encodes the true futures (closure).

COMPLETENESS (per API field, the share of items for which it is returned and well formed): y_int (the future under a), y_base, effect
(== y_int - y_base), uncertainty (y_sd or an uncertainty record), validity (in_domain and score), z_int / z_base (latent
trajectories of the right shape, finite), the abstention flag. A field counts as COMPLETE when it is well formed on >= 95 % of the
probed items of every system (fixed here before the lock; a model may legitimately omit y_sd, which is then reported as "no
uncertainty", scored as confident everywhere by 5.9).
ACCURACY against the simulator (per system; suite means with an unstratified system bootstrap; real systems per system):
- future under a: post-intervention trajectory NMSE (5.1) and the realised RMS error of y_int;
- effect: class-balanced EE on the verdict items, pooled EE on all items, sign accuracy (5.1);
- uncertainty: 90 % interval coverage and its calibration error per horizon, Brier scores of p_detectable / p_sign (5.9), the rank
  correlation of the predicted sd with the realised error;
- validity: the AUC of the validity score for detecting EE_i > 1 (5.12) and EE inside vs outside the claimed domain;
- latent trajectory: the interventional closure gap ICG_y (5.4: the predicted latent rollout against re-encoded true futures);
- abstention: coverage and the false-confidence rate (5.9).
Outputs: <out>/COUNTERFACTUAL_API.json / .md (post-lock: research/phase4/postlock/counterfactual/<run>/, ANSWER-BEARING).
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
from p4post import pairstats as PS  # noqa: E402

STUDY = "counterfactual"
N_PROBE = 24
COMPLETE_SHARE = 0.95
FIELDS = ("y_int", "y_base", "effect", "uncertainty", "validity", "z_trajectory", "abstain_flag")


def cmd_run(args) -> int:
    t0 = time.time()
    real_level = args.real or None
    g = C.guard(args.tier, real_level, what="the counterfactual API evaluation", dry_run_on_val=args.dry_run_on_val, methods=[args.method],
                methods_dir=args.methods_dir)
    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%S")
    rd = C.RunDirs(STUDY, run_id, g["hidden"])
    methods_dir = Path(args.methods_dir) if args.methods_dir else C.LOCKED_METHODS
    mhash = C.snapshot_methods(methods_dir, rd.run / "methods")
    systems = C.resolve_systems(args.tier, real_level, [s for s in (args.systems or "").split(",") if s] or None)
    seed = int(args.seed)
    from p4post.levelc_io import model_source
    if not (args.fits_from or args.levelc_run):
        raise SystemExit("give --levelc-run (post-lock: the Level C fits) or --fits-from (dry runs)")
    models = {s: model_source(s, seed, fits_from=args.fits_from, levelc_run=args.levelc_run) for s in systems}
    missing = sorted(s for s, p in models.items() if p is None)
    if missing:
        raise SystemExit(f"no fitted model for {len(missing)} systems (e.g. {missing[:3]})")
    record = {"study": STUDY, "run_id": run_id, "created_utc": C.utc(), **C.run_marks(g, args.tier, real_level), "hidden": g["hidden"],
              "lock": g["lock"], "method": args.method, "method_hashes": mhash, "fits_from": str(args.fits_from), "levelc_run": args.levelc_run, "seed": seed,
              "systems": sorted(systems), "n_probe": args.n_probe, "modal": {}}
    C.dump_json(record, rd.out / "RUN.json")
    synthetic = any(d["kind"] == "synthetic" for d in systems.values())
    real = any(d["kind"] == "real" for d in systems.values())
    packed = not args.unpacked
    classes = [X.PACK_EVAL] if packed else sorted({"iso_eval_s"} | ({"iso_eval_l"} if real else set()))
    if g["hidden"]:
        record["ledger"] = C.ledger_claim(STUDY, run_id, new_run_reason=args.new_run_reason)
    with C.HiddenRunLog(g["hidden"], STUDY, run_id, f"{args.method} on {args.tier}/{real_level}: {len(systems)} systems"):
        with C.backend(classes, synthetic=synthetic, app_name="brainir-p4-post-cfapi", max_containers=args.max_containers) as be:
            key = be.methods_key(rd.run / "methods")
            specs = []
            for s, sysd in systems.items():
                job = C.eval_job(s, sysd, lift=False, n_boot=args.n_boot, seed=seed)
                job.update({"closure": True, "n_probe": args.n_probe, "call_timeout_s": 900})
                specs.append({"sid": s, "sysd": sysd, "job": job, "model_path": models[s]})
            te = time.time()
            res = X.run_custom(be, "predict_detail", specs, key=key, packed=packed, label="cfapi", done_dir=rd.run / "_done")
            record["modal"]["eval_s"] = X.wall(te)
            record["modal"]["cost"] = be.cost_summary()
    out, errs = {}, {}
    for sp, (val, err) in zip(specs, res):
        if val is None:
            errs[sp["sid"]] = str(err)[:1500]
        else:
            out[sp["sid"]] = val
    C.dump_json({s: PS.strip_private({k: v for k, v in r.items() if k != "isolation"}) for s, r in out.items()}, rd.run / "detail.json")
    record["eval_errors"] = errs
    record["wall_s"] = X.wall(t0)
    record["status"] = "complete"
    C.dump_json(record, rd.out / "RUN.json")
    summ = summarize(rd, record, out)
    print(json.dumps({"run": run_id, "wall_s": record["wall_s"], "systems": len(out), "errors": len(errs),
                      "complete_fields": summ["completeness"]["complete_fields"], "usd": (record["modal"].get("cost") or {}).get("usd_approx_total")},
                     indent=1), flush=True)
    return 0


def completeness(val: dict) -> dict:
    """Per field: the share of items for which it is returned and well formed (probe of the raw output + the per-item rows)."""
    pr = val.get("api_probe") or {}
    n = int(pr.get("n") or 0)
    rows = val.get("items") or []
    nr = len(rows) or 1
    unc_rows = sum(1 for r in rows if r.get("has_y_sd") or r.get("uncertainty_keys"))
    val_rows = sum(1 for r in rows if r.get("validity_in_domain") is not None and r.get("validity_score") is not None)
    z_rows = sum(1 for r in rows if r.get("has_z_int") and r.get("has_z_base") and r.get("z_finite"))
    share = {
        "y_int": (pr.get("shape_ok_y", 0) / n) if n else None,
        "y_base": (pr.get("shape_ok_y", 0) / n) if n else None,
        "effect": (pr.get("effect_consistent", 0) / n) if n else None,
        "uncertainty": unc_rows / nr,
        "validity": val_rows / nr,
        "z_trajectory": (min(pr.get("shape_ok_z", 0) / n, z_rows / nr) if n else z_rows / nr),
        "abstain_flag": (pr.get("abstain_flag", 0) / n) if n else None,
    }
    return {"n_probe": n, "n_items": len(rows), "share": share, "keys": pr.get("keys"), "errors": pr.get("errors")}


def accuracy(val: dict) -> dict:
    eff = val.get("effects") or {}
    cal = val.get("calibration") or {}
    ood = val.get("ood") or {}
    clo = val.get("closure") or {}
    rows = val.get("items") or []
    res = {"effects": eff}
    ee_v = PS.metric({"items": {"effects": eff}}, "EE")
    pairs = [(r["pred_sd"], r["rmse"]) for r in rows if r.get("pred_sd") is not None and r.get("rmse") is not None]
    rho = None
    if len(pairs) >= 8:
        from scipy.stats import spearmanr
        rho = float(spearmanr([a for a, _ in pairs], [b for _, b in pairs]).statistic)
    ins = [r for r in rows if r.get("validity_in_domain") is True]
    outs = [r for r in rows if r.get("validity_in_domain") is False]

    def pooled(rs):
        num = sum((r.get("num") or {}).get("medium") or 0.0 for r in rs)
        den = sum((r.get("den") or {}).get("medium") or 0.0 for r in rs)
        return (num / den) if den > 0 else None
    return {"EE_verdict": ee_v, "EE_pooled_all": ((eff.get("EE_medium") or {}).get("point")),
            "post_nmse": ((eff.get("post_nmse_medium") or {}).get("point")),
            "rmse_mean": float(np.mean([r["rmse"] for r in rows if r.get("rmse") is not None])) if any(r.get("rmse") is not None for r in rows) else None,
            "sign_accuracy": (eff.get("sign_accuracy") or {}).get("all"),
            "interval_coverage_90": {h: (v or {}).get("coverage") for h, v in (cal.get("interval_coverage_90") or {}).items()},
            "calibration_error_90": {h: (v or {}).get("calibration_error") for h, v in (cal.get("interval_coverage_90") or {}).items()},
            "reports_uncertainty": cal.get("reports_uncertainty"), "brier_detectable": (cal.get("brier_detectable") or {}).get("score"),
            "brier_sign": (cal.get("brier_sign") or {}).get("score"), "sd_error_spearman": rho,
            "validity_auc": (ood.get("validity_auc") or {}).get("auc"), "EE_in_domain": pooled(ins), "EE_out_of_domain": pooled(outs),
            "n_in_domain": len(ins), "n_out_of_domain": len(outs), "ICG_y": ((clo.get("ICG_y") or {}).get("point") if isinstance(clo, dict) else None),
            "closure_error": clo.get("error") if isinstance(clo, dict) else None, "coverage": cal.get("coverage"),
            "false_confidence": (cal.get("false_confidence") or {}).get("rate")}


def summarize(rd: C.RunDirs, record: dict, out: dict | None = None) -> dict:
    out = out if out is not None else C.load_json(rd.run / "detail.json", {})
    systems = C.resolve_systems(record["tier"], record.get("real_level"), record["systems"])
    per = {s: {"kind": systems[s]["kind"], "completeness": completeness(v), "accuracy": accuracy(v)} for s, v in out.items()}
    comp_fields = []
    for f in FIELDS:
        shares = [p["completeness"]["share"].get(f) for p in per.values()]
        if shares and all(x is not None and x >= COMPLETE_SHARE for x in shares):
            comp_fields.append(f)
    syn = sorted(s for s, p in per.items() if p["kind"] == "synthetic")
    suite = {}
    for m, worst in (("EE_verdict", 10.0), ("EE_pooled_all", 10.0), ("post_nmse", 10.0), ("rmse_mean", None), ("sign_accuracy", None),
                     ("brier_detectable", None), ("validity_auc", None), ("ICG_y", 1.0), ("coverage", None), ("false_confidence", 1.0),
                     ("sd_error_spearman", None)):
        vals = {s: per[s]["accuracy"].get(m) for s in syn}
        if worst is None:
            vals = {s: v for s, v in vals.items() if v is not None}
            if len(vals) >= 2:
                suite[m] = PS.strip_private(PS.suite_mean(vals, sorted(vals), worst=float("nan"), n_boot=1000, seed=3))
        elif syn:
            suite[m] = PS.strip_private(PS.suite_mean(vals, syn, worst=worst, n_boot=1000, seed=3))
    cov90 = {}
    for h in ("short", "medium", "long"):
        vals = {s: (per[s]["accuracy"]["interval_coverage_90"] or {}).get(h) for s in syn}
        vals = {s: v for s, v in vals.items() if v is not None}
        if len(vals) >= 2:
            cov90[h] = PS.strip_private(PS.suite_mean(vals, sorted(vals), worst=float("nan"), n_boot=1000, seed=4))
    res = {**C.marks_of(record), "run_id": record["run_id"], "method": record["method"], "tier": record["tier"], "n_systems": len(per),
           "completeness": {"complete_fields": comp_fields, "incomplete_fields": [f for f in FIELDS if f not in comp_fields],
                            "rule": f"well formed on >= {COMPLETE_SHARE:.0%} of the probed items of every system"},
           "suite_accuracy": suite, "suite_interval_coverage_90": cov90, "per_system": per, "descriptive_accuracy": True}
    C.dump_json(res, rd.out / "COUNTERFACTUAL_API.json")
    L = [f"# Counterfactual API: `{record['method']}` ({record['tier']}; run {record['run_id']})", ""] + C.dry_banner(record) + [
         f"Complete fields: {', '.join(comp_fields) or 'none'}; incomplete: {', '.join(res['completeness']['incomplete_fields']) or 'none'} "
         f"(rule: {res['completeness']['rule']}).", "", "| accuracy (suite mean over synthetic systems) | point | 95 % CI |", "|---|---|---|"]
    for m, e in suite.items():
        ci = e.get("ci95") or [None, None]
        L.append(f"| {m} | {e.get('point') if e.get('point') is None else round(e['point'], 4)} | "
                 f"[{'-' if ci[0] is None else round(ci[0], 4)}, {'-' if ci[1] is None else round(ci[1], 4)}] |")
    for h, e in cov90.items():
        L.append(f"| 90 % interval coverage ({h}) | {round(e['point'], 4) if e.get('point') is not None else '-'} | |")
    (rd.out / "COUNTERFACTUAL_API.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    return res


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
    r.add_argument("--n-probe", type=int, default=N_PROBE)
    r.add_argument("--n-boot", type=int, default=2000)
    r.add_argument("--run-id", default=None)
    r.add_argument("--max-containers", type=int, default=40)
    r.add_argument("--dry-run-on-val", action="store_true", help="BEFORE the lock only: a stand-in dry run on the Level B val tier")
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
            print(json.dumps(summarize(C.RunDirs(STUDY, args.run_id, bool(rec.get("hidden"))), rec)["completeness"]))
            return 0
    raise SystemExit(f"no run {args.run_id}")


if __name__ == "__main__":
    raise SystemExit(main())
