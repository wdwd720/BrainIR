# Resolution of the label-side review, round 1 (`REVIEW_labels_round1.md`)

**Update (LOG L47):** finding 2 (a and b) is resolved by a new labels version, **v1.1** (`research/ledger/labels_v1_1/`, `LOCK_labels_v1_1.json`, tag `ledger-labels-v1.1`, changelog in the folder), as the prompt prescribes for a bug found after a lock; the reviewer verified v1.1 (section "v1.1 verification" of the review): finding 2 resolved, nothing wrong, scoring inputs byte-identical to v1. Finding 1 (coverage) is not a bug and cannot be repaired by re-processing; it needs new labeling under a new pre-registration (labels v2).

The labels are locked (`ledger-labels-v1`). PREREG 12 forbids label-side code changes once Stage 2 has records, and the prompt
says a bug found after a lock becomes a new version, never an edit. So nothing in v1 changes; every finding is recorded here,
in the LOG (L45) and in the handoff, and carried into a labels v2 under a new pre-registration.

| # | finding | resolution |
|---|---|---|
| 1 (major) | coverage loss: the excluded atlas and walking_stopping families were not replaced; the atlas/walking/screen literature is absent from the final records; at most 13 types can reach the primary set | Reported (handoff sections 6, 8). v2: re-run every family with tool-results reads denied at tool level. |
| 2a (major) | `norm_doi` (frozen `labels_collect.py`) truncates unversioned eLife DOIs, merging all eLife papers: capture-recapture 181.6 instead of 197.1, 5 search-only records dropped, eLife rows merged in `sources.csv` | Frozen code, not fixed in v1; the scoring inputs are unaffected (the reviewer reproduced `records.jsonl` and `type_labels.csv` exactly). **Corrected statistic published as an addendum:** `final/COMPLETENESS_ADDENDUM.json` (`ledger/scripts/completeness_addendum.py`: frozen inputs and rules, only the DOI normalisation varied) reproduces 181.6 as reported and gives 197.1 with the fix and 153 search-only records. v2: fix `norm_doi`. |
| 2b (major) | the breaching search session is kept in the capture-recapture estimate and the search-only records (PREREG names only pass-1, pass-2 and adjudication sessions) | Search records never enter the consensus. The addendum also gives the estimate with this session excluded: 125.0 (with 2a fixed; pass 1 found 39 %), 56 search-only records. v2: exclude breaching search sessions too. |
| 3 (minor) | every outside-room read was accepted by the tool permissions; the 9 "blocked attempts" are failed reads (guard or natural failure), not permission denials; exclusion depended on timing | Agreed; wording noted. v2: deny at tool level. |
| 4 (minor) | evidence is mediated by the fetch tool's own model; pass-2 identifier fields can cue (`name_in_paper` equals the pass-1 type in 128/166; 21 fields carry behaviour words); about a third of fetches returned errors (mostly 429) | Reported (handoff section 8: agreement likely overstates reliability). v2: neutral identifiers, rate limiting. |
| 5 (minor) | 22 not found, 3 unresolved, 34 score-flagged records excluded, all by the rules | Reported. |
| 6 (minor) | latent code gaps (taint scope, pass-2 gate coverage, `lock.py check` silent on missing raw files and the prereg hash) | No effect here (the reviewer verified both by hand). v2. |
