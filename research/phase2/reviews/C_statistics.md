# Review C — statistics: pre-registration, paired comparisons, multiplicity, adversarial scoring, real-network sweeps, calibration, report numbers

Reviewer: independent agent (review C of `research/phase2/REVIEW_PLAN.md`), 2026-09-24. Post-lock (lock commit `959d689`, tag
`brainir-v1-preblind`), main repository, read-only. The only file written is this review. Re-analyses ran locally, one process at a
time and each under a minute, from throw-away scripts in the session scratchpad; they are not committed, and their key outputs are quoted
below. Hidden-evaluation results were used only as already logged. No oracle file was opened, and no neuron identifier appears here.

State reviewed: `HEAD` = `4b3ff3e` (report with the v1.2 sweeps, the hidden sweep scoring and the v1.2 transfer). The review was
finalised at the orchestrator's request without waiting for the blind evaluation (`research/phase2/blind_eval/attempt_01`). At that
point all three predictions were frozen (`FROZEN.json`, 18:28), and the evaluator's result had not yet been logged. The orchestrator will
report the blind result next to the sweep distribution. Post-review changes (the regenerated `abl_v1_summary.*`, and new files
`cmp_sel_v12_*` and `cmp_conf_adv_*`) were not re-checked.

## Verdict in one paragraph

The pre-registered machinery was followed.
- Every rule predates the data it governs.
- The confirmation-role suites were each used by exactly one run, after the freeze and before the lock.
- The paired designs are exactly paired, and failures are handled correctly wherever runs failed (none did in the confirmation).
- I reproduce the main confirmation comparison and the decision rule from the `.json.gz` records. The decision to lock v1.2 is sound,
  and it survives instance-level tests and multiplicity adjustment.
- The report's numbers match the result files, apart from the small items listed in finding C14 and in the table of checked claims.

The framing is not yet honest enough:
1. The locked v1.2 is compared only with the weakest comparator. Its comparisons with the strongest candidates are missing, and there
   it costs more calls and loses one success metric. v1.0 results appear under the name "BrainIR v1" (C1).
2. The adversarial confirmation tests fresh seeds of traps that v1.2 was built and tested against (C2).
3. The adversarial truth definition was changed after the method's developer saw its own runs scored wrong. The change was fair, but it
   is undisclosed in the report, and the 90 % rule's margin depends on it (C3).
4. Most of the synthetic success gap over `greedy_reference` comes from its frozen k = 3 (C4).
5. "Identity claims reliable" rests on 6 hard pairs (C5).

**Severity counts: 0 blockers, 5 major, 10 minor.**

## Files read (and not read)

- **Specification and protocol.**
  - `CLAUDE.md`; `goal3.md` §§20–22, 27–31, 48, 50–54 (lines 941–1021, 1133–1322, 1750–1999).
  - `research/phase2/SELECTION_PROTOCOL.md`, with its git history: `263bc74`, `60ec1ab`, `713f23b`, `6a8cbeb`.
  - `research/phase2/REVIEW_PLAN.md`; `research/phase2/METHOD_LOCK.json`; `research/LOG.md` §10 (lines 282–436).
  - `research/phase2/HIDDEN_EVAL_LOG.md`; `research/phase2/hidden_eval_ledger.json`.
- **Report.** `PHASE2_REPORT.md` at `959d689` and at `4b3ff3e` (and the diff between them).
- **Reviews.**
  - Read in full: `AG_resolution.md`, `B_resolution.md`.
  - Read in part: the B2 section of `B_optimisation.md`.
  - Only the severity tables and the lines the report quotes: `A_causal.md`, `G_adversarial.md`, `E_cross_connectome.md`,
    `F_computational.md`.
- **Method document.** `research/phase2/BRAINIR_V1_METHOD.md`: grepped for adversarial / calibration; lines 920–959 read.
- **Scripts.**
  - Read in full: `compare_tournament_methods.py`, `compare_pair_arms.py`, `compare_reliability.py`, `rescore_adversarial.py`,
    `budget_curve.py`.
  - Read in part: `ablations.py` (lines 1–60), `reliability_sweep.py` (lines 50–60 and 140–160, plus grep), `blind_eval.py`
    (lines 1–60).
- **Library.**
  - `src/brainir/discovery/tournament.py` (in full), `adversarial.py` (lines 1–140 and 640–1020), `reliability.py` (in full),
    `transfer.py` (lines 87–171).
  - `src/brainir/methods/greedy_reference.py` (lines 1–60).
- **Results, markdown and summaries** (`research/phase2/tournament/`):
  - confirmation: `cmp_conf_greedy_reference`, `conf_mech_b1000`, `conf_adv`, `conf_v12_pairs_v1f`, `conf_v12_pairs_v2f`;
  - selection comparisons: `cmp_sel_v1_*`, `cmp_sel_v11_*`;
  - pairs: `cmp_arms_pairs_*`, `arms_pairs_v1h`, `arms_pairs_v2h`, `sel_pairs_b1000`;
  - ablations: `abl_v1_summary`, `abl_v12_adv_default`;
  - anti-gaming: `ag_v1_summary`, `ag_candidates_summary`;
  - curves: `sel_curve_*_curve`;
  - summary JSONs: `sel_mech_b1000_part{1,2,3}`, `sel_v1/v11/v12_b1000`, `sel_curve_v1_b{50,100}`, `sel_curve_ext_b{50,100}`.
- **Records re-analysed** (`.json.gz`):
  - confirmation: `conf_mech_b1000`, `conf_adv`, `conf_v12_pairs_v1f`, `conf_v12_pairs_v2f`;
  - held-out pairs: `sel_v1_pairs_v{1,2}h`, `sel_v12_pairs_v{1,2}h`;
  - held-out adversarial: `adv_h_v10`, `adv_h_v11`, `adv_h_v12`, `adv_h_comparators`, and their `_rescored` versions;
  - held-out mechanisms: `sel_v1_b1000`, `sel_v12_b1000`, `sel_mech_b1000_part{1,3}`;
  - ablations: `abl_v1_*` (all 15);
  - curves and anti-gaming: `sel_curve_v1_*`, `ag_v1_*`.
- **Real networks.**
  - Every file in `research/phase2/reliability/` (`greedy_frozen_*`, `v12_*`, `compare_v12_vs_greedy_*`, including `*_hidden`).
  - `research/phase2/transfer/xfer_*.md`, plus the headers of `xfer_*.json`.
