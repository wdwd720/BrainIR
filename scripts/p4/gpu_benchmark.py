"""GPU / CPU benchmark of representative Phase 4 training workloads on Modal (goal5 sections 63 and 97). ORCHESTRATOR SIDE.

    uv run --no-sync --project phase4 python scripts/p4/gpu_benchmark.py probe            # which GPU type strings Modal accepts
    uv run --no-sync --project phase4 python scripts/p4/gpu_benchmark.py run [--devices cpu8,h100,...] [--quick]
    uv run --no-sync --project phase4 python scripts/p4/gpu_benchmark.py report           # rewrite the .md from the .json

Workloads (brainir_causal.p4modal.benchwork): latent controlled state-space models with an explicit intervention read-in -
`rollout` (sequential latent rollout, latency-bound), `gru` (GRU filter + parallel multi-horizon loss, throughput-bound), `ens8` (8
models in one batched pass), `node` (control-affine neural ODE, RK4) - on (N_obs, k) in {(20, 4), (200, 16)}, T in {500, 2000}
steps, batches of 64 and 256 trajectories; float32; Adam. Time per training step (median after warm-up), epoch time (1,024
trajectories) and cost per epoch at Modal's list prices (verified on modal.com/pricing 2026-09-26; container CPU and memory
included; the billed total of the run is taken from the billing API afterwards).

CPU containers run the production configuration for reproducible CPU numerics: the host gate (no AVX-512) and the AVX2 kernel pins
(brainir_causal.p4modal.gate / images); refused inputs are re-submitted. GPU containers run ungated, strict float32 (TF32 off), with
the host recorded. Results: research/phase4/GPU_BENCHMARK.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
OUT = ROOT / "research" / "phase4"
APP = "brainir-p4-gpubench"

# Modal list prices, USD per second (modal.com/pricing, read 2026-09-26). GPU prices are per GPU; containers also pay CPU and memory.
GPU_PRICE_S = {"B300": 0.001972, "B200": 0.001736, "H200": 0.001261, "H100": 0.001097, "RTX-PRO-6000": 0.000842, "A100-80GB": 0.000694,
               "A100-40GB": 0.000583, "L40S": 0.000542, "A10": 0.000306, "A10G": 0.000306, "L4": 0.000222, "T4": 0.000164}
CORE_S, GIB_S = 0.0000131, 0.00000222
GPU_CANDIDATES = ["T4", "L4", "A10", "A10G", "L40S", "A100-40GB", "A100-80GB", "RTX-PRO-6000", "H100", "H200", "B200", "B300"]
CPU_SIZES = [4, 8, 16, 32, 64]
CPU_MEM_MB = {4: 16384, 8: 16384, 16: 32768, 32: 32768, 64: 65536}
GPU_CPU, GPU_MEM_MB = 4.0, 32768
KINDS = ["rollout", "gru", "ens8", "node"]


def container_price_s(device: str) -> float:
    if device.startswith("cpu"):
        c = int(device[3:])
        return c * CORE_S + CPU_MEM_MB[c] / 1024 * GIB_S
    return GPU_PRICE_S[device] + GPU_CPU * CORE_S + GPU_MEM_MB / 1024 * GIB_S


# ------------------------------------------------------------------------------------------------ container callables (closures)
def _callables():
    def bench_cpu(spec):
        import sys as _s
        _s.path.insert(0, "/repo/p4bench")
        from p4modal import gate
        h = gate.host_cpu()
        if not gate.admissible(h):
            return gate.refusal(h)
        from p4modal import benchwork as B
        r = B.run_suite(spec["kinds"], "cpu", threads=spec["threads"], configs=[tuple(c) for c in spec["configs"]], **spec.get("kw", {}))
        r["host"] = h
        r["spec"] = spec
        return r

    def bench_gpu(spec):
        import sys as _s
        _s.path.insert(0, "/repo/p4bench")
        import torch
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        from p4modal import benchwork as B
        from p4modal import gate
        r = B.run_suite(spec["kinds"], "cuda", threads=spec.get("threads"), configs=[tuple(c) for c in spec["configs"]], **spec.get("kw", {}))
        r["host"] = gate.host_cpu()
        r["spec"] = spec
        return r

    def probe(_):
        import subprocess
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as e:  # noqa: BLE001
            out = f"error: {e!r}"
        return {"nvidia_smi": out}

    return bench_cpu, bench_gpu, probe


def _output():
    import modal
    return modal.enable_output()


# ------------------------------------------------------------------------------------------------ probe
def cmd_probe(candidates: list[str]) -> dict:
    """All candidates in one app (in parallel); if the app is refused (an unknown type string), one tiny app per candidate, so that an
    unknown type cannot fail the others."""
    import modal
    _, _, probe = _callables()
    res = {}
    app = modal.App(f"{APP}-probe")
    img = modal.Image.debian_slim(python_version="3.12")
    fns = {g: app.function(gpu=g, cpu=1.0, memory=2048, timeout=900, serialized=True, name=f"probe_{g.replace('-', '_')}", image=img)(probe)
           for g in candidates}
    t0 = time.time()
    try:
        with app.run():
            calls = {g: fn.spawn(None) for g, fn in fns.items()}
            for g, c in calls.items():
                try:
                    r = c.get(timeout=900)
                    res[g] = {"accepted": True, "nvidia_smi": r["nvidia_smi"], "wall_s": round(time.time() - t0, 1)}
                except Exception as e:  # noqa: BLE001
                    res[g] = {"accepted": False, "error": repr(e)[:400], "wall_s": round(time.time() - t0, 1)}
                print(g, json.dumps(res[g]), flush=True)
        return res
    except Exception as e:  # noqa: BLE001
        print(f"one-app probe refused ({e!r}); probing one candidate per app", flush=True)
    res = {}
    for g in candidates:
        app = modal.App(f"{APP}-probe")
        fn = app.function(gpu=g, cpu=1.0, memory=2048, timeout=600, serialized=True, name=f"probe_{g.replace('-', '_')}",
                          image=modal.Image.debian_slim(python_version="3.12"))(probe)
        t0 = time.time()
        try:
            with app.run():
                r = fn.remote(None)
            res[g] = {"accepted": True, "nvidia_smi": r["nvidia_smi"], "wall_s": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            res[g] = {"accepted": False, "error": repr(e)[:400], "wall_s": round(time.time() - t0, 1)}
        print(g, json.dumps(res[g]), flush=True)
    return res


# ------------------------------------------------------------------------------------------------ run
def cmd_run(devices: list[str], quick: bool) -> dict:
    import modal
    from brainir_causal.p4modal import images
    from brainir_causal.p4modal.benchwork import CONFIGS
    from brainir_causal.p4modal.gate import is_refusal
    configs = [CONFIGS[0], CONFIGS[-1]] if quick else CONFIGS
    kw = {"budget_s": 20.0, "max_steps": 10} if quick else {"budget_s": 30.0, "max_steps": 20}
    bench_cpu, bench_gpu, _ = _callables()
    app = modal.App(APP)
    fns = {}
    for d in devices:
        if d.startswith("cpu"):
            c = int(d[3:])
            fns[d] = app.function(cpu=float(c), memory=CPU_MEM_MB[c], timeout=3 * 3600, max_containers=8, serialized=True,
                                  image=images.bench_image(gpu=False), name=f"bench_{d}")(bench_cpu)
        else:
            fns[d] = app.function(gpu=d, cpu=GPU_CPU, memory=GPU_MEM_MB, timeout=3 * 3600, max_containers=4, serialized=True,
                                  image=images.bench_image(gpu=True), name=f"bench_{d.replace('-', '_').lower()}")(bench_gpu)
    # CPU: one container per workload kind (the slow side); GPU: one container per device (all kinds)
    jobs = []
    for d in devices:
        if d.startswith("cpu"):
            jobs += [(d, {"kinds": [k], "threads": int(d[3:]), "configs": [list(c) for c in configs], "kw": kw}) for k in KINDS]
        else:
            jobs.append((d, {"kinds": KINDS, "threads": None, "configs": [list(c) for c in configs], "kw": kw}))
    results, refusals, errors = [], {}, []
    t0 = time.time()
    with _output(), app.run() as run:
        app_id = getattr(run, "app_id", None)
        live = {i: (fns[d].spawn(s), d, s, 1) for i, (d, s) in enumerate(jobs)}
        last = time.time()
        while live:
            for i, (call, d, s, n) in list(live.items()):
                try:
                    r = call.get(timeout=0)
                except Exception as e:  # noqa: BLE001
                    if "timeout" in type(e).__name__.lower():
                        continue
                    errors.append({"device": d, "kinds": s["kinds"], "error": repr(e)[:600]})
                    del live[i]
                    continue
                if is_refusal(r):
                    refusals[d] = refusals.get(d, 0) + 1
                    if n >= 200:
                        errors.append({"device": d, "kinds": s["kinds"], "error": "no admissible host after 200 attempts"})
                        del live[i]
                    else:
                        live[i] = (fns[d].spawn(s), d, s, n + 1)
                    continue
                r["device"] = d
                results.append(r)
                del live[i]
                print(f"  {d} {s['kinds']} done ({time.time() - t0:.0f} s, container {r.get('wall_s')} s)", flush=True)
            if live:
                time.sleep(3)
            if time.time() - last > 120:
                print(f"  {len(jobs) - len(live)} of {len(jobs)} jobs done ({time.time() - t0:.0f} s); in flight: "
                      f"{sorted({v[1] for v in live.values()})}", flush=True)
                last = time.time()
    return {"app": APP, "app_id": app_id, "wall_s": round(time.time() - t0, 1), "quick": quick, "results": results,
            "refusals": refusals, "errors": errors, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


# ------------------------------------------------------------------------------------------------ table + recommendation
def summarize(raw: dict) -> dict:
    rows = []
    for r in raw["results"]:
        d = r["device"]
        price = container_price_s(d)
        for row in r["rows"]:
            if "error" in row:
                rows.append({"device": d, **{k: row[k] for k in ("kind", "n_x", "k", "t_len", "batch")}, "error": row["error"]})
                continue
            rows.append({"device": d, "kind": row["kind"], "n_x": row["n_x"], "k": row["k"], "t_len": row["t_len"], "batch": row["batch"],
                         "step_s": round(row["step_s_median"], 5), "epoch_s": round(row["epoch_s"], 3),
                         "usd_per_epoch": round(row["epoch_s"] * price, 6), "traj_per_s": round(row["traj_per_s"], 2),
                         "n_timed": row["n_timed"], "peak_mem_gb": row.get("peak_mem_gb"), "loss_finite": row["loss_finite"],
                         "gpu": r["info"].get("gpu"), "host_cpu": (r.get("host") or {}).get("model")})
    rec = {}
    for key in sorted({(x["kind"], x["n_x"], x["k"], x["t_len"], x["batch"]) for x in rows if "error" not in x}):
        cand = [x for x in rows if "error" not in x and (x["kind"], x["n_x"], x["k"], x["t_len"], x["batch"]) == key]
        fastest = min(cand, key=lambda x: x["step_s"])
        cheapest = min(cand, key=lambda x: x["usd_per_epoch"])
        best_cpu = min((x for x in cand if x["device"].startswith("cpu")), key=lambda x: x["step_s"], default=None)
        best_gpu = min((x for x in cand if not x["device"].startswith("cpu")), key=lambda x: x["step_s"], default=None)
        rec["|".join(map(str, key))] = {"fastest": fastest["device"], "fastest_step_s": fastest["step_s"],
                                        "cheapest_per_epoch": cheapest["device"], "cheapest_usd_per_epoch": cheapest["usd_per_epoch"],
                                        "best_cpu": best_cpu and best_cpu["device"], "best_cpu_step_s": best_cpu and best_cpu["step_s"],
                                        "best_gpu": best_gpu and best_gpu["device"], "best_gpu_step_s": best_gpu and best_gpu["step_s"],
                                        "cpu_wins": bool(best_cpu and best_gpu and best_cpu["step_s"] <= best_gpu["step_s"])}
    return {"rows": rows, "per_workload": rec}


KEEP_KEYS = ("equivalence", "recommendation")        # written by other commands (modal_p4.py equiv-gpu, by hand): never dropped


def write_report(raw: dict, probe: dict | None) -> None:
    summ = summarize(raw)
    old = json.loads((OUT / "GPU_BENCHMARK.json").read_text(encoding="utf-8")) if (OUT / "GPU_BENCHMARK.json").exists() else {}
    doc = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "app": raw.get("app"), "app_id": raw.get("app_id"),
           "wall_s": raw.get("wall_s"), "prices_usd_per_s": {"gpu": GPU_PRICE_S, "cpu_core": CORE_S, "memory_gib": GIB_S,
                                                             "source": "modal.com/pricing, read 2026-09-26 (standard, preemptible)"},
           "containers": {"cpu_mem_mb": CPU_MEM_MB, "gpu_container_cpu": GPU_CPU, "gpu_container_mem_mb": GPU_MEM_MB},
           "probe": probe, "refusals": raw.get("refusals"), "errors": raw.get("errors"),
           "device_info": {r["device"]: {**r["info"], "host": r.get("host")} for r in raw["results"]}, **summ}
    for k in KEEP_KEYS:
        if k in old:
            doc[k] = old[k]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "GPU_BENCHMARK.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    (OUT / "GPU_BENCHMARK.md").write_text(render_md(doc), encoding="utf-8", newline="\n")


def render_md(doc: dict) -> str:
    rows = doc["rows"]
    devs = sorted({r["device"] for r in rows}, key=lambda d: (not d.startswith("cpu"), int(d[3:]) if d.startswith("cpu") else container_price_s(d)))
    keys = sorted({(r["kind"], r["n_x"], r["k"], r["t_len"], r["batch"]) for r in rows}, key=lambda k: (k[0], k[1], k[3], k[4]))
    lines = ["# Phase 4 GPU / CPU benchmark (goal5 section 63)", "",
             f"Generated {doc['generated_utc']} by `scripts/p4/gpu_benchmark.py` (app `{doc.get('app')}`, wall {doc.get('wall_s')} s). "
             "Workloads: `brainir_causal.p4modal.benchwork` (latent controlled SSMs with an intervention read-in; float32, TF32 off, Adam). "
             "Step = forward + backward + optimiser step, median after warm-up; epoch = 1,024 trajectories. Cost per epoch at Modal list "
             "prices (standard, preemptible; container CPU and memory included): GPU containers "
             f"{doc['containers']['gpu_container_cpu']:g} cores / {doc['containers']['gpu_container_mem_mb'] // 1024} GiB; CPU containers "
             "run gated (no AVX-512) with the AVX2 kernel pins (the reproducible production configuration).", ""]
    rec = doc.get("recommendation")
    if rec:
        lines += ["## Recommendation", "", rec, ""]
    lines += ["## Seconds per training step", "", "| workload (kind, N_obs, k, T, batch) | " + " | ".join(devs) + " |",
              "|---|" + "---|" * len(devs)]
    for key in keys:
        cells = []
        for d in devs:
            r = next((x for x in rows if x["device"] == d and (x["kind"], x["n_x"], x["k"], x["t_len"], x["batch"]) == key), None)
            cells.append("-" if r is None else ("err" if "error" in r else f"{r['step_s']:.3g}"))
        lines.append(f"| {key[0]} {key[1]}/{key[2]} T={key[3]} B={key[4]} | " + " | ".join(cells) + " |")
    lines += ["", "## USD per epoch (1,024 trajectories)", "", "| workload | " + " | ".join(devs) + " |", "|---|" + "---|" * len(devs)]
    for key in keys:
        cells = []
        for d in devs:
            r = next((x for x in rows if x["device"] == d and (x["kind"], x["n_x"], x["k"], x["t_len"], x["batch"]) == key), None)
            cells.append("-" if r is None else ("err" if "error" in r else f"{r['usd_per_epoch']:.2g}"))
        lines.append(f"| {key[0]} {key[1]}/{key[2]} T={key[3]} B={key[4]} | " + " | ".join(cells) + " |")
    lines += ["", "## Fastest and cheapest per workload", "", "| workload | fastest | step s | cheapest per epoch | USD | best CPU | best GPU | CPU wins |",
              "|---|---|---|---|---|---|---|---|"]
    for k, v in doc["per_workload"].items():
        lines.append(f"| {k.replace('|', ' ')} | {v['fastest']} | {v['fastest_step_s']:.3g} | {v['cheapest_per_epoch']} | {v['cheapest_usd_per_epoch']:.2g} | "
                     f"{v['best_cpu']} ({v['best_cpu_step_s'] and round(v['best_cpu_step_s'], 3)}) | {v['best_gpu']} ({v['best_gpu_step_s'] and round(v['best_gpu_step_s'], 3)}) | "
                     f"{'yes' if v['cpu_wins'] else 'no'} |")
    eq = doc.get("equivalence")
    if eq:
        t64, t32 = eq["tolerances"]["float64"], eq["tolerances"]["float32"]
        lines += ["", "## CPU / GPU equivalence (brainir_causal.equiv; goal5 acceptance criterion 39)", "",
                  f"Builder `{eq['builder']}` (a latent controlled SSM with an intervention read-in, `rollout`, and a GRU filter, `gru`; cuDNN on "
                  f"GPUs), {eq['steps']} Adam steps from the same seed, parameters and data created on the CPU and then moved. In one GPU container: "
                  "a CPU run and two GPU runs. Tolerances, stated before any GPU run: float64 loss / parameters / predictions "
                  f"{t64['loss_rel']:g} / {t64['param_rel']:g} / {t64['pred_rel']:g} relative; float32 (TF32 off) {t32['loss_rel']:g} / "
                  f"{t32['param_rel']:g} / {t32['pred_rel']:g}. Determinism: deterministic algorithms, cuDNN deterministic without autotuning, "
                  f"cuBLAS workspace {eq['settings'].get('cublas_workspace')}. App `{eq.get('app_id')}`; all pass: **{eq.get('all_pass')}**.", "",
                  "| GPU class | model | dtype | GPU vs CPU (same container): loss, params, predictions | GPU run to run | container CPU vs local (Windows) CPU: params | criterion 39 |",
                  "|---|---|---|---|---|---|---|"]
        for r in eq["rows"]:
            if "error" in r:
                lines.append(f"| {r.get('gpu_class')} | - | - | error: {str(r['error'])[:80]} | - | - | - |")
                continue
            g, t, lc = r["gpu_vs_cpu"], r["gpu_run_to_run"], r.get("container_cpu_vs_local_cpu") or {}
            lines.append(f"| {r['gpu_class']} ({r.get('gpu')}) | {r['config']['kind']} | {r['dtype']} | {g['loss_rel_max']:.1e}, {g['param_rel']:.1e}, "
                         f"{g['pred_rel']:.1e} | {'bitwise identical' if t['bitwise_identical'] else 'differs'} | "
                         f"{lc.get('param_rel', float('nan')):.1e} | {'pass' if r.get('criterion_39_pass') else 'FAIL'} |")
        if eq.get("platform_note"):
            lines += ["", eq["platform_note"]]
    if doc.get("probe"):
        lines += ["", "## GPU type strings (probe)", "", "| string | accepted | nvidia-smi |", "|---|---|---|"]
        for g, p in doc["probe"].items():
            lines.append(f"| {g} | {'yes' if p.get('accepted') else 'no'} | {(p.get('nvidia_smi') or p.get('error') or '')[:120]} |")
    lines += ["", "## Devices", ""]
    for d, info in doc["device_info"].items():
        lines.append(f"- {d}: {info.get('gpu') or info.get('cpu_model')} (torch {info.get('torch')}, CUDA {info.get('cuda')}, threads "
                     f"{info.get('threads')}, host {((info.get('host') or {}).get('model'))})")
    if doc.get("errors"):
        lines += ["", "## Errors", ""] + [f"- {e}" for e in doc["errors"]]
    errs = [r for r in rows if "error" in r]
    if errs:
        lines += ["", "## Failed cases (recorded, not retried)", ""] + [
            f"- {r['device']} {r['kind']} {r['n_x']}/{r['k']} T={r['t_len']} B={r['batch']}: {str(r['error'])[:160]}" for r in errs]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--candidates", default=",".join(GPU_CANDIDATES))
    r = sub.add_parser("run")
    r.add_argument("--devices", default=None, help="comma list: cpu4..cpu64 and accepted GPU strings (default: all CPU sizes + probed GPUs)")
    r.add_argument("--quick", action="store_true")
    sub.add_parser("report")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    probe_file = OUT / "GPU_BENCHMARK.json"
    if a.cmd == "probe":
        res = cmd_probe([c for c in a.candidates.split(",") if c])
        old = json.loads(probe_file.read_text(encoding="utf-8")) if probe_file.exists() else {}
        old["probe"] = res
        probe_file.write_text(json.dumps(old, indent=1) + "\n", encoding="utf-8", newline="\n")
        return 0
    if a.cmd == "run":
        old = json.loads(probe_file.read_text(encoding="utf-8")) if probe_file.exists() else {}
        probe = old.get("probe")
        if a.devices:
            devices = [d for d in a.devices.split(",") if d]
        else:
            gpus = [g for g, v in (probe or {}).items() if v.get("accepted") and g != "A10G"]
            devices = [f"cpu{c}" for c in CPU_SIZES] + gpus
        raw = cmd_run(devices, a.quick)
        (OUT / "GPU_BENCHMARK.raw.json").write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8", newline="\n")
        write_report(raw, probe)
        return 0
    raw = json.loads((OUT / "GPU_BENCHMARK.raw.json").read_text(encoding="utf-8"))
    old = json.loads(probe_file.read_text(encoding="utf-8")) if probe_file.exists() else {}
    rec = old.get("recommendation")
    write_report(raw, old.get("probe"))
    if rec:
        doc = json.loads(probe_file.read_text(encoding="utf-8"))
        doc["recommendation"] = rec
        probe_file.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
        (OUT / "GPU_BENCHMARK.md").write_text(render_md(doc), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
