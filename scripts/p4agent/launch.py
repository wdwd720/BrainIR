"""Launch a Phase 4 room agent as a SEPARATE headless Claude Code session (goal5 sections 4-5; research/phase4/LEAKAGE_POLICY.md).

    uv run --project phase4 python scripts/p4agent/launch.py --name <agent> --room C:\\Dev\\BrainIR_p4bench --prompt-file <file>
                                    [--scratch <dir>] [--allow-web] [--model opus] [--resume <session-id>] [--sbx-cpus 2]
                                    [--sbx-mem-gb 6]

The session's project directory is the room: it loads only the room's CLAUDE.md, gets its own memory and transcript store, and never
inherits the orchestrator's context. Isolation layers:
    1. PreToolUse guard (scripts/p4agent/guard_hook.py, run with `python -I` outside the room; names from the orchestrator's config
       scripts/p4config/names.py): paths must resolve inside the room and outside other agents' private areas; host commands limited
       to file / text tools; writes only into the work areas; ALL code through the bare command `sbx`; no MCP; web only with
       --allow-web (methods-only queries); generic refusal messages;
    2. the Docker sandbox (`sbx`): the room mounted READ-ONLY with only the work areas and the agent's own .tmp/<scratch> read-write,
       no network, no capabilities, seccomp without link creation, CPU / memory / pid caps, no bytecode written into the room. The
       wrapper on the agent's PATH is the copy OUTSIDE the room (C:\\Dev\\BrainIR_p4audit\\sbx_bin\\<room>\\sbx); it must match the
       outside manifest's record and carry its NTFS deny ACE, else the launch is refused (the guard re-checks it on every call);
    3. OS-level immutability of the room's allowlisted files and directories (NTFS deny ACE; scripts/p4agent/ntfs_protect.py): the
       launch is refused when the room's protection is missing;
    4. Python audit hook (pyguard via PYTHONPATH) for any host Python (none should run: host interpreters are refused);
    5. permission deny rules for the main repository, every other room, the orchestrator's stores, credentials and caches;
    6. no MCP servers; cross-session, scheduling, notification and PowerShell tools disallowed;
    7. a private TEMP inside the room (.tmp/<scratch>; other agents' .tmp is refused by the guard and invisible in the sandbox);
    8. the simulation-service identity (review F, F-M4; round 2, N-M1): a fresh secret token per launch
       (brainir_causal.simservice.issue_token), BOUND to the agent's queue simq/<scratch>/ (the service refuses it in any other queue;
       the launch revokes the queue's earlier tokens), recorded by its hash in the service's token table OUTSIDE the room (default
       <audit>/simservice/<room>/tokens.json; start the service with --tokens <that file> and a ledger directory outside the room)
       and written to <audit>/simservice/<room>/agent_tokens/<scratch>.token (outside the room): the sandbox wrapper reads it and
       forwards it into the container as P4_SIM_TOKEN; the agent's host environment never holds it (the guard also refuses agent-set
       P4_* variables and any mention of P4_SIM_TOKEN in host commands);
    9. the full event stream written OUTSIDE the room (<audit>/agents/) for the transcript audit.
Prints the session id and the final result; exit code = the CLI's.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_AUDIT = Path(r"C:\Dev\BrainIR_p4audit")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _names():
    """The orchestrator's names config (never in a room): the room names for the deny rules."""
    p = HERE.parent / "p4config" / "names.py"
    if not p.exists():
        raise SystemExit("the names config scripts/p4config/names.py (orchestrator only) is missing")
    return _load("p4config_names_launch", p)


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
    for r in ("BrainIR",) + tuple(_names().ROOMS):
        if r.lower() == room.name.lower():
            continue
        pats += [f"//c/Dev/{r}/**", f"//C:/Dev/{r}/**"]
    deny = [f"{tool}({pat})" for tool in ("Read", "Edit", "Write") for pat in pats]
    return {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd, "timeout": 30}]}]},
            "permissions": {"deny": deny}, "includeCoAuthoredBy": False}


