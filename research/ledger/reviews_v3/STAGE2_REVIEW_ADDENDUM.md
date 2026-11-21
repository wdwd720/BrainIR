<!-- Addendum: the Stage 2 reviewer revised its wording after LOCK_predictions_h1.json had hashed STAGE2_REVIEW.md; the locked file is unchanged and this copy holds the revised wording (LOG L90). -->
# Stage 2 review (PREREG v3 P9.5): group builder, motor map, prediction rules, gates, run registry

Verdict: pass with notes

Fresh reviewer, 2026-11-21. First pass (items 1-5) at b40814f, second pass (item 6 and P9.3) at 637ec9e; the tree is clean apart
from this file. **No blocker and no major finding.** The minors below do not touch any prediction. No dimension value or outcome
count is quoted; one unit's tuner-outcome categories are named to show that the last-run path was exercised.

## Findings

1. **minor (documentation; resolved in LOG L80).** LOG L79 said every campaign tag points at d636200. They point at three
   commits, d636200, 5a87662 and b40814f, each with identical runner-side code, so this had no effect.
2. **minor (explained in L80).** P9.1 names `g3v2_evaluate.py`, but the gate was computed by `p9_full_cord.py`, added after the
   tag. It imports the evaluator's loader and reference values, and its item 1-3 and 5 thresholds are the same (I compared them).
   I checked build identity myself: W (1,372,404 pairs) and sizes are identical in run 2's `g3v2` payload, the P7 payload and the
   H-M payload.
3. **minor (addressed in L80).** `REGISTRY_BEFORE_FREEZE.json` had no committed script. One now exists,
   `ledger/scripts/posthoc/registry_scan.py`, which I did not run because it writes a gate file. My own scan reproduces every count
   in the gate.
4. **minor (addressed).** The H-S provenance files held no input hashes. `gates_v3/HS_INPUTS.json` now records them, and its
   eight table hashes match the files I recomputed (unchanged since 02:28 PST, before my recomputation). Nit: `predict_h1.py`'s usage line says "seven" wiring baselines; it writes
   eight.
5. **note.** In the signed and linear H-S arms, d1 is the maximum of signed pool values, so for an inhibitory unit it is the
   least negative pool. This is M4 as written.
6. **note.** The primary groups also hold 7 `efferent ascending` and 6 `Interneuron TBD` neurons, which U3's "every class" covers.
   Birthtime is read from the v1.2.1 annotations while the network is v1.2.3; the two agree on all 13,064 thoracic members.
7. **note.** The H-M chunk 16 was re-run as attempt 2 of the same run (L82-L83). One re-run is within P9's "one re-run of the
   missing jobs". Its 36 records are complete and internally consistent, and one of them is in the determinism sample, where its
   digest is identical. Every H-M and hmdet chunk carries the trust gate's numerics digest, a72e417cfd91.
8. **limit.** A file scan cannot exclude a local run that wrote nothing under `data/ledger`. By code reading, the Stage 0
   diagnosis stimulates DNg100 only or nothing, and `build_hm` has had the freeze guard in every committed version.

## What I checked

- **Units and groups.** I recomputed `UNITS_v1.csv` from `full_cord().table` and the birthtime: 43 units, all 16 columns equal,
  and the rulebook's U2 table equals the CSV. My own member lists equal `groups_h1.members` for 8 variants x 43 units.
- **Job specs.**
  - H-M: 688 jobs = 43 x seeds 0..15. Every `members` equals `members(..., "primary")`, and the config is P1's (kind `group_v3`,
    T = 1 s, screen 128/10 runs/100/7667/1022/100 Hz/0.01 Hz after 0.25 s, extras `legs` + `mn` only). The payload's W, sizes,
    readout, leg masks and `mn` order equal `full_cord()`, `leg_setup` and the motor map.
  - Sensitivity: 1,072 jobs = exactly the `run` groups of `gha3.sens_plan` and of my independent plan, with equal members.
  - The H-D and H-C members also equal the primary groups.
  - The 50 determinism keys equal `default_rng(20261312).choice(sorted H-M keys, 50, replace=False)`, with the same specs.
