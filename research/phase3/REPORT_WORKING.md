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

($ROOMS = the directory holding the rooms on the development machine.)

| room | purpose | agents |
|---|---|---|
| `$ROOMS/BrainIR_p3clean` | method development (5 family developers, then the composer) | m_lin, m_ks, m_nn, m_cb, m_sd, composer |
| `$ROOMS/BrainIR_p3bench` | synthetic benchmark generator | p3bench_author |
| `$ROOMS/BrainIR_p3lit` | methods-only literature review (filtered web access) | p3lit |
| `$ROOMS/BrainIR_p3reviewG` | review G: new adversarial trap families | review_g |
| `$ROOMS/BrainIR_p3regen` | regeneration of Phase 2 candidates (script only, no agent) | — |

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
regenerated in `$ROOMS/BrainIR_p3regen` as follows:
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

Frozen before method development: `benchmarks/state_discovery_v1/PROTOCOL.md`, `BENCHMARK_LOCK.json` (version 1: 81 files, 24
dataset entries), tag `state-discovery-benchmark-v1` (re-locked once before any use, research/LOG.md section 11.3). The lock in force
since the method lock is version 3 after two execution-only re-locks (97 files, 27 dataset entries; tag
`state-discovery-benchmark-v3-relock2`).

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
- the true-latent reference reaches "compact causal state discovered" on 2 of 45 dev systems, plus 1 in the separate category
  "microstate equivalence untestable". It is partially supported on 28 and fails the interventional condition on 41;
- the full-state ceiling is never compact with a testable E.

The verdict counts barely move at the CI ends of any tolerance. A candidate's verdict counts must be read against this reference
distribution.

### 4.2 Benchmark version 3: the pre-lock reviews A-D, and the correction before the method lock

Four independent pre-lock reviewers examined the composed candidate (brainir_state_v1) and benchmark version 2 on public data:
A (system identification), B (causal inference), C (representation learning) and D (computational neuroscience)
(`research/phase3/reviews/{A,B,C,D}_prelock.md`). They found 7 blockers and 19 major issues. Every evaluation fix went into
**version 3** (tag `state-discovery-benchmark-v3`, 2026-09-25). At that point no method was locked, no method had been fitted or
evaluated on the FINAL suite, and no hidden real data existed. (One orchestrator precompute of k-independent reference controls had
touched 2 of the 48 FINAL systems and was stopped; its 4 cache files use a superseded key and are never read. No method was involved.
This was found by post-lock review L; see `research/phase3/HIDDEN_EVALUATIONS.md`, errata.) Method findings went to the developer as generic requirements only. The mapping of every
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
  projections pass "closed" on 24 % of the dev systems (11 of 45, Wilson 95 % interval about [0.14, 0.39]; one more system would
  have crossed the 25 % threshold of the wording rule) and the true latent on 80 %. A PCA latent with one dimension too few passes
  on 17 % (5 of 29): a latent that misses a dimension passes "closed" about one time in six. The closure gap does not enter the
  verdict (tau_gap is null).
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

The true-latent reference reaches "compact causal state discovered" on 2 of 45 dev systems plus 1 with microstate equivalence
untestable (a separate category), partially supported on 22, not supported on 20. PCA-k reaches "partially supported" on 6, random-k
on 2.

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

**Level B round 1 (pre-registered pilot, 16 heldout systems, no shared fits).** Run on Modal in 74 min (job-record estimate about
$11). By mean rank (S1-S7; version-2 scores, as the round was decided), the top 10 survive:

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

**Level B round 2 (all 48 heldout systems, G seeds, sharing groups and nulls with leave-one-out).** Run on Modal in 70 min
(job-record estimate about $26). The table shows version-2 scores, as the round was decided; `research/phase3/tournament/RERANK_V3.md`
rescores rounds 1-3 under the version-3 profile rules (descriptive).

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
- G4, a 9-stage delay chain: 3 of 5 claim a compact causal state with k = 3-4; lin_dmdc's verdict is the separate category
  "compact causal state discovered (microstate equivalence untestable)" with k = 14;
- G10, a non-compressible system that looks low-dimensional: lin_falds's verdict is "compact causal state discovered (microstate
  equivalence untestable)" (k = 10); only lin_dmdc declares no compact state;
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
relaunches after network failures and the composer's late part. Its job-record estimate is about $25.7 (48.7 container-hours;
section 22 gives the billed amounts):
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
- leaving out one profile component at a time, it stays first in 5 of 8 cases. Its first place depends on prediction (S1), held-out
  intervention fidelity (S2) and exact dimension (S6): without S1 it falls to 4th (mean rank 5.43; lin_falds first, 4.86); without
  S2 it ties for first with lin_dmdc_t (5.57) and is placed 2nd by the tie-break; without S6 it is 3rd;
- on S1-S5 alone (the pre-registered descriptive ranking) it leads by 0.2 of a mean rank: 4.6 against lin_dmdc_t 4.8 and
  lin_subspace 5.0;
- `research/phase3/tournament/RERANK_V3.md` (descriptive): rescoring the version-2 round-3 records (the composer's candidate before
  its version-3 changes) under the version-3 profile rules would have ranked lin_subspace first (P(rank 1) 0.52 against 0.24).

The selection was therefore fragile, and section 8 shows it did not replicate.

**Comparator.** The comparator rule ranks the baselines on S1-S5 over the fixed compressible list, with its own eligibility
(failures on that list at most 10 %, Markov / rollout-consistency check passed on at least 90 %). Its pool has 8 baselines:
ks_hankel and ks_hankel_t pass this rule although they are ineligible for the tournament ranking (their shared and leave-one-out fits
failed), and nn_aelin, nn_aelin_t, nn_rssm and nn_seqbottleneck fail the Markov check on more than 10 % of the systems. lin_dmdc_t is
first. Without the two ks_hankel variants, lin_dmdc_t and lin_pcadyn tie at mean rank 3.0 and lin_dmdc_t wins the pre-registered
tie-break (fewer transition parameters: 15 against 26), so the choice does not change. lin_dmdc_t is lin_dmdc with its wall-clock
branch removed (the tuner's determinism-only variant): identical k and verdicts on all 46 systems and profiles equal to about 1e-14.
The order between the two was set by float-level differences and has no consequence; the deterministic variant is the one the
protocol's determinism rule asks for.

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
- At the lock, no method had been fitted or evaluated on the FINAL synthetic suite, and no hidden real data existed (self-audit I9;
  the stopped reference-control precompute on 2 FINAL systems, section 4.2, involved no method, and self-audit I9 cannot see it).
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
The per-part directories are `final_b_<method>/`, merged in `research/phase3/tournament/final_b/`. Its job-record estimate is about
$54.8 (section 22 gives the billed amounts), and nothing was selected on this suite.

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
unbiased FINAL suite it ranks third (P(rank 1) = 0.25, rank interval [1, 8]) behind the comparator and its twin, and it is also third
on S1-S5 alone (mean ranks 2.5, 3.3 and 3.6). Leaving out one profile component at a time, it is never first: 4th without S1, 5th
without S2, 2nd without S3, 4th without S4, 4th without S5, 3rd without S6, 2nd without S7 and 3rd without S8. The pattern is
consistent with the winner's curse of a narrow selection.

**Against the comparator, paired over the 46 compressible systems** (method minus comparator; median difference [system-bootstrap
95 % CI]; self-audit Q15 and `research/phase3/reviews/POSTLOCK_NUMBERS.json`):
- **significantly better on prediction:** S1 -0.30 [-0.57, -0.07] (profile medians 0.997 against 1.34; it is the only method near
  the full-state bound);
- **significantly better on exact k:** 27 against 16 of 46 (14 systems exact only for the method, 3 only for the comparator; exact
  McNemar p = 0.013; paired rate difference 0.24 [0.09, 0.41]);
- **no significant paired difference** on held-out C (S2: +0.001 [-0.10, 0.09]), residual microstate gain (S3: +0.0004 [-0.0012,
  0.027]), microstate equivalence (S4) or latent recovery (S5: -0.0001 [-0.0024, 0.0010]; the pre-registered K non-inferiority test
  is not passed, Holm p 0.30; superiority Holm p 1.0). The profile medians (S3 0.031 against 0.014, S5 0.987 against 0.991) are
  unpaired and show no significant difference;
- **abstention** (S7 = (recall + 1 - false-alarm rate) / 2; a profile difference driven by recall on the 2 controls, partly offset
  by fewer false alarms): recall 1 of 2 non-compressible controls against 2 of 2; false alarms on 2 % of the compressible systems
  against 28 %; confident-wrong 52 % against 33 %;
- S2 compares the method's C on the pairs it supports with the comparator's C on all pairs: the method abstained on some held-out
  pairs of 14 of the 46 systems.

**The locked method on the FINAL suite (46 compressible systems):**
- verdicts: "compact causal state discovered" on 17; the separate category "compact causal state discovered (microstate equivalence
  untestable)" on 2 (syn-5501045d59 and syn-fe069050cb: matched pairs not close); "partially supported" on 12; "not supported" on 15;
- "compact" certifies sufficiency on the tested domain, not k. 5 of these 19 verdicts have the wrong k: 4 over-estimated (nuisance
  trap A: k = 8 against 1; transient trap J: 3 against 2; parameter trap H: 2 against 1; one untrapped system: 2 against 1) and 1
  under-estimated (5 against 6). "Compact" is the registered k <= max(1, N_observed / 5), not minimality. Two of the 19 are not
  state-mediated: trap A (latent recovery min R^2 0.12; C - C_scrambled [-0.40, 0.28]) and the stimulus-copy trap D ([-0.66,
  0.003]);
- conditions met: predictive 32, interventional 24, closed 36, microstate-equivalent 34 (E testable on 40), state-mediated
  intervention effects 27. "Closed" = D micro-gain and history-gain upper CIs within tau_D / tau_H, and markov_ok. Its power on the dev
  calibration is 80 % for the true latent, 24 % for random-k projections and 17 % for PCA with one dimension too few (section 4.2);
  here one system passes "closed" with k = 5 against a true 6;
- intervention scope: the synthetic held-out intervention types are additive compositions of single-neuron interventions acting
  through a low-rank population signal (PROTOCOL.md section 2.2). The interventional results are scoped to held-out targets and such
  compositions. They are not evidence of type generalisation in circuits with thresholds and rectification: on the rate-model
  systems, which rectify, no interventional claim holds (section 14). On 4 systems the interventional condition fails only because
  pairs were abstained on;
- kick-clip sensitivity (pre-registered, PROTOCOL.md section 2.2): 22 of 46 systems have held-out pairs with clipped kicks (1-9
  each); without them S2 moves from 0.483 to 0.456. No conclusion changes;
- the Markov / rollout-consistency check passes on 46 of 46. Its event-free restart, decoy and readout-consistency parts show zero
  inconsistency everywhere. The restart after held-out events ran on 44 of 46 systems and was untested on 2, where the model abstained
  on every held-out event; markov_ok counts an untested events check as passed;
