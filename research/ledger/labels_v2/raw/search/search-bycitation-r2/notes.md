# Notes — session `search-bycitation-r2`, pass `search`, kind `by_citation`

Output: `out/leads.csv` (57 lead rows from 22 papers), `out/sightings.csv` (3 rows, see "Score sightings" below).
I did not write any records. The leads give only the experiments and where they are in each paper, with no outcomes.

## Method

1. **Citation lists.** The Europe PMC REST search returned HTTP 500/503 for most of the session, and PubMed/PMC web pages showed a
   browser-check wall. I took the citing-paper lists from OpenAlex instead:
   - Cande et al. 2018 (10.7554/eLife.34275, OpenAlex W2783823892): 159 citing works listed (`filter=cites:`).
   - Namiki et al. 2018 (10.7554/eLife.34272, W2780788446): 347 citing works (2 pages, 200 + 147).
   - 2025 DN split-GAL4 catalogue (bioRxiv 10.1101/2025.02.22.639679 = W4407896025; eLife 10.7554/eLife.107450 = W4414342573): 5 citing works.
2. **Triage.** I removed citing works that are clearly out of scope: reviews, pose-estimation and other methods papers, vertebrate,
   larval or other-insect studies, anatomy/connectome-only papers and flight-only papers. I then opened the candidates.
3. **Full-text access** (in order of what worked): Europe PMC `fullTextXML` (when it was up); the PMC OAI API
   (`pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?verb=GetRecord...`), which worked reliably late in the session; nature.com through the
   `?error=cookies_not_supported` redirect; bioRxiv `.full` pages (often blocked by HTTP 429 rate limits); WebSearch snippets.
4. **Web searches used** (beyond the citation lists): the titles of individual candidates; "Drosophila descending neuron
   CsChrimson activation walking split-GAL4 Namiki 2018 Cande 2018 new descending neuron 2025"; "Drosophila descending neuron
   optogenetic activation backward walking OR turning OR grooming DNg ..."; "Drosophila "descending neuron" CsChrimson front
   leg/hind leg/leg extension ..."; "Bidaye lab 2025 ...", "Feng Bidaye 2024 ...", "Feng Dickson central steering circuit DNa03 DNa11
   LAL013 ..."; "decapitated OR headless Drosophila optogenetic activation descending neuron leg movements 2025 2026" (this query
   caused a sighting, see below); "Drosophila descending neurons optogenetic activation takeoff/landing/escape DNp ...".

## Papers with leads (how they were read)
- Zacarias 2018 Nat Commun: Europe PMC full text.
- Braun 2024 Nature: nature.com full text. The Methods say Web, DNp24, DNg30, DNb01 and DNg16 were "tested but not analysed". I listed them as leads to check, but they may have no reported data.
- Sapkal 2024 Nature (halting): nature.com full text. The paper's *own* in-silico predictions of halt neurons are mentioned. I did not read them, and they are not a Pugliese-type score.
- Feng 2020 Nat Commun: nature.com full text.
- Bidaye 2020 Neuron: cell.com and Europe PMC unavailable; read through bioRxiv 10.1101/798439v1. The 156-line activation screen (Fig. 1A-B) does not name the lines in the text I could read. The per-line list may be in Table S1 or the Key Resources table, which I did not see.
- Guo, Zhang & Simpson 2022 Curr Biol: cell.com returned 403 and there is no PMC copy. I worked from the abstract (OpenAlex) and search snippets only (DNg11 lines ss02391, ss01579, ss01550, ss02617). **Figure locators still need checking.**
- Yang et al. 2024 Cell: Europe PMC full text. Only DNa02 was activated optogenetically; DNg13 was manipulated by current injection, which is not a record.
- Rayshubskiy et al. 2025 eLife: Europe PMC full text (DNa02 ReaChR, Fig. 8).
- Liessem/Dahlhoff et al. 2026 Curr Biol (walking direction): the Curr Biol version returned 403; read through bioRxiv 10.1101/2025.07.22.666129 v1. SS02553 labels about 8 types, including DNp17 and the dopaminergic "DopaMeander". The paper did not activate MDN itself.
- Israel et al. 2022 Curr Biol (MDN, SEZ): Europe PMC full text.
- Ache et al. 2019 Nat Neurosci (DNp07, DNp10): nature.com showed only the abstract and supplementary legends, so main-figure panels and Methods were not visible.
- Nat Commun 2025, multimodal signaling (SS01587, named "DNp28" in the paper): Europe PMC full text. **Mapping conflict:** the kit maps SS01587 to DNp29, but this paper and the Bidaye preprint call it DNp28.
- Cao & Anderson 2026 Curr Biol (threat display; DNpe050, DNp60): PMC OAI full text.
- Feng et al. 2024 bioRxiv "A central steering circuit" / v2 "Hierarchical Transformation...": **the bioRxiv full text could not be opened (HTTP 429 every time).** These leads come from search snippets of the PDF and need checking (DNa03 SS84990/SS96514, DNa11, DNa02, DNae003, DNae014).
- Jiang et al. 2025 Curr Biol (DNp27): abstract and highlights only (paywalled).
- Dallmann et al. 2026 bioRxiv (Roadrunner): bioRxiv full text, first 100k characters. MDN was activated in a gap-crossing assay. I could not confirm whether the initial sparse-line screen included DN lines.
- Palacios Castillo et al. 2026 Curr Biol (OA/TA): PMC OAI. VL1/VL2 are described as descending; VL-labelling lines were activated in aggression assays (Fig. 6B). I could not see which lines these were or whether legs were observed.
- Song/abdomen papers (Shiozaki 2024 Nat Neurosci for pIP10 and pMP2; Nat Commun 2024 for vpoDN and DNp13; Wang 2020 and Mezzera 2020 for DNp13): the DN activations are in freely moving or decapitated flies, but legs are not described. I listed them as leads so the coders can decide; they are low priority.
- Cande 2018 atlas: one summary row only (this is the seed screen; its lines are not listed one by one here).

