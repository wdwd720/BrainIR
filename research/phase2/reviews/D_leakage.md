# Review D — leakage (post-lock)

Independent post-lock review (REVIEW_PLAN.md, review D), 2026-09-24. Question: could hidden-answer information have influenced
BrainIR v1 (v1.2.0), its configuration, the libraries it uses, the synthetic suites it was selected and confirmed on, or the
evaluation?

**This file is answer-bearing in places** (sections D4, D5 and the answers to questions 2 and 4 compare development outputs with the
oracle). It must never be copied into a clean development directory. I quote no cell type, body id or tier-A token of the answer.

State reviewed: HEAD `4b3ff3e` (the repository moved from `959d689` to `4b3ff3e` during the review). The lock is commit `959d689`
with tag `brainir-v1-preblind`. Every locked file is identical from the freeze commit `c3362c0` through HEAD
(`git diff --stat c3362c0 959d689` and `959d689 HEAD` over `src scripts/cleanroom_entry scripts/method_lock.py scripts/blind_eval.py
pyproject.toml uv.lock`: empty; clean working tree for these paths).

## Summary

- **Findings: 0 blockers, 4 major, 7 minor.**
- **No identity leakage.** No neuron id, tier-A position, tier-A token, cell type or oracle label of the answer occurs in the method,
  its configuration or the discovery library. None occurs anywhere in the clean room either, and none appears in the tool traffic of
  any clean-room agent.
- **No early hidden evaluation.** No hidden evaluation ran before the lock. The benchmark freeze holds. The blind predictions produced
  so far come from the locked file and reproduce the pre-lock oracle-free runs exactly.
- **What did leak is structure and one calibrated constant.** The answer's structure (about three neurons: an excitatory pair plus
  one of two interchangeable inhibitory neurons, found by keep-only pruning) was written in clean-room documents. It was also in
  every agent's context through the main `CLAUDE.md`. A rhythm amplitude gate calibrated so that the published cores pass was put
  into the discovery library.
- **Isolation was procedural, not technical.**
  - Every clean-room agent ran as a subagent of the answer-aware session. Its working directory was the main repository, and its
    designated temp directory was the orchestrator's scratchpad, which holds answer-bearing files.
  - The tier-B bundle (real cell types) sat in the clean room for about 8 hours.
  - Apart from review E's join count on the size column of tier B, the tool-call audit finds no access to any answer-bearing or
    name-bearing file.
- **Behavioural evidence argues against steering.**
  - On the real MANC network, development versions returned an answer-consistent core at least three times. Each later change moved
    away from it.
  - The locked configuration returns, at the locked seed, a core that does not fill the inhibitory slot.
  - Answer-seeking would have produced the opposite pattern.

## How I checked

1. **Transcript audit.** I parsed the Claude Code transcripts of the orchestrating session and of every Phase 2 subagent
   (`~/.claude/projects/C--Dev-BrainIR/<session>/subagents/agent-*.jsonl`): the literature agent, developers A–F, the composer, and
   reviews A, B, E, F and G.
   - For each agent I listed every tool call that touched a path outside `C:\Dev\BrainIR_p2clean`, used Grep/Glob without a
     clean-room path, used the web or named an answer-bearing file.
   - I listed every tool input or result that contained a published cell type, a core body id, a tier-A token of an answer neuron, an
     oracle label or an answer phrase.
   - I read the orchestrator's messages to the composer and the reviewers.
   - Scripts: `audit_transcripts.py` and `grep_calls.py` in the session scratchpad, folder `reviewD/`.
2. **Code scans.**
   - An AST literal scan of `src/brainir/methods` and `src/brainir/discovery` for integers equal to a tier-A position of an answer
     neuron or stimulus (> 16), the answer's tier-A tokens, the strings E1–E5/I1/I2, and the floats 8.0, 14.0 and 10.5–11.5
     (`scan_code_literals.py`).
   - A text scan of the whole clean room for types, body ids, tokens and answer phrases (`scan_tree.py`).
   - A name search of the clean room for all 353 held-out and final instance names.
3. **Real-bundle trajectory.** I mapped every real-bundle core found in the clean room onto the oracle (`real_runs_vs_oracle.py`).
4. **Git and locks.**
   - `git log` / `git show` around the lock, and the registry index.
   - `benchmarks/dng100/freeze.py --check`, `scripts/method_lock.py check` and `pytest tests/test_leakage_guard.py`.
