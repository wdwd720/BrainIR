"""Download CACHED outputs from the Phase 4 Modal volumes WITHOUT starting any Modal container (ORCHESTRATOR SIDE; the user's
directive of 2026-09-28: no further Modal spend; research/phase4/LOCAL_EXECUTION_PLAN.md). Uses the client's direct volume reads
(`Volume.listdir` / `read_file_into_fileobj`), which run no function, so no compute is billed. Files already present locally with the
same size are skipped (resume), so an interrupted fetch just runs again.

    uv run --no-sync --project phase4 python scripts/p4/fetch_cached_volume.py --volume eval --remote data/real/real_levelb \
        --local C:/Dev/BrainIR_p4run/vol/eval/data/real/real_levelb
    ... --volume eval --remote store/index_shards --local C:/Dev/BrainIR_p4run/vol/eval/store/index_shards
    ... --volume eval --keys-from <file of store keys> --remote store/rec --local C:/Dev/BrainIR_p4run/vol/eval/store/rec

Writes <local>/.fetch_record.json (files, bytes, skipped, wall)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

VOLUMES = {"fit": "brainir-p4-fit", "eval": "brainir-p4-eval", "store": "brainir-p4-store"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", required=True, choices=sorted(VOLUMES))
    ap.add_argument("--remote", required=True, help="directory on the volume (or the rec root with --keys-from)")
    ap.add_argument("--local", required=True)
    ap.add_argument("--keys-from", default="", help="a file of store keys: fetch <remote>/<key[:2]>/<key>.npz for each")
    ap.add_argument("--threads", type=int, default=8, help="concurrent file reads")
    args = ap.parse_args(argv)
    import modal
    vol = modal.Volume.from_name(VOLUMES[args.volume])
    local = Path(args.local)
    local.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    todo: list[tuple[str, int | None]] = []
    if args.keys_from:
        for k in Path(args.keys_from).read_text(encoding="utf-8").split():
            todo.append((f"{args.remote.strip('/')}/{k[:2]}/{k}.npz", None))
    else:
        for e in vol.listdir(args.remote.strip("/"), recursive=True):
            if e.type == modal.volume.FileEntryType.FILE:
                todo.append((e.path, int(e.size)))
    import threading
    from concurrent.futures import ThreadPoolExecutor
    st = {"n": 0, "skipped": 0, "bytes": 0, "missing": 0}
    lock = threading.Lock()
    base = args.remote.strip("/")

    def one(item):
        path, size = item
        rel = path[len(base):].lstrip("/") if path.startswith(base) else path
        dst = local / rel
        if dst.exists() and (size is None or dst.stat().st_size == size):
            with lock:
                st["skipped"] += 1
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + f".{threading.get_ident()}.part")
        try:
            with open(tmp, "wb") as fh:
                vol.read_file_into_fileobj(path, fh)
        except Exception as e:  # noqa: BLE001 - a key that is not on the volume
            tmp.unlink(missing_ok=True)
            with lock:
                st["missing"] += 1
                if st["missing"] <= 5:
                    print(f"missing {path}: {type(e).__name__}", flush=True)
            return
        tmp.replace(dst)
        with lock:
            st["n"] += 1
            st["bytes"] += dst.stat().st_size
            if st["n"] % 200 == 0:
                print(f"  {st['n']} files, {st['bytes'] / 1e6:.0f} MB, {time.time() - t0:.0f} s", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, int(args.threads))) as ex:
        list(ex.map(one, todo))
    n, skipped, nbytes, missing = st["n"], st["skipped"], st["bytes"], st["missing"]
    rec = {"volume": VOLUMES[args.volume], "remote": args.remote, "files": n, "bytes": nbytes, "skipped_present": skipped,
           "missing": missing, "wall_s": round(time.time() - t0, 1), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (local / ".fetch_record.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec), flush=True)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