- **Provenance.** `benchmarks/dng100/manifests/experiments/index.jsonl` and the per-run records (suite, launch commit and timestamps only).
- **Synthetic truth.** `data/synthetic/adversarial_final/truth/*.json`: the `adversarial` entries only, to re-score under the first
  definition. `SALT.txt` and `BUILD_REPORT.json` were not opened.
- **Clean room.** `C:\Dev\BrainIR_p2clean`: directory listings and mtimes only.
- **Blind run.** `research/phase2/blind_eval/attempt_01/runs/prediction_*.json`: each core was compared with the sweep; no
  identifier is reproduced here. The evaluator's output was not read.
- **Not opened:** `benchmarks/dng100_walking_cpg/`, `benchmarks/dng100/oracle/`, `research/literature/`, `research/audit/`,
  `goal1.md`, `goal2.md`, `PHASE1_REPORT.md`, `benchmarks/dng100/baselines/results/`, `~/.modal.toml`.

## Answers to the eight questions

### Q1. Pre-registration and timing

Git commit times and registry completion times are given in local time (−07:00).

| event | when | evidence |
|---|---|---|
| protocol §§1–6 | 09-23 13:15 | `263bc74` |
| first selection-role run (`sel_curve_part1_b250`) completes | 09-23 15:50 | registry 22:50Z |
| amendment §7 (harder pairs, identity rule, joint vs controls) | 09-23 19:17 | `60ec1ab` |
| first run on `pairs_v2_*` (`arms_pairs_v2h`, `sel_v1_pairs_v2h`) | 09-23 22:20 | registry 05:20Z |
| §7.3 correction (Brier rule → calibration in the large), after the selection-role pairs showed precision 1.00 | 09-23 23:15 | `713f23b`, disclosed in the protocol |
| amendment §8 (success_intact, adversarial rule) | 09-24 00:23 | `6a8cbeb` |
| adversarial generator and scorer; `adversarial_heldout` and `adversarial_final` built | 09-24 01:02 | `1b0d240` |
| v1.0 and comparators on `adversarial_heldout` | 09-24 01:38–01:41 | `adv_h_v10`, `adv_h_comparators` |
| v1.1 committed | 09-24 09:52:57 | `e22db1f` |
| adversarial truth definition changed; held-out runs re-scored | 09-24 09:56:31 | `d6dc789` (C3) |
| v1.2 frozen | 09-24 16:27:28 | `c3362c0` |
| v1.2 on the selection-role suites | 16:33–16:39 | registry |
| confirmation runs, all launched from `fbf967d` | 16:40–17:36 | registry: `conf_v12_pairs_v1f`, `conf_v12_pairs_v2f`, `conf_mech_b1000`, `conf_adv` |
| `METHOD_LOCK.json` and tag | 17:37:52 | `959d689` |
| hidden scoring of the six sweeps | 17:39–17:45 | `HIDDEN_EVAL_LOG.md` (00:39–00:44Z) |

- **Amendments.** Each was written before the data it governs.
- **Rule changes after selection-role data.** There were two: the §7.3 correction and the adversarial truth definition. Both were made
  before any confirmation data existed, and both apply to every method. The first is disclosed in the protocol. The second is not
  disclosed in the report (C3).
- **Rule changes after confirmation data.** None:
  - the analysis code was last changed before the confirmation: `compare_tournament_methods.py` at `6a8cbeb`, `compare_pair_arms.py` at
    `60ec1ab`, `compare_reliability.py` at `a5204d9`, `adversarial.py` and `tournament.py` at `d6dc789`;
  - `git diff --stat c3362c0 959d689 -- src scripts` is empty.
- **Use of the confirmation suites.** Each confirmation-role suite appears in exactly one registry run, after the freeze and before the
  lock. The selection-role suites were re-used for v1.0, v1.1, v1.2 and the ablations, as the protocol allows. The composer also
  received aggregates of `adversarial_heldout` (BRAINIR_V1_METHOD.md:8–9), so that suite is design data for v1.1/v1.2, not held-out
  evidence. AG_resolution.md labels it "selection role", correctly.

### Q2. Paired comparisons

**Unit of resampling.**
- Instances, in `compare_tournament_methods.py:124–133` and `compare_pair_arms.py:61–73`. This is right: the 6 runs of an instance
  (2 orders × 3 seeds) are correlated.
- Clustering the adversarial comparison by trap variant (22 clusters) or by trap (6) leaves the conclusions unchanged: v1.2 − greedy_plus
  correct +0.26, CI [+0.14, +0.40] by variant and [+0.10, +0.55] by trap.
- Two scripts resample runs instead:
  - `ablations.py:41–49` (C7);
  - `compare_reliability.py:94, 100–104`, whose runs share node orders (C8).

**Pairing.**
- `conf_mech_b1000`: 342 common (instance, order, seed) keys, 0 unmatched, 0 pairs with a different network hash, identical score
  seeds (5000–5003), 0 failed runs, 0 budget-exhausted runs, 0 runs over budget.
- Sweeps: order k is `make_permuted_bundle(seed = 1000 + k)` for both methods (`reliability_sweep.py:52–57`), paired on (order, seed).
- Pair arms: paired on (suite, instance, seed).

**Failures.**
- The rule "unsuccessful, full budget, robust pass 0" is applied in `compare_tournament_methods.py:55–70`, `compare_pair_arms.py:36–39`
  and `tournament.summarize` (lines 406–430). No confirmation run failed.
- `compare_reliability.py:30` and `ablations.py:42–43` drop failed runs instead (C7, C8). No run failed there either.

**Re-derivation of the main confirmation comparison** from `conf_mech_b1000.json.gz`: my own code, instance bootstrap with 20,000
resamples and a different RNG; instance-level exact sign tests.

