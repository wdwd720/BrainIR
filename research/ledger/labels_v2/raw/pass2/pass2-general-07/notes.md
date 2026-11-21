# pass2-general-07 — notes (phase 1)

Session `pass2-general-07`, pass `pass2`. I read only the local copies in `sources/`. I made no web access and opened no model, simulation or prediction.

## What was read
- **10.1371/journal.pone.0267834** (Luo et al. 2022, PLoS One): I read the full text, Table 1 and Figs 2–3. The S1/S2 movies were not downloaded and are not needed.
- **10.1038/s41467-025-64907-9** (Steinfath et al. 2025, Nat Commun): I read the full text, Table 1, Figs 3–4, the supplementary information (Fig. S4 legend) and the peer-review file (as far as it was relevant). The paper's own circuit model (pIP10/DNvib, Fig. 6) does not count as a sighting under §8. I did not use it.
- **10.1016/j.cub.2026.07.076** (Palacios Castillo et al. 2026, Curr Biol): I read the full text, which is an author-manuscript XML. The local copy has no figures, supplementary tables or Table S1.

## Records: 7 written, 0 not found
All 7 experiments were found. None has `saw_simulation_score` = true, and there were no sightings (`sightings.csv` has only its header).

## Uncertainties and decisions
1. **"DNp28" → DNp29 (record 0003).** Nat Commun Table 1 names the line `DNp28 (SS01587)` with the genotype R11H10-p65.AD; VT033947-GAL4.DBD. `driver_lines.csv` maps SS01587, with these same two hemidrivers, to **DNp29** (two Namiki 2018 entries). The kit's DNp28 line is SS01056 (R17A04 x R24A03). I mapped by driver line to DNp29 at `medium` confidence and kept `name_in_paper` = DNp28. I did not propose "DNp28" as a synonym of DNp29. **Adjudication should check this.**
   - The behaviour is locomotion induced in a female being courted, measured only as centroid velocity (~1 → ~12 mm/s). Following the "increased locomotion without leg tracking" convention, I coded all legs `yes` at medium confidence. The paper does not state the walking direction.
2. **VL neurons (records 0001/0002).**
   - The paper says the VL cluster has two descending subtypes, VL1 and VL2. Using the kit synonyms OA-VL1 → DNd02 and OA-VL2 → DNd03, sorted alphabetically, sibling 1 = DNd02 and sibling 2 = DNd03.
   - The text does not name the split-GAL4 line(s) used for "VL neurons" in Fig. 6B, and Fig. 6 is not available locally. I therefore cannot verify that the tested line labels both types. The key resources table lists SS01545, which the kit maps to DNd02 only. I set `line_specificity` = unknown and `labeler_confidence` = low.
   - The only reported outcome for VL is aggression (lunges were not reduced). No leg or locomotion outcome is given for VL lines, so the legs are `not_assessed` and the category is `other`. These records carry essentially no leg information, and adjudication may decide they do not qualify under §1.
   - I proposed VL1/VL2 as synonyms in `proposed_synonyms.csv`.
3. **DNp09 / SS1540 (record 0007).**
   - The kit lists the name DNp09 as ambiguous (MANC DNp09, or DNp71 via the hemibrain name), and SS01540 is AMBIGUOUS. I chose DNp09 at medium confidence because the paper uses Namiki nomenclature. It gives no anatomy.
   - The paper itself attributes the freezing possibly to other neurons in the line, so I set `minor_offtarget`.
   - The preparation is tethered with no tarsal contact. The behaviour is freezing (legs `no`, `stops`/`halting`).
   - About 20% of non-retinal-fed flies also froze.
4. **GF (record 0006):** the paper explicitly says GF = DNp01. The behaviour is takeoff (single movement, legs `no`). The tethered flies were not walking, so walking is `not_assessed`.
5. **pIP10 / pMP2 (records 0004/0005):** both drove song only (all males sang, none vibrated). The legs are not described, so they are `not_assessed`. The record uses the strongest intensity of the series as given (1–14 mW/cm2).
6. Penetrance values for the PLoS One figures were read off the bar charts and are approximate.

## Unreachable / missing
- The Curr Biol 2026 figures (Fig. 4A line summary, Fig. 6B/D), Table S1 and Data S1 are not in the local copy. A session that can fetch them could identify the VL line(s) and check whether Fig. 6D includes VL locomotion.
