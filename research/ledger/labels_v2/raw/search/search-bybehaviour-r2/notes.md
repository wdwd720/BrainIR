# notes: search-bybehaviour-r2 (pass: search; kind: by_behaviour)

Output: `out/leads.csv` (one row per DN type or line per paper; header as specified). No records were written; this is a
search session. Also `out/sightings.csv` (see the "Score sighting" section). No sources were assigned locally (there is
no `sources/` directory in this room), so `dispositions.csv` does not apply. Every lead is a pointer for later labelling.
I did not record any outcome as evidence.

## Databases and tools
- Web search (general engine), with queries built from behaviours and methods.
- Europe PMC REST API (`/search` with lite/core results, and `/PMCxxxx/fullTextXML` for full text). This was the main
  route to full text. It often returned HTTP 500/503 or timed out.
- PMC HTML (pmc.ncbi.nlm.nih.gov). It worked a few times, then returned reCAPTCHA pages.
- bioRxiv HTML full text and api.biorxiv.org (for metadata). The HTML often returned HTTP 429.
- Semantic Scholar API (abstract/OA check only).
- These sites blocked access (403 or error page): cell.com, sciencedirect, nature.com (login redirect),
  elifesciences.org HTML, royalsocietypublishing.org and researchgate. The eLife CDN PDFs were too large or
  binary-unreadable (no pdftoppm in this environment), and so were the McKellar 2019 PDF and the Caltech thesis PDF.
- I did not visit GitHub or Zenodo. I did not open the Pugliese 2026 (Nature / bioRxiv 2025.09.12.675944) or Sapkal
  2026 (10.64898/2026.04.29.721658) papers.

## Queries (by behaviour / method)
- "Drosophila descending neurons optogenetic activation screen walking grooming CsChrimson split-GAL4"
- "moonwalker descending neurons backward walking activation Drosophila MDN CsChrimson"; Europe PMC: (moonwalker OR MDN)
  AND Drosophila AND (CsChrimson OR TrpA1) AND backward
- Europe PMC: Drosophila AND grooming AND "descending neuron*" AND (CsChrimson OR TrpA1 OR activation)
- "descending neurons anterior grooming activation Guo Simpson DNg12"; Hampel/Seeds aDN; "hindleg/posterior/abdominal
  grooming descending neuron activation"; "grooming descending neuron activation screen split-GAL4 2023-2025"
- Europe PMC: Drosophila AND (takeoff OR escape OR jump) AND "descending neuron*" AND (CsChrimson OR Chrimson OR TrpA1 OR
  optogenetic*); Europe PMC: ("giant fiber" OR "giant fibre") AND (CsChrimson OR Chrimson OR TrpA1 OR P2X2 OR ReaChR OR
  photostimulation)
- "giant fiber optogenetic activation takeoff"; "von Reyn 2014 / 2017"; "Lima Miesenbock 2005"; "Card lab DN activation
  takeoff landing"; "DN activation jump takeoff 2024 2025 bioRxiv DNp04 DNp06 DNp11"
- Europe PMC: Drosophila AND ("descending neuron" OR "descending neurons") AND (CsChrimson OR Chrimson OR ReaChR OR TrpA1
  OR dTrpA1) AND (walking OR locomotion OR leg OR legs). That gave 177 hits; I triaged all titles, sorting both newest
  and oldest first.
- Europe PMC: named-DN query (aSP22, DNa12, pIP10, oviDN, DNp13, pMN1, DNp10, DNa01, DNa02, DNg11, DNg12, DNp09, DNp42,
  DNb02, DNg14, DNp07, DNp17, BDN2, aDN1, aDN2, DNg13, DNa03, DNb05, DNb06) AND (CsChrimson OR Chrimson OR ReaChR OR
  TrpA1 OR activation). I triaged the first 100 of 176 hits.
- Europe PMC: Drosophila AND (TrpA1 OR dTrpA1) AND ("descending neuron(s)" OR "command neuron") AND (walking OR grooming
  OR jump OR takeoff OR leg)
