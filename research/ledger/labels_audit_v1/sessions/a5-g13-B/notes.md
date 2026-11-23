# Session a5-g13-B notes (audit, run 5)

Assigned types: DNa02, DNfl023 (aDN2), DNfl028, DNg100 (BDN2), DNg12, DNg62 (aDN1), DNg74 (web), DNg75 (cDN1), DNg97 (oDN1).
Sources: the three listed in assigned_sources.csv. All were readable as full text. No web access was used.

## Dallmann et al. 2025 (10.1038/s41586-025-09554-2): no qualifying experiment
- DNg100 was activated optogenetically (625 nm LED, about 4 s) only in fully restrained flies. All legs except one front leg were glued, and that tibia was moved passively by a magnet while hook axons were imaged (Extended Data Fig. 10, Methods). The paper reports no leg behaviour, so this is not a record.
- The treadmill optogenetics (CsChrimson/GtACR1) targeted 9A interneurons, not descending neurons.
- DNg97, DNg75, DNa02, DNg12 and DNg74 appear only in connectome analysis, calcium imaging (DNg74) or the paper's own LIF simulation (Fig. 5i, recruitment of chief 9A). None of this is a rhythm score, rank or walking driver call from a Pugliese-type screen. saw_simulation_score is therefore false for DNg100.
- Figures, extended data and supplementary files were not downloaded (0 images). Legends in text.txt were enough to establish that no leg-behaviour readout exists for the activation experiment.

## Ispizua et al. 2026 bioRxiv (10.64898/2026.05.03.722293): 1 record
- DNg100>CsChrimson in decapitated, freely moving flies; red LED flashlight. "Reliably elicited sustained running bouts", tracked in 3D (Fig. 5c-d, Supplementary Video 5, not downloaded).
- Uncertainties:
  - n_flies is not stated.
  - The Video 5 legend says the fly "speeds up" when the light turns on, so it may not have been standing before.
  - Line specificity is not described in the paper.
  - labeler_confidence is set to medium for these reasons.

## Seeds et al. 2014 eLife (10.7554/elife.02951): no qualifying experiment
- dTrpA1 activation screen of broad GAL4 lines for grooming. The text and supplements contain no mention of descending neurons.
- None of the lines (R23A07, R40F04, R26B12, R24B03, R53A06, R45G01, R17F11) appears in driver_lines.csv as a line for an assigned type. R40F04 and R45G01 occur only as hemidrivers of unrelated split lines.
- Supplementary file 1 contains chamber engineering drawings; files 2 and 3 contain MATLAB code.
