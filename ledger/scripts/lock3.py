"""Run 3 locks (PREREG v3 Part X): new lock files written with run 2's helpers (`lock2.py`, frozen, imported unchanged) and checked
with run 2's walk, but with run 3's OWN amendment ledger (`AMENDMENTS_v3.jsonl`) and rules for the run 3 locks; run 2's amendment
rows never count for a run 3 lock, and run 3's rows never count for a v1/v2 lock.

    lock3.py prereg          # LOCK_prereg_v3.json   (the freeze; then labelcode, then the tag)
    lock3.py labelcode       # LOCK_labelcode_h1.json (label code + kit v3; chained to the prereg lock)
    lock3.py predictions --platform P            # LOCK_predictions_h1.json: H-M, H-M-s0-3 and all eight H-S arms, before any h1 session
    lock3.py predictions-b ARM ... [ARM=reason ...] --platform P   # LOCK_predictions_h1b.json: H-D, H-C, sensitivity arms
    lock3.py labels          # LOCK_labels_h1.json
    lock3.py reliability     # LOCK_reliability_v1.json
    lock3.py amend PATH --reason TEXT [--old-rev REV] [--crash-fix]
    lock3.py check research/ledger/LOCK_x.json   # v3 locks: v3 amendment rows only; other locks: run 2's check unchanged

Amendment rules (PREREG v3 Part X): code or kit v3 files only, never a file any v1 or v2 lock hashes; after `UNBLIND_h1.json` exists
(or its retired copy) only a `--crash-fix` of the h1 scoring code; once `LOCK_predictions_h1.json` exists, never the prediction-side
or scoring code; once the first h1 label session has started, never the label code or the kit. `check` honours a row only if it
obeys the rules with the flags it recorded AND with the commit times of the predictions lock and the flag and the first session.
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

RES = L2.RES
REPO = L2.REPO
CODE_GLOBS = L2.CODE_GLOBS
LABEL_CODE_H1 = ["ledger/scripts/labels3_*.py", "ledger/scripts/gate_h1.py", "ledger/src/brainir_ledger/labels_h1/**/*.py",
                 "ledger/src/brainir_ledger/labels_h1/*.py", "ledger/tests/test_labels3*.py", "ledger/tests/test_gate_h1*.py"]
KIT_V3 = ["research/ledger/kit_v3/*"]
SCORING_H1 = ["ledger/src/brainir_ledger/scoring_h1/*.py", "ledger/scripts/score_h1.py"]
PREDICTION_SIDE = SCORING_H1 + ["ledger/src/brainir_ledger/groups_h1.py", "ledger/scripts/predict_h1.py",
                                "ledger/src/brainir_ledger/typescreen_v3.py", "ledger/src/brainir_ledger/jobs_v3.py", "ledger/scripts/gha3.py",
                                "ledger/scripts/gha_runner3.py", ".github/workflows/ledger-gha3.yml", "ledger/scripts/gha3r.py"]
EARLIER = ["LOCK_prereg_v1.json", "LOCK_predictions_v1.json", "LOCK_labels_v1.json", "LOCK_labels_v1_1.json", "LOCK_prereg_v2.json",
           "LOCK_labelcode_v2.json", "LOCK_scoring_v2.json", "LOCK_predictions_v2.json", "LOCK_labels_v2.json"]
V3_LOCKS = ("LOCK_prereg_v3.json", "LOCK_labelcode_h1.json", "LOCK_predictions_h1.json", "LOCK_predictions_h1b.json", "LOCK_labels_h1.json",
            "LOCK_reliability_v1.json")
PRIMARY_ARMS = ["H-M", "H-M-s0-3", "H-S-k0", "H-S-k1-signed", "H-S-k1-unsigned", "H-S-k2-signed", "H-S-k2-unsigned", "H-S-k3-signed",
                "H-S-k3-unsigned", "H-S-lin"]
SECONDARY_ARMS = ([f"H-D-{c}" for c in (128, 256, 384, 512)] + [f"H-C-rewire-{s}" for s in (101, 102, 103, 104, 105)]
                  + [f"H-C-classshuffle-{s}" for s in (201, 202, 203, 204, 205)] + [f"H-M-S-{v}" for v in ("all", "post", "T1", "T2", "T3", "L", "R")])
AMEND3 = RES / "AMENDMENTS_v3.jsonl"
FLAGS3 = ("predictions_locked", "h1_sessions_started", "unblinded", "crash_fix")
H1_MANIFESTS = Path.home() / "ledger_rooms" / "run3" / "_manifests"
UNBLIND_FILES = ("research/ledger/UNBLIND_h1.json", "research/ledger/results/run3/UNBLIND_h1_used.json")
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
    L2._require_tracked(ps, "run 3")
    return {L2.rel(p): L2.sha(p) for p in ps}


def _chain(*names: str) -> dict[str, str]:
    L2._require_present(*names)
    return {f"research/ledger/{n}": L2.sha(RES / n) for n in names}


def _code(globs, exclude=()) -> dict[str, str]:
    untracked: list = []
    out = {k: v for k, v in L2.globs(globs, untracked).items() if not _matches(k, exclude)}
    bad = [u for u in untracked if not _matches(u, exclude)]
    if bad:
        raise SystemExit(f"refused: untracked code would not be hashed: {bad[:10]} (git add it first); nothing written")
    return out


# ------------------------------------------------------------------------------------------------ amendments (v3)
def _earlier_hashed(repo: Path = REPO) -> set[str] | None:
    """Every path a v1 or v2 lock hashes: never amended by a v3 row (frozen things stay frozen)."""
    out: set[str] = set()

    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v)
            elif L2._is_sha(v) and "/" in k:
                out.add(k)
    for n in EARLIER:
        try:
            walk(json.loads((Path(repo) / "research" / "ledger" / n).read_text(encoding="utf-8")))
        except (OSError, ValueError, AttributeError):
            return None
    return out


def amendable_kind3(path) -> str | None:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in PurePosixPath(path).parts:
        return None
    if _matches(path, KIT_V3):
        return "kit"
    if path.startswith(("ledger/", ".github/")) and PurePosixPath(path).suffix in (".py", ".sh", ".toml", ".yml", ".lock"):
        return "code"
    return None


def row_problem3(row, earlier: set[str] | None, times: dict | None = None) -> str | None:
    """None when a row of AMENDMENTS_v3.jsonl may count, else why not. `times` (commit times from git) adds order checks."""
    if not isinstance(row, dict):
        return "not a JSON object"
    path = row.get("path")
    kind = amendable_kind3(path)
    if kind is None:
        return "not a v3-amendable path (ledger code or kit v3)"
    if earlier is None:
        return "an earlier lock is missing or unreadable: no amendment counts"
    if path in earlier:
        return "hashed by a v1 or v2 lock: never amended"
    if not (L2._is_sha(row.get("old")) and L2._is_sha(row.get("new"))):
        return "old / new are not SHA-256 values"
    if not all(isinstance(row.get(k), bool) for k in FLAGS3):
        return f"lacks the flags ({', '.join(FLAGS3)})"
    if times:
        t = times.get("row_utc")
        if t is None:
            return "the row has no valid utc"
        for flag, key in (("predictions_locked", "predictions_lock"), ("unblinded", "unblind"), ("h1_sessions_started", "first_session")):
            if times.get(key) is not None and t >= times[key] and not row[flag]:
                return f"recorded {flag}=false although the row is later than the {key.replace('_', ' ')}"
    scoring = _matches(path, SCORING_H1)
    if row["unblinded"]:
        return None if (row["crash_fix"] and scoring) else "after unblinding only a crash fix of the h1 scoring code"
    if row["predictions_locked"] and _matches(path, PREDICTION_SIDE):
        return "the prediction-side and scoring code are frozen once LOCK_predictions_h1.json exists"
    if row["h1_sessions_started"] and (kind == "kit" or _matches(path, LABEL_CODE_H1)):
        return "the label code and kit v3 are frozen once the first h1 label session has started"
    return None


def _first_commit_utc(rel: str, repo: Path = REPO) -> int | None:
    out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "--", rel], cwd=repo, capture_output=True, text=True).stdout
    xs = [int(x) for x in out.split()]
    return min(xs) if xs else None


def _first_session_utc(repo: Path = REPO) -> int | None:
    starts = []
    for m in sorted((Path(repo) / "research" / "ledger" / "labels_h1" / "sessions").glob("*.json")):
        for run in json.loads(m.read_text(encoding="utf-8")).get("runs", []):
            t = _utc(run.get("start_utc"))
            if t is not None:
                starts.append(t)
    if H1_MANIFESTS.exists():
        for m in H1_MANIFESTS.glob("*.json"):
            for run in json.loads(m.read_text(encoding="utf-8")).get("runs", []):
                t = _utc(run.get("start_utc"))
                if t is not None:
                    starts.append(t)
    return min(starts) if starts else None


def _times(repo: Path = REPO) -> dict:
    unb = [t for t in (_first_commit_utc(r, repo) for r in UNBLIND_FILES) if t is not None]
    return {"predictions_lock": _first_commit_utc("research/ledger/LOCK_predictions_h1.json", repo), "unblind": min(unb) if unb else None,
            "first_session": _first_session_utc(repo)}


def rows3(repo: Path = REPO) -> list[tuple[int, object, str | None]]:
    p = Path(repo) / "research" / "ledger" / "AMENDMENTS_v3.jsonl"
    if not p.exists():
        return []
    earlier, base, out = _earlier_hashed(repo), _times(repo), []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out.append((i, None, "invalid JSON"))
            continue
        out.append((i, row, row_problem3(row, earlier, {**base, "row_utc": _utc(row.get("utc")) if isinstance(row, dict) else None})))
    return out


def _chains3(repo: Path = REPO):
    chains, ignored = {}, []
    for i, row, problem in rows3(repo):
        if problem:
            ignored.append({"line": i, "path": row.get("path") if isinstance(row, dict) else None, "problem": problem})
            continue
        succ = chains.setdefault(row["path"], {}).setdefault(row["old"], [])
        if row["new"] not in succ:
            succ.append(row["new"])
    return chains, ignored


def amend(path: str, reason: str, old_rev: str = "HEAD", crash_fix: bool = False) -> None:
    p = REPO / path
    if amendable_kind3(path) is None or not p.is_file():
        raise SystemExit(f"{path}: only ledger code and kit v3 files can be amended (never rules, labels, predictions)")
    shown = subprocess.run(["git", "show", f"{old_rev}:{path}"], cwd=REPO, capture_output=True, check=False)
    if shown.returncode != 0:
        raise SystemExit(f"{path} does not exist at {old_rev}: nothing to amend")
    old, new = hashlib.sha256(shown.stdout).hexdigest(), L2.sha(p)
    if old == new:
        raise SystemExit(f"{path} is unchanged relative to {old_rev}")
    row = {"utc": time.strftime(UTC, time.gmtime()), "path": path, "old": old, "new": new, "reason": reason,
           "old_rev": L2.git("rev-parse", old_rev), "predictions_locked": (RES / "LOCK_predictions_h1.json").exists(),
           "h1_sessions_started": H1_MANIFESTS.exists() and any(H1_MANIFESTS.glob("*.json")),
           "unblinded": any((REPO / r).exists() for r in UNBLIND_FILES), "crash_fix": bool(crash_fix)}
    problem = row_problem3(row, _earlier_hashed(), {**_times(), "row_utc": _utc(row["utc"])})
    if problem:
        raise SystemExit(f"refused: {problem} (PREREG v3 Part X)")
    with AMEND3.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row))


def check(path: Path, repo: Path = REPO) -> int:
    """v3 locks: run 2's walk with v3 amendment rows only; any other lock: run 2's check unchanged."""
    if Path(path).name not in V3_LOCKS:
        return L2.check(Path(path), repo)
    orig = L2._chains
    L2._chains = _chains3
    try:
        return L2.check(Path(path), repo)
    finally:
        L2._chains = orig


# ------------------------------------------------------------------------------------------------ the locks
def lock_prereg() -> None:
    L2._require_absent("LOCK_prereg_v3.json")
    rec = L2.base("prereg_v3")
    rec["prereg_v3"] = _section([RES / "PREREG_v3.md", RES / "RUN3_PROMPT.md"])
    rec["units"] = _section((RES / "hl_units").glob("*"))
    rec["motor_map"] = _section((RES / "motor_map").glob("*"))
    rec["diag_v3"] = _section((RES / "diag_v3").glob("*"))
    rec["gates_v3_at_freeze"] = _section((RES / "gates_v3").glob("*"))
    rec["reviews_v3_at_freeze"] = _section((RES / "reviews_v3").glob("*"))
    rec["earlier_locks"] = _chain(*EARLIER)
    rec["code"] = _code(CODE_GLOBS, LABEL_CODE_H1)  # binding: prediction side, scoring h1, harness, tools (label code: labelcode_h1)
    rec["code_scope"] = ("every git-tracked file matching lock2.CODE_GLOBS at the freeze except run 3's label code (LABEL_CODE_H1, "
                         "bound by LOCK_labelcode_h1.json, written right after this lock and before the tag); binding")
    L2.write("LOCK_prereg_v3.json", rec)


def lock_labelcode() -> None:
    L2._require_absent("LOCK_labelcode_h1.json")
    rec = L2.base("labelcode_h1")
    rec["label_code_h1"] = _code(LABEL_CODE_H1)
    rec["kit_v3"] = _section((RES / "kit_v3").glob("*"))
    plan = [p for p in (RES / "labels_h1" / "plan.json", RES / "labels_h1" / "known_sources.csv", RES / "labels_h1" / "registry_main.csv")
            if p.is_file()]
    rec["label_plan"] = _section(plan + sorted((RES / "labels_h1" / "specs").glob("*")))
    rec["chained"] = _chain("LOCK_prereg_v3.json")
    L2.write("LOCK_labelcode_h1.json", rec)


def _arms(arms) -> dict:
    out = {a: _section((RES / "predictions_h1" / a).glob("*")) for a in arms}
    for a, files in out.items():
        if f"research/ledger/predictions_h1/{a}/predicted.csv" not in files:
            raise SystemExit(f"{a}: no predicted.csv; nothing written")
    return out


def lock_predictions(platform: str) -> None:
    """PREREG v3 P10: the primary lock holds H-M, H-M-s0-3 and all eight H-S arms (never dropped, never a subset), written and
    committed before the first h1 label session."""
    L2._require_absent("LOCK_predictions_h1.json")
    if _first_session_utc() is not None:
        raise SystemExit("an h1 label session has started: the primary predictions lock must precede it (PREREG v3 P10); refused")
    rec = L2.base("predictions_h1")
    rec["arms_locked"] = _arms(PRIMARY_ARMS)
    rec["platform"] = platform
    rec["gates_v3"] = _section((RES / "gates_v3").glob("*"))
    rec["reviews_v3"] = _section((RES / "reviews_v3").glob("*"))
    rec["code"] = _code(CODE_GLOBS, LABEL_CODE_H1)
    rec["chained"] = _chain("LOCK_prereg_v3.json", "LOCK_labelcode_h1.json")
    rec["marking"] = "exam 2 primary predictions, locked before the first h1 label session and before any unblinding"
    L2.write("LOCK_predictions_h1.json", rec)


def lock_predictions_b(arms: list[str], not_locked: dict[str, str], platform: str) -> None:
    """The descriptive arms (H-D, H-C, sensitivity groups), before LOCK_labels_h1.json; every secondary arm is either locked or
    named with a reason."""
    L2._require_absent("LOCK_predictions_h1b.json")
    if (RES / "LOCK_labels_h1.json").exists():
        raise SystemExit("LOCK_labels_h1.json exists: the secondary predictions lock must precede it; refused")
    bad = sorted((set(arms) | set(not_locked)) - set(SECONDARY_ARMS))
    missing = sorted(set(SECONDARY_ARMS) - set(arms) - set(not_locked))
    if bad or missing:
        raise SystemExit(f"arms not secondary: {bad}; secondary arms neither locked nor explained: {missing}; nothing written")
    rec = L2.base("predictions_h1b")
    rec["arms_locked"] = _arms(arms)
    rec["arms_not_locked"] = not_locked
    rec["platform"] = platform
    rec["gates_v3"] = _section((RES / "gates_v3").glob("*"))
    rec["chained"] = _chain("LOCK_prereg_v3.json", "LOCK_predictions_h1.json")
    rec["marking"] = "exam 2 descriptive arms, locked before LOCK_labels_h1.json and before any unblinding"
    L2.write("LOCK_predictions_h1b.json", rec)


def lock_labels() -> None:
    L2._require_absent("LOCK_labels_h1.json")
    rec = L2.base("labels_h1")
    lab = RES / "labels_h1"
    rec["labels"] = _section(lab.glob("*"))
    for need in ("consensus.csv", "records.csv", "pairs.csv", "agreement.json", "verification.json", "transcript_audit.json"):
        if f"research/ledger/labels_h1/{need}" not in rec["labels"]:
            raise SystemExit(f"labels_h1/{need} missing; nothing written (PREREG v3 T8-T9: assembly, verification and audit first)")
    rec["raw"] = _section(lab.glob("raw/**/*"))
    rec["sessions"] = _section(lab.glob("sessions/*"))
    rec["work"] = _section(lab.glob("work/**/*"))
    rec["specs"] = _section(lab.glob("specs/*"))
    rec["verify"] = _section(lab.glob("verify/**/*"))
    review = RES / "reviews_v3" / "LABEL_REVIEW_h1.md"
    if not review.is_file():
        raise SystemExit("reviews_v3/LABEL_REVIEW_h1.md missing: the label review precedes the labels lock; nothing written")
    rec["label_review"] = _section([review])
    rec["kit_v3"] = _section((RES / "kit_v3").glob("*"))
    rec["chained"] = _chain("LOCK_prereg_v3.json", "LOCK_labelcode_h1.json")
    L2.write("LOCK_labels_h1.json", rec)


def lock_reliability() -> None:
    L2._require_absent("LOCK_reliability_v1.json")
    rec = L2.base("reliability_v1")
    rec["reliability"] = _section((RES / "reliability_v1").glob("**/*"))
    rec["code"] = _code(CODE_GLOBS, LABEL_CODE_H1)
    rec["chained"] = _chain("LOCK_prereg_v3.json")
    L2.write("LOCK_reliability_v1.json", rec)


def main() -> None:
    what = sys.argv[1]
    args = sys.argv[2:]
    if what == "check":
        raise SystemExit(check(Path(args[0])))
    if what == "amend":
        amend(args[0], args[args.index("--reason") + 1], args[args.index("--old-rev") + 1] if "--old-rev" in args else "HEAD",
              "--crash-fix" in args)
        return
    plat = args[args.index("--platform") + 1] if "--platform" in args else "unknown"
    rest = [a for i, a in enumerate(args) if a != "--platform" and (i == 0 or args[i - 1] != "--platform")]
    if what == "predictions":
        lock_predictions(plat)
        return
    if what == "predictions-b":
        lock_predictions_b([a for a in rest if "=" not in a], dict(a.split("=", 1) for a in rest if "=" in a), plat)
        return
    {"prereg": lock_prereg, "labelcode": lock_labelcode, "labels": lock_labels, "reliability": lock_reliability}[what]()


if __name__ == "__main__":
    main()
