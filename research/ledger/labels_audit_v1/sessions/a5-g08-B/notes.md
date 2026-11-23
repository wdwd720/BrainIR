# Session a5-g08-B notes (audit, run 5)

Assigned types: DNp01, DNp09, DNp13, DNp71, MDN. Assigned sources: 3, all with full text in the room. No web was used.

## 10.1016/j.neuron.2020.07.032 (Bidaye et al. 2020)
- Wrote 6 records, all for DNp09 (paper: "DNp09 (henceforth referred to as P9)", lines SS01540 and P9S2).
- **Mapping ambiguity:** synonyms.csv says "DNp09" is also the hemibrain name of MANC DNp71 (ambiguous=True), and driver_lines.csv lists SS01540 and P9S2 as AMBIGUOUS DNp09;DNp71. I chose DNp09 (mapping_confidence medium) because the paper uses the Namiki et al. 2018 DN split-GAL4 nomenclature. However, the paper also matched P9 to hemibrain cell 1228264951 (STAR Methods). If that hemibrain cell is typed "DNp09" in hemibrain naming, it would point to MANC DNp71. An adjudicator should check this. I wrote no separate DNp71 records.
- Figure images, supplementary figures (S1-S7) and videos are not in the room ("image file: not available"; supplementary files not downloaded). Records for Fig. S2 panels rest on main-text sentences only.
- Not recorded: Fig. S5L (BPN + P9 co-activation, because it combines a DN with a non-DN brain neuron); MDN-1>CsChrimson used only as a positive control to set light intensity (no outcome reported); P9 GCaMP imaging; TeTx silencing.
- The Fig. 1B screen covered 156 DN lines, possibly including lines for other assigned types (DNp01, DNp13, MDN). Per-line results appear only in the unavailable figure, so I could not write records for them.

## 10.1038/s41467-024-53610-w (Li et al. 2024)
- dsx-GAL4 ∩ Otd-Flp > CsChrimson activates all dsx brain neurons, including the DNs vpoDN and DNp13 (pMN1); in decapitated flies only their VNC neurites are activated. Only abdomen extension and wing angle were measured. Legs are not described, apart from responses such as grooming/jumping/turning, which were excluded as "invalid" in vpoDN-line experiments, and leaning/flipping over in D. santomea. No record; disposition no_qualifying_experiment.

## 10.1038/s42003-025-09344-6 (Israel & Parnas 2025)
- Activation experiments target MooSEZ, an SEZ neuron that is not a DN in the adult, and broad lines (GH146II, NP225, NP5288, R60F09, R11E07, AMB split). MDN appears only as MDN-LexA>TNT silencing. One split line (VT032768 ∩ R60F09) also labels an unnamed bilateral pair of SEZ DNs, which I cannot map. No record.

## Simulation scores
- I saw no simulation score, rank or driver call for any assigned type. saw_simulation_score = false on all records. No sightings file needed.
