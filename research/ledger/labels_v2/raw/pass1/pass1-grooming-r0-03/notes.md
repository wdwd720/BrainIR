# Session pass1-grooming-r0-03 (pass1) notes

## Assigned sources
1 source: 10.1016/j.cub.2021.12.055 (Guo, Zhang & Simpson 2022, Curr Biol, "Descending neurons coordinate anterior grooming behavior in Drosophila").

## What was tried
- Local `sources/10_1016_j_cub_2021_12_055/`: `text.txt` holds the abstract only (Europe PMC). There are no figures, supplements or page images.
- Web (only routes for this exact DOI):
  - https://doi.org/10.1016/j.cub.2021.12.055 redirects to linkinghub.elsevier.com (PII S0960982221017425).
  - https://www.sciencedirect.com/science/article/pii/S0960982221017425 returned HTTP 403.
  - https://www.cell.com/current-biology/fulltext/S0960-9822(21)01742-5 returned HTTP 403. The PDF URL also returned 403. An earlier guessed Cell PII URL also returned 403.
  - Europe PMC REST (MED:35120659) shows pmcid none, isOpenAccess N, inPMC N, inEPMC N, and no author manuscript. The only full-text link is the DOI, marked "Subscription required".
  - PubMed page 35120659 returned only a cookie notice.
- I did not search for a bioRxiv preprint. The instructions limit fetching to exactly the assigned DOI and forbid searching for other papers, and a preprint has a different DOI. If a preprint exists, a session allowed to use it could get full text there.

## Outcome
- The abstract reports activation outcomes: head sweeps and leg rubs started separately or together by different DNs, and unilateral activation that coordinates leg rubs or decouples the legs into single-sided head sweeps. However, it names **no DN type, no driver line, no effector and no preparation**. A record needs one DN type or driver line (section 1) and a name for `name_in_paper`, so no record could be written, even at `abstract_only`/`low`.
- Disposition: `unreachable` (0 records). This source needs a session with full-text access (Cell Press subscription or the preprint).

## Simulation / score sightings
None. I saw no model, simulation or connectome-activation score. `sightings.csv` was not created.
