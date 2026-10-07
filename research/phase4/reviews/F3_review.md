# Review F3: leakage and isolation, third pre-freeze round (verification)

Reviewer F. All scripts are in `.tmp/F/r3/`, and every number below comes from running them with `sbx` or on the host under the guard.

**Side effects:** none. Every write attempt into a protected or foreign path was refused before it ran, by the guard or by the sandbox mounts. Probes inside my own areas created and removed empty files. Probes of other reviewers' files were append-opens with 0 bytes written, and those opens were refused anyway.

**Which generator:** `extra/generator/SYNTHETIC_BENCHMARK.md` has no section 14, so this room still holds the **round-2 generator** (my re-run below reproduces the round-2 numbers exactly). The revision announced in the notes is not verified here.

**Reviewer T:** the task names `reviews/F/T_review.md`; no such file exists. T's own review is in `reviews/T/` and is not addressed to F, so this table covers my findings only.

## 1. Per-finding table

Round-2 findings, and the round-1 findings left partly / unverified / not fixed.

| # | finding | status | fix location | my re-run / evidence |
|---|---|---|---|---|
| **N-B1** (r2 blocker) | public `readout_dim` = 8 flags the no-compact-state controls (types 20/21) | **not fixed** (generator not yet revised) | `extra/generator/src/p4synth/types.py:563,576` unchanged | `gen_meta2.py` (4 suites, 225 systems): rule `readout_dim == 8` → TP 18, FP 4, FN 0, TN 203, identical to round 2. `ydim.py`: in the rebuilt `data/synthetic_dev`, the only two systems with `readout_dim` 8 are type 21 (`syn-01f497d7f752`) and type 20 (`syn-1251c8ff2973`); all 8 others have 6. |
| **N-M1** | cross-agent cache timing oracle; portable tokens | **fixed** | `simservice.py:40-60` (identity), `:110-125` (`issue_token(queue=, revoke_queue=)`), `:528-536` (`store_for`: `<store>/agents/<name>-<hash>/`); guard refuses environment listings and naming the token | `simsvc.py` (inline pool, toy system): A's token through B's queue → refused ("missing or unknown simulation token"); through the shared queue → refused. A ran 10 protocols; B's latency on those 10 has median **123.8 ms**, on 10 fresh ones **110.1 ms** (no cache hit), and on B's own repeats **2.0 ms**. Namespaces on disk: `dev_a-…`, `dev_b-…`. Host: `printenv`, `export -p`, `declare -x` → G7; `/proc/self/environ` → G2; naming the token variable → G1. The token is visible only inside the agent's own container (`sbx env` lists its name), where it is useless outside that agent's queue. Residual: see N3-m1. |
| **N-M2** | shared work areas writable across agents | **fixed** | sbx v4: the room is read-only, only the agent's own subdirectory of each owned area is bound read-write, and other agents' `runs/`/`notes/` subdirectories are not mounted; guard ownership rule (`protected_<room>.json` `owned_areas`) | Sandbox (`owned.py`): `reviews/E`, `reviews/H`, `reviews/T` and every file in them → EROFS; the `reviews/`, `runs/`, `notes/` roots → EROFS; `runs/E`, `notes/E` → not visible; my own `reviews/F`, `runs/F`, `notes/F`, `.tmp/F` → writable; `.tmp` shows only `F`. Host: `touch reviews/E/…` G4; `cp --target=reviews/E` G4; `cd reviews && cp … E/` G2; `d=E; cp … reviews/$d/` G4; glob `reviews/[E]/` G4; `sort -uoreviews/E/…` G4; `gzip -S /../E/…` G2. The canary v4 table (`extra/results/CANARY_TEST.md`, round 3) shows the same with two agents. It was operator-run, because live agents declined the attack steps. |
| **N-M3** | size fields partly predict k | **not fixed** (generator not revised) | — | `gen_meta2.py`: every k = 4 system has `n_units > 150` (10/10); 10 of the 17 systems above 150 units have k = 4; corr(k, n_units) = 0.334. Unchanged. |
| N-m1 | GNU long-option abbreviations pass the guard | **fixed** | guard: getopt-style prefix resolution | `sort --outp=CLAUDE.local.md`, `sed --in-pl`, `sed --in-pla=`, `sed -si`, `shuf --outp=docs/API.md` → all G4. |
| N-m2 | tripwire closure reachable via `gc` | **accepted** (documented defence in depth) | EVAL_ARCHITECTURE §7 | `tripwire.py`: direct → refused; thread with `exec` → refused; the `gc` flip → READ OK. Unchanged; acceptable while the OS boundary holds (B2/B3 below). |
| N-m3 | worker module state persists within a phase | **fixed** | `isolation.py:676-690` (`history_digests`), `:800-815` (`RemoteFresh._call`: restart the sub-phase worker when the new history's last row was seen followed by more rows) | `fresh.py` (a memorising model through `RemoteFresh`): a prefix of a history the worker already saw → **new process** (pid 20 → 25). Continuing a seen history stays in the worker, which is correct: that worker already made its prediction. The rule is now **load-bearing**, see N3-m2: in the rebuilt data, 946 of 1,744 items (54 %; 48 per synthetic system) have their non-constant held-out future inside another item's longer history. For **all 946** the digest rule would restart the worker (0 misses, `memo.py`). |
| N-m4 | constant all-zero item futures (real) | **partly** | dataset design v2 | `degen.py`: 16 of 1,744 items (real_A_m1 5, real_A_m2 3, real_C_m2 5, others 1 each), down from 26; synthetic 0. Not a leak; handed to E/H. |
| B2 (r1), OS part | fit/loop boundary = OS, not the in-process guard | **unverified** by running; evidence consistent | `isolation.LinuxUidTransport`/`DockerTransport`, `container_lockdown` | `extra/results/isolation_smoke_modal.json`, `adversary_os_only` (tripwire OFF): evalvol, fitvol, storevol, repo, other_jobs, driver_environ, driver_mem → PermissionError; net → OSError; dns → gaierror; write_tmp → PermissionError; setuid0 → PermissionError; `env_modal` = []. A same-uid `subprocess` is possible (documented). Lockdown: the three volumes' resolved targets and `/repo`, `/root`, `/home`, `/mnt`, `/srv` at 0o700. I cannot run Modal or Docker-in-Docker. |
| B3 (r1), OS part | held-out data only in the driver | **unverified** by running (the process split was verified in round 2); evidence consistent | same | Same file: `lift_after_reveal` refused, `rollout_in_C` refused, workers `uid 10010`, phases A/B1/B2; `isolation_probe_modal.json`: `/proc/<driver>/mem`, `environ`, `maps` denied, `cmdline` readable (documented), Modal API "Token missing". |
| M4 (r1) | self-declared simulation identity | **fixed** | via N-M1 | see N-M1 |
| **M5 (r1)** | feedback covert channel / release caps | **partly** | `feedback.py:128-185` (`release`: persistent `RELEASE_LOG`, the only path; no override flags) | `fb.py`: r1–r4 (set A) → RELEASED; r5 in a later call → refused (cap across calls); r6 with set B → refused; conf tier → refused. **But re-releasing a round id already in the log with DIFFERENT content passes.** `r1` with new candidates `m7, m8, m9` → RELEASED; `r2` with `m10` → RELEASED; the log still counts 4 rounds (3 release events). `release` checks only the round id and its system fingerprint for known rounds, not the content, so re-running a tournament round under an old id releases unlimited new aggregates. Fix: store a sha256 of each round's aggregate and refuse a release whose aggregate for a known round differs, or make round ids single-use in `tournament.py run`. |
| M7 (r1) | remote dev runner isolation | **unverified** by running; evidence consistent | `devrun4.py` (Modal Sandbox, `block_network`, uid 65534, read-only devdata) | `extra/results/devrun4_isolation_smoke.json` (CPU and T4): DNS refused; `/proc/1/environ` and the parent's environ denied; `/devdata` write denied; `/room/src` write denied; `/bin/sh` refused; a child **without** the hook: DNS gaierror, TCP OSError, `modal` not importable. |
| m2 (r1) | `TestItem` arrays are views | **not fixed** | `evalio.py:115` still `np.asarray(v, dtype=np.float64)` | Low impact now: workers receive pickled copies; only trusted in-process references alias. |

**Counts (14 rows):** fixed 5 (N-M1, N-M2, N-m1, N-m3, M4); partly 2 (M5, N-m4); not fixed 3 (N-B1, N-M3, m2); unverified 3 (B2-OS, B3-OS, M7; the recorded evidence is consistent); accepted 1 (N-m2).

## 2. New findings

No new blocker. The remaining M5 gap (re-release of a known round id) is counted under M5 above, not twice.

- **N3-m1: the simulation worker container is unreviewable and shared by every agent.**
  - `brainir_causal.simdocker` (`DockerPool`, EVAL_ARCHITECTURE §11: "every local simulation … runs in ONE container") is **not in the review set**: `extra/brainir_causal/` has no `simdocker.py`, although `simservice.py`, `tournament.py` and two tests import it.
  - Per-agent store namespaces close the cache channel (verified above), but one container serving all agents still leaks another agent's *activity* through queueing delay. That is load, not content. LEAKAGE_POLICY §2.9 itself reports per-pair spreads of 90–150 ms on a loaded host.
  - Fix: add `simdocker.py` to the review allowlist, and document the contention channel (or use per-agent worker containers / fair-share scheduling).
- **N3-m2: the fresh-worker rule is now load-bearing and has an exemption.**
  - Dataset design v2 ("every item equals its twin up to its onset") makes 54 % of items' held-out futures appear inside other histories (946/1,744).
  - `history_digests` skips the check when a history's last row is "uninformative" (all entries equal, or equal to the first row). A memorising model matches the whole prefix, not only the last row, so the exemption is unnecessary. It misses nothing on today's data (0 of 946).
  - Fix: key the rule on the digest of the whole prefix (or on any row), and add a build-time test that runs the item / pool / sample call sequence of every public and held-out set through `RemoteFresh` bookkeeping and asserts no worker receives a history after a longer one containing it.

**My area applied to the new parts:**
- **Owned areas:** hold on the host and in the sandbox (N-M2 row).
- **Token binding and environment-listing refusals:** hold (N-M1 row).
- **Per-agent store namespaces:** no cross-agent cache/timing channel left in the service logic (N-M1). The load channel remains (N3-m1).
- **Persistent release history:** holds across calls, except for the re-release gap (M5 row).
- **Public files:**
  - No earlier-phase outcome or answer phrase in `docs/` (search for phase/earlier/oracle/answer references: only generic literature uses in METHODS_REVIEW.md).
  - `data/`: 67 manifests / lift cases / pools plus all index rows, 578 distinct keys and 380 distinct string values, all generic. Real systems are anonymous (`real:A:full` …, "real system 1…10" in the calibration targets, which cover exactly the 10 public real systems, so no hidden system's statistics). No explicit initial states remain; carrier records none (checked in round 2; the design-v2 build notes say 0).
  - I could not scan for the dataset / circuit names themselves: the guard refuses those words as input, and I did not circumvent it. That part rests on the builder's scanner.

## 3. Verdict

**Not ready to freeze.** The isolation stack is now in good shape:
- owned areas, queue-bound tokens, per-agent store namespaces, getopt-aware write checks and fresh workers all hold under my re-runs;
- the Modal / dev-runner evidence is consistent with an OS-level boundary (unverified by me, since it can't run here).

Three things remain:
1. The round-2 blocker **N-B1** and major **N-M3** are unchanged, because the room still holds the round-2 generator: `readout_dim` = 8 identifies the no-compact-state controls (TP 18 / FP 4 / FN 0), and size fields partly give away k = 4. The announced revision must be synced and re-checked, including the classifier test proposed in round 2.
2. The feedback release gate can still be bypassed by re-releasing a known round id with new content, which gives unlimited aggregates under the 4-round cap (M5 partly).
3. The simulation worker module (`simdocker.py`) should enter the review set before the freeze.
