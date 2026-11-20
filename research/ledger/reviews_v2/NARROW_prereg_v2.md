fix first: 1-3 block the freeze; 4-7 are one-line fixes.

1. Contradiction; loosens gates 1 and 4. L12 "After a lock, a file it hashes may change only as a bug fix" is unscoped, and S5.1 "recorded amendments count as matching" covers the v1 locks. So v1 `frozen_code` (`agreement.py`, `aggregate.py`) may change after kappa is seen, against "v1 is not amended". Replace: "After a v2 lock, a file it hashes that no v1 lock hashes may change only as a bug fix". Add to S5.1: "the v1 locks must also pass the frozen `lock.py check`, where amendments do not count".

2. Post-unblinding choice. S4: "A run whose pipeline crashed is run again once the crash is fixed (L12)". "Crash" is undefined (`score_v2.py` counts any `error` status), re-runs are unbounded, and PREREG v1 section 1 makes an analysis error a result. Replace: "A crash is an uncaught exception that stops a run; it is re-run once after the fix, and results already written govern. An analysis with status `error` is a result, not a crash."

3. Contradiction. L12 allows "kit files (`kit_v2/`) only before the first v2 label session", yet says "files hashed by this lock are not edited". "Bug fix" fits only code, yet kit tables (`synonyms.csv`, `exposed_types.csv`) decide labels. Replace: "kit prompts (`kit_v2/PROMPT_*.md`) only before the first v2 label session, only to restate a rule of this text, each checked by the fresh L12 reviewer; other kit files are never amended", and "files hashed by this lock change only by L12 or P4b amendments".

4. Loosens gate 6. S5.6 "confirming 1-5 from the gate report": no one independent judges amendments. Replace: "confirming 1-5 from the gate report, that each listed amendment is a bug fix under L12 (from its diff), and that nothing has been joined".

5. P4b unenforced. S5.1 "code-snapshot sections are reported, not required (L12)": until `LOCK_predictions_v2.json`, the P4b files are only in a snapshot. Replace: "code-snapshot sections are reported, not required, except the P4b files in `LOCK_prereg_v2.json`, which must match or be reached by recorded amendments".

6. Later choice. S4 "not with the frozen kit-only check" drops the equality with the locked `type_labels.csv`. Replace with: "and require them to equal labels v2's locked `type_labels.csv`".

7. Contradiction. S5.6 runs the gate script "once before the checklist and once after it", but L14 says the gate "runs once". Replace in L14: "the gate (its script twice, S5.6)".
