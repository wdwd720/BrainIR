# Session a5-g18-A notes (label audit, run 5)

Assigned types: DNa01, DNa02, DNg62 (aDN1), DNxl022 (hemibrain DNa01), MDN (DNp50).
Assigned sources: 2, both read from local files only (text.txt, figures, supp text, page-image text). No web used.

## 10.1016/j.cub.2022.01.035 (Israel et al. 2022, moonwalker SEZ neurons)
- 7 MDN records: Fig. 2/S2A (MDN3-GAL4 and VT50660-GAL4 > ChR2-XXM, intact free), Fig. 4B (same two lines, decapitated, 10-s light),
  Fig. 3B (VT50660 > CsChrimson, no-TNT control), Fig. 7H (VT50660 > CsChrimson, 30 s), Fig. 3E (MDN+MAN-LexA > CsChrimson).
  All show backward walking, coded yes for all three leg pairs per the convention; no leg tracking (Ctrax centroid/orientation only).
- effect_on_walking set to not_assessed: the effect is a reversal to backward walking in freely moving groups (mix of walking and standing),
  which the vocabulary has no value for.
- Not recorded: Fig. 3D (MDN+MAN activation while MDNs silenced by TNT), Fig. 1H-I (MDN silencing with odor), Ca2+ imaging.
- Fig. S2C intensity series uses GH146II-GAL4 only, not MDN lines.
- DNa01 and DNa02 appear only in hemibrain connectivity analysis (Fig. 7K); no activation experiment -> no records.
  (The name DNa01 would be ambiguous in the kit: DNa01 vs DNxl022; moot here.)
- Decapitated flies walked on the open-arena floor; headless_surface coded `other`.
- MDN3-GAL4 coded `clean` based on the paper's description as the narrow/more specific split; VT50660-GAL4 coded `unknown` (described as broad, other cells not named).

## 10.1101/2024.12.17.628844 (Özdil et al. 2024, antennal grooming networks)
- Real-fly activation only of JO-F neurons (aJO-GAL4-1 > CsChrimson), Table 1 lists only aJO-GAL4-1, UAS-CsChrimson, smFP.
- aDN1 (DNg62) appears only as a seed neuron in the connectome network and as a hit in the paper's own simulated activation screen
  (Fig. 6E, 'green outlines: aBN1,2, aDN1, ...'). This is the paper's own model, not a Pugliese-type screen; no records were written for aDN1,
  so no saw_simulation_score flag is affected. No sightings.csv row needed.
- Disposition: no_qualifying_experiment.

No sources unreachable.
