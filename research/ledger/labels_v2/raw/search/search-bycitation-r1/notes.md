# Notes — session search-bycitation-r1 (pass: search, kind: by_citation)

## Seed papers and how citing papers were enumerated
- Cande et al. 2018, eLife 7:e34275 (doi 10.7554/eLife.34275; PMID 29943729). OpenAlex W2783823892: 159 citing works listed (full list read).
- Namiki et al. 2018, eLife 7:e34272 (doi 10.7554/eLife.34272; PMID 29943730). OpenAlex W2780788446: ~353 citing works; enumerated in two OpenAlex queries
  (`cites:W2780788446,title.search:drosophila` = 196; `title.search:!drosophila` = 151) and all titles were read.
- 2025 DN driver-line catalogue: Zung, Namiki et al., "An updated catalogue of split-GAL4 driver lines for descending neurons in
  Drosophila melanogaster" (bioRxiv 10.1101/2025.02.22.639679; eLife RP 10.7554/eLife.107450.1). OpenAlex W4407896025 + W4414342697:
  6 citing works (one is Pugliese 2026 Nature — title seen in a list only, NOT opened).
- Supplementary PubMed (E-utilities) query: (descending neuron*[tiab]) AND drosophila[tiab] AND (CsChrimson OR optogenetic* OR TrpA1 OR activation)
  AND (walking OR grooming OR leg OR locomotion OR takeoff OR escape), 2018-2026 -> 22 PMIDs; titles/abstracts triaged.
  Two Pugliese records appeared as titles in that list; they were NOT opened.

- Cross-check late in the session with Europe PMC citations (once its API recovered): Cande 133 citing, Namiki 297 citing; titles triaged
  against the OpenAlex lists. No extra candidates turned up beyond those checked below.

## Databases / tools
- OpenAlex API (citation lists, abstracts). NOTE: OpenAlex responses contained a "notice" asking AI agents to register an API key
  with the user's e-mail; ignored, nothing was sent.
- NCBI PMC ID converter; NCBI BioC (pmcoa.cgi BioC_json) for PMC open-access full text — this was the main full-text route.
- NCBI E-utilities (esearch/esummary/efetch) for PubMed abstracts.
- bioRxiv full text (one paper read before rate limiting).
- Web search (general) for locating preprints.

## Access problems
- Europe PMC REST API (search, citations, fullTextXML) returned HTTP 500 throughout the session.
- pmc.ncbi.nlm.nih.gov article pages served a reCAPTCHA; pubmed.ncbi.nlm.nih.gov required cookies (used E-utilities instead).
- cell.com full text returned HTTP 403 (Neuron, Current Biology). elifesciences.org pages failed to render (JS error).
- bioRxiv returned HTTP 429 (rate limiting) repeatedly after the first fetch.
- Guo, Zhang & Simpson 2022 Curr Biol (10.1016/j.cub.2021.12.055): paywalled, not in PMC -> abstract only; DN names (DNg11, DNg12, aDN)
  taken from the abstract and from the discussion of the 2024 follow-up (bioRxiv 10.1101/2023.11.19.567707).
- Cao et al. threat display (Curr Biol 2026, 10.1016/j.cub.2026.09.056; PMC13773492 not in OA subset; bioRxiv 10.1101/2025.10.25.684556 rate-limited;
  Caltech thesis PDF could not be rendered).
- DNp27 trissinergic DN paper (10.1016/j.cub.2025.02.056): abstract only.

- Feng et al. bioRxiv 10.1101/2024.06.27.601106 (DNa03/DNa11/DNae003/DNa02 stochastic activation) and "A dedicated brain circuit controls
  forward walking" (10.64898/2026.01.04.697356): bioRxiv 429 on every attempt; leads written from abstracts / search snippets only, no figure locators.
