# Post-lock review Y (nonlinear dynamics / system identification) of PHASE3_REPORT.md (draft)

Reviewer Y. Scope: reporting, statistics and claims only (goal4 section 70). Nothing here proposes a change to the locked method.
Every number below was re-derived from the result files in this room with `uv run --no-sync python` (scratch scripts in `.tmp/`).
Paths are room paths: `results/level_c/01/level_c_results.json` = LC, `results/tournament/final_b/brainir_state_v1.json` = FB,
`results/counterexamples/<run>/` = CX/<run>, `results/ablations/<run>/SUMMARY.json` = AB/<run>, `results/SELF_AUDIT.json` = SA,
`results/benchmark/calibration.json` = CAL.

## Summary verdict

**Not acceptable as written: 3 blockers and 9 major issues.** The headline conclusion stands: "not supported" for the real circuits and
"partially supported" on the synthetic suite. The aggregate counts I could trace are correct (FINAL verdicts, exact k, the counterexample
tables, the ablation CIs and the Level C C values). But the draft does not show how the real-circuit result arises, and it misreads the
counterexamples:

1. On the real systems the locked method **abstained**:
   - it declared `no_compact_state` on 8 of 10 real systems, including net2 full;
   - it abstained on **every held-out kick and current pair on all three full networks**. The held-out C that the draft reports was
     computed on silencing pairs only;
   - it abstained on every held-out pair of 4 of the 7 mechanisms.

   The draft never says so. It also calls a "compact predictive state for the three full networks" supported, although the method
   itself declared no compact state on net2 full.
2. The claim that the Markov checks "with events" show zero inconsistency on every system is false. On 4 real systems the check after
   events never ran, because the model abstained on every held-out event.
3. The counterexample section says the extreme effect errors arise "where the model predicts huge spurious effects". The job rows show
   the opposite. The extreme ratios come from protocols with a near-zero TRUE effect: a tiny denominator, a modest numerator and a
   small post-event error. The section also misstates the domain: a large share of the candidates lie inside the public protocol
   families.

The major issues:
- the closure power check is not carried to the closure results;
- the real verdicts are not stated to be conditional on the synthetic calibration;
- "compact" verdicts with the wrong k go unmentioned;
- k is not related to the readout's rhythm, and there is no N_observed context on the mechanisms;
- the dimension of the full networks is fragile under data resampling, and the draft does not say so;
- the robustness table uses a non-primary horizon that softens the out-of-distribution degradation roughly threefold;
- the interventional closure gap is omitted;
- the parameter counts of I and J are missing, and self-audit Q9 and Q17 pass vacuously;
- the positive-sounding net1 + net3 transfer result needs a qualifier.

---

## BLOCKERS

### Y-B1. The method's own abstentions on the real systems are hidden, and one "supported" claim contradicts them

**Evidence (LC, `systems.<sid>.brainir_state_v1`):**
- `verdict.abstention.no_compact_state = true` and `verdict.declared_failure = true` on **8 of 10** real systems:

  | system | reason |
  |---|---|
  | net2 full | "latent explains too little beyond the input (val 0.480 > 0.5 x input floor 0.843)" |
  | net1 mech a (02fa13b8) | k = 2 > N/5 = 0.6 |
  | net1 mech b (cce0c6c4) | k = 3 > N/5 = 0.8, and the input-floor rule |
  | net2 mech a (3aa95ab7) | k = 2 > N/5 = 0.6, and the input-floor rule |
  | net2 mech b (3e8f8895) | k = 3 > N/5 = 1.2 |
  | net2 mech c (6883ab7b) | k = 5 > N/5 = 0.6 |
  | net3 mech a (362044b4) | k = 3 > N/5 = 0.8 |
  | net3 mech b (92614efe) | k = 2 > N/5 = 0.6, and the input-floor rule |

  Only net1 full and net3 full have `declared_failure = false`.
- `res.C_heldout`: `n_pairs = 120`, `n_abstained_unsupported = 60` on **each** full network. Per family (`res.C_per_family`), the method
  abstained on 30 of 30 pairs of each of H_kick_A, H_kick_B, H_pulse_A and H_pulse_B, so it supports only silencing
  (`kinds_supported = ["silence"]` in CX/real_*_brainir_state_v1_effect). The reported held-out C (1.27 / 0.96 / 1.04) covers the 60
  silencing pairs (H_silence1_B, H_group_silence) out of 120. `interventional_reason` includes "pairs abstained on" on all three full
  networks.
