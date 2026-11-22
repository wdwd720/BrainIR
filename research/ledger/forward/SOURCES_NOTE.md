# Why this ledger has two sources

PREREG v4 E2 names three sources: the authors' model, two-step signed counting, and the robust model (the passing Part C fix with the highest specific reproducibility). No fix passed all four Part C criteria (`reliability_v2/C.json`, locked by `LOCK_reliability_v2.json`: `passing` is empty, `robust_model` is null), so there is no robust model and the ledger has two sources. Per fix, on the primary type set:

- Fix 1 (dose-sweep scoring): fails 2 cross-fly agreement; 2 left-right agreement; 3 still informative.
- Fix 2 (pooled read-out): fails 2 cross-fly agreement; 2 left-right agreement; 4 still about the wiring.
- Fix 3a (floor 1): fails 2 cross-fly agreement (not evaluable: not evaluable: no pre-floor MaleCNS counts (PREREG v4 C2.3)); 2 left-right agreement; 4 still about the wiring.
- Fix 3b (floor 3): not evaluated: cx-3b-run4: no results collected.
- Fix 4 (symmetrised): fails 2 cross-fly agreement; 4 still about the wiring.
- Fix 5a (type-pooled within side): fails 2 cross-fly agreement; 2 left-right agreement; 4 still about the wiring.
- Fix 5b (type-pooled across sides): fails 2 cross-fly agreement; 4 still about the wiring.
- Fix 6 (input-normalised): failed its DNg100 control at every gain (C4).
- Fix 7 (consensus annotations): fails 2 cross-fly agreement; 2 left-right agreement; 4 still about the wiring.
- Fix 8 (all network fixes): failed its DNg100 control at every gain (C4).
- Fix 9 (combined): not run (C3: needs a passing procedure-level and network-level fix).

Criterion 2 needs cross-fly agreement of at least 0.8 of its matched ceiling (and left-right where the fix keeps the sides distinct); criterion 4 needs specific reproducibility above 0 and at most 2 driver types in the rewired control. Fix 3b was dropped under the budget rule (PREREG v4 X9; LOG L122) and fix 9 needs a passing procedure-level and network-level fix.
