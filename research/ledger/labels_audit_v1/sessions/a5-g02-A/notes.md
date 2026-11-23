# Session a5-g02-A — audit notes (run 5)

Assigned types: DNa01, DNa02, DNb05, DNb06, DNg13, DNg14, DNg15, DNg16, DNp05, DNp09,
DNp11, DNp18, DNp28, DNp29, DNp71, DNxl022, MDN.
Assigned sources: 2 (both reachable as full text).

## What I read

- `sources/10_1016_j_cell_2024_08_033/text.txt` in full (main text, STAR Methods, all
  supplementary figure legends S1-S7) plus the figure legends inline. Table S1 is a
  statistics table only (p-values), not consulted for behaviour.
- `sources/10_1038_s41467_025_64907_9/text.txt` in full, plus `supp/41467_2025_64907_MOESM1_ESM.txt`
  (Fig. S4 legend, the supplementary panel covering the DNp28 experiment) and the Fig. 3
  image.

## Decisions and judgement calls

**Cell 2024 — DNg13 was not recorded.** DNg13 is an assigned type and the paper reports a
clear activation experiment with leg tracking ("Depolarizing current triggered ipsilateral
turning (relative to the recorded soma)"), but the activation was delivered by whole-cell
patch-clamp **depolarizing current injection**, not optogenetically or thermogenetically.
PROTOCOL section 1 defines a record as activation with an optogenetic or thermogenetic
effector, and `record_schema.json` restricts `effector_kind` to `optogenetic` /
`thermogenetic`, so this experiment cannot be encoded. The Methods explain why: SPARC-
CsChrimson could not be used for DNg13 because the line also drives an ascending neuron,
and in those flies "light stopped locomotion". If the ledger wants current-injection
activations, DNg13 Fig. 4G-I is the experiment to add.

**Cell 2024 — GtACR1 experiments excluded.** Unilateral and bilateral DNa02 GtACR1
(Fig. 4D-F, S6D-F) are hyperpolarisation/silencing, not activation.

**Cell 2024 — calcium imaging excluded.** Figures 2, S2, S3 image DNa01, DNa02, DNb05,
DNb06, DNg13, DNg14, DNg15, DNg16, DNp05, DNp09, DNp11, DNp18 (many of them assigned
types) during walking. Imaging is not activation, so no records.

**Leg-rhythm coding for the two DNa02 records.** Both analyses included only trials in
which the fly was already walking (forward velocity >= 1 mm/s around the stimulus), and
the reported outcome is a change in stride length / turning / slowing in an ongoing walk.
Per PROTOCOL section 3 ("Turning or a speed change in a fly that was already walking"),
the three leg-rhythm fields are `not_assessed` and the result is carried by
`effect_on_walking`. Standing flies were not stimulated as a separate condition.

**Nat Commun 2025 — DNp28 name/line conflict.** The paper writes "DNp28" and gives the
line as SS01587 (Table 1: `R11H10-p65.AD(attP40); VT033947-GAL4.DBD(attP2)`, "DNp28
(SS01587) by Gwyneth Card"). The kit's `driver_lines.csv` maps SS01587 to **DNp29**
(from Namiki 2018, AD_DBD R11H10-x-VT033947 — the same hemidrivers). So the paper's name
and the kit's line mapping disagree. I recorded `manc_type` = `DNp28` (the paper's own
name, a MANC type) with `mapping_confidence` = `medium` and explained this in
`mapping_basis`; both DNp28 and DNp29 are on my assigned type list, so the record is in
scope either way. Logged in `out/proposed_driver_lines.csv` for adjudication. Only one
record was written (not one per candidate type) because the paper names exactly one type.

**Nat Commun 2025 — other activations are out of scope.** P1a, pC2l, pIP10 and pMP2 were
activated with CsChrimson (Fig. 4B, 5C-F). pIP10 and pMP2 are descending neurons, but
neither appears in `type_list.csv` or `synonyms.csv` and neither is on my assigned type
list, and the reported outcomes are song/vibration, not leg movement. The vGlut-GtACR1
experiment is silencing of all motor neurons, not a DN activation. "DNvib" is a
hypothesised, unidentified neuron.

**Leg-rhythm coding for the DNp28 record.** Activation induced female walking/acceleration
scored from centroid velocity tracking (DeepPoseKit head/thorax/abdomen/wings; the legs
were not tracked). Per PROTOCOL section 3, walking is `yes` for all three leg pairs with
`labeler_confidence` at most `medium`.

## Simulations seen

Both papers contain their own modelling: the Cell paper draws connectome-based inferences
about DNa02/DNg13 premotor targets (Fig. 7D-F), and the Nat Commun paper fits GLMs and a
rate-based circuit model (Fig. 6, S8, S10). Neither prints a rhythm score, rank or
driver/non-driver call for a DN type from a connectome activation screen of the
Pugliese type, so `saw_simulation_score` is `false` on all three records. No simulation
result was used as evidence.

## Nothing unreachable

Both sources had full text, figures, page images and supplements present. No source needed
the `unreachable` disposition.
