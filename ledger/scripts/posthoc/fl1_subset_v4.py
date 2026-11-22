"""Publisher for the rest of run 4's GitHub queue (LOG L131-L133): operations only, no analysis.

Two problems it solves. (1) `fl-1-run4` attempt 1 failed (one runner lost, five chunks past the 340-minute limit), and a re-run of a
failed chunk repeats the whole 742-job chunk; its jobs (unchanged specifications and payload) are re-packed into chunks of at most
PER jobs. (2) A campaign's chunks are published together, so a large one waits for many free slots at once; a campaign can instead be
published as several partial attempts (chunk ranges), each needing fewer slots.

A partial attempt is published by putting a subset pack (its chunks renumbered from 0, a manifest listing only them, the same payload)
in the campaign folder, re-creating the campaign's release from it and pushing the next attempt tag; the full local pack is restored
right after and checked, because collection merges all attempts by job key against the full manifest. The release is deleted only
when every job of the campaign's earlier attempts has started (their inputs are downloaded at start).

Queue items, published first-fit in priority order (the first item whose chunks + 1 fit under the 20-job limit; 90 s after each
publish before counting again, L119): `CAMPAIGN` (all of it), `CAMPAIGN@A-B` (packed chunks A..B), `fl-1-subset@A-B` (chunks A..B of
the re-packed failed jobs of fl-1 attempt 1). It is the only publisher while it runs (any feeder is stopped).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/fl1_subset_v4.py FL1_RUN_ID ITEM ...
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
BACKUPS = REPO / "data" / "cache"
FL1 = "fl-1-run4"
MAX_JOBS = 20
PER = 420


def sh(*a: str) -> str:
    return subprocess.run(a, cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def log(msg: str, f: str = "feeder_run4_core2.log") -> None:
    with open(LOGS / f, "a") as fh:
        fh.write(time.strftime("%H:%M:%S") + " " + msg + "\n")


def g4(*a: str) -> str:
    return sh("uv", "run", "--project", "ledger", "--no-sync", "python", "ledger/scripts/gha4.py", *a)


def backup(name: str) -> Path:
    bk = BACKUPS / f"{name}_full_pack_backup"
    if not bk.exists():
        shutil.copytree(GHA / name, bk)
    return bk


def runs_of(name: str) -> list[dict]:
    runs = json.loads(sh("gh", "api", "repos/{owner}/{repo}/actions/runs?per_page=100&event=push"))["workflow_runs"]
    return [r for r in runs if r["head_branch"] == f"gha4-run-{name}" or r["head_branch"].startswith(f"gha4-run-{name}-r")]


def tags_of(name: str) -> set[str]:
    out = sh("git", "ls-remote", "--tags", "origin", f"gha4-run-{name}*")
    return {line.split("refs/tags/")[1] for line in out.splitlines() if "refs/tags/" in line}


def next_attempt(name: str) -> int:
    t = tags_of(name)
    if f"gha4-run-{name}" not in t:
        return 0
    n = 2
    while f"gha4-run-{name}-r{n}" in t:
        n += 1
    return n


def all_started(name: str) -> bool:
    for r in runs_of(name):
        jobs = json.loads(sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{r['id']}/jobs?per_page=100"))["jobs"]
        if not jobs or any(j["status"] in ("queued", "waiting", "pending", "requested") for j in jobs):
            return False
    return True


def fl1_plan(run1: str) -> tuple[list[int], list[list]]:
    jobs = json.loads(sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run1}/jobs?per_page=100"))["jobs"]
    if not (jobs and all(j["status"] == "completed" for j in jobs)):
        raise SystemExit("fl-1 attempt 1 not completed")
    failed = sorted(int(j["name"].split("(")[1].rstrip(")")) for j in jobs if j["name"].startswith("run") and j["conclusion"] != "success")
    bk = backup(FL1)
    items = []
    for i in failed:
        items += pickle.loads((bk / f"chunk_{i}.pkl").read_bytes())
    per = max(PER, math.ceil(len(items) / 15))
    return failed, [items[i:i + per] for i in range(0, len(items), per)]


def packed_chunks(name: str) -> list[list]:
    bk = backup(name)
    n = json.loads((bk / "manifest.json").read_text())["n_chunks"]
    return [pickle.loads((bk / f"chunk_{i}.pkl").read_bytes()) for i in range(n)]


def publish_part(name: str, chunks: list[list], note: dict) -> None:
    """Publish `chunks` (lists of (payload key, job)) as the next attempt of `name`, then restore the full local pack."""
    bk = backup(name)
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
    man = {"campaign": name, "area": full["area"], "n_jobs": len(items), "n_chunks": len(chunks), "payload_keys": pkeys, "files": files,
           "keys_sha256": hashlib.sha256("\n".join(keys).encode()).hexdigest(), "keys": keys,
           "git_head": sh("git", "rev-parse", "HEAD"), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "part_of": {**note, "full_keys_sha256": full["keys_sha256"]}}
    (d / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    att = next_attempt(name)
    try:
        if att != 0:
            subprocess.run(["gh", "release", "delete", f"ledgerdata-{name}", "--yes"], cwd=REPO, capture_output=True)
        out = g4("publish4", name, *(["--attempt", str(att)] if att else [])).splitlines()[-1]
    finally:
        for f in d.glob("chunk_*.pkl"):
            f.unlink()
        for f in bk.iterdir():
            shutil.copy(f, d / f.name)
    ok = (d / "manifest.json").read_text() == (bk / "manifest.json").read_text()
    log(f"{out} [part: {len(items)} jobs, {len(chunks)} chunks, {note}; full local pack restored: {ok}]")
    if name == FL1:
        log(f"FL1 part published ({len(items)} jobs, {len(chunks)} chunks, {note}); full local pack restored: {ok}", "collect_all.log")


def main() -> None:
    run1, queue = sys.argv[1], list(sys.argv[2:])
    subprocess.run(["pkill", "-f", "gha4.py feeder"], capture_output=True)
    plan = fl1_plan(run1) if any(q.startswith("fl-1-subset") for q in queue) else ([], [])
    log(f"publisher start: queue {queue}; fl-1 failed chunks {plan[0]} -> {len(plan[1])} re-packed chunks")

    def resolve(item: str) -> tuple[str, list[list] | None, dict]:
        if "@" not in item:
            return item, None, {}
        base, rng = item.split("@")
        a, b = (int(x) for x in rng.split("-"))
        if base == "fl-1-subset":
            return FL1, plan[1][a:b + 1], {"fl1_attempt1_failed_chunks": plan[0], "repacked_chunks": [a, b]}
        return base, packed_chunks(base)[a:b + 1], {"packed_chunks": [a, b]}

    while queue:
        act = int(g4("active-jobs").splitlines()[-1])
        for item in queue:
            name, chunks, note = resolve(item)
            n = len(chunks) if chunks is not None else json.loads((GHA / name / "manifest.json").read_text())["n_chunks"]
            if act + n + 1 > MAX_JOBS:
                continue
            if chunks is not None and next_attempt(name) != 0 and not all_started(name):
                continue
            if chunks is None:
                log(g4("publish4", name).splitlines()[-1])
            else:
                publish_part(name, chunks, note)
            queue.remove(item)
            time.sleep(90)
            break
        else:
            log(f"active jobs {act}; waiting (next: {queue[0]})")
            time.sleep(60)
    log("publisher done")


if __name__ == "__main__":
    main()