- dimension (seed 0): exact k on 27, under-estimated on 3, over-estimated on 16. Within the Hopf implementation group (true k = 2 in
  all four) it selects k = 2, 6, 6 and 2: the selected dimension depends on the physical implementation;
- latent recovery K (min R^2 both ways): median 0.987, mean 0.86; below 0.9 on 13 of 46 and below 0.5 on 5 (lowest 0.12, 0.15 and
  0.16);
- abstention: on 1 of the 2 non-compressible controls; on the other it returned k = 3 without abstaining (verdict "not supported").
  1 false alarm among the 46 compressible systems (2 %). On 52 % of all systems it neither abstains nor meets the interventional and
  closed conditions (the "confident-wrong" rate of family L);
- seeds (G, 8 systems x 3 seeds): the same k on 4 of 8; latent agreement (r2_min_mean) 0.69-1.00; prediction disagreement up to 1.14
  NMSE (syn-146831129f). The dimension rates above are seed-0 values;
- sharing: neither implementation group is supported. The Hopf group is "untestable" because the method's own adaptation code
  crashed, not because of a sharing test; the gated-integrator group is rejected. All 3 unrelated pairs are rejected (S8 = 0.5). In
  every group the returned "shared" model equals the independent models (parameters 8,066 = 8,066 and 922 = 922);
- failures: 4 of 108 fits (the leave-one-out adaptation fits, the known defect) and 0 of 99 evaluations;
- fit time: 24,088 s in total (median 190 s per fit) against 1,835 s (11 s) for the comparator, about 13 times as much, for
  significant gains on prediction and exact k only.

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

The locked method's typical effect error on random protocols is moderate: 0.57 (median over systems), against 0.70 for the
comparator. Its worst effect errors per system range from 12 to 9.8 x 10^8 (median worst / random-median 2,357).

**What the extreme errors are** (the job rows, `research/phase3/reviews/POSTLOCK_NUMBERS.json`). The effect error is the ratio of the
predicted-effect error to the true effect's energy, so it explodes when the true effect is near zero:
- on 36 of 47 searchable systems the worst protocol's true-effect energy is below 1 % of a typical (random-protocol median)
  protocol's; among all 4,048 candidates, 39 % have such a near-null true effect, and 74 % have a numerator at most 10 times the
  typical one;
- the post-event readout is predicted with NMSE < 1 in 77 % of the candidates.

So most extreme ratios measure a small spurious predicted effect against a near-null true effect (silencing near-silent neurons,
clipped kicks), not a gross failure of the rollout; the comparator's candidates look the same (46 % near-null).

**Where they are.** Counterexamples occur inside and outside the public protocol families: 20 % of the candidates lie entirely inside
the public families, on 44 of 47 systems. Per protocol, the candidate rate is 0.08 inside and 0.14 outside the families, and 0.155
with a perturbed initial state against 0.111 from nominal states.

**Missing state.** The searches did not isolate a specific missing state variable. The higher candidate rate from perturbed initial
states (about 1.4 times) is weak evidence that off-manifold initial conditions carry state the latent lacks; the near-null effects
point to a mis-scaled event read-in rather than to a missing dimension.

Answer to "can the counterexample search break it immediately?": on 9 of 48 FINAL systems for the effect error (the comparator: 3),
and on 3 of 48 for the post-event error (one system cannot be searched).

## 10. Ablations (goal4 sections 84, 85 criterion 40)

The ablations switch off one component of the locked method at a time (its own `ablate` switches), with paired differences
against the full method over the compressible systems (median [system-bootstrap 95 % CI]).

**Dev suite** (development data, 15 switches x 48 systems; `research/phase3/ablations/ablations_dev/`; job-record estimate $24):
- `event_calibration`: calibrated per-kind event gains and silencing mechanism replaced by raw mechanisms. Held-out C worsens by
  +0.26 [0.10, 0.60], and "compact" verdicts fall from 8 to 3. This is the component that carries S2.
- `nn_dim_rule`: the rebuilt plateau tolerance replaced by ks_sindy's rule. The exact-k rate changes by -0.15 [-0.30, -0.02]. This is
  the component that carries S6 on the dev suite.
- `fold_repeats`, `nested_selection` and `sparsity` lower the exact-k rate (-0.11, -0.09, -0.07), with CIs that include 0.
- `delays` raises it (+0.09, CI includes 0).
- Every other switch leaves every median at 0: on most systems the variant produces the same model, because the switch acts only
  where its condition fires. Examples are `abstention` (it changes flags only), `domain_clip` (the latent box is rarely active) and
  `sharing` (the shared law is never supported).

### 10.1 FINAL-suite ablations (primary; hidden, logged; `research/phase3/ablations/ablations_final/`)

This run is the pre-registered primary ablation analysis: the only data that neither selected nor tuned the method. It covers 15
switches x 48 systems, reusing the confirmation's fits of the full method, in 7,154 s (job-record estimate $27.8). An earlier attempt
was aborted before any result, for Modal scheduling, and re-run; both are logged. Verdict counts below are "compact" + "compact (E
untestable)"; the full method has 17 + 2. The CIs are system-bootstrap 95 % intervals of the median paired difference, unadjusted
over 15 switches x 6 components (descriptive).
- **`event_calibration`:** held-out C worsens by +0.30 [0.13, 0.47], and "compact" verdicts fall from 17 + 2 to 9 + 1. It is the
  only component whose median CI on S1-S5 excludes 0.
- **Dimension components.** The dev-suite effect of `nn_dim_rule` (-0.15 exact-k rate) does not replicate here: -0.04 [-0.15,
  0.07].
  - `nested_selection` -0.07 [-0.20, 0.07]; compact 15 + 3;
  - `fold_repeats` 0 [-0.11, 0.11]; compact 16 + 3;
  - `sparsity` +0.07 [-0.02, 0.15]; compact 16 + 2;
  - `delays` +0.07 [0, 0.13] (the CI touches 0): removing the delay features, if anything, helps the exact-k rate. "Compact" verdicts
    fall to 13 + 2 without delays.
- **All other switches leave every median at 0,** because their conditions rarely fire on this suite or (sharing) the shared law is
  never supported. They still change some verdicts or flags:
  - `abstention` (never abstain): S7 falls from 0.74 to 0.50 (abstention recall 0.5 to 0);
  - `draw_folds`: compact 15 + 2; `grid_extension`: 17 + 1; `domain_clip`: partially supported 12 to 10, not supported 15 to 17;
  - `sharing_test`: 3 evaluation failures;
  - `esindy`, `input_floor`, `oscillation_check`, `sharing`: no verdict change.
