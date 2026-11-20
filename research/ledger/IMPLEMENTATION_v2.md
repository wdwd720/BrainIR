# PREREG v2: rule -> implementation (PREREG v2 L12)

Every rule of `PREREG_v2.md` and the code that implements it. Frozen v1 modules are imported, never edited. All v2 code is in
new files and is hashed in `LOCK_labelcode_v2.json` / `LOCK_scoring_v2.json` before the first v2 label session.

| rule | implementation |
|---|---|
| L1 fresh rooms `~/ledger_rooms/run2/`, no v1 content | `labels2_rooms.build_room` (copies only kit v2 files, the session's inputs and its assigned sources) |
| L2 frozen schema, merge, consensus, agreement | `labels2_collect`: `LC.collect` (frozen collector re-pointed at v2 folders), `AGG.merge_passes`, `AGG.type_labels`, `agreement.agreement` |
| C1 no web tools except search / `reader_web` (and its `second_web`, `adjudication_web`) | `labels2_rooms.flags_v2(kind)` (`WEB_TOOLS`; file tools only for other kinds); routing `labels2_collect.readers` (downloader status `abstract_only`/`unreachable`), `reassign` (reader-marked `unreachable` -> `reader_web`), `second`/`adjudication` (web groups), `_web_slugs()`; dropped earlier records `_pass1_generic` (`replaces`) |
| C4 atlas `UNMAPPED` | kit `PROTOCOL.md` section 8, `PROMPT_ATLAS_CODE.md`; frozen validator accepts the sentinel |
| L3 breach kinds 1-5, exception, family mapping | `labels2_audit.py` (frozen `audit_session` with `dedicated` -> `pugliese_dedicated`; `scan()` adds own-tool-result paths, mirror fetches, forbidden tokens in WebSearch/WebFetch results and reads of own tool-results files) |
| L3 kind 4, audit timing, verifier audit | `labels2_audit.py` (`no_transcript`; main audit refuses after the labels lock; `--verify` writes `labels_v2/verify/transcript_audit_verify.*`); `labels2_collect._breaching()` refuses without `transcript_audit.json`; the audit is re-run before `second`, `adjudication` and `finalize` (orchestrator procedure, LOG) |
| L3 consequences | `labels2_collect.reassign` (sources without disposition, breaching readers, `replaces`); `labels2_collect.redo_breaching` (`<session>-r1` once for second readers, adjudicators, atlas coders, atlas map, verifier); `_atlas_session`, `_quote_checks_generic`, `_pass2_records`, `merged` skip breaching sessions |
| L4 sightings | kit `PROTOCOL.md` section 8; `sightings.csv` copied by the frozen collector; eligibility via frozen `eligible()` |
| L5 contract, reassignment <= 2 | `labels2_collect.reassign` (attempt suffix `-a1`, `-a2`) |
| L6 eligibility, exposed by nature | frozen `eligible()`; `labels2_collect.finalize` writes `exposed_v2.csv` and passes kit list + by-nature set to `type_labels` |
| L7 registry, normalisation, download, banned hosts, atlas IDs | `labels2_collect.registry` (`norm_doi` with the v1.1 fix), `labels2_download.py` (banned hosts refused on every request and redirect; `banned_host` in `meta.json`), `labels2_collect.readers` (banned-host sources never assigned), `labels2_collect.atlas_ids` (from the kit's Cande rows) |
| L8 readers <= 6 sources | `labels2_collect.readers` |
| L8 atlas map / coders / key / duplicates / expansion / multi_dn | `labels2_collect.atlas_ids`, `atlas_map`, `_atlas_key`, `atlas_pairs`, `atlas_quotes` (key: (line ID upper-cased without spaces, headless or intact); first `record_id` kept; `exp_id = atlas:<line>:<headless|intact>:<type>`; `other_cell_types`); coder rooms without the type map (`labels2_rooms.build_room`) |
| L8 searches -> leads | kit `PROMPT_SEARCH.md`; `labels2_collect.leads` |
| L8 second reading, neutral identifiers, Phase B snapshot | `labels2_collect.second` (`neutral()` word list), `labels2_rooms phaseb` (snapshot before quotes) |
| L8 adjudication batches, seed 20261206 | `labels2_collect.adjudication` |
| L8 dedupe order | `labels2_collect.dedupe_v2` (frozen `content_signature`) |
| L8 quota slow-down | `labels2_rooms.schedule` (cap 3 above 85 %) |
| L9 recall rounds, Chapman | `labels2_collect.leads` (per-round units, fraction new), Chapman in `finalize` report |
| L10 fill | `labels2_collect.line_spec_fill` (before `type_labels`) |
| L11 verification frame (no dedicated, no `reader_web` sources), blind sample after the labels lock, new files only | `labels2_collect._verify_frame`, `verify_sample` (refuses before the lock or twice), `verify_score` (collects the non-breaching verifier's outputs with hashes into `labels_v2/verify/`), `collect` refuses after the lock |
| L13 isolation | `labels2_rooms.flags_v2`, `deny_paths`; canaries `gates_v2/CANARY_v2.json`, `CANARY_v2b.json` |
| P1 tuner v2, K calibration, B1r/B2r, gates | `typescreen_v2.py`, `jobs_v2.py`, `gha.py` builders `calibk`, `regress`, `b1r`, `b2r`; regression and determinism comparisons by digest |
| P2 G3 v2 | item 4' decided by `g3v2_preview.py` -> `gates_v2/G3v2_PREVIEW.json` (before the freeze); formal run: `gha.py` builder `g3v2`, `g3v2_evaluate.py` (items 1-3, 5; 4' reported) |
| P3 B4 v2 | `b4v2.py` (verdict-based bounds, every-run-in-bounds for `halts`, majority for `saturates`) |
| P4 platform, trust gate | `gha.py`, `gha_runner.py`, `.github/workflows/ledger-gha.yml`; `gates_v2/TRUST_GATE.json` |
| P5 locks, push after labels | `lock2.py predictions`; push procedure (LOG) |
| S4 runs and flags | `scoring_v2/pipeline_v2.py`, `scripts/score_v2.py` |
| S5 gate | `scripts/gate_v2.py` -> `gates_v2/UNBLINDING_GATE.json` |
| P4b, L12 locks, amendments, check | `lock2.py prereg / labelcode / scoring / predictions / labels / amend / check` (git-tracked code only; `labelcode` hashes this map; snapshot sections reported only; archive members skipped; chained hashes; amendment chains from `AMENDMENTS_v2.jsonl`; `amend` refuses rules, data, kit after the first session, and anything after `UNBLIND.json`) |
