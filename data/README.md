# data/

Bulk data is **not** in git (see `.gitignore`); only this README and `manifests/` are versioned.
Relocate the bulk data root with the environment variable `BRAINIR_DATA_DIR` (manifests stay here).

```
data/
  raw/<dataset>/<version>/            immutable official downloads (read-only files), mirrors the
                                      remote bucket layout; ':' in remote names -> '_' (Windows)
      _acquisition.json               per-file URL, GCS generation, size, CRC32C/MD5/SHA-256, timestamps
      docs/                           snapshots of the official documentation pages at acquisition time
  processed/<dataset>/<version>/      canonical BrainIR tables, rebuilt ONLY by `brainir ingest`
      neurons.parquet                 one row per neuron (source definition: has a superclass)
      connections.parquet             neuron->neuron synapse counts (+HP subset, autapse flag, dominant neuropil)
      connection_neuropils.parquet    per-edge counts by primary neuropil of the PSD (+ '<unassigned>')
      neuron_neuropils.parquet        per-neuron pre/post counts by primary neuropil (+ '<unassigned>')
      neuropils.parquet               ROI catalogue and hierarchy
      neuron_annotations_source.parquet  verbatim typed copy of all source annotation columns (all bodies)
      validation_report.{json,md}     every check the build performed
      build_info.json                 inputs (sha256, generation), outputs (sha256, rows), timings, env, git
  cache/                              disposable (DuckDB spill files, logs, API caches)
  manifests/                          COMMITTED machine-readable provenance
      <dataset>_<version>.manifest.json
      <dataset>_<version>.validation.{json,md}
```

Rules

* Never edit files in `raw/` or `processed/` by hand. Raw files are read-only; processed files are
  overwritten atomically by the pipeline.
* Rebuild everything from scratch with:

  ```
  uv run brainir acquire --tier metadata --tier core --tier synapses                          # MaleCNS v1.0, ~18.7 GB
  uv run brainir acquire --dataset manc --version v1.0 --tier metadata --tier core --tier synapses   # MANC v1.0, ~3.0 GB
  uv run brainir acquire --dataset manc --version v1.2 --tier metadata --tier core            # MANC v1.2, ~1.95 GB
  uv run brainir ingest                                               # male-cns v1.0, ~8 min on 8 cores / 16 GB free RAM
  uv run brainir ingest --dataset manc --version v1.0                 # ~40 s
  uv run brainir ingest --dataset manc --version v1.2.1               # ~50 s (needs raw manc/v1.0 for ROIs + NT)
  uv run brainir ingest --dataset manc --version v1.2.3               # ~50 s
  ```

* MANC layout: `raw/manc/v1.0/` (neuPrint bulk export) and `raw/manc/v1.2/` (synapse-partner table + neuroglancer
  annotation snapshots) feed three processed builds, `processed/manc/{v1.0,v1.2.1,v1.2.3}/`. The neuron table of the
  v1.2.x builds has no proofreading status (null `status`/`is_traced`) and carries body-level NT predictions from
  v1.0 by body ID; see the manifests' `definitions` for every such choice.
* `raw/external/` holds third-party derived files (e.g. the authors' matrices of a paper) fetched by benchmark
  scripts with pinned SHA-256; also git-ignored.

* Schemas (with per-column evidence kind) are defined in `src/brainir/schema/tables.py` and documented
  in `docs/schema.md`.
