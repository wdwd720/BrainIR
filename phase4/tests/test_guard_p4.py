"""The Phase 4 room guard (goal5 section 5; early review F): offline checks of the PreToolUse decision function and of the Python
audit hook.

Version 3 (early review F): names from the orchestrator's config (none in the guard or in these tests), generic refusal classes, only
the bare `sbx` resolved to the hash-checked outside copy, writes only into work areas (write-capable options refused), data-driven
paths / scripts refused, other agents' private areas refused, planted control files detected.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GUARD = Path(os.environ.get("P4_GUARD_UNDER_TEST") or REPO / "scripts" / "p4agent" / "guard_hook.py")
ROOT = r"C:\Dev\BrainIR_p4clean"


def _names():
    spec = importlib.util.spec_from_file_location("p4names_for_tests", GUARD.parent.parent / "p4config" / "names.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N = _names()
TV = N.TEST_VECTORS
MAIN = str(REPO)                     # the main repository (outside every room)


def _guard(root: str, web: bool = False, audit: str | None = None, agent: str = "pytest", scratch: str = ""):
    os.environ["P4_CLEAN_ROOT"] = root
    os.environ["P4_ALLOW_WEB"] = "1" if web else "0"
    os.environ["P4_AGENT_NAME"] = agent
    os.environ["P4_AGENT_SCRATCH"] = scratch
    os.environ["P4_AUDIT_DIR"] = audit or str(Path(__file__).resolve().parent / ".guard_test_audit")
    spec = importlib.util.spec_from_file_location(f"p4guard_{abs(hash((root, web, audit, agent, scratch)))}", GUARD)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


# ------------------------------------------------------------------------------------------------ a room with declared work areas
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.fixture()
def room(tmp_path, monkeypatch):
    """A clean-room-like room (declared work areas), its protected list, an outside sbx copy with its manifest record."""
    r = tmp_path / "BrainIR_p4testroom"
    for d in ("docs", "src/brainir_causal/methods", "runs/lin", "notes", "tests/methods", ".tmp/pytest", ".tmp/other", "simq/pytest",
              "simq/other", ".claude"):
        (r / d).mkdir(parents=True)
    files = {"docs/PROTOCOL.md": "protocol\n", "docs/API.md": "api\n", "src/brainir_causal/api.py": "x = 1\n",
             "src/brainir_causal/methods/__init__.py": "", "CLAUDE.md": "rules\n", "CLAUDE.local.md": "", ".mcp.json": "{}\n",
             ".claude/README.md": "ro\n", "sbx": "#!/usr/bin/env bash\necho sandbox\n", "runs/lin/a.py": "print(1)\n",
             ".tmp/other/secret.txt": "other agent\n", "notes/n.md": "note\n"}
    for k, v in files.items():
        (r / k).write_text(v, encoding="utf-8", newline="\n")
    audit = tmp_path / "audit"
    bindir = audit / "sbx_bin" / r.name
    bindir.mkdir(parents=True)
    (bindir / "sbx").write_text(files["sbx"], encoding="utf-8", newline="\n")
    manifest = tmp_path / "CLEANROOM_MANIFEST_test.json"
    manifest.write_text(json.dumps({"files": [{"path": "sbx", "sha256": _sha(r / "sbx")}]}), encoding="utf-8")
    listed = [k for k in files if not k.startswith(("runs/", ".tmp/", "notes/"))]
    (audit / f"protected_{r.name}.json").write_text(json.dumps({
        "room": r.name, "files": listed + ["CLEANROOM_MANIFEST.json"],
        "ro_tops": sorted({k.split("/", 1)[0] for k in listed} | {"CLEANROOM_MANIFEST.json"}),
        "work_areas": ["src/brainir_causal/methods", "tests/methods", "runs", "notes", "simq", ".tmp"], "agent_areas": [".tmp", "simq"],
        "sbx_sha256": _sha(r / "sbx"), "outside_sbx": str(bindir / "sbx"), "manifest": str(manifest), "acl": False}), encoding="utf-8")
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    g = _guard(str(r), audit=str(audit))
    return g, r, audit


def _bash(g, r, cmd, cwd=None):
    return g.decide_full({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd or r)})


ROOM_CASES = [
    # --- the sandbox: bare sbx only (F-B4 b)
    ("sbx pytest -q tests/methods", True),
    ("sbx python runs/lin/a.py > runs/lin/out.log 2>&1", True),
    ("P4_SBX_CPUS=4 P4_SBX_MEM_GB=12 sbx python runs/x.py", True),
    ("timeout 600 sbx python runs/x.py; echo done", True),
    ("nohup sbx python runs/x.py > runs/x.log 2>&1 &", True),
    ("sbx --ps && sbx --stop abc123", True),
    ("sbx python - <<'EOF'\nimport os\nprint(os.listdir('/room'))\nEOF", True),
    ("./sbx python runs/lin/a.py", False),
    ("../BrainIR_p4testroom/sbx python x.py", False),
    ("P4_AGENT_NAME=other sbx python x.py", False),
    # --- protected files: every write-capable path of F-B4 (a, c)
    ("sort -o CLAUDE.local.md .tmp/pytest/cl.md", False),
    ("cp .tmp/pytest/api.md docs/API.md", False),
    ("sed -n 'w sbx' .tmp/pytest/copy_of_wrapper", False),
    ("sed -n '1W docs/API.md' notes/n.md", False),
    ("sed 's/a/b/w docs/API.md' notes/n.md", False),
    ("sed -n '1r /c/Users/x/secret' notes/n.md", False),
    ("sed 's/a/b/e' notes/n.md", False),
    ("sed -f notes/script.sed notes/n.md", False),
    ("awk '{print > \"docs/API.md\"}' notes/n.md", False),
    ("awk '{print $1 >> \"runs/x\"}' notes/n.md", False),
    ("awk 'BEGIN{system(\"python x\")}'", False),
    ("awk '{print $1 | \"sh\"}' notes/n.md", False),
    ("awk 'BEGIN{while((getline l < \"x\")>0) print l}'", False),
    ("awk 'BEGIN{ARGV[1]=\"x\"; ARGC=2} {print}'", False),
    ("awk -f notes/p.awk notes/n.md", False),
    ("find . -name '*.md' -fprint docs/API.md", False),
    ("find . -name x -delete", False),
    ("find . -name '*.py' -exec grep -l foo {} \\;", False),
    ("split -l 1 notes/n.md docs/x", False),
    ("echo x | tee docs/API.md", False),
    ("echo x | tee -a CLAUDE.md", False),
    ("mv docs/API.md runs/x", False),
    ("rm docs/API.md", False),
    ("rm -rf runs", False),
    ("touch docs/new.md", False),
    ("mkdir docs/x", False),
    ("chmod +x sbx", False),
    ("dd if=notes/n.md of=docs/API.md", False),
    ("install notes/n.md docs/API.md", False),
    ("ln -s notes runs/l", False),
    ("cp -s runs/a runs/b", False),
    ("gzip docs/API.md", False),
    ("uniq notes/n.md docs/API.md", False),
    ("shuf -o docs/API.md notes/n.md", False),
    ("tree -o docs/t.txt", False),
    ("sort -T docs notes/n.md", False),
    ("sort --compress-program=python notes/n.md", False),
    ("echo x > sbx", False),
    ("echo x >&docs/API.md", False),
    ("echo rule >> CLAUDE.md", False),
    ("echo x > runs/lin/CLAUDE.md", False),
    ("echo x > runs/sitecustomize.py", False),
    ("echo x > runs/evil.pth", False),
    ("cp notes/n.md .claude/settings.json", False),
    ("echo x > src/brainir_causal/api.py", False),
    ("echo x > src/brainir_causal/methods/__init__.py", False),
    ("echo x > tests/x.py", False),
    ("echo x > newtop.txt", False),
    ("mkdir newdir", False),
    ("cd docs && rm API.md", False),
    ("rm d*/A*.md", False),
    ("rm {docs,runs}/API.md", False),
    ("xargs rm < notes/list.txt", False),
    # --- writes into the work areas stay allowed
    ("echo x > runs/lin/b.txt", True),
    ("cat > runs/lin/x.py <<'EOF'\nd = {k: v for k, v in x.items()}\ny = a /s\nm = ~mask\nz = q/var\nEOF", True),
    ("mkdir -p runs/lin/sub && cp notes/n.md runs/lin/sub/ && mv runs/lin/sub/n.md runs/lin/sub/m.md && rm -r runs/lin/sub", True),
    ("sed -i 's/time.time()/time.process_time()/g' runs/lin/a.py && sbx python runs/lin/a.py", True),
    ("sed -i 's/^See x\\/y.*$/done: see a\\/b; fine/' notes/n.md", True),
    ("echo x | tee runs/lin/log.txt notes/log.md", True),
    ("sort -o runs/lin/s.txt notes/n.md", True),
    ("touch src/brainir_causal/methods/m_x.py tests/methods/test_x.py", True),
    ("echo x > .tmp/pytest/scratch.txt && cat .tmp/pytest/scratch.txt", True),
    ("cd runs && touch lin/c.txt", True),
    ("(cd runs && ls -la) && wc -l notes/*.md | sort -n | tail -3", True),
    ("gzip -c notes/n.md > runs/lin/n.gz", True),
    ("rm runs/lin/*.txt", True),
    # --- other agents' private areas (minor 4)
    ("cat .tmp/other/secret.txt", False),
    ("ls .tmp/*", False),
    ("ls simq/other", False),
    ("echo x > simq/other/req.json", False),
    ("echo x > simq/pytest/req.json", True),
    # --- host execution and allowlist
    ("uv run python -m pytest -q tests", False),
    ("python runs/a.py", False),
    ("py -3 runs/a.py", False),
    ("bash runs/nn/run.sh", False),
    ("source runs/nn/env.sh", False),
    ("runs/nn/tool --x", False),
    ("echo $(python -c 'print(1)')", False),
    ("echo `uv run python x.py`", False),
    ("cat <(python x.py)", False),
    ("ls | xargs -n 1 wc -l", False),
    ("git status", False),
    ("docker run -v C:/:/x busybox cat /x", False),
    ("node -e 1", False),
    ("tar xf a.tar", False),
    ("ps -W", False),
    ("shopt -s extglob", False),
    ("taskkill /F /IM python.exe", False),
    ("pkill -f x", False),
    ("kill 1234", False),                          # an explicit process id could be another agent's wrapper (review F r3c, NF3c-1)
    ("kill -9 12345", False),
    ("pid=4321; kill $pid", False),
    ("sbx python runs/x.py & kill %1", True),
    ("sbx python runs/x.py & kill $!", True),
    ("sbx python runs/x.py & pid=$!; sleep 1; kill $pid", True),
    ("kill -9 -1", False),
    ("kill 0", False),
    # --- environment
    ("PATH=.:$PATH ls", False),
    ("export PATH=runs:$PATH", False),
    ("env LD_PRELOAD=x ls", False),
    ("declare PATH=runs", False),
    ("read PATH < notes/n.md", False),
    ("printf -v PATH '%s' runs", False),
    ("declare -n ref=PATH", False),
    ("BASH_CMDS[sbx]=runs/evil ls", False),
    ("PS4='$(cat x)' ls", False),
    ("env -C /c/Users ls", False),
    ("env -S 'python x.py'", False),
    ("command -p ls", False),
    ("P4_SIM_TOKEN=0000 sbx python x.py", False),
    ("export P4_SIM_TOKEN=0000", False),
    ("env P4_SIM_TOKEN=0000 sbx python x.py", False),
    # --- the simulation token is never read on the host; no environment listings (review F round 2, N-M1)
    ("printenv P4_SIM_TOKEN", False),
    ("echo $P4_SIM_TOKEN", False),
    ("echo \"${P4_SIM_TOKEN}\" > runs/lin/t.txt", False),
    ("printf '%s' \"$p4_sim_token\"", False),
    ("printenv", False),
    ("printenv -0", False),
    ("env", False),
    ("env | sort", False),
    ("set", False),
    ("set | grep P4", False),
    ("export", False),
    ("export -p", False),
    ("declare -p", False),
    ("declare -x", False),
    ("printenv P4_AGENT_SCRATCH", True),
    ("set -euo pipefail; ls", True),
    ("env OMP_NUM_THREADS=2 sbx python runs/lin/a.py", True),
    # --- GNU long-option abbreviations (review F round 2, N-m1)
    ("sort --outp=docs/API.md notes/n.md", False),
    ("sort --outpu docs/API.md notes/n.md", False),
    ("sort --comp=python notes/n.md", False),
    ("sed --in-pl 's/a/b/' docs/API.md", False),
    ("sed --in 's/a/b/' docs/API.md", False),
    ("sed --follow 's/a/b/' notes/n.md", False),
    ("du --files0=notes/n.md", False),
    ("cp --target-dir=docs notes/n.md", False),
    ("chmod --ref=/c/Users/x/f runs/lin/a.py", False),
    ("sort --o=runs/lin/s.txt notes/n.md", True),          # GNU sort: --o is --output (unique); the target is a work area
    ("sort --outp=runs/lin/s.txt notes/n.md", True),
    ("sed --in-pl 's/a/b/' notes/n.md", True),
    ("grep --dereference-r x notes", False),
    ("grep --exclude-f=/c/Users/x/f x notes/n.md", False),
    ("shuf --out=docs/API.md notes/n.md", False),
    ("touch --ref=/c/Users/x/f runs/lin/t", False),
    ("wc --files0=notes/n.md", False),
    ("sha256sum --ch notes/n.md", False),
    # --- paths outside the room
    ("cat /c/Users/x/secret", False),
    ("ls /c", False),
    ("find /c -maxdepth 3 -name 'x*'", False),
    ("cat ~/.claude/history.jsonl", False),
    ("cat $HOME/.modal.toml", False),
    ("cd .. && ls", False),
    ("cd ~ && ls", False),
    ("cd /c/Dev && ls", False),
    ("cd - && ls", False),
    ("cat C:/Dev/BRAINI~1/CLAUDE.md", False),
    ("x=C; y=:/Users; cat $x$y/secret", False),
    ("d=..; cat $d/x", False),
    ("cat .*/x", False),
    ("cat {.,.}{.,.}/x", False),
    ("cat $'\\x2e\\x2e/x'", False),
    ("cat $'\\u002e\\u002e/x'", False),
    ("cat < /c/Users/x/secret", False),
    ("sbx python x.py < /c/Users/x/secret", False),
    ("cat > /tmp/x.py <<'EOF'\nprint(1)\nEOF", False),
    ("curl -s https://example.org", False),
    # --- data-driven paths and scripts
    ("cat $(cat notes/list.txt)", False),
    ("while read f; do cat \"$f\"; done < notes/list.txt", False),
    ("for f in $(cat notes/list.txt); do head -1 $f; done", False),
    ("f=$(head -1 notes/list.txt); tail $f", False),
    ("n=$(grep -c x notes/n.md); sed -n \"${n}p\" notes/n.md", False),
    ("x=$(cat notes/n.md); echo $((x))", False),
    ("echo $(( $(cat notes/n.md) ))", False),
    ("x=$(cat notes/n.md); echo ${a[$x]}", False),
    ("((x = 1))", False),
    ("cat > notes/x <<EOF\n$(cat /c/Users/x/secret)\nEOF", False),
    ("sbx python -c \"print('$(cat /c/Users/x/secret)')\"", False),
    ("echo ${!x}", False),
    # --- literal / safe variables and loops stay allowed
    ("for f in runs/lin/*.py; do head -3 $f; done", True),
    ("for i in $(seq 1 3); do cat runs/lin/r$i.txt 2>/dev/null; done", True),
    ("for i in 1 2; do echo $i; done", True),
    ("d=runs/lin; ls $d; cat $d/a.py", True),
    ("if [ -f runs/x ]; then echo y; else echo n; fi", True),
    ("[[ -f runs/lin/a.py && -d notes ]] && echo ok", True),
    ("n=$(grep -c x notes/n.md); echo \"found $n\"", True),
    ("while read line; do echo \"$line\"; done < notes/n.md", True),
    ("echo $((1 + 2))", True),
    ("diff <(sort notes/n.md) <(sort runs/lin/a.py) | head", True),
    # --- patterns are not paths (minor 3)
    ("grep -rn \"^## \\|^\\* \" notes | head", True),
    ("grep -n '\\.\\w' notes/n.md", True),
    ("grep -rn 'a/./b' notes", True),
    ("rg -n '\\.\\./' src", True),
    ("find . -name '*.py' -newer notes/n.md", True),
    ("sed -n '/^## /,/^## /p' notes/n.md", True),
    ("sed -n '$=' notes/n.md", True),
    ("awk '{print $1/$2}' runs/x.txt", True),
    ("awk -F, '$3 > 5 {print $1}' runs/x.csv", True),
    ("echo 'see a/./b and ../c'", True),
    ("cut -d/ -f2 notes/n.md", True),
    ("jq '.a' runs/x.json", True),
    ("wc -l src/brainir_causal/*.py tests/methods/*", True),
    # --- encoded text, links
    ("echo aGk= | base64 -d", False),
    ("mklink /J runs\\j C:\\Users", False),
]


@pytest.mark.parametrize("cmd,expected", ROOM_CASES)
def test_room_bash_decisions(room, cmd, expected):
    g, r, _ = room
    ok, cls, why = _bash(g, r, cmd)
    assert ok == expected, (cls, why)


def test_sbx_spellings_and_wrapper_integrity(room, monkeypatch):
    g, r, audit = room
    assert _bash(g, r, "sbx python x.py")[0]
    ok, cls, _ = _bash(g, r, "./sbx python x.py")
    assert not ok and cls == "sbx"
    ok, cls, _ = _bash(g, r, f"{r.as_posix()}/sbx python x.py")
    assert not ok
    outside = audit / "sbx_bin" / r.name / "sbx"
    outside.write_text("#!/usr/bin/env bash\nexec \"$@\"\n", encoding="utf-8", newline="\n")      # replaced wrapper
    ok, cls, _ = _bash(g, r, "sbx python x.py")
    assert not ok and cls == "sbxcheck"
    monkeypatch.setenv("PATH", str(r) + os.pathsep + os.environ["PATH"])                          # sbx found in the room first
    ok, cls, _ = _bash(g, r, "sbx python x.py")
    assert not ok and cls == "sbxcheck"


def test_write_and_edit_tools_only_in_work_areas(room):
    g, r, _ = room
    w = lambda p: g.decide_full({"tool_name": "Write", "tool_input": {"file_path": str(r / p), "content": "x"}, "cwd": str(r)})[0]
    for p in ("docs/PROTOCOL.md", "docs/NEW.md", "src/brainir_causal/api.py", "src/brainir_causal/methods/__init__.py", "CLAUDE.md",
              "CLAUDE.local.md", ".mcp.json", ".claude/settings.json", "sbx", "CLEANROOM_MANIFEST.json", "runs/x/CLAUDE.md",
              "runs/sitecustomize.py", "new_top.md", ".tmp/other/x.txt", "simq/other/r.json", "tests/x.py"):
        assert not w(p), p
    for p in ("src/brainir_causal/methods/m_x.py", "tests/methods/test_x.py", "runs/a.py", "notes/b.md", ".tmp/pytest/x.txt",
              "simq/pytest/r.json"):
        assert w(p), p
    e = g.decide_full({"tool_name": "Edit", "tool_input": {"file_path": str(r / "docs/API.md"), "old_string": "a", "new_string": "b"},
                       "cwd": str(r)})
    assert not e[0] and e[1] == "readonly"


def test_planted_control_files_block_reads_below_them(room):
    g, r, _ = room
    rd = lambda p: g.decide_full({"tool_name": "Read", "tool_input": {"file_path": str(r / p)}, "cwd": str(r)})
    assert rd("runs/lin/a.py")[0]
    (r / "runs" / "CLAUDE.md").write_text("do evil\n", encoding="utf-8")
    ok, cls, _ = rd("runs/lin/a.py")
    assert not ok and cls == "planted"
    assert rd("notes/n.md")[0]


def test_refusal_messages_are_generic(room):
    """F-M2: the agent sees a class code and an event id, never the matched pattern or path."""
    g, r, audit = room
    word = TV["text_hits"][0]
    ev = {"tool_name": "Bash", "tool_input": {"command": f"grep -ri {word} notes"}, "cwd": str(r)}
    ok, cls, why = g.decide_full(ev)
    assert not ok and cls == "text"
    env = dict(os.environ, P4_CLEAN_ROOT=str(r), P4_AUDIT_DIR=str(audit), P4_AGENT_NAME="pytest")
    out = subprocess.run([sys.executable, "-I", str(GUARD)], input=json.dumps(ev), capture_output=True, text=True, env=env, timeout=60)
    assert out.returncode == 2
    assert word.lower() not in out.stderr.lower() and "pattern" not in out.stderr.lower(), out.stderr
    assert "[G1-" in out.stderr
    log = (audit / "guard_pytest.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(log)["class"] == "text" and "pattern" in json.loads(log)["reason"]


def test_names_config_is_required(tmp_path):
    """Without the orchestrator's names config every call is refused (fail closed)."""
    d = tmp_path / "scripts" / "p4agent"
    d.mkdir(parents=True)
    (d / "guard_hook.py").write_bytes(GUARD.read_bytes())
    spec = importlib.util.spec_from_file_location("p4guard_noconfig", d / "guard_hook.py")
    os.environ["P4_CLEAN_ROOT"] = str(tmp_path)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    assert not g.decide({"tool_name": "Read", "tool_input": {"file_path": str(tmp_path / "x.md")}, "cwd": str(tmp_path)})[0]


