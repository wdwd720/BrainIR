"""Regenerate the Phase 2 candidate mechanisms from PUBLIC evidence only (goal4 section 5), in an isolated room.

    uv run python scripts/p3/regenerate_candidates.py [--room C:\\Dev\\BrainIR_p3regen]

1. builds the room: the locked library (every file verified against research/phase2/METHOD_LOCK.json), the public blind bundle
   (manifest hash verified) plus a public no-gate rhythm criterion per network, and the in-room driver; a stub README;
2. `uv sync --frozen` from the root lockfile (the Phase 2 environment);
3. runs the locked BrainIR v1.2 (seed 0, budget 1000) on each network in its own process under the Python audit guard, then
   validates every returned candidate (final core + enumerated alternatives) by keep-only on 8 fresh public parameter seeds;
4. writes research/phase3/candidates/regenerated_candidates.json and a provenance record (hashes of everything that went in).
The rule is fixed in advance: every candidate returned at the locked seed is kept if it validates; nothing is chosen by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NETWORKS = ("manc_v1.2.1", "male-cns_v1.0", "manc_v1.2.3")
UV = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe" / "uv.exe"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_room(room: Path) -> dict:
    if room.exists():
        shutil.rmtree(room)
    (room / "src").mkdir(parents=True)
    lock = json.loads((ROOT / "research" / "phase2" / "METHOD_LOCK.json").read_text(encoding="utf-8"))
    locked = lock["source_hashes"]
    copied = {}
    for rel, h in sorted(locked.items()):
        if not rel.startswith("src/brainir/"):
            continue
        src = ROOT / rel
        if _sha(src) != h:
            raise SystemExit(f"locked file changed: {rel}")
        dst = room / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied[rel] = h
    for f in ("pyproject.toml", "uv.lock", ".python-version"):
        shutil.copyfile(ROOT / f, room / f)
        copied[f] = _sha(ROOT / f)
    (room / "README.md").write_text("Phase 3 regeneration room (locked method + public bundle only).\n", encoding="utf-8", newline="\n")
    bundle_src = ROOT / "benchmarks" / "dng100" / "public_blind"
    man = json.loads((bundle_src / "manifest.json").read_text(encoding="utf-8"))
    if man["bundle_sha256"] != lock["benchmark"]["bundles"]["public_blind"]["bundle_sha256"]:
        raise SystemExit("public_blind bundle differs from the one recorded in the method lock")
    shutil.copytree(bundle_src, room / "bundle")
    metric = json.loads((bundle_src / "model_config.json").read_text(encoding="utf-8")).get("metric", {})
    crit = {"type": "rhythm", "analysis_start_s": metric.get("analysis_start_s", 0.25), "active_rate_hz": metric.get("active_rate_hz", 0.01),
            "prominence": metric.get("prominence", 0.05), "score_threshold": metric.get("rhythmic_threshold", 0.5), "amplitude_min_hz": 0.0}
    for net in NETWORKS:
        (room / "bundle" / "networks" / net / "criterion.json").write_text(json.dumps(crit, indent=1) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(Path(__file__).with_name("regen_in_room.py"), room / "regen_in_room.py")
    return {"locked_files": copied, "bundle_sha256": man["bundle_sha256"], "criterion": crit,
            "bundle_files": {p.relative_to(room / "bundle").as_posix(): _sha(p) for p in sorted((room / "bundle").rglob("*")) if p.is_file()},
            "driver_sha256": _sha(room / "regen_in_room.py"), "method_lock_sha256": lock.get("lock_sha256")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", type=Path, default=Path(r"C:\Dev\BrainIR_p3regen"))
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase3" / "candidates")
    args = ap.parse_args(argv)
    room = args.room.resolve()
    t0 = time.time()
    prov = build_room(room)
    subprocess.run([str(UV), "sync", "--frozen"], cwd=room, check=True)
    pyguard = ROOT / "scripts" / "p3agent" / "pyguard"
    env = dict(os.environ, P3_CLEAN_ROOT=str(room), PYTHONPATH=str(pyguard), PYTHONIOENCODING="utf-8",
               TEMP=str(room / ".tmp"), TMP=str(room / ".tmp"))
    (room / ".tmp").mkdir(exist_ok=True)
    py = room / ".venv" / "Scripts" / "python.exe"
    procs = []
    for net in NETWORKS:
        log = open(room / f"regen_{net}.log", "w", encoding="utf-8")
        procs.append((net, subprocess.Popen([str(py), str(room / "regen_in_room.py"), str(room), str(room / f"out_{net}.json"), net], cwd=room,
                                            env=env, stdout=log, stderr=subprocess.STDOUT), log))
    for net, p, log in procs:
        rc = p.wait()
        log.close()
        if rc != 0:
            raise SystemExit(f"{net} failed (exit {rc}); see {room / f'regen_{net}.log'}")
    merged = {"networks": {}}
    for net in NETWORKS:
        part = json.loads((room / f"out_{net}.json").read_text(encoding="utf-8"))
        merged.update({k: v for k, v in part.items() if k != "networks"})
        merged["networks"][net] = part["networks"][net]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "regenerated_candidates.json").write_text(json.dumps(merged, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    prov.update(room="$EXTERNAL/" + room.name, wall_s=round(time.time() - t0, 1), python=str(py.name), uv_sync="--frozen (root uv.lock)",
                commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
                output_sha256=_sha(args.out / "regenerated_candidates.json"))
    (args.out / "regeneration_provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8", newline="\n")
    for net in NETWORKS:
        c = merged["networks"][net]["candidates"]
        print(net, [(r["label"], r["size"], round(r["keep_only_pass_fraction"], 2)) for r in c])
    return 0


if __name__ == "__main__":
    sys.exit(main())
