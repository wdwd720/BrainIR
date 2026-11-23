# PREREG v6: a third animal (BANC), the first two animals' post hoc numbers, and a check of our MaleCNS screen

**Status.** The rulebook of run 6 (`RUN6_PROMPT.md`). Frozen by `LOCK_prereg_v6.json` and the tag `ledger-prereg-v6`, pushed and
timestamped before any BANC screen runs. Everything here is declared before the simulations it concerns (hard limit 1). Only the tests
of Part C and the fixed words of Part V are called pre-registered; everything about the first two animals' hit lists is post hoc (hard
limit 4). The exams stay closed (hard limit 5). Every existing lock and the forward ledger v2 stay as they are (hard limit 6).

**Names used here** (the paper replaces them with plain words; a name map goes in its supplement): MANC = the male nerve cord
connectome (first animal); MaleCNS = the male central nervous system connectome (second animal); BANC = the female brain-and-nerve-cord
connectome (third animal). B1r / B2r = our tuned whole-type screens of MANC / MaleCNS (16 seeds); A1 = the authors' own whole-type
screen of MANC; A0 = the authors' single-neuron screen; K = the tuned procedure's one free setting (K = 1, chosen on DNg100 in run 2).

---

## Part Q. What was seen before this freeze (disclosure)

1. **Runs 1 to 5, all of it**: every locked result (both exams unblinded; the left-right gap in the authors' screen, 0.63 of the
   ceiling; count noise reproducing MANC's left-right gap; the cross-animal agreement 0.38; the replication pattern of run 5, its
   categories and the replicated set DNg100, DNb08, DNit013; Part S's null, p = 0.11, with its two nominally positive graded
   sensitivity analyses, mean copy score p = 0.035 and mean fraction rhythmic p = 0.033; Part T; the label audit and its erratum);
   run 5's four reviews and addenda; the paper and brief drafts.
2. **The referee's unlocked tables** (`reviews_v5/referee_tests/`): at the authors' cut 0.5 the two animals' hit lists overlap at chance;
   at cuts 0.3 to 0.4 about half of the hits recur, above chance; DNg100's replication is built into our calibration of K; exam 1's
   labels are confounded with their sources; other tests listed in that review.
3. **The authors' paper on BANC**: DNg100 drives front-leg rhythm in all four of their datasets including BANC (their mean 0.984, 99.3 %
   of replicates >= 0.5); silencing E1 or E2 abolishes it in BANC (0.014, 0.035) and silencing I2 does not (0.993); their pruning
   circuits in BANC; **their single DNb08 neuron did not drive rhythm in BANC (mean 0.000)**. So nothing about DNb08 in BANC is a
   prediction here (C5).
4. **BANC itself, before this freeze** (LOG L177-L178; `ledger/src/brainir_ledger/banc.py`): the released files (pinned by SHA-256) and
   the authors' run configs and logs (Zenodo, by range requests); the table's annotations, read to build groups and type matches (allowed
   by hard limit 2): 1,313 descending neurons, 922 excitatory, 860 mapped to 309 MANC-type groups (confidence high 206, medium 103, low
   0); the three-animal set has 182 types; DNg100 and DNb08 are high-confidence in both other animals and in BANC. Whole-network facts:
   4,963 neurons, 496,041 signed connections, row signs agreeing with the transmitter rule, 139 front-leg motor neurons. **The build
   gate** (`gates_v6/BANC_GATE.json`): the authors' DNg100 alone at 400 scores 0.994 (64 of 64 seeds >= 0.5); E1 silenced 0.000, E2
   silenced 0.028, I2 silenced 0.993 (descriptive). **Not done before the freeze:** no other BANC neuron was stimulated, DNg100 was not run
   under the tuned procedure, and no wiring summary of BANC descending neurons was computed (the output-side rule of B2 is coded but
   refuses to run before the tag is on origin, `banc.require_unblind`).
5. **Planning numbers** (`gates_v6/PLANNING_v6.json`, from MANC and MaleCNS only): the full-seed Spearman of B1r and B2r on the
   three-animal set (0.37), the expected pooling gain it implies (C6), and simulated power (C4, C8).
