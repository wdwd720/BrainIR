"""Run 3 locks (PREREG v3): new lock files written with run 2's helpers (`lock2.py`, frozen, imported unchanged), checked with
run 2's `check` (every hashed path in every section is binding unless the section is a snapshot section; amendments as v2 L12).

    uv run --project ledger --no-sync python ledger/scripts/lock3.py prereg                 # LOCK_prereg_v3.json (Stage 1 freeze)
    uv run --project ledger --no-sync python ledger/scripts/lock3.py labelcode              # LOCK_labelcode_h1.json (before label sessions)
    uv run --project ledger --no-sync python ledger/scripts/lock3.py predictions H-M ... [ARM=reason ...] --platform P
    uv run --project ledger --no-sync python ledger/scripts/lock3.py labels                 # LOCK_labels_h1.json
    uv run --project ledger --no-sync python ledger/scripts/lock3.py reliability            # LOCK_reliability_v1.json
    uv run --project ledger --no-sync python ledger/scripts/lock3.py check research/ledger/LOCK_prereg_v3.json

A lock file is written once (never overwritten, never if it was committed before) and only from git-tracked files. Earlier locks
are chained by hash in a section keyed by their repository path, so `check` verifies them too.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lock2 as L2  # noqa: E402

RES = L2.RES
CODE_GLOBS = L2.CODE_GLOBS
LABEL_CODE_H1 = ["ledger/scripts/labels3_*.py", "ledger/scripts/gate_h1.py", "ledger/src/brainir_ledger/labels_h1/*.py",
                 "ledger/tests/test_labels3*.py", "ledger/tests/test_gate_h1*.py"]
SCORING_H1 = ["ledger/src/brainir_ledger/scoring_h1/*.py", "ledger/scripts/score_h1.py", "ledger/tests/test_scoring_h1*.py",
              "ledger/tests/test_label_side_isolation_h1.py"]
EARLIER = ["LOCK_prereg_v1.json", "LOCK_predictions_v1.json", "LOCK_labels_v1.json", "LOCK_labels_v1_1.json", "LOCK_prereg_v2.json",
           "LOCK_labelcode_v2.json", "LOCK_scoring_v2.json", "LOCK_predictions_v2.json", "LOCK_labels_v2.json"]


def _section(paths) -> dict[str, str]:
    ps = L2._hashable(paths)
    L2._require_tracked(ps, "run 3")
    return {L2.rel(p): L2.sha(p) for p in ps}


def _chain(*names: str) -> dict[str, str]:
    L2._require_present(*names)
    return {f"research/ledger/{n}": L2.sha(RES / n) for n in names}


def _code(globs, exclude=()) -> dict[str, str]:
    untracked: list = []
    out = {k: v for k, v in L2.globs(globs, untracked).items() if not L2._matches(k, exclude)}
    bad = [u for u in untracked if not L2._matches(u, exclude)]
    if bad:
        raise SystemExit(f"refused: untracked code would not be hashed: {bad[:10]} (git add it first); nothing written")
    return out


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
                         "bound by LOCK_labelcode_h1.json); binding (lock2.check)")
    L2.write("LOCK_prereg_v3.json", rec)


def lock_labelcode() -> None:
    L2._require_absent("LOCK_labelcode_h1.json")
    rec = L2.base("labelcode_h1")
    rec["label_code_h1"] = _code(LABEL_CODE_H1)
    rec["kit_v3"] = _section((RES / "kit_v3").glob("*"))
    rec["chained"] = _chain("LOCK_prereg_v3.json")
    L2.write("LOCK_labelcode_h1.json", rec)


def lock_predictions(arms: list[str], not_locked: dict[str, str], platform: str) -> None:
    L2._require_absent("LOCK_predictions_h1.json")
    rec = L2.base("predictions_h1")
    rec["arms_locked"] = {a: _section((RES / "predictions_h1" / a).glob("*")) for a in arms}
    for a, files in rec["arms_locked"].items():
        if f"research/ledger/predictions_h1/{a}/predicted.csv" not in files:
            raise SystemExit(f"{a}: no predicted.csv; nothing written")
    rec["arms_not_locked"] = not_locked
    rec["platform"] = platform
    rec["gates_v3"] = _section((RES / "gates_v3").glob("*"))
    rec["reviews_v3"] = _section((RES / "reviews_v3").glob("*"))
    rec["code"] = _code(CODE_GLOBS, LABEL_CODE_H1)
    rec["chained"] = _chain("LOCK_prereg_v3.json")
    rec["marking"] = "exam 2 predictions, locked before LOCK_labels_h1.json exists and before any unblinding"
    L2.write("LOCK_predictions_h1.json", rec)


def lock_labels() -> None:
    L2._require_absent("LOCK_labels_h1.json")
    rec = L2.base("labels_h1")
    lab = RES / "labels_h1"
    rec["labels"] = _section(lab.glob("*"))
    for need in ("consensus.csv", "records.csv"):
        if f"research/ledger/labels_h1/{need}" not in rec["labels"]:
            raise SystemExit(f"labels_h1/{need} missing; nothing written")
    rec["raw"] = _section(lab.glob("raw/**/*"))
    rec["sessions"] = _section(lab.glob("sessions/*"))
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
    if what == "check":
        raise SystemExit(L2.check(Path(sys.argv[2])))
    if what == "predictions":
        args = sys.argv[2:]
        plat = args[args.index("--platform") + 1] if "--platform" in args else "unknown"
        args = [a for i, a in enumerate(args) if a != "--platform" and (i == 0 or args[i - 1] != "--platform")]
        lock_predictions([a for a in args if "=" not in a], dict(a.split("=", 1) for a in args if "=" in a), plat)
        return
    {"prereg": lock_prereg, "labelcode": lock_labelcode, "labels": lock_labels, "reliability": lock_reliability}[what]()


if __name__ == "__main__":
    main()
