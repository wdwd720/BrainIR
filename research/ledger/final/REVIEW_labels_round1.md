# Label-side review, run 1 (tag ledger-labels-v1)

**Verdict: labels usable with caveats.** `records.jsonl` and `type_labels.csv` are exactly what the PREREG §6 rules produce from the raw outputs. No included session breached the access rules, score-flagged records are excluded as designed, and the lock is intact. The caveats are about coverage and the completeness statistic.

## Blocker
None.

## Major
1. **Coverage loss in the walking and screen literature.**
   - Neither excluded pass-1 family was replaced. pass1-atlas wrote 0 records; pass1-walking_stopping's 10 are excluded. recent_broad's scope (`kit/families.json`) omits their papers.
   - Final records: 0 from the Cande 2018 atlas, Bidaye 2014, Bidaye 2020 and Sapkal 2024; 6 from Braun 2024.
   - The search sessions hold 82 atlas records and 64 search-only walking-paper records (16 and 34 without search-search_names); none can enter the consensus.
   - 141 final → 100 eligible records → 27 types. 18 types have a front-leg yes/no label and 5 of those are exposed, so at most 13 can reach the primary set. The truth set is a non-random subset.

2. **The capture-recapture result is wrong (labels unaffected; the code is frozen).**
   - (a) **Deviation.** `norm_doi` (`labels_collect.py:162`) strips the article number from unversioned eLife DOIs (`10.7554/elife.34275` → `10.7554/elife`), merging all eLife papers into one unit.
     - Chapman estimate: 181.6 as reported (n1=46, n2=100, m=25), 197.1 with this fixed.
     - 5 search records are wrongly dropped from `search_only_records.jsonl`.
     - `sources.csv` merges all eLife sources into one row.
   - (b) **Unaddressed case.** PREREG's exclusion clause names only pass-1, pass-2 and adjudication sessions; the code drops breaching pass-1 sessions but keeps the breaching search-search_names (`labels_collect.py:254-258`). That session supplies 40 of the 100 search units and 94 of the 148 search-only records.
   - With (a) fixed and (b) excluded: 125.0 (n1=49, n2=62, m=24).

## Minor
3. **Guard timing and audit wording.**
   - All 5 successful outside-room reads (3 sessions, their own WebFetch images) were before the guard started at 17:13:45Z.
   - 2 of the 9 failed attempts also predate the guard (pass1-steering and pass1-escape_landing, PDFs).
   - All 14 outside-room reads show permissionDecision `accept`: none was "denied by the tool permissions" (`labels_audit.py:10,132`); `--restricted` (`labels_rooms.py:13`) did not confine them.
   - The breach classification holds under PREREG's "SUCCESSFUL" wording, but exclusion depended on timing: 8 sessions made the same attempt and were not excluded.

4. **Evidence is mediated by the fetch tool.**
   - Every finished session also used claude-haiku-5-5, inferred to be WebFetch's page processing (api-request lines log only Opus).
   - Raw files were off-limits, so quotes and their checks depend on that model.
   - All 144 labelled experiments had `quote_found=true`; the 22 `false` checks are exactly the not-found experiments.
   - Agreement between passes: front-leg yes/no 112/112 and manc_type 144/144. 128 of 166 `name_in_paper` values equal the pass-1 type.
   - 21 input locators or stimulation fields contain behaviour vocabulary, which could cue pass 2. No input reveals a pass-1 type beyond `name_in_paper`. Agreement likely overstates independent reliability.
   - About a third of fetches returned codes ≥400, mostly 429.

