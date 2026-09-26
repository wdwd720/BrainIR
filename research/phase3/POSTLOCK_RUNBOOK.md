# Phase 3 post-lock runbook (prepared before the lock; orchestrator side)

This is the exact command sequence from the method lock to the report, drawn as a dependency graph. Steps on one level run in parallel.
Everything a step needs was built and tested before the lock (2026-09-25):
- `scripts/p3/counterexamples.py` (Modal backend, local vs Modal equivalence verified);
- `scripts/p3/ablations.py`, `scripts/p3/self_audit.py`, `scripts/p3/compute_summary.py`;
- the post-lock review contracts `research/phase3/review_contracts/POSTLOCK_*.txt`;
- tests: `phase3/tests/test_postlock_infra.py`.

Conventions:
- `UV` = the uv executable. Every command runs from `C:\Dev\BrainIR` as `"$UV" run --project phase3 --no-sync python ...`.
- `M` = the locked method name, from `METHOD_LOCK.json`.
- `B` = the comparator fixed by the round decision (`ROUND_DECISION.json` → `comparator.chosen`).
- `LOCKED = phase3/src/brainir_state/methods`: the locked copy that `method_lock_p3.py --lock` writes.
- **Hidden** = a hidden evaluation. It is logged in `research/phase3/HIDDEN_EVALUATIONS.md` (the scripts append the row themselves,
  except where noted), and its outputs are answer-bearing.

## Dependency graph

```
[L0] pre-lock gate (main session): benchmark v3 re-locked + tagged; composer + baseline tuner done; round 3 attempt 2 + decision
  |
[L1] method lock + commit + tag brainir-state-v1-preblind  (local, minutes; SERIAL BARRIER)
  |
  +--> [L2a] Level B confirmation, synthetic FINAL suite      (Modal CPU, Hidden)            ~20-40 min wall
  +--> [L2b] hidden real data generation                     (Modal CPU, pinned; eval volume)  ~10-15 min wall incl. download
  +--> [L2c] dev-suite ablations of the locked method         (Modal CPU, development data)  ~15 min wall; gives dev models for probes
  |
  +--(L2a done)--> [L3a] ablations on the FINAL suite         (Modal CPU, Hidden)            ~20-30 min wall
  +--(L2a done)--> [L3b] counterexamples, synthetic FINAL     (Modal CPU, Hidden)            ~10 min wall
  +--(L2a + L2b)--> [L3c] Level C                             (fits and evaluations on Modal: LEAKAGE_POLICY 3.1 amendment; Hidden)
                     |
                     +--> [L4a] counterexamples, real, PUBLIC draws  (Modal CPU; development-domain draws on public systems)
                     +--> [L4b] counterexamples, real, HIDDEN draws  (local CPU only, Hidden)
                     +--> [L4c] counterexamples for the comparator B (same as L3b / L4a with B's models; for the report)
  |
  +--(all L3/L4)--> [L5] compute summary + self-audit with probes + report draft (local)
                     |
                     +--> [L6] post-lock reviews S, C, Y, R (agents, in parallel) and L (answer-aware subagent)
                     |
                     +--> [L7] resolve reporting findings; rerun self-audit; final report; final tag
```

The critical path is L1 → L2b → L3c (Level C) → L5 → L6 → L7. L2a, L3a and L3b hide behind L2b and L3c. Level C is the step to
speed up (see L3c).

## Commands

**L1: method lock (serial barrier).**
```
"$UV" run --project phase3 --no-sync python scripts/p3/method_lock_p3.py --lock --method M --baseline B \
    --from C:\Dev\BrainIR_p3run\<decision round>\methods --selection research/phase3/tournament/<decision round>/ROUND_DECISION.json \
    --notes C:\Dev\BrainIR_p3clean\notes\brainir_state_v1.md
git add research/phase3/METHOD_LOCK.json phase3/src/brainir_state/methods && git commit -m "Method lock: BrainIR State v1"
git tag brainir-state-v1-preblind
"$UV" run --project phase3 --no-sync python scripts/p3/method_lock_p3.py --check
"$UV" run --project phase3 --no-sync python scripts/p3/self_audit.py --only I3,I4,I9
```

**L2a: Level B confirmation (Hidden; Modal).**
```
"$UV" run --project phase3 --no-sync python scripts/p3/modal_tournament.py run --round final_b --suite final \
    --methods M,<declared baselines incl. B> --room C:\Dev\BrainIR\phase3 --containers 300
```
- The tournament appends its row to `LEVELB_LOG.md`.
- If the driver does not also append a `HIDDEN_EVALUATIONS.md` row for the final suite, add it by hand. Self-audit check I8 fails
  otherwise.
