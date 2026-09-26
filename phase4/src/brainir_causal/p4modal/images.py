"""Modal images of the Phase 4 backend (ORCHESTRATOR SIDE: builds images from the repository; never runs in a container).

- `bench_image(gpu)`: torch + numpy + this package only (benchmarks, equivalence runs of self-contained models).
- `full_image(gpu)`: the pinned Phase 3 numerical stack + the frozen `brainir` library (the real engine), the frozen Phase 3
  `brainir_state` package (the locked baseline) and `brainir_causal`, the public blind bundle the real engine needs, and the guard's
  sitecustomize directory. CPU images carry the numerical pins of the development machine's kernels (with the host gate, CPU
  numerics are bit-identical to local runs; LOG P3-D26 / P3-D27). GPU images use PyPI's CUDA build of the same torch version.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
P4M_DIR = Path(__file__).resolve().parent
PKG_DIR = ROOT / "phase4" / "src" / "brainir_causal"
TORCH = "torch==2.14.0"
PINNED = ["numpy==2.5.3", "scipy==1.18.1", "pandas==3.0.6", "pyarrow==25.0.1", "pydantic==2.13.5", "scikit-learn==1.9.1",
          "threadpoolctl==3.7.0", "duckdb==1.5.5", "networkx==3.7", "requests==2.34.2", "cloudpickle==3.1.2",
          "python-dateutil==2.9.0.post0"]
# numpy's X86_V4 dispatch and torch's AVX-512 kernels are disabled so that every admissible host runs the AVX2 code paths of the
# development machine (the Phase 3 image settings; OPENBLAS_CORETYPE is deliberately not forced, see scripts/p3/modal_tournament.py)
CPU_PINS = {"NPY_DISABLE_CPU_FEATURES": "X86_V4 AVX512_ICL AVX512_SPR", "ATEN_CPU_CAPABILITY": "avx2"}
IGNORE = ["**/__pycache__/**", "**/*.pyc"]
REPO = "/repo"
PYTHONPATH = "/repo/phase4/src:/repo/phase3/src:/repo/src"
SITE_DIR = "/repo/p4modal_site"


def _torch(img, gpu: bool):
    if gpu:
        return img.pip_install(TORCH)                   # PyPI's Linux wheel = the CUDA build
    return img.pip_install(TORCH, index_url="https://download.pytorch.org/whl/cpu")


def bench_image(gpu: bool):
    import modal
    img = modal.Image.debian_slim(python_version="3.12").pip_install("numpy==2.5.3")
    img = _torch(img, gpu)
    env = {"PYTHONPATH": "/repo/p4bench", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if not gpu:
        env.update(CPU_PINS)
    return (img.env(env)
            .add_local_dir(str(P4M_DIR), "/repo/p4bench/p4modal", ignore=IGNORE + ["site/**"]))


def full_image(gpu: bool = False, extra_pip: list[str] | None = None, extra_dirs: dict[str, str] | None = None):
    """extra_dirs: {repository-relative directory: container path}, e.g. the hash-locked synthetic generator
    ({"benchmarks/causal_state_v1/generator": "/repo/benchmarks/causal_state_v1/generator"}) for images whose simulation services
    serve synthetic systems (never for images of method code alone)."""
    import modal
    img = modal.Image.debian_slim(python_version="3.12").pip_install(*PINNED)
    img = _torch(img, gpu)
    if extra_pip:
        img = img.pip_install(*extra_pip)
    env = {"PYTHONPATH": PYTHONPATH, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if not gpu:
        env.update(CPU_PINS)
    img = (img.env(env)
           .add_local_dir(str(ROOT / "src" / "brainir"), f"{REPO}/src/brainir", ignore=IGNORE)
           .add_local_dir(str(ROOT / "phase3" / "src" / "brainir_state"), f"{REPO}/phase3/src/brainir_state", ignore=IGNORE)
           .add_local_dir(str(ROOT / "benchmarks" / "dng100" / "public_blind"), f"{REPO}/benchmarks/dng100/public_blind", ignore=IGNORE)
           .add_local_dir(str(P4M_DIR / "site"), SITE_DIR, ignore=IGNORE))
    for rel, dest in (extra_dirs or {}).items():
        img = img.add_local_dir(str(ROOT / rel), dest, ignore=IGNORE)
    return img.add_local_dir(str(PKG_DIR), f"{REPO}/phase4/src/brainir_causal", ignore=IGNORE)
