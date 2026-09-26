# Post-lock review C (claims: computational neuroscience and causal inference)

Reviewer: C (post-lock, goal4 section 70). Scope: reporting, statistics and claims of `PHASE3_REPORT.md` (draft). Nothing here proposes
a change to the locked method. I re-derived every number cited below from the result files with `uv run --no-sync python`
(scratch scripts in `.tmp/`). Draft line numbers refer to the room copy of `PHASE3_REPORT.md`.

Main files used:
- `results/level_c/01/level_c_results.json` (LC);
- `results/tournament/final_b/brainir_state_v1.json` (FB);
- `results/SELF_AUDIT.json` and `scripts/self_audit.py`;
- `results/review_g/results_locked_v3.json`;
- `results/counterexamples/*/SUMMARY.json`;
- `docs/PROTOCOL.md` (P) and `docs/goal4.md`.

## Summary verdict

**Not acceptable as written: 3 blockers and 11 major issues.** Both headline conclusions have the right direction:
- NOT SUPPORTED for the connectome-constrained rate-model simulations;
- partially supported on the synthetic FINAL suite.

Several statements that support them are false or overstated, and important negative evidence is missing from the places where a
reader will look for it.

1. **PCA claim.** "A PCA latent of the same dimension predicts even better, on 9 of 10 systems" (summary, sections 21 and 23) is an
   artefact of a horizon mismatch in self-audit Q16. At the pre-registered primary horizon (250 ms), PCA-k is better on only 3 of
   10 systems, all on net2. On net1 full and net3 full the locked method is better than PCA-k.
2. **Real held-out C.** On all three real full networks the locked method abstained on every kick and current pair, held out and
   in-distribution alike (60 of 120 held-out pairs per network). The reported held-out C (1.27, 0.96, 1.04) therefore covers
   silencing pairs only, and 45-49 of those 60 pairs are null. The draft does not say this anywhere. It also does not report that the
   method itself declared "no compact state" on net2 full and on all 7 mechanism systems.
3. **Compact verdicts.** On the FINAL suite, the "compact causal state (all verdict conditions met) on 19 of 46" merges a category
   that the protocol says must never be merged. Two of the 19 are not state-mediated, and one of them is the nuisance trap A, where
   the method was fooled (k = 8 against 1, latent recovery 0.12).
4. **Missing scope statements required by the protocol:**
   - the additive-composition scope of the Level B intervention claim;
   - "real verdicts are conditional on the synthetic calibration";
   - the kick-clip sensitivity;
   - null pairs and non-null C;
   - lineage-aware counts;
   - model assumptions next to Level C statements;
   - the lifting caveat next to causal statements.

## BLOCKERS

### B1. "PCA-k predicts better than the locked method on 9 of 10 real systems" is false at the primary horizon

