# a5-adj-08 adjudication notes

## Sources
- 10.1038/s41467-025-64907-9 (Steinfath, Khalili et al. 2025, Nat Commun): full text, figures, Supplementary Information
  (MOESM1), reporting summary, peer-review file (MOESM3) and the source-data sheets were all available locally. I read the
  main text, Table 1, Methods, the Fig. 3 image and the Fig. S4 legend. No source was unreachable.

## DNp29 (NPF1 / NPFP1)
**Where the readers differed:** reader A wrote no records for this source (the file is empty). Reader B wrote one
record: SS01587 activation in freely moving females, mapped to DNp29, with legs coded yes/yes/yes at medium confidence.

**What I found:** the source has exactly one experiment that qualifies under PROTOCOL section 1 for this type: Fig. 3C-D
(and S4C). CsChrimson is driven by SS01587 in females courted by a wild-type male, at 625 nm, 89 mW/cm2, 5 s on and 25 s
off, 30 trials, with N = 9 retinal-fed pairs. The text says this is "inducing female walking". In Fig. 3C, female
velocity goes from about 1 mm/s to about 12 mm/s during the light and drops back after it. Tracking covered the body only
(no leg tracking), so under section 3 ("increased locomotion" scored without leg tracking) all three leg pairs are `yes`
at medium confidence. The flies were close to stationary before the light came on, so this counts as starting
locomotion, not only a speed change in flies that were already walking. My record agrees with reader B, so reader A
missed this experiment. There are only minor field differences: I set `expression` to `unknown` (the paper does not say)
where B had `bilateral`. The paper does not state the walking direction, so `forward_walking` is an assumption (noted in
the record).

**Mapping issue (important):** the paper calls these neurons "DNp28", but Table 1 gives the line as SS01587 =
R11H10-p65.AD; VT033947-GAL4.DBD. The kit (`driver_lines.csv`) maps that line to DNp29, and the kit's DNp28 lines
(SS01056, SS01589, SS01590) use different hemidrivers. I followed the genotype and set DNp29 at `medium` confidence. If
the label were right and the genotype wrong, the record would belong to DNp28. I added a row to
`proposed_synonyms.csv` documenting the label.

The paper's other activations (P1a, pC2l, pIP10, pMP2) are not assigned types. The vGlut-GtACR1 experiment is
inactivation. Neither produces records here.

## Simulation scores
The paper contains its own rate model of the P1a/pC2l/pIP10/DNvib circuit (Fig. 6, S8, S10). It gives no score, rank or
driver call for DNp29, and no connectome activation-screen output appears. `saw_simulation_score` = false.
