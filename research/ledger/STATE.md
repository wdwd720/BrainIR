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
- Stage 1: A1/A1-lo10/A0/B0/S/B1/B1-alt/B1-lo5/B1-lo10/B5/B2 written; G1 PASS; G2 investigated (L26); arms review done
  (verdict LOCK with conditions; fixes in 35ba697, L27); batched execution (L28). G4 PASS: B1-lo10, B1-lo5.
- (01:05 PST) Modal workspace switched (L31). Controls 101-103 done; 104-105, 201-205 resumed via `controls --only <name>` (log
  `data/cache/ledger_logs/stage1_controls_resumed.log`); G4 watcher 2 (`g4_watch2.log`) for 103-205. Earlier: a watcher runs
  `g4 --only` for B4 and each control as soon as its `types.csv` appears (log `data/cache/ledger_logs/g4_watch.log`);
  G5 pre-lock checks (log `data/cache/ledger_logs/g5_prelock.log`).
- (08:32 PST) Spend guard paused at 02:25 (L33); the last control and its G4 resumed and finished at 08:40.
- (08:47 PST) **PREDICTIONS LOCKED**: `LOCK_predictions_v1.json` (e8bc214), tag `ledger-predictions-v1` (local only, NOT pushed),
  verified on HEAD and on the tag, OTS (L35). Stage 1 is closed: never edit predictions/, gates/, reviews/ or ledger code hashed
  by the lock (new results go to new files).
- **Stage 2 cutoffs (L35):** pass 1 + searches end 13:30; pass 2 (A+B) 16:45; adjudication 18:30; labels lock/tag/OTS/push 19:15;
  then G5 + HANDOFF. Labelers are detached: after every launch keep a tracked background waiter (exits when a labeler PID dies
  or after ~20 min) so the orchestrator is woken; check the wall clock on every wake.
- (10:30 PST) L40: labels finalized and redacted; next `lock.py labels`, commit, tag `ledger-labels-v1`, OTS, push
  (`git push origin ledger/v1 ledger-prereg-v1 ledger-predictions-v1 ledger-labels-v1`), G5 end, HANDOFF.
- (10:05 PST) L39: pass 2 done; adjudication-general and adjudication-dedicated running. Next: collect, audit,
  `labels_collect.py finalize`, labels pre-mortem, `lock.py labels`, tag `ledger-labels-v1`, OTS, push (explicit refspecs),
  G5, HANDOFF.
- (09:39 PST) L38: pass 1 + searches done; pass2 Phase A running for catalogue, grooming, steering, escape_landing,
  pugliese_dedicated, recent_broad. Next per session when it ends: `labels_rooms.py phaseb --session pass2-<fam>`; after all
  Phase B: collect, audit, `labels_prepare.py adjudication`, `launch adjudication --name general` / `--name dedicated`.
- (09:15 PST) L37: pass1-atlas, pass1-walking_stopping, search-search_names BREACHED (read their own saved fetch images) ->
  excluded as frozen, stopped. Tool-results guard (scratchpad `toolresults_guard.sh`) MUST stay running for every later session;
  restart it after any interruption. Running clean: steering(ended), catalogue, pugliese_dedicated, grooming, escape_landing,
  recent_broad, search_behaviour.
- (09:04 PST) Stage 2 running (L36): pass1 steering/atlas/catalogue/pugliese_dedicated/walking_stopping + both searches alive;
  to launch as slots free: grooming, escape_landing, recent_broad. Quota probe: scratchpad `quota.sh` (stream events) and a
  one-turn haiku probe in scratchpad/qprobe; stop launching at 85 %, stop labelers at 93 %.
- (08:41 PST) ALL Modal work done. 10/10 controls pass `r2_controls_check.py`; G4 1,500/1,500 over 15 campaigns; dry run on all
  22 arms ok; ENVIRONMENT/PREDICTIONS_SUMMARY regenerated; pre-mortem L34. Next: commit, `lock.py predictions` (explicit
  names), commit, `lock_verify.py --tag HEAD`, tag, `lock_verify.py`, OTS, commit; then Stage 2 wave 1.
- Lock checklist (pre-mortem L29 = check these, then write the results into the LOG):
  1. every campaign: non-error results == jobs (controls 5,136 each, B4 22,816, B2 5,248, B5 25,680), unique keys, no
     solver failures; replicates rows == jobs; B4 `n_base_rhythmic_128` >= 8; DNg100 sane in B4/B2.
  2. controls really used their own matrix: `shared_payload_key` in each `backend_stats.jsonl` differs between controls
     and from B1-lo10; control scores differ from B1.
  3. G4 json for every simulated campaign (B1-lo5, B1-lo10, 10 controls, B5, B4, B2) passes.
  4. `environment_report.py` re-run after the last campaign (gates/ENVIRONMENT.json).
  5. status-only dry run of the frozen scoring functions on the real tables with synthetic labels in the scratchpad
     (never create UNBLIND.json anywhere).
  6. commit everything (`git add -f research/ledger/predictions` incl. parquet), then
     `lock.py predictions A1 A1-lo10 A0 B0 S B1 B1-alt B1-lo5 B1-lo10 B5 B4 B2 B1-ctl-... "B3=G3 failed (PREREG 9, L16)" "B6=depends on B3 (L18)"`,
     commit the lock, annotated tag `ledger-predictions-v1` (NOT pushed), `ledger/scripts/lock_verify.py` (must pass),
     `ots stamp` the lock file, commit the .ots + verify json. Then Stage 2.

## Next (after the predictions tag)
1. Stage 2 wave 1 (immediately after the tag): `labels_rooms.py launch pass1 --family steering` (pilot),
   `launch search --name search_names`, `launch search --name search_behaviour` (searches need no pass-1 output),
   `movies_room.py launch` (atlas-movie availability; read ONLY `~/ledger_rooms/run1_aux/movies/out/movies_report.md`).
   After ~15 min: `labels_rooms.py status` (alive, record count) + `labels_collect.py collect` (validation counts only).
2. If the pilot writes valid records: launch the other pass-1 families (atlas, catalogue, grooming, walking_stopping,
   escape_landing, pugliese_dedicated, recent_broad), keeping <= ~5 labeler sessions alive at once.
3. As pass-1 sessions finish: `collect`; one `repair --session` round where validation shows invalid lines; then
   `labels_audit.py`; `labels_prepare.py pass2`; `launch pass2 --all` (Phase A); for each finished Phase A
   `phaseb --session pass2-<family>`; then `collect`, `labels_audit.py`, `labels_prepare.py adjudication`,
   `launch adjudication --name general` and `--name dedicated`; `collect`; `labels_audit.py`; `labels_collect.py finalize`.
4. Pre-mortem (LOG), `lock.py labels`, commit, tag `ledger-labels-v1`, OTS; then push `ledger/v1` and the three tags with
   explicit refspecs (`git push origin ledger/v1 ledger-predictions-v1 ledger-labels-v1`; never `main`).
5. G5 again; `HANDOFF_1.md` (<= 1,800 words, 10 sections, no score next to an outcome); print it as the final message.

## Rules to remember
- Orchestrator never opens per-type labels (only validation summaries and aggregate counts) and never joins labels with
  predictions. B3/B6 are not locked (G3 failed, L16/L18).

## Open problems
- `tests/test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges` fails on this Mac at baseline (platform numerics).
- MaleCNS: bulk data not downloaded (L9); B2 uses the authors' pinned MaleCNS network + MaleCNS annotations.
