"""Build the oracle-free Phase 2 development directory (goal3 section 4).

    uv run python scripts/make_phase2_cleanroom.py [--dest C:\\Dev\\BrainIR_p2clean] [--fresh]

Copies ONLY generic material into a separate directory where method-development agents work:
  * the library (src/brainir), packaging files, tests that carry no answer (everything except the leakage guard, which
    reads the oracle path, and the benchmark-package/baseline tests that read oracle-side files),
  * the public BLIND benchmark bundle (benchmarks/dng100/public_blind) and the bundle README (the tier-B bundle with real type
    names is not copied: no tier-B method is developed in the clean room; review E finding 8),
  * the clean-room runner + sandbox (so agents can exercise the method contract) and the frozen baseline SCRIPTS
    (benchmarks/dng100/baselines/*.py; NOT their answer-bearing results/),
  * the synthetic mechanism suite (data/synthetic/mechanisms_v1) and its PUBLIC instances only (truth/ excluded),
  * research/phase2/methods_review.md when present.
Excluded by construction: benchmarks/dng100/oracle, benchmarks/dng100/evaluator, benchmarks/dng100/baselines/results,
benchmarks/dng100_walking_cpg, research/literature, research/audit, goal*.md, PHASE*_REPORT.md, research/LOG.md,
data/raw, data/processed, data/manifests, any *.token / .modal.toml. A CLEANROOM_MANIFEST.json (file list + hashes) is
written so an auditor can verify nothing else was present.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT.parent / "BrainIR_p2clean"

COPY_TREES = [
    "src/brainir",
    "benchmarks/dng100/public_blind",
    "benchmarks/dng100/cleanroom",
    "data/synthetic/mechanisms_v1",
]
COPY_FILES = ["pyproject.toml", "uv.lock", ".python-version", ".gitattributes", "README.md", "benchmarks/dng100/PROTOCOL.md",
              "research/phase2/methods_review.md", "research/phase2/METHOD_DEV_CONTRACT.md", "scripts/run_tournament.py",
              "scripts/build_synthetic_suite.py"]
BASELINE_SCRIPTS = "benchmarks/dng100/baselines"
TEST_EXCLUDE = {"test_leakage_guard.py", "test_leakage_check.py", "test_benchmark_package.py", "test_baselines_contract.py", "test_freeze.py",
                "test_cleanroom_sandbox.py", "test_real_data.py"}
FORBIDDEN_SUBSTRINGS = ("oracle", "walking_cpg", "literature", "PHASE", "goal", "LOG.md", "/truth/", "\\truth\\", "audit", "results")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _copy_tree(src: Path, dst: Path, *, skip_parts: tuple[str, ...] = ("__pycache__", "truth", "results", ".pytest_cache")) -> list[Path]:
    out = []
    if not src.exists():
        return out
    for p in sorted(src.rglob("*")):
        if p.is_dir() or any(part in skip_parts for part in p.relative_to(src).parts) or p.suffix in (".pyc",):
            continue
        rel = p.relative_to(src)
        q = dst / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        out.append(q)
    return out


def build(dest: Path, fresh: bool) -> dict:
    if fresh and dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for t in COPY_TREES:
        copied += _copy_tree(ROOT / t, dest / t)
    for f in COPY_FILES:
        if (ROOT / f).exists():
            (dest / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / f, dest / f)
            copied.append(dest / f)
    # baseline scripts only (no results)
    for p in sorted((ROOT / BASELINE_SCRIPTS).glob("*.py")) + [ROOT / BASELINE_SCRIPTS / "README.md"]:
        if p.exists():
            q = dest / BASELINE_SCRIPTS / p.name
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, q)
            copied.append(q)
    # tests without answer dependencies
    for p in sorted((ROOT / "tests").glob("*.py")):
        if p.name in TEST_EXCLUDE:
            continue
        q = dest / "tests" / p.name
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        copied.append(q)
    for p in sorted((ROOT / "tests").glob("fixtures/**/*")):
        if p.is_file():
            q = dest / "tests" / p.relative_to(ROOT / "tests")
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, q)
            copied.append(q)
    # a CLAUDE.md for the clean room that states the rules and nothing about any circuit
    (dest / "CLAUDE.md").write_text(CLEANROOM_CLAUDE_MD, encoding="utf-8", newline="\n")
    (dest / ".gitignore").write_text("data/cache/\n__pycache__/\n.venv/\n*.pyc\n.pytest_cache/\n.ruff_cache/\n", encoding="utf-8", newline="\n")
    # audit: no forbidden path fragments, no answer tokens
    forbidden = ("oracle/", "walking_cpg", "literature", "/truth/", "baselines/results")
    bad = [str(q.relative_to(dest)) for q in copied if any(s in str(q.relative_to(dest)).replace("\\", "/") for s in forbidden)]
    manifest = {"created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "source_repo_head": _git_head(),
                "n_files": len(copied), "files": {str(q.relative_to(dest)).replace("\\", "/"): _sha(q) for q in sorted(copied)},
                "forbidden_path_hits": bad}
    (dest / "CLEANROOM_MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    return manifest


def _git_head() -> str | None:
    try:
        import subprocess
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


CLEANROOM_CLAUDE_MD = """# BrainIR — Phase 2 clean development environment (oracle-free)

This directory is a copy of the generic BrainIR library, the PUBLIC blind benchmark bundle (`benchmarks/dng100/public_blind`),
the clean-room runner, the frozen baseline scripts and the PUBLIC part of the synthetic mechanism suite
(`data/synthetic/mechanisms_v1/instances`). It contains no benchmark answer, no evaluator, no ground truth of the
synthetic instances (their `truth/` directory is deliberately absent) and no research notes about any specific circuit.

Rules for anyone working here (human or agent):
1. Develop mechanism-discovery methods that are benchmark-generic: no special cases for any dataset, no hard-coded
   mechanism sizes, no cell-type names, no neuron ids, no thresholds tuned against hidden answers.
2. The only feedback you may use is what the public problems and the simulator give you, plus the synthetic
   tournament harness that reports scores on synthetic instances (the harness runs elsewhere and returns metrics only).
3. Never look for, download or reason about published circuits of the benchmark's datasets.
4. Use `uv run --no-sync` inside this directory (it has its own environment: run `uv sync` once).
5. Method code goes to `src/brainir/methods/<name>.py` and registers with `brainir.discovery.MethodRegistry`;
   it must work through `python -m brainir.discovery.run --method <name>` under the clean-room runner.
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--fresh", action="store_true", help="delete the destination first")
    args = ap.parse_args(argv)
    m = build(args.dest, args.fresh)
    print(f"clean room at {args.dest}: {m['n_files']} files; forbidden path hits: {m['forbidden_path_hits']}")
    return 0 if not m["forbidden_path_hits"] else 1


if __name__ == "__main__":
    sys.exit(main())
