# Session a5-g10-A notes (label audit, run 5)

Sources read: all three assigned sources in full text, plus the Dombrovski et al. 2023 supplementary tables (MOESM1), the Extended Data Fig. 1e and Fig. 1e source data, and the images for Fig. 1 and Extended Data Fig. 1. No web access was used.

## Dombrovski et al. 2023 (10.1038/s41586-022-05562-8)
- CsChrimson activation was done in freely standing flies on the FlyPEZ platform, filmed with high-speed video. Only takeoff (rate, mode, direction) and a T2-leg-angle postural shift were measured. Stepping/walking was never scored, so every leg-rhythm field is `no` under PROTOCOL 3: either a single movement (takeoff, lean) or no visible effect. Confidence is `medium` for all lines except GF, because the observation window is short and stepping was not explicitly assessed.
- There is one record per driver line. Fig. 1e pools posture by DN type, so the per-line posture effect is inferred from the pooled type.
- **Line conflict:** the paper calls SS02612 "DNp05", but the kit's driver_lines.csv maps SS02612 to DNp07 (two independent kit rows). Record 0009 follows the paper (DNp05, mapping_confidence medium) and flags the conflict. A proposed row is in proposed_driver_lines.csv.
- SS49010 and SS49024 (both DNp11) are not in the kit; proposed.
- Text says GF takeoff is >90%, but per-line source data give 96.9% (SS00727) and 84.7% (SS27721).
- The paper has its own model, built from LC4 receptive fields, that estimates the visual responses of DNp02, DNp11, DNp04 and GF. It is not a Pugliese-type activation/rhythm score, rank or driver call, so `saw_simulation_score` = false everywhere.
- The silencing (Kir2.1), electrophysiology and P2X2 experiments are not activation-with-legs experiments, so they have no records.

## DeepFly3D (10.7554/elife.48571)
- MDN-1 > CsChrimson gives backward walking: all legs `yes`.
- aDN-GAL4 (R76F12-AD; R18C11-DBD) > CsChrimson gives antennal grooming. The kit maps this line to DNfl023 (aDN2), but a second kit row with the hemidrivers in reversed order gives DNg127/UNMAPPED, so mapping_confidence is medium. The paper does not name the grooming legs. Front legs are coded `yes` using Hampel et al. 2020 (also in this room), which defines antennal grooming as done by the front legs. Middle and hind legs are `unclear`.

## Hampel et al. 2020 (10.7554/elife.59976)
- Only JON sensory subpopulations are activated. aDNs and MDN are mentioned only in the Discussion. Disposition: no_qualifying_experiment.

## Assigned types with no records from these sources
DNg02, DNg03 and DNp07 have no records. DNp07 is only mentioned in Dombrovski as an LPLC4 gradient target. DNp07 would be affected if the kit's SS02612 mapping is correct (see above).

No simulation scores were seen for any assigned type.