def test_free_room_writes_everything_but_the_orchestrators_entries(tmp_path, monkeypatch):
    r = tmp_path / "BrainIR_p4freeroom"
    for d in ("docs", "ref", "src/pkg", ".tmp/pytest", ".claude"):
        (r / d).mkdir(parents=True)
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / f"protected_{r.name}.json").write_text(json.dumps({
        "room": r.name, "files": ["docs/PROTOCOL.md", "ref/protocol.py", "CLAUDE.md", ".claude/README.md", "sbx"], "work_areas": None,
        "agent_areas": [".tmp"]}), encoding="utf-8")
    g = _guard(str(r), audit=str(audit))
    sh = lambda c: _bash(g, r, c)[0]
    assert sh("echo x > src/pkg/a.py") and sh("mkdir results") and sh("echo x > calibration_report.json")
    assert sh("rm -rf src/pkg") and sh("echo x > .tmp/pytest/t")
    assert not sh("echo x > docs/NEW.md") and not sh("rm ref/protocol.py") and not sh("echo x > CLAUDE.md")
    assert not sh("echo x > src/sitecustomize.py") and not sh("echo x > .tmp/other/t")


CASES = [
    # --- file tools, stores, other rooms, tools (no room fixture: the default room path)
    ("Read", {"file_path": rf"{ROOT}\data\x.npz"}, True),
    ("Read", {"file_path": "docs/PROTOCOL.md"}, True),
    ("Read", {"file_path": r"..\BrainIR\x.md"}, False),
    ("Write", {"file_path": rf"{ROOT}\.claude\settings.json", "content": "{}"}, False),
    ("Edit", {"file_path": rf"{ROOT}\CLAUDE.md", "old_string": "a", "new_string": "b"}, False),
    ("Write", {"file_path": rf"{ROOT}\CLAUDE.local.md", "content": "x"}, False),
    ("Write", {"file_path": rf"{ROOT}\runs\x\CLAUDE.md", "content": "x"}, False),
    ("Glob", {"pattern": REPO.as_posix() + "/**/*.md"}, False),
    ("Glob", {"pattern": "**/*.py"}, True),
    ("Glob", {"pattern": "../BrainIR/**/*.md"}, False),
    ("Grep", {"pattern": "x", "path": MAIN}, False),
    ("Grep", {"pattern": "x", "path": "..\\BrainIR"}, False),
    ("PowerShell", {"command": "Get-ChildItem"}, False),
    ("mcp__claude-in-chrome__navigate", {"url": "https://example.com"}, False),
    ("SendMessage", {"to": "main", "message": "hi"}, False),
    ("ListAgents", {}, False),
    ("Monitor", {"command": "ls"}, False),
    ("Task", {"subagent_type": "email-sender", "prompt": "x"}, False),
    ("Task", {"subagent_type": "general-purpose", "prompt": "summarise docs/PROTOCOL.md"}, True),
    ("Task", {"subagent_type": "general-purpose", "prompt": "check that PYTHONPATH is /room/src in the sandbox"}, True),
    ("WebSearch", {"query": "dynamic mode decomposition"}, False),
]


