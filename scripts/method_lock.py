"""Method lock for a Phase 2 discovery method (goal3 section 27): freeze code, configuration and evidence BEFORE any hidden evaluation.

    uv run python scripts/method_lock.py write --method brainir_v1 --budget 1000 --seed 0 \
        --networks manc_v1.2.1 manc_v1.2.3 male-cns_v1.0 --config '{}' \
        --synthetic research/phase2/tournament/<label>.json [...] --doc research/phase2/BRAINIR_V1_METHOD.md \
        --tests-log <file with the pytest summary line> [--seed-policy "..."] [--notes "..."]
    uv run python scripts/method_lock.py check      # recompute every hash; exit 1 on any difference

`write` refuses when any locked file has uncommitted changes (the lock must describe committed code) and writes
research/phase2/METHOD_LOCK.json. After committing the lock, tag the commit `brainir-v1-preblind`; `scripts/blind_eval.py`
refuses to run unless `check` passes and the tag's copy of the lock equals the working copy.

Locked: the whole `src/brainir` package, the clean-room entry script, pyproject.toml and uv.lock (source hashes + a tree hash);
the method's effective configuration (registered defaults + overrides; config hash); the run protocol (entry, method arguments,
networks, seed, budget); package versions; the public bundle hashes and the benchmark lock hash; the synthetic evidence files
(hash + their per-method summaries); the method documentation hash; the public test result; the expected output schema.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.metadata as md
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "research" / "phase2" / "METHOD_LOCK.json"
ENTRY = "scripts/cleanroom_entry/brainir_discovery_entry.py"
LOCKED_GLOBS = ("src/brainir/**/*.py", ENTRY, "pyproject.toml", "uv.lock")
PACKAGES = ("numpy", "scipy", "pandas", "pyarrow", "pydantic", "networkx", "duckdb")
TAG = "brainir-v1-preblind"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def locked_files() -> list[Path]:
    out: set[Path] = set()
    for g in LOCKED_GLOBS:
        out |= {p for p in ROOT.glob(g) if p.is_file() and "__pycache__" not in p.parts}
    return sorted(out)


def source_hashes() -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): _sha(p) for p in locked_files()}


def tree_hash(hashes: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def effective_config(method: str, overrides: dict) -> tuple[dict, str]:
    from brainir.discovery import MethodRegistry

    cls = MethodRegistry.get(method)
    cfg = {**cls.default_config, **overrides}
    return cfg, hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _rel(p: Path | str) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:  # outside the repository (tests only; a real lock references repository files)
        return p.as_posix()


def _synthetic_record(path: Path) -> dict:
    rec = {"path": _rel(path), "sha256": _sha(path)}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        s = d.get("summary")
        if isinstance(s, dict):
            rec["summary"] = {m: {k: v for k, v in (x or {}).items() if k not in ("by_family",)} if isinstance(x, dict) else x for m, x in s.items()}
        for k in ("label", "suite", "budget", "seeds", "networks", "n_jobs", "budget_a", "budget_b", "modes"):
            if k in d:
                rec[k] = d[k]
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return rec


def build_lock(args) -> dict:
    from brainir.benchmark.prediction import PREDICTION_SCHEMA_VERSION
    from brainir.discovery import MethodRegistry

    overrides = json.loads(args.config)
    cfg, cfg_hash = effective_config(args.method, overrides)
    cls = type(MethodRegistry.get(args.method))  # the registry hands out instances
    hashes = source_hashes()
    bench = json.loads((ROOT / "benchmarks" / "dng100" / "BENCHMARK_LOCK.json").read_text(encoding="utf-8"))
    bundles = {}
    for name in ("public_blind", "public"):
        man = json.loads((ROOT / "benchmarks" / "dng100" / name / "manifest.json").read_text(encoding="utf-8"))
        bundles[name] = {"bundle_sha256": man["bundle_sha256"], "tier": man.get("tier")}
    tests = None
    if args.tests_log:
        text = Path(args.tests_log).read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?(?:, (\d+) deselected)?", text)
        last = m[-1] if m else None
        tests = {"command": args.tests_command, "log_sha256": _sha(Path(args.tests_log)),
                 "passed": int(last[0]) if last else None, "failed": int(last[1]) if last and last[1] else 0,
                 "summary_line": next((ln.strip() for ln in reversed(text.splitlines()) if " passed" in ln), None)}
    # the clean-room runner splits --method-args on whitespace: JSON values are written without spaces
    cfg_args = " ".join(f"{k}={json.dumps(v, separators=(',', ':'))}" for k, v in overrides.items())
    method_args = f"--method {args.method} --budget {args.budget}" + (f" --config {cfg_args}" if overrides else "")
    lock = {
        "lock_version": "1.0.0", "created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "method": {"name": args.method, "version": cls.version, "class": f"{cls.__module__}.{cls.__qualname__}", "config": cfg,
                   "config_overrides": overrides, "config_sha256": cfg_hash},
        "run_protocol": {"runner": "benchmarks/dng100/cleanroom/run_method.py", "entry": ENTRY, "method_args": method_args,
                         "bundle": "benchmarks/dng100/public_blind", "networks": args.networks, "seed": args.seed,
                         "seed_policy": args.seed_policy, "budget_calls_per_network": args.budget, "workers": 1,
                         "evaluator": "benchmarks/dng100/evaluator/evaluate.py --run-record (n_replicates 16, t_end 2.0: the frozen defaults)"},
        "git": {"commit": _git("rev-parse", "HEAD"), "branch_or_head": _git("rev-parse", "--abbrev-ref", "HEAD")},
        "source_hashes": hashes, "source_tree_sha256": tree_hash(hashes),
        "package_versions": {p: md.version(p) for p in PACKAGES if _installed(p)}, "python": platform.python_version(),
        "benchmark": {"benchmark_id": bench["benchmark_id"], "lock_sha256": bench["lock_sha256"], "bundles": bundles},
        "synthetic_results": [_synthetic_record(Path(p).resolve()) for p in args.synthetic],
        "documentation": {"path": _rel(args.doc), "sha256": _sha(Path(args.doc))} if args.doc else None,
        "tests": tests, "expected_output": {"prediction_schema_version": PREDICTION_SCHEMA_VERSION, "one_prediction_per_network": True},
        "notes": args.notes,
    }
    lock["lock_sha256"] = hashlib.sha256(json.dumps({k: v for k, v in lock.items() if k not in ("created_utc",)}, sort_keys=True,
                                                    default=str).encode()).hexdigest()
    return lock


def _installed(p: str) -> bool:
    try:
        md.version(p)
        return True
    except md.PackageNotFoundError:
        return False


def check(lock_path: Path = LOCK_PATH, verbose: bool = True) -> list[str]:
    """Recompute what the lock records; return a list of problems (empty = the locked method is intact)."""
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    now = source_hashes()
    rec = lock["source_hashes"]
    for f in sorted(set(rec) | set(now)):
        if rec.get(f) != now.get(f):
            problems.append(f"source {'added' if f not in rec else 'removed' if f not in now else 'changed'}: {f}")
    _cfg, cfg_hash = effective_config(lock["method"]["name"], lock["method"]["config_overrides"])
    if cfg_hash != lock["method"]["config_sha256"]:
        problems.append("effective configuration changed")
    for s in lock.get("synthetic_results", []):
        p = ROOT / s["path"]
        if not p.exists() or _sha(p) != s["sha256"]:
            problems.append(f"synthetic evidence changed or missing: {s['path']}")
    doc = lock.get("documentation")
    if doc and (not (ROOT / doc["path"]).exists() or _sha(ROOT / doc["path"]) != doc["sha256"]):
        problems.append(f"method documentation changed or missing: {doc['path']}")
    for name, b in lock["benchmark"]["bundles"].items():
        man = json.loads((ROOT / "benchmarks" / "dng100" / name / "manifest.json").read_text(encoding="utf-8"))
        if man["bundle_sha256"] != b["bundle_sha256"]:
            problems.append(f"public bundle changed: {name}")
    if verbose:
        print("METHOD_LOCK check:", "OK" if not problems else f"{len(problems)} problem(s)")
        for p in problems[:50]:
            print("  -", p)
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--method", required=True)
    w.add_argument("--budget", type=int, required=True, help="hard simulator-call budget per network")
    w.add_argument("--seed", type=int, default=0)
    w.add_argument("--networks", nargs="+", default=["manc_v1.2.1", "manc_v1.2.3", "male-cns_v1.0"])
    w.add_argument("--config", default="{}", help="JSON overrides of the method's default configuration")
    w.add_argument("--synthetic", nargs="*", default=[], help="synthetic result files the selection rests on")
    w.add_argument("--doc", default=None)
    w.add_argument("--tests-log", default=None)
    w.add_argument("--tests-command", default='uv run pytest -m "not real_data"')
    w.add_argument("--seed-policy", default="one primary blind run per network with the locked seed; reliability sweeps use seeds 0,1,2 x "
                                            "8 salted node orders (order 0 = the bundle's own order)")
    w.add_argument("--notes", default=None)
    w.add_argument("--allow-dirty", action="store_true", help="for dry runs only; a real lock must describe committed code")
    w.add_argument("--out", type=Path, default=LOCK_PATH)
    c = sub.add_parser("check")
    c.add_argument("--lock", type=Path, default=LOCK_PATH)
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return 1 if check(args.lock) else 0
    dirty = [ln for ln in _git("status", "--porcelain", "--", "src/brainir", ENTRY, "pyproject.toml", "uv.lock").splitlines() if ln.strip()]
    if dirty and not args.allow_dirty:
        print("refusing to lock: uncommitted changes in locked files:", *dirty[:20], sep="\n  ")
        return 1
    lock = build_lock(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(lock, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {_rel(args.out)}: method {lock['method']['name']} {lock['method']['version']}, "
          f"{len(lock['source_hashes'])} files, tree {lock['source_tree_sha256'][:16]}, lock {lock['lock_sha256'][:16]}")
    print(f"next: commit it, then `git tag {TAG}`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
