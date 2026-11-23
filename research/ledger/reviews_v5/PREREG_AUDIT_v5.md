Verdict: freeze after these fixes

# Audit of `research/ledger/PREREG_v5.md` before the freeze (run 5)

Audited text: `research/ledger/PREREG_v5.md`, sha256 e0207d4810b789ae5219e8854d4b2ab9ead09785e76fc44b03e2845b3c05ce8f (last modified
2026-11-23 01:08 PST; unchanged while this audit was made). Specification: `research/ledger/RUN5_PROMPT.md`, sha256
65fabef7d1a213a389588052f8d19df1bd8a352e66c475f157491fc249ad1d25, which matches the rulebook's citation. Inputs consulted: the earlier
rulebooks, `pertype_v1/` (README, MANIFEST, VERIFY, all CSVs), LOG L158-L161, `labels_v2/`, `kit_v2/`, `predictions_v2/B1r/`,
`forward/`, and the code the rulebook names (`forward_v1.py`, `gha4.py`, `fixes.py`, `aggregate.py`, `labels2_rooms.py`), plus `gha.py`,
`arms.py`, `jobs*.py` and `lock5.py` where the named code depends on them. The reviewer recomputed every number below, from the
locked files or, where stated, from the source cache and the uncommitted code. Nothing was edited, created or deleted except this
report, and no git command that changes anything was run.

What the verdict means: findings 1-11 should be fixed before the tag, or answered point by point in a resolution file that the
prereg lock hashes. Findings 12-23 are clarity fixes; each removes room for a later choice.

The run 5 code was being written, uncommitted, while this audit was made, and it changed twice during it. Where the text and that
code disagree, this report says so and treats the text as what gets frozen. Code claims below were last re-checked at about 01:45
PST against these files (`ledger/scripts/`, sha256 prefixes): `gha5.py` 08417a6774fbfae9, `audit5_rooms.py` 3d7448e727afbcb9,
`labels_audit_v1.py` 8acfdf7ecbc52c81, `replication_v1.py` a1ab9c5dad3159cf, `stability_v1.py` 7e05b609c62d291c, `forward_v2.py`
b088c18a59f2c7e8; and the directory `research/ledger/audit_kit_v1/`.

## Checked and correct

- **S7 table** (recomputed): 1/C(15,3) = 1/455 = 0.0022; C(t,3)/455 for t = 3..8 = 0.0022, 0.0088, 0.022, 0.044, 0.077, 0.12; 1/C(11,3) =
  1/165 = 0.0061; "seven or more perfectly stable" -> p >= 0.077. All correct.
- **F5 table** (recomputed, exact binomial): q(n) = none, 5, 6, 7, 7, 8, 9 for n = 4..10; power at a = 0.8: 0, 0.33, 0.26, 0.21, 0.50,
  0.44, 0.38; at a = 0.9: 0, 0.59, 0.53, 0.48, 0.81, 0.77, 0.74. All correct.
- **Part Q facts** reproduce from the locked tables: drivers B1r 15, A1 11, B2r 30; B1r x B2r = A1 x B2r = {DNb08, DNg100, DNit013};
  the question round's counts (245 types in all four half-flies: 1 stable, DNg100; 1 near-stable, DNg15; 39 discordant; 92 stable
  non-drivers); A0 all-copies-driver types DNg100, DNb08, DNit011, DNit013; match confidence 217 / 29 / 82; primary set 39 types;
  v2 exposed set 18 types.
- **G7**: the S2 that `forward_v1.flags` computes on MANC equals the locked `predictions/S/types.csv` `S2_twohop_signed` for all 321
  types (maximum difference 0).
- S1-S2 seeds and the sampling rule agree with the builders in `gha5.py`; every exam 1 record's DOI is in the source cache.

## Findings (by severity)

### 1. Blocker. S3's job specification cannot pass S0 as written

Quoted: S3 "run 4's job kind `group_v4`, params `standard`, gain 1, no traces"; S0 "every job's `digest` equal, or, if a digest differs
only through the runner's record format, equal usable flag, accepted current and number of tuning runs and |score difference| < 1e-9
("equivalent"). Otherwise Part S stops and the failure is reported."

