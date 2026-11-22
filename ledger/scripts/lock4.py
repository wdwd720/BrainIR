"""Run 4 locks (PREREG v4 X4-X5): lock files written with run 2's helpers (`lock2.py`, frozen, imported unchanged) and checked with
run 2's walk, with run 4's OWN amendment ledger (`AMENDMENTS_v4.jsonl`); run 2's and run 3's rows never count for a run 4 lock, and
run 4's rows never count for an earlier lock (whose checks are run 3's `lock3.check`, unchanged).

    lock4.py prereg          # LOCK_prereg_v4.json      (the freeze; then the tag ledger-prereg-v4)
    lock4.py reliability     # LOCK_reliability_v2.json (Parts A0-D outputs; tag ledger-reliability-v2)
    lock4.py forward         # LOCK_forward_v1.json     (the forward ledger; tag ledger-forward-v1)
    lock4.py amend PATH --reason TEXT [--old-rev REV]
    lock4.py check research/ledger/LOCK_x.json

Amendment rules (PREREG v4 X4): ledger code only (ledger/**, .github/**: .py .sh .toml .yml .lock), never a file any earlier lock
hashes, never this tool or its test; once `LOCK_reliability_v2.json` is committed, never a file it hashes; once `LOCK_forward_v1.json`
is committed, nothing. A row counts only once committed, timed by the later of its own time and its first commit.
"""

from __future__ import annotations

import calendar
import fnmatch
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lock2 as L2  # noqa: E402
import lock3 as L3  # noqa: E402

RES = L2.RES
REPO = L2.REPO
CODE_GLOBS = L2.CODE_GLOBS + ["ledger/scripts/posthoc/*.py"]  # audit finding 20: lock2's globs do not recurse into posthoc/
NEVER_AMEND = ["ledger/scripts/lock4.py", "ledger/tests/test_lock4.py"]
EARLIER = L3.EARLIER + list(L3.V3_LOCKS)
V4_LOCKS = ("LOCK_prereg_v4.json", "LOCK_reliability_v2.json", "LOCK_forward_v1.json")
AMEND4 = RES / "AMENDMENTS_v4.jsonl"
FLAGS4 = ("reliability_locked", "forward_locked")
UTC = "%Y-%m-%dT%H:%M:%SZ"


def _utc(s) -> int | None:
    try:
        return calendar.timegm(time.strptime(str(s), UTC))
    except (TypeError, ValueError):
        return None


def _matches(path: str, globs) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def _section(paths) -> dict[str, str]:
    ps = L2._hashable(paths)
    L2._require_tracked(ps, "run 4")
    return {L2.rel(p): L2.sha(p) for p in ps}


def _chain(*names: str) -> dict[str, str]:
    L2._require_present(*names)
    return {f"research/ledger/{n}": L2.sha(RES / n) for n in names}


def _code() -> dict[str, str]:
    untracked: list = []
    out = L2.globs(CODE_GLOBS, untracked)
    if untracked:
        raise SystemExit(f"refused: untracked code would not be hashed: {untracked[:10]} (git add it first); nothing written")
    return out


def _hashed_by(names, repo: Path | None = None) -> set[str] | None:
    repo = REPO if repo is None else Path(repo)
    out: set[str] = set()

    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v)
            elif L2._is_sha(v) and "/" in k:
                out.add(k)
    for n in names:
        try:
            walk(json.loads((Path(repo) / "research" / "ledger" / n).read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError):
            return None
    return out


def amendable_kind4(path) -> str | None:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in PurePosixPath(path).parts:
        return None
    if path.startswith(("ledger/", ".github/")) and PurePosixPath(path).suffix in (".py", ".sh", ".toml", ".yml", ".lock"):
        return "code"
    return None


def _first_commit_utc(rel: str, repo: Path | None = None) -> int | None:
    repo = REPO if repo is None else Path(repo)
    out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "--", rel], cwd=repo, capture_output=True, text=True).stdout
    xs = [int(x) for x in out.split()]
    return min(xs) if xs else None