| metric | v1.2 | greedy_reference | difference | my 95 % CI | report / cmp file CI | instances +/− | sign p |
|---|---|---|---|---|---|---|---|
| structural success | 1.000 | 0.754 | +0.246 | [+0.140, +0.360] | [+0.140, +0.360] | 15 / 0 | 6e−5 |
| success_intact | 1.000 | 0.576 | +0.424 | [+0.301, +0.550] | [+0.295, +0.553] | 26 / 0 | 3e−8 |
| causal functional (unscored = 0) | 1.000 | 0.155 | +0.845 | [+0.754, +0.924] | [+0.754, +0.924] | 52 / 0 | 4e−16 |
| planted success | 1.000 | 0.623 | +0.377 | [+0.254, +0.509] | [+0.254, +0.500] | 22 / 0 | 5e−7 |
| essential recall | 1.000 | 0.728 | +0.272 | [+0.172, +0.379] | [+0.172, +0.378] | 18 / 0 | 8e−6 |
| identity Jaccard | 0.958 | 0.803 | +0.155 | [+0.099, +0.215] | [+0.096, +0.217] | 25 / 2 | 6e−6 |
| identical cores | 0.930 | 0.526 | +0.404 | [+0.281, +0.526] | [+0.281, +0.526] | 23 / 0 | 2e−7 |
| calls saved (mean) | 150 | 290 | +140 | [+84, +200] | [+85, +202] | 41 / 16 | 1e−3 |
| simulated seconds saved | 157 | 304 | +147 | [+86, +214] | — | 41 / 16 | 1e−3 |
| CPU seconds saved | 28.5 | 75.6 | +47 | [+13, +89] | — | 42 / 15 | 5e−4 |
| keep-only pass, sd × 2 | 0.954 | 0.733 | +0.221 | [+0.118, +0.334] | [+0.114, +0.332] | 18 / 6 | 0.023 |
| keep-only pass, weight noise | 0.851 | 0.670 | +0.181 | [+0.077, +0.294] | [+0.073, +0.292] | 24 / 18 | 0.44 |

- Every point estimate matches the cmp file and the report exactly. The CIs agree within bootstrap Monte-Carlo error.
- Decision rule (a) holds on both structural success and success_intact, also with 99 % CIs.
- Decision rule (b) holds on all three dimensions by the pre-registered bootstrap criterion (see C10 for multiplicity).
- On the synthetic suites the efficiency advantage over greedy_reference also holds in simulated seconds and CPU.

### Q3. Multiple comparisons and selective reporting

- **How many comparisons.** The result files carry about 250 CI-bearing paired comparisons:
  - selection: 4 v1.0 × 11–13 metrics and 3 v1.1 × 13;
  - confirmation: 14;
  - pair arms: 32;
  - ablations: 70;
  - anti-gaming: 30;
  - real-network sweeps: 18 + 3.

  At the 95 % level, about 12 would exclude 0 by chance under the null.
- **The headline claims are robust:**
  - the confirmation rule survives Holm adjustment and Bonferroni-widened CIs (C10);
  - v1.2 vs greedy_plus on `adversarial_final`: correct +0.26 (instance sign test 38/0, p = 7e−12).
- **Marginal claims quoted in the report:**
  - v1.0 vs group_probe, causal functional +0.047 [+0.006, +0.102]: only 4 instances differ (sign p = 0.13);
  - v1.0 vs group_probe, "36 fewer [9, 71]" calls: sign p = 0.06;
  - v1.0 vs group_probe, identical cores +0.088: CI lower bound exactly 0.000 (`cmp_sel_v1_group_probe.json`), yet it is printed
    without "(n.s.)";
  - the Jaccard effects of the ablations (C7);
  - male-cns consistency in the sweeps (C8).
- **Null and negative results.**
  - Reported with equal weight: joint discovery's null result on hard pairs, the failure to raise success, the real-network compute
    cost, and the non-significant per-network hidden differences. All are given in tables and plain language.
  - Not reported (C1):
    - on the held-out mechanisms, v1.2 needs more calls than greedy_plus and cem_search, and has no significant advantage over
      group_probe; the orchestrator's own `cmp_sel_v11_group_probe.md` prints "rule FAILS";
    - on `adversarial_final`, v1.2's causal functional success is below greedy_plus's, and it uses more calls.

### Q4. Adversarial evaluation

- **Definition of "correct"** (`adversarial.py:930–932`).
  - It requires an exact match with an acceptable core; lenient variants are recorded. This is sound and strict.
  - On degenerate traps, the answer must flag degeneracy. No method raised that flag on a non-degenerate run (0/360 each), so the flag
    was not gamed.
  - Two format effects favour v1.2 in comparisons (C2):
    - the comparators cannot flag degeneracy, so the 36 distributed_drive runs are wrong for them by construction;
    - greedy_reference has 0/1 probabilities, so every wrong answer it gives is "confident-wrong".
- **Re-scoring after the definition change.** It was fair: the same definition was applied to every method, all held-out files were
  re-scored, and all final runs were scored once under it. It was undisclosed in the report, and it is consequential (C3).
- **"≥ 90 % of confident runs correct."**
  - As implemented, the quantity is P(core exactly an acceptable core | every core member has P ≥ 0.85).
  - On `adversarial_final` it is 322/325 = 0.991, with an instance-cluster 95 % CI of [0.979, 1.000] and a variant-cluster CI of
    [0.975, 1.000]. So the METHOD_LOCK note "99.1 %" is right, and the rule passes with statistical margin.
  - It is a run-level statement that ignores the 18 % of runs in which v1.2 was not confident. Coverage (82 % vs 92 % for greedy_plus)
    must be reported next to it, because the rule rewards abstention.
  - Under the first truth definition the value is 0.935 [0.868, 0.991] (C3).

### Q5. Reliability sweeps on the real networks

- **Confound.** The confound of node order with the parameter draw is stated (PHASE2_REPORT.md:228, 387; `tournament.py:463–466`).
- **Wall time and simulated seconds.** Both are reported next to the calls (lines 222–234): 2 s vs 1 s per call, simulated time equal
  or higher, wall time 3.0–3.7×. The CPU time of v1.2 (975 / 786 / 942 s per run) is recorded. The baseline's CPU time is not; only
  its wall time is.
- **Is 8 × 3 enough?**
  - Enough to show consistency and function on the two MANC networks.
  - Not enough to resolve the hidden-success difference on any single network (exact p = 0.13–0.50).
  - Not enough to separate the two methods' consistency on MaleCNS.
  - No power check was done (goal3 §21).
- **Seeds are not replicates.** Within an order, v1.2's 3 seeds agree in 3/8, 8/8 and 5/8 orders, and greedy's in 1/8, 6/8 and 0/8.
- **What the CIs ignore.** The run-level CIs ignore clustering by order, and the Jaccard bootstrap includes self-pairs. Corrected
  intervals are in C8.
