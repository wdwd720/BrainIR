# Resolution of the narrow review (`NARROW_prereg_v2.md`, diff c3b4e70..3d4d160), before the freeze

Each replacement was applied as the reviewer worded it.

| item | resolution |
|---|---|
| 1 amendments could touch v1-locked code | L12: "After a v2 lock, a file it hashes that no v1 lock hashes may change only as a bug fix"; S5.1: v1 locks also pass the frozen `lock.py check`, where amendments do not count. Code: `lock2.py amend` refuses any path a v1 lock hashes; `lock2.py check` ignores amendments for v1 locks. |
| 2 crash undefined, re-runs unbounded | S4: a crash is an uncaught exception that stops a run; repeated once after the fix; results the crashed run wrote govern; an analysis with status `error` is a result. Code: `score_v2.py` writes a `<run>.started.json` marker, removed on completion or refusal; a leftover marker is the only way to `--after-crash-fix`, once, after a recorded `--crash-fix` amendment. |
| 3 kit amendments too broad | L12: only kit prompts, only before the first v2 label session, only to restate a rule, each checked by the fresh L12 reviewer, with a kit changelog row; other kit files never; "files hashed by this lock change only through amendments allowed by L12 or P4b". Code: `amend` accepts only `kit_v2/PROMPT_*.md` and `kit_v2/CHANGELOG.md` among kit files. |
| 4 no independent judgment of amendments | S5.6: the gate reviewer confirms each listed amendment is a bug fix under L12, judged from its diff. |
| 5 P4b unenforced before the predictions lock | S5.1: the P4b files in `LOCK_prereg_v2.json`'s snapshot are binding (match or recorded amendments). Code: `lock2.py check` treats them as binding for that lock. |
| 6 type-label equality dropped | S4: runs P, S-b, S-c require equality of the recomputed `type_labels` with labels v2's locked `type_labels.csv`. |
| 7 gate "once" vs two script runs | L14: "the gate (its script twice, S5.6)". |
