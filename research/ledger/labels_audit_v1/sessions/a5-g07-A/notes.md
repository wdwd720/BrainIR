# Session a5-g07-A — label audit notes (run 5)

Assigned types: DNa04, DNa05, DNa15, DNg100, DNg13, DNp01, DNp02, DNp03, DNp04, DNp06,
DNp07, DNp10, DNp11, DNp26, MDN. Assigned sources: 3. All three were readable; no source is unreachable.
No web access was used; only files in this room.

## What I did

Read each `text.txt` in full, plus `driver_lines.csv`, `type_list.csv` and `synonyms.csv` for mapping, and the
Figure 8 image of the eLife paper to check the adult panels.

## 10.1016/j.cub.2025.11.035 (Croke et al., DNp03) — 3 records

DNp03 is an assigned type and is activated with CsChrimson in three distinct experiments (one unilateral/stochastic
tethered, Fig. 4; one bilateral tethered, Fig. 6B–D; one bilateral free flight, Fig. 6E–M). Driver SS01559 maps to
DNp03 in `driver_lines.csv` (AD/DBD R29F12-x-R88C07, matching the paper's Key Resources Table).

Judgement call worth flagging for the adjudicator: **these are flight experiments and the paper never describes what
the legs do under activation.** Only wing beat/stroke amplitudes, head yaw and body Euler angles were tracked. I wrote
the records anyway with all three leg-rhythm fields `not_assessed`, following PROTOCOL sec. 3 ("Wing, flight, song or
abdomen behaviours: legs `not_assessed` unless the legs are described"). A reader applying the task sentence "reports
what the legs do" strictly would instead give this source `no_qualifying_experiment`. The records are flagged in their
`notes` so they can be dropped cleanly if the stricter reading is preferred.

The paper does score leg extension (Fig. 7G–J), but only for **looming-stimulus** trials in control and Kir2.1-**silenced**
flies — not an activation experiment, so no record.

Other assigned types in this paper (DNa04, DNa05, DNa15, DNp26, and DNp06/DNp07/DNp10/DNp11/DNp01/DNp02/DNp04 in the
introduction and discussion) appear only as connectome partners or literature citations; none is activated here.
DNg13 is mentioned once in the discussion, citing someone else's work. No records for any of them.

`line_specificity` is `unknown` for the DNp03 records: the paper reports verifying DNp03 expression but does not name
off-target cells. (`driver_lines.csv` notes ~3 off-target cell types for SS01559 from Namiki 2018, but that is not a
statement in this source, so I did not use it to name off-targets.)

## 10.1016/j.cub.2026.09.056 (Cao & Anderson, threat display) — no qualifying experiment

The activation experiments target AIP (CL062), DNpe050, DNp60, AVLP491 and AVLP710m. None is an assigned type:
`synonyms.csv` maps DNpe050 to MANC DNxn183 and DNp60 is its own MANC type (neither assigned). DNg100 — the one
assigned type that appears — is mentioned only as a connectome-predicted common downstream target of AVLP491 and
AVLP710m (Fig. S6H); it is never itself activated, so no record. Note that AVLP491 activation does produce leg-driven
locomotion, but AVLP491 is an interneuron, not a DN, and not an assigned type.

## 10.7554/elife.38554 (Carreira-Rosario et al., MDN) — 2 records

Most of this paper is larval (crawling), which PROTOCOL sec. 1 excludes. Two **adult** activation experiments qualify:

1. Fig. 8C,D,F: intersection of larval Split3 (ss01613) with the adult moonwalker line VT044845-lexA driving ReaChR;
   8/10 adults walked backward, in an agar ring arena with wings clipped.
2. Fig. 8G–I: RU486-induced immortalization from Split1, lexAop-CsChrimson; 20/20 adults walked backward in a
   serological pipette.

Both are coded `yes` for all three leg pairs under PROTOCOL sec. 3 ("walking, forward or backward: `yes` for all three
leg pairs") with `labeler_confidence` = `medium`, because backward walking was scored by eye from 5 Hz video as a
probability, with no leg tracking and no stepping frequency. `effect_on_walking` is `not_assessed`: the paper reports
initiation of backward walking, not a modification of ongoing walking. Both lines have a few unnamed off-target
neurons, so `line_specificity` = `minor_offtarget` with a described (not named) entry in `other_cell_types`.

The Fig. 8H penetrance of 1.0 is biased: those adults were preselected as larvae that crawled backward. Noted in the
record.

## Uncertainties

- Whether the DNp03 flight records should exist at all (see above).
- `sex` for the MDN adult experiments is not stated in the paper; recorded as `unknown`.
- No simulation score, rank or driver call from a connectome activation screen was seen in any of the three sources.
  `saw_simulation_score` is `false` on all five records. (The DNp03 paper mentions connectome-based *predictions* of
  its own, e.g. "we predict b3MN and i1MN decrease the contralateral WBA", but that is the paper's own anatomical
  reasoning, not a Pugliese-type screen score.) No `out/sightings.csv` was needed.
- No new synonyms or driver lines to propose; `out/proposed_synonyms.csv` and `out/proposed_driver_lines.csv` were not
  written.
