# Search notes: session `search-bytypename-r1`, pass `search`, kind `by_type_name`

## Output
- `out/leads.csv`: 100 lead rows from 32 distinct sources (one row per DN type or line tested). No records were written, as instructed.
- `out/sightings.csv`: one accidental score sighting, logged twice (see below).

## How I searched
1. I read PROTOCOL.md, type_list.csv and synonyms.csv. I searched driver_lines.csv (418 KB) with grep for specific line IDs and types (SS01540, SS01587, SS02542, SS02635, SS01602, P9S2, DNg25/DNp26/DNp10/DNg16/DNp42).
2. **PubMed E-utilities** (esearch/esummary/efetch):
   - `"descending neuron*" AND Drosophila AND (CsChrimson OR optogenetic* OR TrpA1 OR thermogenetic*)`: 28 hits.
   - `Drosophila AND ("descending neuron(s)" OR "descending interneuron*") AND (activation OR CsChrimson OR Chrimson OR ReaChR OR TrpA1 OR optogenetic*) AND (walking OR locomotion OR grooming OR leg(s) OR takeoff OR escape OR landing OR turning OR steering)`: 48 hits.
   - A query of type names (DNa01, DNa02, DNa03, DNa04, DNb01, DNb02, DNb05, DNb06, DNg11-17, DNg100, DNp01/02/04/06/07/09/10/11/15/42/50, DNg97, DNg75, DNg62, aDN1, aDN2, BDN2, oDN1, cDN1, moonwalker, giant fiber/fibre): 157 hits. Most were giant-fiber physiology or genetics papers; I screened all titles from 2005 onward.
   - Giant fiber/escape/takeoff/landing AND (CsChrimson, ChR2, TrpA1, P2X2, ReaChR, optogenetic) AND adult: 5 hits.
   - `(DNa11 OR DNa03 OR LAL013)`: 0 hits, because PubMed doesn't index these names.
   - I fetched abstracts with efetch to triage.
3. **PMC full text** via the PMC idconv API plus `efetch db=pmc`. This was the most reliable route to full text and figure legends. Read this way: Cande 2018, Bidaye 2020, Feng 2020, Israel 2022, Ache 2019 (Nat Neurosci), Hampel 2015, Carreira-Rosario 2018, Lee 2021, Rayshubskiy 2025, Yang 2024, Zacarias 2018, Cao 2026, Erickson 2026, Fernandez-Acosta 2025, Chen 2018, Babski 2024, Braun 2024, Sapkal 2024, Yoshikawa 2024, Guo 2026 (iScience), Collie 2025, Chai 2025, Gaitanidis 2025, de Vries 2013, Israel 2025, Ros 2024, Dombrovski 2023.
4. **bioRxiv full text** (often rate-limited with HTTP 429, then succeeded on retry): Feng et al. 2024 (10.1101/2024.06.27.601106 v2), Liessem et al. 2025 (10.64898/2025.12.13.693955), Dallmann et al. 2026 (10.64898/2026.01.04.697356). The eLife XML from the eLife CDN worked for Cande 2018.
5. **Web searches** (type names, lab publication lists, citing papers): Simpson lab publication page; queries on MDN, DNp42/DNb06/DNa03/DNb05/DNp15, DNa11, oviDN, aSP22, FlyMAD, giant fiber, landing and takeoff DNs, SEZ DNs and grooming, headless activation.

## Sources excluded after reading (no qualifying adult DN activation with legs observable)
- Chen et al. 2018 Nat Commun: imaging only. Aymanns 2022 eLife: imaging only. Babski 2024 Heliyon: patch-clamp recording only.
- Erickson 2026 Curr Biol (DNa10, DNa04, DNg02, DNa15 etc.): flight only, front legs removed.
- Ros 2024 Curr Biol (DNae014, DNb01): tethered flight only, legs not assessed.
- Namiki 2022 Curr Biol (DNg02) and Croke 2026 Curr Biol (DNp03): flight per their abstracts.
- Fernandez-Acosta 2025 PNAS (Mip2M): larval. Zhu 2024 eLife and Tastekin 2018: larval.
- Lee 2021 eLife: adult activation targets Pair1, not MDN. I kept a Pair1 lead because Pair1 is described as a descending neuron.
- Yoshikawa 2024 Curr Biol (MGT, UMGT1) and Guo 2026 iScience (LegPN/PL/PC): VNC neurons, not DNs.
- Collie 2025 bioRxiv: activates P1, records DNa02. Israel 2025 Commun Biol: activates MooSEZ, not MDN.
- Chai 2025 Proc B: GF silencing only. de Vries 2013 JoVE: Foma-1 (optic lobe). Sen 2019 Curr Biol: activates ascending TwoLumps neurons.
- Wang K 2021 Nature (vpoDN): no activation with legs. Li 2024 Nat Commun: DN activation drives wing spreading. Schretter 2020: aIPg/pC1d, not DNs.
- Zung et al. 2025 eLife RP 107450 (DN split-GAL4 catalogue): anatomy/resource. The abstract and reviews show no behavioural activation, but I didn't read the full text.
- Lee K 2026 PNAS / bioRxiv (MDN cell-body clustering): abstract describes no activation.

