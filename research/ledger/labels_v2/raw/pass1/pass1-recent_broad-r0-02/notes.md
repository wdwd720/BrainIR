# Notes: session pass1-recent_broad-r0-02 (pass1)

## What I did
- Read PROTOCOL.md (v2) in full, then read the six assigned sources from their local copies in `sources/` (text.txt, figure legends, selected figure/page images, supplementary text and source-data CSVs). I did no web access: section 8 says local only, and none was needed.
- Sources with records: 2 (5 records). Sources with no qualifying experiment: 4. Unreachable: 0.
- I saw no Pugliese-type rhythm score, rank or driver call anywhere, so `sightings.csv` is not written and `saw_simulation_score` = false on all records.

## Per source
1. **10.1038/s41467-020-19936-x (Feng et al. 2020, MDN backward walking).** 4 MDN records:
   - Fig. 1 (+ Supp. Fig. 5b,c): intact tethered on ball, MDN-1-GAL4 > CsChrimson, DeepLabCut joint tracking.
   - Supp. Fig. 5a,c: decapitated, same genotype.
   - Fig. 4b / Supp. Fig. 3b: Fly Bowl negative-control genotype, MDN split-LexA > CsChrimson, centroid tracking only.
   - Fig. 7: decapitated red-only control trials, MDN split-LexA.

   Step frequencies are my own means from the Source Data sheets (Supp. Fig. 5c, Fig. 7g), not values stated in the text. The MDN split-LexA (VT049484-ZpLexADBD; VT050660-p65ADZp) labels MDN plus MANs, so those records are `minor_offtarget`; I proposed it in `proposed_driver_lines.csv`. The headless surface is coded as `ball`, inferred from the Methods (decapitated flies were tethered on the same PP ball setup) and the tarsus-ground angle in the traces. LBL40, LUL130 and LUM9 activations are VNC interneurons and motor neurons, not DNs, so I made no records for them. The supplementary videos were not downloaded; I did not need them.
2. **10.1038/s41467-026-72152-x (Özdil et al. 2026, antennal grooming).** No qualifying experiment. Activations were of JO-F sensory neurons (aJO-GAL4-1) and of c23/'asteroid' (SS35281), which the paper calls a central brain inhibitory interneuron. The peer-review file states that aDN1 was not activated experimentally. The paper has its own connectome-constrained network model and simulated activation screen. Under section 8 that does not count as a sighting, but I deliberately did not read or use the model results (Figs. 5-6), and no record rests on them.
3. **10.1038/s41586-023-07006-3 (Mussells Pires et al. 2024).** No qualifying experiment: only FC2, PFL3 and PFL1 were activated. DNs are mentioned only as anatomical targets of PFL3.
4. **10.1038/s41586-024-07890-3 (Cazalé-Debat et al. 2024).** 1 record: plP10 split-GAL4 (VT040556-AD; VT040347-DBD) > CsChrimson, Ext. Data Fig. 4a,b. Uncertainties:
   - **Mapping.** The paper's spelling 'plP10' looks like a variant of pIP10, so I mapped it to pIP10 with medium confidence. The same hemidriver pair is kit row SS46542, which the kit lists as UNMAPPED/DNp79 with previous annotation pIP10. This conflict should be checked by whoever maintains the kit; I proposed the synonym and the line mapping.
   - **Behaviour scoring.** Behaviour was scored only as courtship and defensive (escape/freezing) indices. The leg fields are `not_assessed` and confidence is `low`. The record may be judged out of scope for a leg-rhythm table, but I kept it because a DN line was activated in freely behaving adults scored from video.
   - **Lines not recorded.** The other activated lines (LC16, P1, TRHR23E12, TRH-GAL4, TH-C1-GAL4, OvAbg) are not DN lines, so I made no records for them.
5. **10.1038/s41586-025-08925-z (Stürner et al. 2025).** No qualifying experiment. It is a connectomics resource; DN activation phenotypes appear only as citations to other papers, which I did not record because the experiments are not this source's own.
6. **10.1038/s41593-023-01332-5 (Vijayan et al. 2023).** No qualifying experiment. The activated lines are PU sensory neurons and CMU uterine motor neurons; oviDNs are discussed only as background.

## Conventions applied and other uncertainties
- **Backward walking.** I coded all three leg pairs as `yes` for every MDN record, following the backward-walking convention, even where only the hindleg was tracked (Fig. 7 record). This is noted in each record.
- **Fly Bowl record.** It is scored from centroid motion only, so `labeler_confidence` is `medium`.
- **Record split for the MDN-1-GAL4 data.** I made one record per (figure, line, preparation). The tarsal-amputation data (Fig. 1i,j) are folded into the intact-tethered Fig. 1 record (same line and preparation) and described in `coordination_notes`.
