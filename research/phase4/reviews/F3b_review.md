# Review F3b: round-3 follow-up (isolation re-check of the revised generator's public surface)

Reviewer F. Scripts are in `.tmp/F/r3b/`; every number comes from my own runs in the sandbox (`sbx`) unless marked **evidence** (read, not run).

**Generator version:** `extra/generator/` is the revised generator; the public-surface changes are in section 15 ("Revision v3"), not section 14. The data are `data/synthetic_dev` (10 public systems, rebuilt).

**Side effects:** none. Nothing outside `.tmp/F/r3b/` and this file was written. I did not use `sbx --stop` on other agents' containers (see NF-3).

## 1. Per-item table

| # | item | result | evidence (my runs unless marked) |
|---|---|---|---|
| 1a | benchmark's own public checks on the rebuilt dev data | **pass** | `checks.py`: `suites.assert_public_part` passes on all 10 `data/synthetic_dev` systems. The raw generator record fails `assert_public_record` (non-public keys `content_hash`, `edges`, `engine_id`, `targets`), as it should: the builder strips or partitions them (`suites.synthetic_records`). |
| **1b** | published records: type / k / role cues | **FAIL (NB-1 blocker, NF-5 major)**; readout_dim / sizes fixed | `pg.py`: `readout_dim` 9–20 on the 10 systems (round 2: 8 ⇔ types 20/21); dt 0.001, t_end 2.0 and input_dim 1 everywhere; `public_graph` null. **But** the capability's intervention magnitudes flag the no-compact controls, and type / k are above chance: see §1.1. |
| 1c | non-full `simulate()` info; public row info | **pass** | Published rows: info keys = {`host`, `success`} only (7,098 rows); meta keys whitelisted; no clipping / realized-size / step-count fields. The generator's non-full info is in §1.1. |
| 1d | realized-size kick classes (`meta.mclass`) | **pass** | `mclass.py`: in every system, `mclass` is monotone in the REQUESTED kick size: 0 of 14,026 ordered pairs of single-target kicks inverted. The class carries no clipping / realized-size information (moderate kicks no longer clip). |
| 1e | capability record | **pass** (published); generator-side remark | The generator's capability still holds one per-unit list, `init.units = list(range(n_units))` (`system.py:533`: all units, so no role content). `sampling.normalize_capability` replaces it with `"observed"` in every published and internal record (manifests: `init.units = "observed"` on all 10). |
| 1f | manifests, pools, lift cases | **pass** | `pubscan.py`: manifest system keys = the `PUBLIC_RECORD_KEYS` set; pool keys and lift-case keys whitelisted (no truth, no carrier, no state). |
| **1g** | **held-out targets derivable from the public record** | **FAIL (NF-1, major)** | see §2 |
| 2a | nothing public imports `suites` at module level | **pass**, with remarks | `modsplit.py`: importing every `PUBLIC_MODULES` module from the built public directory loads only public modules. Function-local imports of orchestrator modules remain: `harness.py:245/275/565/577/604/628` (`evaluate_truth`, `synthadapter`, `store`, `isolation`), `loop.py:169` (`simservice.check_public`), `equiv.py:153` (`p4modal`). They are driver-only paths; in a worker or method room they raise ImportError. |
| 2b | worker pubdir excludes `suites` | **pass** | `isolation.build_pubdir` ships 29 files: `PUBLIC_MODULES` (incl. `sampling`, `accounting`, `runguard`, `worker`); no `suites`, `simservice`, `synthadapter`, `store`, `isolation`. |
| **2c** | method-room module list | **FAIL (NF-2, minor, build-breaking)** | `CLEAN_MODULES` includes `accounting` (`make_phase4_cleanroom.py:265-270`), but `NAMES_ORCHESTRATOR` (`:100`) still names `accounting` (and `runguard`). `check_source(accounting → clean room)` returns "orchestrator-side module name in a method room: src/brainir_causal/accounting.py", so the clean room cannot be built (or would be built without the module `refs` / `loop` import). |
| 3a | `_ensure_source` bit-for-bit check | **pass** | `simservice.py:598-634`: store key AND the arrays t/x/u/y compared with the public trajectory file; on mismatch the record is removed and RuntimeError raised. It runs per agent namespace (no cross-agent effect) and is not charged. |
| 3b | error texts toward agents | **pass** | ensure-source, simulation and platform-gate failures (`run_job` → `gate.require_reference_platform`) surface only as `simulation failed (reference <id>)` / `protocol refused (reference <id>)` / `service error (reference <id>)`, with details in `_log_error` (ledger dir, outside the room). Verbatim texts are limited to `ProtocolError` (the public policy's own reasons; the restart ones say only "served to you or public", "same system", "not a sample time") and `PermissionError` from identity (generic). |
| 4a | can a worker read/write/list staged files? | **no** (by reading; OS part **evidence**) | Staging roots `/storevol/_staged`, `/evalvol/_staged` (dirs 0700, files 0600, created by the root driver) sit under mounts the lockdown makes 0700; workers are other uids in their own user/net/IPC namespaces (packed) and have no volume path. **Evidence:** `isolation_smoke_modal.json` `adversary_os_only`: evalvol/fitvol/storevol PermissionError. |
| 4b | can a worker influence where the driver writes, or inject a ref? | **no** | Paths are `<root>/<sha[:2]>/<sha>.bin` of bytes the driver holds; `read_staged` checks the hex format and the sha256. A fit worker's reply is reduced to `{"model", "side", "worker"}` (`fit_records`, `isolation.py:1139-1151`), so a worker cannot return a top-level `model_ref` / `result_ref` / `file_refs`. Eval results and loop file refs are built by the driver; loop file names written on the orchestrator side use `Path(name).name` (`tournament.py:912-914`). The worker chooses only its model's CONTENT (hence its sha, i.e. only its own file). |
| 4c | cross-method transfer through staging | **no** | Content-addressed dedup means two jobs share a file only if they produce identical bytes. A method's evaluation reads only the ref from its own fit record. Staged eval records and loop files go to the eval volume, which fit containers never mount. |
| 4d | lockdown kept across writes / commits / reloads | **by reading yes; evidence only in prose** | `pack_ready` drains every busy slot, reloads, then re-runs the fail-closed `container_lockdown` under the pack lock before any new slot starts. Commits do not remount (P1 probe, LEAKAGE_POLICY §2.13). The staging / pack smokes (`smoke_stage_modal.py`, `smoke_pack_modal.py`) and their results are **not in the room**. `test_pack_isolation.py` runs here: 27 passed, 1 skipped, 1 failed; the failure is a sandbox artefact (`modal` not installed, so `stale_refusal`'s `stop_fetching_inputs` hook cannot be imported; the refusal itself is correct). |
| 4e | what a successful staging attack would need | — | (i) a worker escaping its uid / user namespace to root (gVisor escape) or regaining the network; or (ii) the orchestrator mis-routing a ref (a trusted-code bug; refs are content-addressed and hash-checked, so this would need a wrong-but-valid sha in a payload); or (iii) knowledge of another job's staged sha256 plus a way to name it, which no worker has. |

### 1.1 Prediction of type / k / roles from public fields

**Run:** `predict.py`. The revised generator built 4 development-tier suites with seeds 0, 7, 11, 13 (200 systems, 25 types, 16 no-compact controls). Each system was summarised by the **benchmark's published record** (`suites.synthetic_records`), using every numeric leaf: capability, obs_scale, sizes, public targets / edges, plus degree statistics of the listed edges (84 features). Random forests (300 trees) with leave-one-suite-out cross-validation.

| target | result | baseline |
|---|---|---|
| no compact state (types 20/21) | **AUC 1.000** | 0.5 |
| type | **accuracy 0.200** | chance 0.040 |
| k | **accuracy 0.545** | majority 0.440 |

Non-full `simulate()` info keys on 8 sampled systems: exactly {`engine`, `success`, `system`} (item 1c passes).

**Which field** (the follow-up run that would have ranked features died when Docker Desktop failed; see "Sandbox outage" below). The published data show it directly:
- `capability.kick.moderate` (= `current.moderate`) is **0.5705** on `syn-01f497d7f752` and **0.7139** on `syn-1251c8ff2973`, and **7.04–69.95** on the other eight published systems.
- The last capability `moderate` behaves the same: 1.10 and 2.45 against 19.4–137.0.
- System ids are `hash("id", tier, seed, type, j)` (`suite.py:100`), so these two ids are the type-21 and type-20 systems, the only no-compact controls among the 10 published.
- The rule "kick.moderate < 1 ⇒ no compact state" is 2/2 correct with 0 false positives on the public data.

**Cause (by reading):**
- Section 15 makes the moderate kick "from the kick", i.e. measured from the system's own response.
- Types 20/21 are `SlowModes` systems built as ONE recurrent population without generator / nuisance populations (`types.py:582-610`, `size_medium(..., gen=False, max_obs=5k/3)`), so their measured intervention scale is an order of magnitude smaller.

**Why the generator's own test misses it:** `extra/generator/tests/test_public_leakage.py:34-38` summarises a system by a hand-picked list: counts, ratios, `readout_dim`, `input_dim`, dt, t_end, cost, admissible range, noise scale. It excludes the capability's magnitudes, `obs_scale` and degree-distribution statistics, although all of them are published.

**Unit roles:** my role analysis did not run (the sandbox outage came after the cached-feature step failed). Not re-verified by me; the generator's test reports core-vs-rest AUC 0.53.

**Sandbox outage:** after the first full run, Docker Desktop's engine began returning `500 Internal Server Error` on `_ping` (05:41 onward; re-tried for more than 5 minutes). Every later `sbx` call failed, so the feature-importance and role runs could not be completed. The numbers above are from the one completed run (`.tmp/F/r3b/predict.out`, first block) and from reading the published manifests on the host.

## 2. New findings

**NB-1 (BLOCKER): the published capability record identifies the no-compact-state controls.** This is round-2 N-B1 again, through another field.
- **Location:** the generator's per-system moderate magnitudes (section 15 item 4: "threshold moderate from the kick"), which `sampling.normalize_capability` keeps and `synthetic_records` publishes as `capability.kick.moderate`, `current.moderate`, … .
- **Evidence:** random-forest AUC 1.000 for "no compact state" over 200 generated systems (16 positives; leave-one-suite-out). In `data/synthetic_dev`, `kick.moderate` is 0.57 / 0.71 on the two controls against 7.0–69.9 on every other system.
- **Impact:** a method can declare "no compact causal state" from a public constant and meet the §11 gate of the synthetic conclusion (at least 2/3 of types 20/21) without learning anything. The generator's leakage test (`test_public_leakage.py`) passes only because its feature list omits the capability values.
- **Fix:**
  - Publish intervention magnitudes on a type-blind scale: a common distribution for every system, or classes defined relative to a scale that types 20/21 share with the others. Or keep the measured moderate value orchestrator-side and publish only class labels.
  - Make the leakage test use EVERY numeric leaf of the benchmark's published record (flatten `synthetic_records(...)[0]`) plus degree statistics, not a hand-picked list.
  - Re-run it on several seeds.

**NF-5 (MAJOR): type and k remain predictable above the generator's own threshold.**
- **Evidence:** type accuracy 0.200 vs chance 0.040 (5×); k accuracy 0.545 vs majority 0.440 (+10.5 points). The generator's test allows at most +3 points.
- **Impact:** type fingerprints tie a system to its trap class and k (PROTOCOL 5.16 "k = k_true", dimension criteria).
- **Fix:** same as NB-1 (the full published record in the test; type-blind magnitudes and scales).

**NF-1 (MAJOR): the benchmark ignores the generator's targetable set; hidden targets = observed − public targets.**
- **Location:** `suites.synthetic_records` (`suites.py:333`) reads `pub.get("targetable") or pub.get("observed")`, but the generator's public record calls the field `targets` (`system.py:449`) and has no `targetable` key. The builder therefore silently falls back to the OBSERVED units.
- **Evidence:**
  - `targets.py`, `targets2.py` (the builder's own internal record): internal `targetable == observed` and `targets_heldout == observed − targets_public` (True on the systems checked).
  - On the 10 published systems, `targets_public` contains 6–31 units the generator does NOT list as targetable. Held-out targets include 13 (syn-00e48aa6ad4d) and 4 (syn-2a013a2e85c0) non-targetable units.
  - The generator-targetable but unobserved units (1–14 per system) are never targets.
- **Leak:** the public record gives the complete held-out target set (`observed` is public). This contradicts `synthetic_records`' own docstring ("never lists the hidden targets … nor the full targetable set") and regresses round-1 minor 6 (fixed in round 2).
- **Correctness (for E/H):** target-shift items and public items intervene on units the generator author excluded (e.g. the defining hidden populations and graded trap targets of types 10, 15, 17, 25), so the trap semantics differ from the generator's design.
- **Fix:** rename the key (generator `targetable`, or builder reads `targets`). Make the builder REFUSE a synthetic record without it (no fallback to `observed`). Add a test that `targets_heldout ≠ observed − targets_public` is not derivable, and that `targets_public ∪ targets_heldout == generator targetable`.

**NF-2 (MINOR, build-breaking): `accounting` is both required and forbidden in the method room** (row 2c). Fix: drop `accounting` from `NAMES_ORCHESTRATOR` (and decide on `runguard`), or move the cost ledger into a public module name.

**NF-3 (MINOR): `sbx --stop` lets any agent stop another agent's sandbox jobs; `sbx --ps` lists every agent's jobs.**
- **Location:** `sbx:59-69` (and `sbx_template.sh`): `--stop` checks only the room label, `--ps` filters by room only.
- **Evidence:** `sbx --ps` from my session listed reviewer H's three running containers (names, agent label, start times). By the code, `sbx --stop <H's id>` would pass the room-label check. Not executed, to avoid disrupting H.
- **Impact:** in the shared clean room, one developer can kill another's long experiments or local evaluations. It also shows others' activity timing. Neither is covered by LEAKAGE_POLICY.
- **Fix:** filter `--ps` and require for `--stop` the label `brainir.p4.agent == $P4_AGENT_NAME` (the name the launcher sets; not assignable by agents).

**NF-4 (minor, evidence gap):** the staging and packing smokes (`scripts/p4/smoke_stage_modal.py`, `smoke_pack_modal.py`) and their result files are not in the review room. Add their JSON results to `extra/results/` so the OS-level claims of LEAKAGE_POLICY §2.13 can be checked.

## 3. Counts

17 rows:
- **Pass:** 11 (1a, 1c, 1d, 1e, 1f, 2a, 2b, 3a, 3b, 4b, 4c).
- **Pass by reading plus recorded evidence, OS part not runnable here:** 2 (4a, 4d).
- **Fail:** 3 (1b, 1g, 2c).
- **Informational:** 1 (4e).

New findings: 1 blocker (NB-1), 2 majors (NF-5, NF-1), 3 minors (NF-2, NF-3, NF-4).

## 4. Verdict

**Not ready to freeze.** Most of the revision holds:
- The public dataset files are clean: whitelisted keys, info reduced to {host, success}, and kick classes that carry no clipping.
- `readout_dim` and sizes no longer mark types.
- `suites` never reaches a worker.
- The service's new checks keep agent-facing errors generic.
- Staging on the isolated classes opens no worker-accessible channel. Paths are driver-chosen and content-addressed, workers can't inject refs, and the mounts are locked 0700. The packed and staging smokes themselves are not in the room.

Three things block the freeze:
1. **NB-1:** the published capability's intervention magnitudes still identify the no-compact-state controls (random-forest AUC 1.000; `kick.moderate` 0.57 / 0.71 against at least 7.0 in the published data). This reopens the round-2 blocker on the pre-registered §11 gate. Type and k also remain predictable well above the generator's own threshold (NF-5).
2. **NF-1:** the builder's target partition ignores the generator's targetable set, so the held-out targets are exactly `observed − targets_public` and derivable from public data.
3. **NF-2:** the clean-room build refuses the `accounting` module it requires.

