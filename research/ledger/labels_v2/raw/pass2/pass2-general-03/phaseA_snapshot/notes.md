# pass2-general-03: notes (independent second reading, phase 1)

## Scope and method
- I read PROTOCOL.md (v2, including section 8), record_schema.json, the kit (type_list.csv, synonyms.csv and
  driver_lines.csv, the last searched by line ID), experiments_to_label.csv (23 rows, all `n_siblings` = 1) and
  assigned_sources.csv (6 sources).
- I used only the local copies in `sources/<slug>/`: text.txt, figure images, supplementary text/CSV and page text.
  No web access. I did not open any GitHub/Zenodo, Pugliese or Sapkal material.
- Every row in experiments_to_label.csv was located in its source. 23 records were written to `out/records.jsonl`.
  `not_found.csv` contains only its header.
- Score sightings: none. All records have `saw_simulation_score` = false, and `sightings.csv` contains only its header.
  Two passages mention modelling but are not sightings (section 8): the bootstrap "simulated fly" control in
  Rayshubskiy et al. Fig. 8C, and a cited "computational analysis" of PFL3 pathways in 10.1101/2024.06.27.601106.
  Neither gives a rhythm score, rank or driver call from a connectome activation screen.

## Decisions and uncertainties
- **10.1038/s42003-025-09344-6 (MooSEZ).** All three lines label unnamed "SEZ descending neurons" together with MooSEZ,
  which is not a DN. The authors attribute backward walking to MooSEZ. The DN types cannot be mapped (`UNMAPPED`, low).
  I coded R60F09-GAL4 and the Otd-restricted version as `line_specificity` = unknown because both lines are broad.
  Backward walking was measured from centroid velocity only, so `labeler_confidence` = medium.
- **10.1101/2020.04.04.024703 (DNa02 ReaChR).** Unilateral group: n given as 16 in the Fig. 8B legend, but the Methods
  count 17 brains with left- or right-only expression; I recorded 16 and explained this in `n_flies_note`. The
  bilateral group record (0005) rests on a "data not shown" statement: forward-velocity changes were indistinguishable
  from unilateral and no-expression flies (visual startle). I coded it as no_visible_effect, confidence low.
- **10.1101/2023.08.30.555537 (song).** pMP2 and pIP10 are MANC types in type_list.csv, so mapping is high. The paper's
  table gives MANC v1.0 types DNxn046 and DNxn048 for them; I proposed these as synonyms. The kit has SS43275 and SS46542
  as UNMAPPED (names DNp84 and DNp79); I proposed mappings. The pMP2 line has an off-target "pIP1" in the brain, and the
  kit lists pIP1 as an ambiguous synonym of pIP10, so this off-target cell could itself be a DN. Legs are never
  described: all leg fields are `not_assessed`. I coded `source_type` = systematic_screen because the paper reports
  every tested line, but the screen scored song, not legs.
- **10.1101/2023.10.15.562426.** The DNa02 bilateral SPARC record has n=3. The DNg13 record (Methods, no figure) is
  confounded: light stopped locomotion whenever an off-target ascending neuron expressed CsChrimson, whether or not DNg13
  did. Coded as halting, confidence low, with the authors' attribution in `notes`. The SS ID is not printed; I matched
  hemidrivers VT027166AD;VT009857DBD to SS02259 via the kit.
- **10.1101/2024.06.27.601106.** I coded leg rhythm `yes` for the DNa11 intact leg-kinematics record (stepping about
  3 Hz in all six legs, read from Fig. 6f) and for the amputation record (`preparation` = other: tethered, five legs
  amputated). The pre-stimulus stepping state is not reported, so the intact record is medium confidence. For the
  headless DNa11 record, 8/8 flies turned. The surface is inferred as ball, and legs are `not_assessed` because the
  video is not available locally and the text does not describe the legs. DNae003 maps to DNxn123 via a non-ambiguous
  synonym. For DNa03-SS2 (SS84990) only distribution plots exist (Fig. S3) and the line is broad: confidence low. DNa06
  activation produces head rotation with minimal body turning, coded `other` with secondary posture. Sex was coded
  female from the Methods default ("in most of the experiments, only females"), with no stated exception for SPARC.
- **10.1101/2025.07.22.666129 (DNp17 / SS02553).** The kit lists SS02553 as AMBIGUOUS (DNp17;DNut046), and "DNp17" is
  also an ambiguous synonym of DNut046. With only kit information, the paper's anatomy does not separate the two, so
  both records are `UNMAPPED` (low), with the candidates given in `mapping_basis`. The authors show that the walking
  phenotype comes from the off-target DopaMeander neuron. The DNp17-without-DopaMeander SPARC group shows a small speed
  increase ("only slightly, if at all"): legs `unclear`, confidence low.

## Not accessible
- Supplementary videos (all sources) were not downloaded. No figures needed for labelling were missing.
