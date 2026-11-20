# Labeling protocol (labeler kit v1)

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
| `name_in_paper` | the neuron or line name exactly as the paper uses it |
| `manc_type` | the MANC type from `type_list.csv` / `synonyms.csv` / `driver_lines.csv`, or `UNMAPPED` |
| `mapping_confidence` | `high` (paper names the MANC/Namiki type, or an unambiguous listed synonym), `medium` (via a listed driver line, a strong anatomical description, or a name that maps to more than one MANC type in the kit), `low` (guess) |
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
  `out/proposed_synonyms.csv` (`manc_type,name,kind,source_doi,locator`) or `out/proposed_driver_lines.csv`
  (`line_id,manc_type,other_cells,source_doi,locator`).

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

Write `out/sources.csv` (`doi,title,year,source_type,access,n_records,notes`), `out/notes.md` (what you searched, what you
could not access, anything uncertain) and make sure `out/records.jsonl` has one valid JSON object per line.
