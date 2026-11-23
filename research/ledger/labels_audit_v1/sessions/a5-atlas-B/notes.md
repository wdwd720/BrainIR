# Session a5-atlas-B — audit pass — notes

## Scope and what was read
- Assigned source: Cande et al. 2018, eLife, doi 10.7554/elife.34275 (local copy only; no web access used, no other sources searched).
- Read: `PROTOCOL.md`, `AUDIT_NOTE.md` (governs where it differs), `record_schema.json`, `atlas_line_ids.csv`, `assigned_sources.csv`, `meta.json`,
  full `text.txt`, all 11 figure images (Fig. 1–6 and the 5 figure supplements), and all 43 page images of
  Figure 2—source data 1 (Figure S5, image-only PDF; the extracted `.txt` holds only the caption).
- Not available: the 22 videos (not downloaded; listed as skipped in `meta.json`). No coding depended on them.
- No model, simulation, connectome score, rank or driver call appears anywhere in the source (a grep for
  simulation/connectome terms found nothing). `saw_simulation_score` = false on every record; no `sightings.csv` needed.

## Line coverage
- `atlas_line_ids.csv` lists 120 lines. Figure S5 shows 119 line panels, and all 119 IDs are on the list. The 120th listed line,
  SS02635, appears only in main-text Fig. 2A–C, legend and Videos 6–7; it has no Figure S5 panel. I found no line IDs outside the
  list. Lines named in text/figures beyond S5: SS02635, SS01602 (Fig. 2), SS01540, SS02542, SS01049 (Fig. 4, Videos 9–11),
  SS02542 (Fig. 5C), SS01052/SS01059 (Fig. 6A, as `JRC_SS01052`, `JRC_SS01059`). All are already on the list.
- The paper screened 130 lines. The text says 119 of 130 had a significant region and Fig. 4A gives 13 lines with 0 regions
  (86+22+9+1+1 = 119 with regions). The no-phenotype lines are **not identified by ID** anywhere in the room, so they cannot be
  coded. I wrote no "no visible effect" records because I have no line IDs for them. A separate session could get these IDs
  from the Dryad data (doi 10.5061/dryad.fr89c0c) or from the Namiki et al. 2018 collection.
- All tests are on intact, freely moving males in a 3 cm flat arena. There are no headless or tethered preparations, so each line
  has exactly one record (120 records in total).

## How figure-only records were coded (most records)
- For nearly every line, the only per-line evidence is the Figure S5 panel. It shows the significant behaviour-space region(s)
  as an inset outline, with density and time traces. I placed each inset on the human-curated map of Fig. 1C: anterior grooming
  is at the top, anterior movements on the left (the text calls these "anterior-directed foreleg movements"), still/slow at the
  upper right, wings & abdomen in the center, and locomotion along the bottom (slow at left, fast at right).
- Locomotion region → `forward_walking`, all three legs `yes` (convention: increased locomotion without leg tracking). Confidence
  is `medium` at most; it is `low` when the region is tiny, weak (experimental not clearly above control) or near a region
  boundary. The source does not give walking direction. `forward_walking` is the closest category, and each record says so.
- Anterior-movements region → `other`, legs `unclear`. The kind of foreleg movement (reaching, tapping, twitch) and whether it
  repeats is not stated per line.
- Anterior-grooming region → `anterior_grooming`, front `yes` by the grooming convention, mid/hind `unclear`. Confidence is
  `low` because the top of the map also holds other anterior movements (e.g. proboscis extension). The exception is SS02635,
  where the text says "groomed their heads" (`medium`). Even there, the text does not name the grooming legs.
- Central wings & abdomen region → `other`, legs `not_assessed` (convention for wing/abdomen behaviours when the legs are not
  described).
- Still/slow region → `halting`, legs `no`, `stops` (SS01554; SS02542 from text). SS01540 is coded `forward_walking` with
  secondary `halting`: the text describes repeated running then pausing.
- Regions that are tiny, split, or sit on a boundary between map areas → `other`, legs `unclear`, `low`: SS01053, SS01063,
  SS01073, SS01541, SS01567, SS01570, SS01575, SS01587, SS01590, SS02275, SS02396; also the large regions that span two areas,
  SS01064, SS01553, SS02534.
- Overall counts: 75 `forward_walking` (legs yes), 39 `other`, 4 `anterior_grooming`, 2 `halting`.
- The inset-to-map placement is my reading of small thumbnails. It is the main source of uncertainty in this audit, and an
  adjudicator should check boundary cases against the Dryad data or the videos.
- Quotes for figure records hold the panel's visible words (line ID with any intensity label, axis titles), and every such
  record's `notes` starts with `figure:`. The five text quotes (SS01049, SS01540, SS01602, SS02542, SS02635) were checked
  character for character against `text.txt`. I chose substrings that do not include DN type names.

## Blinding / line specificity
- Following the task, `name_in_paper` = the line ID, `manc_type` = UNMAPPED, `mapping_confidence` = low, and
  `mapping_basis` = "atlas line; type assigned later by script".
- The source cannot be read without seeing DN type labels: Figure S5 panel headers and some legends print them. I did not
  transcribe any of them into the records and did not use them to choose an outcome.
- For 11 lines, the panel header or legend names **two** DN types: SS01068, SS01549, SS01552, SS01569, SS01570, SS01572,
  SS01576, SS02379, SS02384, SS02534 (listed under the same two-type header as SS02379) and SS02635. These are coded
  `line_specificity` = `multi_dn`, with `other_cell_types` saying that a second type is named but not transcribed. Protocol
  section 1 asks for one record per DN type for such lines. Because this session codes by line ID only, the mapping script
  should split these 11 records by type.
- All other lines have `line_specificity` = `unknown`. The paper says only that lines had "little, or no, extraneous
  expression".

## Other details
- Stimulation: the initial screen used ~5 mW/cm² (Methods: 4.5 mW/cm²) with 0.2 mM retinal. Panels labelled "9 mW/cM²" are
  the re-screen at 9 mW/cm² with 0.4 mM retinal (the SS01066 panel is printed "9wM/cM²"). The paper does not show both
  intensities per line in S5, so there is one record per line.
- n_flies = 6 retinal-fed experimental males per line (plus 6 no-retinal controls), 30 trials each.
- `expression` = unknown: split-GAL4, and bilateral/unilateral is not stated.
