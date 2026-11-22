"""Run 4 lock tool (PREREG v4 X4-X5): amendment rules and delegation of earlier locks' checks."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import lock4 as L4  # noqa: E402

SHA = "a" * 64
SHB = "b" * 64


def _row(path="ledger/src/brainir_ledger/agree.py", **kw):
    r = {"path": path, "old": SHA, "new": SHB, "reliability_locked": False, "forward_locked": False}
    r.update(kw)
    return r


def test_amendable_paths():
    assert L4.amendable_kind4("ledger/src/brainir_ledger/agree.py") == "code"
    assert L4.amendable_kind4(".github/workflows/ledger-gha4.yml") == "code"
    assert L4.amendable_kind4("research/ledger/PREREG_v4.md") is None
    assert L4.amendable_kind4("../x.py") is None
    assert L4.amendable_kind4("/abs/x.py") is None


def test_row_rules():
    earlier = {"ledger/scripts/gha3.py"}
    assert L4.row_problem4(_row(), earlier, set()) is None
    assert "earlier lock" in L4.row_problem4(_row("ledger/scripts/gha3.py"), earlier, set())
    assert "never amended" in L4.row_problem4(_row("ledger/scripts/lock4.py"), earlier, set())
    assert "lacks the flags" in L4.row_problem4({"path": "ledger/x.py", "old": SHA, "new": SHB}, earlier, set())
    assert L4.row_problem4(_row(), None, set()).startswith("an earlier lock")
    assert "LOCK_reliability_v2" in L4.row_problem4(_row(reliability_locked=True), earlier, {"ledger/src/brainir_ledger/agree.py"})
    assert L4.row_problem4(_row("ledger/scripts/forward_v1.py", reliability_locked=True), earlier, {"ledger/src/brainir_ledger/agree.py"}) is None
    assert "LOCK_forward_v1" in L4.row_problem4(_row(forward_locked=True), earlier, set())
    # an uncommitted row never counts; a row later than the reliability lock must say so
    assert "not committed" in L4.row_problem4(_row(), earlier, set(), {"row_utc": None})
    assert "reliability_locked=false" in L4.row_problem4(_row(), earlier, set(), {"row_utc": 200, "reliability_lock": 100, "forward_lock": None})


def test_earlier_lock_checks_delegate_and_pass():
    assert L4.check(L4.RES / "LOCK_reliability_v1.json") == 0
    assert L4.check(L4.RES / "LOCK_prereg_v2.json") == 0
