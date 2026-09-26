"""Tournament / evaluation runner (ORCHESTRATOR SIDE): fit a method, or run its experiment loop, in a sandboxed subprocess.

    python -m brainir_causal.runner fit  --method-dir D --method NAME --data DIR [--data DIR2 ...] --systems S1,S2 --out model.pkl
                                         [--config JSON] [--seed N] [--splits train] [--adapt-from MODEL]
    python -m brainir_causal.runner loop --method-dir D --method NAME --designer NAME|own --data DIR --system S --budget B
                                         --sim-queue Q --out DIR [--checkpoints 10,25,50,100,200] [--batch 5] [--seed N] [--config JSON]

The method's code is a copy of the clean room's `src/brainir_causal/methods/` directory (never the orchestrator's tree), mounted as the
package `brainir_causal.methods`. The process pre-imports the scientific stack and the third-party modules the method package
imports (`runguard.preimport`: they load shared objects through ctypes, which the guard refuses), then installs the FIT guard
(`brainir_causal.runguard`) before importing any method code: it can touch only the method copy, the listed public data, the output
directory, the simulation queue and a private temp directory (plus the Python environment and the evaluation libraries), and it
cannot start processes, open network connections or load libraries through ctypes. The side record carries the platform (CPU model,
GPU device, Modal task) so that one evaluation's fits can be checked to come from one platform.

`fit` gives the method the records of the given splits (default 'train' = D0 + D1 of PROTOCOL 4) and the twins of their intervention
trajectories; the fitted model is pickled (model.save) and a JSON side file records info(), the fit wall / CPU time, the peak memory
and the harness-measured compute (`capacity.ComputeMeter`). `loop` runs `brainir_causal.loop.run_loop` from the system's PASSIVE
training set D0 with the method's learner and the named designer ('own' = the method's `designer()`; else a reference designer of
`brainir_causal.designers`); every simulation goes through the service queue, whose server enforces the public policy and budget.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import types
from pathlib import Path

METHODS_PKG = "brainir_causal.methods"


def mount_methods(method_dir: str | Path) -> None:
    """Make `brainir_causal.methods` resolve to the given directory (a copy of a clean room's methods package)."""
    import brainir_causal
    method_dir = str(Path(method_dir).resolve())
    mod = sys.modules.get(METHODS_PKG)
    if mod is None or list(getattr(mod, "__path__", [])) != [method_dir]:
        for k in [k for k in sys.modules if k == METHODS_PKG or k.startswith(METHODS_PKG + ".")]:
            del sys.modules[k]
        mod = types.ModuleType(METHODS_PKG)
        mod.__path__ = [method_dir]
        mod.__package__ = METHODS_PKG
        sys.modules[METHODS_PKG] = mod
        brainir_causal.methods = mod


def import_method(method_dir: str | Path, name: str):
    """The registered method `name` ("module:name" or a plain name). A plain name is looked up in the module of the same name; if
    there is none, every module of the methods package is imported (sorted; a module that fails to import is skipped) so that methods
    registered in a module with another name are found."""
    mount_methods(method_dir)
    from .api import get_method, registered
    if ":" in name:
        module, meth = name.split(":", 1)
        importlib.import_module(f"{METHODS_PKG}.{module}")
        return get_method(meth)
    try:
        importlib.import_module(f"{METHODS_PKG}.{name}")
    except ModuleNotFoundError as e:
        if e.name != f"{METHODS_PKG}.{name}":
            raise
    if name not in registered():
        for p in sorted(Path(method_dir).glob("*.py")):
            if p.stem == "__init__" or name in registered():
                continue
            try:
                importlib.import_module(f"{METHODS_PKG}.{p.stem}")
            except Exception:  # noqa: BLE001, S112 - another developer's broken module must not hide a registered method
                continue
    return get_method(name)


def load_model(method_dir: str | Path, path: str | Path):
    mount_methods(method_dir)
    from .api import load_model as _load
    return _load(path)


def load_records(data_dirs: list[str], systems: list[str], splits: set[str]) -> tuple[list, dict]:
    """(records, public system records) of the listed systems: records of `splits` plus the twins of their intervention
    trajectories. A data dir is an experiment set (manifest.json + index.jsonl + traj/) or a directory of per-system sets."""
    from .data import ExperimentSet
    sets = []
    for d in data_dirs:
        p = Path(d)
        if (p / "manifest.json").exists():
            sets.append(p)
        else:
            sets += [q for q in sorted(p.iterdir()) if (q / "manifest.json").exists()]
    recs, sysinfo = [], {}
    for p in sets:
        es = ExperimentSet.load(p, lazy=True)
        for sid in systems:
            if sid not in es.systems:
                continue
            sysinfo[sid] = es.systems[sid]
            rows = [r for r in es.rows if r["system_id"] == sid]
            keys = {r["key"] for r in rows if r.get("split") in splits}
            recs += [es.load(r) for r in rows if r.get("split") in splits or (r.get("split") == "twin" and (r.get("meta") or {}).get("twin_of") in keys)]
    missing = [s for s in systems if s not in sysinfo]
    if missing:
        raise SystemExit(f"systems not found in the data: {missing}")
    return recs, sysinfo


def _peak_mb() -> float | None:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:  # noqa: BLE001 - Windows: not available
        return None


def _threads() -> None:
    n = os.environ.get("P4_FIT_THREADS", "3")
    os.environ.setdefault("OMP_NUM_THREADS", n)
    os.environ.setdefault("MKL_NUM_THREADS", n)
    try:
        import threadpoolctl
        threadpoolctl.threadpool_limits(int(n))
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        import torch
        torch.set_num_threads(int(n))
    except Exception:  # noqa: BLE001, S110
        pass


_PLATFORM: dict = {}


def platform_record() -> dict:
    """Where a fit ran (goal5 section 63: all official fits of one evaluation run on one platform and, for GPU methods, one GPU
    class): Python, OS, machine, CPU model, core count, the CUDA device when available, the Modal task / class if any."""
    import platform
    rec = {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(), "n_cpu": os.cpu_count(),
           "modal_task": os.environ.get("MODAL_TASK_ID"), "modal_class": os.environ.get("P4M_CLASS")}
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", encoding="utf-8") as fh:
                rec["cpu"] = next((line.split(":", 1)[1].strip() for line in fh if line.startswith("model name")), None)
        else:
            rec["cpu"] = os.environ.get("PROCESSOR_IDENTIFIER")
    except OSError:
        rec["cpu"] = None
    try:
        import torch
        rec["torch"] = torch.__version__
        rec["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            rec["gpu"] = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001 - torch is optional
        rec["torch"] = None
    return rec


def _guard(args, extra: list[str]) -> Path:
    from .runguard import install_fit_guard, preimport
    _PLATFORM.update(platform_record())
    _PLATFORM["preimport"] = preimport(args.method_dir)
    out = Path(args.out).resolve()
    base = out if args.cmd == "loop" else out.parent
    base.mkdir(parents=True, exist_ok=True)
    tmp = base / f".tmp_{out.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = os.environ["TMPDIR"] = str(tmp)
    allowed = [str(Path(args.method_dir).resolve()), str(base), str(tmp)] + [str(Path(d).resolve()) for d in args.data] + extra
    install_fit_guard(allowed)
    return out


def fit_job(method_dir: str, method_name: str, data: list[str], systems: list[str], out: str, *, config: dict | None = None, seed: int = 0,
            splits: str = "train", adapt_from: str = "") -> dict:
    """Fit one method (NO guard here: the caller installs it; the CLI below and the Modal job site do). Writes out (model pickle)
    and out.json (side record); returns the side record."""
    from .capacity import ComputeMeter
    out_p = Path(out)
    method = import_method(method_dir, method_name)
    recs, sysinfo = load_records(data, systems, set(splits.split(",")))
    config = dict(config or {})
    if adapt_from:
        config["adapt_from"] = load_model(method_dir, adapt_from)
    t0 = time.time()
    with ComputeMeter() as meter:
        model = method.fit(recs, systems=sysinfo, config=config, seed=seed)
    model.save(out_p)
    try:
        info = model.info() or {}
    except Exception as e:  # noqa: BLE001
        info = {"info_error": repr(e)}
    side = {"method": method_name, "method_version": getattr(method, "version", "?"), "systems": systems, "seed": seed,
            "config": {k: v for k, v in config.items() if k != "adapt_from"}, "adapted": bool(adapt_from), "n_train": len(recs),
            "splits": splits, "fit_wall_s": round(time.time() - t0, 2), "compute": meter.as_dict(), "peak_mb": _peak_mb(), "info": info,
            "platform": dict(_PLATFORM) if _PLATFORM else platform_record()}
    out_p.with_suffix(".json").write_text(json.dumps(side, indent=1, default=str) + "\n", encoding="utf-8")
    return side


def _fit(args) -> int:
    out = _guard(args, [])
    fit_job(args.method_dir, args.method, args.data, [s for s in args.systems.split(",") if s], str(out),
            config=json.loads(args.config) if args.config else {}, seed=args.seed, splits=args.splits, adapt_from=args.adapt_from)
    return 0


def loop_job(method_dir: str, method_name: str, designer_name: str, data: list[str], system: str, budget: int, sim_queue: str, out: str,
             *, checkpoints: str = "10,25,50,100,200", batch: int = 5, seed: int = 0, config: dict | None = None) -> dict:
    """One experiment loop (NO guard here; see fit_job): the method's learner with the named designer ('own' or a reference
    designer) from the system's passive training set D0; simulations through the service queue `sim_queue`."""
    from . import designers as _designers  # noqa: F401 - registers the reference designers
    from .api import get_designer
    from .loop import run_loop
    from .simclient import SimClient
    method = import_method(method_dir, method_name)
    if designer_name == "own":
        designer = method.designer()
        if designer is None:
            raise SystemExit(f"{method_name} has no designer of its own")
        dname = f"own:{getattr(designer, 'name', type(designer).__name__)}"
    else:
        designer = get_designer(designer_name)
        dname = designer_name
    recs, sysinfo = load_records(data, [system], {"train"})
    d0 = [r for r in recs if not r.protocol.get("events") and (r.meta or {}).get("role", "d0") == "d0" and r.split == "train"]
    sim = SimClient(queue=sim_queue, agent=f"loop:{method_name}:{dname}:{system}:{seed}")
    cps = tuple(int(c) for c in str(checkpoints).split(",") if c)
    rec = run_loop(method, designer, system, sysinfo[system], d0, sim, budget=int(budget), checkpoints=cps, batch=int(batch), seed=int(seed),
                   out_dir=out, config=dict(config or {}), designer_name=dname)
    return {k: rec[k] for k in ("system_id", "designer", "seed", "spent", "refused", "stopped_early")}


def _loop(args) -> int:
    out = _guard(args, [str(Path(args.sim_queue).resolve())])
    summary = loop_job(args.method_dir, args.method, args.designer, args.data, args.system, args.budget, args.sim_queue, str(out),
                       checkpoints=args.checkpoints, batch=args.batch, seed=args.seed, config=json.loads(args.config) if args.config else {})
    print(json.dumps(summary), flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--method-dir", required=True)
    f.add_argument("--method", required=True, help="registered method name, or module:name")
    f.add_argument("--data", action="append", required=True)
    f.add_argument("--systems", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--config", default="")
    f.add_argument("--seed", type=int, default=0)
    f.add_argument("--splits", default="train")
    f.add_argument("--adapt-from", default="")
    lp = sub.add_parser("loop")
    lp.add_argument("--method-dir", required=True)
    lp.add_argument("--method", required=True)
    lp.add_argument("--designer", required=True)
    lp.add_argument("--data", action="append", required=True)
    lp.add_argument("--system", required=True)
    lp.add_argument("--budget", type=int, required=True)
    lp.add_argument("--checkpoints", default="10,25,50,100,200")
    lp.add_argument("--batch", type=int, default=5)
    lp.add_argument("--sim-queue", required=True)
    lp.add_argument("--out", required=True)
    lp.add_argument("--seed", type=int, default=0)
    lp.add_argument("--config", default="")
    args = ap.parse_args(argv)
    _threads()
    if args.cmd == "fit":
        return _fit(args)
    return _loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
