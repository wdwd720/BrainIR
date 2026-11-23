# Session notes — a5-g01-A (label audit, run 5)

Assigned types: DNa01, DNa13, DNb05, DNg79, DNp01, DNp02, DNp03, DNp04, DNp06, DNp07, DNp10,
DNp11, DNp17, DNp47, DNxl022, MDN. Four assigned sources. 9 records written.

## What was read

- `sources/10_1101_2025_07_22_666129/` (Dahlhoff et al., bioRxiv): full `text.txt` (all 464 lines),
  Fig. 3 image, supplementary text (`supp/article.txt`, incl. the statistics tables).
- `sources/10_64898_2025_12_13_693955/` (Liessem et al., bioRxiv): full `text.txt` incl. Methods,
  supplemental figure legends, video legends; Fig. 1 and Fig. S1-1 images; Supplemental Table 1
  (reagents/genotypes) in `supp/article.txt`.
- `sources/10_1016_j_cell_2005_02_004/text.txt`: abstract only.
- `sources/10_1073_pnas_2618114123/text.txt`: abstract only.

## Sources I could not fully access

The task permitted fetching exactly two DOIs. Both attempts failed:

- **10.1016/j.cell.2005.02.004**: `doi.org` → `linkinghub.elsevier.com` (returns only a "Redirecting"
  stub); `cell.com` full-text URL → HTTP 403. Europe PMC REST: `isOpenAccess=N`, `inPMC=N`,
  only a subscription DOI link. Labelled from the abstract (`access = abstract_only`,
  `labeler_confidence = low`), one record for the giant fiber system.
- **10.1073/pnas.2618114123**: `doi.org` → `pnas.org` → HTTP 403 (also `pnas.org/doi/full/...`).
  Europe PMC REST: `isOpenAccess=N`, `inPMC=N`, no preprint link. The abstract describes MDN cell-body
  clustering and backward-walking initiation but quotes no activation experiment, so the source is
  marked `unreachable` rather than `no_qualifying_experiment` — the full text very likely contains
  MDN activation experiments that I could not see. Worth re-fetching in a session with access.

Supplemental Videos S1-S21 of 10.64898/2025.12.13.693955 were not downloaded into the room; leg
detail visible only in those videos could not be checked. Table images in both preprints are listed
as "not available; see the page images" — the information I needed from Supplemental Table 1 was
available as text in `supp/article.txt`, so I did not need the page images.

## Judgement calls

- **Landing responses are not rhythmic stepping.** In 10.64898/2025.12.13.693955 every DN activation
  produces a single leg extension (the landing response) in a tethered flying fly. Per PROTOCOL
  section 3 ("single movements ... `no`"), all three leg-rhythm fields are `no` and
  `effect_on_walking` is `not_assessed`. `behaviour_category` is `landing_or_extension`
  (`no_visible_effect` for DNb05).
- **DNp07 recorded twice.** Two independent driver lines (SS02276 = DNp07_1, SS02612 = DNp07_2) were
  tested in the same preparation (Fig. 1F and Fig. S1-1C), so two records per PROTOCOL section 1.
- **DNb05 negative result** is kept as a record (automated DeepLabCut tracking → `labeler_confidence`
  high). The text says the result was confirmed with several further DNb05 lines, "data not shown";
  those line IDs are included in `driver_lines` but only SS01051 is quantified in Fig. 1F.
- **DNg79 / SS81942**: the paper presents this as a DNg79 line and names no other type, but
  `driver_lines.csv` records the line as labelling "DNg31, DNg79". I coded `multi_dn` with DNg31 in
  `other_cell_types` and said so in the record notes.
- **DNp47 / SS39524**: Supplemental Table 1 shows this "SS" identifier is actually the Gen-1 GAL4
  line GMR70C09 (BDSC #39524), not a split-GAL4. Not in the kit → added to
  `out/proposed_driver_lines.csv`; `line_specificity` set to `unknown`.
- **DNp17 mapping** is `medium`, not `high`: SS02553 is `AMBIGUOUS` (DNp17 / DNut046) in
  `driver_lines.csv`, and the name "DNp17" itself maps to more than one MANC type in `synonyms.csv`
  (row `DNut046,DNp17,flywire,...,2,True`). I chose DNp17, the name the paper uses and the line's
  published annotation, and explained this in `mapping_basis`.
- **Two DNp17 records from one paper.** Fig. 2 (bulk SS02553 activation) and Fig. 3D-E (stochastic
  SPARC activation) are different experiments in different figures. The second is coded
  `labeler_confidence = low`: DNp17-expressing flies without DopaMeander did walk faster than
  no-expression controls, but the paper's own conclusion is that DNp17 "increases walking speed only
  slightly, if at all" and that the phenotype belongs to DopaMeander, a dopaminergic brain
  interneuron (not a DN, and not an assigned type, so no record was written for it).
- **MDN in 10.1101/2025.07.22.666129**: only silencing (Kir2.1) and patch-clamp recordings — no
  activation experiment — so no MDN record, per the instruction to write nothing when a source
  mentions a type but reports no such experiment.
- **Wing-only experiments not recorded**: activation of DNp07/DNp10 during flight changed wingbeat
  frequency (Fig. 2J-K) and activation of DNp10 in walking flies caused wing raising/flicking
  (Fig. S2-2G, Video S9). Neither reports what the legs do, so no records (PROTOCOL section 3,
  wing behaviours).
- **VPN activation** (LPLC4, LLPC2/3 etc., Fig. 3H-I of 10.64898/2025.12.13.693955) drives landing
  leg extensions, but these are visual projection neurons, not DN types on my list, so no records.

## Simulation results seen (AUDIT_NOTE: section 6 bullets 1-2 and the "score sighting" rule do not apply)

I read these parts in full, as the audit note allows, and no record rests on them.

- 10.64898/2025.12.13.693955, Fig. S4-1B and Methods "Leaky integrate-and-fire computational model":
  a connectome-constrained LIF simulation (FlyWire) predicting the spike rate of each landing DN
  when LPLC4 clusters are stimulated. This is the paper's own model, not a Pugliese-type connectome
  activation screen, but it is a simulated prediction for DNp07, DNp10, DNp47, DNg79 and DNb05, so
  `saw_simulation_score = true` on those five records.
- 10.1101/2025.07.22.666129, Fig. 6 and Fig. S5: linear-nonlinear models fitted to recorded MDN,
  DopaMeander and DNp17 activity, with model performance scores per locomotor component. Again the
  paper's own model; `saw_simulation_score = true` on both DNp17 records.
- No rhythm score, rank or driver/non-driver call from a Pugliese-type connectome activation screen
  or BrainIR output was seen in any assigned source, so `out/sightings.csv` was not written.

## Other output files

- `out/records.jsonl` — 9 records, one JSON object per line.
- `out/dispositions.csv`, `out/sources.csv`, `out/proposed_driver_lines.csv`.
- No `out/proposed_synonyms.csv` (no new name-to-type mapping found).