- "steering turning walking DNa01 DNb02 optogenetic"; "Hierarchical Transformation of Navigational Variables"
- "DN halting stopping walking speed optogenetic 2025 2026"; "oviDN activation halting"; "BDN2 DNg100 optogenetic
  walking headless"
- "DN headless/decapitated leg movements 2025"; "reaching / leg extension / posture DN activation tethered"
- "aSP22 McKellar"; "dTrpA1 descending female receptivity"; "aggression/courtship DN leg"

## Lead families covered
- walking_stopping: MDN (many papers), DNp09/P9, BDN2/oDN1, FG/BB, DNp17, Pair1, oviDN, DA-DNs, freezing, and the
  Dallmann 2026 preprint.
- grooming: aDN1/aDN2 (Hampel 2015, Braun 2024), DNg11/DNg12 (Guo 2022), Cande named grooming lines, and the MGT screen.
- steering: DNa02 (Yang 2024, Rayshubskiy 2025, Braun 2024), DNa01, DNb02, DNb01, and the Feng 2024 preprint (DNa11,
  DNa03, DNa02, DNae014, DNb01, DNg13).
- escape_landing: GF (several papers), DNp02/04/06/11 (Dombrovski 2023, Peek thesis), DNp07/DNp10 (Ache 2019, Liessem
  2025), DNp47, DNg79, DNb05.
- recent_broad: Cande 2018 (systematic screen), Braun 2024 (12 DN types), aSP22.
- driver_line_resources: none qualify. Zung et al. 2025 (eLife RP 107450, DN split catalogue) and Namiki 2018
  (anatomy) report no activation experiments. Zung Suppl. Table 5 is useful for finding further published DN lines.

## Not accessed, or only partly read (locators to verify)
- Cande 2018 Figure 2-source data 1 (zip): this lists all 130 screened lines and is needed for one record per line. I
  could not read it. I gave leads for the named lines plus one screen-wide row.
- Bidaye 2020: I could not confirm that Fig. S1 lists every one of the ~156 screened lines.
- Sapkal 2024: Suppl. Tables 1-2 (genotypes), and whether other DNs are shown in Fig. 3j.
- I could not open these at all; their locators come from search snippets or summaries and are marked "not verified" in
  leads.csv:
  - Guo 2022 (Curr Biol; no PMC; NSF PAR copy timed out)
  - McKellar 2019, Bidaye 2014, FlyMAD 2014, Sen 2017, Sen 2019, Lima & Miesenbock 2005, von Reyn 2014 (Janelia PDF
    not opened)
  - Proc R Soc B 2025 (GF): whether it includes any activation is unverified
  - Feng 2024 preprint and Dallmann 2026 preprint (bioRxiv 429)
  - Peek 2018 thesis (record page only)
  - JUNE 2015 lab module
- Wang 2020 (oviDN, Nature, PMC7687045): Europe PMC 500. Whether legs were observable is unverified.
- Vijayan 2023 (oviDN): legs were not reported in the first 100k characters, so this lead is borderline.
- Selective presynaptic inhibition 2025 (DNg100 activation during imaging): I could not check whether legs were
  observable.
- Dahlhoff 2025: the "DNp lines" that increased walking speed are not named in the text; check Table S1.
- Tschida & Bhandawat 2015: activation was P2X2 + ATP (chemogenetic), which is probably not eligible. The DOI is from
  memory and needs checking.
- Lima & Miesenbock 2005: P2X2 + caged-ATP photostimulation. Its eligibility as "optogenetic" needs a decision.

## Checked, no qualifying DN activation (not in leads.csv)
- 10.1016/j.heliyon.2024.e29952 (OA DNs): in vivo recordings only, no activation.
- 10.1038/s41467-026-72152-x (antennal grooming coordination 2026): activates JO-F and c23 interneurons; aDNs are only
  cited.
