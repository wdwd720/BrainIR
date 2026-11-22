"""Re-run the jobs of `fl-1-run4`'s failed chunks as attempt 2 in small chunks (LOG L131): operations only, no analysis.

A re-run of a failed chunk repeats the whole chunk (742 floor-1 jobs, about 5 h on GitHub, close to the job time limit). Instead the
failed chunks' jobs (unchanged specifications and payload) are packed into chunks of at most ~186 jobs and published as attempt 2 of
the same campaign; collection merges every attempt by job key against the full manifest. The local pack is replaced by the subset only
while publishing and is restored right after (and checked). Waits for: the core feeder to finish, attempt 1 to complete, and room for
the chunks under the 20-job limit; then starts a feeder for the determinism campaigns given on the command line.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/fl1_subset_v4.py RUN_ID [then-feed CAMPAIGN ...]
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


def sh(*a: str) -> str:
    return subprocess.run(a, cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def log(msg: str) -> None:
    with open(LOGS / "collect_all.log", "a") as fh:
        fh.write(time.strftime("%H:%M:%S") + " " + msg + "\n")


def g4(*a: str) -> str:
    return sh("uv", "run", "--project", "ledger", "--no-sync", "python", "ledger/scripts/gha4.py", *a)


def main() -> None:
    run1 = sys.argv[1]
    then = sys.argv[sys.argv.index("then-feed") + 1:] if "then-feed" in sys.argv else []
    while subprocess.run(["pgrep", "-f", "gha4.py feeder"], capture_output=True).returncode == 0:
        time.sleep(60)
    while True:
        jobs = json.loads(sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run1}/jobs?per_page=100"))["jobs"]
        if jobs and all(j["status"] == "completed" for j in jobs):
            break
        time.sleep(60)
    failed = sorted(int(j["name"].split("(")[1].rstrip(")")) for j in jobs if j["name"].startswith("run") and j["conclusion"] != "success")
    log(f"FL1 attempt 1 completed; failed chunks {failed}")
    if failed:
        if not BK.exists():
            shutil.copytree(D, BK)
        full = json.loads((BK / "manifest.json").read_text())
        items = []
        for i in failed:
            items += pickle.loads((BK / f"chunk_{i}.pkl").read_bytes())
        per = max(186, math.ceil(len(items) / 15))
        chunks = [items[i:i + per] for i in range(0, len(items), per)]
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
        while int(g4("active-jobs").splitlines()[-1]) + len(chunks) + 1 > MAX_JOBS:
            time.sleep(60)
        subprocess.run(["gh", "release", "delete", f"ledgerdata-{NAME}", "--yes"], cwd=REPO, capture_output=True)
        out = g4("publish4", NAME, "--attempt", "2").splitlines()[-1]
        for f in D.glob("chunk_*.pkl"):
            f.unlink()
        for f in BK.iterdir():
            shutil.copy(f, D / f.name)
        ok = (D / "manifest.json").read_text() == (BK / "manifest.json").read_text()
        log(f"FL1 subset published ({len(items)} jobs of chunks {failed} in {len(chunks)} chunks): {out}; full local pack restored: {ok}")
    if then:
        time.sleep(90)
        with open(LOGS / "feeder_run4_core2.log", "a") as fh:
            subprocess.run(["uv", "run", "--project", "ledger", "--no-sync", "python", "ledger/scripts/gha4.py", "feeder", *then],
                           cwd=REPO, stdout=fh, stderr=subprocess.STDOUT)


if __name__ == "__main__":
    main()
