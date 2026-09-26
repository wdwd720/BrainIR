# Phase 3 compute ledger (goal4 section 59)

Modal list prices used for the estimates: $0.192 per physical core-hour and $0.024 per GiB-hour. Containers have 2 cores and 6 GiB.
The per-job container seconds come from the jobs' own records: `modal_costs.json` per round, and the run logs.

## Modal

| time (PDT, 2026-09-25) | job | app | calls | container-s | ~USD |
|---|---|---|---|---|---|
| 02:48 | calibration smoke, 3 dev systems (first attempt crash-looped: module-level function pickled by reference; 0 containers ran) | ap-xAUUZwyI8kIuFXeNwWhN3n | 0 | 0 | 0.00 |
| 03:05 | calibration smoke, 3 dev systems (v2 code; Linux = Windows to ~1e-9) | ap-xxcC5GxuzBO5OuTwgwTJBH | 3 | 960 | 0.14 |
| 03:15 | CALIBRATION v2, 45 dev systems | ap-E6MBnFZtNmPTE89nrkCTdY | 45 | 14,303 | 2.10 |
| 03:50 | heldout suite extract (tar upload) | ap-IZtRekngNaKzQC5KTQsGZY | 2 | 57 | 0.01 |
| 04:00 | heldout reference controls (k-independent + k = 1), 48 systems | ap-nVT8iyPgdqMw9Ny79fCVGV | 48 | 9,242 | 1.36 |
| 04:05-04:40 | dev-suite smoke tournaments (2 failed attempts found two backend bugs, then a full run: lin_pcadyn, lin_dmdc with G and shared fits) | ap-a1a8RKTA2dmKo4MDM2UMSE, ... | ~560 | ~22,000 | 3.43 |
| 04:15 | final suite extract, fit views, review G suite upload | several | 6 | ~200 | 0.03 |
| 08:40-10:00 | Level B round 1 (pilot, 19 methods; 5 developer parts in parallel) | r1_* | 727 | 76,727 | 11.26 |
| 10:10-11:20 | Level B round 2 (10 survivors, full heldout, G, sharing, LOIO; 10 parts in parallel) | r2_* | 2,276 | 179,718 | 26.36 |
| 11:20-11:55 | review G trap suite, round-2 top five | review_g | ~150 | 11,386 | 1.67 |
| 14:00 | Level B round 3 attempt 1 (brainir_state_v1, benchmark v2) | r3_brainir_state_v1 | 215 | 13,972 | 2.05 |
| 14:10 | review G trap suite, brainir_state_v1 | review_g | ~30 | 1,261 | 0.18 |
| 15:05 | CALIBRATION v3, 45 dev systems (benchmark v3; 486 s wall) | ap-3gPG4qSgSn1dl4e0SJGCd9 | 45 | 13,417 | 1.97 |
| 15:20 | kick-clip lists staged on the eval volume (3 files) | CLI | 3 | 0 | 0.00 |
| 15:25-15:45 | calibration v3 re-runs 2 and 3 (worker crashes; not used: the calibration of record is run 4) | ap-BVqx..., ap-vjS4..., ap-XrYq... | 94 | 26,700 | 3.92 |
| 15:40-15:55 | hidden-data generator: Modal pipeline smoke tests on PUBLIC protocols (4 runs incl. 2 failed attempts) | ap-kvch... and others | ~40 | ~600 | 0.10 |
| 15:52-16:05 | numerics-pinning crash experiment (4 variants x 4 systems x 5) | ap-9iV3e4VAPveQwgf92HrrGo | 76 | 22,484 | 3.30 |
| (forks) | fork A: Level C backend staging and equivalence checks; fork C: counterexample / ablation smoke tests | several | ~100 | ~2,300 | 0.33 |
| 16:54-17:55 | remote runner (`devrun.py`) for the composer's development experiments: 190 jobs in classes small (2 CPU / 8 GiB, 72), medium (4 / 16 GiB, 114) and large (8 / 32 GiB, 4) + 2 orchestrator smoke jobs; priced per class | brainir-p3-devrun | 192 | 48,200 | 14.34 |
| 09-25 22:5x | post-lock verify-public of the ungated Modal generator path (13 of 20 public records not bit-identical) | brainir-p3-tournament | 20 | 154 | 0.02 |
| 09-25 23:0x | gated verify-public, exit mode (60 of 60 identical; throttled scale-up) and refuse mode (60 of 60; 99 refusals), 32 GiB | brainir-p3-tournament | 219 | 2,053 | 0.66 |
| 09-25 23:13-00:29 | HIDDEN real-data generation, host-gated (420 simulation batches, 60 microstate batches, assembly; 32 GiB, about 30 containers). Its cost record was lost (the run stopped at the looping tar call); estimate from wall time x containers: about 36,000 container-s | brainir-p3-tournament | ~2,500 | ~36,000 | ~11.5 |
| 09-26 00:0x | quota probe (sleeper containers; the workspace ran 99 at once) | brainir-p3-quota-probe | ~200 | ~15,000 | ~0.8 |
| 09-26 00:2x | hidden data finish (frozen tar, remote hashes) and re-simulation determinism check (83 protocols) | brainir-p3-tournament | 50 | 685 | 0.10 |
| 09-26 00:0x-00:3x | fast Level C dispatcher validations on public data (frozen vs fast; gated repeats; 16 fits) | brainir-p3-levelc-fast | ~60 | ~2,600 | ~0.6 |
| 09-26 00:30-02:04 | correction for the real Level C run: its record prices every container at 2 cores / 6 GiB; at the actual class sizes (4 cores; 16 / 32 / 128 GiB fits, 32 GiB evaluations) the run cost about $42.2, i.e. $31.0 more (container time already in the record, so 0 here) | brainir-p3-levelc-fast | 0 | 0 | 31.0 |
Running total so far: about **$58.3** (Modal list prices; container-seconds from the jobs' own records).

The per-round records are `research/phase3/tournament/*/modal_costs.json`. Parallelism: each round's methods ran as independent Modal
apps at the same time (up to 100 containers per app); a round's wall-clock time is that of its slowest method (round 1: 74 min, the
nn part; round 2: 70 min, nn_aelin).

## Local

- **Machine.** Ryzen 9 6900HX, 8 cores / 16 threads, shared by the method agents; wall-clock only.
- **Version 1 calibration.** 75 min on 7 workers (superseded).
- **Suite builds.** Synthetic suites and pools about 40 min; real public data about 40 min on 12 workers.
- **Root test suite.** 834 s under agent load.
