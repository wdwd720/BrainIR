# This machine (ledger run 1)

`CLAUDE.md` describes the Windows development PC. This file describes the Mac that ran ledger run 1. Nothing here
changes `CLAUDE.md`.

## Hardware and software
- Apple M5, 10 cores, 16 GB RAM, macOS 26.6 (build 25G72), arm64.
- uv 0.13.7 (Homebrew); uv-managed CPython 3.12.14 (`.python-version`); `uv sync` installs the locked root environment
  unchanged (`uv.lock` untouched).
- NumPy is linked against Apple Accelerate here; Modal containers use OpenBLAS on x86-64 Linux.
- Free disk at the start: 59 GiB (61,855,252 KiB) on the data volume.
- `claude` CLI 2.1.329 is available (used for the separate labeler sessions in Stage 2).
- Git: `origin` = the user's GitHub repo; `gh` is logged in; `git push --dry-run origin ledger/v1` succeeds.
- Bulk data root: `data/` in the repo (git-ignored; `BRAINIR_DATA_DIR` unset).

## Baseline checks (before any ledger change, commit 242e472)

| check | result here | note |
|---|---|---|
| `uv run pytest -m "not real_data"` | 532 passed, **1 failed**, 2 skipped, 18 deselected (160 s) | Fails: `test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges` (platform numerics, LOG L5). Skipped: the clean-room leakage test (no clean room here) and the Modal consistency test (opt-in). |
| `benchmarks/dng100/freeze.py --check` | **pass** (lock bcaa8ee4...f7e7; code and dataset manifests unchanged) | |
| `scripts/method_lock.py check` (Phase 2) | **pass** | |
| `scripts/p3/method_lock_p3.py --check` (Phase 3 method) | **pass** (30 source files) | |
| `scripts/p3/freeze_benchmark.py --check` (Phase 3 benchmark) | **cannot run here** (exit 1): its hashed datasets under `data/phase3/` exist only on the PC | Expected (prompt §3). |
| Phase 4 | no lock exists yet | Nothing Phase 4 is frozen. |
| `uv run pytest` (real-data tests) | not run at baseline (no processed data yet) | Re-checked after ingest; MaleCNS-dependent tests need the optional MaleCNS build. |

The same set is re-run at the end of the run (gate G5). The target is identical results: the same failure, the same
pass/cannot-run pattern.

## Data
See the G0 section below (filled in when the builds finish).

## Modal
See the Modal section below (filled in after the credit check and the smoke test).