Problem: B1r was built by `gha.build_b1r` -> `gha._v2_jobs` -> `arms.group_jobs`, whose default `extras` is `{"readout_traces": True}`,
and run 1's `jobs._digest` (used by both `group_v2` and `group_v4`) hashes `readout_traces` when present. A job "with no traces" can
therefore reproduce no stored B1r `digest`. The difference then comes from the job specification, not "only through the runner's
record format": on a plain reading S0 fails for every job and Part S stops; on a lenient reading every job passes through the
equivalence clause, which checks 4 of the fields the digest covers (not `n_active_all`, `n_high_fr`, `frequency_hz`,
`n_active_readout`, the verdict or the active read-out positions). `gha5.s0_compare` applies the 4-field test to any digest
difference, without the "record format" condition. The uncommitted `gha5.py` has meanwhile switched S0, Part S and Part T to
`gha._v2_jobs` (run 2's `group_v2`, traces stored, as B1r), so the text and the code disagree on the confirmatory procedure.

Fix: S3 = "B1r's job specification exactly (`gha._v2_jobs`: run 2's kind `group_v2`, tuner v2 with K = 1, `b1_screen_cfg(10)`, T = 1 s,
read-out traces stored as in B1r), through run 4's runner, which delegates `group_v2` unchanged". S0 = digest identity for every job.
Drop the equivalence clause, or define it as equality of every field stored in `predictions_v2/B1r/replicates.parquet` (usable,
current, n_tuning_runs, n_active_all, n_high_fr, n_active_readout, n_active_notebook, frequency_hz; score within 1e-9), with the cause
of each digest difference shown, and make `s0_compare` do exactly that. Use the same wording in Part T ("B1r's procedure (S3)") and
X4 (`group_v2` results carry `digest`, not `digest_v4`).

### 2. Major. F5's decision rule can never be decisive with F1's lines

Quoted: F1 "Every type in a Part R category (replicated, near-replicated, single-fly hit, stable non-driver) that has a kit line (G6)";
F5 "Let D be the tested types with a clear outcome on which the replication and single-connectome readings disagree" ... "inconclusive
otherwise (in particular whenever n <= 4)."

Problem: this can be computed now from the locked tables and `kit_v2/driver_lines.csv`. The two readings disagree only on (a)
near-replicated types that are not A1 drivers and (b) single-fly hits that are A1 drivers. With a G6 kit line, (a) = DNa03 (1 line),
DNa13 (5) and DNp71 (2), and (b) = DNp41 (2). Every other A1 driver in a category either agrees (DNg100, DNb08 and DNa07 are yes under
both readings) or has no kit line (DNit011, DNit013, DNxl101, DNxl102, DNxl110, DNxl133). MaleCNS-only hits and stable non-drivers are
no under both. With A1 x B2r categories (R2.3), D is at most {DNa13, DNp71, DNp41}; with `forward_v2.category_of`'s mixed rule it is the same four types; and DNg54 has no kit line. So n <= 4 whatever the
lab finds and whatever "already tested" removes. The rule's only possible output is "inconclusive" (the n = 4 column, power 0), and
the rulebook does not say so; the decision rule of a never-drop item is empty. On a plausible short list (DNp71, DNa07, DNa03, DNa13;
the three untested stable non-drivers with lines and the highest S2, e.g. DNp07, DNg39, DNp26; DNg63, DNp41, DNp02, DNg13, DNg21),
the replication and counting readings disagree on up to 10 types (q = 9; power 0.38 / 0.74), and the single-connectome and counting
readings on up to 8.

Fix: before the freeze, state in F5 that with the kit's lines n <= 4, so the replication-vs-single-connectome comparison can only be
inconclusive. Then pre-register a comparison that can decide on this list, fixing now which pair carries words: for example, the same
binomial rule for replication vs counting, and for single-connectome vs counting. Or widen F1 to lines outside the kit, with a mapping
rule fixed now, and order F3 to make |D| as large as possible. Log the choice as a departure if the words move to another pair.

### 3. Major. L4 counts the audit's own noise as exam 1 errors

