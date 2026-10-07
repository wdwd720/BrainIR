"""PreToolUse guard for Phase 4 room agents (goal5 section 5: technological isolation; research/phase4/LEAKAGE_POLICY.md section 2).

Runs as a Claude Code hook OUTSIDE the room (`python -I`). It receives the pending tool call on stdin and blocks it (exit code 2) when
it could touch anything outside the room, run code on the host, write outside the agent's work areas, or search the web for the
benchmark's topic. The agent sees a GENERIC reason with an opaque code (class and event id); the detailed reason is appended, with
every decision, to a JSONL log OUTSIDE the room (C:\\Dev\\BrainIR_p4audit\\guard_<agent>.jsonl) (early review F, F-M2).

Version 3 (early review F: F-B4, F-M1, F-M2, minor 3 and 4):
1. NAMES. Every forbidden word, room name and web-block pattern is loaded at run time from the orchestrator's names config
   (scripts/p4config/names.py; never copied into a room). This file carries none. Without the config every call is refused.
2. HOST COMMAND ALLOWLIST. Every simple command of a Bash tool call (after splitting pipelines, lists, subshells, command and process
   substitutions, and the substitutions inside unquoted here-documents and double-quoted `-c` bodies) must be an allowlisted file /
   text tool or `sbx`. Interpreters, shells, build tools, package managers, git, docker, xargs, split and everything else are refused
   on the host; the PowerShell tool is refused.
3. THE SANDBOX. Only the bare command `sbx`, found through PATH as the wrapper copy OUTSIDE the room, whose sha256 must equal the
   outside manifest's record and which must carry its NTFS deny ACE, checked on every call. Every path spelling (./sbx, <room>/sbx,
   ...) is refused (F-B4).
4. WRITES. The Write / Edit tools, redirections and every write-capable host command (cp, mv, rm, rmdir, mkdir, touch, chmod, tee,
   sed -i, sort -o / -T, uniq OUTPUT, shuf -o, tree -o, gzip / gunzip) may target only the agent's work areas (from
   protected_<room>.json, written by the room builder: the declared work areas, or in a free room every top-level entry that is not
   the orchestrator's; in .tmp/ and simq/ only the agent's own subdirectory), never a Claude control file or an interpreter hook.
   Write-capable or code-running options are refused: sed w/W/r/R/e and the s///w and s///e flags, awk output redirection, pipes,
   system(), getline <, ARGV and extensions, find -exec/-execdir/-ok/-okdir/-delete/-fprint*/-fls, sort --compress-program,
   --files0-from, checksum --check, file -f, rg --pre / --hostname-bin / -z, dd, install, ln, split, xargs (F-B4). The OS backstop
   is the NTFS deny ACE on every protected path (scripts/p4agent/ntfs_protect.py).
5. DATA-DRIVEN PATHS AND SCRIPTS. File arguments, sed scripts, awk programs and jq filters must be literal after substituting the
   variables assigned from literals in the same command (brace and glob expansion applied to files): command substitutions, unknown
   variables and read-loop variables cannot name files or become scripts; globs that could match `.` or `..` are refused; runtime
   data cannot reach an arithmetic context (array subscripts evaluate command substitutions).
6. PATHS. Every path (after expansion) is resolved with realpath and must stay inside the room and outside other agents' private areas
   (.tmp/<other>, simq/<other>) (minor 4); links / junctions cannot be followed out; Glob / Grep refuse search roots with links; a
   file below a directory that holds a planted Claude control file cannot be read or edited (its instructions would be loaded).
7. ENVIRONMENT. Variables that steer path resolution, command lookup or the sandbox cannot be assigned (also through export,
   declare / local, read, printf -v; name references and integer attributes are refused).
Residual (LEAKAGE_POLICY.md section 4): allow / deny remains a membership oracle for candidate names; host Grep / Glob over the room
root can list other agents' .tmp content (the sandbox cannot).
"""

from __future__ import annotations

import fnmatch
import glob as _glob
import hashlib
import importlib.util
import itertools
import json
import os
import re
import secrets
import shlex
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEAN = os.path.normcase(os.path.realpath(os.environ.get("P4_CLEAN_ROOT", r"C:\Dev\BrainIR_p4clean")))
AUDIT_DIR = os.environ.get("P4_AUDIT_DIR", r"C:\Dev\BrainIR_p4audit")
AGENT = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("P4_AGENT_NAME", "unknown"))
#: the agent's private subdirectory of every per-agent area (.tmp/<area>, simq/<area>): the launcher's --scratch (default: the name)
AGENT_L = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("P4_AGENT_SCRATCH") or AGENT).lower()
ALLOW_WEB = os.environ.get("P4_ALLOW_WEB", "0") == "1"
HOME = os.path.normcase(os.path.realpath(os.path.expanduser("~")))

OWN_KEY = re.sub(r"[^A-Za-z0-9]", "-", os.environ.get("P4_CLEAN_ROOT", r"C:\Dev\BrainIR_p4clean"))
OWN_STORE_DIR = os.path.normcase(os.path.join(HOME, ".claude", "projects", OWN_KEY))
OWN_STORE = re.compile(r"(?i)\.claude[\\/]+projects[\\/]+" + re.escape(OWN_KEY) + r"(?=[\\/\"'\s]|$)")
_BASE = os.path.basename(CLEAN)
SENT = "\x00"                 # a `$` that the shell does NOT expand (single-quoted or escaped)


# ------------------------------------------------------------------------------------------------ configuration
def _load_names():
    """The orchestrator's names config (scripts/p4config/names.py next to this directory); None if missing or broken."""
    try:
        spec = importlib.util.spec_from_file_location("p4config_names_guard", HERE.parent / "p4config" / "names.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for attr in ("GUARD_TEXT", "ROOMS", "WEB_BLOCK"):
            getattr(mod, attr)
        return mod
    except Exception:  # noqa: BLE001
        return None


_N = _load_names()
_SUFFIX = re.escape(_BASE[len("brainir"):]) if _BASE.lower().startswith("brainir") and len(_BASE) > len("brainir") else "(?!)"
FORBIDDEN_PATTERNS = [
    rf"dev[\\/]+brainir(?!{_SUFFIX}(?![\w-]))",       # the main repository and every other BrainIR directory
    rf"c--dev-brainir(?!{_SUFFIX.replace('_', '-')}(?![\w-]))",
]
if _N is not None:
    FORBIDDEN_PATTERNS += list(_N.GUARD_TEXT)
    FORBIDDEN_PATTERNS += [rf"{re.escape(r.lower())}(?![\w-])" for r in _N.ROOMS if r.lower() != _BASE.lower()]
_FORBIDDEN_RX = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]
_ROOM_NAME_RE = re.compile(r"(?i)brainir_p\d[\w-]*")
WEB_BLOCK = [re.compile(p, re.IGNORECASE) for p in (_N.WEB_BLOCK if _N is not None else ())]