@pytest.mark.parametrize("tool,ti,expected", CASES)
def test_guard_decisions(tool, ti, expected):
    g = _guard(ROOT)
    ok, why = g.decide({"tool_name": tool, "tool_input": ti, "cwd": ROOT})
    assert ok == expected, why


@pytest.mark.parametrize("rel", TV["answer_files"])
def test_answer_bearing_files_are_refused(rel):
    g = _guard(ROOT)
    for ev in ({"tool_name": "Read", "tool_input": {"file_path": str(Path(MAIN) / rel)}},
               {"tool_name": "Bash", "tool_input": {"command": f"cat {(Path(MAIN) / rel).as_posix()}"}},
               {"tool_name": "Bash", "tool_input": {"command": f"cat ../BrainIR/{rel}"}}):
        ok, why = g.decide({**ev, "cwd": ROOT})
        assert not ok, (rel, why)


def test_web_filter_for_the_literature_agent():
    g = _guard(r"C:\Dev\BrainIR_p4lit", web=True)
    assert g.decide({"tool_name": "WebSearch", "tool_input": {"query": "interventional state space model identifiability"}, "cwd": "."})[0]
    for q in TV["web_queries"]:
        ok, cls, why = g.decide_full({"tool_name": "WebSearch", "tool_input": {"query": q}, "cwd": "."})
        assert not ok and cls == "web", q


