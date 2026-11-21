# adjudication-general-04 — notes

## What I read
- `PROTOCOL.md` (all sections, including section 8), `disagreements.csv`, `assigned_sources.csv`, the kit tables
  (`type_list.csv`, `synonyms.csv`, `driver_lines.csv`).
- Source 10.1016/j.cub.2026.07.076 (Palacios Castillo, Fajner et al., Curr Biol 2026): `text.txt` in full (Results, figure
  legends, STAR Methods, Key Resources Table, supplementary captions). Checked `fulltext.xml` for any extra content about the
  Fig. 6 line; it had none.
- I used no web access and no model or simulation material.

## What was missing
- The source folder has no figure images, no Data S1 and no Tables S1–S4 (meta.json: "0/0 figures, 0/0 supplementary
  files"). Fig. 6B/6D, Table S1 (cells labelled per line) and Table S4 (complete genotypes) are what would identify the
  "VL neurons" line used for optogenetics. A session that can fetch files should get Fig. 6 and Table S4.

## Decision (both siblings, field `line_specificity`)
- Decided `unknown`, not `multi_dn`. The text says only "Optogenetic activation of VL neurons ... (Figure 6B)". The paper
  describes VL-labelling lines of different specificity:
  - the earlier Namiki line(s) for "VL-like neurons" (Fig. 4B, ref 16; SS01545 is in the key resources table and the kit
    maps it to DNd02 only);
  - new lines that "target both VL1 and VL2" (Fig. 4C);
  - ASM1 lines that "always co-label neurons in the VL cluster".
- The available material doesn't show which of these was used in Fig. 6B, so I can't confirm that the line labels two DN
  types. If it is SS01545, the DNd03 sibling record (0002) would not apply at all.
- `manc_type` follows the sibling convention (k=1 → DNd02, k=2 → DNd03). `mapping_confidence` is `low` for the reason
  above.

## Other concerns
- The Fig. 6B readout is lunge rate (aggression), not leg movement. Walking speed (Fig. 6D) is described in the text only
  for OTA-SG08/SG10/SG40. So the leg fields are `not_assessed`, `behaviour_category` = `other`, and
  `labeler_confidence` = `low`. This experiment may not meet the section 1 requirement that leg movement be observable.
  I still wrote the records because the adjudication task asks for one per experiment; downstream curators may want to
  drop them.
- I added a proposed synonym row each for VL1/VL2 (the paper drops the "OA-" prefix).

## Score sightings
- None. I didn't create `sightings.csv`. `saw_simulation_score` = false on all records.
