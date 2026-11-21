# Notes: adjudication-general-web-01 (pass: adjudication)

## Source
- 10.1016/j.neuron.2010.12.017 (Kohatsu, Koganezawa & Yamamoto 2011, Neuron). The local copy has only the abstract (Europe PMC: no PMC ID, not open access).
- Web fetch attempts, all on the publisher for this DOI only: doi.org (redirected to linkinghub.elsevier.com), cell.com fulltext, sciencedirect.com/pii/S0896627310010408. cell.com and sciencedirect.com both returned HTTP 403. No open full text was available, so I adjudicated from the abstract: `access` = `abstract_only`, `labeler_confidence` = `low`.

## Decision
- `line_specificity`: I chose **unknown** (reading B), not minor_offtarget (reading A). The P2b activation is from fru-GAL4 MARCM clones. In those clones, behaviour correlated with "P1, P2b, or both". The abstract does not list what else each P2b clone labelled or how much. `minor_offtarget` would also need named `other_cell_types` that I cannot source. I set `expression` to `stochastic` because the clones are MARCM.
- `manc_type` (not disputed): the kit marks P2b as ambiguous (DNxl053 / pIP10). The abstract gives no anatomy to choose between them, so I wrote UNMAPPED with mapping_confidence `low`.
- Legs: the abstract names "courtship acts" but does not describe leg movements. I set all leg fields to `not_assessed`, `behaviour_category` to `other` and `effect_on_walking` to `not_assessed`. A reader with the full text should check the leg fields (e.g. foreleg tapping, following/walking).

## Sightings
- None. I saw no simulation or model score. No sightings.csv was written.