6. **MANC's whole-type sweep** (`dx-1-run4`, rulebook v4 fix 1, 321 types x 8 seeds, run 4 on Modal at the user's instruction then) is
   stored but under no lock; run 4 packed it for a Part D/E re-score that never ran (no fix passed). It enters Part H and is locked there
   by SHA-256. Its numbers may have been looked at in run 4's dry runs; treat them as seen.
7. **FANC** (checked once): the Zenodo record lists only run archives; the authors' FANC DNb08 run used `W_20260407_dnb08.npy` (their
   803-neuron DNg100 path plus DNb08), which is in neither the repository nor the record. No FANC network with the descending neurons
   exists, so FANC is not screened.

---

## Part G. Definitions used everywhere

- **G1. Scores, bands, agreement, words.** Rulebook v4 G5-G7 unchanged (`brainir_ledger.agree`): type score = mean score over usable
  replicates (0 if none); driver >= 0.5, non-driver < 0.05; fraction rhythmic = share of all replicates scoring >= 0.5 (an unusable
  replicate counts as not rhythmic). Agreement of screens X and Y over a type set: the **cross-half agreement** rho_x = (rho(X_1, Y_2) +
  rho(X_2, Y_1)) / 2 (Spearman, average ranks; X_1 = X's type score from the first half of the seeds), the **matched ceiling** c =
  (rho(X_1, X_2) + rho(Y_1, Y_2)) / 2, the **ratio** rho_x / c, and the full-seed rho beside them; 95 % percentile intervals from
  10,000 resamples of the types (`default_rng(20261401)`). Halves: 16 seeds 0-7 / 8-15; 8 seeds 0-3 / 4-7; A1's replicates 0-7 / 8-15.
  **Words:** "at the ceiling" if the ratio is >= 0.90 and its interval's upper end >= 1.00; "a real gap" if the upper end is < 1.00;
  "inconclusive" otherwise; "not judged" if c < 0.2.
- **G2. Hit-list overlap** (rulebook v5 R2.2, at a cut z): drivers of X = types with score >= z. Over a type set of size N with n_X
  drivers of X, n_Y of Y and k in both: the **replication rate** k / n_X (and k / n_Y); the **chance expectation** n_X n_Y / N; the
  **hypergeometric p** = P(K >= k), K ~ Hypergeometric(N, n_Y, n_X); the **overlap coefficient** OC = k / min(n_X, n_Y) and its
  **within-animal reference**: cross-half OC = mean of OC(X_1, Y_2) and OC(X_2, Y_1), ceiling = mean of OC(X_1, X_2) and OC(Y_1, Y_2),
  **OC ratio** = cross-half / ceiling (undefined when a list is empty). Intervals for OC quantities: 95 % percentile intervals from
  10,000 resamples of the types (`default_rng(20261601)`, a fresh generator for each pair, type set and cut; a resample in which a
  statistic is undefined is dropped for it and the number dropped is reported). The replication rate's interval in Part C is the exact
  Clopper-Pearson 95 % interval of k out of n_X.
- **G3. Graded version** (no cut on Y): AUROC = the probability that Y's score ranks a driver of X (at cut z) above a non-driver of X
  (ties count one half), over the type set; 95 % interval from 10,000 type resamples (`default_rng(20261601)`, fresh per pair); its
  within-animal reference: the mean of AUROC(X_2 score; X_1 drivers) and AUROC(X_1 score; X_2 drivers) for each animal.
- **G4. Screens** (per-type tables; type = a MANC type name, its members the animal's excitatory descending neurons mapped to it):
  - MANC: tuned B1r (`pertype_v1/B1r.csv`, 16 seeds); original procedure K = 0, `predictions/B1-lo10` (the regression gate of rulebook
    v2 P1 reproduces it with K = 0; `LOCK_predictions_v1.json`); sweep `dx-1-run4` (fix 1, 8 seeds; Part H locks it); A1 (authors).
  - MaleCNS: tuned B2r (`pertype_v1/B2r.csv`); K = 0, `predictions/B2`; sweep `ms-mcns-run6` (Part H, new, 8 seeds).
  - BANC (new, Part B): tuned `bt-banc-run6` (16 seeds), sweep `bs-banc-run6` (8 seeds), one-sided `bh-banc-run6` (8 seeds), copies
    `bn-banc-run6` (8 seeds).
  - **Sweep score** (rulebook v4 fix 1 / B1.4): per replicate the best in-bounds score over the 19 grid currents 4 x 2^(k/2), k = 0..18
    (in bounds = B1's screen bounds and >= 1 active read-out motor neuron), 0 if none is in bounds; every replicate is usable.
- **G5. Type sets.**
  - **Three-animal set** (182 types): MANC types of B1r with a high-confidence match in MaleCNS (`pertype_v1/match_confidence.csv`, run
    5's rule, L160) and in BANC (`banc.match_confidence()`, the same rule, L177).
  - **Pairwise sets:** MANC-MaleCNS = run 5's common types (high 215, all 310). MANC-BANC = B1r types with a BANC group (high: BANC
    confidence high). MaleCNS-BANC = B2r types with a BANC group (high: high in both).
  - **DNg100 is never counted as evidence of replication.** Every count of Parts H and C is given with and without it; Part C's words rest
    on the version without it.

---

## Part H. The first two animals' numbers (ALL POST HOC)

Computed by ledger code (`ledger/scripts/posthoc_v6.py`) from locked tables and the two sweep screens, written to `posthoc_v6/`, locked
by `LOCK_posthoc_v6.json` (tag `ledger-posthoc-v6`). Every table and sentence says "post hoc".

- **H1. Pairs** (MANC first): tuned B1r x B2r; authors' A1 x B2r; original procedure (K = 0) B1-lo10 x B2; sweep dx-1 x ms. Type sets:
  MANC-MaleCNS high (215) and all (310); each with and without DNg100.
- **H2. Hit-list overlap at cuts 0.3, 0.4, 0.5, 0.6** (G2): n_X, n_Y, k, chance expectation, hypergeometric p, both replication rates,
  OC, cross-half OC, ceiling, OC ratio with intervals; the list of types in both at each cut.
- **H3. Graded version** (G3) at each cut, both directions, with the within-animal references.
- **H4. The agreement of each pair** (G1, cross-half, ratio, words, as information; run 4's locked 0.38 is the tuned pair on all types).
- **H5. MaleCNS sweep.** If no whole-type sweep of MaleCNS is stored (none is), `ms-mcns-run6` runs it: B2r's 328 groups, seeds 0..7,
  `sweep_v4` exactly as `dx-1-run4` (`gha6.build_ms`). It concerns animals already seen, so it is post hoc.

---

## Part B. The BANC screens

**B0. Network and groups** (fixed, `banc.py`): the authors' released matrix as it is (no floor, signs as released), sizes `surf_area_um2`,
read-out the 139 front-leg motor neurons (68 left, 71 right), excitatory descending neurons by the authors' BANC rule, grouped by mapped
MANC type (309 groups). Nothing is calibrated on BANC; **K = 1 is not re-chosen** (hard limit 3).

**B1. Whole-type screens.**
- **Tuned (primary):** B1r's procedure exactly (rulebook v2 P1; v4 G1): tuner v2 with K = 1, start current 128, halve / double / bisect,
  at most 10 runs, accept the first run with 10 <= active neurons <= 1,500, <= 200 neurons above 100 Hz and >= 1 active front-leg motor
  neuron; T = 1 s; score = the published rhythm score of the accepted run's active read-out motor neurons; every group, seeds 0..15
  (`gha6.build_bt`, the job specification identical to B2r's, tested).
- **Single members (C5):** each DNb08 and each DNg100 member alone, the same procedure, seeds 0..15 (keys `BT1|<type>#<position>`).
- **Sweep (companion):** rulebook v4 fix 1 (G4), every group, seeds 0..7 (`gha6.build_bs`, identical to `dx-1-run4`'s specification).

**B2. One-sided screens (C1).** Rulebook v4's Part A design: one side's members stimulated, that side's front-leg motor neurons read out
(for the tuner's K and for the score), the tuned procedure, seeds 0..7 (`gha6.build_bh`). **Sides of descending neurons** (rulebook v4 G3,
computed only after the freeze, `banc.dn_sides`): the annotated side (`side`) and the output side (the side holding the majority of the
neuron's output synapse counts onto neurons annotated left or right; undefined if none or exactly half). The annotation is reliable if
it agrees with the output side for >= 90 % of members with a defined output side; if reliable, annotations are used (midline members
left out); if not, every member's side is its output side (undefined members left out). A type is **matched** if it has >= 1 member on
each side; it is **label-consistent** if all its members carry one BANC `cell_type` label (BANC has no bilateral group annotation, so
this replaces rulebook v4's homolog-consistent set).

**B3. Count noise (C2).** Two copies of BANC in which every released count c >= 1 is replaced by a Poisson(c) draw
(`default_rng(20261611)` and `(20261612)`; `fixes.poisson_copy`), the presynaptic neuron's sign carried over, no floor (the authors' BANC
network has none); signing the unresampled counts must reproduce the released matrix exactly (checked by the builder). On each copy the
left one-sided screen (B2) of the C1 types, seeds 0..7 (`gha6.build_bn`).

**B4. Validity rule** (a screen failing its positive control would show "nothing replicates" for the wrong reason).
- The tuned BANC screen is **valid** if DNg100 (both members, whole type) scores >= 0.5 in at least 12 of its 16 seeds (an unusable seed
  counts as < 0.5). K was not chosen on BANC, so here this is a real test.
- If it is not valid, the **sweep becomes primary**, provided DNg100 scores >= 0.5 in at least 6 of its 8 sweep seeds.
- If neither is valid, C3 to C8 are **"not judged"** for BANC and are reported descriptively only.
- When the sweep is primary, every primary comparison of C3, C4, C6, C7 and C8 uses the sweep screens of all three animals (dx-1, ms,
  bs), and the tuned versions are reported beside them.

---

## Part C. Confirmatory tests (pre-registered)

Each test: the statistic, its interval, its words, and its power stated now. High-confidence type sets lead; all matched types stand
beside them. "Primary procedure" = the tuned screens unless B4 makes the sweep primary.

**C1. Left against right in BANC.** BH-L vs BH-R (B2), G1's ratio with interval and words, on the matched label-consistent types
(primary) and on all matched types. Reported beside: per-side driver counts and score distributions; MANC's and MaleCNS's locked
one-sided ratios (0.59 and 0.64, rulebook v4 A2). *Power:* with about 200 types and 8 seeds the ratio's interval is expected to be about
+-0.10 to 0.15 wide (run 4: +-0.10 with 16 seeds and 307 types), so a ratio below about 0.85 would be called a real gap.

**C2. Count noise in BANC.** On C1's primary set: the copy-vs-copy cross-half agreement rho_x (copy 1 vs copy 2, left screens) with its
interval; the observed left-right cross-half agreement rho_x (BH-L vs BH-R, C1). **Words (rulebook v4 B4.5):** "count noise reproduces
BANC's left-right agreement" if the observed value lies inside the copy-vs-copy 95 % interval, otherwise "does not reproduce it".
Reported beside: both ratios, each copy vs BH-L, and the difference observed minus copy-vs-copy with its interval (same resamples).
Departure: run 4's paired second statistic needs a mirror network built from bilateral group annotations, which BANC lacks; the
cross-half statistic does not depend on paired draws (its two halves use disjoint seeds), so it is computed unchanged. *Power:* as C1
(MANC: copy-vs-copy 0.48 of the ceiling, interval +-0.12).

**C3. Agreement across animals.** Pairs MANC-BANC (B1r vs BT), MaleCNS-BANC (B2r vs BT) and, as the reference, MANC-MaleCNS (B1r vs
B2r; post hoc), whole-type screens, G1's ratio, interval and words; on the three-animal set (primary) and on the pairwise high and all
sets; for the tuned procedure and for the sweep (dx-1 vs BS, ms vs BS, dx-1 vs ms; 8 seeds). **Sentence for the results' first line:**
the gap between animals is **"confirmed in the third animal"** if both BANC pairs on the three-animal set under the primary procedure are
"a real gap"; **"not confirmed"** if either is "at the ceiling"; **"inconclusive"** otherwise; **"not judged"** if B4 leaves BANC not
judged. *Power:* as C1; run 4's cross-animal ratio 0.38 (0.26-0.49) on 310 types would be a real gap with a wide margin.

**C4. Hit lists in BANC.** For three lists X: our MANC list (B1r), the authors' list (A1), our MaleCNS list (B2r); Y = BANC (primary
procedure). Type sets: X's animal paired with BANC, high (primary) and all.
- At the authors' cut 0.5 (G2): k / n_X with its Clopper-Pearson interval, the chance expectation, the hypergeometric p. **Words (on the
  set without DNg100):** "at chance at the authors' cut" if p >= 0.05, otherwise "above chance".
- Beside it, without words: the curve at 0.3, 0.4, 0.5, 0.6 (G2), the graded version (G3), the OC ratio against the within-animal overlap
  (G2), every number with and without DNg100.
- *Power* (`PLANNING_v6.json`): for B1r's 11 high-confidence drivers among 182 types and 20 to 30 BANC drivers, 4 to 5 shared drivers are
  needed; power 0.21 to 0.43 if 30 % of X's drivers truly recur, 0.73 to 0.89 if 50 % do; the smallest attainable p is below 1e-9.

**C5. Named neurons.**
- **DNg100** (whole type, primary procedure, tuned unless B4 says otherwise): **predicted to be a driver in BANC** (type score >= 0.5).
  Words: "pass" or "fail". This is a prediction of the unchanged procedure; it is not evidence of replication (G5).
- **DNb08:** no prediction (Part Q 3). Reported: the whole type (tuned and sweep) and each of its four members alone (B1), with the
  authors' BANC result beside it (their configuration is read only after the freeze).
- **A table** of every type that is a driver in at least one of B1r, A1, B2r and BANC (tuned): its score in every screen of Part H and
  Part B, its match confidences, and its category flags.

**C6. Does pooling two animals predict the third?** On the three-animal set, primary procedure, full-seed type scores. For each target T
in {MANC, MaleCNS, BANC} with the other two A and B: d_T = rho(mean(s_A, s_B), s_T) - (rho(s_A, s_T) + rho(s_B, s_T)) / 2 (Spearman).
Statistic D = mean of the three d_T, with a 95 % interval from 10,000 type resamples (`default_rng(20261602)`). **Words:** "pooling helps"
if the interval's lower end is > 0, otherwise "not shown". **Expected size before running** (Spearman-Brown for exchangeable animals,
corr(mean of two, third) = r sqrt(2 / (1 + r))): with r = 0.37 (B1r vs B2r on this set, post hoc) the expected gain is **+0.077**; it
is 0.06 to 0.08 for any r between 0.2 and 0.6, so a real gain of this size may not be distinguishable from zero with 182 types.

**C7. How many connectomes?** rbar = the mean of the three cross-animal ratios (C3's three pairs, three-animal set, primary procedure).
**Spearman-Brown estimate** n* = 4 (1 - rbar) / rbar: the number of animals whose pooled screen would agree with another such pooled screen
at 0.8 of the within-animal ceiling (pooled agreement of n animals = n rbar / (1 + (n - 1) rbar)). Interval: 10,000 type resamples
(`default_rng(20261603)`), the three ratios recomputed on each resample; a resample with rbar <= 0 gives n* = infinity (counted).
Reported rounded up, **labelled an extrapolation**, with its assumption stated: the animals are exchangeable noisy measurements of one
screen, and differences in reconstruction and annotation count as differences between animals. No words beyond the number.

**C8. Does stability under count noise predict the third animal?** A second, independent try of run 5's idea.
- Predictor: each driver's **mean copy score** across run 5's 16 Poisson copies of MANC (`replication_v1/S_tests.json`, `per_type[*].
  mean_copy_score`, locked). Outcome: its BANC type score (primary procedure).
- Types: the 16 drivers of run 5's test that have a BANC group (13: DNa07, DNb08, DNg100, DNg54, DNg63, DNit013, DNp02, DNp41, DNp63,
  DNxl101, DNxl102, DNxl110, DNxl121; DNit011, DNxl053 and DNxl133 have none), **without DNg100: 12 types**.
- Statistic: Spearman rho; one-sided permutation test, p = (1 + #{permuted rho >= observed}) / (1 + 100,000), permutations of the
  outcome with `default_rng(20261604)`. **Words:** "stability under count noise predicts the third animal" if p < 0.05, otherwise "not
  shown".
- Secondary, without words: with DNg100 (13 types); run 5's stability fraction as the predictor; whether stability adds anything beyond
  the type's real-network MANC score (B1r): the partial Spearman correlation of the BANC score with the mean copy score given the B1r
  score.
- **Disclosure:** this predictor was chosen because it was nominally positive in run 5 (p = 0.035), on another animal.
- *Power* (`PLANNING_v6.json`): with 12 types the one-sided 0.05 test needs rho >= 0.48; power 0.24, 0.51 and 0.83 if the true rho is
  0.3, 0.5 and 0.7. A null result is weak evidence.

---

## Part V. Is our MaleCNS screen the authors' model? (descriptive; fixed words)

- **V1.** The authors' MaleCNS DNg100 configuration (their run 33241780: position 9, current 400, T = 2 s) on B2r's network, seeds 0..63.
  Words: "reproduces the authors' DNg100 result" if the mean score is >= 0.90 and >= 90 % of seeds score >= 0.5 (their result: mean
  0.985, 100 %), otherwise "does not reproduce it".
- **V2.** Each of DNb08's four MaleCNS members (positions 328, 330, 345, 391; bodies 12044, 12075, 12189, 12550) alone, at each of the 19
  grid currents and at 250 (the authors' current; their run 2026040200 stimulated position 391 at 250, T = 2 s, on the same network as
  B2r, so no other network is needed), T = 2 s, seeds 0..15 (`gha6.build_pv`). **Words** (RUN6_PROMPT): "reproduces the authors' reported
  result at current X" if any current gives a score >= 0.5 in at least half the seeds (each such member and current is named, the
  authors' own configuration first), otherwise "does not reproduce it at any tested current". Their reported result: mean 0.803, 87.8 %
  of replicates >= 0.5 (n = 1,024).

Whatever V2 shows goes in the paper and the email to the authors.

---

## Part F. The forward list

Forward ledger v2 (`forward_v2/`, `LOCK_forward_v2.json`) does not change. Its 12 types are reported with their BANC scores (tuned and
sweep) and match confidence beside the locked readings, without changing any reading.

---

## Part X. Process

- **X1. Order** (RUN6_PROMPT section 7): publish `ms-mcns-run6` (Part H), `pv-mcns-run6` (Part V), `bt-banc-run6` (B1; its validity
  check as soon as it is collected), `bs-banc-run6`, `bh-banc-run6`, `bn-banc-run6`, then the determinism re-runs; the tests after the
  campaigns. Every builder except the gate refuses before the tag is on origin and this lock verifies (`gha6.require_freeze6`).
- **X2. Compute.** GitHub Actions under the trust gate (passed, `gates_v6/TRUST_GATE_v6.json`), at most 20 jobs queued or running, at
  most 150 runner-hours (step time, run 3's rule), chunks sized from measured job times to finish in under an hour. No Modal; the Mac
  runs no prediction. **Checkpoint:** after `bt` and `ms` are collected, the remaining campaigns are projected from measured times; if the
  projection exceeds 140 runner-hours, campaigns are dropped in RUN6_PROMPT section 11's order (the copies of C2, then the BANC sweep,
  then the one-sided screens of C1), each drop logged. Never dropped: Part H, Part V, the tuned BANC screen with its validity check, C3 to
  C8.
- **X3. Determinism.** Two re-run campaigns (`det6-1-run6`: bt, ms, pv; `det6-2-run6`: bh, bs, bn), 20 jobs per campaign drawn with
  `default_rng(20261629)`; every digest must match. A mismatch is reported with the campaign's results and investigated before its
  tests are read.
- **X4. Analysis code.** `ledger/scripts/posthoc_v6.py` (Part H) and `ledger/scripts/thirdfly_v1.py` (Part C, Part V, Part F) are
  written after this freeze to these definitions, tested on the first two animals' locked data (C3's MANC-MaleCNS pair on all common
  types must reproduce run 4's locked 0.38 cross-animal ratio to three decimals where the same types and seeds are used), and committed
  with their SHA-256 in the LOG **before the first BANC campaign's results are collected**. A later change is an amendment row
  (`lock6.py amend`) with its reason.
- **X5. Locks.** `LOCK_posthoc_v6.json` (Part H outputs; the two sweeps' result logs by SHA-256), tag `ledger-posthoc-v6`;
  `LOCK_thirdfly_v1.json` (the BANC results, Parts C, V, F, gates_v6; the result logs by SHA-256), tag `ledger-thirdfly-v1`; each pushed
  and timestamped with OpenTimestamps; a pre-mortem in the LOG before each. A bug found after a lock makes a new version with a changelog.
- **X6. Random numbers.** Agreement bootstrap 20261401 (v4 G10); overlap and graded bootstraps 20261601 (fresh per pair, set, cut);
  pooling 20261602; how-many-connectomes 20261603; C8 permutations 20261604; Poisson copies 20261611, 20261612; determinism 20261629;
  model seeds as stated per screen.
- **X7. Reporting.** RESULTS_5, the paper and the brief use the words above and no stronger ones; post hoc results say so; DNg100 is
  never evidence of replication; every count with and without DNg100; Part V's outcome goes in the paper and the authors' email.
- **X8. If things go wrong.** DNg100 fails the validity bar: B4, K unchanged. Fewer than 100 three-animal types: the pairwise comparisons
  lead and the report says the three-way set is small (it has 182). A test comes out against the earlier pattern: it is reported with its
  words and the paper is rewritten around it. A campaign cannot finish: its tests are "not run" and say why.

---

## Part D. Departures from RUN6_PROMPT (each with its reason)

| # | RUN6_PROMPT | This rulebook | Reason |
|---|---|---|---|
| 1 | BANC table `wTable_20260217_fullData_consistentColumns.csv` | `wTable_20260217_fullData.csv` for the build | It is the table the authors' BANC config names; the two have the same rows in the same order, and the match columns are identical. |
| 2 | Read-out "the front-leg motor neurons" | the 139 front-leg motor neurons, the 12 neck motor neurons left out | As the MANC and MaleCNS read-outs (the authors' code counts every motor neuron; their notebooks score module-labelled ones). |
| 3 | C1: rulebook v4 A2's primary set (homolog-consistent types) | label-consistent matched types | BANC has no bilateral group annotation. |
| 4 | C2: rulebook v4 B4.2 (paired draws, mirror network) | the cross-half statistic on the one-sided screens; no paired statistic; copies without a floor | The mirror network needs bilateral group annotations (absent); the cross-half statistic does not depend on paired draws; the authors' BANC network has no floor. |
| 5 | C4: the share's interval | Clopper-Pearson for the share; type resamples for the OC ratio and the graded version | An exact interval for a count out of n; the resampling intervals as run 5. |
| 6 | C4 and Part C: "with and without DNg100" | the words rest on the version without DNg100 | DNg100 is never counted as evidence of replication (RUN6_PROMPT section 6). |
| 7 | C8: "the 16 drivers ... that have a BANC match" | 12 types (13 with DNg100) | Three of the 16 have no excitatory BANC group. |
| 8 | Part V V2 | T = 2 s at every current | The authors' DNb08 run length; their reported result is at T = 2 s. |
| 9 | Part H: K = 0 screens | MANC's `predictions/B1-lo10`, MaleCNS's `predictions/B2` | The locked screens of the original procedure (rulebook v2 P1's regression gate ties K = 0 to B1-lo10). |
| 10 | Part H: MANC sweep | `dx-1-run4`, stored but under no lock, locked now by SHA-256 | It is the only whole-type sweep of MANC; disclosed in Part Q 6. |
| 11 | The analysis code | written after the freeze, before any BANC result is collected (X4) | The definitions here are complete; the code is tested on the first two animals' locked data first. |