def test_own_session_store_readable_other_stores_not():
    g = _guard(r"C:\Dev\BrainIR_p4lit")
    home = os.path.expanduser("~")
    own = os.path.join(home, ".claude", "projects", "C--Dev-BrainIR-p4lit", "s", "tool-results", "x.txt")
    other = os.path.join(home, ".claude", "projects", "C--Dev-BrainIR", "memory", "MEMORY.md")
    p3 = os.path.join(home, ".claude", "projects", "C--Dev-" + TV["other_rooms"][0].replace("_", "-"), "s", "x.txt")
    assert g.decide({"tool_name": "Read", "tool_input": {"file_path": own}, "cwd": "."})[0]
    assert not g.decide({"tool_name": "Read", "tool_input": {"file_path": other}, "cwd": "."})[0]
    assert not g.decide({"tool_name": "Read", "tool_input": {"file_path": p3}, "cwd": "."})[0]


def test_other_rooms_by_name_but_not_the_own_room():
    room = r"C:\Dev\BrainIR_p4review"
    g = _guard(room)
    assert g.decide({"tool_name": "Read", "tool_input": {"file_path": room + r"\extra\README.md"}, "cwd": room})[0]
    for other in TV["other_rooms"]:
        ok, cls, _ = g.decide_full({"tool_name": "Read", "tool_input": {"file_path": rf"C:\Dev\{other}\CLAUDE.md"}, "cwd": room})
        assert not ok, other
        assert not g.decide({"tool_name": "Bash", "tool_input": {"command": f"echo {other}"}, "cwd": room})[0], other


