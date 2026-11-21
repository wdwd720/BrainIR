# Session notes — R2-harris-a

Scope: hemilineages 00A, 00B, 01A, 01B, 02A, 03A, 03B, 04A, 04B, 05B, 06A, 06B, 07B, 08A, 08B,
09A, 09B, 10B, 11A, 11B, 12A, 12B, 13A, 13B.

Assigned source (one): **10.7554/eLife.04493** — Harris, Pfeiffer, Rubin & Truman (2015), *Neuron
hemilineages provide the functional ground plan for the Drosophila ventral nervous system*, eLife.
Disposition: `records`, 16 records.

## What I read

- `sources/10_7554_elife_04493/text.txt` in full (abstract, digest, Results, Discussion, Materials
  and methods, all figure and video legends, references).
- `supp/elife04493s001.txt` — Supplementary file 1, the genotype / off-target table. This is the
  source for the `driver`, `effector` and `coverage_notes` fields.
- Figure images `elife04493f004.jpg` (hemilineages 1A–5B), `f005.jpg` (6A–9A), `f006.jpg` (10B–14A)
  and `f009.jpg` (the behavioural summary matrix), plus PDF page images `article_p026.png` and
  `article_p027.png` for Figure 9 and its legend at full size.
- Two supplementary video frame montages (`elife04493v015` for 12B, `elife04493v016` for 13B).

I did **not** work systematically through all 22 video frame montages. The videos are not downloaded
(`meta.json` lists all 44 video files as skipped, "video or audio"); only the frame montages and the
legends are available, and the legends are identical to those already in `text.txt`. Every record is
coded from an explicit verbal description in the Results text, a figure panel legend, or Figure 9 —
not from my own reading of movement out of montage frames, which would amount to inferring movements
the source does not describe (protocol §2, last convention).

## Experimental design in this source

All behavioural experiments are dTRPA1 activation in **decapitated** adult females (3–4 days post
eclosion, decapitated on a cold plate, recovered ≥1 hr), on a hot plate ramped 24 °C → 32 °C (45 s,
flies reared at 21 °C) or 24 °C → 37 °C (55 s, flies reared at 25 °C), filmed from above at 60 fps;
high-speed video (1000–6400 fps) for takeoff/flight phenotypes. One exception: a **tethered intact**
preparation for 5B (fly gripping a Styrofoam ball) — coded as its own record (`R2-harris-a-0005`,
`preparation` = `other`).

Controls described (decapitated flies without the TRPA1 effector, Video 1; and
`R24B02-GAL4` controls) are not records: no hemilineage is being activated in them.

## Coverage outcome

Coded (15 in-scope hemilineages, 16 records): 1A, 2A, 3B, 5B (×2 — decapitated and tethered intact),
6A, 6B, 7B, 8A, 9A, 10B, 11A+11B (×2 — the lineage 11 line, and the same line with tsh-GAL80),
12A, 12B, 13B.

In scope but no activation experiment (`not_in_source`), with the source's stated reason:

| hemilineage | why no record |
|---|---|
| 0A, 4A | "hemilineages 0A, 4A, 16B and 17A are not addressed in this study" |
| 0B, 9B, 4B | never named as a hemilineage targeted for activation. 4B appears only in the Discussion as an anatomical comparison with grasshopper NB3-1; 4B/4A elsewhere in the text are *figure panel* labels ("Figure 4A", "Figure 4B"), not hemilineage names. Hemilineage 9B does not exist in this scheme (only 9A survives) |
| 1B | "our best 1B line showed expression in a dorsal hemilineage in addition to the 1B neurons, we did not use it for behavioral observations" |
| 3A | "The 3A line had major contamination from sensory neurons and was not used for behavioral observations" |
| 8B | "Our line for the 8B interneurons had some expression from other thoracic hemilineages and was not used for behavioral studies" |
| 13A | "We did not have a clean enough line to assess the effects of activating the 13A interneurons" |

The source states it collected behavioural data for 22 of the 33 hemilineage groups; the 15 I coded
are the in-scope subset of those 22.

## Hard cases and judgement calls

- **2A vs "2B" in Supplementary file 1.** The Results section, the Figure 4 legend and Figure 9 all
  call the line `R50G08` hemilineage **2A**. Supplementary file 1 lists the same line under
  `2B` ("Expression in abdominal homologs of 2B neurons"). I coded it as 2A, following the body text
  and figures, and flagged the discrepancy in the record's `coverage_notes` and `notes`. A second
  curator could reasonably read this differently; 2B is outside my scope either way.

