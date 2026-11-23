Verdict: 3 items marked

# Third overclaim review of BRIEF.md (run 4, the two-page version)

Fresh reviewer, read-only. Brief as of commit 70329c9 (unchanged while this review was written). Paths are relative to `research/ledger/`.

Read: `BRIEF.md`, `EVIDENCE_MAP.md`, `results/RESULTS_3.md`, `PREREG_v4.md` (Part Q, G1-G10, A0-A7, B1-B6, C1-C6, E1-E9, X), `RUN4_PROMPT.md` (sections 3, 5, 8, 10), `AMENDMENTS_v4.jsonl`, `reviews_v4/ADVERSARIAL_REVIEW_v4.md` and `ADVERSARIAL_ADDENDUM_v4.md`, both earlier overclaim reviews and `BRIEF_OVERCLAIM_ADDENDUM_2.md`, LOG rows L136-L156. Opened with python3: the JSON under `reliability_v2/`, `gates_v4/` and `results/run4/`; `forward/` (README, notes, CSVs, `CALIBRATION.json`); `kit_v2/driver_lines.csv`; `labels_v2/type_labels.csv`; `predictions/A1/types.csv`.

Every number in the brief matches its source file (table at the end). Lengths below are counted in characters of the Markdown source. Each suggestion is the same length or shorter within its own paragraph, and the words cut to make room are named.

## Items

1. **(a, c) The decisive list is not "the 15 where they disagree most".**
   - Quoted: "The 15 where they disagree most, by only 0.05-0.28:"
   - Problem:
     - The pre-registered rule (E6) ranks only types whose stability flags read `agree` for both sources on both flags (two flies, two sides).
     - 20 of the 63 ledger types qualify. `DECISIVE.csv` is the top 15 of those 20, not the top 15 of the 63.
     - Over all 63 types:
       - The two largest disagreements are larger than the brief's stated maximum of 0.28: DNg35 (0.305) and DNa13 (0.296). Both are left out because the authors' model's two-fly flag reads "disagree".
       - Only 5 of the 15 largest gaps are in the list.
       - 33 types outside the list have a larger gap than its last entry.
     - So a reader takes the table for the largest disagreements and the range for the largest in the ledger. The reader is also not told that the list keeps only predictions that are stable across sides and flies. That matters in a brief about whether the screen agrees across sides and flies, and the model's flags come from our replication, not the authors' runs.
   - Evidence:
     - `forward/LEDGER.csv` (fields `p_rhythmic`, `flag_two_flies`, `flag_two_sides`):

       | type | `authors_model` `p_rhythmic` | `two_step_count` `p_rhythmic` | gap | `authors_model` `flag_two_flies` |
       |---|---|---|---|---|
       | DNg35 | 0.765 | 0.460 | 0.305 | disagree |
       | DNa13 | 0.800 | 0.503 | 0.296 | disagree |

       20 of the 63 types have all four flags `agree`.
     - `forward/DECISIVE.csv` `gap` runs from 0.280 (DNg43) to 0.049 (DNp15).
     - By gap among all 63 types, the 15 rank 3, 4, 6, 7, 12, 19, 23, 31, 32, 35, 36, 42, 45, 47 and 48.
     - `PREREG_v4.md` E6: "the 15 (ties by name) with the largest max over source pairs of |p_i - p_j|, counting a pair only if both sources' flags are `agree` on both flags".
     - `RUN4_PROMPT.md` section 5: "counting only predictions that are stable across the half-flies".
     - `forward/README.md`: the model's flags "come from our replication of it ... not from the authors' own runs".
   - Suggested: "Of side- and fly-stable types, the 15 most divergent, by only 0.05-0.28:" (+21).
     - Room in the same paragraph:
       - ", because no fix passed:" -> " (no fix passed):" (-7);
       - "made before the experiments they predict" -> "made before being tested" (-16).
     - Paragraph total: -2.
     - Evidence-map rows 23 and 24 quote the changed wording and need the same edits. Row 24 should also cite the E6 stability rule.

