# BrainIR prediction ledger: pre-registration, version 5 (run 5: replication, count-noise stability, label audit, forward ledger v2, paper)

Spec: `RUN5_PROMPT.md` (sha256 65fabef7...1d25). Earlier rulebooks (`PREREG.md`, `PREREG_v2.md` to `PREREG_v4.md`) and every earlier lock
stay as they are. This rulebook is frozen by `LOCK_prereg_v5.json` and the tag `ledger-prereg-v5` before any analysis or simulation it
governs. Inputs are the locked per-type tables `pertype_v1/` (`LOCK_pertype_v1.json`, tag `ledger-pertype-v1`) and the earlier locks. It
was audited before the freeze by a fresh reviewer (`reviews_v5/PREREG_AUDIT_v5.md`, on the text kept as
`reviews_v5/PREREG_v5_as_audited.md`) and re-checked after revision (`reviews_v5/PREREG_AUDIT_RECHECK_v5.md`); every finding of both is
answered in `reviews_v5/PREREG_AUDIT_RESOLUTION_v5.md`, which the prereg lock hashes. Departures from RUN5_PROMPT are listed in Part D.

**What is confirmatory.** One test: Part S's test S1 on the B1r driver list, which alone carries words. Its repeat on the A1 list is a
pre-registered secondary test (no words). Part R is descriptive and **post hoc** (its thresholds and categories were chosen after the
pattern was seen). Part L is an audit by fresh reader sessions; its re-score of exam 1 is exploratory. Part T is descriptive and optional.
Part F is a forward ledger whose outcomes do not exist yet.

---

## Part Q. What was seen before this freeze (disclosure)

- Runs 1-4 in full, including both unblinded exams, RESULTS_1 to RESULTS_3, BRIEF and HANDOFF_4.
- The question round (LOG L158 and its answer, 2026-11-23): per-type scores in all nine screens for every type that is a driver somewhere;
  under that round's definitions one "stable driver" (DNg100), one "near-stable" (DNg15), 39 "discordant hits" and 92 "stable
  non-drivers" among the 245 types screened in all four half-flies; authors-concordant types (every A0 copy >= 0.5): DNg100, DNb08,
  DNit011, DNit013; DNg100's exam 1 label (no, headless, 5 records); the exposed set; the E5 flags' meaning.
- The replication pattern (RUN5_PROMPT section 1): drivers (>= 0.5) B1r 15 types, A1 11, B2r 30; in both B1r and B2r: DNg100, DNb08,
  DNit013; of A1's 11, the same 3 are B2r drivers. B1r's per-type scores and usable counts for every driver: the three replicated types
  rank 2, 7 and 11 of the 15 B1r drivers by B1r score; DNg63 is a B1r driver on 1 usable replicate of 16, DNxl121 on 6 of 16.
- While building the per-type tables (LOG L160): the cross-fly match confidence of every MaleCNS type (high 217, medium 29, low 82);
  DNit013's match is low (its MaleCNS body is body-matched to MANC DNit013 but its `mancType` string says DNit011); DNg100 and DNb08 are
  high; of the 15 B1r drivers 11 have a high-confidence match, of the 11 A1 drivers 6.
- **The rulebook audit's report** (`reviews_v5/PREREG_AUDIT_v5.md`), read before this freeze, computed from locked files: (a) the rank
  position of the replicated types by B1r score and a permutation test of the replicated types' mean B1r score (p = 0.26 with 16 seeds,
  0.36 with seeds 0..7); (b) that with the kit's driver lines the replication and single-connectome readings of Part F can disagree on
  at most four types (DNa03, DNa13 and DNp71, near-replicated and not A1 drivers; DNp41, a single-fly hit that is an A1 driver), and a
  plausible short list; (c) that DNg100's exam 1 "no" is what the frozen consensus rule gives on its 5 eligible records (after the
  confidence tier, the headless records are kept, and one headless `minor_offtarget` "no" outranks two headless "yes" records of
  `unknown` specificity), its 23 records from dedicated sources (22 headless "yes") having been set aside as sightings; (d) that exam 1's
  136 atlas records were coded from a figure (their quotes are line IDs) and that 21 of the 39 primary-set types rest on the atlas alone.
  The forensic sessions of Part L never see this report. The re-check (`reviews_v5/PREREG_AUDIT_RECHECK_v5.md`) added: the rank version of
  that reference test (p = 144/455 = 0.32 with 16 seeds, 167/455 = 0.37 with seeds 0..7); the largest per-type source sets (DNp01 24
  sources, MDN 23, DNa02 13); nine Part R types with a kit line and no cached source (DNa14, DNg21, DNg39, DNg63, DNg78, DNp33, DNp35,
  DNp41, DNp46); and that no primary-set type has a sighting record.
- Forward ledger v1's 59 looked-up lines (availability checked 2026-11-22) include lines of the stable non-drivers DNp26, DNg39, DNp31,
  DNg78 and DNp35.
- Run 4's two Poisson copies of MANC (B4.2: one-sided left screen, seeds 0..7, run 4's analysed types) were summarised in run 4 as
  agreement statistics. This run has not looked at their per-type values; that run 4's orchestrator saw them cannot be excluded.
- **Not seen before this freeze:** any result of Part S (its copy seeds 20261511-20261526 have never been used; its design, whole-type
  screens of both sides with B1r's procedure, differs from run 4's), of Part T, or of the label audit's sessions; and the availability
  today of any line. Seen: every type's two-step count (S2, a locked run 1 file) and, through the audit report, the counting reading of the
  plausible short-list types.

## Part G. Definitions used everywhere

