# a5-adj-03 adjudication notes (label audit, run 5)

Assigned type: **DNa02** (SS00730 = R75C10-AD; R87D07-DBD). Assigned sources: Feng et al. 2024 bioRxiv
(10.1101/2024.06.27.601106) and Rayshubskiy et al. 2025 eLife (10.7554/elife.102230). Both were read in full from the local
`text.txt`, plus the relevant figures (Feng Fig. 2, Fig. S3; Rayshubskiy Fig. 8) and Feng Supplementary Table 1 (genotypes).
No web access was used. Neither source contains a Pugliese-type connectome activation score, rank or driver call for DNa02.
`saw_simulation_score` is therefore `false` on all records. The "simulation" in Rayshubskiy is a bootstrap null. Feng cites a
computational study (ref. 49) without printing scores.

## DNa02: where the readers differed

The two readers did **not** disagree on leg rhythm. Every record from both readers has all three leg fields set to `not_assessed`, and so do mine.
They differed on these points:

1. **Feng 2024, line specificity:** Reader A said `minor_offtarget` and Reader B said `unknown`, with an empty `other_cell_types`, even though B's own notes cite
   the off-target cells. The Fig. S4f legend says the SS00730 driver co-labels off-target cells ("off-target cells co-labelled by the
   driver lines"), so I agree with A: `minor_offtarget`.
2. **Feng 2024, sex:** Reader A said female and Reader B said unknown. The SPARC genotype in Supplementary Table 1 is `nSyb-PhiC31 in attP18 / w; ...`, which has two X
   chromosomes, so the flies are female. Methods also say mostly females were used. I agree with A: female.
3. **Rayshubskiy 2025, bilateral group:** only Reader B wrote a separate record for the bilateral-expression siblings. I also wrote
   one. DNa02 was activated bilaterally in walking flies with ball tracking, so it fits PROTOCOL 1. But the authors used this group
   only as a null control and explicitly say they cannot judge forward-velocity effects (visual startle). Every outcome field is
   `not_assessed`, with low confidence.
4. **Experiment missed by both readers: Feng 2024, bilateral group (Fig. 2c).** Neither reader recorded it. The Fig. 2c quantification shows
   that flies with both DNa02 neurons labelled (n=10) do not differ from no-label flies in angular velocity (n.s.). Under PROTOCOL 1, a condition
   with a different outcome gets its own record. I coded it `no_visible_effect` / `effect_on_walking` = `none`, with medium confidence,
   using a figure quote. The text does not discuss this group. Only angular velocity was measured.

## DNa02: what I found

- Both papers activate DNa02 only stochastically (SPARC2-D-CsChrimson; hsFLP ReaChR), in tethered flies **already walking**
  on a spherical treadmill. Neither reports stepping, leg kinematics, or stimulation of standing flies for DNa02 activation.
  The only measures are ball rotational (and, in Rayshubskiy, forward) velocity.
- Unilateral activation causes a weak ipsilateral turning bias in both papers (Feng: "<50°/s, highly probabilistic";
  Rayshubskiy: "small average steering bias"). Under PROTOCOL 3 (turning or speed change in an already-walking fly), this goes in
  `effect_on_walking` = `turns`, and the leg-rhythm fields are `not_assessed`.
- **Bottom line for DNa02 leg rhythm:** neither assigned source supports `yes` or `no`. The answer is `not_assessed` in all four records.
- Not records (checked and excluded): Feng GtACR2 epistasis (Fig. 2e-g), reaper/grim ablation (Fig. 3, S4), and calcium imaging
  (Fig. 5, S7, S8). Rayshubskiy GtACR1 silencing (Fig. 8D-H; this is where its leg kinematics come from), patch-clamp recordings,
  and CsChrimson in ORNs/Gr28b.d thermoreceptors (Fig. 5), which activates sensory neurons, not DNs. The Introduction and Discussion
  cite Cande et al. 2018 and Braun et al. 2024 on DNa02 activation. Those papers are not assigned and were not opened, so no records
  come from them.

## Uncertainties

- Rayshubskiy n: the Fig. 8B legend says 16 unilateral / 17 bilateral, but Methods count 17 unilateral and 47 bilateral brains. I used the legend values.
- Feng's supplementary videos were not downloaded. None of them is described as showing DNa02.