2. **(c) Block 1: "closes ... 0.17 in MANC" for a closure that cannot be told from zero.**
   - Quoted: "Scoring the best of a fixed grid of currents instead of the tuner closes 0.36 of the gap in MaleCNS (0.08-0.61) and 0.17 in MANC (-0.07 to 0.38), partly by lowering seed noise (against its own ceiling, MaleCNS agreement rises only from 0.58 to 0.65)."
   - Problem:
     - The interval is printed. The issue is the verb, and the reading that was dropped.
     - "Closes ... 0.17 in MANC" asserts a MANC closure. The pre-registered procedure share (B1.4) does not establish one: its interval includes 0, and RESULTS_3 reads it as indistinguishable from zero.
     - History of this fix:
       - The first overclaim review's item 8 asked for that reading.
       - Addendum 2, section 3, restored it ("not distinguishable from 0").
       - The two-page cut removed it, while addendum 2, section 4, still lists item 1-8 as kept.
     - A ten-minute reader takes 0.17 as the tuner's share of the MANC gap.
   - Evidence:
     - `reliability_v2/B1_MANC.json` `primary_homolog_consistent.procedure_share_of_gap`: `closure` 0.166, `interval` [-0.069, 0.378].
     - `reliability_v2/B1_MaleCNS.json`:
       - same field: `closure` 0.363, `interval` [0.079, 0.608];
       - `tuner_free.best_in_bounds.closure_vs_tuned.before.primary.ratio` 0.579 and `.after.primary.ratio` 0.654 (`c` 0.852 and 0.953).
     - `results/RESULTS_3.md` section 3.1, reading: "an amount indistinguishable from zero in MANC".
     - `reviews_v4/BRIEF_OVERCLAIM_REVIEW.md` item 8 (its suggested wording).
     - `reviews_v4/BRIEF_OVERCLAIM_ADDENDUM_2.md` section 3 ("'not distinguishable from 0' for MANC's Block 1 closure") and section 4, row 1-8 ("kept").
   - Suggested: "Scoring the best of a fixed grid of currents instead of the tuner closes 0.36 of the gap in MaleCNS (0.08-0.61), partly by lowering seed noise (against its own ceiling, agreement rises only from 0.58 to 0.65), but not demonstrably any in MANC." (-7; the MANC numbers stay in evidence-map row 16.)

3. **(c) Block 3: two closures side by side, without the pre-registered "interact".**
   - Quoted: "In MANC, mirroring one-sided connections closes 0.29 (0.06-0.49) and unpartnered neurons 0.25 (0.06-0.42); no single class closes the gap."
   - Problem:
     - Next to each other, the two closures invite adding them (about half the gap) or reading them as shares of the gap.
     - Three sources say they cannot be read that way:
       - the pre-registered reading (B3.3) finds that the classes interact;
       - RESULTS_3's first caveat says the closures "cannot be read as a decomposition";
       - evidence-map row 17 gives "the classes interact" as this claim's caveat.
     - By the same reading, homologous weights and neuron size also contribute in combination. The two named classes are therefore not the whole account. "No single class closes the gap" says neither of these things.
   - Evidence: `reliability_v2/B3_MANC.json` `primary_homolog_consistent`:
     - `A2.closure.closure` 0.289 (`closure_interval` [0.060, 0.486]);
     - `A3.closure.closure` 0.250 ([0.060, 0.422]);
     - `reading.sum_alone` 0.614;
     - `reading.interact` true;
     - `reading.per_class[c].suffices` false for c = 1-5;
     - `reading.per_class["1"].contributes` and `reading.per_class["4"].contributes` true;
     - `O1.closure.closure` 0.546 ([0.332, 0.724]);
     - `O4.closure.closure` 0.812 ([0.657, 0.951]).

     Rules: `PREREG_v4.md` B3.3 ("if sum_c A_c differs from 1 by more than 0.2 (point estimates), the classes interact (non-additive)"); `results/RESULTS_3.md` section 8, caveat 1.
   - Suggested: "In MANC, mirroring one-sided connections closes 0.29 (0.06-0.49) and unpartnered neurons 0.25 (0.06-0.42); none suffices (classes interact)." (+2).
     - Room in the same paragraph: "one floor was judged on MANC only and one dropped for budget" -> "one floor was judged on MANC only, one dropped for budget" (-3).
     - Paragraph total: -1.

## Checked, not marked

### Every number in the brief, against its source

