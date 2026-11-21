# Notes: session `search-bydriverline-r1` (pass `search`, kind `by_driver_line`)

The output is `out/leads.csv`: one row per paper × DN type or line. As instructed, no records were written, so there is no
records.jsonl and no sources.csv. No sources were assigned (the room has no `sources/` directory), so `dispositions.csv`
has only its header.

## Approach
1. I started from `driver_lines.csv`. I took the distinct `source_doi` values and the `table_source=` provenance
   tags. The provenance tags are the Zung et al. 2025 catalogue's own list of papers that published DN lines: Namiki 2018,
   Cande 2018, Bidaye 2014/2020, Sapkal 2024, Braun 2024, Yang 2024, Hampel 2015, Ros 2024, Sterne 2021, Shuai 2025,
   Aso 2014, Meissner 2024, Wang 2020 ×3, Lillvis 2024, Cheong 2024, Wolff 2025. I then checked each candidate paper
   for adult activation (opto/thermo) with legs observable.
2. I searched by line ID (e.g. "SS01540" OR "SS02608" OR "SS01550" OR "SS02378" CsChrimson). I also ran topic searches by
   family: MDN/backward walking, grooming DNs, landing/takeoff/escape, steering, halting, and recent 2025–2026 DN activation
   preprints. I followed citing papers (e.g. Zacarias 2018, Lee & Doe 2021, Carreira-Rosario 2018, Israel 2022, Feng 2020).
3. Mapping: I used `type_list.csv`, `synonyms.csv` and `driver_lines.csv`.
   - For the lines in the Cande 2018 Figure 2-source data 1 list, I took the line IDs from the kit's own rows for
     DOI 10.7554/eLife.34275, which come from an OCR of Supplementary_File_1.pdf. I did **not** open the 43.8 MB zip
     myself. Types for those lines come from the kit's Namiki 2018 Supplementary file 3 rows; SS05098 and SS05108 come
     from Zung 2025 Supp Table 5.
   - Where the kit marks a name AMBIGUOUS, I wrote the Namiki/paper name in `manc_type` and listed the alternatives in
     `locator`.
   - Names with no MANC type in the kit got an empty `manc_type`: DNg25, DNg28, FG/Foxglove, BPN, Pair1, and aDN
     (R18C11-GAL4).

## Databases / tools
Web search, Europe PMC REST (search + fullTextXML), PMC HTML, bioRxiv full-text HTML, eLife and Nature article pages.
PMC HTML often returned a reCAPTCHA page; I used the Europe PMC fullTextXML instead. bioRxiv returned HTTP 429
intermittently. Retries succeeded for 2025.12.13.693955, 2025.07.22.666129 and 2024.06.27.601106 v1.

## Could not access / incomplete
- **Cande 2018:** Figure 2-source data 1 (the zip) was not opened, so the line list relies on the kit's OCR rows. eLife HTML
  failed to load. I could not read the type names in the Fig. 6 image. The rows give the types named in the text, plus the
  lines from the kit list (about 115).
- **Bidaye 2020 (Neuron):** the 156-line screen list (Fig. 1B/S1) is probably in the NIHMS supplement PDF, which I did not
  open. Only P9/SS01540, P9S2, BPN and SS01587 are listed individually.
- **Ache 2019 (Nat Neurosci):** the 133-line flight screen has no per-line results in the text. It is listed as one
  screen row.
- **Guo, Zhang & Simpson 2022 (Curr Biol):** paywalled. The accepted manuscript at par.nsf.gov/servlets/purl/10384044
  failed to load (socket hang up). Line IDs come from a search snippet; figure panels were not seen.
- **Abstract only or paywalled:** Bidaye 2014 (Science), Sen 2017 (Curr Biol), von Reyn 2014 (Nat Neurosci), FlyMAD
  (Bath 2014; only the Supplementary Video title was seen), and Lee et al. 2026 (PNAS; activation not confirmed in the abstract).
- **Liessem et al. 2025 (bioRxiv 10.64898/2025.12.13.693955):** SS IDs are in Supplemental Table 3, which I did not see.
  Fig. S2-1B–C refers to further "additional neuron types" that are not named in the text.
- **Ispizua et al. 2026 (bioRxiv 10.64898/2026.05.03.722293):** I saw only the search snippet and abstract (headless DNg100
  CsChrimson). The figure panel still needs to be identified.
- **Ros 2024 (Curr Biol, DNae014/DNa15 flight turns):** PMC was blocked by a captcha and Europe PMC returned 500. The
  abstract centres on VES041 in flight. I made no lead because leg observability is doubtful.

## Checked and judged not qualifying (no lead written)
- Sterne 2021 (eLife 71679): anatomy and polarity only for DN lines; no activation.
- Namiki 2022 (Curr Biol, DNg02): activation screen of about 50 lines with wing-only readouts; legs not observed.
- Zhang et al. 2024 (Curr Biol, MGT/UMGT1): VNC neurons, not DNs.
- Dallmann et al. 2025 (Nature): imaging and connectomics of the DNg74/web DN; no activation found.
- von Reyn 2017 (Neuron): LC4 activation, not a DN.
- Chen et al. 2018 (Nat Commun): MDN/DNa01 imaging.
- Yang 2024 (Cell): only DNa02 was optogenetically activated; DNg13 was activated by current injection.
- Hampel 2015: the JO/aBN lines are not DNs (aDN lines are listed).
- Lee & Doe 2021: MDN adult activation is only cited. Pair1 adult activation is listed as a lead; I have not confirmed
  that Pair1 is a DN in adults.
- Jones et al. 2025: larval only.
- Not checked: Özdil et al. 2024/2026 (antennal grooming; may include activation, but I could not confirm DN activation)
  and Zung 2025 (catalogue, no behaviour expected).
- Possible lead not pursued: the UChicago thesis "Control of Escape Behavior by Descending Neurons in Drosophila
  melanogaster" (knowledge.uchicago.edu/records/2k54k-vav60). It probably overlaps with Dombrovski 2023.

## Uncertain mappings
- **BPN** (Bidaye 2020; Sapkal 2024 calls it "higher-brain neuron, not a DN"): left unmapped. The SS01587 row is mapped to
  DNp29 per Namiki Supp file 3, but Bidaye attributes the phenotype to BPN.
- **SS01588** has two Namiki rows (DNg30 and DNp26); both are listed.
- **DNae003 → DNxn123** via synonyms.csv (flywire/malecns name). **DNae014 → DNa15** via driver_lines.csv.

## Model / simulation exposure
- I opened no Pugliese 2026 or Sapkal 2026 material and visited no GitHub or Zenodo pages. GitHub links appeared in search
  results and were not opened.
- Some papers contain their own models (Sapkal 2024 in-silico panels, Dombrovski 2023 simulation, Özdil grooming
  simulations, Liessem connectome analyses). Under section 8 these are not sightings, and I did not read those parts.
- An arXiv result, "Synaptic placement reflects shared input in Drosophila descending neurons" (2610.00690), and a bioRxiv
  "whole-brain connectomics ... suppression of feeding during escape" preprint showed up in search results. I did not open
  either.
- **No sightings:** I saw no rhythm score, rank or driver call. `sightings.csv` was not created.
