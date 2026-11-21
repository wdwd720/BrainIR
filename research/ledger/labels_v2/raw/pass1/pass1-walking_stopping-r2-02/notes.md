# Session pass1-walking_stopping-r2-02 (pass1) — notes

## Assigned source
- 10.1016/j.cub.2019.11.004: Sen, Wang & Dickson 2019, Curr Biol, "TwoLumps Ascending Neurons Mediate Touch-Evoked Reversal of Walking Direction in Drosophila"

## What I read and tried
- Local `sources/10_1016_j_cub_2019_11_004/text.txt`: abstract only (no figures, supplement or page images).
- Web fetch attempts, all for this DOI only:
  - doi.org: redirects to linkinghub.elsevier.com (PII S0960982219314435); the linkinghub page only returned "Redirecting".
  - cell.com full text `S0960-9822(19)31443-5` and its PDF: HTTP 403.
  - ScienceDirect `pii/S0960982219314435`: HTTP 403.
  - Europe PMC REST: isOpenAccess=N, inEPMC=N, no PMCID; the only full-text link is the subscription DOI link. No preprint is listed.
  - PubMed: page needs cookies, so no content.
- I did not search for other papers or preprints with different DOIs.

## Assessment
- The abstract describes optogenetic activation of **TLA ascending neurons**, which triggers backward walking. TLAs are not descending neurons, so this is not a record under section 1.
- MDN (Moonwalker DN, DNp50) appears in the abstract only as a downstream mediator ("TLA-induced reversal is mediated in part by the MDNs"). That evidence presumably comes from MDN silencing combined with TLA activation, plus connectivity and imaging. The abstract reports no MDN activation experiment.
- The full text might still contain a direct MDN activation, e.g. as a positive control. Because I could not check this, I set the disposition to `unreachable`, not `no_qualifying_experiment`. A session with publisher access should check the figures and STAR Methods.
- 0 records written. `out/records.jsonl` is empty.

## Simulation / score sightings
- None seen. No `sightings.csv` written.
