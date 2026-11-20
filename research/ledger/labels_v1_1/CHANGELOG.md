# Labels v1.1 changelog

| version | date | change | labels existing at the time | scoring inputs |
|---|---|---|---|---|
| 1 | 2026-11-20 | initial (`LOCK_labels_v1.json`, tag `ledger-labels-v1`) | - | - |
| 1.1 | 2026-11-20 | (1) eLife DOIs normalised correctly (version suffix stripped, article number kept); (2) the breaching search session excluded from the search-only records and the completeness statistic, like every breaching session (PREREG 6). Source: independent label review round 1, finding 2 (`final/REVIEW_labels_round1.md`). | yes: labels v1 were locked; the orchestrator had seen only aggregate label counts; no label was ever joined to a prediction | `records.jsonl` and `type_labels.csv` byte-identical to v1 |

Changed files relative to v1: `agreement.md`, `agreement.json` (capture-recapture), `sources.csv` (eLife sources no longer merged),
`search_only_records.jsonl`. Built by `ledger/scripts/labels_v1_1.py` from the v1 raw inputs.