- The self-audit (Q2, Q3, Q5-Q8, Q11-Q13, Q16) reads per-system records. It would also use the per-system `res`, the full
  evaluation stripped of `_units`, to test Q13 and Q14 on the synthetic suite. Ask the tournament owner to persist `res` for
  `--suite final`.

**L2b: hidden real data (once; Modal backend, written to the eval volume only, verified local copy).**
```
"$UV" run --project phase3 --no-sync python scripts/p3/generate_real_hidden.py --backend modal --containers 300
```

**L2c: dev-suite ablations of the locked method (development data; Modal).**
```
"$UV" run --project phase3 --no-sync python scripts/p3/ablations.py --suite dev --backend modal --containers 300 --round ablations_dev
```
This run also produces dev-suite fits of the locked method (`C:\Dev\BrainIR_p3run\ablations_dev\full\indep\<sid>_s0.pkl`) for the
self-audit's prefix probe.

**L3a: ablations on the FINAL suite (Hidden; Modal).** This reuses the confirmation's fits of the full method.
```
"$UV" run --project phase3 --no-sync python scripts/p3/ablations.py --suite final --full-from final_b --backend modal \
    --containers 300 --round ablations_final
```

**L3b: counterexamples, synthetic FINAL suite (Hidden; Modal).**
```
"$UV" run --project phase3 --no-sync python scripts/p3/counterexamples.py sweep --method-dir phase3/src/brainir_state/methods --method M \
    --model-pattern "C:/Dev/BrainIR_p3run/final_b/M/indep/{sid}_s0.pkl" --kind synthetic --tier final --systems all \
    --seeds 0,1,2 --strategies random,evolve,structured,bo --budget 60 --objective effect --init-state \
    --backend modal --containers 300 --out-dir research/phase3/counterexamples/final_M
```
A second run with `--objective post` covers the non-intervention error surface. Both are cheap.

**L3c: Level C (Hidden).**
```
"$UV" run --project phase3 --no-sync python scripts/p3/level_c.py --method-dir phase3/src/brainir_state/methods --method M --baseline B \
    --final-round final_b --decision-round <decision round> --resample-arm 5 --parallel 12 --eval-workers 12
```
Speed-up decision for the main session: this is the critical path. The work is about 150 real fits of about 6 min each, plus
about 150 evaluations of 5-15 min each.
- Fits on public real data may run on Modal. The public real fit view must be uploaded once to the fit volume as a tar.
- Evaluations need the hidden real data. LEAKAGE_POLICY.md section 3.1 keeps real hidden data off Modal, so they run locally
  (about 1-2 h wall on 12 workers).
- To move them to Modal, first amend the policy (logged, before generating the data). The amendment would create a separate
  volume `brainir-p3-hidden`, mounted only by evaluation containers and never by fit containers, and delete it after Level C.
- Real-engine numerics differ between Windows and Linux at the solver tolerance (see "Numerical equivalence"). The hidden data
  must therefore be generated on one platform (local). The evaluation reads stored trajectories, so where it runs does not change
  the data.

**L4a / L4b / L4c: counterexamples on the real systems.**
```
# public draws (development-domain parameters): Modal
... counterexamples.py sweep --kind real --model-pattern "C:/Dev/BrainIR_p3run/level_c_01/M/indep/{sid_}_s0.pkl" --systems all \
    --seeds 0,1,2 --strategies random,evolve,structured,bo --budget 60 --objective effect --init-state --backend modal \
    --out-dir research/phase3/counterexamples/real_public_M
# hidden draws (salt-derived): LOCAL only (the script refuses Modal for real --hidden)
... counterexamples.py sweep --kind real --hidden --model-pattern "C:/Dev/BrainIR_p3run/level_c_01/M/indep/{sid_}_s0.pkl" --systems all \
    --seeds 0,1,2 --strategies random,evolve,structured,bo --budget 60 --objective effect --init-state --backend local --workers 8 \
    --reason "post-lock counterexample search, real hidden draws" --out-dir research/phase3/counterexamples/real_hidden_M
```
L4c repeats L3b / L4a with B's models (`.../B/indep/...`).