5. **Gate check.** A local amplitude-gate check: 48 simulations on the public bundle, in-memory simulator, fresh seeds 5000–5007
   (`gate_check.py`).

Limits of the audit:
- The transcripts record actions, not reasoning: model thinking is redacted, for the orchestrator (1,132 characters of thinking over 25
  blocks during the synthetic-generator design) and for the agents. The audit therefore shows what agents opened and printed, not what
  they inferred.
- The agents' parametric knowledge of the published circuit cannot be audited.

## Findings

### D1 — major — The answer's structure, and Phase 1 hidden-evaluation outcomes, were in the clean room and in every agent's context

**Evidence**
- **What the builder copied.** `CLEANROOM_MANIFEST.json` (built 2026-09-23T17:52:11Z, 946 files) and
  `scripts/make_phase2_cleanroom.py:33-42` copy the following:
  - `benchmarks/dng100/PROTOCOL.md`:
    - line 67: the structural family is "excitatory core recall over E1/E2, inhibitory slot I1|I2";
    - line 68: "contralateral copies";
    - lines 89–92: `greedy_prune_sim` "recovers the full core in tier A in two of the three networks (and fails in the third, where its
      greedy path is order-sensitive) — the published answer was itself produced by simulation-guided pruning of this model".
  - `benchmarks/dng100/baselines/README.md:12,20,25`: k = 3 by default; "2 E + 1 I for k = 3"; "heaviest direct target + its
    excitatory and inhibitory reciprocal (2-cycle) partners".
  - `baselines/run_all_baselines.py:140`: "the two published excitatory core neurons".
  - `baselines/recurrence_loop.py:30,149`: "an excitatory pair and an inhibitory slot".
  - `baselines/null_distributions.py`: the metrics `excitatory_core_recall` and `inhibitory_slot_filled`.
  - `README.md:25`: "DNg100 walking-CPG benchmark: spec, answer key".
- **Later syncs.**
  - `scripts/reliability_sweep.py`, with its "E-core recall" and "inhibitory slot rate".
  - `cleanroom/leakage_check.py`, which references `core_contralateral_copies`.
- **`src/brainir/sim/model.py:1`** names "Pugliese et al.". The preprint appeared on 2025-09-12, before the agents' knowledge cutoff.
- **The main `CLAUDE.md` in every context.** Every subagent received `C:\Dev\BrainIR\CLAUDE.md` as project instructions (the
  `instructions` attachment in each transcript).
  - The copies given to the joint developer, the composer and reviews A, B, E and G contain "the simulation-guided baseline
    `greedy_prune_sim` recovers the published core in tier A" (current `CLAUDE.md:127-128`).
  - The copies given to developers A–E point to the answer key and to `oracle/ (answer + tier-A id maps + salt)`.
- **Who read what.**
  - The surrogate_search developer printed `PROTOCOL.md` lines 1–80, including line 67 (agent-a9d16063620639d18,
    2026-09-23T17:55:17Z).
  - The composer never opened `PROTOCOL.md` or any baseline file. Its prompt (orchestrator, 2026-09-23T23:12Z) nevertheless says:
    "The frozen baseline's documented weakness (public in its code and in the benchmark protocol) is order sensitivity … is what the
    evaluation will reward."
- **Two definitions this contradicts.**
  - The benchmark's own LEAKAGE_AUDIT.md defines leakage as "any oracle label anywhere" in "prompts/documents handed to" a method.
  - `PHASE2_REPORT.md` §2 describes the clean room as "no oracle, no Phase 1 reports, no literature about the circuit".

**Assessment**
- **What leaked.**
  - The size (about 3) and sign composition (2 E + 1 of 2 I) of the answer, and the redundancy of its inhibitory member.
  - That keep-only simulation-guided pruning recovers it.
  - That the baseline's failures come from order sensitivity.
- **What did not leak.** Which neurons form the answer.
- **No trace in v1.** v1 contains no size, composition or topology prior (scan, and full read of `brainir_v1.py`).
  - Its design rationale cites synthetic evidence only.
  - The only developer who read the structure (surrogate_search) contributed nothing that survived into v1: the composer dropped the
    surrogate model.
  - The locked MANC output does not have the 2E+1I shape (see D5).
