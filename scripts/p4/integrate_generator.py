"""Integrate a generator delivery from the benchmark author's room into the benchmark (ORCHESTRATOR SIDE; CRITICAL_PATH_PLAN N2).

    uv run --no-sync --project phase4 python scripts/p4/integrate_generator.py [--room C:\\Dev\\BrainIR_p4bench]      # dry run: diff
    uv run --no-sync --project phase4 python scripts/p4/integrate_generator.py --apply                              # replace + hashes
    uv run --no-sync --project phase4 python scripts/p4/integrate_generator.py --check                              # copy == hashes

The delivery is the generator layout of the author's room (research/phase4/contracts/SYNTHETIC_BENCHMARK_CONTRACT.md): the files
SYNTHETIC_BENCHMARK.md, calibration_report.json, timings_accuracy.json and the directories ref/, scripts/, src/p4synth/, tests/
(caches excluded). The dry run lists added / removed / changed files against benchmarks/causal_state_v1/generator/ and refuses a
delivery with a symbolic link, a file above 20 MB, an absolute host path in a text file or a file outside the layout. --apply
replaces the copy (files absent from the delivery are removed) and rewrites research/phase4/GENERATOR_DELIVERY_SHA256.txt
(`<sha256> *./<path>`, raw bytes, sorted). --check verifies the copy against that record. The generator's tests then run on Modal
(`modal_pytest.py --suite generator`), the adapter tests locally, and the tiers are rebuilt (`build_on_modal.py synthetic`).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "benchmarks" / "causal_state_v1" / "generator"
RECORD = ROOT / "research" / "phase4" / "GENERATOR_DELIVERY_SHA256.txt"
ROOM = Path(r"C:\Dev\BrainIR_p4bench")
TOP_FILES = ("SYNTHETIC_BENCHMARK.md", "calibration_report.json", "timings_accuracy.json")
TOP_DIRS = ("ref", "scripts", "src/p4synth", "tests")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".csv"}
ABS_PATH = re.compile(r"(?i)(?<![A-Za-z])[a-z]:[\\/](?:dev|users|windows)\b|/c/dev/|/home/[a-z]|/users/[a-z]")
MAX_BYTES = 20 * 1024 * 1024


def delivery(base: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for f in TOP_FILES:
        p = base / f
        if p.is_file():
            out[f] = p
    for d in TOP_DIRS:
        root = base / d
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if any(part in SKIP_PARTS for part in p.relative_to(base).parts) or p.suffix == ".pyc":
                continue
            if p.is_symlink():
                raise SystemExit(f"refusing: symbolic link in the delivery: {p.relative_to(base)}")
            if p.is_file():
                out[p.relative_to(base).as_posix()] = p
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def problems(files: dict[str, Path]) -> list[str]:
    bad = []
    for rel, p in files.items():
        if p.stat().st_size > MAX_BYTES:
            bad.append(f"{rel}: {p.stat().st_size} bytes (> 20 MB)")
        if p.suffix in TEXT:
            text = p.read_text(encoding="utf-8", errors="replace")
            m = ABS_PATH.search(text)
            if m:
                bad.append(f"{rel}: absolute host path {m.group(0)!r}")
    return bad


def record_text(files: dict[str, Path]) -> str:
    return "".join(f"{sha(files[rel])} *./{rel}\n" for rel in sorted(files))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", type=Path, default=ROOM)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        want = RECORD.read_text(encoding="utf-8")
        have = record_text(delivery(DEST))
        if want != have:
            w, h = set(want.splitlines()), set(have.splitlines())
            print("GENERATOR COPY DIFFERS FROM ITS RECORD:", {"missing_or_changed": sorted(w - h)[:20], "unrecorded": sorted(h - w)[:20]})
            return 1
        print(f"generator copy matches {RECORD.relative_to(ROOT)} ({len(want.splitlines())} files)")
        return 0
    new = delivery(args.room)
    if not any(r.startswith("src/p4synth/") for r in new):
        raise SystemExit(f"no src/p4synth in {args.room}")
    old = delivery(DEST)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(r for r in set(new) & set(old) if sha(new[r]) != sha(old[r]))
    print(f"delivery {args.room}: {len(new)} files; added {len(added)}, removed {len(removed)}, changed {len(changed)}")
    for tag, lst in (("+", added), ("-", removed), ("~", changed)):
        for r in lst:
            print(f"  {tag} {r}")
    bad = problems(new)
    if bad:
        print("REFUSED:", *bad, sep="\n  ")
        return 2
    if not args.apply:
        print("dry run (no change); --apply replaces the copy and rewrites the delivery record")
        return 0
    stage = DEST.with_name(DEST.name + ".incoming")
    if stage.exists():
        shutil.rmtree(stage)
    for rel, p in new.items():
        q = stage / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
    if record_text(delivery(stage)) != record_text(new):
        raise SystemExit("staged copy differs from the delivery (copy error)")
    backup = DEST.with_name(DEST.name + ".previous")
    if backup.exists():
        shutil.rmtree(backup)
    DEST.rename(backup)
    stage.rename(DEST)
    shutil.rmtree(backup)
    RECORD.write_text(record_text(delivery(DEST)), encoding="utf-8", newline="\n")
    print(f"replaced {DEST.relative_to(ROOT)}; wrote {RECORD.relative_to(ROOT)} ({len(new)} files)")
    print("next: modal_pytest.py --suite generator; pytest phase4 adapter tests; build_on_modal.py synthetic --tier dev / val")
    return 0


if __name__ == "__main__":
    sys.exit(main())
