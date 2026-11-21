# Session pass1-steering-r0-03 notes

## Assigned source
- 10.1016/j.cub.2017.02.008: Sen et al. 2017, Curr Biol, "Moonwalker Descending Neurons Mediate Visually Evoked Retreat in Drosophila."

## Access attempts (only for this DOI; no other papers were searched)
- doi.org redirected to linkinghub.elsevier.com, which only returned a "Redirecting" page.
- www.cell.com fulltext, PDF and showPdf URLs: HTTP 403.
- www.sciencedirect.com/science/article/pii/S0960982217301446: HTTP 403.
- Europe PMC REST: isOpenAccess N, inEPMC N, inPMC N, no PMCID, hasPDF N, and the only full-text link is "Subscription required".
- PubMed page: blocked by a cookie wall. I did not look for a bioRxiv version because this DOI has none listed and the instructions forbid searching for other papers.
- Result: only the abstract (sources/.../text.txt) could be read. No figures, legends, methods or supplements.

## Records
- 1 record (pass1-steering-r0-03-0001): MDN, unilateral activation, coded as backward walking with turning. All legs are `yes` under the walking convention, and `labeler_confidence` is low. The outcome comes from the abstract: the unilateral activation experiments "support these hypotheses", one of which is that "turning while walking backward might reflect asymmetric activation of the left and right MDNs".
- Uncertain or placeholder fields:
  - `effector_kind` = `optogenetic` is a schema-forced placeholder. The abstract does not state the effector or whether activation was optogenetic or thermogenetic.
  - `preparation` = `other` means unknown.
  - Sex, driver line, stimulation and n are not stated.
  - It is also not stated explicitly that the unilateral activation used adult flies with leg movement observed. This is inferred from the abstract's framing of "directional locomotor output".
- A full-text pass should verify or correct all of these fields. It may also add records, e.g. bilateral MDN activation controls and epistasis experiments with LC16 activation. LC16 neurons are visual projection neurons, not DNs, so LC16 activation alone would not be a record.
- The abstract sentence that MDN activity is "necessary and sufficient to trigger backward walking [19]" cites earlier work, so no record was made for it.

## Simulation / score sightings
- None seen. No sightings.csv written.
