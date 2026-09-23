# Review B — simulator, rhythm metrics, pruning/screen procedures versus the published model

Reviewer: independent read-only review (Claude), 2026-09-23, working tree at commit `5de3e7c` plus uncommitted Phase 1
files. Scope: `src/brainir/sim/{model,weights,experiments,prune,screen}.py`, `src/brainir/metrics/rhythm.py`, their
tests and fixtures, and `benchmarks/dng100_walking_cpg/robustness_experiments.py dt-convergence` with its results.
Reference: `research/literature/pugliese_model_spec_from_code.md` (the code-derived spec; section numbers below refer
to it), LOG D29/D30/D36, §3.17, §5, and `goal2.md` workstreams 7, 18, 19. No file outside this report was modified;
no real-data simulation was run. The report names no interneuron type of the published core and no body id.

## 1. Verdict

The model layer is a faithful, independently written re-implementation of the published code: the rate equation,
parameter sampler (including the authors' idiosyncratic bound clipping), size scaling (median before zero
replacement), pulse protocol, tolerances, post-processing, intervention semantics, signed-matrix construction and the
published rhythmicity score all match the spec line by line, and the deviations that exist are almost all recorded
(D29, D30, D36, docstrings). I verified independently that `simulate` reproduces an exact matrix-exponential solution
to 3.6e-5 Hz and that the published score agrees to all six decimals with a direct-summation implementation written
from the spec. The added rhythm gates are cleanly separated from the published score. What is not sound yet is the
*evidence* rather than the code: (i) the dt-convergence report quotes a reference-error floor that its own follow-up
run shows to be 10–20x too small, so its finest-step rows and empirical "orders" are not measurements of the schemes;
(ii) the decision procedures (pruning search, activation screen), whose `>= 0.5` comparisons make single replicates
chaotic, have no numerical-sensitivity check at all; (iii) the test suite's "independent reference integrator" is the
same scipy RK45 at the same tolerances, so the dynamics are tested for self-consistency, not against integrator-free
truth (the closed forms that do exist cover only fixed points). Five minor undocumented deviations from the spec were
found (silent-pruning of put-back neurons, window used for the activity circuit, screen usability filter,
uninitialised samples after a solver failure, fixed-step pulse-edge artefact). No blocker.

## 2. Findings (ranked)

### Blockers

None.

### Major

