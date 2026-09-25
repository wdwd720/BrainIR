# Review F — resolution (pre-lock, 2026-09-24/25)

Review F (`F_leakage.md`) found no realised leak: 0 answer tokens in the room or in any agent's traffic. It found 2 blockers and 3
majors about the CAPABILITY of a clean-room agent to escape its room. The five method agents and review G were already running when
the report arrived, so both code guards were replaced in place and tested before the next tool call could rely on them.

## F-B1 (Bash / PowerShell route) — FIXED (guard_hook v2)

`scripts/p3agent/guard_hook.py` now uses resolve-and-contain instead of a substring blocklist.

**Paths.** Every path-like token is resolved with realpath and must lie inside the room. The only exceptions are the uv-managed
interpreters, the uv executable, Git's install directory and the null device. Resolution handles 8.3 names, links, '.' and '..'.
Quoted paths and paths inside inline code are included.

**Refused constructs.** Shell commands may not build paths the guard cannot see. The guard refuses:
- `..`, `/./` and 8.3 names;
- `$PWD` / `$HOME` / environment-variable paths;
- variables used as path prefixes, unless assigned in the same command from a literal or a script argument;
- adjacent variable concatenation;
- location-computing substitutions;
- PowerShell path cmdlets and parent / environment path APIs;
- bare drive roots (`/c`), UNC and device paths;
- link or drive-mapping creation;
- obfuscation (base64, hex / octal escapes, Invoke-Expression, eval);
- interpreters other than Python;
- network tools, and `https?://` in commands;
- package installs;
- writes to the room's CLAUDE.md or `.claude`;
- anything that disables the Python audit hook (`-I` / `-S` / `-E`, PYTHONPATH, P3_CLEAN_ROOT, `unset`, `env -i`,
  sitecustomize).

Empty-quote splicing and caret escapes are removed before matching.

**Script files.** Scripts a command runs (`.sh`, `.ps1`, `.bat`, ...) are checked like the command. So is script content written
with Write / Edit. Heredoc or here-string bodies that a shell executes are checked too.

**Python bodies.** Python code inside commands (heredocs, `-c`) gets the substring checks only. It is checked at run time by pyguard
(below).

**~/.claude.** The whole directory is refused, except the agent's own session store, which is read-only and never a `cd` target.
Other rooms are refused by exact name, never the agent's own room.

**Tests.**
- `phase3/tests/test_guard.py`: 62 cases, including every F-B1 probe as a regression.
- Every tool call the eight agents executed before the fix (streams in `C:\Dev\BrainIR_p3audit`) was replayed through guard v2.
  Only two calls would now be refused, both harmless: the literature agent's `cd` into its own tool-results store, and the benchmark
  author's `/tmp` write, which v1 had already refused. No escape happened under v1.
- The transcript audit now repeats this replay at every milestone (`denied_by_current_guard`).
- The replay of legitimate calls found false positives in v2.0 (dict literals read as drive letters, `$tag/` in a bash script,
  review G's own room name). They were fixed in v2.1 within minutes; the affected agents saw one or two refusals each and continued.

## F-B2 (Python route) — FIXED (pyguard v2)

`scripts/p3agent/pyguard/sitecustomize.py` also uses resolve-and-contain.
- Every file-system audit event is resolved with realpath against the current directory. It is refused under `C:\Dev` or the user
  profile unless it lies in the room, the interpreter's own prefixes or the guard's directory.
- It also:
  - checks `_winapi.CreateFile` file names;
  - refuses resolving native file / process / shell functions through ctypes (CreateFileW, NtCreateFile, _wopen, ShellExecuteW,
    CreateProcessW, ...);
  - refuses all network events;
  - checks child processes: their working directory and path arguments must be permitted; a Python child may not use -I / -S / -E,
    and a child may not have an environment without the guard.

All of review F's probes P0-P12 are now blocked:
- `/./`, relative after `chdir`, stepwise `chdir` into the oracle, 8.3 names;
- `~/.claude/file-history`;
- unguarded `-I` child, child without PYTHONPATH;
- `_winapi` and ctypes native reads.

A normal agent workload runs unchanged: numpy / scipy / torch / sklearn / pandas / pyarrow imports, room data, training, pickling,
ProcessPoolExecutor, tempfile, and a guarded subprocess. The regression test is
`test_guard.py::test_python_guard_v2_resolve_and_contain`.

## F-M1 (answer material in the shared account's ~/.claude) — MITIGATED

Both guards refuse all of `~/.claude` except the agent's own store. The launcher's deny rules for new sessions add file-history,
paste-cache, history.jsonl, todos, shell-snapshots, sessions and the uv cache.

The material itself is not deleted. It is the user's Claude Code history, and deleting it would destroy user data.

## F-M2 (uv cache names the datasets) — FIXED

The uv cache is no longer on the command guard's allowlist. It lies under the user profile, which pyguard protects. Agents never
need to name it: uv reads it natively, and the room's `.venv` holds its own copies.

## F-M3 (heldout / final seeds in cleartext in a committed hidden file) — ACCEPTED, with rationale

The seeds are derived from the committed-by-hash salt (`build_synthetic_suites.tier_seed`) and hash-locked in BENCHMARK_LOCK.json.
They are exactly as exposed as the synthetic truth files and the salt themselves: all three live in the main repository and data
directory, which both guards now protect. Moving them would change a locked file for no gain in protection. The protection that
matters is room containment (F-B1 / F-B2).

## Minor

| finding | resolution |
|---|---|
| F-m1 | the regenerated candidates are by design (goal4 section 5) |
| F-m2 | identical shape signatures across suites: noted for reviews C and G, and as a limitation; developers see aggregates only |
| F-m3 | the audit now also reports calls the current guard would deny |
| F-m4 | kept |

## Residual risk (stated)

The guards are user-space checks on command text and Python audit events. They are not an OS sandbox. OS-level isolation (a
separate account or container) was not used because it cannot run a Claude Code session without sharing the host's OAuth
credentials: refresh-token rotation would break the host session, and there is no API key.

A deliberately obfuscated escape remains conceivable only by combining techniques the guard refuses individually, with a native
program that is not Python. Every executed tool call is logged in full (guard log detail up to 20,000 characters) and re-checked by
the audit at every milestone.
