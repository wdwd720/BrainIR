"""Modal smoke of PACKED isolated containers (research/phase4/LEVEL_B_EXECUTION.md; review F). Several isolated jobs run AT ONCE in one
container, each in its own SLOT (a child driver with the slot's own uid block, group and per-worker user / network / IPC namespaces,
isolation.run_iso_packed). This test proves, on the real image and the real packed path, that concurrent slots are isolated from each
other and from the driver:

  uv run --no-sync --project phase4 python scripts/p4/smoke_pack_modal.py [--out research/phase4/pack_smoke_modal.json] [--slots 4]

One `iso_pack_eval` container runs `slots` ADVERSARIAL "call" jobs at once (`Backend.run_iso_packed`, target pack_probe_call:probe_call).
Each job's worker (unprivileged uid of its slot, in its own user / net / ipc namespaces):
  - writes a secret into its OWN slot job directory, then tries to read every OTHER slot's job directory (root:group 0710);
  - binds an ABSTRACT UNIX socket, a LOOPBACK TCP port and a SYSTEM V shared-memory segment at names SHARED by all slots, holds them for
    2 s (so slots overlap), and tries to CONNECT to those same names (a peer slot's, if the namespaces did not isolate them);
  - reads its own net / ipc namespace ids (the driver checks they differ from the host and between slots);
  - tries to read the child driver's /proc/<ppid>/environ and /proc/<ppid>/mem (dumpable 0), open a network connection, and read the
    repository and the eval volume.
Every cross-slot and cross-boundary attempt must FAIL; the job still returns a finite result. The driver collates the slots and asserts
the isolation, then prints a PASS / FAIL verdict. Run AFTER scripts/p4/smoke_isolation_modal.py (the single-container boundary).
"""

from __future__ import annotations

