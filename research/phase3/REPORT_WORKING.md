# PHASE 3 REPORT — Causal state-variable discovery (working draft; becomes PHASE3_REPORT.md)

<!-- sections 1-6 drafted during method development; results sections filled after Level B, the lock and Level C -->

## 1. What Phase 3 set out to do

Phase 2 found compact neuron-level mechanisms and showed that they are not unique. Phase 3 asks a different question (goal4
section 0): can BrainIR automatically discover the smallest low-dimensional causal STATE representation of a circuit's computation?
Such a representation:
- consists of an encoder z = phi(x_{<=t}, u_{<=t}), dynamics f(z, u, events) and a readout g(z, u);
- predicts unseen trajectories and interventions;
- is closed (Markov);
- is equivalent across microstates;
- is shared across alternative neuron-level implementations and independently reconstructed connectomes?

It should also abstain when no compact causal state exists. Semantic labels (phase, amplitude, ...) are never hard-coded.

## 2. Clean-room construction and technological isolation (goal4 sections 3-5)

The orchestrating session knows the Phase 1 oracle and every Phase 2 hidden result, so it designed no method logic. Every
state-discovery method, the synthetic benchmark generator and the methods literature review were written by fresh oracle-free agents.
Each ran as a separate headless Claude Code session whose project directory is its own room:

| room | purpose | agents |
|---|---|---|
| `C:\Dev\BrainIR_p3clean` | method development (5 family developers, then the composer) | m_lin, m_ks, m_nn, m_cb, m_sd, composer |
| `C:\Dev\BrainIR_p3bench` | synthetic benchmark generator | p3bench_author |
| `C:\Dev\BrainIR_p3lit` | methods-only literature review (filtered web access) | p3lit |
| `C:\Dev\BrainIR_p3reviewG` | review G: new adversarial trap families | review_g |
| `C:\Dev\BrainIR_p3regen` | regeneration of Phase 2 candidates (script only, no agent) | — |

