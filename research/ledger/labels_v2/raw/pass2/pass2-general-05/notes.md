# pass2-general-05: notes (phase 1)

## Scope
- I read `PROTOCOL.md` in full and used the kit files `type_list.csv`, `synonyms.csv` and `driver_lines.csv`. I searched the last of these by grep because it is too large to read whole.
- I read all six assigned sources from `sources/` only: text, figure legends, the relevant figure images and supplementary file 1 of elife.08758. No web access, GitHub or Zenodo, and I did not open any model, simulation or Pugliese/Sapkal material.
- **Sightings: none.** `sightings.csv` has only its header. `saw_simulation_score` is false on every record. elife.102230 contains the paper's own connectome analyses (FAFB/MANC input/output). Under section 8 that is not a sighting.
- **Results:** 29 of 29 experiments were found, so there are 29 records in `out/records.jsonl` (`pass2-general-05-0001` to `-0029`). `not_found.csv` is empty apart from its header.

## Sibling group (R18C11, Seeds 2014, exp 0044-0046, n_siblings = 3)
- Seeds 2014 itself never says which neurons R18C11 labels. The DN identities come from Hampel 2015 (elife.08758, also assigned): R18C11-GAL4 ("aDN-GAL4") "by itself targets expression to three aDNs", named aDN1, aDN2 and aDN3.
- Kit mapping:
  - aDN1 → DNg62
  - aDN2 → DNfl023
  - aDN3 → not in kit, so UNMAPPED
- Sorted alphabetically: DNfl023, DNg62, UNMAPPED. That gives sibling 1 = DNfl023 (exp 0045), sibling 2 = DNg62 (exp 0044) and sibling 3 = UNMAPPED/aDN3 (exp 0046). The count I found (3) matches n_siblings.
- `name_in_paper` is "R18C11" for these rows because Seeds names no neuron.
- Seeds' Fig. 2 grid shows only a p < 0.05 increase in eye/head cleaning for R18C11. Hampel's Fig. 1-fs1A shows a stronger antennal-grooming increase for the same line. Both are coded as anterior_grooming.

## Judgement calls / uncertainties
- **Grooming records:** front legs are `yes` and middle/hind legs `unclear`. Hampel scores all non-grooming time as "standing" by default rather than describing the flies as standing still. In Seeds, white space means "walking or standing".
- **aDN1-spGAL4-1 with antennae amputated (exp 0048):** Fig. 2B only compares amputated vs intact (n.s.). There is no test against amputated controls, so labeler_confidence is low.
- **aDN2 mapping:** synonyms.csv maps aDN2 unambiguously to DNfl023. One driver_lines.csv row (from eLife 107450) instead gives aDN2-spGAL4-2/3/4 as UNMAPPED with the name "DNg127". DNg127 is not in type_list.csv, so I kept DNfl023 at high confidence. An adjudicator may want to look at this conflict.
- **DeepFly3D "aDN-Gal4" (R76F12-AD; R18C11-DBD):** this enhancer pair is Hampel's aDN2-spGAL4-2, so it maps to DNfl023 (medium confidence, via the listed driver line).
- **aBN1/aDN1-spGAL4 (exp 0049/0050):** this line co-labels aBN1, a non-DN brain interneuron that by itself elicits antennal grooming. I coded it as minor_offtarget, but the behaviour cannot be attributed to aDN1.
- **DNa02 bilateral group (exp 0002, record 0023):** I coded no_visible_effect / effect_on_walking none at low confidence. The authors say forward-velocity changes were indistinguishable from no-expression flies (visual startle), so the dataset can't test a forward-velocity effect (data not shown). This is not a clean negative.
- **MDN, Carreira-Rosario 2018:** sex is not stated (`unknown`). In the Fig. 8H record the paper writes the effector as "Chrimson" (LexAop-Chrimson:Venus), while the input row said CsChrimson; I kept the paper's wording. For exp 0001 I broadened the locator to Fig. 8C-F because the genetics and anatomy panels support the Fig. 8D result.
- **Pair1:** not in the kit, so UNMAPPED / low. No synonym is proposed because the kit gives nothing to support one. The sex for the open-field assay (Fig. 3-fs1) is not stated.
- **Preparation:** given values were kept for every row. The "other" rows are antennae-amputated free-moving flies.
- **Proposed kit additions:** `out/proposed_driver_lines.csv` lists R18C11 as a multi-type aDN line (DNg62 and DNfl023). In the current kit R18C11 is only marked UNMAPPED.

## Not accessed
- Videos were not downloaded (as listed in each source's text.txt). No needed figure was missing.