def test_links_and_junctions_cannot_be_followed_out_of_the_room(tmp_path):
    import _winapi
    room = tmp_path / "BrainIR_p4linkroom"
    outside = tmp_path / "outside"
    room.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET")
    _winapi.CreateJunction(str(outside), str(room / "lnk"))
    g = _guard(str(room), audit=str(tmp_path / "audit"))
    d = lambda tool, ti: g.decide({"tool_name": tool, "tool_input": ti, "cwd": str(room)})[0]
    assert not d("Bash", {"command": "cat lnk/secret.txt"})
    assert not d("Bash", {"command": "cat lnk"})
    assert not d("Bash", {"command": "cat l*/secret.txt"})
    assert not d("Bash", {"command": "cd lnk && ls"})
    assert not d("Read", {"file_path": str(room / "lnk" / "secret.txt")})
    assert not d("Glob", {"pattern": "**/*.txt"})           # the search root contains a junction
    assert not d("Grep", {"pattern": "SECRET", "path": str(room)})
    os.rmdir(room / "lnk")                                   # removes the junction only
    assert (outside / "secret.txt").exists()
    assert d("Glob", {"pattern": "**/*.txt"})


def test_guard_code_carries_no_names():
    """F-M1: the guard (which enters the review room) holds no name of the config's lists, also after removing regex escapes."""
    spec = importlib.util.spec_from_file_location("p4builder_for_names", REPO / "scripts" / "make_phase4_cleanroom.py")
    b = importlib.util.module_from_spec(spec)
    sys.modules["p4builder_for_names"] = b
    spec.loader.exec_module(b)
    for f in ("scripts/p4agent/guard_hook.py", "scripts/p4agent/launch.py", "scripts/p4agent/audit_transcripts.py",
              "scripts/p4agent/ntfs_protect.py", "scripts/p4agent/sbx_template.sh", "scripts/make_phase4_cleanroom.py",
              "phase4/tests/test_guard_p4.py"):
        text = (REPO / f).read_text(encoding="utf-8")
        assert b.scan_text(text) is None, (f, b.scan_text(text))


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
OUT = os.environ['P4_TEST_OUTSIDE']
t('abs', lambda: open(OUT + '/README.md').read())
t('dot', lambda: open(os.path.dirname(OUT) + '/./' + os.path.basename(OUT) + '/README.md').read())
t('claude_home', lambda: os.listdir(os.path.join(os.path.expanduser('~'), '.claude')))
t('child_I', lambda: subprocess.run([sys.executable, '-I', '-c', 'print(1)']))
def net():
    import socket
    socket.getaddrinfo('example.org', 80)
