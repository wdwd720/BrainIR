"""Calibration check of the Phase 4 PUBLIC real data against the frozen calibration targets (ORCHESTRATOR SIDE; goal5 section 8).

    uv run --no-sync --project phase4 python scripts/p4/calibration_check_real.py [--root data/phase4/real/real_public/public]
        [--out research/phase4/CALIBRATION_CHECK_real_public.json] [--max-per-kind N]

For every real system of the public part, `calibstats.compute_all` on its public records selected as the targets' `record_selection`
says (default: EVERY public record, `calibstats.load_dataset_dir` without a cap, as `scripts/p4/calibration_targets.py` builds the
targets; LOG P4-D38) or, with --max-per-kind N, at most N records of each record kind (evenly spaced, stimulus schedules without no-op
breakpoints, `step_schedule`) plus the counterfactual twins of the kept intervention records (the selection of the checks before
targets version 3), then for every statistic of benchmarks/causal_state_v1/public/calibration_targets.json: the system's value against the
REAL range of its class (real_full / real_mechanism), against the range over all real systems (real_all) and, for the checked
statistics, against target_range; plus `calibstats.compare` of the ten systems as a suite over the checked statistics. The targets
are anonymous ("real system N"): no system identity is used or inferred. Writes the JSON record; prints every statistic outside its
real range.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import calibstats as CS  # noqa: E402
from brainir_causal import suites as SU  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "phase4" / "real" / "real_public" / "public"
TARGETS = ROOT / "benchmarks" / "causal_state_v1" / "public" / "calibration_targets.json"
DEFAULT_OUT = ROOT / "research" / "phase4" / "CALIBRATION_CHECK_real_public.json"
MAX_PER_KIND = CS.MAX_RECORDS_PER_KIND


def step_schedule(stim: list) -> list:
    """The stimulus schedule without no-op breakpoints (an entry repeating the value in force). Phase 4 counterfactual twins carry
    a no-op breakpoint at their item's onset (`protocol.counterfactual` keeps the integration pieces), which `calibstats.pair_twins`'
    strict protocol comparison and `record_kind` would otherwise read as a different input schedule."""
    out = []
    for t, v in stim or []:
        if out and json.dumps(out[-1][1]) == json.dumps(v):
            continue
        out.append([t, v])
    return out


def load_records(d: Path, max_per_kind: int | None = None) -> tuple[dict, list[dict]]:
    """(public system record, records): every public record (the targets' record selection) or, with max_per_kind, the evenly spaced
    subsample of each record kind plus the twins of the kept records."""
    if max_per_kind is None:
        return CS.load_dataset_dir(d)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    pub = next(iter(man["systems"].values()))
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        r["protocol"] = {**r["protocol"], "stimulus": step_schedule(r["protocol"].get("stimulus"))}
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        if r["split"] == "twin":
            continue
        by_kind.setdefault(CS.record_kind(r), []).append(r)
    keep = []
    for rs in by_kind.values():
        keep += [rs[i] for i in CS._subsample(len(rs), int(max_per_kind))]
    kept = {r["key"] for r in keep}
    keep += [r for r in rows if r["split"] == "twin" and (r.get("meta") or {}).get("twin_of") in kept]
    recs = []
    for r in keep:
        with np.load(d / "traj" / f"{r['key']}.npz") as z:
            recs.append({**r, **{k: z[k] for k in ("t", "x", "u", "y")}})
    return pub, recs


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-per-kind", type=int, default=None,
                    help="subsample each record kind (the selection before targets version 3); default: every record, as the targets")
    args = ap.parse_args(argv)
    tg = json.loads(TARGETS.read_text(encoding="utf-8"))
    stats_t = tg["statistics"]
    from brainir_causal.systems import load_real_public
    sids = sorted(s for s in load_real_public() if (args.root / SU._safe(s) / "index.jsonl").exists())
    if not sids:
        raise SystemExit(f"no public real system under {args.root}")
    per, cls, t0 = {}, {}, time.time()
    for sid in sids:
        pub, recs = load_records(args.root / SU._safe(sid), args.max_per_kind)
        per[sid] = CS.compute_all(recs, pub)
        cls[sid] = "full" if pub.get("mode") == "full" else "mechanism"
        print(f"{sid}: {len(recs)} records, {per[sid]['counts']['n_pairs']} pairs", flush=True)
    out_sys: dict[str, dict] = {}
    outside_class, outside_all, outside_target = [], [], []
    for nm, ent in sorted(stats_t.items()):
        rng_c = {c: ent.get(f"real_{c}") or {} for c in ("full", "mechanism")}
        rng_a = ent.get("real_all") or {}
        for sid in sids:
            v = per[sid].get(nm)
            if not _num(v):
                continue
            rc = rng_c[cls[sid]]
            row = out_sys.setdefault(sid, {})
            flags = {}
            if rc.get("min") is not None:
                flags["in_class_range"] = bool(rc["min"] <= v <= rc["max"])
                if not flags["in_class_range"]:
                    outside_class.append({"system": sid, "statistic": nm, "value": v, "class": cls[sid], "real_range": [rc["min"], rc["max"]]})
            if rng_a.get("min") is not None:
                flags["in_all_range"] = bool(rng_a["min"] <= v <= rng_a["max"])
                if not flags["in_all_range"]:
                    outside_all.append({"system": sid, "statistic": nm, "value": v, "real_range": [rng_a["min"], rng_a["max"]]})
            if ent.get("check") and ent.get("target_range"):
                lo, hi = ent["target_range"]
                flags["in_target_range"] = bool(lo <= v <= hi)
                if not flags["in_target_range"]:
                    outside_target.append({"system": sid, "statistic": nm, "value": v, "target_range": [lo, hi]})
            row[nm] = {"value": v, **flags}
    suite_cmp = CS.compare(per, stats_t)
    n_stats = len({nm for s in out_sys.values() for nm in s})
    rec = {"what": "calibration check: Phase 4 public real data vs calibration_targets.json (calibstats.compute_all)",
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stat_version": CS.STAT_VERSION,
           "targets_version": tg.get("version"),
           "record_selection": ("every public record (calibstats.load_dataset_dir without a cap; the targets' record_selection)"
                                if args.max_per_kind is None else f"at most {args.max_per_kind} records per record kind plus their twins"),
           "root": "$DATA/" + args.root.resolve().relative_to(ROOT / "data").as_posix()
           if (ROOT / "data") in args.root.resolve().parents else args.root.name, "systems": {s: {"class": cls[s]} for s in sids},
           "n_statistics_compared": n_stats,
           "summary": {"outside_class_range": len(outside_class), "outside_all_range": len(outside_all),
                       "checked_outside_target_range": len(outside_target), "suite_compare_ok": f"{suite_cmp['n_ok']}/{suite_cmp['n_tested']}",
                       "suite_compare_missing": suite_cmp["missing"]},
           "outside_class_range": outside_class, "outside_all_range": outside_all, "checked_outside_target_range": outside_target,
           "suite_compare": suite_cmp, "per_system": out_sys, "seconds": round(time.time() - t0, 1)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec["summary"], indent=1))
    for o in outside_all:
        print(f"OUTSIDE real_all: {o['system']} {o['statistic']} = {o['value']:.4g} not in [{o['real_range'][0]:.4g}, {o['real_range'][1]:.4g}]")
    for o in outside_target:
        print(f"OUTSIDE target: {o['system']} {o['statistic']} = {o['value']:.4g} not in [{o['target_range'][0]:.4g}, {o['target_range'][1]:.4g}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