- **G1. Screens and scores.** From `pertype_v1/` only: A0 by copy (`A0_copies.csv`), the four half-fly screens (`MANC_L/R.csv`,
  `MaleCNS_L/R.csv`), the whole-type screens B1r, B2r and A1 (`B1r.csv`, `B2r.csv`, `A1.csv`). Type score = the tables' `score`
  (PREREG v4 G5: mean over usable replicates, 0 if none); fraction rhythmic = PREREG v4 G5 (share of all replicates, usable or not, with
  score >= 0.5; an unusable replicate counts as not rhythmic). Halves: `score_h1` / `score_h2` (seeds 0-7 / 8-15).
- **G2. Driver** = score >= 0.5; **non-driver** = score < 0.05 (PREREG v4 G5).
- **G3. Common types** = types present in both a MANC whole-type table (B1r, 321 types, or A1, 321) and B2r (328). Types in one fly only
  are listed, not categorised.
- **G4. Cross-fly match confidence** = `pertype_v1/match_confidence.csv` `confidence` (high / medium / low; rule in LOG L160 and the
  table's MANIFEST).
- **G5. Exam 1** = labels v2 (`labels_v2/type_labels.csv`, `LOCK_labels_v2.json`). Its primary set = clear front-leg label (yes/no),
  among A1's 321, not in the v2 exposed set (`forward_v1.primary_set`, 39 types); the v2 exposed set = `kit_v2/exposed_types.csv` +
  `labels_v2/exposed_v2.csv` (`brainir_ledger.scoring_v2.pipeline_v2.exposed_set_v2`, 18 types).
- **G6. Kit lines** = the distinct `line_id` values of `kit_v2/driver_lines.csv` rows whose `manc_type` is the type (rows `AMBIGUOUS`,
  `UNMAPPED` or empty name no type). A line is **clean** for type t if no row of that line names another DN type of
  `kit_v2/type_list.csv`: not as its `manc_type`, not among the `candidate_types` of an `AMBIGUOUS` row, and not in its `other_cells`
  text (MANC names and the other names of `synonyms.csv`, matched as in L3) (`forward_v2.lines_for`).
- **G7. Two-step signed counting** = `S2_twohop_signed` of the locked `predictions/S/types.csv` (`LOCK_predictions_v1.json`); **top
  third** = tercile 2 of `forward_v1._tercile` over A1's 321 types (107 types).

---

## Part R. Replication (descriptive; **post hoc**: the thresholds and categories were chosen after the pattern was seen)

**R1. Categories** (common types, whole-type screens), computed twice: with B1r as the MANC screen (primary) and with A1 (R2.3).
- **Replicated:** a driver in both (B1r or A1) and B2r.
- **Near-replicated:** a driver in one, and 0.3 <= score < 0.5 in the other.
- **Single-fly hit:** a driver in one, and score < 0.3 in the other; reported as MANC (driver in B1r or A1) and MaleCNS (driver in B2r).
- **Stable non-driver:** score < 0.05 in the MANC screen and in B2r, and < 0.05 in all four half-fly screens (a type absent from a
  half-fly table cannot be one).
- Every other common type: **neither**. Types in one fly only: listed with their score.
Every category member carries its match confidence; members with a low or medium match are flagged in both directions (a replication
resting on a low-confidence match is flagged exactly as a non-replication is). Each row also gives the usable-replicate counts.

**R2. Reports.** Every report is given for all common types and for common types with a high-confidence match, side by side. **The
high-confidence version leads** in RESULTS_4, the paper and the brief (RUN5_PROMPT section 8: 82 of 328 MaleCNS types, 25 %, have a low
match, which this rulebook counts as "many"); the all-types version stands beside it.
1. Counts and lists of every category, with each type's B1r, B2r, A1 and half-fly scores, usable counts and match confidence.
2. **Overlap of the two flies' hit lists, next to its ceiling** (over common types). (a) Full screens: the number of drivers in each
   screen and in both; the hypergeometric expectation of "both" if the lists were independent; the **replication rates** |X n Y| / |X|
   and |X n Y| / |Y|; the Jaccard index J = |X n Y| / |X u Y| with its maximum for these list sizes, min(|X|, |Y|) / max(|X|, |Y|).
   (b) Matched noise (8 seeds against 8 seeds): for the **overlap coefficient** OC = |X n Y| / min(|X|, |Y|) and for J, the cross-half
   value = mean over (B1r_h1, B2r_h2) and (B1r_h2, B2r_h1), and the **ceiling** = mean of each fly's split-half value (B1r_h1, B1r_h2) and
   (B2r_h1, B2r_h2), with their ratio. **Words in the paper rest on the replication rates and on the OC ratio** (OC is not capped by
   unequal list sizes); J is reported beside them with its size limit. Intervals: 95 % percentile intervals from 10,000 resamples of
   the types with replacement (`default_rng(20261501)`, a fresh generator for each version and screen; all statistics of one version
   share the resamples; a resampled type counts with its multiplicity; a resample in which a statistic is undefined, an empty union or
   list, is dropped for that statistic and the number dropped is reported).
3. **The same with A1** in place of B1r (categories and overlaps; A1's halves are replicates 0-7 / 8-15).
4. **High-confidence version:** reports 1-3 restricted to common types with a high-confidence match; also high + medium.
5. **Copy concordance in A0** (types with at least one copy on each side, and separately types with exactly one copy per side): the
   number of types with at least one driver copy; the number with every copy a driver ("concordant"); the **concordance share** =
   concordant / types with at least one driver copy; and concordant / all types in the set; each concordant type's copies.
6. **The two experimentally confirmed drivers** (DNg100, DNb08): their category in both versions, scores in every screen, A0 copies and
   match confidence, with the selection caveats stated beside them: DNg100 is the neuron the model was calibrated and built around
   (the tuner's K was chosen on it); the original authors chose DNb08 themselves; both are exposed types; two confirmed neurons are a
   tiny sample.

Every table and sentence of Part R says "post hoc". Output: `replication_v1/R_replication.json` and `R_tables.md`
(`ledger/scripts/replication_v1.py`).

---

## Part S. Does stability under synapse-count noise inside one fly predict replication? (pre-registered, confirmatory)

**S1. Copies.** 16 Poisson copies of MANC's raw synapse counts: `fixes.poisson_copy(manc_raw_counts(), seed)` with seeds 20261511 ...
20261526 (copy 1 ... 16), floor 5 applied after resampling (`fixes.at_floor(., 5)`), signed with the MANC presynaptic signs
(`fixes.signed(., mirror.fly("MANC").sign)`), float64 CSR with sorted indices; sizes, read-out and type groups are B1r's
(`gha._nets()`) (`gha5.manc_matrix`).

**S2. Types.** Every type that is a driver in B1r or in A1 (`pertype_v1/B1r.csv`, `A1.csv`; 16 types), plus 40 **sampled non-hits**
(types that are drivers in neither), drawn once as `numpy.random.default_rng(20261527).choice(sorted(frame), 40, replace=False)`,
frame = A1's 321 types minus the 16 (305 types) (`gha5.part_s_types`).

**S3. Procedure.** The whole-type B1r screen with **B1r's job specification exactly** (`gha._v2_jobs`: run 2's job kind `group_v2`,
tuner v2 with K = 1, B1's screen configuration `b1_screen_cfg(10)`, T = 1 s, all of the type's members stimulated, the front-leg motor
neurons read out, read-out traces stored as in B1r), seeds 0..7 per copy, through run 4's runner and workflow unchanged (its job
dispatcher hands `group_v2` to run 2's code) (`gha5.py`, prefixes `s0`, `ps`).

**S0. Regression gate (before any copy campaign is published).** The same specification on the matrix rebuilt from the raw counts at
floor 5 without resampling (the builder refuses unless it equals B1r's matrix entry for entry, same CSR structure), for every Part S
type x seeds 0..7, against B1r's stored per-seed results (`predictions_v2/B1r/replicates.parquet`). **Pass:** every job's run 2
`digest` is identical; or, for a job whose digest differs, every stored field is equal (`usable`, `current`, `n_tuning_runs`,
`n_active_all`, `n_high_fr`, `n_active_readout`, `n_active_notebook`, `frequency_hz`) and the score differs by < 1e-9, with the
differing fields shown ("equivalent"). Anything else **stops Part S**, and the failure is reported (`gha5.py s0-compare`). S0 also times
the jobs that size the copies' chunks (X2).

**S4. Stability.** Per (type, copy): the **copy score** = mean score over the usable seeds of 0..7, 0 if none (G1), with the number of
usable seeds reported. **Stability** = the fraction of the 16 copies whose copy score is >= 0.5. Secondary: the mean copy score.

**S5. Test S1 (primary, confirmatory).** Among the B1r drivers, R = those that are drivers in the locked B2r table (`pertype_v1/B2r.csv`:
DNg100, DNb08, DNit013). **Exact one-sided rank test** (Wilcoxon-Mann-Whitney rank-sum, computed exactly over all subsets): rank the n =
15 B1r drivers by stability, upward (rank 1 = least stable; midranks for ties); statistic = the sum of R's ranks; p = (number of subsets of the n drivers of size |R|
whose rank sum is >= R's) / C(n, |R|) (ties count as >=) (`stability_v1.exact_test`).
- **Words:** "Stability predicts replication" if p < 0.05; otherwise "not shown". Only this test carries words.
- **Pre-registered secondary (no words):** the same test on the A1 list (A1's 11 drivers; R = the A1 drivers that are B2r drivers).
- **Sensitivity (reported beside S1, no words):** (i) restricted to drivers with a high-confidence match (R = DNg100, DNb08; smallest
  attainable p: 1/C(11, 2) = 1/55 = 0.018 on the B1r list, 1/C(6, 2) = 1/15 = 0.067 on the A1 list, which therefore cannot reach 0.05);
  (ii) on the mean copy score; (iii) on the mean fraction rhythmic over copies (per copy: the share of seeds 0..7 that are usable with
  score >= 0.5; robust to tuner acceptance); (iv) without the B1r drivers that have fewer than 12 of 16 usable B1r replicates (DNg63,
  DNxl121); (v) **reference:** the same rank test on the real network's B1r score (seeds 0..7, from `predictions_v2/B1r/replicates.parquet`,
  and seeds 0..15, `pertype_v1/B1r.csv`). **Reading against the score (fixed now):** a positive S1 is described as "noise stability adds to
  the score" only if S1's p < 0.05 and both (v) p values are >= 0.05; otherwise as "not distinguishable from the score itself".

**S6. Test S2.** Among the 40 sampled non-hits: the number of (type, copy) pairs with copy score >= 0.5 out of 640 (the false-hit rate per
copy), the number of types with at least one driver copy, and the number with stability >= 0.5, each with an exact (Clopper-Pearson)
95 % interval where it is a count of types; also by B1r band (non-driver < 0.05; indeterminate 0.05-0.5).

**S7. Power, stated before the test runs.** There are only 3 replicated types among the B1r drivers (and among the A1 drivers). The
smallest attainable p is 1/C(15, 3) = 1/455 = 0.0022 for the B1r list (1/165 = 0.0061 for A1), reached only if the three replicated types
are strictly the three most stable. Ties at the top raise it: if t drivers, the three replicated among them, share the highest
stability, p = C(t, 3)/C(n, 3):

| t (tied at the top, incl. the 3) | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|
| smallest p, B1r list (n = 15) | 0.0022 | 0.0088 | 0.022 | 0.044 | 0.077 | 0.12 |
| smallest p, A1 list (n = 11) | 0.0061 | 0.024 | 0.061 | 0.12 | 0.21 | 0.34 |

So if seven or more B1r drivers are perfectly stable, the test cannot reach p < 0.05 however stable the replicated types are (A1: five or
more). **A null result here is uninformative**: it does not show that stability fails to predict replication. A positive result rests on
three types, two of them the confirmed drivers (selection caveats of R2.6), and one (DNit013) on a low-confidence match, so it would be
suggestive, not general. Two B1r drivers (DNg63, DNxl121) are drivers on few usable replicates, so their stability partly measures tuner
acceptance (sensitivity iv). The table depends only on n and |R|: with 8 copies (X3) it is unchanged; only the granularity of stability
changes (9 values instead of 17).

**S8. Operations.** Collection stores no error record, so a job that ends with an error leaves its key without a result; the chunk is
re-published (same specification, at most twice); a packed key still without a result after that counts as a not-usable seed and is
listed (`stability_v1.results`). **All 16 copies are run and analysed**, unless X3's budget rule chooses 8 copies before any copy campaign
is published (`gates_v5/X3_BUDGET.json`, logged with its reason); once any copy result is collected, every copy that ran is analysed (the
analysis refuses fewer copies than the collected campaigns hold; the copy builder refuses before S0 has passed and X3 is written). A
determinism failure (X4) triggers a full re-run of that campaign as a separately named campaign (`psr-`/`ptr-` prefixes), compared key by
key with the first; if every digest of the re-run matches, the first run's results are used; otherwise S1 is reported without words ("not
determinate").

Output: `replication_v1/S_stability.csv` (per type and copy, with usable counts), `S_tests.json`, `S_report.md`
(`ledger/scripts/stability_v1.py`).

---

## Part T. The single-copy screen in both flies (optional; descriptive)

Run only if, after S0's timing, the projected total stays at or below 80 runner-hours (X3); it is the first thing dropped (X6), and only
before it is published.
- **Types:** every type that is a driver in B1r, B2r or A1 (43 types). **Copies:** every member of those types in B1r's MANC front-leg
  network and in B2r's MaleCNS network (`gha._nets()`; sides as PREREG v4 G3).
- **Procedure:** B1r's job specification (S3) with one copy stimulated, seeds 0..15, on the real networks of B1r (MANC) and B2r (MaleCNS)
  (`gha5.py`, prefix `pt`). This is our single-copy variant of the whole-type procedure (the procedure behind B1r and B2r), not the
  authors' single-neuron notebook (A0) and not BrainIR's earlier single-neuron screen (B0, tuner v1); MANC is run with it as the
  same-procedure reference, and A0 is compared descriptively.
- **Report:** per type and fly, every copy's score; copy concordance (every copy a driver; at least one); DNg100 and DNb08 in full; MANC
  single-copy against A0 per copy (Spearman over copies, descriptive). Output: `replication_v1/T_singlecopy.json`.

---

## Part L. Label audit (fresh reader sessions; the orchestrator never authors a label)

**L1. Sessions.** Every reading is done by a fresh `claude -p` session in its own room (`~/ledger_rooms/run5/<session>/`), launched by
`audit5_rooms.py`, model `opus` with fallback `sonnet` (the model used is recorded).
- **Isolation.** Run 2's frozen flags and deny rules (`labels2_rooms.flags_v2`: file tools only, no shell, no MCP; reads of the
  repository, run 1's rooms, the review rooms and the temporary folders denied) plus deny rules for `~/ledger_rooms/run2/` (exam 1's
  rooms, which hold its records). Sessions run inside **run 2's macOS sandbox profile** (`labels2_rooms.sandbox_profile`: reads of
  `~/ledger_rooms` outside the session's own room, of the repository, of other Claude projects and of the orchestrator's temporary
  folder, given by `LEDGER_SCRATCH`, are denied). **Canary:** before any other session, a canary session in the same mode tries to read
  the targets its mode must block (sandbox: a planted file in another run 5 room, a run 2 room's records, the repository, the
  orchestrator's folder; tool mode: the last three, which its deny rules cover); it passes if its transcript shows no successful access
  outside its room and the planted token appears nowhere in its output. The launcher refuses every other session until the canary of
  that mode has passed (`labels_audit_v1/CANARY_<mode>.json`). If the sandbox prevents a session from running at all, sessions run in
  run 2's tool mode with the deny rules above, after that mode's canary passes; reads of other run 5 rooms are then policed by the
  transcript audit; this is logged.
- **Web.** As run 2's C1, a session whose assigned sources include one whose cached copy is abstract-only or unreachable may fetch exactly
  those DOIs with WebFetch (run 2's `reader_web` flags); no other session has web tools.
- **Room contents.** The task; `kit_v2/PROTOCOL.md`, and, except in atlas coder and atlas adjudicator rooms (which, as in exam 1, get no
  type map: PREREG v2 L8), `type_list.csv`, `synonyms.csv`, `driver_lines.csv`; the audit kit
  (`audit_kit_v1/AUDIT_NOTE.md`, which lifts PROTOCOL section 6's and section 8's rules on simulation results for this audit and wins where
  the two differ, and a copy of `record_schema.json` whose `pass_id` also allows `audit`); the session's type or line list; the assigned
  sources copied from the mechanical download cache (`data/ledger/sources_v2/`, run 2's); and the inputs named below for forensic,
  adjudication and verification sessions. **No reader, coder or adjudicator room holds an exam 1 label or record.** Both exams are
  unblinded, so sessions may read every source, including the dedicated simulation papers; a sighting does not make a record ineligible in
  this audit.
- **Transcript audit and breaches.** Every session is checked by run 1's frozen transcript audit (`labels_audit.audit_session`) with
  run 2's single exception (`labels2_audit`: a read of a file in the session's own tool-results folder that its own WebFetch saved is not
  a breach) and run 2's mirror rule (`audit5_rooms.audit_one`); run 2's forbidden-token rule is not applied, because this audit's
  sessions may read everything about the simulations (hard limit 4). A session breaches if its transcript shows a successful file access
  outside its room, a successful fetch of a banned host or mirror, or no transcript (PREREG v2 L3). A breaching session's records are
  excluded. **Replacement:** every assigned source that no non-breaching session of a lineage gave a disposition goes to a replacement
  session with exactly those sources (`-r1`, then `-r2`; `audit5_rooms.py replace`). A session blocked by a provider safeguard is
  replaced by a new session on another model, logged.

**L2. DNg100 first (forensic).** Two independent sessions (F1, F2), each with: every exam 1 record of DNg100 (`labels_v2/records.jsonl`,
all fields, eligible or not); verbatim excerpts of the consensus rule (PREREG v1 section 6: final records and type consensus;
`audit_kit_v1/CONSENSUS_RULE.md`) and of the blind rule (PREREG v2 L4 and L6, and PREREG v1 section 6's passes;
`audit_kit_v1/BLIND_RULE.md`); the frozen `aggregate.py`; every source those records cite, every dedicated source, and every cached source
whose text mentions DNg100 or another name of it (matched as in L3). Task (`audit_kit_v1/PROMPT_FORENSIC.md`): list the five records
behind the "no" with their quotes; say which sources describe DNg100 activation in headless flies and what they report (quotes); explain
the label as one or more of (a) a mapping error, (b) the consensus rule, (c) sources set aside by the blind rule, (d) a correct reading of
a narrower experiment, (e) other, with evidence; and give the label the sources support. Each also writes `out/explanations.csv` (one yes/no flag for
each of (a)-(e)); if the two sets of flags are not identical, a third session (F3) adjudicates with both reports and the same inputs.

**L3. Re-reading.**
- **Audited types:** (i) the 18 exposed types; (ii) every type in a Part R category other than "neither" (R1, B1r or A1 version) whose
  exam 1 front-leg label is yes, no, unclear or conflicting; (iii) **all 39 primary-set types** (a census), and within them a **random
  sample of 15** drawn as `numpy.random.default_rng(20261528).choice(sorted(primary set), 15, replace=False)`; (iv) every type in a Part R
  category other than "neither" (either version) with a kit line (for F1) (`audit5_rooms.audited_types`).
- **Relevant sources:** for each audited type, every cached source holding an exam 1 record of it (any eligibility), and every cached
  source (dedicated ones included) whose `text.txt` mentions it: its MANC name or any other name in `synonyms.csv` (ambiguous names
  included), as a whole word (case-insensitive for names containing a digit, case-sensitive otherwise), excluding seven other names that
  are common English words (web, sink, snail, snake, mute, oval, knees).
- **The atlas** (Cande et al. 2018, 10.7554/eLife.34275), whose results are a figure of line IDs, is re-coded with **exam 1's atlas
  procedure** (PREREG v2 L8): two independent coding sessions (atlas coders A and B) with exam 1's atlas prompt
  (`kit_v2/PROMPT_ATLAS_CODE.md`, plus the audit note) and exam 1's line list (`labels_v2/work/atlas/atlas_line_ids.csv`) code every
  atlas line by line ID, without types; keys (line ID, headless or intact) on which A and B differ in any leg field, or that only one of them coded, are
  coded again by an atlas adjudicator (C) given both codings; the final codings are mapped to types by exam 1's locked atlas map
  (`labels_v2/raw/atlas_map/atlas-map/atlas_line_map.csv`) with exam 1's script rule (a line mapped to two or more types ->
  `multi_dn`). The atlas is not given to the source readers.
- **Every other relevant source** is read by **two independent sessions** (readers A and B), blind to exam 1. Sources are packed into
  groups of at most 4 sources and at most 300 KB of `text.txt` (first-fit decreasing by size, ties by name); each group is read by one
  reader-A and one reader-B session, whose type list is every audited type relevant to one of its sources (with its other names); a type
  list longer than 20 is split into lists of at most 20, each read by its own A and B sessions of the same sources.
  Readers write v2-schema records for every experiment on real flies that activates a listed type (thermogenetic or optogenetic) and
  reports leg behaviour, with its preparation (headless / intact_free / intact_tethered) and the three leg fields, plus
  `out/dispositions.csv` (one row per source); a source without a disposition goes to a new session, at most twice.
- **Quote check (script, `audit5_rooms.quote_status`).** A reader's record counts only if it is schema-valid and its quote, normalised
  (Unicode NFKC, lower case, line-break hyphenation removed, every run of non-alphanumeric characters made one space, at least 8
  characters), is found in the source's normalised `text.txt` and text supplements, or the reader marks it as read from a figure or page
  image (`notes` starting `figure:`; counted, and reported separately), or it cites a source whose cached copy is abstract-only or
  unreachable (its quote may come from fetched full text) and another reader has a record of the same DOI, preparation, type and
  front-leg value ("web agreed"). Atlas codings are checked by the A/B/C procedure, as in exam 1.
- **Line-specificity fill.** PREREG v2 L10's frozen fill (`labels2_collect.line_spec_fill`) is applied to the counted records before any
  consensus, as in exam 1.
- **Reader labels.** For each audited type and each scope (headless; intact = intact_free and intact_tethered): reader A's label = the
  frozen consensus (`aggregate.type_labels`, eligibility as frozen except that sightings do not exclude) on reader A's counted records plus
  the final atlas records; reader B's likewise.
- **Adjudication.** A type whose reader-A and reader-B labels differ at the scope that matters (exam 1's scope, L4, for a type with an
  exam 1 front label; otherwise either scope) goes to an adjudication session (C) blind to exam 1, given both readers' records of the
  type (all fields) and the sources those records cite (atlas excluded), at most 4 sources per session (one type per session; more
  sources are split over sessions); C writes its own records of the type.
- **Audited label** = the common label where A and B agree; otherwise the frozen consensus on C's counted records plus the final atlas
  records. A label that rests only on `figure:` records therefore stands only where both readers agree or C decides. **Final records**
  of a type = both readers' counted records (C's for a disputed type) plus the final atlas records (`labels_audit_v1/final_records.jsonl`).

**L4. Error rate.** Exam 1's front label is compared with the audited label at exam 1's scope (headless if exam 1's `best_preparation`
is headless, else intact).
- **Error** = (a) an audited label of yes or no that differs from exam 1's; or (b) an audited label that is not yes or no (including
  nothing recorded), where a **verification session** given exam 1's records behind the label at its scope (DOI, locator, quote, driver
  lines, preparation, name in the paper; not the leg fields; as PREREG v2 L11) codes the front-leg value and the unanimity of its codings
  (all yes -> yes, all no -> no, both -> conflicting, else unclear) differs from exam 1's label; records without a verifier answer are
  sent once more, and a type still without one counts as an error; or (c) an **unread** type: one of its relevant sources has no
  disposition from any non-breaching session after two replacements (`audit5_rooms.unread_types`).