- On net1 mech a, net2 mech a, net2 mech c and net3 mech a: `C_n_pairs_primary = 0`, `C_abstained_pairs = 15`, C = NaN.
- PROTOCOL section 7: "A model that declares ... `no_compact_state` for a system cannot receive a 'compact causal state' verdict there"
  and "A method's own abstention is recorded as such and is never converted into a verdict it did not claim."

**Where in the draft:**
- Summary lines 28-29: "A 2-3 dimensional latent predicts the held-out readout of all three full networks ...".
- Section 14, line 703: "**Supported:** a compact predictive state for the three full networks".
- Section 23, lines 1026-1027 and the "Permitted" claim, lines 1043-1046.
- The section 14 table, lines 687-698, shows "n/a" for 3 mechanisms without the reason; only net1 mech a says "abstained on events".
- Section 14 says nothing about abstention on the full networks. Neither "abstain" nor "no_compact_state" appears in sections 11-17
  or 23.

**Why this is a blocker:**
- "Supported: a compact predictive state" for net2 full states a claim that the method itself disclaimed on that system. The protocol
  forbids converting an abstention into a claim.
- The draft presents C = 0.96 / 1.04 / 1.27 as "held-out intervention" performance. It hides that the method made no prediction at
  all for half of the held-out interventions (every kick and current).

**Correction:**
- Section 14, line 703: replace the text with: "Predictive condition met on the three full networks (A below input-only and persistence, paired CIs < 0). The
  method itself declared no compact state on net2 full (its input-floor rule: validation error 0.480 > 0.5 x 0.843) and on all 7
  mechanisms (k > N_observed / 5 on every mechanism, and the input-floor rule on 3). Only net1 full and net3 full carry the method's own
  compact claim."
- Summary and section 23 ("three full networks"): write "net1 full and net3 full (net2 full: predictive condition met, but the method
  abstained)". Give the error Z per network, as section 88 requires: A = 0.024, 0.51 and 0.0055, against PCA-k 0.018, 0.24 and 0.0042.
- Add to section 14 and to the summary: "On all three full networks the locked method supports only silencing. It abstained on all 60
  held-out kick and current pairs per network, so the held-out C (1.27 / 0.96 / 1.04) covers the 60 silencing pairs only. On 4 of the 7
  mechanisms it abstained on every held-out pair (C untestable)." Add an "abstained" column to the section 14 table: 60/120 on each full
  network; 15/15 on 02fa13b8, 3aa95ab7, 6883ab7b and 362044b4; 0 elsewhere.
- Section 14, primary comparisons, lines 711-717: state that the C comparisons are paired on the method's non-abstained (silencing)
  pairs only. For example, on net1 full the comparator's C is 1.10 on those pairs (`primary_comparisons.real:net1:full.C.ratio_b`),
  against 1.50 on all 120 pairs. Say that "non-inferior on net2 C and net3 C" and "better on net3 C" therefore concern silencing only.

### Y-B2. The claim that the Markov / rollout checks "with events" show zero inconsistency on every system is false

**Evidence:**
- LC `verdict.markov_detail.events_worst` is `null` (the check after events never ran) for brainir_state_v1 on net1 mech a
  (02fa13b8), net2 mech a (3aa95ab7), net2 mech c (6883ab7b) and net3 mech a (362044b4).
- On the three full networks the check after events ran on silencing events only (Y-B1).
- In FB `events_worst` is null on syn-6a7b88532a and syn-8e0956913a.
- `harness.verdict` sets `markov_ok = (R ok) and (events_ok is not False)`, so an untested events check counts as a pass.
- The event-free restart, the decoy and the readout-consistency checks (`rollout_z_rel`, `rollout_y_nmse`, `decoy_y_nmse`,
  `readout_nmse`) are exactly 0.0 on every real and FINAL system. That part I confirm.

**Where in the draft:**
- Section 17, line 834: "The Markov / rollout-consistency checks (restart from the model's own z, with and without events, and a
  decoy) show zero inconsistency on every system."
- Section 14, line 700: "passes on all systems for both methods".
- Section 8, line 498: "passes on 46 of 46".

**Correction:**
- Line 834: "The event-free Markov restart, the decoy check and the readout consistency y = readout(z, u) show zero inconsistency on
  every real and FINAL system. The restart after held-out interventions was run only where the model predicted events. It showed zero
  inconsistency on the full networks (silencing events only; the model abstains on kicks and currents), on 3 mechanisms and on 44 of 46
  FINAL systems. It was untested on 4 real mechanisms and 2 FINAL systems, where the model abstained on every held-out event;
  markov_ok counts an untested events check as passed."