Quoted: L3 "the frozen consensus (`aggregate.type_labels`) on each type's checked records of both readers pooled"; L4 "An error is a
different audited value, including `conflicting`, `unclear` or `not_assessed` (cannot verify; as PREREG v2 L11)."; L6 "above 10 %
(i.e. at least 2 of 15)".

Problem: the two readers' records are pooled with no adjudication. Any A/B disagreement on a front-leg value turns the consensus into
`conflicting` (yes + no) or `unclear`, and a record dropped by the quote script can leave `not_assessed`. Each of these counts as an
exam 1 error. Exam 1 had a second reading and adjudication (`aggregate.merge_passes`); the audit has neither, so the audit's own noise
enters the rate. With a 2-of-15 trigger, an audit that produced such an outcome on its own for 10 % or 15 % of types would call exam 1
"compromised" with probability 0.45 or 0.68 even if exam 1 had no error. The v2 L11 precedent is not like for like: there a verifier
was given the record's locator and quote and read that one record. Per-reader labels are computed "for agreement" only.

Fix: before labels are computed, send every type whose reader-A and reader-B labels (at exam 1's scope) differ to a third reader
session, as L2's F3, and compute the audited label from the adjudicated records. Define an error as (a) a clear audited value (yes or
no) that differs from exam 1's, or (b) no clear audited value where a verifier given exam 1's record (locator and quote, not the value)
cannot confirm exam 1's reading (the v2 L11 procedure). Report the present strict pooled rate beside it, with no consequence. A simpler
alternative: count an error only when both readers' own labels differ from exam 1's.

### 4. Major. Atlas-only types cannot pass the script quote check, and `figure:` records are accepted unchecked

Quoted: L3 "a record counts only if its quote is found in the source's `text.txt` (whitespace-normalised, case-insensitive) or the
reader marks it as read from a figure/page image (`notes` starting `figure:`), the latter reported separately."

Problem: exam 1's 136 atlas records (10.7554/eLife.34275; all `intact_free`, `systematic_screen`) were coded from a figure by dedicated
atlas coders (PREREG v2 L8). Their quote is a line ID such as "SS00725", and the locator reads "Figure 2-source data 1 (Fig. S5), p.
29, panel ...". Under L3's normalisation only 5 of the 136 quotes occur in the atlas's `text.txt`, against 275 of 280 for other
sources. Atlas records alone carry 21 of the 39 primary-set types, 12 of the 22 types in the L3 (iii) frame, and 9 of the 17
primary-set types audited under (ii), all of them "yes". For these types an audited label exists only through `figure:` records,
which count with no check at all; otherwise the label is `not_assessed`, which L4 counts as an error. So for about half the sample, L4
measures how generic readers code a figure panel, not how accurate exam 1 is. A single unverified `figure:` record can set a type's
label.

