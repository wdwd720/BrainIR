"""Run 5 locks (RUN5_PROMPT sections 4-6; PREREG v5 Part X): lock files written with run 2's helpers (`lock2.py`, frozen, imported
unchanged) and checked with run 2's walk, with run 5's OWN amendment ledger (`AMENDMENTS_v5.jsonl`). Earlier rows never count for a run
5 lock, and run 5's rows never count for an earlier lock (whose checks are `lock4.check`, unchanged).

    lock5.py pertype         # LOCK_pertype_v1.json      (per-type tables; then the tag ledger-pertype-v1)
    lock5.py prereg          # LOCK_prereg_v5.json       (the freeze; tag ledger-prereg-v5)
    lock5.py replication     # LOCK_replication_v1.json  (Parts R, S, T, L; tag ledger-replication-v1)
    lock5.py forward         # LOCK_forward_v2.json      (Part F; tag ledger-forward-v2)
    lock5.py amend PATH --reason TEXT [--old-rev REV]
    lock5.py check research/ledger/LOCK_x.json

Amendment rules: ledger code only (ledger/**, .github/**: .py .sh .toml .yml .lock), never a file any pre-run-5 lock hashes, never this
tool or its test; once `LOCK_replication_v1.json` is committed, never a file it hashes; once `LOCK_forward_v2.json` is committed,
nothing. A row counts only once committed, timed by the later of its own time and its first commit.

Untracked inputs (git-ignored replicate results, raw annotation files) are recorded by SHA-256 under keys without "/" (for example
`data:ledger:...:results.pkl`), so run 2's walk, which hashes every key containing "/", never looks for them in the repository.
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

RES = L2.RES
REPO = L2.REPO
NEVER_AMEND = ["ledger/scripts/lock5.py", "ledger/tests/test_lock5.py"]
EARLIER5 = list(L4.EARLIER) + list(L4.V4_LOCKS)
V5_LOCKS = ("LOCK_pertype_v1.json", "LOCK_prereg_v5.json", "LOCK_replication_v1.json", "LOCK_forward_v2.json")
AMEND5 = RES / "AMENDMENTS_v5.jsonl"
FLAGS5 = ("replication_locked", "forward2_locked")
UTC = L4.UTC


def amendable_kind5(path) -> str | None:
    return L4.amendable_kind4(path)


def _times5(repo: Path | None = None) -> dict:
    return {"replication_lock": L4._first_commit_utc("research/ledger/LOCK_replication_v1.json", repo),
            "forward2_lock": L4._first_commit_utc("research/ledger/LOCK_forward_v2.json", repo)}


def row_problem5(row, earlier: set[str] | None, rep_hashed: set[str] | None, times: dict | None = None) -> str | None:
    if not isinstance(row, dict):
        return "not a JSON object"
    path = row.get("path")
    if amendable_kind5(path) is None:
        return "not a v5-amendable path (ledger code)"
    if earlier is None:
        return "an earlier lock is missing or unreadable: no amendment counts"
    if path in earlier:
        return "hashed by a pre-run-5 lock: never amended"
    if L4._matches(path, NEVER_AMEND):
        return "the lock tool and its test are never amended (a change is a new version)"
    if not (L2._is_sha(row.get("old")) and L2._is_sha(row.get("new"))):
        return "old / new are not SHA-256 values"
    if not all(isinstance(row.get(k), bool) for k in FLAGS5):
        return f"lacks the flags ({', '.join(FLAGS5)})"
    if times:
        t = times.get("row_utc")
        if t is None:
            return "the row is not committed (or has no valid time): not honoured"
        for flag, key in (("replication_locked", "replication_lock"), ("forward2_locked", "forward2_lock")):
            if times.get(key) is not None and t >= times[key] and not row[flag]:
                return f"recorded {flag}=false although the row is later than the {key.replace('_', ' ')}"
    if row["forward2_locked"]:
        return "nothing is amended once LOCK_forward_v2.json is committed"
    if row["replication_locked"] and rep_hashed is not None and path in rep_hashed:
        return "a file hashed by LOCK_replication_v1.json is never amended after that lock"
    return None


def _row_commit_utc5(row: dict, repo: Path | None = None) -> int | None:
    repo = REPO if repo is None else Path(repo)
    if not isinstance(row, dict) or not L2._is_sha(row.get("new")):
        return None
    out = subprocess.run(["git", "log", "--format=%ct", "-S", row["new"], "--", "research/ledger/AMENDMENTS_v5.jsonl"], cwd=repo,
                         capture_output=True, text=True).stdout.split()
    return min(int(x) for x in out) if out else None


def rows5(repo: Path | None = None) -> list[tuple[int, object, str | None]]:
    repo = REPO if repo is None else Path(repo)
    p = Path(repo) / "research" / "ledger" / "AMENDMENTS_v5.jsonl"
    if not p.exists():
        return []
    earlier = L4._hashed_by(EARLIER5, repo)
    repp = Path(repo) / "research" / "ledger" / "LOCK_replication_v1.json"
    rep_hashed = L4._hashed_by(["LOCK_replication_v1.json"], repo) if repp.exists() else set()
    base, out = _times5(repo), []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out.append((i, None, "invalid JSON"))
            continue
        ct = _row_commit_utc5(row, repo)
        own = L4._utc(row.get("utc")) if isinstance(row, dict) else None
        t = None if ct is None else max(ct, own or 0)
        out.append((i, row, row_problem5(row, earlier, rep_hashed, {**base, "row_utc": t})))
    return out


def _chains5(repo: Path | None = None):
    chains, ignored = {}, []
    for i, row, problem in rows5(repo):
        if problem:
            ignored.append({"line": i, "path": row.get("path") if isinstance(row, dict) else None, "problem": problem})
            continue
        succ = chains.setdefault(row["path"], {}).setdefault(row["old"], [])
        if row["new"] not in succ:
            succ.append(row["new"])
    return chains, ignored


def amend(path: str, reason: str, old_rev: str = "HEAD") -> None:
    p = REPO / path
    if amendable_kind5(path) is None or not p.is_file():
        raise SystemExit(f"{path}: only ledger code can be amended (never rules, criteria, data)")
    shown = subprocess.run(["git", "show", f"{old_rev}:{path}"], cwd=REPO, capture_output=True, check=False)
    if shown.returncode != 0:
        raise SystemExit(f"{path} does not exist at {old_rev}: nothing to amend")
    old, new = hashlib.sha256(shown.stdout).hexdigest(), L2.sha(p)
    if old == new:
        raise SystemExit(f"{path} is unchanged relative to {old_rev}")
    times = _times5()
    row = {"utc": time.strftime(UTC, time.gmtime()), "path": path, "old": old, "new": new, "reason": reason,
           "old_rev": L2.git("rev-parse", old_rev), "replication_locked": times["replication_lock"] is not None,
           "forward2_locked": times["forward2_lock"] is not None}
    repp = RES / "LOCK_replication_v1.json"
    problem = row_problem5(row, L4._hashed_by(EARLIER5), L4._hashed_by(["LOCK_replication_v1.json"]) if repp.exists() else set(),
                           {**times, "row_utc": L4._utc(row["utc"])})
    if problem:
        raise SystemExit(f"refused: {problem} (PREREG v5 Part X)")
    with AMEND5.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row))


def check(path: Path, repo: Path | None = None) -> int:
    """v5 locks: run 2's walk with v5 amendment rows only; any other lock: `lock4.check` unchanged."""
    repo = REPO if repo is None else Path(repo)
    if Path(path).name not in V5_LOCKS:
        return L4.check(Path(path), repo)
    orig = L2._chains
    L2._chains = _chains5
    try:
        return L2.check(Path(path), repo)
    finally:
        L2._chains = orig