- 10.1016/j.isci.2026.114902 (leg rubbing VNC circuits): LegPN/LegPL/LegPC only.
- 10.7554/elife.106446 (inhibitory circuits in grooming): 13A/13B VNC interneurons only.
- 10.1242/jeb.250826 (grooming/feeding/courting choices): leucokinin and aminergic lines only.
- 10.1016/j.isci.2022.103792 (wing grooming command neurons wPN1): VNC interneurons, not DNs.
- 10.7554/elife.71679 (Sterne 2021): DN lines are described anatomically only (in the part read).
- 10.1016/j.isci.2026.115624 (axo-axonic synapses on DNs): GF CsChrimson only in a decapitated prep with TTM/DLM muscle
  recordings, no leg observation.
- 10.1038/s41586-024-07039-2 (head direction to steering): PFL2 P2X2 activation only (first 100k characters).
- 10.1016/j.cub.2024.04.003 (MGT): MGT/UMGT1 are not DNs. The ~100-line screen in Table S1 was not read, so I kept one
  lead for it.
- 10.7554/elife.57685 (spatial readout of looming): no DN activation in the first 100k characters.
- 10.7554/elife.96084 (Cheong, MANC): CsChrimson lines used only for FISH/immunostaining (first 100k characters).
- 10.1038/s41593-023-01332-5 (egg-laying transitions): no DN activation in the part read (PU, CMU only). I removed this
  lead.
- 10.1038/s41467-025-56185-2 / 10.1101/2025.09.30.679458 / 10.64898/2026.08.04.742787 / 10.1038/s41467-023-42202-9:
  larval work only.
- 10.1101/2025.10.28.684868 (PMC12636578, ascending nociceptive pathways): only sensory and ascending lines activated.
- 10.1038/s41467-020-17771-8 (mating states and defensive kicking): no DN activation; decapitated kicking from VNC/sensory
  neurons.
- 10.3389/fnbeh.2015.00096: P2X2 + ATP only (kept as a flagged lead, see above).
- Not opened because they are flight or wing only, with legs not assessed: DNg02 flight (10.1016/j.cub.2022.01.008), DNa15/DNae014 flight turns
  (10.1016/j.cub.2023.12.047), DNp03 saccades (10.1016/j.cub.2025.11.035 and bioRxiv 2024.08.22.608914), and altitude
  control 2026 (10.1016/j.cub.2026.10.049; Europe PMC 500, not checked). vpoDN/DNp13 papers (female receptivity,
  genitalia) were not checked for leg observation. The threat-display paper (10.1016/j.cub.2026.09.056, PMC13773492)
  returned 500 three times and is unchecked. It is a candidate for wing+leg DN activation, so a later session should
  retry it.
- Not opened because they are simulation or model papers: 10.1101/2025.12.14.694122 (whole-brain escape simulation) and
  10.1038/s41586-026-10735-w (connectome paper).

## Score sighting (protocol section 8)
- One WebSearch result summary (query "Drosophila descending neurons optogenetic activation headless OR decapitated flies
  leg movements 2025") described the Pugliese 2026 simulation screen. It said DNg100 was the strongest simulated driver
  of rhythmic leg activity (a rank) and that DNb08 was predicted to drive rhythmic leg movements (a driver call). I did
  not open the page. Both are logged in `out/sightings.csv`. Any later records of DNg100 (BDN2) or DNb08 written from
  my leads should have `saw_simulation_score` = `true`. My leads include DNg100: Sapkal 2024 BDN2 and Selective
  presynaptic inhibition 2025. I added no DNb08 leads.
- A second search summary showed experimental (non-simulation) content from the forbidden Sapkal 2026 preprint
  (DNg100 combined with DNg16/DNg55/DNg75/DNg97 in decapitated flies). This is not a score, but I did not use it and
  wrote no leads from it.

## Uncertain mappings
- aDN in Guo 2022 and the multi-aDN lines in Hampel 2015 are mapped to DNg62 (aDN1) provisionally. The R18C11 and LexA
  lines label three aDNs, so they are multi_dn.
- BB (Bluebell) maps ambiguously to DNg60 or DNxn073 (synonyms.csv). FG (Foxglove), DNg25 and Pair1 have no mapping in
  the kit.
- The P9S2 line is AMBIGUOUS (DNp09;DNp71) in driver_lines.csv.
- DNae014 maps to DNa15 via driver_lines.csv.
