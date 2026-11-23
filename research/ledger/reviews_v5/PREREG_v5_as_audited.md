# BrainIR prediction ledger: pre-registration, version 5 (run 5: replication, count-noise stability, label audit, forward ledger v2, paper)

Spec: `RUN5_PROMPT.md` (sha256 65fabef7...1d25). Earlier rulebooks (`PREREG.md`, `PREREG_v2.md` to `PREREG_v4.md`) and every earlier lock
stay as they are. This rulebook is frozen by `LOCK_prereg_v5.json` and the tag `ledger-prereg-v5` before any analysis or simulation it
governs. Inputs are the locked per-type tables `pertype_v1/` (`LOCK_pertype_v1.json`, tag `ledger-pertype-v1`) and the earlier locks.

**What is confirmatory.** Only Part S's test S1 (and its repeat on the A1 list) is a new confirmatory test. Part R is descriptive and
**post hoc** (its thresholds were chosen after the pattern was seen). Part L is an audit by fresh reader sessions; its re-score of exam 1
is exploratory. Part T is descriptive and optional. Part F is a forward ledger whose outcomes do not exist yet.

---

## Part Q. What was seen before this freeze (disclosure)

- Runs 1-4 in full, including both unblinded exams, RESULTS_1 to RESULTS_3, BRIEF and HANDOFF_4.
- The question round (LOG L158 and its answer, 2026-11-23): per-type scores in all nine screens for every type that is a driver
  somewhere; under that round's definitions one "stable driver" (DNg100), one "near-stable" (DNg15), 39 "discordant hits" and 92 "stable
  non-drivers" among the 245 types screened in all four half-flies; authors-concordant types (every A0 copy >= 0.5): DNg100, DNb08,
  DNit011, DNit013; DNg100's exam 1 label (no, headless, 5 records); the exposed set; the E5 flags' meaning (same band in B1r/B2r and in
  MANC's halves; MaleCNS sides never compared).
- The replication pattern (RUN5_PROMPT section 1): drivers (>= 0.5) B1r 15 types, A1 11, B2r 30; in both B1r and B2r: DNg100, DNb08,
  DNit013; of A1's 11, the same 3 are B2r drivers.
- While building the per-type tables (LOG L160): the cross-fly match confidence of every MaleCNS type (high 217, medium 29, low 82), and
  in particular that DNit013's match is low (its MaleCNS body is body-matched to MANC DNit013 but its `mancType` string says DNit011;
  MaleCNS's DNpe023 pair maps to MANC's two single-neuron types DNit011 and DNit013). DNg100 and DNb08 are high.
- Not seen before this freeze: anything of Part S (no Poisson copy of this run exists; seeds below are new), Part T, the label audit's
  readings, the two-step counting tercile of any type outside the forward ledger v1, and line availability beyond forward ledger v1's 59
  lines.

## Part G. Definitions used everywhere

- **G1. Screens and scores.** From `pertype_v1/` only: A0 by copy (`A0_copies.csv`), the four half-fly screens (`MANC_L/R.csv`,
  `MaleCNS_L/R.csv`), the whole-type screens B1r, B2r and A1 (`B1r.csv`, `B2r.csv`, `A1.csv`). Score = the tables' `score` (G5 of
  PREREG v4: mean over usable replicates, 0 if none). Halves: `score_h1` / `score_h2`.
