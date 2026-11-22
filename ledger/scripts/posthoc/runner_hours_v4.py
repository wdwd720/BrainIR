"""Runner-hours of run 4 (PREREG v4 X1; the step-time rule of LOG L102): for every workflow run whose tag is a run 4 campaign
(`gha4-run-*`, `gha-run-trust-run4`), the time from the first step's start to the last step's end of each job, unique job ids over
all attempts (`jobs?filter=all`). Prints a JSON summary; read-only (GitHub API via `gh`).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/runner_hours_v4.py
"""

from __future__ import annotations

import calendar
import json
import subprocess
import time


def gh(path: str) -> dict:
    return json.loads(subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout)


def _t(s: str | None) -> float | None:
    return None if not s else float(calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")))


def main() -> None:
    runs, page = [], 1
    while True:
        r = gh(f"repos/{{owner}}/{{repo}}/actions/runs?per_page=100&page={page}&event=push")["workflow_runs"]
        runs += r
        if len(r) < 100 or page > 30:
            break
        page += 1
    mine = [r for r in runs if r["head_branch"].startswith("gha4-run-") or r["head_branch"] == "gha-run-trust-run4"]
    seen, total, by_run, n_jobs = set(), 0.0, {}, 0
    for r in mine:
        jobs = gh(f"repos/{{owner}}/{{repo}}/actions/runs/{r['id']}/jobs?per_page=100&filter=all")["jobs"]
        h = 0.0
        for j in jobs:
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            st = [s for s in (j.get("steps") or []) if s.get("started_at") and s.get("completed_at")]
            if not st:
                continue
            a, b = min(_t(s["started_at"]) for s in st), max(_t(s["completed_at"]) for s in st)
            h += (b - a) / 3600.0
            n_jobs += 1
        by_run[r["head_branch"]] = by_run.get(r["head_branch"], 0.0) + h
        total += h
    print(json.dumps({"runner_hours_total": round(total, 2), "jobs_with_steps": n_jobs, "runs": len(mine),
                      "by_campaign": {k: round(v, 2) for k, v in sorted(by_run.items())}}, indent=1))


if __name__ == "__main__":
    main()
