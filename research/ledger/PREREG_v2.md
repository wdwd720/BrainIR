# BrainIR prediction ledger: pre-registration, version 2 (run 2)

Status: **version 2**, frozen by the git tag `ledger-prereg-v2` with `LOCK_prereg_v2.json` (this file, the labeler kit v2 in
`research/ledger/kit_v2/`, and the hashes of every v1 lock). Spec: `research/ledger/RUN2_PROMPT.md`. Decisions: `LOG.md` L49+.

**What v2 is.** The v1 rule (PREREG v1 section 12) forbids amending a stage after it has produced data, so **v1 is not
amended**: rulebook v1, predictions v1, labels v1 and v1.1 stay exactly as locked. v2 is a **new, separately pre-registered
label collection** plus **new secondary prediction arms**, frozen here before either produces any data. Everything not changed
below is as in PREREG v1, section by section.

| version | date | change | stage data existing at the time | labels existing | joined information existing |
|---|---|---|---|---|---|
| 1 | 2026-11-19 | initial (tag `ledger-prereg-v1`) | none | no | no |
| 2 | 2026-11-20 | new label collection (Part L), new secondary arms B1r/B2r, B3/B6 under G3 v2, B4 v2 calls (Part P), label-version and run plan (Part S) | predictions v1 (22 arms); labels v1 and v1.1 | yes (v1, v1.1; the orchestrator saw aggregate label counts only) | **no** |

---

## Part L: labels v2

**L1. Fresh collection.** Labels v2 are made from scratch by new blind sessions in new rooms (`~/ledger_rooms/run2/`). No v2
room contains a v1 record, a v1 label table or a v1 transcript. v1 and v1.1 stay as they are and are used only as the
sensitivity analysis of Part S and in `v1_vs_v2.md` (labels only).

**L2. Unchanged from v1.** The labeling conventions (`kit/PROTOCOL.md` sections 1-7), the record schema and its vocabularies
(`kit/record_schema.json`, validated by the frozen `brainir_ledger.labels.schema`), the two readings plus adjudication
(PREREG v1 section 6: pass 2 relabels from identifiers only in Phase A, then checks the pass-1 quotes in Phase B; a third
blind reader adjudicates every compared field on which the two readings disagree, readings in seeded random order), the
final-record rule, and the type consensus rule (the frozen `brainir_ledger.labels.aggregate`). Clarifications added in v2
(none depends on a particular neuron):
- C1. Sources are downloaded mechanically before the session (L7) and placed in the room. A reader reads the local copy
  first; a live web fetch is allowed only for a source marked unreachable.
- C2. Every session writes the contract files of L5 in addition to its records.
- C3. `saw_simulation_score` takes the v2 meaning of L4; a reader who sees a sighting also writes where (L4).
- C4. The atlas is coded by line ID and mapped to MANC types by a separate session (L8); a line that maps to two or more
  DN types gives one record per type with `line_specificity = multi_dn`, as in v1's sibling rule.

