# Review F3c: round-3 final check (isolation: the generator's final public surface)

Reviewer F. Scripts are in `.tmp/F/r3c/`; all numbers are from my own runs in the sandbox (`sbx`) unless marked as reading.

**Side effects:** none outside `.tmp/F/r3c/` and this file. I did not stop or signal any other agent's process or container. The `kill` probes used `-0` (a no-op) on process ids that do not exist.

**Cost:** building 3 development-tier suites with the final generator took 2,997 s (about 1,000 s per suite) in the machine's single slot, plus about 3 minutes of analysis.

## 1. Per-item table

| # | item | status | evidence |
|---|---|---|---|
| **1a** | NB-1: "no compact causal state" from public fields | **fixed** | `build.py` + `analyse.py`: the final generator built suites 0, 7, 11 (150 systems, 25 types, 12 no-compact controls). Each system is summarised by the benchmark's PUBLISHED record (`suites.synthetic_records`, every numeric leaf: normalised capability, obs_scale, sizes, targets / edges counts) plus statistics of the PUBLIC edge list (degree means / sd / max, isolated fraction, reciprocity): 41 varying features. Random forest, leave-one-suite-out: **AUC 0.477** (folds 0.424 / 0.435 / 0.573); label-permutation null mean 0.447, 95th percentile 0.562. The round-3b field is neutralised: `kick.moderate` has range and median 3.19–9.90 (median 6.13) for controls and 3.03–9.96 (median 6.00) for the others, single-feature AUC 0.503. Best single feature: `capability.time_scale`, AUC 0.644 (12 positives; not significant under the RF null). |
| **1b** | NF-5: type from public fields | **fixed** | type accuracy **0.047** (folds 0.02 / 0.08 / 0.04) vs chance 0.040; permutation null mean 0.039, 95th percentile 0.060. 7 of 150 held-out systems predicted correctly, no type recognised more than twice. **Judgement on the author's residual (6.2–7.3 % vs 4.2 %):** my estimate is inside the null. At that level a type guess is right about 1 time in 15 and carries no usable information about a given system's trap class or k. Not material. |
| **1c** | NF-5: k from public fields | **fixed** (residual = the protocol's own small-regime rule) | All systems: accuracy 0.507 vs majority 0.433 (null 95th percentile 0.464), **above chance**. The signal is entirely the small regime: all 7 systems with fewer than 10 observed units have k = 1, which PROTOCOL's compactness rule k ≤ max(1, N_obs/5) forces; `n_obs` ALONE gives 0.500 (`kcheck.py`). Excluding them: 0.461 vs majority 0.455, null 95th percentile 0.500, i.e. chance. Legitimate structure, not a leak. |
| **1d** | unit roles from public fields | **fixed** | 12,050 units, core fraction 0.619: RF (public in/out degree, observed, public target, degree from / to observed units, size, observed fraction, edge density) **AUC 0.521** (folds 0.526 / 0.519 / 0.520); single features 0.494–0.529. |
| **2** | NF-1: held-out targets | **fixed** | `build.py`, the builder's own internal record, 150 systems: public ⊆ generator-targetable 150/150; held-out ⊆ targetable 150/150; public ∪ held-out = targetable 150/150; held-out = observed − public 0/150; targetable = observed 0/150; targetable set in the public record 0/150. Location: `suites.py:330,357` (`TARGETABLE_KEYS`, `generator_targetable`, no fallback). |
| **3** | NF-3: `sbx --ps` / `--stop` scope | **fixed** | `sbx:59-69`: both filter on `brainir.p4.agent == $agent` (from `P4_AGENT_NAME`). `sbx --ps` lists only my containers; `sbx --stop deadbeef1234` → "not one of your sandbox containers in this room"; `P4_AGENT_NAME=<other> sbx --ps` and `env P4_AGENT_NAME=<other> sbx --ps` → guard G7 (the label source cannot be spoofed). Naming another agent's container in a command → G1. **But see NF3c-1:** the new slot code lets an agent learn other agents' wrapper PIDs, which reopens the NF-3 effect through the orphan rule. |
| **4a** | slot / floor / wait cannot be bypassed | **ok** (by reading + runs) | `MAX_SLOTS`, `MIN_FREE_GB`, `SLOT_DIR` are constants in the immutable wrapper. `P4_SBX_WAIT_S` only bounds the wait (0–3600, validated). The mutex is `mkdir` in `C:\Dev\BrainIR_p4audit\sbx_slot` (outside every room; the guard refuses paths there). Free memory comes from `/proc/meminfo` (not agent-writable). The holder count uses `docker ps -a --filter name=^p4sbx-` inside the mutex, and the container is created inside it. An agent can only HOLD the slot (up to its timeout, 12 h max), i.e. a machine-wide denial of service by long jobs, which is the owner's rule and needs an operator. |
| **4b** | no agent-writable path the wrapper trusts | **ok** | The wrapper reads only its own constants, the token file under `C:\Dev\BrainIR_p4audit\…\agent_tokens` (outside), `SLOT_DIR` (outside) and `/proc/meminfo`. The room paths it creates / binds are checked for links (`[ ! -L … ]`). |
| **4c** | listing / reaching / stopping another agent's container | **FAIL (NF3c-1)** | see §2 |
| **5** | NF-4: smoke evidence for staging / packing | **partly** | `extra/scripts/smoke_pack_modal.py`, `smoke_stage_modal.py` are now in the room, and `extra/LEVEL_B_EXECUTION.md` §§ on packing report their outcomes with app ids (peer socket / port / shm refused, `/repo`, `/evalvol` denied, …). No raw result JSON in `extra/results/` (the other smokes have one). |

**Counts (10 rows):** fixed 6 (1a, 1b, 1c, 1d, 2, 3); ok 2 (4a, 4b); fail 1 (4c, i.e. NF3c-1); partly 1 (5).

NF-2 (the accounting module in the clean room) was not re-run this round; the benchmark notes state it is fixed, so it is **unverified** by me.

New findings: 0 blockers, 0 majors, 2 minors.

## 2. New findings

**NF3c-1 (MINOR): the slot message discloses other agents' (and other rooms') container names, including the wrapper PID; together with host `kill <pid>` and the orphan rule, one agent can get another agent's running sandbox stopped.**
- **Location:** `sbx` (= `extra/scripts/p4agent/sbx_template.sh`).
  - The container name is `p4sbx-${ROOM_NAME}-${agent}-$$-${RANDOM}` (`$$` = the wrapper's PID).
  - The exit-75 message prints `docker ps --filter name=^p4sbx-` names **machine-wide**.
  - `sandboxes()` stops any running `p4sbx-` container older than 60 s whose client PID fails `kill -0`.
- **Evidence:**
  - `P4_SBX_WAIT_S=0 sbx true` (the assignment is allowed: sandbox caps) returned **immediately** with exit 75 and `holding the slot: p4sbx-BrainIR_p4review-review_F_r3c-467271-19498 (45 seconds ago)`. Here that is my own container; with another holder, it is theirs, from any room.
  - The host guard allows `kill` with an explicit PID (`kill -0 999999` and `kill -s 0 999998` ran and reported "No such process").
  - Chain (not executed): read the holder's PID from the message → `kill <pid>` its Git-Bash wrapper (same Windows user, shared MSYS process table) → the next `sbx` call anywhere on the machine finds the container "orphaned" and stops it.
  - Also, room names and agent names of OTHER rooms are printed to any agent, although room names are otherwise forbidden input.
- **Fix:**
  - Print no foreign names in the wait message (only "busy since N s", or the caller's own container).
  - Drop `$$` from the container name (keep the client PID only in the label, which `--ps` no longer shows to others).
  - Refuse host `kill` of processes the agent did not start: the guard can allow only PIDs of the agent's own background jobs (`%n` job specs) instead of any explicit PID.
  - Optionally make the orphan test depend on a client heartbeat in `SLOT_DIR` rather than `kill -0` across MSYS sessions. A wrapper launched from a separate MSYS / Windows process space would otherwise look dead to every other agent's `kill -0` and be stopped after 60 s.

**NF3c-2 (MINOR, availability): one machine-wide slot and a 12 h timeout.** Any agent (or reviewer) can hold the only sandbox for up to `P4_SBX_TIMEOUT_S` = 43,200 s, blocking every room, including the orchestrator's own room checks if they use `sbx`. This is not a leak. My own run held the slot for 50 minutes, because the final generator needs about 1,000 s per development suite.
- **Fix:** a lower cap on sandbox run time while others wait (or pre-emption after N minutes when the queue is non-empty), and route suite-sized work to the remote runner.

## 3. Verdict

**Ready to freeze from the isolation / leakage side**, with two minor items to fix at small cost. On the final generator and the rebuilt data, a classifier over every numeric published field predicts:
- no compact causal state at chance (AUC 0.477, null 95th percentile 0.562);
- type at chance (4.7 % vs 4.0 %, null 95th percentile 6.0 %; the author's 6.2–7.3 % residual is not material);
- unit roles at chance (AUC 0.521);
- k only through the protocol's own small-regime rule (chance once systems with fewer than 10 observed units are excluded).

The held-out targets are no longer derivable, and every target is targetable by the generator (150/150). `sbx --ps` / `--stop` are limited to the caller. The new machine-wide slot adds no agent-controllable bypass and trusts no agent-writable path. Its wait message, however, discloses other agents' and rooms' container names with the wrapper PID, which with the guard's permitted `kill <pid>` and the orphan rule re-creates cross-agent stopping (NF3c-1). This should be fixed before method developers share the clean room, but it does not affect any metric or hidden-data boundary.
