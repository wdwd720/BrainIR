# Level B execution at scale on Modal (fork P1, 2026-09-26/27)

Scope: run the Level B tournament (and the tolerance calibration) at the smallest wall time on Modal WITHOUT changing any result.
Execution only: E15's selection semantics, the evaluator, the reference learner and the statistics are untouched. Everything below
is measured unless marked "projected". Modal runs and their costs: `MODAL_RUNS.md`, section "Fork P1".

## 1. Workspace limits (measured)

| what | measured | how |
|---|---|---|
| containers at once, workspace-wide | **~100** (90 CPU + 10 GPU when both kinds compete) | 300 x 0.25-core sleep jobs + 24 per GPU class at once (ap-OJG7JS1EeYefgmzZ1GngsI) |
| GPU containers at once, per class, class alone | RTX-PRO-6000 **8**, B200 **8**, H200 **7**, A100-80GB **7**, L40S **3**, L4 **3**, H100 **2** | 12 x 30 s jobs per class, one class at a time (ap-P1MlMxrPK2LnAYAvftcB4h); availability at the time |
| largest container | 32 CPU / 256 GiB accepted (the host showed 48 CPUs, 423 GB) | ap-IAVjHJ0KAFS2at13RVAJ8Y |
| inputs per container (`modal.concurrent`) | works: 8 inputs -> 2 containers x 4 at once | same app |
| inline input / output of a function | **2 MiB** (`modal._utils.blob_utils.MAX_OBJECT_SIZE_BYTES`); above it Modal uses its blob store over HTTPS from inside the container, which **block_network blocks** | the profile's fit of the largest val system died pushing its output (ap-fEUcgKU2VXnqwsVfMooZk7) |
| volume write / commit / reload under block_network | works (3 MiB written, committed, reloaded and read intact); commit and reload leave a 0700-locked mount at 0700 | probes P1-13 / P1-14 |

Consequences: beyond ~100 jobs, parallelism comes from PACKING several jobs per large container; GPU fits must be packed several per GPU
(2-8 GPU containers of a class exist at once); anything above 2 MiB (fitted models, large evaluation records, checkpoint files) is
STAGED through a volume (section 2).

HOST GATE (no AVX-512; LOG P3-D26 / P4-D32) under load: the admissible share of Modal's hosts varies by the hour. The comparison rounds
saw 0 refusals on the 32-CPU classes and 14 of 32 fit attempts refused on the 4-CPU class; the dev dry run (P1-35, 13:35-14:00 UTC) saw
932 refusals for 276 fits and 3399 for 400 reference jobs in its first 23 minutes, before admissible hosts came back. Every refusal
costs a container start, and a packed container refuses all 8 of its inputs at once. The execution copes (immediate batched
re-submission, `stop_fetching_inputs`), but the gate's host supply is now the main source of wall-time variance; whether AVX-512 hosts
with the full pin set (numpy / torch pins plus OPENBLAS_CORETYPE / MKL_ENABLE_INSTRUCTIONS) reproduce the reference numerics bit for bit
would be a separate reproducibility study (not done here; the gate stays).

## 2. Design

### Classes (`p4modal/app.py` CLASSES; "slots" = Modal input concurrency)

| class | resources | volumes | slots | use |
|---|---|---|---|---|
| iso_pack_fit | 32 CPU / 128 GiB | fit, store | 8 | method fits (3 threads each) |
| iso_pack_eval | 32 CPU / 256 GiB | fit, eval, store | 8 | evaluations, checkpoint evaluations |
| iso_pack_loop | 32 CPU / 128 GiB | fit, eval, store | 8 | experiment loops (the driver needs the system context) |
| iso_pack_gpu_{rtx6000,b200,h100,h200} | 16 CPU / 128 GiB + 1 GPU | fit, store | 4 | GPU fits, 4 per GPU |
| pack_xl / pack_xxl (trusted) | 32 CPU / 128 or 256 GiB | fit, eval, store | 8 | references (per system x reference), calibration |
| eval_xl / eval_xxl (trusted, unpacked) | 32 CPU / 128 or 256 GiB | fit, eval, store | 1 | E11's MDE packs (their own process pool) |

Every iso class, packed or not, is **block_network** (section 3).

### Packing (`isolation.run_iso_packed`, `Backend.run_iso_packed` / `call_packed` / `run_packed`)
Each input is ONE job in its own slot; a container pulls the next queued input as soon as a slot frees, so a queue submitted
**longest expected first** is a longest-processing-time list schedule over every slot of every container. An iso slot is a CHILD
DRIVER (a fresh nondumpable root process; payload and result via root-only files, nothing on its command line) with the slot's own
uid block (`ROLE_UIDS + 20*s`, s = 1..32), group (20000+s; job directory root:group 0710) and every worker in its own user + network +
IPC namespaces (`setpriv --reuid --regid --clear-groups --no-new-privs` + `unshare --user --map-current-user --net --ipc`); clean-up
touches only the slot's uids; packing fails closed without the namespaces (`namespaces_ok`, which also refuses any non-lo interface).
A trusted slot is a subprocess (as `call`). Numerics: same image, same host gate, and the JOB's thread count everywhere: the model
workers (as before) AND the trusted driver's own numerics (`isolation.pinned_threads(job_threads(p))` around every iso job; before this
the evaluator's regressions ran with the container's CPU count, which the dry run caught, section 5.1), so a packed job computes exactly
what the unpacked job computes (sections 5-6 check it).

