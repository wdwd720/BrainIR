# Notes: session pass1-steering-r0-02 (pass1, steering and turning)

## Sources
- Assigned: 1 source, 10.7554/elife.102230 (Rayshubskiy et al., eLife 2025). Read the local copy: `text.txt` (Europe PMC XML full text), the PDF text (`supp/article.txt`, used for page numbers), Figure 8 image, all figure legends and the MDAR checklist (no data tables). There are no supplementary data tables or videos in the folder, and none were needed.
- No web access used. Not visited: GitHub, Zenodo or the code/data links in the paper's Data availability section.

## What qualified
- The only activation experiment in an adult fly is Fig. 8A-C: stochastic (hs-FLP) ReaChR expression in DNa02 via the split-GAL4 SS00730. Flies were intact (no dissection), tethered and walking on a spherical treadmill, with symmetric 617 nm light from above.
  - Record 0001: unilateral expression, so turning is coded as ipsilateral rotational bias (effect_on_walking = `turns`, legs `not_assessed` because flies were already walking and no leg tracking was done). n = 16.
  - Record 0002: bilateral expression, n = 17, written as a separate record because its outcome differs. **Uncertain coding:** I coded it `no_visible_effect` / `none` because the paper says light-evoked forward-velocity changes were "indistinguishable" across unilateral, bilateral and no-expression flies (attributed to visual startle). The authors also say they could not use this dataset to judge the effect of DNa02 activation on forward velocity. For that reason `labeler_confidence` = `low`. An adjudicator may prefer `not_assessed`.
- Not records: whole-cell recordings (Figs 1-6), CsChrimson in olfactory or thermosensory neurons (fictive odor or heat, which are sensory and not DN activation; Fig. 5), P2X2 in PEN1 neurons (Fig. 4, not DNs), GtACR1 silencing of DNa01/DNa02 (Fig. 8D-H) and connectome analyses (Fig. 7).

## Mapping
- DNa02 is a MANC type in `type_list.csv`. SS00730 → DNa02 is already in `driver_lines.csv`, so no new mappings were proposed.
- Line specificity is `minor_offtarget`: the Fig. 8-figure supplement 2 legend says SS00730 drives "off-target expression in specific optic lobe and VNC cell types".

## Leads for other sessions (cited here, not used as evidence)
The Discussion cites activation results from other papers. These are not recorded here because the records must rest on that paper's own experiments:
- Cande et al. 2018 (10.7554/eLife.34275): DNa01/DNa02 bilateral activation increases locomotion.
- Braun et al. 2024 (10.1038/s41586-024-07523-9): bilateral DNa01/DNa02 activation turning; DNb02.
- Yang et al. 2024 (10.1016/j.cell.2024.08.033): unilateral DNa02; DNg13, DNb05, DNb06.
- Feng et al. 2024 (bioRxiv 10.1101/2024.06.27.601106): DNa03, DNa11, DNae003, DNae014.
- Westeinde et al. 2024: DNa03.

## Simulation scores
None seen. No sightings file was written.
