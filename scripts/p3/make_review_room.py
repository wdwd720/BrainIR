"""Build the pre-lock review room for reviews A-E and H (orchestrator; research/phase3/REVIEW_PLAN.md).

    uv run --project phase3 python scripts/p3/make_review_room.py [--src C:\\Dev\\BrainIR_p3clean] [--dest C:\\Dev\\BrainIR_p3review]

The review room is a snapshot of the clean room:
- the public modules, docs and data (data files hard-linked);
- the candidate methods, notes, tests and runs;
- the aggregate tournament feedback;
- an empty reviews/ directory and a reviewer CLAUDE.md.
Nothing else enters. It is scanned with the clean-room builder's forbidden classes. The manifest (every file with its hash) goes to
research/phase3/REVIEW_ROOM_MANIFEST.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import make_phase3_cleanroom as MK  # noqa: E402

REVIEW_CLAUDE_MD = """# Phase 3 pre-lock review room

You review a state-discovery method before it is locked. Your task is in your first message. This room is a snapshot of the method
developers' room:
- src/brainir_state (the public evaluator, the method API and the candidate methods);
- notes/ (the developers' notes);
- docs/ (PROTOCOL.md, the development contract, the methods review);
- data/ (public data);
- notes/_tournament_feedback.md (aggregate held-out results).

Rules:
1. Work only inside this directory; nothing outside it is reachable.
2. Write your review to reviews/<your letter>_review.md.
3. Do not modify src/, notes/, docs/ or data/.
4. Use `uv run` (environment already synced) with at most 3 threads.
5. No web access.
"""

SKIP = (".venv/", "simq/", ".tmp/", ".pytest_cache/")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(MK.CLEAN))
    ap.add_argument("--dest", default=r"C:\Dev\BrainIR_p3review")
    args = ap.parse_args(argv)
    src, dest = Path(args.src), Path(args.dest)
    if dest.exists():
        raise SystemExit(f"{dest} exists")
    files = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        if rel.startswith(SKIP) or "/__pycache__/" in f"/{rel}" or rel == "CLAUDE.md":
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if rel.startswith("data/"):
            os.link(p, out)
        else:
            shutil.copy2(p, out)
        files.append(rel)
    (dest / "CLAUDE.md").write_text(REVIEW_CLAUDE_MD, encoding="utf-8", newline="\n")
    (dest / "reviews").mkdir()
    probs = []
    for rel in files:
        if MK.FORBIDDEN_NAMES.search(rel):
            probs.append(f"forbidden name {rel}")
        p = dest / rel
        if p.suffix in MK.TEXT_SUFFIXES and p.stat().st_size < 20_000_000:
            m = MK.FORBIDDEN_CONTENT.search(p.read_text(encoding="utf-8", errors="ignore"))
            if m:
                probs.append(f"forbidden content {m.group(0)!r} in {rel}")
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "room": "$EXTERNAL/" + dest.name,
           "source_room": "$EXTERNAL/" + src.name, "n_files": len(files), "scan_problems": probs,
           "files": {rel: hashlib.sha256((dest / rel).read_bytes()).hexdigest() for rel in files if not rel.startswith("data/")},
           "data_files": sum(1 for rel in files if rel.startswith("data/"))}
    (ROOT / "research" / "phase3" / "REVIEW_ROOM_MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    if probs:
        raise SystemExit(f"scan problems: {probs[:5]}")
    print(f"built {dest}: {len(files)} files; scan clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
