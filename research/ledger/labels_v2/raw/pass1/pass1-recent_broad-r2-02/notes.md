# Notes: session pass1-recent_broad-r2-02 (pass1)

## Assigned sources
1 source: 10.1016/j.cell.2026.08.015 (Berg et al. 2026, Cell, "Sexual dimorphism in the complete Drosophila male central
nervous system connectome").

## What was tried
- Local `sources/10_1016_j_cell_2026_08_015/`: abstract only (Europe PMC), no figures/supp/pages.
- Web (this session was allowed to fetch this DOI only):
  - doi.org -> linkinghub.elsevier.com: redirect page only, no content.
  - www.cell.com/cell/fulltext/S0092-8674(26)00942-6: HTTP 403.
  - www.sciencedirect.com/science/article/pii/S0092867426009426: HTTP 403.
  - Europe PMC REST: not in PMC, isOpenAccess N, full text "Subscription required".
  - PubMed 42691995: page returned only a cookie notice.
- I did not look for any preprint version or other papers (that is outside this session's scope).

## Outcome
- The abstract describes a connectome resource (166,700 neurons, male/female type comparison). It reports no
  optogenetic or thermogenetic activation of DNs with leg behaviour, so I wrote no records.
- Disposition `no_qualifying_experiment`, decided from the abstract only. **Uncertainty:** connectome papers sometimes
  include small behavioural validation experiments. If someone later gets the full text (Crossref lists a CC BY
  license), they should check the figures and STAR Methods for CsChrimson/TrpA1 experiments. I think a DN leg-activation
  experiment there is unlikely, but I could not rule it out.

## Simulation / score sightings
None. I saw no model, simulation or Pugliese-type score, so I did not create `sightings.csv`.
