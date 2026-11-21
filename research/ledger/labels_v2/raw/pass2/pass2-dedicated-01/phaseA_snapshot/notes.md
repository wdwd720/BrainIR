# Session pass2-dedicated-01 (pass2): independent second reading

## What I did
- Read PROTOCOL.md (v2, including section 8), record_schema.json, the experiment list, assigned_sources.csv and the kit
  (type_list.csv, synonyms.csv, driver_lines.csv) for every name used.
- Read the two assigned sources from their local copies only (no web access used):
  - Pugliese et al. (bioRxiv 10.1101/2025.09.12.675944, v2): text.txt (results sections that cover the experiments,
    Methods "Fly behavior and optogenetics experiments", Supplementary Information, Extended Data legends), PDF page 29
    (genotypes table), Fig. 2, Fig. 5, Extended Data Fig. 3.
  - Sapkal et al. (bioRxiv 10.64898/2026.04.29.721658, v2): text.txt (Abstract to the end of "Co-stimulation of
    descending inputs...", and Methods up to "Intensity-sampling activation"), Fig. 1-4, Extended Data Figs. 1, 5, 6, 7,
    Supplementary Table 1 (file09) and Supplementary Table 2 / key resources (file10).
- Deliberately NOT opened: Pugliese Fig. 1 and Supplementary Table 1 (the DN activation screen), Pugliese Methods on the
  simulation screens; Sapkal sections "Kinematics-guided connectome search..." and "Connectome analysis", Sapkal Fig. 5,
  Extended Data Figs. 8-12 and supp file11 (CPG/DN sheets).
- 44 of 44 experiment rows found and recorded (records 0001-0044, in row order). not_found.csv is empty (header only).
  All rows had n_siblings = 1.

## Simulation-score sightings (see sightings.csv)
- Pugliese: rhythmicity scores, ranks and driver calls for **DNg100** and **DNb08** are printed in the main text, figure
  headings and legends, Fig. 2e/f and Fig. 5b/5i. These were unavoidable while locating the experiments.
  `saw_simulation_score` = true on every DNg100 and DNb08 record, including all Sapkal DNg100 records.
- I saw no Pugliese-type score for DNg97, MDN (DNp50), DNg16, DNg55 or DNg75. Those records have false. Sapkal cites
  Pugliese (ref. 26) in its experimental text but prints no scores there.

## Coding decisions and uncertainties
- **Row 0002 (DNb08, Fig. 5c-e):** the surface is not stated for DNb08. Methods put only the DNg100 flies on the
  treadmill, the Fig. 5d schematic shows no ball, and the text says movements were "evoked more reliably when the
  spherical treadmill was removed". Coded `air`, confidence medium. Hind legs were not reported (`not_assessed`).
- **Row 0003 (DNb08, main text, no figure):** the only main-text content beyond Fig. 5 is the treadmill comparison. I
  recorded it as the on-treadmill condition: movements evoked less reliably, front and middle `unclear`, confidence low.
  If the first-pass row meant the main-text summary of the Fig. 5 experiment, it duplicates 0002.
- **Air or amputated stepping without a substrate:** `behaviour_category` follows the stepping direction
  (forward_walking for DNg100/DNg97, backward_walking for MDN). The surface and restricted legs are in notes and
  sensory_condition. I used `other` for front-leg-only Fe-Ti oscillation (0017), leg-removal air-stepping (0020) and
  unilateral air-stepping (0019).
- **`effect_on_walking`** is `not_assessed` everywhere except unilateral DNg100 on the ball (`turns`), because the
  headless flies were not walking before stimulation (protocol section 3). Speed differences between co-activation
  genotypes and DNg100 alone are described in notes.
- **Per-leg calls in Sapkal Fig. 1e:** frequencies and medians were read by eye from the scatter plots, so they are
  approximate. Where the text says stepping occurs "to a smaller extent", or a median is near 0 with a wide spread, I
  used `unclear`. Examples: DNg97 mid and hind legs in the slippery and amputated conditions; MDN front legs on the
  slippery surface; MDN mid legs in air and amputated. Clear zero medians with flat example traces are `no` (DNg97
  hind legs in air; MDN front legs in air and amputated).
- **DNg97 on the ball:** coded `yes` for all legs because the text says it "drove stepping rhythms across all six legs",
  although the authors attribute mid and hind stepping to passive mechanical coupling.
- **Sex:** Sapkal Methods say male unless indicated; FeCO-silencing flies are female. Pugliese flies are female.
- **Line specificity:** Sapkal calls its DNg100, DNg97 and MDN splits "highly specific" (coded clean). Extended Data
  Fig. 7d counts ectopic VNC cells: DNg55 alone 1 and DNg75 alone 1 (minor_offtarget), DNg16 alone 0, DNg97 alone 0, and
  2-3 in the combined genotypes (added to other_cell_types). The Pugliese lines have no specificity statement
  (`unknown`). Unilateral flies show 0-1 ectopic VNC cells (minor_offtarget).
- **Co-activation genotypes (0029-0044):** one record per DN type (DNg100 and its partner), `multi_dn`, each naming the
  other.
- **Intensity series (0001, 0021, 0022):** coded at the strongest intensity. In 0021 and 0022 the lowest levels gave
  little or no stepping; this is in penetrance and notes rather than in separate records.
- **MDN genotype:** Sapkal Supplementary Table 1 writes VT044845-ZpGDBD;VT050660-p65ADZp, with the AD and DBD halves
  swapped relative to its key resources table. driver_lines kept as given in the experiment list.
- **Row 0023 (DNg100 head-intact):** n is not given in Supplementary Table 1 (n_flies null). Only ball velocity was
  measured, so confidence is medium.
- Three Sapkal driver lines not in the kit (DNg16, DNg55, DNg75) were added to proposed_driver_lines.csv. All mappings
  in this session are name-based and high confidence; MDN maps to DNp50 via synonyms.csv.

## Files written (all in out/)
records.jsonl (44), dispositions.csv, sightings.csv, not_found.csv (empty), proposed_driver_lines.csv, sources.csv,
notes.md.
