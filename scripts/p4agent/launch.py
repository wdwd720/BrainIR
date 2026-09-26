"""Launch a Phase 4 room agent as a SEPARATE headless Claude Code session (goal5 sections 4-5; research/phase4/LEAKAGE_POLICY.md).

    uv run --project phase4 python scripts/p4agent/launch.py --name <agent> --room C:\\Dev\\BrainIR_p4bench --prompt-file <file>
                                    [--allow-web] [--model opus] [--resume <session-id>] [--sbx-cpus 2] [--sbx-mem-gb 6]

The session's project directory is the room: it loads only the room's CLAUDE.md, gets its own memory and transcript store, and never
inherits the orchestrator's context. Isolation layers:
    1. PreToolUse guard (scripts/p4agent/guard_hook.py, run with `python -I` outside the room): paths must resolve inside the room;
       host commands limited to file / text tools; ALL code through the Docker sandbox wrapper `sbx`; protected room files; no MCP;
       web only with --allow-web (methods-only queries);
    2. the Docker sandbox (`sbx`, image brainir-p4-sandbox:1): only the room mounted (allowlisted paths read-only), no network, no
       capabilities, seccomp without symlink creation, CPU / memory / pid caps. The wrapper copy on the agent's PATH lives OUTSIDE the
       room (C:\\Dev\\BrainIR_p4audit\\sbx_bin\\<room>\\sbx) and must match the room manifest's hash, else the launch is refused;
    3. Python audit hook (pyguard via PYTHONPATH) for any host Python (none should run: host interpreters are refused);
    4. permission deny rules for the main repository, every other room, the orchestrator's stores, credentials and caches;
    5. no MCP servers; cross-session, scheduling, notification and PowerShell tools disallowed;
    6. a private TEMP inside the room;
    7. the full event stream written OUTSIDE the room (<audit>/agents/) for the transcript audit.
Prints the session id and the final result; exit code = the CLI's.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_AUDIT = Path(r"C:\Dev\BrainIR_p4audit")
OTHER_ROOMS = ("BrainIR", "BrainIR_p2clean", "BrainIR_p3audit", "BrainIR_p3audit_test", "BrainIR_p3bench", "BrainIR_p3clean",
               "BrainIR_p3guardtest", "BrainIR_p3lit", "BrainIR_p3postreview", "BrainIR_p3regen", "BrainIR_p3review", "BrainIR_p3reviewG",
               "BrainIR_p3run", "BrainIR_p3smoke", "BrainIR_p4clean", "BrainIR_p4bench", "BrainIR_p4lit", "BrainIR_p4review",
               "BrainIR_p4audit", "BrainIR_p4run", "BrainIR_p4guardtest", "BrainIR_p4canary", "BrainIR_p4bench_test")


def _claude() -> str:
    npm = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if npm.exists():
        return str(npm)
    exe = shutil.which("claude.exe") or shutil.which("claude")
    if not exe:
        raise SystemExit("the claude CLI is not on PATH")
    return exe


def _sha_text(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def settings_json(python: str, room: Path) -> dict:
    guard = (HERE / "guard_hook.py").as_posix()
    cmd = f'"{Path(python).as_posix()}" -I "{guard}"'
    pats = ["~/.claude/projects/C--Dev-BrainIR/**", "~/.claude/projects/C--Dev-BrainIR-p*/**", "~/.claude/.credentials.json",
            "~/.claude/settings.json", "~/.claude.json", "~/.modal.toml", "~/.claude/file-history/**", "~/.claude/paste-cache/**",
            "~/.claude/history.jsonl", "~/.claude/todos/**", "~/.claude/shell-snapshots/**", "~/.claude/sessions/**",
            "~/.claude/plugins/**", "~/AppData/Local/uv/cache/**", "~/AppData/Local/Temp/claude/**"]
    for r in OTHER_ROOMS:
        if r.lower() == room.name.lower():
            continue
        pats += [f"//c/Dev/{r}/**", f"//C:/Dev/{r}/**"]
    deny = [f"{tool}({pat})" for tool in ("Read", "Edit", "Write") for pat in pats]
    return {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd, "timeout": 30}]}]},
            "permissions": {"deny": deny}, "includeCoAuthoredBy": False}


def check_sandbox(room: Path, audit: Path) -> Path:
    """The outside sbx copy must exist and equal the room's manifest record (built by scripts/make_phase4_cleanroom.py)."""
    bindir = audit / "sbx_bin" / room.name
    outside, inside, man = bindir / "sbx", room / "sbx", room / "CLEANROOM_MANIFEST.json"
    if not (outside.exists() and inside.exists() and man.exists()):
        raise SystemExit(f"{room} has no sandbox wrapper / manifest: build the room with scripts/make_phase4_cleanroom.py")
    manifest = json.loads(man.read_text(encoding="utf-8"))
    want = next((e["sha256"] for e in manifest["files"] if e["path"] == "sbx"), None)
    if not (want and _sha_text(outside) == want == _sha_text(inside)):
        raise SystemExit("sandbox wrapper differs from the room manifest: rebuild / --sync the room")
    image = (manifest.get("sandbox") or {}).get("image")
    ok = subprocess.run(["docker", "image", "inspect", str(image), "--format", "{{.Id}}"], capture_output=True, text=True)
    if not image or ok.returncode != 0 or ok.stdout.strip() != image:
        raise SystemExit(f"the room's sandbox image {image} is not present locally: build it or --sync the room to the current image")
    return bindir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--room", type=Path, required=True)
    ap.add_argument("--prompt-file", type=Path)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--allow-web", action="store_true")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--resume", default=None, help="continue an earlier session of this agent")
    ap.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--sbx-cpus", default="2")
    ap.add_argument("--sbx-mem-gb", default="6")
    args = ap.parse_args(argv)
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    room, audit = args.room.resolve(), args.audit.resolve()
    if not (room / "CLAUDE.md").exists():
        raise SystemExit(f"{room} has no CLAUDE.md: build the room first")
    bindir = check_sandbox(room, audit)
    (audit / "agents").mkdir(parents=True, exist_ok=True)
    pyguard = audit / "pyguard"
    pyguard.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "pyguard" / "sitecustomize.py", pyguard / "sitecustomize.py")
    python = sys.executable
    sfile = audit / "agents" / f"{args.name}.settings.json"
    sfile.write_text(json.dumps(settings_json(python, room), indent=1), encoding="utf-8")
    mcp = audit / "agents" / "empty_mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    tmp = room / ".tmp" / args.name
    tmp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for k in list(env):
        if k.upper().startswith(("P3_", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "CLAUDE_PROJECT_DIR", "PYTHONHOME", "DOCKER_")):
            env.pop(k, None)
    env.update(P4_CLEAN_ROOT=str(room), P4_AUDIT_DIR=str(audit), P4_AGENT_NAME=args.name, P4_ALLOW_WEB="1" if args.allow_web else "0",
               P4_SANDBOX="1", P4_SBX_CPUS=str(args.sbx_cpus), P4_SBX_MEM_GB=str(args.sbx_mem_gb), PYTHONPATH=str(pyguard),
               TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp), PYTHONIOENCODING="utf-8")
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    cmd = [_claude(), "-p", "--output-format", "stream-json", "--verbose", "--settings", str(sfile), "--strict-mcp-config",
           "--mcp-config", str(mcp), "--dangerously-skip-permissions", "--model", args.model]
    blocked = ["ListAgents", "SendMessage", "RemoteTrigger", "PushNotification", "CronCreate", "CronDelete", "CronList", "ScheduleWakeup",
               "DesignSync", "EnterWorktree", "ExitWorktree", "PowerShell", "Monitor", "Workflow"]
    if not args.allow_web:
        blocked += ["WebSearch", "WebFetch"]
    cmd += ["--disallowedTools", *blocked]
    if args.resume:
        cmd += ["--resume", args.resume]
    if args.max_turns:
        cmd += ["--max-turns", str(args.max_turns)]
    stamp = time.strftime("%Y%m%dT%H%M%S")
    stream = audit / "agents" / f"{args.name}.{stamp}.jsonl"
    meta = {"name": args.name, "started": stamp, "clean": str(room), "room": str(room), "allow_web": args.allow_web, "model": args.model,
            "resume": args.resume, "stream": str(stream), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "sbx": {"bindir": str(bindir), "cpus": args.sbx_cpus, "mem_gb": args.sbx_mem_gb}}
    session_id, result = None, None
    with open(stream, "w", encoding="utf-8") as out:
        proc = subprocess.Popen(cmd, cwd=str(room), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            out.write(line)
            out.flush()
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "system" and ev.get("subtype") == "init":
                session_id = ev.get("session_id")
            if ev.get("type") == "result":
                result = ev
        rc = proc.wait()
    meta.update(session_id=session_id, exit_code=rc, finished=time.strftime("%Y%m%dT%H%M%S"),
                cost_usd=(result or {}).get("total_cost_usd"), num_turns=(result or {}).get("num_turns"),
                is_error=(result or {}).get("is_error"))
    (audit / "agents" / f"{args.name}.{stamp}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"session {session_id} exit {rc} turns {meta['num_turns']}")
    print((result or {}).get("result", "")[-6000:])
    return rc


if __name__ == "__main__":
    sys.exit(main())
