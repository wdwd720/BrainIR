# Predictions v2: notes hashed by `LOCK_predictions_v2.json` (PREREG v2 P1-P5)

- **Arms locked:** B1r, B2r (tuner v2, K = 1), B4v2. **Not locked:** B3 and B6 (G3 v2 fails on item 4', decided before the
  freeze, P2). Marking: locked after labels v1 existed, before any unblinding; committed locally and pushed only after
  `LOCK_labels_v2.json` exists (P5).
- **Platform:** B1r and B2r on GitHub Actions hosted runners (ubuntu-24.04, Linux x64; run 1's Python and library pins and
  numerics environment; numerics digest a72e417cfd91 on every chunk; trust gate 100/100 identical before the freeze); GitHub
  runs 44831777087 (B1r) and 44831808385 (B2r), runner commit 828e669. B4v2 recomputed on the Mac from the stored B4 replicates
  (log hash of P3 asserted, every result checked against the digests locked in predictions v1; no simulation).
- **Gates (P1):** K on DNg100 alone (`CALIBK.json`); tuner regression 480/480 (`REGRESSION_v2.json`); determinism 200/200, 58 of
  them on another CPU model (`DETERMINISM_v2.json`); positive control and the DNb08 report (`B12R_CONTROLS.json`); baseline
  (`BASELINE_v2_predlock.json`); independent review (`reviews_v2/REVIEW_predictions_v2.md`, resolution alongside).
- **Disclosure:** the regression campaign (30 types other than DNg100, K = 0) ran alongside the K calibration, before K was
  fixed, against the letter of P1 ("No other neuron is run before K is fixed"); 3 local K = 0 jobs ran before the freeze (LOG
  L51). No information path: K = 0 is B1's locked procedure, the results were encrypted on the runners, collected after
  `CALIBK.json` was written, and equal B1's locked digests.
- **Post-freeze prediction code** (hashed here): `calibk_choose.py`, `gha_det.py`, `b12r_gates.py`. `b4v2.py` amended once
  (`AMENDMENTS_v2.jsonl`: P3's log hash asserted; calls unchanged).
- **Reason codes:** the frozen `arms._final` codes a K-rejected run inside the activity bounds as "strong"; `b12r_gates.py`
  recomputes it as "weak" (P1: "counts as too weak") and the type `status` (646 / 576 replicates, 32 / 30 types); scores and
  bands are unchanged.
