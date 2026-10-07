"""Isolated execution of untrusted method code: the model-worker architecture (research/phase4/EVAL_ARCHITECTURE.md; review F,
F-B2 / F-B3).

THREAT MODEL. Every line of method and designer code is untrusted. It must never have access to held-out data (item futures,
counterfactual twins, pool futures, lift outcomes before it requested the lifts, truth), the salt, the orchestrator's internal
records, the synthetic generator, other methods' snapshots or results, the network or Modal workspace credentials. In-process audit
hooks cannot deliver that (F-B2: one assignment switched the old guard off; a thread running `exec` bypassed its evaluation mode), and
an evaluator that holds the answers in the process that runs the method cannot either (F-B3: a gc lookup recovered y_future for 24 of
24 items). So the two parties are separate OS processes:

- the trusted DRIVER (root in a Linux container on Modal; the orchestrator on the development machine) holds every held-out array
  and the simulator, runs the unchanged evaluation code (`brainir_causal.harness.evaluate_model`, E5 / E6's metric families), the
  experiment loop (`brainir_causal.loop.run_loop`: policy check, budget accounting, simulation) and the benchmark references;
- the MODEL WORKER (`brainir_causal.worker`) is a fresh process per (method, system, role) that runs the method's code: as an
  UNPRIVILEGED uid (one uid per role) with a scrubbed environment (no MODAL_* or credential variables; minimal PATH / HOME) and an
  empty private working directory, able to read only the method snapshot, the public modules (`build_pubdir`) and what the driver
  sends it. On the development machine the worker runs in the Docker sandbox image (`DockerTransport`: no network, read-only root,
  all capabilities dropped); on Modal as another uid inside a container with block_network=True (`LinuxUidTransport`).

PROTOCOL. Frames over the worker's stdin / stdout pipes. Driver -> worker messages are pickles (the driver is trusted). Worker -> driver
replies use the SAFE codec (`worker.encode_safe` / `worker.decode_safe`: JSON + uncompressed npz read with allow_pickle=False): the
driver never unpickles anything a worker produced, fitted models included (they travel as opaque bytes from the fit worker to the
evaluation workers; the driver stores them and never loads them). Replies that violate the codec kill the worker.

EVALUATION (`RemoteFresh`, a drop-in `fresh.Fresh`): the driver's harness calls encode / rollout / readout / supports / step / read_in /
intervention_effect / lift / uncertainty / validity / info / schema on a RemoteFresh, which forwards ONLY the call's arguments. The
worker keeps the pristine model bytes and runs every call on a fresh unpickled copy (PROTOCOL section 5). An evaluation runs in three
PHASES, each in a NEW worker process with its own uid:
  A   predictions from pasts only: the items' predictions (histories up to the onset, future inputs, events), composition pairs,
      encodings of PUBLIC training histories (whitening), pool histories (microstate equivalence), truth samples' histories, read-ins,
      the capacity record;
  lift  B1 the native lift requests (histories up to the case time + requested shifts) -> the driver simulates the candidates ->
        B2 (a new process) the encodings of the lifted / twin histories and the model's rollouts from them;
  C   future histories: the encodings of the true future (intervened and twin) histories for closure and the bisimulation re-encodings.
A phase can only move forward (A -> lift -> C) and a closed phase is never reopened, so every prediction exists before the worker is
ever given a future history, and a later phase cannot change an earlier prediction. Between phases the driver kills every process
of the worker uids and removes their System V IPC objects; /tmp, /var/tmp and /dev/shm are not writable by workers and each worker's
working directory is private to its uid, so no state crosses a phase boundary. A new RemoteFresh (new workers) is used for every
(method, system); workers are never reused across methods.

FITS AND LOOPS. A fit worker receives the public training records over the pipe (it needs no file access) and returns the model as
bytes (`fit_job`; `bootstrap_interventions` gives the Level C refits of PROTOCOL 5.10). A loop is run by the DRIVER
(`loop_job`): the method's learner (and, for its own design, its designer) live in one loop worker; the driver runs run_loop, which
validates every proposal against the PUBLIC policy, simulates it, does the budget accounting and sends the new records to the
worker; reference designers are trusted and run in the driver (their model queries go to the loop worker). A worker never gets a
simulation client.

CONTAINERS (Modal, `run_iso_payload`, job kind "iso" of `p4modal.remote`): the driver runs as root and first applies
`container_lockdown`: PR_SET_DUMPABLE 0 (no /proc/<driver>/mem, environ, fd for other uids), the repository, /root and the volume
mounts chmod 0700 (sensitive volumes are mounted READ-WRITE because a read-only mount cannot be chmodded; the driver never writes
them; Modal mount points are symbolic links, so the RESOLVED target is locked, and the lockdown FAILS CLOSED when a private root is
still group- or other-accessible), world-writable directories and files made o-w, stale worker processes killed. The method snapshot is extracted into a
per-job directory under a 0711 root (workers can reach their own job's files by name but cannot list others) and removed after the
job. The containers of the "iso" classes run with block_network=True (`p4modal.app.CLASSES`).

The runguard TRIPWIRE runs inside every worker (its state in a closure); it is not part of the boundary.
"""

from __future__ import annotations

import collections
import contextlib
import hashlib
import io
import itertools
import json
import os
import pickle
import queue
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from . import worker as W
from .fresh import Fresh

PUBDIR = "/opt/p4pub"
JOBS_ROOT = "/opt/p4jobs"
METHOD_MOUNT = "/opt/p4method"
#: a block_network container cannot move an input or output above Modal's 2 MiB inline limit through the blob store; large artefacts
#: (a fitted model, a large evaluation record, a loop's checkpoint files) are STAGED through the STORE volume instead, which works under
#: block_network (P1 probes: a 3 MiB write + commit + reload + read succeeds, and commit / reload do not remount the locked-down mount).
#: STAGE above this size; keep it below MAX_INLINE_OUTPUT so a staged ref (a small dict) always fits inline.
STAGE_THRESHOLD = 1024 * 1024
#: where each kind of artefact is staged, by the DATA'S CLASS (LEAKAGE_POLICY section 3: held-out-derived data live on the eval volume,
#: which fit containers never mount): a fitted model (derived from PUBLIC training data only) -> the STORE volume (fit and eval classes
#: mount it); an evaluation record or a loop's files (derived from held-out data / the system's truth) -> the EVAL volume (mounted only by
#: evaluation and loop classes). Both roots are under mounts the container lockdown makes 0700, so no worker can list or read them.
STAGE_ROOTS = {"store": "/storevol/_staged", "eval": "/evalvol/_staged"}
MAX_INLINE_OUTPUT = 2 * 1024 * 1024 - 128 * 1024


def stage_blob(data: bytes, *, vol: str = "store", roots: dict | None = None) -> dict:
    """Write `data` content-addressed (sha256) under the staging root of volume `vol` (<root>/<sha[:2]>/<sha>.bin; directories 0700) and
    return a REF {"stage": sha, "size": n, "vol": vol}. The PATH is chosen by the DRIVER from the hash of bytes it holds, never from
    anything a worker names; the caller commits the volume (safe under block_network and packing: commit does not remount, P1 probe).
    Idempotent by content (two jobs staging identical bytes write the same file)."""
    root = Path((roots or STAGE_ROOTS)[vol])
    sha = hashlib.sha256(data).hexdigest()
    d = root / sha[:2]
    for q in (root, d):
        q.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(q, 0o700)
    p = d / f"{sha}.bin"
    if not p.exists():
        tmp = p.with_suffix(f".{uuid.uuid4().hex}.part")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, p)
    return {"stage": sha, "size": len(data), "vol": vol}


def _mounted_stage_vols() -> set:
    """The staging volumes this container mounts (a fit class has no eval volume: nothing held-out-derived may be staged there)."""
    return {v for v, r in STAGE_ROOTS.items() if Path(r).parent.exists()}