- **Draft:**
  - l. 30 ("A PCA latent of the same dimension predicts even better, on 9 of 10 systems");
  - l. 991-997 ("predicts the held-out readout BETTER than the locked method on 9 of 10 systems ... adds no predictive value over PCA
    on the real circuits");
  - l. 1028.
- **Cause.** `scripts/self_audit.py` Q16 (`key = next(k for k in pa if k.startswith("A_nmse_h"))`) takes the FIRST A key of the
  PCA-k reference, which is the 10 ms horizon. It compares that with the method's verdict A, which is at the primary 250 ms horizon
  (P section 4: bold 250 ms). The Q16 values in `SELF_AUDIT.json` (net1 full 0.0183, net2 full 0.2411, net3 full 0.0042, ...) equal
  LC `systems.*.brainir_state_v1.references.pca_k.A_B.A_nmse_h10ms.mean` exactly.
- **Re-derived at 250 ms** (LC `...references.pca_k.A_B.A_nmse_h250ms.mean` against `verdict.A`):

| system | method A (250 ms) | PCA-k A (250 ms) | better |
|---|---|---|---|
| net1 full | 0.0244 | 0.0438 | method |
| net1 mech a | 0.0886 | 0.0919 | method |
| net1 mech b | 0.1249 | 1.128 | method |
| net2 full | 0.514 | 0.445 | PCA-k |
| net2 mech a | 0.229 | 0.201 | PCA-k |
| net2 mech b | 0.209 | 0.195 | PCA-k |
| net2 mech c | 0.0252 | 0.0303 | method |
| net3 full | 0.0055 | 0.0069 | method |
| net3 mech a | 0.117 | 0.731 | method |
| net3 mech b | 0.174 | 0.198 | method |

  PCA-k is better on 3 of 10 systems (one network, net2); the method is better on 7 of 10. Among the full networks, PCA-k is better
  only on net2, which is also where the method declared "no compact state" (M2). These are point estimates; no paired CI exists in LC.
  At 10 ms PCA-k is better on 9 of 10 systems, but 10 ms is not the pre-registered horizon.
- **Correction.**
  - Replace every "9 of 10" PCA statement with: "At the primary 250 ms horizon, a PCA latent of the same dimension predicts the
    held-out readout better than the locked method on 3 of 10 systems (net2 full and two net2 mechanisms; point estimates) and worse on
    7. At the shortest horizon (10 ms) PCA-k is better on 9 of 10."
  - Delete "adds no predictive value over PCA on the real circuits".
  - Disclose the Q16 key-selection defect as a self-audit artefact (the check is hashed and cannot be edited, like I3/I8/I11).

### B2. "Compact causal state (all verdict conditions met) on 19 of 46" is false, and it merges two pre-registered categories

- **Draft:** l. 19 ("compact causal state discovered on 19 of 46 compressible systems") and l. 1035 ("finds a compact causal state
  (all verdict conditions met) on 19 of 46").
- **Evidence.** FB `verdict_counts_compressible`:
  - "compact causal state discovered" = 17;
  - "compact causal state discovered (microstate equivalence untestable)" = 2.

  P section 7: the second category "is reported as its own category and never merged with the first". On those 2 systems, E is
  untestable, so "all verdict conditions met" is false for them.
- **The merged count also hides a trap failure.** One of the two is syn-5501045d59, nuisance trap A (FB `per_system`):
  - k = 8 against k_true = 1;
  - latent recovery R^2(true <- model) 0.988 but R^2(model <- true) 0.116, so min R^2 = 0.12;
  - not state-mediated: C - C_scrambled CI [-0.40, 0.28].

  By the self-audit's own definition ("fooled" = a compact claim with min R^2 < 0.5, `self_audit.py` l. 514) this is a system where
  the method was fooled. No self-audit question tests trap A, and the draft never mentions it.
- **Correction.**
  - l. 19 and l. 1035: "compact causal state discovered on 17 of 46 compressible systems, plus 2 with microstate equivalence
    untestable (reported separately); partially supported on 12; not supported on 15".
  - Delete "(all verdict conditions met)" or restrict it to the 17.
  - Add the trap A result wherever traps are discussed (see M9).

### B3. "It never predicts the effects of held-out interventions better than 'no effect'" contradicts the Level C file

- **Draft:** l. 31 (executive summary, real circuits).
- **Evidence.** LC `systems["real:net3:mech:92614efe"].brainir_state_v1.verdict`:
  - `interventional = True`;
  - C = 0.385 [0.215, 0.666], leave-one-pair-out max 0.44.

  So the locked method does predict held-out (group silencing) effects better than no effect on one real system. Sections 14 and 23
  scope the negative correctly ("on no full network"); the summary does not.
- **Correction.** l. 31: "On none of the three full networks does it predict held-out intervention effects better than 'no effect'
  (held-out C 1.27, 0.96 and 1.04, upper CIs >= 1; silencing pairs only, see M1). The only interventional pass on a real system
  (net3 mechanism b, group silencing, C = 0.38 [0.21, 0.67]) is not predictive and not state-mediated: replacing the pre-intervention
  state by the mean training state gives a significantly lower error, C_scrambled = 0.35 with C - C_scrambled [0.015, 0.083]."

## MAJOR issues

### M1. The real held-out C covers silencing only, mostly null pairs; kick and current effects were never predicted

- **Draft:**
  - l. 31-32;
  - section 14 table (l. 687-698) and l. 706-708;
  - l. 1029;
  - the permitted claim at l. 1043-1046 ("held-out effect error 0.96-1.27").
- **Evidence** (LC `systems.<full>.brainir_state_v1.res.C_per_family` and `verdict`), on all three full networks:
  - H_kick_B, H_pulse_B, H_kick_A and H_pulse_A: 30 of 30 pairs abstained on (`n_abstained_unsupported`);
  - `C_abstained_pairs` = 60 of the 120 held-out pairs. `interventional_reason` includes "pairs abstained on".
  - The held-out C is therefore computed on H_silence1_B + H_group_silence only.
  - Null pairs among those 60 (P section 3.1: < 0.1 % of the effect denominator):
    - net1: 45 (n_eff 4.1);
    - net2: 49 (n_eff 1.44, the largest pair carries 83 % of the denominator);
    - net3: 47 (n_eff 3.9).
  - C over the non-null pairs (`C_nonnull`, required by P section 3.1 and section 4 C): 1.20, 0.955 and 1.02.
  - The in-distribution C is silence1_A only.
- **Consequence for the comparisons.** The paired C comparisons against the comparator (primary family) are computed on the common
  silencing pairs. There the comparator's C is 1.10 on net1 and 12.5 on net3 (`ratio_b`), against its all-pairs 1.50 and 1.34.
- **Correction.** Add to the section 14 table: pairs scored / abstained, null pairs, non-null C and n_eff. Word the finding as:
  "On the three full networks the locked method abstained on every kick and current intervention (held out and in-distribution); it
  predicted only silencing, where its held-out C is 1.27 / 0.96 / 1.04 (non-null pairs 1.20 / 0.95 / 1.02; 45-49 of 60 pairs null,
  n_eff 1.4-4.1). Held-out effects of kicks and currents on the real systems are therefore untested for v1." Carry this into the
  summary and into the section 23 permitted claim ("held-out SILENCING effect error 0.96-1.27; kick and current effects abstained
  on").

### M2. The method's own abstentions on the real systems are not reported, and one is overridden by a claim

- **Draft:** l. 28, l. 703 ("Supported: a compact predictive state for the three full networks") and l. 1026-1027.
- **Evidence.** LC `verdict.abstention.no_compact_state = True` on:
  - net2 full ("latent explains too little beyond the input (val 0.480 > 0.5 x input floor 0.843)");
  - all 7 mechanism systems.

  P section 7: "A method's own abstention is recorded as such and is never converted into a verdict it did not claim." The draft
  never uses the word "abstain" for Level C, except "n/a (abstained on events)" in one row.
- **Correction.**
  - Add an "own abstention" column to the section 14 table.
  - Qualify l. 703 and l. 1026: "a 2-3 dimensional state predicted the held-out readout better than input-only and persistence on
    all three full networks; on net2 full the locked method itself declared that no compact state exists (its latent explains too
    little beyond the input)".

### M3. Level C statements are not placed next to the model's assumptions; "real circuits" and the title overstate

- **Draft:**
  - title (l. 1: "Cross-Brain Dynamical Abstraction");
  - l. 9 and l. 1019 ("real connectome-constrained circuits");
  - headings l. 27, l. 702 and l. 1025 ("Real circuits");
  - l. 997 ("on the real circuits");
  - acceptance row 50 (l. 792).
- **Required by the protocol.** P section 1 (l. 37-39): "Every Level C statement ... is reported next to the model's assumptions."
  The assumptions are:
  - first-order threshold-linear-tanh rate ODE;
  - assumed per-trajectory neuron parameters (time constants, gains, thresholds, maximal rates), never anatomy;
  - no synaptic or adaptation dynamics, no spiking, no noise (deterministic engine);
  - absolute-Hz kicks clipped at 0 Hz (r = max(0, r + d)).

  The draft states them only in limitation 1 (l. 849-851) and, for the clipping, in l. 797. The summary, section 14 and section 23
  carry none of them.
- **Cross-brain claim.** "Cross-Brain Dynamical Abstraction" in the title asserts something the evidence rejects: no cross-connectome
  sharing, and no formal abstraction (l. 1050).
- **Correction.**
  - Title: "Causal State-Variable Discovery: synthetic benchmark and connectome-constrained rate-model simulations".
  - Replace "real circuits" by "connectome-constrained rate-model simulations ('real' systems)" in l. 9, 27, 702, 792, 997, 1019
    and 1025.
  - Add one sentence under the l. 27 heading and at the start of section 14: "Simulations of a deterministic first-order rate model
    on connectome-derived weights with assumed neuron parameters drawn per trajectory, no noise, and kicks as absolute rate offsets
    clipped at 0 Hz; not recordings, and not statements about the animal."
- **Checked and correct.** I found no "noise realisation" wording for the real systems and no biological claim; l. 1048-1049
  correctly disclaim them.

### M4. Lineage: counts over the 10 real systems treat one reconstruction and overlapping mechanisms as independent

- **Draft:**
  - l. 28 and l. 1027 ("all three / each of the three full networks");
  - l. 30, 33, 36 and 1028-1032 ("9 of 10", "2 of 10");
  - l. 709 ("Microstate equivalence holds on 8 of 10");
  - the section 14 table, which has no lineage column.
- **Evidence.**
  - LC `lineage_rules`: "Counts of systems with a property are reported per reconstruction and per mechanism family."
  - P section 2.1: lineage is "reported in every Level C row"; mechanisms of one network "count as ONE mechanism family".
- **Correction.**
  - Add a lineage column (reconstruction R1 = net1 / net3, R2 = net2; mechanism families net1:mechfam:ebed812d (2),
    net2:mechfam:b9c9d652 (3), net3:mechfam:ee5f4064 (2)).
  - Restate the counts per reconstruction and per family. Example: "predictive on the full systems of both independent
    reconstructions (net2; net1 and net3 are two builds of one); the same k across seeds on 2 of 10 systems, both of reconstruction
    R1 (net3 full and one net3 mechanism)."

### M5. Causal wording: no state-mediation or lifting caveat next to the causal statements

- **Draft:**
  - l. 19 and l. 1035 ("compact causal state discovered / finds a compact causal state");
  - l. 498-501;
  - l. 708 ("clear interventional pass");
  - l. 1043-1046.
- **Evidence on state mediation** (FB, `state_mediated` = CI of C - C_scrambled below 0, P section 7).
  - Of the 19 compact verdicts, 17 are state-mediated. Two are not:
    - syn-b09f780157, the stimulus-copy trap D (diff CI [-0.66, 0.003]);
    - syn-5501045d59, the nuisance trap A (B2).
  - On all three real full networks `state_mediated = False`, with C = C_scrambled to 3 decimals (net2: 0.956 against 0.954).
  - On net3 mechanism b, C_scrambled is significantly LOWER than C (B3).
- **Evidence on lifting.** No lifting evidence exists for v1 (`lift.supported = False` in every FB and LC row). The draft says so
  only in sections 13, 15 (row 26) and 19.
- **Correction.**
  - Wherever "causal state" or "interventional" is asserted for v1 (l. 19, 498, 1035), append: "(interventional = held-out effects
    of observed-neuron interventions predicted better than no effect; state-mediated on 17 of these 19; latent interventions (do(z))
    untested: v1 does not implement lifting)".
  - In section 14 add a "state-mediated" column: no on every real system where C is defined.
  - In section 23 "Not claimed" add: "that interventions act through the learned state on the real systems (C equals C_scrambled on
    every full network), and any latent-intervention (do(z)) claim for v1".

### M6. The Level B intervention claim is not scoped to additive population-code compositions

- **Draft:** sections 4 (l. 173-178), 8 (l. 490-501) and 23 (l. 1034-1040), and the summary l. 18-24. None contains the required
  scope. `grep additive` finds nothing.
- **Evidence.** P section 2.2 (l. 102-106), review D M2: synthetic held-out group interventions are additive compositions of
  single-neuron operators through a low-rank population signal. Level B claims about held-out intervention types "are therefore
  scoped to 'held-out targets and additive group compositions of single-neuron interventions in population-code systems'; they are
  not evidence of type generalisation in circuits with thresholds and rectification."
- **Correction.** Add this sentence to section 8 and to the synthetic bullet of section 23 and the summary: "Synthetic held-out
  intervention types are additive compositions of single-neuron interventions in population-code systems; the Level B interventional
  results are scoped to held-out targets and such compositions, not to type generalisation in thresholded circuits (on the rate-model
  systems, with rectification, no interventional claim holds)."

### M7. Missing pre-registered items: the kick-clip sensitivity, and "real verdicts are conditional"

- **Kick-clip sensitivity.** P section 2.2 pre-registers "the held-out C without [kick-clip pairs] ... as a sensitivity analysis". It
  is not in the draft (`grep kick-clip` finds nothing).
  - Re-derived (FB `verdict.C_sensitivity.kick_clip`): 22 of 46 compressible systems have excluded pairs (1-9 each).
  - S2 = median held-out C is 0.483 with all pairs and 0.456 without kick-clip pairs. The conclusions do not change.
  - Add one line to section 8.
- **Conditional real verdicts.** P section 6 (l. 325-328): the real systems differ from the calibration (dt, draws, absolute kicks,
  non-additive operators, pooled normaliser), so "Real verdicts are therefore CONDITIONAL on the synthetic calibration, and the
  report says so." `grep conditional` finds nothing.
  - Add to section 14: "The tolerances were calibrated on synthetic DEV systems; the real verdicts are conditional on that
    calibration (PROTOCOL section 6)."

### M8. Sharing and cross-connectome results are worded as properties of the circuits, not of the method

- **Draft:** l. 35 ("No shared dynamics across mechanisms or across independently reconstructed connectomes") and l. 1030.
- **Evidence.**
  - LC `I` and `J`: every "shared" model returned by v1 equals the independent models. The parameter totals are identical (net1+net2
    5,064 = 5,064), and all A and C differences are exactly 0, because the method's internal test declined to share.
  - Model 4 (partial sharing) is `null` (not implemented).
  - The independent-reconstruction test is one pair (net1 + net2) with ONE transfer direction (held net1 only; A +4.92
    [4.80, 5.04], C +251).
  - Within one reconstruction (net1 + net3), adaptation beats a fit from scratch in BOTH directions:
    - held net1: C -0.17 [-0.62, -0.008], A tied;
    - held net3: A -0.178 [-0.345, -0.054].

    The draft reports only the first ("ties on A").
- **Correction.**
  - l. 35 and l. 1030: "The locked method found no support for shared latent dynamics: its internal test declined to share, partial
    sharing is not implemented, and adapting net1's dynamics to net2 (one pair, one direction) was far worse than a fit from scratch.
    This is a result about v1, not evidence that the simulated circuits lack shared dynamics."
  - l. 727: report both net1 + net3 directions (descriptive, one reconstruction).

### M9. Traps where the method was fooled are missing from the summary and the conclusion

- **Draft.** The summary (l. 7-45) and section 23 do not mention traps. Review G is in section 18 and trap H in section 21 only.
- **Evidence (FINAL, FB):**
  - trap A (nuisance): compact claim (E untestable), k 8 against 1, min R^2 0.12 (B2);
  - trap H (parameter): compact claim, k 2 against 1, min R^2 0.60 (self-audit Q13 fail);
  - trap J (transient): compact claim, k 3 against 2;
  - trap D (stimulus copy): compact claim that is not state-mediated.
- **Evidence (review G, locked method, `results_locked_v3.json`):**
  - k wrong on 5 of 9 compressible traps (G1 2/4, G2 8/3, G4 4/9, G7 1/3, G9 4/2);
  - no abstention on the non-compressible G10, rated "partially supported" with k = 1.
- **Also missing from the summary:** abstention recall is only 1 of 2 on the FINAL non-compressible controls, and the confident-wrong
  rate is 0.52 (FB `abstention`).
- **Correction.** Add a summary bullet: "Traps: the locked method claims a compact causal state with the wrong k on the FINAL nuisance
  (k 8 against 1), parameter (2 against 1) and transient (3 against 2) traps. On review G's 10 unseen traps it gets k wrong on 5 of 9
  and does not abstain on the non-compressible G10. Abstention recall on the FINAL controls is 1 of 2. Verdicts certify sufficiency
  on the tested domain, not the correctness of k."

### M10. The self-audit Q8 "pass" is described as something it did not test

- **Draft:** l. 987 ("intervention fidelity not collapsing on unseen perturbation types relative to in-distribution ones (Q8)") and
  l. 1000 ("Q8 and Q19 pass on relative criteria").
- **Evidence.** `scripts/self_audit.py` q8 decides on one thing only: the fraction of synthetic FINAL systems whose held-out C upper CI
  is >= 1. That fraction is 0.41 (19 of 46), against the threshold 0.5. No held-out vs in-distribution comparison enters the decision.
  - Its "real" evidence is descriptive and read at the first window key (100 ms), not the primary 250 ms window. For example, net1
    mechanism b is [0.12, 0.40] at 100 ms against the verdict's [0.36, 2.69].
  - Applied to the real full networks, the Q8 criterion would fail (3 of 3 with upper CI >= 1).
- **Correction.** l. 987: "Q8 passes because held-out C is no better than no effect on 19 of 46 synthetic FINAL systems (41 %,
  threshold 50 %). It is not a held-out vs in-distribution test, and on the real full networks held-out C is no better than no effect
  on 3 of 3." Disclose that its real evidence uses the 100 ms window.

