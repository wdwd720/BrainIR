# BrainIR prediction ledger: pre-registration, version 4 (run 4: why the simulation disagrees with itself)

Status: **version 4**, frozen by the git tag `ledger-prereg-v4` with `LOCK_prereg_v4.json` (this file, `RUN4_PROMPT.md`, the run 4
code, the pre-freeze evidence in `diag_v4/` and `gates_v4/`, the reviews in `reviews_v4/`, and the hashes of every earlier lock).
Spec: `research/ledger/RUN4_PROMPT.md`. Decisions: `LOG.md` L104+. Nothing here may change after the tag; a change is a new version
with a changelog row.

**What v4 is.** Exams 1 and 2 are unblinded and closed. Run 4 collects no labels. It asks whether the simulated screen disagrees
with itself across the two sides of one fly and across two flies, why, and whether any of a fixed list of parameter-free fixes makes
it reproducible; then it locks a forward ledger of predictions for experiments not yet done. Every analysis, metric and criterion of
the run is defined here before the data or simulation it concerns (RUN4_PROMPT hard limit 1). Anything thought of later is reported in
a section marked EXPLORATORY.

| version | date | change | data existing at the time |
|---|---|---|---|
| 4 | 2026-11-21 | reliability v2 (Parts A0, A, B, C), exam re-scores (Part D, exploratory), forward ledger (Part E) | exams 1 and 2 unblinded; R1-R4 (run 3); no run 4 simulation; the pre-freeze checks of Part Q |

---

## Part Q. What was looked at before this freeze (disclosure)

Seen before the freeze, and therefore not evidence for anything decided here:
- Run 3's reliability study (`reliability_v1/`): cross-fly 0.37 (whole type, 16 seeds), split-half ceilings 0.86 / 0.93, wiring
  0.78-0.97, weight noise 0.82 / 0.76 / 0.65, **left vs right 0.43 (R4: MANC, seeds 0..3)**. Per-type R4 values were not opened.
- Exam 1 and exam 2 results (RESULTS_1, RESULTS_2, POSTMORTEM_1); prediction-side tables B1r, B2r, B1 and run 1's controls (driver
  counts of the five rewired controls under B1: 1, 1, 2, 0, 0 of 321; B1 itself 10; B1r 15; B2r 30).
- Timing and current distributions: R4 jobs 20.9 s mean on GitHub; B1r accepted currents 1-99 % 4.06-1024 (min 1.75, max 2048);
  B2r jobs 2.7 s.
- **Side QA (annotations and wiring only, `diag_v4/SIDE_QA.json`, `ledger/scripts/side_qa_v4.py`)**: for excitatory DN members,
  the annotated side against the side that receives most of the neuron's output synapse counts onto sided neurons of the same
  network ("output side"): MANC root side agrees for 851 of 921 (92.4 %); MaleCNS has no root-side annotation for DNs, and its brain
  soma side agrees for 517 of 858 (60.3 %; DNs that cross in the brain); the root side of the matched MANC body agrees for 730 of 849
  (86 %). Handedness: 2,705 of 2,720 non-DN MaleCNS neurons with a curated MANC match have the same soma side as the matched MANC
  body (99.4 %), so "left" means the same in both datasets. The reliability threshold of G3 (90 %) was written after these numbers
  were seen; no screen score entered them.
- Annotation coverage: MANC bilateral groups (`group_id` of the processed `manc:v1.2.3` neurons, by bodyId) cover 4,349 of the
  4,604 front-leg neurons (1,259 one-left-one-right groups); MaleCNS `group` covers 3,924 of 4,310. MaleCNS's matrix is floored at 5
  (no counts below 5), so floors and count noise are MANC only (B4, C3).
- The dose-arm check of Stage 0 (`diag_v4/DOSE_ARM_CHECK.json`, LOG L105): run 3's fixed currents were applied; not a bug.
- The trust gate for run 4 (`gates_v4/TRUST_GATE_v4.json`): run 2's 100 locked jobs, 100 of 100 identical digests.

- **Seen while testing the mirror code (wiring only):** the entry-class counts of B3.1 (entries of W and M; each homologous pair
  counted twice): MANC class 1 110,689, class 2 114,672, class 3 57,022; MaleCNS 63,168 / 71,136 / 40,368. So about half of the
  homologous connection pairs between matched neurons exist on one side only (the share A4(b) reports). No rule here depends on it.
  Mirror-map counts (MANC: 1,259 + 647 + 96 pairs by steps 1-3, 259 left and 307 right unmatched; MaleCNS: 1,108 + 561 + 59, 331 and
  262) and type counts (MANC 308 matched types, 250 with one member per side; MaleCNS after G3's correction 250 matched, 196 one per
  side; 343 MaleCNS DN members corrected, 25 left out) were printed by the same check.

Not computed before the freeze: any left-right or cross-fly comparison of A0 or B0, any per-type R4 value, any correlation of
connection weights between sides or flies, any count dispersion, any run 4 simulation of a real network.

---

## Part G. Definitions used everywhere

**G1. The screen.** B1r's procedure, unchanged (PREREG v2 P1; v1 3.4): tuner v2 with K = 1, start current 128, halve / double /
bisect, at most 10 runs, accept the first run with 10 <= active neurons (any positive rate) <= 1,500, <= 200 neurons above 100 Hz and
>= 1 active read-out motor neuron; T = 1.0 s; score = the published rhythm score of the accepted run's active read-out motor neurons
(t >= 0.25 s, active = peak > 0.01 Hz, prominence 0.05); a replicate with no accepted run is unusable. Model, priors, solver and
numerics exactly as B1r. **One-sided variant (R4's procedure):** only one side's members are stimulated, and the read-out (for K and
for the score) is that side's front-leg motor neurons. **Whole-type variant:** B1r itself (both sides' members, all front-leg motor
neurons).

