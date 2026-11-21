# Coding protocol (labeler kit v3: hemilineage activation)

You are coding published experiments in which a **hemilineage** of the *Drosophila* ventral nerve cord (VNC) was switched on
(activated) in adult flies, and the movements that followed were described. A hemilineage is the set of neurons born from one
neuroblast in one of its two branches (A or B), e.g. "hemilineage 9A". You code what the source reports, in a fixed vocabulary.
Nothing here asks you to judge whether a result is plausible.

## 1. What counts as a record

One record = one experiment: (source, hemilineage as the source names it, driver or clone method, preparation, effector). Code
only experiments **the source itself performed and reports**: an outcome the source cites or restates from another study (for
example in its introduction or discussion) gives no record. Code an experiment when **neurons of a named hemilineage (or of a named
set of hemilineages) were activated** (thermogenetic, e.g.
TrpA1 or dTrpA1 with heat; optogenetic, e.g. CsChrimson with light; or another activation method) **in adult flies** and the
source reports what the flies did (or that they did nothing visible). Write a record also when the source says activation had no
visible effect. Silencing, ablation, anatomy-only or larval experiments are not records. A screen of many lines gives one record
per line tested on a hemilineage, including lines with no effect.

**Record type** (`record_type`):
- `whole_two_sided`: the driver or method targets the whole hemilineage (all thoracic segments the source covers, both sides), as
  the source describes it;
- `clonal`: stochastic or clonal labelling (e.g. MARCM, flp-out clones) of a subset of a hemilineage;
- `one_sided`: only one side (or one segment) is activated, by design;
- `partial_or_mixed`: the source says the driver covers only part of the hemilineage, or also labels other cells that may matter.
When in doubt between `whole_two_sided` and `partial_or_mixed`, use what the source itself says about the driver's coverage, quote
it in `coverage_notes`, and choose `partial_or_mixed` only if the source says so.

**Preparation** (`preparation`): `decapitated` (head removed: headless flies), `intact`, or `other` (say what in
`preparation_detail`, e.g. "tethered", "legs removed", "wings removed").

## 2. The dimensions (code every one, for the activated flies of the record)

| field | dimension | `yes` when the source reports, during activation |
|---|---|---|
| d1 | any visible movement | any movement of any body part |
| d2 | front legs move | movement of one or both front legs |
| d3 | middle legs move | movement of one or both middle legs |
| d4 | hind legs move | movement of one or both hind legs |
| d5 | legs flex or the body lowers, held | a sustained (not repeated) flexion of legs, or the body lowered and held |
| d6 | legs extend or the body rises, held | a sustained extension of legs, or the body raised and held |
| d7 | repeated leg movement without coordination | rhythmic or repeated leg movements that the source does not describe as coordinated walking |
| d8 | coordinated walking | walking or coordinated stepping (in headless flies too) |
| d9 | grooming-like leg rubbing | leg rubbing or grooming-like leg movements |
| d10 | jump or takeoff | a jump, takeoff or escape jump |
| d11 | any wing movement | any movement of the wings |
| d12 | wings raised or opened, held | wings held raised, extended or opened |
| d13 | wing buzzing or flight-like beating | wing vibration, buzzing or flight-like wing beating |
| d14 | haltere movement | haltere movement |
| d15 | abdomen movement | abdominal movement (bending, pumping, curling) |

