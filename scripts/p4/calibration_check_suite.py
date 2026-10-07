"""Criterion 11: calibration check of a built SYNTHETIC tier's public data against the frozen calibration targets (ORCHESTRATOR SIDE;
goal5 section 8; LOG P4-D25).

    uv run --no-sync --project phase4 python scripts/p4/calibration_check_suite.py --tier dev
        [--root data/phase4/suites/dev/public] [--out research/phase4/CALIBRATION_CHECK_dev.json] [--max-per-kind N]

For every system of the tier's public part: `calibstats.compute_all` on its public records, selected as the targets were built (the
targets' `record_selection`: EVERY public record, `calibration_check_real.load_records` = `calibstats.load_dataset_dir` without a cap;
LOG P4-D38) or, with --max-per-kind N, the earlier subsample (at most N records of each record kind, evenly spaced, plus the twins of
the kept intervention records). Then `calibstats.compare` of the whole tier
as a suite against benchmarks/causal_state_v1/public/calibration_targets.json (the suite-level rule of the targets: inside fraction,
overlap with the real range, coverage), and, descriptively, the same comparison per system type (types from the tier's truth
summaries, orchestrator side). Writes the JSON record and prints the summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from brainir_causal import calibstats as CS  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402
from calibration_check_real import TARGETS, load_records  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=("dev", "toy"))
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--modal", action="store_true", help="compute each system's statistics on Modal from the fit volume's public part "
                    "(one gated eval_s container per system; no local download); the comparison runs here")
    ap.add_argument("--stats-cache", type=Path, default=None,
                    help="per-system statistics cache (streamed tiers): compute the systems present, compare only when all are cached")
    ap.add_argument("--max-per-kind", type=int, default=None,
                    help="subsample each record kind (the selection before targets version 3); default: every record, as the targets")
    args = ap.parse_args(argv)
    dirs = SU.tier_dirs(args.tier, SU.SUITES)
    root = args.root or dirs["public"]
    out = args.out or ROOT / "research" / "phase4" / f"CALIBRATION_CHECK_{args.tier}.json"
    tg = json.loads(TARGETS.read_text(encoding="utf-8"))
    stats_t = tg["statistics"]
    truth_path = dirs["truth"] / "systems_truth.json"
    truths = json.loads(truth_path.read_text(encoding="utf-8")) if truth_path.exists() else {}
    per, types, t0 = {}, {}, time.time()
    if args.modal:
        if args.max_per_kind is not None:
            raise SystemExit("--modal computes the targets' record selection (every record) only")
        from brainir_causal.p4modal.app import MOUNT, Backend
        sids = sorted(json.loads((dirs["base"] / "internal_records.json").read_text(encoding="utf-8")))
        base = f"{MOUNT['fit']}/data/suites/{args.tier}/public"
        with Backend(classes=["eval_s"], app_name="brainir-p4-crit11") as be:
            res = be.call("brainir_causal.calibstats:stats_of_dataset_dir", [[f"{base}/{SU._safe(s)}"] for s in sids], cls="eval_s",
                          timeout_s=3600, threads=1, eager=True, reload=["fit"])
        bad = [(s, r) for s, r in zip(sids, res) if not (isinstance(r, dict) and "result" in r)]
        if bad:
            raise SystemExit(f"criterion 11 on Modal failed for {len(bad)} systems: {str(bad[:2])[:1500]}")
        for s, r in zip(sids, res):
            out_r = r["result"]
            if out_r["system_id"] != s:
                raise SystemExit(f"{s}: the volume's public part describes {out_r['system_id']}")
            per[s] = out_r["stats"]
            types[s] = str((truths.get(s) or {}).get("type", "?"))
            print(f"{s}: {out_r['n_records']} records, {per[s]['counts']['n_pairs']} pairs (Modal)", flush=True)
    else:
        cache = args.stats_cache
        sdirs = sorted(d for d in root.iterdir() if (d / "index.jsonl").is_file()) if root.is_dir() else []
        if not sdirs and not cache:
            raise SystemExit(f"no built system under {root}")
        for d in sdirs:
            cf = (cache / f"{d.name}.json") if cache else None
            if cf is not None and cf.exists():
                continue
            pub, recs = load_records(d, args.max_per_kind)
            sid = pub["system_id"]
            per[sid] = CS.compute_all(recs, pub)
            print(f"{sid}: {len(recs)} records, {per[sid]['counts']['n_pairs']} pairs", flush=True)
            if cf is not None:
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(json.dumps({"system_id": sid, "stats": per[sid], "max_per_kind": args.max_per_kind}, default=str) + "\n",
                              encoding="utf-8", newline="\n")
        if cache:
            # STREAMED tiers (LOCAL_EXECUTION_PLAN.md section 7): per-system statistics cached as each batch is built; the suite
            # comparison runs only when EVERY system of the tier is cached (never on a partial suite)
            per = {}
            for f in sorted(cache.glob("*.json")):
                r = json.loads(f.read_text(encoding="utf-8"))
                if r.get("max_per_kind") == args.max_per_kind:
                    per[r["system_id"]] = r["stats"]
            tier_ids = set(json.loads((dirs["base"] / "internal_records.json").read_text(encoding="utf-8")))
            if set(per) != tier_ids:
                print(f"cached {len(set(per) & tier_ids)} / {len(tier_ids)} systems; the suite comparison waits for all", flush=True)
                return 2
        for sid in per:
            types[sid] = str((truths.get(sid) or {}).get("type", "?"))
    suite_cmp = CS.compare(per, stats_t)
    by_type = {}
    for ty in sorted(set(types.values()), key=lambda s: (len(s), s)):
        sub = {s: v for s, v in per.items() if types[s] == ty}
        c = CS.compare(sub, stats_t)
        by_type[ty] = {"n_systems": len(sub), "n_ok": c["n_ok"], "n_tested": c["n_tested"],
                       "not_ok": sorted(nm for nm, r in c["statistics"].items() if not r["ok"])}
    failing = {nm: r for nm, r in suite_cmp["statistics"].items() if not r["ok"]}
    rec = {"what": f"criterion 11: synthetic tier {args.tier} public data vs calibration_targets.json (calibstats.compute_all, suite rule)",
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stat_version": CS.STAT_VERSION,
           "targets_version": tg.get("version"), "n_systems": len(per),
           "record_selection": ("every public record (the targets' record_selection)" if args.max_per_kind is None
                                else f"at most {args.max_per_kind} records per record kind plus their twins"),
           "summary": {"suite_compare_ok": f"{suite_cmp['n_ok']}/{suite_cmp['n_tested']}", "missing": suite_cmp["missing"],
                       "failing": sorted(failing)},
           "suite_compare": suite_cmp, "by_type_descriptive": by_type,
           "per_system": {s: {"type": types[s], **{nm: v for nm, v in per[s].items() if isinstance(v, (int, float)) and not isinstance(v, bool)}}
                          for s in sorted(per)},
           "seconds": round(time.time() - t0, 1)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec["summary"], indent=1))
    for nm, r in sorted(failing.items()):
        print(f"NOT OK {nm}: inside {r['inside_frac']:.2f} (need {r['min_inside_frac']:.2f}), overlap {r['overlaps_real_range']}, "
              f"coverage {r['coverage_ok']}; values {r['values']}; target {r['target_range']}")
    return 0 if not failing and not suite_cmp["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