- **The one plausible effect is emphasis.** The focus on order invariance traces partly to a Phase 1 oracle outcome. goal3 §21 and the
  pre-registered decision rule (b) already demanded reliability, so the marginal effect is small.

**Fix**
- Disclose all of the above in `PHASE2_REPORT.md` §2.
- For any later clean room (e.g. for v2):
  - exclude or redact `PROTOCOL.md` §4–5, the baseline README and scripts, `README.md`, `reliability_sweep.py` and
    `leakage_check.py`;
  - make the builder scan file contents (oracle labels, "inhibitory slot", "published", "2 E + 1 I", "k = 3"), not only paths;
  - give agents a clean-room `CLAUDE.md` only (see D2).

### D2 — major — Isolation was procedural: agents worked from the main repository, with the orchestrator's answer-bearing scratchpad as their temp directory

**Evidence**
- **Every agent had the main repository and the shared scratchpad.** Every Phase 2 subagent transcript records
  `workingDirectory = C:\Dev\BrainIR` and the orchestrator's scratchpad as `scratchpadDirectory`.
  - No separate Claude Code session was ever started in the clean room: there is no `C--Dev-BrainIR-p2clean` project directory.
  - The scratchpad holds `oracle_head.json`, `paper/`, `elife_*.txt|html` and `attack_tierA.py`, alongside `composer_prompt.md`,
    `review_prompts.md` and `hidden_sweeps.log`.
- **Agents used the scratchpad.**
  - The greedy_plus developer wrote and ran `run_real.py`, `run_public.py`, `one_public.py` and `runs/` there.
  - Reviews A, E and G ran `ls` on the scratchpad root. Their tool output listed `oracle_head.json` and `attack_tierA.py` by name:
    review E 2026-09-23T23:20:05Z, review A 2026-09-24T05:12:08Z, review G 2026-09-24T05:13:46Z.
- **What the audit found:**
  - no clean-room agent opened any of those files (no tool input names them);
  - no clean-room agent read, grepped or globbed any path of the main repository; the only exceptions are the literature agent
    writing its own output and review F, which ran in the main repository by design;
  - no clean-room agent ran the library with the main repository's environment;
  - no web use except the methods-only literature agent, whose 83 queries are all methods-only;
  - no tool input or result of any clean-room agent contains a published cell type, a core body id or an answer token.
- **The only out-of-clean-room reads** are the agents' own background-task outputs (`tasks/*.output`), their own persisted tool results
  and their own files in the shared scratchpad (e.g. review B's `review_B_opt/`, greedy_plus's `runs/`).

**Assessment**
- Nothing answer-bearing was opened. But the "oracle-free" guarantee rests on instructions and on this after-the-fact audit, not on
  access control.
- The agents' context also carried the main `CLAUDE.md` (D1).
- `PHASE2_REPORT.md` does not say this.

**Fix**
- Start clean-room agents as separate sessions whose project directory is the clean room, with a private scratchpad. Better still,
  run them under an OS account without read access to `C:\Dev\BrainIR` or the orchestrator's temp directory.
- Keep answer-bearing scratch files out of the shared temp directory.
- Archive this audit (scripts and outputs) with the Phase 2 record, and state the residual risk in the report.

### D3 — major — The tier-B bundle (real cell types and body ids) sat in the clean room for about 8 h, and tier A joins it row by row

**Evidence**
- **Exposure window.**
  - The manifest lists the 18 files of `benchmarks/dng100/public/`.
  - The orchestrator removed them at 2026-09-24T02:08:12Z, after checking that they were an exact copy of the frozen original
    (`diff -rq … && rm -rf benchmarks/dng100/public`).
  - The window, 2026-09-23T17:52Z to 2026-09-24T02:08Z, covers all five candidate developers, the joint developer, review E, and the
    composer's v1.0 work from 23:12Z.
- **Tier A joins tier B.** Review E (`E_cross_connectome.md` finding 8) showed that tier A joins tier B by `size_voxels`: 4,309 of
  4,309 rows in MaleCNS and 4,582 of 4,604 in MANC.
