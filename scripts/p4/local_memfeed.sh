#!/usr/bin/env bash
# Host free-memory feed for the LOCAL backend (brainir_causal.p4modal.local; research/phase4/LOCAL_EXECUTION_PLAN.md). The Docker VM
# cannot see the Windows host's free memory, so this loop (Git Bash on the host) writes "<free MB> <unix time>" every 2 s to
# C:\Dev\BrainIR_p4run\vol\_guard\free_mb, mounted read-only at /p4guard in local driver containers. A stale file (> 30 s) pauses
# new local work, so stopping this loop can only make local runs wait, never run unguarded.
#     bash scripts/p4/local_memfeed.sh            # run in the background while local drivers run
set -u
d=/c/Dev/BrainIR_p4run/vol/_guard
mkdir -p "$d"
while true; do
  mb=$(awk '/^MemFree:/ { printf "%d", $2 / 1024 }' /proc/meminfo 2>/dev/null)
  if [ -n "$mb" ]; then
    printf '%s %s\n' "$mb" "$(date +%s)" > "$d/free_mb.tmp" && mv -f "$d/free_mb.tmp" "$d/free_mb"
  fi
  sleep 2
done
