**In a third animal (BANC), not screened before the rules were frozen [corrected 2026-11-23, see Corrections], the simulated screen again disagreed across animals: its cell-type scores agreed with MANC's at 0.35 and with MaleCNS's at 0.50 of the agreement each screen has with itself (95 % intervals 0.20-0.49 and 0.38-0.62; MANC with MaleCNS 0.31, post hoc, on the same 181 types), so the gap between animals was confirmed in the third animal, with a pre-registered caveat: BANC's wiring of these types also agrees with the other animals' less than theirs does with each other, so part of the gap may come from the build or the type match.**

# BrainIR prediction ledger, results 5 (run 6: the third animal)

Rules: `PREREG_v6.md` (tag `ledger-prereg-v6`, frozen before any BANC screen). Results: `LOCK_thirdfly_v1.json` (tag
`ledger-thirdfly-v1`; `thirdfly_v1/C_tests.json`, tables generated in `thirdfly_v1/C_tables.md`). The first two animals' post hoc numbers:
`LOCK_posthoc_v6.json` (tag `ledger-posthoc-v6`; `posthoc_v6/`). Every word below is the rulebook's, on the sets without DNg100.

**The procedure that carries the results.** The tuned procedure (the one the first two animals were screened with, its one setting
unchanged) failed its pre-registered positive control in BANC: DNg100 scored at least 0.5 in 11 of 16 random draws, and the bar was 12.
By the rule fixed before the screen, the current sweep (19 fixed currents, best score inside the activity bounds; DNg100 8 of 8) became
primary for the cross-animal tests C3, C4 and C6-C8, for all three animals. The tuned versions are reported beside them.

## The tests

| Test (pre-registered) | Words | Numbers |
|---|---|---|
| **C1** left vs right copies in BANC (180 types) | a real gap | 0.58 of the ceiling (0.38-0.77); MANC 0.59, MaleCNS 0.64 (run 4) |
| **C2** count noise in BANC | does not reproduce it | two copies with resampled synapse counts agree at 0.78 (0.64-0.89); left vs right 0.58; difference in agreement -0.21 (-0.37 to -0.05) |
| **C3** across animals (sweep, 181 types) | confirmed in the third animal (wiring caveat) | MANC-BANC 0.35 (0.20-0.49), MaleCNS-BANC 0.50 (0.38-0.62); MANC-MaleCNS 0.31 (0.17-0.45, post hoc). Tuned, beside: 0.32, 0.44, 0.40. Wiring (two-step signed counts, 5-synapse floor): BANC vs MANC 0.61, vs MaleCNS 0.63, below the 0.71 floor; MANC vs MaleCNS 0.82 |
| **C4** our MANC list in BANC (202 types) | above chance | 5 of 17 hits recur (0.10-0.56); 20 BANC hits; 1.7 expected by chance; p = 0.016 |
| **C4** the authors' list in BANC (202 types) | at chance at the authors' cut | 1 of 6 recurs (0.00-0.64); 0.6 expected; p = 0.47 |
| **C4** our MaleCNS list in BANC (182 types) | above chance | 12 of 60 recur (0.11-0.32); 6.3 expected; p = 0.004 |
| **C5** DNg100 (tuned) | pass | type score 0.64 (11 of 16 draws >= 0.5); each copy alone 13 of 16; sweep 0.92 |
| **C5** DNb08 (no prediction) | (none) | whole type tuned 0.00, sweep 0.25; each of its four copies alone 0 of 16 (the authors' copy, position 2446, included); the authors report 0.000 |
| **C6** does pooling two animals predict the third? (181 types) | not shown | pooled vs MANC alone +0.20 (0.08 to 0.32); pooled vs MaleCNS alone +0.02 (-0.03 to 0.07) |
| **C7** how many connectomes? | (an estimate) | mean cross-animal agreement 0.39 of the ceiling; Spearman-Brown: 6.3, so 7 animals (4.3 to 9.7) to reach 0.8; an extrapolation that assumes exchangeable animals |
| **C8** does stability under count noise predict the third animal? (12 types) | stability under count noise predicts the third animal | Spearman 0.57, one-sided p = 0.029 (with DNg100 0.64; without DNb08 0.54; given the MANC score 0.56) |

"At chance" in C4 means the overlap could not be told apart from chance by a test of low power; it does not show that the hits fail to
recur. "Confirmed" in C3 says nothing about size; the ratios do.

## Hits shared across animals (sweep, three-animal set; full table `thirdfly_v1/C_tables.md`)

~~29 of the 182 types are hits (score >= 0.5) in at least one animal under the sweep; 12 in at least two; 3 in all three.~~
**Corrected 2026-11-23 (post hoc, `LOCK_paper_posthoc_v1`):** under the sweep, 71 of the 182 types are hits in at least one animal, 22 in
at least two and 4 in all three: DNg100, DNxl092, DNa13 and DNxl134. The table below is C5's table as pre-registered: it lists only
types that are hits under the current-setting procedure in MANC, MaleCNS or BANC, or in the authors' whole-type screen, so it misses
hits found only by the sweep (DNxl134 among them). The full sweep table is `paper_posthoc_v1/THREE_ANIMAL_SCORES.csv`.

| Type | MANC | MaleCNS | BANC | tuned: MANC / MaleCNS / BANC | authors' screen (MANC) |
|---|---|---|---|---|---|
| DNg100 | 0.81 | 0.98 | 0.92 | 0.83 / 0.67 / 0.64 | 0.90 |
| DNa13 | 0.74 | 0.84 | 0.56 | 0.42 / 0.62 / 0.00 | 0.46 |
| DNxl092 | 0.75 | 0.85 | 0.54 | 0.40 / 0.84 / 0.00 | 0.47 |
| DNp63 | 0.99 | 0.89 | 0.06 | 0.79 / 0.00 / 0.00 | 0.00 |
| DNa07 | 0.99 | 0.92 | 0.00 | 0.86 / 0.42 / 0.00 | 0.84 |
| DNb08 | 0.80 | 0.83 | 0.25 | 0.61 / 0.78 / 0.00 | 0.63 |
| DNg13 | 0.06 | 0.73 | 0.98 | 0.29 / 0.74 / 0.94 | 0.14 |
| DNfl015 | 0.00 | 0.97 | 0.77 | 0.00 / 0.86 / 0.56 | 0.00 |
| DNfl025 | 0.70 | 0.21 | 0.80 | 0.15 / 0.07 / 0.55 | 0.19 |
| DNxn151 | 0.06 | 0.68 | 0.77 | 0.31 / 0.67 / 0.61 | 0.01 |
| DNxn118 | 0.52 | 0.92 | 0.00 | 0.44 / 0.90 / 0.00 | 0.39 |
| DNp71 | 0.63 | 0.76 | 0.02 | 0.44 / 0.56 / 0.01 | 0.47 |

DNg100's recurrence is never evidence: the tuned procedure's one setting was chosen to make it a hit in MANC and MaleCNS.

## Part V: is our MaleCNS screen the authors' model?

- **DNg100** at the authors' MaleCNS configuration: **reproduces the authors' DNg100 result** (mean 0.985, 64 of 64 draws >= 0.5;
  theirs 0.985).
- **DNb08**: at the authors' configuration (their neuron, position 391, current 250, 2-s runs) **it reproduces their result** (15 of 16
  draws >= 0.5, mean 0.86; theirs 0.80). All four DNb08 copies reach the bar at some fixed current. So the network can produce their result,
  and run 5's finding that no single DNb08 copy drove rhythm came from our current-setting procedure [corrected 2026-11-23: the check
  changed the current, the run length and the activity bounds at once, so which of them mattered is not known].

