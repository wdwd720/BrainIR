"""Stage the fitted models of an earlier Level B round into a new round's run directory (orchestrator helper; PROTOCOL.md section 9).

    uv run --project phase3 --no-sync python scripts/p3/stage_round_fits.py --method lin_subspace --from r2_lin_subspace --to r3v3_lin_subspace
        [--from r1_lin ...]

Benchmark version 3 changed the EVALUATION only: a fit depends on the public training data, the method code, the configuration, the
seed, the simulation budget and the time limit, never on the evaluator. When the method's code is unchanged (checked here: every
file of the earlier round's methods snapshot must equal the current clean-room file), re-running the round under version 3 may reuse
the earlier fits. The tournament driver skips a fit whose .pkl and .json exist in the round directory, so staging them makes the new
round an evaluation-only re-run. Fits that failed earlier are NOT staged (they are attempted again). Files are hard-linked (copied
if linking fails). Several --from rounds are searched in order (a later one only fills what the earlier ones lack). Writes a staging
record next to the fits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

RUN = Path(r"C:\Dev\BrainIR_p3run")
ROOM = Path(r"C:\Dev\BrainIR_p3clean")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_unchanged(src_round: Path, room: Path = ROOM) -> list[str]:
    """Files of the round's methods snapshot that differ from (or are missing in) the room's methods package."""
    snap = src_round / "methods"
    cur = room / "src" / "brainir_state" / "methods"
    bad = []
    for p in sorted(snap.rglob("*.py")):
        q = cur / p.relative_to(snap)
        if not q.exists() or _sha(p) != _sha(q):
            bad.append(p.relative_to(snap).as_posix())
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True)
    ap.add_argument("--from", dest="src", action="append", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--room", default=str(ROOM))
    args = ap.parse_args(argv)
    dst_root = RUN / args.to / args.method
    rec = {"method": args.method, "to": args.to, "from": args.src, "staged": {}, "skipped_failed": [], "code_check": {}}
    for src in args.src:
        src_round = RUN / src
        bad = code_unchanged(src_round, Path(args.room))
        rec["code_check"][src] = bad
        if bad:
            raise SystemExit(f"{src}: method code changed since that round ({bad[:5]}); refit instead")
        for sub in ("indep", "shared", "loio"):
            d = src_round / args.method / sub
            if not d.exists():
                continue
            for pkl in sorted(d.glob("*.pkl")):
                js = pkl.with_suffix(".json")
                out = dst_root / sub / pkl.name
                if out.exists():
                    continue
                if not js.exists():
                    rec["skipped_failed"].append(f"{src}/{sub}/{pkl.name}")
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                for a, b in ((pkl, out), (js, out.with_suffix(".json"))):
                    try:
                        os.link(a, b)
                    except OSError:
                        shutil.copy2(a, b)
                rec["staged"][f"{sub}/{pkl.name}"] = src
    dst_root.mkdir(parents=True, exist_ok=True)
    (dst_root / "STAGED_FITS.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.method}: staged {len(rec['staged'])} fits into {args.to} (skipped {len(rec['skipped_failed'])} without a record)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