- **The types are in the model's likely training data.** The answer's cell types appear in a bioRxiv preprint of 2025-09-12
  (`answer_key.json` source), before the agents' knowledge cutoff (June 2026). An agent that recalled them could have de-blinded tier A
  without touching the oracle.
- **Who touched it.** The transcript audit shows only review E: a join count on the size column, with no cell types read, as its
  review states.

**Assessment**
- This was the most direct channel for identity, and nothing shows it was used.
- Review E rated it minor. The report mentions the removal (LOG) but not the exposure window, and not the model-knowledge route.

**Fix**
- Disclose the window and the residual risk.
- Never put tier B, or any file that joins tier A to names, into a tier-A development environment.

### D4 — major — The discovery library defines "function" on the real bundle with an evaluator constant calibrated on the published cores

**Evidence**
- **Where the gate comes from.**
  - For a bundle without `criterion.json` (the real bundle), `src/brainir/discovery/problem.py:79-81` hard-codes
    `"amplitude_min_hz": 0.25`. The line was added in commit `399dfdd` (Phase 2 kickoff, orchestrator).
  - `criteria.py:5-6` says the real bundle "uses `rhythm` with the frozen evaluator's settings".
- **The gate is not public.**
  - The public `model_config.json` "metric" has no amplitude gate.
  - The public library's own gate defaults to 1.0 Hz (`src/brainir/metrics/rhythm.py:188`).
- **It was calibrated on the answer.** The value comes from the hidden evaluator (`evaluator/evaluate.py:48-54`), whose calibration
  note says that a 1 Hz gate rejected "the published MaleCNS core in 5 of 8", and that 0.25 Hz rejects ripples "while keeping every
  published core".
- **Local check.** Keep-only on 8 fresh seeds, pass counts by gate (0 = the public criterion, score ≥ 0.5 only):

| network | set | gate 0 | 0.25 | 0.5 | 1.0 Hz |
|---|---|---|---|---|---|
| male-cns_v1.0 | intact network | 8 | 8 | 8 | 8 |
| male-cns_v1.0 | v1's core | 7 | 7 | 5 | **1** |
| male-cns_v1.0 | v1's tied alternative | 8 | 8 | 8 | 7 |
| manc_v1.2.1 | intact network | 8 | 8 | 8 | 8 |
| manc_v1.2.1 | v1's core (S4, see D5) | 8 | 8 | 8 | 8 |
| manc_v1.2.1 | the 3-member canonical set (S3) | 8 | 7 | 7 | 5 |

**Assessment**
- An answer-calibrated, non-public threshold entered the method's problem definition through the answer-aware orchestrator.
- **Against the public criterion (no gate)**, the 0.25 Hz gate changes nothing for v1's final candidates. It slightly weakens S3 on
  MANC, the set that would fill the inhibitory slot.
- **Against the library's 1.0 Hz default**, the gate is load-bearing for v1's exact MaleCNS core, which drops from 7 to 1 of 8. The
  tied alternative keeps 7 of 8, and both MaleCNS variants satisfy the structural criterion (post-lock oracle comparison), so the
  structural outcome there is probably robust.
- Method and evaluator share the same definition of function, which is defensible. Its provenance is not disclosed.

**Fix**
- Disclose the gate's origin.
- After the lock, as a robustness report and not a new method: run the locked v1 oracle-free on the blind bundle with the criterion's
  gate at 0 and at 1.0 Hz (a `criterion_spec` override in a driver script, no code change). Report whether any core changes, and
  qualify any "independent recovery" claim accordingly.
- In a future benchmark version, publish the complete functional criterion in the bundle.

### D5 — minor — Development iterated on the test networks; the blind run replays a pre-lock run exactly (and the trajectory argues against steering)

**Evidence**
- **The composer ran v1 on the blind bundle about 20 times**, at seed 0 (the locked seed), on MANC and MaleCNS:
  `data/synthetic/dev_v1/real/{manc_s0_v1b, final*, v11_*, d1be_v12_*, v12_*}`.
  - Twelve of them (two v1.2 builds × decisive 0.90 / 0.95 / 0.975 × two networks) answer the orchestrator's request to rerun at
    0.90 and 0.975 (review B, B2).
  - One rule was added after a real-bundle result. It is disclosed in `BRAINIR_V1_METHOD.md` §12.10.