- **Role consistency** (goal3 §21) is not measured on the real networks.

### Q6. Calibration

- **Targets.**
  - `brier_inclusion` and `brier_contested` are circular: the target is the truth set that overlaps the method's own core best
    (`tournament.py:56–60, 116`).
  - `brier_contested_any_alternative` (`:117`) and the adversarial scorer's membership targets (`adversarial.py:934–942`) are not
    circular.
- **The report's only calibration interpretation uses the circular metric** (C6).
- **Bins.** In the adversarial bins, the middle rests on 3–18 instances. The identity-claim "calibration" is untestable, because every
  claim was correct (C5).

### Q7. Numerical claims in PHASE2_REPORT.md

I checked every number in §§6, 8, 9, 10, 11, 12 and 13 against the files (table below). All reproduce, except the items in C14 and
C11: denominators, one missing "(n.s.)", "every candidate", ambiguous or stale text. No reported number is wrong beyond rounding.

### Q8. Hidden comparisons of v1.2 against the frozen baseline

**Sweeps.**
- The sweeps are paired on (order, seed), with exact per-network McNemar tests. They are correctly labelled: no network is significant
  alone, and the pooled test is marked post hoc.
- My cluster-level analysis supports the pooled result: 12 of 13 non-tied (network, order) clusters favour v1.2, sign test p = 0.0034.
- The two MANC networks come from one reconstruction, however (C9).

**Blind run** (C15). The evaluation had not yet been logged when this review was finalised. On every network, the blind prediction's core is
identical to the core of the sweep run (order 0, seed 0):

| network | sweep runs returning that core | modal core |
|---|---|---|
| MANC v1.2.1 | 4 of 24 | 18 of 24 (a different core) |
| MANC v1.2.3 | 20 of 24 | this core |
| MaleCNS | 24 of 24 | this core |

The blind run is therefore one draw of an already hidden-scored distribution. On MANC v1.2.1 that draw is not the modal one, and it
must be reported that way.

## Findings

### C1 — major — The locked v1.2 is compared only with the weakest comparator; where it loses to the strong candidates it is not reported, and v1.0 results are presented as "BrainIR v1"

**Evidence**

**The report's "BrainIR v1" numbers are v1.0 numbers.**
- The comparison table of §6 (PHASE2_REPORT.md:112–124) and three §11 sections (lines 317, 320 and 332: anti-gaming, budget curve,
  ablations) come from records whose `version` field is `"1.0"`: `sel_v1_b1000`, `ag_v1_*`, `sel_curve_v1_*`, `abl_v1_*`.
- The locked method is 1.2.0, and it differs materially on the same held-out suite:

  | version | mean calls | mean wall per run |
  |---|---|---|
  | v1.0 | 106 | 13.3 s |
  | v1.2 | 146 | 26.8 s |

**Locked method on the held-out mechanisms.** Paired, instance bootstrap, my re-derivation from `sel_v12_b1000.json.gz` and
`sel_mech_b1000_part{1,3}.json.gz`; `cmp_sel_v11_*.md` gives the same for v1.1.
- vs greedy_plus:
  - equal success;
  - v1.2 uses 37.7 more calls [30.3, 45.3], and more on 55 of 57 instances (sign p = 2e−14);
  - identical cores +0.19 [+0.11, +0.30].
- vs cem_search: v1.2 uses 31.6 more calls [18.7, 43.0], and more on 53 of 57 instances.
- vs group_probe: no (b) dimension has a CI above 0.
  - Calls: −4.3 [−29.1, +25.5]; v1.2 is costlier on 39 of 57 instances (sign p = 0.0075).
  - Identical cores: +0.088 [0.000, +0.175].
  - Jaccard: +0.021 [−0.014, +0.057].
  - `cmp_sel_v11_group_probe.md` prints "rule FAILS".

**Locked method on `adversarial_final`** (confirmation role, `conf_adv.json.gz`), vs greedy_plus:
- far more often correct: +0.260 [+0.187, +0.341];
- more consistent: Jaccard +0.169 [+0.125, +0.217];
- but it needs 30.7 more calls [17.2, 43.5], more on 57 of 66 instances (CPU 48 vs 31 s per run);
- and its causal functional success is lower: 0.833 vs 0.874 (unscored cores counted as 0), a difference of −0.040
  [−0.076, −0.010]. The pre-registered functional success is also lower: 0.46 vs 0.56 (`conf_adv.md`).
- Both functional gaps come from distributed_drive (0.03 vs 0.25) and subset_of_draws (0.14 vs 0.39). There the trap's correct answer
  (a flagged degenerate set, or the union of copies) is by design not 1-minimal.

**Protocol.** Protocol §5 says: "Every other metric is reported whichever way it goes." Goal3 §48 asks for the same.

**Fix**
- Label every v1.0 number in §6 and §11 as v1.0.
- Add to §8 a table of the locked v1.2 against greedy_plus, cem_search and group_probe on `mechanisms_v1_heldout` (success, identity,
  calls, simulated seconds, CPU, wall), and against greedy_plus and group_probe on `adversarial_final`. Include every metric,
  functional success too, and explain the trap design.
- State plainly that v1.2 buys reliability and adversarial correctness with more calls and CPU than greedy_plus.
- Re-run the budget curve and the anti-gaming checks for v1.2, or say that they were not re-run.

### C2 — major — The adversarial confirmation is in-distribution for v1.2 and partly driven by output format; it cannot support a general robustness claim

**Evidence**

**The clean room holds the whole trap design.**
- It contains the generator, its `VARIANTS` and `PARAM_RANGES`, and the scorer (`C:\Dev\BrainIR_p2clean\src\brainir\discovery\adversarial.py`,
  mtime 2026-09-24 09:53).
- It also holds the design note (`...\research\phase2\reviews\G_adversarial_suite.md`).

**The composer built and tuned v1.x on that generator.**
- The composer "developed [v1.1] on adversarial instances I built myself with the third-party generator" (BRAINIR_V1_METHOD.md:8–10).
- It iterated versions v11a–v11e on an 88-run adversarial development set (lines 872–880).
- It added property tests for the latent-backup, masked-gate and distributed-drive traps (AG_resolution.md:33).

**`adversarial_final` differs from that development data only in its secret seeds.** None of the comparators was designed against these
traps.

