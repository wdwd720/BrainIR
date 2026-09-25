# Review D (leakage): resolution

**This file is answer-bearing** (it summarises review D, whose D4, D5 and question 2 and 4 answers compare development outputs with
the oracle). Never copy it into a clean development directory.

Review: `research/phase2/reviews/D_leakage.md`, post-lock, on HEAD `4b3ff3e`. It found 0 blockers, 4 major and 7 minor findings.

**Verdict:**
- The blind result can be interpreted as free of answer-identity leakage and of oracle feedback.
- It cannot be called fully blind to the answer's structure.
- None of the findings is a blocker. On the real MANC network the development trajectory moved away from the
  answer-consistent core three times, and the locked configuration returns, at the locked seed, the core that does not fill the
  inhibitory slot.

The method is locked, so nothing below changes BrainIR v1.2.0. The resolutions are:
- disclosure in `PHASE2_REPORT.md`;
- a sensitivity analysis;
- fixes to the tooling, which apply to any later clean room or method version.

| # | severity | finding | resolution | status |
|---|---|---|---|---|
| D1 | major | The answer's structure was in the clean room: benchmark `PROTOCOL.md`, the baseline README and scripts, the repository README, the synced `reliability_sweep.py` and `leakage_check.py`. It was also in every agent's context, through the main `CLAUDE.md`. What leaked: the size (about 3), the sign composition (2 E + 1 of 2 I), the redundancy of the inhibitory member, that keep-only pruning recovers it, and that the baseline fails through order sensitivity. Which neurons form the answer did not leak. | **Disclosed** in `PHASE2_REPORT.md` §2, with who read what: one developer, surrogate_search, printed the protocol lines; its method contributed nothing to v1. The composer never opened them, but its prompt named order sensitivity. **Fixed for any later room** (`scripts/make_phase2_cleanroom.py`, commit `ca125e5`): <br>• the protocol, READMEs, baseline scripts and `leakage_check.py` are no longer copied; <br>• every copied text file is scanned for answer phrases; <br>• `--check` validates files before a manual sync; <br>• `CLAUDE.md` no longer states how the baseline fares on the answer. <br>**Residual:** the frozen public bundle and library cite the model's source paper (the sign rule is named after it). An agent that recalls the paper could recall the circuit. This route cannot be closed without a new benchmark version. | disclosed; tooling fixed |
| D2 | major | Isolation was procedural. Every clean-room agent was a subagent of the answer-aware session, with the main repository as its working directory and the orchestrator's scratchpad as its temp directory. That scratchpad holds `oracle_head.json`, the paper text and a tier-A attack script. Reviews A, E and G listed those file names. | **Disclosed** in §2: the transcript audit found that no clean-room agent opened any answer-bearing file, and none read the main repository. The guarantee rests on instructions plus an after-the-fact audit, not on access control. **For any later method version:** start development agents as separate sessions whose project directory is the clean room, with a private temp directory, ideally under an OS account without read access to the main repository. This is recorded in the builder's docstring and in `research/LOG.md`. | disclosed; process fix recorded |
| D3 | major | The tier-B bundle (real cell types) was in the clean room from 2026-09-23T17:52Z to 2026-09-24T02:08Z, covering all candidate development and v1.0's composition. Tier A joins tier B by `size_voxels`, and the answer's cell types predate the model's knowledge cutoff. | **Disclosed** in §2 with the window and the model-knowledge route. Only review E touched it: a join count on the size column, with no types read. The builder has not copied tier B since commit `60ec1ab` (review E). | disclosed; fixed earlier |
| D4 | major | The discovery library defines function on the real bundle with the evaluator's amplitude gate (0.25 Hz), which was calibrated so that every published core passes. It is not in the public bundle, and the library's own default is 1.0 Hz. | **Disclosed** in §2 and §9. **Sensitivity analysis:** the locked v1.2.0 was rerun oracle-free on the blind bundle with the gate at 0 (the public criterion) and at 1.0 Hz, with 8 node orders × 3 seeds per network, the same design as the locked sweeps (`research/phase2/reliability/v12_gate*_*.md`, `scripts/reliability_sweep.py --criterion-gate`). Results: see §9 of the report and the table below. No hidden evaluation of these runs. | disclosed; sensitivity measured |
| D5 | minor | Development iterated on the test networks: the composer ran v1 on the blind bundle about 20 times at seed 0. The blind run replays a pre-lock run exactly. | **Disclosed** in §12. The blind predictions were known oracle-free before the lock, and the blind run is one draw of the hidden-scored sweep (review C, C15). The MANC trajectory is reported as evidence against steering. | disclosed |
| D6 | minor | The build-report incident was under-counted: all five candidate developers printed the head of `mechanisms_v1/BUILD_REPORT.json`, and the joint developer printed the head of `pairs_v1/BUILD_REPORT.json`. | §2 corrected. An orchestrator note was added to `research/phase2/methods/joint.md`. The builder now never copies build or audit reports, or any directory named `truth*`. A trial build showed it would otherwise copy `truth_backup_pre_audit`, which was created after the Phase 2 room was built; the room's manifest confirms that the room never held it. | fixed |
| D7 | minor | The leakage guard covered only published types and core body ids in `src/`. | `tests/test_leakage_guard.py` (commit `9db1da5`): <br>• an AST scan of methods, discovery and the clean-room entry for integers equal to an answer neuron's tier-A position (> 16), for strings containing an answer neuron's tier-A token, and for oracle labels; <br>• token scans of `scripts/`, `tests/` and the clean room's code and documents. <br>All values are read from the oracle at test time and never printed. 7 passed. | fixed |
| D8 | minor | The synthetic generator was written by the answer-aware orchestrator. `ei_pair_oscillator` is an abstract analogue of the answer's loop, not a copy. | **Disclosed** in §3. No family reproduces the answer's structure (review D, question 2). Every candidate reached structural success 1.00 on the held-out suite, so the families could not steer selection. **For a later version:** an oracle-free generator, as review G's author did for the traps. | disclosed |
| D9 | minor | The hidden-evaluation ledger and the blind freeze were uncommitted. | The ledger was committed in `fc25f16`. `FROZEN.json` and the predictions were committed in `bee81b3` at 01:32:17Z, before the evaluator wrote its output at 01:33:32Z. That commit contains the log's FROZEN row, not the evaluation row. | fixed |
| D10 | minor | The frozen baseline encodes the answer's size (k = 3), a Phase 1 design choice. | Stated wherever structural success is compared (report §§8, 9, 12). It biases the structural comparison towards the baseline. | disclosed |
| D11 | minor | Post-lock answer-bearing artefacts sit in `research/phase2/`: hidden sweep rows, the log, the ledger, blind outputs, review D and the report. | The builder refuses these paths (`FORBIDDEN_PATHS`). `CLAUDE.md` marks them answer-bearing. | fixed |

