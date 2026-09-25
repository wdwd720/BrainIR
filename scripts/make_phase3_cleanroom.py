"""Build / check / rebuild the Phase 3 method-development clean room from an explicit allowlist (goal4 sections 3-4).

    uv run python scripts/make_phase3_cleanroom.py --build                # create C:\\Dev\\BrainIR_p3clean (refuses if it exists)
    uv run python scripts/make_phase3_cleanroom.py --check                # verify every allowlisted file, flag anything else
    uv run python scripts/make_phase3_cleanroom.py --sync "<reason>"      # copy changed allowlisted files, record the sync, scan
    uv run python scripts/make_phase3_cleanroom.py --destroy-and-rebuild  # delete and build again (method work areas are lost)

Every file that enters has an allowlist entry {path, source, reason, sha256, leakage_class}; the manifest is written to
research/phase3/CLEANROOM_MANIFEST.json (outside the room) and a copy inside. The room holds ONLY: the public Phase 3 modules (data
formats, protocol, method API, the public evaluator and reference controls, the simulation-service client), a standalone project
file, public datasets (real public train / val trajectories; synthetic dev trajectories WITHOUT truth), the public system definitions
(including the candidate mechanisms regenerated from public evidence), the benchmark PROTOCOL.md, the development contract and the
methods-only literature review. No simulator code (simulation only through the budgeted service), no Phase 1-2 library or report,
no bundle, no oracle, no hidden data, no truth.

`--check` fails on: a missing or modified allowlisted file; any file outside the allowlist and outside the method work areas
(src/brainir_state/methods/, runs/, notes/, .venv/, .tmp/, simq/, .pytest_cache/, __pycache__/); any file anywhere whose name or
content matches a forbidden class (Phase 2 report, oracle, hidden evaluation, truth directories, answer phrases).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN = Path(r"C:\Dev\BrainIR_p3clean")
MANIFEST = ROOT / "research" / "phase3" / "CLEANROOM_MANIFEST.json"
DATA = ROOT / "data" / "phase3"

# module names of brainir_state that are public (the ".py" suffix is added below)
PUBLIC_MODULES = [m + ".py" for m in ("__init__", "data", "protocol", "api", "evaluate", "refmodels", "simclient", "harness", "evaluate_cross",
                                      "evaluate_lift")]
WORK_AREAS = ("src/brainir_state/methods/", "runs/", "notes/", ".venv/", ".tmp/", "simq/", ".pytest_cache/", "tests/methods/")
FORBIDDEN_NAMES = re.compile(r"(?i)(phase2_report|phase1_report|phase0_report|hidden_eval|blind_eval|oracle|method_lock|benchmark_lock|"
                             r"(^|[\\/])truth([\\/]|$)|build_report|audit_report|realsim|realgen|simservice|synthsim|suite_eval|"
                             r"evaluate_synth|synthetic_truth|salt|calibration\.json|synthetic_suites|network_map|systems_internal|"
                             r"goal[1-4]\.md|dng100_walking)")
FORBIDDEN_CONTENT = re.compile(r"(?i)(inhibitory slot|e-core recall|excitatory core recall|published core|published circuit|"
                               r"published answer|\bE1/E2\b|I1\|I2|core_contralateral|answer key|dng100|pugliese|\bmanc\b|male-?cns|"
                               r"hidden_eval_log|phase2_report)")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yaml", ".yml", ".csv"}

CLEAN_CLAUDE_MD = """# BrainIR Phase 3 clean development room (state discovery)

You develop methods that discover low-dimensional causal STATE representations of simulated neural systems: an encoder from the
observed microstate x (and input u) to a latent z, latent dynamics f and a readout g, validated by prediction, closure,
interventions and microstate equivalence. Start with docs/METHOD_DEV_CONTRACT.md, then docs/PROTOCOL.md (the frozen evaluation) and
docs/METHODS_REVIEW.md (methods literature).

Rules (enforced by a guard; do not try to get around it):
1. Work only inside this directory. Nothing outside it is reachable.
2. Simulation only through the budgeted service: `from brainir_state.simclient import SimClient` (public protocol families only).
3. Datasets: data/ (real public train / val trajectories; synthetic development trajectories). There is no ground truth here.
4. Put your method in src/brainir_state/methods/<prefix>_*.py, its tests in tests/methods/, experiments in runs/<prefix>/, notes in
   notes/<prefix>_*.md. Several developers share this room: never modify another developer's files.
