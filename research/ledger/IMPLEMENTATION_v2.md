# PREREG v2: rule -> implementation (PREREG v2 L12)

Every rule of `PREREG_v2.md` and the code that implements it. Frozen v1 modules are imported, never edited. All v2 code is in
new files and is hashed in `LOCK_labelcode_v2.json` / `LOCK_scoring_v2.json` before the first v2 label session.

| rule | implementation |
|---|---|
| L1 fresh rooms `~/ledger_rooms/run2/`, no v1 content | `labels2_rooms.build_room` (copies only kit v2 files, the session's inputs and its assigned sources) |
| L2 frozen schema, merge, consensus, agreement | `labels2_collect`: `LC.collect` (frozen collector re-pointed at v2 folders), `AGG.merge_passes`, `AGG.type_labels`, `agreement.agreement` |
| C1 no web tools except search / `reader_web` | `labels2_rooms.flags_v2(kind)` (`--tools`/`--allowedTools` = file tools only for other kinds) |
| C4 atlas `UNMAPPED` | kit `PROTOCOL.md` section 8, `PROMPT_ATLAS_CODE.md`; frozen validator accepts the sentinel |
| L3 breach kinds 1-5, exception, family mapping | `labels2_audit.py` (frozen `audit_session` with `dedicated` -> `pugliese_dedicated`; `scan()` adds own-tool-result paths, mirror fetches, forbidden tokens) |
| L3 audit timing | `labels2_collect._breaching()` refuses without `transcript_audit.json`; the audit is re-run before `second`, `adjudication` and `finalize` (orchestrator procedure, LOG) |
| L3 consequences | `labels2_collect.reassign` (sources without disposition, breaching readers) ; new sessions for breaching second readers / adjudicators / map / verifier (orchestrator procedure, LOG) |
| L4 sightings | kit `PROTOCOL.md` section 8; `sightings.csv` copied by the frozen collector; eligibility via frozen `eligible()` |
| L5 contract, reassignment <= 2 | `labels2_collect.reassign` (attempt suffix `-a1`, `-a2`) |
| L6 eligibility, exposed by nature | frozen `eligible()`; `labels2_collect.finalize` writes `exposed_v2.csv` and passes kit list + by-nature set to `type_labels` |
| L7 registry, normalisation, download, atlas IDs | `labels2_collect.registry` (`norm_doi` with the v1.1 fix), `labels2_download.py`, `labels2_collect.atlas_ids` (from the kit's Cande rows) |
| L8 readers <= 6 sources | `labels2_collect.readers` |
| L8 atlas map / coders / key / duplicates / expansion / multi_dn | `labels2_collect.atlas_map`, `atlas_pairs` (key: line ID upper-cased without spaces; first `record_id` kept; `exp_id = atlas:<line>:<type>`; `other_cell_types`) |
| L8 searches -> leads | kit `PROMPT_SEARCH.md`; `labels2_collect.leads` |
| L8 second reading, neutral identifiers, Phase B snapshot | `labels2_collect.second` (`neutral()` word list), `labels2_rooms phaseb` (snapshot before quotes) |
| L8 adjudication batches, seed 20261206 | `labels2_collect.adjudication` |
| L8 dedupe order | `labels2_collect.dedupe_v2` (frozen `content_signature`) |
| L8 quota slow-down | `labels2_rooms.schedule` (cap 3 above 85 %) |
| L9 recall rounds, Chapman | `labels2_collect.leads` (per-round units, fraction new), Chapman in `finalize` report |
| L10 fill | `labels2_collect.line_spec_fill` (before `type_labels`) |
| L11 verification frame, blind sample, scoring | `labels2_collect.verify_sample`, `verify_score` |
| L13 isolation | `labels2_rooms.flags_v2`, `deny_paths`; canaries `gates_v2/CANARY_v2.json`, `CANARY_v2b.json` |
| P1 tuner v2, K calibration, B1r/B2r, gates | `typescreen_v2.py`, `jobs_v2.py`, `gha.py` builders `calibk`, `regress`, `b1r`, `b2r`; regression and determinism comparisons by digest |
| P2 G3 v2 | `gha.py` builder `g3v2`; `g3v2_evaluate.py` (alpha 0.01, no correction) |
| P3 B4 v2 | `b4v2.py` (verdict-based bounds, every-run-in-bounds for `halts`, majority for `saturates`) |
| P4 platform, trust gate | `gha.py`, `gha_runner.py`, `.github/workflows/ledger-gha.yml`; `gates_v2/TRUST_GATE.json` |
| P5 locks, push after labels | `lock2.py predictions`; push procedure (LOG) |
| S4 runs and flags | `scoring_v2/pipeline_v2.py`, `scripts/score_v2.py` |
| S5 gate | `scripts/gate_v2.py` -> `gates_v2/UNBLINDING_GATE.json` |
| locks | `lock2.py prereg / labelcode / scoring / predictions / labels / check` |