**L3. Breach rule (replaces v1's).** A breach is a SUCCESSFUL access by a session to anything outside its own room, **except**
reading a file in the session's own tool-results folder that the session itself fetched from an allowed host. Reading the
repository, any ledger directory (`~/ledger_rooms/*` outside the own room, the run-1 rooms, any review folder), another
room, or fetching a banned host (GitHub and its content hosts and mirrors, Zenodo, jsdelivr, nbviewer, githack, statically,
gitee; with every subdomain) is still a breach. A breaching session is excluded: its pass-1 or search records, or every
experiment it read as second reader, adjudicator or verifier. Attempts denied by the tooling are reported, not breaches.
The transcript audit is the frozen `labels_audit.audit_session` run on the v2 rooms with this exception added (a path in
the session's own `.../<session-id>/tool-results/` whose file was written by that session's own WebFetch from an allowed
host is not a breach).

**L4. Score sighting (replaces v1's meaning of `saw_simulation_score`).** A sighting is seeing a rhythm score, a rank or a
driver/non-driver call for a DN type from the Pugliese-type connectome activation screen, wherever it is printed: the
Pugliese papers, the simulation part of the 2026 Sapkal preprint, any BrainIR output. Another paper's own model does not
count. A reader who sees one sets `saw_simulation_score = true` on the affected records and writes a row to
`out/sightings.csv` (`doi, locator, what_was_seen` in {rhythm_score, rank, driver_call}, `types_as_printed`). Records with a
sighting are not eligible (PREREG v1 consensus eligibility, unchanged).

**L5. Session contract.** Every session writes `out/dispositions.csv` with one row per source assigned to it:
`doi, disposition` in {records, no_qualifying_experiment, unreachable}, `n_records, reason`. A source without a disposition,
or of a session that ended before writing one, is reassigned to a new session (at most twice; then it is reported as
unreached). Sessions have no time limit.

**L6. Eligibility (replaces v1's search-only exclusion).** A record is eligible whatever session found it (reader or
search-led reader) once it has passed the second reading (Phase A and Phase B) and, where the readings disagree,
adjudication, and is otherwise eligible under the frozen consensus rule (no sighting, mapping confidence not `low`, a
mapped MANC type).

**L7. Sources and registry.** Registry v2 = the union of: the v1.1 registry (`labels_v1_1/sources.csv`); every DOI in any
run-1 record of any session, the excluded ones included; the leads listed in `RUN1_PROMPT.md` (resolved to DOIs by script
or by the first search session); and every DOI the v2 search rounds report. A DOI list carries no outcome. A script with
no model in the loop downloads every source (full text as text; figures as images; supplementary tables as text or CSV;
PDFs as text plus page images; Europe PMC / PMC open-access packages / publisher open-access copies first; back-off on HTTP
429; every failure logged) into a cache with a manifest of SHA-256 hashes, and copies each source only into the rooms that
are assigned it. The orchestrator never opens a downloaded paper. The dedicated simulation sources (the two Pugliese
papers and the 2026 Sapkal preprint) go only into dedicated rooms; types that can be read only there are exposed by nature,
as in v1 (the exposed list `kit/exposed_types.csv` is unchanged).

**L8. Sessions.**
- Readers (first reading): at most 6 sources per session, already in the room; one session per batch of a family; the
  families of v1 again (atlas aside): walking and stopping, grooming, steering, escape and landing, driver-line resources,
  the dedicated simulation papers, recent broad studies; new DOIs from searches are batched by the family their search
  assigned.
- Atlas (Cande et al. 2018): one mapping session assigns DN type names to every line ID of the atlas from the atlas's own
  figures and tables, Namiki 2018 and the 2025 catalogue (names only; `out/atlas_line_map.csv`: `line_id, manc_types,
  mapping_confidence, mapping_basis`). Two independent coding sessions code each line's activation result by line ID from
  the paper's figures and source data, without the type map; they are the two readings. A script applies the map
  afterwards (C4). Atlas disagreements go to adjudication like any other.
- Searches: by type name, by behaviour, by driver-line ID, and by papers that cite the atlas, Namiki 2018 or the 2025
  catalogue. Search sessions write leads (`out/leads.csv`: `doi, title, year, name_in_paper, family_hint, locator`);
  new DOIs are registered, downloaded and assigned to readers. Their records then follow the normal path.
- Second reading: identifiers only (`exp_id, doi, source_locator, driver_lines, name_in_paper, preparation, effector,
  stimulation`, sibling columns), with the same source files in the room; then Phase B quote checks. With the sources in
  the room, a quote that cannot be found is a real failure (the record is dropped), not a fetch error.
- Adjudication: as v1; the dedicated experiments have their own adjudication session.
- Model: as run 1 (`--model opus`, fallback `sonnet`, the model actually used recorded). Quota (LOG L36): above 85 % of the
  account's seven-day window, launch fewer sessions at once; never stop the collection for quota alone.

**L9. Recall rule.** After the first complete reading of the registry, run independent search rounds (each round: the four
search kinds of L8, fresh sessions) until a round adds fewer than 10 % new (normalised DOI, MANC type) units relative to
all units known before it, or three rounds have run. Report the Chapman capture-recapture estimate between the first
reading's units and round 1's units (dedicated family excluded), with its assumptions (closed population, independent
lists, equal catchability; the two lists come from the same model family, so the estimate is likely low).

**L10. Line specificity fill.** After assembly, a script fills `line_specificity` only where the record's value is `unknown`
and a driver-line ID of the record matches a line ID in `kit/driver_lines.csv` (case-insensitive): `multi_dn` if any
matching row lists two or more candidate DN types or another DN type in `other_cells`; otherwise `clean` if every matching
row carries the source's own top specificity grade (`quality_score=A` / `quality=A`) and no other cell; otherwise
`minor_offtarget` if a matching row carries a lower grade (B or C); otherwise it stays `unknown`. A labeler's own value is
never overwritten. The fill is logged per record.

**L11. Verification sample.** A fresh blind session checks 30 final records drawn at random (seed 20261203) against their
sources: for each, `quote_found` (yes/no) and `front_leg_rhythm_correct` (yes/no/cannot_verify). Error rate on the front-leg
field = (no + cannot_verify) / 30. **Above 10 % is a blocker** (gate condition 3).

**L12. Kit v2 and code.** `research/ledger/kit_v2/` holds the v2 kit (copies of the unchanged v1 files and the v2 prompts;
`CHANGELOG.md`); it is frozen with this rulebook. The type list stays alphabetical and score-free. The v2 label-side code
(launcher, downloader, collector, assembly, audit wrapper; new files only, the frozen v1 modules are imported, never edited)
is written after this freeze and before the first v2 session, reviewed against this document, and hashed in
`LOCK_labelcode_v2.json` before the first session; a later change is a logged bug fix that states whether v2 records existed.

**L13. Isolation.** Run 1's launcher flags (`labels_rooms.FLAGS`) plus tool-level deny rules for reading or listing the
repository, every ledger directory outside the own room and the home folders of the reviewers; if a canary shows the
deny rules do not hold, the session runs inside an operating-system sandbox (`sandbox-exec`) that denies those reads.
Before the first real session a canary in a throwaway room must show: a read of a repository file fails; a read of a
planted fake predictions file outside the room fails; a banned host and its subdomains cannot be fetched; the room's own
files and the session's own tool-results can be read; a PDF and an image in the room can be read. If the outside-room block
cannot be enforced, run 1's tool-results guard plus the audit is used and the weakness is reported.

---

## Part P: prediction additions (all secondary; A1 stays primary and untouched)

**P1. Tuner v2 (two-fly comparison).** B1's locked procedure (PREREG v1 3.4, `n_active_lower = 10`, cap 200, start 128,
halve/double/bisect, at most 10 runs, T = 1.0 s, seeds 0..15) plus one acceptance condition: **at least K active front-leg
MNs** (`n_active_readout >= K` in the accepted run; a run inside the activity bounds with fewer than K active MNs counts as
too weak). Implemented in a new module (`brainir_ledger/typescreen_v2.py`); with K = 0 it is B1's procedure.
- **K is fixed on DNg100 alone:** the smallest K in {1, 2, 3, 5, 10} for which the DNg100 pair (both members) scores
  >= 0.5 in at least 12 of 16 seeds on **both** the MANC front-leg network and the MaleCNS front-leg network. If no K works,
  the start current is anchored on DNg100 instead: per network, the lowest current of the doubling grid 128, 256, 512 at
  which the DNg100 pair scores >= 0.5 in at least 12 of 16 seeds becomes the start current for every type (acceptance as
  B1), and the reason is logged. No other neuron is run before K is fixed; DNb08 is reported afterwards as a check and is
  never used to tune.
- **B1r** = tuner v2 on the MANC front-leg network (B1's 321 groups); **B2r** = tuner v2 on the MaleCNS front-leg network
  (B2's 328 groups, B2's mapping). Two-fly comparison: Spearman B1r vs B2r over common types, top-10 overlap, band agreement.
- Gates: tuner regression (with K = 0, tuner v2 reproduces B1's digests exactly on 30 random types (seed 20261204) x 16
  seeds); positive control (DNg100 >= 0.5 in >= 12 of 16 seeds in B1r and in B2r; DNb08 reported); determinism (100 random
  jobs per arm re-run, seed 20261205, identical digests); nothing broken (baseline checks); independent review of the code
  and the calibration for any use of a neuron other than DNg100.

**P2. B3 and B6 (full cord).** The procedure of PREREG v1 3.7 and 3.11 and LOG L14, unchanged. **Gate G3 v2** = items 1-3
and 5 of PREREG v1 section 9 unchanged, and item 4 rewritten as:
> **4'. Coupling between legs is consistent with the authors' own traces under the same test.** Apply PREREG v1 4.7
> (leg signal version 1, same eligibility) to our G3 replicates (both DNg100 at 380, T = 2 s, seeds 0..63) and to the
> authors' 32 replicates of run 33195857. A pair is evaluable if it has >= 8 eligible replicates in both sets. For each
> evaluable pair of the seven reported pairs (PREREG v1 4.8), test whether the coupling strength differs: pool the two
> sets' eligible offsets, re-split them at random into groups of the original sizes 10,000 times (seed 20261202), statistic
> |R_ours - R_authors|, p = (1 + #{perm >= observed}) / 10,001. **Item 4' passes if at least three pairs are evaluable and no
> evaluable pair has p < 0.01 / k** (k = number of evaluable pairs).
The rule compares two simulations and involves no fly data. Disclosure: run 1's summary values for both simulations are
known (`gates/G3_REPORT.md`); the rule was chosen as the standard two-sample comparison of a statistic with replicate
noise (a status match would call identical R values inconsistent when only n differs), not to obtain a verdict. G3 v2 is
evaluated, including its DNg100-only step (item 5), before the first v2 label session starts. If G3 v2 passes, B3 runs; B6
runs only if the compute budget allows (it is dropped first). If it fails, neither is locked and the reason is reported.

**P3. B4 v2 (calls recomputed from the stored B4 replicates; no new simulation).** For type t at strength s in {32, 128,
512}: R = seeds whose background-only run scores >= 0.5 (fewer than 8 -> `background_not_rhythmic`); L = seeds in R where
t's run scores < 0.5. If |L| >= 0.75 |R|: in-bounds = `n_active_all <= 1500` and `n_high_fr <= 100` (B4's screen
configuration); fall = (background active MNs - t's active MNs) / max(background active MNs, 1), per seed;
- `halts` if at least 75 % of L are in bounds and the median fall over L is >= 0.25;
- `saturates` if more than 25 % of L are out of bounds;
- `rhythm_lost_other` otherwise.
If |L| < 0.75 |R|: as v1 (`speeds_up` / `slows_down` at a median paired relative frequency change above +15 % / below -15 %
over seeds where both runs score >= 0.5, `no_effect`, `no_effect_low_n` with fewer than 4 such seeds). Reported: the
calls at 32, 128 and 512 and the cross-tables 32 vs 128 and 128 vs 512 (whether the direction holds across strengths).

**P4. Platform.** No Modal in run 2. New arms run on GitHub Actions hosted runners (Linux x64, the run 1 image's Python and
library versions and numerics environment; LOG L49-L50) or, as fallback, on the Mac. Trust gate before any new arm: 100
locked run-1 jobs re-run on the platform (identical -> use; rounding only (same usable flags, tuned currents and runs;
score difference < 0.001) -> use and mark the arms "different platform"; otherwise do not use the platform).

**P5. Lock.** `LOCK_predictions_v2.json` is an addition to v1, never a replacement; every arm is marked "locked after labels
v1 existed, before any unblinding"; an arm that fails a gate is not locked.

---

## Part S: scoring

**S1. Unchanged.** The primary prediction (A1), the primary set (labels: clear front-leg label; among A1's 321 types; not
exposed), the statistic (AUROC, stratified bootstrap seed 20261120, one-sided permutation seed 20261121), the bands and the
three decision rules (underpowered; the model predicts; adds value beyond wiring, paired bootstrap seed 20261122), and the
"also reported" items of PREREG v1 section 7.

**S2. Label versions.** **Labels v2 is primary.** Labels v1.1 is a sensitivity analysis. Chosen now, knowing only that v1.1
is too small (12 primary types).

**S3. New arms** enter as secondary analyses: B1r and B2r (AUROC each on the primary set's types they cover; B1r vs B2r
agreement), B3 per leg pair (front, middle, hind labels) and B6 if locked, B4 v2 calls (`call_128` v2 against `stop_call`
and `walking_effect`, as v1 secondary 12, with `saturates` and `rhythm_lost_other` counted and analysed both excluded and
as non-halts). The scoring code is extended for them as a logged change in new files with a new lock version
(`LOCK_scoring_v2.json`) before any unblinding, tested on synthetic data.

**S4. Runs (each happens once).** (P) the primary analysis on labels v2; (S-a) the primary analysis on labels v1.1;
(S-b) PREREG v1 secondary analyses 1-14 on labels v2; (S-c) the S3 analyses on labels v2.

**S5. The unblinding gate (copied from RUN2_PROMPT section 8).** Computed from label files and type names only; every
condition must hold: (1) the locks for rulebook v1 and v2, predictions v1, predictions v2 if it exists, and labels v2 all
pass in a clean checkout; (2) no session that contributed a record breached under the v2 rule; (3) the label review has no
blocker, and the verification sample's error rate on the front-leg field is at most 10 %; (4) agreement between the two
readings on the front-leg field has a Cohen's kappa of at least 0.7 (all four values, all experiments read twice);
(5) the primary set (labels v2, clear front-leg label, among A1's 321 types, not exposed) has at least 20 types, at least 5
yes and at least 5 no; (6) a fresh reviewer signs a checklist confirming 1-5 and that nothing has been joined. **If any
condition fails, nothing is unblinded.** After unblinding, nothing moves: no label, model or scoring-rule change in run 2;
extra analyses only in a section marked exploratory.

**S6. Seeds added in v2.** Trust sample 20261201; G3 v2 permutation 20261202; verification sample 20261203; tuner regression
sample 20261204; determinism re-run sample 20261205; v2 adjudication reading order 20261206.

---

## Disclosure

v2 was informed by label-side counts and failure causes from v1 and v1.1 (sessions excluded, recall, fetch failures,
score-sighting flags, class counts of the v1.1 primary set), and by prediction-side counts and diagnostics (B2's DNg100
control, B4's over-excitation, G3's run-1 values for both simulations). **No joined information existed or was used.** This
protocol was drafted by the orchestrator, who has seen model scores for some types; it contains no rule about any
particular neuron other than the calibration neuron DNg100 (and DNb08 as a reported check), as in v1.