- **Rates:** over the **random sample of 15** and over the **census of the 39 primary-set types**, each with a Clopper-Pearson 95 %
  interval; each also split into atlas-only types (every eligible exam 1 record from the atlas) and others. Reported beside them without
  consequence: the strict rate (any differing audited value counts) and the lenient rate (yes <-> no flips only).

**L5. Systematic fault.** A defect named by the audit and confirmed by a script or the records, such that **recomputing exam 1 with the
frozen code after correcting only that defect** changes exam 1's front label at its scope: (i) a **pipeline defect** (code or a mapping
table applied by code that does not do what its rulebook says: the quote check, the merge, the fill, the aggregation, the atlas map) that
changes the label of any primary-set type or of at least 2 audited types in the same direction; or (ii) a **record-level defect of one
kind** (a mis-recorded field, one record's mapping) that changes the labels of at least 2 audited types in the same direction. A single
record-level error is not systematic; it is counted by L4. Outcomes of the consensus rule as written (its
confidence, multi-DN, preparation and specificity tiers) and of the blind rule as written (sightings excluded; dedicated sources set
aside) are by design and are **not** faults; they are reported: the number of audited types whose exam 1 label the tiers decide (the
label would differ with the tiers skipped), with direction, and the number whose label the sighting exclusion decides.

**L6. Consequence (fixed now).** If the sampled error rate is above 10 % (at least 2 of 15), or the census error rate is above 10 % (at
least 4 of 39), or a systematic fault is found (the sample is part of the census, so with 3 census errors the seeded sample can still
trigger; the prompt's sample rule is kept deliberately, Part D 3), exam 1 is described everywhere as **compromised**, with the audited exploratory re-score
beside it. Otherwise exam 1 stands as reported, with an **erratum** listing every exposed type whose audited label at exam 1's scope
differs from exam 1's (DNg100's entry first).

**L7. Exploratory re-score (once, marked exploratory).** Exam 1's primary statistic, A1's `primary_score` AUROC on the primary set
(PREREG v2 S1), with the stratified bootstrap (seed 20261120) and the one-sided permutation (seed 20261121), recomputed by the frozen
scoring code (`scoring.pipeline.primary`) with audited labels substituted for the primary-set types whose audited label at exam 1's
scope is yes or no; other types keep exam 1's label; the decision rules are not re-applied (`ledger/scripts/rescore_audit_v1.py`,
outside the label-side scripts because it reads the prediction lock).

