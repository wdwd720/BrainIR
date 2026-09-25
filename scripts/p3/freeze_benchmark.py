"""Freeze / check the Phase 3 benchmark state_discovery_v1 (goal4 sections 6-7; PROTOCOL.md section 10).

    uv run --project phase3 python scripts/p3/freeze_benchmark.py [--check]

BENCHMARK_LOCK.json records sha256 hashes of the protocol, the public and hidden definition files, the calibration, the synthetic
generator, the evaluator / generation / tournament code, the regenerated candidates, the Phase 3 environment files, and the manifests
and indexes of every generated dataset (the trajectory files themselves are content-addressed by their keys). The salt is locked by
its commitment only. `--check` recomputes everything and fails on any difference; `phase3/tests/test_benchmark_lock.py` runs it.
Text files are hashed with LF line endings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
LOCK = BENCH / "BENCHMARK_LOCK.json"
TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yaml", ".yml", ".csv", ".lock"}

CODE = ["phase3/src/brainir_state/" + m for m in (
    "__init__.py", "api.py", "data.py", "protocol.py", "evaluate.py", "evaluate_cross.py", "evaluate_lift.py", "evaluate_synth.py",
    "harness.py", "refmodels.py", "realsim.py", "realgen.py", "store.py", "simservice.py", "simclient.py", "synthsim.py", "suite_eval.py",
    "runner.py", "runguard.py")] + ["scripts/p3/" + s for s in (
    "generate_real_data.py", "generate_real_hidden.py", "build_synthetic_suites.py", "calibrate.py", "tournament.py",
    "regenerate_candidates.py", "regen_in_room.py", "freeze_benchmark.py", "simservice_systems.py", "level_c.py", "feedback.py")] + ["phase3/pyproject.toml", "phase3/uv.lock",
                                                                               "scripts/make_phase3_cleanroom.py"]
DATASETS = ["data/phase3/real_public", "data/phase3/synthetic_dev", "data/phase3/synthetic/heldout/public", "data/phase3/synthetic/final/public",
            "data/phase3/synthetic_truth/dev", "data/phase3/synthetic/heldout/truth", "data/phase3/synthetic/final/truth"]
DATASET_FILES = ("manifest.json", "index.jsonl", "micro_index.json", "micro_futures.npz", "truth.json", "truth_index.jsonl")


def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in TEXT:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def collect() -> dict:
    files = {}
    for p in sorted(BENCH.rglob("*")):
        if p.is_file() and p.name != "BENCHMARK_LOCK.json" and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts \
                and not p.suffix == ".pyc":
            files[p.relative_to(ROOT).as_posix()] = sha(p)
    for c in CODE:
        files[c] = sha(ROOT / c)
    for p in sorted((ROOT / "research" / "phase3" / "candidates").glob("*.json")):
        files[p.relative_to(ROOT).as_posix()] = sha(p)
    for p in (ROOT / "research" / "phase3" / "contracts").glob("*.md"):
        files[p.relative_to(ROOT).as_posix()] = sha(p)
    data = {}
    for d in DATASETS:
        dd = ROOT / d
        if not dd.exists():
            continue
        for f in DATASET_FILES:
            if (dd / f).exists():
                data[f"{d}/{f}"] = sha(dd / f)
        tr = dd / "traj"
        if tr.exists():
            names = sorted(q.name for q in tr.glob("*.npz"))
            data[f"{d}/traj/<{len(names)} files: sha256 of the sorted name list>"] = hashlib.sha256("\n".join(names).encode()).hexdigest()
    return {"files": files, "datasets": data}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    cur = collect()
    if args.check:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        bad = []
        for sec in ("files", "datasets"):
            for k, v in lock[sec].items():
                if cur[sec].get(k) != v:
                    bad.append(f"{sec}: {k} changed" if k in cur[sec] else f"{sec}: {k} missing")
            for k in cur[sec]:
                if k not in lock[sec] and sec == "files":
                    bad.append(f"files: {k} not in the lock")
        if bad:
            print("BENCHMARK LOCK CHECK FAILED:\n  " + "\n  ".join(bad[:40]))
            return 1
        print(f"benchmark lock ok ({len(lock['files'])} files, {len(lock['datasets'])} dataset entries)")
        return 0
    salt_commit = json.loads((BENCH / "hidden" / "salt_commitment.json").read_text(encoding="utf-8"))
    tol = json.loads((BENCH / "public" / "tolerances.json").read_text(encoding="utf-8"))
    rec = {"benchmark": "state_discovery_v1", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "git_tag": "state-discovery-benchmark-v1", "salt_sha256": salt_commit["sha256_of_salt"], "tolerances": tol,
           "note": "Changing any hashed file requires a new benchmark version (PROTOCOL.md section 10).", **cur}
    LOCK.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCK.relative_to(ROOT)}: {len(cur['files'])} files, {len(cur['datasets'])} dataset entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
