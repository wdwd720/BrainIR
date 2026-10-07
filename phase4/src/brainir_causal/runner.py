"""Tournament / evaluation runner (ORCHESTRATOR SIDE): fit a method, or run its experiment loop, with the method's code in a MODEL
WORKER (research/phase4/EVAL_ARCHITECTURE.md; review F, F-B2 / F-B3).

    python -m brainir_causal.runner fit  --method-dir D --method NAME --data DIR [--data DIR2 ...] --systems S1,S2 --out model.pkl
                                         [--config JSON] [--seed N] [--splits train] [--adapt-from MODEL] [--bootstrap B]
                                         [--transport docker|local-unsafe]
    python -m brainir_causal.runner loop --method-dir D --method NAME --designer NAME|own|random_matched --data DIR --system S
                                         --budget B --out DIR --internal PATH --store-root DIR [--profile-dir DIR] [--generator DIR PKG]
                                         [--checkpoints 10,25,50,100,200] [--batch 5] [--seed N] [--config JSON]

This process is the trusted DRIVER: it reads the public training records, starts a worker in the Docker sandbox image
(`isolation.DockerTransport`: no network, read-only root, every capability dropped, an unprivileged uid; only the public modules and
the method snapshot are mounted) and sends it the records over a pipe. The fitted model comes back as BYTES and is written to --out
unchanged; it is NEVER loaded here (F-B3). A JSON side record (--out with .json) carries the method's info(), the fit wall / CPU time,
the harness-measured compute (`capacity.ComputeMeter`, measured in the worker), the worker's platform and the isolation record.

`fit` gives the method the records of the given splits (default 'train' = D0 + D1 of PROTOCOL 4) and the twins of their intervention
trajectories; `--bootstrap B` fits the B-th bootstrap resample of the training interventions (PROTOCOL 5.10, the Level C dimension
refits). `loop` runs `brainir_causal.loop.run_loop` from the system's passive training set D0: the learner (and, for '--designer own',
the method's designer) live in the loop worker, while the driver validates every proposal against the public policy, simulates it and
does the budget accounting (reference designers run trusted in the driver). `--transport local-unsafe` runs a plain child process with
no OS sandbox and is for TRUSTED code only (tests, the equivalence harness); the default is the Docker sandbox.

`load_records` / `import_method` / `mount_methods` remain here for the driver's own use (loading public records; the worker imports the
method itself). This module never unpickles a fitted method model.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
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
    """The registered method `name` ("module:name" or a plain name). Used by the DRIVER only to read a method's declared attributes
    (device, designer) in a context where importing it is safe (never to fit or evaluate: that happens in a worker). A plain name is
    looked up in the module of the same name; if there is none, every module of the package is imported (a module that fails is
    skipped)."""
    mount_methods(method_dir)
    from .api import get_method, registered
    if ":" in name:
        module, meth = name.split(":", 1)
        importlib.import_module(f"{METHODS_PKG}.{module}")
        return get_method(meth)
    try:
        importlib.import_module(f"{METHODS_PKG}.{name}")
    except ModuleNotFoundError as e:
        if e.name != f"{METHODS_PKG}.{name}" and not str(e.name or "").startswith(f"{METHODS_PKG}.{name}."):
            raise
    if name not in registered():
        from .worker import method_modules                   # developers' packages methods/<prefix>/ included (review F r2, N-M2)
        for mod in method_modules(method_dir):
            if name in registered():
                break
            try:
                importlib.import_module(f"{METHODS_PKG}.{mod}")
            except Exception:  # noqa: BLE001, S112 - another developer's broken module must not hide a registered method
                continue
    return get_method(name)


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


def platform_record() -> dict:
    """Where the DRIVER runs (the worker reports its own platform; a fit's platform is the worker's)."""
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
    return rec


def _transport(args):
    from .isolation import local_transport
    tr, _pub = local_transport(args.method_dir, kind=args.transport, cpus=float(args.cpus), mem_gb=float(args.mem_gb))
    return tr


def _fit(args) -> int:
    from .isolation import fit_job
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    job = {"method": args.method, "systems": [s for s in args.systems.split(",") if s], "data": [str(Path(d).resolve()) for d in args.data],
           "seed": args.seed, "config": json.loads(args.config) if args.config else {}, "splits": args.splits}
    if args.bootstrap is not None:
        job["bootstrap"] = int(args.bootstrap)
    if args.adapt_from:
        job["adapt_from"] = Path(args.adapt_from).read_bytes()
    res = fit_job(job, _transport(args))
    out.write_bytes(res["model"])
    out.with_suffix(".json").write_text(json.dumps(res["side"], indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return 0


def _loop(args) -> int:
    from .isolation import loop_job
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    job = {"method": args.method, "designer": args.designer, "sid": args.system, "data": [str(Path(d).resolve()) for d in args.data],
           "budget": int(args.budget), "batch": int(args.batch), "seed": int(args.seed),
           "config": json.loads(args.config) if args.config else {}, "store_root": args.store_root,
           "internal_path": args.internal, "heldout_root": args.heldout_root or str(Path(args.data[0]).resolve().parents[2]),
           "heldout_tier": args.heldout_tier, "public_root": args.public_root or (args.heldout_root or ""), "public_tier": args.public_tier}
    if args.checkpoints:
        job["checkpoints"] = [int(c) for c in args.checkpoints.split(",") if c]
    if args.profile_dir:
        job["profile_dir"] = args.profile_dir
    if args.generator:
        job["generator"] = list(args.generator)
    rec = loop_job(job, _transport(args), out_dir=out)
    print(json.dumps({k: rec.get(k) for k in ("system_id", "designer", "seed", "spent", "refused", "stopped_early")}), flush=True)
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
    f.add_argument("--bootstrap", type=int, default=None)
    lp = sub.add_parser("loop")
    lp.add_argument("--method-dir", required=True)
    lp.add_argument("--method", required=True)
    lp.add_argument("--designer", required=True)
    lp.add_argument("--data", action="append", required=True)
    lp.add_argument("--system", required=True)
    lp.add_argument("--budget", type=int, required=True)
    lp.add_argument("--checkpoints", default="10,25,50,100,200")
    lp.add_argument("--batch", type=int, default=5)
    lp.add_argument("--out", required=True)
    lp.add_argument("--internal", default=None)
    lp.add_argument("--store-root", dest="store_root", default="")
    lp.add_argument("--heldout-root", dest="heldout_root", default="")
    lp.add_argument("--heldout-tier", dest="heldout_tier", default="")
    lp.add_argument("--public-root", dest="public_root", default="")
    lp.add_argument("--public-tier", dest="public_tier", default="")
    lp.add_argument("--profile-dir", dest="profile_dir", default="")
    lp.add_argument("--generator", nargs=2, default=None)
    lp.add_argument("--seed", type=int, default=0)
    lp.add_argument("--config", default="")
    for p in (f, lp):
        p.add_argument("--transport", choices=("docker", "local-unsafe"), default="docker")
        p.add_argument("--cpus", default="2")
        p.add_argument("--mem-gb", dest="mem_gb", default="6")
    args = ap.parse_args(argv)
    return _fit(args) if args.cmd == "fit" else _loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
