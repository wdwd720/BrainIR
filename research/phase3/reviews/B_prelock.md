# Review B (causal inference): brainir_state_v1 and the version-2 intervention evidence

Reviewer B. Scope: whether family C (effect error against counterfactual twins, held-out targets and types) and latent lifting justify
causal claims; whether latent interventions and lifts are legitimate; which shortcut confounders are blocked.

Evidence produced for this review: `.tmp/B/cexp.py` (script), `.tmp/B/cexp.jsonl` (results). The script fits brainir_state_v1 (seed 0,
default config) on 10 public dev systems (train + val) and scores it with the public v2 evaluator (`evaluate.eval_intervention`,
`eval_predictive`, SYNTH_CFG, held-out C roles of `harness.SYNTH_ROLES`). Run with `uv run python .tmp/B/cexp.py <sid> ...` (3 threads,
about 90 s per system). Other evidence comes from reading code, cited as file:line.

## Summary verdict

**Not ready to support causal claims as worded; lock the method only after the fixes to reporting / evaluation below.**

The twin construction is sound: pre-event encoding, shared noise, the effect cancels observation and readout noise, and synthetic
held-out targets are disjoint from training targets. v1's own event machinery is also legitimate: events act only through z, the
encoder is pure, and it never sees y. But the C evidence does not support what the verdict label claims.

1. The interventional condition in effect reduces to "significantly better than predicting no effect". tau_C = 3.29 can never bind.
   For v1, half of the tested dev systems score the same C when the pre-intervention state is replaced by the training-mean state.
   So C certifies an event-response operator, not a causal *state*.
2. On the real mechanism systems (7 of 10 real systems), three of the four "held-out" intervention families use the training
   targets.
3. Some synthetic held-out targets are unobserved neurons, whose effects cannot be identified from x. v1 scores them silently as
   "no effect", and on some systems they dominate C.
4. The evaluator never checks that `rollout` is a function of z0. A stateful model can report k = 1 while predicting from the
   full microstate. I demonstrate this.
5. v1 does not support lifting. No latent-intervention (do(z)) claim can be made for it.

## BLOCKERS

### B1. "Causal state" is not established by C: the verdict's interventional condition cannot tell a causal state from a state-independent event response

**Evidence.**
- *tau_C is inert.* Verdict: `C <= tau_C` AND `upper CI < 1` (`src/brainir_state/harness.py:243-244`). tau_C = 3.29
  (`data/tolerances.json`), so any C whose CI upper bound is below 1 also satisfies `C <= 3.29`. The pre-registered sensitivity
  analysis confirms this: the true-latent verdict counts are identical at both CI ends of tau_C, [2.03, 34.1]
  (`extra/benchmark/calibration.json`, `true_latent_verdicts_at_tolerance_ci_ends`). The only operative criterion is "better than
  the null of no effect". A model that predicts about 5 % of every true effect along the right direction has C ≈ (1-0.05)² = 0.90.
  With a tight CI it passes.
- *C does not rank the true state first.* In the calibration's per-system results (45 dev systems), the median held-out C is:
  - PCA-k linear control: 0.68 (C < 1 on 29 / 45);
  - true-latent reference: 1.58 (C < 1 on 16 / 45);
  - full-state ceiling: 1.13.

  A generic linear projection beats the exact state. C therefore measures the quality of the event operator (the true-latent
  reference maps events through a ridge probe, `refmodels.py:388-414`) rather than whether z is the causal state.
- *C is largely state-independent for v1.* I re-scored v1's held-out C with the true pre-event encoding replaced by the mean
  training encoding (same events, same inputs, same model; primary 1 s window):

  | system | k | C (true z0) | C (z0 = training mean) | C (z0 = random training encoding) |
  |---|---|---|---|---|
  | syn-9853fca40a | 1 | 0.064 | 0.059 | 0.093 |
  | syn-566e16b512 | 3 | 0.299 | 0.241 | 0.886 |
  | syn-f365aa5a73 | 2 | 0.157 | 0.197 | 1.23 |
  | syn-1f16e42a17 | 3 | 0.245 | 0.255 | 0.295 |
  | syn-b3e6273583 | 3 | 0.275 | 0.277 | 0.291 |
  | syn-1e61c72597 | 1 | 0.121 | 0.852 | 0.202 |
  | syn-3296f4ad79 | 2 | 0.643 | 0.936 | 1.98 |
  | syn-f60f07a27f | 2 | 0.666 | 0.937 | 1.56 |
  | syn-fe868499dd | 8 | 0.174 | 0.916 | 0.725 |

  (syn-b8dafc4f01: C = 1.000 in every variant, see M2.) On 5 of 9 systems, knowing the actual state does not help: equal or
  better C with the mean state. On 9853, f365, 3296 and b3e6 the per-family C of kicks and currents is identical to 3 digits
  (`per_family_C_v1_vs_meanz0` in `.tmp/B/cexp.jsonl`). This is linear superposition: with an additive kick dz = g (dx/sd) C_0 and a
  near-linear law, d_pred = f^t(z0 + dz) - f^t(z0) does not depend on z0.