- **Lineage 11 (11A/11B).** The source says explicitly it could not target 11A and 11B separately
  ("We were unable to construct lines to target hemilineages 11A and 11B independently, but
  R26B05-GAL4 targets the whole lineage"), so one record covers both, with
  `hemilineages_listed` = `11A;11B`. `record_type` is `partial_or_mixed` because the source itself
  flags occasional expression in a bundle of descending interneurons. The **tsh-GAL80 variant** is
  written as a second record: it is a different line/genotype tested on the same hemilineages and
  protocol §1 asks for one record per line, including lines with little or no effect. Takeoff was
  not abolished (9%, N = 22, vs 100%, N = 13), so d10 is `yes` there with the penetrance recorded.

- **3A line used for 3B?** The Figure 4 legend panel (O) reads "Thermal activation of the 3A
  primarily evokes flicking and scissoring movements of the wings", but panel O belongs to the 3B
  block (M–O) and the Results text attributes exactly this phenotype to 3B via `R23B05-GAL4`, while
  stating the 3A line was never used behaviourally. I treated the legend's "3A" as a typo for 3B and
  coded one 3B record. No 3A record.

- **3B driver.** Text says `R23B05-GAL4`; Supplementary file 1 gives `R23B05-LexA, LexAop-TRPA1` for
  the behavioural genotype. Both are in the `driver` field.

- **d5/d6 (held flexion vs held extension).** Several hemilineages are scored by Figure 9 as
  "Δ posture" without the text saying whether legs flex or extend. Where the direction is stated I
  coded it (9A, 12B, 13B, 20A/22A-style splaying → d6; 5B lowering/crouch → d5). Where Figure 9
  shows a posture bar but the text only says "subtle repositioning" (3B) or "fidgety repositioning"
  (8A), I used `unclear` rather than `no` or a guessed direction.

- **d7 vs d8.** 1A and 12A are coded d8 `yes` (the source calls it walking / locomotion with clear
  intersegmental coordination, even though the gait is not tripod). 10B is d8 `yes` *and* d7 `yes`
  (the text speaks of movement "during walking" and the Discussion lists 10B among the sustained-
  walking hemilineages, while the leg movements themselves are erratic and pivoting). 6B is d8
  `unclear`: there was curving forward movement, but "Most flies did not move far enough (>one body
  length) to be classified as walking" by the source's own criterion.

- **Going airborne without a described jump.** For 2A, 10B and 12A the source says flies went
  airborne but explicitly declines to call it a jump ("We do not know if this was accomplished by a
  jump via their T2 legs or if their tarsi simply lost contact with the substrait"; "there did not
  appear to be an organized jump preceding going airborne"). These are d10 `unclear`. 7B and 11A/B,
  where high-speed video documents a genuine takeoff sequence, are d10 `yes`.

- **Grooming (d9).** Decapitated flies groom spontaneously, so grooming on its own is not an
  activation effect. I coded d9 `yes` only where the source reports grooming during the activation
  period (1A, 2A wing grooming, 3B, 6B, 7B, 8A, 9A), and d9 `no` for 5B, where "Spontaneous grooming
  appeared to be suppressed".

- **"Their legs" / "their limbs"** is read as all three pairs (d2, d3, d4 all `yes`) per protocol §2;
  where only some segments are named (12B: "The T2 and T3 legs … The movements of the T1 legs were
  variable") I coded the named ones `yes` and the variable one `unclear`.

- **d14 (haltere) and d15 (abdomen)** are `not_assessed` throughout: the study filmed from above at
  60 fps and reports no haltere or abdominal observations for any hemilineage in my scope.

## Model predictions

**No sighting.** Nothing in this source is a computational model or network-simulation prediction of
what activating a hemilineage does; the paper is anatomy plus direct dTRPA1 activation behaviour.
`saw_model_prediction` is `false` on every record and `out/sightings.csv` has not been created.
I did not visit any website, and I did not open any of the sources listed in protocol §5.

## Missing / unavailable

- The 44 supplementary video files themselves were not downloaded (frame montages only). This limits
  independent checking of movements the text does not mention, but does not block any record.
- `supp/elife04493s001.docx` was not opened; its text extraction
  (`supp/elife04493s001.txt`) was complete and legible.
- The two peer-review sub-articles (decision letter / author response) are noted in `text.txt` as not
  included. Any experiment reported only there would have been missed; the Results text appears
  self-contained.
