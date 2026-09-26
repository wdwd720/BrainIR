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

### 4.2 Benchmark version 3: the pre-lock reviews A-D, and the correction before the method lock

Four independent pre-lock reviewers examined the composed candidate (brainir_state_v1) and benchmark version 2 on public data:
A (system identification), B (causal inference), C (representation learning) and D (computational neuroscience)
(`research/phase3/reviews/{A,B,C,D}_prelock.md`). They found 7 blockers and 19 major issues. Every evaluation fix went into
**version 3** (tag `state-discovery-benchmark-v3`, 2026-09-25). At that point no method was locked, the FINAL suite had never been
used and no hidden real data existed. Method findings went to the developer as generic requirements only. The mapping of every
finding: `research/phase3/reviews/ABCD_prelock_resolution.md`.

The most consequential corrections:
- **Hidden memory was not tested.** A model could store the full microstate when encoding and use it when rolling out while
  reporting a 1-D latent; reviewers demonstrated it. Version 3 runs every rollout on a fresh copy of the model and requires the model's
  own rollout, restarted from its predicted z (also after interventions), to reproduce itself. A model that fails carries memory
  beyond z: its k is invalid, and it cannot be "compact" or "closed".
- **"Closed" had almost no power.** Random k-dimensional projections passed it on 25 of 45 dev systems. While fixing it we found an
  artefact: the ridge penalty shrank the base (z, u) of the closure regressions, so extra columns that merely repeat z "helped", even
  for the exact state. On a toy system with the exact 2-D state the history gain was 0.74 under version 2; it is 0 under version 3.
  With the base fitted without shrinkage, the residual computed inside each fold and a history-gain condition added, random
  projections pass "closed" on 24 % of the dev systems and the true latent on 80 %.
- **C could not show a causal STATE.** The interventional condition is decided by "held-out effects predicted better than no
  effect" (tau_C cannot bind); version 3 words the claim that way, adds a leave-one-pair-out condition (the claim must not rest on one
  pair), scores events on unobserved neurons apart, and reports whether the prediction depends on the state at all (C with the
  pre-event state replaced by the mean training state).
- **Two components rewarded the wrong thing.** The dimension score gave credit for any reported k range containing the truth (a wider
  range never cost anything); it now scores the point k. Latent recovery (K) measured only one direction; it is now the minimum of
  both.
- **Real systems.** On the real systems the readout NMSE was dominated by near-silent readout neurons weighted up to 1000x; it is now
  pooled. The predictive condition compared with a readout-history control that sees each trajectory's parameters of neurons outside
  x; it now compares with the input-only control and the persistence floor. On mechanism systems the "held-out target" families
  used the public targets; there the held-out C is now group silencing only.
- **Claims and lineage.** "Real" is worded as connectome-constrained rate-model simulations; net1 and net3 are one reconstruction
  and are never counted as two confirmations.

**Version 3 calibration** (45 dev systems on Modal):

| tolerance | value | 95 % CI |
|---|---|---|
| tau_A | 0.784 | [0.26, 2.30] |
| tau_C (does not bind) | 3.69 | [2.10, 51.0] |
| tau_D | 0.092 | [0.051, 0.248] |
| tau_H (history gain) | 0.234 | [0.147, 0.293] |
| tau_gap | reported only (pre-registered power rule failed: random projections pass it as often as the true latent) | |
| tau_E | 0.0179 | [0.0065, 0.027] |

The true-latent reference reaches "compact causal state discovered" on 3 of 45 dev systems (one with E untestable), partially
supported on 22, not supported on 20. PCA-k reaches "partially supported" on 6, random-k on 2.

**Execution.** The version-3 round 3 ran on Modal. Two execution-only re-locks followed while it ran (per-job container memory
recording and container sizing; a builder recovery fix; then a fix of a module-level error that re-lock 1 introduced and that made
every Modal job fail at import). No evaluation module changed in either (the same evaluator code tag). Two round-3 parts that ran
under the broken re-lock 1 are archived as invalid and were re-run (`research/phase3/LEVELB_LOG.md`).

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

**Development:**
- 23:07 to 08:30. On the shared 16-thread machine, the developers' own dev-suite validation chains had grown to 2-12 h. At 08:30 each
  session was stopped and resumed with a generic wrap-up note: freeze the code, finish notes and tests with the results at hand,
  declare candidates vs baselines. All five finished within 7 minutes.
- 19 registered methods: 12 candidates and 7 baselines (goal4 section 23). All transcript audits are clean: 0 forbidden-path inputs;
  the only answer-token hit was a numeric false positive (a file size).

**Level B round 1 (pre-registered pilot, 16 heldout systems, no shared fits).** Run on Modal in 74 min, about $11. By mean rank
(S1-S7), the top 10 survive:

