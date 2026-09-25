# Phase 3 leakage policy (goal4 sections 3-5)

The orchestrating session has seen the Phase 1 oracle and every Phase 2 hidden result. It therefore designs NO state-discovery method
logic. It builds generic infrastructure, the frozen evaluation, the rooms and the audits, runs experiments, and returns aggregate
scores only. Method design happens in fresh, oracle-free agents that run as SEPARATE sessions inside technologically isolated rooms.
This policy answers review D's Phase 2 findings (isolation was procedural; answer structure reached the agents' context).

## 1. Rooms

| room | purpose | who works there | what enters |
|---|---|---|---|
| `C:\Dev\BrainIR_p3clean` | method development (tournament families, composer) | oracle-free method agents | the allowlist of `scripts/make_phase3_cleanroom.py` only (manifest: `CLEANROOM_MANIFEST.json`) |
| `C:\Dev\BrainIR_p3bench` | synthetic state-discovery benchmark generator | one oracle-free benchmark author | its contract, the protocol and dataset specs (manifest `contracts/p3bench_initial_manifest.txt`) |
| `C:\Dev\BrainIR_p3lit` | methods-only literature review | one oracle-free agent with filtered web access | its contract only |
| `C:\Dev\BrainIR_p3regen` | regeneration of Phase 2 candidates from public evidence (goal4 section 5) | the orchestrator runs a script there; no agent | the locked Phase 2 library (hash-verified against the Phase 2 METHOD_LOCK), the public blind bundle (hash-verified) + a public no-gate criterion |
| `C:\Dev\BrainIR_p3audit` | guard decisions, agent event streams, the Python guard | nobody (the guard writes, the orchestrator audits) | — |

Nothing from the main repository enters a room except through these lists. In particular NEVER: `PHASE2_REPORT.md` (answer-bearing),
`PHASE0/1_REPORT.md`, `goal*.md`, `research/LOG.md`, `research/phase2/**` except nothing, `benchmarks/dng100_walking_cpg/**`,
`benchmarks/dng100/oracle|evaluator|baselines/**`, hidden evaluation directories, truth directories, review files, the main
`CLAUDE.md`, the Phase 1-2 library, simulator code, and any file naming the datasets or the circuit.

## 2. Technological isolation of agents (scripts/p3agent/)

1. **Separate sessions.** `launch.py` starts each agent as a headless Claude Code session whose project directory IS the room: it loads
   only the room's CLAUDE.md, gets its own memory and transcript store, and never inherits the orchestrator's context or scratchpad.
2. **PreToolUse guard hook** (`guard_hook.py`, run outside the room with `python -I`): denies every tool call that names a path outside
   the room (Read / Write / Edit / Glob / Grep paths, absolute and relative-escape paths in Bash / PowerShell commands, quoted or not),
   forbidden substrings (the main repository, other rooms, other sessions' stores, credentials, the audit directory, Phase 2
   artefacts), all MCP tools (browser, external services), cross-session and scheduling tools (ListAgents, SendMessage, RemoteTrigger,
   PushNotification, Cron*, ...), non-builtin subagent types, writes to the room's `.claude/` or `CLAUDE.md`, and any attempt to
   disable the Python guard. Web tools are removed for every agent except the literature agent, whose queries are refused when they
   name the benchmark's circuit, organism, datasets or source paper. Each decision is logged (JSONL) outside the room. The agent's OWN
   session store (large tool results) stays readable; every other store is denied.
3. **Python audit hook** (`pyguard/sitecustomize.py`, via PYTHONPATH): every Python the agent starts refuses file, directory and
   process events on forbidden locations, including paths built at run time.
4. **Permission deny rules** for the main repository, the orchestrator's project store, credentials and the audit directory (a second
   layer; they held in bypass mode in the canary test).
5. **No MCP servers** (`--strict-mcp-config` with an empty config); disallowed tools removed at launch.
6. **Private TEMP** inside the room.
7. **Simulation only through the service** (`brainir_state.simservice`): method rooms contain no simulator code; the service enforces
   the public policy (public systems, public seeds < 10^9, public stimulus range, kicks / pulses / single silencing on public targets
   only), so the held-out families of the protocol cannot be simulated during development; per-agent budgets are logged.
8. **Anonymised network names** (net1 / net2 / net3) in every public file; the mapping stays in `benchmarks/state_discovery_v1/hidden/`.
9. **Method sandbox on the orchestrator side** (`brainir_state.runguard`, `brainir_state.runner`, `brainir_state.suite_eval`):
   - Tournament and Level C fits run in subprocesses whose audit hook refuses every file event under the development drive and the
     user's credential / session stores. The exceptions are a snapshot of the room's methods package, a FIT VIEW of the suite
     (train / val rows only, hard-linked into a separate directory), the output directory, the suite's simulation queue and a
     private temp directory (plus the Python environment). The hook also refuses process creation and network connections.
   - Evaluation workers load the held-out data first. They then refuse file, process and network events whenever a frame of the
     method's code is on the call stack.
   - Tested: `phase3/tests/test_phase3_infra.py::test_fit_sandbox_refuses_reads_outside_the_allowed_roots`.