def _part_size(v) -> int:
    if isinstance(v, (bytes, bytearray)):
        return len(v)
    try:
        return len(pickle.dumps(v, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:  # noqa: BLE001
        return 0


def fit_inline(out: dict, role, *, limit: int | None = None, mounted: set | None = None, roots: dict | None = None) -> set:
    """Keep an iso job's TOTAL inline output under `limit` (default MAX_INLINE_OUTPUT): stage its largest parts first until the rest
    fits, whatever each part's own size (5 checkpoints of 470 KB are each under STAGE_THRESHOLD but together exceed 2 MiB). By data
    class: a fit's model -> the STORE volume; an evaluation record or a loop file -> the EVAL volume (held-out-derived); a call result ->
    the EVAL volume when this container mounts it (its data class is unknown, so it is treated as held-out-derived), else the STORE volume
    (a container without the eval volume, i.e. a fit class, holds public data only: e.g. P3's refits through "call"). A part that must be
    staged on a volume this container does not mount raises (a clear job error, never a silent loss). Returns the volumes staged to.
    Mutates `out`."""
    limit = MAX_INLINE_OUTPUT if limit is None else int(limit)
    mounted = set(STAGE_ROOTS) if mounted is None else set(mounted)
    staged: set = set()

    def total() -> int:
        return sum(_part_size(v) for k, v in out.items() if k not in ("iso", "staged"))

    def put(data: bytes, vol: str) -> dict:
        if vol not in mounted:
            raise WorkerError(f"a {role} output part must be staged on the {vol} volume, which this container does not mount")
        staged.add(vol)
        return stage_blob(data, vol=vol, roots=roots)

    if total() <= limit:
        return staged
    cands = []                                              # (size, how to stage it)
    if isinstance(out.get("model"), (bytes, bytearray)):
        cands.append((len(out["model"]), "model"))
    if "result" in out:
        cands.append((_part_size(out["result"]), "result"))
    for name, b in (out.get("files") or {}).items():
        if isinstance(b, (bytes, bytearray)):
            cands.append((len(b), ("file", name)))
    for _size, what in sorted(cands, key=lambda c: -c[0]):
        if total() <= limit:
            break
        if what == "model":
            out["model_ref"] = put(out.pop("model"), "store")
        elif what == "result":
            vol = "store" if (role == "call" and "eval" not in mounted) else "eval"
            out["result_ref"] = put(pickle.dumps(out.pop("result"), protocol=pickle.HIGHEST_PROTOCOL), vol)
        else:
            name = what[1]
            out.setdefault("file_refs", {})[name] = put(out["files"].pop(name), "eval")
    return staged


def staged_input_refs(p: dict) -> list[dict]:
    """The staged refs an iso payload READS (a large evaluation input model), for the freshness check of `run_iso_packed`."""
    refs = []
    if isinstance(p.get("model_ref"), dict):
        refs.append(p["model_ref"])
    for r in list(p.get("input_refs") or []) + list((p.get("model_refs") or {}).values()):
        if isinstance(r, dict):
            refs.append(r)
    return refs


def staged_visible(ref: dict, *, roots: dict | None = None) -> bool:
    sha = str(ref.get("stage", ""))
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        return False
    return (Path((roots or STAGE_ROOTS)[ref.get("vol", "store")]) / sha[:2] / f"{sha}.bin").is_file()


def read_staged(ref: dict, *, roots: dict | None = None) -> bytes:
    """The bytes a `stage_blob` ref names, read by the DRIVER from the ref's volume and verified against its sha256 before use (the
    worker never sees the volume)."""
    sha = str(ref["stage"])
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise WorkerError(f"malformed staged ref {sha!r}")
    root = Path((roots or STAGE_ROOTS)[ref.get("vol", "store")])
    data = (root / sha[:2] / f"{sha}.bin").read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise WorkerError(f"staged blob {sha} is corrupt")
    return data
#: one unprivileged uid per role: the evaluation phases, fits, loops and method descriptions never share a uid
ROLE_UIDS = {"A": 10001, "B1": 10002, "B2": 10003, "C": 10004, "fit": 10010, "loop": 10011, "describe": 10012, "probe": 10019}
#: PACKED containers (research/phase4/LEVEL_B_EXECUTION.md): several jobs run at once in one container, each in its own SLOT s = 1 ..
#: MAX_SLOTS with its own block of worker uids (ROLE_UIDS + UID_STRIDE * s; slot 0 = the uids of an unpacked container) and its own
#: group SLOT_GID0 + s (the slot's job directory is root:group 0710)
UID_STRIDE = 20
MAX_SLOTS = 32
SLOT_GID0 = 20000
UID_MIN, UID_MAX = 10001, 10019 + UID_STRIDE * MAX_SLOTS
PACK_DIR = "/tmp/p4m/pack"
PHASE_ORDER = ("A", "lift", "C")
#: the model API calls each evaluation (sub-)phase may make ("capacity" is the worker op computing the section 5.15 record)
PHASE_OPS = {
    "A": frozenset({"info", "supports", "encode", "rollout", "readout", "step", "intervention_effect", "read_in", "uncertainty", "validity",
                    "schema", "capacity"}),
    "B1": frozenset({"info", "supports", "encode", "lift"}),          # encode only before the first lift request (public histories)
    "B2": frozenset({"info", "supports", "encode", "rollout", "readout"}),
    "C": frozenset({"info", "supports", "encode"}),
}
CALL_TIMEOUT_S = 900.0
INIT_TIMEOUT_S = 600.0
MAX_REPLY_BYTES = 4 * 1024 ** 3
BOOT = "import sys; sys.path[:0] = [{pub!r}]; from brainir_causal.worker import main; raise SystemExit(main())"
#: environment variables a worker inherits from the driver (numerical pins only; never credentials)
PASS_ENV = ("NPY_DISABLE_CPU_FEATURES", "ATEN_CPU_CAPABILITY", "LANG", "LC_ALL")
THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
PRIVATE_DIRS = ("/repo", "/root", "/fitvol", "/evalvol", "/storevol", "/devvol", "/data", "/home", "/mnt", "/srv", "/tmp/p4m", "/p4iso")
SHARED_TMP = ("/tmp", "/var/tmp", "/dev/shm", "/run/shm", "/run/lock", "/var/lock", "/dev/mqueue")
SCAN_SKIP = ("/proc", "/sys", "/dev", "/fitvol", "/evalvol", "/storevol", "/devvol", JOBS_ROOT)
_LOCKED: dict = {}


class InfraFault(BaseException):
    """An INFRASTRUCTURE fault of the isolation layer, never a method's failure: a model worker process died and died again after one
    fresh restart (killed from outside, out of memory, a lost pipe), a packed child driver died without a result, no worker uid was
    free, ... A BaseException, not an Exception, so that no `except Exception` on the evaluation path (`fresh.safe_call`, the metric
    families' guards, the drivers' per-model recorders) can swallow it and charge it to the method as a failed call: the job fails
    LOUDLY and the container callable returns an infrastructure result (p4modal.app: {"__infra__": True, "error": "InfraFault ..."}),
    which the orchestrator re-submits (Backend.run; the Level C and post-lock executors match "InfraFault")."""


class WorkerError(RuntimeError):
    """The worker is unusable because of the METHOD (a call that timed out, a protocol violation): later calls of its phase fail and
    are scored as the method's failures. A worker process that DIED is `WorkerDied` (infrastructure), never this."""


class WorkerDied(InfraFault):
    """The worker PROCESS died (EOF on its pipe, a write that failed): infrastructure. `RemoteFresh` restarts the phase's worker and
    retries the call once; a second death (or a death anywhere else) propagates as an `InfraFault`."""


class WorkerTimeout(WorkerError):
    pass


class ProtocolViolation(WorkerError):
    pass


class RemoteCallError(RuntimeError):
    """The method's code raised inside the worker (a failed call, scored as such)."""

    def __init__(self, msg: str, tb: str | None = None):
        super().__init__(msg)
        self.remote_traceback = tb


# ================================================================================================================ public code
def _p3_sources() -> dict:
    from .frozen_v1 import V1_SOURCES
    return dict(V1_SOURCES)


def _p3_root() -> Path | None:
    import importlib.util
    spec = importlib.util.find_spec("brainir_state")
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve().parent.parent


def build_pubdir(dest: Path | str, *, src_pkg: Path | None = None, with_p3: bool = True) -> dict:
    """Copy the PUBLIC modules (worker.PUBLIC_MODULES) of brainir_causal and the frozen earlier baseline's files (frozen_v1.V1_SOURCES,
    hash-checked) into dest (dest/brainir_causal, dest/brainir_state): the only code a worker imports besides the method snapshot and
    third-party packages. Directories 0755, files 0644 (POSIX). Returns the manifest {relative path: sha256}."""
    dest = Path(dest)
    src_pkg = Path(src_pkg) if src_pkg else Path(__file__).resolve().parent
    files: dict[str, str] = {}
    pk = dest / "brainir_causal"
    if pk.exists():
        shutil.rmtree(pk)
    pk.mkdir(parents=True)
    for m in W.PUBLIC_MODULES:
        s = src_pkg / f"{m}.py"
        if not s.exists():
            continue
        data = s.read_bytes()
        (pk / f"{m}.py").write_bytes(data)
        files[f"brainir_causal/{m}.py"] = hashlib.sha256(data).hexdigest()
    p3_status = "not requested"
    if with_p3:
        root = _p3_root()
        want = _p3_sources()
        bad = {}
        if root is None:
            p3_status = "brainir_state not importable"
        else:
            if (dest / "brainir_state").exists():
                shutil.rmtree(dest / "brainir_state")
            for rel, sha in want.items():
                src = root / rel
                if not src.exists():
                    bad[rel] = "missing"
                    continue
                data = src.read_bytes()
                if hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() != sha:
                    bad[rel] = "MISMATCH"
                    continue
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                (dest / rel).write_bytes(data)
                files[rel] = hashlib.sha256(data).hexdigest()
            p3_status = "ok" if not bad else f"refused: {bad}"
            if bad and (dest / "brainir_state").exists():
                shutil.rmtree(dest / "brainir_state")
    man = {"files": files, "p3_baseline": p3_status, "n_files": len(files)}
    (dest / "PUBDIR_MANIFEST.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if os.name != "nt":
        for d, dirs, fs in os.walk(dest):
            os.chmod(d, 0o755)
            for f in fs:
                os.chmod(os.path.join(d, f), 0o644)
    return man


def extract_snapshot(tar_bytes: bytes | None, tar_path: Path | str | None, dest: Path | str) -> Path:
    """A method snapshot (deterministic tar of the methods package) extracted into dest (root-owned; dirs 0755, files 0644)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    fh = io.BytesIO(tar_bytes) if tar_bytes is not None else open(tar_path, "rb")  # noqa: SIM115
    with fh, tarfile.open(fileobj=fh) as tf:
        tf.extractall(dest, filter="data")
    if os.name != "nt":
        for d, _dirs, fs in os.walk(dest):
            os.chmod(d, 0o755)
            for f in fs:
                os.chmod(os.path.join(d, f), 0o644)
    return dest


# ================================================================================================================ container lockdown
def _libc():
    import ctypes
    import ctypes.util
    return ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)


def set_nondumpable() -> int:
    """PR_SET_DUMPABLE 0 for this process: other uids cannot read /proc/<pid>/mem, environ, fd, maps or ptrace it."""
    return int(_libc().prctl(4, 0, 0, 0, 0))


def _proc_uids() -> list[tuple[int, int]]:
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/status", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("Uid:"):
                        out.append((int(d), int(line.split()[1])))
                        break
        except OSError:
            continue
    return out


def kill_uids(uids=None, rounds: int = 25) -> int:
    """SIGKILL every process whose real uid is in `uids` (default: every worker uid) until none is left. Returns the number killed."""
    if os.name == "nt":
        return 0
    want = set(uids) if uids is not None else set(range(UID_MIN, UID_MAX + 1))
    me = os.getpid()
    n = 0
    for _ in range(rounds):
        victims = [p for p, u in _proc_uids() if u in want and p != me]
        if not victims:
            return n
        for p in victims:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(p, signal.SIGKILL)
                n += 1
        time.sleep(0.05)
    return n


def ipc_cleanup(uids=None) -> int:
    """Remove the System V shared memory segments, semaphores and message queues owned or created by worker uids (they outlive
    processes and are not files, so neither permissions nor process kills remove them)."""
    if os.name == "nt":
        return 0
    want = set(uids) if uids is not None else set(range(UID_MIN, UID_MAX + 1))
    n = 0
    try:
        libc = _libc()
    except OSError:
        return 0
    for kind, fn, id_col, cols in (("shm", "shmctl", 1, (7, 9)), ("sem", "semctl", 1, (4, 6)), ("msg", "msgctl", 1, (7, 9))):
        p = Path("/proc/sysvipc") / kind
        if not p.exists():
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            try:
                ident = int(f[id_col])
                owners = {int(f[c]) for c in cols if c < len(f)}
            except (ValueError, IndexError):
                continue
            if owners & want:
                with contextlib.suppress(Exception):
                    if kind == "sem":
                        getattr(libc, fn)(ident, 0, 0)
                    else:
                        getattr(libc, fn)(ident, 0, None)
                    n += 1
    return n


def _fix_world_writable(root: str = "/", skip=SCAN_SKIP, max_entries: int = 400_000) -> dict:
    """chmod o-w on every world-writable directory and file below root (symbolic links, the skipped trees and read-only file systems
    left alone)."""
    fixed, failed, seen = [], [], 0
    for d, dirs, files in os.walk(root, topdown=True):
        dirs[:] = [x for x in dirs if not any(os.path.join(d, x) == s or os.path.join(d, x).startswith(s + "/") for s in skip)]
        for name in dirs + files:
            seen += 1
            if seen > max_entries:
                return {"fixed": fixed[:200], "n_fixed": len(fixed), "failed": failed[:50], "truncated": True}
            p = os.path.join(d, name)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode) or not (st.st_mode & stat.S_IWOTH):
                continue
            try:
                os.chmod(p, stat.S_IMODE(st.st_mode) & ~0o002)
                fixed.append(p)
            except OSError as e:
                failed.append(f"{p}: {e.strerror}")
    return {"fixed": fixed[:200], "n_fixed": len(fixed), "failed": failed[:50], "truncated": False}


def container_lockdown(*, private=PRIVATE_DIRS, scan: bool = True) -> dict:
    """Root in a Linux container, before any worker starts (idempotent; the file-system scan runs once per container)."""
    if os.name == "nt" or os.geteuid() != 0:
        raise RuntimeError("container_lockdown needs root in a Linux container")
    rec: dict = {"dumpable0": set_nondumpable(), "private": {}, "shared_tmp": {}}
    bad = []
    for p in private:
        if not os.path.lexists(p):
            continue
        # volume mount points may be SYMBOLIC LINKS to the real mount (Modal): lock the resolved target, which is what a worker would
        # reach through the link (these are fixed, known paths, never attacker-chosen). A Modal volume can still be SETTLING when the
        # container starts (chmod does not stick until the mount is fully attached), so retry a few times before failing closed.
        real = os.path.realpath(p)
        mode = None
        err = None
        for _attempt in range(8):
            try:
                os.chmod(real, 0o700)
                mode = stat.S_IMODE(os.stat(real).st_mode)
                err = None
                if not (mode & 0o077):
                    break
            except OSError as e:
                err = e.strerror
            time.sleep(0.5)
        if err is not None:
            rec["private"][p] = f"FAILED {err}" + (f" (-> {real})" if real != p else "")
            bad.append(f"{p}: {err}")
        else:
            rec["private"][p] = oct(mode) + (f" (-> {real})" if real != p else "")
            if mode & 0o077:
                bad.append(f"{p}: {oct(mode)}")
    if bad:
        # fail CLOSED: a private root a worker uid could still read means no worker may start in this container
        raise RuntimeError(f"container lockdown failed for {bad}; refusing to run model workers")
    for p in SHARED_TMP:
        if os.path.isdir(p) and not os.path.islink(p):
            try:
                os.chmod(p, (stat.S_IMODE(os.stat(p).st_mode) & ~0o002) | 0o755)
                rec["shared_tmp"][p] = oct(stat.S_IMODE(os.stat(p).st_mode))
            except OSError as e:
                rec["shared_tmp"][p] = f"FAILED {e.strerror}"
    os.makedirs(JOBS_ROOT, exist_ok=True)
    os.chown(JOBS_ROOT, 0, 0)
    os.chmod(JOBS_ROOT, 0o711)
    if scan and not _LOCKED.get("scanned"):
        rec["world_writable"] = _fix_world_writable("/")
        _LOCKED["scanned"] = True
    rec["killed"] = kill_uids()
    rec["ipc_removed"] = ipc_cleanup()
    _LOCKED["record"] = rec
    return rec


# ================================================================================================================ transports
class WorkerProc:
    """A started worker process and its clean-up."""

    def __init__(self, popen: subprocess.Popen, *, role: str, cleanup=None, where: str = ""):
        self.p = popen
        self.role = role
        self.where = where
        self._cleanup = cleanup
        self._done = False

    @property
    def stdin(self):
        return self.p.stdin

    @property
    def stdout(self):
        return self.p.stdout

    @property
    def stderr(self):
        return self.p.stderr

    def kill(self) -> None:
        with contextlib.suppress(Exception):
            self.p.kill()

    def wait(self, timeout: float) -> int | None:
        try:
            return self.p.wait(timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            with contextlib.suppress(Exception):
                return self.p.wait(10)
            return None

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.kill()
        for fh in (self.p.stdin, self.p.stdout, self.p.stderr):
            with contextlib.suppress(Exception):
                fh.close()
        if self._cleanup is not None:
            with contextlib.suppress(Exception):
                self._cleanup()


def job_threads(p: dict) -> int:
    """The thread count of an iso job: the job's own "threads" (what its model workers use), else the payload's, else 2. Never the
    container's CPU count (which differs between classes)."""
    job = p.get("job") if isinstance(p.get("job"), dict) else {}
    return max(1, int(job.get("threads") or p.get("threads") or 2))


@contextlib.contextmanager
def pinned_threads(n: int):
    """THIS process's BLAS / OpenMP threads pinned to n for the block, restored after (an unpacked container's main process runs later
    inputs). The trusted driver's own numerics (the evaluator's regressions and bootstraps) otherwise run with the container's CPU count
    (20 on iso_eval_s, 48 on the packed 32-CPU classes), which changes the last bits of multi-threaded BLAS reductions: the P1 dry run
    found packed and unpacked evaluation records of the SAME fitted models differing at ~1e-9 relative in the mediation and closure
    families (research/phase4/LEVEL_B_EXECUTION.md section 5). numpy's and scipy's BLAS are loaded first so that the limit reaches both;
    the environment covers any library loaded later in the block."""
    n = max(1, int(n))
    old = {k: os.environ.get(k) for k in THREAD_VARS}
    os.environ.update({k: str(n) for k in THREAD_VARS})
    with contextlib.suppress(ImportError):
        import scipy.linalg  # noqa: F401  - scipy's own BLAS, before the limit
    from threadpoolctl import threadpool_limits
    try:
        with threadpool_limits(limits=n):
            yield n
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _worker_env(home: str, threads: int, extra: dict | None = None) -> dict:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": home, "TMPDIR": home, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads)}
    for k in PASS_ENV:
        if k in os.environ and k not in env:
            env[k] = os.environ[k]
    env.update(extra or {})
    return env


def role_uid(role: str, slot: int | None = None) -> int:
    """The worker uid of `role` in packed-container slot `slot` (None / 0: an unpacked container)."""
    return ROLE_UIDS[role] + UID_STRIDE * int(slot or 0)


def slot_uids(slot: int) -> list[int]:
    """Every uid of slot `slot`'s block (the role uids and the unused ones between them)."""
    base = 10001 + UID_STRIDE * int(slot)
    return list(range(base, base + UID_STRIDE - 1))


def slot_gid(slot: int) -> int:
    return SLOT_GID0 + int(slot)


#: a packed slot's worker drops to its uid / group (no supplementary groups, no new privileges), then enters NEW user, network and IPC
#: namespaces of its own: concurrent jobs of one container share no abstract Unix socket, loopback port, System V or POSIX IPC object
#: (in the container's shared namespaces they could: research/phase4/LEVEL_B_EXECUTION.md, probe of 2026-09-26). --map-current-user
#: keeps the uid / gid inside; the worker has no capability in the new namespace after exec (it is not uid 0 there).
SETPRIV, UNSHARE = "/usr/bin/setpriv", "/usr/bin/unshare"


def slot_worker_cmd(uid: int, gid: int, argv: list[str]) -> list[str]:
    return ([SETPRIV, f"--reuid={uid}", f"--regid={gid}", "--clear-groups", "--no-new-privs", "--",
             UNSHARE, "--user", "--map-current-user", "--net", "--ipc", "--"] + list(argv))


class LinuxUidTransport:
    """Workers as unprivileged uids in THIS container (the driver is root; Modal "iso" classes and the Docker self-test). slot: None for
    an unpacked container (one job at a time; the role uids); s >= 1 in a PACKED container (the slot's uid block and group, and each
    worker in namespaces of its own, `slot_worker_cmd`)."""

    kind = "linux-uid"

    def __init__(self, *, pubdir: str = PUBDIR, jobs_root: str = JOBS_ROOT, method_dir: str | None = None, python: str | None = None,
                 nproc: int = 512, slot: int | None = None):
        self.pubdir, self.jobs_root, self.method_dir = pubdir, jobs_root, method_dir
        self.python = python or sys.executable
        self.nproc = nproc
        self.method_dir_in_worker = method_dir
        self.slot = None if slot is None else int(slot)
        if self.slot is not None and not 1 <= self.slot <= MAX_SLOTS:
            raise ValueError(f"slot {slot} outside 1..{MAX_SLOTS}")
        # EVERY LIVE WORKER HAS ITS OWN UID (P2's finding, 2026-09-27): the uid was a function of the role only, so every model worker of
        # one phase in one job shared it, and a worker start (which SIGKILLs its uid's processes) killed the other models' workers; their
        # next calls failed and were scored as the method's failures. Workers now take a FREE uid of this transport's block (the slot's
        # block; the role's own uid when it is free) and return it after their clean-up, so a start or a clean-up only ever kills its own
        # worker's processes. A job runs at most len(block) workers at once (InfraFault beyond).
        self._uid_lock = threading.Lock()
        self._live_uids: set[int] = set()
        self._block = slot_uids(self.slot or 0)
        self.n_uid_starts = 0

    def _take_uid(self, role: str) -> int:
        """A uid no live worker of this transport holds: never-used uids first (the role's own uid among them first, so a job with one
        worker per role keeps the familiar uids), then the free uid used LONGEST AGO (a reused uid's previous worker was cleaned up: its
        processes killed, its IPC objects and working directory removed; reuse is spaced as far apart as the block allows)."""
        with self._uid_lock:
            pref = role_uid(role, self.slot)
            free = [u for u in self._block if u not in self._live_uids]
            if not free:
                raise InfraFault(f"no free worker uid in {'slot ' + str(self.slot) if self.slot else 'the container'}: "
                                 f"{len(self._live_uids)} workers are live, the block has {len(self._block)} uids")
            last = getattr(self, "_last_used", {})
            uid = min(free, key=lambda u: (last.get(u, -1), u != pref, u))
            self._live_uids.add(uid)
            self.n_uid_starts += 1
            self.__dict__.setdefault("_last_used", {})[uid] = self.n_uid_starts
            return uid

    def _give_uid(self, uid: int) -> None:
        with self._uid_lock:
            self._live_uids.discard(uid)

    def live_uids(self) -> list[int]:
        with self._uid_lock:
            return sorted(self._live_uids)

    def _spawn(self, argv: list[str], uid: int, gid: int, common: dict) -> subprocess.Popen:
        if self.slot is None:
            return subprocess.Popen(argv, user=uid, group=uid, extra_groups=[], **common)
        return subprocess.Popen(slot_worker_cmd(uid, gid, argv), **common)

    def _limit(self, pid: int) -> None:
        import resource
        for lim, val in ((resource.RLIMIT_NPROC, self.nproc), (resource.RLIMIT_CORE, 0)):
            with contextlib.suppress(Exception):
                resource.prlimit(pid, lim, (val, val))

    def start(self, role: str, *, threads: int) -> WorkerProc:
        uid = self._take_uid(role)
        try:
            gid = uid if self.slot is None else slot_gid(self.slot)
            kill_uids([uid])                        # only this worker's OWN uid (stale processes of the worker that held it before)
            ipc_cleanup([uid])
            wd = Path(self.jobs_root) / f"w_{role}_{uuid.uuid4().hex}"
            wd.mkdir(mode=0o700)
            os.chown(wd, uid, gid)
            os.chmod(wd, 0o700)
            argv = [self.python, "-I", "-B", "-c", BOOT.format(pub=self.pubdir)]
            common = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "cwd": str(wd),
                      "env": _worker_env(str(wd), threads), "umask": 0o077, "start_new_session": True, "close_fds": True}
            p = self._spawn(argv, uid, gid, common)
            self._limit(p.pid)
        except BaseException:
            self._give_uid(uid)
            raise

        def cleanup():
            try:
                kill_uids([uid])
                ipc_cleanup([uid])
                shutil.rmtree(wd, ignore_errors=True)
            finally:
                self._give_uid(uid)                 # free for another worker only after its processes are gone
        where = f"uid {uid}" if self.slot is None else f"uid {uid} slot {self.slot} (own user/net/ipc namespaces)"
        return WorkerProc(p, role=role, cleanup=cleanup, where=where)


def sandbox_image() -> str:
    """The pinned Docker sandbox image id (docker/p4sandbox/image.json)."""
    p = Path(__file__).resolve().parents[3] / "docker" / "p4sandbox" / "image.json"
    return json.loads(p.read_text(encoding="utf-8"))["id"]


def docker_exe() -> str:
    exe = shutil.which("docker")
    if exe:
        return exe
    win = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
    if win.exists():
        return str(win)
    raise FileNotFoundError("docker is not installed")


def _mount_src(p: Path | str) -> str:
    return str(Path(p).resolve()).replace("\\", "/")


class DockerTransport:
    """Workers in the Docker sandbox image (the development machine): one container per worker, no network, read-only root, every
    capability dropped, an unprivileged uid, only the public modules and the method snapshot mounted (read-only)."""

    kind = "docker"

    def __init__(self, *, pubdir: Path | str, method_dir: Path | str | None = None, image: str | None = None, cpus: float = 2.0,
                 mem_gb: float = 6.0, work_gb: float = 4.0, pids: int = 512, docker: str | None = None):
        self.pubdir = Path(pubdir)
        self.method_dir = Path(method_dir) if method_dir else None
        self.image = image or sandbox_image()
        self.cpus, self.mem_gb, self.work_gb, self.pids = cpus, mem_gb, work_gb, pids
        self.docker = docker or docker_exe()
        self.method_dir_in_worker = METHOD_MOUNT if self.method_dir else None

    def command(self, role: str, *, threads: int, name: str) -> list[str]:
        uid = ROLE_UIDS[role]
        cmd = [self.docker, "run", "-i", "--rm", "--pull", "never", "--name", name, "--network", "none", "--read-only",
               "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
               "--tmpfs", f"/work:rw,nosuid,nodev,size={int(self.work_gb * 1024)}m,uid={uid},gid={uid},mode=0700",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", str(self.pids),
               "--user", f"{uid}:{uid}", "--cpus", str(self.cpus), "--memory", f"{self.mem_gb}g", "--memory-swap", f"{self.mem_gb}g",
               "-w", "/work", "--label", "brainir.p4.worker=1", "--label", f"brainir.p4.role={role}",
               "--mount", f"type=bind,source={_mount_src(self.pubdir)},target={PUBDIR},readonly"]
        if self.method_dir is not None:
            cmd += ["--mount", f"type=bind,source={_mount_src(self.method_dir)},target={METHOD_MOUNT},readonly"]
        for k, v in _worker_env("/work", threads).items():
            cmd += ["-e", f"{k}={v}"]
        return cmd + [self.image, "python", "-I", "-B", "-c", BOOT.format(pub=PUBDIR)]

    def start(self, role: str, *, threads: int) -> WorkerProc:
        name = f"p4w-{role.lower()}-{uuid.uuid4().hex[:16]}"
        p = subprocess.Popen(self.command(role, threads=threads, name=name), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)

        def cleanup():
            subprocess.run([self.docker, "rm", "-f", name], capture_output=True, timeout=60, check=False)
        return WorkerProc(p, role=role, cleanup=cleanup, where=f"docker {name}")


class LocalUnsafeTransport:
    """Workers as ordinary child processes of the same user: NO isolation beyond the separate process, the scrubbed environment and
    the public code path. Only for TRUSTED models (the equivalence tests, the benchmark's own references); tournaments refuse it."""

    kind = "local-unsafe"

    def __init__(self, *, pubdir: Path | str, method_dir: Path | str | None = None, python: str | None = None):
        self.pubdir = str(Path(pubdir).resolve())
        self.method_dir = str(Path(method_dir).resolve()) if method_dir else None
        self.method_dir_in_worker = self.method_dir
        self.python = python or sys.executable

    def start(self, role: str, *, threads: int) -> WorkerProc:
        wd = tempfile.mkdtemp(prefix=f"p4w_{role}_")
        env = _worker_env(wd, threads)
        if os.name == "nt":
            env.update({"SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\WINDOWS"), "PATH": os.environ.get("PATH", ""), "USERPROFILE": wd,
                        "TEMP": wd, "TMP": wd})
        p = subprocess.Popen([self.python, "-I", "-B", "-c", BOOT.format(pub=self.pubdir)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=wd, env=env)
        return WorkerProc(p, role=role, cleanup=lambda: shutil.rmtree(wd, ignore_errors=True), where="local process (unsafe)")


# ================================================================================================================ the client
class WorkerClient:
    """The driver's end of one worker: requests are pickled, replies decoded with the SAFE codec only."""

    def __init__(self, transport, role: str, *, method_dir: str | None = None, threads: int = 2, allowed=(), tripwire: bool = True,
                 preimport: bool = True, call_timeout_s: float = CALL_TIMEOUT_S, init_timeout_s: float = INIT_TIMEOUT_S,
                 max_reply_bytes: int = MAX_REPLY_BYTES):
        self.role = role
        self.call_timeout_s = float(call_timeout_s)
        self.max_reply_bytes = int(max_reply_bytes)
        self.fatal: str | None = None
        self.closed = False
        self.n_requests = 0
        self.bytes_in = self.bytes_out = 0
        self.t0 = time.time()
        self._ids = itertools.count(1)
        self._q: queue.Queue = queue.Queue()
        self._err: collections.deque = collections.deque(maxlen=400)
        self.proc = transport.start(role, threads=threads)
        self.where = self.proc.where
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._err_loop, daemon=True).start()
        try:
            self.init = self.request("init", timeout=init_timeout_s, method_dir=method_dir, threads=int(threads), allowed=list(allowed),
                                     tripwire=bool(tripwire), preimport=bool(preimport))
        except BaseException:                       # incl. WorkerDied (an InfraFault): the process is cleaned up either way
            self.close()
            raise

    def _read_loop(self) -> None:
        try:
            while True:
                fr = W.read_frame(self.proc.stdout, max_frame=self.max_reply_bytes)
                if fr is None:
                    self._q.put(("eof", None))
                    return
                self._q.put(("frame", fr))
        except BaseException as e:  # noqa: BLE001 - reported to the waiting request
            self._q.put(("error", f"{type(e).__name__}: {e}"))

    def _err_loop(self) -> None:
        try:
            for line in iter(self.proc.stderr.readline, b""):
                self._err.append(line.decode("utf-8", "replace")[:2000])
        except Exception:  # noqa: BLE001, S110
            pass

    def stderr_tail(self, n: int = 40) -> str:
        return "".join(list(self._err)[-n:])[-6000:]

    def _die(self, why: str, exc=WorkerDied):
        self.fatal = why
        self.proc.kill()
        return exc(f"{self.role} worker ({self.where}): {why}; stderr tail: {self.stderr_tail(12)[-1500:]}")

    def request(self, op: str, *, timeout: float | None = None, **kw):
        if self.fatal:
            raise WorkerError(f"{self.role} worker is unusable: {self.fatal}")
        if self.closed:
            raise WorkerError(f"{self.role} worker is closed")
        rid = next(self._ids)
        payload = pickle.dumps({"id": rid, "op": op, **kw}, protocol=pickle.HIGHEST_PROTOCOL)
        try:
            W.write_frame(self.proc.stdin, payload)
        except (OSError, ValueError) as e:
            raise self._die(f"cannot send ({type(e).__name__})") from None
        self.n_requests += 1
        self.bytes_out += len(payload)
        try:
            kind, fr = self._q.get(timeout=timeout or self.call_timeout_s)
        except queue.Empty:
            raise self._die(f"no reply to {op!r} within {timeout or self.call_timeout_s:.0f} s", WorkerTimeout) from None
        if kind != "frame":
            raise self._die(f"no reply to {op!r} ({kind}: {fr})")
        self.bytes_in += len(fr)
        try:
            msg = W.decode_safe(fr, self.max_reply_bytes)
        except Exception as e:  # noqa: BLE001 - anything the codec refuses ends the worker
            raise self._die(f"protocol violation ({type(e).__name__}: {str(e)[:200]})", ProtocolViolation) from None
        if not isinstance(msg, dict) or msg.get("id") != rid or not ({"ok", "error"} & set(msg)):
            raise self._die("protocol violation (malformed reply)", ProtocolViolation)
        if "error" in msg:
            raise RemoteCallError(str(msg["error"])[:2000], str(msg.get("traceback") or "")[-4000:])
        return msg.get("ok")

    def close(self) -> dict:
        stats = None
        if not self.closed and not self.fatal:
            with contextlib.suppress(Exception, WorkerDied):      # a worker that died after its last reply: nothing is lost
                stats = self.request("shutdown", timeout=60)
        self.closed = True
        self.proc.wait(10)
        self.proc.finish()
        return {"role": self.role, "where": self.where, "wall_s": round(time.time() - self.t0, 2), "n_requests": self.n_requests,
                "bytes_in": self.bytes_in, "bytes_out": self.bytes_out, "stats": stats, "fatal": self.fatal,
                "stderr_tail": self.stderr_tail(20)[-3000:]}


# ================================================================================================================ evaluation
def _proxy_class(overrides: dict):
    from .api import CausalStateModel

    def fwd(name):
        def f(self, *a, **k):
            return self._rf._call(name, a, k)
        f.__name__ = name
        return f

    def init(self, rf, k):
        self._rf = rf
        self.k = dict(k or {})

    def refuse(self, *a, **k):
        raise TypeError("a remote model is never serialised or loaded by the driver")

    ns = {"__module__": __name__, "__qualname__": "RemoteModelProxy", "__init__": init, "__reduce__": refuse, "save": refuse,
          "info": lambda self: self._rf.info()}
    for name in ("encode", "rollout", "readout", "supports", "step", "read_in", "intervention_effect", "uncertainty", "validity", "schema"):
        ns[name] = fwd(name)
    # evaluate_lift.lift_supported checks whether the class overrides CausalStateModel.lift: mirror the remote class
    ns["lift"] = fwd("lift") if overrides.get("lift") else CausalStateModel.lift
    return type("RemoteModelProxy", (CausalStateModel,), ns)


#: model calls that hand the worker an observed HISTORY (x_hist is their second argument, after the system id)
HISTORY_OPS = frozenset({"encode", "intervention_effect", "lift", "uncertainty", "validity"})
#: PRE-STARTED SPARE WORKERS per (sub-)phase of a RemoteFresh, after that phase's first restart (research/phase4/EVAL_ARCHITECTURE.md
#: section 6): a worker restart costs about 5.6 s in a packed slot, 4.8 s of it the worker's init (the environment's scientific stack
#: imported before the tripwire), and the digest rule restarts 74-118 times per evaluation on the validation systems
SPARES = 3


def history_digests(x_hist) -> tuple[bytes, bytes | None, set[bytes]]:
    """(digest of the whole history, digest of its LAST row, digests of every row that is followed by at least one more row). Rows are
    compared exactly (float64). No row is exempt (review F round 3, N3-m2: with the dataset design v2 more than half of the items have
    their held-out future inside another item's history, so the rule is load-bearing; an exemption for "uninformative" last rows only
    saves worker restarts)."""
    a = np.asarray(x_hist, dtype=np.float64)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if a.ndim != 2 or a.shape[0] == 0:
        return hashlib.blake2b(a.tobytes(), digest_size=16).digest(), None, set()
    a = np.ascontiguousarray(a)
    rows = [hashlib.blake2b(r.tobytes(), digest_size=16).digest() for r in a]
    whole = hashlib.blake2b(b"".join(rows) + str(a.shape).encode(), digest_size=16).digest()
    return whole, rows[-1], set(rows[:-1])


class RemoteFresh(Fresh):
    """A fitted model (bytes) evaluated in model workers, with the phase discipline of the module docstring. A drop-in
    `fresh.Fresh` for the evaluation code: every call forwards only its arguments and runs on a fresh copy inside the worker.

    WITHIN a phase the worker process persists (a fresh unpickled copy per call, but module state survives), so a model could
    remember the histories it was given. The driver therefore keeps, per worker process, the rows of every history it sent (exactly;
    `history_digests`), and before a history-bearing call checks whether the new history's last row already appeared, followed by
    more samples, in ANOTHER history sent to that process: such a process may hold this history's continuation (e.g. the twin
    future of an item inside a longer history of the same source trajectory), so the process is closed (its uid's processes killed,
    as between phases) and the call goes to a FRESH process (review F round 2, N-m3). Calls in increasing onset order never restart;
    `record()` reports the restarts per phase."""

    def __init__(self, model_bytes: bytes, transport, *, threads: int = 2, call_timeout_s: float = CALL_TIMEOUT_S, allowed=(),
                 load_timeout_s: float = INIT_TIMEOUT_S, spares: int | None = None):
        self._blob = None
        self._pristine = None
        self._same = None
        self.n_copies = 0
        self._model = bytes(model_bytes)
        self._transport = transport
        self._threads = int(threads)
        self._timeout = float(call_timeout_s)
        self._load_timeout = float(load_timeout_s)
        self._allowed = list(allowed)
        self.phase = "A"
        self._lifted = False
        self._workers: dict[str, WorkerClient] = {}
        self._closed: set[str] = set()
        self.meta: dict | None = None
        self.log: dict[str, dict] = {}
        self._proxy = None
        #: per (sub-)phase worker process: row digest -> digests of the histories in which that row is followed by more samples
        self._seen: dict[str, dict[bytes, set[bytes]]] = {}
        self.n_restarts = 0
        #: infrastructure events (a worker process that died, or did not start): each is followed by ONE fresh restart and retry; a
        #: second in a row fails the job (InfraFault), never the method's call
        self.n_infra = 0
        #: SPARES (module constant SPARES): after the first restart of a (sub-)phase, up to `spares` workers of that phase are started IN
        #: ADVANCE, up to and including their init, in background threads; a restart takes the oldest. Its model is loaded only when it
        #: is taken, after the old worker's processes are gone. Until then a spare has run only trusted code (the worker module, the
        #: environment's libraries, the tripwire) and has seen no model and no history: it is exactly a freshly started worker, so the
        #: results are unchanged (tests/test_worker_uids.py; scripts/p4/smoke_uids_modal.py). A transport with a uid block keeps at
        #: least two uids free for the live workers' own restarts.
        self._n_spares = SPARES if spares is None else max(0, int(spares))
        self._spares: dict[str, list] = {}
        self._spare_ex = None
        self.n_spares_used = 0

    @property
    def trusted(self) -> bool:
        return False

    def _restart_sub(self, sub: str) -> None:
        """Close the current worker process of `sub` (not the phase: the next call starts a fresh process)."""
        w = self._workers.pop(sub, None)
        rec = self.log.setdefault(sub, {})
        rec["restarts"] = rec.get("restarts", 0) + 1
        if w is not None:
            c = w.close()
            rec.setdefault("restart_closes", []).append({k: c.get(k) for k in ("n_requests", "wall_s", "fatal")})
        self._seen.pop(sub, None)
        self.n_restarts += 1

    def _new_client(self, sub: str) -> WorkerClient:
        """A started worker (init done, no model) of `sub`: the oldest spare when there is one (waiting for its init if needed), else a
        synchronous start."""
        futs = self._spares.get(sub) or []
        while futs:
            fut = futs.pop(0)
            t0 = time.time()
            try:
                w = fut.result()
            except (WorkerDied, WorkerTimeout, InfraFault) as e:      # it did not come up: recorded; the next spare, or a fresh start
                rec = self.log.setdefault(sub, {})
                rec.setdefault("infra", []).append({"what": "spare start", "error": f"{type(e).__name__}: {str(e)[:300]}"})
                continue
            rec = self.log.setdefault(sub, {})
            rec["spares_used"] = rec.get("spares_used", 0) + 1
            rec["spare_wait_s"] = round(rec.get("spare_wait_s", 0.0) + time.time() - t0, 2)
            self.n_spares_used += 1
            return w
        return WorkerClient(self._transport, sub, method_dir=getattr(self._transport, "method_dir_in_worker", None), threads=self._threads,
                            allowed=self._allowed, call_timeout_s=self._timeout)

    def _spare_room(self, n_new: int = 1) -> bool:
        """A transport with a uid block (LinuxUidTransport) keeps at least two uids free beyond the spares, so a live worker's own
        restart never fails for lack of a uid (the spares' starts are in flight, so the count is taken with them)."""
        block = getattr(self._transport, "_block", None)
        live = getattr(self._transport, "live_uids", None)
        if not block or live is None:
            return True
        pending = sum(1 for fs in self._spares.values() for f in fs if not f.done())
        return len(live()) + pending + n_new + 2 <= len(block)

    def _refill(self, sub: str) -> None:
        """Top up `sub`'s spares after a restart of `sub` (a phase that restarted once tends to restart again: histories at exact fixed
        points, P2's measurement)."""
        if not self._n_spares or sub in self._closed:
            return
        futs = self._spares.setdefault(sub, [])
        while len(futs) < self._n_spares and self._spare_room():
            if self._spare_ex is None:
                from concurrent.futures import ThreadPoolExecutor
                self._spare_ex = ThreadPoolExecutor(max_workers=max(1, self._n_spares), thread_name_prefix="p4-spare")
            futs.append(self._spare_ex.submit(WorkerClient, self._transport, sub,
                                              method_dir=getattr(self._transport, "method_dir_in_worker", None), threads=self._threads,
                                              allowed=self._allowed, call_timeout_s=self._timeout))

    def _drop_spares(self, sub: str | None = None) -> None:
        """Close the spares of `sub` (all subs: None); a spare still starting is closed once its start returns."""
        for s in ([sub] if sub is not None else list(self._spares)):
            for fut in self._spares.pop(s, []):
                try:
                    fut.result().close()
                except BaseException:  # noqa: BLE001, S110 - a spare that did not start holds nothing (its start cleaned up)
                    pass

    def _infra(self, sub: str, what: str, err: BaseException) -> None:
        """Record an infrastructure event of `sub` (a worker process that died or did not come up) and drop the dead worker; the next
        call starts a fresh process of the same (sub-)phase."""
        rec = self.log.setdefault(sub, {})
        rec.setdefault("infra", []).append({"what": what, "error": f"{type(err).__name__}: {str(err)[:300]}"})
        self.n_infra += 1
        w = self._workers.pop(sub, None)
        if w is not None:
            w.close()
        self._seen.pop(sub, None)

    # ---------------------------------------------------------------------------------------------- phases
    def set_phase(self, phase: str) -> None:
        if phase not in PHASE_ORDER:
            raise ValueError(f"unknown evaluation phase {phase!r}")
        if PHASE_ORDER.index(phase) < PHASE_ORDER.index(self.phase):
            raise PermissionError(f"evaluation phases only move forward ({self.phase} -> {phase} refused)")
        if phase == self.phase:
            return
        for sub in list(self._workers):
            self._close_sub(sub)
        self._drop_spares()                          # spares of the finished phase (their worker may already be gone)
        self.phase = phase
        self._lifted = False

    def _close_sub(self, sub: str) -> None:
        self._drop_spares(sub)
        w = self._workers.pop(sub, None)
        if w is not None:
            self.log.setdefault(sub, {})["close"] = w.close()
            self.log[sub]["closed_s"] = round(time.time() - self.log[sub].get("t0", time.time()), 2)
        self._seen.pop(sub, None)
        self._closed.add(sub)

    def _sub_for(self, name: str) -> str:
        if self.phase != "lift":
            return self.phase
        if name == "lift":
            if "B2" in self._workers or "B2" in self._closed:
                raise PermissionError("lift requests after the lift outcomes were revealed are refused")
            self._lifted = True
            return "B1"
        if not self._lifted:
            return "B1"
        if "B1" in self._workers:
            self._close_sub("B1")
        return "B2"

    def _worker(self, sub: str) -> WorkerClient:
        w = self._workers.get(sub)
        if w is not None:
            return w
        if sub in self._closed:
            raise PermissionError(f"evaluation phase {sub} is closed")
        restarted = bool(self.log.get(sub, {}).get("restarts") or self.log.get(sub, {}).get("infra"))
        for attempt in (0, 1):
            try:
                w = self._new_client(sub)
            except (WorkerDied, WorkerTimeout) as e:
                # the process did not come up (it died or never answered its init): infrastructure; one fresh start, then the job
                self._infra(sub, "start", e)
                if attempt:
                    raise InfraFault(f"{sub} worker did not start twice in a row: {type(e).__name__}: {str(e)[:600]}") from None
                continue
            t0 = time.time()
            rec = self.log.setdefault(sub, {})
            try:
                meta = w.request("load_model", timeout=self._load_timeout, blob=self._model)
            except WorkerDied as e:                  # the process died while loading: infrastructure (one fresh start)
                w.close()
                self._infra(sub, "load", e)
                if attempt:
                    raise InfraFault(f"{sub} worker died twice in a row while loading the model: {str(e)[:600]}") from None
                continue
            except Exception:                        # the model's own load failure (it raised, or its load timed out): the method's
                rec.update({"t0": t0, "close": w.close()})
                rec.setdefault("n_calls", 0)
                self._closed.add(sub)
                raise
            break
        if self.meta is None:
            self.meta = meta if isinstance(meta, dict) else {}
        self._workers[sub] = w
        if restarted:
            self._refill(sub)                        # spares for the next restarts of this phase (started after this one's model load)
        rec.update({"t0": rec.get("t0", t0), "load_s": round(rec.get("load_s", 0.0) + time.time() - t0, 2), "init": {
            "platform": (w.init or {}).get("platform"), "tripwire": (w.init or {}).get("tripwire")}})
        rec.setdefault("n_calls", 0)
        return w

    def _call(self, name: str, args=(), kwargs=None):
        sub = self._sub_for(name)
        if name not in PHASE_OPS[sub]:
            raise PermissionError(f"{name} is not allowed in evaluation phase {sub}")
        hist = None
        if name in HISTORY_OPS and len(args) > 1:
            hist = history_digests(args[1])
            whole, last, _ = hist
            if last is not None and sub in self._workers and (self._seen.get(sub, {}).get(last, set()) - {whole}):
                self._restart_sub(sub)            # this process may hold the history's continuation (class docstring)
        for attempt in (0, 1):
            w = self._worker(sub)
            if hist is not None:
                seen = self._seen.setdefault(sub, {})
                for r in hist[2]:
                    seen.setdefault(r, set()).add(hist[0])
            self.log[sub]["n_calls"] += 1
            try:
                if name == "capacity":
                    return w.request("capacity", **(kwargs or {}))
                return w.request("call", name=name, args=list(args), kwargs=dict(kwargs or {}))
            except WorkerDied as e:
                # the worker PROCESS died (killed from outside, out of memory, a lost pipe): infrastructure, never the method's failed
                # call. The same call goes ONCE to a fresh process of the same (sub-)phase (it has seen nothing: the digest record is
                # reset); a second death in a row propagates (WorkerDied is an InfraFault: `safe_call` cannot swallow it)
                self._infra(sub, f"died in {name}", e)
                if attempt:
                    raise
        raise AssertionError("unreachable")

    def _meta(self) -> dict:
        if self.meta is None:
            self._worker(self._sub_for("info"))
        return self.meta or {}

    def close(self) -> dict:
        for sub in list(self._workers):
            self._close_sub(sub)
        self._drop_spares()
        if self._spare_ex is not None:
            self._spare_ex.shutdown(wait=True)
            self._spare_ex = None
        return self.record()

    def record(self) -> dict:
        return {"transport": getattr(self._transport, "kind", "?"), "phases": {s: {k: v for k, v in r.items() if k != "t0"}
                                                                               for s, r in self.log.items()},
                "model_class": (self.meta or {}).get("class"), "model_bytes": len(self._model), "worker_restarts": self.n_restarts,
                "infra_restarts": self.n_infra, "spares_used": self.n_spares_used}

    # ---------------------------------------------------------------------------------------------- the Fresh API
    def get(self):
        if self._proxy is None:
            m = self._meta()
            self._proxy = _proxy_class(m.get("overrides") or {})(self, (m.get("info") or {}).get("k") or m.get("k_attr") or {})
        return self._proxy

    def encode(self, sid, x_hist, u_hist, dt):
        return np.asarray(self._call("encode", (sid, x_hist, u_hist, dt)), dtype=np.float64).reshape(-1)

    def rollout(self, sid, z0, u_future, events, dt):
        return self._call("rollout", (sid, np.asarray(z0, dtype=np.float64), u_future, events, dt))

    def readout(self, sid, z, u):
        return self._call("readout", (sid, z, u))

    def intervention_effect(self, sid, x_hist, u_hist, u_future, events, dt):
        return self._call("intervention_effect", (sid, x_hist, u_hist, u_future, events, dt))

    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        return self._call("lift", (sid, x_hist, u_hist, np.asarray(delta_z, dtype=np.float64), n_candidates, constraints))

    def read_in(self, sid, z, event):
        return self._call("read_in", (sid, np.asarray(z, dtype=np.float64), event))

    def uncertainty(self, sid, x_hist, u_hist, u_future, events, dt):
        return self._call("uncertainty", (sid, x_hist, u_hist, u_future, events, dt))

    def validity(self, sid, x_hist, u_hist, events):
        return self._call("validity", (sid, x_hist, u_hist, events))

    def supports(self, sid, kind):
        return bool(self._call("supports", (sid, kind)))

    def info(self) -> dict:
        return dict(self._meta().get("info") or {})

    def k(self, sid):
        m = self._meta()
        ks = (m.get("info") or {}).get("k") or m.get("k_attr") or {}
        return int(ks[sid]) if sid in ks and ks[sid] is not None else None

    def capacity(self, sids) -> dict:
        """The section 5.15 capacity record, computed on a fresh copy inside the phase-A worker."""
        return self._call("capacity", kwargs={"sids": list(sids)})


def evaluate_remote(model_bytes: bytes, inputs: dict, transport, *, threads: int = 2, call_timeout_s: float = CALL_TIMEOUT_S,
                    **kwargs) -> dict:
    """`harness.evaluate_model` on a model given as BYTES, through model workers (the driver never loads the model)."""
    from .harness import evaluate_model
    rf = RemoteFresh(model_bytes, transport, threads=threads, call_timeout_s=call_timeout_s)
    try:
        res = evaluate_model(rf, inputs, **kwargs)
    finally:
        rec = rf.close()
    res["isolation"] = rec
    return res


# ================================================================================================================ fits
def bootstrap_interventions(records: list, b: int, seed: int = 0) -> list:
    """PROTOCOL 5.10, Level C refits: a bootstrap resample of the training INTERVENTION trajectories (each with its twin), passive
    records kept. Repeated draws are renamed (key '~b<j>', the twin's twin_of updated) so every record keeps a unique key."""
    import dataclasses
    twins = {(r.meta or {}).get("twin_of"): r for r in records if (r.meta or {}).get("twin_of")}
    inter = [r for r in records if r.protocol.get("events") and not (r.meta or {}).get("twin_of")]
    keep = [r for r in records if not r.protocol.get("events") and not (r.meta or {}).get("twin_of")]
    if not inter:
        return list(records)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), int(b), 5_101]))
    counts: collections.Counter = collections.Counter()
    out = list(keep)
    for i in rng.integers(0, len(inter), size=len(inter)):
        r = inter[int(i)]
        c = counts[r.key]
        counts[r.key] += 1
        tw = twins.get(r.key)
        if c == 0:
            out.append(r)
            if tw is not None:
                out.append(tw)
            continue
        k2 = f"{r.key}~b{c}"
        out.append(dataclasses.replace(r, key=k2, meta={**(r.meta or {}), "bootstrap_copy_of": r.key}))
        if tw is not None:
            out.append(dataclasses.replace(tw, key=f"{tw.key}~b{c}", meta={**(tw.meta or {}), "twin_of": k2, "bootstrap_copy_of": tw.key}))
    return out


