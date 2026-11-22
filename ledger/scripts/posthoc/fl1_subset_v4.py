"""Publisher for the rest of run 4's GitHub queue, including the jobs of `fl-1-run4`'s failed chunks as attempt 2 in smaller chunks
(LOG L131-L132): operations only, no analysis.

A re-run of a failed chunk repeats the whole chunk (742 floor-1 jobs, more than 5 h on GitHub, past the 340-minute limit). Instead the
failed chunks' jobs (unchanged specifications and payload) are packed into chunks of at most PER jobs and published as attempt 2 of the
same campaign; collection merges every attempt by job key against the full manifest. The local pack is replaced by the subset only
while publishing and restored right after (and checked).

The queue is published first-fit in priority order: at each poll the first item whose chunks + 1 fit under the 20-job limit is
published, then 90 s pass before jobs are counted again (L119). This is the only publisher while it runs (any feeder is stopped).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/fl1_subset_v4.py RUN_ID ITEM ...   # ITEM: a campaign, or fl-1-subset
"""

from __future__ import annotations

import hashlib
import json
import math
import pickle
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GHA = REPO / "data" / "ledger" / "gha"
LOGS = REPO / "data" / "cache" / "ledger_logs"
NAME = "fl-1-run4"
D = GHA / NAME
BK = REPO / "data" / "cache" / "fl1_full_pack_backup"
MAX_JOBS = 20
PER = 420


def sh(*a: str) -> str:
    return subprocess.run(a, cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def log(msg: str, f: str = "feeder_run4_core2.log") -> None:
    with open(LOGS / f, "a") as fh:
        fh.write(time.strftime("%H:%M:%S") + " " + msg + "\n")


def g4(*a: str) -> str:
    return sh("uv", "run", "--project", "ledger", "--no-sync", "python", "ledger/scripts/gha4.py", *a)


def subset_plan(run1: str) -> tuple[list[int], list[list]]:
    jobs = json.loads(sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run1}/jobs?per_page=100"))["jobs"]
    if not (jobs and all(j["status"] == "completed" for j in jobs)):
        raise SystemExit("attempt 1 not completed")
    failed = sorted(int(j["name"].split("(")[1].rstrip(")")) for j in jobs if j["name"].startswith("run") and j["conclusion"] != "success")
    if not BK.exists():
        shutil.copytree(D, BK)
    items = []
    for i in failed:
        items += pickle.loads((BK / f"chunk_{i}.pkl").read_bytes())
    per = max(PER, math.ceil(len(items) / 15))
    return failed, [items[i:i + per] for i in range(0, len(items), per)]


def publish_subset(run1: str, failed: list[int], chunks: list[list]) -> None:
    full = json.loads((BK / "manifest.json").read_text())
    items = [x for ch in chunks for x in ch]
    for f in D.glob("chunk_*.pkl"):
        f.unlink()
    files = {}
    for k, ch in enumerate(chunks):
        p = D / f"chunk_{k}.pkl"
        p.write_bytes(pickle.dumps(ch, protocol=pickle.HIGHEST_PROTOCOL))
        files[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    for pk in full["payload_keys"]:
        files[f"payload_{pk}.bin"] = full["files"][f"payload_{pk}.bin"]
    keys = sorted(j["key"] for _, j in items)
    man = {"campaign": NAME, "area": full["area"], "n_jobs": len(items), "n_chunks": len(chunks),
           "payload_keys": sorted({k for k, _ in items}), "files": files,
           "keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest(), "keys": keys,
           "git_head": sh("git", "rev-parse", "HEAD"), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "subset_of": {"attempt_1_run": int(run1), "failed_chunks": failed, "full_keys_sha256": full["keys_sha256"]}}
    (D / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    try:
        subprocess.run(["gh", "release", "delete", f"ledgerdata-{NAME}", "--yes"], cwd=REPO, capture_output=True)
        out = g4("publish4", NAME, "--attempt", "2").splitlines()[-1]
    finally:
        for f in D.glob("chunk_*.pkl"):
            f.unlink()
        for f in BK.iterdir():
            shutil.copy(f, D / f.name)
    ok = (D / "manifest.json").read_text() == (BK / "manifest.json").read_text()
    log(f"{out} [FL1 subset: {len(items)} jobs of attempt 1's chunks {failed}; full local pack restored: {ok}]")
    log(f"FL1 subset published ({len(items)} jobs, {len(chunks)} chunks); full local pack restored: {ok}", "collect_all.log")


def main() -> None:
    run1, queue = sys.argv[1], list(sys.argv[2:])
    subprocess.run(["pkill", "-f", "gha4.py feeder"], capture_output=True)
    failed, chunks = subset_plan(run1) if "fl-1-subset" in queue else ([], [])
    if "fl-1-subset" in queue and not failed:
        queue.remove("fl-1-subset")
    log(f"publisher start: queue {queue}; fl-1 failed chunks {failed} -> {len(chunks)} subset chunks")
    while queue:
        act = int(g4("active-jobs").splitlines()[-1])
        for item in queue:
            need = (len(chunks) if item == "fl-1-subset" else json.loads((GHA / item / "manifest.json").read_text())["n_chunks"]) + 1
            if act + need <= MAX_JOBS:
                if item == "fl-1-subset":
                    publish_subset(run1, failed, chunks)
                else:
                    log(g4("publish4", item).splitlines()[-1])
                queue.remove(item)
                time.sleep(90)
                break
        else:
            log(f"active jobs {act}; waiting (next: {queue[0]})")
            time.sleep(60)
    log("publisher done")


if __name__ == "__main__":
    main()
