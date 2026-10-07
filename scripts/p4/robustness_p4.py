"""Post-lock ROBUSTNESS SWEEPS (goal5 section 75; PROTOCOL 4.2 / 5.12 on finer grids). ORCHESTRATOR SIDE. DESCRIPTIVE.

    uv run --no-sync --project phase4 python scripts/p4/robustness_p4.py run --method NAME --tier conf [--real C] --fits-from DIR
        [--items-per-level 8] [--run-id ID]
    uv run --no-sync --project phase4 python scripts/p4/robustness_p4.py run --method p3stand.refstand:p3stand_ref --tier dev
        --methods-dir scripts/p4/standin_methods --fits-from C:/Dev/BrainIR_p4run/postlock/ablations/dry1/full --run-id dry1   # DRY RUN

The Level C evaluation reports each robustness condition of PROTOCOL 4.2 at its two levels (5.12). This study measures DOSE-RESPONSE
curves on finer grids (`p4post.itemsets.ROBUST_GRID`: parameter noise, weight noise, process noise where supported, observation
noise, untold amplitude jitter, untold timing jitter; plus a nominal anchor), ITEMS_PER_LEVEL in-family items per (condition, level)
and system, planned here (hidden-range seeds post-lock), built on Modal by the benchmark's builder into a custom tier, evaluated by
`p4post.isojob.predict_detail` (the benchmark's item scoring in model workers).

Per (condition, level): the suite mean over systems (unstratified system bootstrap) of the per-system pooled EE, the abstention rate,
the mean predicted sd and the realised RMS error of the intervened prediction (readout-sd units), the validity score and the
false-confidence rate. "Uncertainty should increase appropriately" (goal5 75): per condition the ratios sd(level) / sd(nominal) and
error(level) / error(nominal), their log-log slope over levels (1 = proportional) and the flag UNCERTAINTY FLAT (the error grows by
more than 50 % at the largest level while the predicted sd grows by less than 10 %, or the model reports no sd at all).
Outputs: <out>/ROBUSTNESS.json / .md (post-lock: research/phase4/postlock/robustness/<run>/, ANSWER-BEARING).
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
from p4post import pairstats as PS  # noqa: E402

STUDY = "robustness"
FLAT_ERR, FLAT_SD = 1.5, 1.1


def cmd_run(args) -> int:
    t0 = time.time()
    real_level = args.real or None
    g = C.guard(args.tier, real_level, what="the robustness sweeps", dry_run_on_val=args.dry_run_on_val, methods=[args.method],
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
    recs = C.plan_records(args.tier, real_level, sorted(systems))
    tier_c = C.custom_tier("rb", run_id, "grid", hidden=g["hidden"])
    excl = [f for f in (args.exclude_families or "").split(",") if f]
    jobs, owners, plan_counts = [], [], {}
    for s in sorted(systems):
        specs, counts = IS.robustness_specs(recs[s]["pub"], recs[s]["internal"], IS.seed_function(g["hidden"], "rb", run_id, s),
                                            items_per_level=args.items_per_level, exclude=excl)
        plan_counts[s] = {"n_items": len(specs), **counts}
        jobs.append([IS.build_job(s, systems[s]["kind"], tier_c, recs[s]["pub"], recs[s]["internal"], specs, workers=args.build_workers)])
        owners.append(s)
    record = {"study": STUDY, "run_id": run_id, "created_utc": C.utc(), **C.run_marks(g, args.tier, real_level), "hidden": g["hidden"],
              "lock": g["lock"], "method": args.method, "method_hashes": mhash, "fits_from": str(args.fits_from), "levelc_run": args.levelc_run, "seed": seed,
              "custom_tier": tier_c, "exclude_families": excl, "grid": IS.ROBUST_GRID, "items_per_level": args.items_per_level, "systems": sorted(systems),
              "plan": plan_counts, "modal": {}}
    C.dump_json(record, rd.out / "RUN.json")
    synthetic = any(d["kind"] == "synthetic" for d in systems.values())
    real = any(d["kind"] == "real" for d in systems.values())
    packed = not args.unpacked
    classes = ["build", X.PACK_EVAL] if packed else sorted({"build", "iso_eval_s"} | ({"iso_eval_l"} if real else set()))
    if g["hidden"]:
        record["ledger"] = C.ledger_claim(STUDY, run_id, new_run_reason=args.new_run_reason)
    with C.HiddenRunLog(g["hidden"], STUDY, run_id, f"{args.method} on {args.tier}/{real_level}: {len(systems)} systems"):
        with C.backend(classes, synthetic=synthetic, app_name="brainir-p4-post-robust", max_containers=args.max_containers) as be:
            key = be.methods_key(rd.run / "methods")
            tb = time.time()
            bres = be.call("brainir_causal.suites:build_system_job", jobs, cls="build", timeout_s=6 * 3600, threads=1, eager=True,
                           reload=["fit", "eval", "store"], commit=["fit", "eval", "store"])
            record["modal"]["build_s"] = X.wall(tb)
            build = {}
            for s, br in zip(owners, bres):
                val, err = C.call_result(br)
                build[s] = {"error": err[-1500:]} if err else {"counts": ((val.get("parts") or {}).get("eval") or {}).get("counts"),
                                                               "wall_s": val.get("wall_s")}
            record["build"] = build
            specs_e = []
            for s, sysd in systems.items():
                if build[s].get("error"):
                    continue
                job = C.eval_job(s, sysd, lift=False, n_boot=args.n_boot, seed=seed, heldout_tier=tier_c,
                                 heldout_root=C.custom_heldout_root(sysd), part="eval")
                job.update({"roles": ["robust"], "n_probe": 0, "call_timeout_s": 900})
                specs_e.append({"sid": s, "sysd": sysd, "job": job, "model_path": models[s]})
            te = time.time()
            eres = X.run_custom(be, "predict_detail", specs_e, key=key, packed=packed, label="robust-eval", done_dir=rd.run / "_done")
            record["modal"]["eval_s"] = X.wall(te)
            rows, errs = {}, {}
            for sp, (val, err) in zip(specs_e, eres):
                if val is None:
                    errs[sp["sid"]] = str(err)[:1500]
                else:
                    rows[sp["sid"]] = {"items": val.get("items") or [], "ood": val.get("ood"), "wall_s": val.get("wall_s")}
            record["eval_errors"] = errs
            record["modal"]["cost"] = be.cost_summary()
    C.dump_json(rows, rd.run / "items.json")
    record["wall_s"] = X.wall(t0)
    record["status"] = "complete"
    C.dump_json(record, rd.out / "RUN.json")
    summ = summarize(rd, record, rows)
    print(json.dumps({"run": run_id, "wall_s": record["wall_s"], "systems_evaluated": len(rows), "eval_errors": len(errs),
                      "flat_conditions": summ["flat_conditions"], "usd": (record["modal"].get("cost") or {}).get("usd_approx_total")},
                     indent=1), flush=True)
    return 0


def _per_system(rows: list[dict]) -> dict:
    """{role: {"EE", "abstain", "sd", "err", "validity", "fc", "n"}} of one system's items."""
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r["shift"], []).append(r)
    out = {}
    for role, rs in by.items():
        num = sum((r.get("num") or {}).get("medium") or 0.0 for r in rs if (r.get("den") or {}).get("medium"))
        den = sum((r.get("den") or {}).get("medium") or 0.0 for r in rs if (r.get("den") or {}).get("medium"))
        sds = [r["pred_sd"] for r in rs if r.get("pred_sd") is not None]
        errs = [r["rmse"] for r in rs if r.get("rmse") is not None]
        vs = [r["validity_score"] for r in rs if r.get("validity_score") is not None]
        fce = [r for r in rs if r.get("fc_eligible")]
        out[role] = {"EE": (num / den) if den > 0 else None, "abstain": float(np.mean([bool(r.get("abstain")) for r in rs])),
                     "sd": float(np.mean(sds)) if sds else None, "err": float(np.mean(errs)) if errs else None,
                     "validity": float(np.mean(vs)) if vs else None, "fc": (float(np.mean([bool(r.get("fc")) for r in fce])) if fce else None),
                     "n": len(rs), "n_sd": len(sds)}
    return out