- **G2. Driver** = score >= 0.5; **non-driver** = score < 0.05 (as G5 of PREREG v4).
- **G3. Common types** = types present in both B1r (321) and B2r (328). Types in one fly only are listed, not categorised.
- **G4. Cross-fly match confidence** = `pertype_v1/match_confidence.csv` `confidence` (high / medium / low; rule in LOG L160 and the
  table's MANIFEST). A MANC type without a MaleCNS group has no common-type entry.
- **G5. Exam 1** = labels v2 (`labels_v2/type_labels.csv`, `LOCK_labels_v2.json`); its primary set = clear front-leg label (yes/no),
  among A1's 321, not in the v2 exposed set (`forward_v1.primary_set`, 39 types); the v2 exposed set = `kit_v2/exposed_types.csv`
  (resolved) + `labels_v2/exposed_v2.csv` (`forward_v1.exposed_set_v2`, 18 types).
- **G6. Kit lines** = `kit_v2/driver_lines.csv` rows whose `manc_type` is the type (rows `AMBIGUOUS`, `UNMAPPED` or empty excluded). A
  line is **clean** for a type if no kit record of that line names another DN type in `manc_type` or `other_cells` (the forward ledger v1
  rule).
- **G7. Two-step signed counting** = `S2_twohop_signed` exactly as `forward_v1.flags` computes it on the MANC front-leg network (all of a
  type's members, all front-leg motor neurons); **top third** = tercile 2 of `forward_v1._tercile` over A1's 321 types.

---

## Part R. Replication (descriptive; **post hoc**: the thresholds and categories were chosen after the pattern was seen)

**R1. Categories** (common types; whole-type screens; RUN5_PROMPT section 5):
- **Replicated:** a driver in both B1r and B2r.
- **Near-replicated:** a driver in one, and 0.3 <= score < 0.5 in the other.
- **Single-fly hit:** a driver in one, and score < 0.3 in the other; reported as MANC-only (B1r driver) and MaleCNS-only (B2r driver).
- **Stable non-driver:** score < 0.05 in B1r and in B2r, and < 0.05 in all four half-fly screens (types absent from a half-fly table
  cannot be stable non-drivers).
- Every other common type: **neither**. Types in one fly only: listed with their score.

**R2. Reports.**
1. Counts and lists of every category (with each type's B1r, B2r, A1 and half-fly scores and its match confidence).
2. **Overlap of the two flies' hit lists, next to its ceiling** (over common types): Jaccard index J(X, Y) = |X n Y| / |X u Y| of driver
   sets. (a) Full screens: J(B1r drivers, B2r drivers), with the hypergeometric expectation |X||Y|/N of the intersection. (b) Matched
   noise: the cross-half overlap = mean of J(B1r_h1, B2r_h2) and J(B1r_h2, B2r_h1), next to the **ceiling** = mean of each fly's own
   split-half overlap J(B1r_h1, B1r_h2) and J(B2r_h1, B2r_h2) (drivers on 8 seeds each). A 10,000-resample bootstrap over types (seed
   20261501) gives intervals for the cross-half overlap, the ceiling and their ratio.
3. **The same with A1** in place of B1r (A1's 16 replicates split 0-7 / 8-15).
4. **High-confidence version:** reports 1-3 restricted to common types whose match confidence is high (G4); also the medium + high set.
   A hit that fails to replicate only under a low-confidence match is listed as such, not counted as a finding.
5. **Copy concordance in A0** (types with at least one copy on each side): the number of types with at least one driver copy, with every
   copy a driver ("concordant"), and the concordance share; the same restricted to types with one copy per side; each concordant type's
   copies.
6. **The two experimentally confirmed drivers** (DNg100, DNb08): their category, scores in every screen, A0 copies and match confidence,
   with the selection caveats stated beside them: DNg100 is the neuron the model was calibrated and built around (the tuner's K was
   chosen on it); the original authors chose DNb08 themselves; both are exposed types; two confirmed neurons are a tiny sample.

Every table and sentence of Part R says "post hoc". Output: `replication_v1/R_replication.json` and `R_tables.md`.

---

## Part S. Does stability under synapse-count noise inside one fly predict replication? (pre-registered, confirmatory)

**S1. Copies.** 16 Poisson copies of MANC's raw synapse counts: `fixes.poisson_copy(manc_raw_counts(), seed)` with seeds
20261511 ... 20261526 (copy 1 ... 16), floor 5 applied after resampling (`fixes.at_floor(., 5)`), signed with the MANC presynaptic signs
(`fixes.signed(., mirror.fly("MANC").sign)`); sizes, readout and type groups are B1r's (`networks.front_leg()`; `manc_raw_counts`
refuses unless floor 5 of the raw counts reproduces B1r's matrix exactly).

**S2. Types.** Every type that is a driver in B1r or in A1 (from `pertype_v1/B1r.csv` and `A1.csv`), plus 40 types that are drivers in
neither, drawn once at pack time as `numpy.random.default_rng(20261527).choice(sorted(frame), 40, replace=False)`, frame = A1's 321 types
minus the drivers of B1r or A1.

**S3. Procedure.** The whole-type B1r screen (tuner v2, K = 1, B1's screen configuration, T = 1 s, all of the type's members stimulated,
the front-leg motor neurons read out; run 4's job kind `group_v4`, params `standard`, gain 1, no traces), seeds 0..7 per copy, through
run 4's runner and workflow unchanged.

**S0. Regression gate (before any copy is analysed).** The same job specification on the real network (no resampling; floor 5 of the raw
counts, which equals B1r's matrix) for every Part S type x seeds 0..7 must reproduce B1r's stored per-seed results
(`predictions_v2/B1r/replicates.parquet`): every job's `digest` equal, or, if a digest differs only through the runner's record format,
equal usable flag, accepted current and number of tuning runs and |score difference| < 1e-9 ("equivalent"). Otherwise Part S stops and
the failure is reported. This campaign is also the timing probe that sizes the copies' chunks.

**S4. Stability.** Per (type, copy): the copy score = mean score over the usable seeds of 0..7, 0 if none (G5). **Stability** = the
fraction of the 16 copies whose copy score is >= 0.5. Secondary: the mean copy score over the 16 copies.

**S5. Test S1 (primary).** Among the B1r drivers, R = those that are drivers in the locked B2r table (fixed now: the replicated set is
read from `pertype_v1/B2r.csv`). Statistic: the mean stability of R. **Exact one-sided permutation test**: p = (number of subsets of the
B1r drivers of size |R| whose mean stability is >= the observed one) / C(n, |R|), n = the number of B1r drivers (ties count as >=). The
same test is **repeated on the A1 list** (A1 drivers; R = the A1 drivers that are B2r drivers), reported with its own p.
- **Words** (from the B1r test only): "Stability predicts replication" if p < 0.05; otherwise "not shown".
- Sensitivity (reported, no words): (i) the same tests restricted to B1r / A1 drivers with a high-confidence match (if R keeps at least
  2 types); (ii) the same tests on the mean copy score instead of stability.

**S6. Test S2.** Among the 40 non-drivers: the number of (type, copy) pairs with copy score >= 0.5 out of 640 (the false-hit rate per
copy), the number of types with at least one driver copy, and the number with stability >= 0.5, each with an exact (Clopper-Pearson)
95 % interval over types where it is a count of types.

**S7. Power, stated before the test runs.** There are only 3 replicated types among the B1r drivers (and among the A1 drivers). The
smallest attainable p is 1/C(15, 3) = 1/455 = 0.0022 for the B1r list (1/165 = 0.0061 for A1), reached only if the three replicated types
are strictly the three most stable. Ties at the top raise it: if t drivers, the three replicated among them, share the highest
stability, p = C(t, 3)/455:

| t (tied at the top, incl. the 3) | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|
| smallest p (B1r list) | 0.0022 | 0.0088 | 0.022 | 0.044 | 0.077 | 0.12 |

So if seven or more B1r drivers are perfectly stable, the test cannot reach p < 0.05 however stable the replicated types are. **A null
result here is uninformative**: it does not show that stability fails to predict replication. A positive result rests on three types, two
of them the confirmed drivers (selection caveats of R2.6), so it would be suggestive, not general.

Output: `replication_v1/S_stability.json` (per type and copy), `S_tests.json`, `S_report.md`.

---

## Part T. The single-copy screen in both flies (optional; descriptive)

Run only if, after Part S's timing, the projected total stays at or below 80 runner-hours (X3); it is the first thing dropped (X6).
- **Types:** every type that is a driver in B1r, B2r or A1. **Copies:** every member of those types in the MaleCNS network (authors'
  matrix, G3 sides) and in the MANC front-leg network.
- **Procedure:** B1r's procedure (S3) with one copy stimulated, seeds 0..15, on the real (unresampled) networks. This is our single-copy
  variant of the whole-type procedure, not the authors' single-neuron notebook (A0); MANC is run with it as the same-procedure reference.
- **Report:** per type and fly, every copy's score; copy concordance (every copy a driver; at least one); for DNg100 and DNb08 in full;
  MANC single-copy against A0 per copy (Spearman over copies, descriptive). Output: `replication_v1/T_singlecopy.json`, `T_report.md`.

---

## Part L. Label audit (fresh reader sessions; the orchestrator never authors a label)

**L1. Sessions.** Every reading is done by a fresh `claude -p` session in its own room (`~/ledger_rooms/run5/<session>/`), with run 2's
frozen flags and deny rules (`labels2_rooms.flags_v2("reader")`: file tools only, no shell, no web, no MCP; reads of the repository,
other rooms and the orchestrator's folders denied) and run 2's sandbox profile, model `opus` with fallback `sonnet` (recorded). A room
holds only the task, `kit_v2/PROTOCOL.md`, `record_schema.json`, `synonyms.csv`, `type_list.csv`, the assigned sources copied from the
mechanical download cache (`data/ledger/sources_v2/`, run 2's), and, for the forensic sessions only, the inputs listed in L2. Both exams
are unblinded, so readers may read every source, including the dedicated simulation papers; a sighting of a simulation score does not
make a record ineligible in this audit. A session blocked by a provider safeguard is replaced by a new session on another model, logged.

**L2. DNg100 first (forensic).** Two independent sessions (F1, F2), each with: every exam 1 record of DNg100 (`labels_v2/records.jsonl`,
all fields, eligible or not), the consensus rule (PREREG v1 section 6 and `aggregate.type_labels` in plain words) and the blind rule
(PREREG v2 L4, L6), every source those records cite, every dedicated source, and every cached source whose text mentions DNg100 or a
synonym (`kit_v2/synonyms.csv`; case-insensitive, word boundaries). Task: list the five records behind the "no" with their quotes; say
which sources describe DNg100 activation in headless flies and what they report (quotes); explain the label as one or more of: (a) a
mapping error, (b) the consensus rule, (c) sources set aside by the blind rule, (d) a correct reading of a narrower experiment, (e) other,
with evidence. If F1 and F2 differ in the explanation, a third session (F3) adjudicates with both reports and the same inputs.

**L3. Re-reading.** The audited types: (i) the 18 exposed types; (ii) every Part R-categorised type (R1, excluding "neither") with an exam 1
front-leg label in {yes, no, unclear, conflicting}; (iii) 15 non-exposed labelled types drawn as
`numpy.random.default_rng(20261528).choice(sorted(frame), 15, replace=False)`, frame = exam 1's primary set (G5, 39 types) minus the types
of (i) and (ii) (all of it if fewer than 15 remain). Each type is read by **two independent sessions** (readers A and B), **blind to exam
1's labels and records** (no label, no front-leg value of any exam 1 record in the room). A session takes at most 3 types and at most 8
sources. A type's sources: every source with an exam 1 record of the type (any eligibility), every dedicated source mentioning the type or
a synonym, and every cached source whose text mentions the type or a synonym (case-insensitive, word boundaries); if more than 8, split
over sessions so that each source is read by two readers. Readers write records in the v2 schema (`record_schema.json`) for every
experiment that activates the type (thermogenetic or optogenetic) and reports leg behaviour, each with its preparation (headless /
intact_free / intact_tethered) and `front_leg_rhythm` (yes / no / unclear), plus `out/dispositions.csv` (one row per source).
- **Quote check (script):** a record counts only if its quote is found in the source's `text.txt` (whitespace-normalised, case-insensitive)
  or the reader marks it as read from a figure/page image (`notes` starting `figure:`), the latter reported separately.
- **Audited label (script):** the frozen consensus (`aggregate.type_labels`) on each type's checked records of both readers pooled, with
  eligibility as frozen except that sightings do not exclude (no source set aside); computed separately on headless records
  (`front_headless`) and on intact records (`front_intact`), and per reader for agreement.

**L4. Error rate.** Over the 15 sampled types: exam 1's front label against the audited label at exam 1's preparation scope (headless if
exam 1's `best_preparation` is headless, else intact). An **error** is a different audited value, including `conflicting`, `unclear` or
`not_assessed` (cannot verify; as PREREG v2 L11). Error rate = errors / 15 with a Clopper-Pearson 95 % interval; a lenient rate (yes <-> no
flips only) is reported beside it.

**L5. Systematic fault** = a cause named by the audit (forensic or re-reading sessions) and confirmed by a script or by the records
themselves that changes the exam 1 front label of at least 2 audited types in the same way, or of any primary-set type through a pipeline
or rule-implementation error (mapping, quote check, aggregation). The blind rule's setting aside of exposed types' dedicated sources is by
design, already handled by excluding exposed types from exam 1's headline, and is **not** a fault.

**L6. Consequence (fixed now).** If the error rate is above 10 % (i.e. at least 2 of 15) or a systematic fault is found, exam 1 is
described everywhere as **compromised**, with the audited exploratory re-score beside it. Otherwise exam 1 stands as reported, with an
erratum for DNg100's entry (and any other exposed type the audit corrects).

**L7. Exploratory re-score (once, marked exploratory).** Exam 1's primary statistic recomputed with audited labels substituted for the
audited primary-set types whose audited label (at exam 1's preparation scope) is yes or no; other types keep exam 1's label; computed by
the frozen scoring code where it accepts a labels table, otherwise by the same formula; reported beside the locked value.

**L8. Outputs.** `LABEL_AUDIT_v1.md` (report) and `labels_audit_v1/` (assignments, room manifests, every session's outputs with hashes,
checked records, `audited_type_labels.csv`, the comparison with exam 1, errata). Labels v2 is not touched.

---

## Part F. Forward ledger v2 (`forward_v2/`)

**F1. Types.** Every type in a Part R category (replicated, near-replicated, single-fly hit, stable non-driver) that has a kit line (G6)
and has not already been tested in headless flies: excluded if the audit's checked records (L3) hold an eligible headless record with a
yes/no front-leg value for it, or, for a type the audit did not read, if exam 1's eligible records hold one (`labels_v2/records.jsonl`).

**F2. Three readings** (yes/no for rhythmic front-leg stepping in a decapitated fly with the type switched on both sides):
- **Replication reading:** replicated and near-replicated yes; single-fly hits no; stable non-drivers no.
- **Single-connectome reading:** A1 driver yes; everything else no.
- **Counting reading:** top third of two-step signed counting (G7) yes; the rest no.

**F3. The short list** (at most 12 types, in this order): (1) every replicated and near-replicated type of F1; (2) three stable
non-drivers with the highest two-step counting scores, as controls (reserved); (3) single-fly hits, MANC-only first, filling the remaining
places. Within a group: more lines listed as available first, then more clean lines (G6), then the larger B1r score (MANC hits) or B2r
score (MaleCNS hits), then name. If group (1) alone exceeds 9, the same order picks 9. Fewer than 6 qualifying: lock what there is and say
why.

**F4. Per type:** the three readings, every kit line ID, the collection holding it (Janelia FlyLight split-GAL4 / GAL4 at Bloomington /
VDRC), whether it is listed as available on the day of the lookup (read-only page lookups in the public catalogues; no order, account or
form), and whether a kit record of the line names another DN type (possible joint activation).

**F5. Decision rule for the lab result (fixed now).** Each short-listed type tested as in F2 gives yes, no, or no clear outcome. Let D be
the tested types with a clear outcome on which the replication and single-connectome readings disagree, n = |D|, and k the number in D
the replication reading gets right. With q(n) = the smallest k such that the one-sided binomial P(X >= k | n, 1/2) <= 0.05:
- **supports the replication reading** if k >= q(n);
- **supports the single-connectome reading** if n - k >= q(n);
- **inconclusive** otherwise (in particular whenever n <= 4).
The counting reading's accuracy on all tested types and the controls' outcomes are reported beside it, without words. Power (exact
binomial; probability of a decisive result for the reading that is right with per-type accuracy a):

| n (types in D) | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|
| q(n) | none | 5 | 6 | 7 | 7 | 8 | 9 |
| power, a = 0.8 | 0 | 0.33 | 0.26 | 0.21 | 0.50 | 0.44 | 0.38 |
| power, a = 0.9 | 0 | 0.59 | 0.53 | 0.48 | 0.81 | 0.77 | 0.74 |

**F6. Honesty line.** Made after both exams were unblinded and after the replication pattern was seen; clean with respect to the
experiments it predicts, which have not been done. Forward ledger v1 stays, marked superseded for the ask (`forward_v2/README.md`).

---

## Part P. The paper (`paper/PREPRINT_v0.md`, 3,500-4,500 words) and its reviews

Structure as RUN5_PROMPT section 5 Part P. Rules: every number from a locked file; no claim beyond the pre-registered verdicts and Part S's
criterion; post hoc results named as such, in the abstract too; figures made by script from locked files; `paper/CLAIMS.md` gives one row
per claim with the locked file and field, the tag and its status (pre-registered and blind / pre-registered and label-free / post hoc).
The disclosure states that the analyses were designed with, and run by, AI agents under the author's direction, naming the models.
Three reviews, each by a fresh agent told the paper's length limit, each write-once: overclaim, hostile referee (as the original authors;
cheap objections tested), numbers. Each answered in an addendum; the paper revised. A reviewer stopped by a provider safeguard is replaced
by a new one, on another model if needed, and logged.

## Part B. Brief and outreach drafts

`BRIEF_v2.md` (two pages, measured as run 4: US Letter, 1-inch margins, 11 pt, `ledger/scripts/posthoc/brief_pages_v4.py`), leading with
the replication result and the short list, with the first brief's rules (every number from a locked file, what it does not show, no
claim beyond the verdicts, a fresh overclaim reviewer told the two-page limit). Outreach drafts under `outreach/` with blank recipient lines
(authors <= 180 words, lab <= 150 words, one paragraph <= 120 words). Nothing is sent, posted or uploaded.

---

## Part X. Process

- **X1. Order.** Freeze (this file, after a fresh rulebook audit); Part R from the locked tables; Part S (S0 regression and timing, then
  the copies); Part L while Part S runs; Part T if budget allows; `LOCK_replication_v1` (Parts R, S, T, L; tag
  `ledger-replication-v1`); Part F; `LOCK_forward_v2` (tag `ledger-forward-v2`); RESULTS_4, the paper and its reviews, the brief and the
  drafts. Each lock gets a pre-mortem in the LOG first; tags are pushed and timestamped (OpenTimestamps).
- **X2. Compute.** GitHub Actions only (no Modal; the Mac runs no prediction), through run 4's runner and workflow unchanged, campaigns
  packed and published by `gha5.py`. At most 20 GitHub jobs queued or running. At most 100 runner-hours for the run (trust gate
  included), counted by run 4's step-time rule. Chunks sized from S0's measured job times to finish in under an hour.
- **X3. Budget rule.** After S0, the projected total (all remaining campaigns) is written in the LOG. If it passes 80 runner-hours, Part T
  is dropped; if it passes 95, Part S uses 8 copies (1-8) and S7's table is recomputed for that case before any copy result is read.
- **X4. Determinism.** Every campaign passes determinism on a re-run sample: 20 random jobs per campaign
  (`default_rng(20261529)`), re-run in a separate campaign, digests identical.
- **X5. Amendments.** Ledger code only, recorded with `lock5.py amend` in `AMENDMENTS_v5.jsonl` before the change is committed; never a rule,
  criterion, seed, record or label; never a file hashed by a pre-run-5 lock; nothing hashed by `LOCK_replication_v1` after it, nothing at
  all after `LOCK_forward_v2`. A bug found after a lock gets a new version with a changelog; a locked file is never edited.
- **X6. If time runs short** (RUN5_PROMPT section 7): never drop the per-type lock, Part R, the DNg100 and exposed-type audit, Part F, the
  paper, the brief; drop in this order: Part T, the random-sample audit (L3 iii, then L4 becomes "not estimated" and L6 uses the systematic
  fault test only), the hostile referee's tests, copies beyond 8 in Part S (S7 recomputed first), the outreach drafts.
- **X7. Nothing leaves the machine** except pushes to the repository (branch, tags, campaign releases), OpenTimestamps hash submissions
  and read-only catalogue page lookups (F4). No email, post, upload, order or contact.
- **X8. Fairness.** The original authors' work is described accurately and generously; what of theirs holds up is said plainly.