**L8. Outputs.** `LABEL_AUDIT_v1.md` (report) and `labels_audit_v1/` (assignment, room manifests, every session's outputs with hashes,
the transcript audit, checked records, reader and audited labels, the comparison with exam 1, the error rates, errata, the re-score).
Labels v2 is not touched.

---

## Part F. Forward ledger v2 (`forward_v2/`, `ledger/scripts/forward_v2.py`)

**F1. Types.** Every type in a Part R category (replicated, near-replicated, single-fly hit, stable non-driver) that has a kit line (G6)
and has not already been tested in headless flies. A type's category is its B1r x B2r category, or, if that is "neither", its A1 x B2r
category. **Already tested** = an eligible headless record with a yes/no front-leg value among the audit's final records (L3; sightings
allowed), or among exam 1's records of any eligibility (`labels_v2/records.jsonl`; a mapped type and a verified quote). The audit reads
only exam 1's source cache, so for a type with no cached source "not already tested" means "no headless test found in that cache".

**F2. Three readings** (yes/no for rhythmic front-leg stepping in a decapitated fly with the type switched on both sides):
- **Replication reading:** replicated and near-replicated yes; single-fly hits no; stable non-drivers no.
- **Single-connectome reading:** A1 driver yes; everything else no.
- **Counting reading:** top third of two-step signed counting (G7) yes; the rest no.

