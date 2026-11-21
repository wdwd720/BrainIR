# Notes — session `search-bybehaviour-r1` (pass `search`, kind `by_behaviour`)

## What this session produced
- `out/leads.csv`: 112 lead rows, one per (paper, DN type or line tested). I did not record any outcomes; the locators only point to where each experiment is. `manc_type` was filled only where `type_list.csv` / `synonyms.csv` map the paper's name to exactly one MANC type. It is left empty where the kit flags the name or line as ambiguous (e.g. DNp09 = DNp09;DNp71; DNa01 = DNa01;DNxl022; DNb01 = DNb01;DNb09; DNp17 = DNp17;DNut046; bluebell/BB = DNg60;DNxn073; P2b) or where the name is not in the kit (DNg25, Foxglove, Pair1, DNae014, DA-DNs).
- `out/sightings.csv`: 3 rows. All three come from WebSearch result snippets or answer text, not from pages I opened (see below).
- No `records.jsonl`, `sources.csv` or `dispositions.csv`. This is a search-pass session that writes leads only, and no local sources were assigned, so the section-8 disposition contract has no assigned sources to cover.

## Strategy (behaviour-first)
I started from behaviours and methods, then followed papers, their citing papers and reference lists. Families searched: walking (forward, backward), stopping/freezing/halting, grooming (anterior, antennal, abdominal, thoracic, wing), steering/turning, escape/takeoff, landing/leg extension, posture/reaching, courtship/aggression/threat, egg-laying, and headless/decapitated preparations. I also searched for thermogenetic (TrpA1, FlyMAD) and older chemo-optical (P2X2) work.

### Queries used (WebSearch)
- optogenetic activation descending neurons Drosophila walking CsChrimson
- descending neuron activation backward walking Drosophila moonwalker
- descending neurons grooming Drosophila activation command
- Guo Zhang Simpson 2022 Descending neurons coordinate anterior grooming (+ bioRxiv preprint search)
- Braun Hurtak Ramdya Descending networks transform command signals (PMC)
- Sen 2017 Moonwalker retreat; Israel 2022 MooSEZ; Bidaye 2020 P9/BPN; Zacarias 2018 freezing
- giant fiber optogenetic takeoff; von Reyn 2014/2017; Lima & Miesenböck 2005; FlyPEZ (Williamson 2018); Ache 2019 Curr Biol; GF aging PLOS Biol; Titlow 2015 teaching module; GF predation (Chai 2024/2025: silencing only, not a lead)
- landing DNp07 DNp10 (Ache 2019 Nat Neurosci; Liessem 2025 bioRxiv)
- Dombrovski 2023 takeoff direction DNp02/DNp04/DNp11; LC4-DN UChicago thesis
- Yang 2024 Cell steering; Rayshubskiy eLife 2025 steering; Feng 2024 central steering circuit (v2 retitled)
- Sapkal 2024 Nature halting (Foxglove, Bluebell, Brake, oDN1, BDN2)
- Dallmann 2025 Nature proprioception (DNg100 activation)
- Ozdil 2024 grooming (model paper with JO activation; not a DN lead)
- Lee & Doe 2021; Carreira-Rosario 2018 (adult MDN, Pair1)
- Sterne 2021 SEZ split lines (anatomy only as far as I could tell; not a lead)
- thermogenetic TrpA1 DN screens; FlyMAD
- McKellar 2019 aSP22; Kohatsu 2011; von Philipsborn 2011; Kimura pMN1
- courtship pursuit DNs; aggression DNs (CL062/L320); threat display (Duistermars 2018: AIP neurons, not DNs; Cao thesis: DNp60/DNpe050)
- egg-laying oviDN (Cury & Axel 2023; Vijayan 2023; Wang 2020); female rejection DNp13 (Wang 2020; Mezzera 2020)
- Tschida & Bhandawat 2015 DA-DNs
- review "Descending control of motor sequences in Drosophila" (PMC11215313), used to mine its reference list
- nociception/kicking DNs (only sensory-neuron activation found)
- headless/decapitated DN activation screens

### Databases and sites used
- PMC (often blocked by reCAPTCHA). The Europe PMC REST endpoint `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC<ID>/fullTextXML` worked and was my main full-text route: PMC11446846, PMC12778575, PMC12279373, PMC7710706, PMC9849133, PMC4393157, PMC11215313. PMC6031430 (Cande), PMC4599031 (Hampel), PMC11179149 (Yoshikawa) and PMC11186778 (Braun) opened directly. Europe PMC search returned 500 several times; one search worked (it showed Guo 2022 is not in PMC).
- bioRxiv: opened 10.1101/2025.07.22.666129 and 10.64898/2025.12.13.693955. Heavy 429 rate-limiting stopped me reading 10.64898/2026.01.04.697356 (Dallmann, Roadrunner), 10.1101/2024.06.27.601106 (Feng steering, v1 and v2), 10.1101/2020.11.23.393819 (MooSEZ preprint) and 10.1101/798439 (Bidaye 2020 preprint).
- eLife website pages failed to render (JS error). Cell.com and ScienceDirect returned 403. Nature.com redirected to an auth page. PubMed needed cookies.
- Caltech thesis page (abstract only), UChicago knowledge repository (known only from search snippets), eScholarship (empty or binary).