5. **Records dropped, all per the rules.**
   - 22 experiments (from 3 DOIs; 20 of them grooming's) were not found by pass 2. They include 3 of the 4 sibling groups; the remaining group matched 3/3.
   - adjudication-general skipped 3 of 26 experiments (dropped as unresolved).
   - 34 of 141 final records are ineligible because a reader flagged a score. The 15 from non-dedicated sessions cite 6 non-dedicated DOIs; pass 1 flagged 11 (escape_landing) and 5 (steering), pass 2 flagged 0 of those experiments. Where a score was seen cannot be determined without reading results.

6. **Latent code gaps (no effect here).**
   - A breaching pass-2/adjudication session would taint only its valid records (`labels_collect.py:243-247`).
   - The pass-2 input gate checks audit coverage of pass-1 sessions only (`labels_prepare.py:44`).
   - `lock.py check` neither reports missing `raw` files nor verifies `prereg_lock_sha256` (`lock.py:135`). I verified both.
   - Exact-string de-duplication dropped 0; one concordant near-duplicate pair remains.

## Verified without discrepancy
- **Consensus:** re-implemented from PREREG; 0 differences over 477 types, all fields.
- **Merge:** recomputed from raw inputs; category exp_id sets match: agreed 104, adjudicated 37, not found 22, unresolved 3, others 0. Final records equal `records.jsonl`; none comes from a breaching session.
- **Pass-2 inputs:** identifier fields only; quotes entered rooms only at Phase B, after Phase A ended; snapshot hashes match; seeded reading order reproduced (57 fields).
- **Audit:** I find the same 3 breaching sessions and 9 failed attempts. No banned-host or dedicated-source fetch was attempted outside the dedicated sessions, checked by identifier and by article-id overlap with the dedicated sessions' 131 source URLs (0 hits). Residual: 386 non-dedicated fetches keyed by PMC/PMID/PPR ids or free-text queries cannot be linked this way, and WebSearch-snippet sightings cannot be excluded unread. Only the 7 allowed tools were used, and transcripts match the stream logs.
- **Raw copies:** 75/75 byte-identical; prompts and flags as frozen.
- **Lock:** `check` passes. 199 label/kit files and 17 label-side code files are identical in the tag and the working tree; label code and kit are unchanged since the prereg.
- **Redaction:** only the two substitutions in 21 files.
- Chapman formula correct; 29 label tests pass.

## Scope notes
- Beyond the brief I read PREREG headings and §7 lines 327-331, `lock.py` lines 1-60, label-side hashes in `LOCK_prereg_v1.json` and the guard log, and counted patterns in fetch prompts and queries without displaying them. `research/ledger/HANDOFF_1.md` has uncommitted edits that are not mine; I did not open it.

## v1.1 verification (tag ledger-labels-v1.1, commit a21a380)

**Finding 2 is resolved by v1.1, and nothing in v1.1 is wrong.**
- **Unchanged files.** Byte-identical to v1: `records.jsonl`, `type_labels.csv`, `spot_check_sample.csv`, `merge_log.json`, `synonyms.csv`, `driver_lines.csv`, plus the copied `transcript_audit.json`.
- **Changed files.** `agreement.md` differs only in the capture-recapture line and `agreement.json` only in `capture_recapture`. `sources.csv` and `search_only_records.jsonl` also differ.
- **Added and omitted.** v1.1 adds `CHANGELOG.md` and omits `transcript_audit.md` and `REDACTION.json`, which stay in v1.
- **Completeness.** 125.0 (n1 49, n2 62, m 24) equals my recomputation from the v1 raw inputs. Stricter DOI canonicalisation changes nothing.
- **Search-only and sources.** `search_only_records.jsonl` has 56 records, matching my recomputation in set and order, none from the breaching session. `sources.csv` has 77 rows and no merged eLife row; sessions and `n_final_records` per DOI match my recomputation and sum to 141.
- **Lock.** `lock.py check` passes for v1.1 and still for v1. The tag holds exactly the locked bytes: labels 12/12, raw 135/135, kit 17/17, code 56/56. The chained hashes of the v1 and prereg locks match, and v1's files are unchanged since `ledger-labels-v1`.
- **Notes, not errors.**
  - The audit-freshness gate passed on the copied audit's preserved timestamp. Content is identical and there are no new sessions.
  - Excluding the search session applies PREREG's general exclusion rule, as the changelog states. The estimate now rests on one search session.
  - `lock.py check` still skips raw presence and the chained hashes; I verified both.