**Cell values:** `yes` = the source reports this in activated flies (any penetrance; give the penetrance in `penetrance` when the
source gives one). `no` = the source assessed that body part or behaviour and reports no such effect, including "no phenotype" or
"no visible effect" statements that cover it. `unclear` = the source says something about it that does not decide (e.g. "some
twitching" without saying which legs, for d2-d4). `not_assessed` = the source does not say.

**Conventions.**
- Movement of a body part counts for d2-d4, d11, d14, d15 whatever kind it is (held, rhythmic, twitching). "The legs" or "all
  legs" counts for d2, d3 and d4. "Leg movements" without saying which legs: d1 `yes`, d2-d4 `unclear`.
- d5 / d6 are for **held** postures (sustained flexion/extension, the body lowered/raised and kept). A repeated flex-extend cycle is
  d7 or d8, not d5/d6.
- d7 vs d8: coordinated stepping or walking (including "walking-like" in headless flies) is d8; repeated, rhythmic or alternating
  leg movements that the source does not call coordinated walking are d7. If the source reports both, code both `yes`.
- d1 is `yes` if any of d2-d15 is `yes`. d1 is `no` only if the source says the activated flies showed no movement (or "no
  phenotype") for the preparation.
- Code what was observed **during** activation (not after it ended); if the source reports only an after-effect, put it in
  `other_observation` and code the dimensions from what it says about the activation period.
- Use the source's own words. Video stills, figure panels and legends count as the source. Do not infer a movement that the source
  does not describe.

## 3. Fields (machine schema: `record_schema.json`)

`record_id`, `session`, `doi`, `hemilineage_as_named` (exactly as printed, e.g. "9A", "09A", "20A/22A", "lineage 9 A"),
`hemilineages_listed` (the names from `hemilineage_names.csv` that the record covers, separated by `;`; empty if none fits),
`driver` (line name, clone method, or "" if none given), `record_type`, `preparation`, `preparation_detail`, `effector`
(e.g. "UAS-dTrpA1, 30 C" or "UAS-CsChrimson, red light"), `penetrance` (as given, or ""), `coverage_notes` (what the source says
the driver covers or misses), `d1` ... `d15`, `locator` (figure, table, video, section and page as precisely as possible), `quote`
(verbatim, at most 25 words, supporting the most important coded cells), `other_observation` (free text, optional),
`saw_model_prediction` (true/false), `notes`.

## 4. Sources and access

Your assigned sources are already downloaded into `sources/<slug>/`: `text.txt` (full text with figure and table legends),
`figures/` (figure images), `supp/` (supplementary tables as text or CSV), `pages/` (page images of PDFs), `videos/` (frame
montages of supplementary videos: each `<video>_montage_<k>.png` shows frames in time order, left to right and top to bottom; the
time of each frame is in `<video>_frames.txt` and the video's legend in `<video>_legend.txt`), `meta.json`. Read the text, then figures, legends, tables and video montages as
needed. Most sessions have no web tools: if something you need is missing, say so in `out/notes.md` and in the disposition.

## 5. Things you must not do

- Do not open, search for or read any computational model, network simulation, connectome-simulation result or prediction of what
  activating a neuron population does. Do not visit GitHub, Zenodo or any code host. Do not open Pugliese et al. 2026 (Nature,
  doi 10.1038/s41586-026-11195-y; bioRxiv 10.1101/2025.09.12.675944) or Sapkal et al. 2026 (bioRxiv 10.64898/2026.04.29.721658).
- **Sighting.** A sighting is seeing a network-simulation prediction of what activating a hemilineage does (a description of
  connectivity is not a sighting). If you see one by accident, stop reading that part, set
  `saw_model_prediction` = `true` on every record of that hemilineage you write, and add a row to `out/sightings.csv` (header
  `doi,locator,what_was_seen,hemilineages_as_printed`).
- Do not use your own memory of what a hemilineage does as evidence, and do not let it guide what you record. Every record must
  rest on a source you opened in this session, with a quote and a locator.
- Write files only inside `out/` in this room.

## 6. Session contract (when you finish)

- `out/records.jsonl`: one valid JSON object per line (append after each hemilineage, so nothing is lost if the session stops).
- `out/dispositions.csv` (header `doi,disposition,n_records,reason`): one row for EVERY assigned source: `records`,
  `no_qualifying_experiment` or `unreachable` (say why).
- `out/coverage.csv` (header `doi,hemilineage_as_named,n_records,status`): one row per hemilineage in your scope that the source
  mentions in an activation experiment (`coded`) or that you looked for and did not find (`not_in_source`).
- `out/notes.md`: what you read, what was missing or uncertain, how you handled hard cases.
There is no time limit: finish every hemilineage in your scope for every assigned source.
