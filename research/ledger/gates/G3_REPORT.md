# Gate G3: full nerve cord, two-sided DNg100 (authors' configuration)

Both DNg100 at 380, T = 2 s, seeds 0..63, `manc_v1.2.3` full cord = the authors' matrix (LOG L10). Thresholds: PREREG section 9 (committed in 8782b73 before this run was evaluated).

| leg | frac >= 0.5 (ours / authors) | median score (ours / authors) | median active MNs (ours / authors) |
|---|---|---|---|
| T1L | 0.844 / 0.734 | 0.942 / 0.887 | 2 / 2 |
| T1R | 0.609 / 0.578 | 0.780 / 0.687 | 1 / 1 |
| T2L | 0.484 / 0.469 | 0.475 / 0.452 | 1 / 1 |
| T2R | 0.828 / 0.789 | 0.911 / 0.936 | 2 / 2 |
| T3L | 0.203 / 0.164 | 0.271 / 0.215 | 3 / 2 |
| T3R | 0.812 / 0.781 | 0.691 / 0.716 | 12 / 13 |

Hind mean score 0.484 vs front 0.683.

Coupling (leg signal v1, PREREG 4.7):

| pair | n | R | null mean R | p | coupled |
|---|---|---|---|---|---|
| T1L-T1R | 34 | 0.234 | 0.153 | 0.14585414585414586 | False |
| T2L-T2R | 29 | 0.226 | 0.171 | 0.24975024975024976 | False |
| T3L-T3R | 13 | 0.595 | 0.24 | 0.008991008991008992 | True |
| T1L-T2L | 29 | 0.59 | 0.165 | 0.000999000999000999 | True |
| T2L-T3L | 8 | 0.583 | 0.318 | 0.054945054945054944 | False |
| T1R-T2R | 37 | 0.14 | 0.153 | 0.5194805194805194 | False |
| T2R-T3R | 46 | 0.879 | 0.134 | 0.000999000999000999 | True |

Criteria: 1_every_leg_rhythmic PASS, 2_per_leg_agreement PASS, 3_hind_weaker PASS, 4_no_coupling FAIL
**G3 items 1-4: FAIL.** Item 5 is checked on the B3 arm.