- Add the same qualifier to line 498 and line 700.

**Answer to question 1:** no system failed a check, so no k had to be declared invalid. But "passed on every evaluated system, with
and without events" is not established. The check with events is untested on 6 systems and silencing-only on the three full networks.

### Y-B3. The counterexample interpretation is contradicted by the job records

**Evidence** (script `.tmp/cx3.py` over all `jobs/*.json` rows; candidate = err >= the system's threshold; "random-median" = the
median over that system's random-strategy protocols):

| sweep | candidates | true-effect denominator < 1 % of random-median | numerator <= 10x random-median | post-event NMSE < 1 | worst per system with denominator < 1 % | all-in-family candidates | systems with an in-family candidate |
|---|---|---|---|---|---|---|---|
| FINAL v1 effect | 4,048 | 39 % | 74 % | 77 % | 36 of 47 | 793 (20 %) | 44 of 47 |
| FINAL lin_dmdc_t effect | 3,987 | 46 % | 83 % | 80 % | 40 of 48 | 22 % | 42 of 48 |
| real public v1 effect | 585 | 71 % | 89 % | 86 % | 7 of 7 | 120 (21 %) | 6 of 7 |
| real hidden v1 effect | 661 | 62 % | 90 % | 85 % | 7 of 7 | 68 (10 %) | 7 of 7 |
| real public lin_dmdc_t effect | 714 | 77 % | 88 % | 89 % | 10 of 10 | 16 % | 10 of 10 |

- Example: the net1 full worst case in CX/real_hidden has err = 1.0e10 and err_post = 0.063, i.e. a well-predicted post-event readout.
  A typical row (`jobs/real_net1_full_bo_s0.json`) has `effect_num` 0.0127 and `effect_den` 2.2e-5.
- The candidate RATE per protocol on the real public sweep is 0.198 in-family against 0.183 out-of-family (`.tmp/cx4.py`).

**Where in the draft:**
- Section 9, lines 530-531: "effect errors of 10^3 to 10^9 on searched protocols, where the model predicts huge spurious effects".
- Section 16, line 807: "broken almost at once by interventions outside the calibrated domain: worst-case effect errors five to seven
  orders of magnitude above their typical ones".
- Section 23, line 1039: "break easily outside the public protocol domain".

**Why this is a blocker:** the stated mechanism, huge spurious predicted effects, is false for most of the extreme cases. They are
protocols whose true effect is near zero (silencing near-silent neurons, clipped kicks), where the effect-error ratio has a tiny
denominator. The statement that the model breaks "outside" the domain is also false as an exclusive statement. 20 % of the FINAL
candidates and 10-21 % of the real candidates lie entirely inside the public families, on 44 of 47 FINAL systems and on every
searchable real system. On real public draws the in-family rate equals the out-of-family rate.

**Correction:**
- Replace lines 530-531 with: "Its worst effect errors (10^3-10^9) arise mostly on protocols whose true effect is close to zero. On 36
  of 47 systems the worst protocol's true-effect energy is below 1 % of a typical protocol's. The post-event readout is predicted with
  NMSE < 1 in 77 % of the candidates. The extreme ratios therefore measure a small spurious predicted effect against a near-null true
  effect, not a gross failure of the rollout."
- Replace line 807 with a statement that counterexamples occur both inside the public families (in-family candidate rate 0.20 against
  0.18 out-of-family on the real public sweep) and outside them.
- Replace "outside the public protocol domain" (line 1039) with "inside and outside the public protocol families".
- Report the fraction of candidates with a near-null true effect, and C restricted to non-null protocols, next to every counterexample
  table.

---

## MAJOR issues

### Y-M1. Counterexamples: event kinds, unsearchable systems, typical errors and missing state are not reported (question 4)

**Evidence** (CX SUMMARY `systems.<sid>`):
- **Unsearchable systems.** On the real systems the locked method supports no event kind on 3 of 10 (`kinds_supported = []` on
  02fa13b8, 3aa95ab7 and 6883ab7b; `n_scored = 0`).
- **Silencing only on the full networks.** On all three full networks it supports silencing only. The comparator supports all three
  kinds everywhere.
- **Typical real errors are already at or above no-effect.** The typical (random-protocol median) effect error of the locked method on
  the real systems is 4.53 (hidden draws) and 4.92 (public draws) on net1 full, 1.08 and 1.09 on net2 full, and 1.06 and 1.03 on net3
  full. The median over the 7 searchable systems is 0.99 (hidden draws) and 0.95 (public draws).
- **Inflated thresholds.** The candidate threshold max(1, 2 x p90) is 57,732 (hidden draws) and 16,134 (public draws) on net1 full,
  and 770 on net2 full, because p90 is huge.
- **Init-state perturbations.** Perturbed initial states raise the candidate rate: FINAL v1 effect 0.155 against 0.111; real public
  0.246 against 0.150; real hidden 0.248 against 0.194.
- **Q19 denominator.** Q19's denominator of 116 counts the 8 unsearchable system-runs as "not broken". Over the 108 searchable runs,
  20 / 108 = 0.185.

**Where in the draft:**
- Section 16 table: "7 of 10" against the comparator's "10 of 10".
- Line 807: "their typical ones".
- Summary line 39: "5 of 10 real systems".
- Section 21: Q19 = 0.17.
- Sections 9 and 16 never mention event kinds, the in- or out-of-family split, the effect of init states, or what the counterexamples
  imply about missing state. goal4 section 53 says counterexamples "identify missing state".

**Correction:**
- Section 16: "7 of 7 searchable systems (3 mechanisms unsearchable: the model supports no event kind); on the full networks only
  silencing could be searched".
- Add to section 16: "The typical real effect error on random protocols is about 1 (net2 and net3 full) and about 4.5-4.9 (net1 full),
  i.e. no better than predicting no effect before any search".
- Add a per-sweep breakdown by event kind, family membership and init state.
- Add a paragraph on missing state. The effect counterexamples mostly reflect near-null true effects and a mis-scaled event read-in.
  Perturbed initial states raise the rate by about 1.3-1.6x, which is weak evidence that off-manifold initial conditions carry state
  the latent lacks. The searches did not isolate a specific missing state variable.
- Report Q19 on the searchable denominator (0.185).
- Section 15, criterion 37 says "6 sweeps"; there are 7 (4 FINAL + 3 real).

### Y-M2. Closure: the power check is not attached to the closure results, and the real verdicts are not called conditional (question 2)

**Evidence** (CAL `closure_power`):
- 'closed' pass rates: true latent 0.80 (36/45), random-k 0.244 (11/45), PCA-(k-1) 0.172 (5/29), PCA-k 0.44.
- The wording rule ("more than 25 %" of random-k passes means using "no large microstate or history gain detected") is met by one
  system: 12/45 = 26.7 % would have triggered it. The Wilson 95 % interval of 11/45 is about [0.14, 0.39].
- PCA-(k-1), a latent that provably misses a dimension, passes 'closed' on 17 % of the systems.
- On FINAL, 1 of the 3 under-estimated systems passes 'closed' and receives "compact causal state (E untestable)": syn-fe069050cb,
  k = 5 against true 6.
- tau_gap is null, so the closure gap never enters (`closed_parts.closure_gap = true` everywhere).
- PROTOCOL section 6: "Real verdicts are therefore CONDITIONAL on the synthetic calibration, and the report says so." The draft never
  says so; "conditional" appears nowhere.

**Where in the draft:**
- The power figures appear once, in section 4.2 (line 259: "24 % ... 80 %"). The PCA-(k-1) rate is missing.
- Sections 8 (line 501: "closed 36"), 14 (line 709) and 23 (line 1033: net3 full "predictive and closed") use "closed" with no power
  qualifier.

**Correction:**
- The word "closed" is permitted by the rule, and I do not ask to change it.
- Next to every closure result (sections 8, 14 and 23), add: "'closed' = D micro-gain and history-gain upper CIs within tau_D / tau_H
  and markov_ok; the closure gap does not enter (tau_gap null). Power on the dev calibration: the true latent passes on 80 %, random-k
  projections on 24 % (11/45, one system below the 25 % wording threshold), PCA-(k-1) on 17 %. A latent missing one dimension passes
  about 1 time in 6 (FINAL: syn-fe069050cb, k = 5 against 6, passes)."
- Add to sections 14 and 17: "Real verdicts are conditional on the synthetic calibration: dt 1 ms against 10 ms, one parameter draw
  per trajectory, absolute-Hz kicks, a pooled normaliser. The power of 'closed' on the real systems is not calibrated."

### Y-M3. Dimension: "compact causal state" verdicts with the wrong k are not disclosed (question 3)

**Evidence (FB `per_system`):**
- Of the 19 FINAL "compact causal state" verdicts, 5 have the wrong k:

  | system | k | true k | trap |
  |---|---|---|---|
  | syn-5501045d59 | 8 | 1 | A, nuisance; E untestable |
  | syn-0f1a2b2092 | 3 | 2 | J |
  | syn-82a1192491 | 2 | 1 | H |
  | syn-d4f6b8983e | 2 | 1 | |
  | syn-fe069050cb | 5 | 6 | E untestable |

- Recomputed rates: exact k 27/46 = 0.587; under 3/46 = 0.065 (313036b921 1 against 2, 6a7b88532a 1 against 2, fe069050cb 5 against
  6); over 16/46 = 0.348.
- The compact rule k <= max(1, N_obs / 5) was applied as registered: k = 8 with N_obs = 200, and `compact = true` on 46 of 46.
- G seeds: on syn-0f1a2b2092 seed 0 gives k = 3 (compact verdict), seeds 1-2 give the true k = 2. On syn-1de2b0aa08 it is 2, 1, 1
  against true 1.
- The FINAL implementation group "Hopf x4" has true k = 2 on every member, but the method's k is 2, 6, 6, 2 across implementations
  (5f0a0fa085, 0cf4f43f95, 27e0511d5b, e6e4dd04ab).

**Where in the draft:** Summary lines 19-20 and section 23, lines 1035-1036 ("compact causal state on 19 ..., the exact dimension on
27"). Read together they imply that the 19 have the right k. Section 6 notes that verdicts do not certify k, but only for the trap
review.

**Correction:**
- Add: "Of the 19 'compact causal state' verdicts, 5 have the wrong k (4 over-estimated, including k = 8 against 1 on the nuisance
  trap A; 1 under-estimated, k = 5 against 6). 'Compact' is the registered k <= N_observed / 5, not minimality."
- Add: "Within the Hopf implementation group (true k = 2) the method selects k = 2, 6, 6 and 2. The selected dimension depends on the
  physical implementation."
- State that the FINAL dimension rates are seed-0 values, and that 3 of the 8 G systems change k across seeds.

### Y-M4. Dimension on the real systems: no comparison with the readout's structure and no N_observed context; the full networks' k is fragile under resampling (question 3)

**Evidence:**
- **No oscillation diagnostic reported.** The mechanisms were regenerated under a "public no-gate rhythm criterion" (PROTOCOL 2.1),
  i.e. as rhythm generators. The locked method has its own sustained-oscillation detector (`brainir_state_v1.sustained_oscillation`,
  whose flag sets k_min = 2 and is stored in the fit info as `oscillation`), but no result file or report section gives its value per
  real system.
- **Comparator k = 1 on rhythm mechanisms.** The comparator selects k = 1 on net1 mech b and net3 mech a. A 1-D state cannot sustain
  an oscillation (a 1-D linear map oscillates only at period 2), and the draft reports these comparisons without comment.
- **k versus N_observed.** N_observed on the mechanisms is 3, 4, 3, 6, 3, 4 and 3 (LC `n_observed`). The locked method's k equals or
  exceeds N_observed on 2 of the 7: k = 3 with N = 3 on net2 mech a and k = 5 with N = 3 on net2 mech c. The latter is a 5-D state for
  3 observed neurons.
- **Data resampling (`G_resample.per_system`).** The k of the full networks changes under half-sampling of the training data: net1 full
  [2, 2, 8, 2, 2]; net2 full [4, 6, 2, 2, 5]. On net3 full, the draft's one "partially supported" system, k agrees (2 each time), but
  the latent does not: `r2_min_mean` = -1.16.
- **Method's own ranges.** The descriptive k ranges (LC `k_range`) are net1 full [2, 8], net2 full [2, 5] and net3 full [2, 2]. The
  draft reports none of them.
- **Required N_observed report.** PROTOCOL F requires k / N_observed, and for the real systems also k against the neurons that peak
  above 1 Hz. Neither appears.

**Where in the draft:**
- Summary line 28, section 14 lines 703-705 and section 23 ("2-3 dimensional").
- Section 14, lines 731-734, gives seed ranges but not the resampling k of the full networks, and does not say that net3 full is the
  -1.2 case.
- The section 14 table has no N_observed column.

**Correction:**
- Add N_observed, the number of neurons peaking above 1 Hz, the method's descriptive k_range (labelled "descriptive, not scored") and
  the oscillation flag to the section 14 table.
- Add to section 14: "k exceeds or equals the observed population on 2 mechanisms (net2 mech a: k = N = 3; net2 mech c: k = 5 > N =
  3). On the mechanisms, k is not a compression of x."