### M11. The conclusion's basis and scope are not stated

- **Draft:** l. 9-10, l. 792 and l. 1017-1019.
- **Evidence.** P section 7 pre-registers per-system verdicts only. Neither P nor goal4 section 85 gives a suite-level aggregation
  rule, so the two headline labels are the authors' reading of per-system counts.
  - The real label is well supported:
    - 9 of 10 "not supported";
    - the one partial verdict (net3 full) fails the interventional condition;
    - no interventional pass on any full network.
  - The synthetic label rests on:
    - 17 + 2 compact, 12 partial, 15 not supported;
    - 3rd of 9 against the baselines;
    - intervention evidence scoped by M6.
- **Correction.** Add after l. 1019: "PROTOCOL section 7 defines verdicts per system; no suite-level rule was pre-registered. The labels
  summarise the per-system counts: [counts]. The synthetic label is scoped to the FINAL population-code suite and to additive held-out
  interventions (M6)."
- **Also: the one positive real verdict is fragile.** net3 full's "partially supported" comes from a model whose half-sample refits
  do not reproduce its latent: G_resample r2_min_mean = -1.16, and the seed median min R^2 is 0.69. net3 is the same reconstruction as
  net1, where the verdict is "not supported". Say so next to l. 1032-1033.

## Minor issues

