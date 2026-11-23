# a5-adj-05 adjudication notes

Assigned source: Dombrovski et al. 2023, Nature, 10.1038/s41586-022-05562-8 (full text, figures, Supplementary Tables 1-2 and source data were all available locally). Supplementary videos were not downloaded. Their legends (Videos 1-2) cover DNp11 and DNp02 only, so the missing videos do not affect DNp05.

Assigned type: **DNp05** (AMMC-Db2).

## What the source contains for DNp05
- The only real-fly activation experiment is FlyPEZ CsChrimson activation (624 nm, 500 W m-2, 50-ms pulse, dark, unrestrained flies on a platform) of two lines the paper calls DNp05: **SS02612** (n = 311) and **SS00865** (n = 319).
- Takeoff: 4.8% and 4.1% vs 4.2% for Empty, NS (Extended Data Fig. 1e, source data; main text: only DNp04, DNp11 and the combination lines increased takeoff).
- Posture: the pooled DNp05 Delta[T2 leg angle] at 75 ms is not different from Empty (Supplementary Table 1: P = 0.626). The Fig. 1f trace is flat over the 100-ms tracked window.
- No stepping, walking or other leg movement is described. The Kir2.1 silencing of DNp05 lines (Supplementary Table 2, ED Fig. 2) is silencing, so it is not a record. The other DNp05 content is connectomics (Fig. 1c, Fig. 4d, ED Fig. 9) and is not a record either.
- The paper has its own LC4 receptive-field model, but it covers DNp02, DNp11, DNp04 and GF, not DNp05. No Pugliese-type rhythm score, rank or driver call was seen, so `saw_simulation_score` = false.

## Where the readers differed and what I found
- **Leg rhythm:** both readers coded front, middle and hind = `no` with `no_visible_effect` for both lines, so they do not actually disagree on this. I agree with `no`: the paper's only leg measure (T2 posture) shows no effect, and no other leg movement is reported. However, the analysis window is 100 ms after a 50-ms pulse, which is too short to show 3 or more step cycles. I therefore set `labeler_confidence` to `low`, as Reader B did; Reader A used `medium`.
- **Mapping and specificity:** both readers flagged that the kit maps SS02612 to **DNp07**, while the paper calls it DNp05. The AD/DBD pair (VT047755 x VT003280) is the same in both, so this is a real naming conflict, not a typo. Both hemidrivers also appear in kit DNp07 lines (VT047755 in SS02276, VT003280 in SS01549), which makes DNp07 plausible. I kept the record under DNp05 at `medium` with a note, and added the paper's assignment to `out/proposed_driver_lines.csv`. If the kit is right, record 0001 belongs to DNp07, which would not change the leg outcome (`no`). For SS00865 the paper and kit agree (DNp05, high).
- **Minor field differences:** Reader B set expression `bilateral` and SS02612 `clean`. The paper states neither, so I used expression `unknown` and SS02612 specificity `unknown`. For SS00865 I used `clean`, based on the kit's Namiki 2018 row with 0 off-target types.
- **Missed experiments:** none. Neither reader missed a DNp05 activation experiment.
