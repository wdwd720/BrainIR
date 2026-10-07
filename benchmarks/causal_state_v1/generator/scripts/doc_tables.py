"""Markdown tables for SYNTHETIC_BENCHMARK.md from calibration_report.json and timings_accuracy.json."""
import json

cal = json.load(open("calibration_report.json"))
tg = json.load(open("/room/ref/calibration_targets.json"))["statistics"]
rep = cal["comparison"]
print(f"Result: {rep['n_ok']} / {rep['n_tested']} required statistics pass (dev tier, seed 0, {cal['n_systems']} systems, "
      f"{cal['n_int_per_system']} intervention pairs + 22 passive trajectories per system).\n")
print("| statistic | target range | min inside | coverage | inside | suite min / median / max | real range | result |")
print("|---|---|---|---|---|---|---|---|")
for nm in sorted(rep["statistics"]):
    e = rep["statistics"][nm]
    v = e["values"]
    cov = tg[nm].get("coverage")
    real = tg[nm].get("real_all") or {}
    print(f"| `{nm}` | {e['target_range'][0]:.3g} – {e['target_range'][1]:.3g} | {e['min_inside_frac']:.2f} | "
          f"{'[' + ', '.join(f'{c:g}' for c in cov) + ']' if cov else '–'} | {e['inside_frac']:.2f} | "
          f"{v['min']:.3g} / {v['median']:.3g} / {v['max']:.3g} | {real.get('min', float('nan')):.3g} – {real.get('max', float('nan')):.3g} | "
          f"{'pass' if e['ok'] else 'OUTSIDE'} |")
print()
ta = json.load(open("timings_accuracy.json"))
s = ta["summary"]
print(f"CPU per 2 s of simulated time (dev suite, single thread): median {s['cpu_s_per_2s']['median']:.3f} s, "
      f"90th percentile {s['cpu_s_per_2s']['p90']:.3f} s, max {s['cpu_s_per_2s']['max']:.3f} s; suite build {s['build_cpu_s']} s CPU.")
print(f"RK4 error at the default step vs an 8x finer step (max over the trajectory, relative to obs_scale): y median "
      f"{s['err_y_rel']['median']:.1e}, max {s['err_y_rel']['max']:.1e}; x median {s['err_x_rel']['median']:.1e}, max {s['err_x_rel']['max']:.1e}.")
print()
print("| system | N units / obs | dt, h (ms) | CPU s per 2 s | y error | x error | observed order |")
print("|---|---|---|---|---|---|---|")
for sid, r in sorted(ta["systems"].items(), key=lambda kv: kv[1]["label"]):
    o = r["observed_order"]
    print(f"| {r['label']} | {r['n_units']} / {r['n_obs']} | {r['dt'] * 1e3:g}, {r['h'] * 1e3:g} | {r['cpu_s_per_2s']:.3f} | "
          f"{r['err_y_default_vs_8x']:.1e} | {r['err_x_default_vs_8x']:.1e} | {'–' if o is None else f'{o:.1f}'} |")