- **The blind run replays pre-lock runs.** The blind predictions so far equal the pre-lock order-0 / seed-0 sweep runs: `manc_v1.2.1`
  has the same core and 334 primary / 518 total calls; `manc_v1.2.3` has the same core and 367 calls. Both carry
  `method_file_sha256 4bfcf816…`.
- **MANC seed-0 trajectory against the oracle** (compared after the lock). S3 is the 3-member set and S4 the 4-member set of review B,
  finding B2. Both contain the full excitatory core; only S3 fills the inhibitory slot.

| version / build | MANC core | fills the slot |
|---|---|---|
| v1.0 `manc_s0_v1b` (09-23 16:58 PDT) | S4 | no |
| v1.0 `final_manc_s0` (17:17) | S4′ = S4 with its inhibitory member swapped for S3's | yes |
| v1.0 as imported (`final5`, 21:18) | S4 | no |
| v1.1-intermediate (review B table) | S3 | yes |
| v1.1 final `94ea1f8e` | S4 | no |
| v1.2 build `d1be0ca6`, decisive 0.975 | S3, confidently (S4 "worse by size") | yes |
| v1.2 final, 0.975 | S3 tied with S4 (0.5 / 0.5) | tie |
| **v1.2 final, 0.95 = locked; blind run** | **S4** (S3's distinctive member at P = 0.013) | **no** |

- **MaleCNS** returns the same pair of tied variants in every version, and both fill the slot.
- **The locked seed is an unfavourable one.** In the hidden sweep, 20 of 24 MANC runs fill the slot. The locked configuration at
  seed 0 is one of the 4 that do not.

**Assessment**
- This is permitted by the composer contract. It carries no oracle information, but the blind run is oracle-blind, not
  instance-blind.
- The trajectory is the strongest evidence against answer-steering. Three times a version returned an answer-consistent MANC core, and
  each later change moved away from it; the rule added after a real-bundle result demoted the answer-consistent output from a win to
  a tie.

**Fix**
- State in `PHASE2_REPORT.md` that the blind predictions were known (oracle-free) before the lock and that development used the test
  networks.
- Report this trajectory as evidence against steering.

### D6 — minor — The build-report incident is under-counted

**Evidence**
- `PHASE2_REPORT.md` §2 says "Four developers disclosed a one-time glance". The transcripts show that all five candidate developers
  printed the head of `data/synthetic/mechanisms_v1/BUILD_REPORT.json`:
  - greedy_plus: `head -c 3000`;
  - group_probe: `head -80`;
  - surrogate_search: `head -80`;
  - cem_search: `head -40`;
  - evo_pareto: `head -c 1500`.
- The joint developer printed the head of `pairs_v1/BUILD_REPORT.json` (`head -c 1500`: the instance list only).
- The five method documents disclose it; `joint.md` does not.
- The files were removed at 2026-09-23T20:03:04Z.

**Assessment**
- Development-suite truth only. None of the 353 held-out or final instance names occurs anywhere in the clean room, and those suites
  never entered it.
- No effect on the answer, selection or confirmation.

**Fix**
- Correct the count.
- Add the disclosure to `joint.md`.

### D7 — minor — The leakage guard covers only cell types and core body ids

**Evidence**
- `tests/test_leakage_guard.py` scans `src/**/*.py` and a few documents for published types and core and contralateral body ids. It
  passes (4 passed).
- It does not cover:
  - tier-A positions or tokens of the answer;
  - the oracle labels (goal3 §4 names E1/E2/I1/I2);
  - frequency constants;
  - `tests/`, `scripts/` or the clean-room tree.
- My scans of methods, discovery and the whole clean room found none of these. The only answer-adjacent literal is a dummy
  `predicted_frequency_hz=11.0` in a schema test (`tests/test_discovery_infra.py:145`), which is harmless.

**Fix**
- Extend the guard to tier-A positions and tokens read from `oracle/tier_a_ids/` at test time, and to label strings.
- Run the same scan over the clean room before every sync.

### D8 — minor — The synthetic families were designed by the answer-aware orchestrator; none copies the answer

**Evidence**
- `src/brainir/discovery/synthetic.py` was written 2026-09-23T17:39Z (commit `399dfdd`) by the session that had seen the oracle. It
  implements goal3 §7's mandated list; the one gap is that "comparator" is not implemented.
- The E-I pair and ring weights come from the Phase 1 model fixtures in `src/brainir/testing/circuits.py`, which were derived from
  model analysis.
- The suites use no real-network data.
- The adversarial suite was built by an oracle-free third party.
- For the family-by-family comparison, see question 2 below.

**Assessment**
- `ei_pair_oscillator` is a textbook abstraction of the answer's loop (E recurrence plus I feedback, stimulus onto E, about 12 Hz at
  the benchmark current). It is not a copy:
  - 2 members instead of 3;
  - an E autapse instead of a mutually exciting E pair (autapses are absent from the real bundle);
  - no interchangeable inhibitory slot.