- Relate k to the rhythm: state whether the readout oscillates. Where it does, k >= 2 is necessary, and the comparator's k = 1 on net1
  mech b and net3 mech a cannot represent the rhythm.
- Replace "a 2-3 dimensional latent" with: "a 2-3 dimensional latent (seed 0; across 5 half-samples k = 2-8 on net1 full and 2-6 on net2
  full; on net3 full k = 2 each time but the half-sample latents do not agree, min R^2 -1.16)".

### Y-M5. Robustness: the table uses a non-primary horizon that softens the out-of-distribution degradation roughly threefold

**Evidence** (LC `res.A_B` and `res.H_ood`). The primary horizon is 250 ms (PROTOCOL section 4, bold). At that horizon:

| net1 full | held-out | out-of-distribution stimulus | factor |
|---|---|---|---|
| brainir_state_v1 | 0.0244 | 5.74 | about 235 |
| lin_dmdc_t | 0.0224 | 0.644 | about 29 |

The draft's table uses 100 ms: 0.024 → 1.82, 75-fold. At 250 ms on net3 full, v1 goes from 0.0055 to 0.13 and the comparator from
0.0073 to 0.24.

**Where in the draft:** Section 17 table and line 829 ("75-fold on net1, where the comparator loses a factor of 26"); summary line 38
("up to 75-fold").

