# BrainIR prediction ledger: pre-registration, version 2 (run 2)

Status: **version 2**, frozen by the git tag `ledger-prereg-v2` with `LOCK_prereg_v2.json` (this file, `RUN2_PROMPT.md`, the
labeler kit v2 in `research/ledger/kit_v2/`, the hashes of every v1 lock, the gate evidence and reviews present at the freeze).
Spec: `research/ledger/RUN2_PROMPT.md`. Decisions: `LOG.md` L49+. Review: `reviews_v2/`.

**What v2 is.** The v1 rule (PREREG v1 section 12) forbids amending a stage after it has produced data, so **v1 is not
amended**: rulebook v1, predictions v1, labels v1 and v1.1 stay exactly as locked. v2 is a **new, separately pre-registered
label collection** plus **new secondary prediction arms**, frozen here before either produces any data.

**What changes relative to PREREG v1** (everything else in PREREG v1 applies unchanged):

| v1 item | in v2 |
|---|---|
| section 6 breach rule | replaced by L3 |
| meaning of `saw_simulation_score` | replaced by L4 |
| search-only records never enter the consensus | replaced by L6 (searches give leads; every record passes two readings) |
| first-reading sources: open web search by family | replaced by L7-L8 (registered, mechanically downloaded sources; no web tools for readers) |
| exposed list | kit list plus types "exposed by nature" (L6) |
| primary truth | labels v2 (S2); v1.1 is a sensitivity run |
| section 13 (push predictions only after labels freeze) | predictions v1 have been public since 2026-11-20 10:31 PST (after labels v1 froze); predictions v2 are pushed only after labels v2 are locked (P5) |
| `UNBLIND.json` | one flag file with one entry per run (S4), each naming its locks with their SHA-256, who authorised it and when |

| version | date | change | stage data existing at the time | labels existing | joined information existing |
|---|---|---|---|---|---|
| 1 | 2026-11-19 | initial (tag `ledger-prereg-v1`) | none | no | no |
| 2 | 2026-11-20 | new label collection (Part L) | predictions v1; labels v1, v1.1 | yes (v1, v1.1; aggregate counts seen) | no |
| 2 | 2026-11-20 | tuner v2 arms B1r/B2r (P1) | predictions v1 | yes | no |
| 2 | 2026-11-20 | G3 v2 with item 4' (P2), computed before the freeze from stored simulations | predictions v1; run-1 G3 runs | yes | no |
| 2 | 2026-11-20 | B4 v2 calls from stored replicates (P3) | predictions v1 (B4) | yes | no |
| 2 | 2026-11-20 | label versions, run plan, flags (Part S) | as above | yes | no |

---

## Part L: labels v2

**L1. Fresh collection.** Labels v2 are made from scratch by new blind sessions in new rooms (`~/ledger_rooms/run2/`). No v2
room contains a v1 record, label table or transcript. v1 and v1.1 are used only in sensitivity run S-a and in `v1_vs_v2.md`.
Nothing of v1 or v1.1 is ever pooled with v2.

**L2. Unchanged from v1.** The labeling conventions (`kit/PROTOCOL.md` sections 1-7), the record schema and vocabularies
(frozen validator `brainir_ledger.labels.schema`), the two readings plus adjudication (PREREG v1 section 6), the final-record
rule (`aggregate.merge_passes`), and the type consensus rule (`aggregate.type_labels`, eligibility `aggregate.eligible`).
Clarifications (none depends on a particular neuron):
- C1. Sources are downloaded mechanically before the session and placed in the room (L7). Readers, second readers,
  adjudicators, atlas sessions and the verifier have **no web tools**, with one exception: sources whose full text could not
  be downloaded (downloader status `abstract_only` or `unreachable`, or marked `unreachable` by a reader; never banned-host
  DOIs, L7) are read by separate `reader_web` sessions with WebFetch only, for those DOIs, and their second reading, Phase B
  and adjudication run with the same WebFetch-only flags; their records are outside the verification frame. When a source is
  reassigned (L3, L5), the earlier session's records of that source are dropped. PROTOCOL section 5's mention of
  `sources_seed.csv` does not apply.