| rank | method | family | mean rank | P(rank 1) |
|---|---|---|---|---|
| 1 | nn_closed | neural closed SSM | 5.57 | 0.28 |
| 2 | lin_falds | baseline (FA + LDS) | 6.07 | 0.08 |
| 3 | ks_sindy | SINDy on learned coordinates | 6.29 | 0.52 |
| 4 | lin_subspace | CVA subspace ID | 6.57 | 0.04 |
| 5 | lin_balanced | balanced reduction | 7.07 | 0.04 |
| 6 | lin_dmdc | baseline (DMDc) | 8.36 | 0.01 |
| 7 | ks_edmd | EDMD / Koopman | 8.79 | 0.00 |
| 8 | nn_aelin | baseline (AE + linear) | 8.93 | 0.02 |
| 9 | ks_hankel | baseline (Hankel / delay) | 9.21 | 0.01 |
| 10 | cb_cegar | counterexample-guided | 9.50 | 0.00 |

Eliminated: cb_psr, lin_pcadyn, cb_interchange, nn_seqbottleneck, ks_kae, sd_shared, sd_lowrank, nn_rssm, nn_pred_bottleneck. The
pilot has no shared fits, so the sharing-specialised candidates got no credit for sharing.

**Level B round 2 (all 48 heldout systems, G seeds, sharing groups and nulls with leave-one-out).** Run on Modal in 70 min, about
$26.

| method | S1 A/A_full | S2 C | S3 D | S4 E | S5 K R^2 | S6 dim | S7 abst. | S8 sharing | mean rank (7 eligible) |
|---|---|---|---|---|---|---|---|---|---|
| lin_subspace | 0.999 | 0.564 | -0.083 | 0.002 | 0.996 | 0.674 | 0.457 | 0.500 | **3.31** (P(rank 1) 0.57) |
| lin_falds (baseline) | 1.157 | 0.550 | -0.005 | 0.001 | 0.997 | 0.587 | 0.891 | 0.500 | 3.69 |
| nn_closed | 0.938 | 0.746 | -0.008 | 0.002 | 0.991 | 0.783 | 0.978 | 0.500 | 3.88 |
| lin_dmdc (baseline) | 1.079 | 0.613 | -0.049 | 0.002 | 0.995 | 0.565 | 0.902 | 0.500 | 3.94 |
| ks_sindy | 0.969 | 0.585 | -0.035 | 0.002 | 0.995 | 0.652 | 0.696 | 0.167 | 4.12 |
| nn_aelin (baseline) | 1.095 | 0.983 | -0.071 | 0.003 | 0.991 | 0.783 | 0.989 | 0.500 | 4.38 |
| lin_balanced | 1.027 | 0.680 | -0.046 | 0.002 | 0.997 | 0.543 | 0.500 | 0.500 | 4.69 |

**Eligibility.** ks_edmd, ks_hankel and cb_cegar are independent-only by design. Their 18 attempted shared / leave-one-out fits
count as failures, just above the pre-registered 10 % limit, so they are ineligible under the literal rule. This conflicts with the
"untestable" provision for methods that cannot share. As a sensitivity check, ranking all 10 as eligible leaves the first candidate
(lin_subspace) and the best baseline (lin_falds) unchanged; the three rank 7th, 9th and 10th.

**Sharing.** No candidate obtains support for either implementation group (Hopf x4, gated integrator x3):
- shared models are measurably worse than independent ones (paired A differences +0.02 to +0.15 NMSE, CIs above 0);
- encoder-only adaptation rarely beats from-scratch fits on 25 % of the held-out implementation's data;
- the unrelated pairs are correctly rejected by every sharing-capable method (S8 = 0.5 = groups 0 %, pairs 100 %).

**Review G, the new adversarial traps (oracle-free reviewer; 10 systems no developer saw).** On the round-2 top five, every candidate
is confidently wrong on at least one trap ("compact causal state discovered" where the truth disagrees):
- G4, a 9-stage delay chain: 4 of 5 claim a compact state with k = 3-4 (lin_dmdc: k = 14, E untestable);
- G10, a non-compressible system that looks low-dimensional: lin_falds claims a compact state; only lin_dmdc abstains;
- G7: ks_sindy claims a compact state with k = 1 against 3;
- G9, a hidden parameter drift: the dimension is right, the drift unreported.

The symmetry-hidden mode of G1 (k = 4) is found only by lin_dmdc; the others choose k = 2, as the trap intends, but none claims a
compact state there. The verdict's conditions certify sufficiency on the tested horizons and interventions, NOT the minimality or
correctness of k.

<!-- composer, round 3, selection: filled after round 3 -->
