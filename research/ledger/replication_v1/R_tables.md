# Part R: replication across the two flies (POST HOC (PREREG v5 Part R: thresholds and categories chosen after the replication pattern was seen))

Every table and number in this file is post hoc. Source: `research/ledger/pertype_v1/` (LOCK_pertype_v1.json). Rules: PREREG v5 Part R. Driver >= 0.5; replicated = driver in both B1r (or A1) and B2r; near-replicated = driver in one and 0.3-0.5 in the other; single-fly hit = driver in one and < 0.3 in the other; stable non-driver = < 0.05 in both and in all four half-fly screens. The high-confidence version (types whose cross-fly match is high) leads; all types stand beside it.

## B1r (our MANC screen) x B2r (our MaleCNS screen) (post hoc)

| category | high-confidence match | all types | high + medium |
|---|---|---|---|
| replicated | 2 | 3 | 2 |
| near_replicated | 10 | 10 | 10 |
| single_fly_manc | 7 | 10 | 9 |
| single_fly_malecns | 13 | 18 | 14 |
| stable_non_driver | 50 | 83 | 57 |
| neither | 133 | 186 | 150 |

- **replicated** (high): DNb08, DNg100
- **near_replicated** (high): DNa03, DNa07, DNa13, DNp71, DNxl053, DNxl092, DNxl130, DNxn118, DNxn151, DNxn171
- **single_fly_manc** (high): DNg63, DNp02, DNp41, DNp63, DNxl101, DNxl110, DNxl121
- **single_fly_malecns** (high): DNd05, DNfl015, DNfl031, DNfl034, DNg109, DNg13, DNg21, DNxl021, DNxl067, DNxn143, DNxn168, DNxn174, pMP2
- **stable_non_driver** (high): DNa01, DNa05, DNa14, DNa15, DNfl023, DNfl035, DNfl042, DNg04, DNg107, DNg14, DNg16, DNg39, DNg69, DNg73, DNg78, DNg79, DNlt011, DNp01, DNp03, DNp04, DNp05, DNp07, DNp103, DNp26, DNp31, DNp33, DNp35, DNp46, DNut037, DNut040, DNut044, DNut051, DNut052, DNxl056, DNxl078, DNxl079, DNxl081, DNxl098, DNxl105, DNxl116, DNxl117, DNxl119, DNxn071, DNxn102, DNxn119, DNxn123, DNxn130, DNxn137, DNxn170, DNxn176

- **replicated** (all): DNb08, DNg100, DNit013
- **near_replicated** (all): DNa03, DNa07, DNa13, DNp71, DNxl053, DNxl092, DNxl130, DNxn118, DNxn151, DNxn171
- **single_fly_manc** (all): DNg63, DNit011, DNp02, DNp41, DNp63, DNxl101, DNxl102, DNxl110, DNxl121, DNxl133
- **single_fly_malecns** (all): DNd05, DNfl015, DNfl018, DNfl022, DNfl030, DNfl031, DNfl034, DNg109, DNg12, DNg13, DNg21, DNxl021, DNxl067, DNxn104, DNxn143, DNxn168, DNxn174, pMP2
- **stable_non_driver** (all): DNa01, DNa05, DNa14, DNa15, DNfl023, DNfl035, DNfl042, DNg01, DNg02, DNg03, DNg04, DNg05, DNg06, DNg107, DNg110, DNg14, DNg16, DNg39, DNg51, DNg69, DNg73, DNg78, DNg79, DNg82, DNg89, DNg92, DNht001, DNit006, DNlt011, DNnt008, DNnt012, DNp01, DNp03, DNp04, DNp05, DNp07, DNp103, DNp16, DNp26, DNp31, DNp33, DNp35, DNp46, DNp64, DNut036, DNut037, DNut040, DNut042, DNut044, DNut045, DNut046, DNut051, DNut052, DNut057, DNut058, DNxl056, DNxl063, DNxl078, DNxl079, DNxl081, DNxl097, DNxl098, DNxl105, DNxl116, DNxl117, DNxl119, DNxl122, DNxn071, DNxn100, DNxn102, DNxn108, DNxn112, DNxn119, DNxn123, DNxn126, DNxn128, DNxn130, DNxn134, DNxn136, DNxn137, DNxn169, DNxn170, DNxn176

Members flagged for a low or medium match (both directions): replicated: DNit013; single_fly_malecns: DNfl018, DNfl022, DNfl030, DNg12, DNxn104; single_fly_manc: DNit011, DNxl102, DNxl133; stable_non_driver: DNg01, DNg02, DNg03, DNg05, DNg06, DNg110, DNg51, DNg82, DNg89, DNg92, DNht001, DNit006, DNnt008, DNnt012, DNp16, DNp64, DNut036, DNut042, DNut045, DNut046, DNut057, DNut058, DNxl063, DNxl097, DNxl122, DNxn100, DNxn108, DNxn112, DNxn126, DNxn128, DNxn134, DNxn136, DNxn169.