**B-1. The dt-convergence report's reference-error floor is under-estimated by an order of magnitude; the finest RK4
rows and the "orders" derived from them are reference-limited.**
`benchmarks/dng100_walking_cpg/robustness_experiments.py:702-703` estimates the 1e-8/1e-11 reference's own error as
`|RK45 default − reference| × (1e-8 / 2e-6)` and the n6 report (`results/robust_dt_convergence_manc_v1.2.1_nt-paper_n6.md`
line 5) states "~5.7e-04 Hz". The follow-up run with a 1e-10/1e-13 reference (`..._n1_ref1e-10.md` line 20) *measures*
the 1e-8 reference's error directly: 7.21e-3 Hz (max, whole run), 3.97e-4 Hz (max, t <= 0.3 s), 6.74e-5 Hz RMS — 18x and
9x larger than the formula gives for that seed (0.0801 × 5e-3 = 4.0e-4; 8.73e-3 × 5e-3 = 4.4e-5). Error is dominated by
accumulated oscillation phase, which does not scale linearly with the tolerance. Consequences in the n6 table: RK4 at
dt = 1.25e-4 s has mean max error 2.54e-3 (whole run) / 2.46e-4 (early) — at or below the reference's measured error —
so the last "orders" (0.52, 0.35; 1.61) measure the reference, not RK4; the 1e-10 run confirms this (RK4 1.25e-4 error
8.95e-4 vs the 1e-8 RK45's 7.21e-3). Per-seed orders scatter from 0.44 to 3.58 (JSON `per_seed_orders`), as expected
when the error is a non-smooth function of h (kink positions inside steps), so single halvings cannot estimate an order.
The report also says "expected: RK4 -> 4, Euler -> 1 for a smooth right-hand side" (line 21/713) and then notes the C0
kink "lowers the order" without stating what to expect: for a Lipschitz RHS with a derivative jump the solution is C1
and any explicit RK scheme without event location is limited to global order 2 (Euler stays 1). Averaged over the
decade 1e-3 -> 1.25e-4 with the 1e-10 reference, RK4 gives 1.60 (whole run) and 1.79 (early) — consistent with that
bound; Euler's early-window orders 0.90/0.95 are as expected. Part B's "orders" (md lines 48-57, 0.95–1.06) are the
O(dt) pulse-edge artefact of `_fixed_step` (see B-6), not convergence orders. Why it matters: `PHASE1_REPORT.md:116`
will cite this experiment as the WS18 evidence. What *is* sound and should be the headline: score, mean MN frequency
(to 0.01 Hz) and the active-MN set are identical across RK45 / DOP853 / RK4 at every dt / Euler 1e-4 (max |Δscore|
<= 1.7e-3), and only Euler at 1 ms deviates (score −0.04, frequency −0.8 Hz, one extra active MN).
Fix: (a) replace the proportionality estimate by the measured floor (run the 1e-10 reference for the 6 seeds, or
state 7e-3 / 4e-4 Hz from the existing run) and drop or grey out rows below it; (b) state the expected order 2 and
report a least-squares slope over >= 4 step sizes per seed (or demonstrate order-4 recovery on a smooth surrogate,
e.g. softplus with a small width, to show the kink is the cause); (c) relabel Part B's table as "edge artefact";
(d) lead with the decision-level invariance above.

**B-2. The decision procedures (pruning search, activation screen) have no numerical-sensitivity check.**
`dt-convergence` covers the activation protocol's trajectory-level statistics only. `prune.py:127`
(`score >= threshold`), `screen.py:67-71` (`> 0` activity counts) make hard comparisons; spec §10 notes that one
flipped comparison changes a whole pruning trajectory, and `research/LOG.md` §3.17 reports the 1,024-screen circuit
prevalence (68.1 % / 16.5 % / 8.1 %) without knowing whether it moves under DOP853 or tighter tolerances. Why it
matters: goal2 WS18 asks that "important benchmark conclusions do not arise purely from numerical artifacts", and the
pruning prevalence *is* the reproduction's headline. Distributional agreement with the paper is indirect evidence
only. Fix: re-run a subset (e.g. 64 seeds) of the pruning screens with `ModelConfig(method="DOP853")` or
`rtol=2e-7, atol=5e-10` and compare the kept-set prevalence and the per-seed kept sets; do the same for a handful of
screen candidates (rank stability). Cost is a few percent of the original campaign.

**B-3. The "independent reference integrator" is not independent of the integrator, and `simulate` is never tested
against an integrator-free trajectory.**
`src/brainir/testing/circuits.py:124-162` (`reference_simulate`) is scipy RK45 at rtol 2e-6 / atol 5e-9, segmented at
the stimulus onset — the same method, tolerances and segmentation as `simulate`'s default path. Hence
`tests/test_sim_model.py:36-44` (2 % agreement) tests two code paths of one algorithm; a shared misconception (e.g. a
wrong tolerance semantics or an RK45 controller quirk) would pass. The only analytic trajectory
(`test_synthetic_circuits.py:205-216`, the single-neuron exponential to 1e-3 relative) is asserted on
`reference_simulate`, not on `simulate`; `test_sim_model.py:47-54` checks `simulate` only at steady state and only to
2 %. The oscillator `expected` values (frequency, amplitude, mean rate, `period_s`) are measured from the same RK45
reference, i.e. regression fingerprints; the docstring's claim that they "change by < 0.01 Hz when the tolerances are
tightened to 1e-10" (circuits.py:13-16) is asserted nowhere. Hand-derived truths that do exist and are valuable: the
closed-form steady states (single neuron, chain, saturating pair, winner-take-all, Picard fixed points), the
linear-stability numbers of the damped pair (20.43 Hz, 13.5 /s) tested at 30 %, the `find_peaks_1d` toy example, the
size-scaling median, the mask semantics, and the moments of the symmetric truncated normal. I ran an integrator-free
check myself: a 3-neuron network in the linear regime (`r_max = 1e9`, all neurons above threshold, distinct tau/a/theta,
one inhibitory column) against the exact `expm` solution — `simulate` agrees to 3.58e-5 Hz (RK45, both integration
modes), 2.8e-5 (DOP853), 2.8e-6 (RK4 1 ms), 2.6e-10 (RK4 0.1 ms), 0.83 Hz (Euler 1 ms). The code is right; the suite
just cannot show it. Fix: add (1) that linear-regime `expm` test for `simulate` (RK45 within 1e-4 Hz, RK4 1e-4 within
1e-8 Hz) — it fixes the wiring of tau, a, theta, b, post x pre orientation and the pulse; (2) the single-neuron analytic
exponential asserted on `simulate` at 1e-4 relative; (3) a closed-form moment test for the asymmetric truncation used by
weight noise (`sample_trunc_normal(rng, 0, 0.5, lower=-1)`: mean 0.02762, sd 0.47076 — my 2e6-draw check gives 0.02727 /
0.47041); (4) hand-traced state-machine tests for `prune_screen` (factor the accept/reject update into a pure function
fed with canned scores/peaks, and assert the spec §7.2 sequence: restore only the drawn neuron, silent-pruned stay
removed, `prev_put_back` taken before the last restore, convergence after two identical rounds) and for
`screen_candidate` (monkeypatch `brainir.sim.screen.simulate` with canned activity counts and assert the bracket
sequence 128 -> 64 -> 96 -> 80 ...). The current prune/screen tests (`tests/test_sim_prune_screen.py:32-44, 59-73`)
only check the end result on one embedded oscillator.

### Minor

**B-4. Unreached output samples after a solver failure are uninitialised memory.** `src/brainir/sim/model.py:360`
allocates `r = np.empty((len(ts), n))` and fills only the samples the segment solver returned; on `sol.success ==
False` with a truncated `sol.t` the remaining rows keep whatever was in memory, pass `np.clip`, and
`info["non_finite_samples"]` is never set (only `success=False`). Verified with a stubbed `solve_ivp` returning half a
segment: `success=False`, `non_finite_samples=None`, unreached samples "finite" (here zeros). The authors' code turns
unreached points into `inf -> 0`, i.e. a silent trace, and the notebooks see it as such. Fix: `np.full((len(ts), n),
np.nan)`; the existing `nan_to_num` path then zeroes and *counts* them, and `ReplicateResult` should carry
`non_finite_samples` so failed replicates are excluded rather than scored as silent.

**B-5. `_fixed_step` evaluates the pulse indicator at RK stage times.** `model.py:279-287, 290-309`: the k4 stage of
the step ending at `pulse_start` and the k1 stage of the step starting at `pulse_end` see the other side of the
switch, an O(dt) error (0.13 Hz at 1 ms, documented only in `robustness_experiments.py:33-36`, not in `model.py`).
This is why Part B of the dt study shows first-order behaviour for RK4. Fix: integrate the fixed-step schemes
segment-wise with `make_rhs`, reusing the `edges` loop of the adaptive path; then Part B measures what it claims.

**B-6. Silent-pruning excludes put-back neurons (undocumented deviation).** `prune.py:133`
`newly_silent = prunable & (peak <= 0) & ~removed & ~put_back`; the original (spec §7.2, `vnc_sim.py` L313-314) is
`interneuron & (max_frs <= 0) & ~total_removed` — a put-back neuron that is silent in an accepted simulation is marked
removed there and, once the round resets `put_back`, drops out of the network without a test; BrainIR keeps it
eligible. Small effect, but not in the D36 / docstring deviation list. Fix: drop `& ~put_back` or add the deviation to
the docstring and D36.

**B-7. The activity-based circuit uses the analysis window, the original uses the full trace (undocumented).**
`prune.py:180-182` derives `active_kept_positions` from `peak` over t >= 0.25 s (`_score`), whereas the streaming
engine's `mini_circuit = max_t R_final > 0.01` is over the full 0–1 s trace (spec §7.3). A kept neuron active only in
the first 250 ms is in the authors' set and not in BrainIR's. The `PruneResult` docstring ("peak rate > active_rate_hz
in the final simulation") does not say which window. Also `prune.py:173-176`: when no iteration was ever accepted,
BrainIR reports the state *after* the converged iteration's update, the original the state before (degenerate case).
Fix: use `traj.r.max(axis=0)` for `active_kept`, and document both.

**B-8. Screen "usable" is the tuner verdict, not the published usability filter (undocumented).** `screen.py:87-99`
marks a replicate usable when the tuner's `> 0` activity count lands in [5, 1500]; the paper's usability filter is
applied afterwards in the notebooks with `> 0.01` over the whole trace (spec §6.3, §11 row 7) and can NaN a tuner-ok
replicate (or keep an untested final adjustment). The type-level screen (stimulating every member of a type,
`dns_by_type`) is not implemented: `screen_candidate` takes one index. Fix: record `n_active_all` with `> 0.01` and
apply the published filter in `aggregate_screen` (report both counts); accept a tuple of positions per candidate.

**B-9. No amplitude-aware statistic travels with the standard experiment result.** `experiments.py:94-106`
(`score_trajectory`) and `ReplicateResult` carry only the published, min-max-normalised score; the D30 gate
(`RhythmResult.is_sustained_rhythm`) is used only in `robustness_experiments.py:313-324`. Verified: a 0.0002 Hz
peak-to-trough ripple scores 0.9999 (and the published `> 0.01 Hz` activity gate admits a 0.02 Hz MN whose score then
counts fully in the network mean). This is the paper's convention and must stay the primary score, but the reproduction
JSONs (`stim_dng100_*`) cannot be read amplitude-aware. Fix: move `readout_persistence` into `score_trajectory`
(`n_sustained_readout`, `readout_range_hz_max`) so every result carries both views; leave the published score
untouched. Related (goal2 WS7 "test sensitivity to weighting"): the gate thresholds (range >= 1 Hz, late/early >= 0.5,
>= 3 peaks, CV <= 0.35) have no sensitivity analysis; a table of gate pass-rates on the labelled signals and the
reproduction replicates under +/-50 % threshold changes would close that.

**B-10. Silent no-size fallback.** `model.py:138-149` / `experiments.py:129`: `sizes=None` with
`cfg.size_scaling=True` yields s = 1 for every neuron while the recorded config still says `size_scaling: true`.
`reproduce_dynamics.paper_network` (lines 51, 64-69) supplies v1.0 sizes for MANC v1.2.x by body id (documented,
D25) and the MaleCNS build's own sizes, so current results are fine, but a future caller on a v1.2.x network without
external sizes gets an unflagged different model. Fix: raise when `cfg.size_scaling and sizes is None`, or record
`size_scaled=False` in `NeuronParams` / `Trajectory.info`.

**B-11. Motor-neuron set for reported scores: 144 vs the paper's 138.** Pruning-time decisions in the original use the
144 class-MNs (matches BrainIR's readout); the *notebook* scores the paper reports (mean 0.974 etc.) use the 138
module-labelled MNs (spec §5.1, §11 row 19). BrainIR compares a 144-MN mean to a 138-MN mean; the six extra MNs matter
only if active, and this is not mentioned in the reproduction docs. Fix: one sentence in `reproduce_dynamics.py` /
PHASE1_REPORT, and optionally a 138-MN variant if the module labels are available.

**B-12. Small spec mismatches worth a line each.** (a) `rhythm.py:112-118`: all masked neurons without a peak give
mean frequency 0.0; the authors' `nanmean` gives NaN (harmless; `experiments.py:104` maps 0 to None). (b)
`rhythm.py:55`: the dtype expression evaluates `x.dtype` on the raw input and fails for lists (only arrays are ever
passed; simplify). (c) `prune.py:84-93`: the original's `log(p + 1e-10)` categorical lets excluded neurons (MNs
included) be drawn with weight 1e-10; BrainIR excludes strictly — negligible, not in the deviation list. (d)
`model.py:225-229`: mask is applied before weight noise (streaming-engine semantics; the synchronous engine ignores
masks in noise mode, spec §8) — fine, undocumented. (e) `model.py:355-356`: the segments path does not pass
`first_step` (authors' dt0 = 1e-3); irrelevant to results. (f) `tests/test_sim_model.py:70-79` accepts a 2 Hz
difference between single and segment integration on a 60 Hz-amplitude oscillation; the measured difference on the
real network is ~1e-2 Hz, so the bound could be 0.1 Hz.

### Notes (verified, no action)

- Published score reproduced exactly: a direct-summation float64 implementation written from spec §5.2-5.3 (no FFT,
  naive prominence loop) agrees with `neuron_oscillation_score` to all six decimals on eight signal types (sinusoid,
  bursty, damped, white noise, sinusoid + noise, two-frequency, chirp, 1e-4 ripple); `find_peaks_1d` agrees with a
  naive loop on 300 random arrays with ties. The 1751-sample window (t >= 0.25 s on the 2001-point grid) matches.
- `stimulation_experiment(backend=LocalBackend(1|3))`, `n_workers=2` and the serial path give bit-identical results
  and trajectories (4 seeds, ring circuit). For Modal, bit identity cannot be promised (different CPU/BLAS changes the
  RK45 step sequence); D37's smoke test agreement is consistent with, not a proof of, identity — the docstring at
  `experiments.py:126-127` is correct as written for the local pool.
- Section A / Section B separation in `rhythm.py` is clean; `RhythmResult.paper_score` is never modified by the gates.
- Truncated-normal sampler: bounds `[max(lower, mean − 10 sd), mean + 10 sd]`, CDF clips and half-open uniform match
  spec §3.2; symmetric and asymmetric moments verified.
- `size_scaling` takes the median before replacing zeros, as the authors do (LOG §5 pitfall, test present).
- Sign rule `paper_sign` (ACh +1, GABA/Glu −1, everything else 0 with the neuron kept as a zero-output row) and the
  observed-count matrix `C` (pairs from sign-0 presynaptic neurons retained) implement spec §2.1/§2.3 and rule 1
  (`synapse_count` separate from the hypothesis). `brainir_sign` differs only for histamine (−1 under
  `brainir.sign.conventional-v1`, 0 under the paper rule).

## 3. Spec items versus implementation

Status legend: matches / deviates-documented / deviates-undocumented / not implemented.

| # | spec item (section) | published behaviour | BrainIR | status |
|---|---|---|---|---|
| 1 | rate equation (§3.1) | theta inside `tanh((a/r_max)(x − theta))`, `max(., 0)`, single time scale tau | `model.py:264-274` | matches (verified vs exact `expm` solution) |
| 2 | weight scaling (§2.4) | `0.03 · max(W,0) + 0.03 · min(W,0)` | `scaled_weights`, `b_exc`/`b_inh` | matches |
| 3 | glutamate row multiplier (§2.4, optional) | rows of glutamatergic neurons × `gluRatio` | `Intervention.scale_by_nt` declared, applied nowhere | not implemented (placeholder documented) |
| 4 | truncated-normal sampler (§3.2) | inverse CDF; upper `mean + min(100 sd, 1e6)`; z clipped ±10; CDF clipped 1e-10; `u ∈ [ca, cb)`; sd < 1e-10 → max(mean, 0) | `model.py:107-124` | matches (moments verified) |
| 5 | RNG structure (§3.2, §10) | one JAX key per parameter, one `(n_rep, N)` draw | one NumPy stream per replicate, draws in order tau, a, theta, r_max | deviates-documented (D29; bit-exactness not a target) |
| 6 | size scaling (§2.5) | `s = size / nanmedian(size)` with the median taken before zero/NaN replacement; `a/s`, `theta·s`; median over the loaded network | `model.py:127-135`; `signed_matrix` passes network ids only | matches |
| 7 | initial condition (§3.3) | `R0 = 0` | `model.py:326` | matches |
| 8 | pulse (§3.3) | on for `pulse_start <= t <= pulse_end`, 0.02 → T − 1 ms | `resolved_pulse_end`; `single` uses the same inequalities; `segments` splits at the edges | matches (segmenting is a documented design choice, D29) |
| 9 | integrator (§4) | Diffrax Dopri5, PID (integral) controller, rtol 2e-6, atol 5e-9, dt0 1e-3, float32 | scipy RK45 (same tableau), same tolerances, float64; `first_step` only in `single` mode | deviates-documented (D29) |
| 10 | output grid (§4) | 2001 points for T = 2, 1001 for T = 1 | `model.py:324-325` | matches |
| 11 | failure handling (§4) | `max_steps = 1e5`, `throw=False`, unreached → inf → 0 | no step cap; `success` recorded; unreached samples uninitialised | deviates-undocumented (B-4) |
| 12 | post-processing (§3.5) | nan/inf → 0, clip [0, 1000] | `model.py:366-369` | matches |
| 13 | `removeNeurons` (§2.6, §8) | rows and columns zeroed in all replicates; neuron keeps state and input | `Intervention.silence`, `apply_intervention` | matches |
| 14 | `keepOnly` (§2.6) | listed + all class-MNs kept, outer-product mask | `keep_only` + `always_keep` (caller passes readout) | matches |
| 15 | weight noise (§3.4) | `w(1+eta)`, eta ~ TN(0, sd), eta >= −1, upper 10 sd, on raw counts before b, per replicate key | `apply_intervention`, `weight_noise_seed` | matches (asymmetric moments verified) |
| 16 | input noise (§3.4) | dead code | absent | matches |
| 17 | mask vs noise order (§8) | sync engine ignores masks in noise mode; streaming masks first | mask then noise | deviates-undocumented (harmless, B-12d) |
| 18 | shuffle control (§9.1) | column-block permutation within five classes | `robustness_experiments.class_shuffle` (benchmark code, not `src/`) | matches (outside scope of `src/`) |
| 19 | matrix orientation (§2.2) | file pre × post, transposed once; `weighted_W @ R` | built post × pre directly, `Wb @ r` | matches |
| 20 | sign rule / zero rows (§2.1, §2.3) | ACh +, GABA −, Glu −; unknown/unclear rows kept as zeros | `paper_sign`; `W.eliminate_zeros()`; `C` keeps observed pairs | matches |
| 21 | floor and autapses (§2.1, §2.3) | min |w| = 5; zero diagonal; per-ROI vs after-summation floor unknown | `>= 5` after summation (also over the ROI set); autapses dropped | matches (exact reproduction, LOG §3.11) |
| 22 | sizes column (§2.5) | neuPrint `size` (voxels) | `size_voxels`; v1.2.x from v1.0 by body id | matches (D25) |
| 23 | score, per trace (§5.2-5.3) | min-max to [−1, 1], FFT autocorrelation, normalise by max |ac|, non-negative lags, strict peaks with global-side-minima prominence >= 0.05, `min(max height, max prom)`, `f = 1/lag` of most prominent, sin/cos reference, round 1e-6, clip [0, 1] | `rhythm.py:37-93` | matches (verified independently) |
| 24 | score, per simulation (§5.4) | mean over active MNs (peak > 0.01 Hz after sample 250), unmasked contribute 0; `nanmean` of frequencies with a peak | `rhythm.py:96-119`, `experiments.py:94-106` | matches; all-no-peak → 0.0 instead of NaN (B-12a) |
| 25 | analysis window (§5.1) | samples 250: (1751 for T = 2) | `window(0.25)` = 1751 samples | matches |
| 26 | MN set for reported scores (§5.1) | 144 class-MNs at pruning time; 138 module-MNs in notebook scores | 144 everywhere | deviates-undocumented (B-11) |
| 27 | float32 arithmetic of the score (§5.6) | float32 under JIT | float64 default, `dtype` argument; test shows <= 2e-5 difference | deviates-documented |
| 28 | screen tuner (§4.1, sync) | strong: > 1500 any-positive or > 100 with peak > 100 Hz; weak: < 5; halve / double / midpoint; 10 iterations; last untested adjustment simulated | `screen.py:63-99`; untested final → `usable=False` | matches; final-untested case deviates-documented |
| 29 | screen usability filter (§6.3) | notebooks NaN replicates with `nActive(>0.01)` outside [5, 1500] | not applied; `usable` = tuner verdict | deviates-undocumented (B-8) |
| 30 | screen candidates (§6.1) | cholinergic DNs; optional type groups | caller-supplied single indices | type groups not implemented |
| 31 | screen aggregation (§6.3) | mean over usable replicates; rhythmic if >= 0.5 | `aggregate_screen` | matches |
| 32 | screen duration (§6) | T = 1 s, pulse 0.02–0.999 | caller sets `t_end` (default 2.0) | matches by convention (not enforced) |
| 33 | prunable set (§7.1) | every non-MN incl. the stimulated DN | `prunable_mask & ~readout`; stimulus protected by default | deviates-documented (D36) |
| 34 | accept branch (§7.2) | keep draw; silent-prune `interneuron & max <= 0 & ~removed`; draw ~ 1/max(rate, 1) | `prune.py:130-147`; extra `& ~put_back` | deviates-undocumented (B-6) |
| 35 | reject branch (§7.2) | restore drawn neuron only; put_back |= restore; redraw from failed rates; new round keeps `prev_put_back` = pre-restore set | `prune.py:148-168` | matches (D36) |
| 36 | convergence (§7.2) | round ends and `put_back == prev_put_back` (and something happened); revert to last good | `prune.py:124-127, 174-176` | matches (degenerate never-accepted case differs, B-7) |
| 37 | draw floor (§7.2) | `log(p + 1e-10)` lets excluded neurons be drawn | strict exclusion | deviates-undocumented (negligible, B-12c) |
| 38 | iteration cap (§7.3) | 200 (250 for the other DN) | `PruneConfig.max_iterations = 200` | matches |
| 39 | reported circuit (§7.3) | sync: structural; streaming: `max_t R > 0.01` over the full trace | both reported; activity uses the t >= 0.25 window | deviates-undocumented (B-7) |
| 40 | final rerun (§7.3) | one more simulation with the final mask | `prune.py:176-180` | matches |
| 41 | silencing parameters (§8) | same seed → identical parameter draws as the intact run | sampling independent of the intervention | matches |
| 42 | activation duration (§11 row 11) | T = 2 s, pulse 0.02–1.999 | `ModelConfig` defaults | matches |

## 4. What I ran

- `uv run --no-sync pytest -m "not real_data" -q tests/test_sim_model.py tests/test_metrics_rhythm.py
  tests/test_sim_prune_screen.py tests/test_synthetic_circuits.py tests/test_synthetic_signals.py
  tests/test_compute_backend.py` — 184 passed in 21.3 s.
- A scratch script (not committed; synthetic inputs only, seconds of runtime) with six checks: (a) `find_peaks_1d`
  vs a naive loop, 300 random arrays with ties — 0 mismatches; (b) `neuron_oscillation_score` vs a direct-summation
  implementation written from spec §5 — identical to 1e-6 on eight signals, window = 1751 samples; (c) `simulate` vs
  the exact matrix-exponential solution of a 3-neuron linear-regime network (r_max = 1e9) for RK45 segments/single,
  DOP853, RK4 1e-3 / 1e-4, Euler 1e-3 — 3.6e-5 / 3.6e-5 / 2.8e-5 / 2.8e-6 / 2.6e-10 / 0.83 Hz; (d) weight-noise
  sampler moments for sd 0.2 and 0.5 with lower bound −1 vs closed form — mean 0.02727 vs 0.02762, sd 0.47041 vs
  0.47076 (2e6 draws), min >= −1, max <= 10 sd; (e) `stimulation_experiment` serial vs `backend=LocalBackend(1)`,
  `LocalBackend(3)` and `n_workers=2` — JSON-identical results and bit-identical trajectories (4 seeds); (f) a stubbed
  `solve_ivp` returning half a segment — `success=False`, `non_finite_samples` unset, unreached samples uninitialised.
- Read the per-seed rows and `per_seed_orders` of `results/robust_dt_convergence_manc_v1.2.1_nt-paper_n6.json` and
  both dt-convergence markdown reports; no reproduction script and no real-data simulation was executed.