- **Motor map.**
  - The 732 rows are every motor neuron (bodyId and subclass match); the jump MNs are in `middle_leg` and `jump`.
  - Pools rebuilt from body part, type and the authors' `motor module` column (702/141/125/131/6/60/24/16/229; per-leg
    flexor/extensor 26/10, 25/10, 21/7, 20/7, 19/8, 20/8) equal `pool_masks` and the `pools` column.
  - Leg MNs sit in their leg's segment on the soma side, and the rhythm masks equal the 329 module MNs.
- **Rules.** `replicate_readout`, `replicate_dims`, `arm_tables`, `hs_values`, `hs_linear_values` and `predict_h1.py` follow U4,
  M2-M4, P3 and P10 as written.
- **H-S tables.**
  - The 7 matrix-power arms, recomputed for all 43 units with my own pools: largest relative difference 5e-10, the CSV's
    precision. I also worked 09A and 15B for k1-signed by hand.
  - H-S-lin: my own gains, Wb = 0.03 W, and a different LU ordering plus one refinement step: largest difference 4e-10,
    residual 2e-13.
- **Gates.** Trust: 100/100 digests re-checked. P7: 16/16 re-checked, and the job path is unchanged between P7 and the H-M tags.
  P9.1: items 1-3 and 5 pass.
- **Freeze.**
  - The freeze tag is a175625, committed 10:23:18Z. The 14 hemilineage campaigns were packed 10:24:42-10:28:57Z at its
    descendants, and the first hemilineage Actions run was created at 10:24:52Z.
  - The 9 pre-freeze manifests and the 55 pre-freeze `results.pkl` files (keys only) hold no hemilineage-like key.
  - No P7 random group equals a unit group; the largest single-unit share is 0.10.
  - Prediction tables are first committed in 637ec9e, after the freeze and local only.
  - Prediction code, units, motor map and rulebook are identical a175625..637ec9e, and `lock3.py check` on the prereg lock reports
    142 files, 0 changed.
- **P9.3.**
  - `DETERMINISM_hmdet-run3.json` says 50/50 identical. I recomputed this from the raw logs, reading keys and `digest_v3` only:
    50 records, keys equal to the RNG pick, 0 errors, 50/50 identical.
  - In 49 of the 50 pairs the two runs were on different CPU models.
  - Every `digest_v3` (688 H-M, 50 det) recomputes from its record's content.
- **Item 6 (H-M tables).**
  - Provenance: the `results_sha256`, `keys_sha256` and `digest_v3_sha256` match. The file holds 688 records with unique keys
    equal to the manifest's, 0 errors, and members and seeds equal to the job specs. The motor-neuron order is the map's.
  - Last-run path, for every non-accepted replicate: `final_verdict` agrees with the tuner's thresholds applied to the stored
    `n_active_all`/`n_high_fr`, 10 tuning runs, and the read-out in `final_run_extras`.
  - Read-out consistency, for all 688 records: `mn_active` = peak > 0.01, the active module MNs equal `active_readout_positions`,
    and the per-leg `n_active` agrees.
  - Tables: my independent M2-M3 recomputation reproduces both tables for **all 43 units** (12 dimensions, maximum difference
    5e-11, the CSV's precision) with identical `n_members`, `n_replicates` and outcome counts. It also reproduces all 18,576 rows
    of H-M's `pools.csv`, and H-M-s0-3's `pools.csv` equals the seeds 0-3 subset.
  - Scope: d5, d6 and d7' use the per-leg rhythm score stored in each read-out; I did not recompute it from traces. That score is
    run 1's code, and the P7 digests, which include `legs`, cover it.
  - Named spot units, inspected per replicate: **07B** (too-weak and saturating replicates, so the last-run path is exercised),
    **15B** (a motor unit) and **12A** (drawn with `default_rng(1)`). Each matches all twelve dimensions and the outcome counts.
  - The outcome totals in LOG L84 reproduce for both arms.
- **Not opened.** Nothing under `labels*`, `sources*`, `research/literature/`, `results/` or an HL_OUTCOME_LOCATIONS entry. No
  real-fly hemilineage outcome was read.
