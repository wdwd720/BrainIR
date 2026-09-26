# Post-lock review S (statistics) of PHASE3_REPORT.md (draft)

Reviewer S, goal4 section 70. Scope: reporting, statistics and claims only. Nothing here proposes a change to the locked method.
Every number below was re-derived from the result files in this room. The scripts are in `.tmp/postlock_S/`:
- `rerun.py`: the 13 primary and 13 secondary tests, plus both Holm families;
- `final.py` and `frank.py`: FINAL-suite verdicts, K test, G and rankings;
- `verd.py`, `cfam.py` and `pca.py`: Level C verdicts, C by family and the PCA-k comparison.

The results file is `results/level_c/01/level_c_results.json`, written LC below. The FINAL-suite files are `results/tournament/final_b/*.json`.

## Summary verdict

**NOT ACCEPTABLE AS DRAFTED: 4 blockers, 8 major issues.**

The pre-registered machinery was executed as registered, and I reproduced every stored number of the confirmatory family exactly:
- units, percentile bootstrap with B = 2000, paired designs, one-sided non-inferiority p-values and margins;
- Holm over all 13 tests (all 13 were computable, so none needed the p = 1 rule);
- the secondary superiority family.

The draft's summary of that family is also correct: non-inferior on 5 of 13; significantly better on 2; significantly worse on 3.

The problems lie in claims made outside the confirmatory family:
1. The headline "a PCA latent of the same dimension predicts even better, on 9 of 10 systems" is false. It comes from a horizon mismatch in the self-audit script (PCA-k at 10 ms against the method at 250 ms). At the matched primary horizon the method is significantly better than PCA-k on 6 of 10 systems. PCA-k is significantly better on 2, both on net2.
2. The draft merges the verdict category "compact causal state discovered (microstate equivalence untestable)" into "compact causal state discovered". The protocol forbids this, and the conclusion then states something false ("all verdict conditions met on 19").
3. One sentence about the selection is contradicted by the leave-one-component-out file.
4. The method's own abstentions at Level C are not reported. It declared "no compact state" on 8 of 10 real systems, including net2 full, and it abstained on every kick and pulse pair. The draft nevertheless says a compact state is "supported" on net2 full.

The major issues concern:
- the pre-registered C reporting rule and the C report items;
- claims pooled across correlated real systems;
- the G headline statistics;
- a robustness table at a non-primary horizon, which softens a negative result;
- "worse" claims on the FINAL suite that the paired tests do not support;
- the missing S1-S5 ranking.

## BLOCKERS

### B1. "PCA-k predicts better on 9 of 10 real systems" is false: it compares different horizons

**Draft:**
- Summary, line 30: "A PCA latent of the same dimension predicts even better, on 9 of 10 systems";
- section 21, lines 991-997: "a PCA latent ... predicts the held-out readout BETTER ... on 9 of 10 systems: full networks: 0.018 vs 0.024, 0.24 vs 0.51, 0.004 vs 0.006 ... The locked method's compact state therefore adds no predictive value over PCA on the real circuits";
- section 23, line 1028.

**Evidence.**
- `scripts/self_audit.py:935` takes `next(k for k in pa if k.startswith("A_nmse_h"))`, which is the first key, `A_nmse_h10ms`. It compares that with `verdict["A"]`, which is the primary 250 ms A.
- The "PCA" values in SELF_AUDIT.json Q16 are exactly PCA-k's 10 ms means. For example, net1 full: `references.pca_k.A_B.A_nmse_h10ms.mean` = 0.0183.

Paired over the same hidden trajectories (`evaluate_cross.paired_diff`; per-trajectory `_units`; method minus PCA-k; 95 % CI):

