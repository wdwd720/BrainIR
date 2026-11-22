"""Run a subset of a packed campaign's jobs on Modal (LOG L136): operations only, no analysis.

The subset (chunks of the full pack, or of fl-1's re-packed failed jobs) is placed in the campaign folder as a pack of its own, then
`modal4.py run` loads it (trust gate, spend cap and estimate checked there) and the full local pack is restored as soon as the jobs are
loaded, so the GitHub collector only ever sees the full manifest. Results go to MODAL_<campaign>/results.pkl, merged by key with the
GitHub results by `gha4.load_results` (digests must agree where both exist).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/modal_subset_v4.py CAMPAIGN packed A-B [--fl1-run RUN_ID]
    uv run --project ledger --no-sync python ledger/scripts/posthoc/modal_subset_v4.py fl-1-run4 fl1-repacked A-B --fl1-run RUN_ID
"""

from __future__ import annotations

import hashlib
import json
import pickle
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fl1_subset_v4 as P  # noqa: E402  (backups, fl-1's re-packed plan)

REPO, GHA, LOGS = P.REPO, P.GHA, P.LOGS


def main() -> None:
    name, kind, rng = sys.argv[1], sys.argv[2], sys.argv[3]
    a, b = (int(x) for x in rng.split("-"))
    if kind == "packed":
        chunks = P.packed_chunks(name)[a:b + 1]
    elif kind == "fl1-repacked":
        chunks = P.fl1_plan(sys.argv[sys.argv.index("--fl1-run") + 1])[1][a:b + 1]
    else:
        raise SystemExit(__doc__)
    bk = P.backup(name)
    full = json.loads((bk / "manifest.json").read_text())
    d = GHA / name
    items = [x for ch in chunks for x in ch]
    for f in d.glob("chunk_*.pkl"):
        f.unlink()
    files = {}
    for k, ch in enumerate(chunks):
        p = d / f"chunk_{k}.pkl"
        p.write_bytes(pickle.dumps(ch, protocol=pickle.HIGHEST_PROTOCOL))
        files[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    pkeys = sorted({k for k, _ in items})
    for pk in pkeys:
        files[f"payload_{pk}.bin"] = full["files"][f"payload_{pk}.bin"]
    keys = sorted(j["key"] for _, j in items)
    man = {**{k: full[k] for k in ("campaign", "area")}, "n_jobs": len(items), "n_chunks": len(chunks), "payload_keys": pkeys,
           "files": files, "keys": keys, "keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest(),
           "part_of": {"kind": kind, "range": [a, b], "full_keys_sha256": full["keys_sha256"]}}
    (d / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    log = LOGS / f"modal_subset_{name}_{kind}_{a}-{b}.log"
    with open(log, "w") as fh:
        proc = subprocess.Popen(["uv", "run", "--project", "ledger", "--no-sync", "python", "ledger/scripts/modal4.py", "run", name,
                                 "--s-per-job", "120", "--max-containers", "100"], cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        while "jobs_to_run" not in log.read_text() and proc.poll() is None and time.time() - t0 < 1800:
            time.sleep(5)
    finally:
        for f in d.glob("chunk_*.pkl"):
            f.unlink()
        for f in bk.iterdir():
            shutil.copy(f, d / f.name)
    ok = (d / "manifest.json").read_text() == (bk / "manifest.json").read_text()
    P.log(f"MODAL subset {name} {kind} {a}-{b}: {len(items)} jobs loaded; full local pack restored: {ok}", "collect_all.log")
    rc = proc.wait()
    tail = [x for x in log.read_text().splitlines() if x.startswith("{")][-1:]
    P.log(f"MODAL subset {name} {kind} {a}-{b} done (exit {rc}): {tail[0] if tail else 'no summary'}", "collect_all.log")


if __name__ == "__main__":
    main()