**Correction:** report the primary 250 ms horizon: "an out-of-distribution stimulus degrades the locked method's prediction about
235-fold on net1 full (0.024 to 5.74), against about 29-fold for the comparator". Keep 100 ms as a secondary column, if at all.

### Y-M6. The interventional closure gap, a dynamics diagnostic the protocol requires, is omitted

**Evidence:**
- LC `verdict.interventional_closure_gap` for the locked method is 24.6 (net1 full), 2.38 (net2 full) and 31.4 (net3 full). The
  comparator's is 1.09, 1.01 and 1.03.
- `res.C_heldout.interventional_closure_gap.ratio_no_effect` is almost identical: 24.4, 2.45 and 31.3. So the model's latent after a
  silencing event is as far from the encoding of the intervened history as a rollout that ignores the event.
- On the FINAL suite the median is 0.70 for the locked method and 0.71 for the comparator.
- PROTOCOL section 4 C lists this gap as "also reported" (review A M5). The draft never mentions it.

**Correction:** Add to section 14: "After held-out silencing, the locked model's rolled-out latent differs from the encoder's reading
of the intervened history by 24.6x (net1 full) and 31.4x (net3 full) the intervened-versus-twin encoding distance. A rollout that
ignores the event scores the same. The event operator does not move z along the direction the encoder assigns to the event. This is
the state-level counterpart of C being about 1."