**G2. Networks and half-flies.** MANC = the front-leg network of B1r (`networks.front_leg()`, 4,604 neurons, 144 front-leg motor
neurons, 72 per side). MaleCNS = the authors' MaleCNS front-leg network of B2r (`arms.malecns_network()`, 4,310 neurons, 130 front-leg
motor neurons: 67 left, 63 right). Groups: B1r's and B2r's type groups (excitatory DNs by MANC type; MaleCNS DNs mapped to MANC types
by B2's rule). **The four half-flies:** MANC-L, MANC-R, MaleCNS-L, MaleCNS-R (one-sided variant, members of that side, that side's
motor neurons).

**G3. Side of a neuron.** Annotation first: MANC `somaSide` (LHS/RHS/Midline), else the root side of the authors' full-cord node
table by bodyId (DNs and sensory neurons have no nerve-cord soma); MaleCNS `somaSide` (L/R/M). **Anatomy check for DNs (every
excitatory DN member, not a sample):** the output side = the side holding the majority of the neuron's output synapse counts onto
neurons whose annotated side is L or R in the same network (undefined if it has no such output or exactly half). **Reliability
rule:** a fly's DN side annotation is reliable if it agrees with the output side for at least 90 % of the members whose output side
is defined. If reliable, the annotation is used for every member; if not, every DN member's side is its output side ("corrected"),
members with an undefined output side are left out of the half-fly groups (counted), and every Part A analysis of that fly is also
reported restricted to the types none of whose members was corrected ("uncorrected types"). From Part Q: MANC is reliable (92.4 %),
MaleCNS is not (60.3 %; its DN sides are therefore output sides). **Non-DN check (a sample):** 200 neurons per fly drawn with
`default_rng(20261451)` from the network's non-DN neurons with an annotated L/R side and a soma position (MANC: `soma_x` of the
processed `manc:v1.0` neurons by bodyId; MaleCNS: `somaLocation` of the body annotations); the position side is the side of the
soma's x coordinate relative to the midline x0 = the midpoint of the mean x of left and of right annotated somata in the sample's
network; agreement is reported (no correction is made from this check; if agreement is below 95 % it is reported as a caveat).

**G4. Matching across sides.**
- *Types (Parts A0, A, C):* a type is **matched** in a fly if it has at least one member on each side; L-only and R-only types are
  counted and left out. Member counts per side are recorded; "equal member counts" = the same number on both sides.
