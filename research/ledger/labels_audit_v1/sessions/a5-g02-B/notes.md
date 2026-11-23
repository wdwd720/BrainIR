# Session a5-g02-B (audit, run 5): notes

## Sources read
- **10.1016/j.cell.2024.08.033** (Yang et al. 2024, Cell). Read: full text.txt (results, STAR Methods, figure and supplementary-figure legends) and Fig. 3 legend context.
  - Activation experiments recorded:
    - DNa02 unilateral SPARC-CsChrimson, Fig. 4A-C (turning; trials only from walking flies, so leg rhythm not_assessed).
    - DNa02 bilateral SPARC-CsChrimson, Fig. S6A-C (slows).
  - DNg13 (SS02259) with SPARC-CsChrimson: the Methods say light stopped locomotion whenever an off-target ascending neuron expressed CsChrimson, regardless of DNg13 expression. I recorded this with low confidence and flagged the confound (record 0003). An adjudicator may prefer to drop it.
  - DNg13 depolarizing current injection (Fig. 4G-I) is not optogenetic or thermogenetic activation, so it was not recorded.
  - Other assigned types appear only in calcium imaging (Fig. S2): DNa01, DNb05, DNb06, DNg14, DNg15, DNg16, DNp05, DNp09, DNp11, DNp18. DNp09 is also mentioned in the Discussion. None of these produce records.
  - No connectome-simulation scores, ranks or driver calls were seen.
- **10.1038/s41467-025-64907-9** (Steinfath et al. 2025, Nat Commun). Read: full text.txt and the Fig. 3 image.
  - One record: CsChrimson activation of "DNp28" in courted females (Fig. 3C-D), which induced walking or acceleration.
  - pIP10 and pMP2 activations are not assigned types. P1a and pC2l are not DNs.
  - The paper's own circuit model (Fig. 6) is not a Pugliese-type screen, and it gives no scores for DN types.

## Mapping conflict (needs adjudication)
- Steinfath et al. call the line "DNp28 (SS01587)" and give the genotype R11H10-p65.AD; VT033947-GAL4.DBD.
- The kit's driver_lines.csv maps SS01587 (R11H10 x VT033947) to **DNp29**. That mapping comes from the Namiki 2018 supp. file 3 and the eLife 107450 Supplementary Table 5.
- The kit's DNp28 lines are other lines: SS01056, SS01589 and SS01590.
- I coded record 0004 as manc_type DNp29 with mapping_confidence medium, keeping name_in_paper = DNp28. I also added a proposed_driver_lines row recording the paper's label so the conflict is visible.
- If the label is trusted over the genotype, the record should be DNp28.

## Access
Both sources had full text locally. Nothing was unreachable. No web access was used.
