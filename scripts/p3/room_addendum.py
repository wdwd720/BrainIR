"""Add one reviewed file to a Phase 3 room after it was built (orchestrator; goal4 section 4: everything entering has path, source,
reason, hash and leakage class).

    uv run --project phase3 python scripts/p3/room_addendum.py --src <file> --dest notes/_tournament_feedback.md --reason "..." \
        --leakage-class aggregate-feedback [--room C:\\Dev\\BrainIR_p3clean]

The destination must lie in a work area of the room (the frozen builder's --check does not flag work areas). The file's content is
scanned with the builder's forbidden-name and forbidden-content classes before it is copied. The record is appended to
research/phase3/CLEANROOM_ADDENDA.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import make_phase3_cleanroom as MK  # noqa: E402

ADDENDA = ROOT / "research" / "phase3" / "CLEANROOM_ADDENDA.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--leakage-class", required=True)
    ap.add_argument("--room", default=str(MK.CLEAN))
    args = ap.parse_args(argv)
    src, room = Path(args.src), Path(args.room)
    dest = args.dest.replace("\\", "/")
    if not any(dest.startswith(w) for w in MK.WORK_AREAS):
        raise SystemExit(f"destination must be inside a work area {MK.WORK_AREAS}")
    if MK.FORBIDDEN_NAMES.search(dest):
        raise SystemExit("forbidden destination name")
    text = src.read_text(encoding="utf-8", errors="ignore")
    m = MK.FORBIDDEN_CONTENT.search(text)
    if m:
        raise SystemExit(f"forbidden content in the source file: {m.group(0)!r}")
    out = room / dest
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out)
    rec = {"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "room": "$EXTERNAL/" + room.name, "path": dest,
           "source": "$REPO/" + src.resolve().relative_to(ROOT).as_posix() if src.resolve().is_relative_to(ROOT) else "generated",
           "reason": args.reason, "sha256": hashlib.sha256(out.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
           "leakage_class": args.leakage_class}
    items = json.loads(ADDENDA.read_text(encoding="utf-8")) if ADDENDA.exists() else []
    items.append(rec)
    ADDENDA.write_text(json.dumps(items, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
