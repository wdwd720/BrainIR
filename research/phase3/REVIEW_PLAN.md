# Phase 3 review plan (goal4 sections 69-70)

Reviews run before the method lock (A-H) and after the Level C evaluation (post-lock). Reviewers are separate agents. Their reports go
to the orchestrator only, never directly to the method developers.

- The orchestrator relays blockers about the METHOD to the composer only as generic requirements. Example: "encoder-only adaptation
  must not refit f". It never relays a statement about the synthetic families, the real circuit or hidden results.
- The orchestrator fixes blockers about the BENCHMARK or EVALUATOR. A change to a hashed file after the benchmark freeze is a new
  benchmark version (PROTOCOL.md section 10), logged in research/LOG.md.

## Rooms and inputs

| review | question set (goal4 section 69) | reviewer environment | inputs |
|---|---|---|---|
| A nonlinear dynamics / system identification | state realisation? closure tests meaningful? dimension selection sound? | review room `C:\Dev\BrainIR_p3review` (oracle-free agent, guard + audit) | public evaluator code, PROTOCOL.md, candidate method code + notes (snapshot of the clean room's methods), developer-facing Level B aggregates, test results |
| B causal inference | do intervention results justify causal claims? are latent interventions legitimate? shortcut confounders? | review room | as A |
| C representation learning | observationally predictive but mechanistically wrong? baselines strong enough? capacity controlled? | review room | as A, plus baseline implementations |
| D computational neuroscience | simulations interpreted honestly? low-level interventions biologically sensible? claims > evidence? | review room | as A, plus the public system definitions (anonymised) and the real public data |
| E statistics | experimental unit, contamination, CIs, multiplicity | review room | as A, plus the statistics code (evaluate_cross, harness.verdict) and the tournament driver |
| F leakage / clean room | can method agents reach Phase 2 answers? did answer-bearing files enter? did names or sizes leak? | ANSWER-AWARE subagent in the main repository (its report goes to the orchestrator only) | CLEANROOM_MANIFEST.json, LEAKAGE_POLICY.md, the guard / launcher code, the transcript audit, the rooms themselves |
| G adversarial state discovery | NEW trap families unknown to the composer | oracle-free agent in a copy of the benchmark-author room (`C:\Dev\BrainIR_p3reviewG`) | the generator code and its contract, the candidate method's notes (algorithm description); the new traps are built into a separate suite by the orchestrator (secret seed) and scored before the lock |
| H numerical methods | integration, timing, solver artefacts | review room plus the generator's numerics and the piecewise real engine | realsim.py, the frozen Phase 1 simulator module (no data), p3synth core / diagnostics, the protocol code, the numerical tests |

## Early round (E, H), added 2026-09-25 (LOG P3-D13)

Reviews E and H examine machinery that does not depend on the method: the evaluator, statistics, tournament, generator and
simulators. They run first, while the methods are still in development, in `C:\Dev\BrainIR_p3review` built with
`make_review_room.py --extras eh`. The prompts are in `review_contracts/REVIEW_{E,H}_EARLY_TASK.txt`.

`extra/` holds the orchestrator-side files the plan above gives to E and H. In these copies, dataset, paper and bundle names are
replaced by REDACTED. Nothing hidden enters.

Reviews A-D run on the composed candidate after a `--update` of the same room. E then gets a follow-up on the tournament's actual
ranking.

## Blocker policy

A blocker is a finding that makes a pre-registered claim or metric invalid, for example:
- a leakage route;
- a wrong metric;
- a method that violates the contract (future leakage, y in the encoder, per-neuron memorisation);
- a sandbox escape.

Blockers are resolved before the method lock. The resolution and a re-check are recorded in `reviews/<X>_resolution.md`. Other
findings go to the report as limitations.

## Post-lock reviews

After Level C, reviewers may see the hidden results and flag reporting errors, statistical errors and claims that need weakening.
They never change the locked method under the same version (a method change is v2).
