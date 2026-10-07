"""Seed the remote runner's dev-data volume SERVER-SIDE from the fit volume (ORCHESTRATOR SIDE; isolation tooling, not part of the
benchmark lock).

    uv run --no-sync --project phase4 python scripts/p4/devdata_seed.py [--volume brainir-p4-devdata]

The remote runner's volume must be an exact copy of the clean room's data/ directory (`devrun4.py sync-data` verifies every file by
sha256 and uploads what differs). The big parts of data/ (the dev tier's public part, about 13.6 GB, and the public real data, about
2.3 GB) already exist on the fit volume, where the builds wrote them; uploading them again over the development machine's uplink
would take hours. This script copies them inside Modal (fit volume mounted READ-ONLY, dev-data volume read-write) into the room's
layout (data/synthetic_dev/<system>/..., data/real_public/<system>/...), deletes anything else under those two directories, and
commits. Run `devrun4.py sync-data --room <clean room>` afterwards: it hashes the room's data/, compares with the volume, uploads the
small remaining files (records, tolerances, targets) and fails on any mismatch, so a wrong seed can never go unnoticed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

MAP = (("/fitvol/data/suites/dev/public", "synthetic_dev"), ("/fitvol/data/real/real_public/public", "real_public"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", default="brainir-p4-devdata")
    ap.add_argument("--fit-volume", default="brainir-p4-fit")
    args = ap.parse_args(argv)
    if args.volume.startswith("brainir-p3") or not args.volume.startswith("brainir-p4-devdata"):
        raise SystemExit(f"refusing volume {args.volume!r}: only brainir-p4-devdata* volumes")
    import modal
    app = modal.App("brainir-p4-devdata-seed")
    fit = modal.Volume.from_name(args.fit_volume).read_only()
    dev = modal.Volume.from_name(args.volume, create_if_missing=True)
    vol_name = args.volume

    def seed(mapping: list) -> dict:
        import shutil
        from pathlib import Path
        out = {}
        for src, dst in mapping:
            s, d = Path(src), Path("/devdata") / dst
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d)
            files = [p for p in d.rglob("*") if p.is_file()]
            out[dst] = {"files": len(files), "bytes": int(sum(p.stat().st_size for p in files))}
        import modal as M
        M.Volume.from_name(vol_name).commit()
        return out

    fn = app.function(cpu=4.0, memory=8192, timeout=3 * 3600, volumes={"/fitvol": fit, "/devdata": dev}, serialized=True,
                      name="devdata_seed", image=modal.Image.debian_slim(python_version="3.12"))(seed)
    t0 = time.time()
    with app.run():
        res = fn.remote([list(m) for m in MAP])
    print(json.dumps({"seeded": res, "wall_s": round(time.time() - t0, 1),
                      "next": "devrun4.py sync-data --room <clean room> (verifies every file, uploads the rest)"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
