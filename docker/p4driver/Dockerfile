# Phase 4 ORCHESTRATOR DRIVER image (never an agent image; research/LOG.md P4-D54; scripts/p4/linux_driver.py).
# Runs orchestrator Modal drivers on LINUX inside the local Docker VM: long Modal clients on the Windows host die of system-wide
# socket-buffer exhaustion (WinError 10055); sockets inside the VM do not use the Windows buffers.
# The image holds third-party code only: the phase4 lock's environment (`uv sync --frozen` into /opt/p4venv; torch as the CPU build
# of the locked version, without the CUDA stack a driver never uses), git (drivers record commits) and the docker CLI (drivers that
# plan in the pinned sandbox image reach Docker Desktop through the mounted socket). The repository, the run-artefact root and the
# Modal credentials (read-only) are mounted at run time by the wrapper; nothing of the repository or any credential is baked.
#   uv run --no-sync --project phase4 python scripts/p4/linux_driver.py build
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

COPY --from=docker@sha256:862099ada15c669000bef53aa4cb9d821262829f45b0dda2159ccb276443043b /usr/local/bin/docker /usr/local/bin/docker

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/p4venv \
    UV_PYTHON_PREFERENCE=system \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    HOME=/root

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*' \
 && pip install --no-cache-dir uv==0.12.18

# the lock's third-party environment; the three local packages (brainir, brainir-state, brainir-causal) come from the mounted
# repository through PYTHONPATH at run time (the entrypoint), as in the Modal images
COPY build/ /build/
WORKDIR /build/phase4
RUN uv sync --frozen --no-install-project \
      --no-install-package brainir --no-install-package brainir-state \
      --no-install-package torch --no-install-package triton \
      --no-install-package cuda-bindings --no-install-package cuda-pathfinder --no-install-package cuda-toolkit \
      --no-install-package nvidia-cublas --no-install-package nvidia-cuda-cupti --no-install-package nvidia-cuda-nvrtc \
      --no-install-package nvidia-cuda-runtime --no-install-package nvidia-cudnn-cu13 --no-install-package nvidia-cufft \
      --no-install-package nvidia-cufile --no-install-package nvidia-curand --no-install-package nvidia-cusolver \
      --no-install-package nvidia-cusparse --no-install-package nvidia-cusparselt-cu13 --no-install-package nvidia-nccl-cu13 \
      --no-install-package nvidia-nvjitlink --no-install-package nvidia-nvshmem-cu13 --no-install-package nvidia-nvtx \
 && uv pip install --python /opt/p4venv/bin/python --no-deps torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu \
 && /opt/p4venv/bin/python -c "import numpy, scipy, pandas, pyarrow, pydantic, modal, torch, sklearn, pytest; print('driver stack ok', numpy.__version__, scipy.__version__, modal.__version__, torch.__version__)" \
 && rm -rf /build

COPY sitecustomize.py /opt/p4venv/lib/python3.12/site-packages/sitecustomize.py
COPY entrypoint.sh /usr/local/bin/p4driver-entry
RUN chmod 0755 /usr/local/bin/p4driver-entry

ENV PATH=/opt/p4venv/bin:$PATH
WORKDIR /
ENTRYPOINT ["/usr/local/bin/p4driver-entry"]
CMD ["python", "--version"]
