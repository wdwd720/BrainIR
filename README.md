# BrainIR

**Goal (long-term):** automatically *decompile* biological neural circuits into compact, executable,
human-readable programs. Each program's variables and operations should map back onto real neurons, and its causal
predictions should be testable through interventions.

**Current phase: Phase 0 — data & research foundation.** Status and results: [`PHASE0_REPORT.md`](PHASE0_REPORT.md).
The Phase 0 spec is [`goal1.md`](goal1.md). No modelling, synthesis or simulation code exists yet, by design.

## What exists

| component | where |
|---|---|
| Pinned registry of official MaleCNS v1.0 files (GCS generation + checksums) | `src/brainir/sources/registry.py` |
| Verified, resumable acquisition → immutable `data/raw/` | `src/brainir/acquire.py` |
| Canonical schema: Arrow tables with per-column *evidence kind*; pydantic records (incl. Experiment/Trial) | `src/brainir/schema/`, `docs/schema.md` |
| Deterministic ingestion + ~70 validation checks → `data/processed/` | `src/brainir/ingest/malecns.py` |
| Machine-readable manifest + validation report (committed) | `data/manifests/` |
| Graph access layer (neighbours, neuropils, sign hypotheses, k-hop, paths) | `src/brainir/graph.py` |
| CLI | `brainir --help` |
| DNg100 walking-CPG benchmark: spec, answer key, MaleCNS v1.0 verification (**answer key: never an input**) | `benchmarks/dng100_walking_cpg/` |
| Literature notes, ecosystem survey, research/engineering log | `research/` |
| Tests (synthetic fixture with hand-derived truth + real-data smoke tests) | `tests/` |

## Quickstart (Windows / Linux / macOS)

Requires [uv](https://docs.astral.sh/uv/). uv installs its own CPython 3.12; the system Python is not used.

```bash
uv sync                                                     # create .venv from uv.lock
uv run pytest -m "not real_data"                            # unit tests (synthetic data, ~20 s)

uv run brainir acquire --tier metadata --tier core --tier synapses   # ~18.7 GB, checksum-verified
uv run brainir ingest                                                # ~7-8 min; writes data/processed + manifest
uv run pytest                                                        # all tests incl. real-data smoke tests
uv run python scripts/audit_data_quality.py                          # independent audit -> research/audit/
```

Query examples:

```bash
uv run brainir type DNg100
uv run brainir down 10056 --min 5 --limit 15        # strongest outputs of the left-leg DNg100
uv run brainir edge 10056 <post_id>                 # counts, neuropils, sign hypothesis (rule-versioned)
uv run brainir khop 10056 -k 2 --direction out --min 10
```

```python
from brainir.graph import Connectome
cx = Connectome.open("male-cns", "v1.0")      # 166,700 neurons, 25.58M edges, ~7 s to load
cx.neuron_model(10056)                         # typed record with provenance
cx.downstream(10056, min_count=5)
cx.neuropil_breakdown(10056, int(cx.downstream(10056).post_id[0]))
```

## Ground rules

* Raw data is immutable, and processed data is rebuilt only by code. Every artefact is traceable through
  `data/manifests/*.manifest.json`.
* Keep observations, curated annotations, ML predictions, rule-based hypotheses and model parameters separate. Every
  column declares which one it is.
* `synapse_count` is not synaptic strength. A predicted neurotransmitter is not physiology. One connectome is one fly.
* Benchmark answers live only in `benchmarks/` and are never inputs to discovery. `tests/test_leakage_guard.py`
  enforces this.

## Data licence and citation

MaleCNS is licensed CC-BY 4.0 (HHMI Janelia FlyEM, University of Cambridge, MRC LMB, Google Research). Cite:
Berg S, Beckett IR, Costa M, Schlegel P, Januszewski M, *et al.* "Sexual dimorphism in the complete *Drosophila* male
central nervous system connectome", *Cell* (2026), doi:10.1016/j.cell.2026.08.015 (preprint
doi:10.1101/2025.10.09.680999). Exact details are in the manifest.
