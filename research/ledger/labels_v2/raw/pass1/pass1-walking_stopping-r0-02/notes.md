# Notes: session pass1-walking_stopping-r0-02 (pass1)

## Assigned source
- 10.1126/science.1249964, Bidaye et al. 2014, Science, "Neuronal control of Drosophila walking direction."

## What I tried
- Local `sources/10_1126_science_1249964/`: abstract only (no figures, supplements or pages).
- https://www.science.org/doi/10.1126/science.1249964 and /doi/full/...: HTTP 403 (paywall/blocked).
- Europe PMC REST (DOI query): isOpenAccess N, inPMC N, no PMCID; the only full-text link is the subscription DOI.
- PubMed page: only a cookie wall came back, so I got no extra content.
- I did not search for other papers or preprints, as the instructions say.

## Outcome
- 1 record (MDN, backward walking, from the abstract sentence "...is sufficient to trigger backward walking under conditions in which flies would otherwise walk forward").
  access = abstract_only, labeler_confidence = low.
- Uncertain fields: the abstract does not name the effector, the activation method, driver lines, sex, preparation, stimulation or n.
  `effector_kind` is a required enum, so I entered `thermogenetic` as a **placeholder that the reachable text does not support**. A full-text pass must check it.
  `preparation` = `other` means "not stated". `effect_on_walking` = `not_assessed` (a change of walking direction does not fit the stops/slows/speeds/turns vocabulary).
- MAN is an ascending neuron, not a DN, so it has no record.
- A full-text pass will probably split this into several records (different lines, effectors, preparations).

## Simulation scores
- I saw none. No sightings.csv.
