# Session a5-g13-A notes (audit, run 5)

Assigned types: DNa02, DNfl023 (aDN2), DNfl028, DNg100 (BDN2), DNg12, DNg62 (aDN1), DNg74 (web), DNg75 (cDN1), DNg97 (oDN1).

## 10.1038/s41586-025-09554-2 (Dallmann et al. 2025, Nature)
- Read the full text.txt (PMC author manuscript; figure images, videos and supplementary files are not in the room).
- DNg100, DNg97, DNg75, DNa02, DNg12 and DNg74 are discussed from connectomics. DNg74 was studied by calcium imaging only.
- The one activation experiment, DNg100 CsChrimson (Ext. Data Fig. 10), was done in fully restrained flies with all legs except one front leg glued, while that tibia was moved passively. The readout was calcium in hook axons; no leg behaviour was reported. So no record.
- The 9A CsChrimson activation on the treadmill is not a DN activation, so it is excluded.
- Simulation seen: Fig. 5i and the Results describe a connectome-constrained LIF model that stimulates DNg100, DNg12 and DNg74 and reports chief 9A recruitment. This is the paper's own model of 9A recruitment, not a walking/rhythm score, rank or driver call, so I set saw_simulation_score = false on the DNg100 record. This is flagged here for transparency.

## 10.64898/2026.05.03.722293 (Ispizua et al. 2026, bioRxiv)
- Wrote one record: headless DNg100>CsChrimson in the free-walking chamber, giving running (Results 2.5, Fig. 5c-d, Methods, Supp. Video 5 legend). I checked Fig. 5 visually.
- Uncertainties:
  - The Supp. Video 5 legend says the fly "speeds up" at light onset, and the white imaging strobe also activates CsChrimson (Discussion 3.3), so baseline movement before the red light is possible. I coded effect_on_walking = speeds and confidence = medium, with legs coded yes per the walking convention.
  - n flies and sex are not stated.
  - Line specificity is not described in the paper. The kit's driver_lines.csv lists VT058557-AD; R85F12-DBD as DNg100 with no other cells, so I coded it clean.

## 10.7554/elife.02951 (Seeds et al. 2014, eLife)
- Read the main text and grepped text.txt and the supp text files for DN names: none found.
- The GAL4 lines tested do not map to assigned types in driver_lines.csv. R40F04 and R45G01 appear only as hemidrivers of split lines for DNc01/DNc02, DNp37/DNp58 and DNp12.
- So no record.
