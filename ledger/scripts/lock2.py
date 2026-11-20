"""Lock files for run 2 (the frozen `lock.py` writes only the v1 file names; this is its v2 counterpart, LOG L51+).

    lock2.py prereg       -> research/ledger/LOCK_prereg_v2.json      (PREREG_v2.md, RUN2_PROMPT.md, kit_v2, v1 lock hashes, code snapshot)
    lock2.py labelcode    -> research/ledger/LOCK_labelcode_v2.json   (v2 label-side code before the first v2 session)
    lock2.py scoring      -> research/ledger/LOCK_scoring_v2.json     (v2 scoring code and tests, before any unblinding)
    lock2.py predictions ARM ... [ARM=reason ...] --platform TEXT -> research/ledger/LOCK_predictions_v2.json (additive to v1)
    lock2.py labels       -> research/ledger/LOCK_labels_v2.json
    lock2.py check LOCKFILE   (every 64-hex value whose key is an existing path is re-hashed; missing paths reported)
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


def globs(gs) -> dict[str, str]:
    out = {}
    for g in gs:
        out.update(hashes(REPO.glob(g)))
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
    rec["code_snapshot"] = globs(CODE_GLOBS)
    write("LOCK_prereg_v2.json", rec)


def lock_labelcode() -> None:
    rec = base("labelcode_v2")
    rec["label_code"] = globs(LABEL_CODE)
    rec["kit_v2"] = hashes((RES / "kit_v2").glob("*"))
    rec["prereg_v2_lock_sha256"] = sha(RES / "LOCK_prereg_v2.json")
    write("LOCK_labelcode_v2.json", rec)


def lock_scoring() -> None:
    rec = base("scoring_v2")
    rec["scoring_code"] = globs(["ledger/src/brainir_ledger/scoring/*.py", "ledger/src/brainir_ledger/scoring_v2/*.py",
                                 "ledger/scripts/score_v2.py", "ledger/tests/test_scoring_v2*.py"])
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
    rec["code"] = globs(CODE_GLOBS)
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
    changed, missing, n = [], [], 0

    def walk(d):
        nonlocal n
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v) and ("/" in k or k.endswith((".json", ".md"))):
                p = REPO / k
                n += 1
                if not p.exists():
                    missing.append(k)
                elif sha(p) != v:
                    changed.append(k)
    for sec, val in rec.items():
        if isinstance(val, dict):
            walk(val)
    print(json.dumps({"lock": path.name, "n_checked": n, "changed": changed, "missing": missing}))
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
    {"prereg": lock_prereg, "labelcode": lock_labelcode, "scoring": lock_scoring, "labels": lock_labels}[what]()


if __name__ == "__main__":
    main()
