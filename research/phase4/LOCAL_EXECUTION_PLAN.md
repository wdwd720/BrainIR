# Phase 4 without further Modal spend: local execution plan (orchestrator; 2026-09-28)

The user's directive (2026-09-28): the Modal budget cannot be raised. Finish Phase 4 with ZERO additional Modal spend and WITHOUT
reducing scientific quality, tests, reviews, seeds, evaluations, hidden-evaluation integrity or acceptance criteria. Reuse every
cached Modal output; run heavy work locally, memory-safe (one memory-heavy job or sandbox at a time, capped workers / RAM, about
6-8 GB of free RAM kept, checkpoint / resume); optimise execution only (never the science, the benchmark, locked rules, thresholds
or the evaluation protocol). If a required step truly cannot run on this machine, exhaust the safe optimisations first, then stop
and report exactly which single task, its RAM / compute requirement and why.

## 1. The machine

- AMD Ryzen 9 6900HX (Zen 3+, 8 cores / 16 threads, no AVX-512), 28.7 GB RAM, no CUDA GPU. Docker's VM: 16 CPUs, 15 GB cap.
- Free RAM with one agent session and its sandbox running and the user's own applications open: 2.5-8.4 GB (measured 2026-09-28).
  The memory budget of a heavy job is therefore about 2-4 GB (free RAM minus the 6 GB floor); it must shrink when the user's
  own use grows. Heavy jobs run under a memory guard (pause new units below 6 GB free, stop the youngest unit below 4 GB, resume).
