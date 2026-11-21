# Session atlas-map: notes

## What was done
- I mapped all 120 line IDs in `atlas_line_ids.csv` to MANC types. The result is `out/atlas_line_map.csv`, with 120 rows.
- **Atlas source:** Cande et al. 2018, *eLife* 34275.
  - I read all 43 pages of "Figure 2-source data 1" (Supplementary File 1 = Figure S5, image-only PDF) and wrote down the type heading printed above each line ID. The atlas uses short Namiki names, e.g. `A1` = DNa01, `G25` = DNg25, `P20` = DNp20, and combined headings such as `D2 & D3`. The main text confirms the convention: SS01602 is called "DNg25" in one place and "G25" in another.
  - **Correction to the kit:** `driver_lines.csv` says this PDF prints "no DN type" for its lines. That is wrong: every panel has a type heading.
  - 119 of the 120 lines appear in Fig. S5. SS02635 is named only in the main text and the video/figure legends ("DNg07 and DNg08 (SS02635)").
  - I also checked the main text and legends (Fig. 4 legend: SS01540 = DNp09, SS02542 = DNb01, SS01049 = DNp10) and the Fig. 6B per-type line counts (N).
- **Namiki et al. 2018 (eLife 34272):** used through the kit's `driver_lines.csv` rows, which cite its Supplementary files 1, 3 and 5 and its key resources table.
- **2025 catalogue (Zung et al., eLife 107450):**
  - Its text (p.3–4) says that Namiki's DNb01, DNg05, DNg16 and DNp13 were each split into two types (DNb01/DNb09, DNg05/DNg126, DNg16/DNg69, DNp13/DNp62). It also says the Namiki line annotations were updated, adding some types and removing some.
  - Its Supplementary Table 5 is **not** in the room. I used it only through the kit rows that cite it.

## Mapping rules I applied
- Where the 2025 catalogue updates a line's annotation, I used the 2025 version as the current anatomy and named the atlas/Namiki label in `mapping_basis`. Confidence is then at most `medium`.
- When the kit marks a name as ambiguous (several candidate MANC types, from hemibrain/FlyWire/MaleCNS synonym conflicts), I chose the MANC type with the same name as the Namiki type and set `medium`.
- `high` means: the atlas label, Namiki and the 2025 catalogue all agree, and the name maps to exactly one MANC type.

## Points a reviewer should check
1. **Lines where 2025 removes a type the atlas lists.** In each case I kept only the 2025 type(s); reconsider if you prefer the union with the atlas label.
   - SS02635: atlas DNg07+DNg08 → 2025 DNg07 only
   - SS01549: atlas DNp07+DNp13 → 2025 DNp07 only
   - SS02534: atlas DNp02+DNp11 → 2025 DNp02 only
2. **Lines that 2025 re-types because of a split.**
   - SS01543: G16 → DNg69
   - SS02542: B1/DNb01 → DNb09. SS02383 (also labelled B1 in the atlas) stays DNb01.
3. **Lines where 2025 adds a type** (multi-DN lines):
   - SS01553: +DNp57
   - SS01565, SS02285, SS02538: +DNg82
   - SS02275: +DNg04
   - SS02395: +DNc01 (the atlas calls this line C2)
   - SS02617: +DNg12, marked "Probable" in 2025
   - SS05107: +DNg93
4. **Lines with no MANC type.** SS01602 (DNg25), SS01063 and SS01564 (DNg28): DNg25 and DNg28 are not in `type_list.csv` and have no synonyms there. `manc_types` is left empty, confidence `low`. I did not propose a synonym because nothing in the room links them to a MANC type.
5. **SS01067.** Fig. S5 p.20 prints it under the "G13" heading. Namiki and 2025 both say DNp03, and the Fig. 6B counts (G13 N=2, P3 N=5) only work if SS01067 is P3. I mapped it to DNp03 (`medium`) and treated the heading as a layout artifact.
6. **SS01588.** Namiki's key resources table says DNp26, but Namiki Supp. file 3, the 2025 catalogue and the atlas heading (G30) all say DNg30. I used DNg30 (`medium`).
7. **SS02379 and SS02609.** Namiki Supp. file 1 also lists them as example lines for DNg24 and DNp21 respectively. These types are not in Supp. file 3 or the 2025 annotation, so I did not include them.
8. **Typo in the atlas.** One movie legend calls SS01540 "G9"; the Fig. 4 legend and S5 say DNp09/P9. I used DNp09.

## Lines the atlas tested but never identifies
- The atlas text says 130 split-GAL4 lines were screened. Only 120 IDs appear anywhere in the atlas figures and tables I have (Fig. S5 + text + legends), so about 10 tested lines are not identified. They may be in the Dryad data package (doi 10.5061/dryad.fr89c0c), which is not in the room; I did not fetch it.
- Fig. 6B shows more lines per type than Fig. S5 for some types: G30 N=6 vs 5, P4 N=4 vs 3, P10 N=4 vs 3, P27 N=2 vs 1, A5&A7 N=2 vs 1, D2 N=2 vs 1. These are consistent with the unidentified lines.
- Fig. 6B also includes "pIP10", which the text calls a previously characterised sparse GAL4 driver (von Philipsborn et al. 2011). No line ID is given, so it has no row in the map. The text also mentions fruitless-GAL4, which is not a DN line.

## Blinding and compliance
- I did not open, search for or see any model, simulation, connectome activation screen, rhythm score, rank or driver call.
- I visited no websites; all work used files in the room. Nothing was written outside `out/`.
- Reading the atlas text and figures for line/type pairings unavoidably exposed some behaviour words in the same sentences, and the behaviour maps in Fig. S5 and Fig. 6 (whose panels are grouped under behaviour headings). I took **names only** from them. No behaviour, effect or category was recorded, and none was used to choose a mapping. The only Fig. 6 information used is the per-type line counts (N), to resolve SS01067.
- No behaviour records were written in this session. `dispositions.csv` gives the atlas `records` with 0 records as a deliberate flag; the reason field explains it.
