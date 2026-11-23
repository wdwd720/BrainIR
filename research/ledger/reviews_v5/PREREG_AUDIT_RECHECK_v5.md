Verdict: freeze after these fixes

# Re-check of the revised `research/ledger/PREREG_v5.md` (run 5)

**What was re-checked.**
- Revised text: `research/ledger/PREREG_v5.md`, sha256 0c59c4bc4f5912384a74ac9a7f7da821ce3727b556bc8bc5f52ef84135ced819.
- Against: the audited text, kept unchanged as `reviews_v5/PREREG_v5_as_audited.md` (sha256 e0207d48..., identical to the version I
  audited); the resolution `reviews_v5/PREREG_AUDIT_RESOLUTION_v5.md` (sha256 244e4461...); and my first report, which is unchanged.
- Code read in full. It is still untracked, so it can change before the freeze. Files in `ledger/scripts/`, with sha256 prefixes:
  `gha5.py` fe45b4ffd14f7ee1, `stability_v1.py` 310817f356b926a9, `replication_v1.py` 605706bcdd7b67ca, `audit5_rooms.py`
  f87711248e301235, `labels_audit_v1.py` 84a7915ceffecbb1, `forward_v2.py` 2bd585b3d6024745, `rescore_audit_v1.py` 0df486a7bd0c90a5.
  These hashes are as of 02:22 PST. `audit5_rooms.py` changed once during the re-check (02:10, a quota-aware scheduler); every finding
  below holds for the current version.
  Also read: the four new tests, `research/ledger/audit_kit_v1/`, and the frozen helpers these files call (`labels2_rooms`,
  `labels_audit`, `labels2_audit`, `labels2_collect`, `gha`, `gha4`).
- Ground rules: nothing was edited, created or deleted except this report; no git command that changes anything was run; Python was
  run with bytecode writing off.

**What the verdict means.** New findings 1-4 (majors) must be fixed before the tag. They are text or code fixes and need no data. New
findings 5-15 are recommended; 5 and 6 are code bugs that would otherwise need amendments after real data exist.

**Checked and correct.**
- The new tables are right. S7's A1 row is C(t,3)/165 = 0.0061, 0.024, 0.061, 0.12, 0.21, 0.34. The extended F5 table is right for
  n = 1-12 (q = none, then 5, 6, 7, 7, 8, 9, 9, 10; power 0.62 / 0.91 at n = 11 and 0.56 / 0.89 at n = 12). F5's "at most 0.070" is the
  maximum size under chance over n <= 12 (n = 8).
- The counts in the text are right:
  - 16 drivers and 305 frame types (S2);
  - 43 Part T types;
  - 107 types in the top third (G7);
  - 11 of 15 and 6 of 11 high-confidence drivers, with the minimum p values 1/55 and 1/15;
  - 24 abstract-only or unreachable sources;
  - 4 of 39 for the census threshold.
- **S3/S0 now match the code.** The jobs are built by `gha._v2_jobs`, and the "equivalent" fields are those of `s0_compare`.
- **Parts R and F (`replication_v1.py`, `forward_v2.py`) implement the text's rules.** This covers the categories, both versions, OC and
  J with their ceilings, the bootstrap rules, the clean-line rule and the F3 order. Two output files are named differently from the
  text (new 13).
- **The audit's schema copy differs only as L1 says.** `audit_kit_v1/record_schema.json` differs from kit v2's only by a description
  and the added `audit` pass.
- **One worry I checked is moot.** Allowing sighting records in the audit could make L4 count a difference that the blind rule
  creates by design. But no primary-set type has a sighting record, so this cannot happen.

## The 23 findings of the first report