Verified by a canary test (2026-09-24): an agent asked to read a canary outside its room through the Read tool, `cat`, `cd ..`, Glob,
WebSearch, a Python script building the path at run time, and `~/.claude/projects` was blocked at every step, could read inside its
room, and the canary text never appeared in its transcript. The guard's decision function has offline unit checks
(phase3/tests/test_guard.py).

### 2.1 Guard version 2 (after review F, 2026-09-24)

Review F showed that version 1 of both code guards was a substring blocklist, and it demonstrated bypasses (`$PWD/..`, variable
indirection, globs, `/./`, 8.3 names, chdir, native ctypes / _winapi I/O). No bypass was ever used: a replay of every executed call
through version 2 shows none.

Both guards now resolve and contain:
- every path resolves (realpath, 8.3 / links / dots) inside the room;
- shell commands may not build paths the guard cannot see;
- scripts and embedded shell bodies are checked like commands;
- Python is checked at run time for file, native-I/O, network and child-process events.

Details and tests: `research/phase3/reviews/F_resolution.md`.

## 3. Residual risks (stated, not hidden)

- The hook is not a kernel sandbox: a program started by an allowed command could reach a forbidden location through a route that
  names no path (e.g. a compiled binary). The Python layer covers Python; everything is audited afterwards from the transcripts and
  guard logs.
- The agents are language models that may know published literature about the benchmark's circuit. Rooms contain no dataset names,
  circuit names or identities, and web queries about them are refused; recall from training cannot be excluded.
- The orchestrator (answer-aware) wrote the evaluation, the real-data protocol families and the interfaces. They are generic (no
  neuron is chosen by knowledge of the answer: targets come from seeded splits of the probe population; candidate mechanisms come from
  the regeneration rule), and reviews F (leakage) and E (statistics) audit them.
- The synthetic benchmark author, the literature agent and the method agents share the user's model and machine; they share no files.

### 3.1 Tournament execution on Modal (LOG P3-D15, 2026-09-25)

Level B fits and evaluations, the reference controls and the calibration run on the orchestrator's own Modal account
(`scripts/p3/modal_tournament.py`, container side `scripts/p3/p3modal/`).
- **Volumes.** The synthetic suites (public part, held-out rows, truth) are uploaded to a private volume `brainir-p3-eval`. The public
  fit views and the method snapshots go to a separate volume `brainir-p3-fit`. No real hidden data and no Phase 1-2 oracle file is
  uploaded.
- **Fit containers** mount ONLY the fit volume. Every method subprocess installs a Linux guard (`p3modal.guard`, via sitecustomize)
  before any method code runs. The guard refuses, by realpath:
  - file events under /fitvol, /evalvol, /repo, /tmp, /root, /home, /mnt, /data outside the job's own allowed roots;
  - other processes' /proc entries;
  - process creation and network.
- **Evaluation containers** mount both volumes. The guard applies while a method frame is on the call stack, the same rule as the frozen
  runguard. Each job runs in a fresh interpreter.
- **No agent has network access.** No clean-room agent can reach Modal: the command guard refuses network tools, and pyguard refuses
  socket events.
- **Amendment (benchmark version 3, 2026-09-25, before any hidden real data exist).** Level C runs on Modal like Level B:
  - the PUBLIC real fit view and the public blind bundle (`benchmarks/dng100/public_blind`, 3 MB, already public) are staged on the
    fit volume; the internal real system definitions go to the eval volume only;
  - the hidden real data are generated after the method lock. Their protocols are built locally from the salt (the salt never
    leaves the machine); the simulations run on Modal (`generate_real_hidden.py --backend modal`, which refuses to run before the
    method lock) and write ONLY to the eval volume (`/evalvol/real_hidden_build`, `/evalvol/suites/real/hidden`); the local copy is
    downloaded from there. With the local backend they are uploaded to the eval volume only (`modal_tournament.py upload-real --what
    hidden`). Fit containers never mount the eval volume;
  - evaluation containers read them under the same guard as the synthetic held-out suites;
  - counterexample searches with HIDDEN real parameter draws run locally only (`counterexamples.py` refuses Modal for them).

## 4. Audits

`scripts/p3agent/audit_transcripts.py` (to be run at every milestone and by review F) scans every agent's event stream and guard log
for: tool inputs naming forbidden paths, outputs containing forbidden tokens (dataset names, oracle labels, the answer's types / ids /
tier-A tokens read at audit time from the oracle), denied calls, web queries, and files created outside the room. Findings go to
`research/phase3/reviews/`.

## 5. Post-lock answer-bearing files of Phase 3

Answer-aware from the start: `research/phase3/reviews/F_leakage.md` (review F read the Phase 1 oracle), `F_resolution.md`. After the Level C evaluation: `research/phase3/HIDDEN_EVALUATIONS.md`, `benchmarks/state_discovery_v1/hidden/**` and its outputs,
`data/phase3/hidden/**`, `PHASE3_REPORT.md`. Never copy them into a Phase 4 clean room.
