#!/bin/sh
# Entrypoint of the ORCHESTRATOR DRIVER image (scripts/p4/linux_driver.py). BRAINIR_REPO = the repository's path inside the
# container, which is the host path as the Docker Desktop daemon sees it (/run/desktop/mnt/host/<drive>/...), so nested
# `docker run -v` mounts built from a driver's ROOT resolve on the daemon. The three local packages come from the mounted
# repository (as in the Modal images); /repo is a convenience link.
set -e
# files and directories this driver creates in the mounted repository must stay writable for the other orchestrator containers
# it starts (e.g. the planning container runs as uid 1000), as files created from the Windows host are
umask 0000
if [ -n "$BRAINIR_REPO" ]; then
  export PYTHONPATH="$BRAINIR_REPO/phase4/src:$BRAINIR_REPO/phase3/src:$BRAINIR_REPO/src${PYTHONPATH:+:$PYTHONPATH}"
  ln -sfn "$BRAINIR_REPO" /repo
fi
exec "$@"
