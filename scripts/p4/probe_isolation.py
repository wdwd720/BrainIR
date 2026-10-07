"""Probe the container-level isolation primitives the model-worker architecture relies on (research/phase4/EVAL_ARCHITECTURE.md).

    uv run --project phase4 python scripts/p4/probe_isolation.py [--out research/phase4/isolation_probe.json]

Runs ONE Modal container (block_network=True) that, as root, writes root-only files, mounts a scratch volume read-write (chmod 0700)
and read-only, sets PR_SET_DUMPABLE 0, then starts a child process as an unprivileged uid (setgid / setgroups / setuid in preexec)
with a scrubbed environment and records which accesses the child gets: the volume mounts, root-only files, /repo, /proc/<parent>/mem,
/proc/<parent>/environ, sockets (DNS, TCP, the Modal API through the client), process creation, and the MODAL_* variables. The same
probe runs locally in the Docker sandbox image (--docker) to check the development-machine path. Nothing here runs method code.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_P = Path(__file__).resolve().parents
ROOT = _P[2] if len(_P) > 2 else _P[-1]

CHILD = r'''
import json, os, socket, subprocess, sys
res = {"uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups(), "env_keys": sorted(os.environ),
       "modal_env": sorted(k for k in os.environ if k.upper().startswith("MODAL"))}
ppid = int(sys.argv[1])
def tryit(name, fn):
    try:
        v = fn()
        res[name] = "OK" + (": " + str(v)[:120] if v is not None else "")
    except Exception as e:
        res[name] = "DENIED " + type(e).__name__ + ": " + str(e)[:120]
for p in sys.argv[2:]:
    tryit("listdir " + p, lambda p=p: os.listdir(p)[:5])
    tryit("read " + p + "/secret.txt", lambda p=p: open(os.path.join(p, "secret.txt")).read())
tryit("read /proc/ppid/mem", lambda: open(f"/proc/{ppid}/mem", "rb").read(8))
tryit("read /proc/ppid/environ", lambda: open(f"/proc/{ppid}/environ", "rb").read(80))
tryit("read /proc/ppid/cmdline", lambda: open(f"/proc/{ppid}/cmdline", "rb").read(80))
tryit("read /proc/ppid/maps", lambda: open(f"/proc/{ppid}/maps").read(80))
tryit("dns", lambda: socket.getaddrinfo("example.com", 443))
def tcp():
    s = socket.create_connection(("1.1.1.1", 443), timeout=5); s.close(); return "connected"
tryit("tcp 1.1.1.1:443", tcp)
tryit("subprocess", lambda: subprocess.run(["/bin/echo", "hi"], capture_output=True, timeout=10).stdout)
def modal_api():
    import modal
    return [e.path for e in modal.Volume.from_name("brainir-p4-probe").listdir("/")][:3]
tryit("modal api", modal_api)
tryit("write /tmp", lambda: open("/tmp/child_probe.txt", "w").write("x"))
tryit("write cwd", lambda: open("child_cwd.txt", "w").write("x"))
tryit("setuid 0", lambda: os.setuid(0))
print(json.dumps(res))
'''


def container_probe(ro_path: str, rw_path: str) -> dict:
    """Runs inside the container as root."""
    import ctypes
    import os
    import pwd  # noqa: F401
    import subprocess
    out = {"host_uid": os.getuid(), "modal_env_in_parent": sorted(k for k in os.environ if k.upper().startswith("MODAL"))}
    # root-only files
    os.makedirs("/rootonly", exist_ok=True)
    with open("/rootonly/secret.txt", "w") as fh:
        fh.write("root secret")
    os.chmod("/rootonly/secret.txt", 0o600)
    os.chmod("/rootonly", 0o700)
    # volume mounts
    for p in (rw_path, ro_path):
        try:
            if p == rw_path:
                with open(os.path.join(p, "secret.txt"), "w") as fh:
                    fh.write("volume secret")
                os.chmod(os.path.join(p, "secret.txt"), 0o600)
            os.chmod(p, 0o700)
            out[f"chmod {p}"] = oct(os.stat(p).st_mode & 0o777)
        except Exception as e:  # noqa: BLE001
            out[f"chmod {p}"] = f"FAILED {type(e).__name__}: {e}"[:200]
    # /repo (image files)
    out["repo_exists"] = os.path.isdir("/repo")
    try:
        libc = ctypes.CDLL(None)
        out["prctl_dumpable0"] = libc.prctl(4, 0, 0, 0, 0)          # PR_SET_DUMPABLE = 4
    except Exception as e:  # noqa: BLE001
        out["prctl_dumpable0"] = f"FAILED {e}"
    job = "/job"
    os.makedirs(job, exist_ok=True)
    os.chown(job, 10001, 10001)

    def drop():
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)

    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": job, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    t0 = time.time()
    r = subprocess.run([sys.executable, "-I", "-c", CHILD, str(os.getpid()), rw_path, ro_path, "/rootonly", "/repo", "/root"],
                       capture_output=True, text=True, cwd=job, env=env, preexec_fn=drop, timeout=120)
    out["child_wall_s"] = round(time.time() - t0, 2)
    out["child_rc"] = r.returncode
    out["child_stderr"] = r.stderr[-1500:]
    try:
        out["child"] = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        out["child_stdout"] = r.stdout[-1500:]
    return out


def run_modal(out_path: Path) -> dict:
    import modal
    import io
    app = modal.App("brainir-p4-isoprobe")
    vol = modal.Volume.from_name("brainir-p4-probe", create_if_missing=True, version=2)
    vol2 = modal.Volume.from_name("brainir-p4-probe2", create_if_missing=True, version=2)
    with vol2.batch_upload(force=True) as b:                     # a pre-existing file for the read-only mount
        b.put_file(io.BytesIO(b"read-only volume secret"), "/secret.txt")
    img = modal.Image.debian_slim(python_version="3.12").pip_install("modal==1.5.5").add_local_file(
        __file__, "/probe/probe_isolation.py", copy=True)

    def fn():
        import sys as _s
        _s.path.insert(0, "/probe")
        import probe_isolation as P
        return P.container_probe("/probe_ro", "/probe_rw")

    f = app.function(image=img, volumes={"/probe_rw": vol, "/probe_ro": vol2.with_mount_options(read_only=True)},
                     block_network=True, serialized=True, timeout=600, cpu=1.0, memory=2048)(fn)
    t0 = time.time()
    with modal.enable_output(), app.run():
        res = f.remote()
    res["wall_s"] = round(time.time() - t0, 1)
    res["where"] = "modal (block_network=True)"
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "research" / "phase4" / "isolation_probe_modal.json"))
    args = ap.parse_args(argv)
    res = run_modal(Path(args.out))
    Path(args.out).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
