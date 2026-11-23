# a5-adj-04 audit notes

Assigned type: **DNp03** (no other names). Assigned sources: Croke et al. 2026 (Curr Biol, 10.1016/j.cub.2025.11.035) and
Dombrovski et al. 2023 (Nature, 10.1038/s41586-022-05562-8). I read both in full. For Dombrovski I also read the
supplementary PDF text (Supplementary Table 1), the source-data CSVs and the Fig. 1 and Extended Data Fig. 1 images.
For Croke the figures, videos and Document S1 were not downloaded (text.txt only). The text and legends were enough to code
the activation experiments, but the videos could not be checked for incidental leg movement.

Neither source prints a Pugliese-type rhythm score, rank or driver call. `saw_simulation_score` = false everywhere.
Dombrovski's own LC4 receptive-field model and Croke's connectome analyses are not that kind of score, and neither is
evidence here.

## DNp03: where the readers differed

- **Croke et al. 2026.** Reader A wrote 3 records: unilateral tethered flight (Fig. 4), bilateral tethered flight
  (Fig. 6B-D) and bilateral free flight (Fig. 6E-M). All three are `wing_or_flight`, with every leg field `not_assessed`.
  **Reader B wrote no records from this paper.** I agree with Reader A. These are real activation experiments
  (SS01559 > CsChrimson), but only the wings, head and body were tracked and the legs are never described, so per
  PROTOCOL sec. 3 the legs are `not_assessed`, not `no`. The only leg observation in the paper (all-six-leg extension,
  Fig. 7G-J) comes from looming stimulation of control and Kir2.1-silenced flies. That is not activation, so it is not a
  record. Minor corrections to Reader A: in record 0001 I give the total flies across both sides (13), and I code free
  flight's secondary behaviour as `turning`.
- **Dombrovski et al. 2023.** Both readers wrote the same two records (SS01081 and SS01596, FlyPEZ, 50-ms CsChrimson),
  with all legs `no` and `no_visible_effect`. They differed only on confidence (A medium, B low) and expression
  (A unknown, B bilateral). I agree with the substance: takeoff was not above control (5.2% and 2.8% vs 4.2% for Empty)
  and the DNp03 T2-leg postural shift was not significant. I use **low** confidence: only takeoff and middle-leg
  posture were scored over a window of about 100 ms, too short to see three stepping cycles, and stepping was never
  scored explicitly. I use expression `unknown` (not stated) and sex `unknown` (not stated for FlyPEZ; both readers
  wrote `mixed`). DNp03 is not named in the main text, so the per-line result comes from Extended Data Fig. 1e and
  its source data (noted with `figure:`). The quote is the main-text sentence stating the result by exclusion.
  Extended Data Fig. 2f also lists the DNp03 lines, but that panel is Kir2.1 silencing with looming stimuli, so it is
  not a record.

## Bottom line for DNp03

No experiment in these two sources shows rhythmic leg movement when DNp03 is activated. The flight experiments (Croke)
do not assess the legs. The perched FlyPEZ experiments (Dombrovski) show no visible effect on the legs, but over a window
too short to rule out stepping, so that "no" is low confidence. The readers did not actually disagree about rhythm
outcomes. The disagreement came from Reader B leaving out the three Croke flight records.
