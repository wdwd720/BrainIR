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


def bundle_rel() -> str:
    """Repository-relative path of the previous benchmark's public tier-A bundle: the unique benchmarks/*/public_blind with a manifest
    (found, not named: this file enters the review room; early review F, F-M1). Baked at the same path in the images."""
    found = sorted(p for p in (ROOT / "benchmarks").glob("*/public_blind") if (p / "manifest.json").is_file())
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one public bundle under benchmarks/, found {len(found)}")
    return found[0].relative_to(ROOT).as_posix()


def full_image(gpu: bool = False, extra_pip: list[str] | None = None, extra_dirs: dict[str, str] | None = None):
    """extra_dirs: {repository-relative directory: container path}, e.g. the hash-locked synthetic generator
    ({"benchmarks/causal_state_v1/generator/src": "/repo/benchmarks/causal_state_v1/generator/src"}) for images whose simulation services
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
           .add_local_dir(str(ROOT / bundle_rel()), f"{REPO}/{bundle_rel()}", ignore=IGNORE)
           .add_local_dir(str(P4M_DIR / "site"), SITE_DIR, ignore=IGNORE))
    for rel, dest in (extra_dirs or {}).items():
        img = img.add_local_dir(str(ROOT / rel), dest, ignore=IGNORE)
    return img.add_local_dir(str(PKG_DIR), f"{REPO}/phase4/src/brainir_causal", ignore=IGNORE)


#: the unprivileged worker uids the isolation driver uses (brainir_causal.isolation: ROLE_UIDS for an unpacked container, and one
#: block of UID_STRIDE = 20 uids per slot 1..MAX_SLOTS = 32 of a packed container); baked into the iso image, with the slot groups
ISO_UIDS = tuple(range(10001, 10020 + 20 * 32))
SLOT_GIDS = tuple(range(20001, 20001 + 32))


def iso_image(gpu: bool = False, extra_pip: list[str] | None = None, extra_dirs: dict[str, str] | None = None):
    """The image of the ISOLATED classes (research/phase4/EVAL_ARCHITECTURE.md; job kind "iso"). The repository code is BAKED with
    copy=True (so later build steps can change its permissions), the worker uids exist, and the repository tree is locked down
    (go-rwx on /repo) so an unprivileged worker cannot read the orchestrator code, the generator or any bundle path; the driver (root)
    opens exactly the per-job public directory it builds at /opt/p4pub. extra_dirs (e.g. the hash-locked synthetic generator the
    driver needs for synthetic evaluations and loops) must lie under /repo: they are baked with copy=True BEFORE the lockdown, so they
    are root-only."""
    for dest in (extra_dirs or {}).values():
        if not str(dest).startswith(f"{REPO}/"):
            raise ValueError(f"iso extra_dirs must be baked under {REPO}/ (root-only after the lockdown): {dest}")
    import modal
    img = modal.Image.debian_slim(python_version="3.12").pip_install(*PINNED)
    img = _torch(img, gpu)
    if extra_pip:
        img = img.pip_install(*extra_pip)
    env = {"PYTHONPATH": PYTHONPATH, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if not gpu:
        env.update(CPU_PINS)
    useradd = (f"for u in $(seq {ISO_UIDS[0]} {ISO_UIDS[-1]}); do useradd -M -N -u $u -s /usr/sbin/nologin p4w$u; done && "
               f"for g in $(seq {SLOT_GIDS[0]} {SLOT_GIDS[-1]}); do groupadd -g $g p4slot$g; done")
    # the worker accounts come BEFORE the code layers (they do not change with the code, so the image rebuild after a code change
    # does not redo them); setpriv / unshare (util-linux, part of the base image) start the packed slots' workers
    img = (img.run_commands(f"{useradd} && groupadd -g 10001 p4workers || true", "test -x /usr/bin/setpriv && test -x /usr/bin/unshare")
           .env(env)
           .add_local_dir(str(ROOT / "src" / "brainir"), f"{REPO}/src/brainir", ignore=IGNORE, copy=True)
           .add_local_dir(str(ROOT / "phase3" / "src" / "brainir_state"), f"{REPO}/phase3/src/brainir_state", ignore=IGNORE, copy=True)
           .add_local_dir(str(ROOT / bundle_rel()), f"{REPO}/{bundle_rel()}", ignore=IGNORE, copy=True)
           .add_local_dir(str(PKG_DIR), f"{REPO}/phase4/src/brainir_causal", ignore=IGNORE, copy=True))
    for rel, dest in (extra_dirs or {}).items():
        img = img.add_local_dir(str(ROOT / rel), dest, ignore=IGNORE, copy=True)
    return img.run_commands("chmod -R go-rwx /repo && chmod 0711 /repo && mkdir -p /opt/p4jobs && chmod 0711 /opt/p4jobs")