| system | 250 ms (primary): method / PCA-k, diff [CI] | 10 ms: diff [CI] |
|---|---|---|
| net1 full | 0.0244 / 0.0438, -0.019 [-0.033, -0.011] | -0.0016 [-0.010, 0.003] |
| net1 mech a | 0.0886 / 0.0919, -0.003 [-0.022, 0.015] | +0.012 [-0.014, 0.041] |
| net1 mech b | 0.125 / 1.128, -1.00 [-1.87, -0.44] | -0.009 [-0.022, 0.007] |
| net2 full | 0.514 / 0.445, **+0.069 [+0.010, +0.123]** | -0.051 [-0.115, -0.002] |
| net2 mech a | 0.229 / 0.201, **+0.028 [+0.007, +0.053]** | -0.033 [-0.053, -0.013] |
| net2 mech b | 0.209 / 0.195, +0.014 [-0.032, 0.072] | -0.002 [-0.004, 0.001] |
| net2 mech c | 0.0252 / 0.0303, -0.005 [-0.008, -0.003] | -0.028 [-0.036, -0.021] |
| net3 full | 0.0055 / 0.0069, -0.0013 [-0.0019, -0.0009] | -0.0003 [-0.0007, 0.0001] |
| net3 mech a | 0.117 / 0.731, -0.61 [-1.17, -0.31] | -0.036 [-0.055, -0.024] |
| net3 mech b | 0.174 / 0.198, -0.023 [-0.031, -0.016] | -0.012 [-0.033, 0.006] |

At neither horizon is PCA-k better on 9 of 10 systems.

**Correction.** Replace the three passages with:

> "At the primary 250 ms horizon, a PCA latent of the same dimension predicts the held-out readout significantly better than the locked method on 2 of 10 systems. Both are on net2: net2 full (+0.069 [0.010, 0.123]) and net2 mechanism a. The locked method is significantly better on 6 of 10 systems, including net1 full and net3 full. There is no clear difference on 2. These are per-system descriptive comparisons with unadjusted CIs."

Also:
- Delete "adds no predictive value over PCA on the real circuits".
- Disclose Q16's real-system part as a defect of the check, as the draft does for I3, I8 and I11. The check is hash-locked, so disclose it rather than edit it.

### B2. The E-untestable category is merged into "compact causal state discovered", and section 23 then states something false

**Draft:**
- line 19: "compact causal state discovered on 19 of 46";
- line 498: "on 19 (2 with microstate equivalence untestable)";
- line 1035: "finds a compact causal state (**all verdict conditions met**) on 19 of 46";
- section 10.1: "compact verdicts fall from 19 to 10" and "from 19 to 15".

**Evidence.**
- `final_b/brainir_state_v1.json` `verdict_counts_compressible`: compact 17; compact (E untestable) 2 (syn-5501045d59, syn-fe069050cb); partially supported 12; not supported 15.
- PROTOCOL.md section 7: the E-untestable category "is reported as its own category and never merged with the first".
- On the 2 systems, E was untestable ("matched pairs not close", median distance ratios 0.468 and 0.255). So not all conditions were met.

**Correction.**
- Section 23: "compact causal state discovered (all conditions met) on 17 of 46; the same with microstate equivalence untestable on 2 of 46".
- Summary, section 8 and section 10.1: use the same split. In section 10.1: event_calibration 17+2 → 9+1; delays 17+2 → 13+2.
- Section 4.2 does the same for the true-latent calibration reference ("3 of 45 (one with E untestable)"): write 2 + 1.

### B3. "Its advantage rests on S2 and S6, not on prediction" is contradicted by the leave-one-component-out ranking

**Draft**, section 6, line 425.

**Evidence.** `r3v3/ROUND_DECISION.json` `descriptive.leave_one_component_out`:
- without S1 (prediction): brainir_state_v1 falls to 4th (mean rank 5.43; lin_falds 4.86). This is the largest drop of any component;
- without S2: 2nd, tied with lin_dmdc_t at mean rank 5.571 and placed by the tie-break;
- without S6: 3rd.

**Correction:**

> "Its first place depends on prediction (S1), held-out intervention fidelity (S2) and exact dimension (S6). Without S1 it falls to 4th; without S2 it ties for 1st and is placed 2nd; without S6 it is 3rd."

### B4. A compact state is claimed on net2 full, where the method itself declared "no compact state"

**Draft:**
- section 14, line 703: "**Supported:** a compact predictive state for the three full networks";
- Summary, line 28;
- section 23, lines 1026-1027 and the "Permitted" claim, lines 1043-1046.

