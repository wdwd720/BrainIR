"""Run an orchestrator Modal driver inside a LINUX container on the local Docker VM (ORCHESTRATOR ONLY; research/LOG.md P4-D54).

Long Modal clients on the Windows host die of system-wide socket-buffer exhaustion ("OSError: [WinError 10055] ... lacked sufficient
buffer space"); sockets inside the Docker VM do not use the Windows buffers. This wrapper runs any driver script in the image
`brainir-p4-driver:1` (docker/p4driver: the phase4 lock's third-party environment, git, the docker CLI; nothing of the repository):

    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py build                       # image + docker/p4driver/image.json
    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py run   scripts/p4/<driver>.py [args...]    # foreground
    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py start scripts/p4/<driver>.py [args...]    # detached
    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py status | logs NAME [--tail N] | stop NAME
    common options (before the script): --extra-mount HOST_DIR (repeatable), --memory-gb 4, --cpus 4, --name NAME

The container gets:
- the repository, read-write, at the path the Docker Desktop daemon uses for the host path (C:\\Dev\\BrainIR ->
  /run/desktop/mnt/host/c/Dev/BrainIR), and that path is the working directory. A driver's ROOT (from its own __file__) is
  therefore a path the daemon understands, so nested `docker run -v` mounts a driver builds (e.g. build_on_modal.py planning in
  the pinned sandbox image) resolve correctly. /repo is a convenience link to it.
- the run-artefact root C:\\Dev\\BrainIR_p4run the same way, exported as P4_RUN_BASE (the variable levelc_lib reads) and
  P4_RUN_ROOT (drivers that still hard-code 'C:/Dev/BrainIR_p4run' must read one of them first: see WINDOWS_ONLY and
  needs_override());
- the Modal credentials READ-ONLY (the user's ~/.modal.toml at /root/.modal.toml; the wrapper never reads, prints or copies it);
- the Docker Desktop socket (/var/run/docker.sock), for drivers that start local containers;
- PYTHONIOENCODING=utf-8, PYTHONDONTWRITEBYTECODE=1, a memory cap (default 4 GB) and a CPU cap (default 4).
Arguments that are Windows paths under a mounted directory are translated; any other Windows path is refused (mount it with
--extra-mount). Detached runs write data/phase4/driver_runs/<name>/{run.json, log.txt, exit_code} (data/ is git-ignored).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "brainir-p4-driver:1"
IMAGE_DIR = ROOT / "docker" / "p4driver"
RECORD = IMAGE_DIR / "image.json"
RUNS = ROOT / "data" / "phase4" / "driver_runs"
RUN_ROOT_HOST = Path(r"C:\Dev\BrainIR_p4run")
MODAL_CONFIG = Path.home() / ".modal.toml"
#: drivers that cannot run in the Linux container (Windows-only tooling or host services), with the reason
WINDOWS_ONLY = {
    "scripts/p4/launch_clean_room.py": "builds NTFS-protected rooms and launches agents (Windows host tooling)",
    "scripts/p4/prefreeze_check.py": "spawns the Windows uv and the Windows-only host tests",
    "scripts/p4/devrun4.py": "the clean room's remote-runner daemon works on the Windows room paths",
    "scripts/p4/simservice_docker.py": "the simulation service's trusted host part runs on the Windows host beside the rooms",
    "scripts/make_phase4_cleanroom.py": "NTFS ACLs",
    "scripts/p4agent/launch.py": "agent launcher (Windows guard, rooms)",
    "scripts/p4agent/audit_transcripts.py": "replays the Windows guard",
}
_WIN_ROOT = re.compile(r"""["']C:[/\\]{1,2}Dev[/\\]{1,2}BrainIR_p4""")
#: rooms a driver may need (mounted only with --extra-mount); the wrapper then exports their container path under these names
ROOM_ENV = {"c:/dev/brainir_p4clean": "P4_ROOM_CLEAN", "c:/dev/brainir_p4review": "P4_ROOM_REVIEW", "c:/dev/brainir_p4bench": "P4_ROOM_BENCH"}


def daemon_path(p: Path | str) -> str:
    """The Docker Desktop daemon's path of a Windows host path: C:\\Dev\\BrainIR -> /run/desktop/mnt/host/c/Dev/BrainIR."""
    w = PureWindowsPath(str(p))
    if not w.drive or len(w.drive) != 2:
        raise ValueError(f"not a Windows drive path: {p}")
    rest = "/".join(w.parts[1:])
    return f"/run/desktop/mnt/host/{w.drive[0].lower()}/{rest}"