### Large artefacts (block_network cannot move > 2 MiB inline)
The trusted DRIVER stages them through a volume (`isolation.stage_blob` / `read_staged`; `Backend.stage_put` / `stage_get` /
`stage_clear`): a fitted model above `STAGE_THRESHOLD` (1 MiB) to the STORE volume (public-data-derived; fit and eval classes mount
it), a large evaluation record or loop file to the EVAL volume (held-out-derived; never mounted by fit classes). Paths are the
sha256 of the bytes, chosen by the driver; readers verify the hash; directories 0700 / files 0600 under mounts the lockdown makes 0700;
the caller commits the volume (commit does not remount). The tournament downloads staged fits, passes large evaluation inputs by ref,
downloads staged records and loop files, and clears the round's staged artefacts at its end (retention; recorded in ROUND.json).
`Backend.run_iso` / `run_iso_packed` refuse an inline payload above the limit before submission; an output still too large inline fails
its job with a clear error (never a container crash into Modal's retries).
The iso "call" role (trusted orchestrator functions such as P3's `p4post_iso:*`) is covered both ways: large INPUT models by ref
(`"model_refs": {name: Backend.stage_put ref}`, read and hash-checked by the driver, freshness-checked like `model_ref`), and a large
RESULT staged by total size, on the EVAL volume when the container mounts it (the result's data class is unknown) and on the STORE
volume on a fit class (no eval volume: public data only). So P3's drivers can drop their own model staging later.

### Volumes and freshness
A packed container reloads each mounted volume ONCE per wave GENERATION (`Backend.run_packed` stamps every wave): the first wave before
the lockdown; a newer wave (e.g. the checkpoint evaluations after the loops) DRAINS the container's busy slots, then reloads and locks
down again (`pack_ready`; trusted: `remote._reload_once`). No per-input reload (a reload hid files from other slots: P2's report) and no
payload-level commit on a packed class (it raises). The method snapshot is uploaded before the first wave (`methods_key`, one
merge-safe `put_file`); large evaluation inputs are uploaded before their wave; nothing uploads into a directory holding other data.

### Reference cache keyed by code
The harness keys its reference cache by system / name / k only, so the Modal rounds place it under
`<root>/<tier>/<sha256 of every brainir_causal module>[:16]` (`tournament.ref_code_key`): a pre-freeze change of refs.py or the
evaluator is never answered from a stale cache. Dry runs use their own root (`--ref-cache-root`).

### Scheduling and resume
- Cost model (`tournament._expected_s`): for a fit, the measured wall time of the same fit when one is on disk (--refit / resume:
  its side record's `fit_wall_s`), else a prior: size class (real full network 100, real medium 40, other real 20, synthetic 10) x unit
  count / 50, x 1.6 for an evaluation and x 6 for a loop; references x a per-reference weight. Evaluations and loops always use the
  prior (a fit's wall does not predict its evaluation's: 686-1008 s evaluations for 307-995 s fits in the dry run). (The first version
  read a `job_wall_s` field no record carries, so it always used the prior; fixed 2026-09-27.)
- Resume: every fit writes `<round>/<method>/fits/<sid>_s<seed>.pkl`, every evaluation `<round>/<method>/evals/<sid>_s<seed>.pkl`,
  every system's references `<round>/refs/<sid>.pkl` as they arrive; a rerun skips what exists (unless `--refit`).
  `Backend.run_packed(keys=, done_dir=)` gives the same to any caller (P2, P3, E11).
- Retries: only infrastructure failures (host-gate refusals; calls that raise on Modal, e.g. a child driver killed by memory ->
  `PackInfraError`); a job's own failure is a result, never retried. A REFUSED input is re-submitted within 15 s (`Backend.run`: the
  wave goes out as one map; refused inputs are collected for `RESUBMIT_BATCH_S` = 15 s and go out together as one more SYNCHRONOUS map in
  a client thread, at most `RESUBMIT_MAPS` = 8 such maps in flight); the earlier waves re-submitted refusals only after the map's slowest
  job, which cost E11 and P3 up to 25 min (P1's comparison round: two refused evaluations waited 1114 s, the stage took 2193 s instead of
  about 1200 s). The refusing container stops fetching inputs (`gate.refusal`, `isolation.stale_refusal`), the payload (incl. the wave's
  generation stamp) is re-sent unchanged, so a re-submission never changes what a job computes. Two dead ends on the way, both measured:
  (1) `spawn` / `spawn_map`: an async invocation returns at most 8 KiB inline (modal `MAX_ASYNC_OBJECT_SIZE_BYTES`) and moves larger
  outputs through Modal's blob store, which a block_network container cannot reach (P2's finding; every re-submitted iso fit of P1's
  full dry run died pushing its output, `ClientConnectorDNSError`); polling such calls also mistook the built-in `TimeoutError` of a
  running call for a failure (E13; `FunctionCall.get(timeout=0)` raises the BUILT-IN TimeoutError; the affected runs were P1-31, the only one of mine on that code, 11:53-12:05 UTC, and E13-18: refused inputs spawned up to 4 times, duplicated compute, no stored result or volume commit affected); (2) one synchronous `Function.remote` per refused input in a 64-thread pool: a refusal storm on the
  dev dry run (344 refusals in 8 min, 235 inputs re-submitted) came with the host's socket-buffer exhaustion (WinError 10055).
  `run_eager` is `run` now; `test_the_backend_never_uses_the_async_invocation_path` keeps spawn, async calls and call polling out of
  `p4modal/app.py`, and `test_run_batches_refusals_and_bounds_the_resubmission_maps` bounds the maps in flight.
- NEVER CHARGED: a job whose FINAL result is an infrastructure failure (the Backend's "call failed repeatedly" after its
  re-submissions, an InfraFault marker, the host-gate or staging bounds; `tournament.infra_failure`) is never stored as a fit,
  evaluation, reference, loop or checkpoint result and never charged to a method: the round is marked INCOMPLETE in ROUND.json (the
  failures listed), is neither assembled nor decided, and exits 3; rerunning the same command resumes exactly the missing jobs (before,
  such a failure was stored as the job's error and charged; P1-41 found two).
- Resume keys: fits `fit|method|system|seed|boot` (they depend on the method snapshot only); evaluations, references, loops and
  checkpoint evaluations also carry the evaluator code key (`ref_code_key`), so a resume after a pre-freeze code change recomputes them.
  The references are resumable per (system, reference) (`<round>/_done/references`).
- Inline size check: the payload's size as Modal ships it (`modal._serialization.serialize`); the first estimate measured nested
  bytes by their text form, about 3.6x too large (P3: a 1.14 MB model refused as "4.08 MB").

### Cost records (`Backend._cost`; reconciled against the billing report in section 5)
From CONTAINER time, never an input's wall at a whole container's price (which counted a packed container up to 8 times: P3's toyC run
recorded $11.15 against $2.28 billed). Every result carries its container (`__task`), its span on the container's clock (`__span`)
and the container's start (`__boot`, from /proc/uptime). Per wave and container: the union of its inputs' spans (busy), plus, the
first time the Backend sees the container, its start-up before its first input and its idle tail (`SCALEDOWN_S` = 60 s, now set
explicitly on every function). Each result gets its OCCUPANCY share of its container's busy time (`__share_s`; a slice shared by k
inputs counts 1/k for each), so per-job costs add up to the container's.

### Tournament wiring (`scripts/p4/tournament.py`, `cmd_run_modal`; `--pack` default, `--no-pack` = the earlier path)
Paths: the run and room defaults come from `P4_RUN_BASE` / `P4_ROOM_CLEAN` when set (P8's Linux driver container,
`scripts/p4/linux_driver.py`, where Modal clients do not hit the Windows socket exhaustion; the room comes in with --extra-mount), else
the host defaults. `--ref-cache-root` must be a container path (Git Bash rewrites `/evalvol/...`; launch with `MSYS_NO_PATHCONV=1`).
describe -> in ONE app: references (packed per (system, reference) on pack_xl: the verdict references plus the full-state bound's
extra candidate `full_state_joint`, `REF_JOB_NAMES`, E13 / LOG P4-D51, which `choose_bounds` weighs beside FULL-STATE and the full-state
baselines by the unchanged rule; each job fits FULL-STATE first as the harness always does, so NO-EFFECT keeps its base) in a thread,
CONCURRENTLY with the fits (packed, longest first; CPU iso_pack_fit, GPU
iso_pack_gpu_<class>) -> evaluations (packed, longest first; they do not read the references, so they do not wait for them) -> finalists
/ full: loops (packed; 'own' and the reference designers, then `random_matched` with the own loop's profile) and checkpoint
evaluations (packed, a new generation) -> the wait for the references -> bounds and verdict assembly (unchanged).

### Calibration (`scripts/p4/calibrate.py --pack [--split]`)
`--pack`: every system's `calibrate_system` through `call_packed` on pack_xl, largest first, resumable. `--split`: wave 1 = every
(system, reference) fit job (`calibrate_system_fit_job`), wave 2 = each system's assembly (`calibrate_system_assemble_from_file`); both
on the trusted pack_xl (not block_network, so no 2 MiB limit). Bit-identity: section 6.

## 3. Isolation evidence

- The network boundary is UNCHANGED: block_network on every iso class. A first design dropped it for the packed classes and relied on
  the per-worker network namespace; on Modal's gVisor `unshare --net` does NOT give a clean namespace when the container has a network
  (the worker's namespace still held eth0; `namespaces_ok` reported "eth0,lo" and failed closed), so that design was withdrawn
  (2026-09-27). Inside a block_network container the per-worker namespaces isolate the slots from EACH OTHER.
- Probe (ap-IAVjHJ0KAFS2at13RVAJ8Y, ap-SDXKoPqnlCDWs0HjpteuCj): two workers of different uids in one container, SHARED namespaces:
  abstract Unix socket, loopback TCP and SysV shm all reachable; each in its OWN user/net/ipc namespaces: all refused. Root cannot
  `unshare` in gVisor; the unprivileged worker can (CapEff 0 inside).
- `scripts/p4/smoke_pack_modal.py --mode isolation` (ap-hAhT10kxpZ498E8Euqd0tg; 4 concurrent slots of iso_pack_eval, block_network,
  the worker's tripwire OFF so only the OS boundary stands): PASS. uids 10021 / 10041 / 10061 / 10081; net:[25,27,30,33],
  ipc:[26,28,31,34]; every peer's abstract socket and loopback port refused, every peer's shm key absent; the driver's /proc/<ppid>/mem
  denied; network unreachable; /repo and /evalvol denied; no sibling job directory visible; no MODAL_* variable.
- `--mode stress` (ap-EDk1wfWhs7RX6bZ9sh1KZA): 96 concurrent packed jobs reading the method tar from the fit volume with 3 fresh
  uploads mid-run: 96/96 OK, 0 lockdown failures, 0 missing tars (P2's failure, per-input reloads, reproduced as a scenario and fixed).
- The driver runs no method code: method code is imported only in model workers (`worker.import_method`); the driver decodes worker
  replies only through the SAFE codec (`worker.encode_safe` / `decode_safe`, `np.load(allow_pickle=False)`; `WorkerClient` reads every
  reply through it); fitted models are opaque bytes it never unpickles; iso "call" targets are trusted modules only
  (`resolve_iso_target` refuses `brainir_causal.methods.*`).
- Unit tests (`phase4/tests/test_pack_isolation.py`, 31): slot uid blocks and groups; slot range; call targets; `pack_ready` reloads
  once before the lockdown and refreshes once per newer generation after draining; the packed branches never reload per input, commit
  exactly the staged volumes, and refuse a payload commit; `namespaces_ok`'s fail-closed decision on faked interface lists; staging is
  content-addressed, hash-checked, private and routed by data class; inline payloads above 2 MiB are refused and refs accepted, sized
  as Modal's serializer ships them; `fit_inline` stages by total size; the call role's staged volumes, input models by ref and result
  routing; a warm container refuses an invisible staged input without reloading; the stale-refusal bound; immediate batched
  re-submission of refused inputs (while the slow job runs; bounded maps in flight; give-up after repeated call failures); no async
  invocation path in `p4modal/app.py`; `run_packed` longest-first order, input-order results, resume; the driver's thread pin (job
  threads, BLAS limited inside and restored after, `run_iso_payload` runs the driver pinned); the cost accounting (union of each
  container's input spans, start-up, idle tail, occupancy shares, refused containers). `phase4/tests/test_compare_rounds.py` (3): the
  bit-identity check itself. `phase4/tests/test_tournament_bounds.py` (2): `full_state_joint` in the reference stage and the bound
  rule. `phase4/tests/test_calibrate_split.py` (3): split = direct (toy, default learner) and the draw_context refusal.
- Test runs after the last changes (host; the Modal run P1-36 lost its client): test_pack_isolation, test_compare_rounds,
  test_tournament_bounds, test_tournament_decide (incl. the slow end-to-end round, 576 s), test_level_c_driver, test_postlock_drivers,
  test_p4modal_local and test_calibrate_split (toy, 273 s; draw_context) all pass. The last full Modal run of the touched files is
  P1-30 (124 passed), before the later changes.

## 4. Profile (per class)

Measured in the packed / unpacked comparison rounds (section 5; val tier, 3 systems: syn-7021c9527755 small, syn-b7013ac667eb the
largest synthetic, real:A:m1; 2 stand-ins x 3 seeds) and the GPU profile (P1-14).

Per job (job wall inside the container, packed classes; n = 3 seeds each):

| job | small synthetic | real mechanism | largest synthetic |
|---|---|---|---|
| fit, frozen_brainir_state_v1 (iso_pack_fit, 3 threads) | 307-310 s | 310-314 s | 829-878 s |
| fit, FULL-STATE stand-in (iso_pack_fit, 3 threads) | 447-514 s | 443-517 s | 977-995 s (model 4.78 MB: staged) |
| evaluation, frozen v1 (iso_pack_eval, n_boot 2000, lift on) | 686-835 s | 710 s | 711 s |
| evaluation, FULL-STATE stand-in (iso_pack_eval) | 897-1008 s | 770-875 s | 886-894 s (model by ref) |

Per wave, same jobs, packed vs unpacked (the unpacked small classes are refused by the host gate much more often):

| wave | packed | unpacked |
|---|---|---|
| 18 fits | 1074 s, 0 refusals (iso_pack_fit) | 3318 s, 14 refusals, 3 waves (iso_fit_s) |
| references | 21 jobs (system x reference), 1724 s, 0 refusals (pack_xl) | 3 jobs (per system), 3691 s, 3 refusals (eval_l) |
| 18 evaluations | 1308 s, 0 refusals (iso_pack_eval) | see section 5 |

GPU (the GPU stand-in, 2 fits per class, wave time including container start; P1-14): B200 139 s, RTX-PRO-6000 141 s, H100 159 s,
H200 172 s, L40S 311 s; 4 fits at once on ONE RTX-PRO-6000 (iso_pack_gpu_rtx6000): 354 s, i.e. about 88 GPU-seconds per fit against
about 141 unpacked. Class choice: RTX-PRO-6000 as the round's GPU class (as fast as B200 on this latency-bound model at half the
price, 8 at once), packed 4 per GPU; B200 (8 at once) for throughput-bound training; H100 (2 at once) and L40S (3 at once, slowest)
not used at scale. CPU wins for the CPU stand-ins (references stay on CPU: the validated, bit-reproducible configuration).

## 5. Dry run

### 5.1 Packed = unpacked, bit for bit (and the one defect it found)
`scripts/p4/compare_rounds.py`: every evaluation record and every reference result of two rounds compared exactly (timing / host fields
removed, NaN = NaN, dataclass estimates incl. their bootstrap replicate arrays by content), fitted model files by sha256 (reported, not
gating: the stand-ins embed their own train_cost timings; a structural diff shows those are the ONLY differing fields).
- Comparison rounds `p1cmp_packed` / `p1cmp_unpacked` (val tier; real:A:m1, syn-7021c9527755, syn-b7013ac667eb; the FULL-STATE stand-in
  and frozen_brainir_state_v1 x 3 seeds; n_boot 2000, lift on): references 3/3 identical; evaluations **0/18 identical**, differing in
  the last bits (about 1e-9 relative) of the mediation and closure families. Cause: the trusted DRIVER's own numerics (the evaluator's
  regressions and bootstraps) ran with the container's CPU count as BLAS threads (20 on iso_eval_s, 48 on the 32-CPU packed class),
  while the model workers were pinned. Fix: `isolation.pinned_threads(job_threads(p))` around every iso job (packed or not), the child
  driver started pinned, and the local tournament path pinned to the same counts (P1, 2026-09-27; `EVAL_ARCHITECTURE.md` section 6).
- After the fix (`p1cmp2_packed` / `p1cmp2_unpacked`: the same fits, evaluations recomputed): evaluations **18/18 identical**,
  references 3/3 identical: `bit_identical: true`.
- GPU packing (`scripts/p4/gpu_pack_identity.py`, ap-0Ib7Kq15IgcCh1id15G47V): the GPU stand-in fitted twice unpacked (one fit per
  RTX-PRO-6000) and 4 times at once on ONE RTX-PRO-6000 (iso_pack_gpu_rtx6000): all 6 models identical (every parameter array's sha256
  and the final training loss).
- Staging (`scripts/p4/smoke_stage_modal.py`, ap-dr324PZAUfmm5dvnzOofJH): within each class kind, the evaluation of the inline model,
  of the forced-staged model passed by ref, and with the result forced through staging are identical records (packed and unpacked).
  Its packed-vs-unpacked check failed for the same driver-thread cause (it ran before the fix; the comparison rounds above re-check it).
- Calibration split: `phase4/tests/test_calibrate_split.py` (toy fixture and the default learner) passes on the pinned Linux stack
  (P1-18, P1-20, P1-30); on the interim DEV tier (2 systems, the split on pack_xl against the direct path on eval_l, the same code,
  P1-34) every per-system row and the whole calibration record (tolerances, power table, percentile, verdicts) are IDENTICAL
  (section 6).

### 5.2 Wall time, packed vs unpacked (the same jobs; val tier, 3 systems)
| stage | packed | unpacked |
|---|---|---|
| 18 fits | 1074 s, 0 refusals (iso_pack_fit) | 3318 s, 14 refusals, 3 waves (iso_fit_s) |
| references | 1724 s: 21 jobs, (system, reference), pack_xl | 3691 s: 3 jobs, per system, eval_l, 3 refusals |
| 18 evaluations | 1308 s (P1-22); 2193 s in P1-27 (2 refused inputs waited 1114 s for the old wave) | 1692 s; 3766 s in P1-27 (27 refusals) |
| 6 loops (budget 10) + 6 checkpoint evaluations | 1897 s + 1183 s | (not run) |
| round without loops | about 2460 s (describe, then max(fits + evaluations, references)) | 5193 s |
The small unpacked classes are refused by the host gate far more often than the 32-CPU packed classes (27 of 45 evaluation attempts in
P1-27), which the coordinator also observed. The re-submission is immediate now (section 2), which removes the wave waits above.

### 5.3 Full-like round (all 60 val systems, 2 stand-ins x 3 seeds)
Run 1 (P1-25, before the fixes of 2026-09-27): 272 of 360 fits in 51 min with the references running concurrently; stopped to move to
the fixed code. Run 2 (P1-31, resumed from the done directory: 274 fits reused) exposed two problems, both fixed: (1) the first
immediate re-submission used `spawn`, whose output above 8 KiB goes through the blob store, and every re-submitted iso fit died pushing
its output (section 2); (2) another fork's content-hash check (LOG P4-D50, landed 11:54 UTC during the run) refuses every synthetic val
system: the val tier's records predate the round-2 generator (all 306 synthetic reference jobs refused; the 49 finished real-system
reference jobs were fine). The val tier cannot be used with the current code until it is rebuilt; the full-like dry run moved to the
interim dev tier.
DEV full-like round (`p1dev_full`: all 50 interim dev systems, the FULL-STATE stand-in + frozen v1 x 3 seeds, packed; P1-33 died of
WinError 10055 after 13 min and was resumed as P1-35 from its done directory, 24 fits reused):
| stage | jobs | wall | host-gate refusals | occupancy of the packed slots |
|---|---|---|---|---|
| fits (iso_pack_fit) | 276 (+24 resumed) | 1736 s | 932 | 65 % (190,056 input-s on 39 containers) |
| evaluations (iso_pack_eval) | 300 | 3333 s | 2021 | 88 % |
| references (pack_xl), concurrent with both | 398 of 400 when stopped | > 5263 s | 3530 | 68 % |
The refusals came in a storm: in the first 23 minutes 932 fits and 3399 reference attempts were refused before admissible hosts came
back (section 1); every stage still completed, which the batched immediate re-submission made possible without client failures.
The round was then STOPPED BY THE HOST (Claude Code's memory-pressure reaper: the Windows host ran critically low on memory while the
session was idle; not a failure of the run), at the start of its loops; per that notice it was not restarted. Its fits, evaluations
and 398 reference results are stored in its done directories (a rerun resumes them).
The references are the round's longest stage on the dev systems (mean 1280 s per (system, reference) job, 400 jobs), not the fits.

### 5.4 Cost records against the billing report
Reconciled on ap-0Ib7Kq15IgcCh1id15G47V (the GPU identity run: 1 packed + 2 unpacked RTX-PRO-6000 containers): billed $0.5449
(RTX-PRO-6000 $0.3848, memory $0.0921, CPU $0.0681). The busy-only record of that run said $0.2967 (54 %); busy time plus each
container's 60 s idle tail gives $0.5075 (93 %); the remaining ~22 GPU-seconds are container start-up, which the records now include
(`__boot`). With the complete model (busy + start-up + idle tail), on the packed CPU class: the dev split calibration
(ap-1wlwGRK9gUcO8zJlcuO9I2, pack_xl: 14 fit jobs on 2 containers, 2 assembly jobs on 1) recorded $1.2863 against **$1.2507 billed
(+2.8 %)**; the old per-input pricing would have recorded $3.86 (5492 input-seconds at the whole container's price, 3.1x).
At scale, the dev round's COMPLETED jobs (from their stored records; `scratchpad` reconstruction with `_cost`'s model) price at
$140.57 (fits $27.31, evaluations $45.25, references $68.01) against $156.78 billed for P1-33 + P1-35 through 14:00 UTC (the 15:00
bucket not yet in the report); the rest is what those records did not hold: the refused containers (~810 container starts in the
storm), the jobs in flight when P1-33's client died and when P1-35 was stopped. REFUSED containers are now recorded too (a refusal
carries its container's record; `_cost` prices a refused-only container's start-up and refusals, `refused_only_s`,
`test_cost_records_bill_the_refused_containers`). The old per-input pricing of packed classes (each input at a whole container's price) over-stated packed runs up to 8x
(P3's toyC run: $11.15 recorded against $2.28 billed; P1-7 / P1-9 / P1-10 / P1-12 above: $1.04 / $0.95 / $0.89 / $5.49 estimated against
$0.27 / $0.24 / $0.23 / $0.76 billed).

## 6. Calibration split: bit-identity

DEV-TIER CHECK (P1-34, interim dev tier, systems syn-00e48aa6ad4d and syn-04c74abe0096, current code): `calibrate.py --pack --split`
(14 fit jobs on pack_xl in 1016 s, 2 assembly jobs in 524 s) against the direct `calibrate.py --cls eval_l` (2 jobs in 3861 s, 9
refusals): both per-system rows and the calibration record compared exactly (`compare_rounds._norm`: timings removed) are
**IDENTICAL**. Recorded cost of the split $1.45 (billed $1.42).

`calibrate._calib_build` (fits + registration + item set) and `_calib_evaluate` (evaluations + row) are the two halves of
`calibrate_from_inputs`; the per-(system, reference) jobs (`calib_fit_job`) fit one reference each through `_calib_fit(only=name)`
(`refs.fit_references` for that one name, its skip and error rules unchanged), their pickled models are merged in `fit_references`
order (NO-EFFECT wrapping the FULL-STATE fit, as `fit_references` does) and passed to `_calib_build(prefit=...)`, so the item set comes
from the SAME single `supported_items` line (E13's) in both paths. `phase4/tests/test_calibrate_split.py` (toy fixture, two systems,
FAST learner): the split row equals the direct row in every field except the wall-clock / CPU timings; passed on the pinned Linux stack
(modal_pytest, ap-6ffL6fqQhwuNntBPazc89r) and locally.
Cause of the earlier Modal failure (E15): (1) the first test compared the reference models' train_cost cpu_s / wall_s, which differ
between ANY two runs (two DIRECT runs of the same inputs differ there too); (2) the first split recomputed the item set in a second
place from the reloaded model, a duplicate of E13's line that E15's round-3 change of the class-balanced cells / families could make
diverge; the current split has no duplicate. Neither involved BLAS threads: the calibration reads stored truth arrays and never
constructs a generator system (P6's thread fix, LOG P4-D50, does not enter), and both paths run their jobs with 2 threads.
Execution (E13's item 3): the split runs ONE job per (system, reference) on pack_xl (32 CPU / 128 GiB, 8 jobs per container, 2
threads each), longest first; on the dev tier the jobs peaked at ~4 GB each and the longest (FULL-STATE) took 878 s, against ~40 min
per system for the unsplit job on eval_s. TRUE-STATE's `draw_context` is recorded per system (`true_state_draw_context`), and a system
whose truth provides draws while the fitted TRUE-STATE has draw_context False is REFUSED (E13's item 4; in `_calib_build`, so both
paths; `test_calibration_refuses_a_z_only_true_state_when_the_truth_has_draws`).

## 7. Projected wall time per real round

A PROJECTION (`scripts/p4/project_round.py`: every stage's jobs list-scheduled longest first onto containers x slots; fits and
references concurrent; container start-up 90 s per stage) from the MEASURED job durations of the dry runs (packed classes):
fits (median / p90 / max): FULL-STATE stand-in synthetic 678 / 950 / 2104 s, real mechanism 494 / 533 / 612 s, real full 902 / 946 /
972 s; frozen v1 synthetic 407 / 642 / 864 s, real mechanism 297 / 381 / 585 s, real full 698 / 1524 / 1646 s (335 fits); evaluations
686-1008 s on val (36) and a mean of 1025 s on dev (300); reference jobs 630-750 s per (system, reference) on real mechanisms (49) and a
mean of 1280 s on synthetic dev systems (398). ASSUMED: 90 containers x 8 slots for the round
(the workspace limit is ~100; other work idle), real-full-network evaluations 2000 s and references 1400 s (not measured), candidates
as expensive as the FULL-STATE stand-in, a loop at budget 200 costing 6500 s (the stand-in: initial fit + 40 refits of ~150 s; a
method's own update cost decides this), a checkpoint evaluation 900 s.

| round (PROTOCOL 10) | fits (+ references) | evaluations | loops | checkpoint evaluations | total |
|---|---|---|---|---|---|
| pilot: 8 candidates + 2 baselines, 25 synthetic + 3 real mechanisms | 37 min | 36 min | - | - | 1.2 h |
| medium: 4 + 2, 50 synthetic + 7 real mechanisms | 44 min (references) | 36 min | - | - | 1.3 h |
| finalists without loops: 3 + 1, all 60 systems | 44 min (references) | 35 min | - | - | 1.3 h |
| full with the default active design: 3 candidates x 9 designers x 3 loop seeds | 44 min | 35 min | 12.7 h | 8.5 h | 22.5 h |
| full with 2 designers x 1 loop seed | 44 min | 35 min | 1.8 h | 0.8 h | 3.9 h |

Without loops a round is bounded by its longest single jobs (a 2104 s fit, a ~2000 s evaluation) and by the reference stage (400
jobs of ~1280 s on 30 containers), not by the fit capacity. The projection assumes a normal host-gate refusal rate; in a refusal storm
(section 1) the dev round's stages took 1.5-2x their job-bound times. With the default active design the loops and their checkpoint evaluations are over 95 % of the round and scale with
total work / slots: 4860 loops and ~24,000 checkpoint evaluations. Levers that change no result: more slots per container where memory
allows (the stand-in's loop container peaked at 15.5 GB of 128 GiB), more containers (the workspace limit). The loop design itself
(designers, seeds, budgets) is E11's MDE decision. Reproduce or update: `uv run --no-sync --project phase4 python
scripts/p4/project_level_b.py <out.json>` (the inputs above are its constants; re-run with the candidates' measured costs).

## 8. Model workers: one uid each, deaths as infrastructure, pre-started spares (P2's finding, 2026-09-27)

THE BUG. A worker's uid was a function of its ROLE (`role_uid`): every phase-A worker of every model of one job (one slot) ran under
the same uid, and a worker start SIGKILLs every process of its uid (as does a worker's clean-up). A job that interleaves calls to
several `RemoteFresh` models therefore killed each model's idle worker at the next model's start; that model's next calls failed within
~2 ms (WorkerDied, BrokenPipeError) and `fresh.safe_call` scored them as the METHOD's failed calls (P2's diagnostic
ap-kuS6FeR9tgcCHld4VpH8Ek; LEVEL_C_DRIVER.md section 9). Only `LinuxUidTransport` (every Modal iso class) killed by uid; the Docker and
local transports were not affected.

THE FIX (isolation.py, p4modal/app.py; tests `phase4/tests/test_worker_uids.py`, 10):
- ONE UID PER LIVE WORKER: `LinuxUidTransport._take_uid` gives every live worker a uid of the transport's block (the slot's block of
  19; never-used uids first, the role's own uid among them first, then the free uid used longest ago), a start and a clean-up kill only
  their own uid, and the uid returns to the pool only after its processes, IPC objects and working directory are gone. More live
  workers than uids raises an InfraFault (loud), never a shared uid.
- A DEAD WORKER IS INFRASTRUCTURE: `WorkerDied` is an `InfraFault`, a BaseException (`except Exception`, incl. `safe_call`, cannot
  swallow it). `RemoteFresh` restarts the (sub-)phase's worker once and retries the same call on the fresh process (it has seen
  nothing; the digest record is reset); a second death in a row, or a worker that does not start twice, fails the job. The container
  callable returns an InfraFault as `{"__infra__": True, "error": "InfraFault ..."}`; `Backend.run` re-submits it (at most
  MAX_CALL_FAILS; the final error reads "call failed repeatedly on Modal (infrastructure): ... InfraFault ..."); the Level C and
  post-lock executors now match "InfraFault" as infrastructure (one string added to each INFRA_PATTERNS). `PackInfraError` (a packed
  child driver that died) is an InfraFault too: before, it became the job's own error result, charged to the method. Fits, loops and
  method descriptions: a worker that dies, or does not start, fails the job as infrastructure (`start_client`). Timeouts and protocol
  violations stay the METHOD's failures (a call over 900 s; a worker that corrupts the protocol).
- EVIDENCE: the unit tests run the REAL transport logic with local OS primitives: two interleaved models (every call succeeds, no
  start or clean-up ever kills a live worker), the role-uid allocation of before (live workers killed: reproduces the bug), a worker
  killed from outside (served again by a fresh process, recorded), a worker that dies twice (InfraFault through `safe_call`), the
  container callable, the packed child driver and the Backend. On real Linux (Docker sandbox image as root, unpacked and packed-slot
  modes) and on Modal (`scripts/p4/smoke_uids_modal.py` + `uid_probe_call.py`: packed slots of one iso_pack_eval container, real uids,
  setpriv + unshare, gVisor): distinct uids per live worker, a digest restart of one model leaves the other's process untouched, a worker
  SIGKILLed from outside is replaced with one infrastructure restart recorded, no uid left live (P1-37 ... P1-40).

AUDIT (which jobs could be affected, and which stored results must be discarded):
| job | live models per job | exposed to the cross-model kill? |
|---|---|---|
| tournament evaluations, checkpoint evaluations (`harness.evaluate_job`) | 1 (phases sequential) | no |
| calibration (split and direct) | 0 (trusted references in-process) | no |
| fits, loops (learner + own designer in ONE worker), method descriptions | 1 | no |
| E11's MDE (`active_mde`) | 0 (trusted reference learners) | no |
| P3's post-lock drivers (`p4post_iso`: fit_c, eval_c, predict_detail, encodings, readin_probe, memo_probe, lift_jitter; self-audit probes, counterexamples, ablations through them) | 1 at a time (each closed before the next) | no |
| Level C per-model evaluations (`levelc_remote.eval_items`, `same_items`, `fit_records`) | 1 at a time | no |
| Level C 5.11 `representation_stability` over 10 interleaved models (before P2's record / replay workaround) | 10 | **YES** |
| P2's `stability_diag` (the diagnostic that found it) | 2, by design | yes (diagnostic only) |
The digest-rule restarts of ONE model killed only that model's own (closing) worker: not affected. A byte-level scan of every stored
result (my rounds, P2's levelc_dry, P3's postlock_dryrun in both places, data/phase4/driver_runs) for the signature of a swallowed
worker death (WorkerDied, "no reply to", "cannot send", "worker is unusable", BrokenPipe; a dead worker's close record carries it as
"fatal") found it ONLY in P2's STABILITY_DIAG.json. DISCARD: every Level C 5.11 result computed with interleaved models before P2's
record / replay workaround (P2 has flagged them: "5.11 ran on a reduced, model-independent sample"). Nothing else needs discarding.
Worker deaths from OTHER causes (out of memory, lost pipes) were also silently scored before this fix; the scan found none in the
stored results.

PRE-STARTED SPARES (`RemoteFresh(spares=3)`; measured, then implemented because it is clearly safe). A restart costs 5.6-5.8 s in a
packed slot: boot 0.27 s, init 5.0 s (the environment's scientific stack imported before the tripwire; the method's own code runs only
at the model load, 0.11 s), close 0.45 s; the digest rule restarts 74-118 times per evaluation on the validation systems (e.g. 97 on
real:A:m1: about 540 s of a 705 s evaluation) and about 105 times per model on the real mechanisms at Level C (P2). After a phase's
first restart, up to 3 workers of that phase are started in advance up to and including their init; a restart takes the oldest and
loads the model only after the old worker's processes are gone. SAFE: until it is taken a spare has run only trusted code (the worker
module, the environment's installed libraries, the tripwire), has no model and has seen no history, so it is exactly a freshly started
worker; no method code of the new worker runs while the old one is alive (a spare's method code could otherwise listen for a covert
signal from the live worker, which is why spares are NOT pre-loaded with the model); the method snapshot and the public code are
read-only for workers. Measured on Modal, back-to-back restarts (the worst case: a restart before every call): 5.81 s -> 3.18 s per
restart with 3 spares, outputs identical; on real Linux: 6.0 s -> 1.3-2.5 s once the spares are warm. A uid block keeps two uids free
for the live workers' own restarts; spares close with their phase.
ON REAL EVALUATIONS (P1-41): the evaluations of the post-fix comparison round re-run with the new code (per-worker uids, the
infrastructure retry, spares) against the stored records of P1-26 (role uids, no spares), the same fits: every value identical in all
four evaluations that completed (every metric family and bootstrap replicate; the only difference is a key another fork's evaluator
change added, result/lift/per_lift). 94-95 spares were used per evaluation; the real:A:m1 evaluations took 459 s instead of 705 s
(frozen v1) and 488 s instead of 765 s (the stand-in): -35 %. Section 7's evaluation stage shrinks accordingly.
OPEN: one Modal run of the smoke (P1-38, before the uid choice changed from "role uid first" to "never used / least recently used
first") hung for 25+ minutes without a result and was stopped; the same call target passed on real Linux (Docker, packed-slot mode)
and on Modal after the change (P1-39, P1-40). The cause was not identified (immediate reuse of a freed uid in gVisor is a candidate);
the smoke now carries a watchdog that returns every thread's stack and the process table at a deadline.

## 9. Container-start numerics self-test (P9's host-gate study, "Hardening"; 2026-09-27)

WHAT. The flag gate admits a host by its CPU flags only (no AVX-512, AVX2 present). Every GATED class (all 26 CPU classes: build*,
eval_*, fit_*, iso_*, pack_*, sim, sim_eval; not util and not the GPU classes) now also runs a fixed micro battery ONCE per container,
after the flag gate and before its first input (`p4modal.gate.numerics_selftest`, cached under a lock, so the inputs of a packed
container wait for one run), and its hashes must equal the checked-in reference `phase4/src/brainir_causal/p4modal/numerics_reference.json`.
The battery (`p4modal/selftest.py`) runs in three fresh processes at once (their imports overlap; the pins of the container, the BLAS /
OpenMP pools sized for 4 threads): "main" (numpy's SIMD ufuncs and reductions; numpy's OpenBLAS GEMM, A.T A, GEMV, solve, lstsq, SVD,
eigh, Cholesky, inverse; scipy's LAPACK, sparse mat-vec and RK45; the synthetic generator: two systems built and simulated nominally
and with a kick at one BLAS thread, of a tier name no suite uses, "selftest", so the battery builds no benchmark system), "torch"
(float64 / float32 GEMM at two sizes, torch LAPACK, an MLP fitted by 20 Adam steps in float64 and float32) and "engine"
(`brainir.sim.model.simulate` on a 60-unit sparse signed network). The OpenBLAS, scipy and torch items run at each of the job kinds'
thread counts 1, 2, 3, 4 (results depend on the thread count, P9). 15 items; each is the sha256 over the dtype, shape and bytes of every
output array. The generator item is OPTIONAL (recorded as absent where the generator is not baked, e.g. the describe classes' images).

VERDICTS.
- pass: the job runs; its result carries `__selftest` {ok, s, wall_s, cached, absent, host_class, reference_class} (volatile for
  `scripts/p4/compare_rounds.py`). reference_class says whether the host's class is one the reference was built on; a NEW class that
  reproduces the reference passes on its numerics.
- mismatch (an item's hash differs, an item raises, a part crashes or times out): the container refuses the host EXACTLY like the flag
  gate (`gate.refusal`: stop_fetching_inputs, the refusal marker; the Backend re-submits the input to a fresh container), and the
  refusal carries the mismatching items, the errors, the host class and the full host fingerprint. The Backend keeps them
  (`selftest_refusals`, up to 200, and `selftest_counts` {passed, refused} per class, both in `cost_summary()`, i.e. in every run's cost
  record).
- stale (the reference was built by another battery, i.e. `selftest.battery_id()` = the module source's hash differs; or by another
  library stack: numpy, scipy, torch exactly, python by major.minor; or there is no reference): an INFRASTRUCTURE fault
  ("InfraFault (numerics reference)"), never a host verdict: re-submitted like any infrastructure fault, then given up; the round is
  incomplete and nothing is charged. Any edit of `selftest.py` or of the pinned stack therefore needs a rebuilt reference (the test
  below fails until then).
- bounds: an input refused by the self-test on `MAX_SELFTEST_REFUSALS` = 8 containers, and every waiting input of a class once
  `SELFTEST_BREAKER` = 24 self-test refusals came with no container of the class passing it (a systematic fault), are given up as
  infrastructure failures ("InfraFault (numerics self-test)", in the tournament's INFRA_MARKS: never charged, the round is incomplete).
  The flag gate's own refusals keep their earlier bound (MAX_REFUSALS).

REFERENCE (`scripts/p4/build_numerics_reference.py --write`, run through `scripts/p4/linux_driver.py`). An app of its own, NO gate and
no self-test (every host kind shows up), the two official images with the generator baked, 4- and 32-CPU containers, one input per
container (stop_fetching_inputs). The builder writes the reference only if EVERY admissible container agrees on every item, none failed
and all 15 items are present. The reference is a pure function of the recorded rows (`research/phase4/numerics_selftest/
build_report.json`, every container's items, host class and fingerprint; `--from-report` rebuilds it without Modal).
Built 2026-09-27T19:38Z (P1-44, ap-DmWb8hfN8EkGKyvdEJnvye): 80 containers, the 67 admissible ones all AMD `fam175/model1` (Zen 3; gVisor
reports no model name, the numeric family / model name the class as in P9's study) agree on all 15 items. The battery tells every
refused class apart: AMD model 17 (Zen 4, AVX-512) reproduces 5 of 15 items (numpy's SIMD ufuncs and the torch items: the pins hold
there), Intel models 85 / 106 1 of 15; every one of them differs on the OpenBLAS, scipy, engine and generator items. A further probe
(P1-46, 150 containers): all 110 admissible containers (Zen 3) reproduce the checked-in reference; the 40 AVX-512 containers would all
be refused by the self-test alone (10 or more mismatching items each). Zen 2 (AMD model 49; P9: bit-identical to Zen 3 on every
benchmark workload, 9 of 51 admissible containers in P9's round 3 at 17:15Z) did not appear in any of the 300 classified admissible
containers of 19:35-19:50Z (builds P1-43 / P1-44, the probe, the validation), so the reference is recorded on Zen 3 only; a Zen 2 host that computed differently would be refused and
recorded, never admitted.

VALIDATION on the official classes (P1-45, ap-D92ys93uCJZFhaGYi6ASUN; `scripts/p4/validate_selftest_modal.py`, trivial `time.sleep`
jobs submitted at once so each lands on its own container): **63 containers passed the self-test (fit_s 30, iso_fit_s 30, pack_xl 3:
full image, iso image, packed), 0 self-test refusals (0 false refusals)**, 0 infrastructure faults, 96 of 96 jobs completed; the flag gate
refused 37 AVX-512 containers as before (245 refusal markers: a refusing container also refuses the inputs Modal had already routed to
it). Record: research/phase4/numerics_selftest/validation_20260927T194551Z.json.

COST. The battery's wall on Modal: median 4.1 s, range 2.6-5.9 s over the 230 builder / probe containers of the final battery (both
images, 4 and 32 CPU); median 4.6 s, max 6.3 s inside the official classes (the validation). Per container at list price: 4-CPU / 16 GiB classes (fit_s, iso_fit_s) $0.0004 (validation median 4.6 s x $0.0000879/s); 8-CPU / 32 GiB ~$0.0008;
32-CPU / 128 GiB (pack_xl, iso_pack_fit, iso_pack_loop, fit_xl, eval_xl, build_xl) $0.0032 (4.6 s x $0.00070/s); 32-CPU / 256 GiB
(iso_pack_eval, pack_xxl, eval_xxl) $0.0045; the non-preemptible classes 3x that. A container's first input starts ~4-5 s later. A self-test refusal costs a container
start plus the battery; the flag gate refuses AVX-512 hosts before the battery runs, so they cost what they did before.
TESTS: `phase4/tests/test_numerics_selftest.py` (14): the verdict rules; a FAKED MISMATCH refuses the host (stop_fetching_inputs,
the mismatching item, the host class and the fingerprint recorded, the job not run, the cached verdict for the container's next
input); a pass runs the battery once per container (8 concurrent packed inputs: one run); a stale or missing reference is an
infrastructure fault (and the tournament's `infra_failure` treats it and the Backend's give-up as such); the flag gate refuses first and
ungated classes skip the battery; the Backend's per-input cap and class breaker; THE REFERENCE MATCHES ITS BUILDER (the battery id,
the item set, the pinned numpy / scipy / torch of `images.py` and the reference python, admissible reference classes, and the builder
applied to the recorded report rebuilds the checked-in file byte for byte); the builder refuses disagreement, errors, thin evidence and a
missing generator item.
