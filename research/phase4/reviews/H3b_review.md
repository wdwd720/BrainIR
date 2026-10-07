# Review H3b: numerical methods and compute (round-3 follow-up: verification)

Reviewer H. Scope: my round-3 minors (NEW-1 to NEW-4), N4, N6, and the round-1 M5 carried forward.

As instructed, the generator-side checks (N1 direct, N2, N3, N5) are marked **pending generator revision** and were not run: the
generator is being revised again.

**How the checks were run.** Scratch is in `.tmp/H/r3b/`, and every script ran with `sbx` on the package assembled in
`.tmp/H/r3b/pkg`. Where the reference platform is required, the numpy CPU pin was exported inside the sandbox; the review sandbox
does not set `NPY_DISABLE_CPU_FEATURES` itself (see note 3).

**Run interruption.** A first attempt at the generator runs died with a Docker Desktop crash. After the restart only the
generator-independent checks were run. The N4 end-to-end build uses the current generator, but only the evaluator side is judged
from it.

## 1. Per-finding table

| # | finding | status | location of the fix | my re-run (numbers) |
|---|---|---|---|---|
| NEW-1 | the service's reproduction check compared store keys only; `run_job` ungated | **fixed** (residual minor NEW-6) | `simservice.py:598-635` (t, x, u, y compared bit for bit with the public file; a mismatch is removed); `simservice.py:352-356` + `p4modal/gate.py:104-133` (`require_reference_platform`) | `ensure.py` in fresh namespaces. **Reference platform:** served, 1 source recomputed and verified, max \|dx\| = 0.0. **1e-9 perturbation:** refused ("simulation failed (reference …)"), 0 sources accepted, the record removed from the namespace. `gate.py`: with the host faked as AVX-512, `run_job` refuses ("runs only on the reference platform") and `SimContext.run` refuses too. On this admissible host WITHOUT the numpy pin, `run_job` refuses ("pin NPY_DISABLE_CPU_FEATURES not 'X86_V4 AVX512_ICL AVX512_SPR'"). |
| NEW-2 | paired windows covered 0.8 to 1.0 of the primary horizon | **fixed** | `refs.py:1162-1165` (`_paired_lengths`: m steps AFTER the onset), `refs.py:1201-1270` | `new2.py`. **The rule:** over 5,261 long random pairs, the post-onset steps covered are exactly m (min = max = 50). **Real fits:** PCA-2 and FULL-STATE on the toy public data report `paired_post_onset = {window 50, min_steps_long_pairs 50, n_clipped_short_pairs 0}`, with the primary horizon = 50 steps. |
| NEW-3 | loop / refs / designers not importable from the public package | **fixed** | `src/brainir_causal/sampling.py` (new); `accounting.py` now public | `imports.py`: all 27 modules of `/room/src/brainir_causal` import on their own; no orchestrator module (suites, store, simservice, synthadapter, realsim) is present |
| NEW-4 | planning container used a mutable tag, no pins, no gate | **partly** | `build_on_modal.py:196-235` (image by recorded id, `CPU_PINS` passed); `plan_synthetic.py:34-38` (`reference_platform_problems`) | The refusal logic ran: `reference_platform_problems()` lists exactly the missing pin on the unpinned sandbox and is empty with the pin. The docker-launched planning run and the image-id comparison are code-read only (no Docker inside the sandbox). |
| N4 | exact jump vs the one-sample observation | **partly** | `evaluate_truth.py:20-22, 190-215` (headline "next_sample" vs `dz_true_next`; "exact" beside it); `evalio.py:107`; `suites.py:2075-2093` | `n4build.py` (a tiny eval build of `syn-01f497d7f752`): all 208 items carry `dz_true_next`; the 41 kick items acting at the onset also carry `dz_true`; \|dz_true_next − dz_true\| / \|dz_true\| is median 0.041, max 0.070 (the definitional gap, now kept apart). The END-TO-END score is not valid (new finding NEW-5): an oracle whose latent IS the true state scores R² = −26.2, cosine 0.15, on both definitions (`n4score.py`). |
| N6 | synthetic simulations not host-gated | **fixed** | `suites.py:1381-1382`; `simservice.py:352-356` | `gate.py`: builds and service jobs both refuse a faked AVX-512 host. Rebuilt synthetic_dev: 7,098 of 7,098 rows carry an admissible, pinned fingerprint (`datachk.py`). |
| M5 (r1) | host / ISA dependence outside provenance | **partly** | as N6 and NEW-1; `realsim.py:155` | Everything runnable is verified (gates on both synthetic paths, fingerprints on all real and synthetic rows). The real engine is still not installed, so its own gate is unverified. |
| N1 (direct) | generator shows events at their onset sample | **pending generator revision** | — | Not run. The benchmark-side check was verified in round 3. The rebuilt synthetic_dev has 0 of 2,624 items differing from their twin (x, y, u) at or before the onset (`datachk.py`). |
| N2 | step accuracy on several seeds / spreads / extreme windows | **pending generator revision** | — | not run |
| N3 | non-trivial truth-equivalent states | **pending generator revision** | — | not run |
| N5 (synthetic) | realized kick sizes; classes by realized size | **pending generator revision** | — | Not run. Observed in passing: the current generator's full output reports only `clipped_kicks`, not realized sizes. In the `n4build.py` eval build, no kick test item clipped (40 items; the requested class equals the class; 0 flagged unknown). |

