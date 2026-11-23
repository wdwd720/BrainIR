# Session a5-atlas-A — pass `audit` — notes

## What I read
- `AUDIT_NOTE.md`, `PROTOCOL.md` (all sections), `TASK.md`, `record_schema.json`, `atlas_line_ids.csv` (120 lines), `assigned_sources.csv`.
- Assigned source: Cande et al. 2018, eLife, doi 10.7554/elife.34275 (`sources/10_7554_elife_34275/`). I read all of `text.txt`, plus Figs 1, 2-figsupp2, 3, 4, 5 and 6. I also viewed all 43 page images of Figure 2-source data 1 (Supplementary File 1 = "Figure S5", line-by-line analysis). Its text extraction is empty except for the legend, so the page images were the only usable form.
- No web access was used and no other sources were searched. All files were written only inside `out/`.

## Simulation scores
- This paper contains no connectome simulation, rhythm score, rank or driver call, and I saw none. `saw_simulation_score` = false on every record, and no `sightings.csv` was needed.

## Coverage
- All 120 lines in `atlas_line_ids.csv` have exactly one record.
- 119 lines come from Figure S5. SS02635 does not appear in S5; it is the worked example in Fig. 2A–C (head grooming), and its record is coded from the text and the Fig. 2 legend.
- I found no line IDs in the figures or source data beyond `atlas_line_ids.csv`. Fig. 6A names JRC_SS01052 and JRC_SS01059, which are both already in the list.
- The paper screened 130 lines and found phenotypes in 119 (text). It never names, by ID, the lines with no significant region (Fig. 4A plots 13 lines with 0 regions, but without IDs). I therefore could not write `no_visible_effect` records for them. A separate source (e.g. the Dryad video set, doi 10.5061/dryad.fr89c0c, not assigned here) would be needed.
- Preparation: every test in this atlas is an intact, freely moving male in a 3 cm arena (`intact_free`). There are no headless or tethered tests, so there is one record per line.
- Light intensity: lines whose S5 panel label carries "(9 mW/cM²)" were scored from the 9 mW/cm2, 0.4 mM retinal re-screen. All others were scored from the ~5 mW/cm2 (4.5 mW/cm2) initial screen. Each line appears once in S5, so there was no within-line intensity split.

## How I coded (and limits)
- Evidence per line is the S5 inset showing the significant region(s) on the behaviour map. I interpreted it against the human-curated map in Fig. 1C:
  - bottom = locomotion (slow at left, fast at right)
  - left = anterior foreleg movements
  - top = anterior grooming
  - upper right = still/slow
  - centre = wings & abdomen
- I used the density-vs-time traces and the experimental/control density maps as support.
- Coding rules:
  - Locomotion region: walking, all three leg pairs `yes` (PROTOCOL 3, "increased locomotion" without leg tracking). `labeler_confidence` is at most medium; it is low when the region is tiny, the effect is weak, or controls also rise. Walking direction is not distinguished by this assay; I used `forward_walking` as the category and say so in notes.
  - Slow-locomotion regions bordering the anterior-movements area: walking, low confidence, `effect_on_walking` = `not_assessed`.
  - Anterior grooming region: `anterior_grooming`, front `yes`, other legs `unclear`.
  - Anterior movements region: `other`, legs `unclear`, because the region mixes reaching (single movements) with foreleg tapping. The exception is SS01049, where the text says "anterior reaching", so front is `no`.
  - Still/slow region: `halting`, legs `no`, `stops` (SS02542, SS01554). SS01540 is a run-then-freeze sequence (text), coded as walking with secondary `halting`.
  - Wings & abdomen region, and tiny ambiguous regions: `other`, legs `unclear`.
- Quotes: figure-only evidence quotes the S5 panel label (line ID, plus intensity when printed), and notes start `figure:`. Five records (SS02542, SS01602, SS01540, SS01049, SS02635) quote the main text. I checked each of those character-for-character against `text.txt`.
- Blinding: the S5 panel group headers (and some main-text sentences) print DN type names next to line IDs. I did not use or record these. Locators give the page and the line-ID panel label only, and every record keeps `manc_type` = `UNMAPPED`, `mapping_confidence` = `low`, `mapping_basis` = "atlas line; type assigned later by script". I also did not use Fig. 6 (which is organised by DN type) to interpret individual lines.
- Specificity/expression: the atlas does not report per-line off-target expression, so it is `unknown`/`unknown` throughout. `n_flies` = 6 experimental flies per line (30 trials each).
- Uncertain records (low confidence, behaviour `other`/`unclear`): SS01541, SS02396, SS01575, SS01567, SS01063, SS01553, SS01570, SS01569, SS01608, SS02385, SS02257, SS01587, SS01588, and the anterior-movement lines. Region positions were read by eye from small insets, so a second reader may place boundary regions differently.
