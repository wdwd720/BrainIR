"""The Phase 3 clean-room guard (goal4 sections 3, 71 'CLEAN ROOM'): offline checks of the PreToolUse decision function."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "scripts" / "p3agent" / "guard_hook.py"


def _guard(root: str, web: bool = False):
    os.environ["P3_CLEAN_ROOT"] = root
    os.environ["P3_ALLOW_WEB"] = "1" if web else "0"
    spec = importlib.util.spec_from_file_location(f"guard_{abs(hash((root, web)))}", GUARD)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


ROOT = r"C:\Dev\BrainIR_p3clean"
CASES = [
    ("Read", {"file_path": rf"{ROOT}\data\x.npz"}, True),
    ("Read", {"file_path": "docs/PROTOCOL.md"}, True),
    ("Read", {"file_path": r"C:\Dev\BrainIR\PHASE2_REPORT.md"}, False),
    ("Read", {"file_path": r"C:\Dev\BrainIR\benchmarks\dng100\oracle\oracle.json"}, False),
    ("Read", {"file_path": r"..\BrainIR\research\phase2\HIDDEN_EVAL_LOG.md"}, False),
    ("Read", {"file_path": r"C:\Dev\BrainIR_p2clean\CLAUDE.md"}, False),
    ("Write", {"file_path": rf"{ROOT}\.claude\settings.json", "content": "{}"}, False),
    ("Edit", {"file_path": rf"{ROOT}\CLAUDE.md", "old_string": "a", "new_string": "b"}, False),
    ("Bash", {"command": "cat /c/Dev/BrainIR/PHASE2_REPORT.md"}, False),
    ("Bash", {"command": 'cat "C:/Dev/BrainIR/benchmarks/state_discovery_v1/hidden/network_map.json"'}, False),
    ("Bash", {"command": "cd .. && ls"}, False),
    ("Bash", {"command": "ls ~/.claude/projects"}, False),
    ("Bash", {"command": "cat $HOME/.modal.toml"}, False),
    ("Bash", {"command": "PYTHONPATH= python x.py"}, False),
    ("Bash", {"command": "python -I x.py"}, False),
    ("Bash", {"command": "uv run python -m pytest -q tests"}, True),
    ("Bash", {"command": "ls data/../src && uv run python runs/a.py"}, False),     # '..' is refused outright (guard v2)
    ("Bash", {"command": "cd /c/Dev/BrainIR_p3clean/notes && ls"}, True),
    ("Bash", {"command": 'cd "C:/Dev/BrainIR_p3clean/runs" && ls'}, True),
    ("Bash", {"command": "cd runs && ls"}, True),
    ("Bash", {"command": "cd ~ && ls"}, False),
    ("Bash", {"command": "cd /c/Dev && ls"}, False),
    ("Bash", {"command": "cd - && ls"}, False),
    ("Glob", {"pattern": "C:/Dev/BrainIR/**/*.md"}, False),
    ("Glob", {"pattern": "**/*.py"}, True),
    ("Grep", {"pattern": "E1", "path": r"C:\Dev\BrainIR"}, False),
    ("PowerShell", {"command": r"Get-Content C:\Dev\BrainIR\PHASE2_REPORT.md"}, False),
    ("mcp__claude-in-chrome__navigate", {"url": "https://example.com"}, False),
    ("SendMessage", {"to": "main", "message": "hi"}, False),
    ("ListAgents", {}, False),
    ("Task", {"subagent_type": "email-sender", "prompt": "x"}, False),
    ("Task", {"subagent_type": "general-purpose", "prompt": "summarise docs/PROTOCOL.md"}, True),
    ("WebSearch", {"query": "dynamic mode decomposition"}, False),
    # review F bypasses of guard v1 (F-B1), refused by guard v2
    ("Bash", {"command": "cat $PWD/../BrainIR/PHASE2*"}, False),
    ("Bash", {"command": "d=..; cat $d/BrainIR/goal3.md"}, False),
    ("Bash", {"command": "cat $PWD/../BrainIR/benchmarks/dng100/orac*/oracle.json"}, False),
    ("Bash", {"command": "ls /c"}, False),
    ("Bash", {"command": "find /c -maxdepth 3 -name 'PHASE2*'"}, False),
    ("Bash", {"command": "cat C:/Dev/BRAINI~1/CLAUDE.md"}, False),
    ("Bash", {"command": "cat C:/Dev/Brain*/PHASE2*"}, False),
    ("Bash", {"command": "x=C; y=:/Dev/BrainIR; cat $x$y/README.md"}, False),
    ("Bash", {"command": "bash <<'EOF'\ncat ../../BrainIR/README.md\nEOF"}, False),
    ("Bash", {"command": "cat ~/.claude/history.jsonl"}, False),
    ("Bash", {"command": "ls C:/Users/'Mihir Modi'/AppData/Local/uv/cache"}, False),
    ("Bash", {"command": "curl -s https://example.org"}, False),
    ("Bash", {"command": "unset PYTHON\"\"PATH; uv run python runs/x.py"}, False),
    ("Bash", {"command": "echo rule >> CLAUDE.md"}, False),
    ("PowerShell", {"command": "Get-Content (Join-Path (Split-Path (Get-Location)) 'BrainIR/README.md')"}, False),
    ("PowerShell", {"command": "New-Item -ItemType Junction -Path simq/r2 -Target C:/Dev"}, False),
    ("Glob", {"pattern": "../BrainIR/**/*.md"}, False),
    ("Grep", {"pattern": "x", "path": "..\\BrainIR"}, False),
    ("Write", {"file_path": rf"{ROOT}\runs\e.ps1", "content": "Get-Content (Join-Path (Split-Path (Get-Location)) 'x')"}, False),
    # legitimate development commands stay allowed
    ("Bash", {"command": "cat > runs/cb/x.py <<'EOF'\nd = {k: v for k, v in x.items()}\ny = a /s\nm = ~mask\nz = q/var\nEOF"}, True),
    ("Bash", {"command": "cat > runs/nn/b.sh <<'EOF'\ntag=$1\nmkdir -p runs/nn/$tag\nfor sid in \"$@\"; do echo runs/nn/$tag/$sid; done\nEOF"}, True),
    ("Bash", {"command": "uv run python -c \"import json; print({k:v for k,v in json.load(open('data/x.json')).items()})\""}, True),
    ("Bash", {"command": "for f in runs/nn/*.json; do echo $f; done"}, True),
    ("Bash", {"command": "OMP_NUM_THREADS=3 uv run python runs/lin/eval.py > runs/lin/out.log 2>&1"}, True),
    ("Bash", {"command": "sed -i 's/time.time()/time.process_time()/g' runs/sd/p.py && uv run python runs/sd/p.py"}, True),
    ("Bash", {"command": "sed -i 's/c = f(x)/c = g(x)/' runs/nn/p.py"}, True),
    ("Bash", {"command": "awk '{print $1/$2}' runs/x.txt"}, True),
    # processes may be stopped only by explicit id (other agents and the simulation service share the machine)
    ("PowerShell", {"command": "Stop-Process -Id 1234 -Force"}, True),
    ("PowerShell", {"command": "Stop-Process -Name python"}, False),
    ("PowerShell", {"command": "Get-Process python | Stop-Process"}, False),
    ("Bash", {"command": "taskkill /F /IM python.exe"}, False),
    ("Bash", {"command": "kill 1234"}, True),
]


@pytest.mark.parametrize("tool,ti,expected", CASES)
def test_guard_decisions(tool, ti, expected):
    g = _guard(ROOT)
    ok, why = g.decide({"tool_name": tool, "tool_input": ti, "cwd": ROOT})
    assert ok == expected, why


def test_web_filter_for_the_literature_agent():
    g = _guard(r"C:\Dev\BrainIR_p3lit", web=True)
    assert g.decide({"tool_name": "WebSearch", "tool_input": {"query": "Koopman autoencoder identifiability"}, "cwd": "."})[0]
    for q in ("DNg100 walking circuit", "Pugliese connectome model", "MANC ventral nerve cord", "Drosophila leg motor neurons"):
        assert not g.decide({"tool_name": "WebSearch", "tool_input": {"query": q}, "cwd": "."})[0], q


def test_own_session_store_readable_other_stores_not():
    g = _guard(r"C:\Dev\BrainIR_p3lit")
    home = os.path.expanduser("~")
    own = os.path.join(home, ".claude", "projects", "C--Dev-BrainIR-p3lit", "s", "tool-results", "x.txt")
    other = os.path.join(home, ".claude", "projects", "C--Dev-BrainIR", "memory", "MEMORY.md")
    assert g.decide({"tool_name": "Read", "tool_input": {"file_path": own}, "cwd": "."})[0]
    assert not g.decide({"tool_name": "Read", "tool_input": {"file_path": other}, "cwd": "."})[0]


def test_other_rooms_by_name_but_not_the_own_room():
    g = _guard(r"C:\Dev\BrainIR_p3reviewG")
    room = r"C:\Dev\BrainIR_p3reviewG"
    assert g.decide({"tool_name": "Read", "tool_input": {"file_path": room + r"\p3synth\review_g.py"}, "cwd": room})[0]
    assert not g.decide({"tool_name": "Read", "tool_input": {"file_path": r"C:\Dev\BrainIR_p3review\CLAUDE.md"}, "cwd": room})[0]
    assert not g.decide({"tool_name": "Read", "tool_input": {"file_path": r"C:\Dev\BrainIR_p3clean\CLAUDE.md"}, "cwd": room})[0]


PYGUARD_PROBES = r"""
import os, sys, subprocess
res = {}
def t(name, fn):
    try:
        fn(); res[name] = 'ALLOWED'
    except PermissionError:
        res[name] = 'blocked'
    except Exception as e:
        res[name] = 'error:' + type(e).__name__