def needs_override(script: Path) -> str | None:
    """A reason when the script itself hard-codes a Windows run root without reading P4_RUN_ROOT (imported modules are covered by the
    image's sitecustomize guard, which refuses writes through a Windows path at run time)."""
    try:
        src = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if _WIN_ROOT.search(src) and not any(v in src for v in ("P4_RUN_ROOT", "P4_RUN_BASE")):
        return "hard-codes a C:/Dev/BrainIR_p4* root; read it from os.environ['P4_RUN_BASE'] (the name levelc_lib uses) first"
    return None


#: LOCAL execution (the user's directive of 2026-09-28: no further Modal spend; research/phase4/LOCAL_EXECUTION_PLAN.md): the three
#: Modal volumes as local directories, mounted at the containers' own paths, and the host's free-memory feed (scripts/p4/local_memfeed.sh)
LOCAL_VOL_HOST = RUN_ROOT_HOST / "vol"
LOCAL_MOUNTS = {"fit": "/fitvol", "eval": "/evalvol", "store": "/storevol"}
GUARD_DIR_HOST = LOCAL_VOL_HOST / "_guard"


def _local_mounts(vol_root: Path | None = None) -> list[str]:
    """The local volumes under vol_root (default LOCAL_VOL_HOST; a scratch root keeps a check's writes away from the real volumes)."""
    root = Path(vol_root) if vol_root else LOCAL_VOL_HOST
    args = []
    for vol, cont in LOCAL_MOUNTS.items():
        h = root / vol
        h.mkdir(parents=True, exist_ok=True)
        args += ["-v", f"{h}:{cont}:rw"]
    GUARD_DIR_HOST.mkdir(parents=True, exist_ok=True)
    return args + ["-v", f"{GUARD_DIR_HOST}:/p4guard:ro"]


def _mounts(extra: list[str], local: bool = False, vol_root: Path | None = None) -> tuple[list[str], dict[str, str]]:
    """docker -v arguments and the host -> container prefix map used to translate arguments. local: the local volumes and the memory
    feed instead of the Modal credentials (a local run can never start a Modal container)."""
    RUN_ROOT_HOST.mkdir(parents=True, exist_ok=True)
    pairs = [(ROOT, daemon_path(ROOT), "rw"), (RUN_ROOT_HOST, daemon_path(RUN_ROOT_HOST), "rw")]
    for e in extra:
        h = Path(e).resolve()
        if not h.is_dir():
            raise SystemExit(f"--extra-mount {e}: not a directory")
        pairs.append((h, daemon_path(h), "rw"))
    args, prefix = [], {}
    for host, cont, mode in pairs:
        args += ["-v", f"{host}:{cont}:{mode}"]
        prefix[str(host).replace("\\", "/").rstrip("/").lower()] = cont
    if local:
        return args + _local_mounts(vol_root) + ["-v", "/var/run/docker.sock:/var/run/docker.sock"], prefix
    if not MODAL_CONFIG.is_file():
        raise SystemExit(f"no Modal credentials at {MODAL_CONFIG} (the file is mounted read-only; its content is never read here)")
    args += ["-v", f"{MODAL_CONFIG}:/root/.modal.toml:ro", "-v", "/var/run/docker.sock:/var/run/docker.sock"]
    return args, prefix


def _translate(arg: str, prefix: dict[str, str]) -> str:
    """A Windows path argument under a mounted host directory -> its container path; any other Windows path is refused."""
    m = re.match(r"^(--[^=]+=)?([A-Za-z]:[\\/].*)$", arg)
    if not m:
        return arg
    head, p = m.group(1) or "", m.group(2).replace("\\", "/")
    low = p.lower()
    for host, cont in sorted(prefix.items(), key=lambda kv: -len(kv[0])):
        if low == host or low.startswith(host + "/"):
            return head + cont + p[len(host):]
    raise SystemExit(f"argument {arg!r} is a Windows path outside the mounted directories: pass a repository-relative path or "
                     "mount its directory with --extra-mount")


def _check_script(script: str) -> tuple[Path, str]:
    sp = (ROOT / script).resolve() if not Path(script).is_absolute() else Path(script).resolve()
    try:
        rel = sp.relative_to(ROOT).as_posix()
    except ValueError:
        raise SystemExit(f"{script}: the driver must live in the repository")
    if not sp.is_file():
        raise SystemExit(f"{script}: no such file")
    if rel in WINDOWS_ONLY:
        raise SystemExit(f"{rel} cannot run in the Linux driver container: {WINDOWS_ONLY[rel]}")
    why = needs_override(sp)
    if why:
        raise SystemExit(f"{rel} {why}; until then run it on the Windows host")
    return sp, rel


