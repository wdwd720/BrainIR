"""Phase 3 method lock (goal4 sections 57, 86; PROTOCOL.md section 10).

    uv run --project phase3 python scripts/p3/method_lock_p3.py --lock --method NAME --baseline NAME --from <methods snapshot dir>
                                                                --selection <research/phase3/tournament/<round>/AGGREGATE...json> [--notes ...]
    uv run --project phase3 python scripts/p3/method_lock_p3.py --check

--lock copies the selected snapshot of the clean room's methods package into phase3/src/brainir_state/methods/ (the locked code the
Level B confirmation and Level C run from), then writes research/phase3/METHOD_LOCK.json with:
- the commit;
- source hashes of the locked methods package;
- the benchmark lock hash and the clean-room manifest hash;
- the training-data manifests;
- the method's configuration (default_config, version, supported sharing / adaptation);
- the dimension rule and objective (from its notes);
- the seed policy, the fit budgets and the package environment.
The tag brainir-state-v1-preblind is created by the orchestrator after committing. --check verifies every hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "research" / "phase3" / "METHOD_LOCK.json"
LOCKED_DIR = ROOT / "phase3" / "src" / "brainir_state" / "methods"
NOTES_COPY = ROOT / "research" / "phase3" / "METHOD_NOTES.md"
TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".lock"}


def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in TEXT:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def tree_hashes(d: Path) -> dict:
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(d.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def environment() -> dict:
    out = {"python": sys.version.split()[0], "uv_lock_sha256": sha(ROOT / "phase3" / "uv.lock"),
           "pyproject_sha256": sha(ROOT / "phase3" / "pyproject.toml")}
    try:
        from importlib import metadata
        out["packages"] = {d.metadata["Name"].lower(): d.version for d in metadata.distributions()
                           if d.metadata["Name"].lower() in {"numpy", "scipy", "torch", "scikit-learn", "pandas", "pyarrow", "pydantic"}}
    except Exception:  # noqa: BLE001
        pass
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--method", default="")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--from", dest="src", default="")
    ap.add_argument("--selection", default="")
    ap.add_argument("--notes", default="")
    args = ap.parse_args(argv)
    if args.check:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        bad = [k for k, v in lock["source_sha256"].items() if not (ROOT / k).exists() or sha(ROOT / k) != v]
        extra = [k for k in tree_hashes(LOCKED_DIR) if k not in lock["source_sha256"]]
        for k, v in lock["inputs_sha256"].items():
            if (ROOT / k).exists() and sha(ROOT / k) != v:
                bad.append(k)
        if bad or extra:
            print("METHOD LOCK CHECK FAILED:", {"changed": bad, "added": extra})
            return 1
        print(f"method lock ok ({lock['method']}, {len(lock['source_sha256'])} source files)")
        return 0
    if not args.lock:
        ap.error("--lock or --check")
    if LOCK.exists():
        raise SystemExit("METHOD_LOCK.json exists: a locked method is never re-locked under the same version (a change is v2)")
    src = Path(args.src)
    if LOCKED_DIR.exists():
        shutil.rmtree(LOCKED_DIR)
    shutil.copytree(src, LOCKED_DIR, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    sys.path.insert(0, str(ROOT / "phase3" / "src"))
    import importlib
    from brainir_state.api import get_method
    for p in sorted(LOCKED_DIR.glob("*.py")):
        if p.stem != "__init__":
            importlib.import_module(f"brainir_state.methods.{p.stem}")
    m = get_method(args.method)
    inputs = {}
    for rel in ("benchmarks/state_discovery_v1/BENCHMARK_LOCK.json", "research/phase3/CLEANROOM_MANIFEST.json",
                "data/phase3/real_public/manifest.json", "data/phase3/real_public/index.jsonl",
                "data/phase3/synthetic/heldout/public/manifest.json", "data/phase3/synthetic/heldout/public/index.jsonl"):
        if (ROOT / rel).exists():
            inputs[rel] = sha(ROOT / rel)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    notes = Path(args.notes).read_text(encoding="utf-8") if args.notes and Path(args.notes).exists() else ""
    if notes:       # the developer's full notes at lock time (dimension rule, objective, changes since the tournament), hash-checked
        NOTES_COPY.write_text(notes.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        inputs[NOTES_COPY.relative_to(ROOT).as_posix()] = sha(NOTES_COPY)
    rec = {"method": args.method, "method_version": getattr(m, "version", "?"), "name": "BrainIR State v1", "locked_utc":
           time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commit_at_lock": commit, "tag": "brainir-state-v1-preblind",
           "strongest_baseline": args.baseline, "selection_record": args.selection,
           "configuration": {"default_config": getattr(m, "default_config", {}), "supported_sharing": list(getattr(m, "supported_sharing", ())),
                             "supports_adaptation": bool(getattr(m, "supports_adaptation", False))},
           "dimension_rule_and_objective": notes, "notes_file": NOTES_COPY.relative_to(ROOT).as_posix() if notes else None,
           "seeds": {"level_c": "seeds 0-4 for the locked method (G), seed 0 for everything else", "level_b_confirmation": "seed 0; seeds 1-2 on 8 systems"},
           "budgets": {"fit_timeout_s": {"synthetic": 1800, "real": 3600, "shared": "2x"}, "sim_budget_units_per_fit": 250,
                       "threads_per_fit": 3},
           "intervention_training_split": "public families only (PROTOCOL.md section 3)",
           "evaluator": "benchmarks/state_discovery_v1 (BENCHMARK_LOCK.json)", "environment": environment(),
           "source_sha256": tree_hashes(LOCKED_DIR), "inputs_sha256": inputs}
    LOCK.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCK.relative_to(ROOT)}: {args.method} ({len(rec['source_sha256'])} source files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
