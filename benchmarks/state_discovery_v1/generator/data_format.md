# Dataset format

Reference implementation: `reference/data.py` (`Dataset`, `write_dataset`, `append_rows`). On disk a dataset is a directory:

```
manifest.json   {"dataset_id", "version", "dt", "systems": {system_id: {"observed": [ids], "readout": [ids] (may be empty for
                 synthetic systems whose readout is a computed signal), "input_dim": int, "kind": "synthetic", "group": null,
                 ...}}, "splits": [...], "families": {...}}
index.jsonl     one line per trajectory: {"key", "system_id", "split", "family", "protocol": {...}, "info": {...}}
traj/<key>.npz  t (T,), x (T, N_obs) float32, u (T, n_u) float32, y (T, n_y) float32
```

- x holds the system's OBSERVED microstate (the encoder input; never the readout), y its readout, u its external input.
- The `family` field of the index is a PUBLIC label of the protocol family (e.g. "nominal", "kick", "silence_single",
  "group_silence", "param_draw"), never the system's dynamical family.
- The manifest must not reveal the system's dynamical family, trap, latent dimension or implementation group: system ids are
  opaque, and `group` stays null in public datasets.
- Truth (latent trajectories z, dimensions, groups, descriptions) goes to a SEPARATE directory in whatever format you document.
