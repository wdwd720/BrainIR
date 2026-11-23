# a5-adj-02: adjudication notes (label audit run 5)

Type assigned: **DNa02** (line SS00730; the hemidrivers R75C10AD / R87D07DBD).
Sources read: all four in `assigned_sources.csv`, all full text, with figures and supplements opened where needed (Nature ED Fig. 5 image,
Nature Supplementary Information pp. 7-9 and Supplementary Table 5, Cell Supplementary Figure 6 page image, 2023 preprint Fig. S4 legend).
I did not search for other sources. I did not see any Pugliese-type rhythm score, rank or driver call for DNa02, so `saw_simulation_score` = false everywhere.
The Nature paper does make connectivity-based predictions ("broadcaster" DNs), but that is the paper's own model. I did not use it as evidence.
No `sightings.csv` or proposed synonyms or lines were needed.

## Bottom line for DNa02

None of the four sources shows that activating DNa02 starts rhythmic leg movement, and none shows that it does not.
- Every experiment with leg tracking (Cell 2024 and its 2023 preprint) analysed only trials in which the fly was **already walking** (forward velocity >= 1 mm/s).
  In those trials DNa02 changes stride length (the return stroke) and step direction, which is a turn (unilateral) or slowing (bilateral).
  Under PROTOCOL section 3 the leg-rhythm fields are therefore `not_assessed`.
- 2020 preprint: the flies were walking on the ball, and only ball rotation was measured. Leg fields are `not_assessed`.
- Nature 2024: the intact flies turned weakly. The pre-stimulus state is not stated and the legs were not tracked, so the leg fields are `unclear`.
  In headless flies there was no turn or side-velocity change relative to headless controls, and the paper says nothing about the legs, so those fields are also `unclear`.

## Where the readers differed and what I found

1. **Nature 2024, headless (ED Fig. 5e).** Reader A coded all legs `no` (confidence low) with `effect_on_walking` = none. Reader B coded `unclear` (medium) with not_assessed.
   I agree with B on the legs. The only measures are turn velocity and side velocity. These do not differ from headless controls (P = 0.158 and 0.085, Supplementary Table 5).
   Forward velocity is not reported for DNa02, and neither the legend nor the text describes leg movement.
   Headless flies were kept only if their legs showed spontaneous coordinated movement (Methods), so the legs were not motionless.
   Whether stimulation started stepping cannot be read from the data shown. So `unclear` is right, not `no`.
   I set `effect_on_walking` = none, which refers to the measured turn/side velocity only.
   The headless "hanging without ground contact" condition appears only in Supplementary Video 4, which was not downloaded. It gets no record.
2. **Nature 2024, intact.** Both readers coded `unclear` with turning, and I agree.
   One detail: intact controls also responded to the light (intact vs headless controls P = 0.047). The paper compares intact with headless, not intact experimental with intact controls.
   A coded expression `unknown` and B coded `bilateral`. The line is a standard bilateral split-GAL4, so I used bilateral.
   Both readers coded line specificity `clean`, which matches this paper's own wording. Other sources report minor off-target expression for SS00730, and the record notes this.
3. **2020 preprint, bilateral-expression group.** Only Reader B wrote a record for it. I include it.
   The bilateral siblings received the same light, and the outcome differs from the unilateral group: no directional bias, and forward-velocity changes no different from no-expression flies.
   It is coded `no_visible_effect`, legs `not_assessed` (the flies were already walking and the legs were not tracked), confidence low (data not shown).
   B used the visual-startle sentence as the quote, and I used the same sentence. B coded `effect_on_walking` not_assessed. I used none relative to controls, since the paper explicitly reports no difference from no-expression flies.
4. **Cell 2024 and the 2023 preprint (unilateral and bilateral).** Both readers agree and so do I: `not_assessed` legs, turns (unilateral), slows (bilateral), minor off-target cells (lobula visual neurons and abdominal ganglion cells).
   Minor differences: A gave the 2023 bilateral record medium confidence and B gave it high; I used high, because the result is significant with all six legs tracked.
   Both readers listed the 2023 driver line as the hemidriver pair. I wrote SS00730 for consistency, since it is the same pair.
5. Duplicates: the 2023 preprint duplicates the Cell 2024 experiments, and the 2020 bioRxiv v4 matches the eLife version, which is not assigned here. The records are kept per source as instructed. Downstream deduplication should treat 0001/0005 and 0002/0006 as the same experiments.

## Not accessible
- Nature Supplementary Videos 1-6 were not downloaded (meta.json: skipped as video). I needed only Video 4 (DNa02 headless and hanging).
