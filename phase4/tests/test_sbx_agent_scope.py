"""`sbx --ps` / `sbx --stop` act on the calling agent's own sandbox containers only (review F round 3b, NF-3): the listing filters
by the room AND the agent label, and a stop is refused for another agent's container or another room's. The agent label is the
launcher's P4_AGENT_NAME, which the host guard never lets an agent assign."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "scripts" / "p4agent" / "sbx_template.sh"


def _block(text: str, flag: str) -> str:
    m = re.search(r'if \[ "\$\{1:-\}" = "' + re.escape(flag) + r'" \]; then\n(.*?)\nfi\n', text, re.DOTALL)
    assert m, flag
    return m.group(1)


def test_the_template_scopes_listing_and_stopping_to_the_calling_agent():
    t = TEMPLATE.read_text(encoding="utf-8")
    ps, stop = _block(t, "--ps"), _block(t, "--stop")
    assert 'label=brainir.p4.room=$ROOM_NAME' in ps and 'label=brainir.p4.agent=$agent' in ps
    assert 'brainir.p4.agent' in stop and '"$ROOM_NAME|$agent"' in stop
    assert 'label "brainir.p4.agent=$agent"' in t or '--label "brainir.p4.agent=$agent"' in t   # containers carry the same label


def _render(tmp_path: Path, room: str) -> Path:
    t = TEMPLATE.read_text(encoding="utf-8")
    fake = tmp_path / "docker"
    log = tmp_path / "docker.log"
    fake.write_text("#!/usr/bin/env bash\n"
                    f'echo "$*" >> "{log.as_posix()}"\n'
                    'if [ "$1" = "inspect" ]; then\n'
                    '  case "${@: -1}" in\n'
                    f'    mine) echo "{room}|alice";;\n'
                    f'    other) echo "{room}|bob";;\n'
                    '    foreign) echo "otherroom|alice";;\n'
                    '    *) exit 1;;\n'
                    '  esac\n'
                    'fi\n', encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    rep = {"@DOCKER@": fake.as_posix(), "@ROOM_NAME@": room, "@MAX_CPUS@": "4", "@MAX_MEM_GB@": "8", "@FREE_ROOM@": "0"}
    for k, v in rep.items():
        t = t.replace(k, v)
    t = re.sub(r"@[A-Z_]+@", "x", t)
    sbx = tmp_path / "sbx"
    sbx.write_text(t, encoding="utf-8", newline="\n")
    sbx.chmod(0o755)
    return sbx


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="needs a POSIX bash (runs on the Linux test hosts)")
def test_ps_and_stop_touch_only_the_calling_agents_containers(tmp_path):
    sbx = _render(tmp_path, "room1")
    env = {**os.environ, "P4_AGENT_NAME": "alice"}
    r = subprocess.run(["bash", str(sbx), "--ps"], env=env, capture_output=True, text=True)
    log = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert r.returncode == 0 and "label=brainir.p4.room=room1" in log and "label=brainir.p4.agent=alice" in log
    for cid, ok in (("mine", True), ("other", False), ("foreign", False), ("missing", False)):
        (tmp_path / "docker.log").write_text("", encoding="utf-8")
        r = subprocess.run(["bash", str(sbx), "--stop", cid], env=env, capture_output=True, text=True)
        stopped = "stop --timeout 10 " + cid in (tmp_path / "docker.log").read_text(encoding="utf-8")
        assert stopped is ok, (cid, r.stderr)
        if not ok:
            assert r.returncode != 0 and "not one of your sandbox containers" in r.stderr