**Evidence.**
- `LC systems["real:net2:full"].brainir_state_v1.verdict.abstention` = {no_compact_state: True, reason: "latent explains too little beyond the input (val 0.480 > 0.5 x input floor 0.843)"}; declared_failure = True.
- PROTOCOL.md section 7: a model that declares no_compact_state "cannot receive a 'compact causal state' verdict there", and "a method's own abstention is recorded as such and is never converted into a verdict it did not claim".

**Correction.**
- Section 14: "The predictive condition holds on all three full networks (paired CIs below 0 against input-only and persistence). On net2 full the method itself declared no compact state, so a compact predictive state is supported only on net1 full and net3 full, which are two builds of ONE reconstruction."
- Add the same qualifier to the Summary and to the section 23 claim.

## MAJOR issues

### M1. Level C abstentions are not reported, and the held-out C covers silencing only

**Evidence** (LC `res.C_per_family`, `verdict.abstention`):
- On all three full networks the method abstained on every kick and pulse pair: H_kick_B, H_pulse_B, and the in-distribution H_kick_A and H_pulse_A. That is 60 of 120 held-out pairs (`C_abstained_pairs` 60, `C_n_pairs_primary` 60).
- The reported held-out C values (1.27, 0.96, 1.04) therefore cover only H_silence1_B and H_group_silence.
- On 4 of 7 mechanisms the method abstained on all 15 held-out pairs.
- It declared no_compact_state on 8 of 10 real systems: all 7 mechanisms and net2 full.
- The comparator abstained nowhere. It declared no_compact_state on net2 full, net3 full and net3 mech a.

The draft never mentions any of this. Its only trace is "n/a (abstained on events)" on one row (grep: no other hit).

**Consequence for the primary family.**
- The paired C test uses the common units (`paired_ratio_diff_boot`, `sorted(set(a) & set(b))`), so net2 C and net3 C non-inferiority rest on the 60 silencing pairs only.
- The C margin uses the baseline's C on those pairs (net1: ratio_b 1.10 against its full C of 1.50).
- Section 17's "Failures and non-finite values count as the worst value" is therefore not true of Level C C: abstained pairs are excluded, not scored as the worst value.

**Correction.**
- Add to the section 14 table a column "method abstention / C scope", for example "no_compact_state; C on silencing pairs only (kicks and pulses abstained)".
- Summary line 31: "on held-out silencing it never predicts effects better than 'no effect'; on held-out kicks and pulses it abstains".
- Section 17: state that at Level C abstained pairs are excluded from C and from the paired comparison, which then covers only the pairs the method scored.

### M2. The pre-registered C reporting rule is not applied, and required C report items are missing

**Rule.** PROTOCOL.md section 8 (review C M4) and LC `primary_comparisons[*].C.claim`: a C non-inferiority result must be worded "no worse than the baseline, neither better than predicting no effect" when the method's own upper CI is >= 1.

**Where the rule is missed.**
- net2 C: method C 0.956 [0.938, 1.018]. Section 14, line 713, and the Summary line 34 just say "non-inferior".
- net3 C: 1.036 [1.014, 1.201]. The draft says "not from a good C", which is only partly the required wording.

**Required C items (PROTOCOL.md section 4 C) missing at Level C:**
- n_eff: net2 full **1.44**, so the net2 C non-inferiority rests on about 1.4 effective pairs;
- null pairs: 45/60, 49/60 and 47/60;
- C over non-null pairs;
- leave-one-pair-out maxima;
- the alternative normalisers;
- state dependence: C − C_scrambled includes 0 on all full networks (net1 [-0.043, 0.039]; net2 [-0.002, 0.005]; net3 [-0.004, 0.003]; `state_mediated` False).

**Correction.**
- Apply the rule's wording to both C rows and to the Summary.
- Add n_eff, null pairs, C over non-null pairs, LOO max and C − C_scrambled per full network.
- State that the effect predictions on the full networks do not depend on the encoded state.

