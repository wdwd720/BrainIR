# Notes: session pass1-escape_landing-r0-03 (pass1)

## What I did
- Read PROTOCOL.md (v2, incl. section 8), the schema and the six local source folders. All six were abstract-only
  (no figures, supplements or page images).
- As this session allowed, I tried to fetch each assigned DOI from the web: the publisher (doi.org, linkinghub, cell.com,
  sciencedirect.com, nature.com), the Europe PMC REST search, the PMC ID converter and PMC itself. I used Crossref
  metadata only to find the Cell Reports PII and its full-text link. I did not search for other papers.
- I did not look for bioRxiv preprints of these papers: they would have different DOIs, and my instructions limit
  fetching to exactly the assigned DOIs. A later session could check whether preprint versions are allowed.

## Access results
- 10.1073/pnas.1400997111 (Wu et al. 2014): full text on PMC (PMC3986155). One record: 12862-Gal4 > ChR2 giant fiber
  activation, jumping (Fig. 5B-C). The Europe PMC fullTextXML endpoint returned HTTP 500, so I read the PMC HTML page
  through the web-fetch tool, which summarises pages. The quote came back as quoted text, but I could not check it
  against a raw copy. It should be verified. Sex and n were not stated for the jumping experiment.
  The Pain-Gal4 > ChR2 experiment (Fig. 6) is a memory readout, so it is not a DN leg experiment. The NpHR panels are
  silencing.
- 10.1016/j.cell.2005.02.004 (Lima & Miesenböck 2005): cell.com and ScienceDirect returned HTTP 403 and there is no PMC
  copy. One abstract-only record (giant fiber system, jumping), labeler_confidence low. The abstract does not say whether
  flies were intact or headless, so preparation is coded `other`. No driver line is named in the abstract.
- 10.1016/j.celrep.2018.10.048, 10.1016/j.cub.2018.12.019, 10.1016/j.neuron.2017.05.036: every Elsevier host returned
  HTTP 403, the Elsevier API link returned 400, and none are in PMC or Europe PMC. Their abstracts describe no codable
  activation experiment: McKellar 2019 mentions a pair of DNs but names neither the neuron nor a line, and says nothing
  about legs. Disposition: unreachable.
- 10.1038/nn.3741: nature.com served only an auth redirect and the page shell, and there is no PMC copy. The abstract
  covers only recording. Disposition: unreachable.
- A session with institutional access should retry the four unreachable papers and Lima 2005. Their full texts may
  contain GF/DN activation experiments (e.g. CsChrimson) that I could not see.

## Uncertainties
- 12862-Gal4 is not in driver_lines.csv. I proposed it as DNp01 in out/proposed_driver_lines.csv. Its specificity is
  `unknown` because the legend says GF is "preferentially labeled".
- No simulation or model score was seen, so there is no sightings.csv.
