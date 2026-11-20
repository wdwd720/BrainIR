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
- Stage S: caffeinate, branch, prompt saved, `uv sync`, baseline (1 platform test failure, P3 benchmark check cannot run),
  MANC downloads + builds, **G0 PASS** (byte-identical builds; authors' front-leg and full-cord matrices exact), Modal
  account checked (L7), pinned ledger backend with numerics env (L11-L12), pilot (DNg100/DNb08) vs B0 and determinism.
- Stage 0 drafted: PREREG v1, scoring pipeline + UNBLIND guard, label schema/aggregator/agreement, kit (PROTOCOL, prompts,
  families, type list, synonyms, exposed list), label-side scripts (rooms/prepare/collect), arm code (`arms.py`,
  `run_arms.py`), lock script. 47 ledger tests pass.
- DNg100-only calibration on the full cord (L14) and **G3 evaluated before the freeze: FAIL on item 4 (coupling)** ->
  B3/B6 not locked (L16).

## In progress
- Independent review of Stage 0 (subagent) -> fix -> lock_prereg -> tag `ledger-prereg-v1` -> push -> OTS.
- Driver-line map extraction (subagent; anatomy only) -> kit v1.1 before Stage 2 if it arrives after the tag.

## Next (Stage 1, after the tag)
1. `run_arms.py authors`, `b0`, `baselines`; `b1 --lower 5`, `b1 --lower 10`, `select-b1`; `g1`; `controls`; `b5`; `b4`; `b2`.
2. Gates G1, G2 (B1 vs A1), G4 (determinism re-runs), G5 (baseline checks), independent review of the arms.
3. Lock predictions (LOCK_predictions_v1.json, tag, OTS; push the predictions tag only after the label passes, LOG).
4. Stage 2: pilot labeler on one family, then pass 1 (8 families), pass 2, search x2, adjudication, finalize, freeze labels.

## Open problems
- `tests/test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges` fails on this Mac at baseline (platform numerics).
- MaleCNS (arm B2): decide from free disk and RAM after the MANC ingest.