**Two output-format effects.**
- **Degeneracy flag.** distributed_drive (36 of 396 runs) can only be answered correctly by flagging degeneracy, and greedy_plus,
  group_probe and greedy_reference have no such output (0/36 each). Without distributed_drive, the correct rates are v1.2 0.978,
  greedy_plus 0.792 and group_probe 0.742, against 0.980 / 0.720 / 0.674 with it.
- **0/1 probabilities.** greedy_reference is "confident" in 396 of 396 runs because its probabilities are 0/1. Its confident-wrong rate
  of 0.91 therefore measures the absence of an uncertainty model.

**Fix**
- State in §8 that `adversarial_final` tests fresh draws of six trap designs that v1.2 was built and tuned against, and that
  the comparators were not.
- Give the correct rates with and without distributed_drive, and give the confident-run coverage per method (v1.2 0.82, greedy_plus 0.92,
  group_probe 0.90, greedy_reference 1.00).
- If a robustness claim beyond the known traps is wanted, a post-lock third party should build a trap family that never entered the clean
  room. Such evidence can only invalidate, not tune.

### C3 — major — The adversarial truth definition changed after the method's developer saw its runs scored wrong; the change was fair and pre-confirmation, but it is undisclosed in the report, and the 90 % rule's margin depends on it

**Evidence**

**Timeline.**
- v1.0 and the comparators were scored at 01:38–01:41; v1.1 was committed at 09:52:57.
- At 09:56:31 (`d6dc789`) the definition changed so that acceptable cores contain every measured-essential node. The commit message
  says the third party "resolved an inconsistency the composer reported". G_adversarial_suite.md §3a says "Decided 2026-09-24 on the
  coordinator's question".
- Under the first definition, v1.1 was confident-wrong on all 18 held-out `identical_decoy/nfc_band` runs. Its P(correct | confident)
  was 0.926; after re-scoring, 0.979 (`adv_h_v11.json.gz` vs `adv_h_v11_rescored.json.gz`).

**Fairness holds.**
- Every held-out file was re-scored under one definition. I compared each record before and after; every flip is on
  `identical_decoy/nfc_band`:

  | method | wrong → correct | correct → wrong | net |
  |---|---|---|---|
  | v1.1 | 18 | 0 | +18 |
  | group_probe | 18 | 0 | +18 |
  | v1.0 | 14 | 1 | +13 |
  | greedy_plus | 13 | 1 | +12 |
  | greedy_reference | 0 | 0 | 0 |

- All four methods were scored once, under the same definition, on `adversarial_final`.
- The rule is principled: it aligns the trap scorer with §8.2's success_intact.

**Sensitivity.** I re-scored `conf_adv` under the first definition, reading the designed acceptable cores from
`data/synthetic/adversarial_final/truth`, where `definition` is absent for all 1,584 runs.

| method | correct, first → current | P(correct \| confident), first → current |
|---|---|---|
| v1.2 | 0.934 → 0.980 | 0.935 [0.868, 0.991] → 0.991 [0.979, 1.000] |
| greedy_plus | 0.682 → 0.720 | 0.738 → 0.779 |
| group_probe | 0.629 → 0.674 | 0.679 → 0.730 |

The ≥ 90 % rule still passes on the point estimate, but under the first definition its 95 % lower bound (one-sided 0.879) falls below
0.9. The comparative conclusions do not change.

**Residue.** `rescore_adversarial.py:29` keeps `calibration_items` and `brier_contested` from the original scoring. The re-scored
held-out runs therefore keep first-definition calibration targets for the moved nodes, while v1.1 and v1.2 were scored with the new ones.

**Fix**
- In §8's adversarial paragraph, disclose the change, its trigger, and its timing relative to the data.
- Give every method's numbers under both definitions (the table above).
- Recompute the calibration fields of the re-scored held-out files, or state the residue.

### C4 — major — On the synthetic confirmation, greedy_reference's frozen k = 3 produces most of the success gap; the report reads as a general win over "greedy"

**Evidence**
- greedy_reference stops at k = 3 survivors (`greedy_reference.py:13, 54`; PHASE2_REPORT.md:65).
- In `conf_mech_b1000.json.gz`, 12 of 57 instances (72 runs) have a smallest sufficient set larger than 3:
  - there, greedy_reference's structural success is 0.33 (median core 13.5), against v1.2's 1.00;
  - these runs carry 57 % of the +0.246 structural-success gap.
- On the other 45 instances, greedy_reference returns 3 neurons when fewer suffice. Its causal functional success there is 0.107, so
  most of the +0.845 causal-functional gap is non-minimality forced by k.
- On `delayed_inhibitory_oscillator` (a 5-node mechanism, 42 runs), greedy_reference scores 0.00 by construction (`conf_mech_b1000.md`).
- The mechanism suites are at ceiling for every non-reference method: all five candidates and v1.0–v1.2 have structural success 1.00 on
  `mechanisms_v1_heldout`. Only greedy_reference could fall short there, so rule (a) against it was close to certain to pass.
- The decision rule was pre-registered against greedy_reference, so the lock is unaffected. The claim "beats greedy" (goal3 §50.30) is
  what needs qualifying.

**Fix**
- In §8, state that greedy_reference keeps the frozen k = 3.
- Give the gap split by smallest-sufficient-set size (≤ 3 vs > 3).
- Place the k-free greedy (greedy_plus) comparisons of C1 next to it.

### C5 — major — "Identity claims reliable" rests on 28 claims from 6 of 27 hard pairs; the rule passes on point estimates only, and its original version would have failed

**Evidence**

**Where the claims come from.** In `conf_v12_pairs_v2f.json.gz`, the 28 claims come from 18 runs on 6 distinct pairs, with 12, 4, 3, 3,
3 and 3 claims per pair. The 8 null pairs (24 runs) received 0 claims.

**How much the evidence supports.**
- A naive Clopper–Pearson 95 % lower bound on precision is 0.877. But the pair is the unit, and with 6 all-correct pairs the bound is
  0.025^(1/6) = 0.54, below the 0.8 threshold.
- 0 claims on 8 null pairs bounds the per-pair claim rate on nulls at ≤ 0.31 (95 %).
- On `pairs_v1_final`, the 94 claims come from 16 pairs (pair-level bound 0.79).

