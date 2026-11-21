# Session pass1-driver_line_resources-r0-03 — notes

## Access attempts (web fetching allowed for this session, assigned DOIs only)
For all three sources the local `sources/` folders held the Europe PMC abstract only, with no figures, supplements or pages.

- Publisher pages: `cell.com/.../fulltext/<PII>` and `sciencedirect.com/science/article/pii/<PII>` returned HTTP 403 for all three. `linkinghub.elsevier.com` returned only a "Redirecting" stub.
- Europe PMC REST: no PMCID, isOpenAccess=N, inEPMC=N for 10.1016/j.cub.2019.02.019 and 10.1016/j.neuron.2010.12.017. The local meta.json shows the same for 10.1016/j.neuron.2011.01.011.
- PMC ID converter: "Identifier not found in PMC" for all three DOIs.
- I did not look for preprints or other papers (bioRxiv versions would have different DOIs). I did not visit any forbidden site.

## Decisions
- **Kohatsu et al. 2011 (10.1016/j.neuron.2010.12.017):** I wrote 1 record (P2b, dTrpA1, MARCM, so expression is `stochastic`). The abstract ties courtship initiation to P1, P2b or both, so P2b's sufficiency on its own is uncertain. The abstract describes no leg acts, so all leg fields are `not_assessed` and `behaviour_category` = `other`. The kit maps "P2b" to two types (DNxl053, pIP10; ambiguous) and the abstract gives no anatomy to choose between them, so `manc_type` = `UNMAPPED`. Confidence is low.
- **Ding et al. 2019 (10.1016/j.cub.2019.02.019) and von Philipsborn et al. 2011 (10.1016/j.neuron.2011.01.011):** both abstracts mention DNs driving song (pIP10 in von Philipsborn). Neither states the effector, driver line, preparation or any leg observation, so I could not code a record with a supporting quote without relying on memory (not allowed). Both are marked `unreachable` so that a session with full-text access can check the figures and methods.

## Simulation sightings
None. No `sightings.csv` was written.
