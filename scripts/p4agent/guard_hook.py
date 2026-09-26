"""PreToolUse guard for Phase 4 room agents (goal5 section 5: technological isolation; research/phase4/LEAKAGE_POLICY.md section 2).

Runs as a Claude Code hook OUTSIDE the room (`python -I`). It receives the pending tool call on stdin and blocks it (exit code 2,
reason on stderr) when it could touch anything outside the room, run code on the host, modify the room's protected files, or search
the web for the benchmark's datasets / circuit. Every decision is appended to a JSONL log outside the room.

Phase 4 = the Phase 3 guard version 2 (resolve-and-contain on paths, refused path-building constructs, embedded scripts checked,
~/.claude refused except the agent's own session store; see scripts/p3agent/guard_hook.py and research/phase3/reviews/F_resolution.md)
plus:
1. HOST COMMAND ALLOWLIST. Every simple command of a Bash tool call (after splitting pipelines, lists, subshells, command and process
   substitutions) must start with an allowlisted file / text tool or `sbx`. Interpreters, build tools, package managers, shells,
   git, docker and everything else are refused on the host: all code runs in the Docker sandbox through `sbx` (the room's wrapper,
   read-only for agents). Host tools that can execute code are restricted (find -exec, xargs, sed e, awk system / pipes, rg --pre,
   cp -s / -l, tar / unzip). The PowerShell tool is refused.
2. PROTECTED FILES: the room's allowlisted files (C:\\Dev\\BrainIR_p4audit\\protected_<room>.json, written by the room builder),
   CLAUDE.md, CLAUDE.local.md, .mcp.json, .claude/ and sbx cannot be modified from the host.
3. LINKS: every path-like token (relative ones included) is resolved with realpath and must stay inside the room, so a junction or
   link inside the room cannot be followed out of it; Glob / Grep refuse search roots that contain a link or junction. (Code in the
   sandbox cannot create symbolic links: seccomp profile.)
4. Environment variables that steer path resolution or the sandbox (PATH, PYTHONPATH, LD_PRELOAD, BASH_ENV, DOCKER_*, P4_* except the
   sandbox caps, ...) cannot be assigned in commands.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

CLEAN = os.path.normcase(os.path.realpath(os.environ.get("P4_CLEAN_ROOT", r"C:\Dev\BrainIR_p4clean")))
AUDIT_DIR = os.environ.get("P4_AUDIT_DIR", r"C:\Dev\BrainIR_p4audit")
AGENT = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("P4_AGENT_NAME", "unknown"))
ALLOW_WEB = os.environ.get("P4_ALLOW_WEB", "0") == "1"
HOME = os.path.normcase(os.path.realpath(os.path.expanduser("~")))

OWN_KEY = re.sub(r"[^A-Za-z0-9]", "-", os.environ.get("P4_CLEAN_ROOT", r"C:\Dev\BrainIR_p4clean"))
OWN_STORE_DIR = os.path.normcase(os.path.join(HOME, ".claude", "projects", OWN_KEY))
OWN_STORE = re.compile(r"(?i)\.claude[\\/]+projects[\\/]+" + re.escape(OWN_KEY) + r"(?=[\\/\"'\s]|$)")

_BASE = os.path.basename(CLEAN)
_SUFFIX = re.escape(_BASE[len("brainir"):]) if _BASE.lower().startswith("brainir") and len(_BASE) > len("brainir") else "(?!)"
FORBIDDEN_PATTERNS = [
    rf"dev[\\/]+brainir(?!{_SUFFIX}(?![\w-]))",       # the main repository and every other BrainIR directory
    r"\.claude[\\/]",                                 # ~/.claude (the own store is replaced by a placeholder first)
    r"\.credentials", r"\.modal\.toml", r"\.claude\.json",
    rf"c--dev-brainir(?!{_SUFFIX.replace('_', '-')}(?![\w-]))",
    r"phase\d_report", r"hidden_eval", r"blind_eval", r"dng100", r"[\\/]oracle", r"salt_reveal", r"real_hidden",
    r"state_discovery_v1[\\/]+hidden", r"brainir-p3-(eval|fit|devdata)", r"research[\\/]+phase[23]\b", r"data[\\/]+phase3\b",
    r"\bgoal\d+\.md\b",
    r"\bpythonpath\b", r"\bp[34]_clean_root\b", r"\bsitecustomize\b", r"\busercustomize\b", r"\bpyguard\b",
    r"\bpy(thon)?[0-9.]*(\.exe)?\s+(-[a-zA-Z]+\s+)*-[a-zA-Z]*[ISE]",
    r"disableallhooks", r"\benv\s+-(i|u)\b", r"\bunset\b", r"remove-item\s+env:",
]
_ROOM_NAME_RE = re.compile(r"(?i)brainir_p\d[\w-]*")
_ROOMS_EXPLICIT = ("brainir_p2clean", "brainir_p3audit", "brainir_p3run", "brainir_p3regen", "brainir_p3review", "brainir_p3reviewg",
                   "brainir_p3postreview", "brainir_p3clean", "brainir_p3bench", "brainir_p3lit", "brainir_p3smoke",
                   "brainir_p3guardtest", "brainir_p3audit_test", "brainir_p4clean", "brainir_p4bench", "brainir_p4lit",
                   "brainir_p4review", "brainir_p4audit", "brainir_p4run", "brainir_p4guardtest", "brainir_p4canary")
FORBIDDEN_PATTERNS += [rf"{r}(?![\w-])" for r in _ROOMS_EXPLICIT if r != _BASE.lower()]

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
    (r"\\\\[?.]\\|(^|[\s\"'=(])\\\\[A-Za-z0-9]", "UNC and device paths are not allowed"),
    (r"(^|[\s;&|(\"'])(curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm|start-bitstransfer|ftp|sftp|scp|ssh|telnet|nc|ncat|"
     r"bitsadmin)(\.exe)?(\s|$)|urllib|\brequests\.(get|post)|\bhttpx\b|\bsocket\.|https?://", "network access is not allowed"),
    (r"(>>?|\btee\b|\bcp\b|\bmv\b|\bsed\s+-i|set-content|add-content|out-file|\brm\b|\bdel\b|remove-item|move-item|copy-item|\bchmod\b|"
     r"\btouch\b|\bmkdir\b)[^\n;&|]*(claude\.md|claude\.local\.md|\.mcp\.json|\.claude\b|(?<![\w.-])\.?/?sbx(?![\w.-])|"
     r"cleanroom_manifest\.json)", "the room's CLAUDE.md, .claude, .mcp.json, sbx and manifest are read-only"),
    (r"dirname\s*\(\s*os\.getcwd|getcwd\(\)\s*\)\s*\.\s*parent|\bos\.path\.split\s*\(\s*os\.getcwd", "parent-of-cwd idioms are not allowed"),
    (r"stop-process\s+(-name|-processname)\b|\|\s*stop-process\b|\|\s*%\s*\{\s*stop-process|\btaskkill\b[^\n;&|]*/im\b|"
     r"\b(pkill|killall)\b|\bwmic\b[^\n;&|]*\bdelete\b|get-process[^\n;&]*\|\s*(stop-process|kill)|\bstop-process\s+\*",
     "stop processes only by their explicit id; other work runs on this machine"),
]
WEB_BLOCK = [r"dng100", r"\bbdn2\b", r"pugliese", r"walking\s*cpg", r"walking\s+central\s+pattern", r"malecns", r"male\s*cns",
             r"\bmanc\b", r"neuprint", r"flywire", r"ventral\s+nerve\s+cord", r"drosophila", r"\bfly\b.*\b(leg|walking|motor)",
             r"descending\s+neuron", r"front[-\s]?leg", r"hemibrain", r"connectome"]
BLOCKED_TOOLS = {"ListAgents", "SendMessage", "RemoteTrigger", "PushNotification", "CronCreate", "CronDelete", "CronList", "ScheduleWakeup",
                 "DesignSync", "EnterWorktree", "ExitWorktree", "SendUserFile", "FetchInboxMessage", "ReadNotifications", "Artifact",
                 "ArtifactComments", "ArtifactData", "ArtifactCheck", "SendFeedback", "PowerShell", "Monitor", "Workflow",
                 "TaskStop"}
ALLOWED_SUBAGENTS = {"general-purpose", "Explore", "Plan", "claude"}
SCRIPT_EXT = re.compile(r"(?i)[\w./\\:-]+\.(sh|bash|zsh|ps1|psm1|psd1|bat|cmd)\b")

# host tools an agent may run directly (file inspection / text processing / bookkeeping); everything else goes through sbx
HOST_ALLOWED = {
    "ls", "cat", "head", "tail", "wc", "file", "stat", "du", "df", "tree", "find", "grep", "egrep", "fgrep", "rg", "sort", "uniq", "cut",
    "tr", "sed", "awk", "gawk", "diff", "cmp", "comm", "paste", "join", "column", "nl", "fold", "fmt", "rev", "tac", "echo", "printf",
    "true", "false", "test", "[", "[[", "]]", "]", "sleep", "date", "basename", "mkdir", "touch", "cp", "mv", "rm", "rmdir", "chmod",
    "gzip", "gunzip", "zcat", "md5sum", "sha256sum", "sha1sum", "cksum", "jq", "xargs", "tee", "wait", "kill", "jobs", "fg", "bg",
    "type", "which", "whoami", "uname", "hostname", "pwd", "cd", "pushd", "popd", "read", "seq", "expr", "yes", "split", "numfmt",
    "shuf", "exit", "return", "break", "continue", "local", "declare", "export", "set", "shopt", "ulimit", "umask", "sbx", ":", "nproc",
    "env", "timeout", "nice", "nohup", "command", "time", "stdbuf", "realpath", "dirname", "readlink", "printenv",
}
WRAPPERS = {"env", "timeout", "nice", "nohup", "command", "time", "stdbuf", "xargs"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "{", "}", "time"}
INTERPRETERS = re.compile(r"(?i)^(python[0-9.]*w?|py|pythonw|uv|uvx|pip[0-9.]*|pytest|py\.test|conda|mamba|poetry|pipx|jupyter|ipython|"
                          r"node|nodejs|npm|npx|deno|bun|yarn|pnpm|perl|ruby|gem|php|lua|java|javaw|javac|dotnet|rscript|r|julia|go|"
                          r"cargo|rustc|gcc|g\+\+|cc|clang|make|cmake|ninja|powershell|pwsh|cmd|cscript|wscript|mshta|rundll32|regsvr32|"
                          r"wsl|bash|sh|zsh|dash|ksh|fish|busybox|git|docker|docker-compose|kubectl|modal|claude|code|start|explorer|"
                          r"source|\.|exec|eval|trap|alias|builtin|enable|hash|coproc|ps|tar|zip|unzip|7z|curl|wget|ssh|scp)$")
ENV_FORBIDDEN = re.compile(r"(?i)^(path|pythonpath|pythonhome|pythonstartup|ld_preload|ld_library_path|bash_env|env|shellopts|bashopts|"
                           r"prompt_command|ifs|home|userprofile|temp|tmp|tmpdir|cdpath|globignore|msys\w*|docker_\w*|p[34]_(?!sbx_)\w*|"
                           r"claude\w*|anthropic\w*|modal\w*|git_\w*|path_\w*)$")
ALLOWED_OUTSIDE = [re.compile(p, re.IGNORECASE) for p in (
    r"^[a-z]:[\\/]+program files[\\/]+git([\\/]|$)", r"^/dev/null$", r"^nul$",
)]

PATH_TOKEN = re.compile(r"""(?ix)
    (?<![\w])[a-z]:[\\/][^\s"'`|;&<>()]*
  | (?:^|(?<=[\s"'=]))/[a-z](?:/[^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
  | (?:^|(?<=[\s"'=]))~(?:[\\/][^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
  | (?:^|(?<=[\s"'=]))/(?:tmp|home|users|mnt|etc|root|var|proc|cygdrive|dev|usr|bin|opt|srv|run|sys)(?:/[^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
""")
QUOTED_ABS = re.compile(r"""["']\s*((?:[a-zA-Z]:[\\/]|/[a-zA-Z]/)[^"']*)["']""")


def _protected() -> tuple[set[str], list[str]]:
    """(protected room-relative files, read-only room-relative directories) from the builder's list outside the room."""
    files, dirs = {"claude.md", "claude.local.md", ".mcp.json", "sbx", "cleanroom_manifest.json"}, [".claude"]
    try:
        d = json.loads((Path(AUDIT_DIR) / f"protected_{_BASE}.json").read_text(encoding="utf-8"))
        files |= {f.lower() for f in d.get("files") or []}
        rw = [r.lower().rstrip("/") for r in d.get("rw_nested") or []]
        for r in d.get("read_only_dirs") or []:
            dirs.append(r.lower().rstrip("/"))
        dirs = [x for x in dirs if x]
        return files, [x for x in dirs] + [f"!{r}" for r in rw]
    except (OSError, ValueError):
        return files, dirs


PROTECTED_FILES, PROTECTED_DIRS = _protected()


def _log(decision: str, tool: str, reason: str, detail: str) -> None:
    try:
        Path(AUDIT_DIR).mkdir(parents=True, exist_ok=True)
        with open(Path(AUDIT_DIR) / f"guard_{AGENT}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": AGENT, "decision": decision, "tool": tool,
                                 "reason": reason, "detail": detail[:20000]}) + "\n")
    except OSError:
        pass


def _resolve(p: str, cwd: str) -> str:
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


def _rel(p: str) -> str | None:
    if not _under(p, CLEAN):
        return None
    return os.path.relpath(p, CLEAN).replace("\\", "/").lower()


def _is_protected(p: str) -> bool:
    rel = _rel(p)
    if rel is None:
        return False
    if rel in PROTECTED_FILES or rel == ".claude" or rel.startswith(".claude/"):
        return True
    rw = [d[1:] for d in PROTECTED_DIRS if d.startswith("!")]
    if any(rel == r or rel.startswith(r + "/") for r in rw):
        return False
    return any(rel == d or rel.startswith(d + "/") for d in PROTECTED_DIRS if not d.startswith("!"))


def _normalise_command(cmd: str) -> str:
    s = cmd.replace('""', "").replace("''", "")
    # (no caret removal: cmd.exe is refused, and in bash a caret is literal, e.g. in regular expressions)
    s = s.replace("\\\n", " ").replace("`\n", " ")
    return s


def _forbidden_text(s: str) -> str | None:
    s = OWN_STORE.sub("<own-session-store>", s)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, s, flags=re.IGNORECASE):
            return f"forbidden pattern {pat!r}"
    for m in _ROOM_NAME_RE.finditer(s):
        if m.group(0).lower() != _BASE.lower():
            return f"another room is named ({m.group(0)[:40]})"
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
        if re.search(r"[*?\[]", probe):
            probe = re.split(r"[*?\[]", probe, maxsplit=1)[0]
            probe = probe.rsplit("/", 1)[0] if "/" in probe else probe.rsplit("\\", 1)[0]
        res = _resolve(probe or raw, cwd)
        if _allowed_outside(raw, res):
            continue
        if not _inside(res):
            return f"path outside the room: {raw[:120]}"
    return None


def _check_relative_tokens(tokens: list[str], cwd: str) -> str | None:
    """Every token that names a path (contains a separator, or exists relative to cwd) must resolve inside the room: a link or junction
    in the room cannot be followed out of it."""
    for t in tokens:
        if not t or t.startswith(("-", "__", "/", "\\")) or "=" in t.split("/", 1)[0] or "\n" in t or \
                re.search(r"[$^|]|\\[A-Za-z.()\[\]{}|+?*]", t) or re.fullmatch(r"\\?[{};+]+|\\\W", t):
            continue                         # options, placeholders, absolute paths (checked by _check_paths), patterns / regexes
        probe = re.split(r"[*?\[]", t, maxsplit=1)[0] if re.search(r"[*?\[]", t) else t
        if not probe:
            continue
        if ("/" in probe or "\\" in probe or os.path.lexists(os.path.join(cwd or CLEAN, probe))) and not re.match(r"^[a-z]+://", probe):
            res = _resolve(probe, cwd)
            if not _inside(res) and not _allowed_outside(probe, res):
                return f"path leaves the room (link or junction?): {t[:120]}"
    return None


HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)
PYC = re.compile(r"(\bpy(?:thon[0-9.]*)?(?:\.exe)?\b[^\n;&|]*?\s-c\s+)(\"(?:\\.|[^\"\\])*\"|'[^']*')", re.DOTALL)
SAFE_VALUE = re.compile(r"""^(\$[0-9@*#]|"\$[0-9@*#]"|\$\{[0-9]\}|[\w.,:+=@%-]*|"[\w.,:+=@%/ -]*"|'[\w.,:+=@%/ -]*')$""")


def _split_bodies(s: str) -> tuple[str, list[tuple[str, str]]]:
    """Heredoc bodies and python -c bodies -> placeholders. kind 'box' = consumed by sbx (runs in the sandbox), 'data' = written to a
    file / fed to a host tool, 'sh' = consumed by a host shell (refused anyway by the command allowlist)."""
    bodies: list[tuple[str, str]] = []

    def heredoc(m):
        line_start = s.rfind("\n", 0, m.start()) + 1
        consumer = s[line_start:m.start()]
        if re.search(r"(^|[\s;&|(])(\./)?sbx(\s|$)", consumer):
            kind = "box"
        elif re.search(r"(?i)\b(bash|sh|zsh|powershell|pwsh|cmd)\b", consumer):
            kind = "sh"
        else:
            target = re.search(r">\s*([^\s;&|<>]+)", consumer)
            kind = "sh" if (target and SCRIPT_EXT.fullmatch(os.path.basename(target.group(1).strip("\"'")))) else "data"
        bodies.append((kind, m.group(3)))
        return m.group(0)[: m.group(0).find("\n")] + " __BODY__"
    t = HEREDOC.sub(heredoc, s)

    def pyc(m):
        bodies.append(("box", m.group(2)[1:-1]))
        return m.group(1) + " __BODY__ "
    t = PYC.sub(pyc, t)
    return t, bodies


def _unsafe_variable_paths(s: str) -> str | None:
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


# ------------------------------------------------------------------------------------------------ shell structure
def _extract_substitutions(s: str) -> tuple[str, list[str]]:
    """Replace $(...), `...`, <(...), >(...) (outside single quotes) by __SUBST__; return (text, [inner commands])."""
    out, subs, i, n = [], [], 0, len(s)
    sq = dq = False
    while i < n:
        c = s[i]
        if c == "'" and not dq:
            sq = not sq
            out.append(c)
            i += 1
            continue
        if c == '"' and not sq:
            dq = not dq
            out.append(c)
            i += 1
            continue
        if c == "\\" and not sq and i + 1 < n:
            out.append(s[i:i + 2])
            i += 2
            continue
        if not sq and (s.startswith("$(", i) or ((s.startswith("<(", i) or s.startswith(">(", i)) and not dq)):
            if s.startswith("$((", i):                       # arithmetic expansion: keep as text
                j = s.find("))", i)
                j = n if j < 0 else j + 2
                out.append(s[i:j])
                i = j
                continue
            depth, j, q1, q2 = 1, i + 2, False, False
            while j < n and depth:
                cj = s[j]
                if cj == "'" and not q2:
                    q1 = not q1
                elif cj == '"' and not q1:
                    q2 = not q2
                elif not q1 and not q2:
                    if cj == "(":
                        depth += 1
                    elif cj == ")":
                        depth -= 1
                j += 1
            subs.append(s[i + 2:j - 1])
            out.append("__SUBST__")
            i = j
            continue
        if c == "`" and not sq:
            j = s.find("`", i + 1)
            j = n if j < 0 else j
            subs.append(s[i + 1:j])
            out.append("__SUBST__")
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out), subs


def _segments(s: str) -> list[tuple[str, bool]]:
    """Split a command list into simple commands (quote-aware) at ; & | newline ( ) and at braces that stand alone. Returns
    [(segment, is_case_pattern)]: a segment closed by an unmatched ')' is a case pattern, not a command."""
    segs, cur, i, n, depth = [], [], 0, len(s), 0
    sq = dq = False

    def flush(case_pattern=False):
        seg = "".join(cur).strip()
        if seg:
            segs.append((seg, case_pattern))
        cur.clear()
    while i < n:
        c = s[i]
        if c == "'" and not dq:
            sq = not sq
        elif c == '"' and not sq:
            dq = not dq
        elif c == "\\" and not sq and i + 1 < n:
            cur.append(s[i:i + 2])
            i += 2
            continue
        elif not sq and not dq:
            if c == "$" and i + 1 < n and s[i + 1] == "{":
                j = s.find("}", i)
                j = n - 1 if j < 0 else j
                cur.append(s[i:j + 1])
                i = j + 1
                continue
            if c == "&" and ((i > 0 and s[i - 1] in "<>") or (i + 1 < n and s[i + 1] == ">")):
                cur.append(c)
                i += 1
                continue
            if c in ";|&\n":
                flush()
                i += 1
                continue
            if c == "(":
                depth += 1
                flush()
                i += 1
                continue
            if c == ")":
                if depth > 0:
                    depth -= 1
                    flush()
                else:
                    flush(case_pattern=True)
                i += 1
                continue
            if c in "{}" and (i == 0 or s[i - 1] in " \t\n;") and (i + 1 >= n or s[i + 1] in " \t\n;"):
                flush()
                i += 1
                continue
        cur.append(c)
        i += 1
    flush()
    return segs


REDIR = re.compile(r"^(\d*|&)(>>?|<|<>|>&|<&|&>|&>>)(.*)$")


def _tokens(seg: str) -> list[str]:
    """Words of a simple command with bash-like (POSIX) quoting; an unparsable segment falls back to whitespace splitting (the raw
    text is path-checked separately)."""
    try:
        lex = shlex.shlex(seg, posix=True, punctuation_chars=False)
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:
        return seg.split()


ABS_TOKEN = re.compile(r"(?i)^([a-z]:[\\/]|/[a-z](/|$)|~([\\/]|$)|/(tmp|home|users|mnt|etc|root|var|proc|cygdrive|dev|usr|bin|opt|srv|run|sys)(/|$))")


def _check_abs_token(t: str, cwd: str) -> str | None:
    """An absolute-looking word (spaces allowed: it is one shell word) must resolve inside the room or an allowed location."""
    if not ABS_TOKEN.match(t) or t in ("/dev/null",):
        return None
    probe = t
    if re.search(r"[*?\[]", probe):
        probe = re.split(r"[*?\[]", probe, maxsplit=1)[0]
        probe = probe.rsplit("/", 1)[0] if "/" in probe else probe.rsplit("\\", 1)[0]
    res = _resolve(probe or t, cwd)
    if _allowed_outside(t, res) or _inside(res):
        return None
    return f"path outside the room: {t[:120]}"


def _check_simple(seg: str, cwd: str, host_text: list[str]) -> str | None:
    toks = _tokens(seg)
    words, redirs = [], []
    k = 0
    while k < len(toks):
        t = toks[k]
        m = REDIR.match(t)
        if m and not t.startswith("<<"):
            target = m.group(3)
            if not target and k + 1 < len(toks):
                target = toks[k + 1]
                k += 1
            if target and not target.startswith("&") and target != "__BODY__":
                redirs.append(target)
            k += 1
            continue
        if t.startswith("<<"):
            k += 2 if t in ("<<", "<<-") else 1
            continue
        words.append(t)
        k += 1
    for r in redirs:
        if r in ("/dev/null", "nul"):
            continue
        why = _check_abs_token(r, cwd) or _check_relative_tokens([r], cwd)
        if why:
            return f"redirection: {why}"
        if _is_protected(_resolve(r, cwd)):
            return "redirection into a protected room file"
    # leading assignments and keywords
    while words and (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0] in KEYWORDS):
        if words[0] in KEYWORDS:
            words = words[1:]
            continue
        name = words[0].split("=", 1)[0]
        if ENV_FORBIDDEN.match(name):
            return f"assigning {name} is not allowed"
        words = words[1:]
    if not words:
        return None
    if words[0] in ("for", "select", "case"):
        return None                                   # the rest of a for / case header is data
    why, is_sbx = _check_word(words, cwd)
    if why:
        return why
    if not is_sbx:                                    # sbx arguments are container paths: not host-checked
        host_text.append(seg)
        for t in words[1:]:
            why = _check_abs_token(t, cwd)
            if why:
                return why
    return None


def _cmd_name(w: str) -> str:
    b = w.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return b[:-4] if b.endswith(".exe") else b


SED_E = [re.compile(r"(?:^|[;{}\n])\s*(?:\d+|\$|/(?:\\.|[^/\\])*/)?\s*!?\s*e(?:\s|;|$)"),
         # s/pattern/replacement/flags with an 'e' flag; a backslash is consumed only as part of an escape pair
         re.compile(r"(?:^|[;{}\n])\s*(?:\d+|\$|/(?:\\.|[^/\\])*/)?\s*!?\s*s([^\w\s\\;{}\n])(?:\\.|(?!\1)[^\\])*\1(?:\\.|(?!\1)[^\\])*\1"
                    r"[a-zA-Z0-9]*e")]


def _check_word(words: list[str], cwd: str, depth: int = 0) -> tuple[str | None, bool]:
    """(refusal reason or None, whether the command runs in the sandbox)."""
    w0 = words[0]
    if "__SUBST__" in w0 or w0 == "__BODY__":
        return "a command substitution may not be used as the command name", False
    name = _cmd_name(w0)
    if ("/" in w0 or "\\" in w0) and name == "sbx":
        if _resolve(w0, cwd) != os.path.normcase(os.path.join(CLEAN, "sbx")):
            return "only the room's own sbx wrapper may be run", False
        return None, True
    if "/" in w0 or "\\" in w0:
        return "running files on the host is not allowed; run code in the sandbox: sbx <command>", False
    if name == "sbx":
        return None, True
    if name not in HOST_ALLOWED:
        if INTERPRETERS.match(name):
            return (f"'{name}' may not run on the host: run code in the Docker sandbox (sbx python ..., sbx pytest ..., "
                    f"sbx bash script.sh)"), False
        return f"'{name}' is not an allowed host command (host: file and text tools only; code: sbx <command>)", False
    args = words[1:]
    if name == "export":
        for a in args:
            if not a.startswith("-") and ENV_FORBIDDEN.match(a.split("=", 1)[0]):
                return f"exporting {a.split('=', 1)[0]} is not allowed", False
    if name == "cp" and any(a in ("-s", "-l", "--symbolic-link", "--link") or (re.match(r"^-[a-zA-Z]+$", a) and set(a[1:]) & set("sl"))
                            for a in args):
        return "cp may not create links", False
    if name == "rg" and any(a.startswith("--pre") or a in ("-L", "--follow") for a in args):
        return "rg --pre / --follow are not allowed", False
    if name == "sed":
        scripts, i = [], 0
        while i < len(args):
            a = args[i]
            if a in ("-e", "--expression") and i + 1 < len(args):
                scripts.append(args[i + 1])
                i += 2
                continue
            if a.startswith("--expression="):
                scripts.append(a.split("=", 1)[1])
            elif not a.startswith("-") and not scripts:
                scripts.append(a)
            i += 1
        if any(rx.search(sc) for sc in scripts for rx in SED_E):
            return "sed's e command / flag executes commands and is not allowed", False
    if name in ("awk", "gawk"):
        prog = " ".join(args)
        if re.search(r"\bsystem\s*\(|\|\s*getline|\|&|print[f]?[^;{}]*\|\s*[\"'$]", prog):
            return "awk may not run commands (system, pipes)", False
    if name == "find":
        for i, a in enumerate(args):
            if a in ("-exec", "-execdir", "-ok", "-okdir"):
                if i + 1 >= len(args):
                    return "find -exec without a command", False
                why, _ = _check_word(args[i + 1:], cwd, depth + 1)
                if why:
                    return f"find -exec: {why}", False
            if a in ("-L", "-follow"):
                return "find may not follow links", False
    if name in WRAPPERS and depth < 4:
        rest = list(args)
        if name == "xargs":
            while rest and rest[0].startswith("-"):
                opt = rest.pop(0)
                if opt in ("-n", "-I", "-P", "-L", "-d", "-s", "-E", "-a") and rest:
                    rest.pop(0)
        elif name == "timeout":
            while rest and rest[0].startswith("-"):
                opt = rest.pop(0)
                if opt in ("-s", "-k", "--signal", "--kill-after") and rest:
                    rest.pop(0)
            if rest:
                rest.pop(0)                           # the duration
        elif name == "nice":
            while rest and rest[0].startswith("-"):
                opt = rest.pop(0)
                if opt == "-n" and rest:
                    rest.pop(0)
        elif name == "stdbuf":
            while rest and rest[0].startswith("-"):
                rest.pop(0)
        elif name == "command":
            if rest and rest[0] in ("-v", "-V"):
                return None, False
            while rest and rest[0].startswith("-"):
                rest.pop(0)
        elif name == "env":
            while rest and (rest[0].startswith("-") or re.match(r"^[A-Za-z_]\w*=", rest[0])):
                a = rest.pop(0)
                if "=" in a and ENV_FORBIDDEN.match(a.split("=", 1)[0]):
                    return f"assigning {a.split('=', 1)[0]} is not allowed", False
        if rest:
            return _check_word(rest, cwd, depth + 1)
        return None, False
    why = _check_relative_tokens(args, cwd)
    if why:
        return why, False
    return None, False


def _check_shell(cmd: str, cwd: str, depth: int = 0) -> str | None:
    s0 = _normalise_command(cmd)
    why = _forbidden_text(s0)
    if why:
        return why
    s, bodies = _split_bodies(s0)
    for kind, body in bodies:
        if kind == "sh" and depth < 3:
            why = _check_shell(body, cwd, depth + 1)
            if why:
                return f"embedded script: {why}"
    s_nosub, subs = _extract_substitutions(s)
    for sub in subs:
        if depth < 4:
            why = _check_shell(sub, cwd, depth + 1)
            if why:
                return f"command substitution: {why}"
    host_text: list[str] = []
    for seg, case_pattern in _segments(s_nosub):
        if case_pattern:
            continue
        why = _check_simple(seg, cwd, host_text)
        if why:
            return why
    # the Phase 3 checks on the HOST part of the command (sbx arguments are container paths and are not checked here)
    ht = "\n".join(host_text)
    why = _unsafe_variable_paths(ht)
    if why:
        return why
    for pat, msg in SHELL_CONSTRUCTS:
        if re.search(pat, ht if msg.startswith(("parent-directory", "'/./'", "8.3")) else s, flags=re.IGNORECASE | re.MULTILINE):
            return msg
    why = _check_paths(ht, cwd)
    if why:
        return why
    for m in re.finditer(r"(?:^|[;&|(]\s*|\s)(?:cd|chdir|pushd|set-location|sl)\b\s*(\"[^\"]*\"|'[^']*'|[^\s;&|)]*)", s_nosub,
                         flags=re.IGNORECASE | re.MULTILINE):
        target = m.group(1).strip("\"'")
        if target in ("", "-", "~") or not _inside(_resolve(target, cwd), allow_own_store=False):
            return "changing directory outside the room (or to home / previous directory)"
    return None


def _links_under(root: str, limit: int = 60000) -> str | None:
    """A link or junction below root (Glob / Grep would traverse it)."""
    n = 0
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    n += 1
                    if n > limit:
                        return None
                    try:
                        if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                            return e.path
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return None


def decide(ev: dict) -> tuple[bool, str]:
    tool = ev.get("tool_name", "")
    ti = ev.get("tool_input") or {}
    cwd = ev.get("cwd") or CLEAN
    blob = json.dumps(ti, ensure_ascii=False)
    if tool.startswith("mcp__"):
        return False, "MCP tools (browser, external services) are disabled in the room"
    if tool in BLOCKED_TOOLS:
        return False, f"{tool} is disabled in the room"
    if tool in ("Task", "Agent") and str(ti.get("subagent_type") or "general-purpose") not in ALLOWED_SUBAGENTS:
        return False, f"subagent type {ti.get('subagent_type')!r} is not allowed (use general-purpose, Explore or Plan)"
    if tool in ("WebSearch", "WebFetch"):
        if not ALLOW_WEB:
            return False, "web access is disabled for this agent"
        for pat in WEB_BLOCK:
            if re.search(pat, blob, flags=re.IGNORECASE):
                return False, f"web query names a blocked topic ({pat!r}); methods-only research"
        return True, "web ok"
    if tool == "Bash":
        if not _inside(_resolve(cwd, CLEAN), allow_own_store=False):
            return False, "the shell's working directory is outside the room"
        why = _check_shell(str(ti.get("command", "")), cwd)
        return (False, why) if why else (True, "command ok")
    why = _forbidden_text(blob if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit") else
                          json.dumps({k: v for k, v in ti.items() if k in ("file_path", "path", "notebook_path")}))
    if why:
        return False, why
    for key in ("file_path", "path", "notebook_path"):
        if key in ti and ti[key]:
            raw = str(ti[key])
            for pat, msg in SHELL_CONSTRUCTS[:3]:
                if re.search(pat, raw):
                    return False, f"{key}: {msg}"
            p = _resolve(raw, cwd)
            writing = tool in ("Write", "Edit", "MultiEdit", "NotebookEdit")
            if not _inside(p, allow_own_store=not writing):
                return False, f"{key} outside the room: {raw}"
            if writing and _is_protected(p):
                return False, "this room file is read-only (allowlisted / generated by the orchestrator)"
            if writing and (os.sep + ".claude" + os.sep in p + os.sep or os.path.basename(p) in ("claude.md", "claude.local.md", ".mcp.json")):
                return False, "Claude control files (CLAUDE.md, CLAUDE.local.md, .mcp.json, .claude/) may not be written"
            if tool in ("Glob", "Grep") and os.path.isdir(p):
                lk = _links_under(p)
                if lk:
                    return False, "the search root contains a link or junction; report it to the orchestrator"
    if tool in ("Glob", "Grep"):
        pat = str(ti.get("pattern", "")) if tool == "Glob" else ""
        if pat and (re.search(r"(?<![.\w])\.\.(?![.\w])", pat) or re.match(r"^\s*([a-zA-Z]:|/|\\\\|~)", pat)):
            p = _resolve(re.split(r"[*?\[]", pat, maxsplit=1)[0] or CLEAN, cwd)
            if not _inside(p, allow_own_store=False) or ".." in pat:
                return False, "glob pattern outside the room"
        if not ti.get("path"):
            lk = _links_under(_resolve(cwd, CLEAN))
            if lk:
                return False, "the search root contains a link or junction; report it to the orchestrator"
    return True, "ok"


def main() -> int:
    try:
        ev = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(f"guard: unreadable hook input ({e}); denied", file=sys.stderr)
        return 2
    try:
        ok, reason = decide(ev)
    except Exception as e:  # noqa: BLE001
        ok, reason = False, f"guard error ({type(e).__name__}); denied"
    _log("allow" if ok else "deny", ev.get("tool_name", ""), reason, json.dumps(ev.get("tool_input") or {}, ensure_ascii=False))
    if ok:
        return 0
    print(f"BLOCKED by the Phase 4 room guard: {reason}. Work only inside the room; run code with sbx; see CLAUDE.md.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