def start_client(transport, role: str, **kw) -> WorkerClient:
    """A `WorkerClient` whose process does not come up (it dies, or never answers its init) is an INFRASTRUCTURE fault (InfraFault),
    never the method's failure; a worker that dies later raises WorkerDied (an InfraFault) from its request."""
    try:
        return WorkerClient(transport, role, **kw)
    except WorkerTimeout as e:
        raise InfraFault(f"{role} worker did not start: {e}") from None


def fit_records(transport, *, method: str, records: list, systems: dict, config: dict | None = None, seed: int = 0,
                adapt_from: bytes | None = None, threads: int = 3, timeout_s: float = 4 * 3600) -> dict:
    """Fit a method in a fit worker. Returns {"model": bytes, "side": {...}, "worker": {...}}; raises on failure (a worker process that
    died: WorkerDied, an InfraFault; the fit's own error or its timeout: the method's failure)."""
    w = start_client(transport, "fit", method_dir=getattr(transport, "method_dir_in_worker", None), threads=threads,
                     call_timeout_s=timeout_s)
    try:
        out = w.request("fit", timeout=timeout_s, method=method, records=list(records), systems=dict(systems), config=dict(config or {}),
                        seed=int(seed), adapt_from=adapt_from)
    finally:
        wrec = w.close()
    if not isinstance(out, dict) or not isinstance(out.get("model"), bytes):
        raise ProtocolViolation("the fit worker returned no model bytes")
    return {"model": out["model"], "side": dict(out.get("side") or {}), "worker": wrec}


