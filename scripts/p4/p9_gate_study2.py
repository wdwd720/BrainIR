"""Host-gate study, round 2 (ORCHESTRATOR ONLY; fork P9; research/phase4/HOST_GATE_STUDY.md).

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py start scripts/p4/p9_gate_study2.py run --n 60 --tag r2
    uv run --no-sync --project phase4 python scripts/p4/p9_gate_study2.py analyse --tag r2

Round 1 (p9_gate_study.py r1) showed: AMD model-17 AVX-512 hosts crash (SIGSEGV) whenever OPENBLAS_CORETYPE is forced, and differ
without it; the one Intel model-85 host matched every numpy / scipy workload with the core type forced but not the torch one. Round 2:
(1) LOCALISES the crash: micro tests (numpy matmul, scipy.linalg, numpy.linalg.svd / lstsq, torch matmul) and every battery workload
    in its OWN process with faulthandler, under the core type forced alone and with the MKL pins;
(2) tests MKL's reproducibility modes for torch (MKL_CBWR=COMPATIBLE; MKL_CBWR=AVX2,STRICT), each with the core type forced, on EVERY
    host (admissible hosts give the same-pin reference);
(3) more containers, to meet more AVX-512 host models.
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
OB = {"OPENBLAS_CORETYPE": "Haswell"}
MKLI = {"MKL_ENABLE_INSTRUCTIONS": "AVX2", "ONEDNN_MAX_CPU_ISA": "AVX2"}
VARIANTS = {"base": {}, "ob": dict(OB), "mkl_avx2_ob": {**MKLI, "MKL_CBWR": "AVX2", **OB},
            "mkl_compat_ob": {**MKLI, "MKL_CBWR": "COMPATIBLE", **OB}, "mkl_strict_ob": {**MKLI, "MKL_CBWR": "AVX2,STRICT", **OB}}
WORKLOADS = ("gen", "real", "refs", "eval", "v1")
MICRO = r'''
import hashlib, sys
kind = sys.argv[1]
import numpy as np
rng = np.random.default_rng(0)
a = rng.standard_normal((257, 257)); b = rng.standard_normal((257, 131))
if kind == "np_matmul":
    out = a @ b
elif kind == "np_svd":
    out = np.linalg.svd(a)[1]
elif kind == "np_lstsq":
    out = np.linalg.lstsq(a, b, rcond=None)[0]
elif kind == "scipy_solve":
    import scipy.linalg as sl
    out = sl.solve(a @ a.T + 257 * np.eye(257), b)
elif kind == "torch_matmul":
    import torch
    torch.set_num_threads(1)
    out = (torch.from_numpy(a) @ torch.from_numpy(b)).numpy()
print("MICRO", hashlib.sha256(np.ascontiguousarray(out).tobytes()).hexdigest())
'''
MICRO_KINDS = ("np_matmul", "np_svd", "np_lstsq", "scipy_solve", "torch_matmul")
SHAPES = {"s": (4.0, 16384), "l": (16.0, 65536), "x": (32.0, 131072)}


def _image():
    from brainir_causal import suites as SU
    from brainir_causal.p4modal import images
    img = images.full_image(gpu=False, extra_pip=["pytest==9.1.1"],
                            extra_dirs={SU.GENERATOR_REL: SU.GENERATOR_CONTAINER, "phase4/tests": "/repo/phase4/tests"})
    return img.add_local_file(str(ROOT / "scripts" / "p4" / "p9_gate_battery.py"), "/repo/scripts/p4/p9_gate_battery.py")


def cmd_run(args) -> int:
    import modal
    internal = json.loads((ROOT / "benchmarks" / "causal_state_v1" / "hidden" / "real_systems_internal.json").read_text(encoding="utf-8"))
    sysdefs = {s: internal[s] for s in ("real:A:m1", "real:A:full")}
    app = modal.App(f"brainir-p4-p9-gate-{args.tag}")
    image = _image()

    def probe(payload: dict) -> dict:
        import os
        import subprocess
        import sys as _s
        import time as _t
        t0 = _t.time()
        info = {}
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
            block = fh.read().split("\n\n")[0]
        for line in block.splitlines():
            k, _, v = line.partition(":")
            k = k.strip()
            if k in ("vendor_id", "cpu family", "model", "model name", "stepping", "microcode", "cache size"):
                info[k] = v.strip()
            elif k == "flags":
                info["flags_simd"] = sorted(f for f in v.split() if f.startswith(("avx", "fma", "amx")))
        from brainir_causal.p4modal import gate as G
        adm = bool(G.admissible(G.host_cpu()))
        info["gate_admissible"] = adm
        info["nproc"] = os.cpu_count()
        with open("/tmp/p9_sysdefs.json", "w", encoding="utf-8") as fh:
            json.dump(payload["sysdefs"], fh)
        with open("/tmp/p9_micro.py", "w", encoding="utf-8") as fh:
            fh.write(payload["micro"])
        base_env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONFAULTHANDLER": "1"}
        micro, runs = [], []
        # admissible containers: every variant x workload only on the first few (the same-pin reference); later ones record the host.
        # gatecheck mode: EVERY admissible container runs the full battery (the current gate's classes), AVX-512 hosts only record
        if payload.get("gatecheck"):
            full = adm
        else:
            full = (not adm) or payload["i"] < payload["n_ref"]
        for vname, extra in payload["variants"].items():
            env = {**base_env, **extra}
            if vname != "base" and not payload.get("gatecheck"):
                for kind in payload["micro_kinds"]:
                    r = subprocess.run([_s.executable, "/tmp/p9_micro.py", kind], env=env, capture_output=True, text=True, timeout=600)
                    h = next((ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("MICRO ")), None)
                    micro.append({"variant": vname, "kind": kind, "returncode": r.returncode, "hash": h,
                                  "stderr_tail": "" if h else r.stderr[-1200:]})
            if not full:
                continue
            for threads, w in [(th, w) for th, ws in payload.get("thread_sets", [[1, list(payload["workloads"])]]) for w in ws]:
                ts = _t.time()
                env_t = {**env, "OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads)}
                r = subprocess.run([_s.executable, "/repo/scripts/p4/p9_gate_battery.py", "--threads", str(threads), "--only", w,
                                    "--sysdefs", "/tmp/p9_sysdefs.json"], env=env_t, capture_output=True, text=True, timeout=2400)
                line = next((ln for ln in r.stdout.splitlines() if ln.startswith("P9RESULT ")), None)
                res = json.loads(line[len("P9RESULT "):]) if line else None
                wl = (res or {}).get("workloads", {}).get(w)
                runs.append({"variant": vname, "workload": w, "threads": threads, "returncode": r.returncode, "hashes": (wl or {}).get("hashes"),
                             "summ": (wl or {}).get("summ"), "error": (wl or {}).get("error"),
                             "blas": (res or {}).get("libs_after", {}).get("blas"),
                             "stderr_tail": "" if res else r.stderr[-2500:], "s": round(_t.time() - ts, 1)})
        return {"input": payload["i"], "shape": payload["shape"], "host": info, "micro": micro, "runs": runs, "full": full,
                "wall_s": round(_t.time() - t0, 1)}

    fns = {s: app.function(image=image, cpu=c, memory=m, timeout=4 * 3600, max_containers=60, serialized=True, name=f"p9b_{s}",
                           max_inputs=1)(probe) for s, (c, m) in SHAPES.items()}
    shapes = sorted(SHAPES)
    gate = args.mode == "gatecheck"
    payloads = [{"i": i, "shape": shapes[i % len(shapes)], "variants": {"base": {}} if gate else VARIANTS, "workloads": list(WORKLOADS),
                 "sysdefs": sysdefs, "micro": MICRO, "micro_kinds": list(MICRO_KINDS), "n_ref": args.n_ref, "gatecheck": gate,
                 "thread_sets": [[1, list(WORKLOADS)], [4, ["refs", "eval", "v1"]]] if gate else [[1, list(WORKLOADS)]]}
                for i in range(args.n)]
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with modal.enable_output(), app.run() as run_ctx:
        from concurrent.futures import ThreadPoolExecutor
        by = {s: [p for p in payloads if p["shape"] == s] for s in shapes}
        with ThreadPoolExecutor(len(shapes)) as ex:
            outs = [r for f in [ex.submit(lambda s: list(fns[s].map(by[s], return_exceptions=True)), s) for s in shapes] for r in f.result()]
        app_id = getattr(run_ctx, "app_id", None)
    res = [o if isinstance(o, dict) else {"exception": repr(o)[:1000]} for o in outs]
    rec = {"tag": args.tag, "app_id": app_id, "wall_s": round(time.time() - t0, 1), "variants": VARIANTS, "n": args.n, "containers": res}
    (OUT / f"raw_{args.tag}.json").write_text(json.dumps(rec) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"tag": args.tag, "app_id": app_id, "wall_s": rec["wall_s"], "containers": len(res),
                      "exceptions": sum(1 for r in res if "exception" in r)}))
    return 0


def hclass(h: dict) -> str:
    fl = set(h.get("flags_simd") or [])
    isa = "avx512" if any(f.startswith("avx512") for f in fl) else "avx2"
    return f"{h.get('vendor_id')}/m{h.get('model')}/{isa}" + ("+amx" if any(f.startswith("amx") for f in fl) else "")


def cmd_analyse(args) -> int:
    from collections import defaultdict
    rec = json.loads((OUT / f"raw_{args.tag}.json").read_text(encoding="utf-8"))
    conts = [c for c in rec["containers"] if "host" in c]
    ref, ref_n, ref_bad, ref_host, ref_classes = {}, defaultdict(int), [], {}, defaultdict(set)
    mref = {}
    for c in conts:
        if not c["host"].get("gate_admissible"):
            continue
        for m in c["micro"]:
            if m["hash"]:
                k = (m["variant"], m["kind"])
                mref.setdefault(k, m["hash"])
                if mref[k] != m["hash"]:
                    ref_bad.append(("micro",) + k)
        for r in c["runs"]:
            if not r.get("hashes"):
                continue
            k = (r["variant"], r["workload"], r.get("threads", 1))
            if k not in ref:
                ref[k], ref_host[k] = r["hashes"], hclass(c["host"])
            ref_n[k] += 1
            ref_classes[k].add(hclass(c["host"]))
            if r["hashes"] != ref[k]:
                ref_bad.append({"key": k, "host": hclass(c["host"]), "ref_host": ref_host[k],
                                "arrays": sorted(a for a in ref[k] if ref[k][a] != r["hashes"].get(a))[:3]})
    classes = defaultdict(int)
    for c in conts:
        classes[hclass(c["host"]) + (" (admissible)" if c["host"].get("gate_admissible") else "")] += 1
    table = defaultdict(lambda: defaultdict(lambda: {"same": 0, "diff": 0, "crash": 0, "err": 0, "first": None, "stderr": None}))
    mtable = defaultdict(lambda: defaultdict(lambda: {"same": 0, "diff": 0, "crash": 0, "stderr": None}))
    for c in conts:
        if c["host"].get("gate_admissible"):
            continue
        hc = hclass(c["host"])
        for m in c["micro"]:
            cell = mtable[f"{hc} | {m['variant']}"][m["kind"]]
            if m["hash"] is None:
                cell["crash"] += 1
                cell["stderr"] = cell["stderr"] or m["stderr_tail"][-400:]
            else:
                cell["same" if m["hash"] == mref.get((m["variant"], m["kind"])) else "diff"] += 1
        for r in c["runs"]:
            cell = table[f"{hc} | {r['variant']}"][r["workload"]]
            if r.get("hashes") is None:
                cell["crash" if (r.get("returncode") or 0) < 0 else "err"] += 1
                cell["stderr"] = cell["stderr"] or (r.get("stderr_tail") or r.get("error") or "")[-600:]
                continue
            rf = ref.get((r["variant"], r["workload"], r.get("threads", 1)))
            if r["hashes"] == rf:
                cell["same"] += 1
            else:
                cell["diff"] += 1
                if rf:
                    cell["first"] = cell["first"] or sorted(k for k in rf if rf[k] != r["hashes"].get(k))[:2]
    out = {"tag": args.tag, "host_classes": dict(classes), "reference_disagreements": ref_bad,
           "reference_counts": {"|".join(map(str, k)): v for k, v in ref_n.items()},
           "reference_host_classes": {"|".join(map(str, k)): sorted(v) for k, v in ref_classes.items()},
           "micro": {k: dict(v) for k, v in mtable.items()}, "workloads": {k: dict(v) for k, v in table.items()}}
    (OUT / f"analysis_{args.tag}.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"host_classes": out["host_classes"], "reference_disagreements": ref_bad}, indent=1))
    print("reference counts:", out["reference_counts"])
    print("admissible host classes per reference key:", out["reference_host_classes"])
    for k in sorted(mtable):
        print("MICRO", k, {kind: f"{c['same']}={c['diff']}x{c['crash']}" for kind, c in mtable[k].items()})
    for k in sorted(table):
        print("WL   ", k, {w: f"{c['same']}={c['diff']}x{c['crash']}!{c['err']}" + (f" {c['first']}" if c["first"] else "") for w, c in table[k].items()})
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--n", type=int, default=60)
    r.add_argument("--n-ref", type=int, default=6, help="admissible containers (by input index) that run the full reference")
    r.add_argument("--tag", required=True)
    r.add_argument("--mode", choices=("pins", "gatecheck"), default="pins",
                   help="gatecheck: every admissible container runs the full battery under the official pins at 1 and 4 threads")
    a = sub.add_parser("analyse")
    a.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_analyse(args)


if __name__ == "__main__":
    raise SystemExit(main())
