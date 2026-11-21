# PREREG v3 audit: resolution (before the freeze)

Audit: `PREREG_AUDIT.md` (fresh agent, verdict "freeze after fixes": 3 blockers, 7 majors, 4 grouped minors). Every finding was
applied before the freeze; the rulebook's "Departures" paragraph lists the resulting departures from RUN3_PROMPT.

| # | finding | resolution |
|---|---|---|
| 1 | amendment rule not enforced (run 2's `amend`/`check` honour any v2 row) | `lock3.py amend` + run 3's own ledger `AMENDMENTS_v3.jsonl`; `lock3.py check` honours only v3 rows for v3 locks and v3 rows never for v1/v2 locks; rules (never v1/v2-hashed files; after the primary predictions lock never prediction-side/scoring code; after the first h1 session never label code/kit; after the flag only a scoring crash fix), checked with recorded flags and with commit times; the gate checks run 3 locks with `lock3.py`; tests `test_lock3_amend.py` |
| 2 | label side not frozen at the freeze | `LOCK_labelcode_h1.json` (label code, kit v3, label plan and specs) written right after `LOCK_prereg_v3.json`, before the tag; T2-T4, T7 now state the label-side choices (own experiments only, `whole_two_sided` wording as in the kit, pairing key with effector class and the single-leftover rule, eligibility, kappa = 1 when chance agreement is 1) |
| 3 | best H-S depends on which arms are locked | the primary predictions lock requires H-M, H-M-s0-3 and all eight H-S arms; the scorer refuses unless all eight H-S arms are locked; tests |
| 4 | "beyond wiring" without "predicts" | `decide`: "adds value beyond wiring" needs "predicts"; otherwise reported as "H-M ranks above the best wiring baseline" |
| 5 | chance is not 0.5 | the permutation null's mean and 2.5-97.5 % range are reported as chance for the mean rank, top-1 and top-3; "predicts" needs the interval's lower bound above both 0.5 and the null mean |
| 6 | linear steady state dropped on a wrong argument | computed as an eighth baseline `H-S-lin` (sparse LU, one solve per unit); the spectral radius (34.33) and the solve's residual (8e-11, DNg100 test) recorded by `diag_v3_linear.py` -> `diag_v3/LINEAR_DIAG.json` |
| 7 | predictions-before-labels neither rule nor check | primary predictions lock before the first h1 session (lock tool refuses afterwards; gate condition 1 checks commit times); descriptive arms in `LOCK_predictions_h1b.json` before the labels lock (also checked) |
| 8 | "kept local" conflicts with the publisher | every Stage 2 and Stage 4 campaign is published right after the freeze, before any prediction file is committed; `publish3` refuses while HEAD holds exam 2 predictions without the labels lock; nothing is pushed between the predictions commit and the labels lock |
| 9 | cited results can become records | kit, T2 and T6: records only for experiments the source itself performed; a lead qualifies only with its own activation |
| 10 | label-to-scorer join untested; refusal after the flag | `test_assembled_labels_load_in_the_scorer` (assembly output through the scorer's reader); S6: a post-flag refusal is handled like a crash (reader fix only, recorded and logged) |
| 11 | text precision | tie tolerance, H-S tie order, centring within the analysed subset, all 16 columns required, recomputation tolerance (1e-9; frozen numbers stand), departures listed, M1 row fixed |
| 12 | meaning of `accepted`; bracketing parity | declared in P1 |
| 13 | guards and tests | `require_freeze` also needs the tag to be an ancestor of HEAD and the prereg lock to verify; isolation test extended (more prediction tokens) and reversed (prediction code never names label locations); the scorer checks the gate report's lock hashes against the flag and records its code hashes and HEAD; gate files written once |
| 14 | truth-side wording | sighting = network-simulation prediction of a hemilineage's activation phenotype; eligibility and re-reading of breached scopes stated; full-vocabulary agreement and record match rate reported; Part D items 5-6 (downloads before the freeze; folder names); motor-map changes confirmed by the reviewer (`MOTOR_MAP_REVIEW.md`, "Confirmation of applied changes"), d15 without variant |

Also adopted from the motor-map reviewer's confirmation: dimension 1 is the maximum over the six body-part pools (a fraction of all
702 motor neurons diluted small pools).

## Re-check of the fixes (`PREREG_RECHECK.md`, fresh agent: "freeze after fixes", 2 blockers, 2 majors, 4 minors): all applied

| # | finding | resolution |
|---|---|---|
| 1 | a false `unblinded: true` unlocks the scoring code | a recorded unblinding counts only when the flag was committed before the row; `amend` sets `unblinded` from the flag's commit, not its existence; test |
| 2 | the checker can amend itself; scoring tests amendable | `lock3.py` and its test are never amended (a change is a new version); the scoring and prediction-side tests freeze with the prediction side; tests |
| 3 | a row's time is self-declared | a row is timed by max(its utc, the first commit holding its line); uncommitted rows never count; the gate notes `AMENDMENTS_v3.jsonl`'s hash; the S5.6 checklist confirms every honoured row is a bug fix |
| 4 | run 3 locks can be edited and recommitted | gate condition 1 requires exactly one commit per run 3 lock (run 2's `_lock_commits`); Part X: locks written once, lock commits never rebased |
| 5 | session times | a run without a parseable start time fails; every audited session needs a manifest; `check` uses only the repository's manifests |
| 6 | S3 tie order and float noise | the first arm within 1e-12 of the best; stated in S3 |
| 7 | recomputation from the text | S2 states that p, intervals and the chance band come only from the frozen pipeline; the recomputation checks mean rank, top-1, top-3; S1 and S2 wording fixed |
| 8 | lock-tool traps | `lock_labels` requires both prediction locks committed; `amend` uses the first-session time from repository and room manifests |
