# Cross-connectome evaluation — MANC v1.2.1 <-> MaleCNS v1.0

Mapping table `81699b6bad9c5810a65d97a69679142d72e1ff7313ba9853bdad6ff00cba7bb5` (schema 1.1.0). **Caveat:** every correspondence below is a `curated_body_match`, i.e. the MaleCNS release's own `manc_body_id` annotation restated by the table — curated evidence, not something BrainIR derived; the two datasets are two animals and no row asserts identity (LOG D35, D39). The functional transfer is the derived part.

## Correspondence of the published core through the public mapping table

| label | MANC id | MaleCNS id | MANC->MaleCNS best (kind/conf/amb) | published among cands | MaleCNS->MANC best | published among cands |
|---|---|---|---|---|---|---|
| stimulus | 10093 | 10056 | 10056 curated_body_match/high/1 | True | 10093 curated_body_match/high/1 | True |
| E1 | 10707 | 800173 | 800173 curated_body_match/high/1 | True | 10707 curated_body_match/high/1 | True |
| E2 | 11751 | 800863 | 800863 curated_body_match/high/1 | True | 11751 curated_body_match/high/1 | True |
| I1 | 13905 | 801884 | 801884 curated_body_match/high/1 | True | 13905 curated_body_match/high/1 | True |
| I2 | 10242 | 800374 | 800374 curated_body_match/high/1 | True | 10242 curated_body_match/high/1 | True |
| E3 | 10715 | 800216 | 800216 curated_body_match/high/1 | True | 10715 curated_body_match/high/1 | True |
| E4 | 12021 | 800663 | 800663 curated_body_match/high/1 | True | 12021 curated_body_match/high/1 | True |
| E5 | 162543 | 800286 | 800286 curated_body_match/high/1 | True | 162543 curated_body_match/high/1 | True |

## Functional transfer (keep-only simulations, n = 64, T = 1.0 s)

### manc_to_male-cns: source modal circuit ['E1', 'E2', 'I1'] -> mapped ids [800173, 800863, 801884] (destination's own modal circuit ['E1', 'E2', 'I2'], I = 400.0; stimulus mapped through the table equals the benchmark's: True; null = sign-matched random interneuron triple, signs [1, 1, -1])

| condition | kept | mean score | median | frac >= 0.5 | median f (Hz) | median active MNs |
|---|---|---|---|---|---|---|
| intact_network | 4309 | 0.983 | 0.994 | 1.000 | 11.412617587499998 | 8.0 |
| own_modal_circuit_keep_only | 3 | 0.795 | 0.799 | 1.000 | 16.6325136875 | 5.0 |
| mapped_modal_circuit_keep_only | 3 | 0.765 | 0.775 | 1.000 | 15.1952214875 | 9.0 |
| null_sign_matched_random_triple_keep_only | 3 | 0.000 | 0.000 | 0.000 | None | 3.0 |

### male-cns_to_manc: source modal circuit ['E1', 'E2', 'I2'] -> mapped ids [10242, 10707, 11751] (destination's own modal circuit ['E1', 'E2', 'I1'], I = 250.0; stimulus mapped through the table equals the benchmark's: True; null = sign-matched random interneuron triple, signs [1, 1, -1])

| condition | kept | mean score | median | frac >= 0.5 | median f (Hz) | median active MNs |
|---|---|---|---|---|---|---|
| intact_network | 4604 | 0.969 | 0.997 | 1.000 | 10.526315799999999 | 3.0 |
| own_modal_circuit_keep_only | 3 | 0.978 | 0.995 | 1.000 | 16.393442599999997 | 2.0 |
| mapped_modal_circuit_keep_only | 3 | 0.857 | 0.862 | 1.000 | 14.9253731 | 2.0 |
| null_sign_matched_random_triple_keep_only | 3 | 0.000 | 0.000 | 0.000 | None | 0.0 |
