# Session pass1-recent_broad-r1-02 (pass1) — notes

## What I tried (web fetch was permitted for exactly the assigned DOIs)
- Europe PMC REST search (by DOI, several query forms) and europepmc.org: HTTP 500 or 403 every time (2026-11-20).
- PMC ID converter (pmc.ncbi.nlm.nih.gov idconv): all three DOIs "Identifier not found in PMC". elink pubmed->pmc returned only citing-paper links, no self PMC versions. PubMed XML ArticleIdList has no PMC IDs.
- Publisher: doi.org -> linkinghub (a redirect stub only); cell.com fulltext/abstract and sciencedirect.com: HTTP 403.
- NCBI E-utilities (esearch/efetch on PubMed): worked. PMIDs: 32795445 (Wang 2020), 32795437 (Mezzera 2020), 40107265 (Jiang 2025). This gave me the abstract of Jiang 2025, which was missing from the local folder.
- I did not use bioRxiv: preprints have other DOIs, and finding them would have meant searching for other papers.
- Crossref metadata for 10.1016/j.cub.2025.02.056 had no abstract.

## Outcome
- No records written (`out/records.jsonl` is empty). All three sources: disposition `unreachable` (full text). Each abstract was read.
- Why there are no abstract-only records: section 1 requires optogenetic or thermogenetic activation, and `effector_kind` is a required enum. None of the abstracts (or PubMed keywords/MeSH) states the effector. Writing a record would mean guessing that field. Leg observations are also not described.
  - Wang et al. 2020 (10.1016/j.cub.2020.07.083): "We show that the DNp13 descending neurons act as command-type neurons for ovipositor extrusion" (abstract). This is probably an activation experiment, but it is an abdominal behaviour; under section 3, legs would be `not_assessed` unless described. Kit lines from this paper: SS61089, SS61090 (DNp13; driver_lines.csv). DNp13 maps with high confidence (MANC type name).
  - Mezzera et al. 2020 (10.1016/j.cub.2020.06.071): the abstract reports only silencing of the ovipositor-extrusion DN pair (not named in the abstract). Whether there is an activation experiment is unknown.
  - Jiang et al. 2025 (10.1016/j.cub.2025.02.056): the abstract says "artificial activation of DNp27 decreased flies' activity". The abstract does not say how activity was measured, so whether this counts as a leg/locomotion readout needs the full text. This is the best candidate for a fetch session with full-text access. Note: this quote came through the WebFetch summariser, not from a local file, so verify it before use. DNp27 is a MANC type in type_list.csv.
- No simulation scores, ranks or driver calls were seen, so there is no `sightings.csv`.
- No proposed synonyms or driver lines.