**The calibration criterion is weak, and it was changed.**
- "Calibration in the large" (|0.973 − 1.00| ≤ 0.10) is met automatically when every claim is correct.
- The first §7.3 rule was replaced after the selection-role pairs showed precision 1.00 (SELECTION_PROTOCOL.md:108–112, `713f23b`;
  disclosed there, not in the report). It required a Brier score below the constant predictor at the observed precision, and it would
  have failed mechanically on `pairs_v2_final`.
- The identity calibration (a, b, c) was fitted on the composer's development pairs, drawn from the same generator
  (BRAINIR_V1_METHOD.md:927–932).

**What the report says.** PHASE2_REPORT.md:198–203: "The claims are therefore called reliable."

**Fix.** Keep the pre-registered verdict, but add:
- 28 claims from 6 pairs, one of which gave 12;
- a pair-level 95 % lower bound on precision of 0.54;
- coverage of 18 of 81 runs, with core recall 0.24;
- that the rule is a point-estimate rule;
- that the first version of the rule was degenerate at precision 1 and would have failed.

Do not call the claims "reliable" without this qualification.

### C6 — minor — The only calibration interpretation in the report uses the circular Brier score; the pending reliability diagram needs populated bins and cluster-aware uncertainty

**Evidence**

**The report's calibration sentence.** PHASE2_REPORT.md:346: "Brier 0.004 → 0.000: on these instances v1's probabilities are
under-confident."
- It uses `brier_inclusion`. Its target is the truth set that overlaps the method's own core best, and it is averaged over every
  assessed candidate (`tournament.py:56–60`).
- The report's own §13 (lines 422–423) calls that target circular.
- A 0/1 model scores 0 whenever its core matches, so "under-confident" does not follow.

**Which Brier scores are circular.**
- `brier_contested` also uses the best-matching target (`tournament.py:116`).
- `brier_contested_any_alternative` (`:117`) and the adversarial targets are not circular.
- For v1.2 on `conf_mech` the circular and non-circular values are 0.019 and 0.105.

**Bin population.** v1.2's reliability bins on `adversarial_final` (items / distinct instances):

| bin | items / instances |
|---|---|
| [0, 0.05) | 992 / 57 |
| [0.05, 0.30) | 4 / 4 |
| [0.30, 0.60) | 37 / 3 |
| [0.60, 0.85) | 406 / 18 |
| [0.85, 1] | 1,183 / 59 |

The middle bins rest on 3–18 instances, and items repeat across the 6 runs of each instance.

**Fix**
- Remove the "under-confident" sentence, or recompute it with a non-circular target.
- Report calibration as reliability tables with item and instance counts per bin and instance-cluster CIs.
- Lead with the non-circular Brier score.

### C7 — minor — Ablations resample runs, not instances; two quoted Jaccard effects are not significant

**Evidence**
- `ablations.py:41–49` bootstraps (instance, order, seed) triples and drops unscored runs (none failed).
- With the instance as the unit (54 instances):

  | component switched off | effect | report |
  |---|---|---|
  | group testing | +104.6 calls [+55.3, +160.9] | [+69, +143] |
  | minimality cleanup | −0.065 [−0.120, −0.019] (still excludes 0) | |
  | canonical order | identity Jaccard −0.025 [−0.093, +0.037]; 4 instances change, 1 up and 3 down | 0.944 → 0.920 (line 338) |
  | adaptive replication | −0.019 [−0.056, 0.000]; one instance | 0.944 → 0.926 (line 340) |

- The report quotes the last two without uncertainty, and LOG §10 (line 414) says "the canonical order raises consistency".

**Fix**
- Resample instances in `ablations.py` and count failed runs as failures.
- Quote the Jaccard effects with CIs, and call them not significant.

### C8 — minor — Real-network sweep CIs ignore the node-order cluster and count self-pairs; one "every network" claim overstates

**Evidence**

**How the CIs are computed.** `compare_reliability.py:94, 100–104` resamples the 24 runs independently, although the runs share
8 orders. Duplicated runs enter the pairwise Jaccard as self-pairs with Jaccard 1.

**Corrected intervals.** With orders as clusters and self-pairs excluded, the Jaccard differences are:

| network | Jaccard difference [95 % CI] |
|---|---|
| manc_v1.2.1 | +0.170 [+0.096, +0.274] |
| male-cns_v1.0 | +0.128 [0.000, +0.288] |
| manc_v1.2.3 | +0.198 [+0.031, +0.392] |

The conclusions stand, but "On every real network v1.2 is more consistent" (line 228) holds on two of three networks.

**Other gaps.**
- `compare_reliability.py:30` drops failed runs.
- The 8 × 3 design had no power check (Q5).

**Fix**
- Cluster by order, exclude self-pairs and count failures.
- Write "more consistent on both MANC networks; on MaleCNS 1.00 vs 0.87 with a CI reaching 0".
- State that the per-network sweeps are underpowered for the success comparison.

### C9 — minor — The pooled hidden test is correctly labelled post hoc; add the cluster test and the shared-reconstruction caveat

**Evidence**

**The pooled test and my cluster test.**
- 13 vs 2 discordant runs give an exact McNemar p of 0.0074, which I reproduce.
- With (network, order) as the cluster, 12 clusters favour v1.2, 1 favours greedy and 11 tie. The sign test gives p = 0.0034, and a
  cluster sign-flip permutation gives p = 0.0031. Clustering by order therefore does not weaken the result (line 368 expects that it
  "overstates the evidence somewhat"). The dependence that matters is between the networks (next point).

**The two MANC networks are one reconstruction.** `manc_v1.2.1` and `manc_v1.2.3` come from one v1.2 synapse table. The pooled evidence
therefore comes from two independent datasets, and 11 of the 13 v1.2-only successes are on MANC.

**"Recovers the published circuit" overstates the criterion.** Line 365 says this, but the criterion is E-core recall 1 with the
inhibitory slot filled. v1.2's mean precision is 0.958 and 0.969 on the two MANC networks.

**Fix**
- Add the cluster-level test and say "two independent reconstructions".
- Write "meets the frozen structural criterion" instead of "recovers the published circuit".

### C10 — minor — The decision rule has no non-inferiority margin, an unadjusted OR over five metrics, and mean instead of the pre-registered median calls; none of this changes the verdict

**Evidence**