1. **l. 698 and l. 708:** net3 mechanism b C = 0.3846 rounds to 0.38, not 0.39.
2. **Mechanism rows, section 14 table (Q3 of the task):**
   - Label the held-out C column for the 7 mechanism rows "group silencing only (the only held-out type on mechanisms;
     H_kick_B / H_pulse_B / H_silence1_B are in-distribution there, P section 7)". Section 4.2 (l. 269-270) says this, but the table
     where the numbers appear does not.
   - Replace "n/a" by "abstained (group silencing)" for net2 mechanisms a and c and net3 mechanism a.
   - Give CIs for the mechanism C values: net1 b 0.91 [0.36, 2.69]; net2 b 0.79 [0.74, 1.13]; net3 b 0.38 [0.21, 0.67].
3. **l. 709, "Microstate equivalence holds on 8 of 10 systems":** 6 of the 8 are mechanism systems where k >= N_observed (for example
   net2 mechanism c, k = 5 for 3 observed neurons). There the latent can carry the whole microstate and E is nearly uninformative.
   Report 1 of 3 full networks (net2) separately.
4. **l. 39 (summary counterexamples):** "5 of 10 real systems" is the public-draw sweep. Add "3 of 10 with hidden draws"
   (`real_hidden_brainir_state_v1_effect`: 3).