## Couldn't access or couldn't verify
- **Cande 2018 Fig. 6B type list:** it's an image, and the per-line PDF (FigureS5_Cande_et_al.pdf) is over 10 MB, too big to fetch. I listed the 19 types named in the text plus one catch-all screen row. The kit's driver_lines.csv already has OCR'd line IDs from Figure 2-source data 1.
- **Ache 2019 Nat Neurosci 133-line screen:** per-line results aren't in the text I read; kept as a catch-all row.
- **Paywalled or blocked (cell.com 403, not in PMC):** Guo 2022 Curr Biol (exact figure numbers for DNg12/DNg11/aDN), Sen 2017 Curr Biol (MDN asymmetric activation), McKellar 2019 Curr Biol (aSP22), von Reyn 2017 Neuron, Ache 2019 Curr Biol, Liessem 2026 Curr Biol.
- **Fetched but not text-readable** (raw PDF, poppler not installed): von Reyn 2014 Nat Neurosci, McKellar 2019 PDF.
- **Not fetched; leads rest on search snippets or abstracts:** Bidaye 2014 Science, Bath 2014 Nat Methods (FlyMAD), Lima & Miesenböck 2005 Cell, Wang F 2020 Nature (oviDN), Sci Rep 2023 (oviDN), Titlow 2015 (abstract only).
- **Liessem/Dahlhoff 2026:** the bioRxiv full text (10.1101/2025.07.22.666129) kept returning 429. The DNp17/SS02553 lead comes from a search snippet.
- **Ozdil et al. 2026 Nat Commun / bioRxiv 2024.12.17.628844** (antennal grooming): the abstract describes its own simulated activation screen. I couldn't confirm any real-fly DN activation (Nature login redirect), so I wrote no lead. Worth a check.
- **Europe PMC REST** returned 500/503 throughout and wasn't usable. The eLife HTML and figure pages didn't load, and the PMC figure pages showed a captcha.

## Mapping notes
- **P9 = DNp09.** driver_lines.csv lists SS01540 and P9S2 as AMBIGUOUS DNp09;DNp71. I used DNp09, the paper's own name.
- **BB / bluebell:** ambiguous in synonyms.csv (DNg60 or DNxn073). I wrote DNg60 provisionally.
- **No kit mapping found (manc_type left empty):** FG/Foxglove (Sapkal 2024), Pair1 (Lee 2021), DNg25 (Cande 2018; not in type_list), and "aDN" without a subtype (Guo 2022; R18C11 / aDN-LexA in Hampel 2015).
- **DNpe050 → DNxn183** and **DNae003 → DNxn123** via the flywire names in type_list. **DNae014 → DNa15** via driver_lines.csv.
- **Mute → DNad006**, **oDN1 → DNg97**, **BDN2 → DNg100**, **aDN1 → DNg62**, **aDN2 → DNfl023**, all from synonyms.csv.
- BPN (Bidaye 2020; Sapkal 2024), BRK (ascending), MAN (ascending), MooSEZ and Roadrunner are described as non-DNs, so they aren't leads. The exception is the SS01587 row: the line maps to DNp29 in driver_lines.csv, although the paper attributes the phenotype to BPN.

## Score sightings (section 8)
- I never opened the Pugliese 2026 papers or the Sapkal 2026 preprint.
- However, two WebSearch result summaries paraphrased the Pugliese 2026 Nature simulated activation screen as ranking **DNg100** the strongest driver of rhythmic leg activity. This was a search about the Dallmann 2026 preprint, then a search about headless activation.
- I stopped reading those summaries and logged the sighting in `out/sightings.csv` (what_was_seen = `rank`, type DNg100). Any record for DNg100 / BDN2 (e.g. from Sapkal 2024, lead row "BDN2") must have `saw_simulation_score = true`.
- The same summary also mentioned DNb08 headless experiments described in the Pugliese paper, and the 2026 Sapkal preprint's headless experiments. I didn't follow up on either or add them as leads.
- Sapkal 2024 Nature and Ozdil 2024/2026 contain the papers' own connectome models. Under section 8 these don't count as sightings, and I didn't look at those model results.
- The arXiv paper "Synaptic placement reflects shared input in Drosophila descending neurons" (2610.00690) appeared in search results; I didn't open it.

## Families covered (family_hint)
- **walking_stopping:** MDN, DNp09/P9, BDN2, FG, BB, Pair1, DNp17, DNg25, DNb01.
- **steering:** DNa01, DNa02, DNa03, DNa06, DNa11, DNae003, DNg13, DNa05, DNa07.
- **grooming:** aDN1, aDN2, DNg11, DNg12, DNg07/08, DNg10, oDN1.
- **escape_landing:** GF, DNp02, DNp04, DNp06, DNp11, DNp07, DNp10, DNp47, DNg79, DNb05.
- **recent_broad:** DNb02, DNg14, DNp42, oviDN, Mute, DNpe050, DNp60, aSP22.
- **driver_line_resources:** the Cande, Ache and Bidaye screens.
