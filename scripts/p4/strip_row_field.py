"""Drop one engine-bookkeeping field from the dataset rows of the built REAL sets (ORCHESTRATOR SIDE; LOG P4-D26).

    uv run --no-sync --project phase4 python scripts/p4/strip_row_field.py [--field simulator] [--dry-run]

Why: the real engine's rows carried `info.simulator`, the model identifier of the engine, which names the source of the real systems.
The room builder refuses such rows, so `suites.PUBLIC_INFO_KEYS` no longer lists the field (new builds never write it) and this
script removes it from the sets that were built before the change: the local public real data, its copy on the fit volume and the
Level B sets on the eval volume. Only `index.jsonl` changes (each row re-serialised exactly as `SetWriter` writes it, without the
field); trajectories, manifests, pools and lift cases are untouched. Old and new sha256 of every rewritten file are appended to
research/phase4/REAL_DATA_BUILD.json.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase4" / "src"))

from brainir_causal import suites as SU  # noqa: E402
from brainir_causal.p4modal.remote import VOLUME_NAMES  # noqa: E402

REAL_RECORD = ROOT / "research" / "phase4" / "REAL_DATA_BUILD.json"
LOCAL_PUBLIC = ROOT / "data" / "phase4" / "real" / "real_public" / "public"
#: (volume, volume-relative directory holding one <system>/index.jsonl per real system)
REMOTE_SETS = (("fit", "data/real/real_public/public"), ("eval", "data/real/real_levelb/eval"))


def strip_rows(text: str, field: str) -> tuple[str, int]:
    """(rewritten index text, number of rows that carried the field)."""
    out, n = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        info = row.get("info")
        if isinstance(info, dict) and field in info:
            del info[field]
            n += 1
        out.append(json.dumps(row, sort_keys=True) + "\n")
    return "".join(out), n


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--field", default="simulator")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.field in SU.PUBLIC_INFO_KEYS:
        raise SystemExit(f"refusing: {args.field!r} is still a public info key (suites.PUBLIC_INFO_KEYS)")
    rec = {"what": f"strip info.{args.field} from built real sets (LOG P4-D26)", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "dry_run": bool(args.dry_run), "files": {}}
    # local public real data
    for idx in sorted(LOCAL_PUBLIC.glob("*/index.jsonl")):
        old = idx.read_bytes()
        new_text, n = strip_rows(old.decode("utf-8"), args.field)
        new = new_text.encode("utf-8")
        rec["files"][f"local:{idx.relative_to(ROOT).as_posix()}"] = {"rows_with_field": n, "sha256_old": _sha(old), "sha256_new": _sha(new)}
        if n and not args.dry_run:
            idx.write_bytes(new)
    # remote volumes
    import modal
    for vol_key, base in REMOTE_SETS:
        vol = modal.Volume.from_name(VOLUME_NAMES[vol_key])
        systems = sorted({Path(e.path).name for e in vol.listdir(f"/{base}")})
        updates = {}
        for s in systems:
            path = f"/{base}/{s}/index.jsonl"
            buf = io.BytesIO()
            try:
                vol.read_file_into_fileobj(path, buf)
            except Exception as e:  # noqa: BLE001 - a system directory without an index is recorded, not fatal
                rec["files"][f"{vol_key}:{path}"] = {"error": type(e).__name__}
                continue
            old = buf.getvalue()
            new_text, n = strip_rows(old.decode("utf-8"), args.field)
            new = new_text.encode("utf-8")
            rec["files"][f"{vol_key}:{path}"] = {"rows_with_field": n, "sha256_old": _sha(old), "sha256_new": _sha(new)}
            if n:
                updates[path] = new
        if updates and not args.dry_run:
            with vol.batch_upload(force=True) as b:
                for path, data in updates.items():
                    b.put_file(io.BytesIO(data), path)
            for path, data in updates.items():                    # read back
                buf = io.BytesIO()
                vol.read_file_into_fileobj(path, buf)
                if _sha(buf.getvalue()) != _sha(data):
                    raise SystemExit(f"read-back mismatch on {vol_key}:{path}")
    rec["totals"] = {"files": len(rec["files"]), "rows_with_field": sum(v.get("rows_with_field", 0) for v in rec["files"].values()),
                     "errors": sorted(k for k, v in rec["files"].items() if "error" in v)}
    if not args.dry_run:
        runs = json.loads(REAL_RECORD.read_text(encoding="utf-8"))["runs"] if REAL_RECORD.exists() else []
        runs.append(rec)
        REAL_RECORD.write_text(json.dumps({"runs": runs}, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec["totals"], indent=1))
    return 0 if not rec["totals"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
