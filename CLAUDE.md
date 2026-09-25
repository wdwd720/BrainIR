# CLAUDE.md — orientation for future sessions

BrainIR aims to decompile biological neural circuits into compact, executable, testable programs.
**Phase 0 (data & research foundation) is complete**: see `PHASE0_REPORT.md`. Its spec is `goal1.md`.
**Phase 1 (cross-connectome DNg100 benchmark, MaleCNS + MANC) is complete and frozen**: spec `goal2.md`, report
`PHASE1_REPORT.md`, benchmark package `benchmarks/dng100/` locked by `BENCHMARK_LOCK.json` and git tag
`dng100-benchmark-v1`. Changing the bundles, oracle or evaluator requires a new benchmark version (`PROTOCOL.md` §6).
**Phase 2 (blind causal mechanism discovery, spec `goal3.md`) is complete**: report `PHASE2_REPORT.md` (answer-bearing),
locked method BrainIR v1.2.0 (`research/phase2/METHOD_LOCK.json`, tag `brainir-v1-preblind`, commit 959d689), protocol
`research/phase2/SELECTION_PROTOCOL.md`, hidden-evaluation log `research/phase2/HIDDEN_EVAL_LOG.md`. Any change to the
method is a new, separately locked version (goal3 §29). Phase 3 has not started; the report recommends one step (§18).
Read `research/LOG.md` (decisions, discrepancies, pitfalls) before changing anything.

## Phase 2 rules (anti-leakage; goal3 §4)
- This repository's sessions have seen the dng100 oracle. **Method design happens only in fresh agents** working in
  the oracle-free clean directory `C:\Dev\BrainIR_p2clean` (library + public bundles + synthetic suites without
  truth). The orchestrator builds generic infrastructure, runs tournaments and returns aggregate scores only.
- Sync generic files into the clean room one by one (`cp`); never re-run `scripts/make_phase2_cleanroom.py` over it,
  and never copy anything truth-bearing there (`truth/`, build reports, per-instance scores, evaluator outputs).
- Synthetic suites (`data/synthetic/`, git-ignored): development `mechanisms_v1`/`pairs_v1` (readable names, public
  part in the clean room), selection `*_heldout`, confirmation `*_final` (anonymised, fresh salts, never in the clean
  room). Truth, salts, build reports and the truth audit live under `<suite>/truth/` only.
- No hidden-oracle evaluation before `research/phase2/METHOD_LOCK.json` + tag `brainir-v1-preblind`
  (`scripts/method_lock.py`, `scripts/blind_eval.py`); every hidden evaluation is logged, including a reviewer's.
- Post-lock ANSWER-BEARING files (never into any clean room; the builder refuses them): `PHASE2_REPORT.md`,
  `research/phase2/HIDDEN_EVAL_LOG.md`, `hidden_eval_ledger.json`, `reliability/` (hidden rows), `blind_eval/`,
  `reviews/D_leakage.md`, `reviews/D_resolution.md`.
- Clean-room agents for any later version: start them as SEPARATE sessions whose project directory is the clean room, with
  a private temp directory. A subagent inherits this file and the orchestrator's scratchpad (review D, D2). Build a new room
  with the hardened `scripts/make_phase2_cleanroom.py`, and check each manual sync with `--check`.
- Never modify files hashed in `benchmarks/dng100/BENCHMARK_LOCK.json` (incl. `pyproject.toml`, `uv.lock`,
  `src/brainir/{sim,metrics,benchmark,compute}`); `freeze.py --check` must stay green.

