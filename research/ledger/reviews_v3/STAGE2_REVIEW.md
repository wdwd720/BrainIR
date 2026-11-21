# Stage 2 review (PREREG v3 P9.5): group builder, motor map, prediction rules, gates, run registry

Verdict: pending (H-M tables not yet present)

Fresh reviewer, 2026-11-21, `ledger/v1` at b40814f. Items 1-5: **no blocker, no major**. Open: P9.3
(`gates_v3/DETERMINISM_hmdet-run3.json` absent; `hmdet-run3` queued), `hm-run3` still running (no `arms_h1` results here), and the
H-M spot check (item 6). No predicted value is quoted here.

## Findings

1. **minor (documentation).** LOG L79 says every campaign tag points at d636200. The tags point at three commits, and each
   manifest was packed at the same commit: d636200 (hm, hmdet, hc-101..103), 5a87662 (hc-104..205, hsens), b40814f (hd, R3, R4).
   Every runner-side file is identical from a175625 to HEAD, so this has no effect. Correct the LOG line.
2. **minor.** P9.1 names `g3v2_evaluate.py`, but the gate was computed by `p9_full_cord.py`, which was added after the tag. It
   imports the evaluator's loader and reference values, and its item 1-3 and 5 thresholds are the same (I compared them). The
   gate records no build identity, so I checked it myself: W (1,372,404 pairs) and sizes are identical in run 2's `g3v2` payload,
   the P7 payload and the H-M payload.
3. **minor.** No script under `ledger/` or `scripts/` writes `REGISTRY_BEFORE_FREEZE.json`. My scan reproduces every count in it (55 files, 129,854
   keys, 9 manifests, 11,558 keys, 0 hemilineage). Record the method with the Stage 2 gates.
4. **minor.** The H-S `provenance.json` files hold no input hashes (unit list, motor map, W digest, git head). The tables are
   reproducible (below), but the provenance should stand alone. Nit: `predict_h1.py`'s usage line says "seven" wiring baselines;
   it writes eight.
5. **note.** In the signed and linear H-S arms, d1 is the maximum of signed pool values, so for an inhibitory unit it is the
   least negative pool. This is M4 as written.
6. **note.** The primary groups also hold 7 `efferent ascending` and 6 `Interneuron TBD` neurons, which U3's "every class" covers.
   Birthtime is read from the v1.2.1 annotations while the network is v1.2.3; the two agree on all 13,064 thoracic members.
7. **limit.** A file scan cannot exclude a local run that wrote nothing under `data/ledger`. Other evidence covers this: by code
   reading, the Stage 0 diagnosis stimulates DNg100 only (`diag_v3_tolerance.py`) or nothing (`diag_v3_coupling.py`,
   `diag_v3_linear.py`), and `build_hm` has the freeze guard in every committed version.

## What I checked

- **Units.** I recomputed `UNITS_v1.csv` from `full_cord().table` and the birthtime: 43 units (44 thoracic labels minus `TBD`),
  all 16 columns equal. The rulebook's U2 table equals the CSV.
- **Groups.** My own member lists equal `groups_h1.members` for 8 variants x 43 units, and the sizes equal the CSV.
- **H-M jobs.** 688 = 43 x seeds 0..15, and the keys equal the manifest. Every `members` equals `members(..., "primary")`.
  - The jobs match P1: kind `group_v3`, T = 1.0 s, the screen (128, 10 runs, 100/7667/1022, 100 Hz, 0.01 Hz after 0.25 s,
    prominence 0.05), and extras `legs` + `mn` only.
  - The payload's W, sizes, readout, leg masks, E1 and `mn` order equal `full_cord()`, `leg_setup` and the motor-map order.
- **Sensitivity jobs.** 1,072 = 268 groups x seeds 0..3. These are exactly the `run` groups of `gha3.sens_plan` and of my
  independent plan (empty: post 5, T1 1, T2 1, T3 3, L 2, R 2). Every member list is equal.
- **Determinism sample.** The 50 keys equal `default_rng(20261312).choice(sorted H-M keys, 50, replace=False)`, and the specs
  equal H-M's. The members of the H-D (1,376) and H-C (10 x 172) jobs equal the primary groups too.
- **Motor map.**
  - The 732 rows are every motor neuron (bodyId and subclass match); the jump MNs (TTMn 2, STTMm 4) are in `middle_leg` and
    `jump`; neck and `xm` MNs are in no pool.
  - I rebuilt the pools from body part, type and the authors' `motor module` column: 702/141/125/131/6/60/24/16/229, and per-leg
    flexor/extensor 26/10, 25/10, 21/7, 20/7, 19/8, 20/8. These equal both `pool_masks` and the `pools` column.
  - Leg MNs sit in their leg's segment on the soma side; the per-leg rhythm masks equal the map's 329 module-labelled MNs.
- **Rules.** `replicate_readout`, `replicate_dims`, `arm_tables`, `hs_values`, `hs_linear_values` and the `predict_h1.py`
  commands follow U4, M2-M4, P3 and P10 as written (`mn_active` = peak > 0.01 Hz after 0.25 s; never accepted ->
  `final_run_extras`; leg score 0 with no active MN). My own M2-M3 code reproduces `arm_tables` exactly on the P7 allowed groups,
  including 2 saturating and 1 too-weak replicate.
- **H-S tables.**
  - I recomputed the 7 matrix-power arms for all 43 units from W or |W| with my own pools. The largest relative difference is
    5e-10 (the CSV's precision). I also worked 09A and 15B for k1-signed by hand.
  - H-S-lin: my own gains (equal to `mean_neuron_params`), Wb = 0.03 W, and a different LU ordering (MMD_AT_PLUS_A) plus one
    refinement step. The largest difference is 4e-10 (03A, 09A and 15B inspected) and the residual 2e-13.
  - Unit order and `n_members` are correct, and d5, d6 and d7' are 0.
- **Gates.**
  - Trust: I re-checked 100/100 digests against their origin logs.
  - P7: I re-checked 16/16 digests (`g3v2item5` = `p7reg`); 54/54 jobs returned, 0 errors. Between the P7 commit and the H-M
    tags, the runner-side code changed only in `groups_h1`, `labels_h1` and `scoring_h1`, none of which the job path imports.
    The runner, workflow, jobs, screens, legs, `src/brainir` and the pins are unchanged, so the regression covers the H-M code.
  - P9.1: items 1-3 and 5 pass.
- **Freeze.**
  - `ledger-prereg-v3` (lightweight, on origin) is a175625, committed 10:23:18Z. The 14 hemilineage campaigns were packed
    10:24:42-10:28:57Z at its descendants, and the first hemilineage Actions run was created at 10:24:52Z.
  - The 9 pre-freeze manifests and the 55 `results.pkl` files (`sources*` skipped, keys only) hold no hemilineage-like key
    (unit names, components, `NN[ABX]` tokens, `H-` prefixes), and no log was modified after the freeze.
  - The largest single-unit share in a P7 random group is 0.10, and none equals a unit group. No commit holds a
    `predictions_h1` or `arms_h1` path.
  - Prediction code, units, motor map and rulebook are identical a175625..HEAD; `lock3.py check` on the prereg lock: 142 files,
    0 changed.
- **Not opened.** Nothing under `labels*`, `sources*`, `research/literature/`, `results/` or an HL_OUTCOME_LOCATIONS entry; no
  hemilineage result.
