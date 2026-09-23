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
  uv run brainir acquire --tier metadata --tier core --tier synapses   # ~18.7 GB download, verified
  uv run brainir ingest                                               # ~10-15 min on 8 cores / 16 GB free RAM
  ```

* Schemas (with per-column evidence kind) are defined in `src/brainir/schema/tables.py` and documented
  in `docs/schema.md`.
