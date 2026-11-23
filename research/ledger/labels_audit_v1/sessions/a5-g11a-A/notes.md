# Notes: session a5-g11a-A (label audit, run 5)

Sources read (local only, no web): Braun, Hurtak et al. 2024 Nature (10.1038/s41586-024-07523-9), and Yang et al. 2023 bioRxiv
(10.1101/2023.10.15.562426). I read the text, the figure images I needed and the Braun Supplementary Information text (Supp. Tables 2, 5, 6).
I saw no Pugliese/Sapkal-type simulation score, rank or driver call. Braun's own connectome analyses (DN-DN connectivity, clustering) are
not simulation scores. `saw_simulation_score` is false on all records, and no `sightings.csv` was needed.

## Braun et al. 2024 (24 records)
- DNp09 (SS01540; the kit lists it as AMBIGUOUS DNp09/DNp71, so mapping is medium). Records: Fig. 2a (walking-before-stimulus trials, so
  speed change, legs not_assessed); Ext. Data Fig. 2a (non-walking starts, forward walking); Ext. Data Fig. 1d (intensity series);
  Fig. 4b intact and headless (headless: no walking, abdominal contraction); Methods homozygous condition (freezing); Ext. Data Fig. 10
  leg amputation.
- aDN2 = DNfl023 (R76F12-AD;R18C11-DBD; the paper names off-target cells, so minor_offtarget). Records: Fig. 2a, Ext. Data Fig. 1d at
  41.6 uW (grooming) and at 21 uW (rest/stop), Ext. Data Fig. 2b, Fig. 4c intact and Fig. 4c,g headless (front leg approach only).
- aDN1 = DNg62, DNa01, DNa02: Ext. Data Fig. 5b/c/e intact and headless.
- DNg14: Fig. 5g / Ext. Data Fig. 6d (same data) intact and headless. Abdominal behaviour only, so legs not_assessed.
- Web (DNg74, SS41434), DNg30 (SS02378), DNg16 (SS01543) were tested but excluded from the analysis for having no known intact phenotype
  and no clear headless phenotype. Each gets one low-confidence headless "no visible effect" record. No data are shown for these lines,
  and their intact outcomes are not reported.
- Not recorded:
  - Ext. Data Fig. 3 (DNp09 with the VNC resected at T1): imaging only, and the injured VNC gave "no notable leg movements".
  - Headless flies hanging without ground contact: shown only in Supplementary Videos 3-5, which were not downloaded.
  - GF/DNp01: the authors did not repeat that experiment.
  - BDN2 (DNg100), oDN1 (DNg97), DNa08, DNg12: connectome or literature tables only.
  - MDN, DNb02, DNp42, oviDN, DNg11, Mute: not assigned types.
- Uncertain:
  - Intact DNa01/DNa02 turning is coded `unclear` for leg rhythm because the pre-stimulus state was not restricted and legs are not
    described.
  - Headless DNa01/DNa02 are coded `no` with low confidence because only ball velocities were reported.
  - `line_specificity` = clean for the Fig. 5 / Ext. Data Fig. 5-6 lines rests only on the Methods phrase "filtered for lines where a
    clean spGAL4 line was available".

## Yang et al. 2023 (3 records)
- DNa02 unilateral and bilateral SPARC-CsChrimson. Only walking flies (forward velocity >= 1 mm/s) were analysed, so these are steering
  and speed changes and leg-rhythm fields are not_assessed. Stride and return-stroke details are in `coordination_notes`.
- DNg13 SPARC-CsChrimson: in flies where the off-target ascending neuron expressed CsChrimson, light stopped locomotion whether or not
  DNg13 expressed it. This is recorded with low confidence and marked minor_offtarget. The DNg13 current-injection experiments (patch
  clamp) are not opto- or thermogenetic, so they are not recorded.
- The other assigned types in this paper (DNa01, DNb05, DNb06, DNg14, DNg15, DNg16, DNp05, DNp09) were calcium imaging only, so there
  are no records for them.
- Not available: the key resources table and Table S1 exist only as images not rendered in the text. Driver hemidrivers come from the
  "Fly genotypes by figure" section.