def fit_job(job: dict, transport) -> dict:
    """One fit. job: {"method", "systems": [sid, ...], "data": [public data dirs], ["seed"], ["config"], ["splits"] ("train"),
    ["bootstrap"] (Level C refit index), ["adapt_from"] (model bytes), ["threads"], ["timeout_s"]}. Returns {"model": bytes, "side"}."""
    from .runner import load_records
    t0 = time.time()
    splits = str(job.get("splits", "train"))
    recs, sysinfo = load_records(list(job["data"]), list(job["systems"]), set(splits.split(",")))
    if job.get("bootstrap") is not None:
        recs = bootstrap_interventions(recs, int(job["bootstrap"]), seed=int(job.get("bootstrap_seed", 0)))
    out = fit_records(transport, method=job["method"], records=recs, systems=sysinfo, config=job.get("config"), seed=int(job.get("seed", 0)),
                      adapt_from=job.get("adapt_from"), threads=int(job.get("threads", 3)), timeout_s=float(job.get("timeout_s", 4 * 3600)))
    side = out["side"]
    side.update({"systems": list(job["systems"]), "seed": int(job.get("seed", 0)), "config": dict(job.get("config") or {}),
                 "adapted": job.get("adapt_from") is not None, "splits": splits, "bootstrap": job.get("bootstrap"), "n_train": len(recs),
                 "job_wall_s": round(time.time() - t0, 2), "isolation": {"transport": getattr(transport, "kind", "?"),
                                                                           "worker": {k: v for k, v in out["worker"].items() if k != "stderr_tail"}}})
    return {"model": out["model"], "side": side}