def _times(repo: Path | None = None) -> dict:
    return {"reliability_lock": _first_commit_utc("research/ledger/LOCK_reliability_v2.json", repo),
            "forward_lock": _first_commit_utc("research/ledger/LOCK_forward_v1.json", repo)}


def row_problem4(row, earlier: set[str] | None, rel_hashed: set[str] | None, times: dict | None = None) -> str | None:
    if not isinstance(row, dict):
        return "not a JSON object"
    path = row.get("path")
    if amendable_kind4(path) is None:
        return "not a v4-amendable path (ledger code)"
    if earlier is None:
        return "an earlier lock is missing or unreadable: no amendment counts"
    if path in earlier:
        return "hashed by an earlier lock: never amended"
    if _matches(path, NEVER_AMEND):
        return "the lock tool and its test are never amended (a change is a new version)"
    if not (L2._is_sha(row.get("old")) and L2._is_sha(row.get("new"))):
        return "old / new are not SHA-256 values"
    if not all(isinstance(row.get(k), bool) for k in FLAGS4):
        return f"lacks the flags ({', '.join(FLAGS4)})"
    if times:
        t = times.get("row_utc")
        if t is None:
            return "the row is not committed (or has no valid time): not honoured"
        for flag, key in (("reliability_locked", "reliability_lock"), ("forward_locked", "forward_lock")):
            if times.get(key) is not None and t >= times[key] and not row[flag]:
                return f"recorded {flag}=false although the row is later than the {key.replace('_', ' ')}"
    if row["forward_locked"]:
        return "nothing is amended once LOCK_forward_v1.json is committed"
    if row["reliability_locked"] and rel_hashed is not None and path in rel_hashed:
        return "a file hashed by LOCK_reliability_v2.json is never amended after that lock"
    return None


def _row_commit_utc(row: dict, repo: Path | None = None) -> int | None:
    repo = REPO if repo is None else Path(repo)
    if not isinstance(row, dict) or not L2._is_sha(row.get("new")):
        return None
    out = subprocess.run(["git", "log", "--format=%ct", "-S", row["new"], "--", "research/ledger/AMENDMENTS_v4.jsonl"], cwd=repo,
                         capture_output=True, text=True).stdout.split()
    return min(int(x) for x in out) if out else None


def rows4(repo: Path | None = None) -> list[tuple[int, object, str | None]]:
    repo = REPO if repo is None else Path(repo)
    p = Path(repo) / "research" / "ledger" / "AMENDMENTS_v4.jsonl"
    if not p.exists():
        return []
    earlier = _hashed_by(EARLIER, repo)
    relp = Path(repo) / "research" / "ledger" / "LOCK_reliability_v2.json"
    rel_hashed = _hashed_by(["LOCK_reliability_v2.json"], repo) if relp.exists() else set()
    base, out = _times(repo), []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out.append((i, None, "invalid JSON"))
            continue
        ct = _row_commit_utc(row, repo)
        own = _utc(row.get("utc")) if isinstance(row, dict) else None
        t = None if ct is None else max(ct, own or 0)
        out.append((i, row, row_problem4(row, earlier, rel_hashed, {**base, "row_utc": t})))
    return out


def _chains4(repo: Path | None = None):
    chains, ignored = {}, []
    for i, row, problem in rows4(repo):
        if problem:
            ignored.append({"line": i, "path": row.get("path") if isinstance(row, dict) else None, "problem": problem})
            continue
        succ = chains.setdefault(row["path"], {}).setdefault(row["old"], [])
        if row["new"] not in succ:
            succ.append(row["new"])
    return chains, ignored