- **Mean-based paired differences** (descriptive, unadjusted; the stored `ablations_final/SUMMARY.json`, `mean_ci95`) exclude 0 for
  `draw_folds` S1 (-0.14 [-0.33, -0.004]), `sparsity` S5 (+0.027 [0.0015, 0.072]) and `nn_dim_rule` S3 (-0.031 [-0.066, -0.0013]).
  They also exclude 0 at float level (about 1e-14) for `sharing_test` S1 and for S3 of eight switches. (The first correction of this
  paragraph computed S3 from the point estimate of the D micro-gain instead of the pre-registered max(0, upper CI) and wrongly
  rejected review Y's `nn_dim_rule` interval; verification review V found the error.)
- **Reading.** By the pre-registered medians, only the calibrated event machinery measurably matters on unbiased data. Replacing the
  rebuilt dimension rule does not change the exact-k rate measurably (-0.04 [-0.15, 0.07]). Descriptively, three components slightly
  hurt, unadjusted over 90 CIs: without the rebuilt dimension rule the residual microstate gain S3 is lower (-0.031); with
  trajectory folds instead of draw folds prediction S1 is better (-0.14); and without sequential thresholding latent recovery S5 is
  higher (+0.027).

## 11. The hidden real test (generated after the lock) and its numerical checks

The hidden test dataset was generated once, after the method lock, from the committed salt, by the frozen generator.
- **Earlier local starts.** Before the Modal run, three local generation starts were stopped: at 01:46Z, 01:48Z and 05:46Z on
  2026-09-26 (the third was not recorded before review L). They left 1,761 salt-derived trajectories in the local store and wrote no
  dataset. The cross-platform check below compares the Modal dataset with these local records.
- **Fake-salt records.** A pre-lock dry run with a FAKE salt had also left 126 records labelled "hidden" in the store. None matches
  the committed salt or is in the dataset. They were moved to a quarantine directory after post-lock review L (m1).
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
  run, are bit-identical to the stored records. Every trajectory, twin and restart of the hidden test therefore comes from one
  platform that reproduces itself exactly. The one exception to "hidden draws only on gated hosts" is the pre-registered hidden-draw
  counterexample sweep after Level C (section 16), which simulated its own hidden-draw protocols locally on the development machine
  (Windows), where 37 of 1,764 records differ as above.

## 12. Failures, incidents and deviations (all logged; none hidden)

**Method failures (counted, never retried or fixed after the lock).**
- brainir_state_v1's leave-one-implementation-out ADAPTATION fits crash when its internal sharing test has rejected sharing, because
  the source model then holds independent laws of different k:
  - 7 of 7 in round 3 (heldout);
  - 4 in the FINAL confirmation;
  - 6 of the corresponding Level C fits (section 14).
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
- Timing of the execution decisions (post-lock review L, m5):
  - P3-D27 was committed at 07:35Z, after the Level C launch at 07:29:51Z; the scheduler file was final at 07:28Z and is
    byte-identical to the committed version.
  - Both gate decisions (P3-D26, P3-D27) were made after the orchestrator had read the Level B confirmation results, on public
    evidence only: 13 of 20 public protocols not bit-identical on the ungated path, 60 of 60 on the gated one, and public-fit repeats.
  - The gate restricts fits to non-AVX-512 hosts. Host class changes the locked method's delay configuration (below), whereas
    PROTOCOL.md section 10 pre-registered last-digit differences only.

**Post-hoc analyses after the post-lock reviews (logged; descriptive; no method change).**
- The synthetic family H extraction from the stored FINAL fits (section 17).
- The lifting test of the locked v1 through its encoder on the FINAL suite (section 19). It ran locally on 3 workers, in about 2
  minutes.

**Process findings of post-lock review L (no property violated; details in `research/phase3/reviews/POSTLOCK_L.md`).**
- FINAL reference-control precompute before the lock, involving no method (section 4.2).
- Records of the fake-salt dry run and the stopped local hidden-generation starts (section 11).
- Hidden-evaluation log rows appended retrospectively, with two wording errata.
- Snapshot provenance. The post-lock records do not all name the method snapshot they ran. `scripts/p3/postlock_provenance.py`
  (`research/phase3/POSTLOCK_PROVENANCE.json`) now records it:
  - the locked directory (Modal methods key 2f4ad2d3ddf2df33; 30 of 30 LF hashes equal METHOD_LOCK.json; 19 files have CRLF line
    endings in the working tree, so raw hashes differ from the lock's LF hashes while the code is identical);
  - all 13 FINAL part snapshots are byte-identical to it.
- Tool gaps:
  - BENCHMARK_LOCK.json's `git_tag` field still names the version-3 tag, the root cause of the I3 failure;
  - `method_lock_p3.py --check` skips a missing input silently and checks neither the tag nor the environment (review L checked
    both by hand: they match);
  - self-audit I6 / I7 scan two rooms only (review L scanned the others: clean);
  - the post-lock room check fails only on the reviewers' own `__pycache__` files.
- Stale documents: LEAKAGE_POLICY.md section 3.1's "Volumes" bullet and the runbook's Level C text. Both are annotated, and a retention
  decision for the hidden data on the eval volume is recorded (LEAKAGE_POLICY.md section 3.1, errata).

**Reproducibility finding.**
- On Modal hosts with AVX-512, the locked method's fits are not reproducible run to run: the same public fit gave the same k but a
  different delay configuration.
- Gated hosts reproduce it exactly (timing fields aside).
- The Level B rounds and the FINAL confirmation ran on mixed hosts. Their numbers are one realisation; a re-run could flip
  configuration choices on some systems. Level C and the hidden test data ran only on gated hosts (the local hidden-draw
  counterexample sweep excepted, section 11).

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

**Not implemented:** lifting of latent interventions to neural interventions (`lift()` returns nothing), and partial sharing. Its
latent interventions are tested through an evaluator-side lift built from its own encoder (post hoc; section 19).
Shared fits use ks_share's joint training and return the shared law only if an internal held-out non-inferiority test supports it.

## 14. Level C: the connectome-constrained rate-model simulations (hidden test, run once; `research/phase3/level_c/01/`)

**What the "real" systems are.** They are simulations of a deterministic first-order threshold-linear-tanh rate model on
connectome-derived weights:
- neuron parameters (time constants, gains, thresholds, maximal rates) are assumed and drawn per trajectory, never read from anatomy;
- there are no synaptic or adaptation dynamics, no spiking and no noise;
- kicks are absolute rate offsets that the engine clips at 0 Hz.

They are not recordings, and nothing below is a statement about the animal.

The tolerances were calibrated on synthetic dev systems, whose conditions differ: dt 10 ms against 1 ms here, one parameter draw per
trajectory, absolute-Hz kicks, non-additive operators and a pooled normaliser. The real verdicts are therefore CONDITIONAL on the
synthetic calibration (PROTOCOL.md section 6), and the power of "closed" on the real systems is not calibrated.

**Design (PROTOCOL.md sections 7-8; frozen driver `scripts/p3/level_c.py`).**
- **Fits:** the locked method on the 10 real systems with seeds 0-4 (G), plus 5 fits on seeded half-samples of the training data
  (the data arm of G, descriptive); the comparator lin_dmdc_t with seed 0; per-network shared fits with leave-one-implementation-out
  adaptation (I); cross-connectome models on the full networks (J): net1 + net2 (independent reconstructions) and, reported apart,
  net1 + net3 (the same reconstruction).
- **Evaluation:** on the hidden test. Verdicts use the seed-0 fits and the primary 250 ms horizon / window.
- **Pre-registered primary family:** 13 paired comparisons against the comparator (A, C, D, E per full network, and K on the
  synthetic FINAL suite), Holm-corrected, with non-inferiority margins; two-sided differences as the secondary family.
- **Scale:** 163 fits and 128 evaluations. 5,647 s wall on Modal (gated scheduler, P3-D27), under a 100-container workspace limit.
  The critical path was the joint fits (57 min for the first stage).
- **Failures, all in the method's own code:**
  - 2 partial-sharing fits (not implemented);
  - 6 leave-one-out adaptation fits (the known defect).

**Lineage.** net1 and net3 are two builds of ONE reconstruction (R1); net2 is an independent reconstruction (R2). The mechanisms of
one network form one mechanism family (net1: 2 variants, net2: 3, net3: 2). Counts are given per reconstruction and family where
it matters, and net1 and net3 are never counted as two confirmations.

**Verdicts and conditions per system (the frozen verdict rule).** N_obs = observed neurons; in brackets, those peaking above 1 Hz
in the public nominal training trajectories (descriptive; a proxy for PROTOCOL.md's probe set; computed by
`scripts/p3/postlock_numbers.py` from `data/phase3/real_public`, recorded in `research/phase3/reviews/POSTLOCK_NUMBERS.json`). k = the seed-0 fit's k; seeds 0-4
and their modal k in brackets.

| system | lineage | N_obs (> 1 Hz) | brainir_state_v1 k (seeds; modal) | the method's own abstention | verdict | predictive | closed | microstate-equiv. | lin_dmdc_t: k, verdict |
|---|---|---|---|---|---|---|---|---|---|
| net1 full | R1 | 197 (101) | 2 (2,2,2,3,2; 2) | none | not supported | yes | no | no | 16, not supported |
| net1 mechanism a | R1, family net1 | 3 (3) | 2 (2,2,2,6,6; 2) | no compact state: k > N/5 | not supported | no | no | yes | 3, not supported |
| net1 mechanism b | R1, family net1 | 4 (4) | 3 (3,4,8,8,4; 4 or 8) | no compact state: k > N/5; input floor | not supported | yes | no | yes | 1, not supported |
| net2 full | R2 | 213 (136) | 3 (3,2,2,2,2; 2) | no compact state: input floor (val 0.480 > 0.5 x 0.843) | not supported | yes | no | yes | 64, not supported |
| net2 mechanism a | R2, family net2 | 3 (3) | 2 (2,2,6,2,2; 2) | no compact state: k > N/5; input floor | not supported | no | no | yes | 3, not supported |
| net2 mechanism b | R2, family net2 | 6 (6) | 3 (3,2,2,3,2; 2) | no compact state: k > N/5 | not supported | yes | no | yes | 4, partially supported |
| net2 mechanism c | R2, family net2 | 3 (3) | 5 (5,2,2,2,2; 2) | no compact state: k > N/5 | not supported | no | yes | yes | 3, not supported |
| net3 full | R1 | 211 (101) | 2 (2,2,2,2,2; 2) | none | **partially supported** | yes | yes | no | 64, not supported |
| net3 mechanism a | R1, family net3 | 4 (4) | 3 (3,5,4,3,8; 3) | no compact state: k > N/5 | not supported | no | no | yes | 1, not supported |
| net3 mechanism b | R1, family net3 | 3 (3) | 2 (2,2,2,2,2; 2) | no compact state: k > N/5; input floor | not supported | no | yes | yes | 3, not supported |

Mechanism labels: net1 a = mech:02fa13b8, b = mech:cce0c6c4; net2 a = mech:3aa95ab7, b = mech:3e8f8895, c = mech:6883ab7b; net3 a =
mech:362044b4, b = mech:92614efe.

**The method's own abstentions.** It declared "no compact state" on 8 of 10 systems (all 4 of reconstruction R2; the 4 mechanisms
of R1):
- on net2 full, because its latent explains too little beyond the input;
- on all 7 mechanisms, because k exceeds N_observed / 5 (the mechanisms observe 3-6 neurons), and on 3 of them also by the input
  floor.

It claims a compact state only on net1 full and net3 full, two builds of one reconstruction. A method's abstention is recorded as
such and is never converted into a claim (PROTOCOL.md section 7). The comparator declared no compact state on net2 full, net3 full and
net3 mechanism a.

**Intervention results (held-out C, 250 ms window; 1 = predicting no effect).** On the full networks the held-out families are
H_kick_B, H_pulse_B, H_silence1_B and H_group_silence (120 pairs). On the mechanisms the only held-out type is group silencing (15
pairs), because their H_kick_B / H_pulse_B / H_silence1_B targets are in-distribution there.

| system | lineage | held-out pairs scored / abstained | scope of C | null pairs | n_eff | C [95 % CI] | C over non-null pairs | leave-one-pair-out max | C - C_scrambled [CI]; state-mediated |
|---|---|---|---|---|---|---|---|---|---|
| net1 full | R1 | 60 / 60 | silencing only (every kick and current pair abstained) | 45 | 4.1 | 1.27 [1.03, 1.89] | 1.20 | 1.53 | [-0.043, 0.039]; no |
| net2 full | R2 | 60 / 60 | silencing only | 49 | 1.4 | 0.96 [0.94, 1.02] | 0.95 | 0.96 | [-0.002, 0.005]; no |
| net3 full | R1 | 60 / 60 | silencing only | 47 | 3.9 | 1.04 [1.01, 1.20] | 1.02 | 1.06 | [-0.004, 0.003]; no |
| net1 mechanism a | R1, family net1 | 0 / 15 | interventional condition not met: every held-out pair abstained | | | | | | |
| net1 mechanism b | R1, family net1 | 15 / 0 | group silencing | 0 | 4.9 | 0.91 [0.36, 2.69] | 0.91 | 1.18 | [-4.42, -0.07]; yes |
| net2 mechanism a | R2, family net2 | 0 / 15 | not met: every held-out pair abstained | | | | | | |
| net2 mechanism b | R2, family net2 | 15 / 0 | group silencing | 0 | 2.1 | 0.79 [0.74, 1.13] | 0.79 | 0.86 | [-0.18, 0.02]; no |
| net2 mechanism c | R2, family net2 | 0 / 15 | not met: every held-out pair abstained | | | | | | |
| net3 mechanism a | R1, family net3 | 0 / 15 | not met: every held-out pair abstained | | | | | | |
| net3 mechanism b | R1, family net3 | 15 / 0 | group silencing | 0 | 11.7 | 0.38 [0.21, 0.67] | 0.38 | 0.44 | [+0.015, +0.083]; no (scrambling helps) |

- On every full network the method abstained on all kick and current interventions, both held out (60 of 120 pairs) and
  in-distribution. Its event calibration on the training interventions chose gain 0 ("no effect") for kicks and currents, so it
  declared those kinds unsupported (the seed-0 fit records, extracted in `research/phase3/reviews/POSTLOCK_NUMBERS.json` from the
  git-ignored run directory). It predicted only silencing. **Held-out effects of kicks and currents on the real systems are
  therefore untested for v1.** It abstained on every held-out pair of 4 of the 7 mechanisms: 1 of 2 in the net1 family, 2 of 3 in
  the net2 family and 1 of 2 in the net3 family.
- On no full network does it predict held-out effects better than "no effect": the upper CIs are all >= 1. Most silencing pairs are
  null (below 0.1 % of the effect denominator), so the C values rest on few effective pairs. On net2 full the largest pair carries
  83 % of the denominator (n_eff 1.4). Per readout dimension, one of 9 dimensions carries 83 % of the denominator on net1 and one of
  10 carries 77 % on net3 (PROTOCOL.md section 4 normalisers; the alternative per-dimension normalisers give C 1.12 / 0.99 / 1.00
  with a 1e-3 floor and 1.13 / 0.98 / 1.01 with a 1e-2 floor).
- The effect predictions on the full networks do not depend on the encoded state: C with the pre-event state replaced by the mean
  training state is within 0.003 of C on every full network (net1 1.268 against 1.271, net2 0.956 against 0.954, net3 1.036
  against 1.036), and the CI of C - C_scrambled includes 0.
- The only interventional pass on a real system is net3 mechanism b (group silencing, C 0.38 [0.21, 0.67]). It is not
  state-mediated: replacing z0 by the mean training encoding lowers the error (C_scrambled 0.35). The method declared no compact state
  there, and the system is not predictive.
- **Interventional closure gap** (PROTOCOL.md section 4 C, reported): after held-out silencing, the locked model's rolled-out latent
  is 24.6 (net1), 2.4 (net2) and 31.4 (net3) times further from the encoder's reading of the intervened history than the
  intervened-versus-twin encoding distance. A rollout that ignores the event scores the same (24.4, 2.4, 31.3). The event operator
  does not move z where the encoder puts the intervened state; this is the state-level counterpart of C being about 1. The
  comparator's gaps are 1.09, 1.01 and 1.03.

**Prediction (readout NMSE A at the primary 250 ms horizon; the 100 ms value in brackets).**

| full network | lineage | brainir_state_v1 (k) | full-state reference | input-only | PCA with the method's k | lin_dmdc_t (k) |
|---|---|---|---|---|---|---|
| net1 | R1 | 0.024 (0.024), k 2 | 0.020 (0.0070) | 0.034 | 0.044 | 0.022, k 16 |
| net2 | R2 | 0.51 (0.53), k 3 | 0.48 (0.12) | 0.82 | 0.44 | 0.29, k 64 |
| net3 | R1 | 0.0055 (0.0054), k 2 | 0.0099 (0.0015) | 0.012 | 0.0069 | 0.0073, k 64 |

- The predictive condition (A below the input-only control and persistence, paired CIs below 0) holds on the three full networks:
  net1 A - input-only -0.0092 [-0.020, -0.0027]; net2 -0.30 [-0.58, -0.11]; net3 -0.0067 [-0.0077, -0.0056]. These are
  per-system verdict conditions with unadjusted CIs, not results of the Holm family (all p <= 0.003, so they would survive a Holm
  correction over the 6).
- The full-state reference is not an upper bound at 250 ms on net3 (0.0099 against 0.0055); at 100 ms it is (0.0015).
- **PCA with the method's dimension** (paired over the same hidden trajectories; method minus PCA-k; unadjusted per-system CIs,
  descriptive). At the primary 250 ms horizon:
  - reconstruction R1: the locked method is significantly better on both full networks (net1 -0.019 [-0.033, -0.011]; net3
    -0.0013 [-0.0019, -0.0009]) and on 3 of its 4 mechanisms (net1 mechanism b, net3 mechanisms a and b); no clear difference on
    net1 mechanism a;
  - reconstruction R2: PCA-k is significantly better on net2 full (+0.069 [0.010, 0.123]) and net2 mechanism a (+0.028 [0.007,
    0.052]); the locked method on net2 mechanism c; no clear difference on net2 mechanism b.
  At 10 ms PCA-k is better by point estimate on 1 of the 10 systems and significantly better on none.