5. Methods must be generic: no special cases for particular systems, no hard-coded latent dimension, no semantic labels (phase,
   amplitude, excitation...) as training targets. The latent dimension must be chosen by a generic rule.
6. Never use the readout y as encoder input; never let an encoder see future samples.
7. Use `uv run` (the environment is already synced; do not change pyproject.toml). No web access.
8. The CPU is shared: at most 3 threads per process, one heavy experiment at a time.
"""


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n") if p.suffix in TEXT_SUFFIXES else p.read_bytes()).hexdigest()


def allowlist() -> list[dict]:
    """(source, destination, reason, leakage class) of everything that enters the room; sources must exist."""
    items = []

    def add(src: Path, dst: str, reason: str, cls: str):
        items.append({"source": src, "path": dst, "reason": reason, "leakage_class": cls})

    for m in PUBLIC_MODULES:
        add(ROOT / "phase3" / "src" / "brainir_state" / m, f"src/brainir_state/{m}", "public Phase 3 module (formats, API, public evaluator)",
            "generic-public")
    add(ROOT / "phase3" / "cleanroom" / "pyproject.toml", "pyproject.toml", "standalone project (numerical stack + ML dependencies)",
        "generic-public")
    add(ROOT / ".python-version", ".python-version", "interpreter version", "generic-public")
    add(ROOT / "benchmarks" / "state_discovery_v1" / "PROTOCOL.md", "docs/PROTOCOL.md", "the frozen public evaluation protocol",
        "benchmark-public")
    add(ROOT / "research" / "phase3" / "contracts" / "METHOD_DEV_CONTRACT.md", "docs/METHOD_DEV_CONTRACT.md", "development contract",
        "generic-public")
    lit = ROOT / "research" / "phase3" / "METHODS_REVIEW.md"
    if lit.exists():
        add(lit, "docs/METHODS_REVIEW.md", "methods-only literature review (oracle-free agent)", "methods-literature")
    sysj = ROOT / "benchmarks" / "state_discovery_v1" / "public" / "systems_public.json"
    if sysj.exists():
        add(sysj, "data/systems_public.json", "public system definitions (populations, targets A, local graphs)", "benchmark-public")
    tol = ROOT / "benchmarks" / "state_discovery_v1" / "public" / "tolerances.json"
    if tol.exists():
        add(tol, "data/tolerances.json", "calibrated verdict tolerances (PROTOCOL.md section 6; values only)", "benchmark-public")
    cand = ROOT / "research" / "phase3" / "candidates" / "regenerated_candidates_public.json"
    if cand.exists():
        add(cand, "data/regenerated_candidates.json", "candidate mechanisms regenerated from public evidence by the locked Phase 2 method",
            "public-derived")
    for sub, reason in (("real_public", "real public train / val trajectories"), ("synthetic_dev", "synthetic development trajectories (no truth)")):
        d = DATA / sub
        if d.exists():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    add(p, f"data/{sub}/{p.relative_to(d).as_posix()}", reason, "benchmark-public")
    return items


def build(dest: Path) -> dict:
    if dest.exists():
        raise SystemExit(f"{dest} exists: use --check or --destroy-and-rebuild")
    dest.mkdir(parents=True)
    entries = []
    for it in allowlist():
        src, dst = it["source"], dest / it["path"]
        if not src.exists():
            raise SystemExit(f"allowlisted source missing: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        entries.append({"path": it["path"], "source": "$REPO/" + src.relative_to(ROOT).as_posix(), "reason": it["reason"],
                        "sha256": _sha(dst), "leakage_class": it["leakage_class"]})
    (dest / "CLAUDE.md").write_text(CLEAN_CLAUDE_MD, encoding="utf-8", newline="\n")
    entries.append({"path": "CLAUDE.md", "source": "generated by scripts/make_phase3_cleanroom.py", "reason": "clean-room rules",
                    "sha256": _sha(dest / "CLAUDE.md"), "leakage_class": "generated-generic"})
    for d in ("src/brainir_state/methods", "runs", "notes", "simq/requests", "simq/results", "tests/methods"):
        (dest / d).mkdir(parents=True, exist_ok=True)
    (dest / "src" / "brainir_state" / "methods" / "__init__.py").write_text('"""Method implementations (clean-room work area)."""\n',
                                                                               encoding="utf-8", newline="\n")
    manifest = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "room": "$EXTERNAL/" + dest.name, "n_files": len(entries),
                "files": sorted(entries, key=lambda e: e["path"]), "work_areas": list(WORK_AREAS),
                "excluded_by_design": ["brainir (Phase 1-2 library)", "any simulator code", "the public bundle", "PHASE0-2 reports and goal files",
                                       "oracle / evaluator outputs / hidden data", "synthetic generator code and truth",
                                       "benchmark hidden/ and synthetic_hidden/", "calibration outputs beyond the tolerance values"]}
    problems = scan(dest, manifest)
    manifest["build_scan_problems"] = problems
    for p in (MANIFEST, dest / "CLEANROOM_MANIFEST.json"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    if problems:
        raise SystemExit(f"build scan failed: {problems[:5]}")
    return manifest


def scan(dest: Path, manifest: dict) -> list[str]:
    """Problems: allowlisted files missing / modified; unexpected files outside work areas; forbidden names or content anywhere."""
    probs = []
    listed = {e["path"]: e["sha256"] for e in manifest["files"]}
    for path, h in listed.items():
        p = dest / path
        if not p.exists():
            probs.append(f"missing: {path}")
        elif _sha(p) != h:
            probs.append(f"modified: {path}")
    for p in sorted(dest.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(dest).as_posix()
        in_work = any(rel.startswith(w) for w in WORK_AREAS) or "/__pycache__/" in f"/{rel}" or rel == "CLEANROOM_MANIFEST.json" \
            or rel == "uv.lock"
        if rel.startswith(".venv/"):
            continue
        if rel not in listed and not in_work:
            probs.append(f"unexpected file: {rel}")
        if FORBIDDEN_NAMES.search(rel):
            probs.append(f"forbidden name: {rel}")
        if p.suffix in TEXT_SUFFIXES and p.stat().st_size < 20_000_000 and not rel.startswith(".tmp/"):
            try:
                m = FORBIDDEN_CONTENT.search(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                m = None
            if m:
                probs.append(f"forbidden content {m.group(0)!r} in {rel}")
    return probs


def sync(dest: Path, reason: str) -> dict:
    """Bring an existing room up to date with the allowlist: copy every allowlisted file whose source changed (or that is missing),
    update its manifest entry, record the sync (time, reason, files) in the manifest, then scan. Method work areas are untouched."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_path = {e["path"]: e for e in manifest["files"]}
    changed = []
    for it in allowlist():
        src, dst = it["source"], dest / it["path"]
        if not src.exists():
            raise SystemExit(f"allowlisted source missing: {src}")
        if dst.exists() and _sha(dst) == _sha(src):
            continue
        if FORBIDDEN_NAMES.search(it["path"]):
            raise SystemExit(f"forbidden name: {it['path']}")
        if src.suffix in TEXT_SUFFIXES:
            m = FORBIDDEN_CONTENT.search(src.read_text(encoding="utf-8", errors="ignore"))
            if m:
                raise SystemExit(f"forbidden content {m.group(0)!r} in {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        by_path[it["path"]] = {"path": it["path"], "source": "$REPO/" + src.relative_to(ROOT).as_posix(), "reason": it["reason"],
                               "sha256": _sha(dst), "leakage_class": it["leakage_class"]}
        changed.append(it["path"])
    manifest["files"] = sorted(by_path.values(), key=lambda e: e["path"])
    manifest["n_files"] = len(manifest["files"])
    manifest.setdefault("syncs", []).append({"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "reason": reason,
                                             "files": changed})
    problems = scan(dest, manifest)
    if problems:
        raise SystemExit(f"sync scan failed (manifest not written): {problems[:5]}")
    for p in (MANIFEST, dest / "CLEANROOM_MANIFEST.json"):
        p.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    return {"changed": changed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--destroy-and-rebuild", action="store_true")
    g.add_argument("--sync", metavar="REASON", help="update changed allowlisted files in an existing room (work areas untouched)")
    ap.add_argument("--dest", type=Path, default=CLEAN)
    args = ap.parse_args(argv)
    if args.sync:
        r = sync(args.dest, args.sync)
        print(f"synced {args.dest}: {len(r['changed'])} files: {r['changed']}")
        return 0
    if args.destroy_and_rebuild:
        if args.dest.exists():
            shutil.rmtree(args.dest)
        args.build = True
    if args.build:
        m = build(args.dest)
        print(f"built {args.dest}: {m['n_files']} allowlisted files; scan clean")
        return 0
    manifest = json.loads((MANIFEST).read_text(encoding="utf-8"))
    probs = scan(args.dest, manifest)
    print("\n".join(probs) if probs else f"ok: {args.dest} matches the allowlist ({manifest['n_files']} files) and holds no forbidden file")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
