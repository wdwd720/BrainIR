# BrainIR — Phase 1 report: the frozen cross-connectome DNg100 benchmark

Spec: `goal2.md`. Period: 2026-09-22 23:00 → 2026-09-23 (one session, with parallel sub-agents for reviews, baselines,
robustness experiments and fixture generation). Decisions are logged in `research/LOG.md` (D21–D39 and later), the
chronology in its §10. **This file names the published answer (§7–§8) and is answer-bearing: never hand it to a
discovery method** (see `benchmarks/dng100/PROTOCOL.md` §2).

Status line: [PENDING: final status — frozen tag, lock hash, test counts, cloud cost]

---

## 1. What Phase 1 delivers

| deliverable | where | state |
|---|---|---|
| MANC acquisition (paper's exact versions, pinned + verified) | `brainir.sources.registry` (`MANC_V1_0`, `MANC_V1_2`), `data/raw/manc/` | done: 32 files, 5.0 GB, CRC32C/MD5/generation pinned |
| MANC ingestion via dataset adapters | `brainir.ingest.{common,malecns,manc}` | done: builds `manc:v1.0`, `manc:v1.2.1`, `manc:v1.2.3`; MaleCNS rebuilt unchanged in content |
| Validation ≥ MaleCNS rigour, deterministic rebuilds | `data/manifests/manc_*.validation.*`, `*.manifest.json` | done: 0 failures; second builds byte-identical |
| Schema audit / evidence typing | `brainir.schema` 0.2.0, `docs/schema.md` | done |
| MaleCNS ↔ MANC mapping layer | `brainir.mapping`, `research/cross_connectome_mapping.md` | done (v1.2.1 and v1.2.3 tables) |
| Paper reconstruction from code | `research/literature/pugliese_model_spec_from_code.md` | done (unknowns listed) |
| Simulator, rhythm metrics, pruning + activation-screen procedures | `brainir.sim`, `brainir.metrics` | done |
| Synthetic evaluator circuits, labelled test signals | `brainir.testing.{circuits,signals}` | done |
| Public bundle (tier B labelled, tier A blind), manifest + hash | `benchmarks/dng100/public*`, `build_public_bundle.py` | done |
| Oracle with evidence levels; prediction schema 1.0.0 | `benchmarks/dng100/oracle/`, `brainir.benchmark.prediction` | done |
| Frozen evaluator (metric families, no magic number) | `benchmarks/dng100/evaluator/evaluate.py` | done |
| Clean room, automated leakage checks, `LEAKAGE_AUDIT.md` | `benchmarks/dng100/cleanroom/` | done: PASS |
| Baselines + null distributions | `benchmarks/dng100/baselines/` | [PENDING] |
| Reproductions (connectivity, dynamics, interventions, pruning, DN screen, sweeps, negative controls) | `benchmarks/dng100_walking_cpg/` | [PENDING: pruning/DN screen/interventions/mCNS] |
| Cross-connectome evaluation both directions | `cross_connectome_eval.py` | [PENDING: final n] |
| Compute layer (local + Modal), experiment registry | `brainir.compute`, `benchmarks/dng100/manifests/experiments/` | done |
| Protocol, freeze, lock, tag | `PROTOCOL.md`, `freeze.py`, `BENCHMARK_LOCK.json`, tag `dng100-benchmark-v1` | [PENDING: freeze] |
| Independent reviews A–F | `research/audit/phase1_reviews/` | [PENDING] |

Not started, by design: Phase 2 (synthesizer, DSL, UI).

## 2. Datasets

### 2.1 Which MANC the paper used, and how that was established (LOG D21, §3.11)

Pugliese et al. do not state dataset versions. Two raw MANC lineages exist publicly: the neuPrint bulk export of
**v1.0** (`gs://flyem-manc-exports/v1.0/`: Meta, Neurons (24.5 M segments), Neuron_Connections, per-body properties
(102,369 `:Neuron` bodies), traced adjacencies, the minconf-0.0 synapse-partner table) and the **v1.2** segmentation's
synapse-partner table + neuroglancer annotation snapshots (`gs://manc-seg-v1p2/`: v1.2 base, v1.2.1 = 2024-09-27,
24,143 bodies; v1.2.3 = 2025-10-26, 23,665 bodies). No bulk export exists for v1.2.x, so BrainIR **rebuilds** v1.2.1
and v1.2.3 from the v1.2 partner table under the inferred neuPrint count rule (D24: `weight` = pairs with
`conf_post ≥ 0.4`, `weightHP` = `≥ 0.7`, `weightHR` = all pairs), confirmed by flyem-snapshot's docstring and by the
v1.2.3 snapshot's own `syn_*` totals (23,665/23,665 neurons exact).

The authors' front-leg table (4,604 bodies, 2025-08-13) agrees in cell type with the v1.2.1 snapshot for 4,600/4,604
bodies (4,593 with v1.2.3); their full-VNC table (23,532 bodies, 2025-10-06) is v1.2.3. The decisive evidence is
§7.1: every pair and every count of both published matrices is reproduced from the rebuilt `manc:v1.2.1` /
`manc:v1.2.3`. No version was substituted silently; `manc:v1.0` is kept as a third build for the size table the
v1.2.x snapshots lack (D25) and for the count-rule inference.

### 2.2 Builds

| build | neurons | edges (neuron→neuron) | synapses | autapses | validation |
|---|---|---|---|---|---|
| `manc:v1.0` (neuPrint Traced bodies) | 23,514 | 5,275,519 | 30,808,321 | 3 edges / 21 syn | 48 pass, 0 fail, 3 warn |
| `manc:v1.2.1` (snapshot 2024-09-27) | 24,143 | 5,338,378 | 31,002,847 | 36 / 217 | 32 pass, 0 fail, 1 warn |
| `manc:v1.2.3` (snapshot 2025-10-26) | 23,665 | 5,305,638 | 30,934,610 | 36 / 217 | 33 pass, 0 fail, 1 warn |
| `male-cns:v1.0` (Phase 0, rebuilt under schema 0.2.0) | 166,700 | 25,582,938 | 124,177,617 | 101 / 474 | 53 pass, 0 fail, 1 warn |

Rows of the raw v1.2 partner table with weight 0 (HR-only: 5,666,874 in v1.0's terms) are dropped and counted;
float32 confidences are compared in float64 (D16). Every build was run twice and the second build is byte-identical
(`tests/test_determinism.py`, manifests). Provenance (bucket, generation, CRC32C, SHA-256, sizes, code fingerprint,
git commit, definitions, count rule) is in `data/manifests/<dataset>_<version>.manifest.json` (schema 1.1).

### 2.3 Discrepancies documented, not hidden (LOG §3.11–3.16)

The v1.0 property export labels 314 Traced bodies `RT Orphan`; the traced-adjacency export has 23,188 bodies; the
v1.0 Meta `roiHierarchy` is stale and has a typo ("ventral nerve core"); v1.2.x builds carry body-level NT from v1.0 by
body ID and the paper's v1.2.1 `predictedNt` differs for 72/4,604 neurons (rule unknown); MANC ascending neurons are
output-dominated inside the VNC (expectation made informational, D28). Unresolved items are in LOG §8.6–8.7.

## 3. Schema audit (evidence typing)

Schema 0.2.0 (D27): `is_traced` / `neuprint_neuron_label` nullable (v1.2.x has no status); NT vocabulary gains
`unknown` (the classifier's class) distinct from `unclear`; sides gain `B`; a cross-dataset `role_class`
(`brainir.role.v1`) normalises MANC `class` and MaleCNS `super_class`. The five evidence kinds stay in separate
columns: EM observations (counts, ROIs, sizes), curated annotations (types, classes, `manc_body_id`), ML predictions
(`nt_*`), rule-based hypotheses (sign, computed on demand under a named rule; `sign_hypothesis(basis="auto")` records
the field used) and model parameters (never in tables; `ModelConfig` in run records). `synapse_count` is never called
strength; the public bundle carries `synapse_count` (anatomy) and `signed_weight` (hypothesis) side by side.

## 4. Cross-connectome mapping layer (D35, `research/cross_connectome_mapping.md`)

One row per (MaleCNS neuron, MANC candidate) with `mapping_kind` ∈ {curated_body_match, curated_type_match,
same_type_name, same_role_only, unmatched}, `method`, `evidence_kind`, `confidence` (A → B uniqueness, not agreement),
`ambiguity`, `b_ambiguity` (B → A count), side/role/NT/type consistency flags, notes, and both datasets' manifests
(schema 1.1.0). MaleCNS v1.0 → MANC v1.2.1: 24,162 in-scope neurons, 449,984 rows; 18,555 curated body matches
(`high`), 4,414 type matches (78 medium / 4,336 low), 1,165 role-only, 28 unmatched; body-match consistency side
97.0 %, role 96.0 %, NT 91.5 %; for 4,022 body matches (21.7 %) both the annotated MANC type and the MaleCNS type
disagree with the body's current snapshot type — they stay `high` (uniqueness) and are flagged in
`manc_type_consistent` / `a_type_consistent`. **No row asserts identity** (two animals); `curated_*` rows restate the
MaleCNS release's own cross-dataset annotations. Cross-connectome use in the benchmark: §7.6 and the frozen
`oracle/cross_connectome_reference.json` (3,717 curated pairs among the benchmark networks per MANC version).

## 5. Paper reconstruction

`research/literature/pugliese_model_spec_from_code.md` extracts the rate model, parameter distributions, size
scaling, sign rule, integration settings, the oscillation score, the pruning search and the activation screen from the
authors' repository (commit 10e7661), marking every guess. Reproduction results below quantify how far the
reconstruction carries. Procedures that cannot be determined from the repository (engine per run, the Dirichlet
screen, the type-level screen's "≥10 active neurons") are listed in LOG §8.7.

## 6. Simulator and metrics

`brainir.sim` (D29): τ dr/dt = max(r_max tanh((a/r_max)(I + bΣWr − θ)), 0) − r, float64, RK45 rtol 2e-6 / atol 5e-9
(authors' tolerances), integrated segment-wise at pulse edges; truncated-normal per-neuron parameters (τ 20±2 ms,
a 1±0.1, θ 7.5±0.6, r_max 200±10), size scaling a/s, θ·s; `Stimulus`, `Intervention` (silence, keep-only, weight
noise, NT-scaling), `Trajectory`. `brainir.metrics.rhythm` (D30): the published autocorrelation score reproduced
exactly, plus amplitude, envelope-persistence and inter-peak-regularity gates (`is_sustained_rhythm`) because the
published score is amplitude-blind. Generic procedures: `brainir.sim.prune` (stochastic sufficiency search) and
`brainir.sim.screen` (auto-tuned activation screen) (D36). Tests: independent reference integrator on 10 synthetic
circuits, 16 labelled signal kinds, hand-derived score values.

Numerical correctness (`robustness_experiments.py dt-convergence`, `manc:v1.2.1`, 6 seeds, T = 2 s, reference RK45
rtol 1e-8 / atol 1e-11 whose own error is ≈ 6e-4 Hz): the authors' RK45 tolerances differ from the reference by at most
0.11 Hz in any rate (RMS 1.4e-3 Hz), by ≤ 1.6e-3 in the published score and by nothing in the MN frequency;
segment-wise and single-interval integration agree to 0.07 Hz. Fixed-step RK4 at dt = 1 ms is already within
2.3e-2 Hz / 3.8e-4 score and reaches 7.8e-3 Hz at 0.5 ms; its empirical order is ~2, not 4, because the right-hand side
has a C⁰ kink at every threshold crossing. Forward Euler at 1 ms shifts the frequency by −7 % and the score by up to
0.09 — unusable. Finding: the study exposed that the fixed-step schemes originally evaluated the pulse indicator at
the Runge–Kutta stage times (an O(dt) error of ≈ 0.15 Hz at the pulse onset); sub-steps are now split at the pulse
edges (`_fixed_step`, regression test against the closed-form single-neuron response, LOG §5). The adaptive path,
which every reproduction uses, was never affected.

## 7. Reproductions (all with BrainIR's own simulator on BrainIR's own builds)

### 7.1 Published connectivity matrices (`manc_reproduction.md`)

| published network | BrainIR build | pairs (authors / BrainIR) | exact counts |
|---|---|---|---|
| MANC front-leg (4,604; 2025-08-13) | `manc:v1.2.1` | 196,535 / 196,535 | 196,535 (100 %) |
| MANC full VNC (23,532; 2025-10-06) | `manc:v1.2.3` | 1,372,404 / 1,372,404 | 1,372,404 (100 %) |
| MaleCNS front-leg (4,310; 2026-02-10, VNC ROIs) | `male-cns:v1.0` | 118,920 / 118,729 | 118,488 (99.84 %); 116,424 / 116,424 among the 4,280 bodies not proofread since |

Conventions applied as in the paper: floor 5 synapses, autapses removed, output rows of neurons whose label is not
ACh/GABA/Glu zeroed. Sign agreement: the paper's rule on the authors' labels 100 %; BrainIR's conventional rule on
its own `nt_body_prediction` 99.44 % (MANC T1) / 100 % on MaleCNS `nt_consensus`.

### 7.2 DNg100 activation (Fig. 2e)

| statistic | BrainIR, `manc:v1.2.1`, paper NT, n = 1024 | paper (n = 1024) |
|---|---|---|
| mean score | 0.973 | 0.974 |
| median score | 0.999 | 0.999 |
| fraction ≥ 0.5 | 0.997 | 0.998 |
| median active front-leg MNs (range) | 3 (0–5) | 3 (0–6) |
| median MN frequency | 10.75 Hz | ~10–11 Hz |

With BrainIR's own NT labels (`nt_body_prediction` under the paper's sign rule; 72 / 4,604 neurons differ from the
authors' labels) the n = 1024 statistics are identical to three decimals (mean 0.973, median 0.999, 99.7 % ≥ 0.5,
3 (0–5) MNs, 10.75 Hz): the label differences do not touch the rhythm.

MaleCNS front-leg network (`male-cns:v1.0`, authors' consensus NT, VNC synapses only, the benchmark's stimulus neuron,
I = 400, n = 128): mean score 0.983 (paper 0.985), median 0.992 (0.994), 100 % ≥ 0.5 (100 %), median active front-leg
MNs 8 (6–12) (paper 8 (6–16)), median MN frequency 11.4 Hz. Readout = the 130 `fl` motor neurons of the published
network (135 exist in MaleCNS). A first run of this reproduction had stimulated the first DNg100 in the authors' table
order, which in MaleCNS is not the benchmark's neuron, and produced a spurious "recruitment discrepancy" (4 active MNs);
review D caught it (LOG D41). Note on the MANC comparison: the paper's reported statistics use its 138 module-labelled
MNs, BrainIR's the 144 class-labelled front-leg MNs (the six extra MNs matter only if active); the pruning-time
decisions in the authors' code also use the 144.

### 7.3 Interventions (Fig. 3; n = 64, T = 1 s, Modal)

| condition | MANC v1.2.1 BrainIR | paper | MaleCNS v1.0 BrainIR | paper |
|---|---|---|---|---|
| intact | 0.969 | 0.974 | 0.983 | 0.985 |
| silence E1 | 0.000 | 0.000 | 0.044 | 0.028 |
| silence E2 | 0.001 | 0.005 | 0.004 | 0.003 |
| silence I1 | 0.936 | 0.938 | 0.984 | — |
| silence I2 | 0.951 | — | 0.949 | 0.952 |
| silence E3 | 0.755 | — | 0.996 | — |
| keep only the network's modal core (+ stimulus + MNs) | 0.978 (16.4 Hz) | rhythmic | 0.795 (16.7 Hz) | rhythmic |
| keep only the alternative core (other inhibitory partner) | 0.857 | — | 0.765 | — |
| keep only E1 + E2 | 0.000 | — | 0.000 | — |

Every published silencing statement is reproduced to within 0.02 in mean score. The two excitatory core neurons are
individually essential in both connectomes; neither inhibitory partner is essential in the full network, yet the
isolated excitatory pair alone never oscillates: an inhibitory member is required *within the reduced circuit*. The
isolated cores run faster (15–17 Hz) than the intact networks (10.5–11.4 Hz). Files: `results/interventions_*_n64.*`.

### 7.4 Pruning / computational-sufficiency screen (Fig. 3)

1,024 stochastic sufficiency screens (BrainIR's generic `brainir.sim.prune`, one parameter replicate each, T = 1 s) of
the `manc:v1.2.1` front-leg network with the authors' NT labels, on Modal (200 containers, 17.6 min, ≈ $15.5; 0 failed,
1,018 converged, median 101 simulations per screen):

| circuit (activity-based kept set) | BrainIR | paper (1,024 screens) |
|---|---|---|
| E1 + E2 + I1 (modal) | 68.1 % | 62.1 % |
| E1 + E2 + E3 + a fourth interneuron | 16.5 % | 15.2 % (incl. a variant with one motor neuron) |
| E1 + E2 + I2 | 8.1 % | 10.0 % |
| both excitatory core neurons kept | 99.5 % | — |
| kept-set size 3 / 4 / ≥ 5 | 780 / 191 / 53 | — |

The isolated modal circuit oscillates faster (median 16.7 Hz) than the intact network (10.75 Hz). Files:
`results/pruning_manc_v1.2.1_nt-paper_n1024_seed0.*`; registry `5abf1fd8732d5ebb`. The prevalence is now recorded in the
oracle as `brainir_simulation` evidence next to the paper's.

### 7.5 Descending-neuron activation screen (Fig. 1)

933 excitatory descending neurons × 16 parameter replicates, each job auto-tuning its amplitude from 128 (BrainIR's
generic `brainir.sim.screen`), on Modal (100 containers, 42 min, ≈ $18.6, 14,928 jobs, 0 failed):

| statistic | BrainIR (16 replicates) | paper |
|---|---|---|
| rank of the two DNg100 neurons among 933 | 1 and 2 (mean 0.981, 0.911) | 1 and 2 (16-replicate screen); 3 and 4 (128-replicate screen) |
| DNg100 rank among cell types | 1 (0.946 over 32 runs) | 1 |
| candidates with mean score > 0.5 | 31 | 29 (128 replicates) |
| candidates never usable (amplitude could not be tuned) | 134 (14.4 %) | 7.9 % |

The published headline (DNg100 is the top walking-rhythm driver among DNs) reproduces; the DNb08 neurons the paper
follows as a second pathway rank 6 and 14. **Discrepancy**: BrainIR declares almost twice as many candidates
"never usable"; the usability verdict is the tuner's (10 bisection steps between 5 and 1,500 active neurons / ≤ 100
neurons above 100 Hz) and the paper's exact filter is not in its repository (LOG §8). Files:
`results/dn_screen_manc_v1.2.1_nt-paper_r16.*`; registry `eadcf14fb9b2e55b`.

### 7.6 Cross-connectome (`cross_connectome_eval.py`, n = 64, Modal)

Correspondence: every published core neuron and the stimulus map 1:1 (`curated_body_match`, high, ambiguity 1) in
both directions through the public mapping table — because the MaleCNS release carries curated `manc_body_id`
annotations. This is curated evidence restated, not a derivation (LOG D39).

Functional transfer (map one network's modal circuit into the other network and simulate it there keep-only, with
that network's stimulus and MNs):

| direction | intact | destination's own modal core | mapped source modal core |
|---|---|---|---|
| MANC (E1, E2, I1) → MaleCNS (I = 400) | 0.983 | 0.795 | **0.765** (100 % ≥ 0.5, 15.2 Hz) |
| MaleCNS (E1, E2, I2) → MANC (I = 250) | 0.969 | 0.978 | **0.857** (100 % ≥ 0.5, 14.9 Hz) |

The mechanism transfers in both directions: the circuit found in one animal, carried through the public mapping into
the other animal's wiring, generates the motor rhythm there in every replicate. The mapped and own modal cores differ
in their inhibitory member in both directions, so the test is not a tautology. Files: `results/cross_connectome_eval_n64.*`.

### 7.7 Robustness, input sweep, weight noise, negative controls (`robustness_experiments.py`, `manc:v1.2.1`, paired seeds)

- **Parameter spread** (all four SDs × 0 / 0.5 / 1 / 1.5 / 2 / 3; n = 8): mean score 1.000 / 0.989 / 0.969 / 0.958 /
  0.888 / 0.687, fraction ≥ 0.5 = 1 until ×3 (0.75). Paper at ×3: 0.669, 70.8 %.
- **Single parameters** (n = 8): gain a 0.5 / 0.75 / 1 / 1.25 / 1.5 → 0.000 / 0.458 / 0.969 / 0.947 / 0.946 (silent below
  0.75; the most sensitive parameter, as the paper states); threshold θ 5 / 6.5 / 7.5 / 8.5 / 10 → 0.943 / 0.980 / 0.969 /
  0.893 / 0.125 with 13.3 → 9.0 Hz; b 0.015 / 0.02 / 0.03 / 0.04 / 0.06 → 0 / 0 / 0.969 / 0.945 / 0.242 (runaway at 0.06:
  1,608 active neurons); r_max 100–300 → 0.968–0.981, frequency unchanged; τ 10 / 15 / 20 / 30 / 40 ms → 22.5 / 14.1 /
  10.4 / 6.9 / 5.2 Hz (f·τ ≈ 0.21: the only time scale sets the frequency).
- **Input amplitude** (n = 8): I = 180 silent (paper: mostly no active MN); 220 / 260 / 300 / 340 → median MN frequency
  9.26 / 10.76 / 12.12 / 12.90 Hz (paper 9.6 / 11.0 / 12.0 / 12.7).
- **Multiplicative count noise** σ = 0 / 0.05 / 0.1 / 0.15 / 0.2 / 0.3 / 0.5 (n = 64): 0.972 / 0.978 / 0.976 / 0.897 /
  0.866 / 0.727 / 0.433 vs paper (n = 512) 0.974 / 0.965 / 0.954 / 0.884 / 0.814 / 0.669 / 0.435 — the whole curve is
  reproduced within sampling error (an n = 8 pilot had suggested a steeper tail; it was noise).
- **Negative controls** (n = 8; control network built per seed): intact 0.969 (100 % ≥ 0.5, 3 active MNs, 91 active
  neurons); within-class input shuffle 0.173; degree-preserving rewiring 0.262; sign shuffle 0.066; count permutation
  0.193 — 0 % ≥ 0.5 in all four, all failing the same way (massive recruitment, 1,867–3,162 active neurons, slow drifts
  at 1.3–2.0 Hz instead of the ~10 Hz rhythm). The rhythm is a property of this wiring, not of its degree, sign or
  weight statistics.

## 8. The benchmark package (`benchmarks/dng100/`, D31–D33, D38)

[PENDING: bundle hashes after the final export; oracle hash; lock hash]

- **Networks**: `manc_v1.2.1` (primary, 4,604 neurons), `manc_v1.2.3` (4,604), `male-cns_v1.0` (4,309; VNC synapses
  only). Membership = the published node lists; everything else (counts, NT labels, signs, sizes, roles) from BrainIR
  builds. Stimulus = the DNg100 with most output into LegNp(T1)(L); readout = front-leg motor neurons (144 / 144 /
  135).
- **Tier B** (`public/`): release cell types, instances and body IDs. **Tier A** (`public_blind/`): interneuron
  types/instances → salted tokens, neuron IDs → positions (D32). Both: no oracle label, no evaluation output; verified
  by `cleanroom/leakage_check.py` (`LEAKAGE_AUDIT.md`: PASS) and `tests/test_leakage_check.py`.
- **Oracle** (`oracle/oracle.json`): the published core (labels E1–E5, I1, I2 with types, NT, roles), per-network
  ids, modal circuits, essentiality, frequency band, paper statistics, BrainIR reproduction statistics, cross-network
  pairs; every fact carries an evidence level (`paper_simulation`, `brainir_simulation`, `wet_lab`,
  `expert_interpretation`). No interneuron of the circuit has wet-lab evidence.
- **Prediction schema** `brainir.benchmark.prediction` 1.0.0 (`BrainIRMechanismPrediction`: core neurons with roles,
  essentiality, rank, confidence; dynamics; mechanism; cross-connectome claims; method info).
- **Evaluator**: six metric families reported separately (structural, type/role, functional-by-simulation
  [oracle-free], mechanism, cross-connectome, robustness); no aggregate number.
- **Clean room**: `run_method.py` (bundle copy, stripped environment, forbidden imports, prediction hashes recorded
  before evaluation); `PROTOCOL.md` fixes the information budget and what may be claimed.
- **Baselines / nulls** (`baselines/`, run through the clean room on the blind bundle, evaluated by the frozen
  evaluator with 8 simulation replicates): nine non-BrainIR methods. Random matched, k-core/SCC, recurrence-loop,
  community and statistical-motif baselines recover nothing of the published core in any network; degree,
  personalised-PageRank and stimulus→readout betweenness each recover one of the two excitatory core neurons
  (E-core recall 0.5, p ≈ 0.006–0.01 against 500 matched random draws) and never the inhibitory slot, and none of
  their cores is sufficient (keep-only never rhythmic). **The simulation-guided backward-elimination baseline
  (`greedy_prune_sim`) recovers the complete published core in all three networks in tier A** (E-core recall 1.0,
  inhibitory slot filled, precision 1.0, keep-only sufficient in 8/8 replicates, essentiality claims 3/3 confirmed;
  p = 0.002 against the null) in 70–90 s per network. Null distributions (500 draws × three samplers × k ∈ {3, 4, 5}):
  E-core recall mean ≤ 0.005, P(any published label in a random set) 0.4–3.2 %; recall 1.0 is unreachable by chance.
  Consequence for the protocol: on the structural families this benchmark is *solved* by generic simulation-guided
  search under the published model — as it must be, since the published answer was itself produced that way. A
  discovery method therefore has to be judged against `greedy_prune_sim` on the axes the structural score does not
  see: simulation budget, robustness across parameter draws, mechanism explanation, cross-connectome transfer and
  independence from the specific rate model (PROTOCOL.md §5).

## 9. Compute (D34, D37)

`brainir.compute`: `LocalBackend` (process pool) and `ModalBackend` (image built from the repository source; shared
payload uploaded once per campaign to a content-addressed Volume; per-item exceptions returned, never a lost
campaign); every campaign is registered in `benchmarks/dng100/manifests/experiments/` (config, seeds, input hashes,
commit, environment, backend stats, approximate cost, artefact hashes). Modal usage this phase: [PENDING: total $].

## 10. Tests, audits, reviews

[PENDING: final counts] Fast suite (`-m "not real_data"`): 300 tests at commit 247d0f4 (+ agents' suites).
Independent reviews A–F: [PENDING].

## 11. Limitations (precise language)

- Everything called "reproduction" here is agreement between two *simulations* of the same published model on the
  same (rebuilt) anatomy. It says nothing about the fly. The only wet-lab facts in the oracle concern the stimulus
  (DNg100 drives walking) and none concern the interneurons.
- The oracle's `paper_simulation` evidence is one modelling result under one sign rule and one parameter prior; the
  functional family evaluates predictions under that same model, so "sufficient" and "essential" mean *in this model*.
- MaleCNS: the authors' matrix predates v1.0 by 30 proofread bodies (§7.1); the benchmark network uses the released
  v1.0 counts. BrainIR NT labels differ from the authors' for 72 / 4,604 MANC neurons.
- The mapping layer's high-confidence rows are curated annotations of the MaleCNS release; BrainIR did not derive
  them, and the two datasets are different animals.
- Tier B results cannot support an independence claim (type names and body IDs appear in the paper).

## 12. Unresolved issues

[PENDING: keep to what is actually unresolved at the end — LOG §8.6–8.7 plus anything new]

## 13. The one next step for Phase 2

[PENDING]
