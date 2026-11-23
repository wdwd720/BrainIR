# Label audit v1 (run 5, PREREG v5 Part L)

**Consequence (L6, fixed before the audit): exam 1 stands as reported, with an erratum for six exposed types, DNg100 first.** The sampled
error rate is 1 of 15 (6.7 %; 95 % interval 0.2-31.9 %), the census error rate over all 39 primary-set types is 3 of 39 (7.7 %; 1.6-20.9 %),
both at or below the 10 % threshold, and no systematic fault (L5) was found. DNg100's exam 1 label ("no" for rhythmic front-leg stepping in
headless flies) is wrong: the audit finds "yes", for reasons the forensic readers traced to one record and the consensus rule (below).

Every label in this audit was written by fresh reader sessions; the orchestrator wrote none. Files: `labels_audit_v1/` (assignment,
room manifests, every session's outputs with hashes, transcript audit, checked and final records, reader and audited labels, the comparison
with exam 1, `ERROR_RATES.json`, `RESCORE_exploratory.json`).

## 1. DNg100 (forensic sessions F1 and F2)

Two independent sessions had all 28 exam 1 records of DNg100 (5 eligible), verbatim excerpts of the consensus and blind rules, the frozen
aggregation code and the 10 sources that cite or mention DNg100 (including the papers that report simulations). They reached the same
explanation (the same set of flags, so no third session was needed):

- **(a) Mapping error: no.** Every record names BDN2 or DNg100, which the sources equate, with the same split line.
- **(d) A correct reading of a narrower experiment.** The only "no" is a record of DNg100 activated together with a brake neuron (BRK); the
  BRK phenotype (the fly resists leg flexion and extension) is what the record reports. The same figure's DNg100-alone condition shows
  front-leg stepping.
- **(e) A record-level coding inconsistency.** That co-activation record was coded `minor_offtarget`, while the DNg100-alone records from
  the same paper and line were coded `unknown` specificity.
- **(b) The consensus rule** then decided: after the confidence tier, its "best specificity" step kept only the `minor_offtarget` record, so
  one "no" outranked two headless "yes" records.
- **(c) The blind rule** had already set aside the 23 records from the dedicated simulation papers (22 of them headless "yes") as
  sightings, so the "no" stood unopposed.

Both sessions give the correct label as **yes, with high confidence**: every headless experiment that activates DNg100 alone reports
front-leg stepping, across four papers and several surfaces. The re-reading sessions (section 2), blind to exam 1, also give DNg100
"yes" in headless flies.

## 2. Re-reading (L3)

- **Audited types:** 73: the 18 exposed types; 24 Part R types with an exam 1 label; all 39 primary-set types (census), with the seeded
  sample of 15 among them; and 33 Part R types with a kit line (sets overlap).
- **Sources:** 64 reader sources in 26 groups, each read by two independent sessions (readers A and B; 14 of the 52 sessions could fetch
  their abstract-only sources), plus the atlas, re-coded with exam 1's own procedure by two coders blind to types.
- **Quotes:** of 375 reader records, 372 quotes were found verbatim (after normalisation) in the source text and 3 were marked as read
  from a figure; 4 records failed the schema and were dropped.
- **Agreement:** readers A and B gave the same label, at the scope that matters, for 67 of 73 types. The six disputed types (DNa01, DNa02,
  DNp03, DNp05, DNp09, DNp29) went to 8 adjudication sessions. The two atlas coders agreed on 107 of 120 keys; 13 went to the atlas
  adjudicator. Three exam 1 records of primary-set types with a non-clear audited label went to a verifier, which confirmed exam 1's value
  for all three (DNa11 yes, DNg14 yes, DNp13 no).
- **Isolation:** no session breached (run 1's transcript audit with run 2's own-tool-results exception). Run 2's sandbox profile blocked
  every outside read but also stopped sessions from writing their outputs, so all sessions ran in run 2's tool mode, the rulebook's
  pre-specified fallback, after its own canary passed (LOG L166).