- It could not steer selection: all five candidates reached structural success 1.00 on the held-out suite, and v1's components were
  chosen on reliability, calls and minimality across all ten families.

**Fix**
- Record in the report that the generator was written by an answer-aware author, and that no family reproduces the answer's
  structure.
- For a v2, have the generator written oracle-free, as review G did for the adversarial suite.

### D9 — minor — The hidden-evaluation gate's state and the blind freeze are not committed

**Evidence**
- `research/phase2/hidden_eval_ledger.json`, the one-evaluation-per-method-and-network gate that `reliability_sweep.py` enforces, is
  untracked.
- So is `research/phase2/blind_eval/attempt_01/` (running). Its `FROZEN.json` hashes will be written locally only.
- `HIDDEN_EVAL_LOG.md` is committed (`c1f3091`) and agrees with the ledger: 6 entries.

**Fix**
- Commit the ledger with the log.
- Commit `FROZEN.json` before the evaluator's output is inspected.

### D10 — minor — The frozen baseline encodes the answer's size (a Phase 1 design choice)

**Evidence**
- `greedy_prune_sim.py:55` sets `DEFAULT_K = 3`. `greedy_reference` uses k = 3, and `random_matched` uses 2 E + 1 I.
- These were set by answer-aware Phase 1 designers.

**Assessment**
- This biases the structural comparison towards the baseline, not v1. It is part of the frozen benchmark, but it belongs in the
  interpretation of "v1 vs baseline".

**Fix**
- State it wherever the structural family is compared.

### D11 — minor — Post-lock answer-bearing artefacts now sit in `research/phase2/`

**Evidence**
- Post-lock, the following sit in `research/phase2/`:
  - per-run hidden rows (`reliability/v12_*.json`, `greedy_frozen_*.json`, `compare_*_hidden.*`);
  - `HIDDEN_EVAL_LOG.md`;
  - `hidden_eval_ledger.json`;
  - the blind outputs;
  - this review.
- The per-run rows tie tier-A positions to structural outcomes.
- The clean-room builder filters paths on "oracle", "truth" and "results", not on "hidden", "reliability" or `reviews/D_`. Syncs are
  done by hand with `cp`.

**Fix**
- Add these paths to the builder's exclusions and to a pre-sync check.
- Mark them answer-bearing in `CLAUDE.md`.

## Answers to the six questions

1. **Method code and configuration.**
   - I read `brainir_v1.py` completely, and `joint.py` and `correspondence.py` for their logic and constants.
   - None of the following appears: dataset names, cell types, ids, tier-A positions or tokens, oracle labels, size or composition
     constants, frequency bands, or rhythm special cases. Criterion types are used only to name roles.
   - The constants are generic: probabilities, participation thresholds, seed blocks, the tie band, and an identity calibration fitted
     on the composer's own synthetic pairs.
   - The imports reach only the bundle-reading discovery library. `mapping.py` and `oracle/cross_connectome_reference.json` are not
     used.
   - The file hashes equal the lock (`4bfcf816…`, `38609d27…`, `11acef92…`), and the clean-room copies are identical.
   - The one answer-derived element in the libraries v1 uses is the amplitude gate (D4).
