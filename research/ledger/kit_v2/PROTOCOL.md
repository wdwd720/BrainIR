# Labeling protocol (labeler kit v2: sections 1-7 unchanged from v1; section 8 adds the v2 clarifications)

You are curating published experiments on *Drosophila* descending neurons (DNs). The goal is a complete, honest table
of what happens to the **legs** when a DN type is switched on in a real adult fly. You work only with the files in this
room and the public web. You never see, look for or use any computational model, simulation or prediction about DNs.

## 1. What counts as a record

A record is **one experiment**: one DN type, or one driver line that labels DNs, switched on in an **adult fly**
(optogenetically, e.g. CsChrimson, ReaChR, Chrimson88; or thermogenetically, e.g. TrpA1, dTrpA1, Shibire is NOT
activation), with leg movement **observable** (video, tracking, ball, scoring by eye, a described posture, a quantified
locomotion measure). Silencing, imaging, anatomy-only and larval experiments are not records.

- One experiment per (source, figure/table/movie, driver line, preparation). The same line tested headless and intact
  is two records. Different effectors or stimulus intensities in one figure: one record, the strongest clearly reported
  condition, unless the outcome differs between conditions (then one record per condition).
- A line that labels more than one DN type gives **one record per DN type**, each marked as non-specific
  (`line_specificity` = `multi_dn`, the other types named in `other_cell_types`).
- A systematic screen (every tested line reported, including lines with no effect) produces a record for **every** DN
  line it tested, including "no visible effect" ones.

## 2. "Rhythmic leg movement"

Repeated cyclic movement of a leg, **three or more cycles**, that starts or clearly increases with stimulation relative to
controls or the pre-stimulus period. Fill `front_leg_rhythm`, `middle_leg_rhythm`, `hind_leg_rhythm` with `yes`, `no`,
`unclear` or `not_assessed`.

## 3. Conventions (how to code a kind of observation)

- **Walking, forward or backward:** `yes` for all three leg pairs.
- **"Increased locomotion" scored without leg tracking:** `yes` for all pairs, `labeler_confidence` at most `medium`.
- **Grooming:** `yes` only for the legs doing the rubbing or sweeping. The other legs are `no` if the fly is described as
  standing still, otherwise `unclear`.
- **Single movements** (jump, takeoff, leg extension, posture change, reaching): `no`.
- **Turning or a speed change in a fly that was already walking:** record it under `effect_on_walking`. The leg-rhythm
  fields are `not_assessed` unless standing flies were also stimulated.
- **Stopping or freezing:** `no` for every pair observed, and `effect_on_walking` = `stops` (or `behaviour_category` =
  `halting`).
- **Wing, flight, song or abdomen behaviours:** legs `not_assessed` unless the legs are described.
- **"No visible effect" in a systematic screen:** `no` for all pairs; `labeler_confidence` set by how carefully the screen
  scored behaviour (automated leg tracking: high; scoring by eye of coarse behaviours: medium; unclear method: low).
- **Headless flies:** `preparation` = `headless` and record the surface (`ball`, `air`, `slippery_surface`, `other`).
- **A line that labels more than one DN type:** one record per type, marked non-specific (see 1).

## 4. Fields (exact vocabularies; machine schema: `record_schema.json`)