### M3. net3 mechanism b's "clear interventional pass" is not state-mediated, and the Summary's "never" is false as worded

**Draft**, line 708: "The one mechanism with a clear interventional pass (net3 mechanism b, C = 0.39)".

**Evidence.** C 0.385 [0.215, 0.666], LOO 0.44, `interventional` True. However:
- C − C_scrambled = [+0.015, +0.083], so the prediction improves when z0 is replaced by the mean training encoding (`state_mediated` False);
- the method declared no_compact_state there;
- it is not predictive there.

Summary, line 31, says "It never predicts the effects of held-out interventions better than 'no effect'" under the heading for all 10 systems. That is false for this system.

**Correction.**
- Summary: "on no FULL network ...".
- Section 14: "one mechanism passes the interventional condition (C 0.39 [0.21, 0.67]), but its effect predictions do not depend on the encoded state (C − C_scrambled [+0.015, +0.083]); the method declared no compact state there and it is not predictive".

### M4. The FINAL-suite "worse on closure, latent recovery and abstention" is not supported by the paired tests

**Draft:** line 25; lines 492-494; lines 1037-1038.

**Evidence.**
- The pre-registered K test (paired over 46 systems): diff 0.0065 [-0.040, 0.054]; one-sided non-inferiority p 0.040 (Holm 0.30); two-sided p 0.75 (secondary Holm 1.0). There is no evidence of a difference either way.
- SELF_AUDIT.json Q15, paired medians against lin_dmdc_t:
  - S3: +0.0004 [-0.0012, 0.027];
  - S5: -0.00007 [-0.0024, 0.0010];
  - neither is significant.
- The profile-median comparison (0.031 against 0.014, 0.987 against 0.991) is unpaired and has no CI.
- S7 (0.739 against 0.859) comes from recall on 2 non-compressible controls: 1 of 2 against 2 of 2. The method's false-alarm rate is much lower (2 % against 28 %, `abstention`).

**Correction:**

> "better on prediction (paired median S1 difference -0.30 [-0.57, -0.07]) and exact k (27 against 16 of 46; paired difference 0.24 [0.09, 0.41]); no significant difference on held-out C, D, E or K (K: pre-registered non-inferiority not shown, Holm p 0.30; superiority Holm p 1.0); abstention recall 1 of 2 against 2 of 2 controls, false-alarm rate 2 % against 28 %."

### M5. Real-system counts pool correlated systems, against the lineage rule

**Evidence.** LC `lineage_rules`: "Counts of systems with a property are reported per reconstruction and per mechanism family." PROTOCOL.md section 2.1: net1 and net3 are one reconstruction; the mechanisms of one network form one family. The draft instead reports bare counts over 10 systems:
- "not supported on 9 of 10";
- "microstate equivalence holds on 8 of 10";
- "same k on 2 of 10";
- "PCA ... 9 of 10";
- "5 of 10 broken immediately";
- "all three full networks".

**Self-audit Q19** pools 116 "system-runs" (SELF_AUDIT.json Q19 `n` 116): each synthetic system appears twice (effect and post objectives) and each real system twice (public and hidden draws). The pass (0.17 < 0.5) is dominated by the synthetic post sweep. The real public-draw sweep alone is 5/10 = 0.5, which is at the fail threshold (`TH.broken_immediately_frac` 0.5, fail if >= 0.5). Q12 likewise pools 8 synthetic and 10 real systems.

**Correction.**
- Report each real count by lineage: reconstruction A (net1 + net3), reconstruction B (net2), and the mechanism families (net1: 2, net2: 3, net3: 2 overlapping variants). For example: "predictive on the full systems of both independent reconstructions (net1 and net3 are two builds of one)".
- Report Q19 per sweep and state that on real public draws the fraction equals the threshold.

### M6. G: the version-3 headline statistics are incomplete and softened; the data arm is not labelled descriptive

**Missing headline statistic.** Prediction disagreement is a version-3 headline statistic (PROTOCOL.md section 4 G) and is missing in sections 8 and 14:
- FINAL: up to 1.14 NMSE (syn-146831129f);
- real, seeds, per-system mean: net1 mech b 0.084, net3 mech a 0.17;
- real, data arm: net3 mech a **55.7**.

