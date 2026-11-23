"""Run 5 lock tool (PREREG v5 Part X): amendment rules, untracked-input keys and delegation of earlier locks' checks."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import lock5 as L5  # noqa: E402

SHA = "a" * 64
SHB = "b" * 64


def _row(path="ledger/scripts/replication_v1.py", **kw):
    r = {"path": path, "old": SHA, "new": SHB, "replication_locked": False, "forward2_locked": False}
    r.update(kw)
    return r


def test_lock_names_and_scope():
    assert L5.V5_LOCKS == ("LOCK_pertype_v1.json", "LOCK_prereg_v5.json", "LOCK_replication_v1.json", "LOCK_forward_v2.json")
    for n in ("LOCK_prereg_v4.json", "LOCK_reliability_v2.json", "LOCK_forward_v1.json", "LOCK_labels_v2.json"):
        assert n in L5.EARLIER5
    assert not set(L5.V5_LOCKS) & set(L5.EARLIER5)


def test_amendable_paths():
    assert L5.amendable_kind5("ledger/scripts/gha5.py") == "code"
    assert L5.amendable_kind5("research/ledger/PREREG_v5.md") is None
    assert L5.amendable_kind5("research/ledger/pertype_v1/B1r.csv") is None
    assert L5.amendable_kind5("../x.py") is None


def test_row_rules():
    earlier = {"ledger/scripts/gha4.py"}
    assert L5.row_problem5(_row(), earlier, set()) is None
    assert "pre-run-5 lock" in L5.row_problem5(_row("ledger/scripts/gha4.py"), earlier, set())
    assert "never amended" in L5.row_problem5(_row("ledger/scripts/lock5.py"), earlier, set())
    assert "lacks the flags" in L5.row_problem5({"path": "ledger/scripts/x.py", "old": SHA, "new": SHB}, earlier, set())
    assert L5.row_problem5(_row(), None, set()).startswith("an earlier lock")
    hashed = {"ledger/scripts/replication_v1.py"}
    assert "LOCK_replication_v1" in L5.row_problem5(_row(replication_locked=True), earlier, hashed)
    assert L5.row_problem5(_row("ledger/scripts/forward_v2.py", replication_locked=True), earlier, hashed) is None
    assert "LOCK_forward_v2" in L5.row_problem5(_row(forward2_locked=True), earlier, set())
    # an uncommitted row never counts; a row later than the replication lock must say so
    assert "not committed" in L5.row_problem5(_row(), earlier, set(), {"row_utc": None})
    assert "replication_locked=false" in L5.row_problem5(_row(), earlier, set(), {"row_utc": 200, "replication_lock": 100})


def test_untracked_keys_have_no_slash(tmp_path, monkeypatch):
    monkeypatch.setattr(L5, "REPO", tmp_path)
    f = tmp_path / "data" / "ledger" / "x" / "results.pkl"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"abc")
    out = L5._untracked([f])
    assert list(out) == ["data:ledger:x:results.pkl"]
    assert all("/" not in k for k in out)
