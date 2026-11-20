# Arm diagnostics before the predictions lock (prediction side only; no label exists)

Written 2026-11-20 before `ledger-predictions-v1`. Only model outputs are used; the only named types examined are DNg100 and
DNb08 (the prompt's allowed neurons). Nothing here changed any arm: PREREG section 12 allows no amendment once a stage has
produced data, and the G2-style remedy (a demonstrated code bug) does not apply because no code bug was found. These notes
exist so that run 2 reads the B2 and B4 results with their known weaknesses on record before the labels.

## B2 (MaleCNS): the DNg100 positive control fails under the pre-registered procedure

- B2 runs PREREG 3.8 exactly: the kept B1 procedure (auto-tuned current, lower bound 10 active neurons, high-firing cap
  200), unchanged bounds, on the authors' MaleCNS front-leg network.
- DNg100 (2 members, as in MANC) scores **0.059** in B2 against 0.828 in B1 and 0.896 in A1. All 16 replicates are
  accepted at 256 per member after two tuning runs; 15 of 16 have 0-1 active front-leg MNs and only 10-29 active neurons
  in the whole network, so the lower bound (10 active neurons) is met before the network is recruited.
- **The network itself is correct** (`B2_DNG100_CHECK.json`, `ledger/scripts/b2_dng100_check.py`, fixed currents, seeds
  0-3, locked score):

  | condition | score | active front-leg MNs | active neurons |
  |---|---|---|---|
  | DNg100 body 10056 alone, I = 400 (the paper's MaleCNS current) | 0.980-0.997 | 7-8 | 93-125 |
  | DNg100 body 10045 alone, I = 400 | 0.996-0.999 | 3-4 | 70-94 |
  | both members, 256 each (where the tuner accepted) | 0.000 | 0-1 | 14-19 |
  | both members, 512 each (the tuner's next step) | 0.734-0.948 | 10-17 | 283-329 |

  The paper and Phase 1 report 0.985 / 0.983 with 8 MNs for the single benchmark neuron at I = 400; body 10056 matches.
  The MaleCNS network needs more drive than MANC (the paper used 400 there and 250 in MANC), and the published tuning rule
  stops at the first current that meets the bounds.
- Prediction-side context: the procedure accepts many replicates without any MN activity in both animals (usable
  replicates with 0 active front-leg MNs: B1 45.5 %, B2 43.8 %); B2 accepts at the starting current 128 more often (68.7 %
  of usable replicates vs 45.3 % in B1).
- Agreement between the animals (`gates/PREDICTIONS_SUMMARY.json`): B1 vs B2 Spearman 0.31 over 310 common types, top-10
  overlap 1, band agreement 0.68; on the 236 types whose MaleCNS members all have a curated body match without a
  conflicting `mancType` string 0.36, on the 74 others 0.12.
- **Reading for run 2:** B2 is locked as pre-registered, but it is a weak second-fly test. Its disagreement with B1 reflects
  the transfer of the tuning rule at least as much as anatomy. A calibrated second-fly arm (bounds or starting current set
  on DNg100 before any other type is run) would be a new, separately pre-registered version.

## B4 (walking background): "halts" mostly means over-excitation, not a stop

- Background: both DNg100 at 250; rhythmic (score >= 0.5) in 16 of 16 seeds, so calls are made for every type.
- Calls at 128 per member (475 types): no_effect 250, halts 207, slows_down 14, speeds_up 4.
- Of the 207 `halts` types, **199** lose the rhythm with the same number of or more active front-leg MNs than the paired
  background run, and only 8 with fewer. Of the 3,239 replicates of these types that lose the rhythm at 128, 2,787 exceed
  the screen's upper bounds (verdict `strong`: too many active or high-firing neurons).
- DNg100 itself, added on top of its own background, is called `halts` at 128 (81 % of replicates lose the rhythm) and
  at 512 (100 %).
- **Reading for run 2:** B4's `halts` call, as pre-registered (score < 0.5 in >= 75 % of replicates), does not separate
  silencing from saturation of the network. Run 2 should read the B4 stop analysis with this in mind. The split above
  (fewer vs same-or-more active MNs) is a description, not a pre-registered call.

## B5 (fixed strengths)

- DNg100 per strength (type-level, both members): 0 at 32, 64 and 128; 0.828 at 256; 0.168 at 512. The rhythm exists in
  a window of drive and is lost above it, so B5's primary score (maximum over strengths) is the more robust summary.