### Y-M7. Sharing (I, J): the parameter counts are missing, and self-audit Q9 and Q17 pass vacuously (question 6)

**Evidence:**
- **Shared equals independent everywhere.** Parameter counts (shared / independent totals) are identical everywhere:

  | comparison | total |
  |---|---|
  | I net1 | 891 / 891 |
  | I net2 | 5,256 / 5,256 |
  | I net3 | 3,504 / 3,504 |
  | J net1 + net2 | 5,064 / 5,064 |
  | J net1 + net3 | 3,897 / 3,897 |
  | FINAL Hopf group | 8,066 / 8,066 |
  | FINAL gated-integrator group | 922 / 922 |

  `fewer_parameters = false` in every row.
- **The method's own shared law was never scored on hidden data.** Its internal test (`method_own_verdict`) had a smaller shared
  transition law: 16 against 53 parameters on net1, and 16 against 30 on net3. It declined that law on public validation data, so the
  hidden I/J rows compare independent models with themselves (every A_diff / C_diff = 0 [0, 0]) plus the leave-one-out adaptations.
- **Cross-connectome models.** J `model3_shared` equals `model1_independent`, and `model4_partial` is null (not implemented).
- **Transfer direction.** The J transfer was run in one direction only (held = net1 full).
- **Q9.** SA Q9 = pass with the note "nothing to attribute to capacity".
- **Q17.** SA Q17 = pass because the 3 unrelated pairs are "rejected". The same method also fails to support both true implementation
  groups (untestable, rejected), because it never returns a shared law. The null test therefore does not discriminate.

**Where in the draft:**
- Section 14, lines 721-728, has no parameter counts. Criterion 33 (line 773) claims "held-out comparisons with parameter counts".
- Section 21 counts Q9 and Q17 among the 16 passes (lines 961-963, 984).

