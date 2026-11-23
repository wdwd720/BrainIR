# Notes: session a5-g12-B (audit, run 5)

## Sources read
- 10.1038/s41586-024-07854-7 (Sapkal et al. 2024): I read the full text, the figure images (Figs. 1-4, ED Figs. 4 and 6), Supplementary Table 1 (genotypes, n), Supplementary Table 2 (reagents) and Supplementary Table 3 (connectome IDs). The supplementary videos were not downloaded.
- 10.1101/2024.06.27.601106 (Feng et al. 2024): I read the full text, Figs. 2 and 6, Figs. S1, S3 and S14, and Supplementary Information (genotype table, video legends). The videos were not downloaded.

## Coding decisions
- **Coactivations (Sapkal):** walk + halt coactivations (MDN or P9 with BB, FG, FG+BB or BRK, and BDN2 + BRK) are recorded as separate records for the DN type. The co-activated neurons are listed in `other_cell_types` and each record's notes say "Coactivation experiment". BB/FG combos are coded `multi_dn`, since BB is FlyWire DNg60 and FG descends to the anterior VNC. BRK combos are coded `minor_offtarget` because BRK is an ascending neuron (AN19A009) and the vocabulary has no better category. Filter these out if only single-type activations are wanted.
- **BPN and the halt neurons as types:** BPN is not a DN, so BPN coactivations were skipped. FG, BB and BRK alone are not assigned types (BB maps ambiguously to DNg60/DNxn073, neither assigned), so they have no records.
- **Name mapping (Sapkal):** P9 maps to DNp09 at medium confidence, because the kit marks DNp09/SS01540 as ambiguous (DNp09;DNp71). oDN1 maps to DNg97 and BDN2 to DNg100, following the kit's synonyms. Note that the paper's own MANC table lists oDN1 = DNxl054 and BDN2 = DNxl058, which differs from the kit's types.
- **DNae003 (Feng):** the kit maps the name to DNxn123, but the paper states it is the legacy name of the current FlyWire DNae001, which the kit maps to DNxl022 (assigned). I used DNxl022 at medium confidence and proposed a synonym.
- **Ball turning assays (Feng Fig. 2c):** for DNa11, DNa03, DNae003 and DNa02, only ball angular velocity is reported and the pre-stimulus walking state is not stated, so the legs are coded `not_assessed`. DNa11 leg stepping (~3 Hz, all six legs, initiated from standing) is a separate record from Fig. 6.
- **DNa03 flight (Feng Fig. 2d):** no record, because legs are not observable in tethered flight.
- **BDN2 decapitated, ED Fig. 6e:** coded `unclear`. The text claims robust walking, but Methods say BDN2 walked robustly in decapitated flies only in older flies (Fig. 4e-j), and the ED Fig. 6e BDN2 trace is hard to tell apart from baseline.
- **DNa11 decapitated:** the headless surface (ball) is inferred from the setup, not stated.

## Simulation sightings
- Sapkal 2024 includes the authors' own connectome spiking model: simulated firing rates for oDN1, BDN2, DNa02, DNa11, DNa06, cDN1, DNb02 and others, and in-silico P9 activation (Fig. 3, Fig. 5c-d, ED Figs. 6b-c, 9c, 10). This is not a Pugliese-type rhythm score, rank or driver call.
- `saw_simulation_score` is `true` for records of DNp09, DNg97, DNg100, DNa02 and DNa11, and `false` for MDN, DNa03 and DNxl022.
- None of these model results were used as evidence for any record.
