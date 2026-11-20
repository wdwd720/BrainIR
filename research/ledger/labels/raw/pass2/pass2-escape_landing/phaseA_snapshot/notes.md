# Pass 2, session pass2-escape_landing: notes

23 input rows: 21 records written (`records.jsonl`, p2-escape_landing-0001 to -0021) and 2 rows not found (`not_found.csv`).
All rows had n_siblings = 1, so no sibling splitting was needed.

## Could not access
- **von Reyn et al. 2014, Nat Neurosci (10.1038/nn.3741)**: paywalled. The Janelia PDF came back as undecodable binary, and the
  saved local copy was permission-denied. The abstract does not describe the GF activation (Fig. 2), so there is no record
  for exp p1-0005.
- **PNAS 2014 (10.1073/pnas.1400997111)**: PNAS returned 403, PMC returned a reCAPTCHA page, and Europe PMC full text
  returned 500 (publisher blocks full-text download). The abstract does not mention the GF/12862-Gal4 jumping experiment, so
  there is no record for exp p1-0016.
- **Lima & Miesenböck 2005, Cell**: abstract only. The record is low confidence. The abstract says "optically gated ion
  channels"/"phototriggers" and does not name P2X2 or caged ATP, so the effector listed in the input is unverified. "Neurons in
  the giant fiber system" is mapped to DNp01 with medium confidence.
- Driver-line IDs for Nature 2023 (Supplementary Table 2) and for the 2025 bioRxiv preprint (Supplemental Table 1) were not
  visible, so `driver_lines` is `[]` in those records.

## Uncertain
- **Ache et al. 2019, DNp07 lines.** The Methods say SS01549 (DNp07-split-GAL4-2) was used for Fig. 1e/Supp. Fig. 3, and line -1
  (SS02276) for "all other experiments". I therefore gave Fig. 1e records SS01549 and the non-flying record SS02276, whereas
  the input listed both lines. Off-target: the paper mentions faint expression in a second DN not targeting leg neuropils. My
  tool reading attributed this to line -1 (SS02276), while the kit (Namiki 2018) lists DNp13 as off-target in SS01549. I
  could not resolve this, so I marked DNp07 records `minor_offtarget` rather than splitting out a DNp13 record.
- **aSP22 (2025 preprint, exp p1-0022).** The outcome sentence ("all but one DN in the putative landing ensemble reliably
  elicited landing responses") does not name aSP22. That aSP22 was activated is inferred from the text: lines existed for
  every ensemble type except DNg19871, each type was activated, and DNb05 was the only failure. I did not see an aSP22 label in
  Fig. 1F. Confidence is medium.
- **DNp07_2 (exp p1-0018).** The outcome is shown only graphically (Fig. S1-1C), so confidence is medium.
- **Nature 2023, DNp02 alone.** This is coded as a posture change (backward leaning). DNp02 alone is not among the lines that
  significantly increased takeoff.
- All these experiments involve single movements (landing extension, takeoff, posture). Following the protocol, leg rhythm is
  `no` for all pairs and `effect_on_walking` is `not_assessed`.

## Simulation exposure
- The 2025 preprint contains a model/prediction figure (Fig. S4-1). I asked the fetch tool to exclude it and saw no scores.
  `saw_simulation_score` = false on all records.
- I did not visit GitHub, Zenodo, Pugliese et al. 2026 or Sapkal et al. 2026.
