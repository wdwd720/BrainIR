# PREREG v3 audit (fresh, independent)

**Date:** 2026-11-21.

**Rulebook:** read in full at sha256 `eadc92b9…`. Re-checked at `f0400bf4…` (still untracked and changing); every passage cited below is unchanged.

**Code:** committed HEAD `95d41da`, which file:line references follow. Uncommitted edits add an `H-S-lin` arm. With them, the suite gives 185 passed and 1 failed (`test_groups_h1::test_wiring_baselines` expects 7 H-S arms).

## Verdict: **freeze after fixes**

The prediction side is sound:
- `screen_group_v3` equals the frozen `screen_group` apart from the declared read-outs. The tests check run 1's fields and digests.
- M3, the pools and the H-S arithmetic match the text and the current motor map.
- P7 passed.
- GitHub manifests and tags show no hemilineage job. I did not scan the keys in local `results.pkl` files; that is the Stage 2 reviewer's job.

The weak points are the amendment and lock scope, the comparator set for "beyond wiring", and two statistical statements.

## Findings

**1. Blocker: the amendment rule (Part X) is not enforced.**
- *Where:*
  - `lock2.py:199`: `amend` treats `UNBLIND.json`, exam 1's retired flag, as the unblinding marker;
  - `lock2.py:147`: after unblinding, only a scoring_v2 crash fix counts;
  - `lock2.py:386`: `check` honours amendment rows for every non-v1 lock;
  - `gate_h1.py:69` runs that `check` for every h1 lock.
- *Probe:* rows for `scoring_h1/__init__.py`, `groups_h1.py` and `gate_h1.py` are accepted. A genuine S6 crash fix of `pipeline_h1.py` is refused.
- *Consequence:* scoring or rule code can be "bug-fixed" after predictions, after labels, or after `UNBLIND_h1.json` exists. Every lock, and gate condition 1, still pass.
- *Fix:* add `lock3.py amend` and a v3 row predicate.
  - "Unblinded" means `UNBLIND_h1.json` or its retired copy exists. After that, only a `--crash-fix` of `scoring_h1/` or `score_h1.py`.
  - No amendment to the scoring or prediction code (`scoring_h1`, `score_h1`, `groups_h1`, `predict_h1`, `typescreen_v3`, `jobs_v3`) once `LOCK_predictions_h1.json` exists.
  - No amendment to the label code or kit once the first h1 session has started.
  - Point S5.1 and `gate_h1.py:69` at the v3 checker.
  - Add tests.

**2. Blocker: the label side is not frozen at the freeze.**
- *Where:* `lock3.py:64` (the prereg lock excludes `LABEL_CODE_H1`); `lock_prereg` never hashes `kit_v3/`. T8 locks both only "before the first h1 label session", which may come after the predictions exist.
- *What already exists:* the kit `PROTOCOL.md`, `labels3_assemble.py`, `labels_h1/core.py` and `gate_h1.py`. They contain rule-level choices the rulebook does not state:
  - a record is eligible only if none of its sessions breached (`labels3_assemble.py:206`);
  - pairing uses the effector *class*, with a one-to-one fallback for left-over records (`core.py:98-138`), where T3 says "effector";
  - `whole_two_sided` means "all thoracic segments the source covers", and readers choose partial "only if the source says so" (PROTOCOL §1);
  - kappa is set to 1 when chance agreement is 1 (`core.py:225`).
- *Fix:* run `lock3.py labelcode` right after `lock3.py prereg`, before the tag (or hash both in the prereg lock), and write these choices into T2, T3 and T4.

**3. Blocker: "best of seven" H-S depends on which arms are locked.**
- *Where:* `lock3.py:79-93` locks any subset of arms. `pipeline_h1.py:116-120` silently skips unlocked H-S arms and maximises over the rest.
- *Consequence:* leaving out an H-S arm changes the comparator. An orchestrator who remembers outcomes from training could choose which arm to leave out.
- *Fix:*
  - `lock_predictions` refuses unless H-M, H-M-s0-3 and every H-S arm are locked; `arms_not_locked` may name only the others;
  - the scorer refuses unless every H-S arm is present;
  - add tests.

