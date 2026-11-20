# Resolution of review round 2 (verification of round-1 fixes)

Round-2 reviewer (fresh subagent, read-only, probes in the orchestrator's scratchpad) verdict: do not freeze; 3 blockers,
8 majors, minors. Resolutions:

| # | finding | resolution |
|---|---|---|
| 1 | multi-type lines: pass-2 rows indistinguishable once the MANC type is withheld | `name_in_paper` = the paper's name for the DN type; rows with identical identifiers become sibling rows (`sibling_index` k of `n_siblings`, ordered by pass-1 MANC type); pass 2 assigns the line's types in alphabetical order; adjudication sees the sibling columns; PREREG 6. |
| 2 | stale kit `record_schema.json` | regenerated from `schema.json_schema()`; test asserts equality. |
| 3 | blocked attempts counted as breaches | audit pairs each tool call with its result; denied calls are `blocked_attempts` (reported), only successful out-of-room access / banned fetches (and sessions without a transcript) are breaches; verified on the canary rooms (0 breaches, all attempts blocked); PREREG 6. |
| 4 | Phase A not gated or kept | `phaseb` refuses while the session runs or if already started; Phase A records / not-found list copied and hashed before the quotes are delivered; `collect` uses the snapshot and flags later changes; repair limited to one round, no pass-2 repair after Phase B. |
| 5 | KeyError reported as not_locked | dedicated `NotLocked` exception; test (missing column -> error). |
| 6 | baseline failure wipes the primary | baseline comparisons run on the primary's finite set, in their own try; status recorded; test. |
| 7 | B4 non-calls scored | non-calls excluded and counted; `turns` labels excluded from the modulation comparison and counted; PREREG 8.12; test. |
| 8 | collector fragile on realistic output | non-object JSON lines invalid; tolerant CSV reader (BOM, missing header); yes/no spellings of `quote_found` accepted, unrecognised values logged and treated as unverified; proposal files parsed leniently; all outputs written after everything is computed; prompts require header rows. |
| 9 | missing audit treated as clean | pass-2 preparation and finalize refuse unless the audit exists, covers every session and is newer than every session log. |
| 10 | dot-files locked | lock skips dot-files; verify_inputs requires each arm's `types.csv`; labels lock also covers session manifests/status and work inputs. |
| 11 | B2 grouping text vs code | PREREG 3.8 now states the body-match-first rule. |
| minor | exposure/frequency not in the type-label check; dedupe before breach exclusion; capture-recapture includes the dedicated family; wording; lock coverage; repair enforcement; mirror hosts; mapping-confidence wording; 8.2 wording; S-not-locked reason; adjudication `--name` | all fixed (kit exposed list and `freq_hz` compared; breaching pass-1 sessions removed before dedupe in both prepare and finalize; dedicated family excluded from capture-recapture; GitHub mirrors and all subdomains denied by wildcard rules, verified in a canary room after finding that a plain domain rule does not cover subdomains; `--resume` verified to keep the session context). |
