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

**The composer's hybrid (brainir_state_v1).** A separate oracle-free agent composed the final candidate from the aggregate round-1 and
round-2 feedback (never per-system results, never reviewer findings; later requirements were relayed as generic items only). Its
design, objective and dimension rule are in `research/phase3/METHOD_NOTES.md` (the developer's notes, locked and hash-checked):
- ks_sindy's model: a linear causal encoder on delay features, fitted as a reduced-rank predictive basis;
- an E-SINDy integral-form transition law and a polynomial readout;
- event operators that act through the encoder's current-sample block, with per-kind gains calibrated on training events;
- replacements where ks_sindy was weak: the nn family's plateau tolerance for k (rebuilt after the pre-lock reviews with nested
  configuration choice and a cross-fitted reference error) and its input-floor abstention;
- a k sweep that continues past 8 while the error still falls;
- an internal held-out sharing test;
- honest per-kind support, so the method abstains where no calibrated evidence exists.

On public data the developer found the rebuilt rule roughly neutral against the tournament version and stated it.

**Level B round 3 under benchmark version 3** (`research/phase3/tournament/r3v3/`). The round used the round-2 design and 19 parts,
one Modal app each, in parallel. The longest part took 53 min; from the first launch to the decision took about 1.8 h, including
relaunches after network failures and the composer's late part. The round cost about $25.7 (48.7 container-hours):
- the 10 round-2 finalists, re-scored from byte-identical round-2 fits;
- the 3 pilot-eliminated baselines;
- the 5 independently tuned baseline variants;
- brainir_state_v1, fitted in full.

Six methods are ineligible because each failed 18 shared or leave-one-out fits (they cannot share by design): cb_cegar, ks_edmd,
ks_hankel, ks_hankel_t, nn_rssm and nn_seqbottleneck. Primary ranking of the 13 eligible methods (S1-S8, over the 46 compressible
heldout systems):

| rank | method | S1 A/A_full | S2 C | S3 D | S4 E | S5 K | S6 exact k | S7 abst. | S8 | mean rank | P(rank 1) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **brainir_state_v1** | 0.959 | **0.507** | 0.022 | 0.0018 | 0.985 | **0.652** | 0.728 | 0.5 | **5.00** | **0.519** |
| 2 | lin_dmdc_t (baseline, tuned) | 1.079 | 0.657 | 0.017 | 0.0016 | 0.993 | 0.370 | 0.902 | 0.5 | 5.50 | 0.063 |
| 3 | lin_subspace | 0.999 | 0.520 | 0.023 | 0.0018 | 0.990 | 0.630 | 0.457 | 0.5 | 5.81 | 0.151 |
| 4 | lin_dmdc (baseline) | 1.079 | 0.657 | 0.017 | 0.0016 | 0.993 | 0.370 | 0.902 | 0.5 | 5.88 | 0.094 |
| 4 | lin_falds (baseline) | 1.157 | 0.561 | 0.020 | **0.0011** | 0.985 | 0.478 | 0.891 | 0.5 | 5.88 | 0.135 |
| 6 | nn_closed | **0.938** | 0.768 | 0.030 | 0.0023 | 0.978 | 0.565 | 0.978 | 0.5 | 6.62 | 0.029 |
| 7 | lin_pcadyn (baseline) | 1.053 | 0.710 | **0.017** | 0.0015 | 0.966 | 0.239 | 0.848 | 0.5 | 6.88 | 0.003 |
| 8 | lin_pcadyn_t | 1.053 | 0.710 | 0.017 | 0.0015 | 0.966 | 0.239 | 0.848 | 0.5 | 7.00 | 0.001 |
| 9 | lin_balanced | 1.027 | 0.680 | 0.025 | 0.0024 | **0.993** | 0.413 | 0.500 | 0.5 | 7.25 | 0.004 |
| 10 | ks_sindy | 0.969 | 0.605 | 0.022 | 0.0017 | 0.946 | 0.500 | 0.696 | 0.167 | 7.62 | 0.000 |
| 11 | nn_aelin (baseline) | 1.095 | 0.958 | 0.033 | 0.0028 | 0.981 | 0.630 | **0.989** | 0.5 | 7.75 | 0.000 |
| 12 | nn_aelin_t | 1.095 | 0.965 | 0.034 | 0.0032 | 0.980 | 0.609 | 0.989 | 0.5 | 8.31 | 0.001 |
| 13 | lin_falds_t | 1.052 | 1.266 | 0.038 | 0.0032 | 0.837 | 0.087 | 0.739 | 0.333 | 11.50 | 0.000 |

