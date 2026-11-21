# verify-01 notes

Session: `verify-01` (verification of a random sample; 30 rows across 11 assigned sources).
I used only the local files under `sources/`: no web access, no model or simulation output.

## Method
- For each row I searched the local text (`text.txt`, `supp/article.txt`, supplementary text) for the quote, then read
  the surrounding Results text and the figure legend. Where the outcome depended on a figure, I opened the figure image
  (Braun et al. 2024 Fig. 4, ED Fig. 5, ED Fig. 6; Cande et al. 2018 Figs 1, 2, 5, 6 and Supplementary File 1 pages 6,
  12, 13, 14, 20, 22, 34, 41; Yang et al. 601106 Fig. 6).
- `front_leg_rhythm` was decided with PROTOCOL sections 2-4 (walking = yes; single movements such as takeoff or landing
  extension = no; wing or song only = not_assessed; grooming = yes for the rubbing legs).
- Cande et al. 2018 atlas rows: the quote is the line ID, which is printed as the panel title on the Supplementary
  File 1 page images (the PDF text layer is empty), so `quote_found` = true. I judged behaviour from where the
  significant region sits in the behaviour map (Fig. 1C layout) and cross-checked it against the paper's Fig. 6B
  grouping by DN type.

## Results summary
- All 30 quotes were found (differences only in line breaks and hyphenation).
- front_leg_rhythm: yes 15, no 8, unclear 4, not_assessed 3, cannot_verify 0.

## Uncertain calls and issues for adjudication
- **DNa01 headless (ED Fig. 5c)**: I coded `no` because the paper says the behaviour is lost and reports no other
  headless phenotype. Only turn velocity is plotted, though, so this rests on the absence of any reported effect.
- **DNb01 (Braun 2024 Methods)**: the only evidence is "no obvious phenotype on the spherical treadmill". There is no
  figure and the preparation is not stated, so whether this counts as a record at all is borderline.
- **P9 freezing genotype (Bidaye 2020 Fig. S2F-G)**: the text says all genotypes, including the one that freezes,
  initiate walking. If this record was coded as a freeze (`no`), it conflicts with the source.
- **DNg11 headless**: "foreleg rubbing" comes from the text. The figure shows only a sustained joint-angle shift and
  no cycle count.
- **Atlas SS01569 (DNd02/DNd03)**: the significant regions are central, not on the locomotion arc, so I coded `unclear`.
  **SS00898 (DNg17)** and **SS02259 (DNg13)** sit in the "anterior movements" region, so I also coded them `unclear`.
  **SS01597 (DNg07)** has a small region near the lower edge and I coded it `yes` with low-medium confidence.
- **Name mapping flag**: SS02612 is "DNp07_2" in 10.64898/2025.12.13.693955 (Supplemental Table 1) but "DNp05" in
  10.1038/s41586-022-05562-8 (Extended Data Fig. 1 / Supplementary Table 1). Its type mapping should be checked.
- **Locator / line-ID issues**: SS46542 (pIP10) and SS43275 (pMP2) do not appear anywhere in the local text of
  10.1101/2023.08.30.555537. For pIP10+vPR9, the legend has panels H-J while the Results text cites I-K.
- **MDN+BB (Sapkal 2024 halting paper)**: the rhythm comes from MDN-driven backward walking. BB is a halt neuron
  co-activated with MDN.

## Access
All 11 assigned sources were available as full text locally. Videos were not downloaded and were not needed for any
decision, although they would sharpen the DNa01-headless, DNg11 and DNb01 calls.

## Simulation scores
No Pugliese-type rhythm score, rank or driver call was seen, so `out/sightings.csv` was not created. Some sources
contain their own connectome analyses (for example ShREC in 10.64898/2025.12.13.693955 and DN–DN connectivity in
Braun 2024). These are those papers' own models and do not count as sightings under PROTOCOL section 8.
