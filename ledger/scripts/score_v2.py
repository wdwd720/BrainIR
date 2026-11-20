"""One pre-declared scoring run of run 2 (PREREG v2 S4): `brainir_ledger.scoring_v2.pipeline_v2.run`.

    uv run --project ledger --no-sync python ledger/scripts/score_v2.py --run P      # P, S-a, S-b, S-c; each exactly once

Refuses (exit 2; nothing computed, nothing written) unless research/ledger/UNBLIND.json exists, lists the run and names that
run's two locks with their SHA-256 (format: the docstring of `pipeline_v2`), and while the run's result file exists.
Writes research/ledger/results/run2/<run>.json and prints only the status of each analysis.
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.scoring import BlindError  # noqa: E402
from brainir_ledger.scoring_v2.pipeline_v2 import RUNS, run  # noqa: E402


def main(argv: list[str] | None = None, research: Path = RESEARCH) -> int:
    ap = argparse.ArgumentParser(description="PREREG v2 S4 scoring run (needs research/ledger/UNBLIND.json)")
    ap.add_argument("--run", required=True, choices=sorted(RUNS))
    ap.add_argument("--after-crash-fix", action="store_true",
                    help="PREREG v2 S4/L12: re-run a run whose output records an error, after a crash fix recorded with `lock2.py amend --crash-fix`")
    a = ap.parse_args(argv)
    if a.after_crash_fix:
        prev = research / "results" / "run2" / f"{a.run}.json"
        amend = research / "AMENDMENTS_v2.jsonl"
        if not prev.exists():
            print("no earlier output of this run", file=sys.stderr)
            return 2
        old = json.loads(prev.read_text(encoding="utf-8"))
        crashed = "analyses_error" in old or any(v.get("status") == "error" for v in (old.get("analyses") or {}).values()) \
            or (old.get("primary") or {}).get("status") == "error"
        fixes = [json.loads(x) for x in (amend.read_text(encoding="utf-8").splitlines() if amend.exists() else []) if x.strip()]
        later = [f for f in fixes if f.get("crash_fix") and f.get("after_unblinding")
                 and calendar.timegm(time.strptime(f["utc"], "%Y-%m-%dT%H:%M:%SZ")) > prev.stat().st_mtime]
        if not (crashed and later):
            print("refused: the earlier output records no error, or no crash fix was recorded after it", file=sys.stderr)
            return 2
        k = 1 + len(list(prev.parent.glob(f"{a.run}.crashed-*.json")))
        prev.rename(prev.parent / f"{a.run}.crashed-{k}.json")
    try:
        res = run(a.run, research, research / "UNBLIND.json")
    except BlindError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(f"run {a.run}: {RUNS[a.run]['predictions_lock']} + {RUNS[a.run]['labels_lock']} -> results/run2/{a.run}.json")
    if "primary" in res:
        print(f"  primary: {res['primary']['status']}")
    for k, v in (res.get("analyses") or {}).items():
        print(f"  {k}: {v['status']}")
    for k in ("analyses_error", "analyses_missing_from_code"):
        if k in res:
            print(f"  {k}: {res[k] if k == 'analyses_missing_from_code' else res[k]['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
