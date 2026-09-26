# Phase 3 test runs after the post-lock reviews (2026-09-26)

The summary lines are copied verbatim from the runs' own output. Earlier runs (self-audit check I10) are in `SELF_AUDIT.json`.

| run (UTC, 2026-09-26) | command | result |
|---|---|---|
| about 10:55 | `uv run --no-sync pytest -m real_data -q -p no:cacheprovider` (root; needs `data/processed`) | `18 passed, 535 deselected in 26.92s` |
| about 11:40 | `uv run --no-sync pytest -m "not real_data" -q -p no:cacheprovider` (root, the default suite) | `534 passed, 1 skipped, 18 deselected, 2 warnings in 452.72s` (skipped: `tests/test_modal_consistency.py`, opt-in with `BRAINIR_TEST_MODAL=1`) |
| about 11:50 | `uv run --no-sync pytest -q -p no:cacheprovider` (in `phase3/`) | `6 failed, 179 passed, 9 errors` in `tests/test_postlock_review_room.py`: the room builder had just gained the verification reviewer V, whose task file the tests' fake repository did not hold |
| about 11:55 | the same, after V's task was made optional in the builder and the fake repository was extended (`phase3/tests/test_postlock_review_room.py`) | `194 passed in 31.13s` |

Together the root suite has 552 passing tests (534 in the default run and the 18 real-data tests run separately), 1 opt-in skip and
0 failures; the Phase 3 suite has 194 passing tests.