def amend(path: str, reason: str, old_rev: str = "HEAD") -> None:
    p = REPO / path
    if amendable_kind4(path) is None or not p.is_file():
        raise SystemExit(f"{path}: only ledger code can be amended (never rules, criteria, data)")
    shown = subprocess.run(["git", "show", f"{old_rev}:{path}"], cwd=REPO, capture_output=True, check=False)
    if shown.returncode != 0:
        raise SystemExit(f"{path} does not exist at {old_rev}: nothing to amend")
    old, new = hashlib.sha256(shown.stdout).hexdigest(), L2.sha(p)
    if old == new:
        raise SystemExit(f"{path} is unchanged relative to {old_rev}")
    times = _times()
    row = {"utc": time.strftime(UTC, time.gmtime()), "path": path, "old": old, "new": new, "reason": reason,
           "old_rev": L2.git("rev-parse", old_rev), "reliability_locked": times["reliability_lock"] is not None,
           "forward_locked": times["forward_lock"] is not None}
    relp = RES / "LOCK_reliability_v2.json"
    problem = row_problem4(row, _hashed_by(EARLIER), _hashed_by(["LOCK_reliability_v2.json"]) if relp.exists() else set(),
                           {**times, "row_utc": _utc(row["utc"])})
    if problem:
        raise SystemExit(f"refused: {problem} (PREREG v4 X4)")
    with AMEND4.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row))


def check(path: Path, repo: Path | None = None) -> int:
    """v4 locks: run 2's walk with v4 amendment rows only; any other lock: run 3's check unchanged."""
    repo = REPO if repo is None else Path(repo)
    if Path(path).name not in V4_LOCKS:
        return L3.check(Path(path), repo)
    orig = L2._chains
    L2._chains = _chains4
    try:
        return L2.check(Path(path), repo)
    finally:
        L2._chains = orig


# ------------------------------------------------------------------------------------------------ the locks
def lock_prereg() -> None:
    L2._require_absent("LOCK_prereg_v4.json")
    rec = L2.base("prereg_v4")
    rec["prereg_v4"] = _section([RES / "PREREG_v4.md", RES / "RUN4_PROMPT.md"])
    rec["diag_v4"] = _section((RES / "diag_v4").glob("*"))
    rec["gates_v4_at_freeze"] = _section((RES / "gates_v4").glob("*"))
    rec["reviews_v4_at_freeze"] = _section((RES / "reviews_v4").glob("*"))
    rec["earlier_locks"] = _chain(*EARLIER)
    rec["code"] = _code()
    rec["code_scope"] = ("every git-tracked file matching lock2.CODE_GLOBS plus ledger/scripts/posthoc/*.py at the freeze; binding "
                         "(changes only by v4 amendment rows)")
    L2.write("LOCK_prereg_v4.json", rec)


def lock_reliability() -> None:
    L2._require_absent("LOCK_reliability_v2.json")
    rec = L2.base("reliability_v2")
    rec["reliability_v2"] = _section((RES / "reliability_v2").glob("**/*"))
    rec["results_run4"] = _section((RES / "results" / "run4").glob("**/*"))
    rec["gates_v4"] = _section((RES / "gates_v4").glob("*"))
    rec["reviews_v4"] = _section((RES / "reviews_v4").glob("*"))
    rec["code"] = _code()
    rec["chained"] = _chain("LOCK_prereg_v4.json")
    L2.write("LOCK_reliability_v2.json", rec)


def lock_forward() -> None:
    L2._require_absent("LOCK_forward_v1.json")
    if _first_commit_utc("research/ledger/LOCK_reliability_v2.json") is None:
        raise SystemExit("LOCK_reliability_v2.json is not committed: it precedes the forward ledger lock; nothing written")
    rec = L2.base("forward_v1")
    rec["forward"] = _section((RES / "forward").glob("**/*"))
    rec["reviews_v4"] = _section((RES / "reviews_v4").glob("*"))
    rec["code"] = _code()
    rec["chained"] = _chain("LOCK_prereg_v4.json", "LOCK_reliability_v2.json")
    L2.write("LOCK_forward_v1.json", rec)


def main() -> None:
    what = sys.argv[1]
    args = sys.argv[2:]
    if what == "check":
        raise SystemExit(check(Path(args[0])))
    if what == "amend":
        amend(args[0], args[args.index("--reason") + 1], args[args.index("--old-rev") + 1] if "--old-rev" in args else "HEAD")
        return
    {"prereg": lock_prereg, "reliability": lock_reliability, "forward": lock_forward}[what]()


if __name__ == "__main__":
    main()