import argparse
import io
import json
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# the adversarial method, in its own scratch snapshot (never the repo's methods/). encode probes every channel and stashes the report on
# the model; info() returns it (the safe codec passes it as plain data). Each numbered block is a distinct attack.
ADVERSARY = '''
import numpy as np
from brainir_causal.api import CausalStateMethod, CausalStateModel, register

# the possible slot worker uids (isolation.role_uid("A", s) = 10001 + 20*s, s = 1..8) and their per-uid channel names: every slot BINDS
# its own name and tries to CONNECT to EVERY OTHER slot's name. A peer's name is reachable only if the two share a net / ipc namespace,
# so any success is a cross-slot leak (the shared-vs-namespaced positive control is scripts/p4 probe_ns2 of 2026-09-26).
SLOT_A_UIDS = [10001 + 20 * s for s in range(1, 9)]
def _abstract(uid): return "\\0p4slot_%d" % uid
def _port(uid): return 40000 + (uid - 10001)
def _shmkey(uid): return 0x70340000 + (uid - 10001)

def _t(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:80]}"}

def _probe():
        import os, socket, ctypes, time, glob
        uid = os.getuid()
        rep = {"uid": uid, "gid": os.getgid(), "pid": os.getpid(), "ppid": os.getppid()}
        srv_unix = socket.socket(socket.AF_UNIX)
        rep["bind_abstract"] = _t(lambda: (srv_unix.bind(_abstract(uid)), srv_unix.listen(1)) and "bound")
        srv_tcp = socket.socket(); srv_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rep["bind_tcp"] = _t(lambda: (srv_tcp.bind(("127.0.0.1", _port(uid))), srv_tcp.listen(1)) and "bound")
        libc = ctypes.CDLL(None, use_errno=True)
        rep["create_shm"] = _t(lambda: libc.shmget(_shmkey(uid), 4096, 0o1000 | 0o666))
        time.sleep(3.0)                              # let every peer slot bind its own name first
        def conn_unix(peer):
            s = socket.socket(socket.AF_UNIX); s.settimeout(1.0); s.connect(_abstract(peer)); s.close(); return "CONNECTED"
        def conn_tcp(peer):
            s = socket.socket(); s.settimeout(1.0); s.connect(("127.0.0.1", _port(peer))); s.close(); return "CONNECTED"
        def attach_shm(peer):
            other = libc.shmget(_shmkey(peer), 4096, 0)     # 0 flags: attach an EXISTING segment; a peer's exists only if the ipcns is shared
            if other < 0:
                raise OSError(ctypes.get_errno(), "shmget")
            return "ATTACHED"
        reach = {"abstract": {}, "tcp": {}, "shm": {}}
        for peer in SLOT_A_UIDS:
            if peer == uid:
                continue
            reach["abstract"][peer] = _t(lambda peer=peer: conn_unix(peer))
            reach["tcp"][peer] = _t(lambda peer=peer: conn_tcp(peer))
            reach["shm"][peer] = _t(lambda peer=peer: attach_shm(peer))
        rep["reach_peers"] = reach                  # any {"ok": True} here is a real cross-slot leak
        rep["net_ns"] = _t(lambda: os.readlink("/proc/self/ns/net"))
        rep["ipc_ns"] = _t(lambda: os.readlink("/proc/self/ns/ipc"))
        cwd = os.getcwd()
        open(os.path.join(cwd, "SECRET"), "w").write("secret of uid %d" % os.getuid())
        rep["own_secret"] = _t(lambda: open(os.path.join(cwd, "SECRET")).read())
        rep["jobs_root"] = _t(lambda: sorted(os.listdir("/opt/p4jobs")))
        my_job = os.path.realpath(os.path.dirname(cwd))
        sib = []
        for j in glob.glob("/opt/p4jobs/j_*"):
            if os.path.realpath(j) == my_job:
                continue
            sib.append({"dir": os.path.basename(j), "list": _t(lambda j=j: os.listdir(j)),
                        "read_secret": _t(lambda j=j: [open(f).read() for f in glob.glob(os.path.join(j, "**", "SECRET"), recursive=True)])})
        rep["siblings"] = sib
        ppid = os.getppid()
        rep["driver_environ"] = _t(lambda: open("/proc/%d/environ" % ppid, "rb").read(8))
        rep["driver_mem"] = _t(lambda: open("/proc/%d/mem" % ppid, "rb").read(8))
        # the network boundary is the worker's OWN empty net namespace (the packed classes are not block_network: the driver needs
        # Modal's >2 MiB data path). Every route out must fail.
        rep["net_connect_ip"] = _t(lambda: socket.create_connection(("1.1.1.1", 443), timeout=3) and "connected")
        rep["dns"] = _t(lambda: socket.getaddrinfo("modal.com", 443))
        rep["connect_own_container_ip"] = _t(lambda: socket.create_connection((socket.gethostbyname(socket.gethostname()), 22), timeout=2)
                                             and "connected")
        # the driver's network namespace: readable as a link, but setns into it must be refused (no CAP_SYS_ADMIN over it)
        def setns_driver():
            libc = ctypes.CDLL(None, use_errno=True)
            fd = os.open("/proc/%d/ns/net" % ppid, os.O_RDONLY)
            try:
                if libc.setns(fd, 0) != 0:
                    raise OSError(ctypes.get_errno(), "setns")
                return "ENTERED"
            finally:
                os.close(fd)
        rep["driver_ns_net_readlink"] = _t(lambda: os.readlink("/proc/%d/ns/net" % ppid))
        rep["setns_driver_net"] = _t(setns_driver)
        # a worker that makes its OWN new user + net namespace still has no connectivity (an empty netns has only a downed lo)
        def nested_unshare_connect():
            libc = ctypes.CDLL(None, use_errno=True)
            CLONE_NEWUSER, CLONE_NEWNET = 0x10000000, 0x40000000
            if libc.unshare(CLONE_NEWUSER | CLONE_NEWNET) != 0:
                raise OSError(ctypes.get_errno(), "unshare")
            return socket.create_connection(("1.1.1.1", 443), timeout=2) and "connected"
        rep["nested_unshare_then_connect"] = _t(nested_unshare_connect)
        rep["read_repo"] = _t(lambda: os.listdir("/repo"))
        rep["read_evalvol"] = _t(lambda: os.listdir("/evalvol"))
        rep["read_modal_toml"] = _t(lambda: [open(p).read(16) for p in ("/root/.modal.toml", os.path.expanduser("~/.modal.toml"))
                                             if os.path.exists(p)] or "absent")
        toks = []
        for d in ("/root", "/opt/p4jobs", "/tmp", os.getcwd(), "/"):
            toks += _t(lambda d=d: [f for f in os.listdir(d) if "token" in f.lower() or f.endswith(".toml")]).get("value", []) or []
        rep["token_files_found"] = toks
        rep["modal_env"] = sorted(k for k in os.environ if k.upper().startswith("MODAL") or "TOKEN" in k.upper() or k.startswith("P4_"))
        srv_unix.close(); srv_tcp.close()
        return rep

class PackProbe(CausalStateModel):
    def __init__(self):
        self.k = {"toy": 1}
    def encode(self, sid, x, u, dt):
        self._report = _probe()                      # a fresh probe on every call (the OS boundary is the same each time)
        return np.array([float(self._report["uid"])])
    def rollout(self, sid, z0, u, events, dt):
        z = np.tile(np.asarray(z0, float), (len(u), 1)); return {"z": z, "y": z[:, :1]}
    def readout(self, sid, z, u):
        return np.atleast_2d(z)[:, :1]
    def info(self):
        return {"k": {"toy": 1}, "report": _probe()}   # info() itself probes (used by the tripwire-off driver call)

@register
class PackProbeMethod(CausalStateMethod):
    name = "pack_probe"
    def fit(self, data, *, systems, config=None, seed=0):
        return PackProbe()
'''


