# Notes: session pass1-grooming-r0-01 (pass1, grooming / limb-cleaning DNs)

No web access was used. All six assigned sources were read from their local copies in `sources/`. I did not open,
search for or use any Pugliese/Sapkal/BrainIR model output. **No score sighting occurred**, so there is no `sightings.csv`
and `saw_simulation_score` = false on all records.

Two sources contain the authors' *own* connectome analyses or models. Per PROTOCOL §8 these are not sightings. None of
them was used as evidence:
- Braun et al. 2024 makes "connectome-based predictions" (DN–DN degree / broadcaster vs standalone). I recorded only the
  measured optogenetic behaviour.
- Özdil et al. 2024 (bioRxiv) runs a "simulated activation screen" in a connectome-derived network (aDN1, DN52, etc.).
  It is the paper's own model, so it yields no records.

## Per-source summary
| source | disposition | records |
|---|---|---|
| Yoshikawa 2024 Curr Biol (10.1016/j.cub.2024.04.003) | no_qualifying_experiment | 0 |
| Zhang & Simpson 2022 iScience (10.1016/j.isci.2022.103792) | no_qualifying_experiment | 0 |
| Braun et al. 2024 Nature (10.1038/s41586-024-07523-9) | records | 43 |
| Özdil et al. 2024 bioRxiv (10.1101/2024.12.17.628844) | no_qualifying_experiment | 0 |
| Seeds et al. 2014 eLife (10.7554/elife.02951) | records | 3 |
| Hampel et al. 2015 eLife (10.7554/elife.08758) | records | 18 |

## What could not be accessed / caveats
- **Yoshikawa 2024**: only the author-manuscript XML text was available. Figures, Table S1 (the CsChrimson screen of
  ~100 GMR / split lines) and Table S2 were not downloaded. The text reports only MGT (a T3 VNC neuron) and UMGT1 (a VNC
  GABAergic neuron), so neither is a DN. If Table S1 lists DN lines with their phenotypes, a fetch session may want to
  check it. I gave the source `no_qualifying_experiment` rather than `unreachable` because the main text and legends
  were fully readable.
- **Supplementary videos** (all sources) were not downloaded and were not needed for the coding.
- **Braun 2024 peer-review file** (MOESM3) was not used as evidence. MOESM2 (reporting summary) has no text layer.

## Coding decisions worth checking
- **Braun 2024, Fig. 2**: the analysis kept only trials where the fly was walking before stimulation. So DNp09 is coded
  as a speed change (legs `not_assessed`, effect `speeds`). MDN reverses the fly into backward walking, which is coded
  yes for all legs with effect `not_assessed`.
- **Braun 2024, five excluded lines** (Web/DNg74, DNp24, DNg30, DNb01, DNg16): the lines were tested but excluded
  because they showed neither a known intact behaviour nor a clear headless phenotype ("no obvious phenotype on the
  spherical treadmill" for DNb01). No data are shown. I coded `no_visible_effect` in headless flies with legs `no` and
  low confidence.
- **Braun 2024, DNa01 intact**: "in place turning" from ball turn velocity is coded as locomotion (legs yes, medium).
  DNa02 and DNb02 "weakly trigger turning", so their legs are `unclear`.
- **Braun 2024, DNg11**: "foreleg rubbing" in intact and headless flies is coded as front-leg rhythm yes. Note that
  the quantification is only a static front-leg angle.
- **Braun 2024, Mute headless**: the text says ovipositor extension persists, but headless vs control is P = 0.117 (n.s.).
  Legs `not_assessed`.
- **Braun 2024, leg-amputation records (ED Fig. 10)**: preparation `other`; the amputated leg pair is coded `unclear`.
- **Seeds 2014**: this is a screen of >1500 GAL4 lines, but only the 12 hits are reported, so it is coded
  `targeted_study`. Only R18C11-GAL4 is known to label DNs. I took that from Hampel 2015 (read this session) and from the
  kit row R18C11 = 'aDN'. The other 11 lines (R23A07, R40F04, R26B12, R24B03, R71C07, R53A06, R50B07, R45G01, R48G01,
  R17F11, R53E05) are not described as labelling DNs and are not in driver_lines.csv, so they have no records.
  R26B12 labels aBN2, which are brain interneurons. The R18C11 result was read from the Fig. 2 grid only, so the records
  have low confidence.
- **Hampel 2015**: R18C11-GAL4 (aDN-GAL4) and aDN-LexA each target three aDNs plus other neurons. I wrote one record per
  aDN type (multi_dn). aDN3 has no mapping in the kit (`UNMAPPED`). The GAL4 lines R34C03, R11B11, R70H02, R71D01 and
  R76F12 (Fig. 2–figure supplement 1A) were activated, but the paper does not state that they label aDNs, so they have
  no records.
- The off-target cell groups for the aDN2 split pairs were read approximately from the Fig. 2I grid. They are described
  generically.
- Fig. 1–figure supplement 1A and Fig. 2–figure supplement 1A of Hampel 2015 both show R18C11-GAL4 grooming, probably
  the same data. I recorded it once.
- In Hampel 2015, middle and hind legs are not described during antennal grooming, so they are coded `unclear`
  throughout.

## Mapping notes
- DNp09 (SS01540), DNa01 (SS00731) and DNb01 (SS02383) are ambiguous in the kit (DNp71, DNxl022 and DNb09 respectively).
  I kept the paper's Namiki name with medium confidence.
- For SS01543 (DNg16) the kit's sources disagree (DNg16 vs DNg69). I kept DNg16 with medium confidence.
- Proposed driver-line rows (`proposed_driver_lines.csv`): R18C11 (aDN-GAL4), aBN1/aDN1 split (R34C03-AD;R71D01-DBD), and
  aDN2-spGAL4-3/-4 (R70H02-AD;R18C11-DBD, R70H02-AD;R76F12-DBD). No new synonyms are proposed, since aDN3 has no
  identifiable MANC type from these sources. `proposed_synonyms.csv` contains the header only.
