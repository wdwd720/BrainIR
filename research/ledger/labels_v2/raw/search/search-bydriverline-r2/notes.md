# Notes: session search-bydriverline-r2 (pass: search, kind: by_driver_line)

The output is `out/leads.csv`: 185 lead rows from 28 sources (distinct DOIs). No records were written, as instructed.
- 122 rows come from Cande et al. 2018 (eLife 34275):
  - 5 lines named in figures, plus 1 summary row for the screen.
  - 116 per-line rows. These line IDs come from the kit's `driver_lines.csv`, which lists IDs OCR'd from Cande's Figure 2-source data 1. I confirmed in the paper text that the source data is a line-by-line analysis of all DN split-GAL4 lines. I did not open the PDF myself, so the per-line page numbers are the kit's.
  - `manc_type` is left empty for all per-line rows, to be filled in by joining on line ID.
- `manc_type` is filled only where the paper's name maps through `type_list.csv` / `synonyms.csv`. Where the kit says a name or line is ambiguous, this is noted in `locator`.

## Method / databases
- I started from `driver_lines.csv`. Its `source_doi` / `table_source` fields point to Namiki 2018, Zung/Namiki 2025, Cande 2018, Sterne 2021, Meissner 2024/2025, Cheong 2024, Hampel 2015, Sapkal 2024, Braun 2024, Bidaye 2014/2020, Yang 2024, Rayshubskiy 2025, Shuai 2025, Wolff 2025, Wang 2020 and Lillvis 2024. I treated these as the seed set and then searched outward.
- PubMed Central was searched through NCBI E-utilities (esearch + esummary):
  1. `"descending neurons" AND Drosophila AND (CsChrimson OR TrpA1) AND "split-GAL4"` (137 hits)
  2. `"descending neuron" AND Drosophila AND (CsChrimson OR ReaChR OR TrpA1 OR Chrimson) AND (takeoff OR grooming OR landing OR backward OR "walking speed" OR stopping OR halting) NOT larva[ti]` (88 hits)
  3. `("giant fiber" OR "giant fibre") AND Drosophila AND (CsChrimson OR Chrimson OR ReaChR OR TrpA1 OR P2X2) AND (takeoff OR jump OR escape)` (73 hits)
  4. Title searches for specific preprints (Roadrunner, Parallel neuronal ensembles, DN catalogue, Özdil grooming, central steering circuit).
- Full text was read mainly through the NCBI BioC PMC-OA API (`pmcoa.cgi/BioC_json/PMCxxxx`), because pmc.ncbi.nlm.nih.gov returned a reCAPTCHA page. I also used Europe PMC fullTextXML (worked once, for Cande 2018; otherwise HTTP 500/503), bioRxiv full text (one success for Feng et al. v2 and one for the DNp17 preprint; otherwise HTTP 429), the bioRxiv API (abstracts) and web search.
- Web searches covered: DN split-GAL4 activation and walking (2024–2026); Sen 2017 moonwalker; Bidaye 2014; von Reyn 2014/2017; Lima & Miesenböck 2005; Guo 2022 anterior grooming; takeoff DNs (Card lab); headless-fly DN activation; posterior/wing grooming DNs; steering DNs (DNa03/DNa11/DNb05/DNg13); Özdil grooming.

## Could not access / partly accessed (follow-up needed)
- **Guo, Zhang & Simpson 2022, Curr Biol (10.1016/j.cub.2021.12.055):** cell.com returned 403 and there is no PMC copy. The figure locators come from search-result snippets; the DNg11 and aDN panels are not confirmed. ScienceDirect reportedly links an open manuscript.
- **Bidaye et al. 2014, Science (10.1126/science.1249964):** paywalled, no PMC copy. Figure panels not confirmed.
- **Sen et al. 2017, Curr Biol (10.1016/j.cub.2017.02.008):** cell.com returned 403. Panels not confirmed.
- **von Reyn et al. 2014, Nat Neurosci (10.1038/nn.3741):** the Janelia PDF downloaded but could not be rendered (no pdftoppm). Panels not confirmed.
- **Lima & Miesenböck 2005, Cell:** abstract and search snippets only. Note that P2X2 + caged ATP is light-triggered but is not an opsin; the curator should decide whether it counts as optogenetic.
- **Liessem et al. 2025 bioRxiv (10.64898/2025.12.13.693955, landing/takeoff DN ensembles):** abstract only (bioRxiv 429, Europe PMC 500). Likely contains landing-DN activation.
- **Dallmann et al. 2026 bioRxiv (10.64898/2026.01.04.697356, Roadrunner forward-walking circuit):** abstract only. The abstract describes activating central brain neurons (RRN, not DNs) and a recruited DN population. Whether any DN was activated directly is unknown, so no lead was added.
- **Lee et al. 2026 PNAS (10.1073/pnas.2618114123, MDN cell body position):** BioC returned no result. Added as an unconfirmed lead.
- **Cao et al. 2026 Curr Biol (published version of the threat-display preprint):** not in BioC. The leads are from the bioRxiv/PMC preprint version, and the full ~70-line screen list (Fig. S1C / Table S1) was not visible.
- **Cande 2018:** I could not see Figure 6's per-type list or the source-data PDF. The per-line rows rely on the kit's OCR of that PDF.
- **Bidaye 2020:** the 156-line activation screen does not list its line IDs ("available on request").
- **Braun 2024:** the split-GAL4 IDs for most DNs are in Supplementary Table 2 / Suppl. Information p.9, which I did not open directly. The kit already lists the aDN1 and DNp09 lines from it.
- Wu et al. 2014 PNAS (multi-fly optogenetics), Titlow 2015 (GF lab module), Croke 2026 (DNp03, flight), Kuo 2026 (landing), Elabbady 2026, Palacios Castillo 2026 and Currier 2026 were not in the BioC open-access set. These were not checked beyond titles/abstracts.

