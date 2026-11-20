# Resolution of review round 3 (verification of round-2 fixes)

Round-3 reviewer (fresh subagent, read-only, end-to-end synthetic probe of the label workflow): verdict do not freeze;
1 blocker, 3 majors, 3 minors, all in the label-side scripts. Resolutions:

| # | finding | resolution |
|---|---|---|
| 1 | audit decided "failed" by searching result text for words ("restricted", "blocked", "permission"), so a successful fetch of the dedicated paper could be downgraded, and 429/redirect results with no content could count as breaches | a call failed only if the harness marked `is_error`, or (WebFetch) the result starts with a fixed harness no-content prefix ("The server returned HTTP", "REDIRECT DETECTED", ...); page content is never searched; the dedicated-source tokens include the PMC id; unit test with the reviewer's cases; canary transcripts re-audited (all denials blocked; the one pre-wildcard successful github.io fetch caught as a breach) |
| 2 | Grep regex patterns path-tested (false breaches) | Grep: only `path` and `glob` are checked; Glob: the pattern is checked as a path with the room test (absolute patterns inside the room are fine) |
| 3 | Phase A snapshot bypassed when Phase A wrote no records; not-found list not compared | the snapshot's hash file is authoritative: a file absent from the snapshot means Phase A wrote nothing (later records are ignored), both `records.jsonl` and `not_found.csv` are compared and changes flagged |
| 4 | pass-2 preparation did not check audit freshness | added (same rule as finalize) |
| 5 | `lock.py check` ignored `sessions` / `work_inputs` | added |
| 6 | sibling groups split across families after dedupe; driver lines unsorted in the key | sibling groups are formed across all kept records (driver lines sorted) and each group goes whole to the pass-2 session of its earliest-family member |
| 7 | pass 2 could copy `sibling_index`/`n_siblings` into records (invalid) | prompt says not to |

A permanent end-to-end test of the label workflow (`ledger/tests/test_label_workflow_e2e.py`, adapted from the reviewer's
probe) now covers collect, siblings, Phase A snapshot and Phase B, adjudication inputs, audit freshness and finalize.
