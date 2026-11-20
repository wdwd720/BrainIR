"""Lock files for run 2 (the frozen `lock.py` writes only the v1 file names; this is its v2 counterpart, LOG L51+).

    lock2.py prereg       -> research/ledger/LOCK_prereg_v2.json      (PREREG_v2.md, RUN2_PROMPT.md, kit_v2, v1 lock hashes, code snapshot)
    lock2.py labelcode    -> research/ledger/LOCK_labelcode_v2.json   (v2 label-side code before the first v2 session)
    lock2.py scoring      -> research/ledger/LOCK_scoring_v2.json     (v2 scoring code and tests, before any unblinding)
    lock2.py predictions ARM ... [ARM=reason ...] --platform TEXT -> research/ledger/LOCK_predictions_v2.json (additive to v1)
    lock2.py labels       -> research/ledger/LOCK_labels_v2.json
    lock2.py amend PATH --reason TEXT [--old-rev REV]   (PREREG v2 L12: records a bug-fix change of a locked code or kit file in
                               research/ledger/AMENDMENTS_v2.jsonl, before committing it; refused after UNBLIND.json exists)
    lock2.py check LOCKFILE   (every repository file hashed in a binding section is re-hashed; missing ones reported; chained
                               lock hashes re-hashed; code-snapshot sections reported only; archive members skipped; PREREG v2 S5.1)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RES = REPO / "research" / "ledger"
CODE_GLOBS = ["ledger/src/brainir_ledger/**/*.py", "ledger/scripts/*.py", "ledger/scripts/*.sh", "ledger/tests/*.py", "ledger/pyproject.toml",
              "ledger/uv.lock", ".github/workflows/*.yml", ".github/ledger_gha_pub.pem"]
LABEL_CODE = ["ledger/scripts/labels2_*.py", "ledger/scripts/lock2.py", "ledger/scripts/labels_collect.py", "ledger/scripts/labels_prepare.py",
              "ledger/scripts/labels_audit.py", "ledger/scripts/labels_rooms.py", "ledger/src/brainir_ledger/labels/*.py"]
V1_LOCKS = ["LOCK_prereg_v1.json", "LOCK_predictions_v1.json", "LOCK_labels_v1.json", "LOCK_labels_v1_1.json"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def hashes(paths) -> dict[str, str]:
    return {rel(p): sha(p) for p in sorted(set(paths)) if p.is_file() and not p.name.startswith(".")}


SNAPSHOT_SECTIONS = ("prediction_code_snapshot", "code_snapshot")
AMEND = RES / "AMENDMENTS_v2.jsonl"
V2_MANIFESTS = Path.home() / "ledger_rooms" / "run2" / "_manifests"


def _chains() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if AMEND.exists():
        for line in AMEND.read_text(encoding="utf-8").splitlines():
            if line.strip():
                a = json.loads(line)
                out.setdefault(a["path"], {})[a["old"]] = a["new"]
    return out


def _chain_ok(path: str, locked: str, current: str, chains: dict) -> bool:
    """True if recorded amendments lead from the locked hash to the current one (PREREG v2 L12)."""
    h, seen = locked, set()
    while h in chains.get(path, {}) and h not in seen:
        seen.add(h)
        h = chains[path][h]
        if h == current:
            return True
    return False


def amend(path: str, reason: str, old_rev: str = "HEAD") -> None:
    if (RES / "UNBLIND.json").exists():
        raise SystemExit("no amendment after unblinding (PREREG v2 L12)")
    p = REPO / path
    is_kit = path.startswith("research/ledger/kit_v2/")
    is_code = (path.startswith(("ledger/", ".github/")) and p.suffix in (".py", ".sh", ".toml", ".yml", ".lock")) \
        or path == "research/ledger/IMPLEMENTATION_v2.md"
    if not (is_kit or is_code) or not p.is_file():
        raise SystemExit(f"{path}: only code, the implementation map and kit files can be amended (never rules, records, labels, predictions)")
    started = V2_MANIFESTS.exists() and any(V2_MANIFESTS.glob("*.json"))
    if is_kit and started:
        raise SystemExit("kit files can be amended only before the first v2 label session (PREREG v2 L12)")
    blob = subprocess.run(["git", "show", f"{old_rev}:{path}"], cwd=REPO, capture_output=True).stdout
    old, new = hashlib.sha256(blob).hexdigest(), sha(p)
    if old == new:
        raise SystemExit(f"{path} is unchanged relative to {old_rev}")
    recs = any(f.stat().st_size > 0 for f in (RES / "labels_v2" / "raw" / "pass1").glob("*/records.valid.jsonl"))
    row = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "path": path, "old": old, "new": new, "reason": reason,
           "old_rev": git("rev-parse", old_rev), "v2_sessions_started": started, "v2_records_existed": recs}
    with AMEND.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row))


def tracked() -> set[str]:
    return set(subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.splitlines())


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


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def base(stage: str) -> dict:
    return {"stage": stage, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_head": git("rev-parse", "HEAD"),
            "git_dirty_ledger_paths": git("status", "--porcelain", "--", "ledger", "research/ledger", ".github").splitlines(),
            "v1_locks": {f"research/ledger/{n}": sha(RES / n) for n in V1_LOCKS}}


def write(name: str, rec: dict) -> None:
    p = RES / name
    p.write_text(json.dumps(rec, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    print(p.name, sha(p), "dirty:", rec["git_dirty_ledger_paths"])


def lock_prereg() -> None:
    rec = base("prereg_v2")
    rec["prereg_v2"] = hashes([RES / "PREREG_v2.md", RES / "RUN2_PROMPT.md"])
    rec["kit_v2"] = hashes((RES / "kit_v2").glob("*"))
    rec["gates_v2_at_freeze"] = hashes((RES / "gates_v2").glob("*"))
    rec["reviews_v2_at_freeze"] = hashes((RES / "reviews_v2").glob("*"))
    rec["untracked_code_not_hashed"] = []
    rec["code_snapshot"] = globs(CODE_GLOBS, rec["untracked_code_not_hashed"])
    write("LOCK_prereg_v2.json", rec)


def lock_labelcode() -> None:
    rec = base("labelcode_v2")
    rec["implementation_map"] = hashes([RES / "IMPLEMENTATION_v2.md"])
    rec["untracked_code_not_hashed"] = []
    rec["label_code"] = globs(LABEL_CODE + ["ledger/scripts/gate_v2.py"], rec["untracked_code_not_hashed"])
    rec["kit_v2"] = hashes((RES / "kit_v2").glob("*"))
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_labelcode_v2.json", rec)


def lock_scoring() -> None:
    rec = base("scoring_v2")
    rec["untracked_code_not_hashed"] = []
    rec["scoring_code"] = globs(["ledger/src/brainir_ledger/scoring/*.py", "ledger/src/brainir_ledger/scoring_v2/*.py",
                                 "ledger/scripts/score_v2.py", "ledger/scripts/gate_v2.py", "ledger/tests/test_scoring_v2*.py"],
                                rec["untracked_code_not_hashed"])
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_scoring_v2.json", rec)


def lock_predictions(arms: list[str], not_locked: dict[str, str], platform: str) -> None:
    rec = base("predictions_v2")
    rec["arms_locked"] = {a: hashes((RES / "predictions_v2" / a).glob("*")) for a in arms}
    rec["arms_not_locked"] = not_locked
    rec["marking"] = "locked after labels v1 existed, before any unblinding"
    rec["platform"] = platform
    rec["gates_v2"] = hashes((RES / "gates_v2").glob("*"))
    rec["reviews_v2"] = hashes((RES / "reviews_v2").glob("*"))
    rec["untracked_code_not_hashed"] = []
    rec["code"] = globs(CODE_GLOBS, rec["untracked_code_not_hashed"])
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_predictions_v2.json", rec)


def lock_labels() -> None:
    L = RES / "labels_v2"
    rec = base("labels_v2")
    rec["labels"] = hashes(L.glob("*"))
    rec["raw"] = hashes(L.glob("raw/**/*"))
    rec["sessions"] = hashes(L.glob("sessions/*"))
    rec["work_inputs"] = hashes(L.glob("work/**/*"))
    rec["kit_v2"] = hashes((RES / "kit_v2").glob("*"))
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    rec["labelcode_v2_lock_sha256"] = sha(RES / "LOCK_labelcode_v2.json")
    write("LOCK_labels_v2.json", rec)


def check(path: Path) -> int:
    rec = json.loads(path.read_text(encoding="utf-8"))
    changed, missing, snap_changed, amended, n, n_archive = [], [], [], [], 0, 0
    chains = _chains()

    def walk(d, binding):
        nonlocal n, n_archive
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v, binding)
            elif isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v) and ("/" in k or k.endswith((".json", ".md"))):
                if ".zip:" in k:
                    n_archive += 1
                    continue
                p = REPO / k
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
            walk(val, sec not in SNAPSHOT_SECTIONS)
    chained = {"prereg_lock_sha256": "LOCK_prereg_v1.json", "prereg_v2_lock_sha256": "LOCK_prereg_v2.json",
               "labelcode_v2_lock_sha256": "LOCK_labelcode_v2.json", "labels_v1_lock_sha256": "LOCK_labels_v1.json"}
    for key, fname in chained.items():
        if key in rec:
            n += 1
            p = RES / fname
            if not p.exists():
                missing.append(fname)
            elif sha(p) != rec[key]:
                changed.append(fname)
    print(json.dumps({"lock": path.name, "n_checked": n, "changed": changed, "missing": missing, "amended": amended,
                      "snapshot_changed_reported_only": snap_changed, "archive_members_skipped": n_archive}))
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
        amend(args[0], args[args.index("--reason") + 1], args[args.index("--old-rev") + 1] if "--old-rev" in args else "HEAD")
        return
    {"prereg": lock_prereg, "labelcode": lock_labelcode, "scoring": lock_scoring, "labels": lock_labels}[what]()


if __name__ == "__main__":
    main()
