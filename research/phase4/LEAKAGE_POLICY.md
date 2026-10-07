# Phase 4 leakage policy (goal5 sections 4-6) — DRAFT by fork E3, 2026-09-26; isolation v3 by fork E9 (early review F); v4 by fork E16 (review F round 2)

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
`data/phase4/suites/{val,conf}*/**/truth/**`; memory files; the main `CLAUDE.md`; credentials and Modal tokens; salts; the
orchestrator's names config `scripts/p4config/**` (every forbidden name lives there and nowhere else, early review F, F-M1; the review
room gets a generated PLACEHOLDER with dummy words); canary files (`canary*.txt`).
The scanner also refuses any text naming the datasets, the Phase 1 circuit or its source paper, Phase 1-3 answer phrases, Phase 2-3
answer-bearing artefact names (`PHASE3_REPORT`, `HIDDEN_EVALUATIONS.md`, `SALT_REVEAL`, `real_hidden`, `brainir-p3-eval`,
`POSTLOCK_*`, `REPORT_WORKING`, `state_discovery_v1/hidden`, `research/phase3`, `data/phase3`), absolute paths of the main repository
and the names of Phase 2-3 rooms. The scanner reads each text as it is AND after removing regex escapes (`\b`, `\s*`, `\ `, ...),
plus a word list with any separator, so a name written as a regex source is found too (F-M1). Orchestrator code copied into the
review room is scanned the same way; a line that still carries a hit is replaced by `<redacted line>` (fallback only; the count and
the source hash are recorded in the OUTSIDE manifest, never in the room).

### 1.2 Relays to agents

Only generic requirements, written from goal5's generic sections, never results. Tournament feedback = aggregate scores of the
public validation split only. Every relay is a file in `research/phase4/contracts/` or `review_contracts/` and enters a room by
`--sync`, so it is manifested and scanned.

## 2. Technological isolation

Version 3 of the stack (early review F: F-B4, F-M1, F-M2, F-M3, F-M7, minors 1, 3, 4, 9; fork E9, 2026-09-26); version 4 (review F
round 2: N-M1, N-M2, the M4 / M5 residues, N-m1, N-m3; fork E16, 2026-09-26). Evidence: the unit tests named below,
`research/phase4/devrun4_isolation_smoke.json` and the live canary runs in `CANARY_TEST.md`.

1. **Separate sessions** (`scripts/p4agent/launch.py`): the project directory IS the room; own memory / transcript store; never the
   orchestrator's context or scratchpad; no MCP servers (`--strict-mcp-config`, empty config); cross-session, scheduling,
   notification, Monitor, Workflow and PowerShell tools disallowed; web tools only for the literature agent; a private TEMP
   `.tmp/<scratch>` (`--scratch`, default the agent's name; prompts that name `.tmp/<letter>` must launch with `--scratch <letter>`);
   the launcher's environment drops every inherited `P3_*` / `P4_*` / `MODAL_*` / `DOCKER_*` variable; the launch is refused when the
   outside sandbox wrapper differs from the OUTSIDE manifest, when the room's OS protection is missing or when the image is absent;
   each launch issues a fresh simulation-service token (review F, F-M4: `brainir_causal.simservice.issue_token`, recorded by its hash
   in `C:\Dev\BrainIR_p4audit\simservice\<room>\tokens.json`, outside the room; the service runs with `--tokens` that file and a
   ledger directory outside the room). The token is BOUND to the agent's queue `simq/<scratch>/` (round 2, N-M1: the service refuses
   it in any other queue, including the shared one, with the same generic error as an unknown token; a relaunch revokes the queue's
   earlier tokens) and is written to `C:\Dev\BrainIR_p4audit\simservice\<room>\agent_tokens\<scratch>.token` (outside the room):
   the sandbox wrapper reads that file and forwards the token into the container (`-e P4_SIM_TOKEN`, never on a command line). The
   agent's HOST environment never holds it; the guard refuses every `P4_*` assignment, every host command whose text names
   `P4_SIM_TOKEN` and every listing of the environment (`phase4/tests/test_guard_p4.py`,
   `test_launcher_binds_the_token_to_the_queue_and_keeps_it_out_of_the_environment`). The scratch name is the agent's subdirectory in
   every per-agent and owned area (developers: their prefix; reviewers: their letter); the full event stream is written outside the
   room.
