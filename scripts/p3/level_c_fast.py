"""The FROZEN Level C driver with a faster Modal scheduler (orchestrator; LOG P3-D27). Not hashed by the benchmark lock: it changes no
hashed file, no computation and no job, only how the jobs are placed on Modal.

    uv run --project phase3 --no-sync python scripts/p3/level_c_fast.py <level_c.py arguments>
    uv run --project phase3 --no-sync python scripts/p3/level_c_fast.py --validate-modal | --validate-local | --validate-compare

Like `modal_tournament.py level-c` (cmd_level_c), it runs scripts/p3/level_c.py as is, with its execution functions replaced:
- evaluations, reference controls and reproducibility use the FROZEN modal_tournament functions, on a wider evaluation pool;
- fits use `fast_run_fits_real`. It builds the frozen payloads (modal_tournament.modal_run_fits_real, byte for byte), runs the
  same frozen container callables, and writes the same output files. What changes is placement:
  1. per-size worker classes. Mechanism systems, one full network, and several systems including a full network (joint / shared
     training) get separate functions, each with memory well above the measured peaks (real full-network fits: 6.9-8.2 GB).
     Memory does not limit concurrency here: the workspace's limit is about 100 containers;
  2. 4 physical cores per fit. The locked fits run 3 threads (METHOD_LOCK budgets), so each thread gets a full core instead of a
     hyperthread. The thread count and every computation are unchanged;
  3. all independent fits of a driver call are submitted at once, longest class first. The short mechanism fits follow after a
     delay, so that the long joint fits hold containers from the start;
  4. non-preemptible containers for the long classes (a preempted 30-minute fit would restart from zero);
  5. results are written as each fit finishes. Finished fits are never recomputed (the frozen output-file cache).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase3" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "p3"))

CLASSES = {                       # name: resources (cpu = physical cores); memory well above the measured peaks
    "fit_small": {"cpu": 4.0, "memory": 16384, "nonpreemptible": False},     # mechanism systems (a few neurons)
    "fit_full": {"cpu": 4.0, "memory": 32768, "nonpreemptible": True},       # one full network (peak 8.2 GB measured)
    "fit_joint": {"cpu": 4.0, "memory": 131072, "nonpreemptible": True},     # several systems incl. a full network
    "eval": {"cpu": 4.0, "memory": 32768, "nonpreemptible": False},          # evaluations, references, reproducibility
}
ORDER = ("fit_joint", "fit_full", "fit_small")
SMALL_DELAY_S = 45                # the long classes get their containers first
MAX_CONTAINERS = 100              # the workspace limit measured on 2026-09-26 (quota probe: 99 concurrent)


def _gate(call):
    """The container-side host gate (LOG P3-D27): on a host with AVX-512 (whose BLAS kernels differ from the development machine's),
    refuse BEFORE running anything, and stop fetching inputs so that this container exits gracefully and its slot goes to a fresh
    host; otherwise run the frozen callable unchanged. Self-contained (it runs in the container's main process)."""
    def gated(payload):
        flags = set()
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("flags"):
                        flags = set(line.split(":", 1)[1].split())
                        break
        except OSError:
            pass
        if "avx512f" in flags or "avx2" not in flags:
            try:
                import modal.experimental as E
                E.stop_fetching_inputs()
            except Exception:  # noqa: BLE001
                pass
            return {"__refused__": True, "avx512f": "avx512f" in flags}
        r = call(payload)
        if isinstance(r, dict):
            r["__host__"] = {"avx512f": False, "avx2": True}
        return r
    return gated


def make_app():
    import modal
    import modal_tournament as MT
    app = modal.App("brainir-p3-levelc-fast", image=MT.image())
    fitvol = modal.Volume.from_name(MT.FIT_VOLUME, create_if_missing=True)
    evalvol = modal.Volume.from_name(MT.EVAL_VOLUME, create_if_missing=True)
    retries = modal.Retries(max_retries=3, initial_delay=2.0, backoff_coefficient=1.0)      # the frozen retry policy
    fit_call, eval_call = MT._remote_callables()
    fns = {}
    for name, res in CLASSES.items():
        vols = {"/fitvol": fitvol} if name.startswith("fit") else {"/fitvol": fitvol, "/evalvol": evalvol}
        fns[name] = app.function(cpu=res["cpu"], memory=res["memory"], timeout=(3 if name.startswith("fit") else 2) * 3600,
                                 max_containers=MAX_CONTAINERS, retries=retries, volumes=vols, serialized=True,
                                 nonpreemptible=res["nonpreemptible"], name=f"p3c_{name}")(_gate(fit_call if name.startswith("fit") else eval_call))
    return app, fns, fitvol


_REFUSALS: dict = {}
MAX_ATTEMPTS = 400


def _respawn(fn, payload: dict, label: str):
    _REFUSALS[label] = _REFUSALS.get(label, 0) + 1
    p = dict(payload, job_id=uuid.uuid4().hex)
    return fn.spawn(p), p


def gated_eval_map(payloads: list[dict], label: str) -> list:
    """Drop-in replacement of modal_tournament._eval_map on the gated evaluation function: the same results in input order
    (exceptions as values), refusals re-submitted; used by the FROZEN evaluation / reference / reproducibility functions."""
    import modal_tournament as MT
    fn = MT._STATE["eval_fn"]
    if not payloads:
        return []
    t0 = time.time()
    res: list = [None] * len(payloads)
    live = {i: (fn.spawn(p), p, 1) for i, p in enumerate(payloads)}
    while live:
        for i, (call, p, n) in list(live.items()):
            try:
                r = call.get(timeout=0)
            except Exception as e:  # noqa: BLE001
                if "timeout" in type(e).__name__.lower():
                    continue
                r = e
            if isinstance(r, dict) and r.get("__refused__"):
                if n >= MAX_ATTEMPTS:
                    res[i] = RuntimeError(f"not placed on a host without AVX-512 after {n} attempts")
                    del live[i]
                    continue
                c2, p2 = _respawn(fn, p, label)
                live[i] = (c2, p2, n + 1)
                continue
            res[i] = r
            del live[i]
        if live:
            time.sleep(2)
    print(f"  modal {label}: {len(payloads)} in {time.time() - t0:.0f} s (gated; refusals so far {_REFUSALS.get(label, 0)})", flush=True)
    MT._cost([r for r in res if isinstance(r, dict)], label)
    return res


def fit_class(job: dict, modes: dict) -> str:
    systems = list(job["systems"])
    n_full = sum(1 for s in systems if modes.get(s) == "full")
    if len(systems) > 1 and n_full >= 1:
        return "fit_joint"
    return "fit_full" if n_full >= 1 else "fit_small"


_FNS: dict = {}
_MODES: dict = {}
_LOG: list = []


def fast_run_fits_real(jobs: list[dict], parallel: int = 5) -> list[dict]:
    """modal_tournament.modal_run_fits_real with per-class placement (see the module docstring); the same payloads and output files."""
    import modal_tournament as MT
    fitvol = MT._STATE["fitvol"]
    recs: list = [None] * len(jobs)
    todo = []
    for i, j in enumerate(jobs):
        out = Path(j["out"])
        if out.exists() and out.with_suffix(".json").exists():
            recs[i] = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
            continue
        sim = None
        if j.get("sim_queue") and MT._STATE.get("sim_systems"):
            sim = {"budget": int(MT._STATE["sim_budget"]), "systems": {s: MT._STATE["sim_systems"][s] for s in j["systems"] if s in MT._STATE["sim_systems"]}}
        payload = {"job_id": uuid.uuid4().hex, "kind": "fit_real", "methods_key": MT._methods_key(Path(j["method_dir"]), fitvol),
                   "method": j["method"], "systems": list(j["systems"]), "seed": int(j.get("seed", 0)), "config": j.get("config"),
                   "timeout_s": float(j.get("timeout_s", 3600.0)), "stem": out.stem, "datasets": [MT._real_dataset(d) for d in j["datasets"]],
                   "adapt_from": MT._model_files(Path(j["adapt_from"])) if j.get("adapt_from") else None, "sim": sim}
        todo.append((i, fit_class(j, _MODES), payload))
    if not todo:
        return recs
    t0 = time.time()
    calls = {}
    by_class = {c: [t for t in todo if t[1] == c] for c in ORDER}
    print(f"  fast real fits: {len(todo)} to run ({', '.join(f'{c} {len(v)}' for c, v in by_class.items())}); longest classes first", flush=True)
    for c in ORDER:
        if c == "fit_small" and by_class["fit_small"] and (by_class["fit_joint"] or by_class["fit_full"]):
            time.sleep(SMALL_DELAY_S)
        for i, _c, p in by_class[c]:
            calls[i] = (c, _FNS[c].spawn(p), time.time(), p, 1)
    results = {}
    last = time.time()
    while calls:
        for i, (c, call, ts, p, n) in list(calls.items()):
            try:
                r = call.get(timeout=0)
            except Exception as e:  # noqa: BLE001
                if "timeout" in type(e).__name__.lower():
                    continue
                r = e
            if isinstance(r, dict) and r.get("__refused__"):
                if n < MAX_ATTEMPTS:
                    c2, p2 = _respawn(_FNS[c], p, f"fits:{c}")
                    calls[i] = (c, c2, ts, p2, n + 1)
                    continue
                r = RuntimeError(f"not placed on a host without AVX-512 after {n} attempts")
            del calls[i]
            results[i] = r
            out = Path(jobs[i]["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(r, BaseException):
                rec = {"error": f"modal call failed: {r!r}"[:2000]}
                out.with_suffix(".error.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
                recs[i] = rec
            else:
                if r.get("pkl") is not None:
                    out.write_bytes(r["pkl"])
                if r.get("json") is not None:
                    out.with_suffix(".json").write_bytes(r["json"])
                if r.get("error_json") is not None:
                    out.with_suffix(".error.json").write_bytes(r["error_json"])
                recs[i] = r["rec"]
            _LOG.append({"job": out.stem, "class": c, "wall_s": round(time.time() - ts, 1),
                         "container_wall_s": (r.get("container_wall_s") if isinstance(r, dict) else None),
                         "peak_container_mb": (r.get("peak_container_mb") if isinstance(r, dict) else None),
                         "error": isinstance(r, BaseException) or bool(isinstance(r, dict) and r.get("error_json"))})
        if calls:
            time.sleep(3)
        if time.time() - last > 120:
            print(f"  fast real fits: {len(todo) - len(calls)} of {len(todo)} done ({time.time() - t0:.0f} s)", flush=True)
            last = time.time()
    print(f"  modal real fits: {len(todo)} in {time.time() - t0:.0f} s", flush=True)
    for c in ORDER:
        MT._cost([results[i] for i, cc, _p in todo if cc == c and isinstance(results.get(i), dict)], f"real fits ({c})")
    return recs


def run_level_c(rest: list[str]) -> int:
    import level_c as L
    import modal_tournament as MT
    real_defs = json.loads(MT.INTERNAL_SRC.read_text(encoding="utf-8"))
    _MODES.update({s: d["mode"] for s, d in real_defs.items()})
    # the same simulation-service definitions as cmd_level_c (held-out target lists removed)
    MT._STATE.update(sim_budget=L.SIM_BUDGET, real_refcache=str(L.OUT / "_refcache"),
                     sim_systems={s: {k: v for k, v in dict(d, cost=10 if d["mode"] == "full" else 3).items() if k not in ("targets_heldout", "meta")}
                                  for s, d in real_defs.items()})
    L.run_fits, L.evaluate_models, L.reproducibility_jobs = fast_run_fits_real, MT.modal_evaluate_models_real, MT.modal_reproducibility_jobs_real
    L.start_simservice = lambda *a, **k: (Path("modal-per-fit-simulator"), None)
    MT._eval_map = gated_eval_map          # the frozen evaluation / reference / reproducibility functions on gated hosts
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--attempt", default="01")
    known, _ = pre.parse_known_args(rest)
    app, fns, fitvol = make_app()
    _FNS.update(fns)
    MT._STATE.update(fit_fn=fns["fit_full"], eval_fn=fns["eval"], fitvol=fitvol)
    t0 = time.time()
    with MT._output(), app.run():
        rc = L.main(rest)
    from brainir_state.suite_eval import evaluator_code_tag
    rec = {"attempt": known.attempt, "scheduler": "scripts/p3/level_c_fast.py", "host_gate": "no AVX-512 (fits and evaluations)",
           "refusals": _REFUSALS, "classes": CLASSES, "max_containers": MAX_CONTAINERS,
           "wall_s": round(time.time() - t0, 1), "calls": MT._STATE["costs"], "fit_log": _LOG,
           "usd_approx_total": round(sum(c["usd_approx"] for c in MT._STATE["costs"]), 2), "local_evaluator_code_tag": evaluator_code_tag(),
           "remote_evaluator_code_tags": sorted(t for t in MT._STATE.get("remote_code_tags", set()) if t)}
    out = L.OUT / known.attempt / "modal_costs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k not in ("calls", "fit_log", "classes")}), flush=True)
    return rc




# ------------------------------------------------------------------------------------------------ public validation (no hidden data)
VAL_DIR = Path(r"C:\Dev\BrainIR_p3run") / "levelc_fast_validation2"
VAL_CASES = [(m, s) for m in ("brainir_state_v1", "lin_dmdc_t") for s in ("real:net1:mech:02fa13b8", "real:net2:mech:6883ab7b")]
_SKIP_KEYS = ("_guard", "fit_wall_s", "wall_s", "_time", "time_s", "cpu_s", "fit_seconds")          # object-id keyed caches, timings


def compare_models(pa: Path, pb: Path) -> dict:
    """Leaf-by-leaf comparison of two fitted models (the method's own objects), skipping object-id keyed caches and timings."""
    import pickle
    import numpy as np
    import brainir_state.methods  # noqa: F401 - registers the locked methods for unpickling
    a, b = pickle.loads(Path(pa).read_bytes()), pickle.loads(Path(pb).read_bytes())
    out = {"numeric_leaves_differing": 0, "max_rel": 0.0, "other": []}

    def walk(x, y, path: str) -> None:
        last = path.rsplit("/", 1)[-1]
        if any(s in last for s in _SKIP_KEYS):
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y), key=repr):
                walk(x.get(k), y.get(k), f"{path}/{k}")
        elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            if len(x) != len(y):
                out["other"].append(f"{path}: length {len(x)} != {len(y)}")
                return
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, f"{path}[{i}]")
        elif isinstance(x, np.ndarray) and isinstance(y, np.ndarray):
            if x.shape != y.shape or x.dtype != y.dtype:
                out["other"].append(f"{path}: shape / dtype")
            elif not np.array_equal(x, y, equal_nan=x.dtype.kind in "fc"):
                out["numeric_leaves_differing"] += 1
                if x.dtype.kind in "fc" and x.size:
                    out["max_rel"] = max(out["max_rel"], float(np.nanmax(np.abs(x - y)) / max(float(np.nanmax(np.abs(y))), 1e-300)))
        elif hasattr(x, "__dict__") and hasattr(y, "__dict__") and type(x) is type(y):
            walk(vars(x), vars(y), path)
        elif isinstance(x, float) and isinstance(y, float):
            if x != y and not (x != x and y != y):
                out["numeric_leaves_differing"] += 1
                out["max_rel"] = max(out["max_rel"], abs(x - y) / max(abs(y), 1e-300))
        else:
            try:
                if x != y:
                    out["other"].append(f"{path}: {repr(x)[:40]} != {repr(y)[:40]}")
            except Exception:  # noqa: BLE001
                pass
    walk(a, b, "")
    out["identical"] = out["numeric_leaves_differing"] == 0 and not out["other"]
    out["other"] = out["other"][:8]
    return out


def _val_setup():
    import level_c as L
    import modal_tournament as MT
    from brainir_state.suite_eval import SuiteData
    real_defs = json.loads(MT.INTERNAL_SRC.read_text(encoding="utf-8"))
    _MODES.update({s: d["mode"] for s, d in real_defs.items()})
    MT._STATE.update(sim_budget=L.SIM_BUDGET, sim_systems={s: {k: v for k, v in dict(d, cost=10 if d["mode"] == "full" else 3).items()
                                                                if k not in ("targets_heldout", "meta")} for s, d in real_defs.items()})
    sd = SuiteData(MT.REAL_PUBLIC, kind="real")
    return sd.fit_view(VAL_DIR / "fitview_real"), ROOT / "phase3" / "src" / "brainir_state" / "methods"


def _val_jobs(tag: str, view: Path, mdir: Path) -> list[dict]:
    return [dict(method_dir=mdir, method=m, datasets=[view], systems=[s], out=VAL_DIR / tag / m / f"{s.replace(':', '_')}_s0.pkl",
                 seed=0, timeout_s=3600.0, sim_queue=Path("modal-per-fit-simulator")) for m, s in VAL_CASES]


def validate_modal() -> int:
    """The gated dispatcher on PUBLIC data: the same fits twice (repeats r1, r2), each on hosts without AVX-512."""
    import modal_tournament as MT
    view, mdir = _val_setup()
    app, fns, fitvol = make_app()
    _FNS.update(fns)
    MT._STATE.update(fit_fn=fns["fit_full"], eval_fn=fns["eval"], fitvol=fitvol)
    t0 = time.time()
    with MT._output(), app.run():
        recs = fast_run_fits_real(_val_jobs("gated_r1", view, mdir) + _val_jobs("gated_r2", view, mdir))
    print(json.dumps({"wall_s": round(time.time() - t0, 1), "errors": sum(1 for r in recs if (r or {}).get("error")), "refusals": _REFUSALS,
                      "fit_log": _LOG}, indent=1, default=str), flush=True)
    return 0


def validate_local() -> int:
    """The same fits on the development machine (the frozen local sandboxed fit worker; small mechanism systems)."""
    from brainir_state.suite_eval import fit_sandboxed
    view, mdir = _val_setup()
    for j in _val_jobs("local", view, mdir):
        r = fit_sandboxed(Path(j["method_dir"]), j["method"], j["datasets"], j["systems"], Path(j["out"]), seed=0, timeout_s=3600.0)
        print(j["method"], j["systems"][0], "k", r.get("k"), "error", bool(r.get("error")), flush=True)
    return 0


def validate_compare(out_json: Path) -> int:
    rows = []
    for m, s in VAL_CASES:
        f = f"{s.replace(':', '_')}_s0.pkl"
        p1, p2, pl = VAL_DIR / "gated_r1" / m / f, VAL_DIR / "gated_r2" / m / f, VAL_DIR / "local" / m / f
        rows.append({"method": m, "system": s, "gated_r1_vs_r2": compare_models(p1, p2),
                     "gated_r1_vs_local": compare_models(p1, pl)})
    rep = {"rows": rows, "all_gated_repeats_identical": all(r["gated_r1_vs_r2"]["identical"] for r in rows),
           "all_gated_equal_local": all(r["gated_r1_vs_local"]["identical"] for r in rows)}
    out_json.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rep, indent=1), flush=True)
    return 0 if rep["all_gated_repeats_identical"] and rep["all_gated_equal_local"] else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--validate-modal":
        raise SystemExit(validate_modal())
    if argv and argv[0] == "--validate-local":
        raise SystemExit(validate_local())
    if argv and argv[0] == "--validate-compare":
        raise SystemExit(validate_compare(ROOT / "research" / "phase3" / "level_c" / "levelc_fast_validation.json"))
    raise SystemExit(run_level_c(argv))