| # | Finding (severity) | Status | Reason |
|---|---|---|---|
| 1 | S3 "no traces" cannot pass S0 (blocker) | resolved | S3 is B1r's exact specification (`group_v2`, traces). S0 checks every stored field. Code matches. |
| 2 | F5 can only be inconclusive (major) | resolved | A is declared inconclusive by construction. B (replication vs counting) and C (single-connectome vs counting) are added with words, and `forward_v2.comparisons` reports n. |
| 3 | L4 counts the audit's own noise (major) | partly | The text is fixed (adjudication, verification, strict rate without consequence). But the code's "unread" rule counts every audited type without a final record as an error, even when verification confirms exam 1. That reinstates the noise (new 1). |
| 4 | Atlas-only types; unchecked `figure:` records (major) | partly | Re-coding with A/B/C and the agreement rule for `figure:` records are sound. But the atlas rooms receive the type map, which exam 1's procedure withheld (new 3). |
| 5 | L5 has no counterfactual (major) | resolved, but see new 2 (major) | The counterfactual is defined; rule outcomes are decided by design, with counts; "the audit corrects" is defined. The new defect list creates a different major problem on the same rule (new 2). |
| 6 | Discretionary drops (major) | resolved | All 16 copies are analysed once any is collected; L3 (iii) is in the first batch and never dropped; X6 has a fixed checkpoint and a harmless drop list. |
| 7 | Text and code disagree; code untracked (major) | partly | Items (a)-(i) now match. New disagreements: new 1, 3, 4, 5 and 6. The code is still untracked; X5 requires it to be committed before the freeze. |
| 8 | Low-usability drivers; no score reference (major) | resolved | Sensitivities (iii), (iv) and the reference (v) are added and implemented. "Clearly stronger than (v)" is undefined (new 7). |
| 9 | Low-confidence matches one-sided; which version leads (major) | resolved | Flags apply in both directions, both versions are shown side by side, and the high-confidence version leads. |
| 10 | Jaccard ceiling unreachable (major) | resolved | Replication rates and OC carry the words; J is reported with its size limit. |
| 11 | Blindness control misdescribed (major) | partly | Run 2 deny rules, the sandbox, the canary and the breach rule are added. But the tool-mode fallback cannot pass the canary, the canary is not enforced, and the transcript audit is run 1's, not run 2's (new 4). |
| 12 | F3 order ambiguous (minor) | resolved | Every key is fixed, and the code matches. |
| 13 | F5 outcome undefined (minor) | resolved | The protocol is attached, the lab's call is recorded verbatim, and the size is stated. |
| 14 | "Already tested" rests on exam 1 (minor) | resolved | L3 (iv) and the union rule are in place. Nine (iv) types have no cached source at all (new 9). |
| 15 | L3 (iii) frame; L4 population (minor) | resolved | Census plus sample; an unread type is an error. See the optional note in new 12. |
| 16 | L2/L3 process gaps (minor) | resolved | All of (a)-(e) are fixed. The F3 trigger is still a reading of free text (new 13). |
| 17 | L7 statistic unnamed (minor) | partly | Named in the text, but `rescore_audit_v1.py` reads a column that does not exist (new 6). |
| 18 | Part S housekeeping (minor) | partly | (c)-(g) are fixed. (a) and (b) cannot run as written on the collected results (new 5). |
| 19 | Cross-reference slips (minor) | resolved | All four are fixed. |
| 20 | Part R details (minor) | resolved | The text and `replication_v1.overlap` agree. |
| 21 | Header blurs what is confirmatory (minor) | resolved | Only S1 on the B1r list carries words. |
| 22 | Part Q gaps (minor) | resolved | One new inaccuracy: the "not seen" counting-tercile claim (new 10). |
| 23 | No departures table; no resolution file (minor) | resolved | Part D and the resolution file exist. |

Not resolved outright: 3, 4, 7, 11 (partly; majors) and 17, 18 (partly; minors). Each is carried into a new finding below.

## New findings

### 1. Major. The code's "unread" rule turns "the readers recorded nothing" into an exam 1 error, against L4 (b)

Quoted: L4 "(c) a type left unread (L1)." L1 "A breaching session's records are excluded and its task is given to a new session, at most
twice; a type left unread after that counts as an error in L4." L3 "a source without a disposition goes to a new session, at most
twice."

Problem: in the text, "unread" means unread after the replacement sessions. `labels_audit_v1.errors()` defines it as
`unread = au == "not_assessed" and t not in finals` and sets `err = ... or unread`. So any audited primary-set type that ends with no
counted record is an error whatever the verifier finds. This covers:
- both readers writing nothing for it;
- records dropped by the quote check;
- a different `manc_type` chosen by the readers;
- an adjudicator that writes nothing for a disputed type.

L4 (b), the verification route, was added to stop exactly this noise from counting (first report, finding 3), and here it is
bypassed. Separately, nothing in the code implements the replacement of breaching sessions or of sources without a disposition. So
the text's "unread" cannot be computed, and whether to replace a session is left to hand. A type with no verifier output also
becomes an error ("not_verified"); the text is silent on that.

