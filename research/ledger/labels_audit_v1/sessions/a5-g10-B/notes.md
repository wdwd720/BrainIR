# Notes, session a5-g10-B (audit, run 5)

Sources read: all three assigned sources (text.txt, figure legends, key figures, and the Supplementary Information / source data for the Nature paper).

## 10.1038/s41586-022-05562-8 (Dombrovski et al., Nature 2023)
- Flies were freely standing in the FlyPEZ assay with CsChrimson activation. Of the assigned types, these lines were tested: GF/DNp01 (SS00727, SS27721), DNp02 (SS01053, SS01554), DNp03 (SS01081, SS01596), DNp04 (SS00934, SS01080), DNp05 (SS02612, SS00865), DNp06 (SS02256), DNp11 (SS49010, SS49024, SS49051), plus the combination lines SS01544 (DNp02+DNp04) and SS02292 (DNp02+DNp04+DNp06). Every tested line was reported, so every line got a record, including the no-effect lines.
- The outcomes are takeoffs and forward or backward postural leans: single movements or posture changes, so all leg-rhythm fields are `no`. Walking was not measured (`effect_on_walking` = `not_assessed`). The legs were tracked only over about 100 ms after a 50-ms pulse, so these `no` codes cannot exclude stepping later on. Confidence is medium for lines with an effect and low for no-effect lines.
- The posture metric in Fig. 1e/f is pooled by cell type. Takeoff rates are per line (Extended Data Fig. 1e source data).
- **Mapping conflict:** the paper labels SS02612 (VT047755-AD; VT003280-DBD) as DNp05, but driver_lines.csv maps SS02612 to DNp07. I recorded it as DNp05 with medium mapping confidence and added a row to proposed_driver_lines.csv. SS49010 and SS49024 are not in the kit; I mapped them by the paper's name (DNp11).
- The paper includes its own LC4-connectivity model of DN looming responses (Fig. 3, Extended Data Fig. 5). It is not a rhythm score, rank or driver call, so `saw_simulation_score` = false on every record. No sightings.

## 10.7554/elife.48571 (DeepFly3D)
- MDN-1-Gal4 > CsChrimson gives backward walking (all legs `yes`). aDN-Gal4 (R76F12-AD; R18C11-DBD) > CsChrimson gives antennal grooming (front `yes`, middle and hind `unclear`). Both on tethered flies on a ball.
- The aDN line is mapped to DNfl023 (aDN2) through driver_lines.csv. Mapping confidence is medium because the paper only says "aDN" and the kit also has an UNMAPPED/DNg127 row for the same enhancer pair. The videos were not downloaded (not needed).

## 10.7554/elife.59976 (Hampel et al. 2020)
- Only Johnston's organ sensory neurons are activated. DNs (aDN, MDN) appear only in the Discussion, so no records.

No assigned type had a qualifying experiment for DNg02, DNg03 or DNp07 in these sources (DNp07 appears only through the kit's SS02612 mapping; see above).
