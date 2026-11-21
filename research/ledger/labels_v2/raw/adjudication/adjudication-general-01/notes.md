# Adjudication notes: session adjudication-general-01 (pass: adjudication)

## Scope
- 36 experiments from `disagreements.csv` (62 disputed fields) across 6 assigned sources. I wrote one complete record per experiment to `records.jsonl` (`adjudication-general-01-0001` to `-0036`, with `exp_id` copied unchanged). `decisions.csv` has one row per disputed field, plus two companion rows (`mapping_confidence`, `mapping_basis`) for the single `manc_type` dispute.
- No web access was used. All evidence comes from the local `sources/` folders (text, figure images, supplementary text/CSV).
- The undisputed fields in each record are my own reading of the source. The disagreement file does not carry the readers' agreed values, so some undisputed fields may differ from what the readers wrote. The most likely differences:
  - Halting paper, P9 alone (Fig. 2b): I set the legs to `not_assessed` because the flies were already walking (turning/speed convention).
  - Nature 2024 headless DNp09 (Fig. 4b): I set the legs to `no` because the ball tracking shows no forward walking.
  - MDN records: `effect_on_walking` is `not_assessed` because the effect, backward walking, is captured in `behaviour_category`.

## Main judgement calls
- **Line specificity is coded from each source's own statements and images.** The same line therefore gets different codes in different papers:
  - **SS01540 in the Nature 2024 descending-networks paper (Braun):** `clean`. The paper describes "cell-specific expression", and its limitations section names off-target cells only for aDN2.
  - **SS01540 in the halting paper (Sapkal 2024):** `clean`. Extended Data Fig. 4a shows 0 ectopic cells in P9+BRK, a genotype that contains every P9 cell.
  - **SS01540 in the freezing paper (Zacarias 2018) and the walking-initiation paper (Bidaye 2020):** `minor_offtarget`. Zacarias removed off-target expression from its image in Photoshop. Bidaye reports "a few additional neurons" including gamma-lobe expression, and off-target cells in the freezing genotype.
  - **Why this matters:** Bidaye says off-target labelling depends on the reporter genotype, so per-source coding is defensible. Downstream users should still know that Bidaye reports extra cells in SS01540.
- **MDN line in the halting paper:** `unknown`. The MDN split is only imaged combined with halt lines, and ectopic cells from a combination cannot be attributed to the MDN split alone.
- **oDN1 and BDN2 lines (halting paper) and MDN3 (Current Biology 2022):** `unknown`. The papers state an intent to target the neurons, or call the line "narrow", but give no off-target assessment.
- **Walking initiation from a standing or grooming state:** `effect_on_walking` = `speeds`. Translational velocity is measured and rises, so `not_assessed` would understate the data. I applied this consistently to the DNp09, oDN1 and BDN2 records.
- **Freezing paper DNp09 record:** legs `no`, `halting`. Freezing is the dominant outcome (61.5% of trials). The brief initial speed spike happens in flies already walking at about 10 mm/s, so it counts as a speed change.
- **Bidaye 2020 freezing-assay record (`-0019`):** legs `unclear`, effect `stops`, confidence `low`. The text reports both increased walking (all four genotypes) and freezing (one genotype). Fig. S2F-G is not in the local copy, so the balance between running and freezing cannot be read.
- **Bidaye 2020 SS01587 (`-0014`):** `manc_type` = `UNMAPPED`, confidence `low`.
  - The paper names the DN "DN0p28". That name is not in the kit and looks like DNp28, while the kit maps SS01587 to DNp29.
  - The paper's mosaic analysis attributes the walking to BPN, a non-DN brain neuron.
  - Mapping this record to DNp29 would credit that DN with a phenotype the paper assigns elsewhere.
- **Communications Biology 2025 R60F09 records:** `minor_offtarget` is the closest available category. R60F09-GAL4 is a broad line, and the paper attributes the backward walking to MooSEZ, a non-DN neuron. Both records are `UNMAPPED`.

## Access gaps (not unreachable: the full text was readable)
- 10.1016/j.neuron.2020.07.032 (Bidaye 2020): the local copy is PMC XML text only, with no figure images and no supplementary figures. Figs. 1, 2, 4, S1, S2 and S5 were coded from the text and main-figure legends. A later session could fetch the supplementary PDF to firm up records `-0019`, `-0032` and `-0031`.
- Supplementary videos were not downloaded for any source. None was needed for a decision.

## Simulation / score sightings (PROTOCOL section 8)
- **No sightings.** I saw no Pugliese-type rhythm score, rank or driver call. `sightings.csv` has only its header, and every record has `saw_simulation_score` = false.
- **For transparency, I did see two papers' own connectome models.** Section 8 says these do not count as sightings:
  - **Braun 2024** connectome DN-DN network analysis: Fig. 3, Fig. 5b-e, Extended Data Figs. 4-5.
  - **Sapkal 2024** connectome-constrained spiking-network simulation: Fig. 3a-h, Extended Data Fig. 6b-c. These show simulated firing-rate changes for walk/halt co-activation, not rhythm scores.
- I did not open the Pugliese 2026 or Sapkal 2026 papers, GitHub or Zenodo.