Fix: define "unread" as "a relevant source of the type has no disposition from a non-breaching session after two replacements".
Implement disposition tracking and replacement specs (`-r1`, `-r2`) mechanically. Send every other non-clear label, including
"nothing recorded", to verification (L4 b). State that a type whose verification produces no output is an error (or re-run it).

### 2. Major. L5's defect list makes a single misread record a "systematic fault"

Quoted: L5 "A defect (a deviation from the written procedure: a mapping error, a mis-recorded field, or code that does not do what its
rulebook says, in the quote check, the merge, the fill or the aggregation) named by the audit, confirmed by a script or the records,
such that recomputing exam 1 with the frozen code after correcting only that defect changes exam 1's front label at its scope for at
least 2 audited types in the same direction, or for any primary-set type."

Problem: "a mis-recorded field" (an exam 1 reader's misreading) and "a mapping error" in one record are defects, and the clause "or
for any primary-set type" applies to them. So one confirmed misreading that flips one primary-set label makes exam 1 "compromised".
That makes L6's 2-of-15 and 4-of-39 thresholds moot. It also leaves a later judgment call, whether a given difference is a
"mis-recorded field" (a defect) or a reading the auditor merely disagrees with, and that call decides the consequence. "Systematic"
in RUN5_PROMPT means a fault with a pattern.

Fix: limit "or for any primary-set type" to defects in code or pipeline steps (the quote check, the merge, the fill, the aggregation,
or a mapping table applied by code). Record-level defects (a mis-recorded field, a record's mapping) count as systematic only if the
same kind of defect changes at least 2 audited types in the same direction. Every record-level error is already counted by L4.

### 3. Major. The atlas re-coding is not exam 1's procedure: its rooms hold the type map

Quoted: L3 "is re-coded with exam 1's atlas procedure (PREREG v2 L8)" and "code every atlas line by line ID, without types"; L1 "Room
contents. The task; `kit_v2/PROTOCOL.md`, `type_list.csv`, `synonyms.csv`, `driver_lines.csv`; the audit kit".

Problem: PREREG v2 L8 has the coders work "without the map". Run 2's `labels2_rooms.build_room` therefore left `type_list.csv`,
`synonyms.csv` and `driver_lines.csv` out of atlas-coder rooms ("PREREG v2 L8: the coders work without the type map").
`audit5_rooms.build_room` copies all four kit files into every room, including `a5-atlas-A/B` and the atlas adjudicator `a5-atlas-C`.
Yet their prompts say "You do not know, and must not try to find out, which DN types the lines label." With `driver_lines.csv` in the
room, a coder can see which lines belong to well-known walking neurons. Withholding the map removed that bias in exam 1. So the
resolution's "two coders blind to types" is not true of the code, and L1 contradicts L3.

Fix: leave `type_list.csv`, `synonyms.csv` and `driver_lines.csv` out of `atlas_code` and `atlas_adj` rooms, as run 2 did; say so in L1;
add a test.

### 4. Major. The L1 isolation and breach machinery does not run as written

Quoted: L1 "Before the first reader starts, a canary session in the same mode must fail to read a planted file in another room and a
run 2 room's records; if the sandbox prevents a session from running at all, sessions run in run 2's tool mode with the deny rules
above, and this is logged."; L1 "Every session is checked by run 2's frozen transcript audit (`labels_audit.audit_session`)."

Problems:
- (a) **The tool-mode fallback cannot pass its own canary.** The canary's planted file is `~/ledger_rooms/run5/_canary_planted/`,
  and the tool-mode deny rules (`flags_v2` plus run 2's rooms) do not cover `~/ledger_rooms/run5/`. Deny-listing that folder would also
  deny the session's own room. So in tool mode the read succeeds and the canary fails, and if the sandbox does not run, the rulebook
  leaves no way to start the audit.
- (b) **Nothing enforces the canary.** `launch()` does not check `CANARY_<mode>.json` before starting readers.
- (c) **The audit is run 1's, not run 2's.** `audit5_rooms.transcript_audit()` calls run 1's `labels_audit.audit_session` and treats
  every issue as a breach. Run 2's audit (`labels2_audit.py`) added one exception: a session reading its own tool-results files that
  its own WebFetch saved is not a breach. This code lacks that exception, so a web session that reads a PDF it fetched is a breach and
  all its records are excluded. Five of the 22 reader groups are web groups. The eligible exam 1 sources of six primary-set types (DNfl023,
  DNb05, DNg79, DNp07, DNp10, DNp47) lie in them, and all of those of DNg79 and DNp47 do. Combined with new 1, such exclusions become
  L4 errors: four would reach the census threshold.

Fix:
- Use run 2's audit rule (`labels2_audit`'s own-tool-results exception) through a v5 wrapper, and name it in L1.
- Make `launch()` refuse reader, coder, adjudicator and verifier kinds unless the canary for that mode passed.
- For tool mode, either test the canary only against paths the deny rules cover (run 2 rooms, the repository, `LEDGER_SCRATCH`) and
  state that sibling-room reads are policed by the transcript audit, or give each session a parent folder that the other sessions'
  deny rules can name.

### 5. Minor. S8's error and re-run rules do not fit how results are collected

Quoted: S8 "a job still failing counts as not usable (score 0 by G1) and is listed"; "A determinism failure (X4) triggers a full re-run
of that campaign; if digests still differ, S1 is reported without words"; "once any copy result is collected, every copy that ran is
analysed".

Problem:
- **Errors and re-runs are dropped.** `gha.collect` never stores error records and keeps the first result per key. A re-publish
  (`publish5 --attempt`) therefore cannot replace or add results for keys already stored.
- **A persistent error aborts the analysis.** A job that errors in every attempt leaves its key missing, and
  `stability_v1.copy_scores` then stops ("incomplete (type, copy) cells") instead of counting it as not usable. `n_errors` is always 0,
  and errored jobs are counted, not listed.
- **The full re-run cannot be compared.** A full re-run under the same name is discarded key by key, so S8's comparison cannot be
  made.
- **The copy rule is not enforced.** `stability_v1.py part-s --copies 8` would analyse 8 copies even when 16 were collected.
- **The S0 gate is not enforced.** Nothing in `gha5.py` refuses to pack or publish a `ps-*` campaign before `S0_REGRESSION.json` says
  "identical" or "equivalent".

Fix: treat keys still missing after the re-runs as unusable seeds and list them. Run a full re-run as a separately named campaign,
compare it key by key, and say which results are used. Make `part-s` refuse fewer copies than the collected ps campaigns hold. Make
`build_ps` refuse unless the S0 gate passed (and, for 8 copies, unless X3's decision is logged).

### 6. Minor. L7's script cannot run: wrong column name

`rescore_audit_v1.py` selects `cmp_["audited_at_scope"]`, but `labels_audit_v1.errors()` writes the column `audited`, so the
re-score fails with a KeyError. No test covers it. Fix the name before the freeze, so that the fix is not an amendment made after
seeing labels.

### 7. Minor. S5's reading rule and rank direction are not fixed

Quoted: "A positive S1 can only be read as "noise stability adds to the score" if it is clearly stronger than (v); this is stated with
the result, without a test."; "rank the n = 15 B1r drivers by stability (midranks for ties)".

Problem: "clearly stronger" is a judgment made after the result. The text does not say which way ranks run; the code ranks ascending,
which is the right way. For reference, the rank version of (v) gives p = 144/455 = 0.32 (16 seeds) and 167/455 = 0.37 (seeds 0..7).

Fix: define the reading, for example: "adds to the score" only if S1's p < 0.05 and both (v) p values are >= 0.05; otherwise "not
distinguishable from the score itself". Add "(rank 1 = least stable)".

### 8. Minor. Some sessions are very large

Quoted: L3 "given both readers' records of the type (all fields) and the type's relevant sources (at most 3 types per session)".

Problem: type adjudicators have no source cap, and the largest per-type source sets are large (non-atlas text):

| Type | Sources | Size |
|---|---|---|
| DNp01 | 24 | 2.3 MB |
| MDN | 23 | 2.3 MB |
| DNa02 | 13 | 1.8 MB |

Up to three such types can share one room. Separately, one 4-source reader group carries 45 types. Long type lists and very large
rooms make misses likely, and under new 1 misses become errors.

Fix: give an adjudicator only the sources that either reader's records of the type cite, plus the sources where one reader has a
record of the type and the other does not; split by the readers' 4-source / 300 KB rule. Consider splitting groups whose type list is
long.

### 9. Minor. "Final records" undefined; some (iv) types have nothing to read

Quoted: F1 "among the audit's final records (L3; sightings allowed)".

Problem: L3 never defines "final records". In the code they are the readers' counted records (C's for a disputed type) plus the atlas
records. Also, 9 of the L3 (iv) types have no cached source at all (DNa14, DNg21, DNg39, DNg63, DNg78, DNp33, DNp35, DNp41, DNp46), so
for them "not already tested" means "not found in exam 1's source cache".

Fix: define "final records" in L3, and state the cache limit in F1.

### 10. Minor. Part Q: one "not seen" claim does not hold

Quoted: "the two-step counting tercile of a type outside forward ledger v1's 63".

Problem: my first report, disclosed in Part Q, counted disagreements between the replication and counting readings on a short list
that includes DNa07, DNp02, DNg13 and DNp07. Those four types are outside forward ledger v1's 63, and the counts presuppose their
terciles. Every type's S2 is also in a locked run 1 file seen in runs 1-4.

Fix: reword, for example: "seen: S2 of every type (run 1) and, through the audit report, the counting reading of the plausible
short-list types".

### 11. Minor. The forensic prompt leads

Quoted: `audit_kit_v1/PROMPT_FORENSIC.md` "This label has been questioned, because published work is said to report that DNg100
activation drives walking."

Problem: the sentence tells F1 and F2 which answer is expected. That can tilt them away from (d), "a correct reading of a narrower
experiment". Their explanation feeds L5 and the erratum.

Fix: state the question neutrally ("Establish what the sources report about DNg100 activation and why the label came out as it did").
The kit manifest pins the prompt, so change it before the manifest is written.

### 12. Minor (optional). The census and sample triggers overlap

Quoted: L6 "If the sampled error rate is above 10 % (at least 2 of 15), or the census error rate is above 10 % (at least 4 of 39)".

Problem: the sample is a subset of the census. With 3 errors in the census (7.7 %, below the threshold), at least 2 of them fall in a
random 15-type sample about a third of the time (0.33). The fixed seed then decides the consequence. Part D 3 keeps the prompt's rule
deliberately; that is defensible.

Fix: either keep it and say this in L6, or make the census decisive and report the sample rate beside it.

### 13. Minor. Small text-code mismatches and one judgement left to free text

- The F3 trigger depends on reading `forensic.md`. Have F1 and F2 also write `out/explanations.csv` (one flag per a-e), so "the sets
  are not identical" is mechanical.
- The atlas adjudicator also gets keys that only one coder coded (`labels_audit_v1.atlas_sides`). That is sensible; say it in L3.
- F5 says the protocol is copied into `forward_v2/README.md`; `forward_v2.py` writes it into `DECISION_RULE.json`. F3 says reasons go in
  `CANDIDATES.csv`; the code writes `CANDIDATES_WHY.csv`. Align the names.

### 14. Minor. Records from web-fetched full text can never pass the quote check

Quoted: L1 "a session whose assigned sources include one whose cached copy is abstract-only or unreachable may fetch exactly those DOIs
with WebFetch"; L3 "is found in the source's normalised `text.txt` and text supplements".

Problem: `audit5_rooms.quote_status` searches only the cached `text.txt` and text supplements. For the 9 abstract-only or unreachable
reader sources, a quote copied from the fetched full text is not in the cache. It comes back `not_found`, and the record is dropped
unless it is marked `figure:`. The web exception therefore cannot produce counted records. No primary-set type's eligible exam 1
records come from these sources, so L4's rates are unaffected. Exposed-type errata and F1's "already tested" are affected.

Fix: for web-fetched sources, count a record when the other reader independently records the same experiment (same DOI, preparation
and type) with a matching value, or have a second web session check the quote, as exam 1's Phase B did. State the rule in L3.

### 15. Pending before the freeze (process)

- Commit the analysis code (X5), which is still untracked.
- Write `reviews_v5/AUDIT_KIT_MANIFEST_v1.json` (`audit5_rooms.py kit-manifest`) after the kit changes above; `build_room` refuses
  without it.
- Re-run the tests after the fixes. The end-to-end label test exercises neither the "unread" semantics nor the re-score.
