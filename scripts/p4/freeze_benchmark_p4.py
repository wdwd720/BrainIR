"""Freeze / check the Phase 4 benchmark `causal_state_v1` (goal5 section 7; PROTOCOL.md section 12).

    uv run --project phase4 python scripts/p4/freeze_benchmark_p4.py --write      # records BENCHMARK_LOCK.json
    uv run --project phase4 python scripts/p4/freeze_benchmark_p4.py --check      # recompute and compare (exit 1 on any difference)

BENCHMARK_LOCK.json records the LF-normalised sha256 of:
- every file under benchmarks/causal_state_v1/ (protocol, public docs and records, calibration, the locked generator copy, the
  hidden definition files and the salt COMMITMENT; the salt itself lives under data/phase4/hidden/ and is never hashed here);
- the evaluation / generation / tournament code of `brainir_causal` (every module EXCEPT the `methods/` package, which receives
  method snapshots), its Modal backend, the orchestrator scripts listed in SCRIPTS, the phase4 environment files and the Docker
  sandbox definition;
- the manifests and indexes of the generated public datasets and of the orchestrator-held validation suite (trajectory files are
  content-addressed by their keys; the sorted key list is hashed).
`--check` fails on a changed or missing recorded file AND on any NEW file inside benchmarks/causal_state_v1/ or inside the hashed
code directories (a post-freeze document belongs elsewhere). A change of any hashed file after the freeze is a new benchmark version
with a logged reason (PROTOCOL.md section 12). The isolation tooling (scripts/p4agent, the room builder, the remote runner) is NOT
part of the benchmark: it is tracked by the leakage policy and may be hardened during development.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "causal_state_v1"
LOCK = BENCH / "BENCHMARK_LOCK.json"
PKG = ROOT / "phase4" / "src" / "brainir_causal"
TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yaml", ".yml", ".csv", ".lock", ".sh", ".in"}
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
SCRIPTS = ("scripts/p4/freeze_benchmark_p4.py", "scripts/p4/make_public_docs.py", "scripts/p4/calibrate.py", "scripts/p4/tournament.py",
           "scripts/p4/modal_p4.py", "scripts/p4/build_suites.py", "scripts/p4/generate_real_public.py")
ENV_FILES = ("phase4/pyproject.toml", "phase4/uv.lock", "phase4/.python-version")
DOCKER_DIR = ROOT / "docker" / "p4sandbox"
DATASET_ROOTS = ("data/phase4/public/real", "data/phase4/suites/dev/public", "data/phase4/suites/val/public",
                 "data/phase4/suites/val/truth")
DATASET_FILES = ("manifest.json", "index.jsonl", "pools.json", "lift_cases.json", "truth.json", "truth_index.jsonl")


def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in TEXT:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def _walk(d: Path):
    for p in sorted(d.rglob("*")):
        if p.is_file() and not (set(p.parts) & SKIP_PARTS) and p.suffix != ".pyc":
            yield p


def collect() -> dict:
    files = {}
    for p in _walk(BENCH):
        if p != LOCK:
            files[p.relative_to(ROOT).as_posix()] = sha(p)
    for p in _walk(PKG):
        rel = p.relative_to(PKG).as_posix()
        if rel.startswith("methods/"):
            continue
        files[p.relative_to(ROOT).as_posix()] = sha(p)
    for s in SCRIPTS + ENV_FILES:
        if (ROOT / s).exists():
            files[s] = sha(ROOT / s)
    if DOCKER_DIR.exists():
        for p in _walk(DOCKER_DIR):
            files[p.relative_to(ROOT).as_posix()] = sha(p)
    data = {}
    for d in DATASET_ROOTS:
        dd = ROOT / d
        if not dd.exists():
            continue
        for f in DATASET_FILES:
            if (dd / f).exists():
                data[f"{d}/{f}"] = sha(dd / f)
        tr = dd / "traj"
        if tr.exists():
            names = sorted(q.name for q in tr.rglob("*.npz"))
            data[f"{d}/traj/<{len(names)} files: sha256 of the sorted name list>"] = hashlib.sha256("\n".join(names).encode()).hexdigest()
    return {"files": files, "datasets": data}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--version", default="1")
    ap.add_argument("--reason", default="")
    args = ap.parse_args(argv)
    cur = collect()
    if args.write:
        lock = {"benchmark": "causal_state_v1", "version": args.version, "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "reason": args.reason, **cur}
        LOCK.write_text(json.dumps(lock, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {LOCK.relative_to(ROOT)}: {len(cur['files'])} files, {len(cur['datasets'])} dataset entries")
        return 0
    if not LOCK.exists():
        print("no BENCHMARK_LOCK.json")
        return 1
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    bad = []
    for kind in ("files", "datasets"):
        rec, now = lock.get(kind, {}), cur[kind]
        for k, v in rec.items():
            if k not in now:
                bad.append(f"missing {k}")
            elif now[k] != v:
                bad.append(f"changed {k}")
        for k in now:
            if k not in rec and (kind == "datasets" or k.startswith("benchmarks/causal_state_v1/") or k.startswith("phase4/src/")):
                bad.append(f"new {k}")
    for b in bad:
        print(b)
    print("OK" if not bad else f"{len(bad)} difference(s)")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