## Phase 2 layout
- `src/brainir/discovery/`: `problem.py` (bundle loader, `pack_bundle`, `write_bundle_manifest`), `simulator.py`
  (hard call budget, in-run memo, persistent `CausalEffectCache`), `criteria.py`, `interventions.py`, `interface.py`
  (`DiscoveryResult` → frozen prediction schema, `MethodRegistry`), `run.py`, `synthetic.py` / `synthetic_pairs.py`
  (suites; pairs `--design v2` = harder design), `suite_audit.py` (unplanted sufficient sets, participation audit),
  `tournament.py` (scorer incl. `success_intact`, essential recall, identity claims), `pair_tournament.py`,
  `adversarial.py` (third-party trap generator + scorer, review G), `guard.py` (truth guard), `reliability.py` (node-order
  sweeps), `correspondence.py` / `transfer.py` (cross-network), `perturb.py` (anti-gaming, null correspondence),
  `joint.py` (pairs). Suites: `mechanisms_v1`/`pairs_v1` (dev), `*_heldout` incl. `pairs_v2_heldout`,
  `adversarial_heldout` (selection), `*_final` (confirmation, used once).
- `src/brainir/methods/`: `greedy_reference` + tournament candidates (+ `brainir_v1`); every module present is
  registered on import.
- `scripts/`: `run_tournament.py`, `run_pair_tournament.py`, `budget_curve.py`, `anti_gaming.py`,
  `reliability_sweep.py` (`--criterion-gate` = sensitivity only), `compare_reliability.py` (order-clustered CIs),
  `compare_tournament_methods.py` (paired, instance bootstrap, decision rule), `compare_pair_arms.py`, `ablations.py`
  (`--resummarize`), `transfer_experiments.py`, `build_synthetic_suite.py`, `build_pair_suite.py`,
  `build_adversarial_suite.py`, `rescore_adversarial.py`, `reclassify_suite.py`, `audit_suite_truth.py`,
  `phase2_costs.py`, `method_lock.py`, `blind_eval.py`, `make_phase2_cleanroom.py` (`--check`), `cleanroom_entry/`.
- `research/phase2/`: contracts (`METHOD_DEV_CONTRACT.md`, `CROSS_CONNECTOME_CONTRACT.md`, `COMPOSER_CONTRACT.md`),
  `methods/` (per-method docs), `tournament/`, `reliability/`, `transfer/`, `methods_review.md`.
- Pitfalls: a stray `re.py` in `%TEMP%` breaks scripts run from there (use the scratchpad); Modal workers are Linux
  (`path_basename`); delete smoke-run records from `benchmarks/dng100/manifests/experiments/index.jsonl`.

## Environment (Windows 11 dev machine)
- Always use **uv**: `uv sync`, `uv run ...`.
  - The system CPython 3.12 install is broken. uv manages Python 3.12.14 via `.python-version` and
    `python-preference = "only-managed"`.
  - If `uv` is not on PATH in an old shell, it lives at
    `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`.
  - While another `brainir` process runs, use `uv run --no-sync ...`, because a re-sync fails on the locked exe.
- Set `PYTHONIOENCODING=utf-8` for ad-hoc scripts; the console is cp1252.
- Text artefacts are written with LF. The user's global git has `core.autocrlf=true`, and `.gitattributes` forces LF.
- A Render-plugin PostToolUse hook prints an error after every Write/Edit. It is harmless noise.
- Do not patch code containing `\n` escapes via inline Python in bash heredocs; the Bash tool collapses `\\`. Use
  Edit/Write.

