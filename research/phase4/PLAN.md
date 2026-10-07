# Phase 4 plan (ORCHESTRATOR ONLY; never into any room)

Spec: `goal5.md` (Interventionally Trained Causal State Models + Active Experiment Design). Started 2026-09-26 from the Phase 3 final
state (tag `brainir-state-v1-phase3-final`, commit cf5eebe). Decisions go to `research/LOG.md` section 12 (P4-D*).

This file names Phase 3 history, so it is answer-adjacent: it never enters a Phase 4 room, a prompt or a contract. Everything a
clean agent receives is written from goal5's GENERIC text (sections 1-2, 8-19, 24-68) and from public data only.

## 1. Architecture

| piece | location | notes |
|---|---|---|
| Phase 4 code | `phase4/` (uv project, package `brainir_causal`) | depends on root `brainir` and `phase3` `brainir-state` (editable path deps, never edited); numerical stack pinned to Phase 3's (numpy 2.5.3, scipy 1.18.1, torch 2.14.0, scikit-learn 1.9.1) so the frozen Phase 3 v1 runs unchanged as a baseline |
| benchmark | `benchmarks/causal_state_v1/` | PROTOCOL.md, BENCHMARK_LOCK.json, generator/ (hash-locked copy of the author's synthetic generator), public/ (calibration, systems, splits), hidden/ (salt commitment, name map; answer-bearing) |
| orchestrator scripts | `scripts/p4/`, agent stack `scripts/p4agent/` | p4agent = p3agent guard v2 + Docker sandbox rule + Phase 4 room / deny lists (p3agent files are not edited) |
| research | `research/phase4/` | PLAN, INTERFACES, LEAKAGE_POLICY, CLEANROOM_MANIFEST, contracts/, METHODS_REVIEW, tournament/, reviews/, HIDDEN_EVALUATIONS.md |
| data | `data/phase4/` (git-ignored) | store/ (content-addressed), public/, suites/, hidden/ |
| rooms | `C:\Dev\BrainIR_p4clean` (method dev), `_p4bench` (synthetic author), `_p4lit` (literature), `_p4review` (reviews), `_p4audit` (guard / stream logs), `_p4run` (orchestrator runs) | |
| Modal | apps `brainir-p4-*`; volumes `brainir-p4-fit`, `brainir-p4-eval`, `brainir-p4-devdata` | never mount `brainir-p3-eval` (Phase 3 hidden data) |

## 2. Isolation (goal5 sections 4-6)

- Agents = separate headless Claude Code sessions (project dir = room; no MCP; private TEMP; guard hook v2 resolve-and-contain; Python
  audit hook; deny rules). NEW: every agent's code runs in a Docker container (`brainir-p4-sandbox` image, `--network none`, only the
  room mounted, CPU / memory caps) through the room's `sbx` wrapper; host interpreters are refused by the guard. Heavy agent work
  (and all GPU work) goes through the remote runner on network-blocked Modal containers with only the room's public data.
- The Claude sessions themselves are not containerised: an OAuth refresh inside a container would rotate the host's refresh token
  (P3-D2). This residual is stated in LEAKAGE_POLICY.md.
- Room builder `scripts/make_phase4_cleanroom.py` (--build / --check / --destroy-and-rebuild / --audit): allowlist, per-file
  manifest {source, destination, sha256, reason, classification}, content scanner (dataset / circuit / paper names, Phase 2-3
  answer-bearing file names and tokens, absolute repository paths), refusal list.
