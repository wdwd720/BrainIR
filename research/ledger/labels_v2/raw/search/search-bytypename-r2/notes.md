# Notes — session `search-bytypename-r2`, pass `search`, kind `by_type_name`

## What was done
I started from the DN type names and literature synonyms in `type_list.csv` / `synonyms.csv` (MDN, DNp09/P9, aDN/aDN1/aDN2,
DNg11, DNg12, DNa01/02/03/11, DNae014, DNb02, DNg13, DNg14, DNp42, Mute, oviDN, BDN1-4, oDN1, cDN1, BB/bluebell, GF/DNp01,
DNp02/04/06/07/10/11, DNp15/17/20/27/29, DNa13, DNb05/06, aSP22, OA-VPM/VUMd octopaminergic DNs, DNb08) and searched
type by type for adult activation experiments (optogenetic or thermogenetic) with leg movement observable. I followed
reference lists and citing papers where search snippets pointed to them. Output: `out/leads.csv` (79 rows covering 30 papers, one per paper × DN
type/line; "check" in the locator marks leads whose experiment or figure I could not confirm from accessible text).
I wrote no records (search pass). `manc_type` is filled from the kit only; ambiguous kit mappings are noted in the locator.

## Databases / tools
- Web search (general engine), many queries per type name (listed below).
- Europe PMC REST API (`/search`, lite and core result types): used for bibliographic verification, DOI resolution and
  abstract screening. Queries included:
  - `moonwalker drosophila` (89 hits, first 50 screened)
  - `"descending neuron" AND drosophila AND (CsChrimson OR Chrimson OR TrpA1 OR ReaChR) AND PUB_YEAR:[2014 TO 2026]` (86 hits, all screened)
  - `"descending neurons" AND drosophila AND (optogenetic OR optogenetically OR thermogenetic) AND (walking OR grooming OR leg OR takeoff OR landing OR locomotion) AND PUB_YEAR:[2010 TO 2026] NOT larva*` (90 hits, all screened)
  - `drosophila AND ("DNa01" OR "DNa02" OR "DNa03" OR "DNb02" OR "DNg11" OR "DNg12" OR "DNp09" OR "DNg13" OR "DNp07" OR "DNp10" OR "DNp11" OR "DNg14" OR "DNp42" OR "DNg97" OR "DNp29" OR "DNb01")` (74 hits, all screened)
  - DOI batches to read abstracts for screening (about 30 candidate papers).
- PMC full text: PMC7710706 (Feng 2020) read successfully for locators; later PMC pages returned a reCAPTCHA page.
- Web search queries (examples): moonwalker MDN activation; Cande 2018 optogenetic DN screen; DNp09 Bidaye 2020; Zacarias
  2018 DNp09 freezing; Liessem 2026 DopaMeander; MooSEZ; Guo 2022 DNg12 grooming; Hampel 2015 aDN; DNg11 leg rubbing;
  "Fine-grained descending control of steering" DNa02; Rayshubskiy DNa02; Braun 2024 headless DN lines; Feng/Dickson
  DNa02 unilateral (steering circuit); Sapkal 2024 BDN2/oDN1/bluebell; GF von Reyn 2014; Ache 2019 DNp07/DNp10; von Reyn
  2017; Sterne 2021 SEZ lines; DNp11/DNp02/DNp04/DNp06 takeoff; updated DN split-GAL4 catalogue; DNp42; DNg14/DNa13/DNb05/
  DNb06; DNp15/27/20/29; FlyMAD MDN; aSP22 McKellar 2019; Simpson-lab posterior grooming; oviDN Wang 2020 / Vijayan 2023;
  Ache-lab landing DNs; halting DNs 2025-26; "A dedicated brain circuit controls forward walking"; AVLP491 aggression;
  courtship pursuit DNs; Ros 2024 DNb01 flight; Babski 2024 OA-DNs; Palacios Castillo 2026 OA/TA toolkit; Bidaye lab 2025;
  Card lab 2025 escape DNs.

## What I could not access (needs a fetch session)
- bioRxiv full text returned HTTP 429 repeatedly: Dahlhoff/Liessem preprint (10.1101/2025.07.22.666129; which other "DNp lines"
  from an earlier screen raised walking speed is still unknown), Parallel neuronal ensembles (10.64898/2025.12.13.693955;
  landing/takeoff DN activation details taken from search snippets only), Cande preprint (10.1101/230128), Yoshikawa 2024
  preprint.
- cell.com (Current Biology / Neuron / Cell) returned 403; nature.com redirected to a login page; PMC (pmc.ncbi.nlm.nih.gov)
  returned a reCAPTCHA page after the first fetch; Europe PMC fullTextXML timed out or returned 500 for PMC6031430 (Cande),
  PMC11179149 (Yoshikawa) and PMC11186778 (Braun). eLife article pages failed to render ("required part of the site failed to load").