**F3. The short list** (at most 12 types; only types with at least one line listed as available, F4; every candidate not listed is given with the reason
in `CANDIDATES_WHY.csv`): (1) every replicated and near-replicated type of F1, at most 9, by the smaller of its B1r and B2r
scores (descending); (2) three stable non-drivers with the highest two-step counting scores, as controls (places reserved), by S2
(descending); (3) single-fly hits filling the remaining places, MANC ones first because the published model is MANC: (3a) MANC single-fly
hits that are A1 drivers (hits of the authors' own list), (3b) other MANC single-fly hits, (3c) MaleCNS single-fly hits. Ties within a
group: more lines listed as available, then more clean lines (G6), then the larger score (B1r for 3a/3b, B2r for 3c), then name.
Fewer than 6 qualifying: lock what there is and say why.

**F4. Per type:** the three readings, every kit line ID, the collection holding it (`forward_v1.collection_of`), whether it is listed as
available on the day of the lookup, and whether any kit row of the line names another DN type (possible joint activation). Availability
is looked up by a fresh agent from public catalogue pages only (no login, account, order or form), recording per line: `yes`, `no`,
`not_found` or `lookup_failed`, with the URL and the date (as forward ledger v1); only `yes` counts as available.

**F5. Decision rule for the lab result (fixed now).** The protocol is forward ledger v1's (`forward_v1.PROTOCOL`, copied into
`forward_v2/README.md`). Each tested type's **outcome** is the lab's own call, yes / no / no clear outcome, recorded verbatim before the
readings are compared. For two readings X and Y, let D be the tested types with a yes/no outcome on which X and Y disagree, n = |D|, k the
number in D that X gets right, and q(n) the smallest k with one-sided binomial P(K >= k | n, 1/2) <= 0.05: X is **supported over Y** if
k >= q(n), Y over X if n - k >= q(n), else **inconclusive** (always when n <= 4). Each comparison's two one-sided rules together have
size at most 0.0625 (n = 5) to 0.070 (n = 8) under chance. Three comparisons are pre-registered, each with its own words and no
multiplicity correction:
- **A. Replication vs single-connectome** (the prompt's question). With the kit's lines these readings disagree on at most four candidate
  types (Part Q), so **A can only be inconclusive** under this rule; its k of n is reported. A decision would need lines for types on
  which they disagree (for example the A1 drivers DNit011, DNit013, DNxl101, DNxl102, DNxl110 and DNxl133, which have no kit line).
- **B. Replication vs counting** and **C. Single-connectome vs counting**: decidable on this list.
The counting reading's accuracy on all tested types and the controls' outcomes are reported beside them, without words. `forward_v2/`
reports the short list's group sizes and the expected n of A, B and C if every short-listed type gives a clear outcome. Power (exact
binomial; probability of a decisive result for the reading that is right with per-type accuracy a):