**Selection (pre-registered rule, `ROUND_DECISION.json`).** brainir_state_v1 is selected because its bootstrap P(rank 1) = 0.519 is
at least 0.5. The margin is narrow:
- its 90 % rank interval is [1, 5];
- leaving out one profile component at a time, it stays first in 5 of 8 cases. It is 4th without S1 (lin_falds first), 2nd without
  S2 (lin_dmdc_t first) and 3rd without S6 (lin_dmdc_t first).

So its advantage rests on held-out intervention fidelity (S2) and exact dimension (S6), not on prediction.

**Comparator.** lin_dmdc_t is the best of the 8 eligible baselines on S1-S5. nn_aelin, nn_aelin_t, nn_rssm and nn_seqbottleneck fail
the Markov / rollout-consistency check on more than 10 % of the systems. lin_dmdc_t is lin_dmdc with its wall-clock branch removed
(the tuner's determinism-only variant): identical k and verdicts on all 46 systems and profiles equal to about 1e-14. The order
between the two was set by float-level differences and has no consequence; the deterministic variant is the one the protocol's
determinism rule asks for.

**Failures of the selected method in round 3.** All 7 leave-one-implementation-out ADAPTATION fits of the two implementation groups
failed. The cause is a deterministic error in the method's own adaptation code: when its internal sharing test rejects sharing, the
source model holds independent laws of different k, and averaging their latent covariances fails. For both groups the returned
"shared" model equals the independent fits, so its sharing verdict is "untestable" there (S8 = 0.5, the same as every other
sharing-capable method). One descriptive evaluation of an unrelated pair also failed. These count as failures (8 of 204 units) and
were neither retried nor fixed: a fix after this round would have given the selected method a second chance that no other
participant had.

**The tuned baselines.** Only lin_falds_t differed materially from its original. Its dev-suite gain did not carry over: on the heldout
suite it ranks last (S2 1.27, S6 0.09). lin_dmdc_t and lin_pcadyn_t reproduce their originals, ks_hankel_t differs only in S3 at the
third digit, and nn_aelin_t is marginally worse.

## 7. Method lock (goal4 sections 57, 86)

- Locked on 2026-09-26 01:32 UTC: tag `brainir-state-v1-preblind`, commit bce6dbf, recording the lock at commit 6c7c2cd.
- `research/phase3/METHOD_LOCK.json` holds:
  - source hashes of the 30 files of the methods package (byte-identical to the scored round-3 snapshot and to the clean room at
    lock time);
  - the benchmark lock and clean-room manifest hashes, and the training-data manifests;
  - the default configuration, the developer's full notes (METHOD_NOTES.md, hash-checked), seeds, budgets and the package
    environment.
- At the lock, the FINAL synthetic suite had never been used and no hidden real data existed (self-audit I9).
- Integrity at the lock: the Phase 1 freeze check, the Phase 2 method-lock check, the Phase 3 benchmark-lock check and
  `method_lock_p3.py --check` all pass.
- Self-audit I3 fails as written, and this is disclosed rather than patched. The check compares the working benchmark lock with the
  copy at tag `state-discovery-benchmark-v3`, but the two logged execution-only re-locks rewrote the lock file after that tag. The
  property it tests holds: the re-lock-2 tag holds the current lock file exactly, the freeze check passes, and the salt matches its
  commitment.

## 8. Level B confirmation on the FINAL synthetic suite (hidden; run once after the lock)

**Design.** The FINAL suite has 48 systems (46 compressible, 2 non-compressible controls), secret seeds, 3x the test trajectories
and the round-2 design (G seeds on 8 systems, sharing groups and unrelated pairs with leave-one-out fits). The locked method and all
12 declared baselines and tuned variants were run once, as 13 parallel parts on Modal (12 GiB containers; measured peak 2.7 GB).
The per-part directories are `final_b_<method>/`, merged in `research/phase3/tournament/final_b/`. It cost about $54.8, and nothing
was selected on this suite.

**Ranking on the aggregate profile (9 eligible; descriptive).**

| rank | method | S1 A/A_full | S2 C | S3 D | S4 E | S5 K | S6 exact k | S7 abst. | S8 | mean rank | P(rank 1) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | lin_dmdc_t (comparator) | 1.34 | **0.477** | **0.014** | 0.0018 | **0.991** | 0.348 | 0.859 | 0.5 | **3.44** | **0.37** |
| 2 | lin_dmdc | 1.34 | 0.477 | 0.014 | 0.0018 | 0.991 | 0.348 | 0.859 | 0.5 | 3.94 | 0.17 |
| 3 | **brainir_state_v1** | **0.997** | 0.483 | 0.031 | 0.0018 | 0.987 | 0.587 | 0.739 | 0.5 | 4.38 | 0.25 |
| 4 | lin_falds | 1.42 | 0.545 | 0.017 | **0.0013** | 0.973 | 0.413 | 0.924 | 0.5 | 4.62 | 0.16 |
| 5 | nn_aelin | 1.13 | 0.953 | 0.036 | 0.0028 | 0.979 | **0.783** | **0.978** | 0.5 | 4.81 | 0.02 |
| 6 | nn_aelin_t | 1.13 | 0.953 | 0.036 | 0.0028 | 0.979 | 0.783 | 0.978 | 0.5 | 5.06 | 0.01 |
| 7 | lin_pcadyn_t | 1.27 | 0.484 | 0.018 | 0.0019 | 0.955 | 0.239 | 0.837 | 0.5 | 5.75 | 0.01 |
| 8 | lin_pcadyn | 1.27 | 0.484 | 0.018 | 0.0019 | 0.955 | 0.239 | 0.837 | 0.5 | 5.88 | 0.02 |
| 9 | lin_falds_t | 1.16 | 1.10 | 0.019 | 0.0021 | 0.814 | 0.152 | 0.804 | 0.5 | 7.12 | 0.00 |

Ineligible (18 failed shared / leave-one-out fits each): ks_hankel, ks_hankel_t, nn_rssm, nn_seqbottleneck.

**The selection did not replicate as a ranking.** On the heldout suite brainir_state_v1 ranked first with P(rank 1) = 0.52. On the
unbiased FINAL suite it ranks third (P(rank 1) = 0.25) behind the comparator and its twin. The pattern is consistent with the
winner's curse of a narrow selection. Against the comparator, component by component:
- **better:** S1, prediction relative to the full-state model (0.997 against 1.34; it is the only method near the full-state bound);
- **better:** S6, exact k (27 of 46 against 16 of 46);
- **tied:** S2, held-out interventions (0.483 against 0.477), and S4, microstate equivalence;
- **worse:** S3, residual microstate gain (0.031 against 0.014);
- **worse:** S5, latent recovery (0.987 against 0.991);
- **worse:** S7, abstention (0.739 against 0.859).

**The locked method on the FINAL suite (46 compressible systems):**
- the Markov / rollout-consistency check passes on 46 of 46;
- verdicts: "compact causal state discovered" on 19 (2 with microstate equivalence untestable), "partially supported" on 12, "not
  supported" on 15;
- conditions met: predictive 32, interventional 24, closed 36, microstate-equivalent 34 (E testable on 40), state-mediated
  intervention effects 27;
- dimension: exact k on 27, under-estimated on 3, over-estimated on 16;
- abstention: 1 of the 2 non-compressible controls; 1 false alarm among the 46 compressible systems (2 %). On 52 % of all systems it
  neither abstains nor meets the interventional and closed conditions (the "confident-wrong" rate of family L);
- seeds (G, 8 systems x 3 seeds): the same k on 4 of 8; latent agreement min(R^2 both ways) 0.69-1.00;
- sharing: neither implementation group is supported (one untestable, one rejected); all 3 unrelated pairs are rejected (S8 = 0.5);
- failures: 4 of 108 fits (the leave-one-out adaptation fits, the known defect) and 0 of 99 evaluations.

## 9. Counterexample search (goal4 sections 52-54, 87; post-lock, FINAL suite, hidden)

`scripts/p3/counterexamples.py sweep` searched the FINAL synthetic suite, with 48 systems x 3 seeds x 4 strategies and 60 protocols
per search (random, evolutionary, structured single-target probes, Bayesian optimisation), including perturbed initial states. It
ran for the locked method and for the comparator, with two objectives:
- effect: the counterfactual effect error of family C, where 1 = predicting no effect;
- post: the post-event readout error.

The search domain is deliberately wider than the public protocol families. A protocol is a counterexample candidate when its error
is at least max(1, 2 x the system's random-protocol p90). A system is "broken immediately" when at least half of its searches find
a candidate among their first 10 protocols. The results are in `research/phase3/counterexamples/final_*` (0 failed searches in all
four sweeps).

| sweep | systems with counterexamples | distinct counterexamples | median worst / random-median error | broken immediately |
|---|---|---|---|---|
| brainir_state_v1, effect | 47 of 48 (one system cannot be searched: the model abstains on every event kind) | 2,558 | 2,357 | **9** |
| lin_dmdc_t, effect | 48 of 48 | 2,414 | 1,048 | 3 |
| brainir_state_v1, post | 39 of 48 | 698 | 31 | 3 |
| lin_dmdc_t, post | 41 of 48 | 729 | 23 | 3 |

The locked method's median effect error on random protocols is moderate: 0.57 (median over systems), against 0.70 for the
comparator. Its worst cases, however, are extreme: effect errors of 10^3 to 10^9 on searched protocols, where the model predicts
huge spurious effects. Such protocols are easy to find, and on 9 systems they appear almost immediately (the comparator: 3).
Answer to "can the counterexample search break it immediately?": yes, on 9 of 48 FINAL systems for the interventional error, and
on 3 of 48 for the post-event error.

## 10. Ablations (goal4 sections 84, 85 criterion 40)

The ablations switch off one component of the locked method at a time (its own `ablate` switches), with paired differences
against the full method over the compressible systems (median [system-bootstrap 95 % CI]).

**Dev suite** (development data, 15 switches x 48 systems; `research/phase3/ablations/ablations_dev/`; $24):
- `event_calibration`: calibrated per-kind event gains and silencing mechanism replaced by raw mechanisms. Held-out C worsens by
  +0.26 [0.10, 0.60], and "compact" verdicts fall from 8 to 3. This is the component that carries S2.
- `nn_dim_rule`: the rebuilt plateau tolerance replaced by ks_sindy's rule. The exact-k rate falls by 0.15 [0.30, 0.02]. This is the
  component that carries S6.
- `fold_repeats`, `nested_selection` and `sparsity` lower the exact-k rate (-0.11, -0.09, -0.07), with CIs that include 0.
- `delays` raises it (+0.09, CI includes 0).
- Every other switch leaves every median at 0: on most systems the variant produces the same model, because the switch acts only
  where its condition fires. Examples are `abstention` (it changes flags only), `domain_clip` (the latent box is rarely active) and
  `sharing` (the shared law is never supported).

The FINAL-suite ablations (the primary, unbiased ones) are reported in section 10.1.

## 11. The hidden real test (generated after the lock) and its numerical checks

The hidden test was generated once, after the method lock, from the committed salt, by the frozen generator.
- **Contents:** 3,360 trajectories (10 systems; every intervention with its counterfactual twin; held-out targets, group silencing,
  out-of-distribution input and weight noise) and 1,920 microstate restarts. 1.59 GB.
- **Where it ran.** On Modal, only on hosts without AVX-512 (`scripts/p3/hidden_gen_gate.py`, LOG P3-D25 / P3-D26), with 32 GiB
  containers. The salt never left the machine: protocols are built locally and carry only derived seeds. Records and the dataset
  went to the eval volume, and the local copy was downloaded with an end-to-end sha256 check.
- **Why gated.** After the OpenBLAS pin was dropped, AVX-512 hosts ran other BLAS kernels: 13 of 20 public records were not
  reproduced bit for bit on the ungated path, against 60 of 60 on the gated path.
- **Cross-platform check.** 1,727 of 1,764 hidden trajectories are identical to records a stopped local (Windows) run had produced.
  The other 37 differ where the adaptive solver's step sequence differs between Windows and Linux (the documented real-engine
  tolerance).
- **Determinism of the generating platform.** 83 of 83 re-simulated hidden protocols, including the 20 known to differ from the local
  run, are bit-identical to the stored records. Every trajectory, twin and restart therefore comes from one platform that reproduces
  itself exactly.

## 12. Failures, incidents and deviations (all logged; none hidden)

**Method failures (counted, never retried or fixed after the lock).**
- brainir_state_v1's leave-one-implementation-out ADAPTATION fits crash when its internal sharing test has rejected sharing, because
  the source model then holds independent laws of different k:
  - 7 of 7 in round 3 (heldout);
  - 4 in the FINAL confirmation;
  - the corresponding Level C fits (section 13).
- The partial-sharing mode is not implemented (NotImplementedError), so the cross-connectome model (4) fails by design.
- On one FINAL system the model supports no event kind, so its counterexample search had nothing to search.

**Infrastructure incidents (re-run or worked around, with logs kept).**
- Transient DNS / SSL failures of the Modal client crashed tournament drivers. They were re-run over cached fits, and a hung
  duplicate driver was killed.
- Two parts ran under the broken execution re-lock 1 and are archived as invalid.
- Twice, Claude Code stopped background work for low local memory:
  - the memory-capped restart;
  - the sequential plan approved by the user.
- The final-suite ablations were aborted after 8 minutes, before any result, and re-run. The Modal workspace runs at most about 100
  containers at once, and they competed with the critical path.
- The gated tar step of the hidden-data generation looped on one warm AVX-512 container. It was finished with the frozen tar and a
  verified transfer.

**Deviations from the runbook (execution only, decided before the affected results existed).**
- Hidden real data were generated on Modal with a host gate instead of locally (P3-D25, P3-D26).
- Level C ran through a gated per-size scheduler (P3-D27).
- The method-lock tool stores the developer's full notes instead of the first 20,000 characters.
- The confirmation ran as 13 parallel parts, merged.
- One store-index repair: orphaned line fragments from concurrent appends, records intact, backup kept.

**Reproducibility finding.**
- On Modal hosts with AVX-512, the locked method's fits are not reproducible run to run: the same public fit gave the same k but a
  different delay configuration.
- Gated hosts reproduce it exactly (timing fields aside).
- The Level B rounds and the FINAL confirmation ran on mixed hosts. Their numbers are one realisation; a re-run could flip
  configuration choices on some systems. Level C and the hidden data ran only on gated hosts.

## 13. The final algorithm: BrainIR State v1 (brainir_state_v1; locked)

Source: `research/phase3/METHOD_NOTES.md` (the developer's notes, locked) and `phase3/src/brainir_state/methods/brainir_state_v1.py`.

**Plain English.** From the recorded population activity x and the input u, the method:
1. builds causal features: the current activity and, where it helps, delayed copies;
2. finds a small number k of linear combinations of them that best predict the future readout and the future population (a
   reduced-rank "predictive basis");
3. fits a sparse polynomial law of motion for those k coordinates by bagged sparse regression (E-SINDy), and a polynomial readout;
4. represents interventions as instantaneous or continuous pushes on the latent state, through the encoder's current-sample
   weights. Their per-kind gains are calibrated on training interventions, with "no effect" as a fallback, and the method abstains
   on kinds it has no calibrated evidence for;
5. picks k by a generic plateau rule on held-out validation trajectories, and abstains ("no compact state") when k is too large for
   the observed population, when the error never plateaus, when the fit is poor, or when the latent explains less than half of
   what the input alone leaves unexplained.

**Mathematical formulation.** Per system, with x~, u~ standardised and a model grid of about T/400 steps:
- **encoder:** z_t = (f_t - mean f) C_k. Here f_t = [x~_t, x~_{t-l_1}, ..., x~_{t-l_m}] are causal delay features, and C_k holds the
  leading k columns of the reduced-rank ridge map from f to the future targets [y~_{t+h}, P x~_{t+h} / 4], with h up to T/4 and P
  the top-16 PCs. Future-input summaries are partialled out of both sides. The encoder never sees y except as a regression target;
- **dynamics:** z_{t+1} = z_t + Theta(z_t, u_t) Xi, where Theta holds the control-affine monomials of degree <= p (at most 60
  terms). Xi is fitted in integral form over windows of T/100 steps by sequential thresholding, and E-SINDy keeps the terms with
  bootstrap inclusion probability >= 0.6. Rollouts are confined to the training latent box, widened by its span;
- **readout:** y_t = ridge regression on the monomials of (z_t, u_t) of degree 1 or 2;
- **interventions:**
  - a kick is z <- z + g_kick (dx / sd) C_0;
  - a current adds z <- z + g_cur (gamma I / sd) C_0 per step;
  - silencing removes the silenced units' outgoing couplings, from a ridge estimate of the microscopic one-step map, or clamps them
    to rest;
  - the gains g in {0, 0.25, 0.5, 1} are chosen on training interventions;
- **objective:** least squares throughout (no gradient training in an independent fit). Model selection (k, delays, degree,
  threshold, readout degree) minimises the open-loop window NMSE of the readout on validation trajectories.

**Latent dimension rule (generic, validation data only).**
- Sweep k over (1, 2, 3, 4, 5, 6, 8), extended to (10, 12, 16) while the error still falls.
- Choose each k's configuration on one half of the validation units and score it on the other (nested).
- Compute e* = min_k mean error from a cross-fitted reference, and set tol = max(0.1 e*, 0.005).
- Take k = the smallest k >= k_min with error <= e* + tol, where k_min = 2 if the training data oscillate under constant input,
  otherwise 1.
- A range from one-sided paired bounds is reported (descriptive). k is never set by hand.

**Not implemented:** lifting of latent interventions to neural interventions (`lift()` returns nothing), and partial sharing.
Shared fits use ks_share's joint training and return the shared law only if an internal held-out non-inferiority test supports it.
