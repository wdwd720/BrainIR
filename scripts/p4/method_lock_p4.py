"""Phase 4 method lock (goal5 section 69; PROTOCOL.md section 12).

    uv run --project phase4 python scripts/p4/method_lock_p4.py --lock --method NAME --designer NAME|none --baseline NAME
        --from <methods snapshot dir> --selection <research/phase4/tournament/<round>/DECISION.json> --notes <composer notes>
        [--budget N] [--ablation-plan <json>]
    uv run --project phase4 python scripts/p4/method_lock_p4.py --check

--lock copies the selected snapshot of the clean room's methods package into phase4/src/brainir_causal/methods/ (the locked code
that Level C runs from), then writes research/phase4/METHOD_LOCK.json with everything goal5 section 69 names:
- source: sha256 of every file of the locked methods package (LF-normalised) and the commit;
- architecture / objective / dimension rule / training protocol: the composer's notes at lock time (hash-checked copy
  research/phase4/METHOD_NOTES.md) and the method's default configuration;
- active design policy and intervention budget: the designer's name and configuration, the budget per fit;
- thresholds and metrics: the benchmark lock hash (which covers PROTOCOL.md, the evaluator code and public/tolerances.json);
- seeds, fit budgets (time limits, threads, devices);
- dependency versions (python and the numerical stack from the phase4 environment; uv.lock hash; the sandbox image id);
- simulator versions (real engine and synthetic generator ids);
- data manifests (the public training data the tournament used);
- the strongest baseline fixed at Level B and the pre-registered ablation plan.
A locked method is never re-locked under the same version: any change is a new version with its own lock and new hidden data
(goal5 section 69; Phase 3 precedent). The tag brainir-causal-state-v1-preblind is created after the commit. --check verifies every
recorded hash and fails on any added file in the locked package.
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
LOCK = ROOT / "research" / "phase4" / "METHOD_LOCK.json"
LOCKED_DIR = ROOT / "phase4" / "src" / "brainir_causal" / "methods"
NOTES_COPY = ROOT / "research" / "phase4" / "METHOD_NOTES.md"
TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".lock"}
#: the frozen benchmark (its lock covers the protocol, the evaluator, the calibration, the tolerances and every dataset through the
#: build manifests), the clean room's manifest, the images, the Level B-fixed decisions (bounds, strongest baseline, delta_NI as a
#: NUMBER; `level_c.py fixed-from-levelb`) and every post-lock driver (Level C, ablations, counterexample search, robustness sweeps,
#: counterfactual API, self-audit): the lock fixes HOW the hidden evaluation runs as well as WHAT is evaluated
INPUTS = ("benchmarks/causal_state_v1/BENCHMARK_LOCK.json", "benchmarks/causal_state_v1/public/tolerances.json",
          "research/phase4/CLEANROOM_MANIFEST.json", "docker/p4sandbox/image.json", "docker/p4simservice/image.json",
          "research/phase4/LEVEL_B_FIXED.json",            # written by `level_c.py fixed-from-levelb` (levelc_lib.LEVEL_B_FIXED)
          "research/phase4/review_g/review_g.py",          # review G's trap catalog (synthadapter.TRAP_CATALOG_REL): fixed before any
                                                           # hidden evaluation
          "research/phase4/SELF_AUDIT_CONFIG.json")        # the self-audit's comparator roles and baselines (template: the
                                                           # self-audit CONFIG.json of the dry run under research/phase4)
AFTERLOCK_SCRIPTS = ("scripts/p4/level_c.py", "scripts/p4/levelc_lib.py", "scripts/p4/levelc_remote.py", "scripts/p4/ablations_p4.py",
                    "scripts/p4/counterexamples_p4.py", "scripts/p4/robustness_p4.py", "scripts/p4/counterfactual_p4.py",
                    "scripts/p4/self_audit_p4.py", "scripts/p4/p4post_iso.py", "scripts/p4/method_lock_p4.py")
AFTERLOCK_DIRS = ("scripts/p4/p4post",)                     # every .py below is a post-lock driver module (hashed as well)


def afterlock_driver_files() -> list[str]:
    """Every post-lock driver file the lock hashes: AFTERLOCK_SCRIPTS plus every .py under AFTERLOCK_DIRS."""
    out = list(AFTERLOCK_SCRIPTS)
    for d in AFTERLOCK_DIRS:
        out += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / d).rglob("*.py") if "__pycache__" not in p.parts)
    return out


def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in TEXT:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def tree_hashes(d: Path) -> dict:
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(d.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def environment() -> dict:
    out = {"python": sys.version.split()[0], "uv_lock_sha256": sha(ROOT / "phase4" / "uv.lock"),
           "pyproject_sha256": sha(ROOT / "phase4" / "pyproject.toml")}
    from importlib import metadata
    want = {"numpy", "scipy", "torch", "scikit-learn", "pandas", "pyarrow", "pydantic", "threadpoolctl", "modal"}
    out["packages"] = {d.metadata["Name"].lower(): d.version for d in metadata.distributions() if d.metadata["Name"].lower() in want}
    return out


def simulators() -> dict:
    sys.path.insert(0, str(ROOT / "phase4" / "src"))
    out = {}
    try:
        from brainir_causal import realsim
        out["real_engine"] = getattr(realsim, "ENGINE_VERSION", "?")
    except Exception as exc:  # noqa: BLE001
        out["real_engine"] = f"unavailable: {exc}"
    gen = ROOT / "benchmarks" / "causal_state_v1" / "generator"
    out["synthetic_generator_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(gen.rglob("*.py"))} if gen.exists() else {}
    return out


def check() -> int:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    bad = [k for k, v in lock["source_sha256"].items() if not (ROOT / k).exists() or sha(ROOT / k) != v]
    extra = [k for k in tree_hashes(LOCKED_DIR) if k not in lock["source_sha256"]]
    for k, v in {**lock["inputs_sha256"], **(lock.get("afterlock_drivers_sha256") or {})}.items():
        if not (ROOT / k).exists() or sha(ROOT / k) != v:          # a deleted input fails too
            bad.append(k)
    if bad or extra:
        print("METHOD LOCK CHECK FAILED:", {"changed": bad, "added": extra})
        return 1
    print(f"method lock ok ({lock['method']}, {len(lock['source_sha256'])} source files)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--method", default="")
    ap.add_argument("--designer", default="none")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--from", dest="src", default="")
    ap.add_argument("--selection", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--ablation-plan", default="")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    if not args.lock:
        ap.error("--lock or --check")
    if LOCK.exists():
        raise SystemExit("METHOD_LOCK.json exists: a locked method is never re-locked under the same version (a change is v2)")
    src = Path(args.src)
    if LOCKED_DIR.exists():
        shutil.rmtree(LOCKED_DIR)
    shutil.copytree(src, LOCKED_DIR, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    sys.path.insert(0, str(ROOT / "phase4" / "src"))
    import importlib
    from brainir_causal import api
    import pkgutil
    import brainir_causal.methods as _methods
    for mod in pkgutil.walk_packages(_methods.__path__, prefix="brainir_causal.methods."):   # per-developer packages methods/<prefix>/
        importlib.import_module(mod.name)
    m = api.get_method(args.method)
    d = api.get_designer(args.designer) if args.designer != "none" else None
    missing = [rel for rel in INPUTS if not (ROOT / rel).exists()]
    if missing:
        raise SystemExit(f"refusing to lock: missing inputs {missing}")
    inputs = {rel: sha(ROOT / rel) for rel in INPUTS}
    missing_drivers = [rel for rel in afterlock_driver_files() if not (ROOT / rel).exists()]
    if missing_drivers:
        raise SystemExit(f"refusing to lock: missing post-lock drivers {missing_drivers}")
    drivers = {rel: sha(ROOT / rel) for rel in afterlock_driver_files()}
    fixed = json.loads((ROOT / "research" / "phase4" / "LEVEL_B_FIXED.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    notes = Path(args.notes).read_text(encoding="utf-8") if args.notes and Path(args.notes).exists() else ""
    if notes:
        NOTES_COPY.write_text(notes.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        inputs[NOTES_COPY.relative_to(ROOT).as_posix()] = sha(NOTES_COPY)
    abl = json.loads(Path(args.ablation_plan).read_text(encoding="utf-8")) if args.ablation_plan else {}
    rec = {"method": args.method, "method_version": getattr(m, "version", "?"), "name": "BrainIR Causal State v1",
           "locked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commit_at_lock": commit,
           "tag": "brainir-causal-state-v1-preblind", "strongest_baseline": args.baseline, "selection_record": args.selection,
           "configuration": {"default_config": getattr(m, "default_config", {}), "supported_sharing": list(getattr(m, "supported_sharing", ())),
                             "supports_adaptation": bool(getattr(m, "supports_adaptation", False)),
                             "device": getattr(m, "device", "cpu")},
           "active_design": {"designer": args.designer, "designer_config": getattr(d, "default_config", {}) if d else {},
                             "intervention_budget_per_fit": args.budget},
           "architecture_objective_dimension_rule_training_protocol": notes,
           "notes_file": NOTES_COPY.relative_to(ROOT).as_posix() if notes else None,
           "seeds": {"level_c": "seed 0 for every primary fit; seeds 0-4 for representation stability; bootstrap refits 0-4 for "
                                "dimension stability; loop seeds 0-2 for the active-design curves"},
           "budgets": {"fit_timeout_s": {"synthetic": 900, "real_full": 1800, "shared": "2x"}, "threads_per_fit": 4, "gpu_fit_timeout_s": 600},
           "thresholds_and_metrics": "benchmarks/causal_state_v1 BENCHMARK_LOCK.json (PROTOCOL.md, evaluator code, public/tolerances.json)",
           "ablation_plan": abl, "environment": environment(), "simulators": simulators(),
           "level_b_fixed": fixed, "afterlock_drivers_sha256": drivers,
           "source_sha256": tree_hashes(LOCKED_DIR), "inputs_sha256": inputs}
    LOCK.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCK.relative_to(ROOT)}: {args.method} ({len(rec['source_sha256'])} source files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
