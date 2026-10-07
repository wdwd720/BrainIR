#!/usr/bin/env bash
# Keep the Docker VM's Linux page cache from starving the Windows host (LOCAL_EXECUTION_PLAN.md section 3; LOG P4-D72).
# The local builds write many GB of records; the VM keeps them as page cache, which WSL returns to Windows only slowly, so the
# host's free memory falls under the local backend's 6 GB start gate although no job needs the memory. Every 60 s: when the host has
# less than 7 GB free and the VM caches more than 2 GB, sync and drop the clean page cache (echo 1: page cache only; no data is lost,
# nothing is configured). Uses the pinned driver image, no network.
#   bash scripts/p4/local_cachedrop.sh        (background, beside local_memfeed.sh)
set -u
while true; do
  free_mb=$(powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1KB)" 2>/dev/null | tr -d '\r')
  if [ -n "$free_mb" ] && [ "$free_mb" -lt 7168 ]; then
    MSYS_NO_PATHCONV=1 docker run --rm --privileged --network none brainir-p4-driver:1 sh -c \
      'c=$(awk "/^Cached/{print int(\$2/1024)}" /proc/meminfo); if [ "$c" -gt 2048 ]; then sync; echo 1 > /proc/sys/vm/drop_caches; echo "dropped ${c} MB page cache"; fi' \
      | sed "s/^/$(date -u +%H:%M:%SZ) host ${free_mb} MB free: /"
  fi
  sleep 60
done
