# Review F — leakage / clean room (Phase 3, pre-lock)

Independent review for goal4 §3–5, §69 (review F). Scope: the method-development clean room `C:\Dev\BrainIR_p3clean`
(read-only for me; five oracle-free agents are working in it), the agent isolation stack (`scripts/p3agent/`), the
orchestrator-side method sandbox (`phase3/src/brainir_state/runguard.py`), the candidate regeneration
(`C:\Dev\BrainIR_p3regen`, `scripts/p3/regenerate_candidates.py`), the frozen benchmark
(`benchmarks/state_discovery_v1/`) and every agent event stream / guard log in `C:\Dev\BrainIR_p3audit`.

**This file is answer-aware and must never enter any clean room.** I quote no cell type, body id, tier-A token or
position of the Phase 1 answer. My probe scripts and their outputs are under `research/phase3/reviews/F_scratch/`
(they read the oracle to know what to scan for; they print counts and match-classes, never the tokens).

## Summary verdict

- **Findings: 2 blockers, 3 major, 4 minor.**
- **No leak has occurred.** No answer identity (published cell types, core/contralateral body ids, tier-A tokens or
  positions) appears in any room text file (70 scanned) or in any of the eight agents' tool outputs (transcript audit:
  `outputs with ANSWER TOKENS = 0` for all agents). The regenerated candidates are oracle-free and reproduce the locked
  Phase 2 method exactly. The benchmark freeze and the method sandbox verify.