**Correction:**
- Add the parameter-count table above to section 14, together with the method's internal transition-law counts.
- State: "The shared law was never evaluated on hidden data. The method's internal test rejected it on public validation data, so the
  I and J verdicts reflect the independent models and the adaptation fits."
- Report Q9 as **untestable** (n/a): no shared model with a different capacity exists.
- Qualify Q17: "the unrelated pairs are rejected, but so are the true implementation groups; the rejection does not discriminate
  (S8 = 0.5 by construction)".
- Science count: 15 pass, 3 fail, 1 n/a.
- Say that the J transfer is one direction only (net2 → net1 full).

### Y-M8. The net1 + net3 transfer is reported as a positive result without its absolute level

**Evidence:** LC `J.net1+net3.transfer[0]`: C_diff = -0.166 [-0.616, -0.008], `ratio_a` (adapted) = 1.052, `ratio_b` (scratch) = 1.218.
Both are worse than predicting no effect.

**Where in the draft:** Section 14, line 727: "adaptation beats a fit from scratch on C (-0.17 [-0.62, -0.01])".

**Correction:** append: "Both the adapted C (1.05) and the from-scratch C (1.22) are above the no-effect value 1; the advantage is
between two predictions that are no better than predicting no effect."

### Y-M9. Self-audit Q5 (smoothing) and Q14 do not test what the draft says they test

**Evidence:**
- **Q5 is correct as computed but tests only synthetic under-estimation.** SA Q5 `underestimated_fraction` = 0.065 (3/46, which I
  confirm), `fast_systems_underestimated_fraction` = 0.125 (1/8), thresholds 0.25 / 0.5. It uses the synthetic truth only. On the real
  systems the method subsamples 1 ms data to a grid of about T/400 = 5 ms (section 13), i.e. it smooths, and no test covers them.
- **Q14's pass rests on a NaN.** SA Q14 `median` = NaN, because 4 real systems have NaN ratios; `NaN > 3` is False, so it passes. On
  the finite values the median is 1.12, so the outcome holds. But two mechanisms have post-intervention error 5.8x (cce0c6c4) and 6.7x
  (3e8f8895) the unperturbed A.

**Correction:**
- Qualify Q5: "tested on synthetic systems only, where the native dt equals the model grid; the down-sampling of the real 1 ms data
  (grid about 5 ms) is untested".
- Qualify Q14: "median over the 6 real systems with a defined ratio 1.12 (the self-audit's own median is NaN because 4 systems are
  untestable); post-intervention error is 5.8x and 6.7x the unperturbed A on two mechanisms".
- Neither changes a status, but both are presented as tested passes.

---

## Minor issues

- **m1. Dev ablation sign typo.** Section 10, line 543: "The exact-k rate falls by 0.15 [0.30, 0.02]". The file (AB/ablations_dev
  `nn_dim_rule.paired_vs_full.S6_exact_k_rate`) gives -0.152 [-0.304, -0.022]. Write "-0.15 [-0.30, -0.02]".
- **m2. Ablations: effects beyond the medians.**
  - FINAL `delays`: the S6 CI is [0.000, 0.130], its lower bound touches 0. Call it "not significant (CI lower bound 0)".
  - "All other switches leave every median at 0" is true for the medians. But compact verdicts change: `draw_folds` 19 → 17;
    `grid_extension`, `nested_selection` and `sparsity` 19 → 18.
  - The `abstention` switch changes S7 from 0.74 to 0.50 (abstention recall 0.5 → 0).
  - Mean-based paired CIs exclude 0 for `draw_folds` S1 (-0.14 [-0.33, -0.004]), `sparsity` S5 (+0.027 [0.001, 0.072]) and
    `nn_dim_rule` S3 (-0.031 [-0.066, -0.001]).
  - State these, and state that 90 component x switch CIs carry no multiplicity correction. The suites are stated correctly: dev =
    development data; FINAL = primary and unbiased. The selection-bias caveat for dev is adequate.
- **m3. Mechanism C without CIs.** In the section 14 table, the mechanism C values have no CI. Add net1 mech b 0.91 [0.36, 2.69],
  net2 mech b 0.79 [0.74, 1.13] and net3 mech b 0.38 [0.21, 0.67].
- **m4. Wrong section reference.** Section 12, line 595: "the corresponding Level C fits (section 13)" should read section 14.
- **m5. Q8 CIs differ from the verdict CIs.** SA Q8's real "heldout_ci95" values differ from the verdict C CIs, for example net1 full
  [1.10, 2.31] against [1.03, 1.89], and net1 mech b [0.12, 0.40] against [0.36, 2.69]. Presumably another window. Say which window
  Q8 uses.
