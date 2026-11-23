# Session a5-g20-B notes (label audit, run 5)

Assigned types: DNg100 (BDN2), DNp01 (GF / Giant Fiber), MDN (DNp50). Three assigned sources; all were readable (full text).

## 10.1038/s41467-020-19936-x (Feng et al. 2020)
- MDN activation with CsChrimson in four settings, giving five records:
  - Fig. 1: intact, tethered on a ball, MDN-1-GAL4.
  - Supp. Fig. 5: decapitated, plus an intact comparison group.
  - Fig. 4b / Supp. Fig. 3b: Fly Bowl free walking, negative-control genotype, MDN split-LexA.
  - Fig. 7: decapitated control trials, MDN split-LexA; only the hindlegs were tracked.
- Calcium imaging (ex vivo) and trans-Tango are not records. MDN activation combined with silencing of MF cells is not coded as separate MDN records; only the negative control (empty split-GAL4) is coded.
- Uncertain: Supp. Fig. 5 intact (record 0003) has the same genotype and preparation as Fig. 1 (record 0001). It is coded separately because PROTOCOL section 1 makes the figure part of the experiment key; a merger could treat it as a duplicate.
- The MDN split-LexA (VT049484-LexADBD; VT050660-AD) also labels MANs, so it is coded `minor_offtarget`. It is not in driver_lines.csv, so I proposed it in proposed_driver_lines.csv.
- `effect_on_walking`: backward walking (direction reversal) has no option in the vocabulary, so it is set to `not_assessed`; the behaviour is in `behaviour_category`.
- Supplementary movies were not downloaded. They were not needed: the text, legends and source data cover the results.

## 10.1101/2025.10.28.684868 (Jones et al. 2025)
- DNp01 and DNg100 appear only in connectome circuit diagrams (Fig. S6). The genotype table (supp/article.txt pp. 21-22) lists no DN lines. Disposition: no_qualifying_experiment.

## 10.64898/2026.01.04.697356 (Dallmann et al. 2026)
- One record: MDN-1 > CsChrimson in the gap-crossing assay, where flies always walked backward, including standing flies in phase 0.
- BDN2/DNg100 appears only in Supplementary Table 1 (an annotation list) and connectome analyses. Supp. Fig. 2b ranks DNs by connectome-predicted net excitation from RRN/BPN; this is the paper's own connectome analysis, not a Pugliese-type activation-screen score. I did not open that figure panel image.
- No Pugliese/BrainIR rhythm score, rank or driver call was seen for any assigned type, so `saw_simulation_score` = false on all records.
