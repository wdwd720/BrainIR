# pass2-general-01: notes (pass2, independent second reading)

## Scope and method
- I read PROTOCOL.md (v2, including section 8), the kit (type_list, synonyms, driver_lines), experiments_to_label.csv (28 rows) and assigned_sources.csv (6 sources).
- I worked only from the local copies in `sources/`. I made no web access and opened no model, simulation or prediction output.
- Every record rests on my own reading and a verbatim quote of at most 25 words from text or a legend.
- All 28 experiments were found, so there are 28 records. `not_found.csv` has a header only.
- All six sources have the disposition `records`.

## Sightings
- None. No Pugliese-type rhythm score, rank or driver call appeared in any source I read. `saw_simulation_score` is false on every record. I wrote no `sightings.csv` because there were no rows.

## Access gaps (figures and supplements not available locally)
- 10.1016/j.cub.2025.11.035 (DNp03): text and legends only; no figure images or videos.
- 10.1016/j.cub.2026.09.056 (threat display): text and legends only; no figures, no Figures S1-S7, no Tables S1-S2.
- 10.1016/j.neuron.2020.07.032 (Bidaye 2020): text and main legends only; no figure images, no supplementary figures (S1-S5), no Table S1.
- 10.1016/j.cub.2022.01.035 (MDN/MooSEZ): videos not downloaded. Figures and Fig. S2 were read.
- None of these gaps blocked a record; each affected record says so in `notes`.

## Mapping decisions and uncertainties
- **P9 / DNp09 (Bidaye 2020, Zacarias 2018).** The kit maps the name DNp09 and lines SS01540 and P9S2 to either DNp09 or DNp71, because hemibrain type "DNp09" corresponds to MANC DNp71. Both papers use the Namiki name. Their anatomy also fits DNp09: one bilateral pair, dendrites in the posterior protocerebrum, outputs in the SEZ and the ipsilateral leg neuropils. I chose DNp09 at medium confidence. I proposed "P9" as a synonym.
- **SS01587 "DN0p28" (Bidaye 2020).** The paper's name looks like a typo for DNp28, but the kit maps SS01587 to DNp29. I could not decide, so the record is UNMAPPED at low confidence. The paper also attributes this line's walking to BPN, a non-DN neuron in the same line.
- **DNpe050 → DNxn183.** This follows the kit's flywire/malecns synonym, which points to one type only, so confidence is high.
- **MDN(s) → MDN.** MDN is itself a MANC type name. For VT50660-GAL4 the paper says "broad" but names no other cells, so line_specificity is `unknown`.
- **No sibling groups:** every row had `n_siblings` = 1. Coactivation rows (DNpe050+DNp60; P9+BPN) were labelled per the row's name_in_paper and marked non-specific.

## Coding judgements worth a second look
- **DNg13 (Cell 2024, Methods).** Light stopped locomotion whenever the off-target ascending neuron expressed CsChrimson, regardless of DNg13 expression. I coded halting with low confidence; the stop is not attributable to DNg13.
- **DNa02 (Cell 2024).** Only trials where the fly was already walking were analysed, so legs are `not_assessed`. Unilateral activation gives turns; bilateral activation slows the fly.
- **DNp03 and threat-display DNs.** These are wing/flight behaviours; legs are not described, so leg fields are `not_assessed`. For DNpe050 and DNp60 alone, the paper says turning and charging were not changed, so `effect_on_walking` = none.
- **Zacarias 2018, DNp09.** Activation causes a running bout followed by freezing in 61.5% of trials. Legs are coded yes for the induced running and the category is halting (stops), at medium confidence.
- **Bidaye Fig. S2F-G (four genotypes, freezing in one).** Without the supplement I cannot tell which genotype the row refers to. I coded the shared outcome (walking initiation, with halting as secondary) at low confidence. The freezing genotype may deserve its own record once Fig. S2 is available.
- **Bidaye 156-line screen.** It is not reported line by line (genotypes "available on request"), so I coded `targeted_study` and did not create records for the other screened lines.
- **Cell 2024 typo.** The Discussion cites "Figures S7A-C" for the bilateral DNa02 slowing; the legend and Methods place it in S6A-C.

## Validation
- `records.jsonl` has 28 lines, record IDs pass2-general-01-0001 to 0028.
- I had no shell or JSON parser in this session. Instead, regex checks confirmed:
  - every line has the expected start and end and every required field;
  - every enumerated value is valid;
  - headless records have `headless_surface`;
  - off-target and multi_dn records have a non-empty `other_cell_types`.
- Quotes were hand-checked for verbatim wording and the 25-word limit.