def describe_method(transport, method: str, timeout_s: float = 600) -> dict:
    """The method's declared name, version, device and designer (imported in a worker: the driver never imports method code)."""
    w = start_client(transport, "describe", method_dir=getattr(transport, "method_dir_in_worker", None), threads=1, preimport=False,
                     call_timeout_s=timeout_s)
    try:
        return w.request("describe", method=method)
    finally:
        w.close()


# ================================================================================================================ loops
class _LoopModel:
    """The driver's handle of the loop worker's CURRENT model (run_loop saves checkpoints through it; reference designers query it)."""

    def __init__(self, client: WorkerClient):
        self._c = client

    def _fwd(self, name, *a, **k):
        return self._c.request("loop_call", name=name, args=list(a), kwargs=k)

    def info(self):
        return self._c.request("loop_info")

    def save(self, path):
        Path(path).write_bytes(self._c.request("loop_bytes")["model"])

    def encode(self, *a, **k):
        return self._fwd("encode", *a, **k)

    def rollout(self, *a, **k):
        return self._fwd("rollout", *a, **k)

    def readout(self, *a, **k):
        return self._fwd("readout", *a, **k)

    def supports(self, *a, **k):
        return bool(self._fwd("supports", *a, **k))

    def intervention_effect(self, *a, **k):
        return self._fwd("intervention_effect", *a, **k)

    def uncertainty(self, *a, **k):
        return self._fwd("uncertainty", *a, **k)

    def validity(self, *a, **k):
        return self._fwd("validity", *a, **k)


