# CLAUDE.md — orientation for future sessions

BrainIR aims to decompile biological neural circuits into compact, executable, testable programs.
**Phase 0 (data & research foundation) is complete**: see `PHASE0_REPORT.md`. Its spec is `goal1.md`.
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
uv run pytest -m "not real_data"          # ~20 s, synthetic fixture with hand-derived truth
uv run pytest                              # + real-data smoke tests (needs data/processed)
uv run brainir acquire --tier metadata --tier core --tier synapses   # 18.7 GB, pinned + verified
uv run brainir ingest                      # ~7-8 min -> data/processed/male-cns/v1.0 + data/manifests/
uv run python scripts/audit_data_quality.py
uv run python scripts/gen_schema_docs.py   # docs/schema.md is generated; a test fails if stale
uv run python benchmarks/dng100_walking_cpg/investigate_malecns.py   # answer-key analysis (benchmark only)
uv run brainir --help                      # neuron/type/search/up/down/edge/khop/paths/synapses queries
```

## Layout
- `src/brainir/`
  - `sources/registry.py`: pinned official files
  - `acquire.py`
  - `schema/`: evidence kinds, vocab and sign rule, Arrow tables, pydantic models
  - `ingest/malecns.py`: pipeline + checks
  - `graph.py`: `Connectome` API
  - `synapses.py`
  - `manifest.py`
  - `cli.py`
  - `testing/synthetic.py`: fixture
- `data/`: `raw/` (immutable, read-only), `processed/` (rebuilt only by code) and `cache/` are git-ignored;
  `manifests/` is committed.
- `research/`: `LOG.md`, `data_ecosystem.md`, `connectome_ecosystem_survey.md`, `literature/`, `audit/`.
- `benchmarks/dng100_walking_cpg/`: **ANSWER KEY. Never feed it to discovery code.** See its `README.md` for the
  list of answer-bearing files (includes `goal1.md` and `research/literature/`).

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
