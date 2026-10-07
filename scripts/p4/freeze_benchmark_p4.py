"""Freeze / check the Phase 4 benchmark `causal_state_v1` (goal5 section 7; PROTOCOL.md section 12).

    uv run --project phase4 python scripts/p4/freeze_benchmark_p4.py --write      # records BENCHMARK_LOCK.json
    uv run --project phase4 python scripts/p4/freeze_benchmark_p4.py --check      # recompute and compare (exit 1 on any difference)

BENCHMARK_LOCK.json records the LF-normalised sha256 of:
- every file under benchmarks/causal_state_v1/ (protocol, public docs and records, calibration, the locked generator copy, the
  hidden definition files and the salt COMMITMENT; the salt itself lives under data/phase4/hidden/ and is never hashed here);
- the evaluation / generation / tournament code of `brainir_causal` (every module EXCEPT the `methods/` package, which receives
  method snapshots), its Modal backend, the orchestrator scripts listed in SCRIPTS, the phase4 environment files and the Docker
  image definitions (the sandbox image, the simulation-service worker image);
- the per-file sha256 BUILD MANIFESTS of every dataset directory (research/phase4/build_manifests/{real_public,real_B,syn_dev,
  syn_val}_<system>.json: every file each build container wrote, per part; LOG P4-D33); `scripts/p4/freeze_manifests.py
  --verify-local` checks the local copies (dev public part, public real data) against them file for file, `--remote` re-hashes the
  volumes.
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
#: every orchestrator script that builds, calibrates, evaluates or serves the benchmark (missing entries are an error at --write)
SCRIPTS = ("scripts/p4/freeze_benchmark_p4.py", "scripts/p4/freeze_manifests.py", "scripts/p4/make_public_docs.py", "scripts/p4/calibrate.py",
           "scripts/p4/tournament.py", "scripts/p4/modal_p4.py", "scripts/p4/build_on_modal.py", "scripts/p4/plan_synthetic.py",
           "scripts/p4/simservice_docker.py", "scripts/p4/calibration_check_suite.py", "scripts/p4/calibration_check_real.py",
           "scripts/p4/strip_row_field.py", "scripts/p4/verify_real_build.py", "scripts/p4/frozen_v1_smoke.py", "scripts/p4/method_lock_p4.py",
           "scripts/p4/active_mde.py")
ENV_FILES = ("phase4/pyproject.toml", "phase4/uv.lock", "phase4/.python-version")
DOCKER_DIRS = (ROOT / "docker" / "p4sandbox", ROOT / "docker" / "p4simservice")
#: the per-file sha256 build manifests of every dataset directory, one per system and tier, written by the build containers and stored
#: by build_on_modal.py (LOG P4-D33); scripts/p4/freeze_manifests.py verifies the local copies (and optionally the volumes) against them
MANIFEST_DIR = ROOT / "research" / "phase4" / "build_manifests"
MANIFEST_PREFIXES = ("real_public_", "real_B_", "syn_dev_", "syn_val_")


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
        else:
            files[s] = "MISSING"
    for dd in DOCKER_DIRS:
        for p in _walk(dd):
            files[p.relative_to(ROOT).as_posix()] = sha(p)
    data = {}
    if MANIFEST_DIR.exists():
        for p in sorted(MANIFEST_DIR.glob("*.json")):
            if p.name.startswith(MANIFEST_PREFIXES):
                data[p.relative_to(ROOT).as_posix()] = sha(p)
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
    missing = sorted(k for k, v in cur["files"].items() if v == "MISSING")
    if args.write and (missing or not cur["datasets"]):
        print(f"refusing to write: missing scripts {missing}, dataset manifests {len(cur['datasets'])} (run freeze_manifests.py)")
        return 1
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
