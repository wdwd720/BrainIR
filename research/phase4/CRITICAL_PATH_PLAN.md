# Phase 4 remaining work: critical-path plan (orchestrator only; 2026-09-27, user directive "minimum wall time, zero shortcuts")

Rule: nothing below weakens or reorders a barrier. The order FREEZE -> clean room -> developers -> Level B -> composer -> pre-lock
reviews -> METHOD LOCK -> hidden data -> Level C is fixed; reviewer fixes, statistics and final verification are complete. What is
accelerated is everything BETWEEN the barriers: independent work runs concurrently, compute runs on Modal on the largest useful
resources, downstream drivers are built and dry-run before their inputs exist, and long-tail jobs are scheduled first.

## 1. Constraints that shape the schedule
- Modal workspace: about 100 concurrent containers (Phase 3 measurement; re-measured by P1). Parallelism beyond 100 jobs comes from
  PACKING: several isolated jobs per large container (up to 32 CPUs / 128 GB CPU classes; one or more fits per GPU), each job in its
  own model worker (own uid, own private directories), longest expected job first.
- Local machine (28.7 GB RAM, Docker 14 GB, shared with the user's own services): orchestration, git, agent sessions and their small
  sandboxes only. Test suites and simulations run on Modal (or at bounded local concurrency); agents' heavy work goes to the remote
  runner (Modal CPU / GPU classes).
- Official numerics on the reference platform only (P4-D32). CPU references stay on CPU (validated configuration; bit-reproducible);
  GPU is used where it is faster AND scientifically equivalent (method fits declaring cuda: RTX-PRO-6000 default, B200 / H100 / H200
  for throughput-bound training per the profile; CPU / GPU equivalence per equiv.py).

## 2. DAG (estimates are wall time with the planned parallelism)

Stage 0: pre-freeze (critical path marked *)
- N1* generator revision (author, bench room) .................................................. in progress (1-3 h)
- N2* integrate the generator: `integrate_generator.py` (diff, refusals, atomic copy, delivery hashes), its tests sharded on Modal
      (`modal_pytest.py --suite generator`: 222 tests in 3 min), the adapter tests ............... 15 min <- N1
- N3* rebuild dev + val concurrently (in-image planning, Modal builds, build manifests) ........... 30-40 min <- N2
- N4  criterion 11 vs targets v3, one Modal container per system .................................. 10 min <- N3
- N5  tolerance calibration, split per (system, reference) on large classes ....................... 15-30 min <- N3
- N6  active-design MDE, loops PACKED (8 per 32-CPU container, all 576 in one wave) .............. 20-30 min <- N3
- N7  dev public download (6+ parallel streams) ................................................... 40 min <- N3 (overlaps N4-N6)
- N8* round-3 reviews in parallel: E (now; calibration / MDE outputs as a follow-up), H (now; generator / data follow-up),
      F (done; re-checks the generator's public fields after N2), T (after N2 / N3) ............... 2-3 h
- N9* fixes of round-3 findings (parallel forks by ownership), re-verification ................... ?
- N10 freeze preparation in parallel with N8: PROTOCOL final pass, public docs, merged public records, pilot subset from the final
      val tier, full test suite (`modal_pytest.py --suite phase4`, ~4 min sharded, + the HOST_ONLY files on the Windows host),
      Phase 1-3 lock checks, room audits, transcript audit (faithful guard replay) ................... 1 h
- N11* FREEZE: build manifests + --verify-local, commit, freeze_benchmark_p4.py --write, commit, tag

Prepared during Stage 0 (off the critical path; each must land before its consumer):
- P1 Level B execution at scale (packing, longest-first, profiling, GPU class choice, resume): before FREEZE (it touches hashed
     execution code; results must be bit-identical to the unpacked path on a dry run)
- P2 Level C driver end to end (hidden-data generation guarded by the lock, fits + 5 bootstrap refits, evaluation, loops, LOIO /
     LOImplO, OOD / robustness, primary family, conclusion, START / DONE log), dry-run on the dev tier with stand-in models: before
     LOCK (hashed by the method lock)
- P3 ablations (goal5 87-89), counterexample search (84, 91), robustness sweeps (75), counterfactual API evaluation (90), self-audit
     tests (91), drivers dry-run on dev with stand-ins: before LOCK
- P4 contracts: pre-lock reviews A-D, G (new trap families after composition), composer, review I, developer prompts: before FREEZE
- P5 clean-room operations: devdata volume seeded server-side (devdata_seed.py), devrun4 daemon, service worker container, launch
     runbook: ready at FREEZE

Stage 1: post-freeze, pre-lock
- M1 build the clean room (16 GB data) .......................................................... 30 min <- FREEZE
- M2 services: simulation service (Docker worker), remote runner daemon, devdata verify ............ 15 min <- M1
- M3 eight developers (li, sy, nn, od, ko, is, ad, bl) through the runbook's MEMORY-GATED QUEUE (at most 4 sessions alive, the
     next only with >= 8 GB free; LOG P4-D64), all sharing the machine's ONE sandbox slot; every fit / sweep / evaluation on the
     remote runner (GPU classes allowed) ........................................................... 6-12 h
- M4 Level B: pilot (25 val + 3 real mechanisms) -> medium (50 val + 7 mechanisms) -> finalists (top 3 + best baseline) -> full
     (all val + all real, 3 seeds, active-design curves); every round PACKED on Modal (~30-60 min each), feedback between rounds
- M5 composer (I, J) ............................................................................... 2-3 h
- M6 pre-lock reviews A, B, C, D, G and E / H follow-ups in parallel; fixes .......................... 2-3 h
- M7 METHOD LOCK (METHOD_LOCK.json, tag brainir-causal-state-v1-preblind)

Stage 2: post-lock (each hidden run logged START / DONE)
- L1 conf tier + real Level C sets from the salt, in parallel on Modal ............................ 30-45 min <- LOCK
- L2 Level C evaluation, packed .................................................................. 1-2 h <- L1
- L3 ablations, L4 counterexample search, L5 robustness sweeps, L6 counterfactual API, L7 self-audit: concurrently with L2
- L8 review I + post-lock verification in parallel with the report draft; L9 compute summary, final tag

## 3. Scheduling rules
- Longest-tail first inside every campaign: real full networks and large synthetic systems, GPU fits and loops start first.
- Stage data once: dataset parts stay on the volumes where the builds wrote them; images are prebuilt per campaign; method snapshots
  are uploaded once (content-addressed); references are fitted once per system and round and cached.
- Every campaign writes its manifest and cost record; failures are retried as infrastructure only when the error is an
  infrastructure error (preemption, refused host), never on a scientific failure.
- Agents (developers, reviewers): the user's local-resource rule (2026-09-27) holds ONE agent sandbox at a time on the PC. Since
  2026-09-28 the sandbox wrapper enforces it for every room: one machine-wide slot, a sandbox starts only with >= 4 GB free, sbx
  waits up to ~9 min and exits 75, orphaned containers of killed tool calls are stopped (scripts/p4agent/sbx_template.sh;
  phase4/tests/test_sbx_machine_slot.py). Reviewers run one at a time; developers through the runbook's memory-gated queue
  (launch_clean_room.py --max-sessions 4 --min-free-gb 8; phase4/tests/test_launch_queue.py); heavy work remote.
- Long Modal drivers run in the LINUX driver container (LOG P4-D54): Modal clients on the Windows host die of system-wide
  socket-buffer exhaustion (WinError 10055) when several run at once, while sockets inside the Docker VM do not use the Windows
  buffers. `uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run|start scripts/p4/<driver>.py [args]` runs a
  driver in `brainir-p4-driver:1` (docker/p4driver; the phase4 lock's third-party environment, git, the docker CLI; image record
  docker/p4driver/image.json). The repository and C:\Dev\BrainIR_p4run are mounted read-write at the paths the Docker Desktop
  daemon uses (so nested `docker run -v` from a driver, e.g. the in-image planning of build_on_modal.py, resolves), the Modal
  credentials read-only, and the Docker socket. `start` is detached and writes data/phase4/driver_runs/<name>/{run.json, log.txt,
  exit_code}; `status`, `logs` and `stop` follow it. Windows-only tools are refused (the room builder, launch_clean_room.py,
  devrun4.py, simservice_docker.py, prefreeze_check.py, the agent launcher and audit). So is any driver whose own source still
  hard-codes a C:/Dev/BrainIR_p4* root, and the image refuses every write through a Windows path at run time. Such a driver must first
  read its root from P4_RUN_BASE (also exported as P4_RUN_ROOT; rooms mounted with --extra-mount are exported as P4_ROOM_CLEAN /
  P4_ROOM_REVIEW / P4_ROOM_BENCH).
- TEST PLACEMENT (the user's local-resource rule, 2026-09-27: the PC holds ONE agent sandbox plus orchestration). Every test file that
  can run equivalently on Modal runs there, sharded (`scripts/p4/modal_pytest.py --suite phase4|generator`, launched through
  `linux_driver.py run --memory-gb 2`). The toy-tier build tests use a hermetic test salt (phase4/tests/_hermetic.py; the real salt
  never leaves the host), the Level C driver tests an injected git, the generator-pool tests the spawn start method on every
  platform, and the shipped-targets identity a relative 1e-12 against C-library last-bit differences. Only the truly host-bound files
  stay in modal_pytest.HOST_ONLY: the Windows guard / room / ACL tests, the local Docker sandbox tests, and the bit-identity tests
  against the earlier engine's hidden records. They run ONE AT A TIME, after the running agent session has finished, through
  `scripts/p4/host_tests_guarded.py`. It waits for >= 8 GB free RAM and no running agent sandbox, kills a run whose free RAM falls
  below 6 GB ("interrupted by the memory guard": never a pass, rerun later), and writes one JSON record per file under
  research/phase4/host_tests/<run>/.
