# Review F2: leakage and isolation, second early round (verification)

Reviewer F. All scripts are in `.tmp/F/r2/`, and every number below comes from running them with `sbx` or on the host under the guard.

**Side effects:** none this round. Every write attempt on a protected file was refused, either by the guard or by the NTFS ACL. The sandbox probe of `reviews/E_review.md` and `reviews/H_review.md` opened them for append and wrote 0 bytes; their mtimes are unchanged (verified).

**What I could not run:** Modal (the iso containers, the dev runner) and Docker-in-Docker (`DockerTransport`). Claims that rest only on those are marked **unverified**.

## 1. Per-finding table (round 1 → round 2)

| # | round-1 finding | status | where fixed | my re-run / evidence |
|---|---|---|---|---|
| B1 | true latent `z` in public `futures.npz` | **fixed** | `suites.py:164` (`PUBLIC_FUTURE_KEY`), `:1917-1930` (truth arrays kept apart, whitelist asserted before writing), `:1762-1767` (load-time check) | `keys.py`: across all 22 public directories (10 synthetic dev, 10 real, 2 toy), the only future suffixes are `none_{y,x,u}`, `<kind>_y`, `floor_y`, `r32_y`, `cont_y`. Zero `_z` arrays. Traj npz hold only `t`, `x`, `u`, `y`. |
| B2 | runguard switched off by `_TL.busy` or a thread with `exec` | **fixed** in-process; OS boundary **unverified** | `runguard.py:187-216` (closure state, process-wide hook); `install_eval_guard` retired (`:224`); the boundary moved to model workers (`isolation.py`) | `tripwire.py`: the module attribute is gone; direct open → refused; thread with `target=exec` → refused. A `gc` walk still reaches the closure and flips the flag (`closure flags flipped via gc: 1` → READ OK). This is documented as defence in depth (EVAL_ARCHITECTURE §7) and acceptable only if the OS boundary holds. I could not run that boundary (uids/chmod on Modal, `DockerTransport`). |
| B3 | method code in the process that holds held-out answers | **fixed** (process split); OS permissions **unverified** | `isolation.RemoteFresh`, `worker.py`, `harness.evaluate_model` phases A → lift → C | `b3.py`: an adversarial model evaluated through `RemoteFresh` over `LocalUnsafeTransport`. Its `gc` scan inside the worker found 0 `TestItem`/`PoolState`/`StateSample`/`ExperimentSet` objects and 0 arrays > 2000 elements, although the driver held 24 items. The worker's environment is the scrubbed list. **Residual:** a worker keeps module state across calls within a phase (`calls_in_process`: 1 → 2). `memo.py`: I searched the rebuilt data (1,744 items) for any history handed to a phase-A worker that contains another item's held-out future. 26 matches, all constant all-zero futures (std 0), so nothing exploitable today (see N-m3). |
| B4 | host guard: `sort -o`/`cp`/`sed w` rewrite protected files; `./sbx` replaceable | **fixed** | guard v3 (G4/G8 classes); `ntfs_protect.py` deny ACEs; bare `sbx` only | `sort -o CLAUDE.local.md`, `cp … docs/API.md`, `sed -n 'w sbx'` → G4; `./sbx` → G8. The OS backstop works: two guard **bypasses** (N-m1) reached the file system and were refused by the ACLs. `sort --outp=CLAUDE.local.md` → "Permission denied". `sed --in-pl` on `docs/API.md`, `sbx`, `CLEANROOM_MANIFEST.json` and `src/brainir_causal/evaluate.py` → "couldn't open temporary file: Permission denied". No mtime changed. |
| B5 | clean-room manifest names the circuit / earlier artefacts | **fixed** | builder: the in-room manifest holds path/sha256/bytes only; names live in `scripts/p4config/names.py` (placeholder in this room) | The manifest's key set is `path`, `sha256`, `bytes` ×15385, plus `room_kind`, `created_utc`, `n_files`, `note`, `work_areas`. It has no `refusal_list`, `source` or `source_sha256`. |
| M1 | de-redaction oracle; names surviving redaction | **fixed** (oracle); name residue **not verified by me** | the in-room manifest has no source hashes; whole-line `<redacted line>` fallback | 0 occurrences of `source_sha256`/`source`/`redacted` in the manifest. Only 13 `<redacted` markers in the room (LEAKAGE_POLICY, README, builder). With no hash of the unredacted text in the room, the oracle is closed. I tried to re-scan the room for the round-1 name terms, but the guard refuses those words as input (G1). I did not circumvent it, so the absence of names is **unverified** by me; it rests on the builder's normalised scanner. |
| M2 | guard messages echo patterns (oracle) | **fixed** (echo); membership oracle remains (documented) | guard: generic `[G<n>-<id>]` messages; details only in the outside log | Observed: `BLOCKED by the room guard [G1-cecc3240]: this input is not allowed in the room.` Allow/deny itself remains a yes/no oracle (LEAKAGE_POLICY §4, accepted). |
| M3 | container can plant `sitecustomize`/`.pyc`/nested `CLAUDE.md`; room writable | **fixed** | sbx v3: read-only room root, work areas bound read-write, per-agent `.tmp`, `PYTHONDONTWRITEBYTECODE`/`PYTHONPYCACHEPREFIX` | `rw2.py`: `/room/src`, `/room/tests` and `/room` → EROFS; `__pycache__` absent; `/room/.tmp` lists only `F`. **But** other agents' files in shared work areas are writable (N-M2). |
| M4 | self-declared sim identity: free budget, `cached` oracle, readable ledgers | **partly** | `simservice.py:86-109,445-459` (tokens), `:82` (client ledger without the cached split), `:651` (generic errors) | `simsvc.py`: no token (with `agent='dev_A2'`) → "missing or unknown simulation token"; the `agent` field is ignored; A's budget of 3 is enforced; items carry no `cached` field. **Remaining:** (a) a **timing oracle**: B re-requesting protocols A already ran is answered in 5.1/2.8/3.0 ms, fresh ones in 293/275/265 ms (about 60–100×), so cross-agent cache membership is still observable; (b) the token is not bound to a queue and is readable on the host (`printenv P4_SIM_TOKEN` is allowed: 64 characters) and in the container environment. See N-M1. |
| M5 | feedback covert channel / differencing | **partly** | `feedback.py:26-29,62-85,110-120`; `tournament.py:552-560` | `fb.py`: 5 rounds in one call → refused. But rounds 1–4 (set A) in one call → RELEASED, and rounds 5–8 (set B) in a **later call** → RELEASED: the round cap and the fixed-system-set rule hold only within a call and keep no state between releases. A round without a fingerprint passes the set check (`{A, None}` → RELEASED). `--allow-nonval` and `--allow-changed-systems` switch the rules off. The coarsening (0.05 rate steps, 2-significant-digit medians, booleans) is in place. |
| M6 | public keys/seeds brute-forceable; 32-bit tier seed | **fixed** (code-verified) | `suites.py:188-195` (128-bit HMAC tier seed), `:207-228` (salted hidden, public and stream seeds), `:142,1104-1122` (salted streams for `SALTED_TIERS` = val, conf, real B/C) | The code shows val/conf seeds and their public parts are derived from the salt, so the key oracle can no longer confirm a guess (2^128). Dev/toy/real-public stay unsalted by design. |
| M7 | remote dev runner job guard not reviewable | **fixed per code; unverified** | `devrun4.py:16-19,62,116-126,170-186`; `extra/scripts/devrun4_site/` now present | Code: Modal Sandbox with `block_network=True`, read-only dev volume, job as uid 65534, environment built from scratch. Not runnable here; the smoke JSON the policy cites is not in the room. |
| m1 | `tools/remote_run.py` NameError on import | **fixed** | client template uses Python literals | `sbx python tools/remote_run.py --help` → "commands: submit, status, wait, classes". |
| m2 | `TestItem` arrays are views (safe only by dtype accident) | **not fixed** | `evalio.py:115` still `np.asarray(v, dtype=np.float64)` | Unchanged. It matters less now (the worker receives pickled copies of the arguments, not the driver's objects), but in-process trusted references and any float64 input still alias. |
| m3 | forbidden-text patterns bypassed by globs / false positives | **fixed** | guard v3: expansions checked; names are no longer text-refused for in-room paths | `cat extra/scripts/p4agent/py*/site*.py` → allowed and harmless (the word itself is no longer forbidden). |
| m4 | agents' `.tmp` shared | **fixed** in the sandbox | per-agent `.tmp/<scratch>` mount | `/room/.tmp` shows only `F`. Host listing of others' `.tmp` is a documented residual. |
| m5 | sim-service error echo | **fixed** | `simservice.py:651` "simulation failed (reference …)"; details to an outside error log | Code read. |
| m6 | hidden targets = complement of public ones | **fixed** (synthetic) | the targetable set is not public and is not all units | `m6.py`: on the 10 published dev systems, targetable ≠ all units and is absent from the public record (e.g. 104 units, 68 targetable, 49 public). |
| m7 | blacklist pass-through of generator fields | **fixed** | `suites.py:147-162` `PUBLIC_*_KEYS` whitelists | `rows.py`: row keys = {family, info, key, meta, protocol, provenance, split, system_id}; info keys ⊆ `PUBLIC_INFO_KEYS`; manifest and system-record keys whitelisted. |
| m8 | eval-pool sequences reuse the public rng | **fixed** | `suites.py:1697` `salted_stream_seed("pool-seq", …)` | Code read. |
| m9 | frozen baseline scanner exemption | **accepted, tracked** | names config `FROZEN_CONTENT_EXEMPT`, LEAKAGE_POLICY §4 | n/a |

**Counts:** fixed 13 (B1, B4, B5, M1\*, M2, M3, M6, m1, m3–m8; \*oracle part); fixed in-process with the OS part unverified 2 (B2, B3); partly 2 (M4, M5); unverified 1 (M7); not fixed 1 (m2); accepted 1 (m9).

## 2. New findings

### BLOCKER

**N-B1: the public system record reveals the "no compact causal state" controls, a gate of the pre-registered synthetic conclusion.**
- **Location:**
  - The generator hard-codes the readout dimension per type/variant: `extra/generator/src/p4synth/types.py:563` (type 20: `set_readout(lat, g, 8, …)`) and `:576` (type 21: 8). The only other 8s are one variant each of types 1 and 2 (`:167`, `:186`); almost every other type uses 6, 5, 9 or 12.
  - `readout_dim` is a public field (`system.py:448`; it is also the width of every public `y`).
- **Evidence:** `.tmp/F/r2/gen_meta.py` and `gen_meta2.py` built the generator's suites with the public dev seed and three arbitrary (non-secret) seeds for the val/conf tiers, 225 systems in total.
  - The rule "declare no compact state iff `readout_dim == 8`" scores TP 18, FP 4, FN 0, TN 203.
  - On the 10 published dev systems, `readout_dim` is 8 on exactly 2, and both are types 20/21. Every other published system has 6.
  - Across the 50 dev systems, the public signature (n_units, n_observed, kinds, readout_dim, input_dim, n_edges) is unique per system and maps to exactly one type in 50 of 50 cases.
- **Why it invalidates a pre-registered claim:** PROTOCOL.md §11 makes "no compact causal state declared on at least 2/3 of the non-compressible controls (types 20, 21)" a condition of the Synthetic part being SUPPORTED, and §5.16 scores it. A method can meet that condition with 100 % recall from a public constant without learning anything about interventional compressibility. The validation feedback would confirm the rule within the 4 rounds.
- **Fix:**
  - Draw `n_y` (and the silent-channel count) from one type-independent distribution for every type, seeded per system; then re-check that no public field separates types 20/21 (AUC ≈ 0.5).
  - Add a generator test that fits a shallow classifier from public-record fields to (type ∈ {20, 21}), and to k, on several seeds, and fails above a small margin.
  - See also N-M3 for k.

### MAJOR

**N-M1: the sim-service cache is still observable across agents through timing, and tokens are portable.**
- **Location:** `simservice.py` (store shared by all agents of a room; tokens not bound to their queue directory); the guard allows `printenv` on the host.
- **Evidence (`simsvc.py`):** agent B requests three protocols agent A already ran: 5.1/2.8/3.0 ms. Three fresh ones: 293/275/265 ms. With the Docker pool or a real engine the gap is larger. Any process holding a token is charged to that token's owner from any queue.
- **Impact:** within a room this reveals other developers' experiments, and budgets can be spent under someone else's identity. Combined with N-M2, a developer can plant code in another developer's method that writes that developer's `P4_SIM_TOKEN` to `runs/`.
- **Fix:**
  - Per-agent store namespaces, or answer cached and fresh requests with the same (padded) latency.
  - Bind each token to its `simq/<scratch>` queue, and refuse a token arriving from another queue.
  - Refuse `printenv`/`env` output of `P4_SIM_TOKEN` on the host (or deliver the token only to the container, never to the host shell).

**N-M2: shared work areas are writable across agents (the policy says read-only).**
- **Location:** `sbx` binds `reviews/`, `runs/`, `notes/` (clean room: also `src/brainir_causal/methods/`, `tests/methods/`) read-write for every agent. The guard has no per-agent ownership check outside `.tmp/` and `simq/`. LEAKAGE_POLICY §4 states that agents "can READ (not modify) each other's work-area files".
- **Evidence (`rw2.py`):** from my sandbox, `/room/reviews/E_review.md` and `/room/reviews/H_review.md` open for writing (append mode, 0 bytes written, mtimes verified unchanged).
- **Impact:** in the clean room one developer can edit another's method or tests. That allows sabotage, and code the victim then runs in their own sandbox can exfiltrate their `P4_SIM_TOKEN` (N-M1). This is outside the orchestrator's evaluation boundary, but it undermines attribution of methods.
- **Fix:** per-developer subdirectories (`methods/<prefix>/`, `runs/<prefix>/`, `notes/<prefix>/`), bound read-write only for their owner (read-only for others), and a matching guard ownership rule.

**N-M3: public metadata predicts the true dimension on part of the suite.**
- **Evidence (`gen_meta2.py`, 4 suites):** every k = 4 system has `n_units > 150` (10 of 10). Of the 17 systems with `n_units > 150`, 10 have k = 4. corr(k, n_units) = 0.33.
- Type fingerprints are unique (N-B1), so anyone who learns a type's k (e.g. through feedback) can map it everywhere.
- **Impact:** "k = k_true" (PROTOCOL 5.16) and the dimension criteria can be partly met from metadata.
- **Fix:** decorrelate `n_units`/`n_observed`/`n_edges` from k and type (common size distribution), and apply the classifier test proposed in N-B1.

### Minor

- **N-m1: the guard misses GNU long-option abbreviations.** `sort --outp=FILE` and `sed --in-pl` pass the guard (G4 does not fire). The NTFS ACL refused both on every protected path I tried. For non-ACL'd paths (other agents' work-area files, N-M2) the guard is the only barrier. Fix: canonicalise long options by unambiguous prefix (as getopt does) before checking.
- **N-m2: the tripwire closure is reachable through `gc`.** This is documented (EVAL_ARCHITECTURE §7) and demonstrated (`tripwire.py`). It is acceptable only while the OS boundary is the real one; keep a Docker adversarial test (`test_eval_isolation_docker.py`) in CI on the pinned image.
- **N-m3: workers keep module state across calls within a phase.** The PROTOCOL fresh-copy rule is met only per call (a fresh unpickle), not per process. Today no phase-A history contains another item's non-trivial future (26 hits, all constant zero). A future builder change (e.g. several items from one source trajectory at increasing onsets, predicted in a different order) would let a memorising model look up futures. Fix: add a build-time assertion that no history handed to a phase-A worker contains another item's post-onset segment, or order the calls by onset per source.
- **N-m4: degenerate real items.** 26 real-mechanism items (real_A_m1, real_C_m2, real_C_m3) have an all-zero microstate future over 1000 steps (std 0). This is not a leak, but it is worth reviewer E/H's attention: such items add no information to EE/closure.

