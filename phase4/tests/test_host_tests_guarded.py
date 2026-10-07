"""The memory guard of scripts/p4/host_tests_guarded.py (the user's local-resource rule), with FAKED RAM readings: a file waits for
memory and for no agent sandbox, a run whose free RAM falls below the floor is killed and recorded as interrupted (never a pass),
a file that never gets memory is "not started", and a normal run records its status, counts and RAM minimum. Light: the "test file"
is a tiny Python command."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("host_tests_guarded_under_test", REPO / "scripts" / "p4" / "host_tests_guarded.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


class Clock:
    """A fake monotonic clock advanced by the fake sleep."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _cmd(code: str):
    return lambda f: [sys.executable, "-c", code]


def _seq(*vals):
    """A fake probe returning the given readings in order, then the last one forever (the poll loop may run many times)."""
    vals = list(vals)

    def f():
        return vals.pop(0) if len(vals) > 1 else vals[0]
    return f


def test_a_run_waits_for_memory_and_for_no_agent_sandbox(tmp_path):
    clock = Clock()
    free = _seq(4.0, 9.0, 9.0)                             # not enough, then enough (but a sandbox), then free
    busy = _seq(False, True, False)
    rec = G.run_one("test_x.py", tmp_path, free_gb=free, sandbox_running=busy,
                    command_for=_cmd("print('3 passed in 0.01s')"), now=clock.now, sleep=clock.sleep, poll_s=0.01)
    assert rec["status"] == "passed" and rec["counts"] == {"passed": 3} and rec["wait_s"] == 30.0     # two start polls of 15 s
    assert json.loads((tmp_path / "test_x.json").read_text(encoding="utf-8"))["status"] == "passed"


def test_a_run_below_the_floor_is_killed_and_never_a_pass(tmp_path):
    clock = Clock()
    readings = _seq(9.0, 9.0, 5.0)                         # free at the start, then the free RAM falls below 6 GB
    rec = G.run_one("test_y.py", tmp_path, free_gb=readings, sandbox_running=lambda: False,
                    command_for=_cmd("import time; time.sleep(60)"), now=clock.now, sleep=lambda s: None, poll_s=0.0)
    assert rec["status"] == "interrupted by the memory guard" and rec["ram_min_gb"] == 5.0 and rec["rc"] != 0


def test_a_file_without_memory_is_not_started(tmp_path):
    clock = Clock()
    rec = G.run_one("test_z.py", tmp_path, free_gb=lambda: 3.0, sandbox_running=lambda: False, command_for=_cmd("print(1)"),
                    now=clock.now, sleep=clock.sleep, max_wait_s=60)
    assert rec["status"] == "not started" and "3.0 GB" in rec["reason"]


def test_a_failing_file_is_failed(tmp_path):
    clock = Clock()
    rec = G.run_one("test_w.py", tmp_path, free_gb=lambda: 12.0, sandbox_running=lambda: False,
                    command_for=_cmd("import sys; print('1 failed, 2 passed in 0.1s'); sys.exit(1)"), now=clock.now,
                    sleep=clock.sleep, poll_s=0.01)
    assert rec["status"] == "failed" and rec["counts"] == {"failed": 1, "passed": 2}