**Softened r2_min.** Section 14 gives pair medians "0.99, 0.99 and 0.69" and says "agree well". The stored headline `G.r2_min_mean` is 0.976, 0.966 and **0.546**, and net3 full's worst pair is 0.125. net3 full is the one "partially supported" system; its data arm gives r2_min_mean **-1.16**, the lowest of all systems. The draft reports that value only inside a range.

**Seed-0 k on net2 full.** The reported k = 3 comes from seed 0; seeds 1-4 all give k = 2 (`G.k` [3, 2, 2, 2, 2]). net2 mech c: [5, 2, 2, 2, 2].

**Data arm.** It is pre-registered as descriptive (LC `G_resample.role`), but the draft does not say so.

**Correction.**
- Report r2_min_mean, k agreement and prediction disagreement per system.
- Drop "agree well" for net3 full.
- State the modal k across seeds.
- Label the data arm "descriptive".

### M7. The robustness table uses a non-primary horizon, which softens the out-of-distribution result

**Draft:** section 17 table ("A = readout NMSE at the 100 ms horizon"); Summary, line 38 ("up to 75-fold").

**Evidence.** At the pre-registered primary 250 ms horizon (LC `res.H_ood`, `res.A_B`), net1 H_stim_ood gives:
- method 5.74 against 0.0244 in distribution: **235-fold**, with **63** windows at the NMSE cap of 10, so this is a lower bound;
- comparator 29-fold.

net2 has 19 capped windows. PROTOCOL.md section 4 A requires counts of capped windows.

**Correction.**
- Report the table at 250 ms, or give both horizons, with capped-window counts.
- Summary: "degrades prediction up to 235-fold at the primary horizon (a lower bound; 63 capped windows on net1)".

### M8. The pre-registered S1-S5 ranking is not reported