**L5: compute summary, self-audit, report draft.**
```
"$UV" run --project phase3 --no-sync python scripts/p3/compute_summary.py
"$UV" run --project phase3 --no-sync python scripts/p3/self_audit.py --final-round final_b --level-c 01 --run-tests --run-root-tests \
    --modal-checks --probe-prefix --probe-permutation --probe-method-dir phase3/src/brainir_state/methods \
    --probe-model-pattern "C:/Dev/BrainIR_p3run/ablations_dev/full/indep/{sid}_s0.pkl" --probe-systems <3 dev systems>
```
After the run, delete the permutation probe's temporary copies (`data/phase3/p3perm_*`).

**L6: post-lock reviews (parallel).**
- Build the post-lock review room `C:\Dev\BrainIR_p3postreview` after L5, once the draft is in PHASE3_REPORT.md (or still in
  `research/phase3/REPORT_WORKING.md`, the fallback). The builder is answer-aware and makes copies only:
```
"$UV" run --project phase3 --no-sync python scripts/p3/make_postlock_review_room.py --sync-env --prompts "C:\Dev\BrainIR_p3audit\prompts\postlock"
"$UV" run --project phase3 --no-sync python scripts/p3/make_postlock_review_room.py --check
```
  - It copies an explicit list:
    - docs/: PROTOCOL.md, the review contracts (COMMON + S, C, Y, R; never L), and goal4.md sections 7, 53, 59, 68, 70, 84-88 and 91
      only, redacted;
    - METHOD_LOCK.json, PHASE3_REPORT.md;
    - `src/brainir_state` (with the locked `methods/`) and `scripts/`;
    - under `results/`: every tournament round incl. `_failed/` (without `_refcache/`), `level_c/`, `ablations/`, `counterexamples/`,
      `postlock_infra/`, review G's results, the benchmark calibration, tolerances, public systems and lock, SELF_AUDIT,
      COMPUTE_SUMMARY, LEVELB_LOG.md, COSTS_LEDGER.md, and the hidden-evaluation log as `results/EVALUATION_LOG.md`. The agents'
      tool guard refuses paths containing `hidden_eval`; CLAUDE.md and the prompts tell the reviewers.
  - Every text is redacted with the review-room class plus the transcript audit's source names. Binary files are listed, not copied.
  - The build happens in a staging directory. It is refused, and an existing room is left untouched, on any of:
    - a forbidden name or content;
    - a Phase 1 answer token (self_audit I7 rule; classes only);
    - code that no longer parses;
    - a results file the tool guard would block.
  - Manifest: `research/phase3/POSTLOCK_REVIEW_ROOM_MANIFEST.json` (a failure writes `...MANIFEST.FAILED.json`). Required sources
    missing (METHOD_LOCK.json, Level C, ablations, counterexamples, SELF_AUDIT, ...) stop the build: build only after L5.
  - After report fixes, rebuild with `--update` (keeps `reviews/`, `.tmp/`, `.venv/`), then `--check`.
  - `self_audit.py` I6 / I7 scan only the clean and pre-lock review rooms (the script is benchmark-locked). The builder's own scans
    and `--check` cover this room; reviewer L re-runs `--check`.
- Launch reviewers S, C, Y and R as separate sessions, in parallel:
```
for X in S C Y R; do
  "$UV" run --project phase3 --no-sync python scripts/p3agent/launch.py --clean "C:\Dev\BrainIR_p3postreview" --name postlock_$X \
      --prompt-file "C:\Dev\BrainIR_p3audit\prompts\postlock\postlock_$X.txt" > "C:\Dev\BrainIR_p3audit\agents\postlock_$X.out" 2>&1 &
done; wait
```
- Run L as an answer-aware subagent in the main repository.
- Each writes `reviews/POSTLOCK_<X>.md`. Before archiving them to `research/phase3/reviews/`, the orchestrator runs:
  - the transcript audit (`scripts/p3agent/audit_transcripts.py`);
  - the builder's `--check`, which also scans `reviews/`.

**L7: resolve and finalise.** Fix reporting findings (never the method), rerun the self-audit, finalise PHASE3_REPORT.md, then create
the final Phase 3 tag.

## Where the ablations run (proposal for PROTOCOL.md version 3)

goal4 asks for "important ablations" in the report (sections 84, 85 criterion 40) without naming the data.
- **Primary: the FINAL synthetic suite**, run after the Level B confirmation. It is the only data on which component effects are
  unbiased:
  - the heldout suite selected the method, so the full method's advantage there is optimistic;
  - the dev suite is the developer's tuning data.
  Running variants there does not touch the locked method's own confirmation result, which is already written, and nothing is
  selected from them: any change after the lock is v2. The runs are logged as hidden evaluations.