| n (types in D) | 1-4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|
| q(n) | none | 5 | 6 | 7 | 7 | 8 | 9 | 9 | 10 |
| power, a = 0.8 | 0 | 0.33 | 0.26 | 0.21 | 0.50 | 0.44 | 0.38 | 0.62 | 0.56 |
| power, a = 0.9 | 0 | 0.59 | 0.53 | 0.48 | 0.81 | 0.77 | 0.74 | 0.91 | 0.89 |

**F6. Honesty line.** Made after both exams were unblinded and after the replication pattern was seen; clean with respect to the
experiments it predicts, which have not been done. Forward ledger v1 stays, marked superseded for the ask (`forward_v2/README.md`).

---

## Part P. The paper (`paper/PREPRINT_v0.md`, 3,500-4,500 words) and its reviews

Structure as RUN5_PROMPT section 5 Part P. Rules: every number from a locked file; no claim beyond the pre-registered verdicts and Part S's
criterion; post hoc results named as such, in the abstract too; figures made by script from locked files
(`ledger/scripts/posthoc/paper_figures_v5.py`); `paper/CLAIMS.md` gives one row per claim with the locked file and field, the tag and its
status (pre-registered and blind / pre-registered and label-free / post hoc / exploratory). The disclosure states that the analyses were
designed with, and run by, AI agents under the author's direction, naming the models. Three reviews, each by a fresh agent told the
paper's length limit, each write-once: overclaim, hostile referee (as the original authors; cheap objections tested), numbers. Each is
answered in an addendum; the paper is revised. A reviewer stopped by a provider safeguard is replaced by a new one, on another model if
needed, and logged.

