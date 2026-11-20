#!/bin/bash
# Stage 2 guard (LOG L37). Makes every file saved in a ledger labeler session's own tool-results folder (WebFetch binaries,
# oversized tool outputs) unreadable within ~0.2 s of its creation, so that a later Read of it FAILS: a blocked attempt, not a
# breach (PREREG 6). Session transcripts (*.jsonl) are never touched; only <encoded ledger room>/<session>/tool-results/<file>.
# Run in the background for the whole of Stage 2:   bash ledger/scripts/toolresults_guard.sh
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$REPO/data/cache/ledger_logs/toolresults_guard.log"
mkdir -p "$(dirname "$LOG")"
echo "$(date +%H:%M:%S) guard start" >> "$LOG"
while true; do
  find "$HOME/.claude/projects" -mindepth 4 -maxdepth 4 -path '*-ledger-rooms-run1*/*/tool-results/*' -type f -perm -u+r 2>/dev/null | while IFS= read -r f; do
    chmod 000 "$f" && echo "$(date +%H:%M:%S) locked $(echo "$f" | awk -F/ '{print $(NF-3)"/"$NF}' | sed 's/-Users-[^-]*-ledger-rooms-//')" >> "$LOG"
  done
  sleep 0.2
done
