# Phase 4 fit / loop / evaluation execution architecture (E10)

This is the design and implementation that closes the early leakage review F's blockers F-B2 and F-B3 and its major finding F-M5, and
makes them impossible **by construction** rather than by instruction. It replaces the in-process audit-hook sandbox as the boundary
for running untrusted method code.

## 1. Threat model

Every line of method and designer code is UNTRUSTED. It must never have access to:
- held-out data: item futures, counterfactual twins, pool futures, native-lift outcomes before it requested those lifts, truth
  (z, z_obs, true latent effects), the confirmation / real-hidden sets;
- the salt or the tier seeds, the orchestrator's internal records, the synthetic generator code;
- other methods' snapshots or fitted models, or another method's results;
- the network, or the Modal workspace credentials / token.

The isolation is enforced by the operating system (a separate unprivileged process, file permissions, a network-less container),
not by an in-process guard. F showed why an in-process guard cannot be the boundary:
- **F-B2**: the old `runguard` kept its re-entrancy flag in a module attribute, so method code turned the whole guard off with one
  assignment (`g._TL.busy = True`); and its eval mode keyed on "a method frame is on the stack", which a thread whose target is `exec`
  does not have, so `threading.Thread(target=exec, args=(...,))` read held-out files.
- **F-B3**: evaluation ran method code in the SAME process that held the held-out futures; a `gc` walk recovered `y_future` for 24 of
  24 items, and worker processes were reused across methods.

## 2. Two parties

- The trusted **DRIVER** holds every held-out array, the simulator and the truth, runs the unchanged evaluation code
  (`harness.evaluate_model` and the E5 / E6 metric families), the experiment loop (`loop.run_loop`: policy check, budget accounting,
  simulation) and the benchmark references (`refs`, trusted). On Modal it is root inside the container; on the development machine it
  is the orchestrator process.
- The **MODEL WORKER** (`brainir_causal.worker`) is a fresh process that runs the method's code for ONE job role of one
  (method, system): a fit, an experiment loop, or one phase of an evaluation. It imports only the PUBLIC modules of `brainir_causal`
  (a copy under `/opt/p4pub`), the frozen earlier baseline (`brainir_state`, hash-checked) and the method snapshot; it receives
  exactly the arguments of the calls it must answer (and, for fits / loops, the public training records) over a pipe.

### Worker environment (Modal `LinuxUidTransport`)
- a fresh OS process per (method, system, role) as an UNPRIVILEGED uid — one uid per role (`isolation.ROLE_UIDS`: A 10001, B1 10002,
  B2 10003, C 10004, fit 10010, loop 10011, describe 10012, probe 10019), started with `Popen(user=, group=, extra_groups=[],
  umask=0o077, start_new_session=True)`, with `RLIMIT_NPROC` and `RLIMIT_CORE 0`;
- a scrubbed environment: a fixed minimal `PATH`, `HOME`/`TMPDIR` = an empty per-job dir owned by that uid, the thread-count
  variables and only the numeric pins (`NPY_DISABLE_CPU_FEATURES`, `ATEN_CPU_CAPABILITY`); no `MODAL_*` and no credential variables;
- file permissions such that the worker reads only the method snapshot (a root-owned 0755 dir under a 0711 per-job root), the public
  modules (`/opt/p4pub`, world-readable) and, for a fit, its own PUBLIC training records (which arrive over the pipe, not the disk).
  Everything else — `/repo`, `/root`, the volume mounts, the eval/store/generator directories — is root-owned 0700.

### Worker environment (development machine `DockerTransport`)
One container per worker from the pinned sandbox image (`docker/p4sandbox/image.json`): `--network none --read-only
--cap-drop ALL --security-opt no-new-privileges --pids-limit --user <role uid> --tmpfs /work` (owned by the uid) and a read-only bind
mount of the public modules and the method snapshot. Nothing of the repository, the data or the driver is in the container.

