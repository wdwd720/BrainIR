"""The sandbox wrapper's MACHINE-WIDE SLOT (the machine owner's rule, 2026-09-27/28: one agent sandbox at a time on the development
PC). Every room's wrapper counts the sandbox containers of every room (name prefix p4sbx-) inside an atomic mkdir critical
section, creates its container there (so the created container holds the slot before the next wrapper looks) and starts it
attached; it starts only with at least MIN_FREE_GB free; otherwise it waits (P4_SBX_WAIT_S) and exits 75 (naming only the caller's own
containers, never another agent's; review F round 3c, NF3c-1). A
running container whose sbx client process is gone (killed tool call) is stopped as an orphan; a created-but-never-started
container older than 120 s is removed; a stale mutex (older than 2 minutes) is broken. Runs the rendered template against a fake
docker on the Linux test hosts (as test_sbx_agent_scope does)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "scripts" / "p4agent" / "sbx_template.sh"
POSIX = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="needs a POSIX bash (runs on the Linux test hosts)")
OLD = "2020-01-01T00:00:00.000000000Z"


def _dead_pid() -> int:
    for pid in range(999_999, 900_000, -7):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            continue
    raise RuntimeError("no free pid found")


def _setup(tmp_path: Path, containers: list[tuple[str, str, str, str]], *, min_free_gb: str = "0", max_slots: str = "1",
           mine: str = "") -> dict:
    """containers: (id, state, client label, created) as the fake `docker ps -a` / `docker inspect` report them; mine: what the fake
    lists for the caller's OWN containers (the room + agent label filter); any other `docker ps` lists only a running-for time."""
    room, slot = tmp_path / "room", tmp_path / "slot"
    room.mkdir(parents=True)
    log = tmp_path / "docker.log"
    ps_lines = "\\n".join(f"{c} {s} {cl}" for c, s, cl, _cr in containers)
    created = "\n".join(f'    {c}) echo "{cr}";;' for c, _s, _cl, cr in containers)
    fake = tmp_path / "docker"
    fake.write_text("#!/usr/bin/env bash\n"
                    f'echo "$*" >> "{log.as_posix()}"\n'
                    'case "$1" in\n'
                    '  ps) if [ "$2" = "-a" ]; then printf "' + ps_lines + ('\\n' if containers else '') + '"; '
                    'elif printf "%s" "$*" | grep -q "brainir.p4.agent=alice"; then printf "' + mine + '"; '
                    'else printf "2 minutes ago\\n"; fi;;\n'
                    '  inspect) case "${@: -1}" in\n' + created + '\n    *) exit 1;;\n  esac;;\n'
                    '  create) echo "cid-new";;\n'
                    '  start) echo "STARTED ${@: -1}"; exit 0;;\n'
                    '  stop|rm) exit 0;;\n'
                    'esac\n', encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    rep = {"@DOCKER@": fake.as_posix(), "@ROOM_NAME@": "room1", "@ROOM_POSIX@": room.as_posix(), "@ROOM_MOUNT@": room.as_posix(),
           "@IMAGE_ID@": "sha256:x", "@SECCOMP@": "x", "@MAX_CPUS@": "4", "@MAX_MEM_GB@": "8", "@FREE_ROOM@": "0",
           "@RW_PATHS@": "", "@AGENT_AREAS@": "", "@OWNED_AREAS@": "", "@TOKEN_DIR@": "", "@RO_TOPS@": "", "@WORK_DOC@": "none",
           "@SLOT_DIR@": slot.as_posix(), "@MAX_SLOTS@": max_slots, "@MIN_FREE_GB@": min_free_gb}
    t = TEMPLATE.read_text(encoding="utf-8")
    for k, v in rep.items():
        t = t.replace(k, v)
    assert "@" not in "".join(x for x in t.split("\n") if x.strip().startswith(("SLOT_DIR", "MAX_SLOTS", "MIN_FREE_GB")))
    sbx = tmp_path / "sbx"
    sbx.write_text(t, encoding="utf-8", newline="\n")
    sbx.chmod(0o755)
    return {"sbx": sbx, "room": room, "slot": slot, "log": log}


def _run(s: dict, wait_s: int = 2):
    env = {**os.environ, "P4_AGENT_NAME": "alice", "P4_SBX_WAIT_S": str(wait_s), "P4_SBX_MEM_GB": "2"}
    r = subprocess.run(["bash", str(s["sbx"]), "python", "-c", "pass"], cwd=s["room"], env=env, capture_output=True, text=True,
                       timeout=60)
    return r, (s["log"].read_text(encoding="utf-8") if s["log"].exists() else "")


def test_the_template_declares_the_machine_slot():
    t = TEMPLATE.read_text(encoding="utf-8")
    for k in ("@SLOT_DIR@", "@MAX_SLOTS@", "@MIN_FREE_GB@"):
        assert k in t
    assert 'exec "$DOCKER" run' not in t                          # the container is CREATED inside the critical section
    assert '"$DOCKER" create "${create_args[@]}"' in t and 'exec "$DOCKER" start -ai "$cid"' in t
    assert '--filter "name=^p4sbx-"' in t                          # every room's sandboxes count, not only this room's
    assert '--label "brainir.p4.client=$$"' in t and "exit 75" in t
    name_line = next(x for x in t.splitlines() if x.startswith('name="p4sbx-'))
    assert "$$" not in name_line                                   # no process id in the name (review F round 3c, NF3c-1)
    assert '"$tmo" -le 3600' in t and "P4_SBX_TIMEOUT_S:-1800" in t     # the single slot is held for at most 1 h (NF3c-2)


@POSIX
def test_a_free_slot_creates_then_starts(tmp_path):
    s = _setup(tmp_path, [])
    r, log = _run(s)
    assert r.returncode == 0 and "STARTED cid-new" in r.stdout, r.stderr
    lines = log.splitlines()
    ci = next(i for i, x in enumerate(lines) if x.startswith("create "))
    assert lines[ci + 1] == "start -ai cid-new"
    assert "--label brainir.p4.sandbox=1" in lines[ci] and "--network none" in lines[ci] and "--rm" in lines[ci]
    assert re.search(r"--name p4sbx-room1-alice-[0-9a-f]{12} ", lines[ci])        # a random suffix, no process id (NF3c-1)
    assert not (s["slot"] / "mutex").exists()                     # the critical section released its mutex


@POSIX
def test_a_live_holder_in_any_room_makes_sbx_wait_then_exit_75(tmp_path):
    s = _setup(tmp_path, [("h1", "running", str(os.getpid()), OLD)])
    t0 = time.time()
    r, log = _run(s, wait_s=2)
    assert r.returncode == 75 and "no sandbox slot" in r.stderr and "busy since 2 minutes ago" in r.stderr
    assert "h1" not in r.stderr and "YOURS" not in r.stderr      # another agent's container is never named (NF3c-1)
    assert time.time() - t0 >= 2 and "create " not in log and "stop " not in log


@POSIX
def test_the_wait_message_names_only_the_callers_own_container(tmp_path):
    s = _setup(tmp_path, [("h1", "running", str(os.getpid()), OLD)], mine="p4sbx-room1-alice-0a1b2c3d4e5f (3 minutes)")
    r, _log = _run(s, wait_s=1)
    assert r.returncode == 75 and "YOURS: p4sbx-room1-alice-0a1b2c3d4e5f (3 minutes)" in r.stderr


@POSIX
def test_a_timeout_above_one_hour_is_refused(tmp_path):
    s = _setup(tmp_path, [])
    env = {**os.environ, "P4_AGENT_NAME": "alice", "P4_SBX_TIMEOUT_S": "3601"}
    r = subprocess.run(["bash", str(s["sbx"]), "python", "-c", "pass"], cwd=s["room"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "P4_SBX_TIMEOUT_S must be in [1, 3600]" in r.stderr


@POSIX
def test_a_holder_from_the_old_wrapper_without_client_label_counts(tmp_path):
    s = _setup(tmp_path, [("h1", "running", "", OLD)])
    r, log = _run(s, wait_s=1)
    assert r.returncode == 75 and "create " not in log and "stop " not in log


@POSIX
def test_an_orphan_whose_client_is_gone_is_stopped_and_the_slot_taken(tmp_path):
    s = _setup(tmp_path, [("h1", "running", str(_dead_pid()), OLD)])
    r, log = _run(s)
    assert r.returncode == 0 and "stop --timeout 5 h1" in log and "STARTED cid-new" in r.stdout, r.stderr
    assert "stopped orphan h1" in (s["slot"] / "reaped.log").read_text(encoding="utf-8")


@POSIX
def test_a_young_orphan_is_not_stopped(tmp_path):
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000000000Z", time.gmtime())
    s = _setup(tmp_path, [("h1", "running", str(_dead_pid()), now)])
    r, log = _run(s, wait_s=1)
    assert r.returncode == 75 and "stop " not in log


@POSIX
def test_a_stale_created_container_is_removed_and_a_young_one_counts(tmp_path):
    s = _setup(tmp_path, [("c1", "created", "", OLD)])
    r, log = _run(s)
    assert r.returncode == 0 and "rm -f c1" in log and "STARTED cid-new" in r.stdout
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000000000Z", time.gmtime())
    s2 = _setup(tmp_path / "b", [("c2", "created", "", now)])
    r2, log2 = _run(s2, wait_s=1)
    assert r2.returncode == 75 and "rm -f c2" not in log2


@POSIX
def test_too_little_free_memory_waits_and_exits_75(tmp_path):
    s = _setup(tmp_path, [], min_free_gb="100000")
    r, log = _run(s, wait_s=1)
    assert r.returncode == 75 and "GB free" in r.stderr and "create " not in log


@POSIX
def test_a_stale_mutex_is_broken_and_a_fresh_one_is_respected(tmp_path):
    s = _setup(tmp_path, [])
    m = s["slot"] / "mutex"
    m.mkdir(parents=True)
    old = time.time() - 600
    os.utime(m, (old, old))
    r, log = _run(s)
    assert r.returncode == 0 and "STARTED cid-new" in r.stdout
    s2 = _setup(tmp_path / "b", [])
    (s2["slot"] / "mutex").mkdir(parents=True)                    # held by another wrapper right now
    r2, log2 = _run(s2, wait_s=1)
    assert r2.returncode == 75 and "create " not in log2


@POSIX
def test_two_slots_admit_a_second_sandbox(tmp_path):
    s = _setup(tmp_path, [("h1", "running", str(os.getpid()), OLD)], max_slots="2")
    r, log = _run(s)
    assert r.returncode == 0 and "STARTED cid-new" in r.stdout
