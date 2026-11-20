# Search notes — session `search-search_behaviour`, pass `search`

## What was done
Independent literature search for adult *Drosophila* experiments in which a DN type or DN driver line was
activated (optogenetically or thermogenetically) and leg behaviour was observable. No source list was provided.
This produced 101 records from 20 sources in `records.jsonl`. `sources.csv` lists those 20 sources plus 16 more that
were checked and gave no record.

## Databases and tools
- **Europe PMC REST API** (`/search` and `/PMCxxxx/fullTextXML`): the main way to read full text. Queries:
  - `(moonwalker descending) OR (MDN backward walking Drosophila)`
  - `(descending neurons grooming Drosophila) AND (activation OR optogenetic OR TrpA1)`
  - `("descending neuron" OR "descending neurons" OR "giant fiber") AND Drosophila AND (takeoff OR landing OR escape OR jump) AND (CsChrimson OR Chrimson OR TrpA1 OR optogenetic)`
  - `("descending neuron" OR "descending neurons") AND Drosophila AND (walking OR locomotion OR leg) AND (CsChrimson OR Chrimson OR ReaChR OR TrpA1 OR "optogenetic activation") AND PUB_YEAR:[2012 TO 2026]`, sorted by citations (100 hits screened)
  - Targeted DOI and title lookups for Bidaye 2014, McKellar 2019, von Reyn 2014, Sen 2017, Guo 2022, Wang 2020, Mezzera 2020, Zacarias 2018, Namiki 2022, Ros 2024 and others.
- **Web search** (general): Cande 2018; Bidaye 2020; Braun 2024; Guo 2022; McKellar 2019; Zung/Namiki 2025.
- **Publisher sites, PMC and bioRxiv:** pmc.ncbi.nlm.nih.gov for Bidaye 2020, where Europe PMC timed out. bioRxiv full text for Dahlhoff 2025, Liessem 2025 and Yoshikawa 2023.
- **Reference-list mining:** used the Simpson 2024 review (Curr Opin Neurobiol) to find primary DN-activation studies.

## Access problems (sources I could not read)
- **Cande et al. 2018, the systematic screen:** this is the main gap. Per-line phenotypes for the 130 lines are only
  in Figure 6, which is an image, and in Figure 2–source data 1, an image-only PDF over 10 MB that could not be
  fetched. elifesciences.org did not load. I recorded only the DN types whose phenotype is stated in the text, so
  most of the screen's lines, including the no-effect ones that protocol §1 requires, are missing. A full-text
  reader with figure access should finish this source.
- **Bidaye 2014 (Science):** paywalled. Recorded from the abstract only, at low confidence. The abstract does not
  name the effector, so `effector_kind` = thermogenetic is an unverified assumption, flagged in the record notes.
- **Guo et al. 2022 (Curr Biol; DNg11/DNg12 grooming):** paywalled (403), and the abstract names no DN types, so no
  record. This is an important missing source.
- **McKellar et al. 2019 (aSP22/DNa12):** paywalled. The lab PDF failed with a certificate error, and the abstract
  does not name the DN. No record.
- **von Reyn 2014, Sen 2017:** not open access. The abstracts gave no activation result that could be recorded.
- **Cao et al. 2026 (Curr Biol, threat display):** paywalled. Europe PMC returned HTTP 500 and the thesis PDF was not
  readable. No record.
- **Ros et al. 2024 (DNa15, flight turns):** Europe PMC returned HTTP 500. Not read.
- **Female receptivity/rejection DNs** (Wang 2020/2021, Mezzera 2020: DNp13, vpoDN): not open in Europe PMC; not
  read. These are probably ovipositor/abdomen behaviours with legs not assessed.
- **bioRxiv** rate-limited requests (HTTP 429) several times. The Dahlhoff preprint was eventually read.
- Many full texts are long (over 100k characters). I read them in chunks through an extraction tool, so some
  sections (late Methods, supplementary legends) were not read. Quotes come from the extraction tool's verbatim
  output. A few are short fragments; they are marked in `notes` where relevant.

## Coding decisions and uncertainties
- **Mapping:** names that the kit lists for more than one MANC type (DNp09, DNa01, DNb01, DNg07, DNg08, DNg10,
  DNg12, DNg02, BB/bluebell) got `mapping_confidence` = medium and the exact-name MANC type. Kit synonyms used: P9 =
  DNp09 (paper's own equivalence), aDN1 → DNg62, aDN2 → DNfl023, BDN2 → DNg100, oDN1 → DNg97, Mute → DNad006, GF →
  DNp01. BB was mapped to DNg60 (the ambiguous alternative is DNxn073).
- **UNMAPPED:** DNg25 (not in type_list) and Pair1 (Lee & Doe 2021, R75C02-Gal4).
- **Not DNs:** FG (Foxglove), BRK (Brake), MooSEZ, DopaMeander, BPN, PFL3, wPN1 and L320 were treated as non-DN and
  not recorded. SS02553 was recorded as DNp17 with DopaMeander listed as off-target.
- **Sex:** Braun 2024 behaviour sex was not stated in the text I read, so it is `unknown`.
- **Headless surfaces:** Braun 2024 headless flies were on the spherical treadmill (Supplementary Videos 3–4). For
  Feng 2020 decapitated MDN the surface was assumed to be the ball (flagged). Israel 2022 decapitated flies were
  free in an open arena (`other`).
- **Turning in walking flies** (Yang 2024, Rayshubskiy 2025): leg-rhythm fields are `not_assessed`, per the
  convention.
- **Flight/abdomen-only outcomes** (Namiki 2022; Braun DNg14, oviDN, Mute; pIP10): recorded with legs
  `not_assessed`.

## Simulation and model exposure
- I did not visit GitHub, Zenodo, Pugliese 2026 or Sapkal 2026.
- Some papers contain model or connectome-prediction sections: Sapkal 2024 (connectome-constrained model),
  Liessem 2025 (Fig. S4-1 model), Özdil 2026, and Braun 2024 (Fig. 5 title: network connectivity predicts
  necessity). I told the extraction tool to skip those sections and saw no per-DN simulation scores.
  `saw_simulation_score` = false for all records.
- Search results showed titles of computational-model papers (Shiu et al. 2023/2024 brain model; arXiv "Synaptic
  placement reflects shared input in Drosophila descending neurons"). I did not open them.

## Suggested follow-up
- Finish the Cande 2018 per-line table: read Figure 6 or the source-data PDF, and the Dryad videos.
- Get Guo 2022, McKellar 2019, Bidaye 2014, von Reyn 2014 and Sen 2017 through institutional access.
- Read supplementary tables for line IDs: Braun 2024 Supplementary Table 2, Liessem 2025 Supplementary Table 1, and
  the Sapkal 2024 genotype table.
