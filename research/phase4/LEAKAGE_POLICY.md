# Phase 4 leakage policy (goal5 sections 4-6) — DRAFT by fork E3, 2026-09-26

The orchestrating session has seen the Phase 1 oracle, every Phase 2 hidden result and every Phase 3 hidden result (Level C, the
post-lock reviews, the FINAL confirmation). It therefore designs NO causal-state method logic. It builds generic infrastructure, the
frozen benchmark and evaluation, the rooms and the audits, runs experiments and returns aggregate scores only. Method design and the
synthetic systems are written by fresh agents that run as SEPARATE sessions inside technologically isolated rooms.

What agents may know (goal5 section 4): only the generic task — predictive latent states are not sufficient; learn causal state using
interventions. They must never receive: which real system failed in Phase 3, how badly, which intervention type failed, hidden k
values, hidden model rankings, hidden network-specific outcomes, or any Phase 3 answer-bearing file.

## 1. Rooms

| room | purpose | who | what enters |
|---|---|---|---|
| `C:\Dev\BrainIR_p4lit` | methods-only literature review | one agent, filtered web | its contract and CLAUDE.md only |
| `C:\Dev\BrainIR_p4bench` | synthetic causal-state systems (generator + truth) | one author agent | `research/phase4/ROOM_ALLOWLISTS.md` p4bench list (manifest `CLEANROOM_MANIFEST_bench.json`) |
| `C:\Dev\BrainIR_p4clean` | method development (built only after the benchmark freeze) | method agents, composer, baseline agent | p4clean list (manifest `CLEANROOM_MANIFEST.json`) |
| `C:\Dev\BrainIR_p4review` | reviews E, H, F (pre-freeze), A-D, G, E/H follow-ups | reviewer agents | p4review list = p4clean + `extra/` orchestrator code (manifest `CLEANROOM_MANIFEST_review.json`) |
| `C:\Dev\BrainIR_p4audit` | guard logs, agent streams, sandbox wrapper copies, protected-file lists | nobody (hooks write, orchestrator audits) | — |
| `C:\Dev\BrainIR_p4run` | orchestrator runs | orchestrator | — |

Every file that enters a room has a manifest record {path, source, destination, sha256, reason, classification, bytes}
(`scripts/make_phase4_cleanroom.py`). Rooms are updated only by `--sync "<reason>"` (logged in the manifest; interrupted syncs are
recovered), checked by `--check` and audited by `--audit` (re-hash, unmanifested files, links, planted Claude files, content scan of
every text file including agent-created ones; reports in `research/phase4/room_audits/`).

### 1.1 Never into any Phase 4 room (the builder's REFUSAL list; also its content scanner)

`PHASE*_REPORT.md`; `goal*.md`; `research/LOG.md`; `research/phase2/**`; `research/phase3/**`; `research/phase4/PLAN.md`;
`research/phase4/reviews/**` (until a later round explicitly includes an earlier review); `research/phase4/HIDDEN_EVALUATIONS.md`;
`research/literature/**`; `benchmarks/dng100_walking_cpg/**`; `benchmarks/dng100/{oracle,evaluator,baselines}/**`;
`benchmarks/state_discovery_v1/hidden/**`; `benchmarks/causal_state_v1/hidden/**`; `data/phase3/**`; `data/phase4/hidden/**`;
`data/phase4/suites/{val,conf}*/**/truth/**`; memory files; the main `CLAUDE.md`; credentials and Modal tokens; salts.
The scanner also refuses any text naming the datasets, the Phase 1 circuit or its source paper, Phase 1-3 answer phrases, Phase 2-3
answer-bearing artefact names (`PHASE3_REPORT`, `HIDDEN_EVALUATIONS.md`, `SALT_REVEAL`, `real_hidden`, `brainir-p3-eval`,
`POSTLOCK_*`, `REPORT_WORKING`, `state_discovery_v1/hidden`, `research/phase3`, `data/phase3`), absolute paths of the main repository
and the names of Phase 2-3 rooms.

### 1.2 Relays to agents

Only generic requirements, written from goal5's generic sections, never results. Tournament feedback = aggregate scores of the
public validation split only. Every relay is a file in `research/phase4/contracts/` or `review_contracts/` and enters a room by
`--sync`, so it is manifested and scanned.