- **Cande et al. 2018 (10.7554/eLife.34275):** a systematic screen of about 130 split lines covering 58 DN types (phenotypes for 47).
  I could not open Supplementary file 1 / Dryad (doi:10.5061/dryad.fr89c0c), so leads.csv lists only the types named in the
  snippets I could read (DNp09, DNg07, DNg08, DNg10, DNg12, DNg13, DNp29, DNb01) plus one "every line" row. Under protocol §1, a
  record session must enumerate every tested line.
- **Braun et al. 2024 (10.1038/s41586-024-07523-9):** 12 named lines listed. The Nature text says other DN lines were tested
  headless but analysed only if they had a phenotype; the full list of lines tested headless is in the Extended Data /
  Supplementary Information, which I did not reach.
- **Sapkal et al. 2024 (10.1038/s41586-024-07854-7):** whether cDN1, BDN1, BDN3 and BDN4 were activated is not confirmed (check rows).
- **Bidaye et al. 2020 Neuron:** I could not check which lines in the targeted walking-initiation screen are DNs (check row).

## Uncertain mappings / judgement calls
- P9 / DNp09: the kit lists line P9S2 as AMBIGUOUS DNp09;DNp71. I wrote DNp09 (the paper's name is a MANC type name).
- BB/bluebell: kit ambiguous DNg60 / DNxn073; written DNg60 with a note. FG (Foxglove) is not in the kit and is an SEZ neuron
  with a stochastic descending axon, so `manc_type` is empty.
- aDN (aDN-GAL4 R18C11) is UNMAPPED in the kit; aDN1 -> DNg62, aDN2 -> DNfl023 (literature synonyms).
- DNae014 -> DNa15 via kit driver line `DNae014-splitGal4`; DNae003 -> DNxn123 via flywire synonym.
- Mute -> DNad006 (Sterne 2021 synonym).
- DNp17 in Liessem 2026: line SS02553 also labels DopaMeander. The paper attributes the walking phenotype to DopaMeander,
  so the DNp17 row is kept as a multi-cell-line lead.
- Lima & Miesenböck 2005 used P2X2 + caged-ATP photostimulation. Whether this counts as "optogenetic" under protocol §1 is
  for the record session to decide.
- I left these out because the readout is wings, flight, head or abdomen only, or the activated cells are not DNs: Ros et
  al. 2024 (DNae014/DNb01 flight saccades), Namiki 2022 (flight DNs), Croke 2026 / Buchsbaum 2025 (DNp03 flight), Erickson
  2026 (DNa10 altitude, free-flight descent), song DN papers (pIP10, Shiozaki 2024, Roemschied 2023), Tanaka 2020/2022
  (LC11/LPLC1), Yoshikawa 2024 MGT (kept as a check row because DN status is unclear), Syed 2026 (13A/13B VNC neurons),
  TwoLumps (ascending), Pair1 (Lee 2021), Babski 2024 (recordings only), Zung 2025 DN catalogue and Namiki 2018 (anatomy/
  line resources only, no activation), Sterne 2021 (anatomy resource), Özdil 2026 (grooming; perturbations are
  simulations plus non-DN neurons; not opened).
- Not opened on purpose: Bates 2026 Nature "Distributed control circuits across a brain-and-cord connectome"
  (10.1038/s41586-026-10735-w) and arXiv "How much of fly walking is written in the wiring?" (2609.38665) and
  "Synaptic placement reflects shared input in Drosophila descending neurons" (2610.00690). They may contain model or
  simulation content.

## Score sightings (see out/sightings.csv)
- I did not open the Pugliese 2026 papers or the 2026 Sapkal preprint. However, two web-search result summaries paraphrased
  the Pugliese content:
  1. a query about headless DN activation returned a summary saying the in-silico activation screen ranked **DNg100** as
     the strongest driver of rhythmic leg activity (a rank);
  2. a query "DNb08 descending neuron Drosophila activation" returned a summary saying **DNg100 and DNb08** had among the
     highest rhythmicity scores (rhythm score / driver call).
  Any record later written for DNg100 or DNb08 from this session's knowledge should carry `saw_simulation_score = true`.
  After the second sighting I added nature.com/PMC to blocked domains for the remaining type queries and avoided query
  wording likely to surface that paper. Titles of the forbidden papers (Pugliese Nature; Sapkal 2026 preprint "Central
  versus peripheral neural control of a coordinated walking pattern") also appeared in result lists. Seeing a title is not
  a sighting under §8.
- Because of sighting 2, I deliberately did not add a DNb08 lead taken from the Pugliese paper. That paper is a forbidden
  source for this session. A DNb08 activation experiment (SS70620, headless) is reported there; an authorised session
  should handle it.

## Dispositions
This search session was not assigned any sources (`sources/` does not exist in the room). `out/dispositions.csv` therefore
has only its header.
