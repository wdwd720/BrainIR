# Review H3: numerical methods and compute (third pre-freeze round: verification)

Reviewer H. Scope:
- every finding of `reviews/H/H2_review.md` (N1 to N6), and the round-1 findings I left partly fixed or unverified (M5, m5);
- the round-3 items named for H: the onset check and the realized-size kick classes on the rebuilt real data, synthetic host
  gating, state carriers, the reference-platform rule, and the numerics of reference learner v2.

**How the checks were run.** Scratch is in `.tmp/H/r3/`, and every script ran with `sbx python .tmp/H/r3/<script>`. Package:
`src/brainir_causal` plus `extra/brainir_causal`, assembled in `.tmp/H/r3/pkg`.

**Limits:**
- `extra/generator/` is still the round-2 version (no section 14 in SYNTHETIC_BENCHMARK.md). As announced, the revised generator
  and the synthetic tiers rebuilt from it come in a follow-up.
- `data/synthetic_dev` is still the round-2 build: 620 rows with explicit initial states (design v1), and the onset mismatches
  of H2-N1.
- The frozen real-circuit integrator is still not installed in the sandbox.
- `simdocker.py` and `plan_synthetic.py` are not in this room.

## 1. Per-finding table

| # | finding | status | location of the fix | my re-run (numbers) |
|---|---|---|---|---|
| M5 (r1) | host / ISA dependence outside provenance | **partly** | `gate.py:88-95`; `realsim.py:155`; `suites.py:1381-1382` (synthetic builds gated); `store.py:111-117` (fingerprint) | `hosts.py`: 6,554 of 6,554 rebuilt real rows carry an admissible fingerprint (pins set). `gate.py`: with the host faked as AVX-512, `SimContext.run` (builds) refuses, but `simservice.run_job` (developer requests on the default pool) still simulates and stores the record, marked `host.admissible = False` (N6 below). The real-engine gate itself is unverified: the engine is not runnable here. |
| m5 (r1) | greedy_error has almost no floor | **fixed** | `designers.py:164-225` (`effect_floor_sq`, the evaluator's item error, capped at 10) | `greedy.py` (toy public data, 100 items, f_s² = 0.0215): a no-effect model scores err ≤ 1 on every item (median 0.904, max 1.0); a wild model is capped at 10. |
| N1 | the generator shows param / silence events at their onset sample | **partly** | benchmark side: `suites.py:1661` (`onset_mismatch`), `suites.py:1789-1792` (the build aborts); generator side pending | `onsetbuild.py`: a small public-part build with the round-2 generator STOPS on all 3 dev systems that train sil.* / param.1 ("param.1 (d1) y differs from the twin at sample 506 (onset sample 506)"; sil.1 at 651 and 520), so the check works. `realchk.py`: the rebuilt real data has 0 of 2,352 items differing from their twin in x, y or u at or before the onset. The generator fix, and the stale `data/synthetic_dev`, remain. |
| N2 | step accuracy tested only on seed 0 / spread 1 | **unverified** | the generator revision ("seed-agnostic tests") has not been delivered | re-run of `genstep.py` due with the revised generator |
| N3 | truth-equivalent states identical by construction | **unverified** | the generator revision ("non-trivial equivalent states") has not been delivered | re-run of `gentruth.py` due with the revised generator |
| N4 | exact kick jump vs the one-sample observation (4 % median, 15 % worst) | **not fixed** | `evaluate_truth.py:20` still scores the read-in against the exact jump, with a one-sample-later fallback; no change is listed for it | Code read only; the numbers of H2 stand. |
| N5 | kick clipping: real classes by requested size; synthetic clipping invisible | **partly** | `suites.py:1681-1717` (`realized_kick_class`), `suites.py:157-161` | `realchk.py` (real): 252 of 791 kick items clipped, and all 252 carry the class of their realized median size (below 141, weak 77, moderate 30, strong 4); 539 unclipped items are within their class's size range; 0 label problems. Synthetic: realized sizes are deliberately never public (review T, M1). The round-2 generator reports only `clipped_kicks`, so orchestrator-side classes stay the requested ones, flagged `unknown`. To verify with the revised generator. |
| N6 | synthetic simulations not host-gated | **partly** | `suites.py:1381-1382` (`SimContext.run`) | `gate.py`: builds refuse an AVX-512 host; the service path `simservice.run_job` does not (details in NEW-1). |

**Counts (8 rows): 1 fixed, 4 partly, 2 unverified, 1 not fixed.**

## 2. Round-3 items verified (my area)

**Rebuilt real data** (`realchk.py`, `hosts.py`):
- r0 kinds are rest (6,014) and restart (540) only: 0 explicit states;
- all 540 obs.init rows restart from an obs.nominal source of the same parameter draw;
- inclusive onset check: 0 of 2,352 items differ from their twin;
- 0 non-finite values; fingerprints complete and admissible;
- realized-size kick classes are correct (table above).

**State carriers** (`carrier.py`, 12 dev systems, round-2 generator): 48 carrier starts, at t0 = 0 and mid-trajectory (with
process noise). The maximum difference between a carrier start and a direct `simulate(restart_state=...)` is **0.0** over x, y and
the full state (bit-exact).

**Reference learner v2** (`refv2.py`, `refv2b.py`; PCA-2 and FULL-STATE on the toy public data, reduced step counts):
- **float64:** training uses `.double()` torch modules; prediction uses float64 numpy copies (`_NumpyMLP`).
- **Determinism:** two fits with the same seed give bit-identical effects; 1 vs 2 threads are also bit-identical (max difference
  0.0); seed 1 differs.
- **dt rules:**
  - PCA-k: intervention_effect at 2 dt equals the dt prediction [::2], including the calibration factor (max difference
    8.9e-16);
  - FULL-STATE: rollouts from one z0 at 2 dt equal the dt rollout [::2], with a kick (difference 0.0);
  - `_beta_rows` at 2 dt equals `_beta_rows` at dt [::2];
  - 1.5 dt is refused.
- **Per-horizon calibration factor:** beta[0] = 1, clipped to [0, 1] (smoothing leaves at most 2e-16 above 1). PCA-2 on the toy:
  beta = 1.00 / 0.84 / 0.33 at 25 / 50 / 100 % of the long horizon.
- **Paired unrolling:** see NEW-2.

**Reference platform:**
- Builds check that the planned system hash equals the building process's (`suites.py:2145-2147`).
- The generator is bit-identical on this sandbox (Linux, pinned stack, AMD Zen 3+, no AVX-512): 120 of 120 in round 2, and all
  bit-exact carrier and service runs above.
- `simdocker.py` and `plan_synthetic.py` are not in this room: the service worker container and in-image planning are
  **unverified**.

## 3. New findings

### NEW-1 (minor): the service's "reproduces bit for bit" check compares store keys only, and the developer path is not gated

**Where:** `SimServer._ensure_source` (`simservice.py:581-604`) and `run_job` (`simservice.py:335-363`).

**The problem:**
- `_ensure_source` recomputes a public restart source and accepts it when its store KEY equals the public record's.
- A store key hashes the protocol, the system content hash and the engine, never the arrays.
- So the key catches spec-level platform differences (the Windows host changes 39 of 50 content hashes, per
  EVAL_ARCHITECTURE §11), but not integration-level ones.
- Separately, `run_job` has no host gate and relies on the service having been started with `--docker`.

**Evidence** (`ensure.py`):
- On the reference platform, a restart from a public synthetic_dev trajectory whose source was recomputed matches the public arrays
  (max |dx| = 0.0).
- With the generator's outputs perturbed by 1e-9 relative (a stand-in for a non-reference platform), the request is still served,
  with `sources recomputed: 1` and no error. The served arrays differ from the public data by max |dx| = 1.9e-6.
- `gate.py`: `run_job` on a faked AVX-512 host stores and serves the record.

**Fix:**
- Carry a digest of each public record's arrays (x, y, u, and the full state where held) in the public-keys table, and compare it
  after recomputation.
- In `run_job`, refuse synthetic and real simulations outside the reference platform: `require_admissible` plus a check of the
  pinned stack (OS, versions, pins), or refuse the service CLI without `--docker`.

### NEW-2 (minor): the paired unrolling does not cover the full primary horizon after the onset

**Where:** `refs.py:953-990`. Each paired window starts `st = j0 - U{0..pre}` steps, with pre = one short horizon (0.2 x the
primary horizon), and runs `L = min(m, ...)` steps with m = the primary horizon.

**Effect:**
- The post-onset part covered is m - (j0 - st), between 0.8 m and m (mean 0.9 m).
- So the last up to 20 % of the scored window is never trained in paired mode for a share of the draws.
- The round-3 notes and docstring describe "paired item / twin unrolling over the full primary horizon".

**Fix:** `L = min(m + (j0 - st), n - 1 - st)` per pair (or `m + pre` for the batch), or change the documentation.

### NEW-3 (minor): public modules `loop`, `refs` and `designers` cannot be imported from `src/brainir_causal` alone

**Evidence:** importing each public module from `/room/src` alone: `designers` fails (no `brainir_causal.suites`); `loop` and
`refs` fail (no `brainir_causal.accounting`). Every other module imports.

**Why it matters:** if method rooms receive only `src/brainir_causal` (the review room's sandbox mounts it the same way), the public
loop / designer / reference code documented in API.md §7 is unusable there.

**Fix:** move `accounting.py` and the few sampler helpers designers need (`FamilySampler`, `normalize_capability`, ...) into the
public package, or drop the modules from the public tree.

### NEW-4 (minor): the planning container is not pinned as strictly as the service and Modal containers

**Where:** `build_on_modal.py:150-175` (`plan_on_reference_platform`) runs `brainir-p4-sandbox:1` by TAG (mutable), with thread
variables only. It sets no `CPU_PINS` (`NPY_DISABLE_CPU_FEATURES`, `ATEN_CPU_CAPABILITY`) and applies no host gate. The service
container's build refuses a non-pinned image id, and Modal images carry the pins.

**Mitigation in place:** the build container's check of the planned system hash (`suites.py:2145`) catches spec differences on
a non-gated planning host.

**Fix:** run the image by its pinned id, pass `CPU_PINS`, and call `require_admissible` in `plan_synthetic.py`.

## 4. Verdict

**Not ready to freeze yet.** In my area, the benchmark-side machinery is in good shape. The rebuilt real data passes the inclusive
onset check (0 of 2,352), has no explicit states and carries correct realized-size kick classes. State-carrier restarts are
bit-exact. Reference learner v2 is float64, deterministic given the seed (across thread counts too) and consistent under the dt
rules, including its calibration factor. The new build check reliably stops a generator that shows an event at its onset.

What remains open blocks sign-off:
- The generator revision and the synthetic tiers rebuilt from it have not arrived. N1's generator side, N2, N3 and N5's synthetic
  side cannot be verified.
- `data/synthetic_dev` in the room is still the round-2 build, which violates design v2 and would fail the new onset check.
- N4 is unaddressed.
- Four new minors (NEW-1 to NEW-4) are open. NEW-1, the key-only reproduction check with an ungated service path, should be closed
  before developers rely on restarts from public sources.

There are no new blockers or majors. A freeze is reasonable once the revised generator and data pass N1, N2 and N3, and the minors
are closed.