| overlap of the driver lists (95 % bootstrap interval) | high-confidence | all types | high + medium |
|---|---|---|---|
| replication rate: B1r drivers that are B2r drivers | 0.18 [0.00, 0.44] | 0.20 [0.00, 0.43] | 0.15 [0.00, 0.38] |
| replication rate: B2r drivers that are MANC drivers | 0.09 [0.00, 0.22] | 0.10 [0.00, 0.23] | 0.08 [0.00, 0.21] |
| overlap coefficient, full screens | 0.18 [0.00, 0.44] | 0.20 [0.00, 0.43] | 0.15 [0.00, 0.38] |
| OC, cross-fly matched halves | 0.23 [0.00, 0.49] | 0.23 [0.04, 0.46] | 0.19 [0.00, 0.42] |
| OC ceiling: within-fly split halves | 0.87 [0.71, 1.00] | 0.85 [0.72, 0.97] | 0.87 [0.73, 0.98] |
| OC cross-half / ceiling | 0.26 [0.00, 0.55] | 0.27 [0.04, 0.53] | 0.22 [0.00, 0.47] |
| Jaccard, full screens | 0.06 [0.00, 0.16] | 0.07 [0.00, 0.16] | 0.06 [0.00, 0.15] |
| Jaccard, cross-fly halves | 0.07 [0.00, 0.17] | 0.08 [0.01, 0.17] | 0.07 [0.00, 0.15] |
| Jaccard ceiling | 0.61 [0.46, 0.77] | 0.64 [0.50, 0.77] | 0.64 [0.49, 0.78] |
| Jaccard ratio | 0.12 [0.00, 0.27] | 0.13 [0.02, 0.25] | 0.11 [0.00, 0.23] |
- high: 11 drivers in B1r, 23 in B2r, 2 in both (expected 1.18 if independent) over 215 common types; the Jaccard index cannot exceed 0.48 with these list sizes.
- all: 15 drivers in B1r, 29 in B2r, 3 in both (expected 1.40 if independent) over 310 common types; the Jaccard index cannot exceed 0.52 with these list sizes.

## A1 (the authors' MANC list) x B2r (post hoc)

| category | high-confidence match | all types | high + medium |
|---|---|---|---|
| replicated | 2 | 3 | 2 |
| near_replicated | 6 | 6 | 6 |
| single_fly_manc | 3 | 7 | 6 |
| single_fly_malecns | 16 | 21 | 17 |
| stable_non_driver | 47 | 77 | 53 |
| neither | 141 | 196 | 158 |

- **replicated** (high): DNb08, DNg100
- **near_replicated** (high): DNa07, DNa13, DNp71, DNxl092, DNxn118, DNxn171
- **single_fly_manc** (high): DNp41, DNxl101, DNxl110
- **single_fly_malecns** (high): DNa03, DNd05, DNfl015, DNfl031, DNfl034, DNg109, DNg13, DNg21, DNxl021, DNxl067, DNxl130, DNxn143, DNxn151, DNxn168, DNxn174, pMP2
- **stable_non_driver** (high): DNa01, DNa05, DNa14, DNa15, DNfl023, DNfl035, DNfl042, DNg04, DNg107, DNg14, DNg16, DNg69, DNg73, DNg78, DNg79, DNlt011, DNp01, DNp03, DNp04, DNp05, DNp07, DNp103, DNp26, DNp31, DNp33, DNp35, DNp46, DNut037, DNut040, DNut044, DNut051, DNut052, DNxl056, DNxl078, DNxl079, DNxl081, DNxl098, DNxl116, DNxl117, DNxl119, DNxn071, DNxn102, DNxn119, DNxn123, DNxn130, DNxn137, DNxn176

- **replicated** (all): DNb08, DNg100, DNit013
- **near_replicated** (all): DNa07, DNa13, DNp71, DNxl092, DNxn118, DNxn171
- **single_fly_manc** (all): DNg54, DNit011, DNp41, DNxl101, DNxl102, DNxl110, DNxl133
- **single_fly_malecns** (all): DNa03, DNd05, DNfl015, DNfl018, DNfl022, DNfl030, DNfl031, DNfl034, DNg109, DNg12, DNg13, DNg21, DNxl021, DNxl067, DNxl130, DNxn104, DNxn143, DNxn151, DNxn168, DNxn174, pMP2
- **stable_non_driver** (all): DNa01, DNa05, DNa14, DNa15, DNfl023, DNfl035, DNfl042, DNg01, DNg03, DNg04, DNg05, DNg06, DNg107, DNg110, DNg14, DNg16, DNg69, DNg73, DNg78, DNg79, DNg82, DNg89, DNg92, DNht001, DNit006, DNlt011, DNnt008, DNnt012, DNp01, DNp03, DNp04, DNp05, DNp07, DNp103, DNp16, DNp26, DNp31, DNp33, DNp35, DNp46, DNp64, DNut036, DNut037, DNut040, DNut042, DNut044, DNut045, DNut046, DNut051, DNut052, DNut057, DNut058, DNxl056, DNxl063, DNxl078, DNxl079, DNxl081, DNxl097, DNxl098, DNxl116, DNxl117, DNxl119, DNxl122, DNxn071, DNxn100, DNxn102, DNxn108, DNxn112, DNxn119, DNxn123, DNxn126, DNxn130, DNxn134, DNxn136, DNxn137, DNxn169, DNxn176

