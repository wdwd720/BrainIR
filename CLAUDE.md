# CLAUDE.md — orientation for future sessions

BrainIR aims to decompile biological neural circuits into compact, executable, testable programs.
**Phase 0 (data & research foundation) is complete**: see `PHASE0_REPORT.md`. Its spec is `goal1.md`.
**Phase 1 (cross-connectome DNg100 benchmark, MaleCNS + MANC) is in progress**: spec `goal2.md`; status in
`research/LOG.md` §10 and `PHASE1_REPORT.md` (when written).
Read `research/LOG.md` (decisions, discrepancies, pitfalls) before changing anything.

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
- `benchmarks/dng100/`: the frozen benchmark package. `public/` (tier B) and `public_blind/` (tier A: tokenised
  interneuron types, positional ids) are the ONLY things a discovery method may see; `oracle/` (answer + tier-A id
  maps + salt), `evaluator/evaluate.py` (metric families, reads the oracle), `cleanroom/` (runner, example method,
  `leakage_check.py` → `LEAKAGE_AUDIT.md`), `baselines/`, `nodes/`, `manifests/`. Rebuild bundles with
  `uv run python benchmarks/dng100/build_public_bundle.py`; run a method with `cleanroom/run_method.py`; evaluate
  with `evaluator/evaluate.py`.

## MANC facts you must not re-derive (details: LOG D21–D28, §3.11–3.16)
- The paper's MANC front-leg network is neuPrint `manc:v1.2.1`; its full-VNC network is `manc:v1.2.3`. Both are
  reproduced exactly (every pair, every count) by BrainIR's rebuilds from the public v1.2 synapse-partner table.
- neuPrint MANC counts: `weight` = pairs with `conf_post >= 0.4`, `weightHP` = `conf_post >= 0.7`, `weightHR` = all;
  rows with weight 0 exist (HR-only) and are dropped. Autapses are kept by BrainIR, zeroed by the authors.
- Front-leg motor-neuron readout = `super_class == motor_neuron` and `sub_class == 'fl'` (144 in v1.2.1 = the
  authors' set; the 4 `nm` neck MNs are excluded).

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
