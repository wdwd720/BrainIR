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
INPUTS = ("benchmarks/causal_state_v1/BENCHMARK_LOCK.json", "benchmarks/causal_state_v1/public/tolerances.json",
          "research/phase4/CLEANROOM_MANIFEST.json", "data/phase4/public/real/manifest.json", "data/phase4/public/real/index.jsonl",
          "data/phase4/suites/dev/public/manifest.json", "data/phase4/suites/dev/public/index.jsonl", "docker/p4sandbox/image.json")


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
    for k, v in lock["inputs_sha256"].items():
        if (ROOT / k).exists() and sha(ROOT / k) != v:
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
    for p in sorted(LOCKED_DIR.glob("*.py")):
        if p.stem != "__init__":
            importlib.import_module(f"brainir_causal.methods.{p.stem}")
    m = api.get_method(args.method)
    d = api.get_designer(args.designer) if args.designer != "none" else None
    inputs = {rel: sha(ROOT / rel) for rel in INPUTS if (ROOT / rel).exists()}
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
           "source_sha256": tree_hashes(LOCKED_DIR), "inputs_sha256": inputs}
    LOCK.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {LOCK.relative_to(ROOT)}: {args.method} ({len(rec['source_sha256'])} source files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