Fix: give atlas-only types exam 1's atlas procedure (the panels, v2 L8's coding instructions, two coders), or a verification session
for each `figure:` record (given the panel and locator, not the value, as in exam 1's Phase B). Count a `figure:` record only if the
other reader or the verifier gives the same value. Report the error rate separately for atlas-only and other sampled types, and state
now which rate L6 uses.

### 5. Major. L5 has no counterfactual, and leaves the consensus-rule case open

Quoted: L5 "a cause named by the audit (forensic or re-reading sessions) and confirmed by a script or by the records themselves that
changes the exam 1 front label of at least 2 audited types in the same way, or of any primary-set type through a pipeline or
rule-implementation error"; L6 "with an erratum for DNg100's entry (and any other exposed type the audit corrects)."

Problem: "changes the label" needs a counterfactual. For a defect (a wrong mapping, a mis-recorded field, code that does not do what
PREREG v1 section 6 says) the counterfactual is clear: correct the defect and recompute with the frozen code. For the frozen consensus
rule as written there is none, yet RUN5_PROMPT names "the consensus rule" as a candidate explanation. The case is live. With the
frozen `aggregate.type_labels` on exam 1's records, DNg100's "no" comes from the rule as written: of its 5 eligible records, `_tier`
drops a low-confidence "yes", keeps the headless records, then keeps the best specificity. The one `minor_offtarget` headless "no"
therefore outranks two headless "yes" records of `unknown` specificity. Its 23 records from dedicated sources (22 headless, all "yes")
are set aside as sightings. Whether such a rule-as-written outcome, if it decides at least 2 audited types, is a "systematic fault"
(and so makes exam 1 "compromised") is left until after the audit. "The audit corrects" (L6) is also undefined.

Fix: define "changes" as "recomputing with the frozen code after correcting only the named defect gives a different label at exam 1's
scope". State now, on principle and before anyone counts which audited types the tiers decide, whether outcomes of the consensus rule
as written count. Either: by design, not a fault, reported with the number of audited types the tiers decide. Or: a fault if they
decide at least 2 audited types the same way, measured against a named alternative (for example, the majority of tiered-out records,
ties -> conflicting). Define "the audit corrects" as an audited label (after finding 3's adjudication) at exam 1's scope that differs
from exam 1's.

### 6. Major. Discretionary drops allow optional stopping, including on the confirmatory test

Quoted: X6 "drop in this order: Part T, the random-sample audit (L3 iii, then L4 becomes "not estimated" and L6 uses the systematic
fault test only), the hostile referee's tests, copies beyond 8 in Part S (S7 recomputed first), the outreach drafts."; X3 "before any
copy result is read".

Problem: "If time runs short" has no objective trigger, and nothing fixes the point after which a drop is barred. X3's "before any copy
result is read" guards only the budget route. Under X6, copies 9-16 could be dropped after copies 1-8 (or all 16) are collected, and
`stability_v1.part_s` already takes `n_copies`: that is optional stopping on the only confirmatory test. Dropping L3 (iii) removes one
of the two routes to "compromised", and the decision could be taken after the readers' outputs for (i), (ii) or part of (iii) are in.

Fix: Part S analyses 16 copies unless the 8-copy decision is logged, with its reason, before any copy campaign is collected; once any
copy result is collected, every copy that ran is analysed. L3 (iii) sessions go in the first batch, and (iii) cannot be dropped once
any (iii) session has started. Every drop is logged with the time and what had been collected. Define the trigger (for example, a
wall-clock checkpoint).

### 7. Major. The text and the run 5 code disagree, and new code would sit outside the lock

Quoted: L1 "file tools only, no shell, no web, no MCP"; L1 "A room holds only the task, `kit_v2/PROTOCOL.md`, `record_schema.json`,
`synonyms.csv`, `type_list.csv`, the assigned sources copied from the mechanical download cache"; L3 "A session takes at most 3 types
and at most 8 sources."; L3 "(case-insensitive, word boundaries)"; L3 "every Part R-categorised type (R1, excluding "neither")".

Problem: the uncommitted code differs from the text in at least these places.
- (a) S3: see finding 1.
- (b) Web: reader sessions of a web kind may fetch DOIs whose cached copy is abstract-only or unreachable, against L1's "no web".
- (c) Room contents: every room gets `audit_kit_v1/AUDIT_NOTE.md`, which overrides parts of PROTOCOL.md ("Where this note and
  `PROTOCOL.md` differ, this note wins"), and an audit copy of `record_schema.json` with an 'audit' pass. Forensic rooms also get
  CONSENSUS_RULE.md and BLIND_RULE.md. L1 lists neither, and L3 names kit v2's schema.
- (d) Session size: sessions are source groups of at most 4 sources and 300 KB, carrying every type their sources mention (no 3-type
  cap); L3 says 3 types and 8 sources.
- (e) Synonym matching: matching is case-sensitive for names without a digit and skips a stop list ("web", "sink", "snail", ...),
  where L3 says case-insensitive. The code's rule is the better one: under L3's rule, DNg74's synonym "web" matches 33 of the 96 cached
  sources.
- (f) Categories: L3 (ii) takes categories from B1r x B2r or A1 x B2r, and F1 (`forward_v2.category_of`) uses a type's A1 x B2r
  category when it is "neither" under B1r x B2r. R1 is B1r x B2r only. For L3 (ii), both readings happen to give the same 24 types
  today, so the 22-type frame and the seeded sample are the same.
- (g) Short-list order: `forward_v2.shortlist` fills group (3) with A1-driver MANC hits first, then other MANC hits, then MaleCNS hits;
  orders group (1) by B1r score; and orders group (2) by S2 first. The first is a new rule, and the other two settle finding 12's
  ambiguities one way; none of the three is in F3.
- (h) Launch mode: the code now defaults to run 2's tool mode, with the sandbox optional (`--sandbox`). It relies on run 2's
  transcript audit (breach rule, PREREG v2 L3), excluding the records of a breaching session. L1 names the sandbox profile and does
  not mention the breach rule (see finding 11).
- (i) Not tracked: none of `replication_v1.py`, `stability_v1.py`, `labels_audit_v1.py`, `audit5_rooms.py`, `forward_v2.py` is
  tracked. `lock5.py prereg` hashes git-tracked code at the freeze, and `lock5.py amend` refuses a file that did not exist at the old revision. Code first
  committed after the freeze therefore sits outside both the prereg lock and the amendment ledger until `LOCK_replication_v1`. The
  Part S and Part L analysis code could then be written after its inputs exist.

Fix: reconcile item by item before the freeze. The text is what gets frozen; where the code is better, as in (e), change the text.
Commit the Part R, S, L and F code so that `LOCK_prereg_v5` hashes it. Add to X5 that analysis code is committed before the first
collection of the campaigns or sessions it reads, and that any later change is an amendment row, with outputs before and after
reported (as PREREG v4 X4).

### 8. Major. S1's stability is degenerate for two low-usability drivers, and has no score reference

Quoted: S4 "the copy score = mean score over the usable seeds of 0..7, 0 if none (G5)."; S5 "Statistic: the mean stability of R."

Problem: two B1r drivers have few usable replicates. DNg63 is a driver on 1 usable replicate of 16 (seed 3; `frac_rhythmic` 0.06), and
DNxl121 on 6 of 16 (2 of seeds 0..7); every other Part S driver has 15 or 16. For these two, a copy score is 0 whenever the tuner
accepts none of seeds 0..7, and otherwise the mean of one or two scores. Their stability therefore measures tuner acceptance, not
whether a rhythm survives count noise, and since both are non-replicated they can move S1 for a reason unrelated to the question.
Stability is also expected to track the real-network score, because every copy uses the same eight parameter seeds, and no reference
is pre-specified. The same permutation statistic on the locked B1r score gives p = 118/455 = 0.26 (16 seeds), or 162/455 = 0.36 (seeds
0..7); the replicated types rank 2, 7 and 11 of 15 by B1r score. Without that reference beside it, a positive S1 cannot be read as
"noise stability tells you something the score does not", which is RUN5_PROMPT's use case.

Fix: add, without words: (iii) S1 with the fraction-rhythmic copy score (PREREG v4 G5: unusable seeds count as not rhythmic); (iv) S1
without B1r drivers that have fewer than 12 of 16 usable B1r replicates (DNg63, DNxl121); (v) the same permutation test on the B1r
score (seeds 0..7 and 0..15), shown beside S1. Report n_usable per (type, copy). State the DNg63 and DNxl121 facts and the score ranks in
Part Q and S7.

### 9. Major. Low-confidence matches are treated one-sidedly, and which version leads is undecided

Quoted: R2.4 "A hit that fails to replicate only under a low-confidence match is listed as such, not counted as a finding."

Problem: the rule discounts failures that rest on a low-confidence match but not replications that do. DNit013, one of the three
replicated types, has a low-confidence match (LOG L160: its MaleCNS body's `mancType` string says DNit011). Restricted to
high-confidence matches, the replicated set is exactly DNg100 and DNb08, the two confirmed drivers, so the two versions read
differently. RUN5_PROMPT section 8 asks to report both and to lead with the high-confidence version when many matches are low (here
82 of 328, 25 %), yet the rulebook does not say which version leads in RESULTS_4, the paper or the brief. "Not counted as a finding" is
undefined: left out of the counts, of J, or of F1?

Fix: flag every category member whose match is low (or medium), in both directions. Give counts and J for all common types and for
high-confidence types side by side in every report. Fix now which version leads: follow section 8, or state why 25 % is not "many".
Replace "not counted as a finding" with an operational rule.

### 10. Major. The Jaccard "ceiling" cannot be reached with these hit counts

Quoted: R2.2 "the cross-half overlap = mean of J(B1r_h1, B2r_h2) and J(B1r_h2, B2r_h1), next to the ceiling = mean of each fly's own
split-half overlap J(B1r_h1, B1r_h2) and J(B2r_h1, B2r_h2) (drivers on 8 seeds each)."

Problem: J(X, Y) <= min(|X|, |Y|) / max(|X|, |Y|). Over common types, B1r has 15 drivers and B2r 29 (B2r's 30th, DNg74, has no B1r
type), and the half-screens have 17 and 13 drivers against 34 and 30. The cross-half J can therefore be at most about (17/30 + 13/34)/2
≈ 0.47 (full screens: 15/29 = 0.52), while within-fly split halves of similar sizes can approach 1. No cross-fly result with these hit
counts can reach the "ceiling", and the ratio overstates the gap, in the direction of the paper's Result 2.

Fix: report beside J the size-limited maximum and the chance level for the cross-half pairs (the hypergeometric expectation is given
only for full screens). Add a size-robust overlap: the overlap coefficient |X n Y| / min(|X|, |Y|) with its own split-half ceiling, or
the two replication rates of PREREG v4 G6(c). Say which measure the paper's words rest on.

### 11. Major. The readers' blindness to exam 1 rests on a control that L1 misdescribes, and session exclusions are not specified

Quoted: "(`labels2_rooms.flags_v2("reader")`: file tools only, no shell, no web, no MCP; reads of the repository, other rooms and the
orchestrator's folders denied) and run 2's sandbox profile".

Problem: `flags_v2`'s deny list covers the repository, run 1 rooms, review rooms and `/tmp`. It does not cover `~/ledger_rooms/run2/`,
exam 1's session rooms, whose `out/records.jsonl` files hold exam 1's front-leg values and exist on this machine. It does not cover
other run 5 rooms either. Only `sandbox_profile` denies `~/ledger_rooms` as a whole, and it denies the orchestrator's folder only if
`LEDGER_SCRATCH` is set. The current code launches in tool mode by default (finding 7 (h)), so L3's "blind to exam 1's labels and
records" would rest on the after-the-fact transcript audit. L1 does not state that audit, nor what happens to a breaching session.
Excluding a session's records (or reassigning its sources) changes audited labels and so L4, which leaves the choice open.

Fix: correct the parenthetical. Name the mode. If tool mode, write PREREG v2 L3's breach rule and its consequences into L1 (records
excluded; sources reassigned, at most twice; a type left unread counted as fixed in finding 15). Better, require the sandbox with
`LEDGER_SCRATCH` set, keep the transcript audit as a second check, and run a canary (a file planted in a run 2 room) before the first
reader launch.

### 12. Minor. F3's order is ambiguous in four places

Quoted: "Within a group: more lines listed as available first, then more clean lines (G6), then the larger B1r score (MANC hits) or B2r
score (MaleCNS hits), then name."; "(2) three stable non-drivers with the highest two-step counting scores, as controls (reserved)".

Problem:
- (a) Group (1): replicated types are hits in both flies, so "B1r score (MANC hits) or B2r score (MaleCNS hits)" does not say which
  score orders them.
- (b) Group (2): it is unclear whether S2 or available lines comes first.
- (c) Availability: lookup outcomes other than yes and no (not found, lookup failed) are not mapped, and the rulebook does not say who
  looks up or how it is recorded (v4 E6: a fresh agent, URL and date). A type with no line listed as available can still be
  short-listed, although RUN5_PROMPT asks for "orderable lines".
- (d) "Clean": "names another DN type" does not say whether that means a type of `kit_v2/type_list.csv`, how the free text of
  `other_cells` is parsed, or whether AMBIGUOUS rows' `candidate_types` count.

Fix: order group (1) by the smaller of the B1r and B2r scores (or name the score). Order group (2) by S2 descending, then available
lines, clean lines, name. Count only "listed as available = yes", and require at least one available line or say why not. Point
"clean" to code.

### 13. Minor. F5 leaves the outcome itself undefined

Quoted: "Each short-listed type tested as in F2 gives yes, no, or no clear outcome."

Problem: the rulebook says neither who calls "no clear outcome" nor on what criterion, and gives no protocol or criterion for "yes"
(v4 E6 had a five-line protocol, `forward_v1.PROTOCOL`). The two one-sided 0.05 rules together have size 0.0625 at n = 5 and 0.070 at
n = 8. RUN5_PROMPT asks for a power table "for the number of types in each group"; the table is by |D|.

Fix: attach forward_v1's protocol. Define yes / no / no clear outcome, for example as the lab's own call recorded verbatim before the
readings are compared. State the overall error rate, and add the group sizes expected from F3.

### 14. Minor. F1's "not already tested" mostly rests on exam 1, not on the audit

Quoted: "or, for a type the audit did not read, if exam 1's eligible records hold one (`labels_v2/records.jsonl`)."

Problem: RUN5_PROMPT says "according to the audit", but outside the exposed set and the sample, L3 reads only types that have an
exam 1 front label. The likely short-list types DNa03, DNa13, DNp41, DNg63 and DNg21, and the control candidate DNg39, are therefore
judged untested from exam 1 alone. Exam 1's eligible records also exclude sightings, so a headless test reported next to a simulation score would be missed.

Fix: add an L3 item (iv): every Part R type with a kit line, read once for headless tests. Use exam 1's records of any eligibility for
the fallback. Or declare the fallback a departure.

### 15. Minor. L3 (iii)'s frame and L4's population

Quoted: "frame = exam 1's primary set (G5, 39 types) minus the types of (i) and (ii)"; "Error rate = errors / 15".

Problem: the frame is the 22 primary-set types outside Part R's categories (20 "neither", 2 one-fly types; 12 of the 22 are
atlas-only). The 17 primary-set types that (ii) audits anyway never enter L4, so the rate describes a subpopulation. The rulebook has
no rule for a sampled type that cannot be read (all sessions blocked, or no source).

Fix: report the rate on the (ii) primary-set types beside it, or compute L4 over all audited primary-set types (a stratified
estimate), or audit all 22 (a census of the 39). Fix a rule for unread types now: count it as an error, or replace it with the next
draw.

### 16. Minor. L2 and L3 process gaps

Problems and fixes:
- (a) "If F1 and F2 differ in the explanation": define "differ" (the sets of (a)-(e) chosen are not identical).
- (b) "In plain words": L2 says the forensic sessions get "the consensus rule (PREREG v1 section 6 and `aggregate.type_labels` in
  plain words)". A paraphrase by the orchestrator could steer the forensic explanation that L5 then uses. The kit on disk gives
  verbatim excerpts instead (`audit_kit_v1/CONSENSUS_RULE.md`, `BLIND_RULE.md`), which is better. Write "verbatim excerpts of v1
  section 6 and v2 L4 and L6, plus `aggregate.py`" into L2.
