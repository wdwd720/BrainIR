# Session pass2-general-02 — independent second reading (pass2)

## What was done
- Read PROTOCOL.md (v2, incl. section 8), record_schema.json and the kit (type_list.csv, synonyms.csv, driver_lines.csv).
- Labelled all 114 rows of `experiments_to_label.csv` from the six local sources in `sources/` (text, figures, page
  images, supplementary tables and source data). No web access was used and none was needed.
- Output: 114 records in `out/records.jsonl` (`pass2-general-02-0001` … `-0114`), one per experiment row, in file order.
  `exp_id` copied unchanged; `sibling_index` / `n_siblings` not copied. All rows had `n_siblings` = 1.
- `not_found.csv`: empty (every experiment was located). `sightings.csv`: empty (no sighting).
- `dispositions.csv`: all 6 assigned sources = `records`.

## Score sightings / model content
- No Pugliese-type rhythm score, rank or driver call was seen. I did not open any Pugliese or Sapkal 2026 material.
- Two sources contain **their own** connectome analyses, which section 8 says do not count as sightings:
  Braun et al. 2024 (DN–DN network size/clusters; ED Figs. 4–9) and Sapkal et al. 2024 (connectome-constrained
  spiking model, Fig. 3a–h, ED Figs. 6b,c and 10). Labels rest only on the behavioural experiments.
  `saw_simulation_score` = false on all records.

## Coding decisions worth checking
- **Single movements = no rhythm**: takeoff (Dombrovski), landing leg extension (Ache), front-leg flexion/approach
  (Braun headless DNb02/aDN2), posture shifts. All leg fields `no`.
- **Already-walking flies**: Braun Fig. 2 analyses only trials with walking before stimulation. DNp09 there is coded as
  a speed change (legs `not_assessed`, `speeds`). MDN there is coded `yes` because backward walking is a new gait,
  not a speed change. aDN2 there is coded as anterior grooming plus a stop.
- **Ball-velocity-only walking** (Braun, Sapkal arena, Feng Fly Bowl): coded `yes` for all pairs by the walking
  convention, with confidence `medium`. Records with real 3D/2D leg tracking (Feng Fig. 1/Supp. Fig. 5; Sapkal Fig. 1g
  and Fig. 4e–j) are `high`.
- **Turning from rest** (Braun DNa01, DNa02, DNb02 intact; Sapkal P9+FG pivoting): legs `unclear`, because the
  stepping pattern is not described.
- **Abdomen/ovipositor/courtship behaviours** (oviDN, Mute, DNg14, plP10): legs `not_assessed`.
- **Braun "excluded" lines** (Web, DNp24, DNg30, DNb01, DNg16): these were tested but excluded for having no clear
  headless or known intact phenotype, and no data are shown. I coded them `no_visible_effect` with confidence `low`.
  The only supporting quote is the Methods exclusion sentence.
- **Feng Fig. 7 control trials**: only hindlegs were tracked. Front and mid legs are `yes` by the walking convention;
  confidence `medium`.
- **Co-activations (Sapkal Fig. 2, Fig. 4e–j)**: one record per DN in the combined genotype, as the rows require. When
  the partner is a non-DN (BRK = ascending neurons; BPN = brain neurons), I used `minor_offtarget` only to name the
  partner. It is a deliberate co-activation, not real off-target expression. The outcomes mostly reflect the partner
  neuron (e.g. FG/BB records under MDN co-activation show backward walking).

## Mapping issues / uncertainty
- **BB (Bluebell)**: the kit lists BB for both DNg60 and DNxn073. The paper's FlyWire table gives Bluebell's FlyWire
  type as "DNg60", and the kit lists that as the FlyWire name of **DNxn073** (MANC DNg60's FlyWire name is DNge096).
  So I chose DNxn073 at medium. Please adjudicate.
- **FG (Foxglove)**: UNMAPPED. It is not in the kit, and the paper gives only FlyWire type CB0890, with no MANC type.
- **Sapkal screen lines SS31369, SS31366, SS44893, SS31341**: the kit says AMBIGUOUS (DNg60;DNxn073) and the paper
  names no neuron, so UNMAPPED. SS31388 is absent from the kit, so UNMAPPED.
- **oDN1 / BDN2**: kit synonyms give DNg97 / DNg100. The paper's own MANC table (Supplementary Table 3, FANC_MANC
  sheet) instead lists DNxl054 / DNxl058, which are not in the kit's type list. I used the kit mapping and noted the
  discrepancy.
- **DNp09 / P9, DNa01, DNb01**: each name is also a hemibrain synonym of another MANC type (DNp71, DNxl022, DNb09), so
  I set medium and kept the Namiki type.
- **SS02612**: Dombrovski calls it DNp05, but driver_lines.csv lists it as DNp07. I kept DNp05 at medium.
- **plP10**: a spelling variant of MANC type pIP10, mapped at medium. Proposed as a synonym in `proposed_synonyms.csv`.
- **SS01549 (Ache)**: labels DNp07 strongly and DNp13 weakly (Supp. Fig. 1b). It was given as two separate rows, so
  there are two multi_dn records.
- **Sex** is `unknown` for Sapkal decapitated-fly experiments (not stated). Sapkal tethered ball experiments used
  males; free arena used females.
- **Dombrovski** takeoff percentages were read off ED Fig. 1e bars and are approximate. N per line comes from
  Supplementary Table 1.
- **Sapkal ED Fig. 6e**: the colours for P9 vs BDN2 are hard to read. P9 is coded from the text (no forward turning).
  BDN2 is coded from the text with confidence low.

## Not accessible
- Supplementary videos were not downloaded for any source. Nothing needed for these rows was missing otherwise.

## Possible extra experiments (not assigned, not recorded)
- Ache et al. 2019 screened 133 DN split lines in tethered flight but reports only the two positives, so there are no
  per-line results to record.
- Sapkal 2024 ED Fig. 1a/d also shows halting for lines SS40926, SS44892, SS44898, SS44896, R37F06, R36G02 and
  VT012408, plus BRK subset lines. These are not in my row list; BRK is ascending, not a DN.