**4. Major: "adds value beyond wiring" does not require "the model predicts".**
- *Where:* S3; `scoring_h1/__init__.py:116`.
- *Probe:* `decide(p=0.40, lo=0.31, vs.lo=0.02)` gives `model_predicts` false and `adds_value_beyond_wiring` true.
- *Fix:* make the claim only when "the model predicts" also holds; otherwise report the comparison descriptively.

**5. Major: "Chance is 0.5" is not the null (S2, S3).**
- *Probe:* 200 synthetic datasets with no unit-specific information. The units with at least 3 coded dimensions are "movers", and the silent units are coded `no` on at most 2 dimensions.
  - The mean percentile rank averaged 0.577.
  - The interval's lower bound exceeded 0.5 in 24.5 % of datasets.
  - The permutation p was below 0.05 in 5.5 %.
- *Consequence:* the p-value is calibrated and guards the verdict. But the stated chance level, the "lower bound > 0.5" criterion and every descriptive comparison to 0.5 (and top-1/top-3 against 1/43 and 3/43) are misleading.
- *Fix:* report the permutation-null mean and its 2.5–97.5 % range as "chance", for the mean rank and for top-1/top-3. Require the lower bound to exceed the null mean, or drop the interval criterion.

**6. Major: the linearised-steady-state baseline was dropped on a wrong argument (P3).**
- *The argument:* a spectral radius above 1 makes the fixed point unstable, not undefined. (I − gW)⁻¹s exists unless 1 is an eigenvalue of gW.
- *The number:* "34.3" is backed by no hashed artefact.
- *Consequence:* the drop removed a competitor from the S3 maximum, which favours H-M.
- *Status:* uncommitted work now adds `H-S-lin`. To finish it:
  - commit `diag_v3_linear.py` and its output into `diag_v3/`;
  - change "seven" in P3, S3 and S4.5, and drop the "not defined" sentence;
  - update the failing test.

**7. Major: predictions before labels is neither a rule nor a check.**
- *Where:* P10 and T8. `gate_h1.py:59-81` checks that the labelcode lock precedes the first session, but not the predictions lock. The marking at `lock3.py:92` only says "before `LOCK_labels_h1.json` exists". The label plan and session specs are already committed.
- *Fix:* add the rule: `LOCK_predictions_h1.json`, with H-M, H-M-s0-3 and every H-S arm, is committed and OTS-stamped before the first h1 session starts. Arms that finish later go into a separate, descriptive lock. Add a `predictions_h1_before_sessions` check (commit times only) to gate condition 1.

**8. Major: "kept local until the labels lock" (P10) conflicts with the publisher.**
- *Where:* `publish3` refuses until `origin/ledger/v1 == HEAD` (`gha3.py:190`). R3 and R4 also go through `publish3` (`gha3r.py:85`), and every lock needs tracked files.
- *Consequence:* any campaign after `predictions_h1/` is committed (H-C, H-D, sensitivity, determinism, R3/R4 "while the label sessions work") requires first pushing the predictions to the public repository while web-enabled search sessions run. The kit's "do not visit GitHub" reduces this risk but does not remove it.
- *Fix (either):*
  - publish all Stage 2 and Stage 4 campaigns before committing any prediction file;
  - or commit predictions on a local-only branch.

  In both cases, make `publish3` refuse while HEAD contains `predictions_h1/` or `LOCK_predictions_h1.json` and `LOCK_labels_h1.json` is absent.

