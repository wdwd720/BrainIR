# Connectivity reproduction (Pugliese et al. matrices vs BrainIR builds)

Authors' repository `smpuglie/Pugliese_2026` @ `10e7661bf4` (files pinned by SHA-256). Floor: 5 synapses per pair; BrainIR counts are restricted to the paper's ROI set where the paper did so (MaleCNS: VNC neuropils), autapses are removed and output rows of neurons whose label is not ACh/GABA/Glu are zeroed, as in the paper.

| network | BrainIR build | neurons found | pairs (authors / ours) | both | only authors | only ours | exact count | Σsyn authors / ours |
|---|---|---|---|---|---|---|---|---|
| t1_2025-08-13 | manc:v1.2.1 | 4604/4604 | 196535 / 196535 | 196535 | 0 | 0 | 196535 (100.0000%) | 3817772 / 3817772 |
| t1_2025-08-13 | manc:v1.2.3 | 4604/4604 | 196535 / 196535 | 196535 | 0 | 0 | 196535 (100.0000%) | 3817772 / 3817772 |
| t1_2025-08-13 | manc:v1.0 | 4582/4604 | 196535 / 196020 | 196020 | 515 | 0 | 196018 (99.9990%) | 3817772 / 3811454 |
| full_2025-10-06 | manc:v1.2.3 | 23532/23532 | 1372404 / 1372404 | 1372404 | 0 | 0 | 1372404 (100.0000%) | 24149548 / 24149548 |
| full_2025-10-06 | manc:v1.2.1 | 23510/23532 | 1372404 / 1372178 | 1372178 | 226 | 0 | 1372178 (100.0000%) | 24149548 / 24147543 |
| mcns_t1_2026-02-10 | male-cns:v1.0 | 4309/4310 | 118920 / 118729 | 118680 | 240 | 49 | 118488 (99.8382%) | 2190257 / 2185461 |

## Restricted to bodies not proofread between the authors' extraction and the BrainIR release

A body counts as changed when its size differs from the authors' table or it no longer exists.

| network | BrainIR build | changed bodies | pairs (authors / ours) | both | only authors | only ours | exact count |
|---|---|---|---|---|---|---|---|
| t1_2025-08-13 | manc:v1.2.1 | 0 | 196535 / 196535 | 196535 | 0 | 0 | 196535 |
| t1_2025-08-13 | manc:v1.2.3 | 0 | 196535 / 196535 | 196535 | 0 | 0 | 196535 |
| t1_2025-08-13 | manc:v1.0 | 23 | 195964 / 195964 | 195964 | 0 | 0 | 195962 |
| full_2025-10-06 | manc:v1.2.3 | 0 | 1372404 / 1372404 | 1372404 | 0 | 0 | 1372404 |
| full_2025-10-06 | manc:v1.2.1 | 22 | 1372178 / 1372178 | 1372178 | 0 | 0 | 1372178 |
| mcns_t1_2026-02-10 | male-cns:v1.0 | 30 | 116424 / 116424 | 116424 | 0 | 0 | 116424 |

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
