# EXPLORATORY post-mortem of exam 1 (ledger run 2)

**EXPLORATORY: written after the unblinding, not pre-registered.** It explains exam 1 and changes nothing: the verdict
stands (A1 AUROC 0.577, 0.417-0.724, 39 types, 25 yes / 14 no; the model does not predict front-leg rhythm and adds
no value beyond wiring).

`ledger/scripts/posthoc/postmortem_1.py` prints every number below. It checks its 104 inputs against the exam-1 locks and
re-runs P, S-a, S-b and S-c with the frozen scoring code; all four reproduce `results/run2/*.json` exactly. Subsets use
the frozen `evaluate` and label consensus.

Counts are n (yes/no). Intervals are stratified bootstraps (10,000 draws, frozen seeds). **(u)** marks a row underpowered
under the pre-registered rule (fewer than 20 types, or fewer than 5 in a class); no direction is claimed for it.

## 1. EXPLORATORY: the full secondary tables

RESULTS_1's secondary rows, baselines and locked arms (all descriptive); A1's primary set and run S-b unless marked.
RESULTS_1 omitted the baseline intervals. B1-lo10 and B1-lo5 equal B1 and B1-alt.

| analysis | n (yes/no) | AUROC | 95 % interval |
|---|---|---|---|
| A1, primary set (P) | 39 (25/14) | 0.577 | 0.417-0.724 |
| A1, exposed included | 50 (28/22) | 0.510 | 0.363-0.656 |
| A1, exposed only | 11 (3/8) | 0.583 (u) | 0.125-1.000 |
| A1, never-usable excluded | 37 (23/14) | 0.596 | 0.432-0.745 |
| A1, intact only | 38 (26/12) | 0.598 | 0.429-0.750 |
| A1, headless only | 3 (0/3) | n/a | n/a |
| A1, systematic sources only | 32 (25/7) | 0.623 | 0.411-0.800 |
| A1, clean lines only | 13 (1/12) | 0.375 (u) | 0.250-0.500 |
| A1, non-specific lines | 34 (29/5) | 0.593 | 0.400-0.741 |
| A1, labels v1.1 (S-a) | 12 (1/11) | 0.909 (u) | 0.727-1.000 |
| A0 type max / mean | 39 (25/14) | 0.577 / 0.560 | 0.399-0.743 / 0.380-0.729 |
| B0 type max / mean | 39 (25/14) | 0.609 / 0.597 | 0.441-0.761 / 0.429-0.751 |
| B1 (= B1-lo10) | 39 (25/14) | 0.511 | 0.346-0.667 |
| B1-alt (= B1-lo5) | 39 (25/14) | 0.496 | 0.334-0.649 |
| A1-lo10 | 39 (25/14) | 0.577 | 0.417-0.724 |
| B2 (MaleCNS) | 39 (25/14) | 0.503 | 0.354-0.636 |
| B5 (max over strengths) | 39 (25/14) | 0.391 | 0.217-0.574 |
| B1r (S-c) | 39 (25/14) | 0.454 | 0.271-0.636 |
| B2r (S-c) | 37 (23/14) | 0.419 | 0.252-0.585 |
| S1_direct_mn | 39 (25/14) | 0.310 | 0.156-0.470 |
| S2_twohop_signed | 39 (25/14) | 0.669 | 0.443-0.871 |
| S3_twohop_abs | 39 (25/14) | 0.091 | 0.017-0.197 |
| S4_total_out | 39 (25/14) | 0.114 | 0.011-0.240 |
| S5_out_partners | 39 (25/14) | 0.093 | 0.013-0.203 |
| S6_premotor | 39 (25/14) | 0.103 | 0.006-0.223 |
| S7_n_members | 39 (25/14) | 0.634 | 0.511-0.754 |
| S8_informed (informed) | 39 (25/14) | 0.309 | 0.160-0.456 |
| ten controls | 39 (25/14) | mean 0.495 | range 0.304-0.609 |

- **Paired** (39 types): A1 minus S2 -0.091 (-0.320 to 0.150); minus S8_informed 0.269 (0.057 to 0.473).
- **Controls:** classshuffle-201 to -205: 0.580, 0.304, 0.566, 0.409, 0.417. Rewire-101 to -105: 0.554, 0.609, 0.497,
  0.513, 0.501.
- **B5 by strength:** I = 32 0.559, 64 0.523, 128 0.380, 256 0.414, 512 0.477.
- **Arm agreement** (Spearman, no labels): A1-B1 0.792 over 321 types. B2-B1 0.311, bands differing for 100 of 310.
  B1r-B2r 0.366 over 310, top-10 overlap 1, band agreement 0.632.