- The effect metric subtracts the model's own no-event rollout (`evaluate.py:259`). Errors in the model's free dynamics from z0
  cancel, and the post-intervention NMSE is reported but not judged.

Taken together, a system labelled "compact causal state discovered" has shown three things. Its z predicts well (A). Its z is
closed (D). And separately, an event→readout operator predicts effects better than zero. It has not shown that intervention effects
are mediated by, or conditional on, z.

**Where.** PROTOCOL.md sections 6-7 (tau_C, interventional condition); `harness.verdict`; the verdict label for synthetic and real
systems.

**Fix (either one, before Level C).**
- (a) No protocol change: in every report, state the interventional condition as "held-out intervention effects predicted
  better than no effect (C upper CI < 1); tau_C does not bind". Do not attribute causal status to z beyond that.
- (b) A reported state-dependence control, which is cheap:
  - C_scrambled = C with z0 replaced by the mean training encoding, and with a permuted pair's z0;
  - the paired difference C_scrambled - C with the trajectory bootstrap already used;
  - claim "effects are mediated by the state" only where C is significantly below C_scrambled.

  Also report C for the PCA-k and true-latent references next to v1 (they are already fitted), so readers see that C does not rank
  the true state first.

### B2. On the real mechanism systems, the "held-out TARGET" families are not held out

**Evidence.**
- `extra/orchestrator/brainir_state/realgen.py:93-96`: for `mode == "mech"`, `split_targets` returns (all observed, []).
- `realgen.py:187-192`: `H_kick_B`, `H_pulse_B` and `H_silence1_B` draw from `B or A`, i.e. from A, the public targets.
- `data/systems_public.json`: on all 7 mechanism systems, `targets_public` equals `observed`.

`harness.REAL_ROLES["heldout_intervention"]` puts those three families into the verdict's C_heldout. On 7 of the 10 real systems,
3 of the 4 families in the "held-out STATE / INPUT interventions" condition are therefore in-distribution targets with hidden
parameter draws. The developers could simulate and train on exactly those targets (the simulation service refuses only B targets,
and B is empty). Only H_group_silence is held out there, and only by type: 2-3 of 3-6 neurons.

PROTOCOL.md 3.1 does say "for mechanism systems, A = all members". But the family table (lines 104-106) and the verdict rule call
these families held-out targets, and nothing in the result keeps the two apart.

**Fix.** For mechanism systems:
- report H_*_B as in-distribution (merge them with H_*_A in `C_indist`);
- base the held-out C on H_group_silence only, or label the interventional verdict on mechanism systems "in-distribution targets,
  hidden draws; held-out type = group silencing only".

This is a reporting / role-table change. The hidden data do not need to be regenerated.

## MAJOR issues

### M1. The evaluator does not enforce that predictions go through z (stateful side channel; the compact-k claim is unenforced)

`eval_predictive` and `eval_intervention` call `encode_at(...)` and then immediately `model.rollout(sid, z0, ...)` on the same
in-process object (`evaluate.py:192-194, 251-254`; `suite_eval.evaluate_model_job` loads the model once per job). Nothing checks that
the rollout depends only on (z0, u, events). The Markov-consistency check (`eval_rollout_checks`) uses event-free rollouts and
restarts from `zf[a]` right after encoding.

**Demonstration** (`Cheat` in `.tmp/B/cexp.py`): `encode()` stores the full PCA state of the history and returns only its first
coordinate. `rollout()` uses the stored state. The cheat reports k = 1, and on all 10 systems its A and C equal those of the PCA-N
model it hides, to every digit. For example:
- syn-b8dafc4f01: A 0.239 vs 1.38 for an honest PCA-1;
- syn-f365aa5a73: C 0.193.

v1 is clean. `ks_sindy._encode` / `KSModel.encode` are pure (`ks_sindy.py:31-36`, `ks_core.py:459-464`), and the event
rollout carries only z (`ks_core.py:491-535`; the compiled event grid is input, not memory). The hole still applies to every model
scored at Level C, including the strongest baseline, and it undermines the "compact" condition and F.