def _tar(pkg: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, src in pkg.items():
            data = src.encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode = len(data), 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def verdict(reports: list[dict], slots: int) -> dict:
    """PASS iff every slot is fully isolated: distinct uids and net / ipc namespaces, no peer socket / port / shm reachable, no sibling
    job directory readable, no driver memory, no network, no repo / eval volume, no MODAL_* in the environment."""
    ok = True
    reasons = []
    uids, nets, ipcs = set(), set(), set()
    for r in reports:
        wr = (r or {}).get("worker_report") or {}
        if not wr:
            ok = False
            reasons.append(f"slot with no worker report: {str(r)[:200]}")
            continue
        uids.add(wr.get("uid"))
        nets.add((wr.get("net_ns") or {}).get("value"))
        ipcs.add((wr.get("ipc_ns") or {}).get("value"))
        for ch, peers in (wr.get("reach_peers") or {}).items():
            for peer, res in peers.items():
                if isinstance(res, dict) and res.get("ok"):
                    ok = False
                    reasons.append(f"uid {wr.get('uid')} reached peer {peer} via {ch}: {res}")
        for ch in ("driver_environ", "driver_mem", "net_connect_ip", "dns", "connect_own_container_ip", "setns_driver_net",
                   "nested_unshare_then_connect", "read_repo", "read_evalvol"):
            if (wr.get(ch) or {}).get("ok"):
                ok = False
                reasons.append(f"uid {wr.get('uid')} broke {ch}: {wr[ch]}")
        rm = wr.get("read_modal_toml") or {}
        if rm.get("ok") and rm.get("value") != "absent":
            ok = False
            reasons.append(f"uid {wr.get('uid')} read a modal.toml: {rm}")
        if wr.get("token_files_found"):
            ok = False
            reasons.append(f"uid {wr.get('uid')} found token files: {wr['token_files_found']}")
        for sib in wr.get("siblings") or []:
            if sib["list"].get("ok") or sib["read_secret"].get("ok"):
                ok = False
                reasons.append(f"uid {wr.get('uid')} read sibling {sib['dir']}: {sib['list']} {sib['read_secret']}")
        if wr.get("modal_env"):
            ok = False
            reasons.append(f"uid {wr.get('uid')} sees MODAL_* env: {wr['modal_env']}")
        if not (wr.get("own_secret") or {}).get("ok"):
            ok = False
            reasons.append(f"uid {wr.get('uid')} could not use its own directory: {wr.get('own_secret')}")
    if len([u for u in uids if u is not None]) < min(slots, len(reports)):
        ok = False
        reasons.append(f"slots did not all get distinct uids: {sorted(uids)}")
    if len([n for n in nets if n]) < min(slots, len(reports)) or len([i for i in ipcs if i]) < min(slots, len(reports)):
        ok = False
        reasons.append(f"slots did not all get distinct net / ipc namespaces: net {sorted(nets)} ipc {sorted(ipcs)}")
    return {"pass": ok, "reasons": reasons, "uids": sorted(u for u in uids if u is not None),
            "net_ns": sorted(n for n in nets if n), "ipc_ns": sorted(i for i in ipcs if i)}


BIG = 3 * 1024 * 1024          # above Modal's 2 MiB inline limit: travels through its blob store (needs the container network)


def run_modal(slots: int) -> dict:
    import hashlib
    import os
    from brainir_causal.p4modal.app import Backend
    tar = _tar({"__init__.py": "", "pack_probe.py": ADVERSARY})
    pad = os.urandom(BIG)
    payloads = [{"role": "call", "target": "pack_probe_call:probe_call", "job": {"slot_hint": i, "pad": pad, "big_out": BIG},
                 "method_tar": tar, "reload": ["fit"]} for i in range(slots)]
    pad_sha = hashlib.sha256(pad).hexdigest()
    # bake ONLY the trusted call script, from a private snapshot (other forks edit scripts/p4 constantly; a file changing during the
    # image build aborts it). An absolute path replaces the repository-relative join in images.iso_image.
    import shutil
    import tempfile
    snap = Path(tempfile.mkdtemp(prefix="p4packsmoke_"))
    shutil.copy2(ROOT / "scripts" / "p4" / "pack_probe_call.py", snap / "pack_probe_call.py")
    t0 = time.time()
    with Backend(classes=["iso_pack_eval"], extra_dirs={str(snap): "/repo/scripts/p4"}, app_name="brainir-p4-pack-smoke") as be:
        res = be.run_iso_packed(payloads, "iso_pack_eval", expected_s=[1.0] * slots, label="pack-smoke")
    reports = [(r.get("result") if isinstance(r, dict) else {"error": repr(r)[:300]}) for r in res]
    iso = [(r.get("iso") if isinstance(r, dict) else None) for r in res]
    raw = [({k: (str(v)[:1500] if k in ("error", "traceback") else v) for k, v in r.items() if k != "result"}
            if isinstance(r, dict) else {"nondict": repr(r)[:300]}) for r in res]
    v = verdict(reports, slots)
    big = [{"pad_ok": (r or {}).get("pad_sha") == pad_sha and (r or {}).get("pad_len") == BIG,
            "big_out_ok": isinstance((r or {}).get("big_out"), (bytes, bytearray)) and len(r["big_out"]) == BIG} for r in reports]
    if not all(b["pad_ok"] and b["big_out_ok"] for b in big):
        v["pass"] = False
        v["reasons"].append(f"the >2 MiB data path failed: {big}")
    for r in reports:                                  # keep the JSON small
        if isinstance(r, dict):
            r.pop("big_out", None)
    out = {"slots": slots, "wall_s": round(time.time() - t0, 1), "verdict": v, "large_data_path": big,
           "packs": [((i or {}).get("pack") if isinstance(i, dict) else None) for i in iso], "reports": reports, "raw": raw,
           "cost": be.cost_summary() if hasattr(be, "cost_summary") else None}
    return out


def run_stress(n_jobs: int, cls: str) -> dict:
    """Reproduce P2's failure and show it fixed (2026-09-26): many concurrent inputs on a packed class, with a FRESH method tar uploaded
    MID-RUN. Before the volume-reload fix, per-input reloads remounted /fitvol to 0755 (lockdown failed closed) and hid the tar
    (FileNotFoundError). Now the container reloads ONCE before the lockdown, so every describe job succeeds. Returns the counts."""
    import tempfile
    import threading
    from brainir_causal.p4modal.app import Backend

    def _pkg_dir(tag):
        d = Path(tempfile.mkdtemp(prefix=f"p4stress_{tag}_"))
        (d / "__init__.py").write_text("", encoding="utf-8")
        (d / "pack_probe.py").write_text(ADVERSARY, encoding="utf-8")
        return d

    t0 = time.time()
    lockdown_fail = tar_missing = other_err = ok = 0
    with Backend(classes=[cls], app_name="brainir-p4-pack-stress") as be:   # no extra_dirs: describe does not use the "call" role
        key = be.methods_key(_pkg_dir("main"))       # the method tar the describe jobs read from /fitvol/methods/<key>.tar
        payloads = [{"role": "describe", "job": {"method": "pack_probe"}, "methods_key": key, "reload": ["fit"]} for _ in range(n_jobs)]

        # a FRESH upload mid-run: a distinct method tar pushed to the fit volume while the packed jobs are in flight (this is what
        # remounted /fitvol under the old per-input reload; with the fix the in-flight jobs never re-read the volume, so it is harmless)
        def fresh_upload():
            time.sleep(8)
            for _ in range(3):
                be.methods_key(_pkg_dir(f"fresh_{uuid.uuid4().hex[:6]}"))
                time.sleep(2)
        up = threading.Thread(target=fresh_upload, daemon=True)
        up.start()
        res = be.run_iso_packed(payloads, cls, expected_s=[1.0] * n_jobs, label="pack-stress")
        up.join(timeout=1)
        for r in res:
            if not isinstance(r, dict):
                other_err += 1
                continue
            err = str(r.get("error") or "")
            if "container lockdown failed" in err:
                lockdown_fail += 1
            elif "methods" in err and ("FileNotFound" in err or "No such file" in err):
                tar_missing += 1
            elif r.get("error"):
                other_err += 1
            elif (r.get("describe") or {}).get("name") == "pack_probe":
                ok += 1
            else:
                other_err += 1
        cost = be.cost_summary()
    return {"class": cls, "n_jobs": n_jobs, "ok": ok, "lockdown_failures": lockdown_fail, "tar_missing": tar_missing,
            "other_errors": other_err, "wall_s": round(time.time() - t0, 1), "cost": cost,
            "pass": bool(lockdown_fail == 0 and tar_missing == 0 and ok == n_jobs)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "research" / "phase4" / "pack_smoke_modal.json"))
    ap.add_argument("--mode", choices=("isolation", "stress"), default="isolation")
    ap.add_argument("--slots", type=int, default=4)
    ap.add_argument("--n-jobs", type=int, default=64, help="stress mode: concurrent inputs")
    ap.add_argument("--cls", default="iso_pack_fit", help="stress mode: the packed class")
    args = ap.parse_args(argv)
    if args.mode == "stress":
        res = run_stress(args.n_jobs, args.cls)
        Path(args.out).write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({k: res[k] for k in ("class", "n_jobs", "ok", "lockdown_failures", "tar_missing", "other_errors",
                                              "wall_s", "pass")}, indent=1))
        return 0 if res["pass"] else 1
    res = run_modal(args.slots)
    Path(args.out).write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res["verdict"], indent=1))
    print("wall_s", res["wall_s"], "packs", res["packs"])
    return 0 if res["verdict"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
