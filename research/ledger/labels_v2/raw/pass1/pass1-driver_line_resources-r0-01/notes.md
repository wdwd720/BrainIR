# Notes: session pass1-driver_line_resources-r0-01 (pass1)

## What was read
I read only the 6 assigned sources from their local copies in `sources/`. I did no web access, did not look for any model or simulation, and did not visit GitHub or Zenodo. For each source I read text.txt and checked the figure legends, the supplementary text and tables, and the key figures (Namiki 2022 Fig. 1; Zacarias 2018 Fig. 6).

| source | disposition | records |
|---|---|---|
| 10.1016/j.cub.2022.01.008 (Namiki 2022) | no_qualifying_experiment | 0 |
| 10.1016/j.cub.2023.12.047 (Ros 2024) | no_qualifying_experiment | 0 |
| 10.1038/s41467-018-05875-1 (Zacarias 2018) | records | 1 |
| 10.1038/s41467-018-06857-z (Chen 2018) | no_qualifying_experiment | 0 |
| 10.1101/2023.08.30.555537 (Lillvis 2023) | records | 5 |
| 10.1101/2025.02.22.639679 (Zung 2025) | no_qualifying_experiment | 0 |

## Judgement calls (for adjudication)
- **Flight-only activation screens (Namiki 2022, Ros 2024).** I did not treat these as records. All DN activation was done in tethered or magnotethered *flying* flies. The readout was wingbeat amplitude/frequency or body yaw, and no leg observation was made or described. PROTOCOL section 1 requires leg movement to be observable. If adjudication decides that such screens should instead give `not_assessed` records, Namiki 2022 Table S1 lists all 50 lines (49 DN lines plus the empty control SS03500) with their DN types. Ros 2024 activated DNae014 (kit: DNae014-splitGal4 -> DNa15) and DNb01 (SS02383).
- **Song experiments (Lillvis 2023).** These flies were free-moving and filmed on video, so the legs were observable in principle. I wrote records with all leg fields `not_assessed` (convention for wing/song behaviours), because the paper describes song only. The two DNs are pIP10 and pMP2. The other tested neurons (TN1A, dMS2, dPR1, dMS9, vMS12, vPR9, vPR6 ...) are described as VNC intrinsic or ascending neurons, not DNs, so they got no records.
- **DNp09 (Zacarias 2018).** Activation caused a brief rise in walking speed in flies that were mostly already walking, then freezing in 61.5% of trials. I coded this by the stopping convention: legs `no`, `stops`, `halting`, with forward_walking and takeoff_or_jump as secondary behaviours. Confidence is `medium`. The closed-loop speed-dependent stimulation (Fig. 6g) gives the same outcome class at different probabilities, so I folded it into the same record. Mapping: the kit lists SS01540/"DNp09" as AMBIGUOUS (DNp09;DNp71). I chose DNp09 (Namiki-defined type, Namiki line) with `medium` confidence.
- **Line IDs for pIP10/pMP2.** The figures name only cell types ("pIP10-GAL4"). The line IDs (SS46542, SS43275) come from the paper's own Supplementary Table 1 and are proposed in `proposed_driver_lines.csv`. In the kit these lines are currently `UNMAPPED` (named DNp79/DNp84). Synonym proposals are in `proposed_synonyms.csv`.
- **pMP2 line off-target.** The paper's table notes "off-target pIP1 in brain". The kit maps the name pIP1 to pIP10/DNxl053, both DNs. The paper does not call that off-target cell descending, so I did not write a separate record. It is listed in `other_cell_types`.
- **Record 0006 (pIP10 + vPR9-SS1 co-activation).** This deliberately co-activates a DN with non-DN interneurons. I kept it as a pIP10 record with confidence `low`; adjudication may drop it.

## Missing material
- Ros 2024: figures and supplementary videos were not downloaded (text and legends were available). They are not needed for the disposition.
- Zacarias 2018 and Lillvis 2023: supplementary movies were not downloaded.
- Zung 2025: main Figs 2-26 and Supplementary File 1 were not downloaded. They are anatomy images, so the disposition is unaffected.

## Simulation scores
I saw no simulation, rhythm score, rank or driver call, so there is no `sightings.csv`. Ros 2024 and Lillvis 2023 include their own connectomic analyses and machine-learning neurotransmitter predictions. These are not Pugliese-type activation screens, and I did not use them for coding.
