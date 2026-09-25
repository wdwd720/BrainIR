# Re-ranking of Level B rounds 1-3 under the benchmark version 3 profile rules (ANSWER-BEARING)

For the record only: the rounds' decisions stand as made (PROTOCOL.md section 10.1). Recomputed exactly from the stored
per-system records: S3 = max(0, upper CI of the D micro-gain), S5 = min(R^2 true <- model, R^2 model <- true), S6 = exact point k.

Not recomputable from the records:

- S2 keeps the version 2 value (the version 3 observed-target C needs per-pair data that the records do not keep)
- the version 3 Markov / rollout-consistency check is not in the records: the comparator rule is applied without it

## r1 (19 candidates, 15 compressible systems)

| candidate | v2 mean rank | v2 P(rank 1) | v3 mean rank | v3 P(rank 1) | S3 v2 -> v3 | S5 v2 -> v3 | S6 v2 -> v3 |
|---|---|---|---|---|---|---|---|
| ks_sindy | 6.29 | 0.52 | 4.43 | 0.45 | -0.018 -> 0.018 | 0.995 -> 0.989 | 0.80 -> 0.67 |
| lin_falds | 6.07 | 0.08 | 5.57 | 0.12 | -0.018 -> 0.058 | 0.997 -> 0.993 | 0.60 -> 0.53 |
| nn_closed | 5.57 | 0.28 | 5.57 | 0.27 | -0.049 -> 0.056 | 0.997 -> 0.991 | 1.00 -> 0.80 |
| lin_subspace | 6.57 | 0.04 | 6.00 | 0.08 | -0.075 -> 0.000 | 0.996 -> 0.990 | 0.73 -> 0.73 |
| lin_balanced | 7.07 | 0.04 | 7.00 | 0.03 | -0.059 -> 0.039 | 0.998 -> 0.997 | 0.67 -> 0.53 |
| lin_dmdc | 8.36 | 0.01 | 8.36 | 0.01 | -0.062 -> 0.057 | 0.995 -> 0.991 | 0.47 -> 0.33 |
| nn_aelin | 8.93 | 0.02 | 8.57 | 0.03 | -0.084 -> 0.031 | 0.989 -> 0.983 | 0.93 -> 0.73 |
| ks_edmd | 8.79 | 0.00 | 9.14 | 0.00 | -0.057 -> 0.056 | 0.984 -> 0.956 | 0.80 -> 0.53 |
| cb_cegar | 9.50 | 0.00 | 9.71 | 0.00 | -0.009 -> 0.082 | 0.992 -> 0.975 | 0.53 -> 0.33 |
| cb_psr | 10.36 | 0.00 | 10.00 | 0.01 | -0.051 -> 0.065 | 0.992 -> 0.984 | 0.53 -> 0.40 |
| cb_interchange | 10.43 | 0.00 | 10.07 | 0.00 | -0.053 -> 0.077 | 0.989 -> 0.985 | 0.53 -> 0.40 |
| ks_kae | 11.07 | 0.00 | 10.43 | 0.00 | -0.024 -> 0.052 | 0.993 -> 0.987 | 0.73 -> 0.47 |
| nn_seqbottleneck | 10.86 | 0.00 | 10.93 | 0.00 | -0.012 -> 0.079 | 0.995 -> 0.988 | 0.87 -> 0.67 |
| lin_pcadyn | 10.43 | 0.00 | 11.14 | 0.00 | -0.062 -> 0.001 | 0.995 -> 0.980 | 0.27 -> 0.20 |
| ks_hankel | 9.21 | 0.01 | 11.36 | 0.00 | -0.007 -> 0.112 | 0.996 -> 0.962 | 0.67 -> 0.40 |
| sd_shared | 13.14 | 0.00 | 11.93 | 0.00 | -0.001 -> 0.091 | 0.997 -> 0.994 | 0.60 -> 0.60 |
| sd_lowrank | 14.64 | 0.00 | 15.79 | 0.00 | -0.012 -> 0.099 | 0.995 -> 0.933 | 0.47 -> 0.40 |
| nn_rssm | 15.79 | 0.00 | 16.21 | 0.00 | 0.023 -> 0.117 | 0.992 -> 0.918 | 0.00 -> 0.00 |
| nn_pred_bottleneck | 16.93 | 0.00 | 17.79 | 0.00 | 0.001 -> 0.103 | 0.994 -> 0.483 | 0.00 -> 0.00 |

