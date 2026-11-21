# Notes: session pass1-recent_broad-r0-04 (pass1)

## Scope
I read all 6 assigned sources from their local copies in `sources/` (text.txt, figure legends, and the relevant figure
images: 38554 Fig. 8, 48571 Fig. 5, 69767 Fig. 3, 79887 Fig. 2). I did no web access. I did not open any model,
simulation or prediction, and I saw no Pugliese-type score, rank or driver call, so there is no `sightings.csv`. Every
record has `saw_simulation_score` = false.

## Per source
- **10.7554/elife.38554 (Carreira-Rosario 2018)**: 2 records. Almost all experiments are larval and therefore excluded. The
  two adult experiments (Fig. 8D, Fig. 8H) use intersectional or immortalization genetics that start from larval MDN lines
  and lead to backward walking.
  - I coded `expression` = `stochastic` because FLP-based labelling varied between flies: 2 of 10 flies in 8D lacked
    expression, and 8H used preselected larvae.
  - Off-target neurons are noted from Fig. 8F and Fig. 8I.
  - Videos were not downloaded, so leg coding follows the convention for backward walking.
  - I proposed the driver lines ss01613, VT044845-lexA and Split1 (R49F02-AD;R53F07-DBD) for MDN.
- **10.7554/elife.48571 (DeepFly3D, 2019)**: 2 records (MDN and aDN, tethered females on a ball).
  - The "aDN" line R76F12-AD;R18C11-DBD appears twice in `driver_lines.csv`. One row maps it to DNfl023 (aDN2). Another
    row for the same enhancer pair (aDN2-spGAL4-2, from eLife.107450 Supp. Table 5) maps it to DNg127, UNMAPPED. I used
    DNfl023 with `mapping_confidence` = medium. An adjudicator should check this.
  - The paper's text only says "aDN" (citing Hampel 2015), not aDN1 or aDN2.
- **10.7554/elife.58942 (Schretter 2020)**: no qualifying experiment. The neurons activated are aIPg and pC1a-e, which are
  central-brain neurons and not DNs. The Robie et al. 2017 GAL4 screen is only summarised (top hits); it is not reported
  line by line here.
- **10.7554/elife.69767 (Lee & Doe 2021)**: 2 records for adult Pair1 activation (R75C02-Gal4 > CsChrimson), both
  `halting`.
  - **Pair1 is not in type_list, synonyms or driver_lines**, so I set it to UNMAPPED. The paper describes it as a GABAergic
    SEZ descending neuron with a medial SEZ soma and a contralateral axon in a very lateral tract that mainly innervates
    T1. That is not enough to choose a MANC type, so I proposed no synonym.
  - In Fig. 3 (females, closed-loop arena), time spent in "small movements" increased during activation. These are body-part
    movements without translocation, such as grooming or wing movement; legs were not scored individually. Per convention I
    coded all leg pairs `no` for halting and added secondary `other`.
  - The open-field assay (Fig. 3—figure supplement 1) does not state the flies' sex, so I coded `unknown`.
- **10.7554/elife.71679 (Sterne 2021)**: no qualifying experiment. It is an anatomical resource only.
- **10.7554/elife.79887 (Shiu 2022)**: no qualifying experiment, but this is a borderline case to flag. The descending
  neurons Bract (kit synonym for DNfl021; lines SS31320 and SS31386, Fig. 2D) and Fudog (kit synonym for DNg67; lines
  SS35290 and SS35291, Fig. 1—figure supplement 2B) were activated with CsChrimson in adult females. However, the flies
  were mounted on glass slides with nail polish and scored only for proboscis extension within 5 s. The paper does not
  describe or score legs, so I judged that leg movement was not observable as section 1 requires. Results as reported:
  Bract gave about 100% PER; Fudog did not elicit PER. If adjudication prefers records with legs `not_assessed` for such
  assays, these are the candidates.

## Uncertainties
- Sex was not stated for either MDN experiment in 38554, so I coded `unknown`.
- `effect_on_walking` is `not_assessed` for the MDN backward-walking records, because the leg-rhythm fields capture the
  outcome.
