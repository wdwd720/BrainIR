"""Write a ledger lock file (hashes of everything a stage froze).

    uv run --project ledger --no-sync python ledger/scripts/lock.py prereg        # -> research/ledger/LOCK_prereg_v1.json
    uv run --project ledger --no-sync python ledger/scripts/lock.py predictions   # -> research/ledger/LOCK_predictions_v1.json
    uv run --project ledger --no-sync python ledger/scripts/lock.py labels        # -> research/ledger/LOCK_labels_v1.json
    uv run --project ledger --no-sync python ledger/scripts/lock.py check <lockfile>
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import REPO, RESEARCH  # noqa: E402

CODE_GLOBS = ["ledger/src/brainir_ledger/**/*.py", "ledger/scripts/*.py", "ledger/scripts/*.sh", "ledger/tests/*.py", "ledger/pyproject.toml",
              "ledger/uv.lock"]
# code frozen by the pre-registration: the join (scoring), the label side, the lock itself, and their tests. Prediction-side
# code is recorded as a snapshot in the prereg lock and frozen by the predictions lock (PREREG 12).
FROZEN_AT_PREREG = ["ledger/src/brainir_ledger/scoring/*.py", "ledger/src/brainir_ledger/labels/*.py", "ledger/src/brainir_ledger/__init__.py",
                    "ledger/scripts/labels_*.py", "ledger/scripts/build_kit.py", "ledger/scripts/lock.py", "ledger/tests/conftest.py",
                    "ledger/tests/test_stats.py", "ledger/tests/test_unblind_guard.py", "ledger/tests/test_labels.py",
                    "ledger/tests/test_label_isolation.py", "ledger/tests/test_audit.py", "ledger/tests/test_label_workflow_e2e.py"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def hashes(paths) -> dict[str, str]:
    """SHA-256 of regular files; dot-files (e.g. .DS_Store, never committed) are skipped."""
    return {rel(p): sha(p) for p in sorted(paths) if p.is_file() and not p.name.startswith(".")}


def code_hashes(globs=None) -> dict[str, str]:
    out = {}
    for g in (globs or CODE_GLOBS):
        out.update(hashes(REPO.glob(g)))
    return out


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def base_record(stage: str) -> dict:
    dirty = git("status", "--porcelain", "--", "ledger", "research/ledger")
    return {"stage": stage, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_head": git("rev-parse", "HEAD"),
            "git_dirty_ledger_paths": dirty.splitlines(), "code": code_hashes()}


def lock_prereg() -> Path:
    from brainir_ledger import authors as AU
    from brainir_ledger.backend import LedgerModalBackend
    from brainir_ledger.env import fingerprint

    rec = base_record("prereg")
    snapshot = rec.pop("code")
    frozen = code_hashes(FROZEN_AT_PREREG)
    rec.update({
        "frozen_code": frozen,
        "prediction_code_snapshot": {k: v for k, v in snapshot.items() if k not in frozen},
        "prereg": hashes([RESEARCH / "PREREG.md", RESEARCH / "RUN1_PROMPT.md"]),
        "kit_version": 1,
        "kit": hashes((RESEARCH / "kit").glob("*")),
        "reviews": hashes((RESEARCH / "reviews").glob("*")),
        "authors_files_pinned": AU.FILES, "authors_zenodo_configs_pinned": AU.ZENODO_CONFIGS,
        "pre_freeze_evidence": hashes(list((RESEARCH / "gates").glob("G3_*")) + list((RESEARCH / "calibration").glob("*.json"))
                                      + list((RESEARCH / "pilot").glob("*.json")) + list((RESEARCH / "g0").glob("*"))),
        "seeds": {"parameter": "0..15 (G3: 0..63)", "controls": [101, 102, 103, 104, 105, 201, 202, 203, 204, 205], "bootstrap": 20261120,
                  "permutation": 20261121, "paired_bootstrap": 20261122, "coupling_null": 20261123, "g1_sample": 20261124,
                  "adjudication_order": 20261125, "spot_check": 20261126},
        "environment": {"local": fingerprint(), "modal_image": LedgerModalBackend().image_spec()},
    })
    out = RESEARCH / "LOCK_prereg_v1.json"
    out.write_text(json.dumps(rec, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return out


def lock_predictions(arms_locked: list[str], arms_not_locked: dict[str, str]) -> Path:
    from brainir_ledger import PREDICTIONS

    rec = base_record("predictions")
    rec["arms_locked"] = {a: hashes((PREDICTIONS / a).glob("*")) for a in arms_locked}
    rec["arms_not_locked"] = arms_not_locked
    rec["gates"] = hashes((RESEARCH / "gates").glob("*"))
    rec["reviews"] = hashes((RESEARCH / "reviews").glob("*"))
    rec["prereg_lock_sha256"] = sha(RESEARCH / "LOCK_prereg_v1.json")
    out = RESEARCH / "LOCK_predictions_v1.json"
    out.write_text(json.dumps(rec, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return out


def lock_labels() -> Path:
    from brainir_ledger import LABELS

    rec = base_record("labels")
    rec["labels"] = hashes(LABELS.glob("*"))
    rec["raw"] = hashes(list(LABELS.glob("raw/*/*/*")) + list(LABELS.glob("raw/*/*/*/*")))
    rec["sessions"] = hashes(LABELS.glob("sessions/*"))
    rec["work_inputs"] = hashes(LABELS.glob("work/**/*"))
    rec["kit"] = hashes((RESEARCH / "kit").glob("*"))
    rec["prereg_lock_sha256"] = sha(RESEARCH / "LOCK_prereg_v1.json")
    out = RESEARCH / "LOCK_labels_v1.json"
    out.write_text(json.dumps(rec, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return out


def check(lockfile: Path) -> int:
    rec = json.loads(lockfile.read_text(encoding="utf-8"))
    bad = []

    def walk(d):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(v, str) and len(v) == 64 and (REPO / k).exists() and sha(REPO / k) != v:
                bad.append(k)

    # a prereg lock is checked on what it froze (frozen_code), not on the prediction-code snapshot it merely records
    for sec in ("code", "frozen_code", "prereg", "kit", "pre_freeze_evidence", "arms_locked", "gates", "reviews", "labels", "raw", "sessions",
                "work_inputs"):
        if isinstance(rec.get(sec), dict):
            walk(rec[sec])
    missing = []
    for sec in ("prereg", "kit", "labels", "sessions", "work_inputs"):
        for k in (rec.get(sec) or {}):
            if not (REPO / k).exists():
                missing.append(k)
    print(json.dumps({"lock": lockfile.name, "changed": bad, "missing": missing}))
    return 1 if (bad or missing) else 0


def main() -> None:
    what = sys.argv[1]
    if what == "check":
        raise SystemExit(check(Path(sys.argv[2])))
    if what == "prereg":
        print(lock_prereg())
    elif what == "labels":
        print(lock_labels())
    elif what == "predictions":
        # usage: lock.py predictions ARM [ARM ...] [--not-locked ARM=reason ...]
        args = sys.argv[2:]
        arms, notl = [], {}
        for a in args:
            if "=" in a:
                k, v = a.split("=", 1)
                notl[k] = v
            elif a != "--not-locked":
                arms.append(a)
        print(lock_predictions(arms, notl))
    else:
        raise SystemExit(f"unknown stage {what}")


if __name__ == "__main__":
    main()