- (c) Line-specificity fill: say whether PREREG v2 L10's fill runs before the audit consensus (`_tier` depends on line specificity).
- (d) Assignment: fix how sources and types are assigned to sessions and readers (a seed or a deterministic rule).
- (e) Ambiguous synonyms: say whether synonyms with `ambiguous = True` count (for example "DNp09" for DNp71).

### 17. Minor. L7 does not name the statistic

Quoted: "Exam 1's primary statistic recomputed with audited labels".

Fix: name it: A1's `primary_score` AUROC on the primary set (PREREG v2 S1), with the stratified bootstrap (20261120) and the one-sided
permutation (20261121). Say that the decision rules are not re-applied (exploratory).

### 18. Minor. Part S housekeeping

Problems and fixes:
- (a) Errored jobs: the rulebook is silent (the code refuses to analyse until they are re-run). State a re-run rule and what happens if
  a job keeps failing.
- (b) Determinism: X4 gives no consequence for a failed check. State one (for example, re-run the campaign in full; if digests still
  differ, S1 gets no words).
- (c) "S7's table is recomputed" (X3, X6): the table depends only on n and |R|, not on the number of copies. With 8 copies only the
  granularity changes (9 stability values instead of 17). Say so.
- (d) A1 row: add it. C(t,3)/165 = 0.0061, 0.024, 0.061 for t = 3, 4, 5, so the A1 test cannot reach 0.05 if five or more drivers tie
  at the top.
