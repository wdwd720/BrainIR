"""Run 6 locks (RUN6_PROMPT sections 6-7; PREREG v6 Part X): lock files written with run 2's helpers (`lock2.py`, frozen, imported
unchanged) and checked with run 2's walk, with run 6's OWN amendment ledger (`AMENDMENTS_v6.jsonl`). Earlier rows never count for a run
6 lock, and run 6's rows never count for an earlier lock (whose checks are `lock5.check`, unchanged).

    lock6.py prereg          # LOCK_prereg_v6.json       (the freeze; tag ledger-prereg-v6)
    lock6.py posthoc         # LOCK_posthoc_v6.json      (Part H; tag ledger-posthoc-v6)
    lock6.py thirdfly        # LOCK_thirdfly_v1.json     (the BANC screens, tests C1-C8, Part V; tag ledger-thirdfly-v1)
    lock6.py amend PATH --reason TEXT [--old-rev REV]
    lock6.py check research/ledger/LOCK_x.json

Amendment rules: ledger code only (ledger/**, .github/**: .py .sh .toml .yml .lock), never a file any pre-run-6 lock hashes, never this
tool or its test; once `LOCK_posthoc_v6.json` is committed, never a file it hashes; once `LOCK_thirdfly_v1.json` is committed,
nothing. A row counts only once committed, timed by the later of its own time and its first commit.

Untracked inputs (git-ignored replicate results) are recorded by SHA-256 under keys without "/" (as `lock5.py`).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lock2 as L2  # noqa: E402
import lock4 as L4  # noqa: E402
import lock5 as L5  # noqa: E402

RES = L2.RES
REPO = L2.REPO
NEVER_AMEND = ["ledger/scripts/lock6.py", "ledger/tests/test_lock6.py"]
EARLIER6 = list(L5.EARLIER5) + list(L5.V5_LOCKS)
V6_LOCKS = ("LOCK_prereg_v6.json", "LOCK_posthoc_v6.json", "LOCK_thirdfly_v1.json")
AMEND6 = RES / "AMENDMENTS_v6.jsonl"
FLAGS6 = ("posthoc_locked", "thirdfly_locked")
UTC = L4.UTC


def _times6(repo: Path | None = None) -> dict:
    return {"posthoc_lock": L4._first_commit_utc("research/ledger/LOCK_posthoc_v6.json", repo),
            "thirdfly_lock": L4._first_commit_utc("research/ledger/LOCK_thirdfly_v1.json", repo)}


def row_problem6(row, earlier: set[str] | None, ph_hashed: set[str] | None, times: dict | None = None) -> str | None:
    if not isinstance(row, dict):
        return "not a JSON object"
    path = row.get("path")
    if L4.amendable_kind4(path) is None:
        return "not a v6-amendable path (ledger code)"
    if earlier is None:
        return "an earlier lock is missing or unreadable: no amendment counts"
    if path in earlier:
        return "hashed by a pre-run-6 lock: never amended"
    if L4._matches(path, NEVER_AMEND):
        return "the lock tool and its test are never amended (a change is a new version)"
    if not (L2._is_sha(row.get("old")) and L2._is_sha(row.get("new"))):
        return "old / new are not SHA-256 values"
    if not all(isinstance(row.get(k), bool) for k in FLAGS6):
        return f"lacks the flags ({', '.join(FLAGS6)})"
    if times:
        t = times.get("row_utc")
        if t is None:
            return "the row is not committed (or has no valid time): not honoured"
        for flag, key in (("posthoc_locked", "posthoc_lock"), ("thirdfly_locked", "thirdfly_lock")):
            if times.get(key) is not None and t >= times[key] and not row[flag]:
                return f"recorded {flag}=false although the row is later than the {key.replace('_', ' ')}"
    if row["thirdfly_locked"]:
        return "nothing is amended once LOCK_thirdfly_v1.json is committed"
    if row["posthoc_locked"] and ph_hashed is not None and path in ph_hashed:
        return "a file hashed by LOCK_posthoc_v6.json is never amended after that lock"
    return None


def _row_commit_utc6(row: dict, repo: Path | None = None) -> int | None:
    repo = REPO if repo is None else Path(repo)
    if not isinstance(row, dict) or not L2._is_sha(row.get("new")):
        return None
    out = subprocess.run(["git", "log", "--format=%ct", "-S", row["new"], "--", "research/ledger/AMENDMENTS_v6.jsonl"], cwd=repo,
                         capture_output=True, text=True).stdout.split()
    return min(int(x) for x in out) if out else None


def rows6(repo: Path | None = None) -> list[tuple[int, object, str | None]]:
    repo = REPO if repo is None else Path(repo)
    p = Path(repo) / "research" / "ledger" / "AMENDMENTS_v6.jsonl"
    if not p.exists():
        return []
    earlier = L4._hashed_by(EARLIER6, repo)
    php = Path(repo) / "research" / "ledger" / "LOCK_posthoc_v6.json"
    ph_hashed = L4._hashed_by(["LOCK_posthoc_v6.json"], repo) if php.exists() else set()
    base, out = _times6(repo), []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out.append((i, None, "invalid JSON"))
            continue
        ct = _row_commit_utc6(row, repo)
        own = L4._utc(row.get("utc")) if isinstance(row, dict) else None
        t = None if ct is None else max(ct, own or 0)
        out.append((i, row, row_problem6(row, earlier, ph_hashed, {**base, "row_utc": t})))
    return out


def _chains6(repo: Path | None = None):
    chains, ignored = {}, []
    for i, row, problem in rows6(repo):
        if problem:
            ignored.append({"line": i, "path": row.get("path") if isinstance(row, dict) else None, "problem": problem})
            continue
        succ = chains.setdefault(row["path"], {}).setdefault(row["old"], [])
        if row["new"] not in succ:
            succ.append(row["new"])
    return chains, ignored


def amend(path: str, reason: str, old_rev: str = "HEAD") -> None:
    p = REPO / path
    if L4.amendable_kind4(path) is None or not p.is_file():
        raise SystemExit(f"{path}: only ledger code can be amended (never rules, criteria, data)")
    shown = subprocess.run(["git", "show", f"{old_rev}:{path}"], cwd=REPO, capture_output=True, check=False)
    if shown.returncode != 0:
        raise SystemExit(f"{path} does not exist at {old_rev}: nothing to amend")
    old, new = hashlib.sha256(shown.stdout).hexdigest(), L2.sha(p)
    if old == new:
        raise SystemExit(f"{path} is unchanged relative to {old_rev}")
    times = _times6()
    row = {"utc": time.strftime(UTC, time.gmtime()), "path": path, "old": old, "new": new, "reason": reason,
           "old_rev": L2.git("rev-parse", old_rev), "posthoc_locked": times["posthoc_lock"] is not None,
           "thirdfly_locked": times["thirdfly_lock"] is not None}
    php = RES / "LOCK_posthoc_v6.json"
    problem = row_problem6(row, L4._hashed_by(EARLIER6), L4._hashed_by(["LOCK_posthoc_v6.json"]) if php.exists() else set(),
                           {**times, "row_utc": L4._utc(row["utc"])})
    if problem:
        raise SystemExit(f"refused: {problem} (PREREG v6 Part X)")
    with AMEND6.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row))


def check(path: Path, repo: Path | None = None) -> int:
    """v6 locks: run 2's walk with v6 amendment rows only; any other lock: `lock5.check` unchanged."""
    repo = REPO if repo is None else Path(repo)
    if Path(path).name not in V6_LOCKS:
        return L5.check(Path(path), repo)
    orig = L2._chains
    L2._chains = _chains6
    try:
        return L2.check(Path(path), repo)
    finally:
        L2._chains = orig