| brief | file : field | value |
|---|---|---|
| 0.63 (0.53-0.72) | `reliability_v2/A0.json` : `A0.primary_one_member_each_side.primary.ratio`, `.bootstrap.interval.ratio` | 0.628, [0.531, 0.718]; words "a real gap" |
| 0.59 (MANC), 0.64 (MaleCNS) | `reliability_v2/A.json` : `six_agreements_primary_homolog_consistent[pair].primary.ratio` | 0.587, 0.642 |
| across flies 0.32-0.50 | `reliability_v2/A.json` : same field, cross-fly pairs | 0.410, 0.317, 0.317, 0.496 |
| same-side pairs agree no better | `reliability_v2/A.json` : `same_side_minus_opposite_side_cross_fly` | same 0.316, opposite 0.357, `difference` -0.040, `ci95` [-0.103, 0.019] |
| 0.48; 0.47; the test is met | `reliability_v2/NOISE.json` : `primary_homolog_consistent.poisson.copy_vs_copy`, `.observed_left_right_paired_design`, `.poisson.reproduces_left_right` | ratio 0.484 (rho_x 0.400, interval [0.291, 0.505]); ratio 0.469 (rho_x 0.372); true |
| 0.36 (0.08-0.61); 0.17 (-0.07 to 0.38); 0.58 to 0.65 | `reliability_v2/B1_*.json` : `tuner_free.best_in_bounds.closure_vs_tuned` | 0.363 [0.079, 0.608]; 0.166 [-0.069, 0.378]; ratio 0.579 to 0.654 |
| 0.29 (0.06-0.49); 0.25 (0.06-0.42); no class suffices | `reliability_v2/B3_MANC.json` : `A2`, `A3`, `reading.per_class[*].suffices` | 0.289 [0.060, 0.486]; 0.250 [0.060, 0.422]; false x5 |
| six judged and failed (0.31-0.39), two broke the control, one floor MANC only, one dropped, fix 9 not run | `reliability_v2/C.json` : `passing`, `primary[fix].cross_fly.ratio`, notes; `gates_v4/C_GAINS.json` : `fixes[*].verdict` | `passing` []; fixes 1, 2, 4, 5a, 5b, 7: 0.313, 0.333, 0.392, 0.391, 0.378, 0.322; 3a not evaluable; 3b not evaluated; 6 and 8 fail at every gain; 9 not run |
| 307 of 321, 219 of 328 | `reliability_v2/A.json` : `type_counts` | as quoted |
| 63 types | `forward/LEDGER.csv` | 63 types, 126 rows |
| Brier 0.248, 0.239, base rate 0.242 | `forward/CALIBRATION.json` : `sources.*.brier_loo`, `.brier_base_rate_loo` | 0.24776, 0.23945, 0.24238 |
| AUROC 0.33, 0.61 | `forward/CALIBRATION.json` : `sources.*.auroc_loo` | 0.334, 0.611 |
| base rate (0.64) | `forward/CALIBRATION.json` : `base_rate` | 0.641 |
| the 15 table rows | `forward/DECISIVE.csv`, `LEDGER.csv`, `AVAILABILITY.csv` | all match, including each "k of n" and the order |
| 9 of the 15 score 0, mapped to 0.59; highest 0.13 | `forward/LEDGER.csv` (`authors_model`) | 9 at 0.000, mapped to 0.589; DNp56 0.130 |
| none for four types | `forward/AVAILABILITY.csv` : `listed_available` | DNp34, DNp35, DNg87, DNad006 |
| ten on FlyBank only | `forward/AVAILABILITY.csv` : `note` | 10 |
| seven lines name another DN type | `kit_v2/driver_lines.csv` : `manc_type`, `other_cells` | SS01553, SS01588, SS82228, SS58304, SS95034, SS88264, SS12653 |
| 2026-11-22 | `forward/AVAILABILITY.csv` : `date_checked` | all 59 rows |
| figure | `results/run4/fig_agreement.json` : `rows` | matches `WIRING_A4.json` (two-hop signed: 0.810 and 0.756) and `C.json` (model 0.448 against c 0.813; 0.258 against c 0.817) |

### Locks, tags and timing

- The cited files match the hashes in their locks:
  - `LOCK_reliability_v2.json`: `reliability_v2/` (16), `results/run4/` (5), `gates_v4/` (15);
  - `LOCK_forward_v1.json`: `forward/` (8);
  - `LOCK_labels_v2.json`: `kit_v2/` (19).
- The four tags exist:
  - `ledger-prereg-v4` badc4d7;
  - `ledger-reliability-v2` d81668b;
  - `ledger-forward-v1` c3ffcfa;
  - `ledger-labels-v2` 7992bd6.
- `PREREG_v4.md.ots` and `LOCK_prereg_v4.json.ots` carry Bitcoin attestations.
- "Frozen before any simulation of this run" holds:
  - The freeze commit (badc4d7, 2026-11-21 18:24:32) precedes `A0.json` (f68a3fa, 18:27), the R4 reproduction (52ac021, 18:39) and `A.json` (f338e3e, 18:53).
  - The pre-freeze runs were locked re-runs and synthetic circuits only (`gates_v4/P4_PIPELINE*.json`, `TRUST_GATE_v4.json`), as X2 allows.

