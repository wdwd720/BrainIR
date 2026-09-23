"""Write BENCHMARK_LOCK.json: the frozen identity of dng100-benchmark-v1.

    uv run python benchmarks/dng100/freeze.py            # write the lock
    uv run python benchmarks/dng100/freeze.py --check    # verify the tree still matches the lock (exit 1 otherwise)

The lock records SHA-256 of every file that defines the benchmark (public bundles, oracle, evaluator, clean-room tools,
baselines, node lists, protocol, model configuration), the dataset manifests the bundles were derived from, the
prediction schema version and the code commit. Results are comparable only within one lock.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from brainir import __version__, paths
from brainir.benchmark.bundle import BENCHMARK_ID, BUNDLE_FORMAT_VERSION
from brainir.benchmark.prediction import PREDICTION_SCHEMA_VERSION

HERE = Path(__file__).resolve().parent
LOCK = HERE / "BENCHMARK_LOCK.json"
FROZEN_DIRS = ("public", "public_blind", "oracle", "evaluator", "cleanroom", "baselines", "nodes")
FROZEN_FILES = ("PROTOCOL.md", "LEAKAGE_AUDIT.md", "build_public_bundle.py", "freeze.py")
EXCLUDE_SUFFIXES = (".pyc",)
EXCLUDE_PARTS = ("__pycache__", "results")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def frozen_files() -> dict[str, str]:
    out = {}
    for d in FROZEN_DIRS:
        for p in sorted((HERE / d).rglob("*")):
            if p.is_file() and p.suffix not in EXCLUDE_SUFFIXES and not any(x in p.parts for x in EXCLUDE_PARTS):
                out[p.relative_to(HERE).as_posix()] = _sha(p)
    for f in FROZEN_FILES:
        if (HERE / f).exists():
            out[f] = _sha(HERE / f)
    return out


def build_lock() -> dict:
    files = frozen_files()
    bundles = {}
    for name in ("public", "public_blind"):
        m = json.loads((HERE / name / "manifest.json").read_text(encoding="utf-8"))
        bundles[name] = {"tier": m["tier"], "bundle_sha256": m["bundle_sha256"], "created_utc": m["created_utc"],
                         "networks": [{"name": n["name"], "dataset": n["dataset"], "version": n["version"], "n_neurons": n["n_neurons"],
                                       "n_edges": n["n_edges"]} for n in m["networks"]]}
    manifests = {}
    for ds, ver in (("manc", "v1.2.1"), ("manc", "v1.2.3"), ("male-cns", "v1.0"), ("manc", "v1.0")):
        p = paths.manifests_dir() / f"{ds}_{ver}.manifest.json"
        if p.exists():
            manifests[f"{ds}:{ver}"] = _sha(p)
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.repo_root(), capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    lock = {
        "benchmark_id": BENCHMARK_ID, "bundle_format_version": BUNDLE_FORMAT_VERSION, "prediction_schema_version": PREDICTION_SCHEMA_VERSION,
        "frozen_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "brainir_version": __version__, "code_commit": commit,
        "oracle_sha256": _sha(HERE / "oracle" / "oracle.json"), "evaluator_sha256": _sha(HERE / "evaluator" / "evaluate.py"),
        "bundles": bundles, "dataset_manifests_sha256": manifests, "files": files,
    }
    lock["lock_sha256"] = hashlib.sha256(json.dumps({k: v for k, v in lock.items() if k != "frozen_utc"}, sort_keys=True).encode()).hexdigest()
    return lock


def check() -> dict:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    now = frozen_files()
    changed = sorted(k for k in lock["files"] if now.get(k) != lock["files"][k])
    added = sorted(k for k in now if k not in lock["files"])
    return {"ok": not changed and not added, "changed_or_missing": changed, "added": added, "lock_sha256": lock["lock_sha256"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        res = check()
        print(json.dumps(res, indent=1))
        return 0 if res["ok"] else 1
    lock = build_lock()
    LOCK.write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCK.name}: {len(lock['files'])} files, lock_sha256 {lock['lock_sha256'][:16]}, commit {lock['code_commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
