"""Calibration check of a p4synth suite against ref/calibration_targets.json (version 3) with ref/calibstats.py.

Every calibration record of a system (p4synth.calib, 713 per system with the default n_int = 200) goes to calibstats.compute_all.
    sbx python scripts/run_calibration.py --tier dev --seed 20260926 --part 0 --nparts 2 --out scratch/cal_part0.json
    sbx python scripts/run_calibration.py --merge scratch/cal_part0.json scratch/cal_part1.json --out scratch/calibration_report.json
(the room root is read-only inside the sandbox: write to a work area, then copy the report to the root)
"""
import argparse
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, "/room")
from ref import calibstats as CS  # noqa: E402
from p4synth import build_suite  # noqa: E402
from p4synth.calib import calibration_records, sysrec_of  # noqa: E402

_SUITE = None
ARGS = None


def _one(sid):
    s = _SUITE[sid]
    t0 = time.time()
    recs = calibration_records(s, n_int=ARGS.n_int)
    t1 = time.time()
    st = CS.compute_all(recs, sysrec_of(s))
    st = {k: v for k, v in st.items() if not isinstance(v, (list, np.ndarray))}
    return sid, st, round(t1 - t0, 1), round(time.time() - t1, 1), len(recs)


def _report(per, timing, labels, meta):
    tg = json.load(open("/room/ref/calibration_targets.json"))
    rep = CS.compare(per, tg["statistics"])
    checked = sorted(rep["statistics"])
    per_system = {sid: {"label": labels[sid], **{k: per[sid].get(k) for k in checked}} for sid in per}
    out = dict(meta, targets_version=tg.get("version"), record_selection="every calibration record of each system passed to "
               "calibstats.compute_all (no subsample; compute_all uses at most 40 records per record kind for per-trajectory "
               "statistics)", n_systems=len(per), stat_version=CS.STAT_VERSION, comparison=rep, per_system_checked=per_system,
               per_system_all=per, timing=timing)
    json.dump(out, open(ARGS.out, "w"), indent=1, default=float)
    print(f"n_ok {rep['n_ok']} / {rep['n_tested']}  missing {rep['missing']}")
    for nm in checked:
        e = rep["statistics"][nm]
        v = e["values"]
        print(f"{'PASS' if e['ok'] else 'FAIL':4} {nm:40s} in={e['inside_frac']:.2f}/{e['min_inside_frac']:.2f} cov={e['coverage_ok']} "
              f"ovl={e['overlaps_real_range']} range={e['target_range'][0]:.3g}..{e['target_range'][1]:.3g} "
              f"vals={v['min']:.3g}/{v['median']:.3g}/{v['max']:.3g}")


def main():
    global _SUITE, ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="dev")
    ap.add_argument("--seed", type=int, default=20260926)
    ap.add_argument("--n-int", type=int, default=200)
    ap.add_argument("--out", default="calibration_report.json")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--nparts", type=int, default=1)
    ap.add_argument("--merge", nargs="*", default=None)
    ARGS = ap.parse_args()
    if ARGS.merge:
        parts = [json.load(open(f)) for f in ARGS.merge]
        per, timing, labels = {}, {}, {}
        for p in parts:
            per.update(p["per_system_all"])
            timing.update(p["timing"])
            labels.update({sid: v["label"] for sid, v in p["per_system_checked"].items()})
        meta = {k: parts[0][k] for k in ("tier", "seed", "n_int_per_system")}
        meta["wall_seconds_parts"] = [p.get("wall_seconds") for p in parts]
        _report(per, timing, labels, meta)
        return
    _SUITE = build_suite(ARGS.tier, ARGS.seed)
    ids = sorted(_SUITE)[ARGS.part::ARGS.nparts]
    t0 = time.time()
    with Pool(ARGS.procs, maxtasksperchild=1) as pool:
        res = pool.map(_one, ids, chunksize=1)
    per = {sid: st for sid, st, _, _, _ in res}
    timing = {sid: {"simulate_s": a, "compute_all_s": b, "n_records": n} for sid, _, a, b, n in res}
    labels = {sid: f"T{_SUITE[sid].info['type']:02d}-{_SUITE[sid].info['variant']}" for sid in ids}
    meta = {"tier": ARGS.tier, "seed": ARGS.seed, "n_int_per_system": ARGS.n_int, "wall_seconds": round(time.time() - t0, 1)}
    _report(per, timing, labels, meta)


if __name__ == "__main__":
    main()