def _load_protected() -> dict:
    try:
        return json.loads((Path(AUDIT_DIR) / f"protected_{_BASE}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


PROT = _load_protected()
CONTROL_NAMES = {"claude.md", "claude.local.md", ".mcp.json"}
CONTROL_TOPS = {"sbx", "cleanroom_manifest.json", "claude.md", "claude.local.md", ".mcp.json", ".claude"}
PLANTED_NAMES = {"sitecustomize.py", "usercustomize.py"}
FILES = {f.lower() for f in PROT.get("files") or []} | CONTROL_TOPS
RO_TOPS = {t.lower() for t in PROT.get("ro_tops") or []} or ({f.split("/", 1)[0] for f in FILES} | CONTROL_TOPS)
AGENT_AREAS = [a.lower().rstrip("/") for a in (PROT.get("agent_areas") or [".tmp"])]
#: shared areas owned per agent (review F round 2, N-M2): readable by every agent, writable only in <area>/<own scratch>/
OWNED_AREAS = [a.lower().rstrip("/") for a in (PROT.get("owned_areas") or [])]
WORK = None if PROT.get("work_areas") is None else [w.lower().rstrip("/") for w in PROT["work_areas"]
                                                     if w.lower().rstrip("/") not in AGENT_AREAS]

# ------------------------------------------------------------------------------------------------ refusal classes (F-M2)
CLASSES = {
    "error": ("G0", "the room guard could not check this call, so it was refused (report it to the orchestrator if it persists)"),
    "text": ("G1", "this input is not allowed in the room"),
    "outside": ("G2", "the path is outside the room or in another agent's private area; work only inside the room"),
    "host": ("G3", "this program may not run on the host: run code in the Docker sandbox with the bare command sbx "
                   "(e.g. sbx python ..., sbx pytest ..., sbx bash script.sh)"),
    "readonly": ("G4", "you may write only inside your work areas (see CLAUDE.md), never Claude control files; write-capable or "
                       "code-running options of host tools (sed w/r/e, awk redirection / system(), find -exec / -delete / -fprint, "
                       "split, xargs, dd) are refused"),
    "tool": ("G5", "this tool is disabled in the room"),
    "web": ("G6", "this web request is not allowed (methods-only research)"),
    "construct": ("G7", "this shell construct is not allowed in the room: file arguments and scripts must be literal (no variables "
                        "from runtime data, command substitutions or ANSI-C quoting as paths), no .., /./, links, encoded text, "
                        "network tools or killing processes by name; do such work inside the sandbox (sbx bash -c ...)"),
    "sbx": ("G8", "run the sandbox with the bare command sbx (no path, no ./sbx)"),
    "sbxcheck": ("G8", "the sandbox wrapper does not match its record (the orchestrator may be updating the room: retry in a minute; "
                       "if it persists, report it)"),
    "planted": ("G9", "a Claude control file was found in this directory tree; report it to the orchestrator"),
}


class Refuse(Exception):
    def __init__(self, cls: str, detail: str):
        super().__init__(detail)
        self.cls, self.detail = cls, detail


# ------------------------------------------------------------------------------------------------ lists
SHELL_CONSTRUCTS_PATH = [   # applied to the path-bearing host text only (not to patterns, scripts, echo text or sbx arguments)
    (r"(?<![.\w])\.\.(?![.\w])", "parent-directory reference"),
    (r"[\\/]\.[\\/]", "'/./' path component"),
    (r"\w~\d", "8.3 short path name"),
    (r"\$\{?(pwd|oldpwd|home|userprofile|appdata|localappdata|temp|tmp|psscriptroot|pshome|profile|tmpdir)\b\}?", "location variable"),
    (r"\$env:\w+|%\w+%", "environment path variable"),
    (r"(^|[\s\"'=])[a-zA-Z]:(?![\\/])\S", "drive-relative path"),
    (r"\$pwd\b|\.parent\b|\bpardir\b|\.parents\b|\[(system\.)?environment\]::|\[(system\.)?io\.", "parent / environment path API"),
    (r"dirname\s*\(\s*os\.getcwd|getcwd\(\)\s*\)\s*\.\s*parent|\bos\.path\.split\s*\(\s*os\.getcwd", "parent-of-cwd idiom"),
]
SHELL_CONSTRUCTS_ALL = [    # applied to the whole command (here-document bodies removed)
    (r"(\$\(|`)\s*(pwd|cd|dirname|realpath|readlink|cygpath|cmd)\b", "location-computing command substitution"),
    (r"\b(split-path|join-path|resolve-path|get-location|push-location|get-psdrive|new-psdrive|convert-path)\b", "PowerShell path cmdlet"),
    (r"\bmklink\b|-itemtype\s+['\"]?(symboliclink|junction|hardlink)|(^|[\s;&|(])ln\s|\bfsutil\b|\bsubst\b|\bnet\s+use\b", "link"),
    (r"\bbase64\b|\bxxd\b|\bcertutil\b|frombase64string|\s-enc(odedcommand)?\b|\biex\b|invoke-expression|(^|[\s;&|(])eval\s|"
     r"\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}|\\[0-7]{3}|\bchr\(|\[char\]", "encoded or escaped text"),
    (r"\\\\[?.]\\|(^|[\s\"'=(])\\\\[A-Za-z0-9]", "UNC or device path"),
    (r"(^|[\s;&|(\"'])(curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm|start-bitstransfer|ftp|sftp|scp|ssh|telnet|nc|ncat|"
     r"bitsadmin)(\.exe)?(\s|$)", "network tool"),
    (r"stop-process\s+(-name|-processname)\b|\|\s*stop-process\b|\|\s*%\s*\{\s*stop-process|\btaskkill\b[^\n;&|]*/im\b|"
     r"\b(pkill|killall)\b|\bwmic\b[^\n;&|]*\bdelete\b|get-process[^\n;&]*\|\s*(stop-process|kill)|\bstop-process\s+\*", "kill by name"),
    (r"\$\{!", "indirect expansion"),
]
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
    "gzip", "gunzip", "zcat", "md5sum", "sha256sum", "sha1sum", "cksum", "jq", "tee", "wait", "kill", "jobs", "fg", "bg",
    "type", "which", "whoami", "uname", "hostname", "pwd", "cd", "pushd", "popd", "read", "seq", "expr", "yes", "numfmt",
    "shuf", "exit", "return", "break", "continue", "local", "declare", "export", "set", "ulimit", "umask", "sbx", ":", "nproc",
    "env", "timeout", "nice", "nohup", "command", "time", "stdbuf", "realpath", "dirname", "readlink", "printenv",
}
TEXT_ONLY = {"echo", "true", "false", "sleep", "seq", "expr", "yes", "basename", "dirname", "wait", "jobs", "fg", "bg", "exit", "return",
             "break", "continue", "set", "umask", "ulimit", "type", "which", "whoami", "uname", "hostname", "nproc", "pwd", "printenv",
             ":", "numfmt", "tr"}
WRAPPERS = {"env", "timeout", "nice", "nohup", "command", "time", "stdbuf"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "{", "}", "time"}
INTERPRETERS = re.compile(r"(?i)^(python[0-9.]*w?|py|pythonw|uv|uvx|pip[0-9.]*|pytest|py\.test|conda|mamba|poetry|pipx|jupyter|ipython|"
                          r"node|nodejs|npm|npx|deno|bun|yarn|pnpm|perl|ruby|gem|php|lua|java|javaw|javac|dotnet|rscript|r|julia|go|"
                          r"cargo|rustc|gcc|g\+\+|cc|clang|make|cmake|ninja|powershell|pwsh|cmd|cscript|wscript|mshta|rundll32|regsvr32|"
                          r"wsl|bash|sh|zsh|dash|ksh|fish|busybox|git|docker|docker-compose|kubectl|modal|claude|code|start|explorer|"
                          r"source|\.|exec|eval|trap|alias|builtin|enable|hash|coproc|ps|tar|zip|unzip|7z|curl|wget|ssh|scp|xargs|"
                          r"dd|install|split|ln|shopt|typeset|readonly|let|mapfile|readarray)$")
ENV_FORBIDDEN = re.compile(r"(?i)^(path|pythonpath|pythonhome|pythonstartup|ld_preload|ld_library_path|bash_\w*|bashopts|env|shellopts|"
                           r"prompt_command|ps[0-4]|ifs|home|userprofile|temp|tmp|tmpdir|cdpath|globignore|pwd|oldpwd|dirstack|execignore|"
                           r"msys\w*|docker_\w*|p[34]_(?!sbx_)\w*|claude\w*|anthropic\w*|modal\w*|git_\w*|path_\w*)$")
ALLOWED_OUTSIDE = [re.compile(p, re.IGNORECASE) for p in (
    r"^[a-z]:[\\/]+program files[\\/]+git([\\/]|$)", r"^/dev/null$", r"^nul$", r"^/dev/std(in|out|err)$",
)]
NUMERIC_VARS = {"random", "seconds", "lineno", "srandom", "bashpid", "ppid", "epochseconds"}

PATH_TOKEN = re.compile(r"""(?ix)
    (?<![\w])[a-z]:[\\/][^\s"'`|;&<>()]*
  | (?:^|(?<=[\s"'=]))/[a-z](?:/[^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
  | (?:^|(?<=[\s"'=]))~(?:[\\/][^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
  | (?:^|(?<=[\s"'=]))/(?:tmp|home|users|mnt|etc|root|var|proc|cygdrive|dev|usr|bin|opt|srv|run|sys)(?:/[^\s"'`|;&<>()]*)?(?=$|[\s"'`|;&<>()])
""")
QUOTED_ABS = re.compile(r"""["']\s*((?:[a-zA-Z]:[\\/]|/[a-zA-Z]/)[^"']*)["']""")
ABS_TOKEN = re.compile(r"(?i)^([a-z]:[\\/]|/[a-z](/|$)|~|/(tmp|home|users|mnt|etc|root|var|proc|cygdrive|dev|usr|bin|opt|srv|run|sys)(/|$))")
GLOB_CHARS = re.compile(r"[*?\[]")
EXTGLOB = re.compile(r"[@!+*?]\(")


# ------------------------------------------------------------------------------------------------ log and helpers
def _log(decision: str, tool: str, cls: str, reason: str, detail: str, eid: str) -> None:
    try:
        Path(AUDIT_DIR).mkdir(parents=True, exist_ok=True)
        with open(Path(AUDIT_DIR) / f"guard_{AGENT}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": AGENT, "decision": decision, "tool": tool,
                                 "class": cls, "event": eid, "reason": reason, "detail": detail[:20000]}) + "\n")
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


def _rel(p: str) -> str | None:
    if not _under(p, CLEAN):
        return None
    r = os.path.relpath(p, CLEAN).replace("\\", "/").lower()
    return "" if r == "." else r


def _other_agent(p: str) -> bool:
    rel = _rel(p)
    if not rel:
        return False
    parts = rel.split("/")
    return parts[0] in AGENT_AREAS and len(parts) >= 2 and parts[1] != AGENT_L


def _inside(p: str, allow_own_store: bool = True) -> bool:
    if _under(p, CLEAN):
        return not _other_agent(p)
    return allow_own_store and _under(p, OWN_STORE_DIR)


def _allowed_outside(raw: str, resolved: str) -> bool:
    return any(a.match(raw.strip().strip("\"'")) or a.match(resolved) for a in ALLOWED_OUTSIDE)


def _writable(p: str) -> bool:
    """May the agent create / modify / delete this (resolved) path? Only inside its work areas; never control files or hooks."""
    rel = _rel(p)
    if not rel:
        return False
    parts = rel.split("/")
    name = parts[-1]
    if name in CONTROL_NAMES or ".claude" in parts or name in PLANTED_NAMES or name.endswith(".pth"):
        return False
    if parts[0] in AGENT_AREAS:
        return len(parts) >= 2 and parts[1] == AGENT_L
    if rel in FILES:
        return False
    if WORK is None:
        return parts[0] not in RO_TOPS
    for o in OWNED_AREAS:                       # a shared area: only the agent's own subdirectory (N-M2)
        if rel == o or rel.startswith(o + "/"):
            rest = rel[len(o) + 1:].split("/") if rel != o else []
            return bool(rest) and rest[0] == AGENT_L
    return any(rel.startswith(w + "/") for w in WORK)


def _planted_near(p: str) -> bool:
    """Is there a Claude control file in a directory between p and the room root (exclusive)?"""
    if _rel(p) is None:
        return False
    d = p if os.path.isdir(p) else os.path.dirname(p)
    while _under(d, CLEAN) and os.path.normcase(d) != CLEAN:
        try:
            names = {n.lower() for n in os.listdir(d)}
        except OSError:
            names = set()
        if names & (CONTROL_NAMES | {".claude"}):
            return True
        d = os.path.dirname(d)
    return False


def _normalise_command(cmd: str) -> str:
    s = cmd.replace('""', "").replace("''", "")
    s = s.replace("\\\n", " ").replace("`\n", " ")
    return s


def _forbidden_text(s: str) -> str | None:
    if _N is None:
        return "names config unavailable"
    s = OWN_STORE.sub("<own-session-store>", s.replace(SENT, "$"))
    for rx in _FORBIDDEN_RX:
        if rx.search(s):
            return f"forbidden pattern {rx.pattern!r}"
    for m in _ROOM_NAME_RE.finditer(s):
        if m.group(0).lower() != _BASE.lower():
            return "another room is named"
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


# ------------------------------------------------------------------------------------------------ the sandbox wrapper (F-B4)
def _sha_text(p: str) -> str:
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def _which_sbx(cwd: str) -> str | None:
    """The file bash would run for the bare word `sbx` with this PATH (an empty PATH entry is the working directory)."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        d = d.strip().strip('"')
        cand = os.path.join(cwd if d in ("", ".") else d, "sbx")
        if os.path.isfile(cand):
            return os.path.normcase(os.path.realpath(cand))
    return None


def _expected_sbx_hash() -> str | None:
    """The sbx record of the OUTSIDE manifest (research/phase4/CLEANROOM_MANIFEST*.json) and of protected_<room>.json (they must
    agree); a room built before version 3 falls back to its in-room manifest view."""
    want = None
    man = PROT.get("manifest")
    if man:
        try:
            m = json.loads(Path(man).read_text(encoding="utf-8"))
            want = next((e["sha256"] for e in m.get("files", []) if e.get("path") == "sbx"), None)
        except (OSError, ValueError, KeyError):
            return None
    if want is None and not PROT.get("sbx_sha256"):
        try:
            m = json.loads(Path(CLEAN, "CLEANROOM_MANIFEST.json").read_text(encoding="utf-8"))
            want = next((e["sha256"] for e in m.get("files", []) if e.get("path") == "sbx"), None)
        except (OSError, ValueError, KeyError):
            return None
    if PROT.get("sbx_sha256"):
        if want is not None and want != PROT["sbx_sha256"]:
            return None
        want = PROT["sbx_sha256"]
    return want


def _sbx_integrity(cwd: str) -> str | None:
    outside = os.path.normcase(os.path.realpath(PROT.get("outside_sbx") or os.path.join(AUDIT_DIR, "sbx_bin", _BASE, "sbx")))
    found = _which_sbx(cwd)
    if found != outside:
        return f"sbx resolves to {found!r}, not to the outside copy"
    want = _expected_sbx_hash()
    try:
        have = _sha_text(outside)
    except OSError:
        return "outside sbx unreadable"
    if not want or have != want:
        return "outside sbx hash differs from the manifest"
    if PROT.get("acl"):
        try:
            spec = importlib.util.spec_from_file_location("p4_ntfs_guard", HERE / "ntfs_protect.py")
            acl = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(acl)
            if not acl.is_protected(outside):
                return "outside sbx lost its OS protection"
        except Exception as e:  # noqa: BLE001
            return f"ACL check failed ({type(e).__name__})"
    return None


# ------------------------------------------------------------------------------------------------ shell structure
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)", re.DOTALL)
PYC = re.compile(r"(\bpy(?:thon[0-9.]*)?(?:\.exe)?\b[^\n;&|]*?\s-c\s+)(\"(?:\\.|[^\"\\])*\"|'[^']*')", re.DOTALL)


def _split_bodies(s: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Here-document bodies and python -c bodies -> placeholders. Returns (text, [(kind, body)], [host-expanded texts]): kind 'box' =
    consumed by sbx, 'data' = written to a file / fed to a host tool, 'sh' = consumed by a host shell (refused anyway). UNQUOTED
    here-documents and double-quoted -c bodies are expanded by the HOST shell first: they are returned for the substitution and
    arithmetic checks."""
    bodies: list[tuple[str, str]] = []
    expanded: list[str] = []

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
        if not m.group(1):
            expanded.append(m.group(3))
        return m.group(0)[: m.group(0).find("\n")] + " __BODY__"
    t = HEREDOC.sub(heredoc, s)

    def pyc(m):
        body = m.group(2)
        bodies.append(("box", body[1:-1]))
        if body.startswith('"'):
            expanded.append(body[1:-1])
        return m.group(1) + " __BODY__ "
    t = PYC.sub(pyc, t)
    return t, bodies, expanded


