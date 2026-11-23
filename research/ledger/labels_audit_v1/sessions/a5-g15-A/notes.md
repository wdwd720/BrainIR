# Notes: session a5-g15-A (label audit, run 5)

Assigned types: DNa01, DNa02, DNa03, DNa11, DNb05, DNb06, DNg13, DNp09, DNp71, DNxl022.
Assigned sources: Rayshubskiy et al. preprint (10.1101/2020.04.04.024703, bioRxiv v4) and the published eLife paper (10.7554/elife.102230).
Both were read in full from text.txt (methods, legends, discussion). I checked the Fig. 8 images in both versions. Nothing was unreachable.

## Experiments found
- **DNa02 activation (qualifies):** stochastic ReaChR (hsFLP FLP-out) under SS00730. Head-intact flies walking on a ball, with 617 nm light on the head.
  Unilateral-expression flies showed a small ipsilateral steering bias (Fig. 8B,C). Coded as a turn in already-walking flies,
  so the leg-rhythm fields are `not_assessed` (PROTOCOL 3). There is one record per source DOI, so the two records describe the same experiment.
- I wrote no separate bilateral-activation record. The bilateral-expression siblings were used only as a bootstrap null for rotation.
  The forward-velocity changes were put down to visual startle, were the same across unilateral, bilateral and no-expression flies (data not shown),
  and the authors say they could not use them. Someone could argue for a bilateral record with effect "none"; I judged the evidence too weak.
- Not records: whole-cell recordings of DNa01/DNa02; GtACR1 silencing of DNa01/DNa02 (Fig. 8D-H); CsChrimson in olfactory receptor
  neurons (Orco) and antennal thermoreceptors (Gr28b.d), which are not DNs; P2X2/ATP stimulation of PEN1 neurons.
- DNa03, DNa11, DNb05, DNb06, DNg13 and DNp09 appear only as connectome partners or in citations of other studies
  (Yang et al. 2023, Feng et al. 2024, Braun et al. 2024, Bidaye et al. 2020, Cande et al. 2018). DNp71 and DNxl022 do not appear. No records for these.

## Uncertainties
- The number of unilateral flies differs between sources: the Fig. 8B legend says 16, while Methods gives 9 left-only + 8 right-only = 17. I used 16 and explained this in n_flies_note.
- SS00730 off-target expression (optic lobe and VNC cell types) comes from the GtACR1/GFP expression figure. ReaChR expression was scored only in the brain.
  I coded line_specificity as `minor_offtarget`.
- The "simulation" in Fig. 8C is bootstrap resampling, not a connectome model. I saw no connectome simulation scores, so `saw_simulation_score` = false.
