"""PreToolUse guard for Phase 3 clean-room agents (goal4 section 3: technological isolation, read-deny hook, path audit).

Runs as a Claude Code hook OUTSIDE the clean room. It receives the pending tool call on stdin (JSON: tool_name, tool_input, cwd,
session_id, ...) and blocks it (exit code 2, reason on stderr) when it could touch anything outside the clean room, or when a web
query names the benchmark's datasets or circuit. Every decision is appended to a JSONL audit log outside the clean room.

Version 2 (after review F, findings F-B1 / F-M1 / F-M2):
- RESOLVE-AND-CONTAIN: every path-like token of a tool input is resolved with realpath and must lie inside the room (or a short
  explicit allowlist: the uv-managed interpreters, the uv executable, Git's install directory, the null device). Quoted strings
  and inline code are scanned too.
- Shell commands may not BUILD paths the guard cannot see. The following are refused:
  - parent references (..);
  - '/./' components and 8.3 short names;
  - variables or command substitutions used as path prefixes;
  - $PWD / $HOME / environment-variable paths;
  - PowerShell path cmdlets (Split-Path, Join-Path, Get-Location, ...);
  - bare drive roots;
  - UNC / device paths;
  - link creation;
  - encodings used for obfuscation (base64, hex / octal escapes, Invoke-Expression, eval);
  - interpreters other than Python;
  - anything that would disable the Python audit hook.
  Empty-quote splicing (PY""THON) and caret escapes are removed before matching.
- Script files a command runs (.sh, .ps1, .bat, ...) are checked like the command itself, and so is the content written into such
  files.
- The user's whole ~/.claude directory is refused except the agent's OWN session store (read-only).

This is defence in depth on the command text. The Python layer (scripts/p3agent/pyguard/sitecustomize.py) checks resolved paths at
run time, and every transcript is audited afterwards (scripts/p3agent/audit_transcripts.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

CLEAN = os.path.normcase(os.path.realpath(os.environ.get("P3_CLEAN_ROOT", r"C:\Dev\BrainIR_p3clean")))
AUDIT_DIR = os.environ.get("P3_AUDIT_DIR", r"C:\Dev\BrainIR_p3audit")
AGENT = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("P3_AGENT_NAME", "unknown"))
ALLOW_WEB = os.environ.get("P3_ALLOW_WEB", "0") == "1"
HOME = os.path.normcase(os.path.realpath(os.path.expanduser("~")))

# the agent's OWN session store (~/.claude/projects/<key of the clean room>/): large tool results are saved there by the CLI and the
# agent must be able to read them back; every other session's store and the rest of ~/.claude stay forbidden
OWN_KEY = re.sub(r"[^A-Za-z0-9]", "-", os.environ.get("P3_CLEAN_ROOT", r"C:\Dev\BrainIR_p3clean"))
OWN_STORE_DIR = os.path.normcase(os.path.join(HOME, ".claude", "projects", OWN_KEY))
OWN_STORE = re.compile(r"(?i)\.claude[\\/]+projects[\\/]+" + re.escape(OWN_KEY) + r"(?=[\\/\"'\s]|$)")

# the clean room's own name after "BrainIR" (e.g. "_p3clean"): the only "Dev/BrainIR..." location a tool input may name
_BASE = os.path.basename(CLEAN)
_SUFFIX = re.escape(_BASE[len("brainir"):]) if _BASE.lower().startswith("brainir") and len(_BASE) > len("brainir") else "(?!)"
FORBIDDEN_PATTERNS = [
    rf"dev[\\/]+brainir(?!{_SUFFIX})",               # the main repository and every other BrainIR directory
    r"\.claude[\\/]",                                 # ~/.claude (the own store is replaced by a placeholder first)
    r"\.credentials", r"\.modal\.toml", r"\.claude\.json",
    rf"c--dev-brainir(?!{_SUFFIX.replace('_', '-')})",
    r"phase2_report", r"hidden_eval", r"blind_eval", r"dng100", r"[\\/]oracle",
    r"\bpythonpath\b", r"\bp3_clean_root\b", r"\bsitecustomize\b", r"\busercustomize\b", r"\bpyguard\b",
    r"\bpy(thon)?[0-9.]*(\.exe)?\s+(-[a-zA-Z]+\s+)*-[a-zA-Z]*[ISE]", # disabling site / environment for the Python guard
    r"disableallhooks", r"\benv\s+-(i|u)\b", r"\bunset\b", r"remove-item\s+env:",
]
_ROOMS = ("brainir_p2clean", "brainir_p3audit", "brainir_p3run", "brainir_p3regen", "brainir_p3review", "brainir_p3reviewg",
          "brainir_p3clean", "brainir_p3bench", "brainir_p3lit", "brainir_p3smoke", "brainir_p3guardtest", "brainir_p3audit_test")
FORBIDDEN_PATTERNS += [rf"{r}(?![\w-])" for r in _ROOMS if r != _BASE.lower()]
# constructs that build paths the guard cannot see, obfuscate, or escape the room (shell commands and script contents)
SHELL_CONSTRUCTS = [
    (r"(?<![.\w])\.\.(?![.\w])", "parent-directory references (..) are not allowed; use paths inside the room"),
    (r"[\\/]\.[\\/]", "'/./' path components are not allowed"),
    (r"\w~\d", "8.3 short path names are not allowed"),
    (r"\$\{?(pwd|oldpwd|home|userprofile|appdata|localappdata|temp|tmp|psscriptroot|pshome|profile|tmpdir)\b\}?",
     "environment / location variables are not allowed in commands"),
    (r"\$env:(userprofile|appdata|localappdata|temp|tmp|homepath|homedrive|systemdrive|public|programdata|onedrive|home|path)\b",
     "environment path variables are not allowed"),
    (r"%(userprofile|appdata|localappdata|temp|tmp|homepath|homedrive|systemdrive|systemroot|windir|public|programdata|onedrive|cd)%",
     "environment path variables are not allowed"),
    (r"\$\([^)]*\)[\\/]", "command substitutions used as path prefixes are not allowed"),
    (r"(\$\(|`)\s*(pwd|cd|dirname|realpath|readlink|cygpath|cmd)\b", "location-computing command substitutions are not allowed"),
    (r"\b(split-path|join-path|resolve-path|get-location|push-location|get-psdrive|new-psdrive|convert-path)\b",
     "PowerShell path cmdlets are not allowed"),
    (r"\$pwd\b|\.parent\b|\bpardir\b|\.parents\b|\[(system\.)?environment\]::|\[(system\.)?io\.", "parent / environment path APIs are not allowed"),
    (r"\bmklink\b|-itemtype\s+['\"]?(symboliclink|junction|hardlink)|(^|[\s;&|(])ln\s|\bfsutil\b|\bsubst\b|\bnet\s+use\b",
     "creating links or drive mappings is not allowed"),
    (r"\bbase64\b|\bxxd\b|\bcertutil\b|frombase64string|\s-enc(odedcommand)?\b|\biex\b|invoke-expression|(^|[\s;&|(])eval\s|"
     r"\\x[0-9a-fA-F]{2}|\\[0-7]{3}|\bchr\(|\[char\]", "encoded or escaped command text is not allowed"),
    (r"(^|[\s;&|(\"'])(node|nodejs|deno|bun|perl|ruby|php|lua|java|javaw|dotnet|cscript|wscript|mshta|rundll32|regsvr32|osascript|"
     r"bash\.exe|wsl)(\.exe)?(\s|$)", "only Python (uv run python) and standard shell tools may be run"),
    (r"\\\\[?.]\\|(^|[\s\"'=(])\\\\[A-Za-z0-9]", "UNC and device paths are not allowed"),
    (r"(^|[\s;&|(\"'])(curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm|start-bitstransfer|ftp|sftp|scp|ssh|telnet|nc|ncat|"
     r"bitsadmin)(\.exe)?(\s|$)|urllib|\brequests\.(get|post)|\bhttpx\b|\bsocket\.|https?://", "network access is not allowed"),
    (r"\b(uv\s+(add|remove|pip)|pip3?\s+(install|download|uninstall)|conda\s+install)\b", "the environment is fixed; do not install packages"),
    (r"(>>?|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|set-content|add-content|out-file|\brm\b|\bdel\b|remove-item|move-item|copy-item)[^\n;&|]*"
     r"(claude\.md|\.claude\b)|(claude\.md|\.claude\b)[^\n;&|]*(>>?)", "the clean room's CLAUDE.md and .claude settings are read-only"),
    (r"dirname\s*\(\s*os\.getcwd|getcwd\(\)\s*\)\s*\.\s*parent|\bos\.path\.split\s*\(\s*os\.getcwd", "parent-of-cwd idioms are not allowed"),
    # processes are stopped only by explicit id (never by image name / wildcard / pipeline: other agents and the simulation
    # service run on this machine)
    (r"stop-process\s+(-name|-processname)\b|\|\s*stop-process\b|\|\s*%\s*\{\s*stop-process|\btaskkill\b[^\n;&|]*/im\b|"
     r"\b(pkill|killall)\b|\bwmic\b[^\n;&|]*\bdelete\b|get-process[^\n;&]*\|\s*(stop-process|kill)|\bstop-process\s+\*",
     "stop processes only by their explicit id (Stop-Process -Id <pid>); other work runs on this machine"),
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
SCRIPT_EXT = re.compile(r"(?i)[\w./\\:-]+\.(sh|bash|zsh|ps1|psm1|psd1|bat|cmd)\b")

# absolute path tokens (anywhere in the text, quoted or not); a bare drive or drive root is a path too
PATH_TOKEN = re.compile(r"""(?ix)
    (?<![\w])[a-z]:[\\/][^\s"'`|;&<>()]*                                        # C:\  C:\...  C:/...
  | (?:^|(?<=[\s"'=]))/[a-z](?:/[^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])            # /c  /c/...  (Git Bash drives, as arguments)
  | (?:^|(?<=[\s"'=]))~(?:[\\/][^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])           # ~  ~/...
  | (?:^|(?<=[\s"'=]))/(?:tmp|home|users|mnt|etc|root|var|proc|cygdrive)(?:/[^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
""")
QUOTED_ABS = re.compile(r"""["']\s*((?:[a-zA-Z]:[\\/]|/[a-zA-Z]/)[^"']*)["']""")
ALLOWED_OUTSIDE = [re.compile(p, re.IGNORECASE) for p in (
    r"^[a-z]:[\\/]+users[\\/]+[^\\/]+[\\/]+appdata[\\/]+roaming[\\/]+uv[\\/]+python([\\/]|$)",     # uv-managed interpreters
    r"^[a-z]:[\\/]+users[\\/]+[^\\/]+[\\/]+appdata[\\/]+local[\\/]+microsoft[\\/]+winget[\\/]+packages[\\/]+astral-sh\.uv",
    r"^[a-z]:[\\/]+program files[\\/]+git([\\/]|$)", r"^/dev/null$", r"^nul$",
)]


def _log(decision: str, tool: str, reason: str, detail: str) -> None:
    try:
        Path(AUDIT_DIR).mkdir(parents=True, exist_ok=True)
        with open(Path(AUDIT_DIR) / f"guard_{AGENT}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": AGENT, "decision": decision, "tool": tool,
                                 "reason": reason, "detail": detail[:20000]}) + "\n")
    except OSError:
        pass


def _resolve(p: str, cwd: str) -> str:
    """realpath of a path token (Git Bash drive paths and ~ translated; relative paths against cwd); resolves 8.3 names, links and
    '.' / '..' components of existing paths."""
    p = p.strip().strip("\"'")
    m = re.match(r"^/([a-zA-Z])(/.*)?$", p)
    if m:
        p = f"{m.group(1)}:/{(m.group(2) or '/').lstrip('/')}"
    if re.match(r"^[a-zA-Z]:$", p):
        p = p + "\\"
    if p.startswith("~"):
        p = os.path.expanduser(p)
    if not os.path.isabs(p):
        p = os.path.join(cwd or CLEAN, p)
    try:
        return os.path.normcase(os.path.realpath(p))
    except (OSError, ValueError):
        return os.path.normcase(os.path.abspath(p))


def _under(p: str, root: str) -> bool:
    return p == root or p.startswith(root.rstrip("\\/") + os.sep)


def _inside(p: str, allow_own_store: bool = True) -> bool:
    return _under(p, CLEAN) or (allow_own_store and _under(p, OWN_STORE_DIR))


def _allowed_outside(raw: str, resolved: str) -> bool:
    return any(a.match(raw.strip().strip("\"'")) or a.match(resolved) for a in ALLOWED_OUTSIDE)


def _normalise_command(cmd: str) -> str:
    """Remove empty-quote splicing (PY""THON), caret escapes (cmd) and line continuations before matching."""
    s = cmd.replace('""', "").replace("''", "")
    s = re.sub(r"\^(?=\S)", "", s)
    s = s.replace("\\\n", " ").replace("`\n", " ")
    return s


def _forbidden_text(s: str) -> str | None:
    s = OWN_STORE.sub("<own-session-store>", s)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, s, flags=re.IGNORECASE):
            return f"forbidden pattern {pat!r}"
    return None


def _check_paths(text: str, cwd: str) -> str | None:
    cands = [m.group(1) for m in QUOTED_ABS.finditer(text)]
    rest = QUOTED_ABS.sub(" ", text)
    cands += PATH_TOKEN.findall(rest)
    for raw in cands:
        raw = raw.strip().rstrip(",")
        if raw in ("/dev/null",) or raw.lower() == "nul":
            continue
        probe = raw
        if re.search(r"[*?\[]", probe):             # a glob: its non-glob prefix must be inside the room
            probe = re.split(r"[*?\[]", probe, maxsplit=1)[0]
            probe = probe.rsplit("/", 1)[0] if "/" in probe else probe.rsplit("\\", 1)[0]
        res = _resolve(probe or raw, cwd)
        if _allowed_outside(raw, res):
            continue
        if not _inside(res):
            return f"path outside the clean room: {raw[:120]}"
    return None


HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)
HERESTR = re.compile(r"@(['\"])\n(.*?)\n\1@", re.DOTALL)
PYC = re.compile(r"(\bpy(?:thon[0-9.]*)?(?:\.exe)?\b[^\n;&|]*?\s-c\s+)(\"(?:\\.|[^\"\\])*\"|'[^']*')", re.DOTALL)
PY_CONSUMER = re.compile(r"(?i)\b(uv\s+run|python[0-9.]*|py|pytest)\b")
SAFE_VALUE = re.compile(r"""^(\$[0-9@*#]|"\$[0-9@*#]"|\$\{[0-9]\}|[\w.,:+=@%-]*|"[\w.,:+=@%/ -]*"|'[\w.,:+=@%/ -]*')$""")


def _split_bodies(s: str) -> tuple[str, list[tuple[str, str]]]:
    """(shell text with bodies replaced by placeholders, [(kind, body)]): kind 'py' for code run by Python (guarded at run time by
    pyguard) or written to a non-script file; 'sh' for code a shell runs or a script file receives."""
    bodies: list[tuple[str, str]] = []

    def heredoc(m):
        line_start = s.rfind("\n", 0, m.start()) + 1
        consumer = s[line_start:m.start()]
        target = re.search(r">\s*([^\s;&|<>]+)", consumer)
        to_script = bool(target and SCRIPT_EXT.fullmatch(os.path.basename(target.group(1).strip("\"'"))))
        shell_consumer = re.search(r"(?i)\b(bash|sh|zsh|powershell|pwsh|cmd)\b", consumer) and not PY_CONSUMER.search(consumer)
        kind = "sh" if (to_script or shell_consumer) else "py"
        bodies.append((kind, m.group(3)))
        return m.group(0)[: m.group(0).find("\n")] + " __BODY__"
    t = HEREDOC.sub(heredoc, s)

    def herestr(m):
        bodies.append(("sh", m.group(2)))
        return " __BODY__ "
    t = HERESTR.sub(herestr, t)

    def pyc(m):
        bodies.append(("py", m.group(2)[1:-1]))
        return m.group(1) + " __BODY__ "
    t = PYC.sub(pyc, t)
    return t, bodies


def _unsafe_variable_paths(s: str) -> str | None:
    """Variables used as path prefixes ($x/..., ${x}\\...) must be assigned in the same text from a safe value (a positional
    parameter or a literal without separators, '..' or '~') or be a loop variable over such literals."""
    safe = set()
    for name, val in re.findall(r"(?m)(?:^|[;&|\s])(?:local\s+|export\s+)?([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]*)", s):
        if SAFE_VALUE.match(val) and ".." not in val and "~" not in val and not re.search(r"[\\/:]", val.strip("\"'")):
            safe.add(name)
    for name, words in re.findall(r"\bfor\s+([A-Za-z_]\w*)\s+in\s+([^;\n]*)", s):
        if all(SAFE_VALUE.match(w) and not re.search(r"[\\/:~]", w) for w in words.split()) or words.strip() in ('"$@"', "$@"):
            safe.add(name)
    for name in re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?[\\/]", s):
        if name not in safe:
            return f"variable ${name} used as a path prefix (assign it from a literal or a script argument in the same command)"
    if re.search(r"\$\{?\w+\}?\$\{?\w+", s):
        return "adjacent variable concatenation is not allowed"
    return None


def _check_shell(cmd: str, cwd: str, depth: int = 0) -> str | None:
    s0 = _normalise_command(cmd)
    why = _forbidden_text(s0)                         # substring classes apply to everything, bodies included
    if why:
        return why
    s, bodies = _split_bodies(s0)
    for kind, body in bodies:
        if kind == "sh" and depth < 3:
            why = _check_shell(body, cwd, depth + 1)
            if why:
                return f"embedded script: {why}"
    why = _unsafe_variable_paths(s)
    if why:
        return why
    for pat, msg in SHELL_CONSTRUCTS:
        if re.search(pat, s, flags=re.IGNORECASE | re.MULTILINE):
            return msg
    why = _check_paths(s, cwd)
    if why:
        return why
    for m in re.finditer(r"(?:^|[;&|(]\s*|\s)(?:cd|chdir|pushd|set-location|sl)\b\s*(\"[^\"]*\"|'[^']*'|[^\s;&|)]*)", s,
                         flags=re.IGNORECASE | re.MULTILINE):
        target = m.group(1).strip("\"'")
        if target in ("", "-", "~") or not _inside(_resolve(target, cwd), allow_own_store=False):
            return "changing directory outside the clean room (or to home / previous directory)"
    if depth < 2:                                    # scripts the command runs are checked like the command itself
        for m in SCRIPT_EXT.finditer(s):
            p = _resolve(m.group(0), cwd)
            if _inside(p, allow_own_store=False) and os.path.isfile(p):
                try:
                    body = Path(p).read_text(encoding="utf-8", errors="ignore")[:400_000]
                except OSError:
                    continue
                why = _check_shell(body, cwd, depth + 1)
                if why:
                    return f"script {m.group(0)}: {why}"
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
    if tool in ("Bash", "PowerShell"):
        why = _check_shell(str(ti.get("command", "")), cwd)
        return (False, why) if why else (True, "command ok")
    why = _forbidden_text(blob if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit") else
                          json.dumps({k: v for k, v in ti.items() if k in ("file_path", "path", "notebook_path")}))
    if why:
        return False, why
    for key in ("file_path", "path", "notebook_path"):
        if key in ti and ti[key]:
            raw = str(ti[key])
            for pat, msg in SHELL_CONSTRUCTS[:3]:       # '..', '/./', 8.3 names in a tool path
                if re.search(pat, raw):
                    return False, f"{key}: {msg}"
            p = _resolve(raw, cwd)
            writing = tool in ("Write", "Edit", "MultiEdit", "NotebookEdit")
            if not _inside(p, allow_own_store=not writing):
                return False, f"{key} outside the clean room: {raw}"
            if writing and (os.sep + ".claude" + os.sep in p + os.sep or p.endswith(os.sep + "claude.md")):
                return False, "the clean room's .claude settings and CLAUDE.md are read-only"
            if writing and SCRIPT_EXT.fullmatch(os.path.basename(p)):
                body = str(ti.get("content") or ti.get("new_string") or "")
                why = _check_shell(body, cwd, depth=1)
                if why:
                    return False, f"script content: {why}"
    if tool in ("Glob", "Grep"):
        pat = str(ti.get("pattern", "")) if tool == "Glob" else ""
        if pat and (re.search(r"(?<![.\w])\.\.(?![.\w])", pat) or re.match(r"^\s*([a-zA-Z]:|/|\\\\|~)", pat)):
            p = _resolve(re.split(r"[*?\[]", pat, maxsplit=1)[0] or CLEAN, cwd)
            if not _inside(p, allow_own_store=False) or ".." in pat:
                return False, "glob pattern outside the clean room"
    return True, "ok"


def main() -> int:
    try:
        ev = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001 - a malformed event is denied, never allowed
        print(f"guard: unreadable hook input ({e}); denied", file=sys.stderr)
        return 2
    try:
        ok, reason = decide(ev)
    except Exception as e:  # noqa: BLE001 - any failure of the guard denies
        ok, reason = False, f"guard error ({type(e).__name__}); denied"
    _log("allow" if ok else "deny", ev.get("tool_name", ""), reason, json.dumps(ev.get("tool_input") or {}, ensure_ascii=False))
    if ok:
        return 0
    print(f"BLOCKED by the Phase 3 clean-room guard: {reason}. Work only inside the clean room; see CLAUDE.md.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