### Observations that do not meet the marking tests

The first is a slip worth fixing at no cost.

- **The ask's order.** "decapitate, feed all-trans-retinal" reverses the locked protocol, and a decapitated fly cannot feed.
  - `forward/DECISIVE.csv` `protocol`: adults are raised 3-5 days on retinal food and then decapitated.
  - "feed all-trans-retinal, decapitate," has the same length.
- **"No fix worked".** The sentence itself accounts for fixes 3a, 3b, 6, 8 and 9. "No fix passed" has the same length and matches C6 and the brief's later "because no fix passed".
- **Figure caption.**
  - Addendum 2, section 4 (row 1-5), says the caption gives the scale of the wiring points. That holds only in part:
    - The caption says "raw Spearman, not the ratios", and the legend gives the wiring ceiling of 1.
    - Nothing says the wiring points are type-level two-hop sums, while about half of single homologous connections exist on one side only (`reliability_v2/WIRING_A4.json` `single_connections.MANC.share_one_side_only` 0.508, `.MaleCNS.` 0.515).
  - Not marked, because read with result 3 and the Block 3 sentence the figure still points to the right conclusion: differences between single connections, which the sums hide, move the screen.
  - If wanted: "*Raw Spearman agreement (not the ratios above); bars mark ceilings; wiring = type-level two-hop sums.*" (-8). The figure's legend already gives the colour key.
  - The figure's title says "primary types", but its wiring rows use all matched types (`WIRING_A4.json` `summaries_S1_S7_full_spearman`, n 308, 250, 245).
- **"Not shared".** The upper end of the interval (+0.019, `A.json`) bounds any shared part to a small one. Fair as worded.
- **"A larger one across flies".** No pre-registered test compares the two gaps. But all four cross-fly ratios (0.32-0.50) lie below both left-right ratios. Two cross-fly intervals ([0.180, 0.447] and [0.172, 0.458]) lie wholly below both left-right intervals ([0.485, 0.681] and [0.528, 0.741]; `A.json`).
- **Result 3.**
  - B4.5 names the difference as the number to read: observed minus Poisson copy-vs-copy -0.029, [-0.162, 0.102] (`NOISE.json` `primary_homolog_consistent.poisson.observed_minus_copy_vs_copy`). The brief states only the verdict.
  - "Almost as much" and the post-hoc "most of the gap, not demonstrably all" keep the reader from over-reading the near-equality of 0.48 and 0.47.
  - The brief does not say that noise on the scale of reconstruction error was not tested (adversarial review, point 8), but it makes no claim about reconstruction error.
- **Departures.**
  - `AMENDMENTS_v4.jsonl` holds the seven code and cost amendments.
  - The departures from the prompt are listed in `PREREG_v4.md` (end of Part X; X1 for Modal).
  - The post-lock Part D screens and the Modal cap of $41 (set in the wrapper `posthoc/modal4b_v4.py`) have no amendment row; they are recorded in LOG L145-L148.
  - Nothing in the brief rests on them, and the brief names the re-scores as exploratory.
- **"Budget-cut subset".** The analysed set is the pre-registered informative set (237 types) plus a random sample. The budget rule cut the random part from 41 to 25 (`reliability_v2/ANALYSED_SET_X9.json` `n_informative` 237, `n_random_kept` 25), so "budget-cut" describes only the random part.
- **The model column.**
  - 13 of the 15 decisive types are in the authors' screen's non-driver band (`predictions/A1/types.csv` `band`; score below 0.05).
  - Four of them (DNg43, DNp26, DNg87, DNp44; scores 0.01-0.04) are mapped by the fit to 0.68-0.72, above the base rate. A "yes" for them would score for "the authors' model" although its screen called them non-drivers.
  - "None is a driver (highest 0.13)" gives the reader what is needed.
- **Result 1's type set.** A0's primary subset is the 250 MANC types with one member per side, not the homolog-consistent set named in the scope sentence. The two sets nearly coincide: 307 of the 308 matched MANC types are homolog-consistent.
- **"Base rate 0.242".** In the calibration parenthesis this is the base-rate guesser's leave-one-out Brier score; "the base rate (0.64)" in the note is the base rate itself. Readable in context.

### The earlier reviews' fixes

Of the items addendum 2, section 4, lists as kept, all hold in this text except three:
- 1-8 does not hold (item 2 above);
- 1-11 holds only in part (item 3);
- 1-5's claim about the caption holds only in part (observation on the figure caption).

Nothing was edited except this file.
