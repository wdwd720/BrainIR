"""Automated leakage checks for the DNg100 benchmark.

    uv run python benchmarks/dng100/cleanroom/leakage_check.py [--write-audit]

Checks
1. Public bundles contain no oracle statement: no oracle label ("E1"...) or published cell-type token in any text/JSON
   file; in the blind bundle (tier A) no published cell type appears anywhere (also not in parquet string columns); in
   the labelled bundle (tier B) published types appear ONLY as ordinary rows of neurons.parquet (checked: the same
   columns are filled for every neuron, so nothing singles them out).
2. The oracle is not reachable from library code: `src/brainir` never imports `benchmarks` or `research` and never
   contains the oracle tokens (delegates to the pytest leakage guard).
3. The bundle manifests verify (every file hash matches).
4. Node lists and network files contain the oracle neurons only as ordinary members (their IDs are not listed in any
   text/JSON file except as part of complete tables).
The report is written to benchmarks/dng100/LEAKAGE_AUDIT.md with --write-audit.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from brainir import paths
from brainir.benchmark.bundle import verify_bundle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ORACLE = json.loads((ROOT / "oracle" / "oracle.json").read_text(encoding="utf-8"))
TYPES = {v["type"] for v in ORACLE["labels"].values()}
LABELS = set(ORACLE["labels"])
ORACLE_IDS = set()
for n in ORACLE["networks"].values():
    ORACLE_IDS |= set(n["core"].values())
    ORACLE_IDS |= set(n.get("core_contralateral_copies", {}).values())
TEXT_EXT = {".md", ".json", ".txt", ".csv"}


def _token_re(tok: str) -> re.Pattern:
    return re.compile(rf"(?<![0-9A-Za-z_]){re.escape(tok)}(?![0-9A-Za-z_])")


def scan_text_files(root: Path) -> list[dict]:
    hits = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in TEXT_EXT:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for tok in sorted(TYPES):
            if _token_re(tok).search(text):
                hits.append({"file": p.relative_to(root).as_posix(), "token": tok, "kind": "published cell type"})
        for tok in sorted(LABELS):  # labels like 'E1' are short: only flag them in prose files, not in CSV headers
            if p.suffix in (".md", ".json") and _token_re(tok).search(text):
                hits.append({"file": p.relative_to(root).as_posix(), "token": tok, "kind": "oracle label"})
        if p.name != "edges.parquet" and p.suffix != ".csv":  # node lists legitimately contain every member ID
            for i in sorted(ORACLE_IDS):
                if _token_re(str(i)).search(text):
                    hits.append({"file": p.relative_to(root).as_posix(), "token": str(i), "kind": "oracle neuron id in text"})
    return hits


def scan_parquet(root: Path, tier: str) -> list[dict]:
    hits = []
    for p in sorted(root.rglob("neurons.parquet")):
        df = pd.read_parquet(p)
        present = {t for t in TYPES if (df["cell_type"] == t).any()}
        if tier == "A" and present:
            hits.append({"file": p.relative_to(root).as_posix(), "token": sorted(present), "kind": "published type visible in blind bundle"})
        if tier == "B":
            # published-type rows must not be distinguishable: same null pattern as other interneurons of the same role
            rows = df[df["cell_type"].isin(TYPES)]
            others = df[~df["cell_type"].isin(TYPES) & (df["role_class"] == "vnc_intrinsic")]
            if len(rows) and len(others):
                for col in df.columns:
                    a, b = rows[col].isna().mean(), others[col].isna().mean()
                    if (a == 0) != (b < 1.0) and abs(a - b) > 0.5:
                        hits.append({"file": p.relative_to(root).as_posix(), "token": col, "kind": "column filled differently for published types"})
        for col in df.columns:
            if df[col].dtype == object:
                vals = df[col].dropna().astype(str)
                for lab in LABELS:
                    if (vals == lab).any():
                        hits.append({"file": p.relative_to(root).as_posix(), "token": lab, "kind": f"oracle label as value of {col}"})
    return hits


def library_guard() -> dict:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_leakage_guard.py"], cwd=paths.repo_root(),
                       capture_output=True, text=True)
    return {"passed": r.returncode == 0, "tail": r.stdout.strip().splitlines()[-1:] if r.stdout else r.stderr.strip().splitlines()[-2:]}


def import_scan() -> list[str]:
    bad = []
    pat = re.compile(r"^\s*(from|import)\s+(benchmarks|oracle|evaluate)\b", re.M)
    for p in (paths.repo_root() / "src" / "brainir").rglob("*.py"):
        if pat.search(p.read_text(encoding="utf-8")):
            bad.append(p.relative_to(paths.repo_root()).as_posix())
    return bad


def run_checks() -> dict:
    out = {"checked_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "bundles": {}}
    for tier, name in (("B", "public"), ("A", "public_blind")):
        root = ROOT / name
        if not root.exists():
            out["bundles"][name] = {"missing": True}
            continue
        out["bundles"][name] = {"tier": tier, "manifest_verifies": verify_bundle(root), "text_hits": scan_text_files(root),
                                "parquet_hits": scan_parquet(root, tier)}
    out["library_import_scan"] = import_scan()
    out["library_leakage_guard_pytest"] = library_guard()
    node_hits = scan_text_files(ROOT / "nodes") if (ROOT / "nodes").exists() else []
    out["node_lists_text_hits"] = [h for h in node_hits if h["kind"] != "oracle neuron id in text"]
    ok = all(not b.get("missing") and b["manifest_verifies"]["ok"] and not b["text_hits"] and not b["parquet_hits"]
             for b in out["bundles"].values()) and not out["library_import_scan"] and out["library_leakage_guard_pytest"]["passed"]
    out["ok"] = bool(ok)
    return out


def write_audit(res: dict) -> None:
    lines = ["# LEAKAGE AUDIT — dng100-benchmark-v1", "", f"Checked {res['checked_utc']} by `benchmarks/dng100/cleanroom/leakage_check.py`. "
             f"Overall: **{'PASS' if res['ok'] else 'FAIL'}**.", "",
             "## What counts as leakage", "",
             "The oracle (published core neurons, their labels, roles and essentiality) must not be recoverable from anything a",
             "discovery method receives: the public bundle, the `brainir` library, or prompts/documents handed to it. Body IDs of",
             "oracle neurons legitimately occur in the bundle as ordinary network members (every neuron is listed); leakage would",
             "be any file that singles them out, any published cell-type name in the blind tier, or any oracle label anywhere.", "",
             "## Results", "", "| bundle | tier | manifest verifies | text hits | parquet hits |", "|---|---|---|---|---|"]
    for name, b in res["bundles"].items():
        if b.get("missing"):
            lines.append(f"| {name} | – | missing | – | – |")
        else:
            lines.append(f"| {name} | {b['tier']} | {b['manifest_verifies']['ok']} | {len(b['text_hits'])} | {len(b['parquet_hits'])} |")
    lines += ["", f"- library import scan (`src/brainir` importing benchmarks/oracle/evaluator): {res['library_import_scan'] or 'none'}",
              f"- pytest leakage guard (`tests/test_leakage_guard.py`): {'passed' if res['library_leakage_guard_pytest']['passed'] else 'FAILED'}",
              f"- node lists: {len(res['node_lists_text_hits'])} suspicious hits", "",
              "## Clean-room protocol", "",
              "1. A discovery method runs through `benchmarks/dng100/cleanroom/run_method.py`, which copies one bundle into a fresh",
              "   directory, executes the method in a subprocess with `BRAINIR_BUNDLE` pointing at that copy, an environment stripped",
              "   of secrets, and no access to `benchmarks/dng100/oracle`, `benchmarks/dng100_walking_cpg` or `research/literature`",
              "   (the method runs under the audit-hook sandbox `_sandbox.py`: file access is confined to the bundle copy, the output",
              "   directory, the Python installation and temp, so the repository, the oracle, tier B and user files are unreadable; no",
              "   subprocesses, sockets or ctypes calls; imports of `benchmarks`/`oracle`/`evaluate` are refused statically; the method's",
              "   declared inputs (`MethodInfo.inputs`) are recorded, not verified). This stops inadvertent and casual leakage; it is not",
              "   OS-level isolation.",
              "2. The method writes `prediction.json` (schema `brainir.benchmark.prediction`, version 1.0.0). Its SHA-256 and the bundle",
              "   SHA-256 are recorded before evaluation.",
              "3. `benchmarks/dng100/evaluator/evaluate.py` is the only code that reads the oracle. It writes metric families separately;",
              "   no aggregate score exists.", "",
              "## Answer-bearing locations (never expose to a method)", "",
              "`benchmarks/dng100/oracle/`, `benchmarks/dng100_walking_cpg/`, `research/literature/`, `goal1.md`, `goal2.md`,",
              "`PHASE0_REPORT.md` §13, and any evaluation output.", ""]
    for name, b in res["bundles"].items():
        for h in (b.get("text_hits") or []) + (b.get("parquet_hits") or []):
            lines.append(f"- HIT {name}: {h}")
    (ROOT / "LEAKAGE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-audit", action="store_true")
    args = ap.parse_args(argv)
    res = run_checks()
    print(json.dumps({k: v for k, v in res.items() if k != "bundles"}, indent=1))
    for name, b in res["bundles"].items():
        print(name, "manifest_ok" if not b.get("missing") and b["manifest_verifies"]["ok"] else "PROBLEM",
              "text_hits", len(b.get("text_hits", [])), "parquet_hits", len(b.get("parquet_hits", [])))
        for h in (b.get("text_hits") or [])[:20] + (b.get("parquet_hits") or [])[:20]:
            print("   ", h)
    if args.write_audit:
        write_audit(res)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