- (e) High-confidence A1 sensitivity: state that it can never reach 0.05 (6 drivers, |R| = 2, minimum p 1/15 = 0.067; B1r: 11
  drivers, minimum 1/55 = 0.018).
- (f) Wording: S6's "the 40 non-drivers" are types that are drivers in neither (score < 0.5), which clashes with G2's non-driver
  (< 0.05). Rename them, and report S6 by B1r band.
- (g) Budget: say whether X3's 95-hour test includes Part T. Part S is about 7,168 jobs, about 43 CPU-hours at B1r's mean job time, so
  these thresholds are unlikely to bind.

### 19. Minor. Cross-reference slips

- S4's "(G5)": v5's G5 is Exam 1; the score rule is G1 (PREREG v4 G5).
- Part T's "(authors' matrix, G3 sides)": v5's G3 is the common types; this means PREREG v4 G3.
- G5's "`forward_v1.exposed_set_v2`" is defined in `brainir_ledger.scoring_v2.pipeline_v2` (forward_v1 imports it, so it works; cite
  the definition).
- G7 cites a recomputation of values that are locked in `predictions/S/types.csv` (`S2_twohop_signed`, `LOCK_predictions_v1`;
  identical; the top third is 107 types, S2 >= 3511). Cite the locked file (Part P: "every number from a locked file").

