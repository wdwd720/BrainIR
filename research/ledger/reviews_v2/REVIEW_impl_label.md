not ready

Scope: `labels2_collect.py` (with `searches`, commit 828e669), `labels2_rooms.py`, `labels2_audit.py`, `labels2_canary.py`, `lock2.py`, the downloader's status/`banned_host` logic; frozen v1 modules read only. Synthetic reproductions in `~/ledger_rooms_review_impl_a/t/` (t1 B3, t2 B2, t3 B5, t5 B1). Suite: 80 pass, none exercise `labels2_*`. A bare `:N` means `labels2_collect.py` line N.

## Blockers

**B1 `labels2_collect.py:171-174` (readers).** L7/L9: the registry (atlas, Namiki 2018, 2025 catalogue included) gets a first reading; only the atlas has its own sessions (skip set). Code counts the sources of *every* spec/manifest as assigned. `atlas-ids` already wrote `atlas-map.json` listing Namiki and the catalogue, so `readers --round 0` never assigns them (t5). Fix: count only reader/reader_web specs and manifests.

**B2 `:574` (merged).** L3: a breaching second reader "is excluded". `LC.not_found()` reads every raw/pass2 session, so the excluded session's not-found row drops the record its `-r1` replacement found and verified (t2: final 0, `not_found_by_pass2`). Fix: a v2 not-found reader over non-breaching sessions, keeping the Phase A snapshot rule.

**B3 `labels2_audit.py:58,68,93` (kind-1 exception).** Paths are regex-extracted from `json.dumps(content)`: a path followed by a newline (escaped `\n`) or a period is captured with that suffix, `p in fetched` fails, and a legitimate read of the session's own WebFetch binary or oversized output becomes a breach (run 1's L37 failure; reader_web sessions must read fetched PDFs/figures). t1: exact path recovered only before `]` or a quote. I could not see the real message format (transcripts are off limits), and the exception has never run on a real transcript: CANARY_v2c audits rooms 4-6, none of which reads a tool-results file. Fix: exempt when the Read `file_path` occurs verbatim in the raw text of an earlier own tool result; before the first session, run the audit on the run2_canary room1 transcript (it contains this read) and require 1 own read, no breach.

**B4 `:386` (`_breaching`).** L3: the audit "covers every session and is newer than every session log before second-reading inputs are built and before the final aggregation". v1 enforced both in code (`labels_collect.py:177-189`); v2 leaves it to orchestrator procedure (IMPLEMENTATION_v2) and checks only that the file exists, and `leads`, `reassign`, `_atlas_session` proceed without it. A session audited mid-run or before a phaseb/repair resume that breaches later keeps contributing, and the gate reads the same stale audit. Fix: port v1's coverage and mtime checks (newest run2 `*.stream.jsonl`) into `_breaching()` and require it everywhere.

**B5 `:548` (adjudication not incremental).** Names restart at 01; `_spec`/`_write_csv` overwrite. A second run after a later wave (reader_web, reassignments, search rounds) rewrites inputs of sessions that already ran, puts new disputes into batch names whose rooms exist (launch refuses) so they end `disagreed_unadjudicated`, and re-adjudicates others (t3: a new DOI lands in `adjudication-general-01`). Fix: as `second()`, record exp_ids per spec, skip covered ones, number after existing specs; make `_spec` refuse to overwrite.

## Major

**M1 Source identity is the DOI string.** Dedicated detection is exact: `registry :124-130` (FAMILY_PRIORITY lacks `dedicated`, so a run-1 dedicated-session DOI that is not one of the three exact strings, e.g. a bioRxiv `v2` form, becomes `recent_broad`), `leads :259`, `second :489`, `adjudication :538`. Local reads of a dedicated source are invisible to kind 3, so L7 "dedicated sources go only into dedicated rooms" rests on this. Also C1 `replaces` (`:454`), the reader_web frame exclusion (`:642`) and second-reading rooms (`:503`) use `slug(record DOI)`, not the session's assigned slugs: a record typed with another DOI escapes the drop and the exclusion, and its room lacks the source (`copytree` raises after the room exists, so it can never launch, and the exception ends `schedule`). Fix: `is_dedicated()` by `LA.DEDICATED` tokens everywhere plus a `build_room` refusal; tie records to their session's assigned slugs, log others.