## Part B. Brief and outreach drafts

`BRIEF_v2.md` (two pages, measured as run 4: US Letter, 1-inch margins, 11 pt, `ledger/scripts/posthoc/brief_pages_v4.py`), leading with
the replication result and the short list, with the first brief's rules (every number from a locked file, what it does not show, no
claim beyond the verdicts, a fresh overclaim reviewer told the two-page limit). Outreach drafts under `outreach/` with blank recipient
lines (authors <= 180 words, lab <= 150 words, one paragraph <= 120 words). Nothing is sent, posted or uploaded.

---

## Part X. Process

- **X1. Order.** Freeze; Part R from the locked tables; S0, then the copy campaigns; Part L while Part S runs (canary first; the atlas
  coders, the forensic sessions and every group holding a primary-set type in the first batch; then replacements, atlas and type
  adjudication, labels, verification, error rates); Part T if the budget allows;
  `LOCK_replication_v1` (Parts R, S, T, L; tag `ledger-replication-v1`); Part F; `LOCK_forward_v2` (tag `ledger-forward-v2`); RESULTS_4,
  the paper and its reviews, the brief and the drafts. Each lock gets a pre-mortem in the LOG first; tags are pushed and timestamped
  (OpenTimestamps).
- **X2. Compute.** GitHub Actions only (no Modal; the Mac runs no prediction), through run 4's runner and workflow unchanged, campaigns
  packed and published by `gha5.py`. At most 20 GitHub jobs queued or running. At most 100 runner-hours for the run, counted by step time
  (LOG L102; `gha5.py runner-hours`). Chunks sized from S0's measured job times to finish in under an hour.