**9. Major: cited results can become records.**
- *Where:* T2, T6, kit PROTOCOL §1. The kit says to code an experiment when a hemilineage "was activated … and the source reports what the flies did". No rule in the kit limits records to the source's own experiments; I grepped the protocol and prompts for previous/earlier/review/own/cited.
- *Consequence:* a paper that restates Harris 2015 (Soffers' discussion, a search lead, a review) can produce records. Harris would then count twice, as an agreeing "lab", which inflates the consensus and the ceiling.
- *Fix:* records only from activation experiments the source itself performed; cited outcomes get no record. T6: a lead qualifies only if it reports its own activation.

**10. Major: the label-to-scorer join is untested, and a refusal after the flag has no remedy.**
- *The gap:* no test passes `consensus.csv` and `lab_*.csv` as written by `labels3_assemble.py` through `pipeline_h1._cons`. The end-to-end test feeds the scorer a hand-made consensus, and the flow test stops at the gate. The formats look compatible by inspection.
- *The remedy gap:* S6 defines a crash as an uncaught exception, but `score_h1.py` catches `BlindErrorH1` and returns 2. A format refusal after the flag exists is therefore neither a crash nor amendable.
- *Fix:* add that end-to-end test before the freeze. Declare that a post-flag refusal is handled like a crash: fix the reader only, and log it.

**11. Minor: text precision.**
- (a) Ties use a tolerance of 1e-12 (`scoring_h1/__init__.py:14`). State it.
- (b) A tie for best H-S goes to the first arm in `HS_ARMS`. State it.
- (c) By class and the ceiling re-centre O within their subset. Say so in S1 and S4.4.
- (d) `_cons` checks only the 12 primary columns (`pipeline_h1.py:75`), but S7 requires d1–d15 and d7p.
- (e) S6 lacks a tolerance and a rule for when the independent recomputation disagrees.
- (f) List every departure in one place: k0 added; four seeds for H-C and the sensitivity groups; units with at least 3 coded dimensions; precedence across sources; d8, d9 and d12 dropped; H-X not run.
- (g) M1's `any_body` row still says "wing (incl. TTM)".

**12. Minor: never-accepted replicates (P1, M2).**
- In P7, the 50-neuron random group bracketed a cliff: 72 against 5,194 active neurons between currents 20.9 and 23.8. Its seeds ended `weak` or `strong` by bisection parity.
- So M2's "last run" read-out is either near-silent or network-wide, by parity.
- Declare now that this is the model's answer, and that `accepted` means "at least 100 neurons active, members included".

**13. Minor: guards, tests and lock hygiene.**
- (a) `require_freeze` (`gha3.py:53-60`) only checks that a tag of that name exists. Also require it to be an ancestor of HEAD and `lock3.py check LOCK_prereg_v3.json` to pass.
- (b) The isolation regex (`test_label_side_isolation_h1.py:16`) misses `groups_h1`, `predict_h1`, `gha3`, `jobs_v3`, `typescreen_v3`, `arms_h1` and `results.pkl`. Add the reverse test (prediction code never names `labels_h1`, `kit_v3`, `sources_h1` or `consensus`); a grep finds none today.
- (c) The scorer should compare the gate report's lock hashes with the flag's, and record the scoring-code SHA-256 and HEAD in its output.
- (d) `gates_v3_at_freeze` and `reviews_v3_at_freeze` are binding and not amendable. Re-running `p7-check`, `trust-compare` or the canary after the freeze would overwrite a hashed file and fail gate condition 1 for good. Write new files instead.

**14. Minor: truth-side wording.**
- (a) A T7 sighting is "any model prediction". Restrict it to network-simulation predictions of a hemilineage's activation phenotype.
- (b) T4.1 and S5.2 should say what the code does: a final record is eligible only if neither reader nor the adjudicator breached, and a breached scope is re-read (v2 L3).
- (c) Report agreement over the full vocabulary and the record match rate beside the gate's kappa.
- (d) Part D should say what `data/ledger/sources_h1` (modified 01:25, before the freeze) holds and that nobody opened it, and that the location list's folder names tie 13A, 13B and 12B to "grooming" and 9A to "walking_stopping".
- (e) The motor map changed after its review. Get the reviewer's confirmation, and say whether d15 is checked without the 65 AbNT motor neurons (review F3).

**Freeze checklist:** fix 1–3 and 10, write 4–9 into the text, lock the prereg and the labelcode together, then tag.

## Sightings: none

I saw no hemilineage activation or silencing outcome.

- **By existence only:**
  - `data/ledger/sources_h1`: modification time only;
  - `research/ledger/labels_h1`: modification time, and file names seen in a diff stat (`plan.json`, `known_sources.csv`, `specs/*.json`); contents never opened.
- **Read, outcome-free:**
  - `HL_OUTCOME_LOCATIONS.md` (names and categories; see 14d);
  - `kit_v3/PROTOCOL.md`;
  - `MOTOR_MAP_REVIEW.md`, whose own sightings note a haltere-muscle activation summary (not a hemilineage).
- **Other:**
  - P7 results (DNb08 and random groups only);
  - the test suite includes run 2 tests that read exam 1's descending-neuron labels. Nothing was printed.
