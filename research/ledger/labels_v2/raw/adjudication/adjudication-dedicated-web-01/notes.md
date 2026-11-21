# Notes: adjudication-dedicated-web-01 (pass: adjudication)

## Work done
- Read PROTOCOL.md in full, plus the schema, disagreements.csv, assigned_sources.csv and the local source folder.
- One disputed experiment: `pass1-dedicated-r0-02:pass1-dedicated-r0-02-0002` (Pugliese et al. 2026, SS70620 / DNb08,
  headless, CsChrimson). Disputed field: `line_specificity` (`unknown` vs `clean`).

## Access
- Local source `sources/10_1038_s41586_026_11195_y/` has only the abstract (Europe PMC). It has no figures, supplement or pages.
- Allowed web fetches tried:
  - bioRxiv v2 `.full`, `.full-text`, `.full.pdf` and v1 `.full`: all HTTP 429 (Too Many Requests), 6 attempts in total.
  - nature.com article: 303 redirect to idp.nature.com login. Not followed, because it is an authentication/paywall route.
  - Europe PMC REST: the preprint is PPR1083778 (inEPMC N) and the fullTextXML endpoint returned HTTP 500. The Nature
    article has no PMCID.
- So I could not read Fig. 5c-e, its legend, the Methods or Supplementary Video 2. The decision rests on the abstract only.

## Decision
- `line_specificity` = `unknown`. The abstract says nothing about the expression pattern of SS70620. The kit's
  driver_lines.csv lists SS70620 as DNb08 with no other cells (ZungNamiki2025), but that is kit metadata, not this
  paper's statement, so I did not use it to justify `clean`. If a later session can read the Methods or figures and
  they describe the line as specific, `clean` would be justified.
- The record is abstract-only: `access` = `abstract_only` and `labeler_confidence` = `low`. The per-leg rhythm fields are
  `unclear` because the abstract says "rhythmic leg movements" without naming legs. `headless_surface` = `other`
  because the surface could not be read. The non-disputed fields came from readers who had the full text, so their
  values should take precedence over this abstract-only record.

## Score sighting (section 8)
- The local abstract itself states a simulation prediction that DNb08 drives rhythmic leg movements (driver call). It
  also names DNg100 as the strongest driver in the computational activation screen (rank). I logged both in
  `out/sightings.csv` and set `saw_simulation_score` = true on the DNb08 record. No DNg100 record was written.
- No other model or simulation content was viewed. GitHub, Zenodo and Sapkal et al. were not opened.