**What is and is not supported.**
- **Predictive:** the condition holds on the full systems of both independent reconstructions. The method itself claims a compact
  state only on net1 full and net3 full (two builds of R1). On net2 full (R2) it declared that no compact state exists: its own
  input-floor rule fails there on the hidden data too (A 0.514 > 0.5 x input-only 0.817 = 0.408), and a PCA latent of the same
  dimension and the comparator predict significantly better.
  - The dimension is fragile: across 5 half-samples of the training data k is 2-8 on net1 full and 2-6 on net2 full.
  - On net3 full k = 2 every time, but the half-sample latents do not agree (r2_min_mean -1.16).
- **Interventional:** not supported on any full network (above).
- **Closed:** net3 full, net2 mechanism c and net3 mechanism b. "Closed" = D micro-gain and history-gain upper CIs within tau_D /
  tau_H, and markov_ok. On the dev calibration a latent that misses one dimension still passes about one time in six (section 4.2).
- **Microstate equivalence:** holds on all 7 mechanisms (both reconstructions) and on net2 full (R2), not on the two R1 full
  networks (net1, net3). On the
  mechanisms k is 50-167 % of the 3-6 observed neurons, so the latent can carry nearly the whole observed microstate and E is nearly
  uninformative there.
- **Markov / rollout consistency:** the event-free restart from the model's own z, the decoy and the readout consistency y =
  readout(z, u) show zero inconsistency on every system, for both methods. The restart after held-out interventions ran only where
  the model predicted events: silencing events on the 3 full networks and 3 mechanisms. It is untested on 4 mechanisms, where the
  model abstained on every held-out event; markov_ok counts an untested events check as passed. No k had to be declared invalid.
- **Dimension and rhythm:** the method's own oscillation check finds a sustained oscillation under constant input in the training
  data of all 10 systems (seed-0 fit records, extracted in `POSTLOCK_NUMBERS.json`), so it imposes k >= 2 everywhere. The comparator selects k = 1 on net1 mechanism b and net3 mechanism a; a
  1-D state cannot represent a sustained rhythm.
  - On the mechanisms, k (2-5) is 50-167 % of the observed neurons (k = 5 for 3 observed neurons on net2 mechanism c): k is not a
    compression of x there.
  - The method's descriptive k ranges (not scored): net1 full [2, 8], net2 full [2, 5], net3 full [2, 2].

**Pre-registered primary comparisons against the comparator (Holm).**
- Non-inferiority is established on 5 of 13: net2 C, D and E; net3 A and C.
- Significant two-sided differences (secondary family):
  - better on net3 A and net3 C;
  - worse on net1 E, net2 A and net3 E.
- The C comparisons are paired on the common pairs, which are the silencing pairs the method scored. There the comparator's C is
  1.10 on net1 (1.50 on all its 120 pairs), 1.05 on net2 and 12.5 on net3 (1.34 on all pairs). By the pre-registered C reporting
  rule, on net2 and net3 the method is "no worse than the baseline on held-out silencing, and neither is better than predicting no
  effect". net3's superiority on C comes from the comparator's large error on those pairs, not from a good C. Non-inferiority on C
  carries no interventional content.
- "Worse on net3 E" is significant, but its margin (0.2 x 3.2e-6 = 6.3e-7) is effectively zero; the absolute difference (1.9e-5) is
  about 1,000 times below tau_E.
- K on the synthetic FINAL suite is not shown non-inferior (difference 0.0065 [-0.040, 0.054], Holm p = 0.30).
- The comparator is high-dimensional on the full networks (k = 16, 64 and 64) where the locked method uses 2-3. It abstained on no
  intervention pair.

**Sharing (I) and cross-connectome dynamics (J); descriptive, in neither Holm family.**
- The method's internal held-out test declined its shared transition law on every network and pair. For example, on net1 its
  shared law had 16 transition parameters against 53 for the independent ones, and it was not non-inferior on held-out validation
  trajectories; on net2 the counts are 34 against 78, on net3 16 against 30. The shared law was therefore never evaluated on hidden
  data. Every returned "shared" model equals the independent models, so the I and J verdicts reflect the independent models and the
  adaptation fits:

| comparison | parameters, "shared" = independent | verdict |
|---|---|---|
| I net1 (full + 2 mechanisms) | 891 = 891 | rejected |
| I net2 (full + 3 mechanisms) | 5,256 = 5,256 | untestable (every leave-one-out fit failed) |
| I net3 (full + 2 mechanisms) | 3,504 = 3,504 | rejected |
| J net1 + net2 (independent reconstructions) | 5,064 = 5,064 | rejected |
| J net1 + net3 (one reconstruction; descriptive only) | 3,897 = 3,897 | rejected |

- **Leave-one-implementation-out** (encoder-only adaptation against a fit from scratch): worse in every computable case.
  - net1: with the full network held out, A +0.38 [0.29, 0.47] and C +79; with mechanism a held out, A +0.017 [-0.002, 0.039] and
    C +0.23 [0.10, 0.31]; with mechanism b held out, A +9.8 and C +30.
  - net3: with mechanism a held out, A +0.12 [0.07, 0.17].
  - All net2 leave-one-out fits failed (the known defect).
- **Between independent reconstructions** (net1 + net2; one pair, one direction: dynamics fitted with net2 and adapted to net1):
  far worse than a fit from scratch, A +4.92 [4.80, 5.04] and C +251 [78, 926].
- **Within reconstruction R1** (net1 + net3; descriptive, never a confirmation), adaptation beats a fit from scratch:
  - on C with net1 held out, -0.17 [-0.62, -0.008], with A tied (+0.0024 [-0.0002, 0.0046]). Both the adapted C (1.05) and the
    from-scratch C (1.22) are above the no-effect value 1, so the advantage is between two predictions that are no better than
    predicting no effect;
  - on A with net3 held out, -0.18 [-0.35, -0.05]; C is not computable there.
- **Partial sharing** (model 4) is not implemented.
- This is a result about v1: it found no support for shared latent dynamics. That is not evidence that the simulated circuits lack
  shared dynamics.

**Reproducibility on the real systems (G: seeds 0-4; the half-sample data arm is descriptive, PROTOCOL.md section 4 G).**
r2_min = min(R^2 a->b, R^2 b->a) of the aligned latents per seed pair; prediction disagreement = readout NMSE between seeds.

| system | lineage | k over seeds | r2_min_mean | worst pair | prediction disagreement (mean) | k over half-samples | half-sample r2_min_mean |
|---|---|---|---|---|---|---|---|
| net1 full | R1 | 2,2,2,3,2 | 0.976 | 0.95 | 0.004 | 2,2,8,2,2 | 0.65 |
| net2 full | R2 | 3,2,2,2,2 | 0.966 | 0.92 | 0.024 | 4,6,2,2,5 | 0.64 |
| net3 full | R1 | 2,2,2,2,2 | 0.546 | 0.12 | 0.0005 | 2,2,2,2,2 | -1.16 |
| net1 mechanism a | R1, family net1 | 2,2,2,6,6 | 0.24 | -0.39 | 0.019 | 4,3,8,6,4 | 0.45 |
| net1 mechanism b | R1, family net1 | 3,4,8,8,4 | 0.72 | 0.57 | 0.084 | 3,4,4,4,3 | 0.88 |
| net2 mechanism a | R2, family net2 | 2,2,6,2,2 | 0.14 | -0.68 | 0.071 | 2,2,2,2,2 | 0.43 |
| net2 mechanism b | R2, family net2 | 3,2,2,3,2 | 0.78 | 0.62 | 0.031 | 2,3,2,2,4 | 0.72 |
| net2 mechanism c | R2, family net2 | 5,2,2,2,2 | 0.73 | 0.33 | 0.005 | 2,2,2,2,2 | 0.64 |
| net3 mechanism a | R1, family net3 | 3,5,4,3,8 | 0.46 | 0.12 | 0.17 | 8,6,8,3,3 | 0.43 (prediction disagreement 55.7) |
| net3 mechanism b | R1, family net3 | 2,2,2,2,2 | 0.96 | 0.90 | 0.018 | 2,2,2,2,2 | 0.93 |