- **Secondary: the dev suite**, for comparability with the developer's notes. It is labelled as development data.
- **Not on the real hidden data.** Level C runs once, for the locked method, the comparator and the controls. Ablations there would
  multiply hidden evaluations on the one real test set. If real-circuit component effects are wanted, run them descriptively on the
  public real validation data. That needs a role mapping for the public families, which is not built.

## Measured costs and timings (smoke tests, 2026-09-25)

| workload | where | measurement |
|---|---|---|
| counterexample search, synthetic dev system, 12 protocols x 4 strategies | local vs Modal | 13-18 s per search locally under agent load, 9-12 s on Modal; $0.007 for 4 searches (app ap-LAmkLM5G3yhtOdfsJCZtfb) |
| counterexample search, real mechanism system, 8 protocols x 4 strategies (effect objective: 2 simulations per protocol) | local vs Modal | 16-18 s local, 10-11 s Modal; $0.007 (ap-DW6DzPCRyZIK0uvrQgtqF7) |
| real engine, full network (net1), one 1.2 s protocol | local vs Modal | about 8 s local, 5 s Modal (ap-AQgJuEhilb4jPLl3rNFbGz) |
| locked-method (pre-lock v1 snapshot) fits, 2 dev systems x 2 variants | Modal | 4 fits in 132 s wall; 4 evaluations in 45 s (ap-NsXHeWdz2sTd8CXTfgOQqH) |

Projected post-lock costs at these rates:
- counterexamples, synthetic final (48 systems x 4 strategies x 3 seeds, budget 60, effect objective): about 12 container-hours,
  about $6, about 10 min wall with 300 containers;
- real public draws: about 7 container-hours, about $4;
- real hidden draws locally: about 1 h wall on 8 workers;
- ablations on the final suite (13 switches + full, 48 systems, shared fits for 3 variants): about 40 container-hours, about $20,
  20-30 min wall.

## Numerical equivalence (local Windows vs Modal Linux)

- **Synthetic generator and counterexample searches:** equivalent. The same protocol sequences come out for all four strategies,
  and the errors agree to a maximum relative difference of 4e-16 (`research/phase3/postlock_infra/cex_equivalence.json`).
- **Real engine (frozen Dopri5, rtol 2e-6):** not bitwise.
  - Most protocols are bit-identical. Where the adaptive step sequence differs, readouts differ by at most 0.75 % of the readout
    sd, relative L2 at most 9e-4 (`sim_equivalence_real_mech.json`, `sim_equivalence_real_full.json`).
  - Search errors on a real system differ by up to 0.3 % relative, with identical protocol sequences
    (`cex_equivalence_real.json`).
  - Consequences:
    1. Never combine a local and a Modal simulation in one comparison. A twin and its intervened run are always simulated in the
       same process.
    2. The hidden real data are generated on one platform (local).
    3. For real systems, local and Modal counterexample results are equivalent within 1 % relative. This is well inside the search's
       decision thresholds (a factor of 2, or an absolute 1.0).

## Notes for the main session

- The self-audit reads the per-system records of the confirmation round. For synthetic Q13 / Q14 it needs the stored `res`, as
  Level C already stores it.
- Never edit the evaluator while a round or an ablation is in flight.
  - The Modal containers mount the code at app start.
  - `ablations.py` refuses to write verdicts if the evaluator code tag changed during the run.
  - The dev smoke run of 2026-09-25 hit exactly this: benchmark v3 was being edited, and the local verdict needed a tolerance
    (`tau_H`) the v2 tolerances do not have.
  - Rerun `ablations.py --suite dev --allow-unlocked --method brainir_state_v1 --methods-dir C:\Dev\BrainIR_p3run\r3_brainir_state_v1\methods
    --switches domain_clip --systems syn-0dccdf2720,syn-12db9981b8 --shared-variants none --round ablations_smoke_dev` after the v3
    re-lock. It reuses its fits; the evaluations cost about $0.05.
- The real counterexample searches run the public bundle `benchmarks/dng100/public_blind` (3 MB) inside the Modal image, as a mount
  of the post-lock app. It is public (tier A, no oracle), consistent with LEAKAGE_POLICY section 3.1; state it there when the policy
  is next updated.