Isolation layers (`research/phase3/LEAKAGE_POLICY.md`):
1. a PreToolUse guard hook that denies any tool call naming a path outside the room, forbidden substrings (the main repository,
   other rooms, credentials, other sessions' stores, Phase 2 artefacts), MCP and cross-session tools;
2. a Python audit hook in every Python the agent starts (refuses file / process events on forbidden locations, including paths
   built at run time);
3. permission deny rules;
4. no MCP servers;
5. a private TEMP;
6. simulation only through a budgeted service that enforces the public policy, so held-out families cannot be simulated;
7. anonymised network names.

On the orchestrator side, method code runs only inside a sandbox (`brainir_state.runguard`):
- fits run in subprocesses that can read only their inputs (train / val rows hard-linked into a fit view);
- evaluation refuses file, process and network events whenever method code is on the call stack.

A canary test and a transcript audit (`scripts/p3agent/audit_transcripts.py`) check the stack.

The clean room was built from an explicit allowlist: `scripts/make_phase3_cleanroom.py`, manifest
`research/phase3/CLEANROOM_MANIFEST.json`, 7,542 files, each with a hash, source, reason and leakage class. It contains:
- the public Phase 3 modules;
- the public datasets (real train / val / twin; synthetic dev without truth);
- the anonymised public system definitions and the regenerated candidates;
- PROTOCOL.md, the development contract and the methods review.

It contains no simulator code, no Phase 1-2 library, bundle, report, oracle or truth. `--check` rejects forbidden names and content.

## 3. Phase 2 candidates regenerated from public evidence (goal4 section 5)

Phase 3 needs alternative physical implementations, but must not receive them from answer-bearing reports. They were therefore
regenerated in `C:\Dev\BrainIR_p3regen` as follows:
- the locked BrainIR v1.2 sources, hash-verified against the Phase 2 METHOD_LOCK;
- the public tier-A bundle, hash-verified;
- a public no-gate rhythm criterion;
- seed 0, budget 1000.

Every candidate the method returned (its final core and its enumerated alternatives) was validated by keep-only simulation on 8 fresh
public parameter seeds. There were 7 candidates, all 8/8:
- net1: 4 and 3 neurons;
- net2: 3, 3 and 6;
- net3: 3 and 4.

Provenance and hashes: `research/phase3/candidates/`. Each validated candidate became a keep-only "mechanism" system next to the
intact network.

## 4. The frozen benchmark state_discovery_v1 (goal4 sections 6-7, 20-22, 27-29)

Frozen before method development: `benchmarks/state_discovery_v1/PROTOCOL.md`, `BENCHMARK_LOCK.json` (81 files, 24 dataset entries),
tag `state-discovery-benchmark-v1` (re-locked once before any use, research/LOG.md section 11.3).

**Real systems (10).**
- 3 full networks (net1 / net3: two builds of one reconstruction; net2: an independent one) and 7 keep-only mechanisms.
- 3,005 public trajectories: 2 s at 1 ms; 340 train and 85 val per full system, half that per mechanism; twins of the validation
  interventions.
- The hidden test is generated only after the method lock, from a salt committed by sha256. It has 11 families: held-out draws and
  states, public intervention types on held-out targets, group silencing as a held-out type, and out-of-distribution input and
  weight noise. Every intervention trajectory has a counterfactual twin, and there are microstate-restart pools.

**Synthetic benchmark (oracle-free author; 237 tests).**
- 48 systems: all 20 required families; traps A-L; two implementation groups (Hopf x4, gated integrator x3); three unrelated pairs;
  two non-compressible controls.
- The latent is exactly a population signal simulated in x-space (RK4, verified against an independent solver).
- Suites of the same catalogue:
  - dev: public seed; 2,976 trajectories + 1,536 pool trajectories + 6,144 restarts;
  - heldout: secret seed, 2x;
  - final: secret seed, 3x.
- Each suite's test split holds out:
  - initial-state regions;
  - parameter draws;
  - structural noise;
  - intervention types (group kicks / currents / silencing, edge removal);
  - intervention targets (40 % of neurons).

**Metric families A-L**, kept separate (PROTOCOL.md section 4):
- A: multi-step prediction;
- B: readout;
- C: effect error against counterfactual twins on held-out targets / types;
- D: closure gain from discarded microstate, plus closure gap and Markov rollout consistency;
- E: microstate equivalence by restarts;
- F: dimension and the cheating guard;
- G: reproducibility across seeds;
- H: robustness and the parameter-identity probe;
- I / J: shared vs independent dynamics with leave-one-implementation-out adaptation;
- K: synthetic latent and dimension recovery;
- L: abstention.

Lifting of latent interventions is scored where supported. References: the full-state ceiling, input-only, readout-history,
PCA-k, random-k and persistence.

**Version 1 calibration (before any method; 45 compressible, closed dev systems):** tau_A = 1.31, tau_C = 3.18, tau_D = 0.085,
tau_E = 0.0039. Superseded by version 2.

### 4.1 Benchmark version 2: what two early reviews found, and the correction before any held-out use

Two oracle-free reviewers examined the evaluation machinery while the methods were still in development (LOG P3-D13):
- review E (statistics) found 5 blockers and 6 majors;
- review H (numerical methods) found 1 blocker and 7 majors.

Both reviews and their evidence are in `research/phase3/reviews/E_early.md` and `H_early.md`.

The most consequential errors:
- the tournament's ranks depended on the order in which candidates were listed;
- a model that returned NaN on hard start states got a BETTER predictive score;
- the profile medians used each method's own systems, so failures improved scores;
- the Level C multiplicity family was only partly implemented;
- the closed and microstate conditions were point estimates that the evaluator's own seed flipped on about half the systems;
- the microstate metric depended on the coordinate system of the latent (a condition-10 linear map of the TRUE latent flipped the
  verdict on 14 of 29 systems);
- the readout-history shortcut control was handicapped by a coarse horizon grid.

**Version 2** (tag `state-discovery-benchmark-v2`) fixes all of them (PROTOCOL.md section 10.1;
`research/phase3/reviews/EH_early_resolution.md`). It was locked on 2026-09-25, BEFORE any candidate was scored on held-out data
and before the hidden real data existed. The developers received a generic description of the evaluator changes, never the
reviews. One review finding was kept as a limitation: a numerical property of some synthetic kick events, fixed by the hash-locked
generator.

**Version 2 calibration** (45 dev systems on Modal; tolerances with 95 % CIs over systems):

| tolerance | value | 95 % CI | rule |
|---|---|---|---|
| tau_A | 0.784 | [0.26, 2.30] | 90th percentile of the true-latent / full-state relative A gap |
| tau_C | 3.29 | [2.03, 34.1] | 75th percentile of the true-latent reference's held-out C (state / input interventions) |
| tau_D | 0.400 | [0.27, 0.55] | 90th percentile of the true-latent reference's UPPER CI of D |
| tau_E | 0.0179 | [0.0063, 0.027] | 90th percentile of the true-latent reference's UPPER CI of E (testable systems) |

The calibration's main finding is that **held-out intervention effects are hard even for a model that has the exact state**. Under
the calibrated tolerances:
- the true-latent reference reaches "compact causal state discovered" on 3 of 45 dev systems (one of them with E untestable). It is
  partially supported on 28 and fails the interventional condition on 41;
- the full-state ceiling is never compact with a testable E.

The verdict counts barely move at the CI ends of any tolerance. A candidate's verdict counts must be read against this reference
distribution.

## 5. Methods-only literature review (goal4 section 24)

An oracle-free agent with filtered web access wrote `research/phase3/METHODS_REVIEW.md` (584 KB):
- 110 method entries across seven areas: classical system ID; Koopman / DMD / SINDy; predictive and causal states; neural SSMs;
  causal representation learning and abstraction; population dynamics and similarity; experiment design and evaluation;
- 324 sources (48 read in full, 45 repository / docs, 179 abstracts, 52 unverified);
- eight tournament families with recipes;
- implementation advice for the 19 baselines;
- evaluation measures and pitfalls.

The transcript audit found no answer tokens and two benign guard denials.

## 6. Method tournament (goal4 sections 23, 30, 56)

Five oracle-free developers worked in parallel in the clean room, each on a family, with the baselines assigned to them:

| developer | family | baselines |
|---|---|---|
| lin | A linear subspace / balanced reduction | PCA + linear dynamics, DMDc, FA + LDS |
| ks | B sparse nonlinear (SINDy) + C Koopman | Hankel / delay DMD |
| nn | D predictive bottleneck + F latent neural SSM | AE + linear, RSSM, sequence bottleneck |
| cb | E intervention-aware causal bottleneck (interchange training, microstate PSR, CEGAR) | — |
| sd | G shared cross-implementation models (multi-encoder, unit-space low-rank RNN) | — |

<!-- tournament results, composer, selection: filled after Level B -->