def _untracked(paths) -> dict[str, str]:
    """SHA-256 of untracked inputs, keyed without '/' (see the module text)."""
    out = {}
    for p in sorted(Path(x) for x in paths):
        if not p.is_file():
            raise SystemExit(f"untracked input missing: {p}; nothing written")
        out[p.resolve().relative_to(REPO).as_posix().replace("/", ":")] = L2.sha(p)
    return out


def _gather(sub: str) -> list[Path]:
    return sorted((RES / sub).glob("**/*")) if (RES / sub).exists() else []


# ------------------------------------------------------------------------------------------------ the locks
def lock_pertype() -> None:
    L2._require_absent("LOCK_pertype_v1.json")
    rec = L2.base("pertype_v1")
    rec["pertype_v1"] = L4._section(_gather("pertype_v1"))
    rec["gates_v5_at_lock"] = L4._section(_gather("gates_v5"))
    rec["run5_prompt"] = L4._section([RES / "RUN5_PROMPT.md"])
    man = json.loads((RES / "pertype_v1" / "MANIFEST.json").read_text())
    rec["untracked_inputs_sha256"] = _untracked([REPO / p for p in man["untracked_inputs"]])
    rec["earlier_locks"] = L4._chain(*EARLIER5)
    rec["code"] = L4._code()
    L2.write("LOCK_pertype_v1.json", rec)