### `LocalUnsafeTransport`
A plain same-user child process with the scrubbed env and the public code path but NO OS sandbox. It is for TRUSTED code only (the
equivalence tests, the benchmark's own references); tournaments never use it.

## 3. Wire protocol and the SAFE codec (closes the F-B3 unpickle surface)

Frames over the worker's stdin/stdout pipes (`worker.read_frame` / `write_frame`: an 8-byte big-endian length + payload). The worker
dups its original stdout to a private protocol fd and redirects fd 1 and `sys.stdout` to stderr, and fd 0 to `/dev/null`, before any
method code runs, so prints never corrupt the protocol.

- **driver → worker**: a pickle of `{"id", "op", ...}`. The driver is trusted; only the worker unpickles.
- **worker → driver**: the SAFE encoding (`worker.encode_safe`): a JSON header describing the value (dict / list / str / number /
  bool / None) with numeric numpy arrays and raw bytes carried in an UNCOMPRESSED `.npz`. The driver decodes it with `json` and
  `np.load(allow_pickle=False)` ONLY (`worker.decode_safe`). It refuses compressed or oversized archive members (decompression bombs),
  object-dtype arrays, unknown markers and excessive nesting. **The driver never unpickles anything a worker produced** — fitted
  models included: a fit worker returns the model as opaque bytes, the driver stores them and passes them to the evaluation workers
  without ever loading them. An object whose `__reduce__` would run code is degraded to its `repr` by the codec and never
  reconstructed (test: a `Pwn` "latent" leaves no side effect).

## 4. Evaluation: `RemoteFresh` and the three phases

`isolation.RemoteFresh(model_bytes, transport)` is a drop-in `fresh.Fresh` for the evaluation code. Every model call
(`encode`, `rollout`, `readout`, `supports`, `step`, `read_in`, `intervention_effect`, `lift`, `uncertainty`, `validity`, `info`,
`schema`, plus `capacity`) forwards ONLY that call's arguments to a worker, which evaluates it on a FRESH unpickled copy of the
pristine model bytes (PROTOCOL section 5). `RemoteFresh.get()` returns a proxy whose class overrides `lift` iff the remote model's
class does, so `evaluate_lift.lift_supported` still works.

An evaluation runs in three PHASES, each in a NEW worker process with its OWN uid; a phase only moves forward (A → lift → C) and a
closed phase is never reopened:

| phase | uid | what the worker is asked | why isolated |
|---|---|---|---|
| A | 10001 | predictions from PASTS only: item predictions (history ≤ onset, future inputs, events), composition pairs, encodings of PUBLIC training histories (whitening), pool histories (microstate equivalence), truth samples' histories, read-ins, the capacity record | every prediction exists before any future history is ever given to a worker |
| lift B1 | 10002 | native-lift requests (histories ≤ case time + requested shifts) → the DRIVER simulates the candidates | lift requests are made before their outcomes exist |
| lift B2 | 10003 | encodings of the lifted / twin histories and rollouts from them | a NEW process, so the lift outcomes cannot be recalled into a later lift request |
| C | 10004 | encodings of the TRUE FUTURE (intervened and twin) histories: closure and the bisimulation re-encodings | future-history encodings only, and only after A and the lift are closed, so C cannot recall A's predicted latents to fake the own-closure gap |

Between phases the driver kills every process of the worker uids and removes their System V IPC objects; `/tmp`, `/var/tmp` and
`/dev/shm` are made non-writable by workers in `container_lockdown`, and each worker's working directory is private to its uid, so no
state crosses a phase boundary. A NEW `RemoteFresh` (new workers) is used for every (method, system); workers are never reused across
methods.

WITHIN a phase a worker process serves many calls and keeps its module state (review F round 2, N-m3). The driver therefore keeps
exact row digests (`isolation.history_digests`) of every history it sent to each worker process; a call whose history ends at a row
that another history of the same process holds FOLLOWED by more samples (a longer history of the same trajectory, or a trajectory
restarted from that state) is sent to a fresh worker process of the same role (`worker_restarts` in the record; test
`test_isolation_memo.py`). Histories whose last row is constant or equal to their first row are not tracked; calls in increasing
onset order never restart.

Metrics through a `RemoteFresh` equal metrics on the same model in-process to 1e-12 on the toy tier (test
`test_isolation_local.py::test_metrics_through_remote_fresh_equal_direct`).

## 5. Fits and loops

- **Fit** (`isolation.fit_job` → `fit_records`): the driver reads the public training records and sends them to a fit worker, which
  fits and returns the model as BYTES and a side record (compute, info, platform). The model is never loaded by the driver. The Level C
  dimension refits of PROTOCOL 5.10 are `bootstrap_interventions(records, b, seed)`: a bootstrap resample of the training
  INTERVENTION trajectories (each with its twin; passive data kept; repeated draws renamed so keys stay unique), one fit per resample.
- **Loop** (`isolation.loop_job`): the DRIVER runs `loop.run_loop`. The method's learner (and, for `--designer own`, its designer)
  live in ONE loop worker (`WorkerLearner` / `WorkerDesigner`); the driver validates every proposal against the PUBLIC policy,
  simulates it, does the budget accounting and sends the new records to the worker. Reference designers are trusted and run in the
  driver, querying the worker's current model through a proxy (`_LoopModel`); the magnitude-matched control `random_matched`
  (`designers.MagnitudeMatchedDesigner.from_loop`) is built from the method's own loop directory and also runs in the driver. A
  worker never gets a simulation client. The designer rng is a seed drawn from the driver's generator.

## 6. Container lockdown (Modal, `run_iso_payload`)

The driver runs as root and applies `container_lockdown` before any worker starts (idempotent; the file-system scan once per
container):
- `prctl(PR_SET_DUMPABLE, 0)` on itself, so no worker uid can read `/proc/<driver>/mem`, `environ`, `fd` or ptrace it;
- `chmod 0700` on `/repo`, `/root`, `/data`, the volume mounts and the other private roots — sensitive volumes are mounted
  READ-WRITE precisely because a read-only mount cannot be chmodded (the probe below shows a read-only mount stays world-readable);
  the driver never writes them. Modal volume mount points are SYMBOLIC LINKS (`/fitvol -> /__modal/volumes/vo-…`, mode 0755 by
  default: world-readable), so the lockdown chmods the RESOLVED target, and it FAILS CLOSED: if any existing private root is still
  group- or other-accessible afterwards, it raises and no worker starts in that container (the Modal smoke found the first version,
  which skipped links, leaving the three volumes world-readable behind the tripwire only);
- `chmod o-w` on `/tmp`, `/var/tmp`, `/dev/shm` and the other shared temp dirs; a world-writable-file scan over `/`;
- the per-job root `/opt/p4jobs` is 0711 (a worker reaches its own job dir by name but cannot list others);
- before and after each job, `kill_uids()` SIGKILLs every process of the worker uids and `ipc_cleanup()` removes their SysV IPC.

The "iso" Modal classes (`p4modal.app.CLASSES`) set `block_network=True`, mount only what the role needs (fit / loop never the eval
volume), and use the `iso_image` (`p4modal.images.iso_image`): the repository code baked with `copy=True`, the worker uids created,
and `chmod -R go-rwx /repo` so an unprivileged worker cannot read the orchestrator code, the generator or a bundle path by default.
The container-side entry is `remote.run_iso` (job kind `iso`), which never unpickles worker output.

### Empirical isolation probe (Modal, `scripts/p4/probe_isolation.py`; `research/phase4/isolation_probe_modal.json`)

One `block_network=True` container, root writes root-only files and a read-write and a read-only volume, sets dumpable 0, then runs a
child as uid 10001 with the scrubbed env. Child results:

| access | result |
|---|---|
| its uid / groups / env | 10001, groups `[]`, env only `HOME LC_CTYPE PATH PYTHONDONTWRITEBYTECODE PYTHONIOENCODING`; no `MODAL_*` |
| read-write volume (chmod 0700) | DENIED (permission) |
| read-only volume (cannot be chmodded, stays 0755) | READABLE — so sensitive volumes are mounted read-write and locked down |
| `/rootonly`, `/root` (0700) | DENIED |
| `/proc/<driver>/mem`, `/environ`, `/maps` | DENIED (dumpable 0); `/cmdline` readable (only the driver's argv — see residual risks) |
| DNS, TCP 1.1.1.1:443, the Modal API | DENIED (network unreachable; no token) |
| `setuid(0)` | DENIED |
| subprocess as the same uid | allowed (harmless; the in-worker tripwire refuses it anyway) |

### Modal smoke of the whole stack (`scripts/p4/smoke_isolation_modal.py`; `research/phase4/isolation_smoke_modal.json`)

One iso-image container (block_network=True, 4 CPU / 16 GiB) runs the root driver: lockdown, public-code directory, and for two
scratch methods (a small 5-unit and a 40-unit linear system; a package built by the script, never the repo's methods/) a fit in a
uid-10010 worker and a RemoteFresh evaluation (encode, capacity, lift, the A → lift → C transitions), plus an adversarial and an
"unpicklable output" method. Result of the final run (127.5 s wall including container start; about $0.011):

| check | result |
|---|---|
| mounts before lockdown | `/fitvol`, `/evalvol`, `/storevol` are symlinks to `/__modal/volumes/…`, mode 0755 |
| lockdown | dumpable 0; `/repo`, `/root`, the three volumes (resolved), `/home`, `/mnt`, `/srv` all 0700; `/tmp`, `/var/tmp` 0775, `/dev/shm` 1775 (no write for other) |
| smoke_small / smoke_big | fit 6.3 s / 5.6 s, evaluation 16.5 s / 15.8 s (three fresh workers each; start-up dominated by the stack pre-import); lift request after the outcomes: refused; rollout in phase C: refused |
| adversary, tripwire ON | every probe refused: the three volumes, `/repo`, other jobs, the driver's environ / mem, TCP, DNS, `/tmp` write, subprocess, setuid 0; no `MODAL_*` in its env |
| adversary, tripwire OFF (the OS alone) | volumes, `/repo`, other jobs: PermissionError; driver environ / mem: PermissionError (dumpable 0); TCP: network unreachable; DNS: no resolution; `/tmp` write: PermissionError; setuid 0: PermissionError; no `MODAL_*`; a same-uid subprocess is possible (harmless: same uid, no new privileges; the tripwire refuses it in normal operation) |
| unpicklable "latent" (`__reduce__` → os.system) | never reconstructed (the codec degrades it to a repr); the driver's encode fails with a TypeError; no side effect |

### Packed containers and large-artefact staging (fork P1, 2026-09-26/27; `research/phase4/LEVEL_B_EXECUTION.md`)

- PACKING (`isolation.run_iso_packed`, the `iso_pack_*` classes, Modal input concurrency): several jobs at once in one container, each
  in its own SLOT: a nondumpable root CHILD DRIVER (payload and result through root-only 0600 files under a 0700 directory; nothing on
  its command line) with the slot's uid block (`ROLE_UIDS + 20 * slot`), group (20000 + slot; the job directory root:group 0710) and
  every worker in its own user + network + IPC namespaces (`slot_worker_cmd`). Slots are isolated from EACH OTHER by uid, group,
  directory modes and namespaces; the network boundary is unchanged: every iso class, packed or not, is block_network (on gVisor
  `unshare --net` keeps the container's eth0 when the container has one, so the namespaces are not a network boundary by themselves;
  `namespaces_ok` fails closed on any non-lo interface). Evidence: LEAKAGE_POLICY section 2.13.
- THE DRIVER RUNS NO METHOD CODE, packed or not: method code is imported only in model workers (`worker.import_method`, in a worker
  process); the driver talks to them through the SAFE codec only (`worker.encode_safe` / `worker.decode_safe`: JSON + npz with
  allow_pickle=False, section 3), and fitted models are opaque bytes the driver never unpickles (`fit_records` returns them; evaluation
  workers load them). The child driver unpickles only its OWN payload file (written by the parent driver, root-only) and the parent only
  the child's result file (the trusted driver's output). An iso "call" target is trusted code only (`resolve_iso_target` refuses
  `brainir_causal.methods.*` and any module outside brainir_causal / the baked scripts directory).
- LARGE ARTEFACTS: Modal cannot move an input or output above 2 MiB inline on a block_network container (it would use its blob store),
  so the DRIVER stages a fitted model (> `STAGE_THRESHOLD`) to the STORE volume and a large evaluation record or loop file to the EVAL
  volume (`isolation.stage_blob` / `read_staged`: content-addressed sha256 paths chosen by the driver, hash-checked on read, 0700
  directories and 0600 files under mounts the lockdown makes 0700) and returns a small ref; the caller commits the volume (commit does
  not remount); the orchestrator downloads (`Backend.stage_get`) or forwards the ref, passes large EVALUATION INPUT models by ref
  (`Backend.stage_put`), and clears a round's staged artefacts at its end (`Backend.stage_clear`). `Backend.run_iso` / `run_iso_packed`
  refuse an inline payload above the limit before submission (its size as Modal's serializer ships it); an output still too large
  inline fails its job with a clear error. The iso "call" role takes large input models by ref too (`model_refs`, read and hash-checked
  by the driver); a large call result goes to the EVAL volume when the container mounts it, else (a fit class, public data only) to the
  STORE volume.
- FRESHNESS: a packed container reloads its volumes once per wave GENERATION (`Backend.run_packed` stamps every wave), draining its busy
  slots before a newer wave's refresh; no per-input reload (it hid files from other slots) and no payload-level commit on packed classes.
- ONE UID PER LIVE WORKER (P2's finding, 2026-09-27): a worker's uid was a function of its role, so all phase-A workers of all models of
  one job shared it, and a worker start (which SIGKILLs its uid's processes) killed the other models' idle workers; their next calls
  failed (WorkerDied, BrokenPipeError) and `safe_call` scored them as the METHOD's failures. `LinuxUidTransport` now gives every live
  worker its own uid of the transport's block (the slot's block; the role's own uid when free, else the free uid used longest ago),
  a start and a clean-up kill only their own uid, and the uid returns to the pool only after its processes are gone
  (`_take_uid` / `_give_uid`; more live workers than uids raises an InfraFault). A reused uid's previous worker left nothing behind:
  its processes killed, its IPC objects removed, its working directory (the only place a worker uid can write after the lockdown)
  deleted. Docker and local transports never killed by uid and were not affected.
- A DEAD WORKER IS INFRASTRUCTURE: `WorkerDied` is an `InfraFault` (a BaseException), so no `except Exception` on the evaluation path can
  swallow it. `RemoteFresh` restarts the phase's worker once and retries the same call (the fresh process has seen nothing; the digest
  record is reset); a second death in a row, or a worker that does not start twice, fails the job loudly. The container callable returns
  an InfraFault as {"__infra__": True, "error": "InfraFault ..."}, never as the job's result; `Backend.run` re-submits it (at most
  MAX_CALL_FAILS times; the final error says "call failed repeatedly ... InfraFault"), the Level C and post-lock executors match
  "InfraFault" as infrastructure. `PackInfraError` is an InfraFault too (before, a dead packed child driver became the job's error
  result). Timeouts and protocol violations stay the METHOD's failures (a call over its 900 s, a worker that corrupts the protocol).
- PRE-STARTED SPARES (`RemoteFresh(spares=3)`, `isolation.SPARES`): a worker restart costs about 5.6 s in a packed slot, of which 4.8 s
  is the worker's init (the environment's scientific stack imported before the tripwire: no method code; method code first runs at the
  model load, 0.12 s), and the digest rule restarts 74-118 times per evaluation on the validation systems. After the first restart of a
  (sub-)phase, up to 3 workers of that phase are started in advance, up to and including their init; a restart takes the oldest and
  loads the model into it only after the old worker's processes are gone. A spare has run only trusted code and has seen no model and
  no history until then, so it is exactly a freshly started worker (identical results: tests, Modal smoke). Spares are closed with their
  phase; a uid block keeps two uids free for the live workers' own restarts.
- NUMERICS INDEPENDENT OF THE CLASS: the driver's own numerics (the evaluator's regressions and bootstraps, the loop driver, call
  targets) run with the JOB's thread count (`isolation.pinned_threads(job_threads(p))`, packed or not), as the model workers always did.
  Before this they ran with the container's CPU count (20 on iso_eval_s, 48 on the 32-CPU classes), and the same fitted models then gave
  evaluation records differing at ~1e-9 relative in the mediation and closure families (P1 dry run, LEVEL_B_EXECUTION section 5.1).

## 7. The runguard tripwire (defence in depth, not the boundary)

`runguard.install_tripwire` installs a process-wide audit hook whose state (policy, re-entrancy flag, refused-event list) lives in a
CLOSURE — there is no module attribute to assign (closes F-B2's first bypass), and the hook is process-wide so it also covers a thread
whose target is `exec` (closes F-B2's second bypass). It refuses file-system events under protected roots outside the allowed roots,
process creation, network and `ctypes` library loading, and raises early with a generic message. `install_eval_guard` is RETIRED and
raises. The tripwire is best-effort: code that walks the garbage collector can still reach the closure, which is exactly why nothing
depends on it — the boundary is the OS.

## 8. Feedback (F-M5)

`feedback.aggregate` releases, per candidate and per system kind: eligibility, the pass RATES of criteria A–H coarsened to steps of
0.05, medians of the primary metrics rounded to 2 significant digits, the verdict-category counts, and whether any fit / evaluation
failed as BOOLEANS. Cells over fewer than 3 systems are suppressed. `feedback.check_release` enforces: the validation tier only, at
most 4 rounds, at most 12 candidates per round, and a FIXED system set across a tier's rounds (a stable `system_ids_hash`; differing
sets are refused, closing the round-to-round differencing channel). The tournament `feedback` command calls it and refuses otherwise.
**Residual channel**: a developer still sees, each of ≤4 rounds, the coarsened aggregates over a fixed validation set for ≤12
candidates. A method could in principle modulate its own coarsened medians / rates to signal a few bits about the validation systems
it trains on; the coarsening (0.05 rate steps, 2-sig-fig medians), the fixed system set, the round cap and the ≥3-system suppression
bound that capacity to a small number of bits over the whole tournament, and the validation systems are never the confirmation or
real-hidden systems that decide the answer.

## 9. Coordinator items wired in

1. **Verdict inputs are only the in-family / target / near / far / hidden roles.** `harness.evaluate_model` scores every item, and the
   verdict metrics come from `verdict.collect_metrics` / `evaluate.ee_cb`, which select the `VERDICT_KINDS` from the per-item units;
   `evaluate_mediation` / `eval_closure` select the verdict items themselves. OOD and robustness items go to the 5.12 report
   (`res["items"]["ood"]`) only.
2. **Criterion F computable.** `harness.assemble_verdict(ev, refs, tol, k_refits=[...], level=...)` passes the k list to
   `verdict.collect_metrics(k_values=..., level=...)`: at Level B the round's 3 fit seeds' k, at Level C the 5 bootstrap refits of the
   training interventions (`isolation.bootstrap_interventions`; the tournament's `refits/` fits). Without them F is missing and nothing
   is SUPPORTED.
3. **Full-state bound and ID-shortcut comparator FIXED at Level B.** The tournament's `choose_bounds` picks, per system, the better on
   the validation suite of the FULL-STATE reference and the best full-state baseline (and of the ID-SHORTCUT reference and the best ID
   baseline), stores the choice in `BOUNDS.json`, and passes those effects as `fullbound_eff` / `idshortcut_eff` to the verdict.
4. **Lift whitening from PUBLIC training data.** `evaluate_model` encodes the public training histories in phase A and passes them as
   the lift whitening (`whiten_z` / `whiten_histories`), never test data; MEV / lift whitening floors are 1e-6 × max (E5 / E6).
5. **Selection from `select.py`.** The tournament calls `select.per_system_values`, `select.rank(candidates, true_state=, full_bound=,
   systems=)` and `select.halve(order, baselines, eligible=, carried_baseline=, finalists=)`; it never re-implements the rule.
6. **`verdict.build_primary_family` hook.** The Level C driver builds the primary family (H1–H6, Holm at alpha 0.05; PROTOCOL 11) with
   `verdict.build_primary_family(suite=..., networks=..., margins=...)` and `verdict.primary_estimates` per real full network, and the
   overall conclusion with `verdict.phase4_conclusion(..., synthetic_capped_at_partial=...)`. The active-design success rule of
   PROTOCOL 5.17 is one-sided at alpha 0.025 for each of its two arms (`loop.active_success`).

## 10. Residual risks

- `/proc/<driver>/cmdline` is readable by a worker (the probe): it exposes only the driver's argv (`python -m ...`), never data or
  secrets. The driver passes no secret on its command line.
- The tripwire is reachable through the garbage collector; it is defence in depth, not the boundary (section 7).
- A read-only Modal mount cannot be locked down, so any volume a worker uid must be kept off is mounted read-write and chmodded by the
  driver; a new sensitive mount added later must follow the same rule (asserted implicitly: fit / loop classes do not mount `eval`).
- The feedback residual channel of section 8.
- GPU iso classes are not host-gated (as the other GPU classes); their determinism is handled by `equiv`, unchanged.
- A worker can start a subprocess as its own uid at the OS level (no new privileges; the tripwire refuses it in normal operation);
  it gains nothing the worker itself does not have.
- Per-call overhead: every model call is a pipe round trip plus a fresh unpickle of the model (the PROTOCOL 5 fresh-copy rule, as
  before). The worker supports batched calls (`calls`), but the E5 / E6 metric code calls the model one item at a time, so batching
  is not used yet; evaluation start-up costs three worker pre-imports (about 5 s each on Modal).
- The legacy Modal job kind `method` (`remote.run_method`: one guarded subprocess whose result file is unpickled) still exists for
  E4's infrastructure smoke (`scripts/p4/modal_p4.py smoke-method`); tournaments, fits, loops and evaluations never use it.

## 11. The developers' simulation service on the reference platform (fork E12; LOG P4-D32 / P4-D33)

WHY. The synthetic generator is bit-identical across Linux environments with the pinned stack (the Modal containers and the local
sandbox image `brainir-p4-sandbox:1`: 50 / 50 dev-tier content hashes equal) but not on the Windows host (11 / 50). Official builds
plan in the image (`scripts/p4/plan_synthetic.py`) and simulate on Modal; the service that answers the developers' `SimClient`
requests must compute on the same platform, or its records differ from the benchmark's (store keys carry the system content hash,
so restarts from public trajectories would be refused, and fresh simulations would differ in the last bits).

TWO PARTS (`brainir_causal.simservice` + `brainir_causal.simdocker`):
- HOST PART (`SimServer`, unchanged in behaviour): the room's per-agent queues `simq/<scratch>/`, identity by launcher-issued tokens,
  the public policy, budgets and ledgers (outside the room), served keys, the public restart-source table and, with `--modal`, the
  Modal client for real FULL networks (gated hosts; their restart sources are read from the volume store). It never builds a
  generator system: synthetic engine ids come from the container (`DockerPool.describe`).
- WORKER CONTAINER (`DockerPool`, CLI `--docker`): every local simulation (synthetic systems, real mechanisms; real FULL networks too
  when no remote backend is configured) runs in ONE container of the service worker image `brainir-p4-simsvc:1`
  (docker/p4simservice, id in its image.json: the pinned sandbox image plus `duckdb==1.5.5`, which the real engine's graph loader
  imports, installed `--no-deps`; `build-image` refuses a sandbox tag that is not the pinned id and a build that changes any other
  package, by pip freeze): `--network none`, read-only root with a private /tmp, all capabilities dropped, no new privileges,
  uid 1000, CPU / memory caps, the host gate's numerics pins (`CPU_PINS`, one BLAS thread). Only `simservice.run_job` is sent to the
  container (recognised under any module name, so `python -m brainir_causal.simservice` works); any other non-builtin callable is
  refused, never run on the host. Mounts: phase4/src, src/brainir, the previous public bundle (at its repository-relative path) and the hash-locked
  generator (at `suites.GENERATOR_CONTAINER`) READ-ONLY; read-write only the service store and the bridge directory, both under
  `C:/Dev/BrainIR_p4audit/simservice/<room>/`. The container never sees a room, a queue, a token table or a ledger. Jobs and results
  cross as files (job JSON with container paths; result JSON + an .npz of t, x, u, y read with `allow_pickle=False`); a job error
  ends as the service's generic "simulation failed (reference ...)". A heartbeat counter (the container's own monotonic clock) stops
  the container if the host part dies.

CACHE ISOLATION (review F round 2, N-M1). Every token-identified agent has its own store namespace
(`SimServer.store_for`: `<store>/agents/<name>-<hash>/`, a complete TrajectoryStore; the Docker pool maps it below `/svc/store`), so
another agent's requests never change the files a request reads or writes, nor its latency; an agent's own repeats come from its
namespace, public restart sources are recomputed into it on first use, and an agent's remote job neither reads nor writes the shared
Modal volume store (job["fresh"]). Trusted in-process callers share the service store. Tokens are bound to the agent's queue.

PUBLIC RESTART SOURCES. The table (`simservice.build_public_keys`, format `p4-public-keys-2`) lists every row of the room's public
dataset directories (items, twins, components, pool sources) with its store key, system, sampling and PUBLIC PROTOCOL; store keys
are accepted as aliases of their rows. The public store records (full microstates) exist only on the Modal volumes, so a public
source missing from the request's store namespace is RECOMPUTED from its protocol before the restart (`SimServer._ensure_source`; recursively,
at most 8 levels, for a source that restarts itself; not charged to the agent; counted per request as `public_sources_recomputed` in
the orchestrator log). The recomputed store key must equal the public record's (canonical protocol, system content hash, engine),
else the request fails with the generic error and the details go to the error log. Public parts never hold state carriers, so every
public protocol is self-contained.

