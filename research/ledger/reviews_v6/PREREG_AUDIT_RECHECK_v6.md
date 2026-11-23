# PREREG v6 audit: re-check of the revision (commit 2c7fcdc)

## What I re-read

- `PREREG_AUDIT_RESOLUTION_v6.md`, the revised `PREREG_v6.md` and LOG L179.
- The changed code: `thirdfly_v1.py`, `prereg6_planning.py`, `gha6.py`, `lock6.py`, `banc.py`, `screens6.py`.
- The changed tests: `test_gha6.py` and `test_thirdfly_v1.py`.
- `TYPE_SETS_v6.json` and `PLANNING_v6.json`.

## What I checked directly

- The frozen set sizes equal the rulebook's: 182/181, 203/202, 293/292, 183/182, 298/297, 215/214, 310/309, 97/96 and C8's 13/12/11.
- `dx-1-run4`'s log hashes to the SHA-256 stated in Part Q 6 (1db9b231...).
- 0.71 is the two-step signed count's own lowest value in run 4 (0.713, MANC-R vs MaleCNS-L).
- No test, and nothing in the planning script, computes BANC wiring.

Nothing was simulated, committed or edited. Severity is as in the audit.

## Status of the 14 findings

1. **C6 forced positive: resolved.**
   - The words now rest on BANC as the only target: d_M and d_C from the same resamples, and both lower ends must be above zero.
   - The prompt's D is kept beside it without words, and Part D row 7 lists the change.
   - The code (`c6`) matches the text.
   - Under exchangeability the expected gain is 2r / sqrt(2 (1 + q)) - r. This reproduces the stated 0.053 / 0.079 / 0.106.
   - The statistic is no longer positive by construction: the null check gave "pooling helps" in 0 of 40 shuffles.
   - Power is low (0.00 / 0.15 / 0.54), and the text says so.
2. **C8 turning an undefined rho into positive words: resolved.**
   - An undefined rho now gives "not shown" without permuting, and NaN permutations count as >= observed.
   - It is tested. C2's and C4's word paths are also guarded now.
3. **DNg100 handling: resolved.**
   - G5 names the word-bearing `_noDNg100` sets, and they are frozen and checked against recomputation by a test.
   - `c1`, `c2`, `c3`, `c6` and `c7` compute both versions and take their words from the set without DNg100.
   - C5 is exempt.
4. **C5 judged on the sweep: resolved.** `c5` always reads the tuned screen. The sweep score and the tuned seed count are reported beside it, and the relation to B4 is stated.
5. **X4 out of date and amendments too loose: partly resolved.**
   - The text now lists the frozen code and adopts run 5's limits.
   - But the new timing clause leaves no route for fixing an analysis bug found on collected data (new finding N1).
   - `lock6.amend` still enforces none of the new limits; they are procedural, as in run 5.
6. **Undefined cases: resolved.**
   - C3 says "not judged" when a pair is not judged, in both text and code.
   - C7 has n* = 1 for rbar >= 0.8, infinity for rbar <= 0, "not computed" when a pair is not judged, and an order-statistic interval, so it cannot give NaN.
   - C4 says "not judged" for an empty driver list, and A1 under sweep-primary is written down.
   - X2 now has a projection formula, and the BANC sweep is never dropped when the tuned screen is invalid.
   - X3 has run 5's re-run rule and errored-job rule (`screens6._fill`, tested), and the type order is fixed.
7. **"Confirmed" as a failure's default: resolved, with a gap (N3).**
   - The first line now carries both BANC ratios and the MANC-MaleCNS ratio.
   - A fixed descriptive wiring check now carries a pre-written caveat.
   - `c3_wiring` refuses to run before the freeze.
8. **Power statements: partly resolved.**
   - C4 is recomputed on each list's word set, the "at chance" sentence is fixed, and C5 and C7 explain why they have no p.
   - C8's critical rho of 0.497 is the 95th percentile of a discrete distribution. At rho = 0.4965 the permutation p is just above 0.05, so the real cut is the next lattice point, 0.503. My earlier count was P(rho >= 0.503) = 0.0496.
   - The stated powers (0.243 / 0.506 / 0.828, and those for 13 and 11 types) therefore count one non-significant value as significant and are slightly high.
   - The words are unaffected, because the test uses its own permutation p. Relabel the value or recompute with `>= 0.5035`.
