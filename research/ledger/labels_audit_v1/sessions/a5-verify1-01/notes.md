# Notes — session a5-verify1-01 (audit, verification of 3 sample rows)

Read first: `AUDIT_NOTE.md` (overrides PROTOCOL where they differ), then `PROTOCOL.md` sections 1-8.
Only the three assigned local sources were used; no web access, no model or simulation output.

## Per row

1. **DNa11 / SS77821** (10.1101/2024.06.27.601106, intact_tethered): quote found verbatim in Discussion
   ("Hierarchical motor control"). Fig. 6f shows both front legs (contra/ipsi T1) stepping at ~3 Hz during unilateral
   activation; the authors state DNa11 can "initiate stepping". Coded **yes**. The main phenotype is a turn (saccade).
   I treated it as stimulation-evoked stepping rather than "turning in an already-walking fly", because of the
   initiation statement and the per-leg stepping data. A stricter reader could argue for `not_assessed` if they judged
   the flies were already walking. Baseline walking state is not described explicitly for the DeepFly3D experiment.
2. **SS01069 (G14)** (10.7554/elife.34275, intact_free): the "quote" is just the line ID, visible on page 21 of
   Figure 2-source data 1 (page image; the PDF has no extractable text). Region 4 inset sits in the bottom-centre of the
   map, which is the locomotion region in Fig. 1C. Its density rises at light onset and stays above control through the
   15-s stimulus. Coded **yes** under the "increased locomotion without leg tracking" convention (confidence at most medium).
   Uncertainty: region identity is read from a small inset; the paper has no text description for this line.
3. **DNp13 via SS01549** (10.1038/s41593-019-0413-4, intact_tethered): quote found verbatim in Supplementary Fig. 1b
   legend. Activation gives a single landing-like extension of all legs. This is a single movement, so coded **no**.
   The paper attributes the phenotype to DNp07 and says DNp13 does not innervate leg neuropil. The record is a
   multi_dn line record, as protocol section 1 requires.

## Simulation scores
None seen. The two grep hits for "simulat" in the steering preprint are a typo for optogenetic "stimulation" (Methods)
and a VR visual-scene description, not model outputs. `sightings.csv` is header-only.

## Not accessed
Supplementary videos in all three sources were not downloaded; none was needed to decide the rows.
