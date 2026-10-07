# Review F (leakage and isolation), early pre-freeze round

Reviewer F. Scope: goal5 section 83. The questions were whether hidden benchmark information can reach method developers, and whether the isolation is enforced by technology or only by instructions.

All scripts are in `.tmp/F/`, and every number below was produced by them in `./sbx`. Two helper agents read `suites.py`/`synthadapter.py` and the runner/tournament/Modal code. I re-ran or re-read every claim I adopted from them. Claims I could not verify are marked **(unverified)**.

**Side effects to disclose.** While testing the host guard I rewrote three protected files with byte-identical content: `CLAUDE.local.md`, `docs/API.md` and `sbx`. Their sha256 still match the manifest, but their mtimes changed (11:45–11:50 local). Nothing else outside `.tmp/F/` and this file was modified. My probe files in `src/`, `tests/` and the room root were deleted right after the write succeeded.

## Summary verdict

**Not ready to freeze.** The isolation is partly technological, but in its current state it does not deliver what the protocol and the builder's docstrings claim:

- **Hidden truth ships in the public data.** Public pool files carry the true latent state. This invalidates latent-recovery, dimension, mediation and pool/microstate claims on every dev-tier system, and every method developed on that data.
- **Method code can reach held-out data during evaluation.**
  - The fit/eval audit-hook sandbox can be switched off by method code with one assignment.
  - Evaluation runs method code in the same process as the held-out futures, and a `gc` lookup returns them (24/24 items).
- **Host isolation can be bypassed with allow-listed text tools.**
  - `sed w` / `sort -o` / `cp` rewrite protected room files, including the `./sbx` wrapper the guard lets run on the host.
  - Rewriting `./sbx` gives unsandboxed host code execution.
  - Container code can plant `.pyc` files and `sitecustomize` modules that every later sandboxed Python loads.
- **Names reach the clean room.** The unredacted refusal list sits in every room's `CLEANROOM_MANIFEST.json`, and the scanner exempts that file. It names the circuit and earlier-phase artefacts.
- **Redaction is reversible.** The review room's redaction can be undone from `source_sha256` (5 of 14 redacted files fully recovered).

The simulation-service public policy is sound on families, targets, seeds and truth events. Its identity/budget model is not: agent names are self-declared.

---

## BLOCKERS

### F-B1: true latent `z` is written into the PUBLIC pool futures (dev and toy tiers)
- **Location:** `extra/brainir_causal/suites.py:1471-1472` writes `arrays[f"{tag}_{name}_z"]` whenever `with_truth` is set.
  - `with_truth` defaults to `True` (`suites.py:1375`) and `build_tier` never passes `False`.
  - The public dev/toy parts include `pool_src`, so `data/synthetic_dev/*/pools/futures.npz` in the clean room would carry it.
  - The test `test_public_part_passes_the_public_policy` never inspects `futures.npz` keys.
- **Evidence (`.tmp/F/verify_z.py`):**
  - `data/toy_example/syn_toy_0/pools/futures.npz` has 4240 arrays, of which 1820 are `s*_*_z`, shape (101, 2) float32. The true dimension k = 2 is readable from the shape.
  - syn_toy_1 has 2420 `_z` arrays.
  - Fitting `y = z·w + b` on the no-intervention futures gives w = [1.0, 0.5], b = 0, max residual 9.6e-7 (syn_toy_0) and 4.7e-7 (syn_toy_1). This is the exact latent the readout is built from.
  - The helper additionally regressed `z` on observed `x` of the 600 pool states: R² = [1.0, 0.9998]. The true encoder is learnable from public data.
- **Impact:** any method trained on the dev tier can use supervised truth. The latent-recovery, dimension, SMS, micro-equivalence and lift claims are all contaminated. Methods developed before the fix cannot be certified truth-blind.
- **Fix:**
  - Never write `_z` when `dest == "public"` or `policy == "public"`. Put pool truth under `truth/<sid>/pools/`.
  - Add a build assertion and a test that public `futures.npz` keys match only `^s\d+_(none|<kinds>|floor)_(y|x|u)$`.
  - Rebuild the toy/dev public parts, and purge any room copy with a logged sync.