## Checked and excluded (no DN activation with legs observable)
- Chen et al. 2018 Nat Commun (VNC imaging): imaging only.
- Lau et al. 2025 Curr Biol "Supraspinal commands...": zebrafish.
- Segmentally repeated VNC circuits drive different leg rubbing behaviors (iScience 2026, 10.1016/j.isci.2026.114902): only non-DN lines (LegPN, LegPL, LegPC).
- Heliyon 2024 octopaminergic DNs: patch-clamp only.
- Sex-specific behavioral feedback, Nat Commun 2026: only central brain lines.
- Nat Commun 2019 "GABAergic and peptidergic sleep neuron": C. elegans.
- Wang et al. 2023 Nat Neurosci egg-laying: no DN activation (PU sensory and CMU motor lines only).
- Namiki et al. 2022 Curr Biol, DNg02 flight screen (50 lines): tethered flight, wingbeat only, no legs. **This is a DN activation screen, but legs were not observable**, so I made no leads.
- Flight-only DN activations (DNp03 2024/2025; Ros et al. 2024 DNae014 flight saccades; altitude control 2026): free or tethered flight, legs not observed. Excluded, not opened in full.
- Descending neurons integrate learnt information... bioRxiv 2025: larval.
- Mechanosensory and command contributions to grooming (Yoshikawa 2024): MGT is a VNC neuron (search snippet).
- Inhibitory circuits... grooming (Syed et al.): 13A/13B VNC neurons.
- Busch et al. 2018 (HS cells), Collie et al. 2026 Neuron (pursuit), Rubin et al. 2026 (sexually dimorphic central neurons): no DN activation found in the snippets.
- Hoverfly optic-flow eLife 2026: different species.
- Cheong et al. MANC (eLife 96084): connectome only (from search snippets).
- Ache et al. 2019 Curr Biol (GF looming): no DN activation found in the snippets.
- 2025 DN driver-line catalogue (bioRxiv 639679 / eLife 107450): the abstract describes an anatomy and driver-line resource. I found no activation experiments (abstract only; the eLife page failed to load).
- Hampel et al. 2024 eLife 87602 (somatotopic grooming): no DN activation in the first 100k characters.

## Not accessed or not verified
- The Guo 2022 Curr Biol full text (403), the Feng 2024 bioRxiv full text (429), the Liessem 2026 Curr Biol full text (403; preprint used instead), Wang 2020 and Mezzera 2020 (cell.com 403; the Mezzera PDF on ORA was not opened), the Jiang 2025 full text (paywall), the Bidaye 2020 supplementary table of screened lines, and Braun 2024 Supplementary Table 2 (line IDs).
- Not opened on purpose: "Distributed control circuits across a brain-and-cord connectome" (Nature 2026, 10.1038/s41586-026-10735-w); "Sensorimotor behaviour from an untrained brain-and-nerve-cord connectome" (arXiv 2026); "Connectomes as Structural Priors..." (2026); "Focal neuronal loss ... connectome model of fly steering" (2026). All look like model or simulation papers. The first might contain experiments, so a later session could check it carefully.
- I did not open the Pugliese 2026 papers or the Sapkal 2026 preprint. Web sources used: OpenAlex, nature.com, Europe PMC, PMC OAI, bioRxiv, WebSearch. I did not visit GitHub or Zenodo.

## Score sightings (see `out/sightings.csv`)
- Two web-search result summaries (not the papers themselves) paraphrased the Pugliese 2026 Nature abstract and Fig. 5: a computational DN activation screen named **DNg100** as the strongest driver and **DNb08** as driving leg rhythm in simulation. As soon as I recognised this, I stopped reading that material and opened neither paper.
- One search summary quoted the 2026 Sapkal preprint (10.64898/2026.04.29.721658) saying that **DNg100 (BDN2) and DNg97 (oDN1)** drive forward walking. It was unclear whether this came from the simulation part, so I logged it conservatively.
- **Any records later written from these leads for DNg100, DNb08 or DNg97 by this session's material should carry `saw_simulation_score = true`.** This affects the Sapkal 2024 leads for oDN1 (DNg97) and BDN2 (DNg100).
- Search summaries also said, without my asking, that Pugliese et al. ran headless DNg100/DNb08 optogenetic experiments. I did not add leads from that paper, because opening it is forbidden.

## Uncertainties
- The DNp09 name and the SS01540 line are listed in the kit as AMBIGUOUS (DNp09;DNp71). I entered DNp09.
- BB (Bluebell) is ambiguous between DNg60 and DNxn073; I entered DNg60. FG (Foxglove) and vpoDN are not in the kit, so `manc_type` is left empty.
- I mapped DNae014 to DNa15 using the kit's driver_lines entry `DNae014-splitGal4`, and DNae003 to DNxn123 using synonyms.