## 3. My area applied to the new parts (generator and rebuilt data)

These checks came out clean:
- **Public data:**
  - No truth arrays anywhere in the public data (B1 re-run).
  - Public row, info, meta, manifest and system-record keys are whitelisted.
  - All public restart keys and lift-case keys refer to public rows: 0 restarts to non-public keys, 0 carrier records.
  - The 1,364 explicit `r0: state` rows set only observed units (40–67 % of them).
- **Generator internals stay out of the public record:** unit ids are not ordered by role (the share of core units among the lowest ids tracks the core fraction, 0.08–0.87), and the targetable set is not public.
- **Host fingerprint:** the `info.host` field in public rows holds only BLAS/CPU/OS/library versions, with no hostname or paths. The Windows-computed rows are only the toy example (1,442 rows).
- **Graph structure is a legitimate, but strong, cue:** on the public edge subset, core units have higher in-degree than non-core units (per-system AUC 0.59–0.76). Interventions on non-core units never change z or y (generator truth). Since the graph is public by design, this is method-relevant structure rather than a leak, but the generator makes it an easy shortcut. Consider randomising in-degree across roles.

The leaks through public metadata are N-B1 and N-M3 above.

## 4. Verdict

**Not ready to freeze.**
- **Round-1 blockers:** the first-round blockers are fixed, B2 and B3 in their in-process parts. The OS-level parts rest on the Modal and Docker evidence, which I could not re-run.
  - Public truth arrays are gone.
  - Method code no longer shares a process with held-out data.
  - The host guard plus the NTFS ACLs now stop every write route I tried.
  - The room manifest no longer names anything.
- **New blocker:** the new synthetic generator encodes the "no compact causal state" controls in a public constant (`readout_dim` = 8: TP 18, FP 4, FN 0 over 225 systems). That lets a method satisfy a pre-registered gate of the synthetic conclusion without learning, and its size fields partly reveal k.
- **Before freezing, also close:** the sim-service timing oracle and portable tokens, shared work areas that other agents can modify, and a feedback release gate that keeps no state across calls.
