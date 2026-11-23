# Session a5-g21-A (label audit, run 5)

## What I read
Only the two assigned sources in `sources/` (no web, no other files). For each I read `text.txt` in full,
the supplementary text files, the supplementary tables (CSV), and the main/extended figures as images.

## Sapkal et al. 2026 (10.64898/2026.04.29.721658) — 42 records
Optogenetic CsChrimson activation of walking DNs in decapitated (and a few head-intact) tethered flies, with
3D leg tracking, across four conditions: ball, slippery surface, air-suspended, air + all legs amputated.
One record per (figure group, driver line/genotype, preparation), as PROTOCOL §1 requires.

Covered assigned types: DNg100 (BDN2), DNg97 (oDN1), MDN, DNg16, DNg55 (BDN3), DNg75 (cDN1).
- DNg100: all six legs step in all four conditions; also FeCO-silencing, proximal-joint immobilization,
  unilateral (stochastic FLP-out), segment-specific leg removal, light-intensity titration, head-intact and
  homozygous groups, and the Fig. 4 co-activation control datasets.
- DNg97: all six legs on the ball, front legs only when sensory feedback is reduced.
- MDN: all six legs backward on the ball, hind legs only when sensory feedback is reduced.
- DNg16, DNg55, DNg75 alone: no walking induced in decapitated flies (coded `no_visible_effect`, legs `no`,
  `labeler_confidence` medium because the read-out shown is ball forward velocity, not leg tracking).
- Co-activation pairs (DNg100 + DNg16 / DNg55 / DNg75 / DNg97), ball and air: each genotype labels two DN
  types, so there is one record per type with `line_specificity` = `multi_dn`.

Judgement calls:
- For DNg97 and MDN under reduced feedback, legs whose Fig. 1e medians are near zero but non-zero in some
  trials are coded `unclear`; legs with a flat zero median and no stepping in the example traces are `no`.
- Several frequency values are read off figure panels (noted in `frequency_note` / `notes` beginning
  `figure:` where the result itself comes from a panel).
- Types mentioned only in connectome analysis (DNb08, DNg12, DNp09 in Extended Data Fig. 12) have no
  experiment and so no record.
- `line_specificity` = `minor_offtarget` where Extended Data Fig. 7d / 5a report ectopic VNC cells for the
  genotype; `clean` where the figure shows none.
- The paper cites the Pugliese connectome-simulation CPG work but prints no per-DN rhythm score, rank or
  driver call, so `saw_simulation_score` is `false` on all records.

## Özdil et al. 2026 (10.1038/s41467-026-72152-x) — 0 records
Antennal grooming study. The experiments on flies activate (i) JO-F antennal sensory neurons
(aJO-GAL4-1 > CsChrimson) and (ii) the c23 'asteroid' brain interneuron (SS35281 > CsChrimson), which
suppresses antennal grooming. Neither is a DN type on my assigned list. aDN1 (= DNg62) and other DNs appear
only in the connectome-derived artificial-network activation/silencing screen, i.e. in simulation; the
authors' rebuttal (Supplementary peer-review file) states explicitly that activating aBN2/aDN1 to test the
prediction was infeasible. A simulation result is not evidence, so no record was written and the source is
dispositioned `no_qualifying_experiment`.

I did see the simulated activation-screen result naming aDN1 (DNg62) in that paper. It is the paper's own
model, not a Pugliese-type score, and no record of that type was written, so no `saw_simulation_score`
flag applies; recording it here for transparency.

## Not accessible
Supplementary videos for both papers were not downloaded (video files). Nothing else was missing.