2. **PreToolUse guard** (`scripts/p4agent/guard_hook.py`, `python -I`, outside the room; `phase4/tests/test_guard_p4.py`):
   - NAMES: every forbidden word, room name and web-block pattern is loaded from the orchestrator's config at run time; the guard code
     carries none; without the config every call is refused (fail closed);
   - GENERIC REFUSALS (F-M2): the agent sees `BLOCKED by the room guard [G<n>-<event id>]: <generic hint>`; classes: G0 guard error,
     G1 forbidden input, G2 outside the room / another agent's area, G3 host execution, G4 write outside the work areas or a
     write-capable option, G5 disabled tool, G6 web, G7 shell construct, G8 sandbox spelling / wrapper integrity, G9 planted control
     file. The matched pattern and the detail go only to `C:\Dev\BrainIR_p4audit\guard_<agent>.jsonl` (keyed by the event id);
   - HOST COMMAND ALLOWLIST: every simple command (after splitting pipelines, lists, subshells, command and process substitutions,
     and the substitutions of unquoted here-documents and double-quoted `-c` bodies, which the host shell expands) must be a file /
     text tool or `sbx`; interpreters, shells, build tools, package managers, git, docker, tar / unzip, `xargs`, `split`, `dd`,
     `install`, `ln`, `shopt` and everything else are refused on the host;
   - THE SANDBOX (F-B4 b): only the bare command `sbx`, which must resolve through PATH to the copy OUTSIDE the room, whose sha256
     must equal the OUTSIDE manifest's record and the protected list's, and which must carry its NTFS deny ACE, checked on every
     call; every path spelling (`./sbx`, `<room>/sbx`, ...) is refused;
   - WRITES (F-B4 c): the Write / Edit tools, redirections and every write-capable host command (cp, mv, rm, rmdir, mkdir, touch,
     chmod, tee, `sed -i`, `sort -o` / `-T`, `uniq` OUTPUT, `shuf -o`, `tree -o`, gzip / gunzip) may target only the agent's work
     areas (`C:\Dev\BrainIR_p4audit\protected_<room>.json`: the declared work areas, or in a free room every top-level entry that
     is not the orchestrator's; in `.tmp/` and `simq/` only the agent's own subdirectory; in the shared areas OWNED per agent, clean
     room `src/brainir_causal/methods`, `tests/methods`, `runs`, `notes` and review room `reviews`, `runs`, `notes`, only
     `<area>/<scratch>/`, so other agents' files there are read-only (round 2, N-M2)), never a Claude control file, a
     sitecustomize / usercustomize module or a `.pth` file. Refused options: sed `w` / `W` / `r` / `R` / `e` and the `s///w`,
     `s///e` flags (a sed parser, `sed -f`), awk output redirection, pipes, `system()`, `getline <`, `ARGV`, `@load` / `@include` and
     every option but `-F` / `-v` / `-e`, find `-exec` / `-execdir` / `-ok` / `-okdir` / `-delete` / `-fprint*` / `-fls` / `-L`,
     `sort --compress-program`, `--files0-from`, checksum `--check`, `file -f`, `rg --pre` / `--hostname-bin` / `-z`, `grep -R`,
     `rm --no-preserve-root`, `jq -L` / `include` / `import`, `tree -R`, env options, `command -p`;
   - LONG OPTIONS (round 2, N-m1): GNU long options are canonicalised as getopt does before any check: an exact name wins, a unique
     prefix becomes that option (`sort --outp=F` is `--output=F`, `sed --in-pl` is `--in-place`), an ambiguous prefix is refused;
     per-tool tables of every long option, with a conservative global table as the fallback;
   - DATA-DRIVEN PATHS: file arguments, sed scripts, awk programs and jq filters must be literal after substituting variables assigned
     from literals in the same command, brace and glob expansion (every expansion is checked); command substitutions, unknown or
     read-loop variables, positional parameters and ANSI-C quoting cannot name files or become scripts; globs that could match `.` or
     `..` are refused; runtime data cannot reach an arithmetic context (array subscripts evaluate command substitutions); `((...))`,
     `${!x}`, name references and integer attributes are refused;
   - PATHS / LINKS: every path (after expansion) is resolved with realpath and must stay inside the room and outside other agents'
     private areas (minor 4); a junction inside the room cannot be followed out; Glob / Grep roots containing a link or junction are
     refused; `cd` targets are tracked (subshells included) for relative paths;
   - PLANTED CONTROL FILES: Read / Write / Edit of a file below a directory that holds a CLAUDE.md, CLAUDE.local.md, .mcp.json or
     .claude (other than the room root's placeholders) is refused (G9), so instructions planted in a shared work area are never
     loaded;
   - ENVIRONMENT: variables that steer path resolution, command lookup or the sandbox (PATH, PYTHONPATH, BASH_*, PS0-4, IFS, CDPATH,
     GLOBIGNORE, PWD, DOCKER_*, P4_* except the sandbox caps, ...) cannot be assigned, also not through export, declare / local,
     read, `printf -v` or an array subscript; the environment is never listed on the host (`printenv` / `env` without names, bare
     `set`, `export` / `declare` / `local` without names) and no host command may name the simulation token (round 2, N-M1);
   - patterns, scripts and echo text are not path-checked (minor 3: a grep regex with `\.\w` is allowed); PYTHONPATH and similar
     words are no longer refused as TEXT (only their assignment is).
3. **OS-level immutability** (F-B4 a; `scripts/p4agent/ntfs_protect.py`, `phase4/tests/test_room_acl.py`): the room builder puts an
   NTFS deny ACE for Everyone on every allowlisted file (FILE_MASK: write, append, attributes, extended attributes, delete, take
   ownership), every orchestrator directory and the root of rooms with declared work areas (DIR_MASK = FILE_MASK + delete child),
   the root of a free room and every work area holding an allowlisted file (PARENT_MASK: delete child, delete, take ownership; NTFS
   lets delete-child on a parent delete, rename or REPLACE a file whose own DELETE is denied: measured, `sed -i` replaced such a
   file), every other work-area root (ANCHOR_MASK: delete, take ownership), and on the outside sandbox copy, its seccomp profile and
   their directory. Reads are unaffected. `--sync` and `--destroy-and-rebuild` lift the ACEs first and restore them afterwards
   (also after a failed sync); `--check` / `--audit`, the launcher and (for the outside copy) the guard verify them. Measured: another
   process of the same user (Python, the Git Bash file tools) and a sandbox container with a WRITABLE bind mount of the directory
   cannot write, append, rename, replace, delete or create entries under a protected path.
4. **Docker sandbox** for ALL agent code (`sbx`, image `brainir-p4-sandbox:1`, `docker/p4sandbox/`; pinned stack = the evaluation
   environment's; image pinned by id in the wrapper, `--pull never`) (F-M3):
   - the room is mounted READ-ONLY at /room; only work areas are bound read-write over it. The shared areas are OWNED per agent
     (round 2, N-M2): clean room `src/brainir_causal/methods`, `tests/methods`, `runs`, `notes`, review room `reviews`, `runs`,
     `notes`; the area itself stays read-only (every agent's subdirectory readable) and only `<area>/<scratch>` is bound read-write
     (the wrapper creates it; the builder records the owned areas in `protected_<room>.json` for the guard). Bench room (a free room,
     one author): every top-level entry that is not the orchestrator's, bound at each call (the root itself stays read-only: new
     top-level entries are created on the host; `calibration_report.json` is pre-created); no other host path, no docker socket;
   - per-agent areas: `/room/.tmp` (and `/room/simq` in the clean room) is a private read-only in-memory directory that holds only the
     caller's own `.tmp/<scratch>` (`simq/<scratch>`) bound read-write; other agents' directories are invisible (minor 4);
   - no bytecode in the room (`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPYCACHEPREFIX=/tmp/pyc`); pytest's cache provider is off in rooms
     with declared work areas; `src/` (the evaluator package on PYTHONPATH) is read-only, so no sitecustomize, shadow module or forged
     `.pyc` can be planted there;
   - `--network none` (loopback only), `--cap-drop ALL`, `no-new-privileges`, non-root uid 1000, read-only root file system, private
     in-memory /tmp; seccomp = Docker's default profile minus `symlink` / `symlinkat` (`docker/p4sandbox/seccomp_nolinks.json`);
     CPU / memory / pid caps (default 2 CPUs, 6 GB, 512 pids; per-room maxima), a per-command timeout (default 6 h).
   The wrapper the agent runs lives OUTSIDE the room (`C:\Dev\BrainIR_p4audit\sbx_bin\<room>\sbx`, first on the agent's PATH, NTFS
   protected); the room-root copy is read-only and never run (the guard refuses path spellings).
5. **Room builder** (`scripts/make_phase4_cleanroom.py`, `phase4/tests/test_room_builder.py`): names from the config (F-M1);
   the scanner described in 1.1; the in-room manifest holds paths, hashes and sizes only (F-B5); the scan reports every bytecode file
   or cache directory, Claude control file other than the root placeholders, nested `.claude`, sitecustomize / usercustomize module
   and `.pth` file anywhere in the room (agents' `.tmp` included), `--sync` records these reports and deletes bytecode and pytest
   caches outside the agents' `.tmp`; an OPTIONAL source that the scanner refuses is left out and reported (never copied); the
   review room gets the job guard `extra/scripts/devrun4_site/` and the placeholder names config, never the repository canary.
6. **Python audit hook** (`scripts/p4agent/pyguard`) for any host Python (defence in depth: host interpreters are refused).
7. **Permission deny rules** (second layer) for the main repository, every other p2 / p3 / p4 room (names from the config), the
   orchestrator's session / memory stores, credentials, the uv cache, file-history, paste cache, shell snapshots.
8. **Remote runner** (`scripts/p4/devrun4.py`; F-M7): every heavy / GPU development job runs in its OWN Modal Sandbox with NO network
   at all (`block_network`; the code tar goes in and the results come out through the sandbox filesystem API on the orchestrator
   side), no Modal credentials inside, one sandbox per job, the `brainir-p4-devdata` volume mounted READ-ONLY, NO repository code
   beyond the room's `src/`, `baselines/` and the requester's `runs/<prefix>/`; the job runs as an unprivileged user (uid 65534)
   with an environment built from scratch (no `MODAL_*`), owns only its work area, cannot read the sandbox runtime's environment
   (`/proc/1/environ` denied); its own Python processes are additionally guarded by `scripts/p4/devrun4_site` (no sockets, no other
   programs). One queue per developer (round 2, N-M2): `runs/<prefix>/_remote/`, the only runs/ subdirectory its sandbox can write;
   the daemon takes the prefix from the queue's directory, runs only scripts of that same `runs/<prefix>/` and packs only that
   developer's `runs/<prefix>/` (never a queue) into the code tar (`phase4/tests/test_devrun4_queues.py`). Measured on CPU and T4 GPU
   jobs, including a child interpreter WITHOUT the audit hook: DNS and TCP fail, no Modal
   client, data read-only, a 40 MB input and a 30 MB output transferred intact (`research/phase4/devrun4_isolation_smoke.json`).
   Modal Functions could not be used: with `block_network` or `restrict_modal_access` they cannot receive or return blob-sized
   payloads (measured). Every job is logged in `C:\Dev\BrainIR_p4audit\remote_runner.jsonl`.
9. **Simulation only through the budgeted service** (`brainir_causal.simclient`): method rooms contain no simulator code; the service
   refuses held-out and hidden-only families, non-public targets / edges / seeds / input ranges and truth events. In the clean room
   the sandbox exposes only `simq/<scratch>` of the calling agent (the client and the service must use that directory).
   CACHE ISOLATION (round 2, N-M1; `phase4/tests/test_simservice_isolation.py`): every token-identified agent has its OWN store
   namespace (`<store>/agents/<name>-<hash>/`): its requests read and write only there, so another agent's requests change neither
   the files a request touches nor its latency (review measurement: 3-5 ms for a trajectory another agent had asked for, 265-293 ms
   for a new one; after the change, paired re-measurement on the toy tier, same protocol for agent B on a service where agent A had
   asked for it and on one where nobody had, requests of about 250-270 ms: 3 x 40 pairs on a quiet host gave median differences
   -5.2, -1.7 and +4.0 ms (signs alternating, per-pair spread about 15 ms), 3 x 40 pairs on a loaded host +2.9, +15.7 and -28.0 ms
   (spread 90-150 ms); a first design that recomputed on a SHARED store with matched file operations still showed a systematic 5-12
   ms, from the Windows host's first-open cost of freshly written files, and was replaced); an agent's own repeats come from its
   namespace; public restart sources are recomputed into each namespace on first use; an agent's remote job (real full networks)
   neither reads nor writes the shared Modal volume store. Trusted in-process callers share the service store.
10. **Tournament feedback** (round 2, the F-M5 residue; `brainir_causal.feedback.release`, `phase4/tests/test_feedback_fm5.py`): the only
    release path: validation tier only, no override; every release is appended to `research/phase4/tournament/FEEDBACK_RELEASES.json`
    (outside every room; rounds, system-set fingerprint, file hash) and checked against it, so the cap of 4 DISTINCT rounds and the
    single system-set fingerprint hold across calls (a round released again must carry the same fingerprint; a round without a
    fingerprint is refused).
11. **Model workers within a phase** (round 2, N-m3; `brainir_causal.isolation.RemoteFresh`, `phase4/tests/test_isolation_memo.py`): a
    worker process keeps module state across the calls of one phase, so the driver keeps exact row digests of every history each
    worker process was given; a call whose history ends at a row that another history of the same process holds FOLLOWED by more
    samples (a longer history of the same trajectory, or a trajectory restarted from that state) is sent to a FRESH worker process
    (`worker_restarts` in the evaluation record). Calls in increasing onset order never restart; results are unchanged.
12. **Audits**: `scripts/p4agent/audit_transcripts.py` (names, paths and classes from the config; tool calls, forbidden paths /
    names, earlier answer-bearing artefact CLASSES in outputs, earlier answer tokens by class, web queries, guard denials, calls the
    current guard would deny) at every milestone; `make_phase4_cleanroom.py --check` / `--audit` per room (manifest, links, planted
    files, OS protection); the canary test (`CANARY_TEST.md`).
13. **Packed containers** (fork P1, 2026-09-26/27; `research/phase4/LEVEL_B_EXECUTION.md`; `brainir_causal.isolation.run_iso_packed`,
    `phase4/tests/test_pack_isolation.py`, `scripts/p4/smoke_pack_modal.py`): the packed iso classes run several isolated jobs AT ONCE
    in one container (Modal input concurrency). Each job runs in its own SLOT: a child driver (root, nondumpable) with the slot's own
    block of worker uids (`ROLE_UIDS + 20 * slot`, slots 1..32; slot 0 = the unpacked uids), its own group (20000 + slot; the slot's
    job directory is root:group 0710, so no other slot can even traverse it), and every worker in NEW user, network and IPC
    namespaces of its own (`setpriv --reuid --regid --clear-groups --no-new-privs` then `unshare --user --map-current-user --net
    --ipc`); clean-up kills and removes only the slot's own uids. WHY the namespaces are required: a Modal probe (2026-09-26, apps
    ap-IAVjHJ0KAFS2at13RVAJ8Y / ap-SDXKoPqnlCDWs0HjpteuCj) showed that two worker processes of DIFFERENT uids in one container reach
    each other through an abstract Unix socket, a loopback TCP port and a System V shared-memory segment (all three CONNECTED /
    ATTACHED), and that in separate namespaces all three are refused; root in Modal's gVisor cannot `unshare`, the unprivileged
    worker can (CapEff 0 inside). Packing FAILS CLOSED when the namespaces are unavailable (`isolation.namespaces_ok`). Adversarial
    evidence on the real packed path (ap-hAhT10kxpZ498E8Euqd0tg, 4 concurrent slots, the worker's tripwire OFF so only the OS
    boundary stands): distinct uids and distinct net / ipc namespaces per slot; every peer slot's abstract socket and loopback port
    refused and its shared-memory key absent; the driver's /proc/<pid>/mem denied; no network; /repo and /evalvol denied; no sibling
    job directory visible; no MODAL_* variable. Volumes: a packed container reloads each mounted volume ONCE per wave generation (the
    first wave before the lockdown; a newer wave drains the container's busy slots first, then reloads and locks down again); no job
    reloads per input (a per-input reload hid files from other slots: P2's report) and a payload-level commit request on a packed class
    fails loudly; workers cannot read or write the volumes in any case (0700 after the lockdown).
    WORKER UIDS (2026-09-27, P2's finding): every LIVE worker holds its own uid of the slot's block (before, all workers of one role in
    one job shared a uid, and a worker start killed the other models' workers); a start or a clean-up kills only its own uid, and a uid
    is reused only after its previous worker's processes, IPC objects and working directory are gone (after the lockdown a worker uid
    can write nowhere else), so a reused uid carries nothing between workers. A worker process that DIES is an infrastructure fault
    (restarted once, then the job fails loudly), never scored as the method's failed call. PRE-STARTED SPARE workers (after a phase's
    first digest-rule restart) run only trusted code until they are taken: the worker module, the environment's installed libraries and
    the tripwire; they receive the model only after the worker they replace is gone, so no method code of the new worker ever runs while
    the old one (which saw the histories) is alive, and the digest rule's guarantee (a restarted call reaches a process that has seen
    no history) is unchanged.
    NETWORK BOUNDARY UNCHANGED: every iso class, packed or not, stays block_network. On Modal's gVisor, `unshare --net` does NOT give a
    worker a clean namespace when the container has a network (eth0 persists; `isolation.namespaces_ok` found "eth0,lo" and failed
    closed, 2026-09-27), so the per-worker namespaces isolate slots from EACH OTHER inside a block_network container; the container's
    block_network keeps every worker off the network. `namespaces_ok` fails closed on any interface other than lo (read from the
    worker's /proc/net/dev) and on lo up where sysfs reports its flags.
    LARGE ARTEFACTS (Modal moves inputs / outputs above 2 MiB through its blob store, which block_network blocks): the trusted driver
    STAGES a fitted model, a large evaluation record or a large loop file through a mounted volume (`isolation.stage_blob` /
    `read_staged`, `Backend.stage_put` / `stage_get` / `stage_clear`):
    (a) the path is chosen by the DRIVER as the sha256 of the bytes it holds (`<root>/<sha[:2]>/<sha>.bin`), never from anything a
        worker names; a malformed ref never becomes a path;
    (b) content-addressed, and every reader verifies the sha256 before use;
    (c) by the data's class: fitted models (public training data only) on the STORE volume, evaluation records and loop files (derived
        from held-out data / the system's truth) on the EVAL volume, which fit containers never mount; a trusted iso "call" result (its
        class unknown) on the EVAL volume when the container mounts it, else on the STORE volume (a container without the eval volume,
        i.e. a fit class, holds public data only); both staging roots are under mounts the lockdown makes 0700 (directories 0700, files
        0600), so no worker of any slot or method can list or read them, and a driver reads only the ref its own payload names (incl. a
        call's input `model_refs`);
    (d) retention: the orchestrator removes a round's staged artefacts once it holds them (`stage_clear`, recorded in ROUND.json);
        an interrupted round's leftovers are content-addressed, unreadable to workers, and removed by the next clear;
    (e) evidence: `scripts/p4/smoke_stage_modal.py` (a > 2 MiB model through fit then evaluation on a packed and an unpacked class;
        a small model forced through staging equals the inline path bit for bit), `phase4/tests/test_pack_isolation.py`.
    Probes (2026-09-27): a block_network container writes, commits and another reloads and reads a 3 MiB file intact; commit and reload
    leave a 0700-locked mount at 0700 (they do not remount), so a slot's staging commit does not disturb the other slots.

## 3. Modal

- Phase 4 volumes only: `brainir-p4-devdata` (copy of the clean room's `data/`), `brainir-p4-fit` (public fit views, method
  snapshots), `brainir-p4-eval` (validation / confirmation truth, hidden data; mounted only by evaluation containers, never by fit or
  development containers).
- NEVER mounted by any Phase 4 container: `brainir-p3-eval` (Phase 3 hidden data, answer-bearing), `brainir-p3-fit`,
  `brainir-p3-devdata`. `devrun4.py` refuses any volume that is not `brainir-p4-devdata*`.
- No agent has Modal access; the orchestrator mediates every job.
- The container-start numerics self-test of the gated classes (`p4modal/selftest.py`; LEVEL_B_EXECUTION.md section 9) runs trusted
  code only, as root, before the container's first input and in its own processes; it reads no job input, volume or bundle, and its
  generator item builds systems of a tier name no suite uses ("selftest"), so it touches no benchmark system. Its reference
  (`p4modal/numerics_reference.json`) holds sha256 hashes of fixed-seed computations and host classes only.

## 4. Residual risks (stated, not hidden)

- The Claude sessions themselves are not containerised: an OAuth refresh inside a container would rotate the host's refresh token
  and could log the orchestrator out (Phase 3 decision P3-D2). Their tool calls run on the host under the guard; only the code they
  execute runs in Docker.
- The guard is not a kernel sandbox: it reads command text. An allowlisted host tool with an unforeseen execution or write feature
  could escape it; the allowlist is small, the known write / execute options are refused, file arguments must be literal, and the
  NTFS deny ACEs are the OS-level backstop for every protected path. Transcripts are audited afterwards.
- NTFS owner rights: the OWNER of a file keeps an implicit WRITE_DAC, so a process of the same Windows user that is NOT under the guard
  could remove the deny ACEs (icacls, Set-Acl, a Python / .NET program). Room agents have no such process: host interpreters and ACL
  tools are refused by the guard (tested), and code in the Docker sandbox cannot edit NTFS ACLs (tested). `--check` detects a removed
  ACE. WRITE_DAC is deliberately not denied: where an OWNER RIGHTS ACE is inherited (directories Python creates with mode 0o700), a
  denied WRITE_DAC locks the builder itself out (measured; two such test directories in %TEMP% need an elevated `takeown` to delete).
- Membership oracle (F-M2): the refusal messages are generic (class and event id only), but allow / deny itself still tells an agent
  whether an input matches one of the forbidden patterns. The patterns name only public datasets, the earlier circuit and earlier
  artefact names, none of which is answer-bearing on its own.
- Agents sharing a room READ each other's subdirectories of the owned areas (`runs/`, `notes/`, method packages, tests, reviews) by
  design; writing them is refused by the sandbox mounts and the guard (round 2, N-M2). A file at the ROOT of an owned area (the
  earlier flat layout, e.g. `runs/x.py`) is read-only for every agent: agents work in `<area>/<scratch>/`. Host Grep / Glob over the
  room root can list another agent's `.tmp` content (the guard refuses explicit paths into it; the sandbox does not show it at all)
  (minor 4). A container can create a nested CLAUDE.md in its own subdirectory; the guard then refuses reads below it (G9) and
  `--check` / `--audit` report it. The Windows ACLs cannot tell agents apart (one Windows user): between agents, the owned areas
  are enforced by the sandbox mounts and the guard only.
- The simulation service still shares its CPU and its bookkeeping (one worker pool; the ledger and served-key files are rewritten
  per request and grow with every agent's use), so a busy service answers more slowly: another agent's activity level, not its
  protocols; and its worker processes' in-memory caches (generator systems are built at start; a parameter draw that
  another agent's request just made in the same worker process may be reused: at most the cost of one parameter draw, not measured
  separately). Inside its own container an agent can print its own token (`sbx env`); the token is valid only through its own queue.
- The runguard tripwire inside model workers is reachable through the garbage collector (review F round 2, N-m2): it is a tripwire
  only (defence in depth, EVAL_ARCHITECTURE section 7); the boundary is the OS one (a fresh unprivileged uid per role and phase,
  container lockdown, no network; in a packed container also a uid block and group per slot and per-worker user / network / IPC
  namespaces, section 2.13), exercised adversarially by `phase4/tests/test_eval_isolation_docker.py`, which must stay in the
  test runs on the pinned image, and for packing by `scripts/p4/smoke_pack_modal.py --mode isolation` on Modal.
- Packed containers (section 2.13) share CPU, memory bandwidth and caches between concurrent slots, and a packed GPU class shares
  one GPU between its slots' fit workers (separate CUDA contexts): timing / contention covert channels of low bandwidth remain,
  of the same kind as co-tenancy on a shared host; a GPU slot only ever holds public training data (fits). Other processes'
  command lines stay visible in /proc (they carry no data: the child drivers get their payload through root-only files).
- The within-phase restart rule (section 2.11) matches exact rows; histories that end in a constant row (e.g. a silent unit
  pattern) or at their own first row are not tracked, and a model could still recognise an approximate match (not the same samples)
  of another history.
- The free bench room gives its single author read-write access to its own top-level entries in the sandbox; only the orchestrator's
  entries are protected.
- A frozen earlier-baseline file (`baselines/brainir_state_v1/brainir_state/evaluate.py`, hash-locked, imported by the locked v1)
  carries one scanner hit (a docstring path to an earlier review directory); it is the only exemption, listed in the names config
  (`FROZEN_CONTENT_EXEMPT`) and tracked here (minor 9).
- `kill <pid>` stays allowed on the host for explicit process ids > 1 (agents stop their own background jobs); it could stop another
  process of the same user whose id the agent guesses.
- Recall from training: agents may know published literature about the Phase 1 circuit; rooms contain no dataset, circuit or paper
  names, and web queries about them are refused.
- The orchestrator (answer-aware) writes the evaluation, the real-system protocol families and the interfaces. They follow goal5's
  generic text; no target, family or threshold is chosen by knowledge of a Phase 3 hidden outcome; reviews F (leakage) and E
  (statistics) audit them.
- Early-review exposure (transcript audit 2026-09-26T2140Z, research/phase4/audits/): reviewers F and H saw the NAMES (not the
  contents) of earlier-phase artefacts in the pre-fix in-room manifest's refusal list (fixed since: the in-room manifest holds only
  paths, hashes and sizes, and names live only in the orchestrator's config). Reviewers are not developers and never enter the clean
  room; no content of an earlier answer-bearing file reached any Phase 4 agent. The synthetic author's stream was clean.
- The literature agent (`p4lit`) was started at 10:06 local, before the Phase 4 stack existed, with the reviewed Phase 3 stack
  (`scripts/p3agent`, guard v2, web filter) in its own room with only its contract; it needs no code execution. Its later audit
  (`audit_transcripts.py`) shows 1 guard denial (a network command) and no forbidden output.

## 5. Operating rules

- Never rebuild a sandbox image tag in place: build a new tag, then `--sync` every room (a rebuilt tag deletes the previous image,
  which rooms reference by id; incident 2026-09-26 10:52, fixed by syncing the bench room within minutes, no failed agent call).
- Rooms change only through the builder (`--build`, `--sync "<reason>"`, `--destroy-and-rebuild`): the NTFS ACEs block hand edits of
  protected paths, and the builder lifts and restores them. Run `--check` after every sync and before every agent launch round.
- Build the clean (method-development) room only after the benchmark freeze. The review room is built BEFORE the freeze for the
  early reviews E, H and F of the evaluation machinery (reviewers develop no method; the room follows the p4review allowlist and the
  refusal list, so no hidden record, salt or truth of the validation / confirmation tiers enters it) and synced for later rounds.
  Sync generic files one by one with a logged reason.
- Every name the isolation stack needs goes into `scripts/p4config/names.py` only (never into code, tests or contracts that enter a
  room); `phase4/tests/test_guard_p4.py` and `test_room_builder.py` fail when room-bound code carries a name.
- Launch agents whose prompts name a scratch directory with `--scratch <dir>`; prompts and room CLAUDE.md files say "run code with
  the bare command `sbx`" (never `./sbx`) and "scratch files under $TEMP (.tmp/<scratch>)". Developers are launched with
  `--scratch <prefix>` (the prefix of their assignment) and reviewers with `--scratch <letter>`: the scratch name is the agent's
  subdirectory of every owned area (`src/brainir_causal/methods/<prefix>/`, `tests/methods/<prefix>/`, `runs/<prefix>/`,
  `notes/<prefix>/`; `reviews/<letter>/`), its simulation queue and token file and its remote-runner queue.
- Rooms built before isolation v4 must be `--sync`ed before the next launch round (new sandbox wrapper with the owned areas, the
  protected record with `owned_areas`); legacy flat files at the root of an owned area are moved into their owners' subdirectories
  by the orchestrator (they are read-only for the agents).
- Start each room's simulation service with the launcher's token table (`--tokens C:\Dev\BrainIR_p4audit\simservice\<room>\tokens.json`;
  `scripts/p4/simservice_docker.py start` does this) and a ledger directory outside the room.
- Tournament feedback goes out only through `feedback.release()` (the tournament's `feedback` command); never edit
  `_tournament_feedback.md` or `FEEDBACK_RELEASES.json` by hand.
- A source that `--sync` reports as REFUSED (optional items are left out, e.g. data whose records carry a forbidden word) is fixed at
  the source before the next sync; never whitelist it in the scanner.
- Run `--audit` for every room and `audit_transcripts.py` at every milestone (before each tournament round, before the lock, after
  the hidden evaluation) and keep the reports.
- Guard refusals: agents report `[G<n>-<event id>]`; look the event id up in `C:\Dev\BrainIR_p4audit\guard_<agent>.jsonl`.

## 6. Phase 4 answer-bearing material (never into any room; the builder refuses it)

Before the lock: `research/phase4/PLAN.md`, `research/LOG.md` section 12, validation and confirmation truth, the salt, internal real
system records and the name map (`benchmarks/causal_state_v1/hidden/`), per-system tournament scores beyond the published aggregates.
After the lock, in addition: `PHASE4_REPORT.md`, `research/phase4/HIDDEN_EVALUATIONS.md`, every hidden-evaluation output, the
post-lock reviews, the hidden data (`data/phase4/hidden/**`), the eval volume `brainir-p4-eval`.
