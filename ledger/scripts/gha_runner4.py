"""Runner side of a run 4 GitHub Actions campaign: a copy of run 3's `gha_runner3.py` whose only change is the job entry point,
run 4's `jobs_v4.run_job` (kinds group_v4 / sweep_v4; every other kind is passed unchanged to run 3's, run 2's and run 1's entry
points). Executed on a hosted runner by `.github/workflows/ledger-gha4.yml` (tags gha4-*; PREREG v4 X1).

Input folder (downloaded from the campaign's `ledgerdata-*` release): `manifest.json`, `payload_<key>.bin` (zlib-pickled shared
payloads exactly as run 1 packed them, `brainir.compute.backend.pack_shared`), `chunk_<i>.pkl` (a list of
`(payload_key, job)` pairs; jobs carry `Shared` markers instead of matrices). The runner checks every file's SHA-256 against the
manifest and every payload's content key, then runs `brainir_ledger.jobs_v4.run_job` for each job in a fresh forked process (one
process per job, like run 1's batches), and writes the results as one pickle. It prints progress counts only, never a result.

    python ledger/scripts/gha_runner4.py run --data DIR --chunk I --out res.pkl [--workers 4]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import pickle
import sys
import time
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir.compute.backend import resolve_shared  # noqa: E402
from brainir_ledger.jobs import probe  # noqa: E402
from brainir_ledger.jobs_v4 import run_job  # noqa: E402  (run 4's kinds; everything else via run 3's, 2's and 1's entry points)

_PAYLOADS: dict[str, dict] = {}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _one(item):
    pkey, job = item
    return run_job(resolve_shared(job, _PAYLOADS[pkey]))


def run(data: Path, chunk: int, out: Path, workers: int) -> None:
    man = json.loads((data / "manifest.json").read_text())
    files = man["files"]
    cname = f"chunk_{chunk}.pkl"
    for name in [cname] + [f"payload_{k}.bin" for k in man["payload_keys"]]:
        if _sha(data / name) != files[name]:
            raise SystemExit(f"hash mismatch: {name}")
    items = pickle.loads((data / cname).read_bytes())
    for pkey in sorted({k for k, _ in items}):
        blob = (data / f"payload_{pkey}.bin").read_bytes()
        if hashlib.sha256(blob).hexdigest()[:32] != pkey:
            raise SystemExit(f"payload content key mismatch: {pkey}")
        _PAYLOADS[pkey] = pickle.loads(zlib.decompress(blob))
    pr = probe({"key": "chunk-probe"})
    print(f"chunk {chunk}: {len(items)} jobs, numerics digest {pr['numerics_digest'][:12]}, workers {workers}", flush=True)
    t0, res = time.time(), []
    with mp.get_context("fork").Pool(processes=workers, maxtasksperchild=1) as pool:
        for i, r in enumerate(pool.imap_unordered(_one, items, chunksize=1), start=1):
            res.append(r)
            if i % 25 == 0 or i == len(items):
                print(f"chunk {chunk}: {i}/{len(items)} done, {sum('error' in x for x in res)} errors, {time.time() - t0:.0f} s", flush=True)
    meta = {"campaign": man["campaign"], "chunk": chunk, "n_jobs": len(items), "n_results": len(res), "probe": pr,
            "wall_s": round(time.time() - t0, 1), "workers": workers}
    out.write_bytes(pickle.dumps({"meta": meta, "results": res}, protocol=pickle.HIGHEST_PROTOCOL))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--data", required=True)
    r.add_argument("--chunk", type=int, required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    run(Path(a.data), a.chunk, Path(a.out), a.workers)


if __name__ == "__main__":
    main()
