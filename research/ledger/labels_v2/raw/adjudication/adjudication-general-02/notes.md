# Notes: adjudication-general-02 (pass `adjudication`)

## Scope
- 10 disputed experiments (15 disputed fields) from `disagreements.csv`, across 6 assigned sources, all read locally (`text.txt`, figures, `supp/`).
- I opened no web resources, models or simulations. Every decision rests on the local source text, legends, figures and the kit CSVs.
- Outputs: `records.jsonl` (10 records, `adjudication-general-02-0001`…`0010`), `decisions.csv` (15 rows), `dispositions.csv` (6 sources, all `records`), `sources.csv`, `proposed_driver_lines.csv` (SS77821→DNa11, SS84990→DNa03), `sightings.csv` (header only).

## Score sightings
- None. I saw no Pugliese-type rhythm score, rank or driver call. Some papers have their own models, which section 8 says are not sightings:
  - 10.1101/2025.07.22.666129: LN models
  - 10.64898/2025.12.13.693955: ShREC metric and LPLC4 cluster simulation
  - 10.1101/2024.06.27.601106: connectome tables
- `saw_simulation_score` = false on all records.

## Decisions where I went beyond both readings, or which are uncertain
- **DNp17 (exp 0018, 0019): manc_type = UNMAPPED, low.**
  - The kit maps the name DNp17 and the line SS02553 to two types, DNp17 and DNut046 (`driver_lines.csv` AMBIGUOUS; `synonyms.csv` ambiguous=True).
  - The kit's cross-references put the brain types FlyWire/hemibrain "DNp17" at DNut046, and the MANC type "DNp17" at brain DNge088. That hints at DNut046, but the paper's own anatomy (lower tectulum, haltere and neck neuropils) does not settle it.
  - So I applied the section 4 rule: if you cannot decide, UNMAPPED. A later pass with MANC morphology could probably resolve it.
  - Separately, the paper attributes the walking phenotype to DopaMeander (a non-DN), not DNp17.
- **DNa11 headless (exp 0012): all legs `unclear`.**
  - The readers had split front vs middle/hind inconsistently. The only evidence is one sentence plus the Supplementary Video 6 legend (8/8 turned, "much more slowly").
  - The video was not downloaded. The substrate isn't stated, so `headless_surface` = `other`.
- **DNa03-SS2 (exp 0014): minor_offtarget.**
  - Based on my reading of the Fig. S1f expression image (heavy optic-lobe and other labelling). The paper names none of these cells, so `other_cell_types` describes them by location.
- **DNp07_2 / SS02612 (exp r0-02-0002): unknown.**
  - The paper never describes this line's expression. The kit (Namiki 2018 supp. 3) notes about 2 background off-target types, so `clean` was not supported.
- **L320 (r0-03-0005):** front `no` (single movements in thrusts and alert stance), middle/hind `unclear` (not tracked; retreat observed but not quantified).
- **L320 DMD (r0-03-0007):** minor_offtarget. DMD spatial targeting restricts light, not expression, and the authors report spill-over activation.
- **DNg100 headless (r0-03-0011): effect_on_walking = speeds.**
  - From the Supplementary Video 5 legend.
  - Caveat: the white strobe illumination also activates CsChrimson (Discussion), so there is no true light-off baseline.

## Not accessible
- All supplementary videos/movies across sources (not downloaded by design). No figure needed for a decision was missing. No source is `unreachable`.