## Commands
```
uv run pytest -m "not real_data"          # ~25 s, synthetic fixtures with hand-derived truth
uv run pytest                              # + real-data smoke tests (needs data/processed)
uv run brainir acquire --tier metadata --tier core --tier synapses                          # MaleCNS v1.0, 18.7 GB
uv run brainir acquire --dataset manc --version v1.0 --tier metadata --tier core --tier synapses   # 3.0 GB
uv run brainir acquire --dataset manc --version v1.2 --tier metadata --tier core            # 1.95 GB
uv run brainir ingest                      # male-cns v1.0, ~8 min -> data/processed/male-cns/v1.0 + data/manifests/
uv run brainir ingest --dataset manc --version v1.0      # ~40 s;  v1.2.1 / v1.2.3 ~50 s each (rebuilt from synapses)
uv run python scripts/audit_data_quality.py
uv run python scripts/gen_schema_docs.py   # docs/schema.md is generated; a test fails if stale
uv run python benchmarks/dng100_walking_cpg/investigate_malecns.py            # answer-key analysis (benchmark only)
uv run python benchmarks/dng100_walking_cpg/reproduce_manc_connectivity.py    # paper matrices vs BrainIR builds
uv run python benchmarks/dng100_walking_cpg/reproduce_dynamics.py stim --dataset manc --version v1.2.1 --n 128
uv run python benchmarks/dng100_walking_cpg/reproduce_interventions.py --dataset manc --version v1.2.1 --n 64
uv run python benchmarks/dng100_walking_cpg/reproduce_pruning.py --n 1024 --backend modal --containers 200     # ~$25
uv run python benchmarks/dng100_walking_cpg/reproduce_dn_screen.py --replicates 16 --backend modal              # ~$10
uv run python benchmarks/dng100_walking_cpg/cross_connectome_eval.py --n 32                                    # both directions
uv run python benchmarks/dng100_walking_cpg/robustness_experiments.py dt-convergence|param-sweep|input-sweep|weight-noise|negative-controls
uv run python benchmarks/dng100/build_public_bundle.py      # re-export public/ + public_blind/ (then leakage_check, freeze)
uv run python benchmarks/dng100/build_cross_connectome_reference.py   # oracle/cross_connectome_reference.json from the mapping tables
uv run python benchmarks/dng100/cleanroom/leakage_check.py --write-audit
uv run python benchmarks/dng100/baselines/run_all_baselines.py   # clean-room runs + frozen evaluation of every baseline
uv run python benchmarks/dng100/freeze.py [--check]        # BENCHMARK_LOCK.json (git tag dng100-benchmark-v1)
uv run brainir mapping build --a male-cns:v1.0 --b manc:v1.2.1   # cross-connectome candidate table + summary
uv run brainir --help                      # neuron/type/search/up/down/edge/khop/paths/synapses/mapping queries
```

## Layout
- `src/brainir/`
  - `sources/registry.py`: pinned official files (`male-cns:v1.0`, `manc:v1.0`, `manc:v1.2`) and `BUILD_VERSIONS`
    (processed builds `manc:v1.2.1` / `manc:v1.2.3` come from raw `manc:v1.2` + an annotation snapshot)
  - `acquire.py`
  - `schema/`: evidence kinds, vocab (sign rule, role-class rule), Arrow tables, pydantic models
  - `ingest/common.py` (generic steps/validation/writing), `ingest/malecns.py`, `ingest/manc.py` (adapters)
  - `graph.py`: `Connectome` API (`role_class` derived on load; `sign_hypothesis(basis="auto")`)
  - `sim/`: rate-model simulator (`model.py`), signed-matrix builder (`weights.py`), experiments, pruning search
    (`prune.py`), activation screen (`screen.py`)
  - `metrics/rhythm.py`: published rhythmicity score + independent measures
  - `mapping.py`: MaleCNS↔MANC candidate table (never identity; see `research/cross_connectome_mapping.md`)
  - `benchmark/`: prediction schema + public-bundle exporter (safe for discovery code); `compute/`: local/Modal
    backends + experiment registry
  - `synapses.py`, `manifest.py`, `cli.py`
  - `testing/`: `synthetic.py` (MaleCNS fixture), `synthetic_manc.py` (same truth in MANC formats),
    `signals.py` / `circuits.py` (labelled test signals and model circuits)
- `data/`: `raw/` (immutable, read-only), `processed/` (rebuilt only by code) and `cache/` are git-ignored;
  `manifests/` is committed. MANC raw dirs: `raw/manc/v1.0/`, `raw/manc/v1.2/`; the bz2 partner table of v1.0 is
  decompressed into `cache/manc_v1.0/` (content-addressed).
- `research/`: `LOG.md`, `data_ecosystem.md`, `connectome_ecosystem_survey.md`, `manc_release_notes.md`,
  `literature/`, `audit/`.
