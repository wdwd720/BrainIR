#!/bin/bash
# Stage 1 core sequence (run after the ledger-prereg-v1 tag). Logs to <data>/cache/ledger_logs/stage1_*.log.
set -u
cd "$(dirname "$0")/../.."
L=data/cache/ledger_logs
mkdir -p "$L"
run() {
  local name=$1; shift
  echo "== $(date -u +%H:%M:%S) $name" | tee -a "$L/stage1_sequence.log"
  uv run --project ledger --no-sync python ledger/scripts/run_arms.py "$@" > "$L/stage1_$name.log" 2>&1
  local rc=$?
  echo "   exit=$rc $(tail -1 "$L/stage1_$name.log")" | tee -a "$L/stage1_sequence.log"
  return $rc
}
run authors authors || exit 1
run b0 b0 || exit 1
run baselines baselines || exit 1
run b1_lo5 b1 --lower 5 || exit 1
run b1_lo10 b1 --lower 10 || exit 1
run select_b1 select-b1 || exit 1
run g1 g1
run g1_cause g1-cause
run g2 g2
echo "== $(date -u +%H:%M:%S) core done" | tee -a "$L/stage1_sequence.log"
