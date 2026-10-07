"""Host-gate study driver (ORCHESTRATOR ONLY; fork P9; research/phase4/HOST_GATE_STUDY.md).

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py start scripts/p4/p9_gate_study.py run --n 24 --tag r1
    uv run --no-sync --project phase4 python scripts/p4/p9_gate_study.py analyse --tag r1

`run`: a separate Modal app (never the official classes; NO host gate: every host kind is used on purpose) whose containers take ONE
input each (fresh containers, so fresh hosts). Every container records its host (vendor, cpuid family / model / stepping, the SIMD
flags) and runs scripts/p4/p9_gate_battery.py in fresh processes, once per candidate pin set (VARIANTS) and thread count, capturing
crashes by signal. Three container shapes (4 / 16 / 32 CPU) to reach more host pools. Raw results go to
research/phase4/host_gate_study/raw_<tag>.json.
`analyse`: groups containers by host class, checks that the admissible hosts agree among themselves under the official pins
(the reference), then compares every (non-admissible host, pin set, thread count) with the reference, workload by workload and array
by array, with the magnitude of the first differences from the sampled values.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))
OUT = ROOT / "research" / "phase4" / "host_gate_study"
MKL = {"MKL_ENABLE_INSTRUCTIONS": "AVX2", "MKL_CBWR": "AVX2", "ONEDNN_MAX_CPU_ISA": "AVX2"}
#: candidate pin sets, strict to relaxed; "base" = the official image pins only (numpy and ATen AVX2 paths)
VARIANTS = {"base": {}, "mkl": dict(MKL), "mkl_ob_haswell": {**MKL, "OPENBLAS_CORETYPE": "Haswell"},
            "mkl_ob_zen": {**MKL, "OPENBLAS_CORETYPE": "Zen"}}
REAL_SYSTEMS = ("real:A:m1", "real:A:full")
#: container shapes (CPU, MiB): different shapes may be placed on different host pools
SHAPES = {"s": (4.0, 16384), "l": (16.0, 65536), "x": (32.0, 131072)}


def _image():
    from brainir_causal import suites as SU
    from brainir_causal.p4modal import images
    img = images.full_image(gpu=False, extra_pip=["pytest==9.1.1"],     # the battery imports two test modules (pytest at import)
                            extra_dirs={SU.GENERATOR_REL: SU.GENERATOR_CONTAINER, "phase4/tests": "/repo/phase4/tests"})
    return img.add_local_file(str(ROOT / "scripts" / "p4" / "p9_gate_battery.py"), "/repo/scripts/p4/p9_gate_battery.py")


def cmd_run(args) -> int:
    import modal
    internal = json.loads((ROOT / "benchmarks" / "causal_state_v1" / "hidden" / "real_systems_internal.json").read_text(encoding="utf-8"))
    sysdefs = {s: internal[s] for s in REAL_SYSTEMS}
    app = modal.App(f"brainir-p4-p9-gate-{args.tag}")
    image = _image()

    def probe(payload: dict) -> dict:
        import os
        import subprocess
        import sys as _s
        import time as _t
        t0 = _t.time()
        info = {}
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
                block = fh.read().split("\n\n")[0]
            for line in block.splitlines():
                k, _, v = line.partition(":")
                k = k.strip()
                if k in ("vendor_id", "cpu family", "model", "model name", "stepping", "microcode", "cpu MHz", "cache size", "siblings"):
                    info[k] = v.strip()
                elif k == "flags":
                    fl = v.split()
                    info["flags_simd"] = sorted(f for f in fl if f.startswith(("avx", "fma", "amx", "sse4", "vaes", "vpclmul", "gfni", "sha")))
        except OSError as exc:
            info["error"] = str(exc)
        from brainir_causal.p4modal import gate as G
        host = G.host_cpu()
        info["gate_admissible"] = bool(G.admissible(host))
        info["nproc"] = os.cpu_count()
        with open("/tmp/p9_sysdefs.json", "w", encoding="utf-8") as fh:
            json.dump(payload["sysdefs"], fh)
        runs = []
        for vname, extra in payload["variants"].items():
            for threads, only in (((1, ""),) if payload.get("pilot") else ((1, ""), (4, "refs,eval,v1"))):
                env = {**os.environ, **extra, "OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads),
                       "MKL_NUM_THREADS": str(threads), "PYTHONDONTWRITEBYTECODE": "1"}
                cmd = [_s.executable, "/repo/scripts/p4/p9_gate_battery.py", "--threads", str(threads), "--sysdefs", "/tmp/p9_sysdefs.json"]
                if only:
                    cmd += ["--only", only]
                if payload.get("pilot"):
                    cmd += ["--quick"]
                ts = _t.time()
                try:
                    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=payload.get("timeout", 2400))
                    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("P9RESULT ")), None)
                    res = json.loads(line[len("P9RESULT "):]) if line else None
                    runs.append({"variant": vname, "threads": threads, "returncode": r.returncode, "result": res,
                                 "stderr_tail": "" if res else (r.stderr[-1500:] + r.stdout[-500:]), "s": round(_t.time() - ts, 1)})
                except subprocess.TimeoutExpired:
                    runs.append({"variant": vname, "threads": threads, "returncode": None, "result": None, "stderr_tail": "timeout",
                                 "s": round(_t.time() - ts, 1)})
        return {"input": payload["i"], "shape": payload["shape"], "host": info, "runs": runs, "wall_s": round(_t.time() - t0, 1)}

    fns = {}
    for shape, (cpu, mem) in SHAPES.items():
        fns[shape] = app.function(image=image, cpu=cpu, memory=mem, timeout=4 * 3600, max_containers=60, serialized=True,
                                  name=f"p9_probe_{shape}", max_inputs=1)(probe)
    variants = {"base": {}} if args.pilot else VARIANTS
    shapes = sorted(SHAPES)
    payloads = [{"i": i, "shape": shapes[i % len(shapes)], "variants": variants, "sysdefs": sysdefs, "pilot": bool(args.pilot)}
                for i in range(args.n)]
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with modal.enable_output(), app.run() as run_ctx:
        from concurrent.futures import ThreadPoolExecutor
        by = {s: [p for p in payloads if p["shape"] == s] for s in shapes}

        def go(shape):
            return list(fns[shape].map(by[shape], return_exceptions=True))
        with ThreadPoolExecutor(len(shapes)) as ex:
            outs = [r for f in [ex.submit(go, s) for s in by] for r in f.result()]
        app_id = getattr(run_ctx, "app_id", None)
    res = [o if isinstance(o, dict) else {"exception": repr(o)[:1000]} for o in outs]
    rec = {"tag": args.tag, "app_id": app_id, "wall_s": round(time.time() - t0, 1), "variants": VARIANTS, "n": args.n, "containers": res}
    (OUT / f"raw_{args.tag}.json").write_text(json.dumps(rec) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"tag": args.tag, "app_id": app_id, "wall_s": rec["wall_s"], "containers": len(res),
                      "exceptions": sum(1 for r in res if "exception" in r)}))
    return 0


# ------------------------------------------------------------------------------------------------------------ analysis
def host_class(h: dict) -> str:
    flags = set(h.get("flags_simd") or [])
    isa = "avx512" if any(f.startswith("avx512") for f in flags) else ("avx2" if "avx2" in flags else "other")
    extra = "+amx" if any(f.startswith("amx") for f in flags) else ""
    return f"{h.get('vendor_id', '?')}/fam{h.get('cpu family', '?')}/model{h.get('model', '?')}/{isa}{extra}"


def cmd_analyse(args) -> int:
    rec = json.loads((OUT / f"raw_{args.tag}.json").read_text(encoding="utf-8"))
    conts = [c for c in rec["containers"] if "host" in c]
    ref: dict = {}          # (threads, workload) -> {array: sha} from admissible hosts under "base"
    ref_hosts: dict = {}
    disagreements = []
    for c in conts:
        if not c["host"].get("gate_admissible"):
            continue
        for r in c["runs"]:
            if r["variant"] != "base" or not r.get("result"):
                continue
            for w, v in r["result"]["workloads"].items():
                key = (r["threads"], w)
                if v.get("error"):
                    disagreements.append({"host": host_class(c["host"]), "threads": r["threads"], "workload": w, "error": v["error"][:200]})
                    continue
                if key not in ref:
                    ref[key], ref_hosts[key] = v["hashes"], host_class(c["host"])
                elif v["hashes"] != ref[key]:
                    diff = sorted(k for k in set(ref[key]) | set(v["hashes"]) if ref[key].get(k) != v["hashes"].get(k))
                    disagreements.append({"host": host_class(c["host"]), "ref_host": ref_hosts[key], "threads": r["threads"], "workload": w,
                                          "n_diff": len(diff), "first": diff[:3]})
    table: dict = {}
    for c in conts:
        hc = host_class(c["host"]) + (" (admissible)" if c["host"].get("gate_admissible") else "")
        for r in c["runs"]:
            key0 = (hc, r["variant"], r["threads"])
            row = table.setdefault(f"{key0[0]} | {key0[1]} | t{key0[2]}", {"containers": 0, "crashes": 0, "workloads": {}})
            row["containers"] += 1
            if r.get("returncode") is not None and r["returncode"] < 0:
                row["crashes"] += 1
            if not r.get("result"):
                row.setdefault("failures", []).append((r.get("returncode"), (r.get("stderr_tail") or "")[-300:]))
                continue
            for w, v in r["result"]["workloads"].items():
                cell = row["workloads"].setdefault(w, {"identical": 0, "different": 0, "errors": 0, "first_diff": None, "max_rel": 0.0})
                refh = ref.get((r["threads"], w))
                if v.get("error"):
                    cell["errors"] += 1
                    continue
                if refh is None:
                    continue
                if v["hashes"] == refh:
                    cell["identical"] += 1
                else:
                    cell["different"] += 1
                    diff = sorted(k for k in set(refh) | set(v["hashes"]) if refh.get(k) != v["hashes"].get(k))
                    cell["first_diff"] = cell["first_diff"] or diff[:2]
                    # magnitude from the sampled values of the first differing array (relative to its absolute sum)
                    rs = _ref_summ(conts, r["threads"], w, diff[0])
                    vs = (v.get("summ") or {}).get(diff[0])
                    if rs and vs and len(rs) == len(vs):
                        scale = max(abs(rs[1]), 1e-300)
                        rel = max(abs(a - b) for a, b in zip(rs, vs)) / scale
                        cell["max_rel"] = max(cell["max_rel"], rel)
    out = {"tag": args.tag, "reference_disagreements_among_admissible_hosts": disagreements, "table": table,
           "host_classes": sorted({host_class(c["host"]) + (" (admissible)" if c["host"].get("gate_admissible") else "") for c in conts}),
           "libs_by_class": _libs(conts)}
    (OUT / f"analysis_{args.tag}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: out[k] for k in ("host_classes", "reference_disagreements_among_admissible_hosts")}, indent=1)[:6000])
    for k, row in sorted(table.items()):
        cells = " ".join(f"{w}:{c['identical']}={c['different']}!{c['errors']}" + (f"(rel {c['max_rel']:.1e})" if c["different"] else "")
                         for w, c in sorted(row["workloads"].items()))
        print(f"{k}: n={row['containers']} crash={row['crashes']} {cells}" + (f" FAIL {row.get('failures')[:1]}" if row.get("failures") else ""))
    return 0


def _ref_summ(conts, threads, w, name):
    for c in conts:
        if not c["host"].get("gate_admissible"):
            continue
        for r in c["runs"]:
            if r["variant"] == "base" and r["threads"] == threads and r.get("result"):
                s = (r["result"]["workloads"].get(w) or {}).get("summ") or {}
                if name in s:
                    return s[name]
    return None


def _libs(conts) -> dict:
    out: dict = {}
    for c in conts:
        hc = host_class(c["host"])
        for r in c["runs"]:
            if not r.get("result"):
                continue
            la = r["result"].get("libs_after") or {}
            key = f"{hc} | {r['variant']}"
            if key in out:
                continue
            out[key] = {"blas": [(b.get("lib", "")[:40], b.get("internal_api"), b.get("architecture")) for b in (la.get("blas") or [])
                                 if isinstance(b, dict)], "torch": la.get("torch"), "numpy_features_on": la.get("numpy_features_on")}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--n", type=int, default=24)
    r.add_argument("--tag", required=True)
    r.add_argument("--pilot", action="store_true", help="one pin set, one thread count, quick battery (pipeline check)")
    a = sub.add_parser("analyse")
    a.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_analyse(args)


if __name__ == "__main__":
    raise SystemExit(main())
