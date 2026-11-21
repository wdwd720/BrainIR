# Notes: adjudication-general-03 (pass `adjudication`)

## Scope and what was read
- Assigned source: Cande et al. 2018, eLife, doi 10.7554/elife.34275 (local copy `sources/10_7554_elife_34275/`). Disposition: `records`, with 69 records.
- I read the whole of `text.txt` (Results, legends, Discussion, Methods), plus the images of Fig. 1, Fig. 2 and Fig. 6. I also read every Figure 2-source data 1 (Fig. S5) page that holds a disputed panel: pp. 1-3, 6-8, 10, 13-14, 16-19, 22-31, 34-40, 42-43.
- Fig. S5 is image-only. Its text layer has only the legend. Each panel gives only the line ID, a panel header (the DN type abbreviation, e.g. `A7`, `P2 & P11`) and an inset showing the significant region on the behaviour map. Each panel was read visually against the map key in Fig. 1C.
- No web access was used and none was needed. The videos were not downloaded (the Dryad clips were not available) and were not needed for any decision.
- **Sightings: none.** I opened no model or simulation material, and none appears in this source. `sightings.csv` has its header only, and `saw_simulation_score` = false on all records.

## Outputs
- `records.jsonl`: 69 records, one per distinct exp_id in `disagreements.csv`, with ids `adjudication-general-03-0001` to `-0069` in file order. `exp_id` is copied unchanged.
- `decisions.csv`: 98 rows, one per disputed field.
- `dispositions.csv`, `sources.csv`, `sightings.csv` (header only).

## Conventions I applied (all decisions follow from these)
1. **Locomotion in the fast part of the map.** If the significant region falls in the lower-right part of the map, I code walking for all three legs (`yes`, PROTOCOL s3) and set `effect_on_walking` = `speeds`. The basis is the Fig. 1C legend, which says the bottom of the map is ordered by running speed from left to right. This decides most of the `speeds` vs `not_assessed` disputes. It is a judgement call: flies were stimulated in whatever state they were in, and the paper does not split out flies that were already walking. I chose `speeds` because the measured effect is a shift into the fast-running part of the map. Confidence is `medium` because there is no leg tracking. It drops to `low` where the effect over control is weak (SS01080, SS02553, SS02554, SS01579) or where the line-level region conflicts with the paper's type-level category in Fig. 6 (SS01073 = G2 wing/abdomen; SS05098 = G3 slow locomotion).
2. **Large diagonal band covering the anterior foreleg-movement area and the slow-locomotion area** (SS01057, SS01064, SS01588, SS02534): all legs `unclear`. The paper reads this map area both ways: Fig. 6 calls the P26 region of this shape Broad Locomotion, but files G26 under Anterior Movements. So reaching cannot be separated from walking.
3. **Tiny, noisy or ambiguous regions** (SS01053, SS01063, SS01564): legs `unclear`. For SS01063 I chose `effect_on_walking` = `not_assessed` over `stops`, because no stopping is reported and the region is not clearly in the still/slow area.
4. **DNd02 (SS01575), still/slow area:** legs `unclear`, not `not_assessed`. The legs are visible in the video, but the paper's "slow movements" does not settle slow stepping versus stillness.
5. **Wing/abdomen behaviours with legs not described** (SS02257 DNp27; SS01587 DNp29 abdomen grooming): legs `not_assessed` (PROTOCOL s3). The paper does not say which legs groom the abdomen, so `no` was rejected. `stops` was rejected for DNp29 because grooming, not freezing, is reported.
6. **`line_specificity`.** I chose `multi_dn` where the paper itself names two types for the line: SS01549 header "P7 & P13", SS02534 header "P2 & P11", and SS02635 "targeting DNg07 and DNg08".

## Undisputed fields I had to fill (my values, flagged for review)
- `name_in_paper` uses the paper's own name for the type, e.g. `A7` from the Fig. S5 panel header, or `DNg25` and `DNg07` from the text. This follows PROTOCOL s4, which allows a line ID only when the paper names no neuron. The `disagreements.csv` rows list the line ID instead. For the kit-derived second types that the paper never names (SS01565/SS02285 DNg82, SS02275 DNg04, SS02395 DNc01), `name_in_paper` is the line ID.
- `manc_type` follows the type encoded in each exp_id. `mapping_confidence` is `medium` throughout: the panel abbreviations are shortened Namiki names, the types come via a listed driver line, and many names are flagged AMBIGUOUS in the kit. The three UNMAPPED rows get `low` (DNg28 for SS01063 and SS01564; DNg25 for SS01602; none of these are in type_list.csv).
- `line_specificity` is `unknown` for single-type lines. The paper only says the lines have "little, or no, extraneous expression".
- Single-type lines whose region is in fast locomotion are coded `forward_walking`. The map does not distinguish backward walking.
- SS02635 (head grooming): front legs `yes` as the rubbing legs. The paper does not explicitly name the legs, so this is a convention-based coding. Middle and hind legs are `unclear`.

## Uncertainties and kit issues to review
- **SS01543:** the paper's panel header is `G16`, and DNg16 is itself a MANC type. `driver_lines.csv` gives DNg16 in two sources but DNg69 in eLife.107450 Supp. Table 5. The exp_id says DNg69; I kept it with `mapping_confidence` `low`. This needs a human mapping check.
- **SS01588:** the kit lists DNg30 (Namiki Supplementary file 3) but DNp26 in the Namiki key resources table. Cande's panel header `G30` supports DNg30.
- **Multi-type lines with `n_siblings` = 1 in `disagreements.csv`.** SS01565, SS02275, SS02285, SS02395, SS01572, SS02379 and SS02384 each have two exp_ids, but every row says `n_siblings` = 1. I coded each record `multi_dn` with the sibling type in `other_cell_types`.
  - For SS01572, SS02379 and SS02384, the paper's panel header names both types.
  - For SS01565, SS02275, SS02285 and SS02395, the paper labels only one type (G1 or C2). The second type comes from the kit (eLife.107450), not from this paper.
- **Line-level vs type-level disagreement.** Several lines show a fast-locomotion region while Fig. 6 files their type under another category: SS01047 P6, SS01061 G26, SS01077 G30, SS01566 G11, SS01596 P3, SS02612 P7, SS01565/SS02275/SS02285 G1, SS01073 G2. Fig. 6 shows multi-line averages. I coded each record from its own Fig. S5 panel and noted the conflict in the record.
- **Reading accuracy.** Region positions were read by eye from 150-dpi page images of small insets. Where the position was borderline I cross-checked against the experimental 0-3 s and 3-6 s density maps in the same panel.
- No proposed synonyms or driver lines: no unlisted mapping was found.
