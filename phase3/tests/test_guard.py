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
    ("Bash", {"command": "ls data/../src && uv run python runs/a.py"}, True),
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


def test_python_guard_blocks_runtime_paths(tmp_path):
    """The audit hook refuses opens of forbidden locations even when the path is built at run time."""
    import subprocess
    import sys
    pyguard = GUARD.parent / "pyguard"
    code = "p = 'C:/Dev/' + 'Brain' + 'IR/CLAUDE.md'\ntry:\n    open(p).read(); print('READ')\nexcept PermissionError:\n    print('BLOCKED')\n"
    env = dict(os.environ, P3_CLEAN_ROOT=str(tmp_path / "BrainIR_p3clean"), PYTHONPATH=str(pyguard))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert "BLOCKED" in out.stdout, out.stdout + out.stderr