- **But the agent-side isolation is not technological, as goal4 §3 requires.** Both code guards (the PreToolUse hook
  `guard_hook.py` and the Python audit hook `pyguard/sitecustomize.py`) are **substring blocklists on raw text**, not
  resolve-and-contain checks. I demonstrated offline that a clean-room agent's `Bash`/`PowerShell` tool can read
  `C:\Dev\BrainIR`'s answer-bearing files (`PHASE2_REPORT.md`, the dng100 oracle, `goal*.md`) and the user's
  `~/.claude` transcript/history stores, through `$PWD`/variable-built parent paths, `/./` insertion, 8.3 short names,
  globs, and native (`ctypes`/`_winapi`) I/O. The permission `deny` rules — the one layer that *is* enforced under
  `--dangerously-skip-permissions` — cover only `Read`/`Edit`/`Write`, not `Bash`/`PowerShell`. These are BLOCKERS
  because the isolation guarantee in `LEAKAGE_POLICY.md` §2 ("denies every tool call that names a path outside the
  room … paths built at run time") is materially false for the shell route.
- **The orchestrator-side method sandbox (`runguard`, review-F question 4) is sound.** It uses the correct
  resolve-realpath-and-contain model with a positive allowlist, denies process/network, and its FIT/EVAL tests pass. A
  method executed by the tournament cannot read the synthetic truth / real-hidden data.
- **Candidate regeneration (question 3) is clean and oracle-free**, and the candidate positions are tier-A positional
  ids that are not mappable to identities without the salt (which is not in the room).

Because no exploitation has happened and the running agents are cooperative method developers, the blockers are about
**capability**, not a realized leak. They must be fixed before a version whose blindness has to survive an adversarial
or prompt-injected agent (the literature agent has web access), and before goal4 §3's "enforce isolation
technologically" can be claimed.

## BLOCKERS

### F-B1 — A clean-room agent's Bash/PowerShell can read the main repo's answer-bearing files; the only gate (the PreToolUse hook) is bypassable and there is no deny-rule backstop for Bash — severity: BLOCKER

**Evidence** (offline runs of `guard_hook.decide()` on crafted inputs; `F_scratch/probe_guard_hook.py`). The following
were returned **ALLOW** by the hook that gates every agent tool call:

- `cat $PWD/../BrainIR/PHASE2*` → ALLOW. Root cause: `_norm` (guard_hook.py:80-89) does not expand `$PWD` but *does*
  collapse `..`, so `$PWD/../BrainIR/PHASE2*` normalises to `<room>\$PWD\..\BrainIR\PHASE2*` → `<room>\BrainIR\PHASE2*`,
  which `_inside` (92-96) judges *inside the room*. At runtime the shell expands `$PWD` to the room and `..` escapes to
  `C:\Dev`, reading `C:\Dev\BrainIR\PHASE2_REPORT.md` (answer-bearing).
- `d=..; cat $d/BrainIR/goal3.md` → ALLOW. Variable indirection: the `..` in `d=..` is not in a slash context, so the
  relative-escape check (145-147) does not fire; `$d/BrainIR/...` matches no `PATH_TOKEN` and no forbidden substring.
  (`goal3.md` carries the Phase-2 oracle label scheme; `goal2.md`, `README.md`, `PHASE1_REPORT.md`, `research/LOG.md`
  are reachable the same way.)
- `cat $PWD/../BrainIR/benchmarks/dng100/orac*/oracle.json` → ALLOW. The forbidden pattern `[\\/]oracle[\\/]` (45) is
  defeated by the glob `orac*`; `oracle.json` (the Phase 1 answer) is then read.
- `find /c -maxdepth 3 -name 'PHASE2*'` and `ls /c` → ALLOW. `PATH_TOKEN` (60-66) requires `/c/…`; a bare `/c` is not
  matched, so drive-root enumeration is allowed.
- `uv run python -c "print(open('C:/Dev/./BrainIR/goal2.md').read())"` → ALLOW at the hook: `_check_bash` strips quoted
  strings before the unquoted path scan (137), so the absolute path inside the inline code is never checked; and
  `C:/Dev/./BrainIR` defeats the literal `dev[\\/]+brainir` substring (37).

The permission `deny` list (launch.py:51-53) contains only `Read(...)`, `Edit(...)`, `Write(...)` entries — it has **no
`Bash`/`PowerShell` entry** — so the shell route has no second enforced layer (deny rules do apply under
`--dangerously-skip-permissions`, which is why the direct `Read` tool on the main repo *is* blocked; Bash is not). For
pure-shell commands (`cat`, `find`, `git`) there is also no Python audit hook. Net: one bypassable layer stands between
an agent and every answer-bearing file whose literal path avoids the five narrow forbidden substrings — and globs defeat
even those.

The running agents did **not** do this (transcript audit: `forbidden_path_inputs = 0`, `outputs_with_answer_tokens = 0`
for all; the guard correctly denied the naive attempts it saw — `/tmp`, `cd ..`, `.claude/projects`, see F-verified).
The finding is that the capability exists.

**Fix**
- Replace the blocklist with a positive **resolve-and-contain** model for Bash/PowerShell: reject the call unless every
  path it could touch resolves (after `$PWD`/env/`~`/8.3/`.`/`..` expansion) inside the room or a tiny explicit
  allowlist. Since a shell command's runtime targets cannot be fully predicted from text, prefer OS-level isolation:
  run each agent under a dedicated OS account (or container / Modal) with no read access to `C:\Dev\BrainIR`, the other
  rooms, or the answer-aware account's `~/.claude`. This is exactly review D's Phase-2 fix (D2), still open.
- Until then, at minimum: block `$PWD`/any `$var`-built or unexpanded-variable path, block bare drive roots (`/c`,
  `C:\`), stop stripping quoted strings before the path scan (scan inside `-c`/`-e`/here-docs), and expand 8.3 and `.`
  components before containment. Add `Bash(...)`/`PowerShell(...)` to a positive-allow permission model rather than a
  deny list.

### F-B2 — The Python audit hook (pyguard) is a substring blocklist and misses `/./`, relative-after-chdir, 8.3 names, native I/O, and the user's `~/.claude` history stores — severity: BLOCKER

**Evidence** (the real `sitecustomize.py` run in a child with `P3_CLEAN_ROOT` set and `PYTHONPATH` pointing at pyguard,
exactly as an agent's `uv run python` runs; `F_scratch/probe_pyguard*.py`). The audit hook loaded (`guard loaded:
True`) and **correctly blocked** the literal control (`open('C:/Dev/BrainIR/README.md')`), but **allowed**:

- `open('C:/Dev/./BrainIR/README.md')` — `/./` defeats the `dev[\\/]+brainir` substring in `_FORBIDDEN`
  (sitecustomize.py:14-17). Read 4323 bytes.
- `os.chdir('C:/Dev'); open('BrainIR/README.md')` and `os.chdir('C:/Dev'); os.chdir('BrainIR'); open('PHASE2~1.MD')` —
  a relative path after `chdir` contains no forbidden substring; the Phase 2 report was read via its 8.3 name.
- stepwise `chdir` into `benchmarks/dng100/oracle` + `open('oracle.json')` — read the Phase 1 oracle (18127 bytes).
- `open('C:/Dev/BRAINI~1/CLAUDE.md')` (8.3 name of the Phase 2 clean room) and `os.listdir('C:/Dev/BR8E16~1')` (8.3 of
  the audit dir) — allowed.
- `_winapi.CreateFile(...)` + `os.read` and `ctypes.CreateFileW/ReadFile` on the main repo — allowed: raw WinAPI does
  not raise the Python audit events in `_EVENTS` (18-20), so the hook never sees them.
- `os.listdir('~/.claude/file-history')` — allowed. pyguard's `_FORBIDDEN` covers `.claude[\\/]+projects`,
  `.credentials`, `.modal.toml`, `.claude.json` only; it does **not** cover `~/.claude/history.jsonl`,
  `~/.claude/file-history/`, or `~/.claude/paste-cache/`, which hold the answer-aware session's transcripts. (The
  PreToolUse hook *does* block those by name — pattern at guard_hook.py:42 — but an 8.3 name such as `HISTOR~1.JSO`
  defeats that too, and pyguard is the backstop that here fails.)

Regex containment shows the same class of gap: `_FORBIDDEN` matches `C:\Users\Mihir Modi\.claude\.credentials.json` and
`…\.claude\projects\C--Dev-BrainIR\…` but **not** their 8.3 forms (`CREDEN~1.JSO`, `C--DEV~1`), nor `history.jsonl`,
`file-history\…`, `paste-cache\….txt`.

**Fix**
- Make pyguard positive and path-resolving: on each FS event, `realpath` the argument (Windows resolves 8.3, `.`,
  symlinks) and deny unless it is inside the room or an explicit allowlist. A blocklist of substrings cannot be made
  complete.
- Native-code I/O (`ctypes`/`_winapi`) cannot be caught by `sys.addaudithook` — this is the residual the policy admits
  (§3) and is another argument for OS/container isolation as the primary control.
- Add the user's `~/.claude` transcript/history/paste-cache stores to whatever isolation is used (see F-M1).

## MAJOR

### F-M1 — The account the agents run as holds answer material in `~/.claude`, reachable through the F-B1/F-B2 gaps — severity: MAJOR

**Evidence** (`F_scratch/claude_home_scan.py`, counts only). The orchestrator's own transcript/history stores under
`C:\Users\…\.claude` contain answer and name tokens: `file-history` has 179 files with hits (dataset/circuit/author
names and answer cell types in the hundreds; e.g. `manc` 842, `malec…` 553, `pugli…` 84, the four answer interneuron
type strings 6–7 each), and `paste-cache` 2 files. These are the payload that F-B1/F-B2 expose: the method agents run
as the *same* Windows user as the answer-aware orchestrator, so its history is on the same account.

**Fix** — run agents under a separate OS account (as in F-B1); failing that, redact/move answer-aware history out of the
shared account before agents run, and extend both guards' coverage to the whole of `~/.claude` (not just `projects`).

### F-M2 — The uv cache exposes package metadata naming the datasets and circuit, through a path the hook explicitly allows — severity: MAJOR

**Evidence** (`F_scratch/uvcache_*.py`). `guard_hook.ALLOWED_OUTSIDE` (117-122) explicitly whitelists
`%LOCALAPPDATA%\uv\cache`; pyguard does not cover it. The cache holds the editable-install `brainir` wheel METADATA
and its `archive-v0` copies, whose long description names the datasets, the circuit and the paper
(`dng100`, `MANC`, `MaleCNS`, `Drosophila`, benchmark file paths). An agent can `unzip -p` the cached wheel or read the
archive copy and learn the organism/dataset/circuit names (no body ids or tier-A tokens are there — this is a
**name** leak, not identity).

**Fix** — build the room's `.venv` from a cache that contains no `brainir`/`brainir_state`/`p3synth` editable metadata
(a dedicated `UV_CACHE_DIR`), or strip the description from the Phase-3 package metadata; keep the uv-cache allowance
narrowed to wheels of third-party numeric/ML deps only.

### F-M3 — The held-out and final synthetic-suite seeds are stored in cleartext in a committed file; "secret seed" is not enforced, and F-B1 makes them reachable — severity: MAJOR

**Evidence.** `benchmarks/state_discovery_v1/hidden/synthetic_suites.json` is git-tracked and contains the heldout and
final suite seeds as plain integers (not derived from, nor protected by, the salt — only the salt has a sha256
commitment). With the committed generator `benchmarks/state_discovery_v1/generator/p3synth/`, these seeds regenerate
the hidden synthetic truth. The file is excluded from the room (allowlist + `FORBIDDEN_NAMES` `synthetic_suites`), but
F-B1's Bash bypass makes it reachable from within an agent, turning a selection/confirmation-suite exposure into a live
one. PROTOCOL.md §1–2 call these seeds "secret".

**Assessment** — the seeds *are* covered by `BENCHMARK_LOCK.json` (freeze `--check` green), so they cannot be silently
changed after the fact; the integrity risk is limited. The leakage risk is that heldout drives Level-B selection and
final is the one-shot confirmation, so a developer who reached this file could overfit selection. Contained today only
by the (breakable) room isolation.

**Fix** — do not commit the raw heldout/final seeds; derive them from the committed-by-hash salt at run time (as the
protocol says), or store only their hash until Level C; keep the file out of every room (already done) and close F-B1.

## minor

### F-m1 — The regenerated candidates encode the Phase-2 discovery result as tier-A positions in the room (by design)
`data/regenerated_candidates.json` and `data/systems_public.json` in the room list each mechanism's members as tier-A
positional ids. These 3–6-member sets are, in fact, mostly the Phase-1 answer's excitatory core plus an inhibitor
(`F_scratch/cand_vs_answer.py`, counts only: each candidate covers both essential neurons; 3 of its members are answer
core/contralateral positions). This is **explicitly permitted** by goal4 §5 (candidates regenerated from public
evidence by the locked method) and is oracle-free. The positions are tier-A ids, not mappable to cell types or body ids
without the salt (confirmed: net1 stimulus is tier-A position 3084, not the real body id) which is not in the room.
Residual = an agent with parametric knowledge could recognise the small E-E-I loop from `local_graph` signs — the same
recall residual the policy already states (§3.2). No action needed beyond keeping the salt/oracle out of the room.

### F-m2 — Synthetic system shape signatures are identical across dev/heldout/final and often unique
`(n, n_observed, readout_dim, input_dim)` is identical for all 48 systems across the dev, heldout and final suites, and
29/48 signatures are unique (`F_scratch/sizes.py`). Developers never see heldout/final data, but they know the
catalogue is public and could fingerprint a hidden family by shape and special-case it. Mitigated by the contract's
no-special-casing rule, aggregate-only Level-B feedback, held-out interventions/params/initial-states, and review G's
unknown traps. Worth a note to reviews C/G; consider perturbing `n`/observed sizes per suite in a future version.

### F-m3 — `audit_transcripts.py` name-flagging is coarse
It flags `outputs_with_forbidden_names` on any occurrence of `goal4.md`/`hidden_eval` etc.; the non-zero counts (e.g.
`m_cb` 2×`goal4.md`, 1×`hidden_eval`) all come from agents legitimately reading `docs/PROTOCOL.md`, which references
those paths. Benign, but it dilutes real signal. Consider excluding known-benign PROTOCOL strings so a genuine hit
stands out. The answer-token check (word-boundary on types/body-ids/positions>16) is correct and reads 0 everywhere.

### F-m4 — Guard logging is on and works for naive cases
The guard denied real attempts during development (m_lin 3, m_sd 1, p3lit 2, p3bench 1): `/tmp` writes, `cd` outside the
room, `.claude/projects`, and the shared-memory write from m_lin. This confirms the layer functions for the obvious
routes; only the crafted routes of F-B1/F-B2 evade it. Keep the logs with the Phase-3 record.

## What I verified as sound

- **No answer identity in the room.** 70 room text files scanned for published types, core/contralateral body ids,
  tier-A tokens, oracle labels (E1/E2/I1/I2), dataset/circuit/author names and answer phrases
  (`F_scratch/scan_room.py`): the only hits are (a) 5 coincidental numeric substrings inside
  `synthetic_dev/index.jsonl` that are seed/state values, not body ids (contexts checked), and (b) "Brunton"/METADATA
  author names in `docs/METHODS_REVIEW.md` (a legitimate methods citation) — no dataset name, no identity. npz payloads
  carry only `t/x/u/y`; venv metadata carries no names.
- **No answer tokens in any agent's traffic.** `audit_transcripts.py` over all eight streams: `outputs with ANSWER
  TOKENS = 0`, `forbidden-path inputs = 0`, `blocked tools = 0`, web only for the literature agent (558 methods-only
  fetches; 2 name-flagged inputs were method-topic, not the circuit). Room memory is empty; the shared memory write was
  guard-denied.
- **Candidate regeneration is clean (question 3).** All 70 locked `src/brainir/` files in `C:\Dev\BrainIR_p3regen`
  match the Phase-2 `METHOD_LOCK.json` hashes exactly; the bundle is byte-identical to `public_blind/` plus a
  `criterion.json` whose amplitude gate is **0** (the public no-gate criterion — not the answer-calibrated 0.25 Hz gate
  that review D flagged, so the D4 issue is avoided); provenance hashes verify (`output_sha256`, `method_lock_sha256`
  both match); `research/phase3/candidates/regenerated_candidates.json` equals the room's per-network outputs; the
  method ran oracle-free at seed 0, budget 1000 (`F_scratch/verify_regen.py`).
- **Method sandbox is sound (question 4).** `runguard.install_fit_guard/eval_guard` resolve `realpath` and test
  containment against a positive allowlist (method copy, fit view = train/val hard-links, output dir, sim queue, temp,
  environment), deny `subprocess`/`socket`, and the EVAL guard fires whenever a method frame is on the stack (so
  unpickling and every model call are covered while hidden data is loaded first by the evaluator). Tests pass:
  `phase3/tests/test_phase3_infra.py` 10 passed (incl. `test_fit_sandbox_refuses_reads_outside_the_allowed_roots`),
  `phase3/tests/test_guard.py` 36 passed.
- **Benchmark is frozen and verifiable.** `freeze_benchmark.py --check` green (81 files, 24 dataset entries);
  `BENCHMARK_LOCK.json` hashes the protocol, generator, truth files, the seed file, the code and the candidates, and
  commits the salt by sha256 only; git tag `state-discovery-benchmark-v1` present. Answer-bearing data
  (`data/phase3/hidden/salt.txt`, all `.../truth/…`) is git-ignored.
- **Enforced permission layer works for Read/Edit/Write.** `deny` rules block the `Read`/`Edit`/`Write` tools on the
  main repo, the Phase-2 room and the audit dir even under bypass mode; the own-session store is readable and other
  sessions' stores are denied (`test_guard.py`). p3clean is the only developer room in the manifest; MCP is disabled;
  web is off for method agents.

## Files and evidence
- Read: `goal4.md` §3–7, §69; `research/phase3/LEAKAGE_POLICY.md`, `CLEANROOM_MANIFEST.json`;
  `scripts/make_phase3_cleanroom.py`; `scripts/p3agent/{guard_hook.py, launch.py, audit_transcripts.py,
  pyguard/sitecustomize.py}`; `phase3/src/brainir_state/{runguard.py, runner.py, suite_eval.py, simservice.py,
  simclient.py, synthsim.py, realgen.py, data.py, api.py}`; `scripts/p3/{regenerate_candidates.py, regen_in_room.py,
  generate_real_data.py, simservice_systems.py, tournament.py, freeze_benchmark.py}`;
  `benchmarks/state_discovery_v1/{PROTOCOL.md, BENCHMARK_LOCK.json, hidden/synthetic_suites.json}`;
  `research/phase3/contracts/**` and `agent_prompts/**`; `research/phase2/reviews/D_leakage.md`.
- Probes (`research/phase3/reviews/F_scratch/`, F-only; safe to delete): `answer_tokens.py`, `scan_room.py`,
  `probe_guard_hook.py`, `probe_pyguard*.py`, `verify_regen.py`, `cand_vs_answer.py`, `sizes.py`, `uvcache_*.py`,
  `claude_home_scan.py`, `npz_keys.py`, `manifest_*.py`, `sys_peek.py`, `oracle_peek.py`, `contexts.py`.
- Commands: `audit_transcripts.py` (8 agents; 0 answer tokens), `freeze_benchmark.py --check` (green),
  `pytest phase3/tests/test_guard.py test_phase3_infra.py` (36 + 10 passed).
