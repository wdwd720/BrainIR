"""Build the oracle-free Phase 2 development directory (goal3 section 4).

    uv run python scripts/make_phase2_cleanroom.py [--dest C:\\Dev\\BrainIR_p2clean] [--fresh]

Copies ONLY generic material into a separate directory where method-development agents work:
  * the library (src/brainir), packaging files, tests that carry no answer (everything except the leakage guard, which
    reads the oracle path, and the benchmark-package/baseline tests that read oracle-side files),
  * the public BLIND benchmark bundle (benchmarks/dng100/public_blind) and the bundle README (the tier-B bundle with real type
    names is not copied: no tier-B method is developed in the clean room; review E finding 8),
  * the clean-room runner + sandbox (so agents can exercise the method contract; not the leakage check),
  * the synthetic mechanism suite (data/synthetic/mechanisms_v1) and its PUBLIC instances only (every truth* directory and every
    build or audit report excluded),
  * research/phase2/methods_review.md when present.
Excluded by construction: benchmarks/dng100/oracle, benchmarks/dng100/evaluator, benchmarks/dng100/baselines/results,
benchmarks/dng100_walking_cpg, research/literature, research/audit, goal*.md, PHASE*_REPORT.md, research/LOG.md,
data/raw, data/processed, data/manifests, any *.token / .modal.toml. A CLEANROOM_MANIFEST.json (file list + hashes) is
written so an auditor can verify nothing else was present.

Hardened after review D (research/phase2/reviews/D_leakage.md, findings D1, D2, D11) for any LATER clean room (the Phase 2 room
was built before these changes, and every change here is recorded in PHASE2_REPORT.md section 2):
  * the benchmark PROTOCOL.md, the repository README.md and the baseline scripts and README are no longer copied (they describe
    the answer's structure: its size, sign composition, the inhibitory slot and that pruning recovers it);
  * every copied text file is scanned for answer phrases (CONTENT_PATTERNS); a hit fails the build unless the file is listed in
    ALLOWED_CONTENT_HITS with its reason (frozen benchmark code that cannot change);
  * `--check PATH ...` applies the same path and content rules to files before a manual one-by-one sync (`cp`);
  * post-lock answer-bearing Phase 2 outputs are refused by path (hidden evaluations, reliability sweeps, blind runs, review D,
    the Phase 2 report).
Isolation remains procedural unless development agents run as SEPARATE sessions whose project directory is the clean room, with a
private temp directory (review D, D2): a subagent of the answer-aware session inherits that session's CLAUDE.md and scratchpad.
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
COPY_FILES = ["pyproject.toml", "uv.lock", ".python-version", ".gitattributes",
              "research/phase2/methods_review.md", "research/phase2/METHOD_DEV_CONTRACT.md", "scripts/run_tournament.py",
              "scripts/build_synthetic_suite.py"]
TEST_EXCLUDE = {"test_leakage_guard.py", "test_leakage_check.py", "test_benchmark_package.py", "test_baselines_contract.py", "test_freeze.py",
                "test_cleanroom_sandbox.py", "test_real_data.py"}
FORBIDDEN_SUBSTRINGS = ("oracle", "walking_cpg", "literature", "PHASE", "goal", "LOG.md", "/truth/", "\\truth\\", "audit", "results")
# path fragments refused in the room and by --check (review D, D11: post-lock answer-bearing Phase 2 outputs included)
FORBIDDEN_PATHS = ("oracle/", "walking_cpg", "literature", "/truth/", "truth/", "baselines/", "PROTOCOL.md", "evaluator/", "hidden",
                   "research/phase2/reliability", "research/phase2/blind_eval", "research/phase2/reviews/D_", "research/phase2/tournament",
                   "PHASE2_REPORT", "PHASE1_REPORT", "PHASE0_REPORT", "BUILD_REPORT", "AUDIT_REPORT", "build_report", "audit_report", "goal")
# answer phrases (lower-case substrings) that no clean-room file may contain (review D, D1). The model's source paper is cited by
# the frozen public bundle itself (sign rule `pugliese2026.sign.predictedNt`, model_config, network.json) and by the library, so
# its name is not a pattern: that residual route (an agent recalling the paper) is disclosed in PHASE2_REPORT.md section 2.
CONTENT_PATTERNS = ("inhibitory slot", "e-core recall", "excitatory core recall", "published core", "published circuit", "published answer",
                    "2 e + 1 i", "2e+1i", "e1/e2", "i1|i2", "core_contralateral", "answer key", "dng100 walking")
# files that must be copied, cannot change and mention a pattern only to prohibit or deny it (review D, D1)
ALLOWED_CONTENT_HITS = {
    "src/brainir/benchmark/bundle.py": "frozen benchmark code (BENCHMARK_LOCK); the docstring says the bundle has 'no published circuit'",
    "research/phase2/METHOD_DEV_CONTRACT.md": "the development contract; its rule forbids looking for the published circuits",
}
# never copied, whatever the tree (review D, D1 and D6: answer structure; build and audit reports carry development truth)
SKIP_NAMES = ("BUILD_REPORT", "AUDIT_REPORT", "build_report", "audit_report", "leakage_check.py", "LEAKAGE_AUDIT")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _copy_tree(src: Path, dst: Path, *, skip_parts: tuple[str, ...] = ("__pycache__", "truth", "results", ".pytest_cache")) -> list[Path]:
    out = []
    if not src.exists():
        return out
    for p in sorted(src.rglob("*")):
        # any directory named truth* (e.g. truth_backup_pre_audit) carries truth (review D follow-up)
        if p.is_dir() or any(part in skip_parts or part.startswith("truth") for part in p.relative_to(src).parts) or p.suffix in (".pyc",):
            continue
        if any(s in p.name for s in SKIP_NAMES):
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
    # the frozen baseline scripts and their README are NOT copied any more (review D, D1: they describe the answer's structure);
    # the baseline's algorithm is available as the generic `greedy_reference` method in src/brainir/methods
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
    # audit: no forbidden path fragments, no answer phrases
    rels = {q: str(q.relative_to(dest)).replace("\\", "/") for q in copied}
    bad = [r for q, r in rels.items() if path_violation(r)]
    content = {r: hits for q, r in rels.items() if (hits := content_hits(q)) and r not in ALLOWED_CONTENT_HITS}
    allowed = {r: {"hits": hits, "reason": ALLOWED_CONTENT_HITS[r]} for q, r in rels.items() if r in ALLOWED_CONTENT_HITS and (hits := content_hits(q))}
    manifest = {"created_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "source_repo_head": _git_head(),
                "n_files": len(copied), "files": {r: _sha(q) for q, r in sorted(rels.items(), key=lambda kv: kv[1])},
                "forbidden_path_hits": bad, "forbidden_content_hits": content, "allowed_content_hits": allowed}
    (dest / "CLEANROOM_MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    return manifest


def path_violation(rel: str) -> bool:
    rel = rel.replace("\\", "/").lower()
    return any(s.lower() in rel for s in FORBIDDEN_PATHS) or any(part.startswith("truth") for part in rel.split("/")[:-1])


def content_hits(p: Path) -> list[str]:
    """Answer phrases found in a text file (binary files such as parquet are not scanned)."""
    if p.suffix.lower() in (".parquet", ".gz", ".npz", ".npy", ".png", ".pdf", ".zip", ".whl", ".pyc"):
        return []
    try:
        text = p.read_text(encoding="utf-8").lower()
    except (UnicodeDecodeError, OSError):
        return []
    return [pat for pat in CONTENT_PATTERNS if pat in text]


def check_files(paths: list[Path]) -> list[str]:
    """Problems that forbid syncing these files into the clean room (path rules, then content rules)."""
    problems = []
    for p in paths:
        p = Path(p).resolve()
        try:
            rel = p.relative_to(ROOT).as_posix()
        except ValueError:
            rel = p.as_posix()
        if path_violation(rel):
            problems.append(f"{rel}: forbidden path")
        elif rel not in ALLOWED_CONTENT_HITS and (hits := content_hits(p)):
            problems.append(f"{rel}: answer phrases {hits}")
    return problems


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
    ap.add_argument("--check", nargs="+", type=Path, default=None, help="only check these files before a manual sync; build nothing")
    args = ap.parse_args(argv)
    if args.check:
        problems = check_files(args.check)
        print("\n".join(problems) if problems else f"ok: {len(args.check)} file(s) may be synced")
        return 1 if problems else 0
    m = build(args.dest, args.fresh)
    print(f"clean room at {args.dest}: {m['n_files']} files; forbidden path hits: {m['forbidden_path_hits']}; "
          f"forbidden content hits: {sorted(m['forbidden_content_hits'])}")
    return 0 if not (m["forbidden_path_hits"] or m["forbidden_content_hits"]) else 1


if __name__ == "__main__":
    sys.exit(main())
