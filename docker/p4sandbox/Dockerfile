# Phase 4 agent code sandbox (goal5 section 5; research/phase4/LEAKAGE_POLICY.md section 2).
# Every clean-room agent runs its code in this image through the room's `sbx` wrapper:
#   docker run --rm --network none --read-only --cap-drop ALL ... -v <room>:/room brainir-p4-sandbox:1 <cmd>
# The image holds third-party packages only (no repository code, no data); the room is the only mount.
# Build: docker build -t brainir-p4-sandbox:1 docker/p4sandbox   (record the image id in research/phase4/LEAKAGE_POLICY.md)
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/mpl \
    MPLBACKEND=Agg \
    ATEN_CPU_CAPABILITY=avx2

# the numerical stack of the Phase 3 / Phase 4 evaluation environment (numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, torch 2.14.0)
COPY requirements.txt /opt/p4sandbox/requirements.txt
RUN pip install --no-cache-dir -r /opt/p4sandbox/requirements.txt \
 && pip install --no-cache-dir --no-deps torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip check \
 && pip freeze > /opt/p4sandbox/pip-freeze.txt \
 && useradd --uid 1000 --create-home --home-dir /home/agent agent \
 && python -c "import numpy, scipy, pandas, pyarrow, pydantic, sklearn, torch, matplotlib; print('stack ok', numpy.__version__, torch.__version__)"

USER 1000:1000
WORKDIR /room
CMD ["python", "--version"]