### 20. Minor. Part R details

- (a) R2.2: "A 10,000-resample bootstrap over types (seed 20261501) gives intervals" does not fix the interval type (95 % percentile?),
  shared resamples, the NaN rule (an empty union gives 0/0; v4 G6 dropped such resamples and counted them), multiplicity of
  duplicated types, or the seeds for R2.3 and R2.4.
- (b) R2.3: "The same with A1 in place of B1r" does not say whether it covers R1's categories too (`replication_v1.py` computes them,
  and `audit5_rooms.py` uses them).
- (c) R2.5: "the concordance share" needs a denominator (types with at least one driver copy, or all types with a copy on each side).
- (d) R2.1: list each type's usable-replicate counts beside its scores, since DNg63's driver status rests on one usable replicate.

### 21. Minor. The header blurs what is confirmatory

Quoted: "Only Part S's test S1 (and its repeat on the A1 list) is a new confirmatory test."

Problem: the A1 repeat carries no words (S5). Fix: call it a pre-registered secondary test, so that the confirmatory claim rests on one
p.

### 22. Minor. Part Q's disclosure gaps

Add to Part Q:
- that B1r's per-type scores and usable counts for every driver were seen (the replicated types rank 2, 7 and 11 of 15; DNg63 has 1
  usable replicate), since these bear on S1's likely outcome;
