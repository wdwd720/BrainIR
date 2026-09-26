# Phase 3 compute summary (goal4 sections 58-59)

Generated 2026-09-26T12:02:08Z by scripts/p3/compute_summary.py.
Modal list prices: $0.192 per physical core-hour, $0.024 per GiB-hour; containers 2 cores / 6 GiB.

**Modal total: about $271.9** over 20486 container calls (405.96 container-hours).

| task | backend | containers | container-s | wall-s | ~USD | source |
|---|---|---|---|---|---|---|
| calibration smoke, 3 dev systems (first attempt crash-looped: module-level function pickled by reference; 0 containers r | Modal CPU | 0 | 0 | - | 0.00 | COSTS_LEDGER.md |
| calibration smoke, 3 dev systems (v2 code; Linux = Windows to ~1e-9) | Modal CPU | 3 | 960 | - | 0.14 | COSTS_LEDGER.md |
| CALIBRATION v2, 45 dev systems | Modal CPU | 45 | 14303 | - | 2.10 | COSTS_LEDGER.md |
| heldout suite extract (tar upload) | Modal CPU | 2 | 57 | - | 0.01 | COSTS_LEDGER.md |
| heldout reference controls (k-independent + k = 1), 48 systems | Modal CPU | 48 | 9242 | - | 1.36 | COSTS_LEDGER.md |
| final suite extract, fit views, review G suite upload | Modal CPU | 6 | 200 | - | 0.03 | COSTS_LEDGER.md |
| review G trap suite, round-2 top five | Modal CPU | 150 | 11386 | - | 1.67 | COSTS_LEDGER.md |
| review G trap suite, brainir_state_v1 | Modal CPU | 30 | 1261 | - | 0.18 | COSTS_LEDGER.md |
| CALIBRATION v3, 45 dev systems (benchmark v3; 486 s wall) | Modal CPU | 45 | 13417 | - | 1.97 | COSTS_LEDGER.md |
| kick-clip lists staged on the eval volume (3 files) | Modal CPU | 3 | 0 | - | 0.00 | COSTS_LEDGER.md |
| calibration v3 re-runs 2 and 3 (worker crashes; not used: the calibration of record is run 4) | Modal CPU | 94 | 26700 | - | 3.92 | COSTS_LEDGER.md |
| hidden-data generator: Modal pipeline smoke tests on PUBLIC protocols (4 runs incl. 2 failed attempts) | Modal CPU | 40 | 600 | - | 0.10 | COSTS_LEDGER.md |
| numerics-pinning crash experiment (4 variants x 4 systems x 5) | Modal CPU | 76 | 22484 | - | 3.30 | COSTS_LEDGER.md |
| fork A: Level C backend staging and equivalence checks; fork C: counterexample / ablation smoke tests | Modal CPU | 100 | 2300 | - | 0.33 | COSTS_LEDGER.md |
| remote runner (`devrun.py`) for the composer's development experiments: 190 jobs in classes small (2 CPU / 8 GiB, 72), m | Modal CPU | 192 | 48200 | - | 14.34 | COSTS_LEDGER.md |
| post-lock verify-public of the ungated Modal generator path (13 of 20 public records not bit-identical) | Modal CPU | 20 | 154 | - | 0.02 | COSTS_LEDGER.md |
| gated verify-public, exit mode (60 of 60 identical; throttled scale-up) and refuse mode (60 of 60; 99 refusals), 32 GiB | Modal CPU | 219 | 2053 | - | 0.66 | COSTS_LEDGER.md |
| HIDDEN real-data generation, host-gated (420 simulation batches, 60 microstate batches, assembly; 32 GiB, about 30 conta | Modal CPU | 2500 | 36000 | - | 11.50 | COSTS_LEDGER.md |
| quota probe (sleeper containers; the workspace ran 99 at once) | Modal CPU | 200 | 15000 | - | 0.80 | COSTS_LEDGER.md |
| hidden data finish (frozen tar, remote hashes) and re-simulation determinism check (83 protocols) | Modal CPU | 50 | 685 | - | 0.10 | COSTS_LEDGER.md |
| fast Level C dispatcher validations on public data (frozen vs fast; gated repeats; 16 fits) | Modal CPU | 60 | 2600 | - | 0.60 | COSTS_LEDGER.md |
| correction for the real Level C run: its record prices every container at 2 cores / 6 GiB; at the actual class sizes (4  | Modal CPU | 0 | 0 | - | 31.00 | COSTS_LEDGER.md |
| tournament:final_b_brainir_state_v1 | Modal CPU | 235 | 30795 | 3023.7 | 5.75 | research/phase3/tournament/final_b_brainir_state_v1/modal_costs.json |
| tournament:final_b_ks_hankel | Modal CPU | 235 | 11004 | 2537.1 | 2.05 | research/phase3/tournament/final_b_ks_hankel/modal_costs.json |
| tournament:final_b_ks_hankel_t | Modal CPU | 217 | 5274 | 2242.7 | 0.98 | research/phase3/tournament/final_b_ks_hankel_t/modal_costs.json |
| tournament:final_b_lin_dmdc | Modal CPU | 282 | 14755 | 3002.8 | 2.75 | research/phase3/tournament/final_b_lin_dmdc/modal_costs.json |
| tournament:final_b_lin_dmdc_t | Modal CPU | 282 | 16165 | 2022.4 | 3.02 | research/phase3/tournament/final_b_lin_dmdc_t/modal_costs.json |
| tournament:final_b_lin_falds | Modal CPU | 252 | 11886 | 2777.0 | 2.22 | research/phase3/tournament/final_b_lin_falds/modal_costs.json |
| tournament:final_b_lin_falds_t | Modal CPU | 247 | 36860 | 3577.9 | 6.88 | research/phase3/tournament/final_b_lin_falds_t/modal_costs.json |
| tournament:final_b_lin_pcadyn | Modal CPU | 284 | 16427 | 2894.5 | 3.07 | research/phase3/tournament/final_b_lin_pcadyn/modal_costs.json |
| tournament:final_b_lin_pcadyn_t | Modal CPU | 252 | 7897 | 2861.7 | 1.48 | research/phase3/tournament/final_b_lin_pcadyn_t/modal_costs.json |
| tournament:final_b_nn_aelin | Modal CPU | 230 | 39876 | 3937.8 | 7.44 | research/phase3/tournament/final_b_nn_aelin/modal_costs.json |
| tournament:final_b_nn_aelin_t | Modal CPU | 219 | 41323 | 4251.9 | 7.71 | research/phase3/tournament/final_b_nn_aelin_t/modal_costs.json |
| tournament:final_b_nn_rssm | Modal CPU | 249 | 38146 | 3973.7 | 7.12 | research/phase3/tournament/final_b_nn_rssm/modal_costs.json |
| tournament:final_b_nn_seqbottleneck | Modal CPU | 203 | 23226 | 3010.7 | 4.33 | research/phase3/tournament/final_b_nn_seqbottleneck/modal_costs.json |
| tournament:r1_cb | Modal CPU | 113 | 9616 | 1454.6 | 1.41 | research/phase3/tournament/r1_cb/modal_costs.json |
| tournament:r1_ks | Modal CPU | 150 | 12039 | 1944.5 | 1.77 | research/phase3/tournament/r1_ks/modal_costs.json |
| tournament:r1_lin | Modal CPU | 193 | 13045 | 2128.6 | 1.92 | research/phase3/tournament/r1_lin/modal_costs.json |
| tournament:r1_nn | Modal CPU | 196 | 33351 | 4411.1 | 4.89 | research/phase3/tournament/r1_nn/modal_costs.json |
| tournament:r1_sd | Modal CPU | 75 | 8677 | 1210.3 | 1.27 | research/phase3/tournament/r1_sd/modal_costs.json |
| tournament:r2_cb_cegar | Modal CPU | 206 | 12944 | 1798.9 | 1.90 | research/phase3/tournament/r2_cb_cegar/modal_costs.json |
| tournament:r2_ks_edmd | Modal CPU | 195 | 10788 | 1900.9 | 1.58 | research/phase3/tournament/r2_ks_edmd/modal_costs.json |
| tournament:r2_ks_hankel | Modal CPU | 213 | 8701 | 1406.6 | 1.28 | research/phase3/tournament/r2_ks_hankel/modal_costs.json |
| tournament:r2_ks_sindy | Modal CPU | 244 | 17484 | 2048.6 | 2.56 | research/phase3/tournament/r2_ks_sindy/modal_costs.json |
| tournament:r2_lin_balanced | Modal CPU | 229 | 16956 | 2468.5 | 2.49 | research/phase3/tournament/r2_lin_balanced/modal_costs.json |
| tournament:r2_lin_dmdc | Modal CPU | 239 | 7772 | 1889.1 | 1.14 | research/phase3/tournament/r2_lin_dmdc/modal_costs.json |
| tournament:r2_lin_falds | Modal CPU | 260 | 16655 | 1636.3 | 2.44 | research/phase3/tournament/r2_lin_falds/modal_costs.json |
| tournament:r2_lin_subspace | Modal CPU | 236 | 8732 | 1875.2 | 1.28 | research/phase3/tournament/r2_lin_subspace/modal_costs.json |
| tournament:r2_nn_aelin | Modal CPU | 221 | 45141 | 4187.9 | 6.62 | research/phase3/tournament/r2_nn_aelin/modal_costs.json |
| tournament:r2_nn_closed | Modal CPU | 233 | 34545 | 2287.8 | 5.07 | research/phase3/tournament/r2_nn_closed/modal_costs.json |
| tournament:r3_brainir_state_v1 | Modal CPU | 215 | 13972 | 1091.3 | 2.05 | research/phase3/tournament/r3_brainir_state_v1/modal_costs.json |
| tournament:r3v3_brainir_state_v1 | Modal CPU | 214 | 25204 | 1292.1 | 3.70 | research/phase3/tournament/r3v3_brainir_state_v1/modal_costs.json |
| tournament:r3v3_cb_cegar | Modal CPU | 114 | 3068 | 669.4 | 0.45 | research/phase3/tournament/r3v3_cb_cegar/modal_costs.json |
| tournament:r3v3_ks_edmd | Modal CPU | 126 | 1976 | 597.6 | 0.29 | research/phase3/tournament/r3v3_ks_edmd/modal_costs.json |
| tournament:r3v3_ks_hankel | Modal CPU | 141 | 1988 | 582.5 | 0.29 | research/phase3/tournament/r3v3_ks_hankel/modal_costs.json |
| tournament:r3v3_ks_hankel_t | Modal CPU | 180 | 2620 | 577.2 | 0.38 | research/phase3/tournament/r3v3_ks_hankel_t/modal_costs.json |
| tournament:r3v3_ks_sindy | Modal CPU | 148 | 2944 | 625.2 | 0.43 | research/phase3/tournament/r3v3_ks_sindy/modal_costs.json |
| tournament:r3v3_lin_balanced | Modal CPU | 159 | 3367 | 707.3 | 0.49 | research/phase3/tournament/r3v3_lin_balanced/modal_costs.json |
| tournament:r3v3_lin_dmdc | Modal CPU | 126 | 2773 | 203.5 | 0.41 | research/phase3/tournament/r3v3_lin_dmdc/modal_costs.json |
| tournament:r3v3_lin_dmdc_t | Modal CPU | 219 | 4466 | 758.8 | 0.65 | research/phase3/tournament/r3v3_lin_dmdc_t/modal_costs.json |
| tournament:r3v3_lin_falds | Modal CPU | 152 | 2880 | 598.2 | 0.42 | research/phase3/tournament/r3v3_lin_falds/modal_costs.json |
| tournament:r3v3_lin_falds_t | Modal CPU | 147 | 3839 | 737.3 | 0.56 | research/phase3/tournament/r3v3_lin_falds_t/modal_costs.json |
| tournament:r3v3_lin_pcadyn | Modal CPU | 231 | 4960 | 806.1 | 0.73 | research/phase3/tournament/r3v3_lin_pcadyn/modal_costs.json |
| tournament:r3v3_lin_pcadyn_t | Modal CPU | 218 | 5330 | 793.5 | 0.78 | research/phase3/tournament/r3v3_lin_pcadyn_t/modal_costs.json |
| tournament:r3v3_lin_subspace | Modal CPU | 164 | 9432 | 353.3 | 1.38 | research/phase3/tournament/r3v3_lin_subspace/modal_costs.json |
| tournament:r3v3_nn_aelin | Modal CPU | 116 | 3728 | 634.8 | 0.55 | research/phase3/tournament/r3v3_nn_aelin/modal_costs.json |
| tournament:r3v3_nn_aelin_t | Modal CPU | 219 | 48130 | 3167.3 | 7.06 | research/phase3/tournament/r3v3_nn_aelin_t/modal_costs.json |
| tournament:r3v3_nn_closed | Modal CPU | 140 | 4379 | 559.1 | 0.64 | research/phase3/tournament/r3v3_nn_closed/modal_costs.json |
| tournament:r3v3_nn_rssm | Modal CPU | 230 | 26972 | 2367.4 | 3.96 | research/phase3/tournament/r3v3_nn_rssm/modal_costs.json |
| tournament:r3v3_nn_seqbottleneck | Modal CPU | 178 | 17316 | 1891.9 | 2.54 | research/phase3/tournament/r3v3_nn_seqbottleneck/modal_costs.json |
| tournament:smoke_modal_dev | Modal CPU | 467 | 22758 | 1088.7 | 3.34 | research/phase3/tournament/smoke_modal_dev/modal_costs.json |
| ablations:ablations_dev | Modal CPU | 1872 | 163396 | - | 23.96 | research/phase3/ablations/ablations_dev/modal_costs.json |
| ablations:ablations_final | Modal CPU | 1746 | 189743 | - | 27.83 | research/phase3/ablations/ablations_final/modal_costs.json |
| ablations:ablations_smoke_dev | Modal CPU | 6 | 336 | - | 0.05 | research/phase3/ablations/ablations_smoke_dev/modal_costs.json |
| counterexamples:final_brainir_state_v1_effect | Modal CPU | 576 | 8965 | 1432.2 | 1.31 | research/phase3/counterexamples/final_brainir_state_v1_effect/modal_costs.json |
| counterexamples:final_brainir_state_v1_post | Modal CPU | 576 | 6126 | 439.3 | 0.90 | research/phase3/counterexamples/final_brainir_state_v1_post/modal_costs.json |
| counterexamples:final_lin_dmdc_t_effect | Modal CPU | 576 | 8785 | 1423.8 | 1.29 | research/phase3/counterexamples/final_lin_dmdc_t_effect/modal_costs.json |
| counterexamples:final_lin_dmdc_t_post | Modal CPU | 576 | 6384 | 470.7 | 0.94 | research/phase3/counterexamples/final_lin_dmdc_t_post/modal_costs.json |
| counterexamples:real_public_brainir_state_v1_effect | Modal CPU | 120 | 15334 | 1085.5 | 3.27 | research/phase3/counterexamples/real_public_brainir_state_v1_effect/modal_costs.json |
| counterexamples:real_public_lin_dmdc_t_effect | Modal CPU | 120 | 16683 | 1209.5 | 3.56 | research/phase3/counterexamples/real_public_lin_dmdc_t_effect/modal_costs.json |
| level_c:01 | Modal CPU | 331 | 75784 | 5656.1 | 11.12 | research/phase3/level_c/01/modal_costs.json |
| equivalence:cex_equivalence | Modal CPU | 4 | 44 | 40.4 | 0.01 | research/phase3/postlock_infra/cex_equivalence.json |
| equivalence:cex_equivalence_real | Modal CPU | 4 | 47 | 28.1 | 0.01 | research/phase3/postlock_infra/cex_equivalence_real.json |
| equivalence:sim_equivalence_real_full | Modal CPU | 1 | 30 | 37.3 | 0.00 | research/phase3/postlock_infra/sim_equivalence_real_full.json |
| equivalence:sim_equivalence_real_mech | Modal CPU | 1 | 3 | 12.2 | 0.00 | research/phase3/postlock_infra/sim_equivalence_real_mech.json |

## Simulation cache (content-addressed trajectory store)

| service | trajectories | from cache | hit rate |
|---|---|---|---|
| clean_room | 476 | 0 | 0.0 |

Reference-control cache files per suite: {"dev": 294, "final": 377, "heldout": 841, "review_g": 72}

## Local machine

- **Machine.** Ryzen 9 6900HX, 8 cores / 16 threads, shared by the method agents; wall-clock only.
- **Version 1 calibration.** 75 min on 7 workers (superseded).
- **Suite builds.** Synthetic suites and pools about 40 min; real public data about 40 min on 12 workers.
- **Root test suite.** 834 s under agent load.

## GPUs

not used: all methods are frozen CPU code; GPU use would require changing method code (forbidden by the lock).

## Post-lock correction and billed amount

- Duplicate ledger rows removed (Level B round 1 (pilot, Level B round 2 (10 survivors, Level B round 3 attempt 1): estimate {"usd": 311.57, "container_h": 481.07, "containers": 23704} -> {"usd": 271.9, "container_h": 405.96, "containers": 20486}.
- **Billed by Modal: $136.03** (126 apps, 2026-09-25T03:00:00+00:00 to the hour 2026-09-26T11:00Z; `research/phase3/MODAL_BILLING.md`). The list-price estimate above assumes a 2-core / 6 GiB reservation per container; Modal bills measured usage, including the containers that refused non-gated hosts.
- By stage (billed): {"lock hour 01:00 UTC (end of round 3 + start of the FINAL confirmation)": 11.09, "post-lock (FINAL, hidden data, Level C, sweeps, ablations, reviews G)": 79.8, "pre-lock (development, calibration, Level B)": 45.14}.

## Simulated data

| dataset | trajectories | simulated seconds | restart index entries |
|---|---|---|---|
| real_public | 3005 | 6010.0 | None |
| real_hidden | 3360 | 6720.0 | 1920 |
| synthetic_dev | 4512 | 18048.0 | 6144 |
| synthetic_heldout | 7487 | 29948.0 | 6144 |
| synthetic_final | 10464 | 41856.0 | 6144 |
| synthetic_review_g | 1559 | 6236.0 | 1280 |

## Counterexample protocols

| sweep | protocols scored | searches | wall-s | backend |
|---|---|---|---|---|
| final_brainir_state_v1_effect | 32872 | 576 | 1434.6 | modal |
| final_brainir_state_v1_post | 33827 | 576 | 440.4 | modal |
| final_lin_dmdc_t_effect | 33582 | 576 | 1426.1 | modal |
| final_lin_dmdc_t_post | 34545 | 576 | 471.6 | modal |
| real_hidden_brainir_state_v1_effect | 3126 | 120 | 3340.2 | local |
| real_public_brainir_state_v1_effect | 3153 | 120 | 1086.3 | modal |
| real_public_lin_dmdc_t_effect | 4891 | 120 | 1210.3 | modal |

## Fits

- Level C: brainir_state_v1 {"fit_records": 145, "fit_cpu_h": 31.72, "fit_wall_h": 16.12, "simulator_calls_during_fits": 0}; lin_dmdc_t {"fit_records": 10, "fit_cpu_h": 0.17, "fit_wall_h": 0.17, "simulator_calls_during_fits": 10}; host-gate refusals {'fits:fit_joint': 458, 'fits:fit_full': 1006, 'fits:fit_small': 121, 'real evaluations': 78, 'real references': 38, 'real reproducibility': 12}.
- FINAL confirmation fit wall time: {"brainir_state_v1": {"fit_wall_s_total": 24088.170000000002, "fit_wall_s_median": 190.49}, "lin_dmdc_t": {"fit_wall_s_total": 1835.4499999999998, "fit_wall_s_median": 10.945}}.

## Not recorded

- training samples and optimisation steps per fit (the locked method's fits are closed-form least squares; the joint shared fits use a fixed optimiser schedule; no per-fit step counter is stored)
- local CPU-hours (the local machine was not metered; wall-clock and worker counts are listed under 'local')
