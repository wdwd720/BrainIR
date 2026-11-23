# a5-atlas-C audit notes

Source: Cande et al. 2018 (10.7554/elife.34275). I read text.txt, Fig. 1/1C (map layout: anterior grooming at the top, anterior movements on the upper left, still/slow on the upper right, wings & abdomen in the centre, locomotion along the bottom from slow (left) to fast (right)), Fig. 1-figure supplement 2, Fig. 2-figure supplement 2, and the Figure 2-source data 1 (Figure S5) page images for each disputed line. The S5 PDF has no text layer, so all evidence comes from figures: quotes are the panel labels and every note starts with `figure:`. Region positions were read from small inset maps on page images I could not enlarge, so all records are `labeler_confidence` low.

Rule applied: a significant region that lies clearly inside "locomotion" counts as walking (all legs yes). A region that is tiny or straddles two areas gives unclear. A region in "wings & abdomen" with no leg description gives not_assessed. "Anterior grooming" gives front legs yes (grooming convention). No simulation scores appear in this source (saw_simulation_score false). The S5 pages carry section headers that name cell types. I did not use or transcribe them.

## Per-key adjudication
- SS01053 (intact): agree with **B**. A single tiny, noisy region sits on the border between wings & abdomen and locomotion, and there is no locomotion hot spot. A's walking call is not supported. Legs unclear.
- SS01064 (intact): agree with **B**. A large region runs diagonally across anterior movements into slow locomotion, and the effect is transient. Legs unclear, walking as secondary only.
- SS01073 (intact): agree with **A**. The dominant Region 2 is at the lower right (fast locomotion) and is elevated and oscillating through the whole light period, with a 3-6 s hot spot at the lower right. Walking yes, speeds.
- SS01547 (intact): agree with **A** on walking (Region 2 lies in the lower-left/centre slow-locomotion band and is sustained), but I set effect_on_walking to not_assessed rather than A's speeds, because the region is at the slow end. B placed it in anterior movements. I read it as lower than that, but this is a borderline call.
- SS01550 (intact): agree with **A**. Region 1 is in the "anterior grooming" area and sustained, so front legs are yes by the grooming convention and the other legs unclear. Region 2 (anterior movements) is secondary. B's all-unclear ignores the grooming convention. Confidence is low because the top area also holds proboscis extension.
- SS01597 (intact): agree with **neither**. The region is tiny and sits just below centre on the border between wings & abdomen and locomotion. That does not support A's walking yes, and it is not clearly a wing/abdomen call either (B's not_assessed). Coded unclear.
- SS01608 (intact): agree with **B**. A tiny central wings & abdomen region with a brief onset peak, and the legs are not described, so legs not_assessed (section 3). A's unclear does not follow the wing/abdomen convention.
- SS02257 (intact): agree with **B**. The dominant Region 2 is in wings & abdomen, right of centre, so legs not_assessed. Same reason as SS01608.
- SS02275 (intact): agree with **A**. The small region lies in the lower-right part of locomotion, and the 0-3 s experimental map has a strong lower-right locomotion hot spot. Walking yes, low confidence. B read it as a border spot.
- SS02534 (intact): agree with **B** on legs (unclear: a large region straddles anterior movements and slow locomotion). I disagree with B's multi_dn coding. The page groups it under a two-type section header, but naming types is out of scope here, so line_specificity is unknown; the script assigning types should handle it.
- SS02634 (intact): agree with **B**. A large left region spans anterior movements and slow locomotion. Legs unclear.
- SS05107 (intact): agree with **B**. A small left-of-centre region sits in anterior movements near the slow-locomotion border. Legs unclear.
- SS05108 (intact): agree with **B**. A small elongated region sits on the border between anterior movements and slow locomotion. Legs unclear.

Not accessed: the videos (not downloaded) and the Dryad video compilation. They might settle the border cases (SS01053, SS01597, SS01064, SS02534, SS02634, SS05107, SS05108).