## Could not access or verify (needs a fetch session)
- Guo et al. 2022 Curr Biol (10.1016/j.cub.2021.12.055): paywalled, not in PMC. The DNg11 line IDs (ss02391, ss01579, ss01550, ss02617) come from a search snippet only.
- Bidaye 2014 Science (MDN): paywalled; figure locators not taken.
- Sen 2017 Curr Biol, Israel 2022 Curr Biol, von Reyn 2017 Neuron, Williamson 2018 Cell Rep, Lima 2005 Cell: cell.com 403. Sen 2017 is open archive but the fetcher was blocked.
- Bidaye 2020 Neuron (PMC9435592): Europe PMC returned 500 and bioRxiv returned 429. Screen line list not checked.
- Feng 2024 bioRxiv, Dallmann 2026 bioRxiv: rate-limited, so leads rest on search snippets.
- McKellar 2019 PDF: downloaded but could not be rendered (no pdftoppm), so the figure locator is missing.
- Cao 2027 Caltech thesis, UChicago LC4-DN thesis, eScholarship thesis qt79q0480f: PDFs not readable as text.
- Curr Biol 2025 DNp03 paper (PMC12977095): Europe PMC 500; DOI not retrieved.
- Cell 2026 male CNS connectome (courtship-pursuit DNs): unclear whether it includes activation or only silencing; DOI not retrieved.
- Published Curr Biol 2026 version of Dahlhoff et al. (walking direction): DOI not retrieved, so the lead uses the preprint DOI.
- JNeurosci 2024 aggression paper: DOI inferred from the URL pattern (10.1523/JNEUROSCI.0142-24.2024); needs verification.

## Cande et al. 2018 screen
The paper reports every screened line (about 130 split lines, 58 cell types) in Figure 2–source data 1 (an image-only PDF inside a zip). I did not re-OCR it. I wrote leads for the types and lines named in the text (Figs 2, 4, 6B and the Discussion) plus one aggregate row for the full screen. The kit's `driver_lines.csv` already lists the line IDs extracted from that source data (source DOI 10.7554/eLife.34275). The per-cell-type panel Fig. 6B is an image, so only the types named in the text were captured.

## Score sightings (Section 8)
Three WebSearch results contained text about the Pugliese connectome activation screen: DNg100 described as the top or strongest simulated driver, and a statement about the simulation's prediction for DNg100 drive. I never opened the Pugliese pages (bioRxiv 10.1101/2025.09.12.675944, Nature 10.1038/s41586-026-11195-y, PMC13142387, the Tuthill-lab PDF) or the 2026 Sapkal preprint (10.64898/2026.04.29.721658), which also appeared in search results. The sightings are logged in `out/sightings.csv`; the affected type is **DNg100**, so any record written for DNg100 from these leads should carry `saw_simulation_score = true`. Search snippets also mentioned an experimental DNb08 headless result attributed to the Pugliese paper, and Sapkal-2026 co-activation experiments (via The Transmitter). I did not add either as a lead, because both sources are off limits. I saw no score, rank or driver call for DNb08 or any other type.
Two papers contain their own models: Liessem 2025 (a LIF model of the LPLC4 cluster) and Sapkal 2024. These are not Pugliese-type screens and are not sightings.

## Judgement calls and caveats
- These leads are included but flagged as borderline:
  - Tschida & Bhandawat 2015: P2X2 with focal ATP is chemogenetic, not opto- or thermogenetic.
  - Lima & Miesenböck 2005: P2X2 with photo-uncaged ATP.
  - Dallmann 2025: DNg100 activation during imaging; unclear whether leg movement was scored.
  - Yang 2024: the DNg13 line's off-target ascending neuron.
  - Flight-only or abdominal studies (DNp03 flight saccades, oviDN, DNp13, pIP10 song), where legs may not be described.
- Excluded as not DN activation: MGT/Mago-no-Te (VNC neuron), wPN1 (VNC), LegPNs (VNC), BPN and Roadrunner (brain), AIP threat neurons, P1, LC/VPN lines, Brake (ascending), TLA (ascending), MooSEZ (SEZ neuron; DN status unverified, so only the MDN experiments in that paper were listed), larval-only studies, and Chai 2024/2025 (silencing only).
- Not followed: Shiu et al. (whole-brain model paper; synonyms Bract, Fudog and Rounddown come from it), to stay clear of model results.
- I used my memory only to choose search terms. Every lead rests on a page or search result I saw in this session; leads marked "check" or "verify" are less certain.