def docker_cmd(script: str, sargs: list[str], *, name: str, memory_gb: float, cpus: float, extra: list[str], detached_dir: str | None,
               local: bool = False, workers: int = 1, min_free_mb: int = 6144, kill_free_mb: int = 3072, vol_root: str | None = None):
    sp, rel = _check_script(script)
    mounts, prefix = _mounts(extra, local=local, vol_root=Path(vol_root) if vol_root else None)
    repo = daemon_path(ROOT)
    env = {"BRAINIR_REPO": repo, "P4_RUN_BASE": daemon_path(RUN_ROOT_HOST), "P4_RUN_ROOT": daemon_path(RUN_ROOT_HOST),
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "P4_LINUX_DRIVER": "1"}
    if local:
        sys.path.insert(0, str(ROOT / "phase4" / "src"))
        from brainir_causal.p4modal.images import CPU_PINS          # the reference platform's numerics pins (as in the Modal images)
        env.update({"P4_BACKEND": "local", "P4_LOCAL_VOLUMES": "1", "P4_LOCAL_WORKERS": str(int(workers)),
                    "P4_LOCAL_GUARD_FILE": "/p4guard/free_mb", "P4_LOCAL_MIN_FREE_MB": str(int(min_free_mb)),
                    "P4_LOCAL_KILL_FREE_MB": str(int(kill_free_mb)), **CPU_PINS})
    cmd = ["docker", "run", "--rm", "--init", "--name", name, "--memory", f"{memory_gb}g", "--cpus", str(cpus), "-w", repo]
    for host, var in ROOM_ENV.items():
        if host in prefix:
            env[var] = prefix[host]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += mounts + ["--label", "brainir.p4driver=1"] + (["--label", "brainir.p4local=1"] if local else []) + [IMAGE]
    inner = ["python", f"{repo}/{rel}"] + [_translate(a, prefix) for a in sargs]
    if detached_dir is None:
        return cmd + inner, rel
    # detached: the container's own shell writes the log and the exit code under the run directory
    shell = 'python "$@" > "$P4DRV_DIR/log.txt" 2>&1; echo $? > "$P4DRV_DIR/exit_code"'
    cmd[3:3] = ["-d"]
    idx = cmd.index(IMAGE)
    cmd[idx:idx] = ["-e", f"P4DRV_DIR={detached_dir}"]
    return cmd + ["sh", "-c", shell, "sh", f"{repo}/{rel}"] + [_translate(a, prefix) for a in sargs], rel


def _name(rel: str) -> str:
    return f"p4drv-{Path(rel).stem.replace('_', '-')}-{time.strftime('%Y%m%d%H%M%S')}"


# ------------------------------------------------------------------------------------------------ build
def cmd_build(args) -> int:
    ctx = Path(tempfile.mkdtemp(prefix="p4driver_ctx_", dir=str(ROOT / "data" / "phase4")))
    try:
        for f in ("Dockerfile", "sitecustomize.py", "entrypoint.sh"):
            b = (IMAGE_DIR / f).read_bytes().replace(b"\r\n", b"\n")      # LF inside the image (the shebang of the entrypoint)
            (ctx / f).write_bytes(b)
        (ctx / "build" / "phase4").mkdir(parents=True)
        for f in ("pyproject.toml", "uv.lock", ".python-version"):
            src = ROOT / "phase4" / f
            if src.exists():
                shutil.copyfile(src, ctx / "build" / "phase4" / f)
        t0 = time.time()
        r = subprocess.run(["docker", "build", "-t", IMAGE, str(ctx)], text=True)
        if r.returncode != 0:
            raise SystemExit(f"docker build failed (rc {r.returncode})")
    finally:
        shutil.rmtree(ctx, ignore_errors=True)
    iid = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], capture_output=True, text=True).stdout.strip()
    size = subprocess.run(["docker", "image", "inspect", "--format", "{{.Size}}", IMAGE], capture_output=True, text=True).stdout.strip()
    probe = subprocess.run(["docker", "run", "--rm", IMAGE, "python", "-c",
                            "import json, sys, numpy, scipy, pandas, modal, torch, sklearn; print(json.dumps({'python': sys.version.split()[0], "
                            "'numpy': numpy.__version__, 'scipy': scipy.__version__, 'pandas': pandas.__version__, 'modal': modal.__version__, "
                            "'torch': torch.__version__, 'scikit-learn': sklearn.__version__}))"],
                           capture_output=True, text=True)
    stack = json.loads(probe.stdout.strip().splitlines()[-1]) if probe.returncode == 0 else {"error": probe.stderr[-500:]}
    dv = subprocess.run(["docker", "run", "--rm", IMAGE, "docker", "--version"], capture_output=True, text=True).stdout.strip()
    rec = {"tag": IMAGE, "id": iid, "size_bytes": int(size or 0), "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "build_s": round(time.time() - t0, 1),
           "base": "python@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f",
           "docker_cli": {"from": "docker@sha256:862099ada15c669000bef53aa4cb9d821262829f45b0dda2159ccb276443043b", "version": dv},
           "uv": "0.12.18", "stack": stack,
           "notes": ("ORCHESTRATOR driver image, never an agent image. phase4/uv.lock synced with --frozen into /opt/p4venv, without the "
                     "three local packages (they come from the mounted repository) and without the CUDA stack (torch = the CPU build of "
                     "the locked version). No repository file or credential is baked; see scripts/p4/linux_driver.py.")}
    RECORD.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec, indent=1))
    return 0