**The rule as implemented** (`compare_tournament_methods.py:148–158`).
- (a) passes whenever the CI's upper end is ≥ 0, with no margin and no power requirement.
- (b) is an OR over identity Jaccard, identical cores, calls, sd × 2 and weight noise.

**Multiplicity.** Using instance-level sign tests with Holm adjustment over the five:

| metric | p | survives Holm? |
|---|---|---|
| identical cores | 2e−7 | yes |
| Jaccard | 6e−6 | yes |
| calls | 1e−3 | yes |
| sd × 2 | 0.023 | yes |
| weight noise | 0.44 (24 vs 18 instances) | no |

With Bonferroni-widened 99 % bootstrap CIs, all five exclude 0. On 18 instances, greedy_reference's larger cores are the more robust.

**Median vs mean.** The protocol's efficiency metric is "median calls" (§3.3), but the script uses the mean. The median also favours
v1.2 (115 vs 236).

**Fix**
- Nothing is needed for the lock.
- In §8, add that the robustness advantage is significant by the pre-registered bootstrap CI but not by an instance-level sign test.
- For future protocols, pre-register a margin and a multiplicity rule.

### C11 — minor — Summary tables and paired tables use different denominators for causal functional success

**Evidence**
- `tournament.summarize` (lines 421, 430) excludes runs that lack `functional_success_causal`: cores of more than 40 neurons, which is
  30 greedy_reference runs in each of `conf_mech` and the held-out suite.
- `compare_tournament_methods.py:43` counts the same runs as failures.
- The same runs therefore appear as 0.215 (PHASE2_REPORT.md:80) and 0.20 (line 118), and as 0.17 (`conf_mech_b1000.md`) and 0.155
  (line 177).

**Fix.** Count unscored cores as failures in `summarize`, or footnote the difference.

### C12 — minor — Anti-gaming checks are at ceiling and underpowered, cover v1.0 only, and omit evo_pareto

**Evidence**
- For v1.0 and the four leading candidates, structural success is 1.00 before and after every transform (`ag_v1_summary.md`,
  `ag_candidates_summary.md`), on 47 instances × 1 order × seed 0.
- A 5 % loss rate would still give 0 lost runs with probability 0.95^47 = 0.09.
- The invariance of the returned core itself is not checked.
- "every candidate" (line 306) covers 5 of the 6 methods: evo_pareto is missing.
- The records are v1.0.

**Fix**
- Re-run for v1.2.
- Compare the returned cores (identical-core rate), not success.
- Correct "every candidate".

### C13 — minor — The transfer null is weak, and the transfer evidence is 3 runs per cell

**Evidence**
- `transfer.py:87–106` draws null sets from every candidate interneuron of matching sign. The docstring (line 9) also claims matching on
  anchor coverage, which the code does not do.
- The null is evaluated on 3 seeds (line 171), the mechanism on 6. A 0.00 null therefore shows only that random neurons do not work.
- Every cell of `xfer_*.md` holds 3 runs.

**Fix**
- Use a degree- or reachability-matched null from the intact-active pool (the null of `5e10188` exists), with the same seeds for null
  and mechanism.
- Call the transfer results descriptive (n = 3).

### C14 — minor — Stale, mislabelled or ambiguous report text (the mismatch list)

**Evidence**
1. Line 120: "+0.088" identical cores vs group_probe is printed without "(n.s.)". Its CI is [0.000, +0.175].
2. Line 123: v1.0's planted success is called "lower than greedy_plus's". The CI is [−0.099, +0.000], so it is not significant.
3. Line 306: "every candidate" covers 5 of 6 methods (C12).
4. Line 209: the orders are called "salted". They are seeded (1000 + k), and order 0 is the bundle's own order.
5. Line 271: "107 and 25 claims" are greedy_plus's. greedy_reference's joint mode made 61 and 22 more, all correct, and there was one
   false null claim per base method, not one in total.
6. Lines 410–411 say "being fixed (v1.1)", and line 436 says "Reviews B, C and D: pending". Review B finished at `b185e3f` / `f13fb24`
   with 0 blockers, 1 major and 8 minors.
7. §7 (lines 126–160) describes v1.0's selection rule, not v1.2's admissibility-first selection.
8. `research/LOG.md` §10 stops at 2026-09-24 01:10. It has no entries for v1.1, v1.2, the confirmation, the lock or the hidden
   evaluations.
9. Items C11 (0.215 / 0.20; 0.17 / 0.155), C6 (line 346), C7 (lines 338, 340), C8 (line 228) and C9 (line 365).

**Fix.** Update §7, §13 and LOG §10, and correct the wording in each item above.

### C15 — minor — (Q8) The blind run is one draw of the sweep, and on MANC v1.2.1 it is not the modal draw

**Evidence**
- The three frozen blind predictions (`research/phase2/blind_eval/attempt_01/runs/prediction_*.json`, written 17:59–18:28) each return
  exactly the core of the sweep run (order 0, seed 0) in the matching `v12_*.json`.
- On MANC v1.2.1 that core has 4 members and appears in 4 of the 24 sweep runs; the modal core appears in 18. On MANC v1.2.3 the blind
  core is the modal core (20 of 24); on MaleCNS every sweep run returns it (24 of 24).
- The blind configuration (bundle order, seed 0) is therefore already inside the logged, hidden-scored sweep. The blind evaluation adds
  the frozen evaluator's other families, not independent structural evidence.
- On MANC, the choice between the two valid cores has sat near a decision threshold in every version (review B finding B2, and
  B_resolution.md). The single blind outcome is exactly the kind of result that one run can misrepresent.

**Fix**
- Report the blind result next to the sweep distribution (hidden structural success 20/24, 24/24 and 21/24), and state that the blind run
  reproduces the (order 0, seed 0) sweep configuration.
- Do not set a single blind run against a single greedy run (goal3 §20). The paired sweep comparison of §12 is the right one.

## Numerical claims checked against the files

