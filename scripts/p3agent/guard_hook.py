"""PreToolUse guard for Phase 3 clean-room agents (goal4 section 3: technological isolation, read-deny hook, path audit).

Runs as a Claude Code hook OUTSIDE the clean room. It receives the pending tool call on stdin (JSON: tool_name, tool_input, cwd,
session_id, ...) and blocks it (exit code 2, reason on stderr) when it would touch anything outside the clean room, or when a web
query names the benchmark's datasets or circuit. Every decision is appended to a JSONL audit log outside the clean room.

Environment (set by scripts/p3agent/launch.py):
    P3_CLEAN_ROOT   the clean room (default C:\\Dev\\BrainIR_p3clean)
    P3_AUDIT_DIR    where decisions are logged (default C:\\Dev\\BrainIR_p3audit)
    P3_AGENT_NAME   label of the agent (log file name)
    P3_ALLOW_WEB    "1" to allow WebSearch / WebFetch (methods-only queries); anything else denies all web access

This is defence in depth, not a kernel sandbox: a program started by an allowed command could construct a forbidden path at run
time. The Python layer (scripts/p3agent/pyguard/sitecustomize.py, loaded through PYTHONPATH) covers Python; every session
transcript is audited afterwards (scripts/p3agent/audit_transcripts.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

CLEAN = os.path.normcase(os.path.abspath(os.environ.get("P3_CLEAN_ROOT", r"C:\Dev\BrainIR_p3clean")))
AUDIT_DIR = os.environ.get("P3_AUDIT_DIR", r"C:\Dev\BrainIR_p3audit")
AGENT = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("P3_AGENT_NAME", "unknown"))
ALLOW_WEB = os.environ.get("P3_ALLOW_WEB", "0") == "1"
HOME = os.path.normcase(os.path.expanduser("~"))

# the clean room's own name after "BrainIR" (e.g. "_p3clean"): the only "Dev/BrainIR..." location a tool input may name
_BASE = os.path.basename(CLEAN)
_SUFFIX = re.escape(_BASE[len("brainir"):]) if _BASE.lower().startswith("brainir") and len(_BASE) > len("brainir") else "(?!)"
# substrings that are never allowed in any tool input (case-insensitive regexes)
FORBIDDEN_PATTERNS = [
    rf"dev[\\/]+brainir(?!{_SUFFIX})",               # the main repository and every other BrainIR directory
    r"brainir_p2clean",                               # the Phase 2 clean room (holds answer-structure documents)
    r"brainir_p3audit",                               # this guard's own logs
    r"\.claude[\\/]+projects",                        # every Claude session transcript and memory
    r"\.claude[\\/]+(settings|file-history|history|sessions|shell-snapshots|todos|agent-memory|backups)",
    r"\.credentials", r"\.modal\.toml", r"\.claude\.json",
    rf"c--dev-brainir(?!{_SUFFIX.replace('_', '-')})",  # the orchestrator's temp / project folders
    r"phase2_report", r"hidden_eval", r"blind_eval", r"dng100_walking_cpg", r"[\\/]oracle[\\/]",
    r"\bpythonpath\b", r"\bpython[0-9.]*(\.exe)?\s+-[a-zA-Z]*[ISE]",   # disabling the Python guard
    r"disableallhooks",
]
# web queries / URLs must not name the benchmark's circuit, datasets or source paper
WEB_BLOCK = [r"dng100", r"\bbdn2\b", r"pugliese", r"walking\s*cpg", r"walking\s+central\s+pattern", r"malecns", r"male\s*cns",
             r"\bmanc\b", r"neuprint", r"flywire", r"ventral\s+nerve\s+cord", r"drosophila", r"\bfly\b.*\b(leg|walking|motor)",
             r"descending\s+neuron", r"front[-\s]?leg", r"hemibrain", r"connectome"]

# tools that reach other sessions, the user's devices or run later on their own
BLOCKED_TOOLS = {"ListAgents", "SendMessage", "RemoteTrigger", "PushNotification", "CronCreate", "CronDelete", "CronList", "ScheduleWakeup",
                 "DesignSync", "EnterWorktree", "ExitWorktree", "SendUserFile", "FetchInboxMessage", "ReadNotifications", "Artifact",
                 "ArtifactComments", "ArtifactData", "ArtifactCheck", "SendFeedback"}
ALLOWED_SUBAGENTS = {"general-purpose", "Explore", "Plan", "claude"}

PATH_TOKEN = re.compile(r"""(?ix)
    (?:[a-z]:[\\/][^\s"'`|;&<>()]*)          # C:\... or C:/...
  | (?:(?<![\w.])/[a-z]/[^\s"'`|;&<>()]*)    # /c/... (Git Bash drive)
  | (?:\\\\[^\s"'`|;&<>()]+)                 # UNC
  | (?:~[\\/][^\s"'`|;&<>()]*)               # ~/...
  | (?:(?<![\w.])/(?:tmp|home|users|mnt|etc|root|var)(?:/[^\s"'`|;&<>()]*)?)
""")
ENV_HOME = re.compile(r"(?i)(\$\{?(home|userprofile|appdata|localappdata|temp|tmp)\}?|%(userprofile|appdata|localappdata|temp|tmp|homepath)%)")


def _log(decision: str, tool: str, reason: str, detail: str) -> None:
    try:
        Path(AUDIT_DIR).mkdir(parents=True, exist_ok=True)
        with open(Path(AUDIT_DIR) / f"guard_{AGENT}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": AGENT, "decision": decision, "tool": tool,
                                 "reason": reason, "detail": detail[:500]}) + "\n")
    except OSError:
        pass


def _norm(p: str, cwd: str) -> str:
    p = p.strip().strip("\"'")
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    if m:                                             # Git Bash drive path
        p = f"{m.group(1)}:/{m.group(2)}"
    if p.startswith("~"):
        p = os.path.expanduser(p)
    if not os.path.isabs(p) and not re.match(r"^[a-zA-Z]:", p):
        p = os.path.join(cwd or CLEAN, p)
    return os.path.normcase(os.path.abspath(p))


def _inside(p: str) -> bool:
    if p == CLEAN or p.startswith(CLEAN + os.sep):
        return True
    own = os.path.normcase(os.path.join(os.path.expanduser("~"), ".claude", "projects", OWN_KEY))
    return p == own or p.startswith(own + os.sep)


# the agent's OWN session store (~/.claude/projects/<key of the clean room>/): large tool results are saved there by the CLI and the
# agent must be able to read them back; every other session's store stays forbidden
OWN_KEY = re.sub(r"[^A-Za-z0-9]", "-", os.environ.get("P3_CLEAN_ROOT", r"C:\Dev\BrainIR_p3clean"))
OWN_STORE = re.compile(r"(?i)\.claude[\\/]+projects[\\/]+" + re.escape(OWN_KEY) + r"(?=[\\/\"'\s]|$)")


def _strip_own_store(s: str) -> str:
    return OWN_STORE.sub("<own-session-store>", s)


def _forbidden_text(s: str) -> str | None:
    s = _strip_own_store(s)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, s, flags=re.IGNORECASE):
            return f"forbidden pattern {pat!r}"
    return None


ALLOWED_OUTSIDE = [re.compile(p, re.IGNORECASE) for p in (
    r"^[a-z]:[\\/]+users[\\/]+[^\\/]+[\\/]+appdata[\\/]+roaming[\\/]+uv[\\/]+python",     # uv-managed interpreters
    r"^[a-z]:[\\/]+users[\\/]+[^\\/]+[\\/]+appdata[\\/]+local[\\/]+uv[\\/]+cache",        # uv cache
    r"^[a-z]:[\\/]+users[\\/]+[^\\/]+[\\/]+appdata[\\/]+local[\\/]+microsoft[\\/]+winget[\\/]+packages[\\/]+astral-sh\.uv",
    r"^[a-z]:[\\/]+program files[\\/]+git", r"^/dev/null$", r"^nul$",
)]


def _check_bash(cmd: str, cwd: str) -> str | None:
    why = _forbidden_text(cmd)
    if why:
        return why
    if ENV_HOME.search(cmd):
        return "home/temp environment variables are not allowed (use paths inside the clean room)"
    # quoted strings are checked whole (paths may contain spaces), then removed before the unquoted scan
    quoted = [a or b for a, b in re.findall(r'"([^"]*)"|\'([^\']*)\'', cmd)]
    for q in quoted:
        if re.match(r"^\s*([a-zA-Z]:[\\/]|/[a-zA-Z]/|\\\\|~[\\/])", q):
            if not any(a.match(q.strip()) for a in ALLOWED_OUTSIDE) and not _inside(_norm(q, cwd)):
                return f"path outside the clean room: {q[:120]}"
    unquoted = re.sub(r'"[^"]*"|\'[^\']*\'', " ", cmd)
    for tok in PATH_TOKEN.findall(unquoted):
        raw = tok.strip().rstrip(",")
        if any(a.match(raw) for a in ALLOWED_OUTSIDE):
            continue
        if not _inside(_norm(raw, cwd)):
            return f"path outside the clean room: {raw[:120]}"
    # relative escapes: any token with a '..' segment must still resolve inside the clean room
    for tok in re.findall(r"[^\s\"'`|;&<>()]*\.\.[^\s\"'`|;&<>()]*", cmd):
        if re.search(r"(^|[\\/])\.\.([\\/]|$)", tok) and not _inside(_norm(tok, cwd)):
            return f"relative path escapes the clean room: {tok[:120]}"
    for m in re.finditer(r"(?:^|[;&|]\s*|\s)(?:cd|pushd|set-location|sl)\s+(\"[^\"]*\"|'[^']*'|[^\s;&|]+)", cmd, flags=re.IGNORECASE):
        target = m.group(1).strip("\"'")
        if target in ("-", "") or not _inside(_norm(target, cwd)):
            return "changing directory outside the clean room"
    return None


def decide(ev: dict) -> tuple[bool, str]:
    tool = ev.get("tool_name", "")
    ti = ev.get("tool_input") or {}
    cwd = ev.get("cwd") or CLEAN
    blob = json.dumps(ti, ensure_ascii=False)
    if tool.startswith("mcp__"):
        return False, "MCP tools (browser, external services) are disabled in the clean room"
    if tool in BLOCKED_TOOLS:
        return False, f"{tool} is disabled in the clean room (cross-session, scheduling or external-notification tool)"
    if tool in ("Task", "Agent") and str(ti.get("subagent_type") or "general-purpose") not in ALLOWED_SUBAGENTS:
        return False, f"subagent type {ti.get('subagent_type')!r} is not allowed (use general-purpose, Explore or Plan)"
    if tool in ("WebSearch", "WebFetch"):
        if not ALLOW_WEB:
            return False, "web access is disabled for this agent"
        for pat in WEB_BLOCK:
            if re.search(pat, blob, flags=re.IGNORECASE):
                return False, f"web query names a blocked topic ({pat!r}); methods-only research"
        return True, "web ok"
    why = _forbidden_text(blob)
    if why:
        return False, why
    if tool in ("Bash", "PowerShell"):
        why = _check_bash(str(ti.get("command", "")), cwd)
        return (False, why) if why else (True, "command ok")
    for key in ("file_path", "path", "notebook_path"):
        if key in ti and ti[key]:
            p = _norm(str(ti[key]), cwd)
            if not _inside(p):
                return False, f"{key} outside the clean room: {ti[key]}"
            if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit") and (
                    os.sep + ".claude" + os.sep in p + os.sep or p.endswith(os.sep + "claude.md")):
                return False, "the clean room's .claude settings and CLAUDE.md are read-only"
    if tool == "Glob" and re.match(r"^\s*([a-zA-Z]:|/|\\\\|~)", str(ti.get("pattern", ""))):
        p = _norm(str(ti["pattern"]).split("*")[0] or CLEAN, cwd)
        if not _inside(p):
            return False, "glob pattern outside the clean room"
    return True, "ok"


def main() -> int:
    try:
        ev = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001 - a malformed event is denied, never allowed
        print(f"guard: unreadable hook input ({e}); denied", file=sys.stderr)
        return 2
    ok, reason = decide(ev)
    _log("allow" if ok else "deny", ev.get("tool_name", ""), reason, json.dumps(ev.get("tool_input") or {}, ensure_ascii=False))
    if ok:
        return 0
    print(f"BLOCKED by the Phase 3 clean-room guard: {reason}. Work only inside the clean room; see CLAUDE.md.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