| field | content |
|---|---|
| `record_id` | unique within your output, e.g. `p1-cande-0001` |
| `pass_id` | `pass1`, `pass2`, `search` or `adjudication` (given in your instructions) |
| `session` | your session name (given) |
| `doi` | the source DOI (`10....`); a URL only if no DOI exists |
| `title`, `year` | optional |
| `source_locator` | figure / table / supplementary file / movie, e.g. `Fig. 3b`, `Supplementary File 2, row 41` |
| `page` | optional |
| `quote` | a verbatim quote of at most 25 words that supports the record (from the text, a legend or a table cell) |
| `source_type` | `systematic_screen` (every tested line reported) or `targeted_study` |
| `access` | `full_text`, `abstract_only`, `supplement_only`, `figure_or_movie` |
| `name_in_paper` | the paper's name for this DN type, exactly as written (e.g. `DNa02`, `MDN`, `web`); only if the paper names no neuron for the line, the line name (the line ID always goes in `driver_lines`) |
| `manc_type` | the MANC type from `type_list.csv` / `synonyms.csv` / `driver_lines.csv`, or `UNMAPPED` |
| `mapping_confidence` | `high` (the paper's name is a MANC/Namiki type name or listed synonym that the kit maps to exactly one MANC type), `medium` (via a listed driver line, a strong anatomical description, or a name the kit maps to more than one MANC type: `synonyms.csv` column `ambiguous`, `driver_lines.csv` value `AMBIGUOUS` with `candidate_types`), `low` (guess) |
| `mapping_basis` | one sentence: how you mapped the name |
| `driver_lines` | list of line IDs (e.g. `["SS01540"]`); `[]` if none named |
| `effector`, `effector_kind` | e.g. `CsChrimson`, `optogenetic` / `thermogenetic` |
| `stimulation` | light colour/intensity/duration or temperature, as stated |
| `type_coverage` | how much of the type the line labels, if stated |
| `sex` | `male`, `female`, `mixed`, `unknown` |
| `preparation` | `intact_free`, `intact_tethered`, `headless`, `other` |
| `sensory_condition` | e.g. dark, on ball, in air, if stated |
| `headless_surface` | required when headless: `ball`, `air`, `slippery_surface`, `other` |
| `expression` | `bilateral`, `unilateral`, `stochastic`, `unknown` |
| `line_specificity` | `clean`, `minor_offtarget`, `multi_dn`, `unknown` |
| `other_cell_types` | other labelled cells named by the paper (required for `minor_offtarget` / `multi_dn`) |
| `front_leg_rhythm`, `middle_leg_rhythm`, `hind_leg_rhythm` | `yes`, `no`, `unclear`, `not_assessed` |
| `behaviour_category` | `forward_walking`, `backward_walking`, `turning`, `anterior_grooming`, `posterior_grooming`, `halting`, `takeoff_or_jump`, `landing_or_extension`, `wing_or_flight`, `posture`, `no_visible_effect`, `other` |
| `secondary_behaviours` | optional list from the same vocabulary |
| `frequency_hz` | stepping or leg-cycle frequency if reported (a number; for a range give the midpoint), else null |
| `frequency_note` | optional text, e.g. the reported range or how it was measured |
| `coordination_notes` | e.g. tripod, tetrapod, metachronal, one side only, if described |
| `effect_on_walking` | `stops`, `slows`, `speeds`, `turns`, `none`, `not_assessed` |
| `penetrance`, `n_flies` | as reported (penetrance free text; n_flies an integer, else null) |
| `n_flies_note` | optional text when the number of flies is a range or unclear |
| `labeler_confidence` | `high`, `medium`, `low` (abstract-only or paywalled: always `low`) |
| `saw_simulation_score` | `true` if you saw any model/simulation score or prediction for this DN type, else `false` |
| `notes` | optional |

Output one JSON object per line in `out/records.jsonl`. Use JSON `true`/`false`/`null`, not strings, and numbers (not
text) in numeric fields. Cross-field rules: `preparation` = `headless` needs `headless_surface`; `line_specificity` =
`minor_offtarget` or `multi_dn` needs `other_cell_types`; a name that maps to more than one MANC type (the kit lists all
candidates) gets `mapping_confidence` at most `medium`, the type the paper's anatomy supports, and an explanation in
`mapping_basis` (if you cannot decide, use `UNMAPPED`).

## 5. Sources and access

- Start from `sources_seed.csv`; search beyond it. Prefer full text (journal HTML, PMC, bioRxiv full text), supplementary
  tables and figure legends. If a source is paywalled and no open version exists, label from the abstract only:
  `access` = `abstract_only`, `labeler_confidence` = `low`.
- Every record needs a locator and a verbatim quote (at most 25 words). Never invent a quote. If you cannot find a
  supporting sentence, do not write the record.
- Name mapping: use `type_list.csv` (alphabetical MANC types with other names), `synonyms.csv` and `driver_lines.csv`.
  If you find a mapping that is not listed, use it, set `mapping_confidence` honestly and add a row to
  `out/proposed_synonyms.csv` (header `manc_type,name,kind,source_doi,locator`) or `out/proposed_driver_lines.csv`
  (header `line_id,manc_type,other_cells,source_doi,locator`); quote fields that contain commas.

## 6. Things you must not do

- Do not open, search for or read any computational model, simulation, connectome-simulation result, "rhythmicity score",
  "activation screen" in a model, or prediction about which DNs drive walking. Do not visit GitHub or Zenodo at all (they
  are blocked for this work). Unless your instructions say this is your dedicated source, do not open Pugliese et al. 2026
  (Nature, doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025.09.12.675944) or Sapkal et al. 2026 (bioRxiv
  10.64898/2026.04.29.721658).
- If you see a simulation score or model prediction for a DN type by accident, stop reading that part, set
  `saw_simulation_score` = `true` on every record of that type you write, and note it in `out/notes.md`.
- Do not use your own memory of what a neuron does as evidence, and do not let it guide which outcome you record. Every
  record must rest on a source you opened in this session, with a quote.
- Write files only inside `out/` in this room.

## 7. When you finish

Write `out/sources.csv` (a CSV file whose first line is the header `doi,title,year,source_type,access,n_records,notes`;
quote any field that contains a comma), `out/notes.md` (what you searched, what you
could not access, anything uncertain) and make sure `out/records.jsonl` has one valid JSON object per line.

## 8. Version 2 clarifications (they take precedence where they differ from sections 5-7)

- **Local sources.** Your assigned sources are already downloaded into `sources/<slug>/` in your room: `text.txt` (full text
  or abstract), `figures/` (figure images), `supp/` (supplementary tables as text or CSV), `pages/` (page images of PDFs),
  `meta.json` (DOI, title, what could be downloaded). Read the text, then the figures, legends and supplementary tables (you
  can open images). Most sessions have no web tools: if a source or a figure you need is missing, record that in
  `out/notes.md` and give the source the disposition `unreachable` with the reason; a separate session will try to fetch
  it. Only a session whose instructions say so may fetch a source from the web. Section 5's mention of `sources_seed.csv`
  does not apply in version 2.
- **Session contract.** Before you stop, write `out/dispositions.csv` (header `doi,disposition,n_records,reason`) with one
  row for EVERY source assigned to you: `records` (you wrote records from it), `no_qualifying_experiment` (you read it and
  it has no experiment of section 1) or `unreachable` (you could not read it; say why). There is no time limit: finish
  every assigned source.
- **Score sighting (replaces the meaning of section 6, second bullet).** A sighting is seeing a rhythm score, a rank or a
  driver / non-driver call for a DN type from the Pugliese-type connectome activation screen, wherever it is printed (the
  Pugliese papers, the simulation part of the 2026 Sapkal preprint, any BrainIR output). Another paper's own model does not
  count. If you see one: stop reading that part, set `saw_simulation_score` = `true` on every record of the affected types,
  and add a row to `out/sightings.csv` (header `doi,locator,what_was_seen,types_as_printed`; `what_was_seen` is
  `rhythm_score`, `rank` or `driver_call`).
- **Atlas lines.** Where your instructions say you code by driver-line ID, write `manc_type` as `UNMAPPED`,
  `mapping_confidence` as `low` and `mapping_basis` as `atlas line; type assigned later by script`; the type is filled in
  afterwards from a separate mapping.