- C2. Every session writes the contract files of L5.
- C3. `saw_simulation_score` takes the meaning of L4; the reader also writes where (`out/sightings.csv`).
- C4. Atlas records are coded by line ID with `manc_type = UNMAPPED` (the frozen validator's sentinel) and mapped by script
  (L8).

**L3. Breach rule (replaces v1's).** A session breaches if its transcript shows any of:
1. a SUCCESSFUL file access outside its own room, **except** a read of a file in its own `<project>/<session-id>/tool-results/`
   folder whose path appears in one of its own earlier tool results (a binary saved by its own WebFetch of an allowed host, or
   an oversized output of its own tool); reading the repository, any ledger directory, another room, another session's
   project folder, the orchestrator's folders or a temporary folder is a breach;
2. a SUCCESSFUL fetch of a banned host or any subdomain (github.com, githubusercontent.com, github.io, zenodo.org, jsdelivr.net,
   nbviewer, githack.com, statically.io, gitee.com, softwareheritage.org, sourcegraph.com, archive.org, gitlab.com,
   bitbucket.org, codeberg.org, huggingface.co), or of any URL containing `smpuglie`, `pugliese_2026`, `wdwd720` or `brainir`;
3. a SUCCESSFUL fetch of a dedicated source (the two Pugliese papers, the 2026 Sapkal preprint) outside a dedicated session;
4. no transcript (unauditable);
5. a WebSearch or WebFetch result, or a read of the session's own tool-results file, whose text contains `wdwd720`, `smpuglie`
   or `BrainIR` (the repository, its owner, the authors' code); files placed in the room by the orchestrator are exempt.
Attempts denied by the tooling are reported, not breaches. The audit is the frozen `labels_audit.audit_session` (v2 family
`dedicated` passed as its `pugliese_dedicated`) plus kinds 1-exception and 5 (`labels2_audit.py`). It covers every session and
is newer than every session log before second-reading inputs are built and before the final aggregation. Consequences: a
breaching reader's records are excluded and its sources are reassigned to a new session (within L5's limit of two
reassignments per source); a breaching second reader, adjudicator, atlas coder or atlas-map session is excluded and its task
is given once to a new session with the same inputs (`<session>-r1`; a breaching replacement is not replaced again); a
breaching verifier voids the verification, which is redone once by a new session with the same sample; leads of a
breaching search session are dropped.

**L4. Score sighting.** A sighting is seeing a rhythm score, a rank or a driver/non-driver call for a DN type from the
Pugliese-type connectome activation screen, wherever printed (the Pugliese papers, the simulation part of the 2026 Sapkal
preprint, any BrainIR output). Another paper's own model does not count. The reader sets `saw_simulation_score = true` on the
affected records and writes `out/sightings.csv` (`doi, locator, what_was_seen` in {rhythm_score, rank, driver_call},
`types_as_printed`). Records with a sighting are not eligible.

**L5. Session contract.** Every session writes `out/dispositions.csv`, one row per assigned source: `doi, disposition` in
{records, no_qualifying_experiment, unreachable}, `n_records, reason`. A source without a disposition (including those of a
session that ended early) is reassigned to a new session, at most twice; then it is reported as unreached. Valid records of a
non-breaching session that ended early are kept for the sources it gave a disposition; its records of a source without a
disposition are dropped when that source is reassigned (C1). Sessions have no time limit. `assigned_sources.csv` has the columns
`doi, slug, title, status`.

**L6. Eligibility.** A record is eligible whatever session found it once it has passed the second reading (Phase A, Phase B)
and, where the readings disagree, adjudication, and is eligible under the frozen consensus rule (no sighting, mapping
confidence not `low`, a mapped MANC type). **Exposed by nature:** a type whose eligible records all come from dedicated
sessions is added to the exposed set (`labels_v2/exposed_v2.csv`), so it never enters the primary set. The v2 exposed set =
`kit_v2/exposed_types.csv` (unchanged from v1) plus `exposed_v2.csv`.

**L7. Sources.** Registry v2 = the union of the v1.1 registry (`labels_v1_1/sources.csv`), every DOI in any run-1 record of
any session (the excluded ones included), the atlas (10.7554/eLife.34275), Namiki 2018 (10.7554/eLife.34272), the 2025
catalogue (10.7554/eLife.107450), the dedicated sources, and every DOI the v2 search rounds report. DOIs are normalised
(lower case; an eLife version suffix stripped, the article number kept: the v1.1 fix). A DOI list carries no outcome. A
script with no model in the loop (`labels2_download.py`) downloads each source (full text as text, figures as images,
supplementary tables as text or CSV, PDFs as text plus page images; Europe PMC and PMC open-access packages first; back-off
on HTTP 429; failures logged) into a cache with a SHA-256 manifest and copies each source only into the rooms assigned it.
The orchestrator never opens a downloaded paper. Dedicated sources go only into dedicated rooms. A DOI on a banned host
(L3 kind 2, e.g. a Zenodo deposit) is registered but never fetched, live or otherwise, nor assigned (status `banned_host`).
The PMC open-access route reads the public PMC open-data bucket (the `oa.fcgi` package service was retired in August 2026). `atlas_line_ids.csv` is
built by the orchestrator from the kit's Cande rows (`kit/driver_lines.csv`, line IDs only, read in run 1 by OCR); the map
session may add line IDs it finds.

**L8. Sessions.**
- Readers: at most 6 sources per session, by family (walking and stopping, grooming, steering, escape and landing,
  driver-line resources, the dedicated simulation papers, recent broad studies); the family title orients, the task is the
  assigned sources only.
- Atlas (Cande et al. 2018): (i) one map session assigns DN types to every line ID from the atlas's figures and tables,
  Namiki 2018 and the 2025 catalogue (names only; `out/atlas_line_map.csv`). This map is a single reading: its
  `mapping_confidence` becomes the records' `mapping_confidence`. (ii) Two independent coding sessions code each line's
  activation result by line ID without the map (coder A = first reading, coder B = second reading; B also checks A's quotes
  in Phase B). Key = (the line ID upper-cased without spaces, headless or not), so a line tested headless and intact gives two
  experiments (PROTOCOL section 1); per key one record per coder (a duplicate keeps the first `record_id` and is logged).
  (iii) A script maps each key's records to one record per mapped type (`exp_id = atlas:<line>:<headless|intact>:<type>`); a line mapped to two or more types gets `line_specificity = multi_dn` with `other_cell_types` = its
  other mapped types (this precedes L10); an unmapped line stays `UNMAPPED` (ineligible).
- Searches (four kinds: by type name, by behaviour, by driver-line ID, by papers citing the atlas, Namiki 2018 or the 2025
  catalogue) have web tools and write leads only (`doi, title, year, name_in_paper, manc_type, family_hint, locator`); new
  DOIs are registered, downloaded and given to readers.
- Second reading: identifiers only, as v1, with behaviour words in `source_locator` and `stimulation` replaced by `[...]`
  (whole words, case-insensitive; fixed list: walk, walking, stop, stopping, halt, halting, groom, grooming, turn, turning, steer, steering, escape, takeoff,
  take-off, jump, landing, flight, backward, forward, rhythm, rhythmic, locomotion, leg, legs, posture, freeze, freezing);
  the same source files are in the room; Phase B checks the first reader's quotes after Phase A is snapshotted (v1).
- Adjudication: as v1, at most 6 sources per session; dedicated experiments have their own sessions.
- Duplicates across first-reading sessions (identical frozen content signature) are kept once, from the session earliest in
  the order atlas, driver_line_resources, grooming, walking_stopping, steering, escape_landing, recent_broad, dedicated
  (ties: session name).
- Model as run 1 (`--model opus`, fallback `sonnet`, recorded). Quota (L36): above 85 % of the seven-day window at most 3
  sessions run at once; the collection is never stopped for quota alone.

**L9. Recall rule.** Units = (normalised DOI, MANC type). After the first complete reading of the registry, run search
rounds (the four kinds, fresh sessions) until a round adds fewer than 10 % new units relative to all units known before it
(first readings plus earlier rounds' leads), or three rounds have run. Chapman estimate between the first reading's units and
round 1's units (dedicated family excluded), reported with its assumptions (closed population, independent lists, equal
catchability; both lists come from the same model family, so it is likely low).

**L10. Line-specificity fill (after merging, before the consensus).** Only records whose `line_specificity` is `unknown` and
one of whose driver-line IDs matches a `line_id` of `kit_v2/driver_lines.csv` (case-insensitive): if a matching row's
`other_cells` names a MANC DN type of the type list -> `multi_dn`; otherwise, if a matching row's `other_cells` is non-empty
-> `minor_offtarget`; the named cells are added to `other_cell_types`. The script never sets `clean` (a line is clean only when
a source says so, i.e. a reader recorded it). Name ambiguity (`candidate_types`) is ignored. Every fill is logged. The
consensus is computed after the fill.

**L11. Verification sample.** Drawn once, after `LOCK_labels_v2.json`, from the locked records; everything the verification
writes is a new file under `labels_v2/verify/` (the sample, the verifier's collected outputs with their hashes, its transcript
audit `transcript_audit_verify.json`, `verification.json`), hashed in the gate report; no locked file is rewritten. Frame: eligible final records that are neither dedicated nor from `reader_web` sources, sorted by `exp_id`; sample:
`numpy.random.default_rng(20261203).choice(n, min(30, n), replace=False)`. A fresh blind session receives the identifiers,
locator and quote but **not** the recorded front-leg value; it reports `quote_found` and its own `front_leg_rhythm` reading. A
script compares: an error is a different value or `cannot_verify`; error rate = errors / sample size. **Above 10 % is a
blocker.** A breaching verifier is replaced once (L3); if the replacement also breaches, gate 3 fails.

**L12. Code.** All v2 label-side code, the gate script and the scoring v2 code are written after this freeze and locked
before the first v2 label session (`LOCK_labelcode_v2.json`, `LOCK_scoring_v2.json`), together with
`IMPLEMENTATION_v2.md` (each rule of this document -> the code that implements it), which a fresh reviewer checks before
that session. **Amendments.** After a lock, a file it hashes may change only as a bug fix (code made to do what this text
says; no rule changes): code and `IMPLEMENTATION_v2.md` until the unblinding, kit files (`kit_v2/`) only before the first v2
label session (with a row in `kit_v2/CHANGELOG.md`, itself amended). Each change is recorded before it is committed with
`lock2.py amend` in `AMENDMENTS_v2.jsonl` (path, old and new SHA-256, reason, whether v2 sessions had started and v2 records
existed, UTC) and logged in the LOG; `lock2.py check` counts a file as matching only if recorded amendments lead from its
locked hash to its current hash; the gate report lists every amendment. Rules, records, labels and predictions are never
amended. After `UNBLIND.json` exists the tool refuses everything except the fix of a crash in the scoring v2 code (RUN2_PROMPT
Stage 4: fix only the crash, log it, never alter a rule; `--crash-fix`). An amendment is a new version of the file with its
changelog row; the lock file is never edited, and the locked version stays in git at the lock's commit. Code-snapshot sections of a lock
(`prediction_code_snapshot`, `code_snapshot`) only record code at that moment; the binding code hashes are those of
`LOCK_labelcode_v2.json`, `LOCK_scoring_v2.json` and `LOCK_predictions_v2.json`. After this freeze, reviews and gate evidence
are added as new files; files hashed by this lock are not edited.

**L13. Isolation.** Run 1's launcher flags (`labels_rooms.FLAGS`: `--restricted`, banned hosts with every subdomain) plus
v2 deny rules: the mirrors of L3 kind 2; reads and edits of the repository, `~/ledger_rooms/run1*`, the review folders, the
orchestrator's project folder and every run-1 session's project folder, `~/ledger_rooms_review*`, `/private/tmp`, `/tmp`;
other v2 sessions' project folders are blocked by `--restricted` (canary 2). Web tools only for search sessions (WebSearch
and WebFetch) and for `reader_web` sessions and their second readings and adjudications (WebFetch only). The canaries (`gates_v2/CANARY_v2*.json`) showed the required blocks and permissions with tool
rules alone; if a later canary or audit shows a leak, sessions run inside `sandbox-exec` denying those reads.

**L14. Process.** Each of: the label review, the verification, the gate, runs once. A failed gate ends the collection (no
further sessions to rescue it). After `LOCK_labels_v2.json`, nothing in labels v2 changes (the verification
adds new files under `labels_v2/verify/` only, L11).

---

## Part P: prediction additions (all secondary; A1 stays primary and untouched)

**P1. Tuner v2 (two-fly comparison).** B1's locked procedure (PREREG v1 3.4: `n_active_lower = 10`, cap 200, start 128,
halve/double/bisect, at most 10 runs, T = 1.0 s, seeds 0..15) plus one acceptance condition: at least K active front-leg
MNs in the accepted run (a run inside the activity bounds with fewer counts as too weak). Module `typescreen_v2.py`; K = 0
is B1's procedure.
- **K on DNg100 alone:** the smallest K in {1, 2, 3, 5, 10} for which the DNg100 pair scores >= 0.5 in at least 12 of 16
  seeds (an unusable seed counts as < 0.5) on both the MANC and the MaleCNS front-leg networks. If none: per network, the
  lowest current of 128, 256, 512 at which the DNg100 pair at that fixed current scores >= 0.5 in >= 12 of 16 seeds becomes
  the start current of the tuner (acceptance as B1); if none, B1r/B2r are not run. No other neuron is run before K is fixed;
  DNb08 is reported afterwards and never tuned on.