def sim_tokens_path(room: Path, audit: Path) -> Path:
    return audit / "simservice" / room.name / "tokens.json"


def agent_token_file(room: Path, audit: Path, scratch: str) -> Path:
    """Where the sandbox wrapper reads the agent's simulation token (outside the room; `make_phase4_cleanroom.render_sbx` bakes the
    directory into the wrapper)."""
    return audit / "simservice" / room.name / "agent_tokens" / f"{scratch}.token"


def issue_sim_token(room: Path, audit: Path, agent: str, budget: int | None, tokens: Path | None = None, *,
                    scratch: str | None = None) -> tuple[str, Path]:
    """A fresh simulation-service token for this agent, bound to its queue simq/<scratch>/, in the token table OUTSIDE the room (review
    F, F-M4; round 2, N-M1); earlier tokens of the same queue are revoked."""
    path = (tokens or sim_tokens_path(room, audit)).resolve()
    if path == room or room in path.parents:
        raise SystemExit(f"{path} lies inside the room: the token table must stay outside it")
    from brainir_causal.simservice import issue_token                       # the phase4 project environment (uv run --project phase4)
    return issue_token(path, agent, budget, queue=scratch, revoke_queue=scratch is not None), path


def write_agent_token(room: Path, audit: Path, scratch: str, token: str | None) -> Path:
    """Write (or, with token None, remove) the agent's token file for the sandbox wrapper; atomic; outside the room."""
    f = agent_token_file(room, audit, scratch).resolve()
    if f == room or room in f.parents:
        raise SystemExit(f"{f} lies inside the room")
    f.parent.mkdir(parents=True, exist_ok=True)
    if token is None:
        f.unlink(missing_ok=True)
        return f
    tmp = f.with_name(f".{f.name}.{os.getpid()}.tmp")
    tmp.write_text(token, encoding="ascii")
    os.replace(tmp, f)
    return f


