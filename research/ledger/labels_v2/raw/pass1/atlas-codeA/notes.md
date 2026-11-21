# Session atlas-codeA, pass1: notes

## Source and what was read
- One assigned source: Cande et al. 2018, eLife, doi 10.7554/elife.34275 (`sources/10_7554_elife_34275/`). No web access was used.
- Read: `text.txt` (full text incl. all figure legends), `meta.json`, figures 1, 1-S2, 2, 2-S1, 2-S2, 3, 4, 5, 6.
- Read all 43 page images of **Figure 2-source data 1** (Supplementary File 1, "Figure S5"). Its PDF text layer is empty, so the
  page images are the only per-line evidence.
- Not read or used: the 11 videos and the Dryad per-fly clips (not downloaded), and the transparent reporting form (it has no
  behavioural data). No model, simulation or prediction was opened or seen. **No score sightings**, so no `sightings.csv`.
  `saw_simulation_score` = false on all records.

## Coverage
- 120 records, one per line ID. This matches `atlas_line_ids.csv` exactly: 119 lines have a panel in Figure 2-source data 1,
  and SS02635 is shown only in Fig. 2A-C. I found no line IDs in the paper that are not in the list. Fig. 6A names
  JRC_SS01052 and JRC_SS01059, which are both already covered.
- **Only one preparation**: every test in this atlas was on intact, freely walking males in a 3 cm arena. There were no
  headless or tethered tests, so each line gets one record (`intact_free`).
- **Lines without a record**: the paper says 130 lines were screened. Fig. 4A shows 13 lines with zero activated regions, and
  "119 of the 130" lines had a significant phenotype. These no-effect lines are never identified by ID anywhere in the paper,
  its legends or its source data, so I could not write "no visible effect" records for them. As a result, this record set
  contains no `no_visible_effect` records. A later session with the Dryad data (doi 10.5061/dryad.fr89c0c), or with the
  Namiki et al. 2018 line list, might identify them.
- **One condition per line**: Figure 2-source data 1 shows one analysed condition per line. Panels labelled "(9 mW/cM2)" are
  the high-intensity re-screen with 0.4 mM retinal. All others are the initial screen at ~5 mW/cm2 (4.5 mW/cm2 in Methods)
  with 0.2 mM retinal. Each record codes the condition shown, which is the strongest reported condition per section 1.

## How behaviours were coded (applies to all figure-based records)
The paper gives no per-line text description. Its line-by-line evidence is the source-data figure. For each line, an inset
on the behaviour map marks the region(s) whose density rose significantly in the first 3 s of light, compared with the
recovery period and with no-retinal controls. I read each inset's position against the human-curated map in **Fig. 1C**.
Where a line had several regions, I used the dominant one (the largest density change, from the "Total Region Density"
panel):
- **Locomotion area** (bottom; slow on the left, fast on the right): `forward_walking`, legs yes/yes/yes. The paper does not
  give direction, so "forward" is an assumption; backward walking would also land in this area. There was no leg tracking,
  so `labeler_confidence` is at most medium (section 3, "increased locomotion"). `effect_on_walking` = `not_assessed`,
  because flies were in mixed behavioural states and the map cannot separate starting from speeding up or slowing.
- **Anterior movements area** (upper left: "anterior-directed foreleg movements", reaching/tapping): `other`, legs
  `unclear`. The figure cannot show whether the movements are rhythmic (e.g. tapping) or single reaches. Exception: SS01049,
  where the text says "reaching", is coded front leg = no.
- **Anterior grooming area** (top): `anterior_grooming`, front yes, middle and hind unclear.
- **Still/slow area** (upper right): `halting`, legs no, `stops`. Low confidence, because this area also contains slow
  movement.
- **Wings & abdomen area** (centre): `other`, legs `not_assessed`.
- **Boundary or tiny regions**: `other`, legs `unclear`, low confidence. Small lower-centre spots at the top edge of the
  locomotion area were read as slow locomotion with low confidence (SS01053, SS01567, SS01570, SS01597, SS02377, SS01552).
- **Quote**: for figure-based records, the quote is the panel's line-ID label, as allowed for figure evidence. The locator
  gives the page and panel. Five records rest on main-text or legend quotes: SS01049 (Fig. 4D), SS01540 (Fig. 4B),
  SS01602 (Fig. 2D-F), SS02542 (Fig. 4C) and SS02635 (Fig. 2A-C).
- Totals: 84 forward_walking, 29 other, 4 anterior_grooming, 3 halting. Confidence is medium for 50 records and low for 70.
- `n_flies` = 6, the retinal-fed experimental flies per line (with 6 no-retinal controls and 30 trials each). Sex is male:
  the paper says "we assayed only males". Expression is coded `unknown`.

## Blinding: what I saw and how I kept it out of the records
- I could not avoid seeing DN type names. The main text and legends name types for SS02635, SS01602, SS01540, SS02542 and
  SS01049. In the source data, each panel is headed by a cell-type code (e.g. "A1", "G2") above the line ID. I did **not**
  copy any type name into the records. Locators cite page and line-ID panel only, and quotes were chosen so they contain no
  type name. I did not use Fig. 6, which shows phenotypes averaged per type, to code any line. I used it only to check for
  line IDs. `manc_type` = UNMAPPED and `mapping_confidence` = low throughout, per section 8.
- `line_specificity` = `unknown` for all records. Naming the other types would break the blinding. However, 10 lines appear
  under a source-data heading that lists **two** cell types: SS02384, SS01572, SS01552, SS01570, SS01569, SS01576, SS01068,
  SS02379, SS02534 and SS01549. These are probably multi-DN lines, and their records say so in `notes`. When the
  type-mapping script runs, it should set `multi_dn` and split these into one record per type (section 1).

## Uncertainties worth adjudicating
- Every figure-based call depends on reading small insets on a 150 dpi page image. Boundary cases are flagged in each
  record's `notes`. The lines most worth checking against the Dryad videos are SS01541, SS01547, SS01569, SS01590,
  SS02396, SS02634, SS05107, SS05108, SS01063 and SS01066.
- SS01540 combines running and pausing. I coded legs yes for the running bouts, `effect_on_walking` = `stops`, and
  `halting` as a secondary behaviour.
- The red LED wavelength is given as 617 nm in the Fig. 1 legend and 627 nm in Methods. The light intensity is given as
  5 mW/cm2 in the text and 4.5 mW/cm2 in Methods.
