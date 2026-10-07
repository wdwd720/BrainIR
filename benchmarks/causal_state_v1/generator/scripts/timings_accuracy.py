"""Timings and integration accuracy of a suite (numbers reported in SYNTHETIC_BENCHMARK.md).

    sbx python scripts/timings_accuracy.py --tier dev --seed 0 --out scratch/timings_accuracy.json
"""
import argparse
import json
import time

import numpy as np

from p4synth import build_suite


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="dev")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="timings_accuracy.json")
    a = ap.parse_args()
    t0 = time.process_time()
    acc = 0
    for i in range(10 ** 7):          # machine-speed reference (the sandbox's speed varies with the host load)
        acc += i
    loop_s = time.process_time() - t0
    t0 = time.process_time()
    suite = build_suite(a.tier, a.seed)
    build_cpu = time.process_time() - t0
    rows = {}
    for sid, s in suite.items():
        p = s.base_protocol(params_seed=3)
        s.simulate(p)
        t0 = time.process_time()
        for _ in range(3):
            s.simulate(p)
        cpu = (time.process_time() - t0) / 3
        pk = s.base_protocol(params_seed=2, events=[{"kind": "kick", "t": 0.7, "delta": {str(s.core_targets()[0]): 3.0}}])
        o1 = s.simulate(pk, full=True)
        n0 = o1["info"]["n_sub"]
        o2 = s.simulate(pk, full=True, nsub=2 * n0)
        o8 = s.simulate(pk, full=True, nsub=8 * n0)
        sc = s.obs_scale()
        e1y = float(np.abs(o1["y"] - o8["y"]).max() / sc["y"])
        e2y = float(np.abs(o2["y"] - o8["y"]).max() / sc["y"])
        e1x = float(np.abs(o1["x"] - o8["x"]).max() / sc["x"])
        order = float(np.log2(max(e1y, 1e-300) / max(e2y, 1e-300))) if e2y > 1e-13 else None
        rows[sid] = {"label": f"T{s.info['type']:02d}-{s.info['variant']}", "n_units": s.n_units, "n_obs": len(s.observed),
                     "dt": s.dt, "t_end": s.t_end_default, "h": o1["info"]["h"], "cpu_s": round(cpu, 4),
                     "cpu_s_per_2s": round(cpu * 2.0 / s.t_end_default, 4), "err_y_default_vs_8x": e1y, "err_x_default_vs_8x": e1x,
                     "observed_order": order}
        print(rows[sid]["label"], rows[sid]["cpu_s_per_2s"], f"{e1y:.1e}", f"{e1x:.1e}", order, flush=True)
    cpus = [r["cpu_s_per_2s"] for r in rows.values()]
    ey = [r["err_y_default_vs_8x"] for r in rows.values()]
    ex = [r["err_x_default_vs_8x"] for r in rows.values()]
    summ = {"machine_python_loop_1e7_s": round(loop_s, 3), "build_cpu_s": round(build_cpu, 2), "cpu_s_per_2s": {"median": float(np.median(cpus)), "p90": float(np.percentile(cpus, 90)),
                                                                "max": float(max(cpus))},
            "err_y_rel": {"median": float(np.median(ey)), "max": float(max(ey))}, "err_x_rel": {"median": float(np.median(ex)),
                                                                                                "max": float(max(ex))}}
    json.dump({"summary": summ, "systems": rows}, open(a.out, "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
