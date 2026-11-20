# Gate G5 at the end of run 1 (2026-11-20 ~10:45 PST)

The Stage S baseline set (`research/ledger/SETUP.md`), re-run after the labels lock on `ledger/v1` @ d116b10. (The pre-lock run is
`gates/G5_REPORT.md`, hashed by the predictions lock, so this end-of-run result is a new file.)

| check | baseline (242e472) | end of run | same? |
|---|---|---|---|
| `uv run pytest -m "not real_data"` | 532 passed, 1 failed, 2 skipped, 18 deselected | 532 passed, 1 failed, 2 skipped, 18 deselected (127 s); the same test fails (`test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges`, platform numerics, L5) | yes |
| `benchmarks/dng100/freeze.py --check` | pass | exit 0, lock bcaa8ee4...f7e7 | yes |
| `scripts/method_lock.py check` (Phase 2) | pass | exit 0 (`METHOD_LOCK check: OK`) | yes |
| `scripts/p3/method_lock_p3.py --check` | pass | exit 0 (30 source files) | yes |
| `scripts/p3/freeze_benchmark.py --check` | cannot run here | exit 1, same missing `data/phase3/...` files | yes (expected) |
| ledger tests (`ledger/tests`) | n/a | 63 passed | n/a |
| `lock.py check` (prereg, predictions, labels locks; clean checkout) | n/a | all clean | n/a |

**G5: PASS** (identical pattern). No file outside `ledger/` and `research/ledger/` differs from `main`.