## 3. Comparison with exam 1 (L4)

Of the 54 audited types that have an exam 1 front label, 12 differ in any way at exam 1's scope (the strict count).

| Type | Exam 1 | Audited | Counts as an error? | Why |
|---|---|---|---|---|
| DNg30 (primary, sampled) | yes | no (headless) | yes, under L4's scope rule | Exam 1's `best_preparation` is headless because one low-confidence headless record exists, but its "yes" was decided by intact atlas records after the confidence tier dropped that record. The audit's records are the same experiments; at the intact scope it agrees ("yes"). |
| DNp03 (primary) | no | yes (intact) | yes | Exam 1 coded one source's screen figure "clean, medium confidence"; the audit's adjudicator coded the same records low confidence, so the atlas "yes" decided. The audit's own readers split (A no, B yes). |
| DNp05 (primary) | no | yes (intact) | yes | The same source and mechanism as DNp03. |
| DNa11, DNg14, DNp13 (primary) | yes, yes, no | not clear | no | The verifier confirmed exam 1's value. |
| DNg100 (exposed) | no | **yes** | erratum | Section 1. |
| DNa01, DNa02 (exposed) | no | unclear | erratum | Adjudicated; headless records disagree. |
| DNg13 (exposed) | no | unclear | erratum | |
| DNg62 (exposed) | yes | unclear | erratum | |
| MDN (exposed) | yes | conflicting | erratum | |

**Rates:** sample 1 of 15 (DNg30), census 3 of 39 (DNg30, DNp03, DNp05). Both are below the 10 % threshold. Atlas-only types: 0 of 21
errors; other types: 3 of 18. Lenient rate (yes <-> no flips only): 1 of 15 and 3 of 39. Without the scope-rule case (DNg30), the census
count would be 2 of 39; it is counted, as the rule says.

## 4. Systematic fault? (L5)

No. The defect the forensic sessions named for DNg100 (a co-activation record coded with a better line specificity than the plain
records) is record-level and changes one audited type. DNp03 and DNp05 move the same way through the same source, but no defect in exam 1
was named: a blind adjudicator rated that figure's confidence lower than exam 1's readers did, and the audit's own two readers split.
**By design (reported, not faults):** the consensus rule's tiers decide the exam 1 label of 30 of the 54 compared types (unanimity over
all eligible records would give another value, mostly "conflicting"), and the sighting exclusion decides one (DNg100). Readers of exam 1
should know how much its labels rest on the tie-break order.

## 5. Erratum to exam 1 (L6)

Exposed types (never in exam 1's headline) whose audited label differs: **DNg100 no -> yes** (headless); DNa01 no -> unclear; DNa02
no -> unclear; DNg13 no -> unclear (intact); DNg62 yes -> unclear; MDN yes -> conflicting. Exam 1's locked files are unchanged.

## 6. Exploratory re-score (L7, once)

With audited labels substituted for the primary-set types whose audited label is yes or no (DNg30, DNp03 and DNp05 change), A1's AUROC
on the 39 primary-set types is **0.559** (95 % interval 0.396-0.706, permutation p = 0.25), against the locked **0.577** (0.417-0.724,
p = 0.18), which the frozen code reproduces exactly. Two-step signed counting, the best wiring baseline, is 0.713 on the audited labels
(0.669 locked). The audit does not change exam 1's conclusion. **Exploratory.**

## 7. Limits

- The audit readers are language-model sessions of the same family as exam 1's; agreement between them is not independence from the model.
- They read exam 1's source cache (64 sources plus the atlas); 9 audited types have no cached source at all.
- The atlas line map is exam 1's single reading, held fixed.
- L4's scope rule produced one error (DNg30) that is not a disagreement about any record.
- Cost: 68 sessions, $141 at list price, all on Claude Opus 5.5.