**Fix (orchestrator).**
- Before rollouts, re-encode a decoy history (another trajectory) and check that `rollout(z0)` is unchanged; or evaluate
  rollouts on a fresh `copy.deepcopy`/unpickled model that never saw the encode call.
- Extend the Markov-consistency check to rollouts WITH events.

### M2. Synthetic held-out targets include unobserved neurons. Their effects cannot be identified from x and are silently scored as "no effect"

- The generator splits intervention targets over all N neurons, not over the observed ones (`extra/generator/p3synth/suite.py:128-137`).
- On 5 of 48 dev systems, held-out test events touch unobserved neurons: 74c2, b3e6, b8da, f60f, fe86 (`.tmp/b_targets.py`).
  Held-out unobserved neurons are neither observed nor ever intervened on in training, so no method can know their couplings.
- v1 declares `supports(kind) = True` and then drops unobserved ids in `compile_events` (`ks_core.py:105-125`). It therefore
  predicts exactly zero effect with no signal. On syn-b8dafc4f01, 7 of 8 held-out pairs have unobserved targets, all 7 get
  d_pred ≡ 0, and those pairs carry 99.8 % of the C denominator.
- On syn-f60f07a27f, C over observed-target pairs is **0.074**. The unobservable pairs (72 % of the denominator) raise the reported C
  to 0.67 [0.07, 1.62], so the interventional condition fails for reasons unrelated to the state.
- The API promises abstention instead of silent "no effect" (`api.py` docstring). But `supports` is per kind, not per event, and
  the verdict fails any system with an abstained pair (`harness.py:244`). An honest per-event abstention is punished more than a
  silent zero.

The calibration (the true-latent reference also drops unobserved ids, `refmodels.py:396-405`) and the tournament S2 carry the same
contamination.

**Fix (evaluation).**
- Report C separately for pairs whose targets are all observed, and use that as the held-out-target C.
- Report unobserved-target pairs as their own descriptive family.

**Generic requirement to relay to the method developer:** events on neurons outside the observed population must be flagged
(info / per-event report), not silently dropped.

### M3. The held-out C is carried by 1-3 pairs, so the per-system interventional verdict rests on one or two trajectories

- On the dev suite, n_eff of the held-out C (primary window) is 1.17-3.72 out of 8 pairs on the 10 systems I ran. Examples:
  syn-1f16e42a17 1.17, syn-1e61c72597 1.44, syn-566e16b512 1.49.
- The percentile bootstrap over 8 (heldout suite: about 16) pairs with a ratio statistic is unreliable in exactly this regime.
  syn-566e16b512 passes with upper CI 0.99993.
- n_eff is reported (v2), but the verdict does not use it.

**Fix.**
- Require a minimum n_eff (for example ≥ 4) for "interventional" or mark it "untestable".
- Report C per family (already computed in `C_per_family`) next to the pooled ratio in every claim.

### M4. No latent-intervention (lifting) evidence exists for v1, and the lifting evaluator is gameable

- v1's `lift()` returns [] (notes section 5), so `eval_lifting` records `supported: False`. No claim about do(z := z + dz), latent
  interventions or implementation invariance can be made for the locked method. Reports must say so explicitly next to any
  "causal state" wording.
- For other models, the implementation-invariance ratio can be gamed. `eval_lifting` does not check that the "DISTINCT" lifts are
  distinct (`evaluate_lift.py:95-120`). Three identical or near-identical lifts give same-shift divergence ≈ 0, a perfect
  invariance ratio.

**Fix.** Reject lifts whose event sets are identical, or whose achieved microstate changes have cosine similarity above a threshold,
before computing the ratio.

### M5. The tau_C calibration measures the reference's event probe, not a causal state

tau_C is the 75th percentile of the true-latent reference's C. That reference's events go through a ridge probe x→z with
Wlin = the probe weights, and silencing clamps the decoded x at rest (`refmodels.py:388-414`). The generator's causal routes are
different:
- a kick on neuron j moves the latent by D[:, j]·dv_j through phi⁻¹;
- silencing removes j's contribution to c while x_j keeps decaying (`p3synth/core.py:333-338, 360-371`).

Result: the reference with the exact state fails the interventional condition on 41 of 45 systems (median C 1.58, PROTOCOL
section 6), and tau_C lands above 1 (see B1).

**Fix.** Report this as a limitation. Do not describe tau_C as "calibrated from a true causal state".