def check_sandbox(room: Path, audit: Path) -> tuple[Path, dict]:
    """The outside sbx copy must exist, equal the OUTSIDE manifest's record (and the room's protected list) and, when the room was
    built with OS protection, still carry its deny ACE; the room's sandbox image must be present locally."""
    bindir = audit / "sbx_bin" / room.name
    outside, prot_file = bindir / "sbx", audit / f"protected_{room.name}.json"
    if not (outside.exists() and prot_file.exists()):
        raise SystemExit(f"{room} has no sandbox wrapper / protected list: build the room with scripts/make_phase4_cleanroom.py")
    prot = json.loads(prot_file.read_text(encoding="utf-8"))
    if not prot.get("manifest"):
        raise SystemExit(f"{room} was built by an older room builder: --sync it (scripts/make_phase4_cleanroom.py --room <r> --sync ...)")
    manifest = json.loads(Path(prot["manifest"]).read_text(encoding="utf-8"))
    want = next((e["sha256"] for e in manifest["files"] if e["path"] == "sbx"), None)
    if not (want and want == prot.get("sbx_sha256") == _sha_text(outside)):
        raise SystemExit("sandbox wrapper differs from the outside manifest: rebuild / --sync the room")
    if prot.get("acl"):
        acl = _load("p4_ntfs_launch", HERE / "ntfs_protect.py")
        paths = [outside] + [room / f for f in prot.get("files") or []]
        missing = acl.check_paths([str(p) for p in paths])
        if missing:
            raise SystemExit(f"the room's OS protection is missing on {len(missing)} paths (e.g. {missing[0]}): --sync the room")
    image = (manifest.get("sandbox") or {}).get("image") or prot.get("image")
    ok = subprocess.run(["docker", "image", "inspect", str(image), "--format", "{{.Id}}"], capture_output=True, text=True)
    if not image or ok.returncode != 0 or ok.stdout.strip() != image:
        raise SystemExit(f"the room's sandbox image {image} is not present locally: build it or --sync the room to the current image")
    return bindir, prot


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--room", type=Path, required=True)
    ap.add_argument("--prompt-file", type=Path)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--scratch", default=None, help="the agent's private subdirectory of .tmp/ (and simq/) (default: --name)")
    ap.add_argument("--allow-web", action="store_true")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--resume", default=None, help="continue an earlier session of this agent")
    ap.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--sbx-cpus", default="2")
    ap.add_argument("--sbx-mem-gb", default="6")
    ap.add_argument("--sim-tokens", type=Path, default=None, help="the simulation service's token table (default: "
                                                                    "<audit>/simservice/<room>/tokens.json; outside the room)")
    ap.add_argument("--sim-budget", type=int, default=None, help="this agent's simulation budget (default: the service's)")
    ap.add_argument("--no-sim-token", action="store_true", help="rooms without a simulation service")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", args.name) or (args.scratch and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*",
                                                                                                         args.scratch)):
        raise SystemExit("--name / --scratch: letters, digits, _ . - only")
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    room, audit = args.room.resolve(), args.audit.resolve()
    if not (room / "CLAUDE.md").exists():
        raise SystemExit(f"{room} has no CLAUDE.md: build the room first")
    bindir, prot = check_sandbox(room, audit)
    scratch = args.scratch or args.name
    (audit / "agents").mkdir(parents=True, exist_ok=True)
    pyguard = audit / "pyguard"
    pyguard.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "pyguard" / "sitecustomize.py", pyguard / "sitecustomize.py")
    python = sys.executable
    sfile = audit / "agents" / f"{args.name}.settings.json"
    sfile.write_text(json.dumps(settings_json(python, room), indent=1), encoding="utf-8")
    mcp = audit / "agents" / "empty_mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    tmp = room / ".tmp" / scratch
    tmp.mkdir(parents=True, exist_ok=True)
    for area in (prot.get("agent_areas") or []) + (prot.get("owned_areas") or []):     # private and shared per-agent subdirectories
        if area != ".tmp" and (room / area).is_dir():
            (room / area / scratch).mkdir(exist_ok=True)
    env = dict(os.environ)
    for k in list(env):
        if k.upper().startswith(("P3_", "P4_", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "CLAUDE_PROJECT_DIR", "PYTHONHOME", "DOCKER_",
                                 "MODAL_")):
            env.pop(k, None)
    env.update(P4_CLEAN_ROOT=str(room), P4_AUDIT_DIR=str(audit), P4_AGENT_NAME=args.name, P4_AGENT_SCRATCH=scratch,
               P4_ALLOW_WEB="1" if args.allow_web else "0", P4_SANDBOX="1", P4_SBX_CPUS=str(args.sbx_cpus),
               P4_SBX_MEM_GB=str(args.sbx_mem_gb), PYTHONPATH=str(pyguard), TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp),
               PYTHONIOENCODING="utf-8")
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    token_rec = None
    if not args.no_sim_token:
        token, tpath = issue_sim_token(room, audit, args.name, args.sim_budget, args.sim_tokens, scratch=scratch)
        tfile = write_agent_token(room, audit, scratch, token)             # read by the sandbox wrapper; never the host environment
        token_rec = {"table": str(tpath), "queue": scratch, "file": str(tfile),
                     "token_sha256_prefix": hashlib.sha256(("p4-sim-token|" + token).encode()).hexdigest()[:12]}
    else:
        write_agent_token(room, audit, scratch, None)
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
    meta = {"name": args.name, "scratch": scratch, "started": stamp, "clean": str(room), "room": str(room), "allow_web": args.allow_web,
            "model": args.model, "resume": args.resume, "stream": str(stream), "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "sbx": {"bindir": str(bindir), "cpus": args.sbx_cpus, "mem_gb": args.sbx_mem_gb}, "sim_token": token_rec}
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
    try:
        sys.stdout.reconfigure(errors="replace")                               # a cp1252 console must not crash the final report
    except (AttributeError, ValueError):
        pass
    print(f"session {session_id} exit {rc} turns {meta['num_turns']}")
    print((result or {}).get("result", "")[-6000:])
    return rc


if __name__ == "__main__":
    sys.exit(main())
