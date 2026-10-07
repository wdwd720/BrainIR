# Phase 4 real data: build and verification (fork E8, 2026-09-26; rebuilt with dataset design v2 by fork E14, 2026-09-27)

Records: `REAL_DATA_BUILD.json` (every run, per-system counts, store publication, costs, verifications),
`build_manifests/real_<level>_<system>.json` (sha256 of every built file), `MODAL_RUNS.md` (runs E8-1 to E8-7, E14-1 to E14-4).

## Current data: dataset design v2 (fork E14, 2026-09-27; LOG P4-D36, research/phase4/DATA_DESIGN_V2.md)

Both levels were rebuilt on the same path as below after the design-v2 changes: no explicit initial state in any set ('obs.init' and
the pools' 'init' sources are restarts from nominal passive trajectories of the same parameter draw), capability records with
system-wide values only, every intervention item checked equal to its twin through its onset sample, kick items labelled by their
realized size.

| level | planned -> records | errors / replaced / dropped | store publication | kick items clipped (relabelled) | constant-future items | wall, cost |
|---|---|---|---|---|---|---|
| public | 4,202 -> 6,554 (521 per full network, 713 per mechanism; 600 pool states, 3 sequences, 20 floor states, 16 lift cases per system) | 0 / 0 / 0 | 5,808 new, 746 already present and bit-identical, 0 mismatches | 252 / 791 (191) | 10 test items (kept) | 588 s, ~$0.88 |
| B | 1,600 -> 1,840 (184 per system) | 0 / 0 / 0 | 1,336 new, 504 present and bit-identical, 0 mismatches | 32 / 80 (29) | 24 (kept) | 378 s, ~$0.58 |

Verification of the public data (downloaded to `$DATA/phase4/real/real_public/public`, 6,604 files, 2.10 GB; this machine = a gated
host):
- whitelists (`suites.assert_public_part`) pass for every system; the local copy equals the build manifests file for file
  (`freeze_manifests.verify_local`, real part);
- public policy: 6,554 rows and 24,200 pool futures, 0 violations; 0 rows with an explicit initial state (before: 620 'obs.init' rows);
- onset / twin check: 2,352 intervention items, 0 differ from their twin at or before their onset sample;
- bit-identity: 120 re-simulations (12 per system, restart sources replayed first), all equal to the stored arrays and keys;
- host fingerprints (`scripts/p4/check_build_hosts.py`): 6,554 / 6,554 public rows and 1,840 / 1,840 Level B rows (read on the eval
  volume) carry an admissible fingerprint (AMD, AVX2, no AVX-512F, Linux, pinned numerical stack).

Calibration check against the targets version 3 (`scripts/p4/calibration_check_real.py` -> `CALIBRATION_CHECK_real_public.json`; LOG P4-D38): the targets are now computed from this data, and the check computes the statistics on every public record, as the
targets' record selection states. All 3,110 per-system values equal the targets' per-system values exactly; 0 values outside the
class range or the real range, 0 checked values outside their target range, `calibstats.compare` 35 / 35 (307 s). With the earlier
selection (`--max-per-kind 40`: 40 records per record kind plus their twins; `CALIBRATION_CHECK_real_public_max40.json`) the same
systems give 745 values outside their class range, 350 outside the real range and 1 checked value outside its target range
(`kick_rel_scale_p50` of one mechanism, 0.0327 against 0.0374), still 35 / 35: pooled statistics depend on the selection, so
criterion 11 uses the targets' selection.

The sections below describe the E8 build (dataset design v1, SUPERSEDED: its 'obs.init' rows set explicit initial states on half of
the observed units, up to the top of the rate range).

## What was built (E8, design v1, superseded)

Both levels were built on Modal by `scripts/p4/build_on_modal.py real --level public|B`. Each system ran in its own `build` container
(16 cores, host-gated). The builds ran after the dataset fixes of reviews F, H and E (`brainir_causal.suites`):
- whitelisted public files, with no truth, no network names and no engine sizes in any row;
- salted Level B streams;
- the numerical-floor futures and the simulated pool input;
- failed and non-finite records refused, and a host fingerprint on every record.

| level | where | per system | total |
|---|---|---|---|
| public (development data; enters the clean room) | fit volume `data/real/real_public/public/<system>`; store volume `store/`; local copy `$DATA/phase4/real/real_public/public` | full networks: 353 planned trajectories -> 521 records; mechanisms: 449 -> 713. Every system: 600 pool states, 3 sequences (kick, current pulse, silencing: the trained kinds), 20 floor states, 16 lift cases | 6,554 records, 2.32 GB; 0 errors, 0 replacements |
| B (Level B validation sets, orchestrator-held) | eval volume `data/real/real_levelb/eval/<system>`; store `/evalvol/store` | 160 planned -> 184 records: in-family cells on public targets with twins, 16 passive, 120 pool sources. 600 pool states, 3 sequences, 20 floor states | 1,840 records, 1.21 GB; 0 errors |

How the Level B sets are drawn:
- They follow the public policy (public-range seeds, trained families, public targets).
- Their streams are SALTED (`suites.real_stream_seed`), so they cannot be regenerated from the public code.

Wall time and cost:
- public: 780 s, about $1.44;
- Level B: 374 s, about $0.55;
- earlier superseded or killed attempts: see MODAL_RUNS.md.

## Verification (E8, design v1; `scripts/p4/verify_real_build.py`, all ten systems, this machine = a gated host)

- **Whitelists:** `suites.assert_public_part` passes for every public part. It checks:
  - the files present;
  - the record, row, meta, info, pool and lift keys;
  - the keys of the public futures.
- **Public policy:** every protocol passes `simservice.check_public`, with 0 violations. That covers the 6,554 rows and the 24,200 pool futures rebuilt from pool.json (every state under every sequence plus the floor repeats; restart keys = the pool's own sources).
- **Bit-identity:** 60 re-simulations on this machine, all equal to the stored arrays and keys:
  - 20 records, including full networks and twins;
  - 10 pool-source trajectories;
  - 30 pool futures restarted from them (the no-intervention future including x and u, one sequence, and the floor repeat).
- **Store publication:** 4,086 records that earlier runs (E8-1, E8-2, on other hosts) had already put on the store volume were compared array by array with the new ones. All were bit-identical (0 mismatches).

## Calibration check (E8, design v1, against the v1 targets; `scripts/p4/calibration_check_real.py`)

`calibstats.compute_all` on each system's public records was compared with `public/calibration_targets.json`.

Suite-level result: `calibstats.compare` passes 35 of 35 checked statistics.

Per-system values outside their real range:
- 854 of 3,050 values fall outside the range over all real systems;
- 27 values of checked statistics fall outside their target range;
- almost all of these are statistics of the INTERVENTION DESIGN, not of the systems.

Phase 4 design differences behind these values:
- magnitude classes 0.1-3 m_s, including below-detection and weak;
- onsets at 0.15-0.5 T;
- no persistent silencing among the trained real families;
- initial states up to 200 Hz;
- twins that share their item's integration pieces (a no-op breakpoint at the onset). This makes the pre-event noise floor exactly 0.

The checked statistics outside their target range:
- full networks: effect sizes (`eff_rel_x_p50`, `eff_rel_y_p50`, `eff_rms_x_rel_scale_p50`, `frac_eff_rel_y_below_0.01`, `snr_param_x/y_median`), 2-3x below the targets;
- `peak_rate_rel_p50`: 5 systems above 8.8;
- `kick_rel_scale_p50`: 2 mechanisms below;
- `kick_clipped_frac_all`: 1 mechanism below;
- `dim_x_pooled_obs_n95`: one full network, 43 against at most 41.

Consequence: the design-dependent targets were derived under the earlier data design, so they do not describe data built under this design.

Pairing note: the script removes no-op stimulus breakpoints before pairing. Without that step, `calibstats.pair_twins` finds no pair in Phase 4 data.