5. **l. 714-716 (net2 C, net3 C non-inferiority and superiority):** apply the P section 8 C reporting rule explicitly: "no worse
   than the baseline, neither better than predicting no effect". LC `primary_comparisons.*.C.claim` already carries that sentence.
   Add that the paired C uses the common silencing pairs only (M1).
6. **l. 1048:** "true state variables of the fly nervous system" names the organism. Use the neutral goal4 section 88 form ("of the
   animal's nervous system") in keeping with the anonymisation.
7. **l. 816-835:** the parameter-identity probe range "0.33-0.58" is for the full networks, and l. 977 "0.30-0.81" is for all 10
   systems. Label each so the two do not read as a contradiction.
8. **l. 1050, "formal causal abstraction (the interventional and sharing conditions fail)":** add "and no lifting / do(z) evidence
   exists for v1".
9. **Section 14:** the real C effect denominators are concentrated on few readout dimensions. For net1 full, one of 9 dimensions
   carries 83 % (`den_share_by_dim`). Report the per-dimension shares as pre-registered (P section 4, normalisers).

## What I re-derived and found correct

- **Level C verdicts** (LC `systems.*.verdict`): k, verdict, predictive, closed and microstate-equivalent for all 10 systems and both
  models match the section 14 table.
  - Full-network held-out C: 1.27 [1.03, 1.89], 0.96 [0.94, 1.02] and 1.04 [1.01, 1.20].
  - "not supported" on 9 of 10 and "partially supported" on net3 full.
  - Closure on 3 systems (net3 full, net2 mechanism c, net3 mechanism b); microstate equivalence on 8.
  - Markov checks pass everywhere.
- **Predictive differences:**
  - net3 full A - input-only -0.0067 [-0.0077, -0.0056];
  - net2 full -0.30 [-0.58, -0.11].
- **Primary family** (Holm, LC `primary_holm`):
  - non-inferior on net2 C, D and E and on net3 A and C (5 of 13);
  - secondary: better on net3 A and C, worse on net1 E, net2 A and net3 E;
  - K diff 0.0065 [-0.040, 0.054], Holm p 0.30;
  - comparator k 16 / 64 / 64.
- **G on the real systems:**
  - same k across seeds on 2 of 10;
  - full-network median min R^2 over seed pairs 0.99, 0.99 and 0.69;
  - mechanisms k 2-8;
  - data arm: same k on 4 of 10, r2_min_mean from -1.16 to 0.93.
- **Sharing:**
  - I: rejected on net1 and net3, untestable on net2;
  - J: both pairs rejected;
  - net1 + net2 transfer A +4.9, C +251.
- **Robustness at 100 ms:**
  - the section 17 table values;
  - out-of-distribution stimulus 75.8-fold (method, net1) against 25.7-fold (comparator);
  - probe accuracies.
- **FINAL suite (FB):**
  - S1-S8 profile of the locked method;
  - conditions predictive 32, interventional 24, closed 36, microstate-equivalent 34 (E testable 40), state-mediated 27;
  - k exact 27, under 3, over 16;
  - abstention recall 0.5, false alarms 1 of 46, confident-wrong 0.52;
  - fits 4 of 108 failed.
- **Counterexample sweeps** (all seven SUMMARY.json files) match the tables in sections 9 and 16, including Q19's 0.17 over 116
  system-runs.
- **Review G on the locked method:** k wrong on 5 of 9, G10 "partially supported" with k = 1, comparator k right on 3 of 9.
- **Claim hygiene:**
  - no "noise realisation" wording for the real systems;
  - no biological claim;
  - net1 and net3 are never counted as two confirmations in the J section;
  - real I is labelled descriptive.
- **Limitations.** Limitation 1 states the model assumptions correctly; the problem is only where they are placed (M3).