def _extract_substitutions(s: str, subs: list[str] | None = None, dq_context: bool = False) -> tuple[str, list[str]]:
    """Replace $(...) and `...` by __SUBST<n>__ and <(...), >(...) by __PSUBST<n>__ (outside single quotes, also inside arithmetic
    expansions); return (text, [inner commands]). dq_context: s is the body of an unquoted here-document or of a double-quoted
    string, where quote characters are literal and every $(...) is expanded."""
    subs = [] if subs is None else subs
    out, i, n = [], 0, len(s)
    sq = dq = False
    while i < n:
        c = s[i]
        if c == "'" and not dq and not dq_context:
            sq = not sq
            out.append(c)
            i += 1
            continue
        if c == '"' and not sq and not dq_context:
            dq = not dq
            out.append(c)
            i += 1
            continue
        if c == "\\" and not sq and i + 1 < n:
            out.append(s[i:i + 2])
            i += 2
            continue
        if not sq and (s.startswith("$(", i) or ((s.startswith("<(", i) or s.startswith(">(", i)) and not dq)):
            if s.startswith("$((", i):                       # arithmetic expansion: kept as text (checked separately); the
                depth, k = 2, i + 3                          # substitutions inside it are extracted like any other
                while k < n and depth:
                    depth += (s[k] == "(") - (s[k] == ")")
                    k += 1
                inner_text, _ = _extract_substitutions(s[i + 3:max(i + 3, k - 2)], subs, dq_context)
                out.append("$((" + inner_text + "))")
                i = k
                continue
            proc = not s.startswith("$(", i)
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
            out.append(f"__{'P' if proc else ''}SUBST{len(subs) - 1}__")
            i = j
            continue
        if c == "`" and not sq:
            j = s.find("`", i + 1)
            j = n if j < 0 else j
            subs.append(s[i + 1:j])
            out.append(f"__SUBST{len(subs) - 1}__")
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out), subs


def _segments(s: str) -> list[tuple[str, str]]:
    """Split a command list into simple commands (quote-aware) at ; & | newline ( ) and at braces that stand alone. Returns
    [(kind, segment)] with kind 'cmd', 'case' (closed by an unmatched ')', i.e. a case pattern), 'open' / 'close' (subshell)."""
    segs, cur, i, n, depth = [], [], 0, len(s), 0
    sq = dq = False

    def flush(kind="cmd"):
        seg = "".join(cur).strip()
        if seg:
            segs.append((kind, seg))
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
            if s.startswith("$((", i) or s.startswith("$[", i):
                j = s.find("))" if s.startswith("$((", i) else "]", i)
                j = n if j < 0 else j + (2 if s.startswith("$((", i) else 1)
                cur.append(s[i:j])
                i = j
                continue
            if s.startswith("[[", i) and (i == 0 or s[i - 1] in " \t\n;&|(!"):
                j = s.find("]]", i)
                j = n if j < 0 else j + 2
                cur.append(s[i:j])
                i = j
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
                segs.append(("open", "("))
                i += 1
                continue
            if c == ")":
                if depth > 0:
                    depth -= 1
                    flush()
                    segs.append(("close", ")"))
                else:
                    flush("case")
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


def _tokens(seg: str) -> list[str]:
    """Words of a simple command with bash quoting. A `$` that the shell does not expand (inside single quotes, or escaped) is
    replaced by SENT, so that only real expansions are treated as variables."""
    words, cur, i, n, in_word = [], [], 0, len(seg), False
    while i < n:
        c = seg[i]
        if c in " \t\n":
            if in_word:
                words.append("".join(cur))
                cur, in_word = [], False
            i += 1
            continue
        in_word = True
        if c == "'":
            j = seg.find("'", i + 1)
            j = n if j < 0 else j
            cur.append(seg[i + 1:j].replace("$", SENT))
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            while j < n and seg[j] != '"':
                if seg[j] == "\\" and j + 1 < n and seg[j + 1] in '"\\$`\n':
                    cur.append(SENT if seg[j + 1] == "$" else seg[j + 1])
                    j += 2
                    continue
                cur.append(seg[j])
                j += 1
            i = j + 1
            continue
        if c == "\\" and i + 1 < n:
            cur.append(SENT if seg[i + 1] == "$" else seg[i + 1])
            i += 2
            continue
        cur.append(c)
        i += 1
    if in_word:
        words.append("".join(cur))
    return words


def _plain(w: str) -> str:
    return w.replace(SENT, "$")


def _cmd_name(w: str) -> str:
    b = w.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return b[:-4] if b.endswith(".exe") else b


REDIR = re.compile(r"^(\d*)(&>>|&>|>>|>\||>&|<<<|<>|<&|>|<)(.*)$", re.DOTALL)
WRITE_REDIR = {">", ">>", ">|", ">&", "&>", "&>>", "<>"}


def _split_words(seg: str) -> tuple[list[str], list[tuple[str, str]]]:
    toks = _tokens(seg)
    words, redirs, k = [], [], 0
    while k < len(toks):
        t = toks[k]
        if t.startswith(("<<-", "<<")) and not t.startswith("<<<"):
            k += 2 if t in ("<<", "<<-") else 1              # here-document marker (its body was removed)
            continue
        m = REDIR.match(t)
        if m and not ASSIGN.match(t):
            op, target = m.group(2), m.group(3)
            if not target and k + 1 < len(toks):
                target = toks[k + 1]
                k += 1
            redirs.append((op, target))
            k += 1
            continue
        words.append(t)
        k += 1
    return words, redirs


