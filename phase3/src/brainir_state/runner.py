"""Tournament / evaluation runner (orchestrator side): fit a method in a sandboxed subprocess, then load the model for evaluation.

    python -m brainir_state.runner fit --method-dir D --method NAME --dataset DS [--dataset DS2 ...] --systems S1,S2 \
        --out model.pkl [--config JSON] [--seed N] [--sim-queue Q] [--agent NAME] [--splits train,val]

The method's code is a copy of the clean room's `src/brainir_state/methods/` directory (never the orchestrator's tree), mounted as
the package `brainir_state.methods`. The fit process installs the FIT guard before importing any method code: it can read only the
method copy, the listed public datasets, the output directory, the simulation queue and its private temp directory (plus the Python
environment), and it cannot start processes or open network connections. The fitted model is pickled (StateModel.save); a JSON
side-file records the model's info(), the fit time and the peak memory.
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


def mount_methods(method_dir: str | Path) -> None:
    """Make `brainir_state.methods` resolve to the given directory (a copy of a clean room's methods package)."""
    import brainir_state
    method_dir = str(Path(method_dir).resolve())
    mod = sys.modules.get("brainir_state.methods")
    if mod is None or list(getattr(mod, "__path__", [])) != [method_dir]:
        mod = types.ModuleType("brainir_state.methods")
        mod.__path__ = [method_dir]
        mod.__package__ = "brainir_state.methods"
        sys.modules["brainir_state.methods"] = mod
        brainir_state.methods = mod


def import_method(method_dir: str | Path, name: str):
    mount_methods(method_dir)
    from brainir_state.api import get_method
    module = name.split(":")[0]
    importlib.import_module(f"brainir_state.methods.{module}")
    return get_method(name.split(":")[-1])


def load_model(method_dir: str | Path, path: str | Path):
    mount_methods(method_dir)
    from brainir_state.api import load_model as _load
    return _load(path)


def _fit(args) -> int:
    from .runguard import install_fit_guard
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / f".tmp_{out.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    allowed = [str(Path(args.method_dir).resolve()), str(out.parent), str(tmp)] + [str(Path(d).resolve()) for d in args.dataset]
    if args.sim_queue:
        allowed.append(str(Path(args.sim_queue).resolve()))
    install_fit_guard(allowed)     # before any method code is imported; TEMP / TMP must point into `tmp` (set by the launcher)
    from .data import Dataset
    method = import_method(args.method_dir, args.method)
    systems = [s for s in args.systems.split(",") if s]
    splits = set(args.splits.split(","))
    train, sysinfo = [], {}
    for d in args.dataset:
        ds = Dataset(d)
        for sid in systems:
            if sid in ds.systems:
                sysinfo[sid] = ds.systems[sid]
                train += [ds.load(r) for r in ds.select(system_id=sid) if r["split"] in splits]
    missing = [s for s in systems if s not in sysinfo]
    if missing:
        raise SystemExit(f"systems not found in the datasets: {missing}")
    config = json.loads(args.config) if args.config else {}
    if args.adapt_from:
        config["adapt_from"] = load_model(args.method_dir, args.adapt_from)
    sim = None
    if args.sim_queue:
        from .simclient import SimClient
        sim = SimClient(queue=args.sim_queue, agent=args.agent or f"run:{args.method}")
    t0, c0 = time.time(), time.process_time()
    model = method.fit(train, systems=sysinfo, config=config, sim=sim, seed=args.seed)
    wall, cpu = time.time() - t0, time.process_time() - c0
    model.save(out)
    info = {}
    try:
        info = model.info() or {}
    except Exception as e:  # noqa: BLE001
        info = {"info_error": repr(e)}
    side = {"method": args.method, "method_version": getattr(method, "version", "?"), "systems": systems, "seed": args.seed,
            "config": {k: v for k, v in config.items() if k != "adapt_from"}, "adapted": bool(args.adapt_from), "n_train": len(train),
            "fit_wall_s": round(wall, 2), "fit_cpu_s": round(cpu, 2), "info": info,
            "sim_budget": (sim.budget() if sim is not None else None)}
    out.with_suffix(".json").write_text(json.dumps(side, indent=1, default=str) + "\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--method-dir", required=True)
    f.add_argument("--method", required=True, help="registered method name, or module:name")
    f.add_argument("--dataset", action="append", required=True)
    f.add_argument("--systems", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--config", default="")
    f.add_argument("--seed", type=int, default=0)
    f.add_argument("--splits", default="train,val")
    f.add_argument("--sim-queue", default="")
    f.add_argument("--agent", default="")
    f.add_argument("--adapt-from", default="", help="a fitted model (pickle) whose transition law is frozen (config['adapt_from'])")
    args = ap.parse_args(argv)
    if args.cmd == "fit":
        # threads: the orchestrator runs several fits in parallel
        n = os.environ.get("P3_FIT_THREADS", "3")
        os.environ.setdefault("OMP_NUM_THREADS", n)
        os.environ.setdefault("MKL_NUM_THREADS", n)
        try:
            import torch
            torch.set_num_threads(int(n))
        except Exception:  # noqa: BLE001
            pass
        return _fit(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