## 2. Technological isolation

1. **Separate sessions** (`scripts/p4agent/launch.py`): the project directory IS the room; own memory / transcript store; never the
   orchestrator's context or scratchpad; no MCP servers (`--strict-mcp-config`, empty config); cross-session, scheduling,
   notification, Monitor, Workflow and PowerShell tools disallowed; web tools only for the literature agent (queries naming the
   benchmark's circuit, organism, datasets or paper refused); private TEMP inside the room; full event stream written outside the room.
2. **PreToolUse guard** (`scripts/p4agent/guard_hook.py`, `python -I`, outside the room). Phase 3 guard v2 (resolve-and-contain,
   refused path-building constructs, embedded scripts checked, ~/.claude refused except the agent's own session store) plus:
   - a HOST COMMAND ALLOWLIST: every simple command (after splitting pipelines, lists, subshells, command and process substitutions)
     must be a file / text tool or `sbx`; interpreters, shells, build tools, package managers, git, docker, tar / unzip and
     everything else are refused on the host; code-executing options of host tools are refused (find -exec with a non-allowlisted
     command, xargs, sed `e`, awk system / pipes, rg --pre, cp -s / -l, find -L);
   - PROTECTED FILES: the room's allowlisted files (list written by the builder outside the room), CLAUDE.md, CLAUDE.local.md,
     .mcp.json, .claude/, sbx and the manifest cannot be modified from the host;
   - LINKS: every path-like token, relative ones included, is resolved with realpath and must stay inside the room; Glob / Grep roots
     containing a link or junction are refused;
   - environment assignments that steer paths or the sandbox (PATH, PYTHONPATH, LD_PRELOAD, BASH_ENV, DOCKER_*, P4_* except the
     sandbox caps, ...) are refused.
   Unit tests: `phase4/tests/test_guard_p4.py` (incl. a real NTFS junction and a replay of every Phase 3 agent call).
3. **Docker sandbox** for ALL agent code (`sbx`, image `brainir-p4-sandbox:1`, `docker/p4sandbox/`; pinned stack = the evaluation
   environment's; image pinned by id in the wrapper, `--pull never`):
   - only the room is mounted (at /room); every allowlisted path read-only, the work areas read-write; no other host path, no docker
     socket;
   - `--network none` (loopback only), `--cap-drop ALL`, `no-new-privileges`, non-root uid 1000, read-only root file system, private
     in-memory /tmp;
   - seccomp = Docker's default profile minus `symlink` / `symlinkat` (`docker/p4sandbox/seccomp_nolinks.json`): code in a container
     could otherwise create symbolic links in the room, which Docker Desktop materialises on the host as junctions pointing outside
     the room (demonstrated 2026-09-26, `CANARY_TEST.md`);
   - CPU / memory / pid caps (default 2 CPUs, 6 GB, 512 pids; per-room maxima), a per-command timeout (default 6 h).
   The wrapper the agent runs lives OUTSIDE the room (`C:\Dev\BrainIR_p4audit\sbx_bin\<room>\sbx`, first on the agent's PATH; the
   room-root copy is read-only everywhere); the launcher refuses to start if the copies differ from the manifest or the image is missing.
4. **Python audit hook** (`scripts/p4agent/pyguard`) for any host Python (defence in depth: host interpreters are refused).
5. **Permission deny rules** (second layer) for the main repository, every other p2 / p3 / p4 room (incl. `BrainIR_p3postreview`,
   `BrainIR_p3run`, `BrainIR_p3audit`, `BrainIR_p3review*`, `BrainIR_p3clean`), the orchestrator's session / memory stores,
   credentials, the uv cache, file-history, paste cache, shell snapshots.
6. **Remote runner** (`scripts/p4/devrun4.py`): heavy and GPU development jobs on network-blocked Modal containers with NO repository
   code, the room's `src/`, `baselines/` and the requester's `runs/<prefix>/`, and the `brainir-p4-devdata` volume (a hash-verified
   copy of the room's `data/`); the job's processes cannot use the network or start other programs; results come back into the
   requester's work area; every job logged in `C:\Dev\BrainIR_p4audit\remote_runner.jsonl`.
7. **Simulation only through the budgeted service** (`brainir_causal.simclient`): method rooms contain no simulator code; the service
   refuses held-out and hidden-only families, non-public targets / edges / seeds / input ranges and truth events.
8. **Audits**: `scripts/p4agent/audit_transcripts.py` (tool calls, forbidden paths / names, Phase 2-3 answer-bearing artefact CLASSES
   in outputs, Phase 1 answer tokens by class, web queries, guard denials, calls the current guard would deny) at every milestone;
   `make_phase4_cleanroom.py --audit` per room; canary test (`CANARY_TEST.md`).

## 3. Modal

- Phase 4 volumes only: `brainir-p4-devdata` (copy of the clean room's `data/`), `brainir-p4-fit` (public fit views, method
  snapshots), `brainir-p4-eval` (validation / confirmation truth, hidden data; mounted only by evaluation containers, never by fit or
  development containers).
- NEVER mounted by any Phase 4 container: `brainir-p3-eval` (Phase 3 hidden data, answer-bearing), `brainir-p3-fit`,
  `brainir-p3-devdata`. `devrun4.py` refuses any volume that is not `brainir-p4-devdata*`.
- No agent has Modal access; the orchestrator mediates every job.

## 4. Residual risks (stated, not hidden)

- The Claude sessions themselves are not containerised: an OAuth refresh inside a container would rotate the host's refresh token
  and could log the orchestrator out (Phase 3 decision P3-D2). Their tool calls run on the host under the guard; only the code they
  execute runs in Docker.
- The guard is not a kernel sandbox: it reads command text. An allowlisted host tool with an unforeseen execution feature could run
  code; the allowlist is small and the code-executing options known to us are refused; transcripts are audited afterwards.
- `kill <pid>` stays allowed on the host (agents stop their own background jobs); it could stop another process of the same user.
- Agents sharing a room can read (not modify) each other's work-area files and could plant instructions in a nested CLAUDE.md
  (host writes of CLAUDE.md are refused; container writes into work areas are possible). `--audit` reports nested Claude files.
  No agent in a room holds answer-bearing material, so this is an interference risk, not a leakage risk.
- Recall from training: agents may know published literature about the Phase 1 circuit; rooms contain no dataset, circuit or paper
  names, and web queries about them are refused.
- The orchestrator (answer-aware) writes the evaluation, the real-system protocol families and the interfaces. They follow goal5's
  generic text; no target, family or threshold is chosen by knowledge of a Phase 3 hidden outcome; reviews F (leakage) and E
  (statistics) audit them.
- The literature agent (`p4lit`) was started at 10:06 local, before the Phase 4 stack existed, with the reviewed Phase 3 stack
  (`scripts/p3agent`, guard v2, web filter) in its own room with only its contract; it needs no code execution. Its later audit
  (`audit_transcripts.py`) shows 1 guard denial (a network command) and no forbidden output.

## 5. Operating rules

- Never rebuild a sandbox image tag in place: build a new tag, then `--sync` every room (a rebuilt tag deletes the previous image,
  which rooms reference by id; incident 2026-09-26 10:52, fixed by syncing the bench room within minutes, no failed agent call).
- Build the clean (method-development) room only after the benchmark freeze. The review room is built BEFORE the freeze for the
  early reviews E, H and F of the evaluation machinery (reviewers develop no method; the room follows the p4review allowlist and the
  refusal list, so no hidden record, salt or truth of the validation / confirmation tiers enters it) and synced for later rounds.
  Sync generic files one by one with a logged reason.
- Run `--audit` for every room and `audit_transcripts.py` at every milestone (before each tournament round, before the lock, after
  the hidden evaluation) and keep the reports.

## 6. Phase 4 answer-bearing material (never into any room; the builder refuses it)

Before the lock: `research/phase4/PLAN.md`, `research/LOG.md` section 12, validation and confirmation truth, the salt, internal real
system records and the name map (`benchmarks/causal_state_v1/hidden/`), per-system tournament scores beyond the published aggregates.
After the lock, in addition: `PHASE4_REPORT.md`, `research/phase4/HIDDEN_EVALUATIONS.md`, every hidden-evaluation output, the
post-lock reviews, the hidden data (`data/phase4/hidden/**`), the eval volume `brainir-p4-eval`.
