"""The post-freeze runbook's MEMORY-GATED developer queue (scripts/p4/launch_clean_room.py `gated_queue`; the machine owner's rule,
2026-09-27/28: the PC holds one agent sandbox plus orchestration; LOG P4-D64): a developer starts only while fewer than
max_sessions sessions are alive and the host has at least min_free_gb free; everyone starts eventually, in order."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _runbook():
    spec = importlib.util.spec_from_file_location("p4_launch_clean_room", REPO / "scripts" / "p4" / "launch_clean_room.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Session:
    def __init__(self, life: int):
        self.left = life                 # polls until the session ends

    def poll(self):
        self.left -= 1
        return None if self.left > 0 else 0


def test_the_queue_respects_the_session_cap_and_the_memory_floor():
    rb = _runbook()
    started, logs = [], []
    free = iter([9.0, 9.0, 9.0, 7.0, 7.5, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0] + [9.0] * 50)

    def start(d):
        started.append(d)
        return _Session(3)
    rec = rb.gated_queue(["a", "b", "c", "d", "e"], start, max_sessions=2, min_free_gb=8.0, free=lambda: next(free),
                         sleep=lambda s: None, log=logs.append)
    assert started == ["a", "b", "c", "d", "e"]                 # everyone starts, in order
    assert all(r["sessions_alive_before"] < 2 for r in rec)       # never a third session alive
    assert all(r["free_gb"] >= 8.0 for r in rec)                  # never below the memory floor
    assert any("waiting" in m and "7.0 GB free" in m for m in logs)


def test_the_queue_waits_while_memory_is_low_even_with_free_session_slots():
    rb = _runbook()
    readings = [5.0, 6.0, 7.9, 8.0]
    it = iter(readings)
    started = []
    rb.gated_queue(["a"], lambda d: started.append(d) or _Session(1), max_sessions=4, min_free_gb=8.0, free=lambda: next(it),
                   sleep=lambda s: None, log=lambda m: None)
    assert started == ["a"]


def test_the_dry_run_starts_nothing(tmp_path, monkeypatch):
    rb = _runbook()
    monkeypatch.setattr(rb, "RECORD", tmp_path / "rec.json")
    calls = []
    monkeypatch.setattr(rb, "gated_queue", lambda *a, **k: calls.append(1))
    rb.main(["--dry-run", "--developers", "li,sy"])
    assert not calls                                              # the dry run lists the launches without the queue
    import json
    steps = [s["step"] for s in json.loads((tmp_path / "rec.json").read_text(encoding="utf-8"))["steps"]]
    assert steps[-2:] == ["developer li", "developer sy"]