# ------------------------------------------------------------------------------------------------ variables and expansion
ASSIGN = re.compile(r"^([A-Za-z_]\w*)(\[[^\]]*\])?(\+?)=(.*)$", re.DOTALL)
VAR_REF = re.compile(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)|__SUBST(\d+)__|\$\(\([^)]*\)\)|\$\[[^\]]*\]|\$\{[^}]*\}|\$[0-9@*#?$!_-]")
SEQ_SUBST = re.compile(r"^\s*seq(\s+-?\d+){1,3}\s*$")


class Ctx:
    def __init__(self, cwd: str, sub_numeric: dict[int, bool]):
        self.cwd0 = cwd
        self.cur = cwd
        self.stack: list[str] = []
        self.cwds = {cwd}
        self.sub_numeric = sub_numeric
        self.env: dict[str, list[str] | None] = {}
        self.path_text: list[str] = []

    def values(self, tok: str, limit: int = 64) -> list[str] | None:
        """The word's possible values after substituting variables assigned from literals in this command (None = not literal:
        unknown or data variable, command substitution, positional parameter, ANSI-C / locale quoting, ...)."""
        if "$" not in tok and "__SUBST" not in tok and "`" not in tok:
            return [_plain(tok)]
        pieces, pos = [], 0
        for m in VAR_REF.finditer(tok):
            pieces.append([tok[pos:m.start()]])
            name = m.group(1) or m.group(2)
            g0 = m.group(0)
            if m.group(3) is not None:
                if not self.sub_numeric.get(int(m.group(3))):
                    return None
                pieces.append(["0"])
            elif g0.startswith(("$((", "$[")):
                pieces.append(["0"])
            elif name:
                if name.lower() in NUMERIC_VARS:
                    pieces.append(["0"])
                elif self.env.get(name) is not None:
                    vals = [v.replace("$!", "0") for v in self.env[name]]
                    if any("$" in v or "__SUBST" in v or "`" in v for v in vals):
                        return None
                    pieces.append(vals)
                else:
                    return None
            elif g0 == "$!":
                pieces.append(["0"])
            else:
                return None
            pos = m.end()
        pieces.append([tok[pos:]])
        if any("$" in p or "`" in p for alts in pieces for p in alts):
            return None
        out = []
        for combo in itertools.product(*pieces):
            out.append(_plain("".join(combo)))
            if len(out) > limit:
                return None
        return out


def _brace_expand(s: str, limit: int = 512) -> list[str]:
    """Bash brace expansion ({a,b}, {1..3}, {a..c}) of one word."""
    depth, start = 0, -1
    for i, c in enumerate(s):
        if c == "{" and (i == 0 or s[i - 1] != "$"):
            if depth == 0:
                start = i
            depth += 1
        elif c == "}" and depth:
            depth -= 1
            if depth == 0:
                inner, pre, post = s[start + 1:i], s[:start], s[i + 1:]
                parts, d, cur = [], 0, []
                for ch in inner:
                    if ch == "," and d == 0:
                        parts.append("".join(cur))
                        cur = []
                        continue
                    d += ch == "{"
                    d -= ch == "}"
                    cur.append(ch)
                parts.append("".join(cur))
                if len(parts) == 1:
                    m = re.fullmatch(r"(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?", inner)
                    mc = re.fullmatch(r"([A-Za-z])\.\.([A-Za-z])", inner)
                    if m:
                        a, b = int(m.group(1)), int(m.group(2))
                        step = abs(int(m.group(3) or 1)) or 1
                        rng = range(a, b + 1, step) if a <= b else range(a, b - 1, -step)
                        parts = [str(x) for x in list(rng)[:limit]]
                    elif mc:
                        a, b = ord(mc.group(1)), ord(mc.group(2))
                        parts = [chr(x) for x in (range(a, b + 1) if a <= b else range(a, b - 1, -1))]
                    else:
                        return [pre + "{" + inner + "}" + r for r in _brace_expand(post, limit)][:limit]
                out = []
                for p in parts:
                    for r in _brace_expand(pre + p + post, limit):
                        out.append(r)
                        if len(out) >= limit:
                            return out
                return out
    return [s]


def _glob_danger(pattern: str) -> bool:
    """Could a glob component match '.' or '..' (bash matches a leading dot only explicitly)?"""
    for comp in re.split(r"[\\/]", pattern):
        if not GLOB_CHARS.search(comp):
            continue
        if comp.startswith(".") or (comp.startswith("[") and "." in comp.split("]", 1)[0]):
            if fnmatch.fnmatchcase("..", comp) or fnmatch.fnmatchcase(".", comp):
                return True
    return False


def _expand(word: str, cwd: str, limit: int = 5000) -> list[str]:
    """Brace + glob expansion of one literal word (the literal itself is always included)."""
    out = []
    for w in _brace_expand(word):
        if EXTGLOB.search(w):
            raise Refuse("construct", "extended glob in a path")
        out.append(w)
        if GLOB_CHARS.search(w):
            if _glob_danger(w):
                raise Refuse("construct", "glob that can match '.' or '..'")
            try:
                if re.match(r"^/[a-zA-Z]/", w):
                    matches = []                      # (outside paths are refused on the literal)
                elif os.path.isabs(w):
                    matches = _glob.glob(w, include_hidden=True)
                else:
                    matches = _glob.glob(w, root_dir=cwd, include_hidden=True)
            except (OSError, ValueError, re.error):
                matches = []
            out.extend(matches[:limit])
    return out


# ------------------------------------------------------------------------------------------------ path checks
def _check_path(word: str, ctx: Ctx, mode: str = "read") -> None:
    """A file argument: literal (after variable substitution), inside the room after expansion; writable for mode 'write'."""
    vals = ctx.values(word)
    if vals is None:
        raise Refuse("construct", f"non-literal path argument {_plain(word)[:80]!r}")
    for v in vals:
        if v in ("-", "/dev/null", "nul", "/dev/stdin", "/dev/stdout", "/dev/stderr") or re.fullmatch(r"__PSUBST\d+__", v):
            continue                                     # (a process substitution is a pipe; its command is checked on its own)
        if v.startswith("~") and mode == "write":
            raise Refuse("outside", f"home-relative write target {v[:80]!r}")
        for e in _expand(v, ctx.cur):
            why = _forbidden_text(e)
            if why:
                raise Refuse("text", f"expanded path: {why}")
            ctx.path_text.append(shlex.quote(e))
            if mode == "write":
                p = _resolve(e, ctx.cur)
                if _allowed_outside(e, p):
                    continue
                if not _inside(p, allow_own_store=False):
                    raise Refuse("outside", f"write target outside the room: {e[:120]}")
                if not _writable(p):
                    raise Refuse("readonly", f"write target not in a work area: {e[:120]}")
            else:
                for c in ctx.cwds:
                    p = _resolve(e, c)
                    if not _inside(p) and not _allowed_outside(e, p):
                        raise Refuse("outside", f"path outside the room: {e[:120]}")


def _check_write_into(dest: str, srcs: list[str], ctx: Ctx, parents: bool = False) -> None:
    """cp / mv destination: into an existing directory (or one named with a trailing slash) -> dest/<basename of each source>."""
    vals = ctx.values(dest)
    if vals is None:
        raise Refuse("construct", "non-literal destination")
    for v in vals:
        if not (v.endswith(("/", "\\")) or os.path.isdir(_resolve(v, ctx.cur))):
            _check_path(v, ctx, "write")
            continue
        for s in srcs:
            for sv in ctx.values(s) or []:
                for e in _expand(sv, ctx.cur):
                    tail = e.strip("/\\") if parents else os.path.basename(e.rstrip("/\\"))
                    _check_path(v.rstrip("/\\") + "/" + tail, ctx, "write")


def _canon_long(a: str, known=None) -> str:
    """GNU getopt accepts any unambiguous PREFIX of a long option (`sort --outp=F` is `--output=F`, `sed --in-pl` is `--in-place`;
    review F round 2, N-m1): expand a prefix to the option it abbreviates. `known`: the TOOL's complete long-option list (GNU
    semantics: an exact name wins, a prefix of one option is that option, a prefix of several is refused, as GNU refuses it);
    without one, the union of every option the guard names (conservative: an abbreviation shared with another tool's option is
    refused). An unknown option is left unchanged."""
    k, eq, v = a.partition("=")
    pool = known if known else LONG_CANON
    if k in pool or len(k) <= 2:
        return a
    cands = [o for o in pool if o.startswith(k)]
    if len(cands) > 1:
        raise Refuse("readonly", f"ambiguous abbreviated long option {k[:40]}")
    return (cands[0] + (eq + v if eq else "")) if cands else a


def _opts(args: list[str], short_val: str = "", long_val: tuple = (), short_opt_attached: str = "", known=None) -> tuple[list, list]:
    """GNU-style option parsing: ([(option, value or None)], positionals). short_val: letters taking a value; long_val: long options
    taking a value ('--x=v' or '--x v'); short_opt_attached: letters with an OPTIONAL value that must be attached (sed -i[SUF]).
    Abbreviated long options are expanded first (`_canon_long`)."""
    opts, pos, i = [], [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos += args[i + 1:]
            break
        if a.startswith("--") and len(a) > 2:
            a = _canon_long(a, known)
            if "=" in a:
                k, v = a.split("=", 1)
                opts.append((k, v))
            elif a in long_val and i + 1 < len(args):
                opts.append((a, args[i + 1]))
                i += 1
            else:
                opts.append((a, None))
        elif a.startswith("-") and len(a) > 1:
            j = 1
            while j < len(a):
                c = a[j]
                if c in short_opt_attached:
                    opts.append(("-" + c, a[j + 1:]))
                    break
                if c in short_val:
                    if j + 1 < len(a):
                        opts.append(("-" + c, a[j + 1:]))
                    else:
                        opts.append(("-" + c, args[i + 1] if i + 1 < len(args) else ""))
                        i += 1
                    break
                opts.append(("-" + c, None))
                j += 1
        else:
            pos.append(a)
        i += 1
    return opts, pos


def _has(opts, *names) -> bool:
    return any(o in names for o, _ in opts)


def _vals(opts, *names) -> list[str]:
    return [v for o, v in opts if o in names and v is not None]


def _literal_script(word: str, ctx: Ctx, what: str) -> list[str]:
    """A sed script / awk program / jq filter must not be built from runtime data."""
    vals = ctx.values(word)
    if vals is None:
        raise Refuse("construct", f"{what} built from runtime data")
    return vals


# ------------------------------------------------------------------------------------------------ sed / awk programs
def _sed_bad(script: str) -> str | None:
    """None if the sed script only edits the stream; else why not (commands r R w W e, flags w e, unparsable text)."""
    s, i, n = script, 0, len(script)

    def ws(k):
        while k < n and s[k] in " \t":
            k += 1
        return k

    def regex_addr(k):
        if s[k] == "\\":
            if k + 1 >= n:
                return None
            d, k = s[k + 1], k + 2
        else:
            d, k = "/", k + 1
        while k < n and s[k] != d:
            if s[k] == "\\":
                k += 2
            elif s[k] == "\n":
                return None
            else:
                k += 1
        if k >= n:
            return None
        k += 1
        while k < n and s[k] in "IM":
            k += 1
        return k

    def addr(k):
        if k < n and s[k].isdigit():
            while k < n and s[k].isdigit():
                k += 1
            if k < n and s[k] == "~":
                k += 1
                while k < n and s[k].isdigit():
                    k += 1
            return k
        if k < n and s[k] == "$":
            return k + 1
        if k < n and s[k] in "/\\":
            return regex_addr(k)
        return k
    while i < n:
        i = ws(i)
        if i >= n:
            break
        if s[i] in ";\n":
            i += 1
            continue
        if s[i] == "#":
            j = s.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        j = addr(i)
        if j is None:
            return "unparsable address"
        if j != i:
            i = ws(j)
            if i < n and s[i] == ",":
                i = ws(i + 1)
                if i < n and s[i] in "+~":
                    i += 1
                    while i < n and s[i].isdigit():
                        i += 1
                else:
                    j = addr(i)
                    if j is None or j == i:
                        return "unparsable address"
                    i = j
                i = ws(i)
        if i < n and s[i] == "!":
            i = ws(i + 1)
        if i >= n:
            return "missing command"
        c = s[i]
        if c in "eEwWrR":
            return f"sed command {c}"
        if c in "{}=dDgGhHnNpPxzFlqQLv":
            i += 1
            while c in "lqQL" and i < n and s[i].isdigit():
                i += 1
            continue
        if c in ":btT":
            j = i + 1
            stop = ";\n" if c == ":" else ";\n}"
            while j < n and s[j] not in stop:
                j += 1
            i = j
            continue
        if c in "aic":
            j = i + 1
            while j < n:
                if s[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if s[j] == "\n":
                    break
                j += 1
            i = j
            continue
        if c in "sy":
            if i + 1 >= n or s[i + 1] in "\\\n":
                return "bad delimiter"
            d, j, parts = s[i + 1], i + 2, 0
            while j < n and parts < 2:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == d:
                    parts += 1
                j += 1
            if parts < 2:
                return "unterminated command"
            if c == "s":
                while j < n and s[j] not in ";\n}#":
                    f = s[j]
                    if f in "we":
                        return f"s flag {f}"
                    if f not in "gpiImM0123456789 \t":
                        return f"unknown s flag {f!r}"
                    j += 1
            i = j
            continue
        return f"unknown sed command {c!r}"
    return None


def _strip_awk(prog: str) -> str:
    """awk program without string literals and regex literals (division is kept)."""
    out, i, n, prev = [], 0, len(prog), ""
    while i < n:
        c = prog[i]
        if c == '"':
            j = i + 1
            while j < n and prog[j] != '"':
                j += 2 if prog[j] == "\\" else 1
            out.append('""')
            i = j + 1
            prev = '"'
            continue
        if c == "/" and (prev == "" or prev in "(,~!&|{};\n=:?"):
            j = i + 1
            while j < n and prog[j] != "/" and prog[j] != "\n":
                j += 2 if prog[j] == "\\" else 1
            out.append("//")
            i = j + 1
            prev = "/"
            continue
        out.append(c)
        if not c.isspace():
            prev = c
        i += 1
    return "".join(out)


def _awk_bad(prog: str) -> str | None:
    p = _strip_awk(prog)
    if re.search(r"\bsystem\s*\(|@load|@include|@namespace|\bARGV\b|\bARGC\b|\bENVIRON\s*\[[^]]*\]\s*=|\bPROCINFO\b", p):
        return "awk system() / extensions / ARGV"
    if re.search(r"\|&|(?<!\|)\|(?!\|)", p):
        return "awk pipe"
    if re.search(r"\bgetline\b[^;{}\n]*<", p):
        return "awk getline from a file"
    for m in re.finditer(r"\bprintf?\b([^;{}\n]*)", p):
        stmt, prev = m.group(1), None
        while prev != stmt:
            prev, stmt = stmt, re.sub(r"\([^()]*\)", "", stmt)
        if ">" in stmt:
            return "awk output redirection"
    return None


# ------------------------------------------------------------------------------------------------ host commands
LONG_VAL_COMMON = ("--target-directory", "--suffix", "--reference", "--mode", "--date", "--time", "--output", "--expression", "--file",
                   "--regexp", "--max-count", "--after-context", "--before-context", "--context", "--glob", "--iglob", "--type",
                   "--type-not", "--type-add", "--max-depth", "--field-separator", "--assign", "--source", "--lines", "--bytes",
                   "--key", "--buffer-size", "--temporary-directory", "--delimiter", "--fields", "--characters",
                   "--skip-fields", "--skip-chars", "--check-chars", "--head-count", "--input-range", "--random-source", "--width",
                   "--format", "--printf", "--exclude-from", "--exclude", "--include", "--exclude-dir", "--ignore-file", "--replace",
                   "--sort", "--sortr", "--threads", "--max-columns", "--encoding", "--label", "--ignore", "--hide", "--from-file",
                   "--to-file", "--output-delimiter", "--block-size", "--time-style", "--color", "--colour", "--indent", "--signal",
                   "--kill-after", "--adjustment", "--line-length", "--pid", "--sleep-interval", "--max-filesize", "--path-separator",
                   "--separator", "--group-separator", "--relative-to", "--relative-base", "--devices", "--directories",
                   "--binary-files", "--parallel", "--batch-size")


def _longs(s: str) -> frozenset:
    return frozenset("--" + w for w in s.split())


#: the COMPLETE long options of the host tools the guard checks (GNU coreutils, sed, grep, diffutils, gzip, file), so that an
#: abbreviation is expanded exactly as the tool expands it (`_canon_long`)
LONGS = {
    "sort": _longs("batch-size buffer-size check compress-program debug dictionary-order field-separator files0-from "
                   "general-numeric-sort help human-numeric-sort ignore-case ignore-leading-blanks ignore-nonprinting key merge month-sort "
                   "numeric-sort output parallel random-sort random-source reverse sort stable temporary-directory unique version "
                   "version-sort zero-terminated"),
    "sed": _longs("debug expression file follow-symlinks help in-place line-length null-data zero-terminated posix quiet silent "
                  "regexp-extended sandbox separate unbuffered version"),
    "cp": _longs("archive attributes-only backup copy-contents debug dereference force interactive link no-clobber no-dereference "
                 "preserve no-preserve parents recursive reflink remove-destination sparse strip-trailing-slashes symbolic-link suffix "
                 "target-directory no-target-directory update verbose one-file-system context keep-directory-symlink help version"),
    "mv": _longs("backup debug exchange force interactive no-clobber no-copy strip-trailing-slashes suffix target-directory "
                 "no-target-directory update verbose context help version"),
    "du": _longs("null all apparent-size block-size bytes total dereference-args max-depth files0-from human-readable inodes "
                 "dereference count-links no-dereference separate-dirs si summarize threshold time time-style exclude-from exclude "
                 "one-file-system help version"),
    "wc": _longs("bytes chars lines files0-from max-line-length words total help version"),
    "grep": _longs("extended-regexp fixed-strings basic-regexp perl-regexp regexp file ignore-case no-ignore-case word-regexp "
                   "line-regexp null-data no-messages invert-match version help max-count byte-offset line-number line-buffered "
                   "with-filename no-filename label only-matching quiet silent binary-files text devices directories exclude "
                   "exclude-from exclude-dir include recursive dereference-recursive files-without-match files-with-matches count "
                   "initial-tab null before-context after-context context group-separator no-group-separator color colour binary"),
    "shuf": _longs("echo input-range head-count output random-source repeat zero-terminated help version"),
    "touch": _longs("no-create date no-dereference reference time help version"),
    "chmod": _longs("changes no-preserve-root preserve-root quiet silent reference recursive verbose help version"),
    "date": _longs("date debug file iso-8601 resolution rfc-email rfc-3339 reference set universal utc help version"),
    "diff": _longs("normal brief report-identical-files context unified ed rcs side-by-side width left-column suppress-common-lines "
                   "show-c-function show-function-line label expand-tabs initial-tab tabsize suppress-blank-empty paginate "
                   "new-file unidirectional-new-file ignore-case ignore-tab-expansion ignore-trailing-space ignore-space-change "
                   "ignore-all-space ignore-blank-lines ignore-matching-lines text strip-trailing-cr recursive no-dereference "
                   "exclude exclude-from starting-file from-file to-file ignore-file-name-case no-ignore-file-name-case "
                   "old-line-format new-line-format unchanged-line-format line-format old-group-format new-group-format "
                   "unchanged-group-format changed-group-format minimal horizon-lines speed-large-files color palette "
                   "help version"),
    "file": _longs("brief checking-printout exclude exclude-quiet extension files-from separator no-dereference dereference "
                   "magic-file mime mime-type mime-encoding keep-going list no-buffer no-pad print0 preserve-date raw "
                   "special-files uncompress uncompress-noreport parameter apple help version"),
    "gzip": _longs("stdout to-stdout decompress uncompress force help keep list license no-name name quiet recursive rsyncable "
                   "suffix synchronous test verbose version fast best"),
    "uniq": _longs("count repeated all-repeated skip-fields group ignore-case skip-chars unique zero-terminated check-chars help "
                   "version"),
    "md5sum": _longs("binary check tag text zero ignore-missing quiet status strict warn help version"),
    "mkdir": _longs("mode parents verbose context help version"),
    "rm": _longs("force interactive one-file-system no-preserve-root preserve-root recursive dir verbose help version"),
    "rmdir": _longs("ignore-fail-on-non-empty parents verbose help version"),
    "tee": _longs("append ignore-interrupts output-error help version"),
}
for _alias, _base in (("egrep", "grep"), ("fgrep", "grep"), ("gunzip", "gzip"), ("sha256sum", "md5sum"), ("sha1sum", "md5sum"),
                      ("cksum", "md5sum")):
    LONGS[_alias] = LONGS[_base]


#: every long option the guard names anywhere (the handlers' write / path / refusal / value options): abbreviations of tools
#: without a LONGS entry are expanded against this set (`_canon_long`; conservative)
LONG_CANON = frozenset(set(LONG_VAL_COMMON) | {
    "--compress-program", "--files0-from", "--output", "--temporary-directory", "--random-source", "--in-place", "--file",
    "--follow-symlinks", "--expression", "--line-length", "--dereference-recursive", "--exclude-from", "--regexp", "--pre",
    "--pre-glob", "--follow", "--search-zip", "--hostname-bin", "--ignore-file", "--files", "--type-list", "--target-directory",
    "--suffix", "--no-preserve", "--sparse", "--symbolic-link", "--link", "--no-target-directory", "--parents", "--no-preserve-root",
    "--date", "--reference", "--time", "--mode", "--context", "--magic-file", "--files-from", "--stdout", "--to-stdout", "--list",
    "--test", "--help", "--version", "--check", "--echo", "--library-path", "--from-file", "--to-file", "--source", "--field-separator",
    "--assign", "--characters-as-bytes", "--traditional", "--posix", "--re-interval", "--sandbox", "--use-lc-numeric",
    "--non-decimal-data", "--bignum", "--line-format", "--old-line-format", "--new-line-format", "--unchanged-line-format", "--palette",
    "--tabsize", "--horizon-lines", "--show-function-line", "--ignore-matching-lines", "--starting-file", "--charset", "--filelimit",
    "--timefmt", "--context-separator", "--field-context-separator", "--field-match-separator", "--dfa-size-limit",
    "--regex-size-limit", "--engine", "--hyperlink-format", "--generate", "--colors", "--type-clear", "--arg", "--argjson", "--args",
    "--jsonargs", "--slurpfile", "--rawfile", "--indent", "--adjustment", "--signal", "--kill-after"})


def _check_command(words: list[str], ctx: Ctx, depth: int = 0) -> bool:
    """Checks one simple command (after assignments / redirections); returns True if it runs in the sandbox."""
    w0 = words[0]
    if any(x in w0 for x in ("__SUBST", "__PSUBST", "__BODY__", "$", "`", SENT)):
        raise Refuse("host", "a computed command name")
    name = _cmd_name(w0)
    if name == "sbx":
        if "/" in w0 or "\\" in w0:
            raise Refuse("sbx", f"path spelling of sbx: {w0[:80]}")
        why = _sbx_integrity(ctx.cur)
        if why:
            raise Refuse("sbxcheck", why)
        return True
    if "/" in w0 or "\\" in w0:
        raise Refuse("host", "running a file on the host")
    if name not in HOST_ALLOWED:
        raise Refuse("host", f"host command {name!r}")
    args = words[1:]
    if name in WRAPPERS:
        return _check_wrapper(name, args, ctx, depth)
    # listing the whole environment / every variable (review F round 2, N-M1: the host shell must not print secrets)
    if name == "printenv" and not [a for a in args if not a.startswith("-")]:
        raise Refuse("construct", "printing the whole environment")
    if name == "set" and not args:
        raise Refuse("construct", "listing every shell variable")
    if name in ("export", "local", "declare") and not [a for a in args if not a.startswith(("-", "+"))]:
        raise Refuse("construct", "listing variables")
    if name in TEXT_ONLY:
        return False
    if name == "printf":
        opts, _ = _opts(args, "v")
        for v in _vals(opts, "-v"):
            _assign_ok(v)
        return False
    if name in ("export", "local", "declare"):
        for a in args:
            if a.startswith(("-", "+")):
                if set(a[1:]) & set("ni"):
                    raise Refuse("construct", "name references / integer attributes")
                continue
            _assign_ok(a)
        return False
    if name == "read":
        opts, pos = _opts(args, "adinNptu")
        for v in _vals(opts, "-a") + pos:
            _assign_ok(v)
        return False
    if name == "kill":
        _check_kill(args, ctx)
        return False
    if name in ("cd", "pushd", "popd"):
        _check_cd(name, args, ctx)
        return False
    if name in ("test", "[", "[[", "]]", "]"):
        _check_test(args, ctx)
        return False
    if name == "date":
        opts, _ = _opts(args, "dfrI", ("--date", "--file", "--reference"), known=LONGS["date"])
        for v in _vals(opts, "-f", "-r", "--file", "--reference"):
            _check_path(v, ctx)
        return False
    HANDLERS.get(name, _h_generic)(name, args, ctx)
    return False


def _assign_ok(word: str) -> None:
    m = re.match(r"^([A-Za-z_]\w*)", _plain(word))
    if m and ENV_FORBIDDEN.match(m.group(1)):
        raise Refuse("construct", f"assigning {m.group(1)}")


def _check_wrapper(name: str, args: list[str], ctx: Ctx, depth: int) -> bool:
    rest = list(args)
    if name == "env":
        while rest and (rest[0].startswith("-") or ASSIGN.match(rest[0])):
            a = rest.pop(0)
            if a.startswith("-"):
                raise Refuse("construct", f"env option {a}")
            _assign_ok(a)
        if not rest:
            raise Refuse("construct", "printing the whole environment")
    elif name == "timeout":
        while rest and rest[0].startswith("-"):
            opt = rest.pop(0)
            if opt in ("-s", "-k", "--signal", "--kill-after") and rest:
                rest.pop(0)
        if rest:
            rest.pop(0)                               # the duration
    elif name == "nice":
        while rest and rest[0].startswith("-"):
            opt = rest.pop(0)
            if opt in ("-n", "--adjustment") and rest:
                rest.pop(0)
    elif name == "stdbuf":
        while rest and rest[0].startswith("-"):
            opt = rest.pop(0)
            if opt in ("-i", "-o", "-e") and rest:
                rest.pop(0)
    elif name == "command":
        if rest and rest[0] in ("-v", "-V"):
            return False
        while rest and rest[0].startswith("-"):
            if "p" in rest.pop(0):
                raise Refuse("host", "command -p")
    elif name == "time":
        while rest and rest[0].startswith("-"):
            rest.pop(0)
    if not rest:
        return False
    if depth >= 4:
        raise Refuse("construct", "wrappers nested too deeply")
    return _check_command(rest, ctx, depth + 1)


def _check_kill(args: list[str], ctx: Ctx) -> None:
    rest, seen_sig = list(args), False
    while rest and rest[0].startswith("-") and rest[0] != "--" and not seen_sig:
        a = rest.pop(0)
        if a in ("-l", "-L"):
            return
        if a in ("-s", "-n") and rest:
            rest.pop(0)
        seen_sig = True                                   # only the first dash word is a signal specification
    if rest and rest[0] == "--":
        rest.pop(0)
    # ONLY the agent's own background jobs of this command: a job spec (%n), $! or a variable assigned from $! in the same command.
    # An explicit process id is refused (review F round 3c, NF3c-1): with the shared MSYS process table it could name another
    # agent's sandbox wrapper, whose container the machine slot's orphan rule would then stop. Sandbox containers: sbx --stop.
    for a in rest:
        if re.fullmatch(r"%\d*", a) or a == "$!":
            continue
        vals = None
        m = re.fullmatch(r"\$\{?([A-Za-z_]\w*)\}?", a)
        if m and ctx.env.get(m.group(1)):
            vals = ctx.env[m.group(1)]
        if not vals or not all(v == "$!" for v in vals):
            raise Refuse("construct", f"kill target {_plain(a)[:40]!r} (only your own background jobs of this command: %n or $!; "
                                      "stop a sandbox container with sbx --stop)")


def _check_cd(name: str, args: list[str], ctx: Ctx) -> None:
    if name == "popd":
        ctx.cur = ctx.stack.pop() if ctx.stack else ctx.cwd0
        ctx.cwds.add(ctx.cur)
        return
    pos = [a for a in args if not a.startswith("-") or a == "-"]
    if len(pos) != 1 or pos[0] == "-" or pos[0].startswith("~"):
        raise Refuse("outside", "changing directory to home / the previous directory / nowhere")
    vals = ctx.values(pos[0])
    if vals is None or len(vals) != 1:
        raise Refuse("construct", "non-literal cd target")
    target = vals[0]
    p = _resolve(target, ctx.cur)
    if not _inside(p, allow_own_store=False):
        raise Refuse("outside", f"changing directory outside the room: {target[:120]}")
    ctx.path_text.append(shlex.quote(target))
    if name == "pushd":
        ctx.stack.append(ctx.cur)
    ctx.cur = p
    ctx.cwds.add(p)


UNARY_FILE_OPS = {"-e", "-f", "-d", "-r", "-w", "-x", "-s", "-L", "-h", "-b", "-c", "-p", "-S", "-O", "-G", "-N", "-k", "-u", "-g"}
BINARY_FILE_OPS = {"-nt", "-ot", "-ef"}


def _check_test(args: list[str], ctx: Ctx) -> None:
    for i, a in enumerate(args):
        if a in UNARY_FILE_OPS and i + 1 < len(args):
            _check_path(args[i + 1], ctx)
        elif a in BINARY_FILE_OPS and 0 < i < len(args) - 1:
            _check_path(args[i - 1], ctx)
            _check_path(args[i + 1], ctx)


def _file_cmd(name: str, args: list[str], ctx: Ctx, short_val: str = "", path_opts: tuple = (), refuse: tuple = ()) -> tuple:
    """Positionals are files to read; options in path_opts take a file to read; options in refuse are refused."""
    opts, pos = _opts(args, short_val, LONG_VAL_COMMON, known=LONGS.get(name))
    for o, _ in opts:
        if o in refuse:
            raise Refuse("readonly", f"{name} option {o}")
    for v in _vals(opts, *path_opts):
        _check_path(v, ctx)
    for a in pos:
        _check_path(a, ctx)
    return opts, pos


FILE_SHORT_VAL = {"head": "nc", "tail": "ncs", "cut": "dfbc", "nl": "bdfhilnsvw", "fold": "w", "fmt": "wpg", "column": "scoNW",
                  "paste": "d", "join": "t12joeav", "tac": "s", "cmp": "in", "stat": "c", "df": "Btx", "ls": "IwT", "comm": "",
                  "rev": "", "cat": "", "zcat": "", "wc": "", "md5sum": "", "sha256sum": "", "sha1sum": "", "cksum": ""}


def _h_generic(name, args, ctx):
    refuse = {"wc": ("--files0-from",), "md5sum": ("-c", "--check"), "sha256sum": ("-c", "--check"), "sha1sum": ("-c", "--check"),
              "cksum": ("-c", "--check")}.get(name, ())
    _file_cmd(name, args, ctx, FILE_SHORT_VAL.get(name, ""), (), refuse)


def _h_diff(name, args, ctx):
    opts, pos = _opts(args, "UCxXIFWSL", known=LONGS["diff"], long_val=LONG_VAL_COMMON + ("--line-format", "--old-line-format", "--new-line-format",
                                                          "--unchanged-line-format", "--palette", "--tabsize", "--horizon-lines",
                                                          "--show-function-line", "--ignore-matching-lines", "--starting-file"))
    for v in _vals(opts, "-X", "--exclude-from", "--from-file", "--to-file"):
        _check_path(v, ctx)
    for a in pos:
        _check_path(a, ctx)


def _h_du(name, args, ctx):
    _file_cmd(name, args, ctx, "dBtX", ("-X", "--exclude-from"), ("--files0-from",))


def _h_file(name, args, ctx):
    _file_cmd(name, args, ctx, "mfFPe", ("-m", "--magic-file"), ("-f", "--files-from"))


def _h_tree(name, args, ctx):
    opts, pos = _opts(args, "LPIoHT", LONG_VAL_COMMON + ("--charset", "--filelimit", "--timefmt"))
    if _has(opts, "-R"):
        raise Refuse("readonly", "tree -R")
    for v in _vals(opts, "-o"):
        _check_path(v, ctx, "write")
    for a in pos:
        _check_path(a, ctx)


def _h_realpath(name, args, ctx):
    opts, pos = _opts(args, "", LONG_VAL_COMMON)
    for v in _vals(opts, "--relative-to", "--relative-base"):
        _check_path(v, ctx)
    for a in pos:
        _check_path(a, ctx)


def _h_gzip(name, args, ctx):
    opts, pos = _opts(args, "S", ("--suffix",), known=LONGS["gzip"])
    stdout = _has(opts, "-c", "--stdout", "--to-stdout", "-l", "--list", "-t", "--test", "-h", "--help", "-V", "--version")
    for a in pos:
        _check_path(a, ctx)
        if not stdout:
            _check_path(a, ctx, "write")


def _h_sort(name, args, ctx):
    opts, pos = _opts(args, "ktoST", LONG_VAL_COMMON, known=LONGS["sort"])
    for o, _ in opts:
        if o in ("--compress-program", "--files0-from"):
            raise Refuse("readonly", f"sort option {o}")
    for v in _vals(opts, "-o", "--output"):
        _check_path(v, ctx, "write")
    for v in _vals(opts, "-T", "--temporary-directory"):
        _check_path(v.rstrip("/\\") + "/sort-tmp", ctx, "write")
    for v in _vals(opts, "--random-source"):
        _check_path(v, ctx)
    for a in pos:
        _check_path(a, ctx)


def _h_uniq(name, args, ctx):
    opts, pos = _opts(args, "fsw", LONG_VAL_COMMON, known=LONGS["uniq"])
    if len(pos) > 2:
        raise Refuse("construct", "uniq takes at most two files")
    if pos:
        _check_path(pos[0], ctx)
    if len(pos) == 2:
        _check_path(pos[1], ctx, "write")


def _h_shuf(name, args, ctx):
    opts, pos = _opts(args, "noi", LONG_VAL_COMMON, known=LONGS["shuf"])
    for v in _vals(opts, "-o", "--output"):
        _check_path(v, ctx, "write")
    for v in _vals(opts, "--random-source"):
        _check_path(v, ctx)
    if not _has(opts, "-e", "--echo"):
        for a in pos:
            _check_path(a, ctx)


def _h_tee(name, args, ctx):
    _, pos = _opts(args, known=LONGS["tee"])
    for a in pos:
        _check_path(a, ctx, "write")


def _h_mkdir(name, args, ctx):
    opts, pos = _opts(args, "m", ("--mode", "--context"), known=LONGS["mkdir"])
    for a in pos:
        _check_path(a, ctx, "write")
        if _has(opts, "-p", "--parents"):
            for v in ctx.values(a) or []:
                parts = v.replace("\\", "/").rstrip("/").split("/")
                for k in range(1, len(parts)):
                    anc = "/".join(parts[:k])
                    if anc and not os.path.exists(_resolve(anc, ctx.cur)):
                        _check_path(anc, ctx, "write")


def _h_rmdir(name, args, ctx):
    opts, pos = _opts(args, known=LONGS["rmdir"])
    for a in pos:
        _check_path(a, ctx, "write")
        if _has(opts, "-p", "--parents"):
            for v in ctx.values(a) or []:
                parts = v.replace("\\", "/").rstrip("/").split("/")
                for k in range(1, len(parts)):
                    _check_path("/".join(parts[:k]), ctx, "write")


def _h_rm(name, args, ctx):
    opts, pos = _opts(args, known=LONGS["rm"])
    if _has(opts, "--no-preserve-root"):
        raise Refuse("readonly", "rm --no-preserve-root")
    for a in pos:
        _check_path(a, ctx, "write")


def _h_touch(name, args, ctx):
    opts, pos = _opts(args, "drt", ("--date", "--reference", "--time"), known=LONGS["touch"])
    for v in _vals(opts, "-r", "--reference"):
        _check_path(v, ctx)
    for a in pos:
        _check_path(a, ctx, "write")


CHMOD_MODE = re.compile(r"[0-7]{1,4}|[ugoa]*([-+=][rwxXstugo]*)+(,[ugoa]*([-+=][rwxXstugo]*)+)*")


def _h_chmod(name, args, ctx):
    mode, ref, targets = None, [], []
    for a in args:
        if a.startswith("--"):
            a = _canon_long(a, LONGS["chmod"])
            if a.startswith("--reference="):
                ref.append(a.split("=", 1)[1])
            continue
        if re.fullmatch(r"-[cfvR]+", a):
            continue
        if mode is None and not ref and CHMOD_MODE.fullmatch(a):
            mode = a
            continue
        targets.append(a)
    for v in ref:
        _check_path(v, ctx)
    for a in targets:
        _check_path(a, ctx, "write")


def _h_cp_mv(name, args, ctx):
    opts, pos = _opts(args, "St", ("--target-directory", "--suffix", "--no-preserve", "--sparse"), known=LONGS[name])
    for o, _ in opts:
        if o in ("-s", "-l", "--symbolic-link", "--link"):
            raise Refuse("construct", f"{name} may not create links")
    tdir = _vals(opts, "-t", "--target-directory")
    if tdir:
        srcs, dest = pos, tdir[-1]
    else:
        if len(pos) < 2:
            raise Refuse("construct", f"{name} needs a source and a destination")
        srcs, dest = pos[:-1], pos[-1]
    for s in srcs:
        _check_path(s, ctx)
        if name == "mv":
            _check_path(s, ctx, "write")
    if _has(opts, "-T", "--no-target-directory"):
        _check_path(dest, ctx, "write")
    else:
        _check_write_into(dest, srcs, ctx, parents=_has(opts, "--parents"))


def _h_grep(name, args, ctx):
    opts, pos = _opts(args, "efmABCdD", LONG_VAL_COMMON, known=LONGS[name])
    if _has(opts, "-R", "--dereference-recursive"):
        raise Refuse("readonly", "grep -R follows links")
    for v in _vals(opts, "-f", "--file", "--exclude-from"):
        _check_path(v, ctx)
    if not _vals(opts, "-e", "--regexp") and not _vals(opts, "-f", "--file") and pos:
        pos = pos[1:]                                    # the pattern
    for a in pos:
        _check_path(a, ctx)


def _h_rg(name, args, ctx):
    opts, pos = _opts(args, "efgtTmABCMjEdr", LONG_VAL_COMMON + ("--context-separator", "--field-context-separator",
                                                                "--field-match-separator", "--dfa-size-limit", "--regex-size-limit",
                                                                "--engine", "--hyperlink-format", "--generate", "--colors",
                                                                "--type-clear", "--pre", "--pre-glob", "--hostname-bin"))
    for o, _ in opts:
        if o in ("--pre", "--pre-glob", "-L", "--follow", "-z", "--search-zip", "--hostname-bin"):
            raise Refuse("readonly", f"rg option {o}")
    for v in _vals(opts, "-f", "--file", "--ignore-file"):
        _check_path(v, ctx)
    if not (_has(opts, "--files", "--type-list") or _vals(opts, "-e", "--regexp") or _vals(opts, "-f", "--file")) and pos:
        pos = pos[1:]
    for a in pos:
        _check_path(a, ctx)


FIND_REFUSE = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls", "-L", "-follow",
               "-files0-from"}
FIND_PATTERN = {"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-lname", "-ilname"}
FIND_PATH = {"-newer", "-anewer", "-cnewer", "-samefile"}
FIND_VALUE = {"-maxdepth", "-mindepth", "-type", "-xtype", "-size", "-mtime", "-mmin", "-atime", "-amin", "-ctime", "-cmin", "-user",
              "-group", "-uid", "-gid", "-perm", "-printf", "-regextype", "-used", "-links", "-inum", "-fstype", "-context"}


def _h_find(name, args, ctx):
    i = 0
    while i < len(args) and args[i] in ("-H", "-P", "-L", "-D", "-O"):
        if args[i] == "-L":
            raise Refuse("readonly", "find -L follows links")
        i += 2 if args[i] in ("-D", "-O") else 1
    while i < len(args) and not args[i].startswith(("-", "(", "!", ",", ")")):
        _check_path(args[i], ctx)
        i += 1
    while i < len(args):
        a = args[i]
        if a in FIND_REFUSE:
            raise Refuse("readonly", f"find {a}")
        if a in FIND_PATTERN or a in FIND_VALUE:
            i += 2
            continue
        if a in FIND_PATH or re.fullmatch(r"-newer[abcmt][abcmt]", a):
            if i + 1 < len(args):
                _check_path(args[i + 1], ctx)
            i += 2
            continue
        i += 1


def _h_sed(name, args, ctx):
    opts, pos = _opts(args, "efl", ("--expression", "--file", "--line-length"), short_opt_attached="i", known=LONGS["sed"])
    for o, _ in opts:
        if o in ("-f", "--file", "--follow-symlinks"):
            raise Refuse("readonly", f"sed option {o}")
    scripts = _vals(opts, "-e", "--expression")
    if not scripts and pos:
        scripts, pos = [pos[0]], pos[1:]
    for sc in scripts:
        for v in _literal_script(sc, ctx, "sed script"):
            why = _sed_bad(v)
            if why:
                raise Refuse("readonly", why)
    inplace = _has(opts, "-i", "--in-place")
    for a in pos:
        _check_path(a, ctx)
        if inplace:
            _check_path(a, ctx, "write")


AWK_OK = {"-F", "-v", "-e", "--source", "--field-separator", "--assign", "-b", "--characters-as-bytes", "-c", "--traditional", "-P",
          "--posix", "-r", "--re-interval", "-S", "--sandbox", "-N", "--use-lc-numeric", "-n", "--non-decimal-data", "-M", "--bignum"}


def _h_awk(name, args, ctx):
    opts, pos = _opts(args, "Fve", ("--field-separator", "--assign", "--source"))
    for o, _ in opts:
        if o not in AWK_OK:
            raise Refuse("readonly", f"awk option {o}")
    progs = _vals(opts, "-e", "--source")
    if not progs and pos:
        progs, pos = [pos[0]], pos[1:]
    for p in progs:
        for v in _literal_script(p, ctx, "awk program"):
            why = _awk_bad(v)
            if why:
                raise Refuse("readonly", why)
            ctx.path_text.append(v)                      # awk programs stay subject to the path checks (they could name files)
    for a in pos:
        if ASSIGN.match(a):
            continue
        _check_path(a, ctx)


def _h_jq(name, args, ctx):
    i, files, filt = 0, [], None
    while i < len(args):
        a = args[i]
        if a in ("-L", "--library-path") or a.startswith("-L"):
            raise Refuse("readonly", "jq -L")
        if a in ("--arg", "--argjson"):
            i += 3
            continue
        if a in ("--slurpfile", "--rawfile"):
            if i + 2 < len(args):
                _check_path(args[i + 2], ctx)
            i += 3
            continue
        if a in ("-f", "--from-file"):
            if i + 1 < len(args):
                _check_path(args[i + 1], ctx)
                filt = ""
            i += 2
            continue
        if a == "--indent":
            i += 2
            continue
        if a in ("--args", "--jsonargs"):
            break
        if a.startswith("-") and a != "-":
            i += 1
            continue
        if filt is None:
            filt = a
        else:
            files.append(a)
        i += 1
    for v in (_literal_script(filt, ctx, "jq filter") if filt else []):
        if re.search(r"\b(include|import)\s*\"", v):
            raise Refuse("readonly", "jq include / import")
        ctx.path_text.append(v)
    for f in files:
        _check_path(f, ctx)


HANDLERS = {
    "diff": _h_diff, "du": _h_du, "file": _h_file, "tree": _h_tree, "realpath": _h_realpath, "readlink": _h_realpath,
    "gzip": _h_gzip, "gunzip": _h_gzip, "sort": _h_sort, "uniq": _h_uniq, "shuf": _h_shuf, "tee": _h_tee, "mkdir": _h_mkdir,
    "rmdir": _h_rmdir, "rm": _h_rm, "touch": _h_touch, "chmod": _h_chmod, "cp": _h_cp_mv, "mv": _h_cp_mv, "grep": _h_grep,
    "egrep": _h_grep, "fgrep": _h_grep, "rg": _h_rg, "find": _h_find, "sed": _h_sed, "awk": _h_awk, "gawk": _h_awk, "jq": _h_jq,
}


# ------------------------------------------------------------------------------------------------ simple commands / variables
def _literal_value(v: str, ctx: Ctx) -> list[str] | None:
    if _plain(v) == "$!" and SENT not in v:
        return ["$!"]
    m = re.fullmatch(r"__SUBST(\d+)__", v)
    if m:
        return ["0"] if ctx.sub_numeric.get(int(m.group(1))) else None
    return ctx.values(v)


def _collect_vars(segs: list[tuple[str, str]], ctx: Ctx) -> None:
    """Values of the variables assigned in this command (literal assignments, for-loop words, `seq` substitutions); variables with a
    non-literal assignment (read, printf -v, substitutions, ...) hold runtime DATA (None)."""
    env: dict[str, list[str] | None] = {}
    ctx.env = env

    def add(name, vals):
        if name in env and env[name] is None:
            return
        env[name] = None if vals is None else (env.get(name) or []) + vals
    for kind, seg in segs:
        if kind != "cmd":
            continue
        words, _ = _split_words(seg)
        i = 0
        while i < len(words) and (ASSIGN.match(words[i]) or words[i] in KEYWORDS):
            m = ASSIGN.match(words[i])
            if m:
                if m.group(2) and not re.fullmatch(r"\[\d*\]", m.group(2)):
                    raise Refuse("construct", "array subscript in an assignment")
                add(m.group(1), _literal_value(m.group(4), ctx))
            i += 1
        rest = words[i:]
        if not rest:
            continue
        c = _cmd_name(rest[0])
        if c in ("for", "select") and len(rest) >= 2:
            nm = rest[1]
            if nm.startswith("(("):
                continue
            words_in = rest[3:] if len(rest) > 2 and rest[2] == "in" else None
            if words_in is None or c == "select":
                add(nm, None)
                continue
            vals: list[str] | None = []
            for w in words_in:
                v = _literal_value(w, ctx)
                if v is None:
                    vals = None
                    break
                vals += v
            add(nm, vals)
        elif c in ("export", "local", "declare"):
            for a in rest[1:]:
                m = ASSIGN.match(a)
                if m:
                    add(m.group(1), _literal_value(m.group(4), ctx))
        elif c == "read":
            opts, pos = _opts(rest[1:], "adinNptu")
            for nm in pos + _vals(opts, "-a"):
                add(nm, None)
        elif c == "printf":
            opts, _ = _opts(rest[1:], "v")
            for nm in _vals(opts, "-v"):
                add(nm, None)


ARITH = re.compile(r"\$\(\((.*?)\)\)|\$\[(.*?)\]|\bfor\s*\(\((.*?)\)\)|\$\{#?\w+\[[^\]]*\][^}]*\}|\$\{\w+:(?![-=?+])[^}]*\}", re.DOTALL)


def _check_arith(text: str, ctx: Ctx) -> None:
    """Runtime data must not reach an arithmetic context (bash evaluates array subscripts in it, command substitutions included)."""
    data = {k for k, v in ctx.env.items() if v is None}
    if re.search(r"(?<![$\w])\(\(", re.sub(r"\bfor\s*\(\(", "", text)):
        raise Refuse("construct", "arithmetic command")
    for m in ARITH.finditer(text):
        body = m.group(0)
        if "__SUBST" in body and not all(ctx.sub_numeric.get(int(k)) for k in re.findall(r"__SUBST(\d+)__", body)):
            raise Refuse("construct", "command substitution in an arithmetic context")
        if set(re.findall(r"[A-Za-z_]\w*", body)) & data:
            raise Refuse("construct", "runtime data in an arithmetic context")
    for m in re.finditer(r"\[\[(.*?)\]\]", text, re.DOTALL):
        body = m.group(1)
        if re.search(r"(^|\s)-(eq|ne|lt|le|gt|ge|v)(\s|$)", body):
            if "__SUBST" in body or set(re.findall(r"[A-Za-z_]\w*", body)) & data:
                raise Refuse("construct", "runtime data in an arithmetic comparison")


def _check_simple(seg: str, ctx: Ctx) -> bool:
    """Checks one simple command; returns True if it runs in the sandbox."""
    words, redirs = _split_words(seg)
    while words and (ASSIGN.match(words[0]) or words[0] in KEYWORDS):
        m = ASSIGN.match(words[0])
        if m:
            _assign_ok(m.group(1))
        words = words[1:]
    for op, target in redirs:
        if op == "<<<":
            continue                                     # a here-string is text
        if op in (">&", "<&") and re.fullmatch(r"\d*-?", target or ""):
            continue                                     # a file-descriptor duplication
        if not target or target in ("/dev/null", "nul", "-"):
            continue
        _check_path(target, ctx, "write" if op in WRITE_REDIR else "read")
    if not words:
        return False
    if words[0] in ("for", "select", "case", "in", "esac", ";;"):
        return False                                     # the rest of a for / case header is data (collected separately)
    is_sbx = _check_command(words, ctx)
    if not is_sbx:
        exempt = _exempt_words(words)
        ctx.path_text.append(" ".join(shlex.quote(_plain(w)) for i, w in enumerate(words) if i not in exempt))
        for i, t in enumerate(words[1:], 1):
            if i in exempt or t.startswith("-"):
                continue
            for v in ctx.values(t) or []:
                if GLOB_CHARS.search(v) or re.match(r"^[a-z]+://", v):
                    continue
                if ABS_TOKEN.match(v) or "/" in v or "\\" in v or os.path.lexists(os.path.join(ctx.cur, v)):
                    for c in ctx.cwds:
                        p = _resolve(v, c)
                        if not _inside(p) and not _allowed_outside(v, p):
                            raise Refuse("outside", f"path leaves the room: {v[:120]}")
    return is_sbx


def _exempt_words(words: list[str]) -> set[int]:
    """Indices of words that are patterns / scripts / text (not paths): excluded from the path-construct checks."""
    name = _cmd_name(words[0])
    args = words[1:]
    ex: set[int] = set()
    if name in TEXT_ONLY | {"printf", "test", "[", "[[", "]]", "]", "kill", "date", "export", "local", "declare", "read"}:
        return set(range(1, len(words)))
    if name in ("grep", "egrep", "fgrep", "rg"):
        has_e = False
        for i, a in enumerate(args, 1):
            if a in ("-e", "--regexp", "-g", "--glob", "--iglob", "--include", "--exclude", "--exclude-dir") and i < len(args):
                ex.add(i + 1)
                has_e = has_e or a in ("-e", "--regexp")
            elif a.startswith(("--regexp=", "--glob=", "--iglob=", "--include=", "--exclude=", "--exclude-dir=")):
                ex.add(i)
        if not has_e:
            skip = False
            for i, a in enumerate(args, 1):
                if skip:
                    skip = False
                    continue
                if a in ("-f", "--file", "-m", "-A", "-B", "-C", "-t", "-T", "-M", "-j", "-E", "-d", "-r", "--max-count", "--context",
                         "--type", "--max-depth", "-g", "--glob", "--iglob"):
                    skip = True
                    continue
                if a.startswith("-") and a != "-":
                    continue
                ex.add(i)
                break
    elif name == "sed":
        first = True
        for i, a in enumerate(args, 1):
            if a in ("-e", "--expression") and i < len(args):
                ex.add(i + 1)
                first = False
            elif a.startswith("--expression="):
                ex.add(i)
                first = False
        if first:
            for i, a in enumerate(args, 1):
                if not a.startswith("-"):
                    ex.add(i)
                    break
    elif name == "find":
        for i, a in enumerate(args, 1):
            if a in FIND_PATTERN and i < len(args):
                ex.add(i + 1)
    elif name in ("sort", "cut", "join", "paste", "column", "tac", "nl"):
        for i, a in enumerate(args, 1):
            if a in ("-t", "-k", "-d", "-s", "-f", "--field-separator", "--key", "--delimiter", "--separator") and i < len(args):
                ex.add(i + 1)
    elif name in ("ls", "tree", "du", "diff"):
        for i, a in enumerate(args, 1):
            if a in ("-I", "-P", "--ignore", "--hide", "-x", "--exclude") and i < len(args):
                ex.add(i + 1)
    return ex


# ------------------------------------------------------------------------------------------------ whole command
SECRET_VARS = re.compile(r"(?i)p4_sim_token")


def _check_shell(cmd: str, cwd: str, depth: int = 0) -> None:
    if depth > 4:
        raise Refuse("construct", "nesting too deep")
    s0 = _normalise_command(cmd)
    why = _forbidden_text(s0)
    if why:
        raise Refuse("text", why)
    if SECRET_VARS.search(s0):
        raise Refuse("text", "the simulation token is never read on the host (N-M1)")
    s, bodies, expanded = _split_bodies(s0)
    for kind, body in bodies:
        if kind == "sh":
            _check_shell(body, cwd, depth + 1)
    exp_subs = []
    for text in expanded:
        exp_subs += _extract_substitutions(text, dq_context=True)[1]
    for sub in exp_subs:
        _check_shell(sub, cwd, depth + 1)
    s_nosub, subs = _extract_substitutions(s)
    numeric = {}
    for i, sub in enumerate(subs):
        _check_shell(sub, cwd, depth + 1)
        numeric[i] = bool(SEQ_SUBST.match(sub))
    ctx = Ctx(cwd, numeric)
    segs = _segments(s_nosub)
    _collect_vars(segs, ctx)
    _check_arith(s_nosub, ctx)
    for text in expanded:
        _check_arith(text, ctx)
    for kind, seg in segs:
        if kind == "open":
            ctx.stack.append(ctx.cur)
        elif kind == "close":
            ctx.cur = ctx.stack.pop() if ctx.stack else ctx.cwd0
        elif kind == "cmd":
            _check_simple(seg, ctx)
    ht = "\n".join(ctx.path_text)
    for pat, msg in SHELL_CONSTRUCTS_PATH:
        if re.search(pat, ht, flags=re.IGNORECASE | re.MULTILINE):
            raise Refuse("construct", msg)
    for pat, msg in SHELL_CONSTRUCTS_ALL:
        if re.search(pat, s_nosub, flags=re.IGNORECASE | re.MULTILINE):
            raise Refuse("construct", msg)
    cands = [m.group(1) for m in QUOTED_ABS.finditer(ht)]
    cands += PATH_TOKEN.findall(QUOTED_ABS.sub(" ", ht))
    for raw in cands:
        raw = raw.strip().rstrip(",")
        if raw in ("/dev/null",) or raw.lower() == "nul":
            continue
        probe = raw
        if GLOB_CHARS.search(probe):
            probe = GLOB_CHARS.split(probe, maxsplit=1)[0]
            probe = probe.rsplit("/", 1)[0] if "/" in probe else probe.rsplit("\\", 1)[0]
        res = _resolve(probe or raw, cwd)
        if not _allowed_outside(raw, res) and not _inside(res):
            raise Refuse("outside", f"path outside the room: {raw[:120]}")


# ------------------------------------------------------------------------------------------------ decision
def decide_full(ev: dict) -> tuple[bool, str, str]:
    """(allowed, refusal class, detailed reason)."""
    if _N is None:
        return False, "error", "names config unavailable"
    tool = ev.get("tool_name", "")
    ti = ev.get("tool_input") or {}
    cwd = ev.get("cwd") or CLEAN
    blob = json.dumps(ti, ensure_ascii=False)
    try:
        if tool.startswith("mcp__"):
            raise Refuse("tool", "MCP tool")
        if tool in BLOCKED_TOOLS:
            raise Refuse("tool", f"{tool} is disabled")
        if tool in ("Task", "Agent") and str(ti.get("subagent_type") or "general-purpose") not in ALLOWED_SUBAGENTS:
            raise Refuse("tool", f"subagent type {ti.get('subagent_type')!r}")
        if tool in ("WebSearch", "WebFetch"):
            if not ALLOW_WEB:
                raise Refuse("tool", "web disabled")
            for rx in WEB_BLOCK:
                if rx.search(blob):
                    raise Refuse("web", f"web block {rx.pattern!r}")
            return True, "", "web ok"
        if tool == "Bash":
            rc = _resolve(cwd, CLEAN)
            if not _inside(rc, allow_own_store=False):
                raise Refuse("outside", "the shell's working directory is outside the room")
            _check_shell(str(ti.get("command", "")), rc)
            return True, "", "command ok"
        writing = tool in ("Write", "Edit", "MultiEdit", "NotebookEdit")
        why = _forbidden_text(json.dumps({k: v for k, v in ti.items() if k in ("file_path", "path", "notebook_path")}) if writing
                              else blob)
        if why:
            raise Refuse("text", why)
        for key in ("file_path", "path", "notebook_path"):
            if key in ti and ti[key]:
                raw = str(ti[key])
                for pat, msg in SHELL_CONSTRUCTS_PATH[:3]:
                    if re.search(pat, raw):
                        raise Refuse("construct", f"{key}: {msg}")
                p = _resolve(raw, cwd)
                if not _inside(p, allow_own_store=not writing):
                    raise Refuse("outside", f"{key} outside the room: {raw[:160]}")
                if writing and not _writable(p):
                    raise Refuse("readonly", f"{key} not in a work area: {raw[:160]}")
                if tool in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "NotebookRead") and _planted_near(p):
                    raise Refuse("planted", f"control file above {raw[:160]}")
                if tool in ("Glob", "Grep") and os.path.isdir(p) and _links_under(p):
                    raise Refuse("outside", "the search root contains a link or junction")
        if tool in ("Glob", "Grep"):
            pat = str(ti.get("pattern", "")) if tool == "Glob" else ""
            if pat and (re.search(r"(?<![.\w])\.\.(?![.\w])", pat) or re.match(r"^\s*([a-zA-Z]:|/|\\\\|~)", pat)):
                p = _resolve(GLOB_CHARS.split(pat, maxsplit=1)[0] or CLEAN, cwd)
                if not _inside(p, allow_own_store=False) or ".." in pat:
                    raise Refuse("outside", "glob pattern outside the room")
            if not ti.get("path") and _links_under(_resolve(cwd, CLEAN)):
                raise Refuse("outside", "the search root contains a link or junction")
        return True, "", "ok"
    except Refuse as r:
        return False, r.cls, r.detail


def decide(ev: dict) -> tuple[bool, str]:
    """(allowed, '<class>: <detailed reason>') -- the detailed reason never reaches the agent."""
    ok, cls, why = decide_full(ev)
    return ok, (why if ok else f"{cls}: {why}")


def main() -> int:
    eid = secrets.token_hex(4)
    try:
        ev = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(f"BLOCKED by the room guard [{CLASSES['error'][0]}-{eid}]: {CLASSES['error'][1]}.", file=sys.stderr)
        _log("deny", "", "error", f"unreadable hook input ({type(e).__name__})", "", eid)
        return 2
    try:
        ok, cls, reason = decide_full(ev)
    except Exception as e:  # noqa: BLE001
        ok, cls, reason = False, "error", f"guard error ({type(e).__name__}: {e})"
    _log("allow" if ok else "deny", ev.get("tool_name", ""), cls, reason, json.dumps(ev.get("tool_input") or {}, ensure_ascii=False),
         eid)
    if ok:
        return 0
    code, hint = CLASSES.get(cls, CLASSES["error"])
    print(f"BLOCKED by the room guard [{code}-{eid}]: {hint}.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