**M2 Atlas.** (a) `:381` B's quote checks are keyed by line and preparation, not by the A session whose quotes B saw: if A is replaced after B's Phase B, A-r1's quotes count as verified. Record the A session in `quotes_to_verify_B.csv`; use them only if it equals `_atlas_session("atlas-codeA")`. (b) `:333` falls back to live records when the snapshot has no records.jsonl (frozen rule: absent means none). (c) `atlas_map :325-326`: key not whitespace-stripped as `_atlas_key` is; `mapping_confidence` unnormalised ("High" makes every record of the line invalid after the merge, dropped); `manc_types` split only on `;`, unknown names dropped silently (a two-type line loses `multi_dn`); duplicate map rows and duplicate A/B keys (L8 "is logged") not logged.

**M3 L5 beyond readers.** `reassign :292` handles reader kinds only: a second reader, adjudicator, atlas coder or map session that ends without dispositions is never re-run, so its experiments end `no_pass2`/`disagreed_unadjudicated`. The attempt counter restarts on `-w` chains (`:302`; up to four reassignments of one source), unreached sources are never reported, and a re-run after a late breach overwrites an existing `-aN` spec.

**M4 L9.** Chapman is not implemented anywhere (IMPLEMENTATION_v2 says `finalize`). `_units_known :278` includes the current round's unit file on a re-run (fraction_new falls to 0: early stop) and counts the atlas as (atlas, UNMAPPED). `searches :230` accepts round 0, the `--round` default: four rounds possible. `leads :248` keeps breaching searches' leads when no audit file exists.

**M5 L11.** `verify_score :671` accepts a verifier without an audit row or still running (a partial file gives a spurious blocker); the verify spec goes to `work/specs` (`:659`), not `verify/`; `verify_sample` does not check `records.jsonl` against the lock's hash.

**M6 Downloader denylist (`labels2_download.py:125-133, 324-335`).** L7 ties banned hosts to L3 kind 2; IMPLEMENTATION_v2 says they are refused on every request and redirect. `BANNED_HOSTS` lacks softwareheritage.org, sourcegraph.com, archive.org and huggingface.co, and there is no URL-token check (smpuglie, pugliese_2026, wdwd720, brainir), while the crossref/Europe PMC route follows links it did not choose (open-access copies on web.archive.org are common). Room files are exempt from kind 5, so this path is unaudited. `BANNED_DOI_PREFIXES` covers Zenodo only (a Hugging Face DOI, 10.57967/, would be fetched and routed to reader_web). Status is `unreachable` plus a flag, not `banned_host`. Fix: reuse the kind-2 hosts and tokens in `banned_reason`.

## Minor

- No post-lock refusal in finalize/readers/second/adjudication/reassign/leads (L14; `check` would then fail the gate).
- `labels2_rooms.py:342` repair lacks v1's guards (one round; pass-2 and atlas-B only before Phase B).
- Models actually used are not persisted (v1 wrote `_status.json`; L8 "recorded").
- `lock2.py:57` `_chains` keeps one successor per old hash (branches lost); `check` honours amendment rows for any path, labels and non-prompt kit files included. Restrict it to `amend`'s predicate.
- `nbviewer.jupyter.org` is not denied at tool level (the audit catches it); deny `run1*` and the orchestrator's project folder by glob.
- `labels2_audit.py:63` mirror check ignores `FETCH_FAIL_PREFIXES`; the kind-5 check covers Read but not Grep of own tool-results.
- `sightings.csv` is never cross-checked against `saw_simulation_score`.
- `verify_sample.csv` omits `preparation` (atlas lines have headless and intact records).
- Order: `LOCK_predictions_v2.json` hashes all code in a binding `code` section; if it is written before these fixes, each fix needs a `lock2.py amend` row.

No deviation found in: `flags_v2` tool sets per kind; every prompt renders without leftover placeholders; coder rooms lack type_list/synonyms/driver_lines; `dedupe_v2` order; `neutral()` word list; L10 fill (literal; 316 of 336 kit `other_cells` rows are exact type tokens); exposed by nature; S5.4 inputs; sample formula and error rule; Zenodo DOIs are never fetched or assigned; `lock2` v1/P4b handling.
