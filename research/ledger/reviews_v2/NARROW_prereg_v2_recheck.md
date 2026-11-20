# Narrow review, re-check after the fixes (verbatim summary of the reviewer's final note, 2026-11-20)

Verdict on 86b5ba6 (the frozen text): **freeze**. All seven fixes of `NARROW_prereg_v2.md` were applied as worded; no sentence
loosens a gate or leaves a choice for later. Two literal tensions change no gate outcome because the specific clause governs
and the code follows it: L12 "Code-snapshot sections ... only record code" vs S5.1's P4b exception; "other kit files are never
amended" vs `kit_v2/CHANGELOG.md` "(itself amended)".

Code fix required before `LOCK_scoring_v2.json` (no text change): S4 says "An analysis ending with status `error` is a result,
not a crash", but `pipeline_v2.run` caught exceptions of the primary analysis and of S-b's whole `secondary()` call, so a
failing primary would become a permanent result that no crash fix may touch. Let both propagate (a crash, repeated once after
the fix); keep `error` statuses only for single secondary analyses and the baseline comparison (PREREG v1 section 1).