Members flagged for a low or medium match (both directions): replicated: DNit013; single_fly_malecns: DNfl018, DNfl022, DNfl030, DNg12, DNxn104; single_fly_manc: DNg54, DNit011, DNxl102, DNxl133; stable_non_driver: DNg01, DNg03, DNg05, DNg06, DNg110, DNg82, DNg89, DNg92, DNht001, DNit006, DNnt008, DNnt012, DNp16, DNp64, DNut036, DNut042, DNut045, DNut046, DNut057, DNut058, DNxl063, DNxl097, DNxl122, DNxn100, DNxn108, DNxn112, DNxn126, DNxn134, DNxn136, DNxn169.

| overlap of the driver lists (95 % bootstrap interval) | high-confidence | all types | high + medium |
|---|---|---|---|
| replication rate: A1 drivers that are B2r drivers | 0.33 [0.00, 0.80] | 0.27 [0.00, 0.57] | 0.22 [0.00, 0.55] |
| replication rate: B2r drivers that are MANC drivers | 0.09 [0.00, 0.22] | 0.10 [0.00, 0.23] | 0.08 [0.00, 0.21] |
| overlap coefficient, full screens | 0.33 [0.00, 0.80] | 0.27 [0.00, 0.57] | 0.22 [0.00, 0.55] |
| OC, cross-fly matched halves | 0.29 [0.00, 0.67] | 0.26 [0.00, 0.53] | 0.20 [0.00, 0.48] |
| OC ceiling: within-fly split halves | 0.84 [0.68, 1.00] | 0.88 [0.77, 0.99] | 0.86 [0.75, 1.00] |
| OC cross-half / ceiling | 0.34 [0.00, 0.72] | 0.30 [0.00, 0.58] | 0.23 [0.00, 0.53] |
| Jaccard, full screens | 0.07 [0.00, 0.19] | 0.08 [0.00, 0.18] | 0.06 [0.00, 0.17] |
| Jaccard, cross-fly halves | 0.07 [0.00, 0.17] | 0.07 [0.00, 0.16] | 0.06 [0.00, 0.15] |
| Jaccard ceiling | 0.66 [0.46, 0.85] | 0.71 [0.55, 0.85] | 0.70 [0.53, 0.86] |
| Jaccard ratio | 0.10 [0.00, 0.24] | 0.10 [0.00, 0.22] | 0.08 [0.00, 0.20] |
- high: 6 drivers in A1, 23 in B2r, 2 in both (expected 0.64 if independent) over 215 common types; the Jaccard index cannot exceed 0.26 with these list sizes.
- all: 11 drivers in A1, 29 in B2r, 3 in both (expected 1.03 if independent) over 310 common types; the Jaccard index cannot exceed 0.38 with these list sizes.

## Copy concordance in the authors' single-neuron screen A0 (post hoc)

- copies_on_both_sides: 308 types; 18 with at least one driver copy; 2 with every copy a driver (DNb08, DNg100); share 0.11 of the types with a driver copy, 0.01 of all.
- one_copy_each_side: 250 types; 14 with at least one driver copy; 1 with every copy a driver (DNg100); share 0.07 of the types with a driver copy, 0.00 of all.

## The two experimentally confirmed drivers (post hoc)

- **DNg100**: replicated (A1 x B2r: replicated); match high; B1r 0.83, B2r 0.67, A1 0.90; half-flies MANC_L 0.98, MANC_R 0.97, MaleCNS_L 0.80, MaleCNS_R 0.99; A0 copies 10093 (L) 0.85, 10339 (R) 0.84.
- **DNb08**: replicated (A1 x B2r: replicated); match high; B1r 0.61, B2r 0.78, A1 0.63; half-flies MANC_L 0.64, MANC_R 0.37, MaleCNS_L 0.67, MaleCNS_R 0.00; A0 copies 13892 (L) 0.62, 14061 (L) 0.73, 14680 (R) 0.58, 14966 (R) 0.66.

Selection caveats: DNg100 is the neuron the model was calibrated and built around (the tuner's K was chosen on it). The original authors chose DNb08 themselves. Both are exposed types. Two confirmed neurons are a tiny sample.
