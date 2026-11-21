"""One pre-declared scoring run of run 2 (PREREG v2 S4): `brainir_ledger.scoring_v2.pipeline_v2.run`.

    uv run --project ledger --no-sync python ledger/scripts/score_v2.py --run P      # P first, then S-a, S-b, S-c; each exactly once

Refuses (exit 2; nothing computed, nothing written) unless research/ledger/UNBLIND.json exists, lists the run and names that
run's two locks with their SHA-256 (format: the docstring of `pipeline_v2`), the gate's run-2 report holds all six conditions,
`lock2.check(LOCK_scoring_v2.json)` passes and (for S-a, S-b, S-c) run P has ended; and while the run's result file exists.
Writes research/ledger/results/run2/<run>.json and prints only the status of each analysis.

Attempts (PREREG v2 S4: "A crash is an uncaught exception that stops a run; the run is repeated once after the fix (L12)").
Each attempt writes `results/run2/<run>.started.json` first, recording its own `utc`, pid and host; it is removed when the
attempt completes or is refused. On an uncaught exception the marker records it before the exception propagates: an
`Exception` is a crash (`exception`, its UTC and traceback tail); anything else (Ctrl-C's KeyboardInterrupt, SystemExit) is an
interruption (`interrupted_by`). A kill or a sleep leaves the marker without either. A leftover marker blocks a new attempt:
- it records an exception (a crash): one repeat with `--after-crash-fix`, only when `AMENDMENTS_v2.jsonl` holds a crash-fix row
  for the scoring v2 code (recorded with `lock2.py amend --crash-fix` after UNBLIND.json; accepted by the shared
  `lock2.amendment_row_problem`) whose `utc` is later than the marker's `utc`; the marker becomes `<run>.crashed-1.json`;
- it records none (interrupted or killed): one repeat with `--after-interruption`, no amendment needed, refused while the
  recorded pid is still alive on this host; the marker becomes `<run>.interrupted-1.json`.
Earlier attempts' markers are logged in the result (`prior_attempts`). A refusal during a repeat restores the earlier marker.
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.scoring import BlindError  # noqa: E402
from brainir_ledger.scoring_v2 import pipeline_v2 as P2  # noqa: E402
from brainir_ledger.scoring_v2.pipeline_v2 import RUNS, run  # noqa: E402

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now() -> str:
    return time.strftime(UTC_FORMAT, time.gmtime())


def _utc(s) -> int | None:
    try:
        return calendar.timegm(time.strptime(s, UTC_FORMAT)) if isinstance(s, str) else None
    except ValueError:
        return None


def _alive(marker: dict) -> bool:
    """The attempt's process still runs (same host only; an unknown host cannot be checked and is taken as ended)."""
    pid = marker.get("pid")
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid() or marker.get("host") != socket.gethostname():
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def crash_fixes_after(research: Path, marker: dict) -> list[dict]:
    """Crash-fix amendment rows of the scoring v2 code recorded after the attempt began (marker `utc`), each accepted by
    `lock2.amendment_row_problem` (PREREG v2 L12)."""
    t0 = _utc(marker.get("utc"))
    if t0 is None:
        return []
    tool = P2.load_lock2()
    out = []
    for _, row, problem in tool.amendment_rows(P2.repo_of(research)):
        if problem is None and row["crash_fix"] and row["after_unblinding"] and tool.is_scoring_v2(row["path"]) \
                and (_utc(row.get("utc")) or 0) > t0:
            out.append(row)
    return out


def _record(path: Path, marker: dict, e: BaseException) -> None:
    rec = dict(marker)
    if isinstance(e, Exception):  # PREREG v2 S4: a crash
        rec.update({"exception": f"{type(e).__name__}: {e}"[:2000], "exception_utc": _now(), "traceback": traceback.format_exc()[-4000:]})
    else:  # KeyboardInterrupt, SystemExit: an interruption, not a crash
        rec.update({"interrupted_by": type(e).__name__, "interrupted_utc": _now()})
    with contextlib.suppress(Exception):  # never mask the original exception
        path.write_text(json.dumps(rec) + "\n", encoding="utf-8")


