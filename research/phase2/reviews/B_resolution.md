# Review B (optimisation): resolution

Review: `research/phase2/reviews/B_optimisation.md`, run on BrainIR v1.1 (`94ea1f8e…`). It found 0 blockers, 1 major and 8
minors. Its verdict: "accept the final v1.1 for the lock once B2 is fixed or recorded as an accepted limitation".

The oracle-free composer made the method fixes as BrainIR v1.2.0. The method file's sha256 is `4bfcf816…`, recorded in every
result's `diagnostics["code"]`.

| # | severity | finding | resolution | status |
|---|---|---|---|---|
| B1 | minor | The code did not identify its own version; the method changed during the review. | Version 1.2.0. The method file's sha256 (`_brainir_v1_sha256.py`, checked by a test) is written into diagnostics and method info. The method doc explains the two v1.0 hashes: `9ca36c4d` = `3a07cf80` with `Oracle` renamed to `Prober`, byte for byte. §12.9 corrected. | fixed |
| B2 | major | On the real MANC network the choice between two valid cores was decided at the threshold edge (P = 0.954 against 0.95) by a t test on a bimodal statistic; a stricter threshold flipped it. | Reliance now tests function failures as paired discordant counts, by the sufficiency rule, and the readout change against the noise band on replicates where neither silencing fails. A decision needs P > 0.975 at the default (a factor-2 margin on the error rate); 0.90–0.975 becomes a tie after extending to the replicate cap. Inside the band, no later key (size, stress) may overrule the side the reliance evidence leans to. That rule was added after the composer saw a real-bundle run fall into the band; it changed none of 1,026 dev runs. Real bundle: MANC is decisive at the default (5 against 0 failures, P = 0.984) and returns the same core as v1.1; at `decisive` = 0.975 it is an explicit tie (0.5 / 0.5); MaleCNS is unchanged at every setting (a tie of two sets, as before). | fixed |
| B3 | minor | Full-network CPU dominates at scale, and the screen is the largest part of it. | Recorded as a limitation. v1.1/v1.2 cost about 3× v1.0's CPU on the real networks, the price of the single-silencing evidence reviews A and G required. | accepted |
| B4 | minor | Choosing among sufficient sets is a family-dependent heuristic; enumerating alternatives is the largest phase. | Recorded as a limitation. Admissibility (validated, participating, containing every measured essential) is principled; the choice among admissible sets remains a heuristic, and ties share the probability mass. | accepted |
| B5 | minor | Some calls change no returned core. | Stress probes now run only for equal-size pairs still tied after reliance: identical cores and probabilities in 198 runs, 108 calls saved. The other savings were not adopted, because they could change results (the full pooled necessity test is kept). | partly fixed |
| B6 | minor | At low budgets the answer depends on the budget; the certificate and the alternatives are starved first. | The certificate's calls are reserved before the screen and the enumeration. `budget_limited_phases` and the `budget_limited` flag are recorded, so a budget-limited answer is visible. | fixed |
| B7 | minor | The seed-to-replicate map has period 16. | A warning is recorded for seed ≥ 16. All Phase 2 sweeps and tournaments use seeds 0–2. | fixed |
| B8 | minor | Two minimality steps ended without a closing check. | The minimality rounds and the certificate repeat until nothing is removed, else they flag `minimality_unverified`. A certificate removal stands only if the reduced core validates decisively. | fixed |
| B9 | minor | The selection was an incumbent tournament with a non-transitive comparator. | Round robin: the winner is an undefeated candidate (the canonical one if undefeated). A cycle keeps the canonical candidate, ties everything and flags `selection_cycle`. Reliance is computed per pair on that pair's own distinctive members. Order independence is unit-tested; no cycle occurred in 1,092 runs. | fixed |

**No regression against v1.1 on the composer's dev suites:**
- adversarial: correct 0.97 / 1.00 (dev / held-out), 0.00 confident-wrong; v1.1's core in 175 of 176 runs;
- plain: small suite 276 of 282 identical cores, medium 48 of 48, large 12 of 12; low budgets 110 of 110 identical;
- pairs: 102 of 102 identical, 71 of 71 identity claims correct.

The orchestrator's held-out re-runs of v1.2 are recorded in `research/phase2/reviews/AG_resolution.md`.