9. **Part Q omissions: resolved.** Q4 now covers the sign check, the gate's per-side output and DNg100's side; Q8 covers the literature notes; Q9 covers the audit's numbers.
10. **Inputs outside a pre-freeze hash: resolved, with one caveat (N6).** The sweep log's SHA-256 is in Part Q 6 and in `lock_prereg`, and the type sets are frozen and read from file.
11. **BANC's weaker "high": partly resolved.**
    - The weakness is stated, and the same-name subset is reported beside C3 for both BANC pairs.
    - In C4 the code computes it only for the B1r list, although G5 and Part D row 14 say "beside C3 and C4" (N5).
12. **DNb08 in C8: resolved.** There is now a secondary analysis without DNb08 (11 types), and the disclosure says why.
13. **Part V: resolved.**
    - The authors' own configuration gets the first sentence, with "8 of 16" as its bar.
    - The scoring rule and the read-out difference are stated, with no companion read-out (Part D row 10).
    - Missing V seeds are not filled (N4).
14. **Tests and guards: resolved.**
    - The one-sided test now asserts each job's read-out key and the 68 and 71 masks.
    - `require_unblind` also verifies the lock.
    - `det6` stage 1 includes `bg`.

## New findings

**N1 (major): the amendment window rules out fixing analysis bugs after data collection.**
- *Where:* X4.
- *Problem:* X4 allows a bug fix only if it is "committed and pushed **before the data it affects are collected**", yet also asks for "outputs before and after ... if the code had already run on real data".
  - The analysis runs only after collection, so a crash or bug that BANC data exposes cannot be fixed under X4 before `LOCK_thirdfly_v1`.
  - The "new version" route applies only after a lock. That leaves the likeliest kind of amendment with no legal path.
  - `lock6.amend` would accept the row anyway, so the tool and the text disagree.
- *Fix:* split the rule in two.
  - **Builder and simulation code:** amend only before the campaign it affects is published.
  - **Analysis code:** a bug fix is allowed after collection, as v5 X5 allowed. Commit the row before the change, report the outputs before and after side by side, and never change a rule, criterion, seed, set, threshold or word.

**N2 (minor): C5 is judged even when neither screen is valid, and Part D does not list this.**
- B4 now exempts C5 when neither screen is valid, so DNg100's pass or fail stays on the tuned screen.
- RUN6_PROMPT says C3 to C8 are "not judged" in that case.
- The choice is defensible, because a failed prediction should be reported, but list it in Part D.

**N3 (minor): two gaps in C3's wiring check.**
- **Different floors:** BANC's two-step signed count uses the floorless matrix, while MANC's, MaleCNS's and the 0.71 cut are at the 5-synapse floor.
  - So the caveat can fire from the floor difference alone.
  - Either add a descriptive floor-5 BANC companion, or say that the floor counts as part of "the build".
- **Caveat not attached:** `c3_wiring` returns the caveat separately; `c3`'s `first_line_words` does not include it.
  - Make `run()` attach it, so the first line cannot be quoted without it.
- **Wording:** say that 0.71 is the lowest value of this statistic in run 4 (0.713), not "the lowest of the seven wiring summaries".

**N4 (minor): Part V does not apply X3's missing-key rule.**
- `part_v` reads raw results. A V2 seed lost to an error turns "k of 16" into "k of 15".
- Fill missing keys as score 0, as G4 does for the other screens.

**N5 (minor): some outputs carry words that are not of record.**
- `C6_with_DNg100` has a `words` field, and C1 to C3's companion blocks carry `agree`'s words unmarked.
- Mark them "not the words of record", as `c4` does.
- Also add the same-name version for the A1 and B2r lists in C4: the same-name set lies inside both word sets.

**N6 (minor): the stored sweep hash is never checked.**
- The prereg lock stores `dx-1-run4`'s SHA-256 under an untracked key.
- `lock6.check`'s walk skips those keys (no "/"), and `screens6.sweep_manc` does not check the hash.
- Add a load-time check against the value in Part Q 6.

## Verdict

No blocker remains. N1 should be fixed before the freeze, because it governs what may legally happen between collection and the results lock. The minors can be fixed in the same pass.
