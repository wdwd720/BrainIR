# Tournament feedback (aggregate held-out profiles; PROTOCOL.md section 9)

Every value is an aggregate over held-out synthetic systems you have never seen. Per-system results are not released.

- **S1_A_over_full**: median multi-step prediction error relative to the full-state ceiling (lower is better; 1 = ceiling)
- **S2_C_heldout**: median effect error on held-out intervention types / targets (lower is better; 1 = predicting no effect)
- **S3_D_micro_gain**: median closure gain from discarded microstate (lower is better; ~0 = closed)
- **S4_E_ratio**: median microstate-equivalence ratio, latent-matched vs random pairs (lower is better)
- **S5_K_r2_rff**: median recovery of the true latent from z (R^2; higher is better)
- **S6_dim_rate**: fraction of compressible systems where the selected dimension equals the true one or lies in the reported range
- **S7_abstention**: abstention quality: mean of recall on non-compressible controls and 1 - false-alarm rate (higher is better)
- **S8_sharing_correct**: balanced accuracy of the sharing verdicts: mean of the correct rates over the implementation groups (supported) and over the unrelated pairs (rejected)
- Profiles (benchmark version 2): S1-S6 are taken over the same fixed list of compressible held-out systems for every candidate; a failed fit or evaluation counts as the worst value. S4 leaves out systems where the candidate's E is untestable. Ranks average ties and do not depend on the order of the candidates; a component that is missing for every candidate (S8 in the pilot, which has no shared fits) is left out.

## Round r1 (heldout)

| candidate | eligible | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | mean rank | verdicts (compressible systems) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nn_closed | True | 1.03 | 0.743 | -0.0487 | 0.00249 | 0.997 | 1 | 0.933 | - | 5.57 | compact causal state discovered: 4, not supported: 4, partially supported: 7 |
| lin_falds | True | 1.04 | 0.558 | -0.0185 | 0.00231 | 0.997 | 0.6 | 0.933 | - | 6.07 | compact causal state discovered: 5, not supported: 7, partially supported: 3 |
| ks_sindy | True | 0.96 | 0.345 | -0.0181 | 0.00371 | 0.995 | 0.8 | 0.967 | - | 6.29 | compact causal state discovered: 7, not supported: 3, partially supported: 5 |
| lin_subspace | True | 1.04 | 0.621 | -0.0751 | 0.00217 | 0.996 | 0.733 | 0.467 | - | 6.57 | compact causal state discovered: 4, not supported: 5, partially supported: 6 |
| lin_balanced | True | 1.06 | 0.652 | -0.059 | 0.00227 | 0.998 | 0.667 | 0.5 | - | 7.07 | compact causal state discovered: 2, compact causal state discovered (microstate equivalence untestable): 1, not supported: 6, partially supported: 6 |
| lin_dmdc | True | 1.08 | 0.614 | -0.0617 | 0.00202 | 0.995 | 0.467 | 0.867 | - | 8.36 | compact causal state discovered: 3, not supported: 7, partially supported: 5 |
| ks_edmd | True | 1.03 | 0.754 | -0.0574 | 0.00325 | 0.984 | 0.8 | 0.933 | - | 8.79 | compact causal state discovered: 3, not supported: 6, partially supported: 6 |
| nn_aelin | True | 1.2 | 0.862 | -0.084 | 0.00316 | 0.989 | 0.933 | 0.967 | - | 8.93 | compact causal state discovered: 2, not supported: 6, partially supported: 7 |
| ks_hankel | True | 1.19 | 0.592 | -0.0068 | 0.00302 | 0.996 | 0.667 | 0.933 | - | 9.21 | compact causal state discovered: 2, compact causal state discovered (microstate equivalence untestable): 1, not supported: 6, partially supported: 6 |
| cb_cegar | True | 1.05 | 0.696 | -0.00853 | 0.00288 | 0.992 | 0.533 | 0.967 | - | 9.5 | compact causal state discovered: 6, not supported: 4, partially supported: 5 |
| cb_psr | True | 1.07 | 0.739 | -0.0512 | 0.00379 | 0.992 | 0.533 | 0.967 | - | 10.4 | compact causal state discovered: 5, not supported: 4, partially supported: 6 |
| lin_pcadyn | True | 1.08 | 0.609 | -0.0618 | 0.0043 | 0.995 | 0.267 | 0.8 | - | 10.4 | compact causal state discovered: 3, not supported: 7, partially supported: 5 |
| cb_interchange | True | 1.06 | 0.58 | -0.0533 | 0.0038 | 0.989 | 0.533 | 0.867 | - | 10.4 | compact causal state discovered: 5, not supported: 5, partially supported: 5 |
| nn_seqbottleneck | True | 1.11 | 0.936 | -0.0115 | 0.003 | 0.995 | 0.867 | 0.5 | - | 10.9 | compact causal state discovered: 2, not supported: 4, partially supported: 9 |
| ks_kae | True | 1.01 | 0.97 | -0.0239 | 0.00518 | 0.993 | 0.733 | 0.867 | - | 11.1 | not supported: 7, partially supported: 8 |
| sd_shared | True | 1.1 | 0.86 | -0.000794 | 0.00511 | 0.997 | 0.6 | 0.467 | - | 13.1 | compact causal state discovered: 1, not supported: 5, partially supported: 9 |
| sd_lowrank | True | 2.41 | 0.961 | -0.0125 | 0.00332 | 0.995 | 0.467 | 0.433 | - | 14.6 | compact causal state discovered: 1, not supported: 10, partially supported: 4 |
| nn_rssm | True | 1.34 | 1.1 | 0.0226 | 0.00392 | 0.992 | 0 | 0.933 | - | 15.8 | not supported: 6, partially supported: 9 |
| nn_pred_bottleneck | True | 1.24 | 1.59 | 0.000737 | - | 0.994 | 0 | 0.5 | - | 16.9 | not supported: 8, partially supported: 7 |