- **Stop calls** (types, agreement, kappa): B4 v1 52, 0.635, -0.038. B4 v2 excluding saturates and rhythm_lost_other
  35, 0.943, -0.029; counting them as non-halts 52, 0.962, -0.020.
- **Walking-modulation kappa:** B4 v1 -0.046 (43 types), B4 v2 0.000 (27). **Frequency:** n = 0.

Among baselines only S7's interval lies wholly above 0.5; S1, S3-S6 and S8 lie wholly below (Section 4).

## 2. EXPLORATORY: why so many zeros

| A1 score (primary set) | types (yes/no) | active neurons per usable replicate: median of type medians (range) |
|---|---|---|
| above 0 | 14 (10/4) | 157.25 (16-1133.5) |
| 0, never usable | 2 (2/0) | no usable replicate (2-3 active) |
| 0, usable | 23 (13/10) | 16.5 (7-132.5); at most 25 in 17 (11/6) |

- **Read-out.** A1's replicates count active neurons only network-wide. B1, the replication, also records active
  front-leg motor neurons (MNs; 144, against A1's 138). For the 23 usable-zero types:
  - never usable: 1 (1/0), DNp20 (A1-usable at 7 active neurons in all 16 replicates);
  - read-out silent in every usable replicate: 14 (7/7);
  - read-out active but not rhythmic (score at most 0.0024): 8 (5/3).
- **Reachability arms**, on the 25 A1-zero types:
  - B1r (tuner v2, at least 1 active front-leg MN) never accepts a run for 8 (8/0): DNa08, DNa10, DNg04, DNg14, DNg82,
    DNp16, DNp20, DNp29. It scores 8 (3/5) at 0 and 9 (4/5) above 0.
  - B5 (fixed currents 32-512) is 0 at all five currents for 11 (9/2).
- **Ties:** 0.5771 = (100 + 75 + 27) / 350 pairs. 10 non-zero yes beat 10 zero no (100); 15 zero yes lose to 4
  non-zero no (60); 150 zero-zero ties count half (75); 27 of 40 non-zero pairs won. The 14 non-zero types alone give
  0.675 (u) (0.275-1.000), 10/4.

**What the screen can test.** B1's tuner accepts the first current giving 10 to 1,500 active neurons network-wide, at
most 200 above 100 Hz; A1's run used the same bounds and counts 5 to 1,500 as usable (PREREG v1 3.1, 3.4). Neither
rule looks at the front-leg MNs, and for 17 of the 23 usable-zero types the accepted runs had a median of at most 25
active neurons, near that floor.

An A1 zero thus mostly records that activity at the accepted operating point did not reach, or did not oscillate in, the
read-out, not that the type cannot evoke rhythm. The screen grades only the 14 of 39 types with a non-zero
score; the other 25 enter through the tie rule.

The zeros explain the ties, not the verdict: B1r still leaves 17 (12/5) at 0 and scores 0.454; B5 0.391.

## 3. EXPLORATORY: the source confound

Atlas: Cande et al. 2018 (10.7554/elife.34275). Rows recompute the labels v2 consensus under record filters (row 2
filters types). Last column: types with A1 > 0.

| analysis | n (yes/no) | AUROC | 95 % interval | A1 > 0 (yes/no) |
|---|---|---|---|---|
| primary set, all records | 39 (25/14) | 0.577 | 0.417-0.724 | 10/4 |
| types not labelled from the atlas alone | 18 (4/14) | 0.357 (u) | 0.250-0.464 | 0/4 |
| atlas records removed | 17 (2/15) | 0.367 (u) | 0.267-0.467 | 0/4 |
| atlas records only | 31 (30/1) | 0.700 (u) | 0.617-0.783 | 12/0 |
| other systematic screens only | 6 (0/6) | n/a | n/a | 0/1 |
| headless records only | 3 (0/3) | n/a | n/a | 0/1 |
| intact records only | 38 (26/12) | 0.598 | 0.429-0.750 | 11/3 |
| atlas removed, exposed included | 28 (5/23) | 0.526 | 0.261-0.822 | 2/10 |
| headless only, exposed included | 11 (2/9) | 0.528 (u) | 0.056-1.000 | 1/6 |

- **"The atlas gave no 'no'" holds per type, not per record.** The atlas alone labels 21 (21/0) types. Its 133 eligible
  records read yes 94, unclear 33, no 3, not assessed 3; the other papers' 221 read yes 94, no 66, unclear 10, not
  assessed 51. On atlas records alone, 7 of the 14 "no" types would be yes (DNb05, DNp02, DNp03, DNp04, DNp05, DNp07,
  DNp11), DNp06 unclear and DNp10 no; 5 have no atlas record. Their "no" comes from other papers, which the frozen
  consensus ranks higher on reader confidence or line specificity.
- **Two "atlas removed" numbers.** RESULTS_1's exploratory 0.357 (4/14) filters types; removing atlas records gives
  0.367 (2/15). DNg14 drops out (its non-atlas records are not assessed), and DNg30 flips to no (its one non-atlas record,
  headless, low confidence, clean line, reads no).
- **Preparation.** Headless records label 3 types, all no (DNfl023, DNg30, DNp42); DNg30 is yes in the primary set.
  Intact records give 26/12 against 25/14: DNp42 turns yes on its intact tethered record, and DNfl023 drops out because
  its intact records conflict. The scorecard's preparation column is a type's best preparation over all records, not
  necessarily the deciding one.

A1 is above 0 for 10 of the 21 atlas-alone yes types, 0 of the 4 other-source yes types and 4 of the 14 "no" types.
Without the atlas, every remaining yes type scores 0, so the AUROC is ties plus losses to the 4 non-zero "no" types.
The narrow intervals below 0.5 in rows 2 and 3 are this artefact: an all-zero class cannot be resampled away from 0.
The only atlas-free set here passing the size rule needs the exposed types: 28 (5/23), 0.526 (0.261-0.822). With these
labels the primary AUROC cannot tell a label effect from a source effect.

## 4. EXPLORATORY: wiring

| Spearman of S2 with | S1 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|
| 39 primary-set types | -0.380 | -0.359 | -0.353 | -0.409 | -0.355 | 0.244 | -0.099 |
| all 321 types | -0.227 | -0.170 | -0.138 | -0.140 | -0.155 | 0.058 | -0.049 |

| primary set | S2 > 0 / = 0 / < 0 | median S2 | median abs(S2) | median S3 | median S4 | median S7 (members) |
|---|---|---|---|---|---|---|
| yes (25) | 9 / 1 / 15 | -361 | 2,587 | 4,301 | 501 | 2 |
| no (14) | 4 / 0 / 10 | -39,163 | 75,814 | 347,014 | 3,714 | 2 |

- **Sign carries little:** sign(S2) alone gives 0.551, and S2/S3 (magnitude divided out) 0.474.
- **Magnitude separates the classes.** The "no" types have about 80 times the yes types' unsigned two-hop sum (S3) and
  7 times their output synapses (S4), hence S3-S6 at 0.09-0.11. 10 of the 14 have net-negative sums, so their large
  magnitude becomes a very negative S2, ranked near the bottom.
- **Drivers.** Each of those 10 sits below 76-100 % of the yes types (DNb05 and DNg79 below all 25). Against:
  DNp07 and DNp47 (above every yes type), DNp42 and DNp05 (above 88 %), and the yes types DNg15 and DNb06 (below
  86 % of "no" types). Leave-one-out AUROC: 0.643 (drop DNb05 or DNg79) to 0.720 (drop DNp07 or DNp47).
- **Magnitude follows source as well as label.** Median S3: 3,545 (21 atlas-alone yes), 18,321 (4 other-source yes),
  347,014 (14 "no"). With the label fixed (yes types only), S3 gives 0.631 (u) for 4 other-source against 21
  atlas-alone. With the source fixed (the 18 other-source types, 4/14), it gives 0.089 (u). Source and label are too
  collinear to separate.
- **Type size coincides with source.** 9 of the 10 types with more than 2 members are atlas-alone yes types; the tenth,
  DNg79, is "no". Within the other-source types (4/14) S7 gives 0.464 (u). A1 correlates with S7 (Spearman 0.458) and S2
  (0.306).

This is the Section 3 confound, seen through wiring.

## 5. EXPLORATORY: no new claims

Everything here was computed after the unblinding, on subsets chosen after seeing the result. It changes no verdict,
rule, label, prediction, band or lock of exam 1 and is no basis for rescoring; rows marked (u) support no direction. No
transformed wiring feature is proposed as a predictor; these features only take S2 apart. The post-mortem explains why
exam 1 came out as it did (ties at zero, labels whose class follows their source, a wiring baseline following the same
source) and says nothing about the fly. Testing any idea raised here needs new labels or arms, pre-registered and locked
before scoring.