def _gather(sub: str) -> list[Path]:
    return sorted(p for p in (RES / sub).glob("**/*") if p.is_file()) if (RES / sub).exists() else []


def lock_prereg() -> None:
    L2._require_absent("LOCK_prereg_v6.json")
    rec = L2.base("prereg_v6")
    rec["prereg_v6"] = L4._section([RES / "PREREG_v6.md", RES / "RUN6_PROMPT.md"])
    rec["reviews_v6_at_freeze"] = L4._section(_gather("reviews_v6"))
    rec["gates_v6_at_freeze"] = L4._section(_gather("gates_v6"))
    rec["earlier_locks"] = L4._chain(*EARLIER6)
    # PREREG v6 Part Q 6 / audit finding 10: MANC's whole-type sweep, under no earlier lock, fixed before any BANC result
    rec["untracked_inputs_sha256"] = L5._untracked([REPO / "data" / "ledger" / "reliability_v2" / "MODAL_dx-1-run4" / "results.pkl"])
    rec["code"] = L4._code()
    rec["code_scope"] = ("every git-tracked file matching lock2.CODE_GLOBS plus ledger/scripts/posthoc/*.py at the freeze; binding "
                         "(changes only by v6 amendment rows)")
    L2.write("LOCK_prereg_v6.json", rec)


def _manifest_untracked(sub: str) -> dict:
    man = RES / sub / "MANIFEST.json"
    if not man.exists():
        return {}
    return L5._untracked([REPO / p for p in json.loads(man.read_text()).get("untracked_inputs", [])])


def lock_posthoc() -> None:
    L2._require_absent("LOCK_posthoc_v6.json")
    if L4._first_commit_utc("research/ledger/LOCK_prereg_v6.json") is None:
        raise SystemExit("LOCK_prereg_v6.json is not committed: it precedes this lock; nothing written")
    rec = L2.base("posthoc_v6")
    rec["posthoc_v6"] = L4._section(_gather("posthoc_v6"))
    rec["untracked_inputs_sha256"] = _manifest_untracked("posthoc_v6")
    rec["code"] = L4._code()
    rec["chained"] = L4._chain("LOCK_prereg_v6.json")
    L2.write("LOCK_posthoc_v6.json", rec)


def lock_thirdfly() -> None:
    L2._require_absent("LOCK_thirdfly_v1.json")
    if L4._first_commit_utc("research/ledger/LOCK_posthoc_v6.json") is None:
        raise SystemExit("LOCK_posthoc_v6.json is not committed: it precedes this lock; nothing written")
    rec = L2.base("thirdfly_v1")
    rec["thirdfly_v1"] = L4._section(_gather("thirdfly_v1"))
    rec["gates_v6"] = L4._section(_gather("gates_v6"))
    rec["untracked_inputs_sha256"] = _manifest_untracked("thirdfly_v1")
    rec["code"] = L4._code()
    rec["chained"] = L4._chain("LOCK_prereg_v6.json", "LOCK_posthoc_v6.json")
    L2.write("LOCK_thirdfly_v1.json", rec)


def main() -> None:
    what = sys.argv[1]
    args = sys.argv[2:]
    if what == "check":
        raise SystemExit(check(Path(args[0])))
    if what == "amend":
        amend(args[0], args[args.index("--reason") + 1], args[args.index("--old-rev") + 1] if "--old-rev" in args else "HEAD")
        return
    {"prereg": lock_prereg, "posthoc": lock_posthoc, "thirdfly": lock_thirdfly}[what]()


if __name__ == "__main__":
    main()