### F-B2: method code can switch off the fit/eval sandbox (`runguard`) with one assignment
- **Location:** `extra/brainir_causal/runguard.py:30`. `_TL = threading.local()` is a module attribute, and both hooks return immediately when `_TL.busy` is true (`:183`, `:213`).
- **Evidence (`.tmp/F/runguard_off.py`):** `install_fit_guard(allowed=[.tmp/F], protected=[/room/docs])` is installed, with `docs/` standing in for hidden data.
  - Before the assignment: `open(docs/API.md)` is **refused** (`method sandbox: open outside the allowed roots`).
  - After `import brainir_causal.runguard as g; g._TL.busy = True`, the same open reads fine.
  - Network and process rules go off the same way, because every rule sits behind the same flag.
- **Second bypass in eval mode (`.tmp/F/evalguard_thread.py`):** the check keys on "a method frame is on the stack" (`:204-210`).
  - A method that starts `threading.Thread(target=exec, args=(compile(..., "<gen>", "exec"),))` has no method frame on that thread's stack.
  - Result: `{'direct': 'refused', 'thread': 'READ OK'}`.
- **Impact:** on the orchestrator's host, the fit process runs with `cwd=ROOT` (the main repository) and the full orchestrator environment (`scripts/tournament.py:111,114`).
  - With the guard off, a method can read `data/phase4/hidden/salt.txt`, the internal records, and validation/confirmation truth.
  - It can also write them anywhere, including the clean room `C:\Dev\BrainIR_p4clean\runs\` on the same machine. That is a direct channel from hidden data to developers.
  - On Modal the same code reaches whatever the class mounts **(unverified)**. The helper reported that fit classes mount the store volume (`p4modal/app.py:50-65`).
- **Fix:**
  - Stop treating in-process audit hooks as the security boundary. Run fits and loops in an OS-level sandbox: a separate container or user, read-only mounts of *only* the permitted per-job data, no network, no repository mount, and a scrubbed environment (`env={}` plus a whitelist) with a job-local cwd.
  - Keep the hooks only as a tripwire, with the flag inside a closure.
  - Add a regression test that sets `runguard._TL.busy = True` and uses a thread-plus-`exec` target, and expects refusal.

### F-B3: evaluation runs untrusted method code in the process that holds the held-out answers
- **Location:**
  - `scripts/tournament.py:128-144,212`: one `ProcessPoolExecutor` with `_eval_init` for all methods; `harness.evaluate_job` loads held-out items, internal records and the generator in the worker that calls the model.
  - `runguard.py:17-19` itself says "In-memory introspection is not blocked".
- **Evidence (`.tmp/F/view_leak.py`):**
  - Built the orchestrator's `TestItem`s with `suites.items_from_set` on `syn_toy_0` (88 items).
  - A model function that receives only `(x_hist, u_hist, u_future, events, dt)` and scans `gc.get_objects()` for the `TestItem` with the same `x_hist` returned the exact held-out `y_future`/`y_twin` for **24 of 24** intervention items. That makes EE = 0.
  - Workers are also reused across methods, so one method can monkeypatch `harness`/metrics for the methods evaluated after it.
- **Impact:** EE, SMS, ICG, lift and every derived verdict can be forged by a submission. The "locked method is audited" mitigation does not cover pre-lock tournament rounds, and a manual audit is not a technical control.
- **Fix:**
  - Evaluate through a process (or container) boundary. The model process gets only model inputs and returns predictions; held-out futures, twins, truth and internal records live only in the scoring process.
  - Use a fresh process per (method, system) job (`max_tasks_per_child=1`).

### F-B4: the host guard's "protected room files" are not protected, and `./sbx` can be replaced, which gives unsandboxed host execution
- **Location:**
  - `extra/scripts/p4agent/guard_hook.py:87-89`: a regex over `> >> tee cp mv sed -i ...` that only names the Claude control files, `sbx` and the manifest.
  - `_is_protected` is consulted only for shell redirections (`:490`) and the Write/Edit tools (`:731`).
  - `HOST_ALLOWED` (`:106-114`) includes `sort`, `sed`, `awk`, `cp`, `mv`, `rm`, `touch`, `split`, `gzip`, `find`.
  - The `sed` check refuses only the `e` command (`:557-571`), not `w`.
  - `./sbx` is accepted if it resolves to the room's `sbx` (`:534-537`), whatever its content.
- **Evidence (host, real guard, identical-content writes):**
  - `sort -o CLAUDE.local.md .tmp/F/cl.md` was allowed (rc=0, mtime 11:41:00 → 11:45:39).
  - `cp .tmp/F/api.md docs/API.md` was allowed; allowlisted evaluator files are equally exposed.
  - `sed -n 'w sbx' .tmp/F/copy_of_wrapper` was allowed (rc=0, mtime 11:41:21 → 11:50:15). The sha256 is still `1da98fc7…` (manifest value), and `./sbx python -c ...` still works.
- **Impact:**
  - An agent can replace `./sbx` with `exec "$@"`. After that, `./sbx python x.py` runs on the host with the user's rights: whole disk, network, credentials. That defeats the sandbox, the room boundary and every hidden-data protection in one step.
  - It can write persistent instructions into `CLAUDE.local.md`, which every later session in the room loads, or edit the evaluator/docs others rely on.
  - The canary test (`extra/results/CANARY_TEST.md`) tried only `echo >> CLAUDE.md`, so it did not detect this.
- **Fix:**
  - Make protected files immutable at the OS level: an NTFS ACL deny-write for the agent's user, or build the room as another user with read-only ACLs. Do not rely on regexes.
  - Have the guard refuse `./sbx`, `sbx` given as a path, and bare `sbx` unless PATH resolves it to the outside copy; or check the wrapper hash on every call.
  - Refuse write-capable options of allowed tools (`sed` `w`/`W`, `sort -o`, `awk` `>`/`print >`, `find -fprint`/`-delete`, `split`, `cp`/`mv`/`rm`/`touch` onto allowlisted paths).
  - Add these to the canary test.

### F-B5: the clean room's own manifest names the circuit and earlier-phase artefacts; the scanner exempts it
- **Location:**
  - `extra/scripts/make_phase4_cleanroom.py:581` stores `"refusal_list": [p.pattern for p in REFUSE]` in the manifest. `_write_manifest` (`:595-599`) copies it into **every** room, including `BrainIR_p4clean`.
  - `scan()` skips `CLEANROOM_MANIFEST.json` (`:653`), and `check_source` never sees generated files.
- **Evidence:**
  - `CLEANROOM_MANIFEST.json:14352-14376` (this room) holds the unredacted refusal patterns.
  - These include a benchmark directory whose name identifies the specific biological circuit and an identifier of the earlier dataset (`:14362-14363`), plus the earlier-phase research/data paths (`:14356-14357,14364,14366`).
  - Running the builder's own `CONTENT_ALWAYS` over the room (`.tmp/F/scan_room.py`) reports hits at manifest lines 14356, 14357, 14364 and 14366.
- **Impact:** method developers learn the circuit identity and the earlier artefacts' names from a file the room is built with. This directly contradicts the clean-room claim.
- **Fix:**
  - Keep `refusal_list` (and the `source` paths) only in the outside manifest; the in-room copy should hold `path`, `sha256` and `bytes`.
  - Remove the manifest exemption from `scan()`.
  - Make `build`/`sync` fail on any scanner hit in any generated file.

---

## MAJOR

### F-M1: the review room's redaction is reversible, and names survive it
- **De-redaction oracle.** For every redacted copy, the manifest records `source_sha256` of the unredacted source (`make_phase4_cleanroom.py:490-492`).
  - `.tmp/F/dered.py` tried candidate words taken from unredacted text already in the room. The script prints only match/no-match, never the string.
  - It fully recovered all redactions of `extra/brainir_causal/p4modal/images.py` (2), `p4modal/remote.py`, `systems.py`, `scripts/modal_p4.py` and `scripts/tournament.py` (1 each).
  - That is 5 of the 14 redacted files. In all 5 the recovered string is the same 6-character token.
- **Names that the redaction misses.** A regex source like `\bNAME\b` does not match `\bNAME\b` in text: after the literal `\b` there is no word boundary, and `\s*`/`-?` break the literal.
  - Surviving names: dataset/organism names in the builder's `CONTENT_ALWAYS` (`make_phase4_cleanroom.py:72-74`).
  - The guard's `WEB_BLOCK` (`guard_hook.py:95-97`) names the circuit, its anatomy, a neuron identifier and the data type.
  - `audit_transcripts.py:30-31` `NAMES` has more.
- **Fix:**
  - Drop `source_sha256` from the in-room manifest, or replace it with an HMAC.
  - Redact on a word-level list, not on regex hits.
  - Scan redacted output with a pattern that normalises regex escapes (as `scan_room.py` does).
- This matters for the clean room too, if any of these files is ever allowlisted there.

### F-M2: the guard's error messages act as an oracle and leak names
- **Location:** `guard_hook.py:224` (`forbidden pattern {pat!r}`), `:227` (echoes the other room's name), `:710` (echoes the `WEB_BLOCK` regex).
  - During this review the guard echoed patterns such as `'\\bpyguard\\b'` and `'\\.claude[\\\\/]'` back to me.
  - In the clean room, the deployed, unredacted `FORBIDDEN_PATTERNS` would be printed to developers who trigger them.
  - A web-enabled agent (for example in the literature room) that mentions the topic gets the circuit-describing regex back.
  - Even without the echo, allow/deny is a membership oracle for candidate names.
- **Fix:** return a generic reason with an opaque code, and log the matched pattern outside the room only.

### F-M3: container code can plant code and instructions that others load
- **Location:**
  - `sbx:68`: the room is bind-mounted **read-write** at `/room`, and only listed paths are overlaid read-only.
  - `ro_paths` (`make_phase4_cleanroom.py:417-439`) splits `src/brainir_causal/` into per-file mounts, so the directory itself, its `__pycache__`, `src/` and `tests/` stay writable.
  - The code runs with `/room/src` on the Python path (`sbx:85`).
- **Evidence (`.tmp/F/probe_rw.py`, `.tmp/F/pyc_demo.py`):**
  - WRITE OK: `/room/src/`, `/room/src/brainir_causal/`, `/room/src/brainir_causal/__pycache__/`, `/room/tests/`, the room root, and a nested `.tmp/F/ns/CLAUDE.md`.
  - `docs/`, `.claude/` and `CLAUDE.md` are refused.
  - A forged `.pyc` stamped with the honest source's mtime and size is loaded instead of the source (`score()` returns 0.99, while the source says 0.10).
- **Impact:**
  - In the shared clean room, one developer's container can do three things:
    - plant `src/sitecustomize.py`, which every later sandboxed Python imports;
    - shadow `numpy`, since `/room/src` precedes site-packages;
    - forge `.pyc` files for the read-only evaluator.
  - It can also drop nested `CLAUDE.md` files that host sessions load. The builder's docstring says containers must not be able to do this.
  - `scan()` exempts `__pycache__` (`:645`), so forged `.pyc` files are never reported.
- **Fix:**
  - Mount `src/` read-only as a whole, with only `src/brainir_causal/methods` read-write.
  - Set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONPYCACHEPREFIX=/tmp/pyc` in the container.
  - Mount the room root read-only, with explicit read-write work areas.
  - Have `scan()` report every `*.pyc` outside the work areas, and every `CLAUDE.md`/`.claude` in the tree.

