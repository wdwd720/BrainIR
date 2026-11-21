"""Run 3's amendment rules (PREREG v3 Part X; audit finding 1): which rows of AMENDMENTS_v3.jsonl may count."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lock3 as L3  # noqa: E402

H = "a" * 64
G = "b" * 64


def row(path, **flags):
    r = {"utc": "2026-11-21T10:00:00Z", "path": path, "old": H, "new": G, "reason": "bug"}
    r.update({k: False for k in L3.FLAGS3})
    r.update(flags)
    return r


EARLIER = {"ledger/src/brainir_ledger/jobs_v2.py"}


def test_paths():
    assert L3.row_problem3(row("ledger/src/brainir_ledger/groups_h1.py"), EARLIER) is None
    assert "never amended" in L3.row_problem3(row("ledger/src/brainir_ledger/jobs_v2.py"), EARLIER)
    assert "v3-amendable" in L3.row_problem3(row("research/ledger/PREREG_v3.md"), EARLIER)
    assert "v3-amendable" in L3.row_problem3(row("research/ledger/labels_h1/consensus.csv"), EARLIER)
    assert L3.row_problem3(row("research/ledger/kit_v3/PROTOCOL.md"), EARLIER) is None
    assert "earlier lock" in L3.row_problem3(row("ledger/scripts/gha3.py"), None)


def test_after_predictions_lock():
    for p in ("ledger/src/brainir_ledger/groups_h1.py", "ledger/src/brainir_ledger/scoring_h1/pipeline_h1.py", "ledger/scripts/predict_h1.py",
              "ledger/src/brainir_ledger/jobs_v3.py", "ledger/scripts/gha3.py"):
        assert "frozen once LOCK_predictions_h1" in L3.row_problem3(row(p, predictions_locked=True), EARLIER)
    assert L3.row_problem3(row("ledger/scripts/labels3_assemble.py", predictions_locked=True), EARLIER) is None


def test_after_sessions_started():
    for p in ("ledger/scripts/labels3_assemble.py", "ledger/src/brainir_ledger/labels_h1/core.py", "ledger/scripts/gate_h1.py",
              "research/ledger/kit_v3/PROMPT_READER.md"):
        assert "first h1 label session" in L3.row_problem3(row(p, h1_sessions_started=True), EARLIER)


def test_after_unblinding():
    assert "crash fix" in L3.row_problem3(row("ledger/src/brainir_ledger/scoring_h1/pipeline_h1.py", unblinded=True), EARLIER)
    ok = row("ledger/src/brainir_ledger/scoring_h1/pipeline_h1.py", unblinded=True, crash_fix=True, predictions_locked=True)
    assert L3.row_problem3(ok, EARLIER) is None
    assert "crash fix" in L3.row_problem3(row("ledger/src/brainir_ledger/groups_h1.py", unblinded=True, crash_fix=True), EARLIER)


def test_commit_times_override_recorded_flags():
    t_row = L3._utc("2026-11-21T10:00:00Z")
    r = row("ledger/src/brainir_ledger/groups_h1.py")  # recorded predictions_locked=False ...
    assert "later than the predictions lock" in L3.row_problem3(r, EARLIER, {"row_utc": t_row, "predictions_lock": t_row - 60})
    assert L3.row_problem3(r, EARLIER, {"row_utc": t_row, "predictions_lock": t_row + 60}) is None
    assert "later than the first session" in L3.row_problem3(row("ledger/scripts/labels3_assemble.py"), EARLIER,
                                                            {"row_utc": t_row, "first_session": t_row - 1})
    assert "not committed" in L3.row_problem3(dict(r, utc="yesterday"), EARLIER, {"row_utc": None})


def test_check_uses_v3_rows_for_v3_locks_only(monkeypatch):
    seen = []
    monkeypatch.setattr(L3.L2, "check", lambda path, repo=None: seen.append(L3.L2._chains) or 0)
    orig = L3.L2._chains
    L3.check(Path("research/ledger/LOCK_prereg_v3.json"))
    L3.check(Path("research/ledger/LOCK_prereg_v2.json"))
    assert seen[0] is L3._chains3 and seen[1] is orig and L3.L2._chains is orig


def test_recheck_probes():
    t_row = L3._utc("2026-11-21T10:00:00Z")
    # 1: a recorded unblinding without a committed flag before the row does not unlock the scoring code
    forged = row("ledger/src/brainir_ledger/scoring_h1/pipeline_h1.py", unblinded=True, crash_fix=True, predictions_locked=True)
    assert "without a committed unblinding flag" in L3.row_problem3(forged, EARLIER, {"row_utc": t_row, "unblind": None})
    assert L3.row_problem3(forged, EARLIER, {"row_utc": t_row, "unblind": t_row - 10}) is None
    # 2: the checker and its tests are never amended; the scoring tests freeze with the prediction side
    assert "never amended" in L3.row_problem3(row("ledger/scripts/lock3.py"), EARLIER)
    assert "never amended" in L3.row_problem3(row("ledger/tests/test_lock3_amend.py"), EARLIER)
    assert "frozen once LOCK_predictions_h1" in L3.row_problem3(row("ledger/tests/test_scoring_h1.py", predictions_locked=True), EARLIER)
    # 3: an uncommitted row (no commit time) never counts
    assert "not committed" in L3.row_problem3(row("ledger/scripts/labels3_assemble.py"), EARLIER, {"row_utc": None})
