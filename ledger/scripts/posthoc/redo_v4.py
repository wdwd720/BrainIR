"""Re-run the jobs of a GitHub attempt's failed chunks as partial attempts in small chunks (LOG L138): operations only, no analysis.

The failed chunks' jobs (unchanged specifications and payload, taken from the full-pack backup) are re-packed into chunks of PER jobs
and published in parts of K chunks, first-fit under the 20-job limit (90 s after each publish), with `fl1_subset_v4.publish_part`
(partial manifest, release re-created only after every earlier job has started, full local pack restored and checked).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/redo_v4.py CAMPAIGN RUN_ID PER K
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fl1_subset_v4 as P  # noqa: E402


def main() -> None:
    name, run_id, per, k = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    jobs = json.loads(P.sh("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs?per_page=100"))["jobs"]
    if not (jobs and all(j["status"] == "completed" for j in jobs)):
        raise SystemExit("the attempt has not completed")
    failed = sorted(int(j["name"].split("(")[1].rstrip(")")) for j in jobs if j["name"].startswith("run") and j["conclusion"] != "success")
    bk = P.backup(name)
    items = []
    for i in failed:
        items += pickle.loads((bk / f"chunk_{i}.pkl").read_bytes())
    chunks = [items[i:i + per] for i in range(0, len(items), per)]
    parts = [chunks[i:i + k] for i in range(0, len(chunks), k)]
    P.log(f"redo {name}: attempt run {run_id} failed chunks {failed} -> {len(items)} jobs in {len(chunks)} chunks of <= {per}, {len(parts)} parts")
    while parts:
        act = int(P.g4("active-jobs").splitlines()[-1])
        part = parts[0]
        if act + len(part) + 1 <= P.MAX_JOBS and (P.next_attempt(name) == 0 or P.all_started(name)):
            P.publish_part(name, part, {"redo_of_run": int(run_id), "failed_chunks": failed, "per": per})
            parts.pop(0)
            time.sleep(90)
        else:
            P.log(f"active jobs {act}; waiting (redo {name}, {len(parts)} parts left)")
            time.sleep(60)
    P.log(f"redo {name} published")


if __name__ == "__main__":
    main()
