# Notes: session pass2-general-web-01 (pass2), phase 1

## What I did
- Read PROTOCOL.md (v2, including section 8), the schema, the kit files and all 5 local sources. All 5 local copies were abstract only, with no figures or supplements.
- Web fetches went only to the assigned DOIs, through the publisher / PMC / Europe PMC:
  - 10.1073/pnas.1400997111: full text read on PMC (PMC3986155). The fetch tool summarises pages, so I made a second request asking only for the verbatim sentence. The quote in record 0004 comes from that request. Figure images were not inspected.
  - 10.1016/j.cell.2005.02.004, 10.1016/j.cub.2017.02.008, 10.1016/j.neuron.2010.12.017: cell.com / sciencedirect / linkinghub returned HTTP 403. None of them has a PMC copy (meta.json pmcid = null).
  - 10.1126/science.1249964: science.org returned HTTP 403. No PMC copy.
  - Europe PMC REST returned HTTP 500 on every query.
  - I labelled these four papers from their abstracts: `access` = `abstract_only`, `labeler_confidence` = `low`. They should be relabelled if a session can get the full text.
- I did not visit GitHub, Zenodo or the papers in PROTOCOL section 6. I saw no simulation or model score (sightings.csv has only its header).

## Records (5; one per experiment row; every row was found, so not_found.csv has only its header)
- 0001 Lima & Miesenböck 2005: "giant fiber system" → DNp01, mapping medium. The word "system" may include partner neurons that are not DNs, and the abstract names no line. Outcome: jump, wing beating and flight, so legs `no`.
- 0002 Sen et al. 2017: MDN, unilateral activation. Outcome: backward walking with turning, based only on the abstract's hypothesis plus "data ... that support these hypotheses".
- 0003 Kohatsu et al. 2011: the kit marks "P2b" as ambiguous (DNxl053 / pIP10). The abstract gives no anatomy that separates the two, so the type is UNMAPPED. Legs are `not_assessed` because the abstract does not describe the courtship acts.
- 0004 Wu et al. 2014 (PNAS): 12862-Gal4 > ChR2, giant fiber → DNp01 (high). Outcome: jumping, so legs `no`. n = 8. Sex is coded male from the Methods sentence about "the male" in the optogenetic experiments. The line is proposed in proposed_driver_lines.csv.
- 0005 Bidaye et al. 2014: MDN. Outcome: backward walking, so legs `yes`.

## Uncertainties
- **effector_kind in records 0002 and 0005 is a placeholder.** Neither abstract states the effector, but the schema requires `optogenetic` or `thermogenetic`. The values I entered are not supported by any source. Check them against the full text.
- Records 0002 and 0005 keep the given `preparation` = `other` because the abstracts do not show the preparation.
