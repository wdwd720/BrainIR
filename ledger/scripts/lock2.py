"""Lock files for run 2 (the frozen `lock.py` writes only the v1 file names; this is its v2 counterpart, LOG L51+).

    lock2.py prereg       -> research/ledger/LOCK_prereg_v2.json      (PREREG_v2.md, RUN2_PROMPT.md, kit_v2, v1 lock hashes, code snapshot)
    lock2.py labelcode    -> research/ledger/LOCK_labelcode_v2.json   (v2 label-side code before the first v2 session)
    lock2.py scoring      -> research/ledger/LOCK_scoring_v2.json     (scoring code and its tests, before the first v2 session)
    lock2.py predictions ARM ... [ARM=reason ...] --platform TEXT -> research/ledger/LOCK_predictions_v2.json (additive to v1)
    lock2.py labels       -> research/ledger/LOCK_labels_v2.json
    lock2.py amend PATH --reason TEXT [--old-rev REV] [--crash-fix]   (PREREG v2 L12: records a bug-fix change of a locked code
                               or kit file in research/ledger/AMENDMENTS_v2.jsonl, before committing it; after UNBLIND.json exists
                               only `--crash-fix` of the scoring v2 code)
    lock2.py check LOCKFILE   (every repository file hashed in a binding section is re-hashed; missing ones reported; chained
                               lock hashes re-hashed; code-snapshot sections reported only; archive members skipped (the gate
                               checks them); PREREG v2 S5.1)

Writers (PREREG v2 L12: "the lock file is never edited"). Each writer refuses when its lock file exists or was ever committed.
`predictions` and `labels` refuse when a file they would hash is not tracked by git (untracked, or git-ignored: .gitignore
ignores *.parquet and *.log), since a clean checkout would lack it; add such files with `git add -f`. `labels` requires the
label-code and scoring locks and chains all three earlier v2 locks (`prereg_v2_lock_sha256`, `labelcode_v2_lock_sha256`,
`scoring_v2_lock_sha256`); `labelcode` and `scoring` chain the prereg lock. The binding `code` section of `predictions` holds
prediction-side code only: CODE_GLOBS minus the label code and its tests (LABEL_CODE, `labels2_*`, LABEL_TESTS) and the scoring
code with its tests (SCORING_CODE), which are bound by their own locks (`LOCK_labelcode_v2.json`, `LOCK_scoring_v2.json`).

Amendments (PREREG v2 L12). One predicate, `amendment_row_problem`, decides whether a row of AMENDMENTS_v2.jsonl may count; `amend`
writes only rows it accepts and `check` honours only rows it accepts (the others are listed as `amendment_rows_ignored`): the path
is one `amend` accepts (v2 code, IMPLEMENTATION_v2.md, kit prompts, the kit changelog) and no v1 lock hashes it; the row carries
old/new SHA-256 and the flags `amend` records; and it was allowed when written (a kit file only while `v2_sessions_started` is
false; a row with `after_unblinding` true only for a `crash_fix` of the scoring v2 code). `check` counts a file as matching when
honoured rows lead from its locked hash to its current hash (every successor of a hash is followed); never for v1 locks.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RES = REPO / "research" / "ledger"
CODE_GLOBS = ["ledger/src/brainir_ledger/**/*.py", "ledger/scripts/*.py", "ledger/scripts/*.sh", "ledger/tests/*.py", "ledger/pyproject.toml",
              "ledger/uv.lock", ".github/workflows/*.yml", ".github/ledger_gha_pub.pem"]
LABEL_CODE = ["ledger/scripts/labels2_*.py", "ledger/scripts/lock2.py", "ledger/scripts/labels_collect.py", "ledger/scripts/labels_prepare.py",
              "ledger/scripts/labels_audit.py", "ledger/scripts/labels_rooms.py", "ledger/src/brainir_ledger/labels/*.py"]
# the tests of the label code: hashed by `labelcode`, excluded from the predictions lock's code
LABEL_TESTS = ["ledger/tests/test_label*.py", "ledger/tests/test_audit.py"]
# the scoring code and the tests of it, of the gate and of this tool: hashed by `scoring`, excluded from the predictions lock's code
SCORING_CODE = ["ledger/src/brainir_ledger/scoring/*.py", "ledger/src/brainir_ledger/scoring_v2/*.py", "ledger/scripts/score_v2.py",
                "ledger/scripts/gate_v2.py", "ledger/tests/test_scoring_v2*.py", "ledger/tests/test_gate_v2*.py", "ledger/tests/test_lock2*.py",
                "ledger/tests/test_stats.py", "ledger/tests/test_unblind_guard.py"]
NOT_PREDICTION_CODE = LABEL_CODE + ["ledger/scripts/labels2_*"] + LABEL_TESTS + SCORING_CODE
V1_LOCKS = ["LOCK_prereg_v1.json", "LOCK_predictions_v1.json", "LOCK_labels_v1.json", "LOCK_labels_v1_1.json"]
CHAINED = {"prereg_lock_sha256": "LOCK_prereg_v1.json", "labels_v1_lock_sha256": "LOCK_labels_v1.json",
           "prereg_v2_lock_sha256": "LOCK_prereg_v2.json", "labelcode_v2_lock_sha256": "LOCK_labelcode_v2.json",
           "scoring_v2_lock_sha256": "LOCK_scoring_v2.json"}
AMEND_FLAGS = ("v2_sessions_started", "crash_fix", "after_unblinding")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def _hashable(paths) -> list[Path]:
    """The files `hashes` hashes: regular files, dot-files (e.g. .DS_Store) skipped."""
    return [p for p in sorted(set(paths)) if p.is_file() and not p.name.startswith(".")]


def hashes(paths) -> dict[str, str]:
    return {rel(p): sha(p) for p in _hashable(paths)}


def _is_sha(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


SNAPSHOT_SECTIONS = ("prediction_code_snapshot", "code_snapshot")
AMEND = RES / "AMENDMENTS_v2.jsonl"
V2_MANIFESTS = Path.home() / "ledger_rooms" / "run2" / "_manifests"
SCORING_V2 = ("ledger/src/brainir_ledger/scoring_v2/", "ledger/scripts/score_v2.py")
P4B = ["ledger/src/brainir_ledger/typescreen_v2.py", "ledger/src/brainir_ledger/jobs_v2.py", "ledger/scripts/gha.py",
       "ledger/scripts/gha_runner.py", "ledger/scripts/g3v2_preview.py", "ledger/scripts/g3v2_evaluate.py", "ledger/scripts/b4v2.py"]


# ------------------------------------------------------------------------------------------------------------- amendments
def amendable_kind(path) -> str | None:
    """'kit' or 'code' when `amend` accepts a file at this repository path (PREREG v2 L12), else None. Whether a v1 lock hashes
    the path is checked separately (`_v1_hashed`)."""
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in PurePosixPath(path).parts:
        return None
    if path.startswith("research/ledger/kit_v2/PROMPT_") or path == "research/ledger/kit_v2/CHANGELOG.md":
        return "kit"
    if (path.startswith(("ledger/", ".github/")) and PurePosixPath(path).suffix in (".py", ".sh", ".toml", ".yml", ".lock")) \
            or path == "research/ledger/IMPLEMENTATION_v2.md":
        return "code"
    return None


def is_scoring_v2(path) -> bool:
    return isinstance(path, str) and amendable_kind(path) == "code" and path.startswith(SCORING_V2)


def _v1_hashed(repo: Path = REPO) -> set[str] | None:
    """Every path any v1 lock hashes (PREREG v2 L12: never amended); None when a v1 lock is missing or unreadable (then no
    amendment can be shown to be allowed)."""
    out: set[str] = set()

    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(v, str) and len(v) == 64:
                out.add(k)
    for n in V1_LOCKS:
        try:
            walk(json.loads((Path(repo) / "research" / "ledger" / n).read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError):
            return None
    return out


def amendment_row_problem(row, v1_hashed: set[str] | None) -> str | None:
    """None when a row of AMENDMENTS_v2.jsonl may count (PREREG v2 L12), else why not. Shared by `amend` (writes only rows it
    accepts), `check` (honours only rows it accepts) and score_v2.py (a crash-fix repeat needs such a row)."""
    if not isinstance(row, dict):
        return "not a JSON object"
    path = row.get("path")
    kind = amendable_kind(path)
    if kind is None:
        return "not a path lock2.py amend accepts (v2 code, IMPLEMENTATION_v2.md, kit prompts, the kit changelog)"
    if v1_hashed is None:
        return "a v1 lock is missing or unreadable: no amendment counts"
    if path in v1_hashed:
        return "hashed by a v1 lock: never amended"
    if not (_is_sha(row.get("old")) and _is_sha(row.get("new"))):
        return "old / new are not SHA-256 values"
    if not all(isinstance(row.get(k), bool) for k in AMEND_FLAGS):
        return f"lacks the flags lock2.py amend records ({', '.join(AMEND_FLAGS)})"
    if kind == "kit" and row["v2_sessions_started"]:
        return "a kit file amended after the first v2 label session"
    if row["after_unblinding"] and not (row["crash_fix"] and is_scoring_v2(path)):
        return "after unblinding only a crash fix of the scoring v2 code"
    return None


def amendment_rows(repo: Path = REPO) -> list[tuple[int, object, str | None]]:
    """(line number, parsed row or None, problem or None) for every non-empty line of AMENDMENTS_v2.jsonl."""
    p = Path(repo) / "research" / "ledger" / "AMENDMENTS_v2.jsonl"
    if not p.exists():
        return []
    v1, out = _v1_hashed(repo), []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out.append((i, None, "invalid JSON"))
            continue
        out.append((i, row, amendment_row_problem(row, v1)))
    return out


def _chains(repo: Path = REPO) -> tuple[dict[str, dict[str, list[str]]], list[dict]]:
    """Honoured rows as successor lists ({path: {old: [new, ...]}}) and the ignored rows with the reason."""
    chains: dict[str, dict[str, list[str]]] = {}
    ignored: list[dict] = []
    for i, row, problem in amendment_rows(repo):
        if problem:
            ignored.append({"line": i, "path": row.get("path") if isinstance(row, dict) else None, "problem": problem})
            continue
        succ = chains.setdefault(row["path"], {}).setdefault(row["old"], [])
        if row["new"] not in succ:
            succ.append(row["new"])
    return chains, ignored


def _chain_ok(path: str, locked: str, current: str, chains: dict) -> bool:
    """True if honoured amendments lead from the locked hash to the current one (PREREG v2 L12); every successor is followed."""
    succ = chains.get(path, {})
    seen, todo = {locked}, [locked]
    while todo:
        for nxt in succ.get(todo.pop(), []):
            if nxt == current:
                return True
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return False


def amend(path: str, reason: str, old_rev: str = "HEAD", crash_fix: bool = False) -> None:
    unblinded = (RES / "UNBLIND.json").exists()
    if unblinded and not (crash_fix and path.startswith(SCORING_V2)):
        raise SystemExit("after unblinding only a crash fix of the scoring v2 code may be recorded (PREREG v2 L12, --crash-fix)")
    p = REPO / path
    kind = amendable_kind(path)
    if kind is None or not p.is_file():
        raise SystemExit(f"{path}: only v2 code, the implementation map and kit prompts (with the kit changelog) can be amended "
                         "(never rules, other kit files, records, labels, predictions)")
    v1 = _v1_hashed()
    if v1 is None:
        raise SystemExit("a v1 lock is missing or unreadable: an amendment cannot be checked against the v1 locks")
    if path in v1:
        raise SystemExit(f"{path} is hashed by a v1 lock: never amended (PREREG v2 L12)")
    started = V2_MANIFESTS.exists() and any(V2_MANIFESTS.glob("*.json"))
    if kind == "kit" and started:
        raise SystemExit("kit files can be amended only before the first v2 label session (PREREG v2 L12)")
    shown = subprocess.run(["git", "show", f"{old_rev}:{path}"], cwd=REPO, capture_output=True, check=False)
    if shown.returncode != 0:
        raise SystemExit(f"{path} does not exist at {old_rev}: nothing to amend")
    old, new = hashlib.sha256(shown.stdout).hexdigest(), sha(p)
    if old == new:
        raise SystemExit(f"{path} is unchanged relative to {old_rev}")
    recs = any(f.stat().st_size > 0 for f in (RES / "labels_v2" / "raw" / "pass1").glob("*/records.valid.jsonl"))
    row = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "path": path, "old": old, "new": new, "reason": reason,
           "old_rev": git("rev-parse", old_rev), "v2_sessions_started": started, "v2_records_existed": recs,
           "crash_fix": crash_fix, "after_unblinding": unblinded}
    problem = amendment_row_problem(row, v1)
    if problem:
        raise SystemExit(f"refused: {problem} (PREREG v2 L12)")
    with AMEND.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row))


# ------------------------------------------------------------------------------------------------------------- writers
def tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=False).stdout
    return {x for x in out.split("\0") if x}


def globs(gs, untracked: list | None = None) -> dict[str, str]:
    """Hashes of git-tracked files matching the globs (a lock must be reproducible from its commit); untracked matches are
    listed by name in `untracked` and not hashed."""
    tr, out = tracked(), {}
    for g in gs:
        for k, v in hashes(REPO.glob(g)).items():
            if k in tr:
                out[k] = v
            elif untracked is not None:
                untracked.append(k)
    return out


def _matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in patterns)


def prediction_code(untracked: list | None = None) -> dict[str, str]:
    """CODE_GLOBS minus the label code and the scoring code (bound by LOCK_labelcode_v2.json and LOCK_scoring_v2.json)."""
    seen: list = []
    out = {k: v for k, v in globs(CODE_GLOBS, seen).items() if not _matches(k, NOT_PREDICTION_CODE)}
    if untracked is not None:
        untracked.extend(k for k in seen if not _matches(k, NOT_PREDICTION_CODE))
    return out


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def base(stage: str) -> dict:
    return {"stage": stage, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_head": git("rev-parse", "HEAD"),
            "git_dirty_ledger_paths": git("status", "--porcelain", "--", "ledger", "research/ledger", ".github").splitlines(),
            "v1_locks": {f"research/ledger/{n}": sha(RES / n) for n in V1_LOCKS}}


def _require_absent(name: str) -> None:
    """PREREG v2 L12: a lock file is written once and never edited."""
    p = RES / name
    if p.exists() or git("log", "--format=%H", "--", rel(p)):
        raise SystemExit(f"{name} exists or was committed before: a lock file is written once and never edited (PREREG v2 L12); "
                         "refused, nothing written")


def _require_present(*names: str) -> None:
    for n in names:
        if not (RES / n).is_file():
            raise SystemExit(f"{n} is missing: it is written (and chained) before this lock (PREREG v2 L12); refused, nothing written")


def _require_tracked(files: list[Path], what: str) -> None:
    tr = tracked()
    bad = [rel(p) for p in files if rel(p) not in tr]
    if bad:
        raise SystemExit(f"refused: {len(bad)} file(s) the {what} lock would hash are not tracked by git (untracked, or git-ignored: "
                         f".gitignore ignores *.parquet and *.log), e.g. {bad[:10]}. A clean checkout would lack them and the gate's "
                         "condition 1 would fail. Add each with `git add -f <path>`, then lock and commit; nothing written.")


def write(name: str, rec: dict) -> None:
    p = RES / name
    with open(p, "x", encoding="utf-8", newline="\n") as fh:  # never overwrites (a race with another writer fails here)
        fh.write(json.dumps(rec, indent=1, sort_keys=True, default=str) + "\n")
    print(p.name, sha(p), "dirty:", rec["git_dirty_ledger_paths"])


def lock_prereg() -> None:
    _require_absent("LOCK_prereg_v2.json")
    rec = base("prereg_v2")
    rec["prereg_v2"] = hashes([RES / "PREREG_v2.md", RES / "RUN2_PROMPT.md"])
    rec["kit_v2"] = hashes((RES / "kit_v2").glob("*"))
    rec["gates_v2_at_freeze"] = hashes((RES / "gates_v2").glob("*"))
    rec["reviews_v2_at_freeze"] = hashes((RES / "reviews_v2").glob("*"))
    rec["untracked_code_not_hashed"] = []
    rec["code_snapshot"] = globs(CODE_GLOBS, rec["untracked_code_not_hashed"])
    write("LOCK_prereg_v2.json", rec)


def lock_labelcode() -> None:
    _require_absent("LOCK_labelcode_v2.json")
    _require_present("LOCK_prereg_v2.json")
    rec = base("labelcode_v2")
    rec["implementation_map"] = hashes([RES / "IMPLEMENTATION_v2.md"])
    rec["untracked_code_not_hashed"] = []
    rec["label_code"] = globs(LABEL_CODE + LABEL_TESTS + ["ledger/scripts/gate_v2.py"], rec["untracked_code_not_hashed"])
    rec["kit_v2"] = hashes((RES / "kit_v2").glob("*"))
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_labelcode_v2.json", rec)


def lock_scoring() -> None:
    _require_absent("LOCK_scoring_v2.json")
    _require_present("LOCK_prereg_v2.json")
    rec = base("scoring_v2")
    rec["untracked_code_not_hashed"] = []
    rec["scoring_code"] = globs(SCORING_CODE, rec["untracked_code_not_hashed"])
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_scoring_v2.json", rec)


def lock_predictions(arms: list[str], not_locked: dict[str, str], platform: str) -> None:
    _require_absent("LOCK_predictions_v2.json")
    _require_present("LOCK_prereg_v2.json")
    arm_files = {a: _hashable((RES / "predictions_v2" / a).glob("*")) for a in arms}
    gates, reviews = _hashable((RES / "gates_v2").glob("*")), _hashable((RES / "reviews_v2").glob("*"))
    _require_tracked([p for fs in arm_files.values() for p in fs] + gates + reviews, "predictions")
    rec = base("predictions_v2")
    rec["arms_locked"] = {a: {rel(p): sha(p) for p in fs} for a, fs in arm_files.items()}
    rec["arms_not_locked"] = not_locked
    rec["marking"] = "locked after labels v1 existed, before any unblinding"
    rec["platform"] = platform
    rec["gates_v2"] = {rel(p): sha(p) for p in gates}
    rec["reviews_v2"] = {rel(p): sha(p) for p in reviews}
    rec["untracked_code_not_hashed"] = []
    rec["code"] = prediction_code(rec["untracked_code_not_hashed"])
    rec["code_scope"] = ("prediction-side code: CODE_GLOBS minus the label code and its tests (LABEL_CODE, labels2_*, LABEL_TESTS) "
                         "and the scoring code with its tests (SCORING_CODE), which LOCK_labelcode_v2.json and LOCK_scoring_v2.json bind")
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_predictions_v2.json", rec)


def lock_labels() -> None:
    _require_absent("LOCK_labels_v2.json")
    _require_present("LOCK_prereg_v2.json", "LOCK_labelcode_v2.json", "LOCK_scoring_v2.json")
    L = RES / "labels_v2"
    sections = {"labels": _hashable(L.glob("*")), "raw": _hashable(L.glob("raw/**/*")), "sessions": _hashable(L.glob("sessions/*")),
                "work_inputs": _hashable(L.glob("work/**/*")), "kit_v2": _hashable((RES / "kit_v2").glob("*"))}
    _require_tracked([p for fs in sections.values() for p in fs], "labels")
    rec = base("labels_v2")
    rec.update({sec: {rel(p): sha(p) for p in fs} for sec, fs in sections.items()})
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    rec["labelcode_v2_lock_sha256"] = sha(RES / "LOCK_labelcode_v2.json")
    rec["scoring_v2_lock_sha256"] = sha(RES / "LOCK_scoring_v2.json")
    write("LOCK_labels_v2.json", rec)


# ------------------------------------------------------------------------------------------------------------- check
def check(path: Path, repo: Path = REPO) -> int:
    """PREREG v2 S5.1 for one lock file, with repository paths resolved under `repo`. Prints one JSON line; 0 = pass."""
    repo = Path(repo)
    res = repo / "research" / "ledger"
    path = Path(path)
    rec = json.loads(path.read_text(encoding="utf-8"))
    changed, missing, snap_changed, amended, n, n_archive = [], [], [], [], 0, 0
    if path.name in V1_LOCKS:  # amendments never count for v1 locks (PREREG v2 S5.1)
        chains, ignored = {}, []
    else:
        chains, ignored = _chains(repo)
    p4b_binding = set(P4B) if path.name == "LOCK_prereg_v2.json" else set()  # P4b files of the prereg snapshot are binding

    def walk(d, binding):
        nonlocal n, n_archive
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v, binding)
            elif _is_sha(v) and ("/" in k or k.endswith((".json", ".md"))):
                if ".zip:" in k:
                    n_archive += 1
                    continue
                p = repo / k
                n += 1
                if not p.exists():
                    (missing if binding else snap_changed).append(k)
                elif sha(p) != v:
                    if binding and _chain_ok(k, v, sha(p), chains):
                        amended.append(k)
                    else:
                        (changed if binding else snap_changed).append(k)
    for sec, val in rec.items():
        if isinstance(val, dict):
            if sec in SNAPSHOT_SECTIONS and p4b_binding:
                walk({k: v for k, v in val.items() if k in p4b_binding}, True)
                walk({k: v for k, v in val.items() if k not in p4b_binding}, False)
            else:
                walk(val, sec not in SNAPSHOT_SECTIONS)
    for key, fname in CHAINED.items():
        if key in rec:
            n += 1
            p = res / fname
            if not p.exists():
                missing.append(fname)
            elif sha(p) != rec[key]:
                changed.append(fname)
    print(json.dumps({"lock": path.name, "n_checked": n, "changed": changed, "missing": missing, "amended": amended,
                      "snapshot_changed_reported_only": snap_changed, "archive_members_skipped": n_archive,
                      "amendment_rows_ignored": ignored}))
    return 1 if (changed or missing) else 0


def main() -> None:
    what = sys.argv[1]
    if what == "check":
        raise SystemExit(check(Path(sys.argv[2])))
    if what == "predictions":
        args = sys.argv[2:]
        plat = args[args.index("--platform") + 1] if "--platform" in args else "unknown"
        args = [a for i, a in enumerate(args) if a != "--platform" and (i == 0 or args[i - 1] != "--platform")]
        arms = [a for a in args if "=" not in a]
        notl = dict(a.split("=", 1) for a in args if "=" in a)
        lock_predictions(arms, notl, plat)
        return
    if what == "amend":
        args = sys.argv[2:]
        amend(args[0], args[args.index("--reason") + 1], args[args.index("--old-rev") + 1] if "--old-rev" in args else "HEAD",
              "--crash-fix" in args)
        return
    {"prereg": lock_prereg, "labelcode": lock_labelcode, "scoring": lock_scoring, "labels": lock_labels}[what]()


if __name__ == "__main__":
    main()