**Counts (11 rows): 4 fixed, 3 partly, 0 not fixed, 4 pending generator revision.**

## 2. New findings

### NEW-5 (MAJOR, a reported metric; no verdict criterion): the true read-in accuracy (PROTOCOL 5.16) is not identifiable on half the dev systems

**Where:** `eval_readin_truth` (`evaluate_truth.py:190-215`) maps the truth into model coordinates by an unregularised affine
least-squares fit z ≈ z_true·M + b on the truth samples (`suites.truth_samples`: 12 samples per PASSIVE test trajectory). Passive
trajectories do not excite every coordinate of z_true.

**Evidence** (`n4rank.py`). For each of the 10 public dev systems (revised generator as synced), I took the benchmark's passive
test protocols (12 non-restart ones, 144 samples) and computed the rank of [z_true, 1] and the map error for an ORACLE model
(z = z_true, so M should be the identity):

| system | k_true | rank of [z_true, 1] | oracle map error, median over random dz |
|---|---|---|---|
| 5 systems (00e4…, 04c7…, 09b5…, 0e24…, 183f…) | 2–3 | full | ≤ 3e-15 |
| syn-01f497d7f752 | 55 | **3** (of 56) | **0.97** |
| syn-1251c8ff2973 | 49 | 44 (of 50) | 0.16 |
| syn-1bc959e4a710 | 3 | 3 (of 4) | 0.49 |
| syn-09a260ad2d4f | 2 | 2 (of 3) | 0 (coordinates constant in the samples; the error is hidden) |
| syn-2a013a2e85c0 | 3 | 2 (of 4) | 0 (same) |

End to end (`n4score.py`), the oracle whose rollout difference equals the true next-sample difference, and whose read-in equals
the exact jump, scores **R² = −26.2, median cosine 0.15** (next_sample) and −26.0 / 0.15 (exact). The metric reports a perfect
model as badly wrong. The obs.init restarts left out of my sample set restart from nominal passive trajectories, so they add no
new directions. The latent-recovery R² of 5.16 uses the same samples; it drops constant target coordinates, but it cannot score
directions the samples never visit either.

**Fix:**
- Fit the map on states that span z: the onset states of the intervention test items, post-kick states, and the pool states,
  which include generator pool states.
- Check the rank of [z_true, 1] (relative singular-value threshold). Report "unidentifiable" (never a number) when it is below
  k_true + 1, or score only the identifiable subspace.
- Add an oracle regression test: z = z_true must score R² = 1 on every dev system.

### NEW-6 (minor): the new bit-for-bit reproduction check fails OPEN when the public trajectory file is unreachable

**Where:** `simservice.py:624-635` compares the arrays only `if traj and Path(traj).exists()` (and only the names present).
Otherwise the source is accepted and only `n_sources_verified` stays unchanged.

**Evidence** (`ensure.py`, mode perturb-missing): with the table's file paths pointing nowhere and the generator perturbed by
1e-9, the request is served (1 source recomputed, **0 verified**). The served arrays differ from the public data by max
\|dx\| = 1.9e-6. The platform gate prevents this in the intended deployment, but the check itself should not fail silently.

**Fix:** refuse (fail closed) when a public source has no readable trajectory file or lacks one of t / x / u / y, and log it.

**Note 3 (observation).** The review / method sandbox (`sbx`) does not set `NPY_DISABLE_CPU_FEATURES`, so by the benchmark's own
rule it is not the reference platform. It is harmless on this AVX2-only host: 120 of 120 regenerated synthetic_dev trajectories
are bit-identical. Setting the pin in the sandbox image would make "the sandbox image = the reference platform" literally true.

## 3. Verdict

**Not ready to freeze.**
- **Fixed and verified:** every infrastructure fix I could run holds. A recomputed public source must now reproduce the public
  arrays, and a 1e-9 perturbation is refused. Benchmark simulations are refused off the reference platform, on both the build and
  the service paths. The public package imports on its own. The reference learner's paired windows cover the full primary horizon.
- **N4 in part:** its definitions are cleanly separated in the code.
- **Open:**
  - the end-to-end read-in truth metric is unidentifiable on 5 of 10 dev systems: a perfect oracle scores R² = −26 (NEW-5,
    major; a reported, not a verdict, metric);
  - the reproduction check fails open when the public file is missing (NEW-6, minor);
  - the real-engine gate and the docker-launched planning run cannot be exercised in this room;
  - the generator-side checks (N1 direct, N2, N3, N5) await the final generator revision.
- **Freeze path:** fix NEW-5 (fit the truth map on spanning states, with a rank check and an oracle test), make NEW-6 fail
  closed, and pass the pending generator checks. The numerical machinery in my area would then be ready.