t('net', net)
def room_ok():
    open(os.path.join(os.environ['P4_CLEAN_ROOT'], 'x.txt'), 'w').write('ok')
t('room_write', room_ok)
print(res)
"""


def test_python_audit_hook_blocks_outside_paths(tmp_path):
    import ast
    room = tmp_path / "BrainIR_p4clean"
    room.mkdir()
    pyguard = REPO / "scripts" / "p4agent" / "pyguard"
    env = dict(os.environ, P4_CLEAN_ROOT=str(room), PYTHONPATH=str(pyguard), TEMP=str(room), TMP=str(room),
               P4_TEST_OUTSIDE=REPO.as_posix())
    out = subprocess.run([sys.executable, "-c", PYGUARD_PROBES], capture_output=True, text=True, env=env, cwd=str(room),
                         timeout=120, check=False)
    res = ast.literal_eval(out.stdout.strip().splitlines()[-1])
    for k in ("abs", "dot", "claude_home", "child_I", "net"):
        assert res[k] == "blocked", (k, res)
    assert res["room_write"] == "ALLOWED", res


@pytest.mark.slow
def test_replay_of_phase3_agent_calls_denies_only_host_execution_in_method_rooms():
    """Every Phase 3 method-room / benchmark-room call that the Phase 4 guard refuses is host execution, a disabled tool, a write
    outside the work areas or a construct that version 3 refuses (data-driven paths, patterns of the earlier rooms)."""
    p3 = Path(os.environ.get("P3_AUDIT_DIR", ""))
    if not (p3 / "agents").exists():
        pytest.skip("no Phase 3 agent streams on this machine (set P3_AUDIT_DIR)")
    sys.path.insert(0, str(GUARD.parent))
    import audit_transcripts as A
    rep = A.replay_p3(p3)
    assert rep["tool_calls"] > 1000
    for room_name, pr in rep["per_room"].items():
        assert pr["denied_host_interpreter"] >= 0.5 * pr["denied"], (room_name, pr)


def test_launcher_issues_a_simulation_token_outside_the_room(tmp_path):
    """F-M4: one fresh token per launch, recorded only by its hash in a table OUTSIDE the room; a table inside the room is refused."""
    spec = importlib.util.spec_from_file_location("p4launch_under_test", REPO / "scripts" / "p4agent" / "launch.py")
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    room, audit = tmp_path / "BrainIR_p4tokroom", tmp_path / "audit"
    room.mkdir()
    tok, path = L.issue_sim_token(room, audit, "dev_a", 500)
    tok2, _ = L.issue_sim_token(room, audit, "dev_b", None)
    assert path == L.sim_tokens_path(room, audit).resolve() and room not in path.parents
    table = json.loads(path.read_text(encoding="utf-8"))
    assert len(tok) == 64 and tok != tok2 and tok not in path.read_text(encoding="utf-8")
    from brainir_causal.simservice import token_hash
    assert table[token_hash(tok)]["agent"] == "dev_a" and table[token_hash(tok)]["budget"] == 500
    assert table[token_hash(tok2)]["agent"] == "dev_b"
    with pytest.raises(SystemExit):
        L.issue_sim_token(room, audit, "dev_c", None, tokens=room / "tokens.json")


# ------------------------------------------------------------------------------------------------ owned shared areas (review F round 2, N-M2)
@pytest.fixture()
def owned_room(tmp_path, monkeypatch):
    """The clean-room layout with per-agent OWNED shared areas; this guard runs as agent / scratch 'lin'."""
    r = tmp_path / "BrainIR_p4ownroom"
    for d in ("docs", "src/brainir_causal/methods/lin", "src/brainir_causal/methods/nn", "runs/lin", "runs/nn", "notes/lin", "notes/nn",
              "tests/methods/lin", "tests/methods/nn", ".tmp/lin", ".tmp/nn", "simq/lin", "simq/nn", ".claude"):
        (r / d).mkdir(parents=True)
    files = {"docs/API.md": "api\n", "src/brainir_causal/api.py": "x = 1\n", "src/brainir_causal/methods/__init__.py": "",
             "CLAUDE.md": "rules\n", "CLAUDE.local.md": "", ".mcp.json": "{}\n", ".claude/README.md": "ro\n",
             "sbx": "#!/usr/bin/env bash\necho sandbox\n", "runs/lin/a.py": "print(1)\n", "runs/nn/b.py": "print(2)\n",
             "notes/old.md": "an earlier flat note\n", "notes/nn/n.md": "nn note\n"}
    for k, v in files.items():
        (r / k).write_text(v, encoding="utf-8", newline="\n")
    audit = tmp_path / "audit"
    bindir = audit / "sbx_bin" / r.name
    bindir.mkdir(parents=True)
    (bindir / "sbx").write_text(files["sbx"], encoding="utf-8", newline="\n")
    manifest = tmp_path / "CLEANROOM_MANIFEST_own.json"
    manifest.write_text(json.dumps({"files": [{"path": "sbx", "sha256": _sha(r / "sbx")}]}), encoding="utf-8")
    listed = [k for k in files if not k.startswith(("runs/", ".tmp/", "notes/"))]
    (audit / f"protected_{r.name}.json").write_text(json.dumps({
        "room": r.name, "files": listed + ["CLEANROOM_MANIFEST.json"],
        "ro_tops": sorted({k.split("/", 1)[0] for k in listed} | {"CLEANROOM_MANIFEST.json"}),
        "work_areas": ["src/brainir_causal/methods", "tests/methods", "runs", "notes", "simq", ".tmp"], "agent_areas": [".tmp", "simq"],
        "owned_areas": ["src/brainir_causal/methods", "tests/methods", "runs", "notes"],
        "sbx_sha256": _sha(r / "sbx"), "outside_sbx": str(bindir / "sbx"), "manifest": str(manifest), "acl": False}), encoding="utf-8")
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    g = _guard(str(r), audit=str(audit), agent="dev_lin", scratch="lin")
    return g, r, audit


OWNED_CASES = [
    ("echo x > runs/lin/b.txt", True),
    ("mkdir -p runs/lin/sub/deeper && cp notes/nn/n.md runs/lin/sub/", True),
    ("cp notes/nn/n.md notes/lin/copy.md", True),
    ("touch src/brainir_causal/methods/lin/__init__.py src/brainir_causal/methods/lin/lin_ssm.py", True),
    ("touch tests/methods/lin/test_lin_ssm.py", True),
    ("cat runs/nn/b.py notes/nn/n.md notes/old.md", True),                 # reading other developers' work is allowed
    ("grep -rn print runs", True),
    ("sort -o runs/lin/s.txt runs/nn/b.py", True),
    ("echo x > runs/nn/b.py", False),
    ("echo x >> notes/nn/n.md", False),
    ("echo x > runs/b.txt", False),                                         # the top of a shared area belongs to nobody
    ("sed -i 's/a/b/' notes/old.md", False),
    ("mkdir runs/zz", False),
    ("rm -r runs/nn", False),
    ("mv runs/nn/b.py runs/lin/b.py", False),
    ("cp runs/lin/a.py runs/nn/a.py", False),
    ("touch src/brainir_causal/methods/lin_flat.py", False),
    ("touch src/brainir_causal/methods/nn/nn_evil.py", False),
    ("touch tests/methods/test_flat.py", False),
    ("tee runs/nn/x.txt < notes/nn/n.md", False),
    ("sort -o runs/nn/s.txt notes/nn/n.md", False),
    ("sort --outp=runs/nn/s.txt notes/nn/n.md", False),
    ("sed --in-pl 's/a/b/' runs/nn/b.py", False),
    ("cp -t runs/nn notes/nn/n.md", False),
    ("echo x > .tmp/nn/x.txt", False),
    ("echo x > simq/nn/requests/r.json", False),
]


@pytest.mark.parametrize("cmd,expected", OWNED_CASES)
def test_owned_areas_bash_decisions(owned_room, cmd, expected):
    g, r, _ = owned_room
    ok, cls, why = _bash(g, r, cmd)
    assert ok == expected, (cls, why)


def test_owned_areas_write_and_edit_tools(owned_room):
    g, r, _ = owned_room
    w = lambda p: g.decide_full({"tool_name": "Write", "tool_input": {"file_path": str(r / p), "content": "x"}, "cwd": str(r)})[0]
    for p in ("runs/lin/x.py", "notes/lin/x.md", "src/brainir_causal/methods/lin/lin_m.py", "tests/methods/lin/test_lin_m.py",
              ".tmp/lin/x", "simq/lin/requests/r.json"):
        assert w(p), p
    for p in ("runs/nn/x.py", "notes/nn/n.md", "notes/x.md", "src/brainir_causal/methods/nn/nn_m.py", "src/brainir_causal/methods/x.py",
              "tests/methods/test_x.py", "tests/methods/nn/test_nn.py", "runs/x.py", ".tmp/nn/x", "simq/nn/r.json"):
        assert not w(p), p
    rd = g.decide_full({"tool_name": "Read", "tool_input": {"file_path": str(r / "runs/nn/b.py")}, "cwd": str(r)})
    assert rd[0], rd


def test_launcher_binds_the_token_to_the_queue_and_keeps_it_out_of_the_environment(tmp_path):
    """Round 2, N-M1: the token is bound to the agent's queue (earlier tokens of that queue revoked) and written to a file OUTSIDE the
    room for the sandbox wrapper; the launcher never puts it into the agent's environment."""
    spec = importlib.util.spec_from_file_location("p4launch_under_test2", REPO / "scripts" / "p4agent" / "launch.py")
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    room, audit = tmp_path / "BrainIR_p4tokroom2", tmp_path / "audit"
    room.mkdir()
    old, path = L.issue_sim_token(room, audit, "dev_li", 500, scratch="li")
    tok, _ = L.issue_sim_token(room, audit, "dev_li", 500, scratch="li")
    other, _ = L.issue_sim_token(room, audit, "dev_nn", 500, scratch="nn")
    from brainir_causal.simservice import token_hash
    table = json.loads(path.read_text(encoding="utf-8"))
    assert token_hash(old) not in table and table[token_hash(tok)]["queue"] == "li" and table[token_hash(other)]["queue"] == "nn"
    f = L.write_agent_token(room, audit, "li", tok)
    assert f == L.agent_token_file(room, audit, "li").resolve() and room not in f.parents and f.read_text(encoding="ascii") == tok
    L.write_agent_token(room, audit, "li", None)
    assert not f.exists()
    src = (REPO / "scripts" / "p4agent" / "launch.py").read_text(encoding="utf-8")
    assert 'env["P4_SIM_TOKEN"]' not in src
