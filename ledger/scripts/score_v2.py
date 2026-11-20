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
    # PREREG v2 S4: a crash is an uncaught exception that stops a run; the run is repeated once after a crash fix recorded with
    # `lock2.py amend --crash-fix`; an analysis ending with status `error` is a result, not a crash.
    out_dir = research / "results" / "run2"
    started = out_dir / f"{a.run}.started.json"
    crashed = out_dir / f"{a.run}.crashed-1.json"
    if started.exists():
        if not a.after_crash_fix:
            print(f"refused: {started.name} exists (an earlier attempt crashed or is running); see --after-crash-fix", file=sys.stderr)
            return 2
        if crashed.exists():
            print("refused: this run was already repeated once after a crash (PREREG v2 S4)", file=sys.stderr)
            return 2
        amend = research / "AMENDMENTS_v2.jsonl"
        fixes = [json.loads(x) for x in (amend.read_text(encoding="utf-8").splitlines() if amend.exists() else []) if x.strip()]
        if not any(f.get("crash_fix") and f.get("after_unblinding")
                   and calendar.timegm(time.strptime(f["utc"], "%Y-%m-%dT%H:%M:%SZ")) > started.stat().st_mtime for f in fixes):
            print("refused: no crash fix was recorded after the crashed attempt", file=sys.stderr)
            return 2
        started.rename(crashed)
    elif a.after_crash_fix:
        print("refused: no crashed attempt of this run", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / f"{a.run}.json").exists():
        print(f"refused: results/run2/{a.run}.json exists (each run once)", file=sys.stderr)
        return 2
    started.write_text(json.dumps({"run": a.run, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    try:
        res = run(a.run, research, research / "UNBLIND.json")
    except BlindError as e:  # a refusal: nothing was computed
        started.unlink(missing_ok=True)
        print(str(e), file=sys.stderr)
        return 2
    started.unlink(missing_ok=True)  # completed; an uncaught exception leaves the marker (a crash, PREREG v2 S4)
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
