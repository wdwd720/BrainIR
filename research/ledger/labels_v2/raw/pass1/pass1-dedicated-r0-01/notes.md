# Session pass1-dedicated-r0-01: notes

Pass: pass1. Family: walking-CPG papers (dedicated session). No web access was used; everything comes from the local
copies in `sources/`.

## What was read

### 10.1101/2025.09.12.675944 (Pugliese et al., bioRxiv v2)
- Read: `text.txt` (whole main text, legends, Methods and Extended Data legends), the PDF text (`supp/article.txt`) for
  the genotype table (PDF p. 29, image-only in the XML), and figure images Fig. 2, Fig. 5 and Extended Data Fig. 3.
- Deliberately not opened: Fig. 1 image, Extended Data Figs. 1, 2, 4-10 images (all simulation results), and the
  Supplementary Table 1/2/10 pages (DN rhythm-score tables). Extended Data legends were read as text only.
- Experiments found: (1) DNg100 (VT058557-AD x R85F12-DBD) > CsChrimson in headless female flies on a ball, at three laser
  intensities (Fig. 2h-j, ED Fig. 3); (2) DNb08 (SS70620) > CsChrimson in headless female flies (Fig. 5c-e), front and
  middle legs only tracked; (3) a one-sentence mention that DNb08 movements were less reliable on the treadmill.
- Not recorded: the paper also cites earlier DNg100 headless walking (its ref. 50, Sapkal 2024) but did not show that
  experiment; there are no other activation experiments.
- **Sightings** (see `sightings.csv`): the abstract and main text rank DNg100 and DNb08 as top-scoring in the simulated DN
  activation screen, and Fig. 2e / Fig. 5b (opened for the experimental panels) show their simulated rhythmicity-score
  distributions. So `saw_simulation_score` = true on every DNg100 and DNb08 record, in both sources. No scores were
  seen for any other DN type. The Discussion names DNg97, DNg74, DNg12 and DNg62 as inputs to the CPG neurons, and the
  Supplementary Table 10 footnote mentions DNg97/DNg62, but no scores for them were displayed in what I read.

### 10.64898/2026.04.29.721658 (Sapkal et al., bioRxiv v2)
- Read: the whole `text.txt`, figure images Fig. 1, 3, 4 and Extended Data Figs. 1, 5, 7, and Supplementary Tables 1-2
  (`721658_file09`, `721658_file10`). I only checked the header of Supplementary Table 3 (`file11`; connectome IDs).
- This paper contains no Pugliese-type simulation screen output. Its own analysis is connectome path analysis, with no
  rhythm scores. No sighting.
- Experiments: DNg100, DNg97 and MDN in decapitated flies under four conditions (ball, slippery surface, air, amputated
  legs in air); DNg100 with FeCO silencing, with proximal joints glued, unilateral (stochastic), with leg-removal subsets,
  with an intensity series (ball and air), and head-intact; DNg16, DNg55 and DNg75 alone (no walking); and co-activation of
  DNg100 with DNg16, DNg55, DNg75 or DNg97 (ball and air). BPN (brain neurons, not DNs) was not recorded.

## Coding decisions and uncertainties
- **One record per surface.** The sensory-deprivation conditions change which legs step, so each condition is its own
  record. Amputated legs = `headless`, surface `air`, with the amputation in `sensory_condition`.
- **Front-leg-only or hind-leg-only stepping** (DNg97 and MDN in reduced-feedback conditions) is coded
  `behaviour_category` = `other`, with per-leg rhythm fields. Leg pairs whose Fig. 1e distributions are wide and include
  many 0-Hz trials are coded `unclear`.
- **effect_on_walking**: for walking induced from rest in headless flies I used `not_assessed`, because section 3 reserves
  the field for flies that were already walking. For the co-activation ball records I used `speeds`/`slows`/`none`
  **relative to DNg100 alone**, and say so in each record's notes.
- **Frequencies** marked "read off the plot" are my approximate readings of medians from figure panels. Values quoted in the
  text (MDN 2 Hz and 7.6 Hz, about 11 Hz, about 22 Hz) are exact.
- **Line specificity**: DNg100 is coded `minor_offtarget`, based on ED Fig. 5a (0-2 non-DNg100 VNC cell types in the
  stochastic version). DNg55 and DNg75 are `minor_offtarget` (1 ectopic VNC cell type each, ED Fig. 7d), and DNg16 and
  DNg97 are `clean` (0). MDN is `unknown` (not shown). Pugliese lines are `unknown`.
- **DNb08 surface (record 0002)**: inferred as `air`. The Methods put only the DNg100 flies on the treadmill, the Fig. 5d
  schematic shows no ball, and the text says the movements were more reliable without the treadmill. Record 0003 (the
  on-ball mention) is low-confidence and could be merged or dropped.
- **Possible duplicates**: record 0025 (Fig. 4 DNg100, air) has the same n (4 flies, 38 trials) as record 0006 (Fig. 1 air),
  so it may be the same data. The DNg97-alone data in ED Fig. 7e appear to reuse Fig. 1 (6 flies, 60 trials), so no
  separate record was written for them. The DNg100(h) homozygous group (ED Fig. 7e) is mentioned in record 0023 rather
  than recorded on its own.
- **MDN line**: the paper is inconsistent about which hemidriver is the AD and which is the DBD (Supplementary Table 1 vs
  Table 2). The kit row for this pair is UNMAPPED, so I proposed MDN.
- Supplementary videos for both sources were not downloaded and were not needed for coding.

## Files
- `records.jsonl`: 44 records (3 from Pugliese, 41 from Sapkal).
- `dispositions.csv`, `sources.csv`, `sightings.csv`, `proposed_driver_lines.csv`, `proposed_synonyms.csv`.
