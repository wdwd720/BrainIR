# adjudication-dedicated-01: notes

## Scope
- 25 disputed fields across 25 experiments: 1 from Pugliese et al. (bioRxiv 10.1101/2025.09.12.675944) and 24 from Sapkal et al. 2026 (10.64898/2026.04.29.721658). Both sources were read from local files only, with no web access. Both are full text, with figures and Supplementary Table 1 (Sapkal).
- Output: one complete record per experiment (`records.jsonl`, 25 lines, `exp_id` copied), one decision per disputed field (`decisions.csv`), plus `dispositions.csv`, `sources.csv` and `sightings.csv`.

## Decision rules applied
1. **DNg100 line specificity, `minor_offtarget` (13 rows).** The paper calls its split lines "highly specific", but Extended Data Fig. 5a labels "Ectopic VNC cells" counts of 0-2 per fly for the DNg100 split line (VT058557-p65ADZp;R85F12-ZpGDBD) on its own, including DNg100-negative flip-out flies. The ectopic cells are never identified, so `other_cell_types` describes them rather than naming a type. I did not use the co-activation counts in Extended Data Fig. 7d to infer the DNg100 line's own off-target: combining two AD/DBD pairs can create new cross-intersections.
2. **`effect_on_walking` = `not_assessed` for decapitated preparations (11 rows).** Decapitated flies do not walk before stimulation (Fig. 1b controls; Extended Data Fig. 5b). PROTOCOL section 3 reserves this field for turning or speed changes in a fly that was already walking. So:
   - Unilateral DNg100 turning is coded as `behaviour_category` = `turning`.
   - DN-alone null results are coded in the leg fields and `no_visible_effect`.
   - For co-activations, the speed difference versus DNg100 alone is a comparison between genotypes. It is written in `notes`, not in `effect_on_walking`.
   - Sibling records of one co-activation line describe the same outcome, so they get the same value. The two readers had split these by role (DNg100 vs partner DN), which is why each pair disagreed.
3. **DNb08 hind legs, `not_assessed`.** Pugliese Fig. 5d-e and the text report front and middle legs only.

## Uncertainties
- DNb08 surface: Methods state the ball only for DNg100 experiments. The Fig. 5d schematic shows no treadmill, and the text says movements were more reliable with the treadmill removed. I coded `air`, with medium confidence.
- DNb08 `line_specificity` = `clean` rests on the VNC image in Fig. 5c and the kit listing SS70620 as DNb08-only. The paper makes no explicit specificity statement and shows no brain image.
- Stepping frequencies not stated in the text were read approximately from figures. They are in `frequency_note` only; `frequency_hz` is filled only where the text gives a number (~11 Hz air-stepping).
- DNg16/DNg55/DNg75-alone outcomes (Extended Data Fig. 7e) rest on ball velocity only, with no leg tracking, so leg fields are `no` with medium confidence.
- Extended Data Fig. 7e DNg100(i) head-intact: n is not listed in Supplementary Table 1, and only velocity is shown (medium confidence).
- Supplementary Videos 1-7 were not downloaded. Nothing rests on them.

## Score sightings (PROTOCOL section 8)
- Pugliese DNb08 section and Fig. 5a,b,i: simulation rhythmicity results for **DNb08** (seen while reading the behavioural panels). Pugliese Methods (pruning screen): simulated DNg100/DNb08 activation producing oscillations, i.e. a driver call for **DNg100** and **DNb08**. Sapkal Discussion: describes the Pugliese model turning DNg100 input into rhythmic output (driver call for **DNg100**).
- Therefore `saw_simulation_score` = true on all DNb08 and DNg100 records, including the DNg100 sibling records of co-activation lines. It is false for the DNg16, DNg55, DNg75 and DNg97 records; no score for those types was seen. Sapkal contains connectome-path and influence analyses but no Pugliese-type activation scores. No simulation result was used for any decision.
- No GitHub or Zenodo pages were visited, and no other model sources were opened.