- **X3. Budget rule.** After S0, the projected total of everything remaining (Part S copies, Part T, determinism re-runs) is written in
  the LOG. Above 80 runner-hours, Part T is dropped; above 95, Part S uses 8 copies (1-8), decided and logged before any copy campaign is
  published.
- **X4. Determinism.** Every campaign passes determinism on a re-run sample: 20 jobs per campaign drawn with `default_rng(20261529)` from
  its packed jobs, re-run unchanged in a separate campaign (`det5-<stage>-run5`); their digests (`digest_v4` where present, else run 2's
  `digest`) must be identical. A failure triggers a full re-run of the campaign (S8).
- **X5. Code and amendments.** All analysis code of Parts R, S, T, L and F is committed before the freeze and hashed by
  `LOCK_prereg_v5.json`; the audit kit and every kit v2 file a room can receive are pinned by `reviews_v5/AUDIT_KIT_MANIFEST_v1.json`
  (hashed by the same lock; the launcher refuses to build a room if any file differs). A later change to it is an amendment row (`lock5.py amend`, `AMENDMENTS_v5.jsonl`) recorded before the change
  is committed, with the outputs before and after reported if the code had already run on real data; never a rule, criterion, seed,
  record or label; never a file hashed by a pre-run-5 lock; nothing hashed by `LOCK_replication_v1` after it, nothing at all after
  `LOCK_forward_v2`. A bug found after a lock gets a new version with a changelog; a locked file is never edited.
- **X6. If time runs short** (RUN5_PROMPT section 7). Checkpoint: at 12:45 PST on 2026-11-23 (12 hours into the run), if the remaining
  never-drop items cannot be finished by 16:45 PST, items are dropped in this order: Part T (only if not yet published), the hostile
  referee's tests, the outreach drafts. Each drop is logged with the time and what had been collected. Never dropped: the per-type lock,
  Part R, the DNg100 and exposed-type audit, the census and sample of L3 (iii) (in the first batch; never dropped once started), Part F,
  the paper, the brief; copies of Part S are never dropped once collected (S8).
- **X7. Nothing leaves the machine** except pushes to the repository (branch, tags, campaign releases), OpenTimestamps hash submissions,
  the model calls of the reader and reviewer sessions (as in runs 2-4), the L1 sessions' read-only fetches of their assigned DOIs, and
  read-only catalogue page lookups (F4). No email, post, upload, order or contact.
- **X8. Fairness.** The original authors' work is described accurately and generously; what of theirs holds up is said plainly.

---

## Part D. Departures from RUN5_PROMPT (each with its reason)

| # | RUN5_PROMPT | This rulebook | Reason |
|---|---|---|---|
| 1 | Part T: "the single-neuron procedure" on MaleCNS | B1r's job specification with one copy stimulated, in both flies | No single-neuron procedure is validated on MaleCNS in the ledger; B1r/B2r's procedure is the one whose replication Part R describes; MANC is run as the same-procedure reference. |
| 2 | Part R: "overlap ... next to its ceiling" | replication rates and the overlap coefficient carry the words; Jaccard reported with its size limit | With 15 against 29 drivers, Jaccard cannot approach its split-half ceiling (audit finding 10). |
| 3 | Part L: a random sample of 15 | the sample of 15 plus a census of all 39 primary-set types; compromised if either rate is above 10 % | The census removes sampling error; either route triggers the consequence, so the prompt's rule is kept. |
| 4 | Part L: readers re-read sources | the atlas is re-coded with exam 1's atlas procedure; reader disagreements are adjudicated; unclear outcomes are verified | Without these, the audit's own noise and generic figure coding would count as exam 1 errors (audit findings 3, 4). |
| 5 | Part L: "exposed types and every labelled type in the Part R table" | also every Part R type with a kit line (L3 iv) | F1's "not already tested" must rest on the audit (audit finding 14). |
| 6 | Part F: the decision rule compares the replication and single-connectome readings | that comparison is kept and shown to be inconclusive by construction with the kit's lines; replication vs counting and single-connectome vs counting are added with their own words | With the kit's lines the first comparison has at most 4 informative types (audit finding 2). |
| 7 | Part F: "every replicated and near-replicated type with a line" | at most 9 (by the smaller score), controls' places reserved, only types with an available line; single-fly hits ordered A1 drivers first | Keeps the list within 12 with its controls; "orderable lines"; the published model's own hits are where the readings disagree. |
| 8 | Part F: power "for the number of types in each group" | power by the number of informative types (n), with the expected n per comparison and the group sizes reported | The binomial rule's power depends on n, not on group sizes. |
| 9 | Part F: "not already tested in headless flies according to the audit" | the audit's final records, or exam 1's records of any eligibility | Exam 1's sightings-excluded records could miss a headless test; the union is the stricter test. |
| 10 | Section 7: drops "if time runs short" | a fixed checkpoint, a narrower drop list (no copies once collected; L3 iii never dropped once started) | Prevents optional stopping on the confirmatory test and on the error rate (audit finding 6). |
| 11 | Part L: readers "with the sources in the room" | run 2's C1 web exception for abstract-only or unreachable cached sources | 24 cached sources are abstract-only or unreachable; exam 1's readers fetched these. |
| 12 | Part S: "the replicated set fixed from the locked B2r table" | kept; the high-confidence version is a sensitivity analysis | The prompt fixes the primary set; Part R leads with the high-confidence version (section 8). |
