# Notes: session a5-g22-A (audit, run 5)

Assigned types: DNp01 (GF), DNp09, DNp71, MDN. Four assigned sources, all with full text in the room. I read the text, figures and relevant supplements of each. No web access was used.

## Per source
- **10.1098/rspb.2024.1724** (Chai et al. 2025): GF split lines GF1 and GF2 drive only Kir2.1 or Kir2.1;Gal80ts (silencing). No activation, so no records.
- **10.1371/journal.pone.0267834** (Luo et al. 2022): flies tethered with CsChrimson and a 300 ms red pulse.
  - GF-split-Gal4 (R17A04;R68A06) produces takeoff: leg extension, wing depression, flight. Legs coded `no` because this is a single movement. n = 24.
  - SS1540 produces freezing: legs `no`, `stops`. n = 80.
  - Mapping for SS1540: the paper names DNp09. The kit lists DNp09/SS01540 as ambiguous (DNp09 or DNp71 via the hemibrain name). I chose MANC DNp09 with medium confidence because the paper uses Namiki nomenclature.
  - Line specificity is set to `minor_offtarget` because the authors state other SS1540 neurons may cause the freezing.
  - No DNp71 record was written.
- **10.64898/2026.02.26.708359** (Lee et al. 2026 preprint): free females in a pipette, CsChrimson, 5 s of red light. Control MDN activation gives backward walking in Figs 1C, 2K and 3M, so I wrote one record per figure.
  - Scoring was net distance from video with no leg tracking, so `labeler_confidence` = medium.
  - Hb, Lar and Inx8 RNAi arms abolished backward walking (forward movement or pausing). I did not write records for them because the neuron itself is genetically altered; they appear in `notes` only. A different reading could add them as separate condition records.
  - n per group is not stated in the text and was estimated from figure dots.
  - The driver is written "VT50600" (probably VT50660).
  - The single-cell two-photon CsChrimson stimulation in an explant brain gives no behaviour, so it is not a record.
- **10.7554/elife.69767** (Lee & Doe 2021): only Pair1 (R75C02-Gal4) is optogenetically activated in adults. MDN appears only in anatomy and t-GRASP. No records.

## Simulation scores
None of the sources shows a connectome-simulation rhythm score, rank or driver call for any assigned type. `saw_simulation_score` = false throughout.