## Round r2 (heldout)

| candidate | eligible | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | mean rank | verdicts (compressible systems) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lin_subspace | True | 0.999 | 0.564 | -0.0827 | 0.00175 | 0.996 | 0.674 | 0.457 | 0.5 | 3.31 | compact causal state discovered: 11, compact causal state discovered (microstate equivalence untestable): 1, not supported: 19, partially supported: 15 |
| lin_falds | True | 1.16 | 0.55 | -0.0052 | 0.00105 | 0.997 | 0.587 | 0.891 | 0.5 | 3.69 | compact causal state discovered: 7, compact causal state discovered (microstate equivalence untestable): 1, not supported: 26, partially supported: 12 |
| nn_closed | True | 0.938 | 0.746 | -0.00831 | 0.00226 | 0.991 | 0.783 | 0.978 | 0.5 | 3.88 | compact causal state discovered: 8, not supported: 11, partially supported: 27 |
| lin_dmdc | True | 1.08 | 0.613 | -0.0488 | 0.00159 | 0.995 | 0.565 | 0.902 | 0.5 | 3.94 | compact causal state discovered: 9, not supported: 26, partially supported: 11 |
| ks_sindy | True | 0.969 | 0.585 | -0.0354 | 0.00173 | 0.995 | 0.652 | 0.696 | 0.167 | 4.12 | compact causal state discovered: 9, compact causal state discovered (microstate equivalence untestable): 1, not supported: 14, partially supported: 22 |
| nn_aelin | True | 1.09 | 0.983 | -0.071 | 0.00277 | 0.991 | 0.783 | 0.989 | 0.5 | 4.38 | compact causal state discovered: 3, not supported: 19, partially supported: 24 |
| lin_balanced | True | 1.03 | 0.68 | -0.0459 | 0.00236 | 0.997 | 0.543 | 0.5 | 0.5 | 4.69 | compact causal state discovered: 6, compact causal state discovered (microstate equivalence untestable): 4, not supported: 16, partially supported: 20 |
| ks_edmd | False | 1 | 0.745 | -0.0753 | 0.00292 | 0.99 | 0.696 | 0.717 | 0 | - | compact causal state discovered: 7, not supported: 19, partially supported: 20 |
| ks_hankel | False | 1.14 | 0.598 | -0.00314 | 0.00169 | 0.995 | 0.63 | 0.957 | 0 | - | compact causal state discovered: 9, compact causal state discovered (microstate equivalence untestable): 1, not supported: 24, partially supported: 12 |
| cb_cegar | False | 1.03 | 0.625 | -0.0619 | 0.00233 | 0.993 | 0.391 | 0.957 | 0 | - | compact causal state discovered: 12, compact causal state discovered (microstate equivalence untestable): 1, not supported: 19, partially supported: 14 |