**The reviewer's own oracle comparison.** Review D labelled the development-era real-bundle cores and the first two blind predictions
with the oracle during its audit, after the lock (`real_runs_vs_oracle.py`). The orchestrator logged this as an audit comparison in
`research/phase2/HIDDEN_EVAL_LOG.md`. It happened after the method and the predictions were frozen, so it could not influence either.

## D4 sensitivity results

**Design.** Oracle-free sweeps with the locked configuration except the gate: 8 node orders × 3 seeds per network, the same
variants as the locked sweeps. Files: `research/phase2/reliability/v12_gate*_*.md` and `compare_v12_locked_vs_gate*_*.md`.

**Structural outcomes.** These come from the logged scores of identical cores in the locked sweeps. No evaluator was run, and the
analysis is logged in `HIDDEN_EVAL_LOG.md` (`reliability/gate_sensitivity_vs_logged.json`).

| network | gate 0 (public criterion): same core as locked | gate 1.0 Hz: same core as locked | runs meeting the structural criterion, locked / gate 0 / gate 1.0 (unscored) |
|---|---|---|---|
| manc_v1.2.1 | 24 of 24 | 3 of 24 | 20 / 20 / 19 (2) |
| male-cns_v1.0 | 24 of 24 | 0 of 24: 18 runs return the tied alternative the locked runs report at P ≈ 0.42 | 24 / 24 / — (24; review D's audit found that the tied alternative also meets the criterion) |
| manc_v1.2.3 | 22 of 24 (the other 2 move to the modal core) | 1 of 24 | 21 / 23 / 18 (1) |

**Conclusions.**
- **The evaluator-calibrated gate did not help the locked method.** With the public criterion it returns the same cores, 70 of 72,
  and the two changes improve the outcome.
- **Under a stricter 1.0 Hz gate the answers move** among the valid alternatives the method enumerates. Every core still passes
  keep-only under that criterion, and the logged success counts barely change on MANC.
- **The claim of independent recovery stands for the public criterion.** It is qualified in `PHASE2_REPORT.md` §9.3: the exact
  neuron-level answer depends on how strictly "rhythmic" is defined.
