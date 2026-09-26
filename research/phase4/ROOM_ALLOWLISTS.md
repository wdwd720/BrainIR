# Phase 4 room allowlists (orchestrator decision; implemented by `scripts/make_phase4_cleanroom.py`)

Everything not listed is excluded. Every file passes the content scanner. Generated files (CLAUDE.md, sbx, README stubs) are
recorded as `generated`.

## p4bench (synthetic author)
- `CLAUDE.md` <- research/phase4/contracts/p4bench_CLAUDE.md; `sbx` (generated)
- `docs/SYNTHETIC_BENCHMARK_CONTRACT.md`, `docs/PROTOCOL.md` (benchmarks/causal_state_v1/PROTOCOL.md), `docs/PROTOCOL_V2.md`
  (public doc), `docs/CALIBRATION_TARGETS.md` (research/phase4/CALIBRATION_TARGETS.md)
- `ref/protocol.py`, `ref/families.py` (phase4/src/brainir_causal/), `ref/calibstats.py`, `ref/calibration_targets.json`
  (benchmarks/causal_state_v1/public/)
- nothing else (no data, no evaluator, no simulator of any real system)

## p4clean (method development; built only after the benchmark freeze)
- `CLAUDE.md` (generated, generic rules), `sbx` (generated), `.python-version`, `pyproject.toml` (generated: package
  brainir_causal + baselines, pinned stack, NO path dependency on the root `brainir`)
- `src/brainir_causal/`: __init__, api, protocol, families, data, evalio, fresh, stats, evaluate, evaluate_mediation,
  evaluate_micro, evaluate_lift, evaluate_stability, evaluate_transfer, verdict, refs (truth-free references only: the TRUE-STATE
  and OBS-SHORTCUT references must be importable-but-unusable without truth), harness (public / development mode), loop, designers,
  capacity, calibstats, equiv, simclient, select; `methods/__init__.py` (empty package for the developers)
- NOT: realsim, systems (internal parts), store, simservice, synthadapter, suites, evaluate_truth, calibrate, runguard, runner,
  tournament, feedback, p4modal, accounting internals if they read hidden paths
- `baselines/brainir_state_v1/`: the Phase 3 locked method package (hash-verified against research/phase3/METHOD_LOCK.json) and the
  Phase 4 adapter; read-only
- `docs/`: PROTOCOL.md, PROTOCOL_V2.md, API.md, METHOD_DEV_CONTRACT.md, METHODS_REVIEW.md, REFERENCES.md, remote-runner README
- `data/`: synthetic_dev (public trajectories, public system records with split records, public pools; NO truth), real_public
  (Phase 4 public real data), systems_public.json (merged public records), tolerances.json, calibration_targets.json
- `tests/`: the public module tests that run without orchestrator-side modules
- work areas (empty): `runs/`, `notes/`, `tests/methods/`, `simq/`, `runs/_remote/`

## p4review (pre-freeze reviews E, H, F; later A-D, G, E/H follow-ups)
- everything of p4clean (docs, src, data, tests), plus `extra/` = orchestrator-side code: realsim, systems (the CODE only: the
  internal real records under benchmarks/causal_state_v1/hidden/ stay refused; reviewers get the engine's test results instead,
  e.g. the bit-identity and restart checks), store, simservice, synthadapter, suites, evaluate_truth, calibrate, runguard, runner,
  tournament, feedback, p4modal,
  the synthetic generator (benchmarks/causal_state_v1/generator/) with its tests, calibration.json, make_phase4_cleanroom.py,
  scripts/p4agent/ (guard, launcher), devrun4.py, extra/README.md (generated)
- NOT: the salt (data/phase4/hidden/), validation / confirmation truth data (reviewers may generate their own dev-tier builds),
  PLAN.md, LOG.md, anything Phase 2-3 answer-bearing

## Refusal list (all rooms)
PHASE*_REPORT.md, goal*.md, research/LOG.md, research/phase2/**, research/phase3/**, research/phase4/PLAN.md, research/phase4/reviews/**
(until a later round explicitly includes an earlier review), research/phase4/HIDDEN_EVALUATIONS.md, benchmarks/dng100_walking_cpg/**,
benchmarks/dng100/{oracle,evaluator,baselines}/**, benchmarks/state_discovery_v1/hidden/**, benchmarks/causal_state_v1/hidden/**,
data/phase3/**, data/phase4/hidden/**, data/phase4/suites/{val,conf}/**/truth/**, memory files, the main CLAUDE.md.