- NEVER into a Phase 4 room: PHASE*_REPORT.md, goal*.md, research/LOG.md, research/phase2/**, research/phase3/** (except nothing),
  benchmarks/dng100_walking_cpg/**, benchmarks/dng100/{oracle,evaluator,baselines}/**, benchmarks/state_discovery_v1/hidden/**,
  data/phase3/{hidden,real_hidden,_equiv_real_hidden,synthetic_truth}/**, Phase 3 hidden / Level C / tournament / review outputs, the
  eval volume `brainir-p3-eval`, this PLAN.md, the main CLAUDE.md, memory files.
- Relay to agents: generic requirements only (goal5 section 4 list of what they must not receive).

## 3. Benchmark `causal_state_v1` (goal5 sections 7-13, 44-47, 58-60, 70-77)

- Protocol v2 (`brainir_causal.protocol`, `p4-protocol-1`): kicks, currents (pulse / sustained / persistent), current sequences
  (pulse trains, binary sequences, chirps as piecewise-constant segments), silencing (temporary / persistent; single / paired /
  group), edge scaling (weakening / removal), per-neuron parameter perturbation (gain, threshold, time constant), initial-condition
  perturbation, stimulus schedules, weight noise, observation noise. Synthetic-only evaluator events: latent_set / latent_kick.
- Families = kind x arity x magnitude class x temporal pattern; capability record per system; rotating train / held-out family splits
  (frozen), plus hidden-only families never simulatable in development; the service refuses held-out families.
- Real systems: the ten public real systems (three full networks, seven Phase 2-generated mechanisms), re-anonymised; the same
  public / hidden target partition; new hidden data from a NEW salt after the Phase 4 lock.
- Synthetic suite: written by an oracle-free and Phase-3-answer-free author agent (room p4bench) from a generic contract: 25 system
  types of goal5 section 9, the central observational-shortcut trap (section 10), truth (causal state, true read-in, abstract
  interventions, equivalent microstates), calibrated to generic statistics of PUBLIC real data (section 8).
- Splits: dev (public, no truth in room), validation (public data; truth only orchestrator-side, Level B), confirmation (hidden,
  generated from the salt AFTER the method lock), family shift and OOD sets (hidden, after the lock), review G's new traps (after
  composition).
- Evaluator: intervention prediction (multi-horizon, effect error with frozen floor, sign, detectability classes), state mediation
  score (A vs B with microstate residual and intervention identity), interventional closure, microstate equivalence under
  intervention, bisimulation-like test, native lift (miss, cost, future consistency, multiple-lift consistency, success, uncertainty),
  composition, dimension (rule + bootstrap stability), representation stability, abstention / calibration, OOD / robustness, LOIO,
  leave-one-implementation-out, shared dynamics (gated), capacity / compute, active-design efficiency curves.
- References (benchmark code, frozen): no-effect (twin), true-state (synthetic), full-state reference, observational-shortcut
  (synthetic traps), random projection, intervention-ID shortcut. Thresholds calibrated statistically on dev before any method.
- Early reviews E (statistics) and H (numerics) on the evaluation machinery BEFORE the freeze (Phase 3 lesson P3-D13).
- Freeze (BENCHMARK_LOCK.json, tag `causal-state-benchmark-v1`) before any method development.

## 4. Methods (goal5 sections 14-19, 24-43, 48-54, 61-68)

- Literature agent (p4lit, filtered web) -> METHODS_REVIEW (interventional SSMs, causal representation learning, optimal / active
  experiment design, controlled Koopman, subspace ID, controlled SINDy, bisimulation metrics, lifting / inverse control).
- Clean-room developers (after the freeze), one family each, then a composer: linear / DMDc / subspace-ID with control (A-C), sparse
  controlled SINDy / control-affine (D), interventional bottleneck + neural SSM / ODE (E, G, H; GPU via the remote runner),
  controlled Koopman (F), iSSM adaptation (section 17), active design (sections 24-29, 38), baselines (sections 21-23, incl. full-state
  upper bound and intervention-ID shortcut), then composer (I, J).
- Phase 3 BrainIR State v1 = frozen baseline (hash-verified copy; never tuned).
- Public tournament (Level B) on the validation split with successive halving; pre-registered multi-metric rule (section 68 order).
- Reviews A-D, G (new traps), F, E / H follow-ups on the composed candidate; blockers fixed before the lock.
- Method lock `research/phase4/METHOD_LOCK.json`, tag `brainir-causal-state-v1-preblind`.

## 5. Post-lock (goal5 sections 69-99)

Hidden synthetic confirmation, real intervention test, family shift, OOD (once each, logged START / DONE in
`research/phase4/HIDDEN_EVALUATIONS.md`); active-design curves; ablations incl. the two critical ones; counterexample search;
robustness; calibration; self-audit (section 91, tested); review I (claims) + post-lock verification; PHASE4_REPORT.md
(answer-bearing); compute summary from the Modal billing API; final tag.

## 6. Parallel tracks and barriers

1. Now: plan / interfaces / LOG; literature agent; forks: engine (protocol v2, real engine, store, service, systems), calibration
   targets, room + Docker sandbox + agent stack, Modal backend + GPU benchmark.
2. After protocol v2 + calibration targets: synthetic author agent.
3. In parallel with the author: evaluator + references + active-design harness + tournament driver (forks).
4. Barrier: generator delivered + evaluator + references -> dev calibration -> early reviews E/H -> fixes -> FREEZE.
5. After the freeze: developers (parallel), Level B rounds, composer, reviews, LOCK.
6. After the lock: hidden data, Level C, ablations, counterexamples, self-audit, reviews I / verification, report.

Every barrier in 4-6 is serial by design (blindness); everything inside a stage is parallel.

## 7. Notes for the post-lock drivers (collected before the freeze)
- Level C conclusion (fork E15): P_t from `calibrate.true_state_categories` (via `calibrate_system` with the FROZEN tolerances);
  P_m on the same items from `calibrate.calibrate_from_inputs(extra_models={"method": (model, dimension)})` +
  `calibrate.model_categories`; pass both to `verdict.phase4_conclusion` (missing results are charged).
- Official rounds and Level C run with `--backend modal` only (reference platform, P4-D32); synthetic tiers are planned in the
  pinned image (`build_on_modal.py` does it); the conf tier and real Level C sets only after the method lock.