- REFERENCE PLATFORM, verified 2026-09-28: the numerics self-test (p4modal/selftest.py, 15 items) run in the pinned images
  brainir-p4-simsvc:1 and brainir-p4-driver:1 on this CPU equals the Modal reference (numerics_reference.json, built on Modal
  Zen 3 hosts) bit for bit, 15 / 15 (brainir-p4-sandbox:1: 14 / 15, the real engine's duckdb is not in that image). The host passes
  the gate's flag rule (AVX2, no AVX-512). So every official computation run locally in these images gives the numbers Modal
  would have given; the benchmark's records stay bit-reproducible.

## 2. Cached Modal outputs (readable at no compute cost: volume reads start no container)

- Reusable (independent of the synthetic generator): the real public data (already local, data/phase4/real/real_public), the real
  Level B sets (eval volume data/real/real_levelb), the real systems' records in the store volume (store/), the real systems'
  internal records. Downloaded once into the local volume directories (section 3).
- Obsolete after the generator revision v3.3 (every synthetic system changes: new moderate magnitudes, controls accepted by the
  simulated margin): the v3.2 dev / val tiers on the volumes, the 33 calibration fits in data/phase4/calibration_resume, the
  v3.2 review subset. They are kept for the record and never used for a v3.3 result.

## 3. Local execution design (execution only; results identical)

- LOCAL VOLUMES: C:\Dev\BrainIR_p4run\vol\{fit,eval,store} mounted at the containers' volume paths (/fitvol, /evalvol, /storevol), so
  the planned jobs (plan_remote_job, jobs.json) and every driver's paths work unchanged.
- LOCAL BACKEND: the drivers' Modal backend is replaced by a local one with the same interface. It executes the SAME container-side
  entry point (`p4modal.remote.dispatch(payload)`) in worker processes inside the pinned Linux image, after the same gate and
  numerics self-test; volume reload / commit are no-ops on local directories. Only orchestrator payload kinds (call, sim, tar_dir,
  hashes, fetch, extract) before the freeze; isolated method payloads (iso) after it (section 5).
- MEMORY-SAFE SCHEDULER: one heavy job at a time; a unit queue (one system build, one reference fit, one checkpoint task, ...)
  run by N worker processes, N and the thread count chosen from the unit's measured peak and the current free RAM; longest
  units first; every finished unit written to disk at once (resume skips it); a memory guard as above.
- Execution optimisations allowed: batching, caching of evaluation contexts, reuse of identical work (content-addressed store),
  BLAS / thread settings measured per unit kind, avoiding duplicate dataset generation, incremental test runs. Never: fewer seeds,
  systems, items, loops, designers or reviews; never another algorithm, threshold or rule.

## 4. Remaining work and its local cost (Modal measurements; refined with local timings as each stage runs)

| stage | work (measured on Modal) | local estimate | status |
|---|---|---|---|
| author revision v3.3 (N7, N8, NEW-8, spread scope) | agent + one sandbox | hours | running |
| integrate v3.3; plan dev / val in the pinned image | light | minutes | - |
| build dev + val (100 systems) | per system ~285 s wall on 32 workers | ~1-1.5 days | - |
| download real Level B sets + real store records | volume reads | hours | - |
| criterion 11 (dev) | per-system statistics | hours | - |
| tolerance calibration (46 compressible dev systems) | ~400 reference jobs, mean ~1,280 s on 4 threads | ~2 days | - |
| active-design MDE (576 loops, 2,880 checkpoint tasks) | ~909 task core-hours; ~3.4 GB per concurrent task incl. page cache | ~6-10 days (memory-bound: 2-3 tasks at once) | - |
| phase4 + generator test suites, host-only tests | sharded on Modal before | ~1 day, one file at a time | - |
| reviews T (delta), E (final); resolution map; freeze | one sandbox at a time | ~1 day | - |
| developers (8 families) | their heavy runs went to Modal GPU / CPU classes | weeks (one heavy job at a time) | - |
| Level B: pilot, medium, finalists | ~430 slot-hours per round (4-CPU slots) | ~1-2 weeks per round | - |
| Level B: full round with active-design curves (PROTOCOL 10 / 5.17) | ~4,300-4,900 loops + ~24,000 checkpoint evaluations, ~15,000 slot-hours | many months | see section 6 |
| Level C (confirmation, loops, refits, LOIO, OOD / robustness) | 15,884 jobs, 1,382-6,019 slot-hours | ~3 weeks to ~3 months | see section 6 |
| post-lock studies (ablations, counterexamples, robustness, counterfactual API, self-audit) | ~195-270 4-CPU container-hours | ~1 week | - |

## 5. Isolation of method code without Modal (post-freeze)

Level B / C evaluate method code in isolated workers (own uid, user / network / IPC namespaces, block_network). Locally the same
isolation layer runs inside a Docker container of the pinned image with no network; the driver stays trusted. Its local
equivalent is validated (the isolation smoke tests) and reviewed by F before any method runs.

## 6. Feasibility

Everything up to and including the freeze, the developers and the first Level B rounds is feasible here, slowly. On the Modal
measurements, the Level B full round with active-design curves and Level C at the protocol's scale need thousands to tens of
thousands of core-hours with 2-4 GB per concurrent unit; at 2-3 concurrent units on this machine that is many months. The
statement of which single task is infeasible, with its measured requirement, is made when the local timings of the earlier stages
(and every safe optimisation) are in: this section is updated then, before any time is spent on it.

## 7. Storage: private Hugging Face Storage Buckets (the user's directive, 2026-09-28)

The disk has ~36 GB free; the v3.2 tiers measured dev 44.6 GB (public 13.0, eval 13.3, truth 18.4) and val 25.4 GB, and later
stages need more. So large rebuildable / intermediate data live REMOTELY and the PC keeps only the active working subset.
- Buckets (private, created 2026-09-28 under the orchestrator's own login; mutable object storage, not a Git repository):
  `wdwd720/brainir-p4-public` = ONLY material that may enter a room (dev public part, public real data, their archives);
  `wdwd720/brainir-p4-heldout` = everything else (val / conf, eval and truth parts, real Level B / C, store records, run outputs).
  `scripts/p4/remote_store.py` chooses the bucket from the prefix and refuses a held-out prefix in the public bucket; agents never
  get a token and rooms still receive data only through the room builder, so remote storage widens no access.
- Verification before deletion: local SHA256 + Xet content hash of every file; after upload the bucket's size and Xet hash of every
  path must match (round-trip test 2026-09-28: local Xet hash == remote Xet hash, SHA256 equal after download); a manifest
  {path: [sha256, bytes, xet]} beside the data and under research/phase4/remote_store/. `--evict` deletes local files only when every
  file verified. Pulls check SHA256 against the manifest. Xet stores content by hash, so identical bytes are never uploaded twice.
- Streaming: tiers are built in batches of systems (build_on_modal.py synthetic --systems, local backend), each batch pushed,
  verified and evicted before the next; per-system downstream jobs (criterion 11, calibration fits, MDE loops, Level B / C jobs)
  pull their system's parts into a small local cache, write their outputs, push, and evict. Build manifests (SHA256 per file) stay in
  the repository and in the lock, so a pulled copy is checked against the hashes taken where the data were written.
- Build store records (LOG P4-D73): a system's build also publishes its full simulation records (1.2-5.6 GB per system, 50-150 GB
  per tier) to the local eval store. They are NOT pushed: neither the disk nor the bucket holds them, and at the ~3 MB/s uplink a
  download is as slow as a rebuild. `scripts/p4/stream_tier.py` runs batches of 3 systems with a disk guard (>= 22 GB free before a
  build) and deletes a batch's records (`evict_store`) only after its build, criterion 11, calibration, MDE and the verified push
  succeeded. A later stage that needs a system's records (tournament rounds, Level C) rebuilds that system and checks the rebuilt
  files against its build manifest first.
- Docker VM page cache (LOG P4-D72): `scripts/p4/local_cachedrop.sh` runs beside the memory feeder and drops the VM's clean page cache
  when the host has < 7 GB free.