def _refuse(msg: str) -> int:
    print(f"refused: {msg}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None, research: Path = RESEARCH) -> int:
    ap = argparse.ArgumentParser(description="PREREG v2 S4 scoring run (needs research/ledger/UNBLIND.json)")
    ap.add_argument("--run", required=True, choices=sorted(RUNS))
    ap.add_argument("--after-crash-fix", action="store_true",
                    help="PREREG v2 S4/L12: repeat, once, a run whose attempt crashed (its marker records an exception), after the "
                         "fix of the crash was recorded with `lock2.py amend --crash-fix`")
    ap.add_argument("--after-interruption", action="store_true",
                    help="repeat, once, a run whose attempt was interrupted or killed (its marker records no exception); no "
                         "amendment is needed; logged in the result")
    a = ap.parse_args(argv)
    research = Path(research)
    f = P2.attempt_files(research, a.run)
    if f["result"].exists():
        return _refuse(f"results/run2/{a.run}.json exists (each run once, PREREG v2 S4)")
    set_aside = None
    if f["started"].exists():
        m = P2.read_marker(f["started"])
        if m is None:
            return _refuse(f"{f['started'].name} is not readable JSON; nothing is repeated until it is understood")
        if m.get("exception"):
            if not a.after_crash_fix:
                return _refuse(f"{f['started'].name}: the attempt of {m.get('utc')} crashed ({str(m['exception'])[:200]}). Fix only "
                               "the crash, record it with `lock2.py amend --crash-fix`, then repeat once with --after-crash-fix")
            if f["crashed"].exists():
                return _refuse("this run was already repeated once after a crash (PREREG v2 S4)")
            try:
                fixes = crash_fixes_after(research, m)
            except BlindError as e:
                return _refuse(str(e))
            if not fixes:
                return _refuse(f"no crash fix of the scoring v2 code was recorded (lock2.py amend --crash-fix) after the crashed "
                               f"attempt began ({m.get('utc')})")
            set_aside = f["crashed"]
        else:
            if a.after_crash_fix:
                return _refuse(f"{f['started'].name} records no exception: the attempt was interrupted, killed or is still running, "
                               "which is not a crash; see --after-interruption")
            if not a.after_interruption:
                return _refuse(f"{f['started'].name} exists without an exception: the attempt of {m.get('utc')} was interrupted, was "
                               "killed or is still running; to repeat it once, --after-interruption")
            if f["interrupted"].exists():
                return _refuse("this run was already repeated once after an interruption")
            if _alive(m):
                return _refuse(f"the attempt's process (pid {m.get('pid')}) is still running")
            set_aside = f["interrupted"]
        f["started"].rename(set_aside)
    elif a.after_crash_fix or a.after_interruption:
        return _refuse("no earlier attempt of this run")
    prior = [{**(P2.read_marker(p) or {}), "file": p.name} for p in (f["crashed"], f["interrupted"]) if p.exists()]
    marker = {"run": a.run, "utc": _now(), "pid": os.getpid(), "host": socket.gethostname(), "attempt": len(prior) + 1}
    f["started"].parent.mkdir(parents=True, exist_ok=True)
    f["started"].write_text(json.dumps(marker) + "\n", encoding="utf-8")
    try:
        res = run(a.run, research, research / "UNBLIND.json", prior_attempts=prior)
    except BlindError as e:  # a refusal: nothing was computed; the state before this attempt is restored
        f["started"].unlink(missing_ok=True)
        if set_aside is not None:
            set_aside.rename(f["started"])
        print(str(e), file=sys.stderr)
        return 2
    except BaseException as e:  # PREREG v2 S4: recorded in the marker, then propagated (the marker stays)
        _record(f["started"], marker, e)
        raise
    f["started"].unlink(missing_ok=True)
    print(f"run {a.run}: {RUNS[a.run]['predictions_lock']} + {RUNS[a.run]['labels_lock']} -> results/run2/{a.run}.json")
    for p in prior:
        print(f"  earlier attempt ({p['file']}): {p.get('exception') or p.get('interrupted_by') or 'no exception recorded'}")
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