## Read and judged not to contain a DN-activation experiment with legs observable (no lead)
- Yoshikawa et al. 2023/2024 (MGT and UMGT1 activated; VNC neurons, not DNs)
- Syed et al. 2025/2026 (13A/13B VNC interneurons)
- Guo et al. 2026 iScience (LegPNs ascending, LegPLs, LegPCs)
- Collie 2025 (DNa02 recorded only; P1 activated)
- Crown 2026 (PFN neurons)
- Jones 2025 (sensory/ascending only)
- Tanaka & Clark 2022 and 2020 (DNs silenced only; LPLC1/PLP219/LC11 activated)
- Gattuso 2025 (LAL/SMP neurons)
- Özdil 2026 Nat Commun (JO neurons and SS35281 activated; aDNs not activated)
- Calle-Schuler 2026 (aBN2 and GAL4 lines R40F04/R26B12; the text does not call them DNs)
- Sterne 2021 (anatomy only in the visible text)
- Aymanns 2022 (imaging)
- Cheong 2026 eLife (CsChrimson lines used only for FISH/neurotransmitter work)
- Tao 2024 (L320, not DN-specific)
- Chiu 2021 (no DNs)
- Cury 2023 (no DN activation with legs)
- Wang 2020 oviDN (activated, but only abdomen/ovipositor actions scored, so legs not assessed)
- Fernandez-Acosta 2025 (Mip2M DNs, larval only)
- Zacarias 2018 DN screen (Kir2.1 silencing; only the DNp09 activation is a lead)
- Namiki 2022 flight DNs (DNg02, DNg07, DNg29 lines; tethered flight, wing only, legs not observable). Possible borderline case for the curator.
- Steinfath 2025: pIP10 and pMP2 (song/vibration only, no lead). The DNp28 activation with locomotion is a lead.
- Zung/Namiki 2025 DN split-GAL4 catalogue (eLife 107450 / bioRxiv 639679): the abstract describes anatomy and line generation only. Full text was not reachable (eLife page did not load; bioRxiv 429).

## Uncertain mappings flagged in `locator`
- DNp09 (kit: ambiguous with DNp71).
- SS02542 DNb01 (kit: DNb01/DNb09).
- BB/Bluebell (kit: DNg60/DNxn073).
- DNg12 (the name maps to several MANC types).
- SS02553 (DNp17/DNut046).
- SS02635 (DNg07/DNg08, both ambiguous).
- SS33004 (DNp60 plus DNp67).
- FG/Foxglove, Pair1, MooSEZ and aDN (R18C11) have no kit mapping.
- MooSEZ may not be a DN.
- DNpe050 maps to DNxn183 and DNae003 to DNxn123 via kit synonyms.

## Blinding / rule compliance
- I did not open any Pugliese 2026 paper or the 2026 Sapkal preprint. The Pugliese bioRxiv record (PMC13142387) appeared in an esummary title list and was not opened.
- One web search ("…DNg97 OR DNa01…") returned the 2026 Sapkal preprint (10.64898/2026.04.29.721658) as its top result. The search tool's summary paraphrased its experimental content (DNg97/DNg100 co-activation in decapitated flies). I did not open the page and used nothing from it; no lead was added from it. It showed no rhythm score, rank or driver call, so I am not logging it as a sighting.
- Some search-engine and WebFetch summaries volunteered behavioural outcomes (e.g. for Guo 2022, Dombrovski 2023, SS02553). None of these outcomes is recorded in `leads.csv`.
- No model or simulation output was used. Sapkal 2024, Gattuso 2025 and Shiu 2024 contain their own models; I ignored those parts. No GitHub or Zenodo pages were visited; the Özdil GitHub repo appeared only as a search-result link and was not opened.
- No sightings occurred, so `sightings.csv` was not created.
