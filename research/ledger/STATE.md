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
- Stage 0 DONE (`ledger-prereg-v1`, pushed, OTS). **Do not push the branch again until labels are frozen** (predictions
  are now in the working tree; PREREG 13).
- Stage 1: A1/A1-lo10/A0/B0/S/B1/B1-alt written; G1 PASS, G2 investigated (L26). Running: controls (10 campaigns,
  ~5 h), then B5 -> B4 -> B2 (parallel chain); G4 on B1-lo10/B1-lo5; independent arms review (subagent).
- After the campaigns: G4 for each locked simulated arm, G5 baseline checks, fix review findings, pre-mortem, lock
  predictions (`lock.py predictions <arms> B3=... B6=...`, `git add -f` parquet files), tag (not pushed), OTS.

## Next (Stage 1, after the tag)
1. `run_arms.py authors`, `b0`, `baselines`; `b1 --lower 5`, `b1 --lower 10`, `select-b1`; `g1`; `g2`; `controls`; `b5`;
   `b4`; `b2`; `g4 --only <campaign>` for each locked simulated arm.
2. Gates G1, G2, G4, G5 (baseline checks again), independent review of the arms -> fix -> `lock_predictions` (arms list)
   -> tag `ledger-predictions-v1` (NOT pushed until labels freeze, PREREG 13) -> OTS.
3. Stage 2: pilot one family -> pass 1 (8 families, waves of 4) -> collect/validate/repair -> labels_prepare pass2 ->
   pass 2 Phase A -> Phase B -> search x2 -> labels_prepare adjudication -> adjudication (general, dedicated) -> audit ->
   finalize -> lock labels -> tag -> push branch + all three tags -> OTS -> HANDOFF_1.md.

## Rules to remember
- Orchestrator never opens per-type labels (only validation summaries and aggregate counts) and never joins labels with
  predictions. B3/B6 are not locked (G3 failed, L16/L18).

## Open problems
- `tests/test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges` fails on this Mac at baseline (platform numerics).
- MaleCNS: bulk data not downloaded (L9); B2 uses the authors' pinned MaleCNS network + MaleCNS annotations.
