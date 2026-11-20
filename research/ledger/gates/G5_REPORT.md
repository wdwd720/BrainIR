# Gate G5: nothing broken (pre-lock run, 2026-11-20 ~00:15 PST)

The Stage S baseline set (`SETUP.md`), re-run on the ledger branch after all Stage 1 code changes. Target: identical results.

| check | baseline (242e472) | now | same? |
|---|---|---|---|
| `uv run pytest -m "not real_data"` | 532 passed, 1 failed, 2 skipped, 18 deselected | 532 passed, 1 failed, 2 skipped, 18 deselected (149 s) | yes; the same test fails (`test_sim_model.py::test_single_and_segment_integration_agree_and_rk4_converges`, platform numerics, LOG L5); the same two skips |
| `benchmarks/dng100/freeze.py --check` | pass | exit 0, lock bcaa8ee4...f7e7, no code or manifest change | yes |
| `scripts/method_lock.py check` (Phase 2) | pass | exit 0 (`METHOD_LOCK check: OK`) | yes |
| `scripts/p3/method_lock_p3.py --check` | pass | exit 0 (30 source files) | yes |
| `scripts/p3/freeze_benchmark.py --check` | cannot run here (Phase 3 datasets only on the PC) | exit 1, same missing `data/phase3/...` files | yes (expected) |
| ledger tests (`ledger/tests`) | n/a | 63 passed | n/a |

**G5: PASS** (identical pattern). The same set is re-run at the end of the run.