| report section | claims | result |
|---|---|---|
| §6 selection table (36 cells) | `sel_mech_b1000_part{1,2,3}_summary.json` | all match; greedy_reference causal 0.215 uses the summary denominator (C11) |
| §6 budget-curve sentence | `sel_curve_ext_b50_summary.json`, `sel_curve_part*_curve.md` | match |
| §6 pair tournament (24 cells, "about 40 %") | `sel_pairs_b1000.md` | match (savings range 32–44 %) |
| §6 v1-vs table | `cmp_sel_v1_*.md` | match; "+0.088" lacks "(n.s.)"; planted "lower" is not significant (C14) |
| §8 mechanisms (8 rows) | `cmp_conf_greedy_reference.*`, re-derived from records | match (Q2 table) |
| §8 decision rule | `compare_tournament_methods.py`, re-derived | correct |
| §8 pairs and §7.3 numbers | `conf_v12_pairs_v{1,2}f` records | match (mean confidence 0.973; 18 of 81; recall 0.24) |
| §9 greedy table | `greedy_frozen_*.md` | match (8 fidelity seeds 7000–7007) |
| §9 v1.2 table (21 cells, "3–4×", +40 %, +7 %) | `compare_v12_vs_greedy_*.md`, `v12_*.json` | match; "every network" overstates (C8) |
| §10 transfer (16 cells) | `xfer_greedy_plus.md`, `xfer_greedy_reference.md` | match (6 fresh draws, 20 nulls) |
| §10 joint vs controls (8 cells, bullets) | `cmp_arms_pairs_v{1,2}h.md`, `arms_pairs_v{1,2}h.md` | match; "107 and 25" ambiguous (C14) |
| §10 v1's own cross-connectome step | `sel_v1_pairs_v{1,2}h` | match |
| §10 v1.2 transfer table | `xfer_v12.md` | match (359/406, 423 vs 765, 362 vs 359, 367 vs 406, Jaccard 0.80) |
| §11 anti-gaming | `ag_*_summary.md` | match, except "every candidate" (C12) |
| §11 budget curve (20 cells, 49 / 68 / ~100) | `sel_curve_v1_b{50,100}`, `sel_curve_ext_b{50,100}` | match (v1.0 numbers, C1) |
| §11 ablations | `abl_v1_summary.md` | match; the CIs are run-level; two Jaccard effects are not significant (C7) |
| §12 hidden table (all cells, pooled 0.90 / 0.75, 13 / 2, p 0.007, recall 0.83–0.96) | `compare_v12_vs_greedy_*_hidden.md`, `HIDDEN_EVAL_LOG.md` | match |
| §13 review counts and quoted numbers (17 of 22, 6 of 6, 28 of 28) | review files | match; statuses stale (C14) |
| METHOD_LOCK notes ("99.1 %") and AG_resolution ("338 of 396 confident; 97.9 %") | `conf_adv`, `adv_h_v11_rescored` records | match (322/325; 331/338) |

## Reproduction (scratchpad, not committed)

The scripts live in the session scratchpad. Each reads only the files named, writes nothing to the repository, and runs in seconds with
`uv run --no-sync python <script>`.

- **`c_conf_mech.py`** re-derives the confirmation comparison. It checks the pairing, failures, budgets and network hashes. It computes
  the instance bootstrap (20,000 resamples), the instance-level sign and Wilcoxon tests, Holm over the (b) family, and 99 % CIs.
  - "keys A 342 keys B 342 common 342 … failed records 0 … pairs with different network_hash 0 … cores > 40 {'greedy_reference': 30}"
  - "Holm … robust_weight_noise p=4.41e-01 … keep"
- **`c_adv.py`** computes, per method, P(correct | confident) with a Clopper–Pearson CI and instance-cluster CIs, the coverage, the
  per-bin item and instance counts, and paired differences. It covers `conf_adv`, `adv_h_v12`, `adv_h_v11(_rescored)`,
  `adv_h_v10(_rescored)` and `adv_h_comparators(_rescored)`.
  - "brainir_v1 … confident 325 (0.82) conf&correct 322 P(correct|conf) 0.9908 … cluster95 [0.979,1.000]"
- **`c_adv_olddef.py`** scores `conf_adv`, `adv_h_v12` and `adv_h_comparators` under the first truth definition, using the designed
  acceptable cores.
  - "brainir_v1 correct old 0.934 new 0.980 | P(correct|conf) old 0.935 (cluster 95% [0.868,0.991] …) new 0.991"
- **`c_abl.py`** re-analyses the ablations with the instance as the unit.
- **`c_sweeps.py`** covers the real-network sweeps: within-order seed agreement, the per-run cost, order-clustered no-self-pair CIs, and
  cluster-level hidden-success tests.
  - "clusters with a net difference: 12 favour v1.2, 1 favour greedy; cluster sign test p = 0.0034"
- **`c_pair_generic.py`** runs any paired comparison with the instance bootstrap and instance-level sign test. I used it for v1.0 and
  v1.2 against greedy_plus, cem_search and group_probe (held out), and against greedy_plus and group_probe (`adversarial_final`).
  - "brainir_v1 vs greedy_plus … calls_saved diff -37.713 [-45.298, -30.257] instances +2/-55"
  - "(adversarial_final) causal_functional diff -0.040 [-0.076, -0.010]"

## Verdict

- **The lock stands.** The statistical claims behind it are valid:
  - the rules were pre-registered before their data;
  - the confirmation suites were used once, after the freeze;
  - the pairing is exact and the unit of resampling is right for the tournament;
  - the decision rule is applied correctly, and it reproduces from the raw records;
  - it survives instance-level tests and multiplicity adjustment.
- **The hidden sweep comparison is analysed correctly and honestly labelled.** It needs only the cluster test and the
  shared-reconstruction caveat (C9).
- **The report is not yet honest enough about the dimensions where the locked method is not better, or where its advantage is built in.**
  Before the report can be final, the five majors need text and tables. None needs a new method run, except the optional v1.2
  budget-curve and anti-gaming re-runs (C1, C12):
  - C1: v1.2 vs the strong candidates, including its extra calls and its lower causal functional success on `adversarial_final`;
  - C2: the in-distribution adversarial evaluation;
  - C3: disclosure of the truth-definition change and its sensitivity;
  - C4: the effect of greedy_reference's frozen k = 3;
  - C5: the thin evidence behind "identity claims reliable".
- **Conclusion the evidence supports today.** Under the pre-registered rule, BrainIR v1.2 beats the re-expressed frozen greedy on the
  synthetic confirmation. It is more consistent than the frozen greedy on the real networks, at 3–4× the wall time. On the traps it was
  designed against, it is far more often correct and rarely confidently wrong. It is not more query-efficient than the best simple
  candidate (greedy_plus).