class WorkerLearner:
    """run_loop's learner: fit / update run in the loop worker; the returned model is the worker's current model (`_LoopModel`)."""

    def __init__(self, client: WorkerClient, timeout_s: float):
        self.c = client
        self.timeout_s = timeout_s
        self.handle = _LoopModel(client)
        self.cpu_s = 0.0
        self.marks: list[tuple[int, float]] = []

    def _mark(self, r: dict) -> None:
        self.cpu_s += float((r or {}).get("cpu_s") or 0.0)
        self.marks.append((int((r or {}).get("n") or 0), round(self.cpu_s, 3)))

    def fit(self, data, *, systems, config=None, seed=0):
        self._mark(self.c.request("loop_fit", timeout=self.timeout_s, records=list(data)))
        return self.handle

    def update(self, model, new_data, *, data_all, systems, config=None, seed=0):
        self._mark(self.c.request("loop_update", timeout=self.timeout_s, records=list(new_data)))
        return self.handle


class WorkerDesigner:
    """The method's OWN designer, running in the loop worker. The driver passes a seed drawn from run_loop's generator; the proposals
    come back through the safe codec and run_loop validates them against the public policy."""

    def __init__(self, client: WorkerClient, name: str):
        self.c = client
        self.name = name
        self.cpu_s = 0.0

    def propose(self, system_id, system, model, data, n, budget_left, rng):
        r = self.c.request("loop_propose", system_id=system_id, sysrec=dict(system), n=int(n), budget_left=int(budget_left),
                           rng_seed=int(rng.integers(0, 2 ** 63 - 1)))
        self.cpu_s += float((r or {}).get("cpu_s") or 0.0)
        return list((r or {}).get("proposals") or [])


def loop_job(job: dict, transport, *, sim=None, out_dir: Path | str) -> dict:
    """One experiment loop (PROTOCOL 5.17) run by the driver. job: {"method", "designer" ('own' | a reference designer | 'random_matched'),
    "sid", "data": [public data dirs], "budget", ["checkpoints"], ["batch"], ["seed"], ["config"], ["profile_dir"] (random_matched: the
    method's own loop directory), ["threads"], ["timeout_s"]} plus the system-context keys of `harness.system_context` when `sim` is
    not given. Writes run_loop's files (checkpoints, loop_record.json, experiments.jsonl) into out_dir."""
    from . import designers as D
    from .api import get_designer
    from .loop import CHECKPOINTS, DirectSim, run_loop
    from .runner import load_records
    sid = job["sid"]
    recs, sysinfo = load_records(list(job["data"]), [sid], {"train"})
    d0 = [r for r in recs if not r.protocol.get("events") and (r.meta or {}).get("role", "d0") == "d0" and r.split == "train"]
    if sim is None:
        from .harness import system_context
        _inputs, _internal, ctx, _truth = system_context(job)
        sim = DirectSim(ctx, known=recs)
    timeout_s = float(job.get("timeout_s", 4 * 3600))
    c = start_client(transport, "loop", method_dir=getattr(transport, "method_dir_in_worker", None), threads=int(job.get("threads", 3)),
                     call_timeout_s=timeout_s)
    try:
        dsg = str(job["designer"])
        info = c.request("loop_init", method=job["method"], own_designer=(dsg == "own"), systems={sid: sysinfo[sid]},
                         config=dict(job.get("config") or {}), seed=int(job.get("seed", 0)))
        learner = WorkerLearner(c, timeout_s)
        if dsg == "own":
            designer, dname = WorkerDesigner(c, str(info.get("designer"))), f"own:{info.get('designer')}"
        elif dsg == "random_matched":
            designer, dname = D.MagnitudeMatchedDesigner.from_loop(job["profile_dir"], sysinfo[sid]), "random_matched"
        else:
            designer, dname = get_designer(dsg), dsg
        cps = tuple(int(x) for x in job["checkpoints"]) if job.get("checkpoints") else CHECKPOINTS
        rec = run_loop(learner, designer, sid, sysinfo[sid], d0, sim, budget=int(job["budget"]), checkpoints=cps,
                       batch=int(job.get("batch", 5)), seed=int(job.get("seed", 0)), out_dir=out_dir, config=dict(job.get("config") or {}),
                       designer_name=dname)
    finally:
        wrec = c.close()
    # the worker-measured learner / designer CPU seconds (run_loop measures the driver's own process time)
    marks = dict(learner.marks)
    for e in rec.get("checkpoints") or []:
        e["worker_learner_cpu_s"] = marks.get(int(e.get("n_records") or -1))
    rec["worker_learner_cpu_s"] = round(learner.cpu_s, 3)
    rec["worker_designer_cpu_s"] = round(getattr(designer, "cpu_s", 0.0), 3) if dsg == "own" else None
    rec["isolation"] = {"transport": getattr(transport, "kind", "?"), "worker": {k: v for k, v in wrec.items() if k != "stderr_tail"},
                        "worker_platform": (info or {}).get("platform")}
    if wrec.get("fatal"):
        rec["worker_error"] = wrec["fatal"]
    Path(out_dir, "loop_record.json").write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return rec


