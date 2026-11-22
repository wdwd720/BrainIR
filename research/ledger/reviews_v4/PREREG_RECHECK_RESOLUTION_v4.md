# Resolution of the narrow re-check (`PREREG_RECHECK_v4.md`, verdict "freeze after these fixes")

The re-check reviewed `git diff 5826b84 697cb31`; every finding was acted on before the freeze. The re-check file is committed
unchanged.

| # | finding | resolution |
|---|---|---|
| 1 | MAJOR: fix 9's left-right criterion never required in code | `_evaluate_fix`: for fix 9 the left-right criterion is required when its network part is one of 3a, 3b, 5a, 6, 7 (C6.2 says so). |
| 2 | MAJOR: A7's "inconclusive" branch against G7's closure rule; B1.4 could fire on an inconclusive before-pair | A7: each block's closures follow G7 on that block's own before-pair (reported only for a real gap); "closes the whole gap" also requires a real-gap before-pair; code: `block1_closes_whole_gap` requires `reported`. |
| 3 | MAJOR: Modal safeguards only in text | `gha4.load_results` compares `digest_v4` (else `digest`), refuses a result without one, refuses Modal results unless `TRUST_GATE_v4_modal.json` says identical; `modal4.run` refuses without that gate, requires a per-job time estimate and refuses when the logged spend plus the estimate exceeds $15 (X1). |
| 4 | MINOR: Modal hours outside the cap make a later choice | X9: the envelope is 300 GitHub runner-hours plus $15 of Modal (about 59 runner-hour equivalents); the Modal allocation is fixed at the post-Part-A re-budget and logged before publishing; drops and exam 2's condition use the remaining envelope. |
| 5 | MINOR: `dropped_by_presence` miscounted; no test of a ghost becoming present; gate omitted Block 3 | The count is taken inside the builder (`columns_from_counted`); synthetic test with an unmatched right member (its ghost becomes present and takes M's row); `gates_v4/MIRROR_CHECK_v3.json` adds the ten Block 3 hybrids and supersedes v2 (both earlier files kept; LOG L112). |
| 6 | MINOR: primary type set computed at analysis time outside X4 | `gates_v4/TYPE_SETS.json` written before the freeze (matched, primary, MANC side-concordant, MaleCNS uncorrected); every analysis reads it; X4's list now names `pooled.py`, `mirror.py`'s set functions and `gha4.py`'s loading, gain and check functions. |
| 7 | MINOR: step 0 ignored annotated groups within a type (7 MaleCNS types) | Step 0a pairs one-left-one-right annotated groups within the type first, then 0b the Hungarian step; MaleCNS primary types 219 (was 214), MANC 307; G9 states that unmatched extras are not checked. |
| 8 | MINOR: A7 had no "not judged" branch | A7: not judged -> the blocks run on the left-right gap and the report says the ceiling is too low (as the code does). |
