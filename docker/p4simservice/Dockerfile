# Phase 4 SIMULATION-SERVICE WORKERS (ORCHESTRATOR ONLY; never an agent image; LOG P4-D33; brainir_causal.simdocker).
# The pinned agent sandbox image (brainir-p4-sandbox:1: the numerical stack of the Modal containers) plus the ONE package the real
# engine's graph / bundle loader imports that the sandbox lacks, at the Modal images' pinned version (p4modal/images.py PINNED):
# duckdb. Installed --no-deps, so no numerical package changes (pip check must stay clean).
#   uv run --no-sync --project phase4 python scripts/p4/simservice_docker.py build-image   (checks the base id, builds, records
#   docker/p4simservice/image.json)
FROM brainir-p4-sandbox:1
USER root
RUN pip install --no-cache-dir --no-deps duckdb==1.5.5 \
 && pip check \
 && pip freeze > /opt/p4sandbox/pip-freeze-simsvc.txt \
 && python -c "import duckdb, networkx, numpy, scipy; print('simsvc ok', duckdb.__version__, networkx.__version__, numpy.__version__, scipy.__version__)"
USER 1000:1000
WORKDIR /tmp