- **m6. FINAL interventional failures by abstention.** On 4 FINAL systems the interventional condition fails ONLY because pairs were
  abstained on (1c5ebb1701, 6a7b88532a, 8e0956913a, d7a7574c7e). 15 FINAL systems have abstained held-out pairs. Mention this in
  section 8. The S2 profile compares the method's C on its supported pairs with the comparator's C on all pairs.
- **m7. Section 8 sharing is untestable, not rejected.** The Hopf group's "untestable" is caused by the method's crash, not by a
  sharing test. Say so next to "one untestable".

---

## What I re-derived and found correct

- **FINAL counts (FB).**
  - Verdicts: 17 + 2 compact, 12 partial, 15 not supported.
  - Conditions: predictive 32, interventional 24, closed 36, microstate-equivalent 34 (E testable on 40), state-mediated 27, markov_ok
    46 of 46.
  - Dimension: exact k 27, under 3, over 16.
  - Abstention: recall 0.5, false alarm 1/46, confident-wrong 0.521.
  - G: the same k on 4 of 8; r2_min 0.69-1.00.
  - Failures: 4 of 108 fits, 0 of 99 evaluations.
  - The profile values in the section 8 table for the locked method, and the comparator's exact-k rate 16/46.
- **Compact rule.** The rule k <= max(1, N_obs / 5) is applied as registered: synthetic and full real systems judged, mechanisms
  `compact = null`.
- **Level C numbers (LC).**
  - Per-system k and verdicts; the predictive, closed and microstate columns.
  - C and its upper CIs: 1.27 (1.89), 0.96 (1.02), 1.04 (1.20), and 0.91, 0.79 and 0.38 on the mechanisms.
  - Closed on net3 full, net2 mech c and net3 mech b. Microstate-equivalent on 8 of 10.
  - Holm primary: non-inferior on net2 C, D and E, and on net3 A and C. Secondary: better on net3 A and C; worse on net1 E, net2 A
    and net3 E.
  - The seed k agrees on 2 of 10 (median r2min 0.99, 0.99 and 0.69 on the full networks); the half-sample arm on 4 of 10 (-1.16 to
    0.93).
  - PCA-k is better than the method on 9 of 10 (the method is better only on net2 mech c).
  - Parameter probe: 0.30-0.81 overall, 0.33-0.58 on the full networks, comparator 0.96-0.98.
  - Fit failures: 8 (2 partial sharing, 6 leave-one-out).
- **I / J verdicts.** net1 and net3 rejected, net2 untestable. J net1 + net2 transfer: A +4.92 [4.80, 5.04], C +251 [78, 926]. J net1 +
  net3: A +0.0024 [-0.0002, 0.0046], C -0.166 [-0.616, -0.008].
- **Robustness table.** The values match the file at the 100 ms horizon; the choice of horizon is the issue (Y-M5).
- **Counterexample tables (sections 9 and 16).** Every cell reproduces from the SUMMARY `overall` blocks: 47 / 2,558 / 2,357 / 9;
  48 / 2,414 / 1,048 / 3; 39 / 698 / 31 / 3; 41 / 729 / 23 / 3; 7 / 430 / 8.4e5 / 5; 10 / 564 / 3.6e7 / 4; 7 / 416 / 1.7e5 / 3. The
  random medians are 0.57 and 0.70, there are 0 failed searches, and Q19's 20 / 116 = 0.172 reproduces as computed.
- **FINAL ablations (AB/ablations_final).**
  - `event_calibration`: S2 +0.298 [0.125, 0.473], compact 19 → 10.
  - `nn_dim_rule` -0.043 [-0.152, 0.065]; `nested_selection` -0.065 [-0.196, 0.065]; `fold_repeats` 0 [-0.109, 0.109]; `sparsity`
    +0.065 [-0.022, 0.152]; `delays` +0.065 [0, 0.130], compact 19 → 15. All medians of the other switches are 0.
  - Dev: `event_calibration` +0.264 [0.101, 0.595], compact 8 → 3.
- **Calibration power (CAL `closure_power`).** true latent 0.80, random-k 0.244, PCA-(k-1) 0.172 (n = 29), PCA-k 0.444; wording
  "closed". The draft's use of the word "closed" is permitted.
- **Self-audit.** Q5 (0.065 / 0.348 / fast 0.125), Q12 (6/18 agree, 0.795), Q13 and Q16 evidence as quoted in section 21.