OPERATION. `scripts/p4/simservice_docker.py start --room clean [--modal]` writes systems.json (the internal records of the room's
public systems), public_keys.json and launch.json (host command, the container's docker command and mounts, pids, counts) under
`C:/Dev/BrainIR_p4audit/simservice/<room directory name>/` (where the agent launcher writes the token table) and starts the host
part detached; `status` and `stop` manage both parts.

EVIDENCE. `phase4/tests/test_simservice_public_sources.py` (table building, on-demand recomputation equal to the original record,
refusal of a source that does not reproduce, recursion, and the Docker pool answering `run_job` bit for bit like a separate container
of the image). `scripts/p4/simservice_docker.py selftest` (`research/phase4/SIMSERVICE_DOCKER_SELFTEST.json`): one dev system's
public part built IN THE IMAGE by the benchmark's code; the service with an EMPTY store, a token-identified fake agent and its own
queue; a public row's protocol returns the dataset's arrays, restarts from public trajectories (sources recomputed) and a fresh
protocol equal the benchmark's `SimContext` on the build's store, bit for bit; a real mechanism's public row computed in the container
equals the Modal-built dataset arrays and a restart from it is served (its source recomputed); `--compare-modal`: all 529 rows the
image built for that system are among the Modal build's 713 public rows with identical store keys and protocols, and 12 sampled
trajectories are bit-identical. The launcher itself was exercised end to end on a scratch room (start, a synthetic and a real
request from a token-identified agent queue, status, stop): every store record carried the container's (Linux) host fingerprint.