- k agrees across the 5 seeds on 2 systems, net3 full and net3 mechanism b, both of reconstruction R1 (none of R2). It agrees across
  the half-samples on 4: net3 full and net3 mechanism b (R1), net2 mechanisms a and c (R2).
- The seed-0 k is not always the modal k: net2 full 3 against 2; net2 mechanism b 3 against 2; net2 mechanism c 5 against 2; net1
  mechanism b 3 against 4 or 8.
- net3 full, the one "partially supported" system, has a stable k but poorly reproduced latents: r2_min_mean 0.55 over seeds, with
  one pair at 0.12, and -1.16 over half-samples.

## 15. Acceptance criteria (goal4 section 85)

"Met" means the criterion's requirement is fulfilled; a criterion can be met while the method performs poorly on it (then the
result is stated). Where a supporting self-audit check fails, the last column says so (section 21).

| # | criterion | status | evidence | self-audit |
|---|---|---|---|---|
| 1 | Phase 1 benchmark remains frozen | met | `benchmarks/dng100/freeze.py --check` ok | I1 pass |
| 2 | Phase 2 locked method unchanged | met | `scripts/method_lock.py check` OK; nothing under `src/brainir` changed | I2 pass |
| 3 | Main repository integrity passes | met | lock checks, tests | I2 pass (also I1, I4, I10); the benchmark-lock check I3 fails as written (orchestrator note: artefact of the re-lock tags, section 7) |
| 4 | Genuinely clean Phase 3 workspace | met | `$ROOMS/BrainIR_p3clean` from an allowlist (7,542 files), `--check` | I5 pass |
| 5 | PHASE2_REPORT.md cannot enter the clean room | met | builder forbidden list, guards, hash scans | I6 pass |
| 6 | Hidden oracle / evaluation artifacts cannot enter | met | same; transcript audit: 0 forbidden inputs, 0 non-numeric answer tokens | I6, I7 pass |
| 7 | Allowlist machine-readable and audited | met | `CLEANROOM_MANIFEST.json` (hash, source, reason, class per file) | I5, I7 pass |
| 8 | Phase 2 candidates regenerated from public evidence | met | 7 candidates, 8/8 public seeds each | I15 pass |
| 9 | Protocol frozen before method development | met, with disclosure | v1 locked before any method; corrected to v2 (early reviews) and v3 (pre-lock reviews) before any held-out / FINAL / hidden use of the affected evaluations | I3 fails as written (artefact) |
| 10 | Hidden real-intervention generation locked | met | generator hashed in the benchmark lock, salt committed by sha256 and revealed after Level C (it matches) | I3 fails as written (artefact) |
| 11 | Synthetic state-discovery benchmark exists | met | 48 systems x 3 suites, oracle-free author, 237 tests | |
| 12 | Multiple physical implementations of the same hidden dynamics | met | two implementation groups (Hopf x4, gated integrator x3) | |
| 13 | Non-compressible controls | met | 2 per suite | Q18 pass (no compact claim; abstention recall 1 of 2) |
| 14 | Shortcut / adversarial traps | met | traps A-L + review G's 10 new traps | Q1 pass |
| 15 | Strong system-identification baselines | met | 7 declared baselines + 5 independently tuned variants | Q15 pass |
| 16 | Several candidate algorithm families evaluated | met | 5 families, 12 candidates + the composer's hybrid | Q15 pass |
| 17 | Method selection without hidden real evaluation | met | rounds 1-3 on the synthetic heldout suite only | I9 pass; I8 fails as written (artefact: a cache directory counted as an attempt) |
| 18 | Clear mathematical definition of the final method | met | section 13; METHOD_NOTES.md | I4 pass |
| 19 | Latent dimension selected generically | met | the plateau rule (section 13); k never set by hand | I4, Q5 pass (Q5 on synthetic systems only) |
| 20 | Full-state predictive upper bound | met | A_full reference in every verdict (not an upper bound at 250 ms on net3, section 14) | |
| 21 | Input-only and output-history shortcut baselines | met | references in every verdict; A - input-only and A - readout-history reported | Q1-Q3 pass |
| 22 | Multi-step predictive sufficiency measured | met | family A (horizons up to T/4) | Q2-Q4 pass |
| 23 | Hidden intervention fidelity measured | met | family C on held-out types and targets (Level C); the locked method abstained on every real kick and current pair, so for v1 it is measured on silencing only | Q4, Q14 pass; Q8 pass on its synthetic criterion (section 21) |
| 24 | Markov closure measured | met | D (micro / history gain), closure gap, Markov restart checks | Q6 pass (synthetic; real: not closed on 4 of R1's 6 and 3 of R2's 4 systems) |
| 25 | Residual microstate dependence measured | met | D micro-gain, E microstate restarts | Q6, Q7 pass |
| 26 | Latent intervention lifting exists or a rigorous reason is documented | met at benchmark level; for the locked method only post hoc | the benchmark's lifting test (goal4 sections 13-14) exists, scores every model that lifts, and ran on 8 baseline models on the FINAL suite. The locked method has no native `lift()`. After the results were known, the evaluator lifted its latent interventions through its encoder, as the minimum-norm solution of goal4 section 13's lifting problem; the realised shift misses the request by 25 % (median). That test is post hoc, descriptive and synthetic-only (section 19) | |
| 27 | Multiple low-level implementations of equivalent latent interventions tested | met at benchmark level; for v1 only post hoc | up to 72 distinct implementations per system; implementation-invariance ratio median 0.03-0.30 for the 8 baselines that lift, 0.16 for v1 through the post-hoc evaluator-side lift | |
| 28 | Synthetic latent ground truth recovered on held-out systems | met, with a spread | K (min R^2 both ways) on the FINAL suite: median 0.987, mean 0.86, below 0.5 on 5 of 46 | Q1, Q5 pass |
| 29 | Reproducibility across seeds quantified | met; the result is poor | G on the FINAL suite and on the real systems (5 seeds + half-sample arm); host determinism study (P3-D27) | Q12 FAILS (k agrees on 4 of 8 synthetic and 2 of 10 real systems) |
| 30 | Latent coordinate equivalence up to valid transforms | met | K and G use affine / CCA alignment | Q10 pass |
| 31 | Alternative neuron-level mechanisms tested for shared dynamics | met; the method failed | Level C I (mechanisms of each network) and the synthetic groups | Q11 FAILS (adaptation never beats a fit from scratch) |
| 32 | Cross-connectome shared dynamics tested | met | Level C J (net1 + net2; net1 + net3 apart) | Q10 pass; Q9 reported n/a (no shared model was ever returned, section 21) |
| 33 | Independent vs shared dynamics compared fairly | met | held-out paired comparisons with parameter counts; the method never returned a shared law, so shared = independent everywhere (section 14) | Q9 reported n/a; Q17 pass but does not discriminate (section 21) |
| 34 | Cross-implementation generalisation evaluated | met; the method failed | leave-one-implementation-out adaptation (worse than from scratch in every computable case; v1's adaptation code fails when sharing is rejected; counted) | Q11 FAILS; Q17 pass |
| 35 | Robustness under parameter uncertainty | met; the result is poor | held-out parameter draws (synthetic and real), trap H, the parameter-identity probe | Q13 FAILS |
| 36 | OOD input / intervention behaviour | met | real H_stim_ood, H_weight_ood (section 17); counterexample search inside and outside the public families | Q14 pass (see section 21) |
| 37 | Counterexample search | met | 7 sweeps: 4 on the FINAL suite, 3 on the real systems (sections 9 and 16) | Q19 pass pooled; the real public-draw sweep alone is at the fail threshold |
| 38 | Negative controls | met | non-compressible controls, unrelated pairs, null pairs, scrambled-z0, random-k | Q18 pass |
| 39 | Model-capacity controls | met | PCA-k and random-k references, parameter counts | Q16 pass (synthetic criterion; its real-system evidence is void, section 21) |
| 40 | Important ablations complete | met | dev suite (15 switches) and FINAL suite (section 10) | |
| 41 | Simulation / query / compute costs recorded | met | `COMPUTE_SUMMARY.{json,md}` (job records; a double count found by review R removed), `MODAL_BILLING.{json,md}` (billed), `COSTS_LEDGER.md`; items not recorded are listed (section 22) | I13 pass |
| 42 | All old tests green | met | root suite: 534 passed, 1 skipped (the opt-in Modal consistency test), 18 deselected by the default marker; the 18 real-data tests run separately: 18 passed (2026-09-26; `research/phase3/TEST_RUNS.md`); 0 failed | I10 pass |
| 43 | Phase 3 tests green | met | `phase3` suite: 194 passed, 0 failed | I10 pass |
| 44 | Independent reviews A-H complete | met | reviews E and H early, F, G, and A-D before the lock (section 18); post-lock reviews S, C, Y, R and L (section 18.1) | I12 pass |
| 45 | Blockers resolved before method lock | met | benchmark v2 and v3 | I12 pass |
| 46 | Final method locked before hidden real evaluation | met | METHOD_LOCK.json, tag brainir-state-v1-preblind | I4, I9 pass |
| 47 | Hidden evaluation attempts logged | met, with disclosure | HIDDEN_EVALUATIONS.md, incl. the aborted ablation attempt. DONE rows of the 4 FINAL sweeps and the ablation re-run, and rows for the 2 public-draw sweeps and review G's run on the locked method, were missing; they were appended retrospectively (marked) after review R | I8 fails as written (artefact) |
| 48 | No post-hidden-evaluation tuning folded into v1 | met | no method change after the lock (`method_lock_p3.py --check`) | I4 pass; I8 fails as written (artefact) |
| 49 | PHASE3_REPORT.md exists | met | this report | I14 pass |
| 50 | Clear scientific conclusion | met | section 23: NOT SUPPORTED for the connectome-constrained rate-model simulations; partially supported on the synthetic FINAL suite | I14 pass |

**Phase 3 status: complete at the level at which the acceptance criteria are stated.** All 50 are met, criterion 26 at the
benchmark level; for the locked method, which has no native `lift()`, latent interventions were tested only post hoc (section 19).
- The first versions of this report read criterion 26 at the method level and left it "partly met".
- The status changed because of a change of reading, not because of new evidence. Criterion 26 sits among the benchmark's
  measurement items (criteria 20-27: "... exists", "... is measured") and, unlike criteria 18-19, does not name the final method.
  At that level it was met before the post-hoc test.
- The post-hoc test adds evidence for v1, but it does not give the locked method a lift: that still needs a new, separately
  locked method version.

## 19. Conclusion (goal4 section 85, criterion 50) and claim language (section 88)

**Conclusion: NOT SUPPORTED for the connectome-constrained rate-model simulations (the "real" systems); partially supported on
the synthetic FINAL suite, whose latent state is known.**

PROTOCOL.md section 7 defines verdicts per system; no suite-level aggregation rule was pre-registered. The two labels summarise the
per-system counts below. The synthetic label is scoped to the FINAL population-code suite and to held-out targets and additive group
interventions (section 8). The real label is conditional on the synthetic calibration of the tolerances (section 14).

The claim tested: BrainIR can discover the smallest causal state of a circuit's computation, meaning one that is predictively
sufficient, closed, interventionally sufficient, microstate-invariant, compressed, stable, and shared across implementations and
connectomes. The evidence does not support that claim.

- **Connectome-constrained rate-model simulations (Level C, run once on the hidden test).** A deterministic rate model on
  connectome-derived weights, with assumed neuron parameters, no noise and kicks clipped at 0 Hz (section 14).
  - Within this model and intervention domain, a 2-dimensional latent (seed 0) learned from public data predicts the held-out
    readout of net1 full and net3 full (reconstruction R1) better than an input-only model and persistence (readout NMSE 0.024 and
    0.0055), and the method claims a compact state there.
  - On net2 full (the independent reconstruction R2), a 3-dimensional latent (seed 0; modal k over seeds 2) also beats those
    controls (0.51 against 0.82), but the method itself declared that no compact state exists there, and a PCA latent of the same
    dimension and the comparator predict significantly better. On all 7 mechanisms it declared no compact state.
  - At the primary horizon the locked method predicts significantly better than a PCA latent of the same dimension on both R1 full
    networks and 3 of the 4 R1 mechanisms; PCA-k is significantly better on R2's full network and one R2 mechanism.
  - On no full network does it predict held-out intervention effects better than "no effect". There it abstained on every kick and
    current intervention and predicted silencing only (C 1.27, 0.96, 1.04), and its predictions do not depend on the encoded state.
  - It found no support for shared latent dynamics across mechanisms or connectomes. Its internal test never returned a shared law,
    and adapting dynamics between independent reconstructions was far worse than a fit from scratch (one pair, one direction).
  - Its dimension agrees across seeds on 2 systems, both of R1 (net3 full and one net3 mechanism).
  - Verdicts: "not supported" on all 4 systems of R2 and on 5 of the 6 systems of R1. net3 full (R1) is "partially supported":
    predictive and closed ("closed" passes a latent missing one dimension about one time in six, section 4.2), not interventional,
    with latents poorly reproduced across seeds and half-samples.
- **Synthetic systems with known latent state (FINAL suite; no method fitted or evaluated on it before the lock).**
  - "Compact causal state discovered" on 17 of 46 compressible systems, plus 2 in the separate category with microstate equivalence
    untestable; partially supported on 12; not supported on 15.
  - Five of the 19 have the wrong k, including k = 8 against 1 on the nuisance trap A (in the E-untestable category). The verdict
    certifies sufficiency on the tested domain, not k.
  - Exact dimension on 27 of 46. Latent recovery K: median 0.987, mean 0.86, below 0.5 on 5 of 46.
  - It does not beat the strongest baseline overall: third of nine on the aggregate profile. Paired over systems it is
    significantly better on prediction and exact k, with no significant difference on held-out C, closure, microstate equivalence or
    latent recovery. It abstains less often (1 of 2 controls against 2 of 2), with fewer false alarms (2 % against 28 %) and more
    confident-wrong claims (52 % against 33 %).
  - Counterexample searches find large intervention-effect errors, mostly on protocols with a near-null true effect, both inside and
    outside the public protocol families. 9 of 48 systems are broken immediately.

**Claim language.**
- **Permitted:** "Within the tested connectome-constrained rate model (deterministic, assumed neuron parameters, kicks clipped at
  0 Hz) and intervention domain, a 2-dimensional state representation learned from public data was sufficient to predict the
  held-out readout of net1 full and net3 full (two builds of one reconstruction) better than input-only and persistence controls,
  with readout NMSE 0.024 and 0.0055 at the 250 ms horizon (e.g. net3: NMSE difference to the input-only control -0.0067 [-0.0077,
  -0.0056]). On net2 full (the independent reconstruction) a 3-dimensional latent predicted better than those controls (NMSE 0.51
  against 0.82), but the method itself declared that no compact state exists there, and a PCA latent of the same dimension and the
  comparator predicted significantly better. It did not predict the effects of held-out silencing better than predicting no effect
  (held-out silencing effect error 0.96-1.27 against 1), and it abstained on held-out kicks and currents."
