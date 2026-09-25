"""Launch a Phase 3 clean-room agent as a SEPARATE headless Claude Code session (goal4 section 3; review D finding D2).

    uv run python scripts/p3agent/launch.py --name <agent> --prompt-file <file> [--allow-web] [--model opus]
                                            [--resume <session-id>] [--clean C:\\Dev\\BrainIR_p3clean]

The session's project directory is the clean room, so it loads only the clean room's CLAUDE.md, gets its own memory and
transcript store, and never inherits the orchestrator's context. Isolation layers:
    1. PreToolUse guard hook (scripts/p3agent/guard_hook.py, run with `python -I` outside the clean room): denies every tool
       call touching paths outside the clean room, all MCP tools, and web access unless --allow-web (then methods-only queries);
    2. Python audit hook (scripts/p3agent/pyguard/sitecustomize.py via PYTHONPATH): blocks file and process events on forbidden
       locations in every Python the agent starts;
    3. no MCP servers (--strict-mcp-config with an empty config); web tools disallowed unless --allow-web;
    4. a private TEMP inside the clean room;
    5. the full event stream is written OUTSIDE the clean room (P3_AUDIT_DIR/agents/) for the transcript audit.
Prints the session id and the final result; exit code = the CLI's.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_CLEAN = Path(r"C:\Dev\BrainIR_p3clean")
DEFAULT_AUDIT = Path(r"C:\Dev\BrainIR_p3audit")


def _claude() -> str:
    """The native CLI binary, not the npm .cmd shim (cmd.exe would cut arguments at newlines and interpret metacharacters)."""
    npm = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if npm.exists():
        return str(npm)
    exe = shutil.which("claude.exe") or shutil.which("claude")
    if not exe:
        raise SystemExit("the claude CLI is not on PATH")
    return exe


def settings_json(python: str) -> dict:
    guard = (HERE / "guard_hook.py").as_posix()
    cmd = f'"{Path(python).as_posix()}" -I "{guard}"'
    # the agent's own session store (~/.claude/projects/<its key>) must stay readable (large tool results are saved there), so
    # ~/.claude is not denied wholesale here: the guard hook allows only that store and denies every other session's
    deny = [f"{tool}({pat})" for tool in ("Read", "Edit", "Write") for pat in
            ("//c/Dev/BrainIR/**", "//C:/Dev/BrainIR/**", "~/.claude/projects/C--Dev-BrainIR/**", "~/.claude/.credentials.json",
             "~/.claude/settings.json", "~/.claude.json", "~/.modal.toml", "//c/Dev/BrainIR_p2clean/**", "//c/Dev/BrainIR_p3audit/**",
             # review F (F-M1, F-M2): the answer-aware session's history stores and the uv cache
             "~/.claude/file-history/**", "~/.claude/paste-cache/**", "~/.claude/history.jsonl", "~/.claude/todos/**",
             "~/.claude/shell-snapshots/**", "~/.claude/sessions/**", "~/AppData/Local/uv/cache/**", "//c/Dev/BrainIR_p3run/**",
             "//c/Dev/BrainIR_p3regen/**")]
    return {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd, "timeout": 30}]}]},
            "permissions": {"deny": deny}, "includeCoAuthoredBy": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--prompt-file", type=Path)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--allow-web", action="store_true")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--resume", default=None, help="continue an earlier session of this agent")
    ap.add_argument("--clean", type=Path, default=DEFAULT_CLEAN)
    ap.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    ap.add_argument("--max-turns", type=int, default=None)
    args = ap.parse_args(argv)
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    clean, audit = args.clean.resolve(), args.audit.resolve()
    if not (clean / "CLAUDE.md").exists():
        raise SystemExit(f"{clean} has no CLAUDE.md: build the clean room first")
    (audit / "agents").mkdir(parents=True, exist_ok=True)
    pyguard = audit / "pyguard"
    pyguard.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "pyguard" / "sitecustomize.py", pyguard / "sitecustomize.py")
    python = sys.executable
    sfile = audit / "agents" / f"{args.name}.settings.json"
    sfile.write_text(json.dumps(settings_json(python), indent=1), encoding="utf-8")
    mcp = audit / "agents" / "empty_mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    tmp = clean / ".tmp" / args.name
    tmp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(P3_CLEAN_ROOT=str(clean), P3_AUDIT_DIR=str(audit), P3_AGENT_NAME=args.name, P3_ALLOW_WEB="1" if args.allow_web else "0",
               PYTHONPATH=str(pyguard), TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp), PYTHONIOENCODING="utf-8")
    for k in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "CLAUDE_PROJECT_DIR"):
        env.pop(k, None)
    uv_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe"
    if (uv_dir / "uv.exe").exists():
        env["PATH"] = str(uv_dir) + os.pathsep + env.get("PATH", "")
    cmd = [_claude(), "-p", "--output-format", "stream-json", "--verbose", "--settings", str(sfile), "--strict-mcp-config",
           "--mcp-config", str(mcp), "--dangerously-skip-permissions", "--model", args.model]
    blocked = ["ListAgents", "SendMessage", "RemoteTrigger", "PushNotification", "CronCreate", "CronDelete", "CronList", "ScheduleWakeup",
               "DesignSync", "EnterWorktree", "ExitWorktree"]
    if not args.allow_web:
        blocked += ["WebSearch", "WebFetch"]
    cmd += ["--disallowedTools", *blocked]
    if args.resume:
        cmd += ["--resume", args.resume]
    if args.max_turns:
        cmd += ["--max-turns", str(args.max_turns)]
    stamp = time.strftime("%Y%m%dT%H%M%S")
    stream = audit / "agents" / f"{args.name}.{stamp}.jsonl"
    meta = {"name": args.name, "started": stamp, "clean": str(clean), "allow_web": args.allow_web, "model": args.model, "resume": args.resume,
            "stream": str(stream), "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest()}
    session_id, result = None, None
    with open(stream, "w", encoding="utf-8") as out:
        # the prompt goes through stdin: never through the command line
        proc = subprocess.Popen(cmd, cwd=str(clean), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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
