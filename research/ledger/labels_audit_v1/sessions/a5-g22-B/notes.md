# Session a5-g22-B (label audit, run 5)

Assigned types: DNp01 (GF, Giant Fiber), DNp09, DNp71 (hemibrain "DNp09"), MDN (DNp50).
Assigned sources: 4, all locally present and readable (text.txt + figures + supplements). No web used.

## Per source

**10.1098/rspb.2024.1724 (Chai et al. 2025, GF and damselfly predation).** Full text read, plus the PDF text
(`supp/article.txt`) searched for activation effectors. The only genetic manipulation is Kir2.1 silencing of the
GFs (GF1/GF2 split-GAL4); behaviour is evoked by looming stimuli or real damselfly attacks. Silencing is not a
record (PROTOCOL section 1). No record.

**10.1371/journal.pone.0267834 (Luo et al. 2022, low-cost optogenetics device).** Two qualifying activation
experiments, both in intact tethered flies with CsChrimson, 300 ms of 627 nm light:
- GF-split-Gal4 (= DNp01): take-off (middle leg extension, wing depression, flight). Single movement, so all three
  leg pairs coded `no`.
- SS1540-split-Gal4: freezing, coded `no` for all pairs and `effect_on_walking` = `stops`. The paper itself flags
  that the freezing may come from other neurons in the line rather than DNp09, and explicitly says it did *not*
  see the reported DNp09 locomotion increase, which it attributes to the tethered preparation. Recorded under
  `name_in_paper` = DNp09, `line_specificity` = `multi_dn`, `labeler_confidence` = medium for that reason.
  SS01540 is listed as AMBIGUOUS (DNp09;DNp71) in driver_lines.csv, so `mapping_confidence` = medium with DNp09
  (the paper's own name and the kit's preferred reading) as `manc_type`; no separate DNp71 record was written,
  since the ambiguity is one of naming conventions rather than two labelled types.

**10.64898/2026.02.26.708359 (Lee et al. 2026, MDN cell body clustering).** One record: optogenetic activation of
MDN in intact, freely moving adult control flies produces backward walking (Fig. 1C). The same control activation
recurs in Fig. 2K and Fig. 3M with different control genotypes; I treated these as one experiment rather than
three near-identical records, and said so in the record's notes. The Hb / Lar / Inx8 knockdown arms also activate
MDN optogenetically, but the MDNs are genetically disrupted in those flies (activation then fails to elicit
backward walking, or the flies pause); I did not write them as separate records of what MDN activation does, and
noted this on the record instead. The paper's connectome analysis of MDN outputs (MANC) is anatomy, not a
simulation score, so `saw_simulation_score` is `false`.

**10.7554/elife.69767 (Lee and Doe 2021, MDN-Pair1 circuit).** Full text read. CsChrimson is expressed only in
Pair1 (R75C02-Gal4); Pair1 is not an assigned DN type. MDN appears only as anatomical labelling (MDN-LexA,
VT044845-lexA) and t-GRASP, with the backward-walking role cited from earlier work. No activation of an assigned
type, so no record.

## Uncertainties

- Leg-rhythm coding for the 708359 record rests on "walk backwards" with no leg tracking in that figure, so
  `labeler_confidence` is medium (PROTOCOL section 3 convention for locomotion scored without leg tracking).
- n for the 708359 record is not stated numerically in text or legend; I left `n_flies` null and described the
  figure points in `n_flies_note`.
- No simulation scores, ranks or driver calls for any assigned type were seen in these four sources, so
  `out/sightings.csv` was not needed.
- No new synonyms or driver lines were needed beyond the kit, so `out/proposed_synonyms.csv` and
  `out/proposed_driver_lines.csv` were not written.