**Evidence.** PROTOCOL.md section 9: "The ranking on S1-S5 alone and the leave-one-component-out rankings are reported."
- Round 3 (`ROUND_DECISION.json descriptive.S1_S5_only`): brainir_state_v1 4.6, lin_dmdc_t 4.8, lin_subspace 5.0. That is a margin of 0.2.
- FINAL, recomputed with average ranks: lin_dmdc_t 2.5, lin_dmdc 3.3, brainir_state_v1 3.6, so the method is 3rd.
- `tournament/RERANK_V3.md` is not cited. Scoring the version-2 round-3 records under the version-3 profile rules would have selected lin_subspace (P(rank 1) 0.52 against brainir_state_v1's 0.24). That is further evidence that the selection was fragile.

The draft reports P(rank 1) = 0.519, the [1, 5] rank interval, the decision rule and the FINAL P(rank 1) = 0.25 [1, 8] correctly.

**Correction.** Add both S1-S5 rankings to sections 6 and 8. Cite RERANK_V3 as descriptive.

## Minor issues

1. **Section 10, sign error:** the `nn_dim_rule` CI reads "-0.15 [0.30, 0.02]". It should be [-0.30, -0.02] (`ablations_dev/SUMMARY.md`).
2. **Section 10.1, "the only component with a significant effect":** the ablation CIs are unadjusted (15 switches × 6 components). Write "the only component whose CI excludes 0 (unadjusted; descriptive)". Also, delays gives +0.07 [0, 0.13], whose CI touches 0.
3. **Section 14 table:**
   - add the upper CIs for the mechanisms: 0.91 [0.36, 2.69], 0.79 [0.74, 1.13], 0.39 [0.21, 0.67];
   - replace "n/a" with "abstained on all 15 held-out pairs; condition counted as not met" (harness: abstention gives False, not untestable).
4. **Section 6 tables, rounds 1 and 2:** these show version-2 scores. Label them as such.
5. **Comparator pool:**
   - section 6 says "best of the 8 eligible baselines", but the comparator pool in `ROUND_DECISION.json` includes ks_hankel and ks_hankel_t, which the same section lists as ineligible.
   - Without them, lin_dmdc_t and lin_pcadyn tie at mean rank 3.0. lin_dmdc_t wins the pre-registered tie-break on transition parameters (15 against 26), so the choice does not change.
   - The lin_dmdc / lin_dmdc_t order is set by differences of about 1e-14.
   - State the pool of 6 and the tie.
6. **net3 E margin:** 0.2 × 3.2e-6 = 6.3e-7, which is effectively zero. "Worse on net3 E" is significant, but the absolute difference (1.9e-5) is about 1000 times below tau_E. Say so.
7. **Unadjusted verdict-condition CIs:** the "Permitted" claim and section 14 cite these CIs (A − input-only). Label them as per-system verdict conditions, not results of the Holm family. They would survive Holm over 6 (max p 0.004).
8. **Limitation 7** ("poor on the real mechanisms (2 of 10 systems agree)"): k also disagrees on net1 full and net2 full. Write "k agrees across 5 seeds on 2 of 10 systems (net3 full, net3 mech b)".
9. **Section 21, Q12:** "a third of the tested systems" pools the 8 synthetic G systems with the 10 real systems. Report them separately: synthetic 4/8, real 2/10.
10. **Section 17, robustness:** the in-distribution comparator values (0.018, 0.20) are 100 ms values. At 250 ms they are 0.022 and 0.285 (see M7).

## What I re-derived and found correct

- **Primary family** (LC `primary_comparisons`, `primary_holm`):
  - all 12 real tests reproduced bit for bit from the stored `_units`: diff, 95 % CI, margin, p_noninferiority and p_two_sided;
  - A: 60 trajectories; C: 60 common pairs; D: trajectory-cluster bootstrap with 60 clusters; E: pool-trajectory clusters within draw;
  - K reproduced from the FINAL records: 0.00649 [-0.0403, 0.0545], p 0.0400;
  - Holm over the 13 tests reproduced exactly. Non-inferior after Holm: net2 C, net2 D, net2 E, net3 A and net3 C (0.0065 to 0.022). All others are >= 0.30. All 13 tests were computable.
- **Secondary family** reproduced. Significant: net2 A (worse), net3 A (better), net3 C (better), net3 E (worse), net1 E (worse). The draft's lines 712-717 and Summary line 34 are correct.
- **Protocol conformance:**
  - units: real trajectory, synthetic system instance;
  - percentile bootstrap, B = 2000, (1 + count) / (1 + B);
  - margins A 0.2×, C max(0.05, 0.2×), D 0.05, E 0.2×, K 0.05;
  - the paired designs match PROTOCOL.md section 8.
- **FINAL verdicts:** 17 + 2 / 12 / 15; conditions predictive 32, interventional 24, closed 36, microstate-equivalent 34 (E testable 40), state-mediated 27; Markov 46/46; exact k 27, under 3, over 16. The 6 E-untestable systems are neither dropped nor counted as passes; 0 interventional-untestable.
- **FINAL abstention:** recall 0.5; false alarm 0.022; confident-wrong 0.521.
- **FINAL fits and G:** failures 4/108 fits and 0/99 evaluations; G same k 4/8 and r2_min 0.69-1.00.
- **FINAL profiles, mean ranks and P(rank 1):** the section 8 table.
- **Round 3:** the table in section 6; P(rank 1) 0.519; rank interval [1, 5]; the decision rule applied as registered; leave-one-out positions (4th / 2nd / 3rd).
- **Level C verdict table** (section 14): every k, verdict and condition for both models; C values and upper CIs for the full networks; A − input-only CIs; closure on 3 systems; E on 8.
- **Sharing:** I verdicts (rejected / untestable / rejected) and J (net1+net2 transfer A +4.92, C +251; net1+net3 C -0.166 [-0.616, -0.008], A tie).
- **Parameter probe:** 0.33-0.58 against 0.96-0.98.
- **Counterexample tables** (sections 9 and 16) and the Q19 fraction 20/116 = 0.17.
- **Selection bias:** the performance claims rest on the FINAL suite and Level C. Heldout values appear only in selection context, and the non-replication is disclosed.
