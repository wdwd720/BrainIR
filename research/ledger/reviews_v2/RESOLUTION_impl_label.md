# Resolution of the label-side implementation review (`REVIEW_impl_label.md`), before `LOCK_labelcode_v2.json`

Synthetic tests: `ledger/tests/test_labels2_collect.py` (9 tests, one per blocker plus the atlas, assignment and reassignment
rules); the canary transcripts were re-audited with the new exemption (room 1: 1 own tool-result read exempted, no breach;
rooms 2-6: no breach).

| finding | resolution |
|---|---|
| B1 readers skip Namiki and the catalogue | `readers` counts only reader / reader_web specs and manifests as assigned; only the atlas is skipped (test). |
| B2 not-found rows of excluded sessions | `_not_found_v2`: the frozen rule (Phase A snapshot) over second readings in use only (not breaching, not replaced) (test). |
| B3 kind-1 exception by pattern | The Read path must occur verbatim in the raw text of one of the session's own tool results (`scan` returns those texts; `toolUseResult` included). Canary room 1 (a real own-binary read) passes. |
| B4 audit coverage and freshness | `_breaching(sessions=None)` ports v1's checks: every session (or the given ones) finished, audited, and no log newer than its audit; global for `second`, `adjudication`, `leads`, `finalize`; per finished session for `reassign`, `redo-breaching`, `atlas-quotes` (test). |
| B5 adjudication not incremental | Specs record their `disputes`; covered disputes are skipped; new specs take the next free name; `_spec` never overwrites; reading order: one coin per dispute from seed 20261206 (test). |
| M1 source identity | `is_dedicated` by the frozen audit's tokens (registry, leads, second, adjudication); `build_room` refuses a dedicated source outside a dedicated room and an undownloaded source; first-reading records must cite one of the session's assigned sources (a preprint version suffix matches; others logged and not used) (test). |
| M2 atlas | B's quote checks count only for the A session recorded when its quotes were written (`quotes_to_verify_B.meta.json`); snapshot present -> its records only; map key whitespace-stripped, confidence normalised (outside high/medium/low -> low), types split on `;` or `,`, unknown names, duplicate rows and duplicate coder keys logged (test). |
| M3 L5 beyond readers | `reassign`: tasks (second reading, adjudication, atlas coding or map) without a disposition for every assigned source are given once to `<session>-a1`; replaced sessions are not used (`_superseded`); reader reassignments counted per source across all chains (first assignment plus at most two), then `unreached_sources.csv`; new names never overwrite (test). |
| M4 L9 | Chapman in `finalize` (`merge_log.json`); units before round N exclude round N's own file and use mapped atlas records; search rounds 1-3 only; leads need a current audit. |
| M5 L11 | `verify_score` requires the verifier finished and audited after it finished; the verify spec goes to `labels_v2/verify/specs/`; `verify_sample` checks `records.jsonl` against the labels lock. |
| M6 downloader denylist | Kind-2 mirrors (softwareheritage, sourcegraph, archive.org, huggingface, hf.co) and the URL tokens refused on every request and redirect; Hugging Face DOIs banned; status `banned_host`. |
| minor: post-lock refusal | `_unlocked()` in registry, atlas-ids, atlas-quotes, readers, searches, leads, reassign, second, adjudication, finalize; `collect` already refused. |
| minor: repair guards | `labels2_rooms repair`: one round; a second-reading or coder-B repair only before Phase B (as v1). |
| minor: models used | `labels2_rooms status` writes `_status.json` (models per session), which the frozen collector copies per session. |
| minor: lock2 chains, amendment predicate | Handled with the scoring-side fixes (`lock2.py`). |
| minor: deny globs | `~/ledger_rooms/run1*`, the orchestrator's project folder and run-1 project folders by glob; `nbviewer.jupyter.org` denied for WebFetch and in the audit's mirror list. |
| minor: audit mirror success, Grep | A WebFetch answer starting with a fetch-failure message is not a success; kind 5 also covers Grep of own tool-results. |
| minor: sightings cross-check | `merge_log.json` lists sightings rows whose session has no flagged record of that DOI (for the label review). |
| minor: verify sample lacks `preparation` | Not changed: the verifier finds the experiment by its locator and quote; adding a column would change the frozen verifier prompt. |
| minor: order of the predictions lock | The predictions lock's binding code section is restricted to prediction-side code (lock2 fix), so label-code fixes need no amendment of it. |