- **B1r** = tuner v2 on B1's 321 groups (MANC); **B2r** = tuner v2 on B2's 328 groups (MaleCNS, B2's mapping). Two-fly
  comparison: Spearman B1r vs B2r over common types, top-10 overlap, band agreement.
- Gates: tuner regression (K = 0 reproduces B1's digests on 30 random types, seed 20261204, x 16 seeds); positive control
  (DNg100 >= 0.5 in >= 12 of 16 seeds in B1r and B2r: tautological by construction, reported; DNb08 reported as the
  non-tautological check, not a gate); determinism (100 random jobs per arm, seed 20261205, identical digests); baseline
  checks; independent review of code and calibration for any use of a neuron other than DNg100.

**P2. B3 and B6 (full cord).** Procedure of PREREG v1 3.7 / 3.11 and LOG L14, unchanged. **G3 v2** = PREREG v1 section 9
items 1-3 and 5 unchanged, item 4 replaced by:
> **4'. Coupling between legs is consistent with the authors' own traces under the same test.** PREREG v1 4.7 offsets
> (leg signal version 1, same eligibility) for our G3 replicates (both DNg100 at 380, T = 2 s, seeds 0..63) and the authors'
> 32 replicates of run 33195857. A pair of the seven reported pairs is evaluable if it has >= 8 eligible replicates in both.
> For each evaluable pair: permutation test of |R_ours - R_authors| (pool the eligible offsets, re-split into the original
> group sizes 10,000 times, seed 20261202; p = (1 + #{perm >= observed}) / 10,001). **4' passes if at least three pairs are
> evaluable and every evaluable pair has p >= 0.01** (the alpha of PREREG v1 4.7; no multiplicity correction).
**Inputs known; computed before this freeze** by `ledger/scripts/g3v2_preview.py` -> `gates_v2/G3v2_PREVIEW.json` (both hashed by
the prereg v2 lock), from the stored run-1 G3 runs (`data/ledger/calibration/g3_v1/results.pkl`, sha256
61794801ee13d683c137fa906d1b94840164215a4bf0155037e44f8fa27fc1eb; bit-identical on the new platform per the trust gate) and
the authors' trace file (sha256 317b466d5b139f93dbcb930e69178db6b0d4daa8987e9adac210d72a9d91a876):

| pair | n ours / authors | R ours / authors | p |
|---|---|---|---|
| T1L-T1R | 34 / 13 | 0.234 / 0.330 | 0.627 |
| T2L-T2R | 29 / 15 | 0.226 / 0.209 | 0.888 |
| T3L-T3R | 13 / 4 | 0.595 / 0.626 | not evaluable |
| T1L-T2L | 29 / 12 | 0.590 / 0.585 | 0.981 |
| T2L-T3L | 8 / 2 | 0.583 / 1.000 | not evaluable |
| T1R-T2R | 37 / 18 | 0.140 / 0.602 | **0.0035** |
| T2R-T3R | 46 / 27 | 0.879 / 0.746 | 0.058 |

Under the governing rule item 4' **fails** (T1R-T2R). **Item 4' is decided by this preview: B3 and B6 are not locked in run 2;
the formal run is reported.** For the record: a Bonferroni rule (p >= 0.01 / 5) would pass, and a
coupled-status match (v1 4.7 calls per pair) would fail (T1L-T2L, T1R-T2R). The strict rule was chosen because it is v1's own
alpha and because the review showed the correction would turn this fail into a pass. B3 is marked "gate chosen with inputs
known". G3 v2 is still run formally on GitHub (items 1-3 and 5; item 4' recomputed and
reported only) and evaluated before the first v2 label session.

**P3. B4 v2 (calls from the stored B4 replicates; no new simulation).** Data: `data/ledger/arms/B4/results.pkl` (sha256
94cd68fd0e313123f6dbbc02b1258e7c541d20d0e1961629982f4a0b4ce2e3c2), every result checked against the digests locked in predictions v1. For type t at strength s in {32, 128,
512}: R = seeds whose background-only run scores >= 0.5 (fewer than 8 -> `background_not_rhythmic`); L = seeds in R where
t's run scores < 0.5; in bounds = the run's screen verdict is not `strong` (B4's configuration: <= 1,500 active neurons and
<= 100 above the high-firing threshold); fall = (background active MNs - t's active MNs) / max(background active MNs, 1).
If |L| >= 0.75 |R|: `halts` if every run in L is in bounds and the median fall over L is >= 0.25; `saturates` if more than
half of L is out of bounds; otherwise `rhythm_lost_other`. If |L| < 0.75 |R|: as v1 (speeds_up / slows_down / no_effect /
no_effect_low_n). Reported: calls at 32, 128 and 512, cross-tables 32 vs 128 and 128 vs 512.

**P4. Platform.** No Modal in run 2. GitHub Actions hosted runners (Linux x64; run 1's Python, libraries and numerics
environment); fallback the Mac. The trust gate was run before this freeze: 100/100 identical (`gates_v2/TRUST_GATE.json`).

**P4b. Prediction-side code.** `typescreen_v2.py`, `jobs_v2.py`, `gha.py`, `gha_runner.py`, `g3v2_preview.py`,
`g3v2_evaluate.py`, `b4v2.py` are hashed in `LOCK_prereg_v2.json` (code snapshot) and in `LOCK_predictions_v2.json`; between
the two, a change is allowed only as a bug fix (code made to do what this text says), recorded with `lock2.py amend` (L12).

**P5. Lock.** `LOCK_predictions_v2.json` is additive to v1; every arm is marked "locked after labels v1 existed, before any
unblinding"; an arm that fails a gate is not locked. Predictions v2 are committed locally and pushed only after
`LOCK_labels_v2.json` exists; per-type results on the runners are encrypted (only the orchestrator's machine can read them).

---

## Part S: scoring

**S1. Unchanged.** Primary prediction A1; primary set (clear front-leg label, among A1's 321 types, not exposed); AUROC with
the stratified bootstrap (seed 20261120), one-sided permutation (seed 20261121), bands, the three decision rules
(underpowered: < 20 types or < 5 per class; the model predicts: interval lower bound > 0.5; adds value beyond wiring: paired
bootstrap vs the best of S1-S7, seed 20261122) and the "also reported" items of PREREG v1 section 7.

**S2. Label versions.** Labels v2 is primary; labels v1.1 is a sensitivity analysis (chosen knowing only that v1.1 is too
small). No pooling.

**S3. New arms** (secondary): B1r and B2r (AUROC each on the primary-set types they cover; B1r vs B2r agreement as P1:
Spearman over common types, top-10 overlap with ties broken by type name, band agreement); B3 and B6 are not analysed in run
2 (not locked, P2); B4 v2 (`call_128`, as v1 secondary 12): against `stop_call` (halts vs stops: raw agreement, Cohen's kappa,
confusion table) with `saturates` and `rhythm_lost_other` both excluded and counted as non-halts, and against
`walking_effect` (halts -> stops, speeds_up -> speeds, slows_down -> slows, no_effect -> none) with those two calls excluded
and counted. Code in new files, tested on synthetic data, locked in
`LOCK_scoring_v2.json` before the first v2 label session (L12).

**S4. Runs (each once), each an entry of `UNBLIND.json` naming its predictions lock and labels lock with their SHA-256
(exposed set of L6):**
- P (primary analysis): `LOCK_predictions_v1.json` + `LOCK_labels_v2.json`;
- S-a (primary analysis on v1.1): `LOCK_predictions_v1.json` + `LOCK_labels_v1_1.json` (v1 exposed list);
- S-b (PREREG v1 secondary analyses 1-14): `LOCK_predictions_v1.json` + `LOCK_labels_v2.json`;
- S-c (S3 analyses): `LOCK_predictions_v2.json` + `LOCK_labels_v2.json` (only if predictions v2 exist; the primary set uses
  A1's type names, read from `LOCK_predictions_v1.json`, whose hash `LOCK_predictions_v2.json` records).
Runs P, S-b and S-c recompute `type_labels` from labels v2's `records.jsonl` with the v2 exposed set (scoring v2), not with
the frozen kit-only check; S-a uses labels v1.1 with the frozen check and the v1 exposed list. A run whose pipeline crashed is run again once the
crash is fixed (L12); the crashed output is kept beside the new one.

**S5. The unblinding gate (RUN2_PROMPT section 8), from label files and type names only; every condition must hold:**
1. the locks for rulebook v1 and v2, predictions v1, predictions v2 if it exists, labels v1.1, labels v2, label code v2 and
   scoring v2 all pass `lock2.py check` in a clean checkout (every repository file hashed in a binding section exists and
   matches; chained lock hashes match; code-snapshot sections are reported, not required (L12); archive-member keys
   `<archive>.zip:<member>` are outside the repository and checked by the frozen `lock.py check`, which the v1 locks also pass;
   recorded amendments count as matching and are listed, L12);
2. no contributing session breached under L3 or lacks an audit row (contributing: a reader with a final record, the atlas map
   and coders whose records were used, a second reader or adjudicator whose reading of a final record was used, the verifier
   used; a session excluded and replaced under L3 is not contributing);
3. the label review's verdict is `usable` or `usable with caveats` (not `blocked`), and the verification (`labels_v2/verify/verification.json`, by a non-breaching verifier)
   has an error rate on the front-leg field of at most 10 % (L11);
4. Cohen's kappa of the two readings on the front-leg field >= 0.7: the frozen `agreement(p1, p2)["primary_field_all_values"]`
   with p1 = the deduplicated first readings (atlas coder A included, after mapping) of non-breaching sessions and p2 = the
   Phase A second readings of non-breaching sessions (atlas coder B included, after mapping), matched by `exp_id`;
5. the primary set (labels v2, clear front-leg label, among A1's 321 types, not in the v2 exposed set) has at least 20 types,
   at least 5 yes and at least 5 no;
6. a fresh reviewer signs `reviews_v2/GATE_CHECKLIST.md` (verdict line `confirmed`), confirming 1-5 from the gate report and
   that nothing has been joined. The gate script (`gate_v2.py`, on a clean checkout of committed files) runs once before the
   checklist and once after it, only to record condition 6; conditions 1-5 must come out identical, or the gate fails.
**If any condition fails, nothing is unblinded.** After unblinding nothing moves in run 2 (no label, model or scoring-rule
change); extra analyses only in a section marked exploratory.

**S6. Seeds added in v2.** Trust sample 20261201; G3 v2 permutation 20261202; verification sample 20261203; tuner regression
sample 20261204; determinism sample 20261205; v2 adjudication reading order 20261206.

---

## Disclosure

v2 was informed by: label-side counts and failure causes of v1/v1.1 (exclusions, recall, fetch failures, sighting flags,
class counts of the v1.1 primary set, the label review); prediction-side counts and diagnostics, including the per-type
`gates/B4_halts_split.csv` and `gates/B2_mapping_split.csv` (B4 v2's rule was written after these were seen); run 1's G3 values
for both simulations, and item 4' itself, computed before this freeze (P2); the trust gate, run before this freeze. **No
joined information existed or was used.** This protocol was drafted by the orchestrator, who has seen model scores for some
types; it contains no rule about any particular neuron other than the calibration neuron DNg100 (and DNb08 as a reported
check), as in v1.