- **Not claimed:**
  - true state variables of the animal's nervous system;
  - biological truth (all evidence is simulator-based);
  - formal causal abstraction (the interventional and sharing conditions fail; v1's latent interventions were tested only post hoc,
    on the synthetic suite, through an evaluator-side lift, where the latent model's prediction after do(z) has about twice the error
    of its unperturbed prediction);
  - that interventions act through the learned state on the real systems (C is indistinguishable from C_scrambled on every full
    network);
  - that the simulated circuits lack shared dynamics (v1's sharing machinery never returned a shared law);
  - a "compact causal state" on any real system: none received that verdict, and the method declared no compact state on 8 of 10
    (every R2 system and the R1 mechanisms);
  - independence of net1 and net3 (one reconstruction).

## 20. One recommended next phase (not started)

**Interventionally trained causal state models.** The measured failure that decides the verdict is interventional sufficiency:
- the locked method never used its simulation budget: every Level C fit record shows 0 simulator calls;
- it calibrated its intervention read-in from a handful of public training interventions per system. On the real full networks
  that calibration chose "no effect" for kicks and currents, so it abstained on them;
- its silencing predictions do not depend on the encoded state (C is indistinguishable from C_scrambled), and its rolled-out latent
  after an
  intervention stays as far from the encoder's reading of the intervened state as a rollout that ignores the event;
- it has no native `lift()`. Through the evaluator's encoder lift (post hoc, synthetic), requested latent shifts are realised with a
  median 25 % miss, and the latent model's prediction after do(z) has about twice the error of its unperturbed prediction.

The next phase should learn the intervention map from designed interventions: active experiment design within the budgeted public
simulator, with the read-in, the dynamics and the lift fitted jointly on interventional data, and state-mediation as a selection
criterion. It should be evaluated on a new, separately locked benchmark version with the same pre-registration, clean-room and
single-platform (host-gated) execution discipline. That version should include the evaluation lessons of this phase:
- calibration systems whose time step, parameter draws and intervention operators match the real systems, so that real verdicts are
  not conditional on a mismatched calibration;
- effect normalisers that are not dominated by a few pairs or readout dimensions;
- a closure test with more power against latents that miss a dimension.

## 16. Counterexample search on the real systems (post-lock; after Level C's fits)

The searches used the Level C seed-0 fits and the same protocol domain and criteria as section 9. The domain extends past the
public protocol families; real kicks are absolute rate offsets that the engine clips at 0 Hz.
- **Public parameter draws:** development domain, on Modal.
- **Hidden parameter draws:** derived from the salt, run locally as pre-registered (P3-D28).

A search can only probe the event kinds a model supports. The locked method supports silencing only on the full networks, and no
event kind at all on 3 mechanisms, which therefore cannot be searched. The comparator supports kicks, currents and silencing
everywhere.

| sweep | searchable systems | systems with counterexamples | distinct | median worst / random-median error | broken immediately |
|---|---|---|---|---|---|
| brainir_state_v1, public draws, effect | 7 of 10 | 7 | 430 | 8.4 x 10^5 | 5 of 10 (5 of the 7 searchable) |
| lin_dmdc_t, public draws, effect | 10 of 10 | 10 | 564 | 3.6 x 10^7 | 4 of 10 |
| brainir_state_v1, hidden draws, effect (local, 3,340 s) | 7 of 10 | 7 | 416 | 1.7 x 10^5 | 3 of 10 (3 of 7) |

Systems broken immediately, by lineage:
- locked method, public draws: of reconstruction R1, net3 full and 3 mechanisms (net1 b, net3 a, net3 b); of R2, net2 full;
- locked method, hidden draws: of R1, net1 full, net3 full and net1 mechanism b; of R2, none;
- comparator, public draws: of R1, net1 full, net3 full and net1 mechanism a; of R2, net2 full.

- **Typical errors are already at "no effect".** Before any search, the locked method's median effect error on random protocols is
  about 1 on net2 full (1.08-1.09) and net3 full (1.03-1.06), and 4.5-4.9 on net1 full; the median over the 7 searchable systems is
  0.95-0.99. The candidate thresholds, max(1, 2 x p90), are therefore large on the full networks (net1 full: 16,134 with public
  draws and 57,732 with hidden draws; net2 full: 385-770).
- **What the extreme errors are.** As on the synthetic suite, they come mostly from near-null true effects (section 9 explains why
  the ratio then explodes):
  - 71 % (public draws) and 62 % (hidden draws) of the candidates have a true-effect energy below 1 % of a typical protocol's;
  - on every searchable system the worst protocol does;
  - the post-event readout NMSE is below 1 in 86 % and 85 % of the candidates. For example, the worst net1 full case with hidden
    draws has an effect error of 10^10 and a post-event NMSE of 0.06.
- **Inside and outside the public families.** 21 % (public draws) and 10 % (hidden draws) of the candidates lie entirely inside the
  public protocol families, on 6 and 7 of the 7 searchable systems. With public draws the candidate rate per protocol is about the
  same inside and outside the families (0.20 against 0.18); with hidden draws it is 0.13 against 0.23.
- **Initial states.** Perturbed initial states raise the candidate rate (public draws 0.25 against 0.15; hidden draws 0.25 against
  0.19). That is weak evidence that off-manifold initial conditions carry state the latent lacks. The searches did not isolate a
  specific missing state variable.

For the locked method this matches Level C: no interventional claim holds on any real full network, and its typical silencing
prediction is already no better than predicting no effect.

**Self-audit Q19** (pre-registered). A system is broken immediately when at least half of its searches find a counterexample within
their first 10 protocols; the check fails if the fraction reaches 0.5.
- Pooled over the locked method's four sweeps (116 system-runs), the fraction is 0.17, so Q19 passes as registered; over the 108
  searchable system-runs it is 0.185.
- Per sweep: FINAL effect 0.19, FINAL post 0.06, real hidden draws 0.30, real public draws 0.50.
- The real public-draw sweep alone reaches the fail threshold. The pooled pass is dominated by the synthetic sweeps.

## 17. Robustness, statistics and limitations

**Robustness on the real systems (Level C hidden families on the full networks).** A = readout NMSE at the primary 250 ms horizon;
the 100 ms value in brackets. The evaluator caps each window's NMSE at 10. Where windows reach the cap the mean is a lower bound
("≥"), and the number of capped windows is given.

| full network | lineage | model | held-out draws / states | out-of-distribution stimulus | out-of-distribution weight noise |
|---|---|---|---|---|---|
| net1 | R1 | brainir_state_v1 | 0.024 (0.024) | ≥ 5.74, 63 capped (≥ 1.82, 6 capped) | 0.043 (0.046) |
| net1 | R1 | lin_dmdc_t | 0.022 (0.018) | 0.64 (0.46) | 0.063 (0.059) |
| net1 | R1 | input-only control | 0.034 (0.034) | 0.76 (0.78) | 0.045 (0.044) |
| net2 | R2 | brainir_state_v1 | 0.51 (0.53) | ≥ 3.60, 19 capped (≥ 3.52, 19) | 1.26 (1.25) |
| net2 | R2 | lin_dmdc_t | 0.29 (0.20) | ≥ 2.52, 10 capped (≥ 2.09, 2) | 1.26 (1.06) |
| net2 | R2 | input-only control | 0.82 (0.82) | ≥ 5.79, 60 capped (≥ 5.74, 63) | 1.26 (1.24) |
| net3 | R1 | brainir_state_v1 | 0.0055 (0.0054) | 0.13 (0.13) | 0.023 (0.022) |
| net3 | R1 | lin_dmdc_t | 0.0073 (0.0050) | 0.24 (0.13) | 0.057 (0.052) |
| net3 | R1 | input-only control | 0.012 (0.012) | 0.11 (0.11) | 0.025 (0.024) |

- **Out-of-distribution stimulus.** At the primary horizon it degrades the locked method's prediction about 235-fold on net1 full
  (from 0.024 to at least 5.7; a lower bound, because 63 windows reach the cap). The comparator degrades about 29-fold there. On net2
  the locked method degrades about 7-fold and on net3 about 24-fold; the comparator degrades about 9-fold and 32-fold. (At 100 ms, the
  horizon of the first draft, net1's factor is 76 against 26.)
- **Against the input-only control** (point estimates):
  - under the OOD stimulus the locked method predicts worse than the input-only control on net1 (5.7 against 0.76) and net3 (0.13
    against 0.11), both of reconstruction R1; on net2 (R2) the two are not comparable (both capped: 19 and 60 windows);
  - under OOD weight noise it is within about 10 % of the input-only control on all three networks.

  Out of distribution, the compact latent adds little or nothing over the input.
- **OOD weight noise** is tolerated better by the locked method than by the comparator on net1 and net3, and equally on net2.
- **Parameter-identity probe.** On the full networks it decodes the hidden parameter draw from z with accuracy 0.33-0.58 (chance
  0.17), against 0.96-0.98 for the comparator's high-dimensional state. Over all 10 systems the locked method's accuracy is 0.30-0.81
  (section 21, Q13). The compact state carries much less draw-specific information.
- **Transient perturbations.** After held-out interventions the readout error is 1.0-1.2 times the unperturbed error on the full
  networks, and 5.8 and 6.7 times on two mechanisms (net1 mechanism b, net2 mechanism b; section 21, Q14).

**Robustness on the synthetic FINAL suite** (family H = the held-out structural-noise family, 3 trajectories per system; primary
1 s horizon; `research/phase3/tournament/final_b_H/`). The FINAL evaluation computed family H, but the frozen tournament summariser
did not keep it. It was recovered after review R by re-evaluating the stored seed-0 fits (no refit; logged). The extraction ran
twice: the first run read the real-system horizon keys, and its summary was discarded. The re-evaluated
in-distribution A reproduces the stored verdict A exactly (largest relative difference 9e-16).
- Held-out structural noise relative to in distribution, over the 46 compressible systems:
  - locked method: median ratio 1.34 (interquartile range 0.61-3.77), above 2 on 16 systems, up to 69;
  - comparator: median ratio 0.97 (0.37-2.01), above 2 on 12.
- In absolute terms the two do not differ significantly: paired median of the OOD A, method minus comparator, -0.005 [-0.029,
  0.0002].

**Statistics (PROTOCOL.md sections 5-9; unchanged since version 3).**
- Units are trajectories within a system and systems across a suite. CIs are bootstrap 95 % intervals over units, with paired
  designs throughout.
- In the synthetic profiles, failures and non-finite values count as the worst value. At Level C, pairs the method abstained on are
  excluded from C and from the paired C comparisons, which then cover only the pairs the method scored (section 14).
- Selection: rank aggregation over the fixed compressible list, with the selection's bootstrap P(rank 1). The S1-S5 ranking and the
  leave-one-component-out rankings are reported (sections 6 and 8).
- Level C: 13 one-sided non-inferiority tests (margins fixed per family), Holm-corrected, with a two-sided secondary family, also
  Holm-corrected. Per-system verdict conditions, the per-system PCA comparisons and the ablation CIs are unadjusted and descriptive.
- Every tolerance was calibrated on the dev suite before any held-out use (calibration v3: tau_A 0.784, tau_C 3.69, tau_D 0.092,
  tau_H 0.234, tau_E 0.0179; tau_gap descriptive). The real verdicts are conditional on this synthetic calibration (section 14).
- The number of candidates (19 registered + the hybrid), rounds (3, one of them repeated under version 3) and feedback releases (2)
  is disclosed. The selection's advantage did not replicate on the FINAL suite (section 8).

**Limitations.**
1. **The biggest limitation: the learned state does not carry intervention effects.** On the real full networks the locked method
   abstained on every kick and current intervention. Its silencing predictions do not depend on the encoded state and are no better
   than predicting no effect. The core causal claim, interventional sufficiency of the state, was never demonstrated on the real
   systems, and latent interventions were tested only on the synthetic suite (post hoc, through an evaluator-side lift).
2. **Simulator-only evidence.** The "real" systems are connectome-constrained rate-model simulations with assumed neuron parameters,
   deterministic dynamics (no noise), and kicks given as absolute rate offsets that the engine clips at 0 Hz. Nothing here is a
   statement about the living nervous system.
3. **Calibration mismatch.** The tolerances were calibrated on synthetic systems with a different time step, parameter draws and
   intervention operators, so the real verdicts are conditional on that calibration. The closure test passes a latent that misses one
   dimension about one time in six.
4. **Two reconstructions.** net1 and net3 are two builds of one reconstruction, so cross-connectome evidence rests on one pair (net1 +
   net2), tested in one direction.
5. **Missing capabilities of the locked method:** no native lifting of latent interventions (tested only through the evaluator's
   encoder lift, post hoc), no partial sharing, and a defect in leave-one-out adaptation (it crashes when sharing is rejected).
6. **Host-dependent fits.** Model selection amplifies last-digit numerical differences, so the Level B rounds and the FINAL
   confirmation (mixed Modal hosts) are single realisations. Level C and the hidden test data ran on one deterministic platform, which
   still differs from the development machine.
7. **Selection instability.** A narrow selection margin (P(rank 1) = 0.52) that did not replicate; heldout selection bias is possible
   (winner's curse).
8. **Reproducibility of k.** k agrees across 5 seeds on 2 of 10 real systems (net3 full and net3 mechanism b, both of R1) and across 3 seeds on 4
   of 8 synthetic G systems. On net1 full and net2 full it differs across both seeds and half-samples.

## 18. Reviews (goal4 sections 60-70)

Each review ran as a separate agent session in a redacted room. Every finding was resolved by an evaluation fix (a new benchmark
version), a generic requirement to the developers, or a disclosure. The records are under `research/phase3/reviews/`
(answer-bearing) and `research/phase3/review_g/`.

| review | when | scope | outcome |
|---|---|---|---|
| E (statistics) | early, on the evaluator | ranks, units, CIs, medians, controls | 5 blockers, 6 majors: benchmark v2 |
| H (numerics) | early | solvers, normalisers, invariances | 1 blocker, 7 majors: benchmark v2 |
| F (leakage) | after development started; answer-aware | isolation of the rooms, guards, transcripts | 2 blockers (substring guards): guard version 2; no leak had occurred (replay of every executed call) |
| G (adversarial traps) | on the round-2 top five and on brainir_state_v1 | 10 new trap systems no developer saw | every candidate is confidently wrong on at least one trap; the verdicts certify sufficiency, not minimality or correctness of k |
| A (system identification), B (causal inference), C (representation learning), D (computational neuroscience) | before the lock, on the composed candidate | the method and the version-2 evaluation | 7 blockers, 19 majors: benchmark v3 (evaluation) and generic method requirements (the composer's version-3 changes) |
| Post-lock S (statistics), C (claims), Y (dynamics), R (report accuracy), L (leakage and process), V (verification of the corrections) | after Level C, on the draft and then on the corrections | reporting, statistics, claims and process only | section 18.1 |

**Review G's traps on the LOCKED method (post-lock, descriptive, not pre-registered; version-3 evaluator;
`research/phase3/review_g/results_locked_v3.json`).** The earlier review-G run tested the tournament version under the version-2
evaluator. On the 10 traps no developer saw:
- the locked method makes no full "compact causal state" claim: 6 are partially supported, 4 not supported;
- its k is wrong on 5 of the 9 compressible traps: G1 2 vs 4, G2 8 vs 3, G4 4 vs 9, G7 1 vs 3, G9 4 vs 2;
- on the non-compressible G10 it declares no compact state (abstention recall 1 of 1: its latent explains too little beyond the
  input), yet G10 still meets the "partially supported" conditions with k = 1;
- it abstains falsely on the compressible G3 (false alarm 1 of 9); the confident-wrong rate is 0.8.

(The first draft said in this section that the method "does not abstain" on G10, and the first round of corrections repeated it in
the summary; it was false, and verification review V found it.) The comparator gets
k right on 3 of 9, and its verdict on G4 is "compact causal state discovered (microstate equivalence untestable)" with k = 14
against 9. The verdict conditions certify
sufficiency on the tested horizons and interventions; they do not certify the minimality or correctness of k.

Transcript audits of all agent sessions found 0 forbidden-path inputs, no web use outside the literature agent, and no
non-numeric answer tokens. One numeric hit was a coincidental 5-digit file size.

### 18.1 Post-lock reviews (after Level C; reporting, statistics and claims only)

Five reviewers examined the first draft of this report after Level C, and a sixth verified the corrections:
- S (statistics), C (claims: computational neuroscience and causal inference), Y (nonlinear dynamics and system identification) and
  R (report accuracy and completeness), each a separate session in a redacted post-lock room that holds the result files
  (`scripts/p3/make_postlock_review_room.py`);
- L (leakage and process), an answer-aware agent working in this repository;
- V (verification of the corrections), a separate session in the same room after the corrections. For every blocker and major
  finding of S, C, Y and R it re-derived the numbers the corrections rely on, and it scanned the corrected report for new errors.

Scope rule: no reviewer proposed a method change, and none was made; the method stays locked. Every finding was resolved in one of
these ways:
- by correcting or completing this report, with the numbers re-derived by `scripts/p3/postlock_numbers.py` into
  `research/phase3/reviews/POSTLOCK_NUMBERS.json`;
- by the compute correction (`scripts/p3/compute_summary_postlock.py`, `scripts/p3/modal_billing.py`);
- by retrospective rows in the hidden-evaluation log;
- by the extraction of synthetic family H (`scripts/p3/final_h_family.py`);
- by the post-hoc lifting test of v1 through its encoder (`scripts/p3/lift_v1_encoder.py`; section 19). Review V's second pass found
  its wording overstated (criterion 26 "met", Phase 3 "complete" without qualification; v1's lift compared with the baselines' on
  unequal terms; the true-latent spread omitted). All of this is corrected: criterion 26 is met at the benchmark level, and for the
  locked method only post hoc.

No verdict changed. The reviews are in `research/phase3/reviews/POSTLOCK_{S,C,Y,R,L}.md`, and the finding-by-finding resolution map
is `research/phase3/reviews/POSTLOCK_RESOLUTION.md`. A transcript audit of the five room sessions (S, C, Y, R and V) found 0 inputs outside the room and
0 answer tokens.

| review | blockers / majors | main findings | resolution |
|---|---|---|---|
| S | 4 / 8 | PCA "9 of 10" false (a horizon mismatch in self-audit Q16); the E-untestable category merged into "compact"; the selection sentence contradicted by the leave-one-component-out ranking; a compact state claimed on net2 full, where the method abstained; abstentions and the C scope unreported; C reporting rule; lineage pooling; G statistics softened; robustness at a non-primary horizon; "worse" claims without paired support; S1-S5 ranking missing | all corrected (sections 6, 8, 10, 14, 16, 17, 21, 23) |
| C | 3 / 11 | as S on PCA and "compact"; "never" false for net3 mechanism b (not state-mediated); model assumptions and "conditional on the calibration" missing; lineage; causal wording without state-mediation and lifting caveats; additive-composition scope; kick-clip sensitivity missing; sharing worded as a property of the circuits; traps missing from the summary; Q8 described as something it did not test; the title overstated | all corrected; title changed. Two of C's own statements did not reproduce and are not adopted: PCA-k "better on 9 of 10 systems at 10 ms" repeats the horizon error (it is 1 of 10), and the locked method "does not abstain" on review G's G10 is false (it declared no compact state there; review V) |
| Y | 3 / 9 | abstentions hidden; the Markov "with events" claim false on 4 systems; the counterexample mechanism misread (near-null true effects); closure power not attached; wrong-k compact verdicts; dimension fragile under resampling; OOD at a non-primary horizon; interventional closure gap omitted; I/J parameter counts and vacuous Q9 / Q17 | all corrected. Two details did not reproduce: k = N on net2 mechanism a (it is k = 2 for N = 3; k >= N only on net2 mechanism c) and "3 of 8 G systems change k" (it is 4 of 8). Y's mean-based nn_dim_rule S3 interval, first rejected, is right (review V) and is now reported |
| R | 2 / 11 | the PCA claim; the Modal total double-counted three runs (+$40); the acceptance table marked "met" where self-audit checks fail; missing log rows; vacuous or synthetic-only self-audit passes; 18 deselected tests; compute items, post-lock reviews, biggest limitation, Phase 3 status, full-state comparison and final tag missing; LOIO results and J directions | all corrected; the compute section reports the billed amount; the 18 tests were run (18 passed). R's Q14 median (1.04) did not reproduce: it is 1.12 over the 6 finite ratios |
| L | 0 / 1 | no blocker: the lock preceded every hidden evaluation, no change reached v1, every hidden run used the locked bytes, configuration, seeds and budgets, the salt was revealed only after Level C and matches its commitment, and rooms and transcripts are clean. Major: the FINAL suite was touched before the lock by a stopped reference-control precompute on 2 systems (no method involved). Minors: fake-salt dry-run records in the store; an unrecorded third local hidden-generation start and an inaccurate amendment sentence; retrospective log rows and two wording errata; snapshot provenance not recorded; P3-D27 timing; stale documents and no retention decision; tool gaps; the family-H DONE row | statements qualified (sections 4.2, 7, 11); fake records quarantined; errata appended to the log, the leakage policy and the runbook; provenance recorded (`research/phase3/POSTLOCK_PROVENANCE.json`); retention decision recorded; all listed in section 12 |
| V | 1 / 3 (on the corrections; a second pass, `reviews/POSTLOCK_V2.md`, then checked the post-hoc lifting test: 0 / 3) | all original blockers resolved; 35 of 39 majors resolved, 3 partly (lineage; closure power next to the conclusion) and 1 not (C M9). New errors introduced by the corrections: the G10 abstention statement (false); Y's nn_dim_rule S3 interval wrongly rejected (the resolution script had used the point estimate, not the pre-registered S3); the permitted claim still calling the net2-full latent "sufficient"; lineage missing from most Level C tables; 14 minors | all fixed in this version: G10 wording (summary, section 18); section 10.1 from the stored mean CIs; the permitted claim split by reconstruction; lineage columns and per-lineage counts; the minors (section 18.1 map in `POSTLOCK_RESOLUTION.md`) |

## 21. Latent intervention results (lifting; goal4 sections 45-49, criteria 26-27)

Lifting means mapping a desired latent intervention (a shift of z) to concrete neural interventions and checking, through the
simulator, that they achieve the shift and are interchangeable.
- The benchmark scores it where a model implements `lift()`.
- On the FINAL suite, 8 baseline models lift: lin_dmdc, lin_dmdc_t, lin_falds, lin_falds_t, lin_pcadyn, lin_pcadyn_t, nn_aelin and
  nn_aelin_t. For each requested shift they propose several distinct low-level implementations (up to 72 per system).
- **The locked method has no native `lift()`.** After the post-lock reviews, its latent interventions were lifted by the evaluator
  through v1's own encoder, as the minimum-norm solution of goal4 section 13's lifting problem (`scripts/p3/lift_v1_encoder.py`;
  `research/phase3/tournament/final_b_lift_v1/LIFT_V1.json`). The design was fixed and logged (12:09:06Z) before the first run; a
  one-system smoke run followed, and the full run ended at 12:13:02Z:
  - J = d phi / d x_t is the encoder's sensitivity to the current observed microstate, computed by finite differences through the
    public `encode()`. v1's encoder is linear in the current sample (checked: to 1e-11), so J is exact;
  - the lifts are minimum-norm kicks J[:, cols]^+ delta_z on the observed public targets, with the baselines' three-candidate rule;
  - they were scored locally by a re-implementation of the confirmation job's lifting step. It calls the frozen `eval_lifting` with
    the job's cases and settings on the stored seed-0 FINAL fits; it is not the frozen Modal job itself.

  v1 was not changed, refitted or re-selected. The test is post hoc and descriptive (not pre-registered). The real systems have no
  lifting test for any model (Level C did not include one).

| model (FINAL suite, 46 systems) | achieved-shift relative error (median) | readout NMSE after lifting / on the twin | implementation-invariance ratio (median; share < 1) | true-latent shift spread across lifts of one shift (median) |
|---|---|---|---|---|
| lin_dmdc_t (lin_dmdc identical) | 0.37 | 0.35 / 0.14 | 0.16 (92 % of 39 testable systems) | 0.43 |
| lin_falds | 0.64 | 0.22 / 0.13 | 0.12 (100 % of 43) | 0.47 |
| lin_falds_t (45 systems) | 1.02 | 0.21 / 0.12 | 0.06 (97 % of 35) | 0.34 |
| lin_pcadyn (lin_pcadyn_t identical) | 0.89 | 0.49 / 0.13 | 0.30 (89 % of 35) | 0.68 |
| nn_aelin (nn_aelin_t: 0.31) | 0.31 | 0.27 / 0.09 | 0.03 (96 % of 45) | 0.30 |
| brainir_state_v1, lifted by the evaluator through its encoder (post hoc) | 0.25 | 0.17 / 0.079 | 0.16 (100 % of 45) | 0.54 |

The last column is the pre-registered truth-based item (synthetic suites): how much the TRUE latent shift varies across distinct
lifts of one requested shift (lower = the lifts agree on the true state).

**The rows are not comparable in the achieved-shift column.** v1's lift inverts the same encoder through which the evaluator measures
the achieved shift, so its 0.25 is favourable by construction. The baselines' lifts invert their event operators instead. The
true-latent spread does not depend on any model's encoder. On it v1 is second worst (0.54, against 0.30-0.47 for four of the
baselines and 0.68 for lin_pcadyn): lifts that reach the same encoder reading move the true latent state in different ways. For every
model, the readout error after the latent intervention exceeds the error without it on most systems (v1: 42 of 46; baselines: 40 of
45 to 45 of 46).

The implementation-invariance ratio is the future divergence between implementations of the SAME latent shift, divided by the
divergence between DIFFERENT shifts. It is untestable on a system with fewer than two distinct lifts of a shift; untestable or
non-finite ratios are excluded (1-11 of the 46 systems per model).
- **Favourable:** different neural implementations of one latent intervention produce similar futures, much more similar than
  different interventions do.
- **Unfavourable:**
  - the achieved latent shift misses the requested one by 31-102 % in the baselines' lifts (25 % for v1, favourable by construction);
  - the true latent shift varies by 30-68 % across lifts of one requested shift (v1: 54 %);
  - after do(z := z + delta_z) the latent models' readout error is 1.7-3.7 times their error without intervention (v1: 0.17 against
    0.079, about 2.1 times).

So latent interventions are implementation-invariant in their futures but imprecisely realised, not pinned to one true latent shift,
and only partly predicted. That holds in the baselines' models and, through the post-hoc evaluator lift, in v1 (synthetic FINAL suite
only).

## 22. Uncertainty

Every reported effect carries a bootstrap 95 % CI over its units (trajectories, systems or protocols), with paired designs. The
largest uncertainties that bear on the conclusions:
1. **The selection itself:** P(rank 1) 0.52 on the heldout suite and 0.25 on the FINAL suite, with rank intervals [1, 5] and [1, 8].
2. **Real held-out C:** it covers silencing only. It rests on few effective pairs (n_eff 1.4-4.1; 45-49 of 60 pairs are null), and
   one readout dimension carries 77-83 % of the effect denominator on net1 and net3. The per-network CIs are wide (net1: 1.27 [1.03,
   1.89]), but every upper bound is at or above 1.
3. **The dimension:** k on the real systems varies across seeds (2-8 on the mechanisms) and across half-samples (2-8 on net1 full,
   2-6 on net2 full). On the synthetic suite 5 of the 19 "compact" verdicts have the wrong k.
4. **Latent recovery:** the median K of 0.987 hides a tail; K is below 0.5 on 5 of 46 FINAL systems.
5. **Calibration:** the real verdicts are conditional on a synthetic calibration with a different time step and intervention
   operators, and "closed" has limited power (section 4.2).
6. **Platform:** host-dependent configuration choices for fits on mixed hosts (section 12).