# ================================================================================================================ Modal container entry
def ensure_pubdir(dest: str = PUBDIR) -> dict:
    if _LOCKED.get("pubdir") != dest:
        _LOCKED["pubdir_manifest"] = build_pubdir(dest)
        _LOCKED["pubdir"] = dest
    return _LOCKED["pubdir_manifest"]


#: directories of hash-locked orchestrator scripts baked into the iso image (root-only after the image lockdown) whose modules an iso
#: "call" job may name (plain module names, loaded from these files); anything else must be a brainir_causal.* module
ISO_SCRIPT_DIRS = ("/repo/scripts/p4",)


def resolve_iso_target(target: str):
    """The function of an iso "call" job: "brainir_causal.<module>:<function>" or "<module>:<function>" for a module file of
    ISO_SCRIPT_DIRS (trusted code only: the method snapshot is never on this path)."""
    import importlib
    import importlib.util
    mod, _, fn = target.partition(":")
    if not fn or not fn.isidentifier():
        raise ValueError(f"iso call target {target!r} is not 'module:function'")
    if mod.startswith("brainir_causal.") and all(part.isidentifier() for part in mod.split(".")):
        if mod == "brainir_causal.methods" or mod.startswith("brainir_causal.methods."):
            raise PermissionError("an iso call target is never method code")
        return getattr(importlib.import_module(mod), fn)
    if mod.isidentifier():
        for d in ISO_SCRIPT_DIRS:
            f = Path(d) / f"{mod}.py"
            if f.is_file():
                name = f"p4iso_script_{mod}"
                if name not in sys.modules:
                    spec = importlib.util.spec_from_file_location(name, f)
                    m = importlib.util.module_from_spec(spec)
                    sys.modules[name] = m
                    spec.loader.exec_module(m)
                return getattr(sys.modules[name], fn)
    raise PermissionError(f"iso call target {target!r}: only brainir_causal.* modules or modules of {ISO_SCRIPT_DIRS}")


def run_iso_payload(p: dict, slot: int | None = None) -> dict:
    """Container side of job kind "iso" (p4modal.remote.dispatch). payload: {"role": "fit" | "eval" | "loop" | "describe",
    "job": {...}, "methods_key" | "method_tar" (bytes), "model" (bytes, eval), "threads", "timeout_s"}. The driver (this process, root)
    locks the container down, builds the public code directory, extracts the method snapshot into a private per-job directory and
    runs the job with uid workers. Returns plain data (model bytes, side records, evaluation results, loop files).
    slot (a CHILD driver of a packed container, `run_iso_packed`): the parent locked the container down and built the public directory
    before any slot started; this job uses only its slot's uids and group (job directory root:group 0710, so other slots cannot even
    traverse it), its workers run in namespaces of their own, and its clean-up touches only its own uids."""
    t0 = time.time()
    if slot is None:
        lock = container_lockdown()
        pub = ensure_pubdir(PUBDIR)
    else:
        set_nondumpable()
        lock = dict(_PACK_CHILD.get("lock") or {})
        pub = json.loads((Path(PUBDIR) / "PUBDIR_MANIFEST.json").read_text(encoding="utf-8"))
    jobdir = Path(JOBS_ROOT) / f"j_{uuid.uuid4().hex}"
    if slot is None:
        jobdir.mkdir(mode=0o711)
        os.chmod(jobdir, 0o711)
    else:
        jobdir.mkdir(mode=0o700)
        os.chown(jobdir, 0, slot_gid(slot))
        os.chmod(jobdir, 0o710)
    out: dict = {}
    threads = job_threads(p)
    pin = contextlib.ExitStack()
    try:
        pin.enter_context(pinned_threads(threads))  # the driver's own numerics never depend on the container's CPU count
        mdir = None
        if p.get("method_tar") is not None or p.get("methods_key"):
            src = None if p.get("method_tar") is not None else Path("/fitvol/methods") / f"{p['methods_key']}.tar"
            mdir = str(extract_snapshot(p.get("method_tar"), src, jobdir / f"m_{uuid.uuid4().hex}"))
        tr = LinuxUidTransport(pubdir=PUBDIR, jobs_root=str(jobdir), method_dir=mdir, slot=slot)
        job, role = dict(p.get("job") or {}), p["role"]
        staged: set = set()                         # the volumes this job staged artefacts to (the caller commits them)
        # the staging size: STAGE_THRESHOLD, or a payload's "stage_threshold" (tests force staging of a small model with 0, or keep a
        # model inline with a large value, to compare the two paths bit for bit)
        thr = int(p["stage_threshold"]) if p.get("stage_threshold") is not None else STAGE_THRESHOLD
        if role == "fit":
            out = fit_job(job, tr)
            if isinstance(out.get("model"), bytes) and len(out["model"]) > thr:
                out["model_ref"] = stage_blob(out.pop("model"), vol="store")   # public-data-derived: the store volume
                staged.add("store")
        elif role == "describe":
            out = {"describe": describe_method(tr, job["method"])}
        elif role == "eval":
            from .harness import evaluate_job
            model_bytes = read_staged(p["model_ref"]) if p.get("model_ref") is not None else p["model"]   # a large model comes via the volume
            res = evaluate_job(job, transport=tr, model_bytes=model_bytes)
            out = {"result": res}
            with contextlib.suppress(Exception):
                blob = pickle.dumps(res, protocol=pickle.HIGHEST_PROTOCOL)
                if len(blob) > thr:                 # held-out-derived: the EVAL volume only (never a volume fit containers mount)
                    out = {"result_ref": stage_blob(blob, vol="eval")}
                    staged.add("eval")
        elif role == "loop":
            ld = jobdir / "loop_out"
            ld.mkdir(mode=0o700)
            if p.get("profile_files"):
                prof = jobdir / "profile"
                prof.mkdir(mode=0o700)
                for name, blob in p["profile_files"].items():
                    (prof / Path(name).name).write_bytes(blob)
                job["profile_dir"] = str(prof)
            rec = loop_job(job, tr, out_dir=ld)
            files, refs = {}, {}
            for f in sorted(ld.iterdir()):
                if not f.is_file():
                    continue
                b = f.read_bytes()
                if len(b) > thr:                     # a checkpoint model can be large; stage it (EVAL volume: the loop ran on the
                    refs[f.name] = stage_blob(b, vol="eval")     # system's truth), keep small files (records, JSON) inline
                    staged.add("eval")
                else:
                    files[f.name] = b
            out = {"loop_record": rec, "files": files, "file_refs": refs}
        elif role == "call":
            # a TRUSTED orchestrator function that drives model workers itself (several models per job, adapted refits, ...): it runs
            # here in the driver with this job's transport; the models travel as opaque bytes (never loaded by the driver). A large input
            # model comes BY REF ("model_refs": {name: Backend.stage_put ref}; read here, hash-checked, freshness-checked like "model_ref")
            fn = resolve_iso_target(str(p["target"]))
            models = dict(p.get("models") or {})
            for name, ref in (p.get("model_refs") or {}).items():
                models[str(name)] = read_staged(ref)
            res = fn(job, transport=tr, models=models)
            out = {"result": res}
            if isinstance(res, dict) and isinstance(res.get("staged"), (list, tuple, set)):
                staged |= {v for v in res["staged"] if v in STAGE_ROOTS}   # e.g. a target that staged its own model (stage_blob)
        else:
            raise ValueError(f"unknown iso role {role!r}")
    finally:
        pin.close()
        own = None if slot is None else slot_uids(slot)
        kill_uids(own)
        ipc_cleanup(own)
        shutil.rmtree(jobdir, ignore_errors=True)
    staged |= fit_inline(out, p.get("role"), mounted=_mounted_stage_vols())
    # On a block_network container (every iso class, packed or not) Modal cannot return an output above 2 MiB (it would go through the
    # blob store, which needs the network). Large artefacts are staged above; anything still too large (e.g. a test forcing a high
    # stage_threshold) fails the job with a clear error rather than crashing the container's output push into Modal's retries.
    if p.get("__block_network"):
        big = 0
        for v in (out.get("model"),):
            if isinstance(v, (bytes, bytearray)):
                big += len(v)
        for v in (out.get("files") or {}).values():
            if isinstance(v, (bytes, bytearray)):
                big += len(v)
        if "result" in out:
            with contextlib.suppress(Exception):
                big += len(pickle.dumps(out["result"], protocol=pickle.HIGHEST_PROTOCOL))
        if big > MAX_INLINE_OUTPUT:
            out = {"error": f"iso {p['role']} output is {big} bytes inline, above the {MAX_INLINE_OUTPUT}-byte limit of a block_network "
                            f"container, and was not staged (stage_threshold {thr}); stage it through the volume (the default "
                            f"threshold {STAGE_THRESHOLD} does)"}
    out["iso"] = {"role": p["role"], "wall_s": round(time.time() - t0, 2), "pubdir_files": pub.get("n_files"), "driver_threads": threads,
                  "p3_baseline": pub.get("p3_baseline"),
                  "lockdown": {k: v for k, v in lock.items() if k in ("dumpable0", "private", "shared_tmp", "killed", "ipc_removed")},
                  "world_writable_fixed": (_LOCKED.get("record") or {}).get("world_writable", {}).get("n_fixed")
                  if slot is None else (_PACK_CHILD.get("lock") or {}).get("world_writable_fixed")}
    if slot is not None:
        out["iso"]["slot"] = int(slot)
    if staged:
        out["staged"] = sorted(staged)              # the volumes the driver staged to; the caller commits them (safe: commit does not
        out["iso"]["staged"] = sorted(staged)       # remount, and only new content-addressed files were added)
    return out


# ================================================================================================================ packed containers
#: container-side state of a PACKED container (Modal input concurrency: several inputs of one iso class run at once in one container)
_PACK: dict = {"lock": threading.Lock(), "ready": False, "free": [], "busy": set()}
_PACK_CHILD: dict = {}


