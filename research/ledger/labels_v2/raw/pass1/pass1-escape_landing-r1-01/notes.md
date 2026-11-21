# Session pass1-escape_landing-r1-01 (pass1)

## Assigned source
- 10.1016/j.cub.2019.01.079: Ache et al. 2019, Curr Biol, "Neural Basis for Looming Size and Velocity Encoding in the
  Drosophila Giant Fiber Escape Pathway".

## What was in the room
`sources/10_1016_j_cub_2019_01_079/` held only metadata (`text.txt` says UNREACHABLE). There were no figures, supplements or page images.
Crossref lists a CC-BY 4.0 licence, so an open version might exist, but I could not reach one.

## Web routes tried (only for this DOI; no other papers searched or opened)
| route | result |
|---|---|
| https://doi.org/10.1016/j.cub.2019.01.079 | 302 to linkinghub.elsevier.com, which gave only a "Redirecting" stub |
| sciencedirect.com/science/article/pii/S0960982219301381 | HTTP 403 |
| cell.com fulltext and abstract pages (S0960-9822(19)30138-1, plus a mistaken PII first) | HTTP 403 |
| Europe PMC REST search (DOI query, several forms) and article/MED endpoint | HTTP 500 every time (same transient error the downloader logged) |
| europepmc.org web search | HTTP 403 |
| PMC ID converter | "Identifier not found in PMC" |
| PMC search for the DOI | returned one unrelated paper (eLife 90905). I did not open it. |
| bioRxiv pubs API for this published DOI | "Preprint for DOI ... not found" |
| PubMed search page | cookie notice only, no content |

## Outcome
- I read no abstract and no full text, so I wrote **no records** (`out/records.jsonl` is empty). Disposition: `unreachable`.
- I did not use my own memory of the paper's content as evidence.
- I saw no simulation or model score, so there is no `sightings.csv`.
- Suggestion for a later session: retry Europe PMC when its API is back up, or use institutional access to Cell Press. The
  CC-BY licence suggests a PMC or Europe PMC open version may exist (for example under a PMID that could not be resolved here).