t('abs', lambda: open('C:/Dev/BrainIR/README.md').read())
t('dot', lambda: open('C:/Dev/./BrainIR/README.md').read())
def chd():
    os.chdir('C:/Dev'); open('BrainIR/README.md').read()
t('chdir', chd)
t('claude_home', lambda: os.listdir(os.path.join(os.path.expanduser('~'), '.claude')))
t('child_I', lambda: subprocess.run([sys.executable, '-I', '-c', 'print(1)']))
def child_env():
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    subprocess.run([sys.executable, '-c', 'print(1)'], env=env)
t('child_env', child_env)
def winapi():
    import _winapi
    _winapi.CreateFile(r'C:\Dev\BrainIR\README.md', 0x80000000, 1, 0, 3, 0x80, 0)
t('winapi', winapi)
def ct():
    import ctypes
    ctypes.WinDLL('kernel32').CreateFileW
t('ctypes', ct)
def net():
    import socket
    socket.getaddrinfo('example.org', 80)
t('net', net)
def room_ok():
    import tempfile
    open(os.path.join(os.environ['P3_CLEAN_ROOT'], 'x.txt'), 'w').write('ok'); tempfile.gettempdir()
t('room_write', room_ok)
print(res)
"""


def test_python_guard_v2_resolve_and_contain(tmp_path):
    """Review F (F-B2): the audit hook resolves paths (/./, chdir, 8.3) and blocks native / network / unguarded-child routes."""
    import ast
    import subprocess
    import sys
    room = tmp_path / "BrainIR_p3clean"
    room.mkdir()
    pyguard = GUARD.parent / "pyguard"
    env = dict(os.environ, P3_CLEAN_ROOT=str(room), PYTHONPATH=str(pyguard), TEMP=str(room), TMP=str(room))
    out = subprocess.run([sys.executable, "-c", PYGUARD_PROBES], capture_output=True, text=True, env=env, cwd=str(room), timeout=120)
    res = ast.literal_eval(out.stdout.strip().splitlines()[-1])
    for k in ("abs", "dot", "chdir", "claude_home", "child_I", "child_env", "winapi", "ctypes", "net"):
        assert res[k] == "blocked", (k, res)
    assert res["room_write"] == "ALLOWED", res


def test_python_guard_blocks_runtime_paths(tmp_path):
    """The audit hook refuses opens of forbidden locations even when the path is built at run time."""
    import subprocess
    import sys
    pyguard = GUARD.parent / "pyguard"
    code = "p = 'C:/Dev/' + 'Brain' + 'IR/CLAUDE.md'\ntry:\n    open(p).read(); print('READ')\nexcept PermissionError:\n    print('BLOCKED')\n"
    env = dict(os.environ, P3_CLEAN_ROOT=str(tmp_path / "BrainIR_p3clean"), PYTHONPATH=str(pyguard))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert "BLOCKED" in out.stdout, out.stdout + out.stderr
