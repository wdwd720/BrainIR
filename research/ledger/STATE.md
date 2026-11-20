# Ledger run 1: state (resume here after a context compaction)

Read first, in this order: `research/ledger/RUN1_PROMPT.md` (the spec), this file, `research/ledger/LOG.md` (numbered decisions).

## Fixed facts
- Branch `ledger/v1` from `main` @ 242e472. Never push `main`. Push explicit refspecs only (`git push origin ledger/v1 <tag>`).
- Pushing works from this Mac (dry run OK, `gh` logged in).
- Machine: Apple M5 (10 cores), 16 GB RAM, macOS 26.6, uv 0.13.7, managed CPython 3.12.14. ~59 GiB free at start.
- `caffeinate -dimsu` runs as a background task for the whole run.
- Authors' released screen tables at commit 10e7661 (`smpuglie/Pugliese_2026`):
  - A0 = `figures/DN_Screen-hyak-combined128reps/combined{Score,Activity}Summary.csv` (933 x 128, index = wTable row).
  - A1 = `figures/DN_Screen-hyak-run_id=32818378/{score,activity}Summary.csv` (321 types x 16).
- Modal: active profile = the new, empty workspace (no BrainIR volume). Credit and spending limit: see Stage S.
- Baseline checks (before any ledger change): see `SETUP.md`.

## Deadlines (wall clock, PST; the run started 2026-11-19 20:20)
- Prereg tag `ledger-prereg-v1`: target 2026-11-20 03:00.
- Predictions lock `ledger-predictions-v1`: target 2026-11-20 10:00 at the latest, so at least a third of the run is left for labels.
- Labels `ledger-labels-v1`: by the end of the run.

## Done
- Stage S: caffeinate, branch, prompt saved, `uv sync`, baseline tests and lock checks, MANC v1.2 raw download.

## In progress
- MANC v1.0 raw download. Then ingest v1.0, v1.2.1, v1.2.3. Then G0.

## Next
1. Modal credit check; ledger package + pinned backend; smoke test on DNg100/DNb08 only.
2. G0 (manifests compared against `git show HEAD:data/manifests/...`; restore `data/manifests` after every ingest).
3. Stage 0: exposed list (subagent, names only), PREREG, scoring code + tests, labeler kit, freeze.

## Open problems
- `tests/test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges` fails on this Mac at baseline (platform numerics).
- MaleCNS (arm B2): decide from free disk and RAM after the MANC ingest.