- that forward ledger v1's 59 looked-up lines include those of the stable non-drivers DNp26, DNg39, DNp31, DNg78 and DNp35, candidate
  controls whose availability, an F3 sort key, was seen;
- whether run 4's per-type Poisson-copy results (B4.2: one-sided MANC-L, two copies) were ever opened. They are the nearest earlier
  data on per-type count-noise stability; "Runs 1-4 in full" suggests yes, while "anything of Part S" says no.

### 23. Minor. No list of departures, and no resolution file for this audit

Problem: unlike v4, the rulebook has no departures table, and HANDOFF_5 item 2 needs one. Departures from RUN5_PROMPT that are not
listed:
- Part T uses our single-copy tuner variant instead of "the single-neuron procedure", and adds MANC.
- S1 is a permutation test on mean stability, not a "rank test".
- F3 caps group (1) at 9 and reserves the controls before single-fly hits (the prompt says "every replicated and near-replicated type
  with a line").
- F1 falls back on exam 1.
- L3 (ii) is restricted to front labels in {yes, no, unclear, conflicting}.
- The F5 power table is by |D|, not by group.
- Any change made to resolve this audit.

Fix: add a departures table, and a resolution file for this audit (as `PREREG_AUDIT_RESOLUTION_v4.md` did for v4) that the prereg lock
hashes.
