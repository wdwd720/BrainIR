# Resolution of the PREREG v6 audit (all 14 findings applied before the freeze)

The audit (`PREREG_AUDIT_v6.md`) is unchanged. Each finding, what was changed, and where.

| # | Finding | Change |
|---|---|---|
| 1 | C6's words positive by construction | C6 rewritten: d_M and d_C with BANC as the only target, both intervals above zero for "pooling helps", same resamples; the prompt's D beside it without words; expected size, null check (0 of 40 shuffles) and simulated power restated (`prereg6_planning.c6_planning`, `PLANNING_v6.json`); Part D row 7; `thirdfly_v1.c6`; test `test_c6_null_and_c8_undefined`. |
| 2 | C8 turns an undefined rho into positive words | Rulebook: undefined rho gives "not shown", no permutation run; a NaN permutation counts as >= observed. Code `thirdfly_v1.c8`; test (all 12 outcomes 0 gives "not shown"). |
| 3 | Rulebook and code disagree on DNg100 | G5 states the word sets (all `_noDNg100`; C1-C2 label-consistent without DNg100; C8 the 12); every test computes both versions and attaches words to the one without; the sets are frozen in `gates_v6/TYPE_SETS_v6.json` (read by the code, checked against recomputation by a test); C5 exempt. |
| 4 | C5 judged on the sweep under B4's fallback | C5 always on the tuned screen; sweep score and tuned seed count beside it without words; the relation to B4 stated. |
| 5 | X4 out of date; amendment rule too loose | X4 lists the frozen code and copies run 5's limits (bug fixes only; never a rule, criterion, seed, type set, record or label; committed and pushed before the data it affects are collected; outputs before and after reported); old Part D row 11 deleted. |
| 6 | Undefined cases | C3: a not-judged pair gives "not judged"; C7: "not computed" if a pair is not judged, n* = 1 if rbar >= 0.8, infinity if rbar <= 0, order-statistic interval (`_q`), resamples with rbar <= 0 counted; C4: an empty driver list gives "not judged", A1 under sweep-primary written down (B4); X2: projection rule, the sweep never dropped when the tuned screen is invalid; X3: run 5's full re-run rule ("not determinate") and errored-job rule (at most two re-publications, then a not-usable seed with score 0; `screens6._fill`, tested); G1: type order sorted by name. |
| 7 | "Confirmed" is also a failure's default | The first line gives both BANC ratios with intervals beside MANC-MaleCNS; a descriptive wiring check after the freeze (two-step signed count, BANC vs MANC and vs MaleCNS; reference 0.823) with a fixed caveat below 0.71 (`thirdfly_v1.c3_wiring`); Part D row 13. |
| 8 | Power statements | C4 recomputed per list on its word set (`PLANNING_v6.json`); C8's critical value from 400,000 permutations (0.497) and power restated, with the note on ties; C5 and C7 state why they have no p; C4's fixed "at chance" sentence. |
| 9 | Part Q gaps | Part Q 4 (gate per side and frequency, sign check, DNg100's side annotation), Q 8 (the literature notes' BANC facts), Q 9 (the audit's numbers). |
| 10 | Inputs outside a pre-freeze hash | `dx-1-run4`'s result log hashed by `LOCK_prereg_v6.json` (`lock6.lock_prereg`), SHA-256 in Part Q 6; the annotation-only sets written to `gates_v6/TYPE_SETS_v6.json` and read by the analysis. |
| 11 | BANC's "high" weaker | Stated in G5; a same-name subset (97 / 96) beside C3 and C4 without words; Part D row 14; the limitation goes in the paper. |
| 12 | DNb08 in C8 | A secondary analysis without DNb08 (11 types); stated in C8's disclosure. |
| 13 | Part V | The authors' configuration gets its own first sentence (`part_v`'s `authors_configuration_sentence`); the scoring rule stated; the read-out difference (130 vs 129) stated, no companion read-out (Part D row 10). |
| 14 | Tests and guards | The one-sided test now asserts each job's read-out key and the 68 / 71 masks; `banc.require_unblind` also requires `LOCK_prereg_v6.json` to verify; `det6` includes the gate `bg` (X3). |