## The three biggest caveats

1. **The tuned procedure failed its own positive control in BANC** (DNg100 11 of 16 draws, bar 12), so the cross-animal tests rest on the
   current sweep, which calls far more hits (60 of 182 types in MaleCNS) and is not the procedure the first two animals' hit lists came
   from. Our 0.5 cut of the authors' whole-type screen, from their procedure, recurred at chance (1 of 6) [corrected 2026-11-23]: "at
   chance" means the overlap could not be told apart from chance by this test, whose power is low; it does not show that the hits fail
   to recur. The BANC left-right and count-noise tests (C1, C2) used the tuned procedure, as pre-registered.
2. **BANC's wiring of the matched types agrees with the other two animals' less than theirs does with each other** (0.61-0.63 against
   0.82), so part of the gap may come from reconstruction, annotation or the type match; BANC's "high-confidence" matches are weaker
   evidence than MaleCNS's (no name conflicts at all), and BANC is the only female.
3. **The one positive test of a single-connectome predictor (C8) is fragile**: 12 types, a predictor chosen because it was nominally
   positive in run 5, and 10 of the 12 BANC scores below 0.07, so the correlation rests largely on the order of near-zero scores and on
   one clear hit (DNxl102). And count noise, which reproduced MANC's left-right gap, did not reproduce BANC's (C2).

## Corrections (2026-11-23, after the four reviews of the paper)

Logged in LOG L190. The original sentences are kept above, struck through or marked.
1. **Hits in all three animals.** The count came from C5's pre-registered table, which lists only current-setting hits. The correct sweep
   counts (post hoc) are 71 / 22 / 4, with DNxl134 the fourth type in all three animals (`LOCK_paper_posthoc_v1`, tag
   `ledger-paper-posthoc-v1`). This was found by the numbers review (P1).
2. **Blinding.** BANC was not *screened* before the freeze, but it had been looked at: its annotations were read to match types, DNg100
   was run for the build check, and the authors' BANC results were known (PREREG v6 Part Q).
3. **Part V.** The network reproduces the authors' single-DNb08 result. Which part of our current-setting procedure missed it is not
   known.
4. **"At chance".** C4's fixed sentence now stands beside the authors' list in caveat 1, and that list is described as our 0.5 cut of
   their whole-type screen.