2. **Synthetic generator families.**
   - Oscillators:
     - `ei_pair_oscillator` is an abstract analogue of the answer's loop, not a copy (D8);
     - `redundant_oscillator` has two disjoint E-I pairs; the answer instead has a shared excitatory core with an interchangeable
       inhibitor;
     - `two_implementations` pairs an E-I pair with a ring;
     - `ring_oscillator` and `delayed_inhibitory_oscillator` are unrelated.
   - The other five families (`feedforward_driver`, `negative_feedback_controller`, `integrator`, `memory_switch`, `winner_take_all`) are
     unrelated.
   - Complications and sizes are generic.
   - The stimulus current (250) and the rhythm criterion copy the public model and task, plus the gate of D4.
   - Five of ten families are rhythmic, as goal3 §7 lists.
   - Effect on the conclusions: negligible for selection, since every candidate had structural success 1.00. The synthetic results are
     tests of the generic method in the benchmark's own model regime, which is their purpose.
3. **The clean room.**
   - Nothing it contains carries the oracle, the evaluator, per-instance scores or truth of the held-out or final suites, or any answer
     identity.
   - Truth directories exist only for the agents' own dev suites.
   - It did carry answer structure (D1). It carried tier B for about 8 h (D3), and the development build reports for about 2 h (D6).
   - The composer's real-bundle runs were oracle-free; what they show is in D5.
4. **Hidden evaluations.**
   - The two pre-lock `--score-existing` attempts were refused by the gate ("refusing: …", 2026-09-23T23:17:07Z and 23:56:52Z).
   - The orchestrator transcript shows no evaluator invocation before the lock. It only read the evaluator's code, to build the
     tools.
   - No Phase 2 registry record is an evaluation.
   - All six logged hidden evaluations are after the lock:
     - lock written 2026-09-25T00:37:33Z, committed and tagged 00:37:52Z;
     - blind run started 00:38:03Z (MaleCNS prediction still pending at the time of writing);
     - hidden scoring of the sweeps 00:39:25Z–00:44:55Z.
   - The v1.2 sweeps were launched at 2026-09-24T23:41:15Z on commit `fbf967d` with a clean `src`. Their recorded
     `locked_tree_sha256` equals the lock's `911625b9…`, and their config hash equals the lock's (`ee45951e…`).
   - The blind predictions carry the locked method hash and reproduce those sweep runs exactly.
   - `method_lock.py check`: OK.
5. **The benchmark freeze.**
   - `freeze.py --check`: ok, with nothing changed, added or missing, and dataset manifests unchanged.
   - `git log a7c0142..HEAD` over the 131 locked benchmark files and 19 locked code files: no commits.
   - The only post-tag changes under `benchmarks/` are the registry and a documentation edit to `dng100_walking_cpg/README.md`, which
     added goal3.md to the answer-bearing list.
6. **Other channels.**

| channel | finding |
|---|---|
| persistent cache | `CausalEffectCache` is never instantiated (grep); no store exists under `data/cache/`. No channel. |
| labels and names in the suites | Held-out and final names are opaque 12-hex hashes and absent from the clean room. Dev-suite names are readable by design; their truth leaked via the build reports (D6), dev only. |
| aggregate feedback | `selection_results/` and the orchestrator's messages carry aggregates, one per-family remark ("the memory-switch hub-pair case you documented") and no positions or answer terms (grep of every message). Selection-suite information only; the confirmation suites were untouched. |
| cross-connectome mapping | v1 uses anchor fingerprints and bundle annotations only. The curated mapping and the oracle's reference pairs are not imported. |
| node-order variants | Permutations with seeds 1000+k over the already salted bundle order; the composer used its own permutation seeds. No channel. |
| seeds | Seed 0 was fixed pre-lock and used throughout development. It is not favourable on MANC (D5). No seed picking. |

## Verdict

The blind result **can be interpreted as free of answer-identity leakage and of oracle feedback**. Nothing in the method, its
configuration, the discovery library, the clean room or the agents' tool traffic identifies the answer's neurons. No hidden
evaluation preceded the lock. Both the lock and the benchmark freeze verify.

It **cannot be called fully blind to the answer's structure**:
- the development environment disclosed size, composition and "pruning recovers it" (D1);
- one answer-calibrated constant defines function in the library (D4);
- isolation rested on instructions, checked here only after the fact (D2, D3).

The behavioural record is the reason none of this is a blocker. The locked configuration returns, at the locked seed on MANC, the
candidate that does not fill the inhibitory slot, after three development versions had returned the one that does.