- *Neurons (Blocks 2-3, wiring comparisons, fixes 4-5):* a mirror map built in this order, each neuron used once.
  (1) Annotated bilateral group (MANC: processed `manc:v1.2.3` `group_id` by bodyId; MaleCNS: body-annotation `group`) with exactly
  one member on each side in the network: paired. (2) Groups with members on both sides but more than one on a side: pairs are
  chosen within the group by the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`, maximising the total similarity) on the
  cosine similarity of the two neurons' input and output count profiles over the neurons paired in step 1 (the right neuron's profile
  is mirrored through the step 1 pairs); extras go on to step 3. (3) Remaining neurons of the same type (the network table's `type`)
  on opposite sides: the same Hungarian step within the type. (4) Everything else with a side L or R is **unmatched**. The profile
  of a neuron lists, for each step-1 pair, its counts to and from the pair's member on its own side and on the other side (in that
  order), divided by the vector's norm. Neurons
  without a side (midline, unsided) map to themselves. The counts per step and per side are recorded (`mirror_<fly>.json`).
- *Mirror network.* Every unmatched neuron gets a ghost partner slot on the other side (no connections, its own size and sign), so
  the map m is an involution on the extended slot set, and M = P W P^T (M[i, j] = W[m(i), m(j)], with sizes and signs carried by
  m) is an exact relabelling. The left screen on M is the right screen on W. In the extended network a slot is **present** if it is
  a real neuron of that network (in W: the real neurons; in M: the images of the real neurons); only present slots are stimulated.
  Ghost and absent slots have no input, so the model keeps them at rate 0 (max(r_max tanh(.), 0) with input 0 and theta > 0).

**G5. Scores and bands.** Per replicate: the accepted run's score (unusable -> 0 for the "fraction rhythmic"). Per type and design:
the **type score** = mean score over usable replicates, 0 if none (run 2's `primary_score`). Bands: driver (>= 0.5), non-driver
(< 0.05), indeterminate. **Fraction rhythmic** = the fraction of all replicates (usable or not) whose score is >= 0.5.

**G6. Agreement between two screens X and Y over a type set (Spearman of type scores).**
- **Primary (matched to the ceiling), the cross-half agreement:** the replicate seeds are split into a first and a second half (16
  seeds: 0..7 and 8..15; 8 seeds: 0..3 and 4..7; A0's 128 replicates: columns 0..63 and 64..127; B0: seeds 0..7 and 8..15);
  rho_x(X, Y) = (rho(X_1, Y_2) + rho(X_2, Y_1)) / 2, where X_1 is X's type score from the first half only.
- **Matched ceiling:** c(X, Y) = (rho(X_1, X_2) + rho(Y_1, Y_2)) / 2 (each screen against itself across disjoint seeds, same number
  of seeds per mean as rho_x). **Ratio** = rho_x / c.
- **Full-seed agreement** rho(X, Y) on all seeds is reported beside it (no ceiling is claimed for it).
- **Intervals:** 95 % percentile bootstrap over types (10,000 resamples of the type set with replacement, `default_rng(20261401)`;
  every quantity of the resample recomputed from the same resampled types; Spearman with average ranks; a resample in which a
  vector is constant gives NaN and is dropped, the count reported).
- **Secondary measures**, each for full seeds, for the cross-half form and for the split halves (ceiling form):
  (a) rho over types non-zero (type score > 0) in at least one of the pair; (b) rho over types with equal member counts on the two
  sides (left-right pairs only); (c) **replication rate**: of the types called drivers in X, the fraction also drivers in Y, both
  directions and their mean (NaN when X has no driver); (d) Cohen's kappa of the three bands; (e) top-30 overlap: the top 30 types by type
  score among types with a non-zero score (ties broken by type name; fewer if fewer are non-zero), |A ∩ B| / max(|A|, |B|), undefined
  if both lists are empty (zero-score types never enter a list, so a name tie-break among zeros cannot inflate it).
- **Paired same-seed agreement** (Blocks 2-3 and count noise, G8): rho of the 8-seed type scores of two screens run on the same seeds
  with paired draws; its reference is the relabelling control (B2.4), not a split half. It is a labelled second statistic.

**G7. Words for a comparison (one rule for every branch).** For a pair X, Y with ratio rho_x / c and its interval:
- **at the ceiling** if the ratio's point estimate is >= 0.90 and the upper end of its 95 % interval is >= 1.00;
- otherwise **a real gap**; if c < 0.2 the comparison is **not judged** (ceiling too low).
**Gap closure** of an intervention that turns X into X' (compared with the same Y): closure = (rho_x(X', Y) - rho_x(X, Y)) /
(c(X, Y) - rho_x(X, Y)), with the bootstrap interval (same resamples). It is reported only when the before-pair is a real gap; the
after-pair's own ceiling c(X', Y) is reported beside it. An intervention **closes the whole gap** if the after-pair is at the ceiling
by the rule above. Paired form (second statistic): (rho_p(X', Y) - rho_p(X, Y)) / (r_ref - rho_p(X, Y)), r_ref = the relabelling
control's paired agreement.

**G8. Paired draws.** Used in Blocks 2-3 and count noise (not in Parts A0, A, Block 1 or C, which use the unchanged procedure). For
seed s the raw draws (tau, a, theta, r_max) of the real network's N neurons are produced exactly as `sample_neuron_params(cfg, N, s,
sizes)` produces them (one stream in that order); then every matched pair shares the raw draws of its lower-indexed member, every ghost
slot takes its partner's raw draws, and each slot is size-scaled with its own size relative to the real network's median (NaN or 0
size -> scale 1), exactly as `size_scaling` does. With no pair and no ghost this reproduces `sample_neuron_params` bit for bit
(tested). Consequence: the left screen on M and the right screen on W use identical parameters slot for slot.

**G9. Type sets.**
- Part A: every matched type of each fly (both sides present); cross-fly pairs use the types matched in both flies (MaleCNS groups
  carry MANC type names).
- **Informative set I** = the types whose type score is > 0 in at least one of the four half-flies of Part A (16 seeds).
- **Analysed set** for Parts B and C = I plus 50 types drawn with `default_rng(20261402)` from the remaining types matched in both
  flies (all of them if fewer than 50), the same set for every block and fix; each fly uses the analysed types matched in it. Every
  table says that it is on the analysed set.

**G10. Random numbers.** Bootstrap 20261401; analysed-set sample 20261402; relabelling control permutation 20261403; R4
reproduction sample 20261404; determinism samples and the identity-hybrid sample 20261405; Poisson copies 20261411, 20261412; negative-binomial copies 20261421, 20261422; Part E nothing random; side QA sample
20261451. Model seeds as stated per part.

---

## Part A0. The authors' own scores (no simulation)

- **Data.** A0 (the authors' single-neuron screen, 933 excitatory DNs x 128 replicates, locked in predictions v1) and B0 (BrainIR's
  single-neuron screen, 933 x 16). Neuron score = mean over usable replicates, 0 if none (A0: 5 <= nActive <= 1,500; B0: the tuner's
  usable flag), exactly as the locked `predictions/A0/neurons.csv` and B0 tables. A0's 128 replicate columns were checked before
  the freeze: no two are identical.
- **Sides:** MANC rule of G3 (root side). **Pairs:** types with at least one left and one right member; **primary subset: exactly one
  member per side**; for the others the side's score is the mean over that side's member neurons.
- **Test:** G6 on left vs right (primary measure on the primary subset; all secondary measures; the same on all matched types as a
  secondary set), for A0 and for B0 separately. Ceiling: G6's split halves (A0 columns 0..63 vs 64..127; B0 seeds 0..7 vs 8..15).
- **Note (stated in every report):** this screen stimulates one neuron and reads out both front legs together, unlike Part A.
- **Decision.** If A0's primary left-right comparison is **at the ceiling** (G7), the report says first and plainly that the
  left-right gap may be specific to our one-sided procedure, and the left-right results of Parts A-C are reported as properties of
  that procedure, with the cross-fly results given equal weight. Otherwise the authors' own data show a left-right gap.

---

## Part A. Establish the gap

**A1. Runs.** The one-sided screen (G1) on the four half-flies, every matched type, seeds 0..15, with R4's job specification
exactly (run 2's kind `group_v2`, `k_min` 1, B1's screen configuration, `readout_traces` stored for the accepted run, the side's
read-out mask; parameters by `sample_neuron_params` on the real network). **MANC seeds 0..3 are R4's locked runs, reused:** they
match this specification exactly (same network, groups, read-out, seeds, code path). As a check, 100 of them drawn with
`default_rng(20261404)` are re-run through run 4's runner before any other run 4 campaign is used, and must reproduce R4's digests
(run 1 digest field); if any differs, the reuse stops, all MANC seeds 0..3 are re-run, and Part A uses the re-runs.

**A2. Six agreements with matched ceilings** (G6, G7; full-seed rho beside them): MANC-L vs MANC-R, MaleCNS-L vs MaleCNS-R (left vs
right); MANC-L vs MaleCNS-L, MANC-R vs MaleCNS-R (cross-fly, same side); MANC-L vs MaleCNS-R, MANC-R vs MaleCNS-L (cross-fly,
opposite side). Reference row: the whole-type cross-fly comparison of run 3's R1 (B1r vs B2r, 16 seeds) recomputed in the G6
cross-half form. For MaleCNS also on the uncorrected types (G3). Also reported: same-side minus opposite-side cross-fly agreement
(a left-right difference that is consistent across flies makes same-side pairs agree more).

**A3. One bad side?** For each fly: per-type score distributions (median, mean, share non-zero), driver counts, tuner outcome counts
(accepted, last run too weak, last run too strong), and the paired per-type difference L - R (Wilcoxon signed-rank over types with a
non-zero difference). A side is **weaker everywhere** if the Wilcoxon p < 0.01 and at least 60 % of the non-tied types favour the
other side; otherwise not.

**A4. Wiring, same comparisons.** No simulation; deterministic, so no ceiling (reported as such).
- (a) **Summaries:** run 3's S1-S7 baselines computed per half-fly (S1, S2, S3, S6 on the half's members and that side's front-leg
  motor neurons; S4, S5 over all outputs of the half's members; S7 = number of the half's members), the six G6 pairs by full rho.
- (b) **Single connections (neuron level, mirror map of G4):** for each fly, over unordered homologous connection pairs {(i, j),
  (m(i), m(j))} with i, j matched (step 1-3 neurons, not self-mapped): Spearman and Pearson of log counts over pairs present on both
  sides; the share of pairs present on one side only; MANC only (pre-floor counts, B4): of the one-sided pairs, the share whose
  absent partner has a raw count of 1-4 ("absent only because of the 5-synapse floor") and of 0.
- (c) **Across flies, type-to-type:** T[A, B] = summed counts from members of type A to members of type B (MaleCNS neurons carry
  MANC type names through their curated match: `mancBodyid` -> that body's MANC type, else `mancType`; neurons without one are left
  out), over type pairs present in at least one fly: Spearman and Pearson of log weights over pairs present in both, the share present
  in one fly only; also per side pair (same-side and opposite-side blocks).

**A5. Hemilineages and DNg100 (existing runs, descriptive).**
- Run 3's sensitivity groups H-M-S-L vs H-M-S-R (seeds 0..3, locked): Spearman over units for each of the 12 primary dimensions and
  over all unit x dimension cells; ceiling: the same with halves seeds {0, 1} vs {2, 3}, the dimensions recomputed per half with the
  frozen `groups_h1.arm_tables` from the stored results, cross-half form of G6.
- DNg100's own per-leg asymmetry: the authors' full-cord replicates (run 33195857, 32) and ours (run 1's G3 runs, both DNg100 at
  380, T = 2 s, 64 seeds): per segment (T1, T2, T3) the left and right leg scores (median, fraction >= 0.5) and the paired difference
  (Wilcoxon over replicates).

**A6. Summed read-out signal.** For each accepted run: the sum of the stored traces of its active read-out motor neurons
(`readout_traces`, t >= 0.25 s, 1 ms grid; inactive motor neurons have peak <= 0.01 Hz and are left out). Its rhythm score is the
published per-trace autocorrelation score (`network_oscillation_score` on that one trace, prominence 0.05; 0 if no motor neuron is
active). Used only by fix 2 (C1).

**A7. If no real left-right gap.** If MANC-L vs MANC-R is **at the ceiling** (G7), the report says so plainly, and Blocks 2-3, count
noise and Part C's attribution are run on the cross-fly gap instead (B5).

---

## Part B. Attribute the gap (MANC unless stated; analysed set G9; 8 seeds, 0..7)

### Block 1: procedure (unpaired, the Part A design, seeds 0..7, all four half-flies)

- **B1.1 Dose grid (fixed now from B1r's accepted currents):** 19 currents 4 x 2^(k/2), k = 0..18 (4.0, 5.66, 8, ..., 1448, 2048),
  i.e. B1r's 1st-99th percentile range (4.06-1,024) with the top extended one doubling because a half group has about half the members.
  Job kind `sweep_v4`: one job = one (half-fly, type, seed), all 19 currents in order (then the transplant currents of B1.3), each
  a fixed run (run 1's `fixed_run`, no tuner) with the same parameters as the Part A replicate of that seed. Per run: tuner class,
  active counts, read-out score, active read-out motor neurons. **In bounds** = the tuner-v2 acceptance test (10 <= active <= 1,500, <= 200 above 100 Hz, >= 1 active
  read-out motor neuron).
- **B1.2 Matched-current agreement:** left vs right at each grid current (type score = mean over the 8 seeds of the run's score, all
  runs counted), G6 form. Two tuner-free scores per type: **best in-bounds score** (per seed the maximum score over in-bounds currents,
  0 if none; type score = mean over seeds) and **fraction rhythmic in bounds** (per seed the share of in-bounds currents with score >=
  0.5, 0 if none in bounds; mean over seeds). Left vs right for each (G6, G7), and gap closure against Part A's tuned comparison on
  the same seeds 0..7 and types.
- **B1.3 Current transplant:** each side's members at the other side's accepted current of the same seed (Part A), and at their own
  accepted current (seeds whose replicate was accepted; others skipped and counted). Checks: the own-current run must reproduce the
  accepted run's score and active counts exactly (reported as a share). Agreements: L@I_R vs R@I_R and L@I_L vs R@I_L against Part A's
  L@I_L vs R@I_R (G6 on the transplanted seeds), and the closure.
- **B1.4 Reading:** the procedure share of the gap = the largest closure among best in-bounds, fraction rhythmic and the transplant
  (each reported). If Block 1 **closes the whole gap** (G7), the cause is the procedure: Block 2 and the network-level fixes still
  run, on the budget of Part X's reduced plan.

### Block 2: location (paired draws, both flies)

- **B2.1 Networks, all on the extended slot set of G4:** W (the real network), M (full mirror). Per type t (left members L_t, the
  left slots of t = its real left members plus the ghost slots of its unmatched right members): **H_own(t)** = W with the columns of
  t's left slots, their size, sign and presence taken from M ("the stimulated types' own output connections replaced"; with them the
  stimulated neurons' own size and sign); **H_rest(t)** = M with the same items taken from W ("only the rest of the network replaced").
  H_own(t) and H_rest(t) are built on the runner from W, M and the column list (`hybrid` spec of `group_v4`).
- **B2.2 Screens (left side, seeds 0..7, paired draws):** L on W ("before"), R on W, L on M (= R on W up to arithmetic), L on
  H_own(t), L on H_rest(t), and L on the relabelling control (B2.4). The target Y is R on W.
- **B2.3 Sanity checks, which gate every other Block 2-3 number:**
  (i) **left into left:** the hybrid builder with nothing replaced returns W exactly (matrices, sizes, signs, presence compared bit
  for bit) and 50 jobs drawn with `default_rng(20261405)` re-run through the hybrid path give digests identical to L on W;
  (ii) **everything transplanted:** L on M against R on W: the share of jobs with identical usable flag, identical accepted current and
  identical number of tuner runs must be at least the relabelling control's share minus 0.02, and the full-seed rho of type scores at
  least the relabelling control's minus 0.01 (and >= 0.95).
  If either fails, the mirroring is wrong: Blocks 2-3 stop until it passes (a code fix is a recorded amendment, X4), and the failure is
  reported. A fresh reviewer audits the mirror and hybrid code before the freeze (X6).
- **B2.4 Relabelling control (numerical floor):** W relabelled by a uniform random permutation Q (`default_rng(20261403)`) of all
  slots, parameters carried along (slot Q(k) gets slot k's parameters), stimulated set and read-out relabelled; L on Q W Q^T against L
  on W. It measures how much the screen changes under a pure relabelling (floating-point summation order only); it also answers the
  "our implementation" row of RESULTS_3 for the numerical part.
- **B2.5 Reported:** gap closure (G7, cross-half primary; paired second) for H_own and H_rest against L on W; both on MANC and
  MaleCNS. Reading: the share attributable to the stimulated types' own outputs vs the downstream network; if neither closes alone,
  the two interact (stated).

### Block 3: class of wiring difference (paired draws; MANC; MaleCNS for the most informative ones)

- **B3.1 Classes** of difference between W and M on the extended slot set (W = C ⊙ sign of the presynaptic neuron; C unsigned counts
  after the floor): for an entry (i, j) let a = C[i, j], b = C[m(i), m(j)]:
  1. **weights of connections present on both sides:** a > 0 and b > 0, both i and j matched (steps 1-3);
  2. **connections present on one side only:** exactly one of a, b > 0, both i and j matched;
  3. **neurons with no partner on the other side:** every entry with i or j unmatched or ghost, and those slots' size, sign and
     presence;
  4. **neuron size** of matched slots (size -> the partner's size; it sets excitability through the size scaling);
  5. **transmitter sign** of matched presynaptic slots (sign -> the partner's sign).
  Entries between self-mapped neurons are identical in W and M (no class). A hybrid takes the items of its chosen classes from M and
  the rest from W; all five together give M exactly (checked bit for bit; not simulated again: it is "L on M").
- **B3.2 Hybrids simulated (left side, seeds 0..7, paired draws):** each class alone (5) and each class left out (5).
- **B3.3 Reading rule (fixed now):** for class c with closure A_c (alone) and O_c (all but c): c **suffices** if its alone hybrid is
  at the ceiling (G7); c is **needed** if the left-out hybrid is a real gap (G7); c **contributes** if A_c's interval excludes 0 or
  O_c's interval lies below 1; if sum_c A_c differs from 1 by more than 0.2 (point estimates), the classes **interact** (non-additive)
  and the report says which pairs of alone/left-out results disagree, without choosing between them.
- **B3.4 MaleCNS repeats ("most informative", fixed now):** the alone hybrid with the largest A_c and the left-out hybrid with the
  smallest O_c; if both name the same class, also the alone hybrid with the second largest A_c (at most three hybrids), plus MaleCNS's
  W, M and relabelling control (from Block 2).

### Count noise (MANC only: pre-floor counts; paired draws, seeds 0..7)

- **B4.1 Raw counts:** the `synapse_count` (conf >= 0.4, neuPrint `weight`) of every pair of the MANC front-leg neurons in the
  processed `manc:v1.2.1` connections (autapses excluded, as in B1r's build); the network is rebuilt by BrainIR's builder with the node list, signs and sizes of B1r and a
  floor f; **floor 5 must reproduce B1r's matrix exactly** (checked before any noise run).
- **B4.2 Poisson:** every raw count c replaced by Poisson(c) (pairs with c >= 1; `default_rng(20261411)` and `(20261412)` for two
  copies), floor 5 applied, the left screen on each copy; agreement copy 1 vs copy 2 (cross-half primary, paired second), and each copy
  vs L on W.
- **B4.3 Dispersion measured from the data (negative binomial):** over unordered homologous connection pairs {(i, j), (m(i),
  m(j))} with i and j each matched or self-mapped (G4), not both self-mapped, counted once, with raw counts c_L, c_R (at least one
  >= 1): 1/k = sum(((c_L - c_R)^2 / 2 - mbar) * mbar^2) / sum(mbar^4) with mbar = (c_L + c_R) / 2 (least
  squares through the origin of the excess variance on mbar^2; the measured left-right dispersion, no reference to any screen); every
  raw count c >= 1 replaced by a negative-binomial draw with mean c and size k (`(20261421)`, `(20261422)`), floor 5, as B4.2. If the
  estimate of 1/k is <= 0, the dispersion model equals Poisson and is reported as such.
- **B4.4 Floors 1, 3, 5, 10:** the network rebuilt at each floor; L and R screens on each (L on W_f and L on M_f, paired), left-right
  agreement per floor with its own ceiling, closure relative to floor 5.
- **B4.5 "Reproduces the left-right agreement with no fitted parameter":** a noise model does if the observed left-right cross-half
  agreement (L on W vs R on W, paired design, seeds 0..7) lies inside the 95 % interval of that model's copy-vs-copy cross-half
  agreement. Reported for Poisson and for the negative binomial.

### B5. If Part A finds no real left-right gap

Blocks 2-3 and count noise then compare MANC with MaleCNS at the level of types: a "cross-fly hybrid" takes, for the chosen items,
the MaleCNS type-to-type value (A4(c): summed counts between the two types, divided equally over the MANC member pairs that already
connect the two types; types absent in one fly are class 3), with the same five classes defined on type pairs; the same reading
rules apply. This branch is described here so that it is fixed; it is run only if A7's condition holds.

### B6. Reporting for Part B

- Gap closure with its interval for every intervention (Block 1, Block 2, each Block 3 hybrid, each floor, each noise model), primary
  and paired forms.
- **Rescue table.** A **flipped type** (per design: Part A seeds 0..7 for Block 1; the paired baseline L on W vs R on W for Blocks
  2-3 and floors) is one whose band differs between the sides and whose fraction rhythmic differs by >= 0.5. A single intervention
  **rescues** a flipped type if after it the type is no longer flipped against R. Reported: per flipped type, the list of interventions
  that rescue it; per intervention, the share of flips it rescues alone.
- **Case studies (optional, first to drop):** for the 20 most flipped types (largest difference in fraction rhythmic, ties by name), a
  smallest set of Block 3 items (grouped by presynaptic neuron) whose transplant flips the left prediction to the right one, by plain
  delta debugging (ddmin) over those groups, seeds 0..7.

---

## Part C. Fixes (fixed list; no fitted parameter)

**C1. Procedure-level.**
1. **Dose-sweep scoring:** the type score is the best in-bounds score over the 19-current grid of B1.1 (no tuner).
2. **Pooled read-out (optional):** the accepted run's score is the rhythm score of the summed read-out signal (A6) in place of the
   mean over single motor neurons (tuning unchanged).

**C2. Network-level** (applied to the network before the screen; parameters drawn as usual on the fixed network).
3. **Lower floor:** floors 1 and 3 (two fixes, 3a and 3b). MANC only (no pre-floor MaleCNS counts), so criterion 2's cross-fly part
   cannot be evaluated and **fixes 3a and 3b cannot pass**; nor can the rewired control be floored (a rewired network has no
   pre-floor counts), so criterion 4 is not evaluated for them; they are reported on MANC's left-right agreement (stated now).
4. **Symmetrised:** for every pair of homologous entries (i, j), (m(i), m(j)) with i and j matched or self-mapped, both counts are
   replaced by their mean (a connection present on one side becomes half its count on both); signs and sizes unchanged; entries of
   unmatched neurons unchanged.
5. **Type-pooled:** each existing connection's count replaced by the mean count of the existing connections in its class: (5a) within
   side: class = (presynaptic type, its side, postsynaptic type, its side); (5b) across sides: class = (presynaptic type, postsynaptic
   type, whether the two sides are equal, different, or involve an unsided neuron). Neurons without a type form their own type. The set
   of connections is unchanged.
6. **Input-normalised:** for each neuron i of type B, its total incoming excitatory weight E_i and inhibitory weight I_i (absolute)
   are scaled to the mean over B's members (all sides, members with zero included in the mean); a neuron with E_i = 0 (or I_i = 0)
   keeps it; neurons without a type unchanged.
7. **Consensus annotations:** each neuron's size replaced by its type's median size (NaN ignored) and its transmitter sign by its
   type's majority sign (a tie keeps the neuron's own); neurons without a type unchanged.
8. **All network-level fixes together** that apply to both flies, in this order: 7, 4, 5b, 6 (floors excluded: MaleCNS).

**C3. Combined.** 9 = the passing procedure-level fix with the highest specific reproducibility together with the passing network-level
fix with the highest specific reproducibility (ties: the lower fix number). Not run if either list has no passing fix. Its runs
are C5's with the network fix applied and then the procedure fix (fix 1: the 19-current grid sweeps on the fixed network; fix 2:
the pooled score of the screens on the fixed network, traces stored), at its own DNg100 gain (C4).

**C4. Gain (DNg100 only).** Every fix is first run on the DNg100 pair (whole type, G1's whole-type variant; for fix 1 its best
in-bounds score over the grid; for fix 2 its pooled score), seeds 0..15, on both flies, at gain 1 (all synaptic weights times g). It
**passes** if DNg100 scores >= 0.5 in >= 12 of 16 seeds on both flies (unusable counts as < 0.5). If it fails at gain 1, the gains 0.5,
0.75, 1.5, 2 and 3 are run and the smallest passing gain is used for every run of that fix; if none passes, the fix fails and is not
screened further. Unfixed: run 2's calibK (K = 1: MANC 16/16, MaleCNS 13/16) passes. All gains are fixed from one DNg100-only campaign
before any other run of the fixes is published; fix 9's gain, if it needs one, comes from a second DNg100-only campaign before its
screens. DNb08 is reported, never used.

**C5. Runs per fix (analysed set, seeds 0..7, unpaired draws):** the four half-flies (MaleCNS halves for every fix except 3a/3b), and
the **rewired control**: MANC rewired by run 1's degree-preserving generator with network seed 101 (`controls.build`, the network of
B1-ctl-rewire-101), the fix then applied to it, left side. The unfixed reference is Part A (seeds 0..7) plus the unfixed rewired
control (a new campaign) and, for fix 1, the grid sweeps of Block 1 plus a grid sweep of the rewired control.

**C6. A fix "restores reproducibility" only if all four hold** (point estimates unless stated):
1. **Control:** C4 passes.
2. **Agreement:** cross-fly agreement = the mean of the two same-side cross-fly pairs (rho_x and c each averaged over MANC-L/MaleCNS-L
   and MANC-R/MaleCNS-R); ratio >= 0.80. Left-right (mean over the two flies of rho_x and of c) ratio >= 0.80 too where the fix leaves
   the sides distinct (fixes 1, 2, 3, 5a, 6, 7; not 4, 5b, 8, whose left-right numbers are reported only).
3. **Still informative:** the mean over the four half-flies of the number of driver types is between 0.5 and 2 times the unfixed mean
   (Part A seeds 0..7, analysed set).
4. **Still about the wiring:** specific reproducibility SR = rho_x(MANC-L, MaleCNS-L) - rho_x(MANC-L, rewired MANC-L), both under
   the fix; its 95 % interval lies above 0; and the rewired control has **at most 2 driver types ("few")** on the analysed set. The
   number 2 is run 1's largest driver count among its five unfixed rewired controls (B1 procedure, 321 types); the unfixed one-sided
   rewired control's own count is reported beside it, and the number is not changed whatever it shows.
Every fix is reported, pass or fail, with all four numbers. **The robust model** = the passing fix (C2 or C3) with the highest SR point
estimate; if none passes there is no robust model.

---

## Part D. Exams re-scored (EXPLORATORY, after unblinding)

Each table is headed "exploratory, after unblinding". Each variant is scored once by a new write-once script
(`ledger/scripts/posthoc/rescore_v4.py`, outputs opened with mode "x"; it calls the frozen scoring functions and never creates an
unblinding flag).
- **Exam 1:** for each fix, the whole-type screen (G1) on the fixed MANC network at the fix's gain, all 321 B1r types, seeds 0..7 (fix
  1: whole-type grid sweeps; fix 2: pooled score of whole-type runs that store the summed signal); AUROC on run 2's primary set (labels
  v2, as RESULTS_1) with run 2's frozen AUROC and bootstrap functions; compared with the unfixed B1r on seeds 0..7 and with the two-hop
  signed count S2 (0.669).
- **Exam 2:** only for the robust model and only if at least 60 runner-hours remain after Part C: the fix applied to the full cord
  (same definitions; mirror map from the full-cord table), H-M's procedure, 43 units, seeds 0..7; scored with run 3's frozen
  identification function against run 3's consensus; compared with H-M on seeds 0..7 and H-S-k2-signed. Otherwise not run, stated.

---

## Part E. The forward ledger (`research/ledger/forward/`)

- **E1. Types:** every MANC excitatory DN type among A1's 321 with at least one driver line whose `manc_type` is that type in the kit's
  map (`kit_v2/driver_lines.csv`; rows marked ambiguous do not count) and **no clear front-leg label in exam 1** (labels v2
  `type_labels.csv`: `front` not yes/no, or no row).
- **E2. Sources:** the authors' model (A1, locked `predictions/A1/types.csv`, `primary_score`), two-step signed counting (locked
  `predictions/S/types.csv`, `S2_twohop_signed`), and the robust model (its exam 1 whole-type screen, Part D; required if a robust model
  exists). If no fix passes, two sources, and the ledger says why.
- **E3. Probabilities (labels used for this only: training on past results to predict future ones, stated as such):** predictor x =
  the percentile rank (average ties) of the type's score among the source's 321 types; P(yes) = 1 / (1 + exp(-(a + b x))) fitted by
  maximum likelihood (Newton; if it fails to converge in 100 iterations or |b| > 100, Firth's bias-reduced likelihood) on exam 1's
  labelled types (run 2's primary set: clear front-leg label, among A1's 321, not exposed). Fit set: the types whose `best_preparation`
  is `headless` if there are at least 15 of them with both classes present, else all labelled types (stated which). Calibration:
  leave-one-out probabilities over the fit set -> Brier score, the leave-one-out base-rate Brier score, log loss, AUROC, and a 3-bin
  reliability table; the atlas caveat is printed next to it (21 of 25 "yes" types of exam 1 rest on the atlas alone, which gives no
  "no").
- **E4. Sentences:** one per (type, source), generated by script from the locked numbers only, e.g. "Activating DNxx (lines: ...) in a
  decapitated fly: the <source> gives a p % chance of rhythmic front-leg stepping."
- **E5. Stability flags** per type and source (`agree` / `disagree` / `not computed`): authors' model: two flies = B1r vs B2r band;
  two sides = Part A MANC-L vs MANC-R band. Two-step count: S2 computed per fly (R2) and per side (A4a), tercile among the common types
  equal or not. Robust model: two flies = its MANC-L/MaleCNS-L and MANC-R/MaleCNS-R bands both equal; two sides = its MANC-L vs MANC-R
  band (Part C runs; types outside the analysed set `not computed`).
- **E6. Decisive experiments:** among ledger types, the 15 (ties by name) with the largest max over source pairs of |p_i - p_j|,
  counting a pair only if both sources' flags are `agree` on both flags. For each: driver-line IDs (kit), the collection named by the
  line (Janelia split-GAL4 `SS` lines: FlyLight split-GAL4 collection; `R` / GMR lines: Janelia GAL4 at Bloomington; `VT`: Vienna Tiles;
  else as written in the source), whether the line is listed as available in that collection's public catalogue (looked up by a fresh
  agent with the URL and date recorded; `not checked` if the lookup fails), each source's probability and sentence, and a five-line test
  protocol (one template filled by script: driver x UAS-CsChrimson, decapitated, all-trans-retinal, 1 s light pulses, scored for
  rhythmic front-leg stepping blind to genotype).
- **E7. Scoring rule:** future results are scored per source by the Brier score against a base-rate guesser (the exam 1 base rate of
  the fit set).
- **E8. Honesty line (printed in the ledger):** these predictions are made after both exams were unblinded; they are clean with respect
  to the experiments they predict, because those have not been done.
- **E9. Gates (Stage 6):** determinism of every campaign used; every sentence generated by script from a locked number; a fresh reviewer
  checks ten entries (`default_rng(20261461)`) by hand against the tables; then `LOCK_forward_v1.json`, tag `ledger-forward-v1`.

---

## Part F. Results and documents (Stage 7)

`results/RESULTS_3.md` (first line: what causes the gap, or that the cause was not found), the adversarial review (fresh reviewer:
`RESULTS_3.md` and the locked tables, one instruction: find the most plausible way the headline is an artefact and test it if cheap;
committed once; answered in an addendum file), `BRIEF.md` (two pages, one figure: agreement across sides and flies for wiring,
simulation and each fix, ceilings marked; every number from a locked file; a fresh reviewer marks overclaims), `EVIDENCE_MAP.md` (one
row per claim of the brief: claim, locked file and field, tag, main caveat). Alternative explanations in RESULTS_3, one row each with
its test: seed noise (G6 ceilings), ties among zero scores (G6a, non-zero types), the one-sided regime being noisier in itself (A2
ceilings vs R1's whole-type ceilings), mismatched homologs or wrong side labels (G3 check, uncorrected types, B2.3), unequal member
counts (G6b), one side worse everywhere (A3), where the tuner lands (Block 1), our implementation (A0 vs Part A; B2.4).

---

## Part X. Process

- **X1. Platform.** GitHub Actions hosted runners only, run 2's pins and numerics environment; the Mac runs no prediction (it failed the
  identical-digest rule in run 3). Run 4 uses copies with one change each where needed: `jobs_v4.py` (new kinds; other kinds delegate
  to `jobs_v3.run_job`), `gha_runner4.py` (imports `jobs_v4.run_job`), `.github/workflows/ledger-gha4.yml` (tags `gha4-*`; the random
  key is written as 64 hex characters, fixing L82's 1-in-256 newline failure), `gha4.py` (builders, publish4, collect4, feeder).
  **Queue:** at most 20 GitHub jobs queued plus running at a time (the feeder counts jobs); campaigns are chunked so that one campaign
  has at most 20 jobs. **Cap:** 300 runner-hours (step time, as L102); the running total is logged after each stage.
- **X2. Pre-freeze tests** use synthetic circuits and locked re-runs only; no new job kind runs on a real network before the tag. The
  pipeline test after the tag (before Part A): the R4 reproduction (A1) through the new runner.
- **X3. Determinism.** For every campaign, 20 jobs drawn with `default_rng(20261405)` are re-run in a separate determinism campaign per
  stage; digests (`digest_v4`) must be identical.
- **X4. Amendments** (`lock4.py amend`, ledger `AMENDMENTS_v4.jsonl`): code bug fixes only (code made to do what this text says),
  recorded before the commit and before the data they affect are produced; never a rule, a criterion or a file an earlier lock hashes.
- **X5. Locks.** `LOCK_prereg_v4.json` (this file, the prompt, run 4 code, gates_v4, diag_v4, reviews_v4, hashes of all earlier
  locks); `LOCK_reliability_v2.json` (Parts A0-D outputs under `reliability_v2/` and `results/run4/`, campaigns' provenance, code);
  `LOCK_forward_v1.json` (`forward/`, code). Each lock is committed alone, once; tags `ledger-prereg-v4`, `ledger-reliability-v2`,
  `ledger-forward-v1`; pushed with the branch (never `main`, never forced); OpenTimestamps for each lock.
- **X6. Reviews** (fresh agents; each report committed once, later thoughts in an addendum file): the rulebook audit before the tag,
  including the mirror and hybrid code; the ten-entry ledger check (E9); the adversarial review; the brief's overclaim check.
- **X7. Pre-mortems** in the LOG before each lock, each tag push and each irreversible step.
- **X8. Order.** A0, A, Block 1, Block 2, Block 3 and count noise, C, D; the LOG says after each what the result means for the next.

**X9. Budget (runner-hours, estimated from 21 s per MANC screen job, 3 s per MaleCNS job, 4 workers per runner; analysed set assumed
260 types) and cut order.**

| item | estimate |
|---|---|
| Part A (4 half-flies x 16 seeds) | 20 |
| Block 1 (grid + transplant, 4 half-flies) | 21 |
| Block 2 (W, M, R on W, H_own, H_rest, relabelling; both flies) | 21 |
| Block 3 (10 MANC hybrids; MaleCNS repeats) | 32 |
| Count noise (2 Poisson, 2 NB, floors 1, 3, 10) | 35 |
| Part C (unfixed rewired; 8 fixes x [MANC + MaleCNS + rewired + DNg100]; fix 1 rewired sweep; fix 9) | 110 |
| Part D exam 1 (whole type per fix) | 37 |
| total | about 276 |

Re-budgeted after Part A with the real analysed-set size. If the projected total exceeds 280: the analysed set's random part is cut to
25 types; then items are dropped in this order: the case studies, the pooled read-out, the MaleCNS repeats of Block 3, the floors other
than 1 and 5 (B4.4 floors 3 and 10, fix 3b), Part D, the count-noise models (B4.2-B4.3), fixes 6 and 7, the brief. Never dropped: this
rulebook, Part A0, Part A with ceilings, Block 1, Block 2, the forward ledger.

**Departures from RUN4_PROMPT, each with its reason.** (1) Ceilings and agreements use the cross-half form (G6), so that the
comparison and its ceiling have the same number of seeds per mean; full-seed agreement is reported beside it. (2) Paired draws only in
Blocks 2-3 and count noise; Block 1 and Part C use the unchanged procedure (Block 1 reuses Part A's tuned currents and parameters).
(3) MANC seeds 0..3 are R4's runs, reused after a 100-job reproduction check through run 4's runner (A1). (4) MaleCNS DN sides come from the output side (G3):
MaleCNS annotates only the brain soma side for DNs, which disagrees with the nerve-cord output side for 40 % of them. (5) Floors and
count noise on MANC only, and fixes 3a/3b cannot pass criterion 2 (no pre-floor MaleCNS counts). (6) Fix 8 excludes the floors (same
reason). (7) The full-transplant check has a tolerance set by a relabelling control (B2.3-B2.4), because a relabelled matrix sums in
another order. (8) "Few" = 2 driver types (C6.4), from run 1's unfixed rewired controls. (9) The dose grid covers B1r's range with the
top extended one doubling for half groups (B1.1). (10) Fix 5's type pooling keeps the set of connections (no densification); fix 6
scales each neuron's inputs to its type mean. (11) Exam 2 is re-scored only for the robust model and only if 60 runner-hours remain.