# ------------------------------------------------------------------------------------------------ run / start / status
def _local_kw(args) -> dict:
    return {"local": bool(args.local), "workers": int(args.workers), "min_free_mb": int(args.min_free_mb), "kill_free_mb": int(args.kill_free_mb),
            "vol_root": args.vol_root or None}


def cmd_run(args) -> int:
    name = args.name or _name(args.script)
    cmd, rel = docker_cmd(args.script, args.args, name=name, memory_gb=args.memory_gb, cpus=args.cpus, extra=args.extra_mount,
                          detached_dir=None, **_local_kw(args))
    print(f"[linux_driver] {rel} in {IMAGE} as {name}" + (" (LOCAL backend)" if args.local else ""), flush=True)
    return subprocess.run(cmd).returncode


def cmd_start(args) -> int:
    name = args.name or _name(args.script)
    rd = RUNS / name
    rd.mkdir(parents=True, exist_ok=False)
    cmd, rel = docker_cmd(args.script, args.args, name=name, memory_gb=args.memory_gb, cpus=args.cpus, extra=args.extra_mount,
                          detached_dir=f"{daemon_path(ROOT)}/{rd.relative_to(ROOT).as_posix()}", **_local_kw(args))
    r = subprocess.run(cmd, capture_output=True, text=True)
    rec = {"name": name, "script": rel, "args": args.args, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "container_id": r.stdout.strip(), "rc_start": r.returncode, "stderr": r.stderr[-1000:], "image": IMAGE,
           "log": (rd / "log.txt").relative_to(ROOT).as_posix(), "exit_code_file": (rd / "exit_code").relative_to(ROOT).as_posix()}
    (rd / "run.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: rec[k] for k in ("name", "script", "rc_start", "log")}, indent=1))
    return 0 if r.returncode == 0 else 1


def cmd_status(args) -> int:
    ps = subprocess.run(["docker", "ps", "--filter", "label=brainir.p4driver=1", "--format", "{{.Names}}\t{{.Status}}"],
                        capture_output=True, text=True).stdout.strip().splitlines()
    running = {ln.split("\t")[0]: ln.split("\t")[1] for ln in ps if ln}
    for rd in sorted(RUNS.glob("p4drv-*")) if RUNS.exists() else []:
        rec = json.loads((rd / "run.json").read_text(encoding="utf-8")) if (rd / "run.json").exists() else {}
        ec = (rd / "exit_code").read_text().strip() if (rd / "exit_code").exists() else None
        state = running.get(rd.name) or (f"exited {ec}" if ec is not None else "not running (no exit code: killed or never started)")
        print(f"{rd.name}\t{rec.get('script', '?')}\t{state}")
    for n, s in running.items():
        if not (RUNS / n).exists():
            print(f"{n}\t(foreground)\t{s}")
    return 0


def cmd_logs(args) -> int:
    f = RUNS / args.name / "log.txt"
    if not f.exists():
        raise SystemExit(f"no log for {args.name}")
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    print("\n".join(lines[-args.tail:]))
    return 0


def cmd_stop(args) -> int:
    return subprocess.run(["docker", "stop", args.name]).returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    for nm in ("run", "start"):
        s = sub.add_parser(nm)
        s.add_argument("--extra-mount", action="append", default=[])
        s.add_argument("--memory-gb", type=float, default=4.0)
        s.add_argument("--cpus", type=float, default=4.0)
        s.add_argument("--name", default=None)
        s.add_argument("--local", action="store_true", help="LOCAL backend: local volumes, no Modal (LOCAL_EXECUTION_PLAN.md)")
        s.add_argument("--workers", type=int, default=1, help="local backend: payloads at once")
        s.add_argument("--min-free-mb", type=int, default=6144, help="local backend: start new work only above this host free memory")
        s.add_argument("--kill-free-mb", type=int, default=3072, help="local backend: stop the youngest job below this host free memory")
        s.add_argument("--vol-root", default="", help="local backend: host root of the local volumes (default C:/Dev/BrainIR_p4run/vol)")
        s.add_argument("script")
        s.add_argument("args", nargs=argparse.REMAINDER)
    sub.add_parser("status")
    lg = sub.add_parser("logs")
    lg.add_argument("name")
    lg.add_argument("--tail", type=int, default=40)
    st = sub.add_parser("stop")
    st.add_argument("name")
    args = ap.parse_args(argv)
    return {"build": cmd_build, "run": cmd_run, "start": cmd_start, "status": cmd_status, "logs": cmd_logs, "stop": cmd_stop}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