### F-M4: simulation-service identity is self-declared, which gives unlimited budget, a cross-agent cache oracle and readable ledgers
- **Location:**
  - `simservice.py:293-298`: `agent = req["agent"]`, a budget per name, and `served` keys per name.
  - `:363-366,369-370`: returns `cached` and the full ledger.
  - `simclient.py:28` (any `agent=` argument), `runner.py:231` (the loop's `SimClient`).
- **Evidence (`.tmp/F/simsvc_spoof.py`, toy system, budget 2):**
  - `dev_A`'s third protocol is refused ("budget exhausted").
  - The same process then calls with `agent='dev_A2'` and both protocols are accepted.
  - `dev_B` requesting `dev_A`'s protocol gets `cached=True`, which reveals `dev_A`'s experiment.
  - Anyone can query `dev_A`'s ledger (`trajectories 2, units 2`).
- **Impact:**
  - Budget limits, and therefore every active-design efficiency comparison (PROTOCOL 5.17), are unenforced.
  - A loop's designer runs in the fit process with the `simq` directory allowed, so it can open its own `SimClient(agent="x")` and simulate outside the loop's ledger.
  - `cached` is a membership oracle over the shared content-addressed store: other developers' queries, and any orchestrator protocol that falls inside the public policy.
- **Fix:**
  - Bind identity outside the request: per-agent queue directories written by the launcher, or an HMAC token issued per agent/loop.
  - Charge by identity.
  - Stop returning `cached` (count it only in the orchestrator ledger).
  - Give each loop its own queue, token and budget, and have the loop verify that the server-side ledger equals its own.

### F-M5: the feedback channel is a covert channel
- **Location:** `feedback.py:21,41-68`, `tournament.py:295-299`.
  - Per candidate the feedback releases fit/eval failure counts, 8 pass rates, category counts and 6 medians.
  - Methods see validation systems' training data during fit, so they can encode facts about hidden systems in their failures or medians.
  - `MIN_CELL = 3` does not stop differencing between rounds whose system sets differ by one.
  - No cap on submissions or rounds, and no check that feedback comes only from the validation tier (`cmd_feedback` takes any round).
- **Fix:**
  - Fix the system set per tier.
  - Cap rounds and methods.
  - Report failure as a boolean.
  - Coarsen or noise the medians.
  - Refuse feedback for non-validation suites.

### F-M6: public keys and file names are a verification oracle; the validation/confirmation tier seed is 32-bit and public-part seeds are unsalted
**(Helper-verified by rebuilding; I checked the code.)**
- **Keys.** `key = sha256(canonical protocol, system_hash, engine)` (`suites.py:992-994`), and the protocol and engine are public, so `system_hash` is the only unknown. For the toy this recovered `DEV_SEED = 20260926` in 927 tries.
- **Tier seed.** `tier_seed` keeps 32 bits (`suites.py:144`), and the public-part `params_seed`s of the validation/confirmation tiers come from unsalted `public_seed_of` (`:154-171`, `:959`). Fit sandboxes see these.
  - On the toy, the tier seed was recovered from public `params_seed`s after 10,927 tries. The full 2³² space is about 1.7 CPU-hours.
  - With the generator code, the tier seed regenerates hidden targets, rotations and truth.
- **Fix:**
  - Salt the public-part seeds of hidden tiers, and use at least 64-bit tier seeds.
  - Make public keys HMAC(salt, ·) or random ids, with the map kept on the orchestrator side.

### F-M7: the remote dev runner's job guard is not in the review set **(unverified)**
- `devrun4.py:75` loads `scripts/p4/devrun4_site` (an in-process audit hook, the same class as F-B2) into a container whose runtime keeps network access (`:154-155`).
  - That module is not in `extra/`, so it cannot be reviewed.
  - If it follows `runguard`'s pattern, the job has network access and Modal task credentials.
- The dev-data volume is reportedly mounted read-write.
- **Fix:**
  - Add the module to the review set.
  - Run jobs in a Modal Sandbox (or equivalent) with no network, read-only data, no workspace credentials, and a volume that holds only public data.

---

## Minor

1. **`tools/remote_run.py:17` crashes on import:** `NameError: name 'null' is not defined`, because JSON is pasted into Python (`devrun4.py` `CLIENT % json.dumps(...)`). Reproduced: `./sbx python tools/remote_run.py`. Fix: use `repr()`.
2. **`TestItem` does not own its arrays by design.** `evalio.py:104-108` copies only because the stored arrays are float32 and `np.asarray(..., float64)` has to convert. `items_from_set` passes views (`x_hist=r.x[: i0+1]`, `suites.py:1552,1583`), and the model receives the item's own array objects. With float64 inputs the model would get a view whose `.base` holds the future.
   - Checked: 0 of 88 items leak today.
   - Fix: `np.array(..., copy=True)`, set `flags.writeable=False`, and apply the same to `PoolState`/`StateSample`.
3. **Guard forbidden-text patterns are bypassed by globbing.** `cat extra/scripts/p4agent/py*/site*.py` read a file whose name is a forbidden word. Harmless for outside paths, which are resolved separately, but the patterns give no protection for in-room names.
   - The same patterns block legitimate review commands: a grep regex containing `\.\w` is refused as "`/./` path component", and the name of the Python path variable is refused inside an agent prompt.
4. **Background-task outputs of every agent land in the shared room `.tmp/<agent>/`** (launcher `TEMP`), and `scan()` skips `.tmp/` content (`:653`). In the clean room, developers can read each other's tool outputs. This is by design for a shared room, but should be documented.
5. **Sim-service error echo.** `simservice.py:359` returns `simulation failed: {exception}` verbatim. Engine exceptions may carry internal field names or store/bundle paths. Return a generic message and log the details outside the room.
6. **Hidden targets/edges are the exact complement of the public ones** when every unit is targetable (`suites.py:291-316`; toy: public [0, 2, 4] → hidden [1, 3, 5]). This is acceptable if documented, since they still cannot be simulated.
7. **Pass-through fields.** `synthetic_records` (`suites.py:318`) uses a blacklist for public record keys, and index rows copy the generator's `info` verbatim (`:1281`). Harmless for the toy, but a future generator could leak (`type`, `variant`, `k`). Whitelist instead.
8. **Eval-pool intervention sequences reuse the public rng stream** (`suites.py:1420`), so developers know the exact evaluation perturbations in advance.
9. **`baselines/.../evaluate.py:10`** (scanner-exempt) names an earlier-phase review directory. It is harmless, but it is a second exemption to track.

---

## Checked and found sound

- **Launcher deny rules.** Reading the shared session store `~/.claude/projects/C--Dev-BrainIR-p4review` was denied (a Glob on it was refused).
- **Sandbox basics.** Read-only overlays on allowlisted paths hold: writes to `docs/`, `.claude/` and `CLAUDE.md` failed with EROFS. The container has only `P4_*` variables. The canary results agree: no network, no Docker socket, no symlinks.
- **`check_public`:**
  - held-out, hidden-only, unclassified and truth-event protocols are refused;
  - only public targets and edges are accepted;
  - `public_seed_max = HIDDEN_SEED_BASE`, and hidden seeds are salted;
  - only observed arrays are returned.
  - Held-out family lists are public by design (PROTOCOL §3), so its refusal messages do not leak them.
- **Toy public files apart from F-B1** (helper checked, I spot-checked):
  - `index.jsonl` rows use only train families and public targets/edges;
  - `params_seed < 1e9`;
  - traj npz hold only `t`, `x`, `u`, `y`;
  - `pool.json`/`lift_cases.json` reference public keys only;
  - the manifest's system record has no internal keys.
- **Evaluator call surface.** The model receives arrays and event lists only, and truth events are rejected before a model call (`evalio.py:250`).
- **Feedback** carries no system ids and suppresses cells with fewer than 3 systems (but see F-M5).
- **Guard path handling.** It resolves and contains `..`, `/./`, 8.3 names, drive paths, and relative links. Host interpreters are refused.