def namespaces_ok(slot: int = MAX_SLOTS) -> dict:
    """Can a slot worker enter its own user + network + IPC namespaces here (gVisor on Modal: yes, as the unprivileged worker; root
    itself may not)? Runs `slot_worker_cmd` once with a probe command; packing FAILS CLOSED when it cannot."""
    uid, gid = role_uid("probe", slot), slot_gid(slot)
    # the worker's network interfaces AND whether its loopback is UP: the packed classes are not block_network (Modal's >2 MiB data path
    # needs the container network), so the worker's own namespace IS its network boundary. It must hold nothing but a DOWN loopback.
    code = ("import os; n = os.readlink('/proc/self/ns/net'); i = os.readlink('/proc/self/ns/ipc'); "
            "ifs = ','.join(sorted(l.split(':')[0].strip() for l in open('/proc/net/dev').read().splitlines()[2:] if ':' in l)); "
            "flags = open('/sys/class/net/lo/flags').read().strip() if os.path.exists('/sys/class/net/lo/flags') else '0x0'; "
            "print(os.getuid(), os.getgid(), n, i, ifs or '-', flags)")
    try:
        r = subprocess.run(slot_worker_cmd(uid, gid, [sys.executable, "-I", "-S", "-c", code]), capture_output=True, text=True, timeout=60,
                           cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    host = (os.readlink("/proc/self/ns/net"), os.readlink("/proc/self/ns/ipc"))
    return _namespaces_decide(r.returncode, r.stdout, r.stderr, host, uid, gid)


def _namespaces_decide(returncode: int, stdout: str, stderr: str, host: tuple[str, str], uid: int, gid: int) -> dict:
    """Fail-closed decision for `namespaces_ok` (pure, unit-tested): the worker must have run as uid/gid, in a net AND an ipc namespace
    both DIFFERENT from the host's, with NO interface other than loopback, and the loopback DOWN (IFF_UP = 0x1 clear). Anything else -> not
    ok. Interfaces are parsed from /proc/net/dev, lo's flags from /sys/class/net/lo/flags."""
    parts = stdout.split()
    if returncode != 0 or len(parts) != 6:
        return {"ok": False, "worker": stdout.strip()[:200], "host": list(host), "reason": "worker did not report", "stderr": stderr.strip()[-300:]}
    w_uid, w_gid, w_net, w_ipc, ifs, lo_flags = parts
    interfaces = set(ifs.split(",")) - {"-"}
    try:
        lo_up = bool(int(lo_flags, 16) & 0x1)
    except ValueError:
        lo_up = True                                       # unparseable flags -> assume up -> fail closed
    reasons = []
    if w_uid != str(uid) or w_gid != str(gid):
        reasons.append(f"ran as {w_uid}:{w_gid}, not {uid}:{gid}")
    if w_net == host[0]:
        reasons.append("shares the host network namespace")
    if w_ipc == host[1]:
        reasons.append("shares the host IPC namespace")
    if not interfaces <= {"lo"}:
        reasons.append(f"has non-loopback interfaces {sorted(interfaces)}")
    if lo_up:
        reasons.append(f"loopback is UP (flags {lo_flags})")
    return {"ok": not reasons, "worker": stdout.strip()[:200], "host": list(host), "worker_interfaces": ifs, "lo_flags": lo_flags,
            "reasons": reasons, "stderr": stderr.strip()[-300:]}


def pack_ready(slots: int, *, reload_vols=(), reload_once=None, gen: int = 0) -> dict:
    """Once per packed container, before any slot starts: RELOAD the volumes ONCE (so every slot sees the round's uploads), then the
    container lockdown (which chmods the mounts 0700; kills every worker uid of every slot; fails closed), the public code directory, the
    namespace check (fails closed) and the root-only exchange directory of the child drivers. After this, nothing reloads while a slot is
    busy (a reload can hide files from a slot reading them: P2's report, 2026-09-26).
    FRESHNESS ACROSS WAVES: every wave of `Backend.run_packed` stamps its inputs with a generation `gen`. A WARM container that receives
    a newer generation (e.g. the checkpoint evaluations after the loops, whose models were staged after the container's first reload)
    DRAINS first (new inputs wait until no slot of the older generation is busy), then reloads the volumes once, locks the container down
    again (idempotent; it kills stray worker uids, and no slot is running) and records the generation."""
    with _PACK["lock"]:
        if _PACK["ready"] and int(gen) > int(_PACK.get("gen", 0)):
            cond = _PACK["cond"]
            while _PACK["busy"]:
                cond.wait(timeout=5.0)
            if int(gen) > int(_PACK.get("gen", 0)):        # another input of this generation may have refreshed meanwhile
                if reload_once is not None:
                    for v in reload_vols or ():
                        reload_once(v)
                _PACK["record"] = container_lockdown()
                _PACK["gen"] = int(gen)
                _PACK["refreshes"] = int(_PACK.get("refreshes", 0)) + 1
        if not _PACK["ready"]:
            if not 1 <= int(slots) <= MAX_SLOTS:
                raise ValueError(f"slots {slots} outside 1..{MAX_SLOTS}")
            if reload_once is not None:
                for v in reload_vols or ():
                    reload_once(v)                    # ONE reload of each mounted volume, BEFORE the lockdown chmods it 0700
            rec = container_lockdown()
            man = ensure_pubdir(PUBDIR)
            ns = namespaces_ok()
            if not ns["ok"]:
                raise RuntimeError(f"packed isolation needs per-worker user/network/IPC namespaces: {ns}; refusing to run model workers")
            os.makedirs(PACK_DIR, mode=0o700, exist_ok=True)
            os.chown(PACK_DIR, 0, 0)
            os.chmod(PACK_DIR, 0o700)
            if stat.S_IMODE(os.stat(PACK_DIR).st_mode) & 0o077:
                raise RuntimeError(f"{PACK_DIR} is not private")
            _PACK.update(ready=True, slots=int(slots), free=list(range(1, int(slots) + 1)), busy=set(), record=rec, pubdir=man,
                         namespaces=ns, cond=threading.Condition(_PACK["lock"]), gen=int(gen), refreshes=0)
        elif int(slots) != _PACK["slots"]:
            raise RuntimeError(f"packed container started with {_PACK['slots']} slots, asked for {slots}")
        return _PACK


def _take_slot(timeout_s: float = 3600.0) -> int:
    with _PACK["cond"]:
        t_end = time.time() + timeout_s
        while not _PACK["free"]:
            if not _PACK["cond"].wait(timeout=max(0.1, t_end - time.time())) and time.time() > t_end:
                raise RuntimeError("no free slot in the packed container")
        s = _PACK["free"].pop(0)
        _PACK["busy"].add(s)
        return s


def _give_slot(s: int) -> None:
    with _PACK["cond"]:
        _PACK["busy"].discard(s)
        _PACK["free"].append(s)
        _PACK["free"].sort()
        _PACK["cond"].notify_all()                 # slot takers AND a newer generation's drain (pack_ready) may be waiting


def stale_refusal(missing: list[dict]) -> dict:
    """FRESHNESS in a WARM packed container: a staged input committed after the container's start-up reload is not visible here, and a
    reload now could hide files from the other slots' in-progress reads (P2's report: per-input reloads under concurrency hid files and
    broke the lockdown when they ran before it; a reload after the lockdown keeps its 0700, P1 probe, but the hidden-file window stays).
    So the container stops taking inputs (it drains and exits) and refuses this one; the orchestrator re-submits it (the host-gate refusal
    path), and a FRESH container's start-up reload sees the blob. No reload, no lockdown change, no waiting on the busy slots."""
    try:
        import modal.experimental as E
        E.stop_fetching_inputs()
    except Exception:  # noqa: BLE001, S110 - outside Modal, or an older client
        pass
    return {"__refused__": True, "stale_staging": [str(r.get("stage", ""))[:16] for r in missing]}


class PackInfraError(InfraFault):
    """An infrastructure failure of a packed job (its child driver was killed, e.g. out of memory): an InfraFault, so the container
    callable returns it as an infrastructure result and the orchestrator re-submits the input (before 2026-09-27 it was a RuntimeError,
    which the container callable turned into the job's own error result). A job's own (scientific) failure is a RESULT, never this."""


def run_iso_packed(p: dict, slots: int, *, reload_once=None) -> dict:
    """Container side of an iso job in a PACKED class (Modal input concurrency `slots`): takes a free slot and runs the job in a CHILD
    DRIVER (a fresh root process), which runs `run_iso_payload(p, slot)`. The payload and the result travel through root-only files; the
    child's command line holds no data. The volumes are reloaded ONCE, before the container lockdown (`pack_ready`); a packed job never
    reloads or commits (P2's report). Returns what `run_iso_payload` returns, or the same {"error", "traceback"} result an unpacked
    container returns for a failed job."""
    st = pack_ready(slots, reload_vols=p.get("reload") or ("fit",), reload_once=reload_once, gen=int(p.get("__gen") or 0))
    missing = [r for r in staged_input_refs(p) if not staged_visible(r)]
    if missing:
        return stale_refusal(missing)
    t0 = time.time()
    s = _take_slot()
    tag = uuid.uuid4().hex
    pf, of = Path(PACK_DIR) / f"in_{tag}.pkl", Path(PACK_DIR) / f"out_{tag}.pkl"
    try:
        fd = os.open(pf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            pickle.dump({"payload": p, "lock": {**{k: v for k, v in st["record"].items() if k in ("dumpable0", "private", "shared_tmp",
                                                                                                    "killed", "ipc_removed")},
                                                "world_writable_fixed": (st["record"].get("world_writable") or {}).get("n_fixed")}},
                        fh, protocol=pickle.HIGHEST_PROTOCOL)
        cmd = [sys.executable, "-B", "-c", SLOT_BOOT, "slot", "--slot", str(s), "--payload", str(pf), "--out", str(of)]
        env = dict(os.environ, PYTHONFAULTHANDLER="1", **{k: str(job_threads(p)) for k in THREAD_VARS})   # BLAS starts pinned
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)       # the class timeout bounds it, as for an unpacked job
        if r.returncode != 0 or not of.exists():
            raise PackInfraError(f"packed child driver of slot {s} exited {r.returncode} without a result: {r.stderr[-3000:]}")
        with open(of, "rb") as fh:
            out = pickle.load(fh)          # written by the trusted child driver (worker replies were safe-decoded there)
    finally:
        own = slot_uids(s)
        kill_uids(own)
        ipc_cleanup(own)
        for f in (pf, of):
            with contextlib.suppress(OSError):
                f.unlink()
        _give_slot(s)
    if isinstance(out, dict) and isinstance(out.get("iso"), dict):
        out["iso"]["pack"] = {"slots": int(slots), "slot": s, "child_wall_s": round(time.time() - t0, 2),
                              "namespaces": st["namespaces"].get("ok")}
    return out


SLOT_BOOT = "from brainir_causal.isolation import main; raise SystemExit(main())"


def _slot_main(slot: int, payload_path: str, out_path: str) -> int:
    """The CHILD DRIVER of a packed slot (root): nondumpable, reads its payload (root-only file, removed at once), runs the job with the
    slot's uids and writes the result (a failed job is written as the {"error", "traceback"} result an unpacked container returns)."""
    set_nondumpable()
    with open(payload_path, "rb") as fh:
        msg = pickle.load(fh)
    with contextlib.suppress(OSError):
        os.unlink(payload_path)
    _PACK_CHILD["lock"] = msg.get("lock") or {}
    try:
        out = run_iso_payload(msg["payload"], slot=int(slot))
    except Exception as e:  # noqa: BLE001 - a deterministic job error is a RESULT (as in p4modal.app's container callable)
        import traceback
        out = {"error": f"{type(e).__name__}: {e}"[:2000], "traceback": traceback.format_exc()[-6000:]}
    except InfraFault as e:     # an INFRASTRUCTURE fault: returned as such (the parent's container callable passes it on), never a result
        import traceback
        out = {"__infra__": True, "error": f"InfraFault ({type(e).__name__}): {e}"[:2000], "traceback": traceback.format_exc()[-4000:]}
    tmp = out_path + ".part"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, out_path)
    return 0


# ================================================================================================================ local transports
def local_transport(method_dir: Path | str | None, *, kind: str = "docker", work: Path | str | None = None, cpus: float = 2.0,
                    mem_gb: float = 6.0) -> tuple:
    """(transport, pubdir) for the development machine: 'docker' (the sandbox image; the default and the only kind tournaments use)
    or 'local-unsafe' (trusted models only). The public code directory is built under `work` (a temporary directory by default)."""
    work = Path(work) if work else Path(tempfile.mkdtemp(prefix="p4iso_"))
    pub = work / "pub"
    build_pubdir(pub)
    if kind == "docker":
        return DockerTransport(pubdir=pub, method_dir=method_dir, cpus=cpus, mem_gb=mem_gb), pub
    if kind == "local-unsafe":
        return LocalUnsafeTransport(pubdir=pub, method_dir=method_dir), pub
    raise ValueError(f"unknown local transport {kind!r}")


def main(argv=None) -> int:
    """python -m brainir_causal.isolation pubdir DEST | slot --slot S --payload FILE --out FILE (a packed container's child driver)"""
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("pubdir")
    pb.add_argument("dest")
    sl = sub.add_parser("slot")
    sl.add_argument("--slot", type=int, required=True)
    sl.add_argument("--payload", required=True)
    sl.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "pubdir":
        print(json.dumps(build_pubdir(args.dest), indent=1))
    elif args.cmd == "slot":
        return _slot_main(args.slot, args.payload, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
