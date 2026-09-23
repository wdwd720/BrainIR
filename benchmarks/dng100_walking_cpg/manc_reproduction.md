# MANC connectivity reproduction (Pugliese et al. matrices vs BrainIR builds)

Authors' repository `smpuglie/Pugliese_2026` @ `10e7661bf4` (files pinned by SHA-256). Floor: 5 synapses per pair.

| network | BrainIR build | neurons found | pairs (authors / ours) | both | only authors | only ours | exact count | Σsyn authors / ours |
|---|---|---|---|---|---|---|---|---|
| t1_2025-08-13 | manc:v1.2.1 | 4604/4604 | 196535 / 196536 | 196535 | 0 | 1 | 196535 (100.0000%) | 3817772 / 3817784 |
| t1_2025-08-13 | manc:v1.2.3 | 4604/4604 | 196535 / 196536 | 196535 | 0 | 1 | 196535 (100.0000%) | 3817772 / 3817784 |
| t1_2025-08-13 | manc:v1.0 | 4582/4604 | 196535 / 196021 | 196020 | 515 | 1 | 196018 (99.9990%) | 3817772 / 3811466 |
| full_2025-10-06 | manc:v1.2.3 | 23532/23532 | 1372404 / 1372412 | 1372404 | 0 | 8 | 1372404 (100.0000%) | 24149548 / 24149609 |
| full_2025-10-06 | manc:v1.2.1 | 23510/23532 | 1372404 / 1372186 | 1372178 | 226 | 8 | 1372178 (100.0000%) | 24149548 / 24147604 |
| mcns_t1_2026-02-10 | male-cns:v1.0 | 4309/4310 | 118920 / 119977 | 118680 | 240 | 1297 | 118488 (99.8382%) | 2190257 / 2196924 |

## Sign agreement (presynaptic rows with output)

| network | BrainIR build | sign source | rows | agree | fraction |
|---|---|---|---|---|---|
| t1_2025-08-13 | manc:v1.2.1 | paper_rule_on_authors_predictedNt | 4456 | 4456 | 1.0000 |
| t1_2025-08-13 | manc:v1.2.1 | brainir.sign.conventional-v1 on nt_body_prediction | 4456 | 4431 | 0.9944 |
| t1_2025-08-13 | manc:v1.2.3 | paper_rule_on_authors_predictedNt | 4456 | 4456 | 1.0000 |
| t1_2025-08-13 | manc:v1.2.3 | brainir.sign.conventional-v1 on nt_body_prediction | 4456 | 4431 | 0.9944 |
| t1_2025-08-13 | manc:v1.2.3 | brainir.sign.conventional-v1 on nt_type_prediction | 4456 | 4321 | 0.9697 |
| t1_2025-08-13 | manc:v1.0 | paper_rule_on_authors_predictedNt | 4456 | 4456 | 1.0000 |
| t1_2025-08-13 | manc:v1.0 | brainir.sign.conventional-v1 on nt_body_prediction | 4434 | 4409 | 0.9944 |
| full_2025-10-06 | manc:v1.2.3 | paper_rule_on_authors_predictedNt | 22769 | 22769 | 1.0000 |
| full_2025-10-06 | manc:v1.2.3 | brainir.sign.conventional-v1 on nt_body_prediction | 22769 | 22595 | 0.9924 |
| full_2025-10-06 | manc:v1.2.3 | brainir.sign.conventional-v1 on nt_type_prediction | 22769 | 21275 | 0.9344 |
| full_2025-10-06 | manc:v1.2.1 | paper_rule_on_authors_predictedNt | 22769 | 22769 | 1.0000 |
| full_2025-10-06 | manc:v1.2.1 | brainir.sign.conventional-v1 on nt_body_prediction | 22748 | 22574 | 0.9924 |
| mcns_t1_2026-02-10 | male-cns:v1.0 | paper_rule_on_authors_consensusNt | 4068 | 4068 | 1.0000 |
| mcns_t1_2026-02-10 | male-cns:v1.0 | brainir.sign.conventional-v1 on nt_consensus | 4068 | 4068 | 1.0000 |
| mcns_t1_2026-02-10 | male-cns:v1.0 | brainir.sign.conventional-v1 on nt_body_prediction | 4068 | 4040 | 0.9931 |

Mismatching pairs are listed in `tables/manc_reproduction_pairs_*.csv`; full numbers in `tables/manc_reproduction_summary.json`.