- `benchmarks/dng100_walking_cpg/`: **ANSWER KEY. Never feed it to discovery code.** See its `README.md` for the
  list of answer-bearing files (includes `goal1.md`, `goal2.md` and `research/literature/`). Also holds the
  reproduction scripts (`reproduce_manc_connectivity.py`, `reproduce_dynamics.py`, `reproduce_interventions.py`,
  `robustness_experiments.py`) and their `results/`.
- `benchmarks/dng100/`: the frozen benchmark package (`BENCHMARK_LOCK.json`, `freeze.py --check`). `public/` (tier B)
  and `public_blind/` (tier A: tokenised interneuron types, salted-permutation positional ids) are the ONLY things a
  discovery method may see; `oracle/` (answer + tier-A id maps with real types + salt + frozen curated cross-connectome
  pairs), `evaluator/evaluate.py` (metric families, reads the oracle; `--run-record` verifies hashes), `cleanroom/`
  (runner with the audit-hook sandbox `_sandbox.py`, example method, `leakage_check.py` → `LEAKAGE_AUDIT.md`),
  `baselines/` (nine non-BrainIR methods + nulls; `results/` is answer-bearing), `nodes/`, `manifests/`, `PROTOCOL.md`.
  Rebuild bundles with `uv run python benchmarks/dng100/build_public_bundle.py`; run a method with
  `cleanroom/run_method.py`; evaluate with `evaluator/evaluate.py`.

## MANC facts you must not re-derive (details: LOG D21–D28, §3.11–3.16)
- The paper's MANC front-leg network is neuPrint `manc:v1.2.1`; its full-VNC network is `manc:v1.2.3`. Both are
  reproduced exactly (every pair, every count) by BrainIR's rebuilds from the public v1.2 synapse-partner table.
- neuPrint MANC counts: `weight` = pairs with `conf_post >= 0.4`, `weightHP` = `conf_post >= 0.7`, `weightHR` = all;
  rows with weight 0 exist (HR-only) and are dropped. Autapses are kept by BrainIR, zeroed by the authors.
- Front-leg motor-neuron readout = role `vnc_motor` (MANC `super_class == motor_neuron`, MaleCNS `vnc_motor`) and
  `sub_class == 'fl'` (144 in v1.2.1 = the authors' set; 130 in the paper's MaleCNS network; the 4 `nm` neck MNs are
  excluded). The benchmark stimulus = the DNg100 with the most output into `LegNp(T1)(L)` (`choose_stimulus`), NOT the
  first DNg100 in table order (that cost a spurious "discrepancy" once, LOG D41).
- Every published dynamical claim is reproduced by BrainIR's simulator (PHASE1_REPORT §7). How the baselines fare on
  the answer is in the answer-bearing `PHASE1_REPORT.md` / `PROTOCOL.md` §5 only: subagents inherit this file, so it must
  state nothing about the answer's size, composition or recoverability (review D, D1). Modal campaigns cost cents to
  ~$50 each (shared payload, LOG D37).

## Non-negotiable rules
1. Keep observations (EM anatomy), curated annotations, ML predictions (NT), rule-based hypotheses (sign) and model
   parameters in separate columns/types. `synapse_count` is not strength.
2. Neurons = bodies with a superclass (source definition). Edges are neuron→neuron. Autapses are kept and flagged.
   Per-edge neuropil = PSD location, with an explicit `<unassigned>` remainder.
3. IDs are only meaningful with `(dataset, version)`: `neuron_uid = dataset:version:id`.
4. Never commit data, tokens or absolute paths. Provenance records use `$DATA/...` / `$REPO/...`.
5. `src/` must not contain benchmark answer tokens or import `benchmarks/`/`research/`
   (`tests/test_leakage_guard.py`).
6. After changing the schema, regenerate `docs/schema.md`. After changing the pipeline, rebuild and commit the new
   manifest.

## Open items (details in research/LOG.md §8)
- The live neuPrint `male-cns:v1.0` got a property update on 2026-06-08 after the bulk export. Verifying it needs a
  neuPrint login; tokens were reset in Aug 2026.
- Next phase candidates are listed at the end of `PHASE0_REPORT.md`.
