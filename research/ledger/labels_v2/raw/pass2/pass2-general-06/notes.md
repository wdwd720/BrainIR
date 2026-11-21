# pass2-general-06: notes (phase 1)

## What I did
- Read PROTOCOL.md (v2, including section 8) and the kit files: type_list, synonyms, driver_lines and record_schema.
- Labelled all 16 rows of `experiments_to_label.csv` from the local copies in `sources/`, one record each (`pass2-general-06-0001` to `-0016`). Every experiment was found, so `not_found.csv` has only its header.
- All rows had `n_siblings` = 1, so no sibling ordering was needed. The two dsx-GAL4 ∩ Otd-Flp intersection experiments (Li et al. 2024, Fig. 4) were already split by the input into separate DNp13 and vpoDN rows. I marked each of those records `multi_dn` and named the other DN.
- I used no web access, opened no model or simulation outputs, and visited none of the sites in PROTOCOL section 6.
- **Sightings: none.** No Pugliese or Sapkal rhythm score, rank or driver call appeared in any source I read, so I did not create `sightings.csv`. `saw_simulation_score` is false everywhere.

## Points of uncertainty
- **Legs are mostly not assessed.** In 14 of the 16 experiments the behaviour is abdominal (VPO, oviposition, abdomen bend, egg deposition) or wing spreading, and the sources do not describe the legs. Those records have all leg-rhythm fields set to `not_assessed` and `behaviour_category` set to `other`.
- **DNa02 (steering preprint).** Only already-walking flies were analysed, so the record is coded as turning with legs `not_assessed` (section 3). Step-level effects (shorter ipsilateral return stroke) are in `coordination_notes`. Bilateral expression, in which forward velocity drops, is a different condition (Fig. S4) and was not requested.
- **Foxglove (PNAS).** Coded as halting, with all leg-rhythm fields `no` and `effect_on_walking` = `stops`, at medium confidence: halting is used as a tool and not quantified, and there is no control. Mapped to `UNMAPPED`. The kit lists only SS40909 (the reverse AD/DBD pairing) as Foxglove, also UNMAPPED. The paper does not say these are DNs.
- **vpoDN is `UNMAPPED`.** The name (also pMN2) is not in the kit. driver_lines.csv gives "DNp37" for other vpoDN split lines, but DNp37 is not a MANC type in type_list.csv. I made no proposed synonym because I could not establish a MANC type from the source.
- **oviDN maps to the kit's MANC type `oviDN` (high).** Kit conflict: synonyms.csv lists pMP1 as an oviDN synonym (Wang 2020a), but Wang et al. 2020 Extended Data Fig. 1 calls pMP1 "an unrelated cell" that oviDN-SS2 weakly labels. I coded oviDN-SS2 as `minor_offtarget` with pMP1 as the off-target cell. The kit row deserves a check.
- **Wang et al. 2020, Fig. 2 rows.** The text does not say which oviDN split line was used, so `driver_lines` is []. The Fig. 1/2 images and the Supplementary Tables of this source were not downloaded (XML text only); this did not block any record.
- **Vijayan et al. 2023.** The paper names only "oviDN-SS1". Supplementary Table 1 gives the hemidrivers VT050660-AD; VT028160-DBD, which driver_lines.csv identifies as SS46540, so I listed both IDs.
- **Li et al. 2024, headless rows.** Decapitated flies stood on the arena floor, so `headless_surface` = `other`.
- No `preparation` value was changed from the input.

## Files
records.jsonl (16), dispositions.csv (6 sources, all `records`), sources.csv, not_found.csv (empty). No proposed_synonyms or proposed_driver_lines files.