def lock_prereg() -> None:
    L2._require_absent("LOCK_prereg_v5.json")
    if L4._first_commit_utc("research/ledger/LOCK_pertype_v1.json") is None:
        raise SystemExit("LOCK_pertype_v1.json is not committed: it precedes the freeze; nothing written")
    rec = L2.base("prereg_v5")
    rec["prereg_v5"] = L4._section([RES / "PREREG_v5.md", RES / "RUN5_PROMPT.md"])
    rec["reviews_v5_at_freeze"] = L4._section(_gather("reviews_v5"))
    rec["gates_v5_at_freeze"] = L4._section(_gather("gates_v5"))
    rec["chained"] = L4._chain("LOCK_pertype_v1.json")
    rec["earlier_locks"] = L4._chain(*EARLIER5)
    rec["code"] = L4._code()
    rec["code_scope"] = ("every git-tracked file matching lock2.CODE_GLOBS plus ledger/scripts/posthoc/*.py at the freeze; binding "
                         "(changes only by v5 amendment rows)")
    L2.write("LOCK_prereg_v5.json", rec)


def lock_replication() -> None:
    L2._require_absent("LOCK_replication_v1.json")
    if L4._first_commit_utc("research/ledger/LOCK_prereg_v5.json") is None:
        raise SystemExit("LOCK_prereg_v5.json is not committed: it precedes this lock; nothing written")
    rec = L2.base("replication_v1")
    rec["replication_v1"] = L4._section(_gather("replication_v1"))
    rec["labels_audit_v1"] = L4._section(_gather("labels_audit_v1") + [RES / "LABEL_AUDIT_v1.md"])
    rec["gates_v5"] = L4._section(_gather("gates_v5"))
    rec["reviews_v5"] = L4._section(_gather("reviews_v5"))
    man = RES / "replication_v1" / "MANIFEST.json"
    if man.exists():
        rec["untracked_inputs_sha256"] = _untracked([REPO / p for p in json.loads(man.read_text()).get("untracked_inputs", [])])
    rec["code"] = L4._code()
    rec["chained"] = L4._chain("LOCK_pertype_v1.json", "LOCK_prereg_v5.json")
    L2.write("LOCK_replication_v1.json", rec)


def lock_forward() -> None:
    L2._require_absent("LOCK_forward_v2.json")
    if L4._first_commit_utc("research/ledger/LOCK_replication_v1.json") is None:
        raise SystemExit("LOCK_replication_v1.json is not committed: it precedes the forward ledger v2 lock; nothing written")
    rec = L2.base("forward_v2")
    rec["forward_v2"] = L4._section(_gather("forward_v2"))
    rec["reviews_v5"] = L4._section(_gather("reviews_v5"))
    rec["code"] = L4._code()
    rec["chained"] = L4._chain("LOCK_pertype_v1.json", "LOCK_prereg_v5.json", "LOCK_replication_v1.json")
    L2.write("LOCK_forward_v2.json", rec)


def main() -> None:
    what = sys.argv[1]
    args = sys.argv[2:]
    if what == "check":
        raise SystemExit(check(Path(args[0])))
    if what == "amend":
        amend(args[0], args[args.index("--reason") + 1], args[args.index("--old-rev") + 1] if "--old-rev" in args else "HEAD")
        return
    {"pertype": lock_pertype, "prereg": lock_prereg, "replication": lock_replication, "forward": lock_forward}[what]()


if __name__ == "__main__":
    main()