- Version 3 selection rule: **nn_closed** (P(rank 1) of the top candidate 0.451 < 0.5: parsimony (lowest median k) within the tie set (P(rank 1) >= 0.1)).
- Version 3 comparator rule (without the Markov criterion): **lin_falds** (best eligible baseline on S1-S5, ranked among the eligible baselines only (Markov criterion not applied: the records predate the version 3 check)).
- Descriptive ranking on S1-S5 only: lin_subspace, lin_falds, ks_sindy, lin_balanced, nn_closed, lin_dmdc, cb_interchange, lin_pcadyn, ks_edmd, cb_cegar, ks_kae, nn_aelin, cb_psr, nn_seqbottleneck, ks_hankel, sd_shared, sd_lowrank, nn_rssm, nn_pred_bottleneck.

## r2 (10 candidates, 46 compressible systems)

| candidate | v2 mean rank | v2 P(rank 1) | v3 mean rank | v3 P(rank 1) | S3 v2 -> v3 | S5 v2 -> v3 | S6 v2 -> v3 |
|---|---|---|---|---|---|---|---|
| lin_subspace | 3.31 | 0.57 | 3.12 | 0.69 | -0.083 -> 0.008 | 0.996 -> 0.990 | 0.67 -> 0.63 |
| lin_dmdc | 3.94 | 0.10 | 3.94 | 0.10 | -0.049 -> 0.065 | 0.995 -> 0.993 | 0.57 -> 0.37 |
| lin_falds | 3.69 | 0.15 | 3.94 | 0.09 | -0.005 -> 0.068 | 0.997 -> 0.985 | 0.59 -> 0.48 |
| nn_aelin | 4.38 | 0.03 | 4.12 | 0.03 | -0.071 -> 0.045 | 0.991 -> 0.981 | 0.78 -> 0.63 |
| nn_closed | 3.88 | 0.07 | 4.19 | 0.06 | -0.008 -> 0.089 | 0.991 -> 0.978 | 0.78 -> 0.57 |
| ks_sindy | 4.12 | 0.07 | 4.25 | 0.03 | -0.035 -> 0.045 | 0.995 -> 0.946 | 0.65 -> 0.50 |
| lin_balanced | 4.69 | 0.01 | 4.44 | 0.01 | -0.046 -> 0.060 | 0.997 -> 0.993 | 0.54 -> 0.41 |

- Version 3 selection rule: **lin_subspace** (top candidate with P(rank 1) = 0.685 >= 0.5).
- Version 3 comparator rule (without the Markov criterion): **lin_dmdc** (best eligible baseline on S1-S5, ranked among the eligible baselines only (Markov criterion not applied: the records predate the version 3 check)).
- Descriptive ranking on S1-S5 only: lin_subspace, lin_dmdc, ks_sindy, lin_falds, lin_balanced, nn_closed, nn_aelin.

## r3 (11 candidates, 46 compressible systems)

| candidate | v2 mean rank | v2 P(rank 1) | v3 mean rank | v3 P(rank 1) | S3 v2 -> v3 | S5 v2 -> v3 | S6 v2 -> v3 |
|---|---|---|---|---|---|---|---|
| lin_subspace | 3.88 | 0.25 | 3.56 | 0.52 | -0.083 -> 0.008 | 0.996 -> 0.990 | 0.67 -> 0.63 |
| brainir_state_v1 | 3.62 | 0.56 | 4.00 | 0.24 | -0.037 -> 0.057 | 0.995 -> 0.960 | 0.78 -> 0.54 |
| lin_falds | 4.12 | 0.08 | 4.38 | 0.09 | -0.005 -> 0.068 | 0.997 -> 0.985 | 0.59 -> 0.48 |
| lin_dmdc | 4.50 | 0.06 | 4.50 | 0.07 | -0.049 -> 0.065 | 0.995 -> 0.993 | 0.57 -> 0.37 |
| nn_aelin | 5.00 | 0.01 | 4.56 | 0.02 | -0.071 -> 0.045 | 0.991 -> 0.981 | 0.78 -> 0.63 |
| nn_closed | 4.62 | 0.04 | 4.75 | 0.04 | -0.008 -> 0.089 | 0.991 -> 0.978 | 0.78 -> 0.57 |
| ks_sindy | 4.88 | 0.00 | 5.00 | 0.00 | -0.035 -> 0.045 | 0.995 -> 0.946 | 0.65 -> 0.50 |
| lin_balanced | 5.38 | 0.00 | 5.25 | 0.01 | -0.046 -> 0.060 | 0.997 -> 0.993 | 0.54 -> 0.41 |

- Version 3 selection rule: **lin_subspace** (top candidate with P(rank 1) = 0.523 >= 0.5).
- Version 3 comparator rule (without the Markov criterion): **lin_dmdc** (best eligible baseline on S1-S5, ranked among the eligible baselines only (Markov criterion not applied: the records predate the version 3 check)).
- Descriptive ranking on S1-S5 only: lin_subspace, brainir_state_v1, lin_dmdc, lin_falds, ks_sindy, lin_balanced, nn_closed, nn_aelin.

