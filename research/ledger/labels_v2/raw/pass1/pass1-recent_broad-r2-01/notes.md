# Session pass1-recent_broad-r2-01: notes

Pass `pass1`, source family "other activation studies, 2018-2026". I read only the 3 assigned local sources. I did no web
access and did not open or search for any model, simulation or Pugliese/Sapkal material. **No score sightings**, so there
is no `sightings.csv`. Source 1 (Steinfath et al. 2025) has its own rate-based circuit model of song and vibration
(Fig. 6, Supp. info). That does not count as a sighting, and none of my records rely on it.

## 10.1038/s41467-025-64907-9 (Steinfath et al. 2025, Nat Commun): 3 records
- Read: text.txt, Fig. 3 and Fig. 4 images, supplementary PDF text (Figs S4 and S6 legends), the peer-review file (by grep), and
  source-data CSVs (Fig3AC, Fig4B headers).
- **Record 0001, DNp28 / SS01587.** The paper calls the neuron DNp28. Its driver, SS01587 (R11H10-AD; VT033947-DBD,
  Table 1), is listed in `driver_lines.csv` as **DNp29** (Namiki 2018; Zung/Namiki 2025). The R11H10 GAL4 is also DNp29 in
  the kit. I coded `manc_type` = DNp29 with `mapping_confidence` = medium and explained why in `mapping_basis`. **An
  adjudicator should check this: the printed name and the line identity disagree.** I proposed no mapping for this conflict.
- Walking was measured as body velocity from video tracking, with no leg tracking. Female velocity rose from about 1 to about
  10-12 mm/s (read from the Fig. 3C trace). I coded all legs `yes` under the "increased locomotion" convention, with
  confidence medium.
- pIP10 and pMP2 (Fig. 4B): solitary males in a chamber with a video camera. Only song and vibration were scored, so legs
  are `not_assessed` (wing/song convention).
- Not recorded: P1a and pC2l activations (brain-local neurons, not DNs), and vGlut-GtACR1 (silencing).

## 10.1016/j.cub.2026.07.076 (Palacios Castillo et al. 2026, Curr Biol): 2 records
- Only the XML full text was available locally. **Figure images (Figs 1-7), Table S1-S4 and Data S1 were not
  downloaded.**
- The only DN activation: "VL neurons" (OA-VL1 = DNd02, OA-VL2 = DNd03), CsChrimson in the male aggression assay
  (Fig. 6B). The text says only that they "did not decrease aggression". Walking speed (Fig. 6D) was reported only for
  ASM lines, which are not DNs.
- I could not identify the VL driver line IDs or n without Fig. 6B. I wrote one record per VL type (multi_dn, legs
  not_assessed, behaviour `other`, confidence low). **A session that can fetch Fig. 6B and Data S1 (sheet I/K)
  should add the line IDs and n, and check whether walking speed was measured for the VL lines.** The text also says
  ASM1-labelling lines co-label VL neurons, so ASM1 lines may also count as DN-labelling lines. I did not write records
  for them because the text does not say which lines they are or what happened.
- AL2i1/AL2i2 flight experiments (SS32637, OTA-SG11) use non-descending optic-lobe neurons, so they are not records.

## 10.1038/s41593-024-01738-9 (Shiozaki et al. 2024, Nat Neurosci): no qualifying experiment
- The freely moving single-fly and paired-fly activations of pIP10 and pMP2 (Figs 2b, 7; Ext. Data Figs 4b-c, 9) were
  recorded with microphones only. No camera is described for those chambers, so leg movement was not observable.
- The tethered activations (calcium imaging, and the decapitated pIP10 experiment in Ext. Data Fig. 1q-r) had the fly glued to a plate
  by the legs (middle and hind legs cut at the femur-trochanter junction). Only wing video was recorded.
- The ball-standing brain-imaging preparation used the song driver R22D03-LexA, which labels P1 and other neurons and is
  not a DN line.
- From the Methods, this source supports two kit mappings (pMP2 = SS43275; pIP10 split = VT040556-AD x VT040347-DBD). I
  added them to `proposed_driver_lines.csv`.

## Uncertainties
- Records 0002, 0003, 0004 and 0005 have every leg field `not_assessed`. I kept them because the protocol's
  wing/song convention covers such experiments, but they say nothing about leg rhythm.
- The Curr Biol stimulation intensity is printed as "12μM/cm2", probably meaning µW/cm2. I copied it as printed.