The report should present structural success as what PROTOCOL §5 already says it is: expected of any keep-only pruning search on
this benchmark. It should disclose D1–D4. It should add the D4 sensitivity run before any claim of independent structural recovery.

## Files and sources read

- **Phase 2 documents** (`research/phase2/`):
  - `COMPOSER_CONTRACT.md`, `METHOD_DEV_CONTRACT.md`, `CROSS_CONNECTOME_CONTRACT.md`, `SELECTION_PROTOCOL.md`, `HIDDEN_EVAL_LOG.md`,
    `METHOD_LOCK.json`, `REVIEW_PLAN.md`;
  - `BRAINIR_V1_METHOD.md` (§12.9–12.10 and greps);
  - `methods/*.md` (greps), `methods_review.md` (greps);
  - `reviews/B_optimisation.md` (B2), `reviews/E_cross_connectome.md` (findings 7–8);
  - `hidden_eval_ledger.json`, `reliability/v12_manc_v1.2.1.json`, `reliability/v12_manc_v1.2.3.json`;
  - `blind_eval/attempt_01/runs/*.json`.
- **Project documents**: `research/LOG.md` §10 and the decision register, `PHASE2_REPORT.md`, `CLAUDE.md` (main and clean room),
  `goal3.md` §4, §7 and §27–29.
- **Benchmark**:
  - `oracle/oracle.json`, `oracle/oracle.py`, `oracle/tier_a_ids/*.csv` (answer rows only);
  - `public_blind/` (README, model config, answer rows of `neurons.parquet`);
  - `PROTOCOL.md`, `LEAKAGE_AUDIT.md`, `BENCHMARK_LOCK.json`;
  - `evaluator/evaluate.py:44-60` and greps;
  - `baselines/README.md`, `baselines/greedy_prune_sim.py` and `baselines/recurrence_loop.py` (greps);
  - `dng100_walking_cpg/answer_key.json` (source, edges), `dng100_walking_cpg/README.md` diff.
- **Code**:
  - `src/brainir/methods/{brainir_v1.py (full), _brainir_v1_sha256.py, __init__.py, greedy_reference.py}`;
  - `src/brainir/discovery/{correspondence.py (full), synthetic.py (full), criteria.py (full), joint.py, synthetic_pairs.py,
    adversarial.py, problem.py, simulator.py, run.py, transfer.py, __init__.py}`;
  - `src/brainir/metrics/rhythm.py`, `src/brainir/testing/circuits.py`.
- **Scripts**: `make_phase2_cleanroom.py`, `method_lock.py`, `blind_eval.py`, `reliability_sweep.py`, `build_synthetic_suite.py`,
  `cleanroom_entry/brainir_discovery_entry.py`.
- **Tests**: `test_leakage_guard.py`, and parts of `test_discovery_infra.py` and `test_robustness_experiments.py`.
- **Clean room**: `CLEANROOM_MANIFEST.json`, the full file tree, `selection_results/*`, real-bundle results under
  `data/synthetic/dev_v1/real/`, `research/phase2/methods/*_results`, `runs/`, and the `.venv` editable path.
- **Transcripts and scratchpad**:
  - the orchestrator transcript;
  - 13 Phase 2 subagent transcripts, with their prompts and injected instructions;
  - the prompt of the Phase 1 synthetic-circuits agent;
  - the auto-memory files;
  - `v1_fix_contract.md` and `review_prompts.md` in the orchestrator's scratchpad.
- **Git and registry**: git history, tags and diffs; `benchmarks/dng100/manifests/experiments/index.jsonl`.

## Appendix: commands

```
uv run --no-sync python benchmarks/dng100/freeze.py --check          # ok: true
uv run --no-sync python scripts/method_lock.py check                  # METHOD_LOCK check: OK
uv run --no-sync pytest tests/test_leakage_guard.py -q -p no:cacheprovider   # 4 passed
git diff --stat c3362c0 959d689 -- src scripts/cleanroom_entry scripts/method_lock.py scripts/blind_eval.py pyproject.toml uv.lock   # empty
git log --oneline a7c0142..HEAD -- <131 locked benchmark files + 19 locked code files>                                           # empty
# scratchpad reviewD/: audit_transcripts.py, grep_calls.py, scan_code_literals.py, scan_tree.py, real_runs_vs_oracle.py, gate_check.py
```