## Minor issues

- m1. v1 clips rollouts to the widened training box and replaces non-finite z by 0 (`ks_core.py:531-534`). The evaluator's
  "non-finite prediction = failure" rule can never trigger for v1; divergence becomes a bounded, confident prediction. Generic
  requirement: report clipping and non-finite events in `info()`.
- m2. When calibrated event gains are 0 (the "no effect" guard), v1 outputs d_pred ≡ 0 with `supports() = True`. For example, on
  syn-b8dafc4f01 even the observed-target pair has C = 1.000. This scores as not-interventional, which is correct. But a
  zero-gain kind should appear in `info()` as "effect not modelled" rather than as a supported kind.
- m3. In `eval_lifting`, dz is requested at t_i, but the model's lifted rollout starts from `z_twin(j) + dz` at the end of the lift.
  For current lifts (up to 150 ms on real systems), the requested shift and the tested do() refer to different times.
  - `zsd` is computed from the first case only.
  - `hasattr(model, "lift")` is always true (base class), so the check is harmless but meaningless.
- m4. The parameter-identity probe (P) is descriptive only. E blocks draw identity by pairing within draw, but A and C have no
  draw-identity control. This is acceptable because test draws are held out; mention it in the limitations.
- m5. `eval_intervention` counts only pairs that fit the longest window into the primary C. Pairs that fit only shorter windows are
  neither counted as skipped nor reported. The current event-time ranges keep this from happening: synthetic events ≤ 2.8 s + 1 s
  < 4 s, real ≤ 1.7 s + 0.25 s < 2 s. But add a count of pairs in the primary window.

## Shortcut confounders: are they blocked?

| confounder | family A / B | family C | family E | status |
|---|---|---|---|---|
| time (the encoder sees the history length) | not directly controlled; held-out init states / draws and the `time_index` trap system | cancels: both arms share z0, u and the event times | restarts under a common nominal input; futures do not depend on absolute time | largely blocked |
| input | input-only control, paired CI required in `predictive` | cancels: identical u in both arms | common future input | blocked |
| output copy | encoder never receives y (`encode_at`, `evaluate.py:82-87`); readout-history control (wins on every real public system per the v1 notes, 7.5) | n/a | whitened latent distance; output-matched pairs reported | blocked |
| parameter identity | held-out draws in test | held-out draws | pairs within the same draw only | blocked for the verdict; P probe descriptive |
| microscopic memorisation / hidden memory | **open: stateful side channel (M1)** | **open (M1); no Markov check under events** | E uses `encode` only, futures simulated by the orchestrator | partly open |
| state-independent event response | n/a | **not controlled (B1)** | n/a | open |
| unidentifiable targets | n/a | **mixed into C (M2)** | n/a | open |

## What I checked and found sound

- **Pre-event encoding.**
  - The synthetic generator records `xs[i]` before the events of step i are applied (`p3synth/core.py:325-343`).
  - Silencing masks the latent sum from step i; `cs[i]` uses `act_prev`, so y[i0] is pre-event.
  - The real engine records the pre-kick sample and applies the kick after it (`realsim.py:100-107`).
  - `eval_intervention` encodes at i0 = the first event sample and compares from i0 + 1.
- **Twins.**
  - Synthetic twins share `noise_seed`, and all random draws are event-independent in shape and order (`core.py:262-289`), so
    process, private, observation, readout and exogenous noise are common and cancel in d_true.
  - Real twins keep the event breakpoints (`realgen.counterfactual`), and the real engine is deterministic.
- **Held-out targets on synthetic systems.** Test events never touch public targets (0 of all dev test events,
  `.tmp/b_targets.py`). Held-out types (groups, combined, group silence) do not appear in training. The simulation-service policy
  forbids them.
- **v1's latent interventions are legitimate state updates.**
  - Kicks map dx to dz through the encoder's current-sample block. Currents, silencing and edge removal enter through a decoded
    microstate and a fitted microscopic coupling map (`ks_core.py:491-535`).
  - There is no memory beyond z, and the encoder is pure (no cache) and causal.
  - y is used only as a regression target at fit time.
  - Event gains are chosen on training event trajectories only; the simulator is not used.
- Structural interventions (edge removal) are correctly kept out of the verdict, and v1's C_structural is reported separately.
- The C windows fit inside the trajectories for every pre-registered event-time range, so no pair is silently excluded in
  practice.
- Lifting uses one common t_end for the base run, the lifts and the twin (the v2 fix of H M6), as implemented.