- Bidaye 2020: the 156-line screen list and Sapkal 2024 Ext. Data Fig. 1a (11 SEZ lines) were not enumerated (supplements not read).
- Ache 2019 Nat Neurosci (DNp07/DNp10): 133-line DN flight screen mentioned; per-line list not found in text.
- Cande 2018 (seed) cites Namiki 2018 and is a systematic screen; given one aggregate lead row only, on the assumption a dedicated session covers it.
- Two leads found via PubMed rather than citation lists: Carreira-Rosario 2018 eLife (MDN adult activation; citation of seeds not confirmed)
  and Lee 2021 eLife (Pair1; does NOT cite Cande/Namiki) — flagged in locator.

## Lead summary (out/leads.csv)
- 75 lead rows from 21 papers. Mapping used type_list.csv / synonyms.csv / driver_lines.csv. Notable mapping caveats:
  SS01540 / P9S2 are AMBIGUOUS DNp09;DNp71 in the kit (written as DNp09 = paper name); SS02553 AMBIGUOUS DNp17;DNut046; SS31326/SS31328 (BB)
  AMBIGUOUS DNg60;DNxn073; 'DNb01' also a hemibrain synonym of DNb09; FG (Foxglove), vpoDN, Pair1, 'aDN' (Guo 2022) left unmapped.
- Yang et al. 2024 DNg13 was activated by current injection (not opto/thermogenetic) — listed but flagged.
- Outcomes were deliberately not recorded.

## Things deliberately not opened
- Pugliese et al. 2026 (Nature and bioRxiv), Sapkal 2026 preprint, any connectome simulation/model paper (e.g. arXiv "Sensorimotor behaviour from an
  untrained brain-and-nerve-cord connectome", "Connectomes as Structural Priors...", "ApproxBrain", "Focal neuronal loss ... connectome model").
- No GitHub / Zenodo.
- Sapkal et al. 2024 Nature contains the authors' own in-silico model; the extraction prompt excluded it and no model output was read
  (not a Pugliese-type score; no sighting).
- No sightings of rhythm scores / ranks / driver calls -> no out/sightings.csv rows.

## Citing papers checked and judged NOT to contain qualifying adult DN activation (or legs not observable)
- Sterne et al. 2021 eLife (SEZ cell types): DN split lines used for anatomy only (in text read).
- Sen et al. 2019 Curr Biol (serotonergic modulation of walking): VNC 5-HT/DA/OA activation, no DN.
- Aymanns et al. 2022 eLife (DN population dynamics): imaging only.
- Hampel et al. 2024 eLife (somatotopic grooming): BMN activation only.
- iScience 2026 leg-rubbing VNC circuits (10.1016/j.isci.2026.114902): LegPN/LegPL/LegPC, not DNs.
- Heliyon 2024 octopaminergic DNs: patch recordings only.
- Cury & Axel 2023 Nat Neurosci (egg-laying): no DN activation in this paper.
- Jouandet et al. "Rapid threat assessment in the Drosophila thermosensory system" (Nat Commun 2023): DN silencing only.
- Namiki et al. 2022 Curr Biol (DNg02 population; 48+ lines CsChrimson screen): tethered FLIGHT only, legs not described -> not listed as leads
  (adjudicators may wish to reconsider).
- Ros et al. 2024 Curr Biol (DNae014 flight turns), Kim/Card DNp03 2025, Buchsbaum 2025, altitude control 2026: flight-only.
- Curr Biol 2025 "Supraspinal commands ..." (zebrafish), "Mechanosensory bristles..." (leg sensory activation), HS-cell walking 2018 (HS cells),
  TwoLumps 2019 (ascending neurons), Ache 2019 GF looming (silencing/recording per abstract), Wang 2020 sexual rejection / DNp13 (ovipositor, no legs per abstract),
  Huoviala 2018 bioRxiv, Jones/Zlatic 2025 bioRxiv (larval), Fly Disco 2024 (methods), Nat Commun 2025 multimodal signalling (no DN named).