def summarize(rd: C.RunDirs, record: dict, rows: dict | None = None) -> dict:
    rows = rows if rows is not None else C.load_json(rd.run / "items.json", {})
    per = {s: _per_system(v["items"]) for s, v in rows.items()}
    sids = sorted(per)
    conds: dict = {}
    flat = []
    for cond, levels in IS.ROBUST_GRID.items():
        lv_rows = {}
        for lv in (0,) + tuple(levels):
            role = "robust:nominal@0" if lv == 0 else f"robust:{cond}@{lv}"
            have = [s for s in sids if role in per[s]]
            if not have:
                continue
            row = {"n_systems": len(have)}
            for m, worst in (("EE", 10.0), ("abstain", 1.0), ("sd", None), ("err", None), ("validity", None), ("fc", 1.0)):
                vals = {s: per[s][role][m] for s in have}
                if worst is None:
                    vals = {s: v for s, v in vals.items() if v is not None}
                    if len(vals) < 2:
                        row[m] = {"point": None, "n": len(vals)}
                        continue
                    row[m] = PS.strip_private(PS.suite_mean(vals, sorted(vals), worst=float("nan"), n_boot=1000, seed=5))
                else:
                    row[m] = PS.strip_private(PS.suite_mean(vals, have, worst=worst, n_boot=1000, seed=5))
            lv_rows[str(lv)] = row
        if not lv_rows or "0" not in lv_rows or len(lv_rows) < 2:
            conds[cond] = {"levels": lv_rows, "note": "not testable on these systems"}
            continue
        sd0, e0 = (lv_rows["0"].get("sd") or {}).get("point"), (lv_rows["0"].get("err") or {}).get("point")
        ratios = {}
        for lv, row in lv_rows.items():
            if lv == "0":
                continue
            sd, e = (row.get("sd") or {}).get("point"), (row.get("err") or {}).get("point")
            ratios[lv] = {"sd_ratio": (sd / sd0) if (sd is not None and sd0) else None, "err_ratio": (e / e0) if (e is not None and e0) else None}
        pairs = [(v["err_ratio"], v["sd_ratio"]) for v in ratios.values() if v["err_ratio"] and v["sd_ratio"] and v["err_ratio"] > 0 and v["sd_ratio"] > 0]
        slope = None
        if len(pairs) >= 2 and np.ptp([np.log(a) for a, _ in pairs]) > 0:
            slope = float(np.polyfit([np.log(a) for a, _ in pairs], [np.log(b) for _, b in pairs], 1)[0])
        top = ratios[max(ratios, key=lambda k: float(k))] if ratios else {}
        reports_sd = sd0 is not None
        is_flat = (not reports_sd) or bool(top.get("err_ratio") and top["err_ratio"] > FLAT_ERR and (top.get("sd_ratio") or 0) < FLAT_SD)
        if is_flat:
            flat.append(cond)
        conds[cond] = {"levels": lv_rows, "ratios_to_nominal": ratios, "loglog_slope_sd_on_err": slope, "reports_sd": reports_sd,
                       "uncertainty_flat": is_flat}
    out = {**C.marks_of(record), "run_id": record["run_id"], "method": record["method"], "tier": record["tier"], "n_systems": len(sids),
           "conditions": conds,
           "flat_conditions": flat, "rule_flat": f"error ratio > {FLAT_ERR} at the largest level while the sd ratio < {FLAT_SD}, or no sd",
           "descriptive": True}
    C.dump_json(out, rd.out / "ROBUSTNESS.json")
    L = [f"# Robustness sweeps: `{record['method']}` ({record['tier']}; run {record['run_id']}; descriptive)", ""] + C.dry_banner(record) + [
         f"{len(sids)} systems; {record['items_per_level']} items per level. Flat uncertainty: {', '.join(flat) or 'none'}.", "",
         "| condition | level | systems | EE | abstain | pred sd | RMS error | sd ratio | error ratio |", "|---|---|---|---|---|---|---|---|---|"]
    for cond, c in conds.items():
        for lv, row in (c.get("levels") or {}).items():
            rr = (c.get("ratios_to_nominal") or {}).get(lv, {})

            def p(m):
                v = (row.get(m) or {}).get("point")
                return "-" if v is None else f"{v:.3g}"
            L.append(f"| {cond} | {lv} | {row.get('n_systems')} | {p('EE')} | {p('abstain')} | {p('sd')} | {p('err')} | "
                     f"{'-' if rr.get('sd_ratio') is None else round(rr['sd_ratio'], 3)} | {'-' if rr.get('err_ratio') is None else round(rr['err_ratio'], 3)} |")
    (rd.out / "ROBUSTNESS.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
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
    r.add_argument("--items-per-level", type=int, default=IS.ITEMS_PER_LEVEL)
    r.add_argument("--run-id", default=None)
    r.add_argument("--n-boot", type=int, default=200)
    r.add_argument("--build-workers", type=int, default=16)
    r.add_argument("--max-containers", type=int, default=40)
    r.add_argument("--dry-run-on-val", action="store_true", help="BEFORE the lock only: a stand-in dry run on the Level B val tier")
    r.add_argument("--exclude-families", default="", help="families left out of the grid (recorded)")
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
            print(json.dumps(summarize(C.RunDirs(STUDY, args.run_id, bool(rec.get("hidden"))), rec)["flat_conditions"]))
            return 0
    raise SystemExit(f"no run {args.run_id}")


if __name__ == "__main__":
    raise SystemExit(main())
