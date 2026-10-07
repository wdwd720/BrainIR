"""Modal smoke of the model-worker isolation (research/phase4/EVAL_ARCHITECTURE.md; review F, F-B2 / F-B3).

    uv run --project phase4 python scripts/p4/smoke_isolation_modal.py [--out research/phase4/isolation_smoke_modal.json]

One iso-image container (block_network=True) runs the trusted DRIVER as root: it locks the container down (`isolation.container_lockdown`),
builds the public-code directory, and for TWO scratch smoke methods (a package built here, never the repo's methods/) FITS each in an
unprivileged-uid model worker and runs a full RemoteFresh evaluation dance on hand-built toy inputs (encode / rollout / capacity / lift,
the A -> lift -> C phase transitions, and the refusals across phases). It also fits a small "real-mechanism-like" linear system with more
units, and runs an ADVERSARIAL method whose encode tries to read the eval volume, the driver's memory, the network and a subprocess and
whose "latent" is an object that would run code if unpickled. It reports the isolation record, per-method timings and the approximate
cost. This is self-contained (no volume-staged data): the full data path is exercised by the local Docker tests and the round driver.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SMOKE_PKG = {
    "__init__.py": "",
    "smoke_methods.py": '''
import numpy as np
from brainir_causal.api import CausalStateMethod, CausalStateModel, register

def _sys(seed, n):
    rng = np.random.default_rng(seed)
    A = np.array([[-0.8, 2.0], [-2.0, -0.8]]); b = np.array([1.0, 0.3])
    Q, _ = np.linalg.qr(rng.standard_normal((n, n))); M = Q * (1.0 + rng.random(n)); Minv = np.linalg.inv(M)
    G = np.array([[1.0, 0.0], [0.5, -1.0], [0.2, 0.7]])
    return {"A": A, "b": b, "Minv": Minv, "C": Minv[:2], "G": G, "n": n}

class Exact(CausalStateModel):
    def __init__(self, seed, n):
        self.p = _sys(seed, n); self.k = {"toy": 2}
    def encode(self, sid, x, u, dt):
        return self.p["C"] @ np.asarray(x, float)[-1]
    def rollout(self, sid, z0, u, events, dt):
        z = np.asarray(z0, float).copy(); U = np.asarray(u, float).reshape(len(u), -1); out = [z.copy()]
        for j in range(len(U) - 1):
            for e in events:
                if e["kind"] == "kick" and abs(e["t"] - j * dt) < dt / 2:
                    dx = np.zeros(self.p["n"])
                    for kk, v in e["delta"].items(): dx[int(kk)] += v
                    z = z + self.p["C"] @ dx
            z = z + dt * (self.p["A"] @ z + self.p["b"] * U[j, 0]); out.append(z.copy())
        Z = np.stack(out); return {"z": Z, "y": Z @ self.p["G"].T}
    def readout(self, sid, z, u):
        return np.atleast_2d(z) @ self.p["G"].T
    def supports(self, sid, kind):
        return kind == "kick"
    def lift(self, sid, x, u, dz, n=3, c=None):
        Cs = self.p["C"]; dx = np.linalg.pinv(Cs) @ np.asarray(dz, float)
        return [{"events": [{"kind": "kick", "t": 0.0, "delta": {str(i): float(v) for i, v in enumerate(dx)}}],
                 "predicted_dz": Cs @ dx, "cost": 1.0}]
    def info(self):
        return {"k": dict(self.k), "n_params": {"encoder": {"toy": self.p["C"].size}, "transition": 6, "readout": {"toy": self.p["G"].size}}}

@register
class SmokeSmall(CausalStateMethod):
    name = "smoke_small"
    def fit(self, data, *, systems, config=None, seed=0):
        return Exact(int(seed), 5)

@register
class SmokeBig(CausalStateMethod):
    name = "smoke_big"
    def fit(self, data, *, systems, config=None, seed=0):
        return Exact(int(seed) + 1, 40)   # a larger "real-mechanism-like" system

import os
def _t(fn):
    try:
        fn(); return "DID"
    except Exception as e:
        return type(e).__name__
class _Pwn:
    def __reduce__(self):
        return (os.system, ("touch /evalvol/PWNED",))
class Adv(CausalStateModel):
    def __init__(self):
        self.k = {"toy": 2}
    def encode(self, sid, x, u, dt):
        self._probe(); return np.array([1.0, 2.0])
    def _probe(self):
        ppid = os.getppid()                     # the DRIVER (the worker's parent, root, dumpable 0)
        self.attack = {"evalvol": _t(lambda: os.listdir("/evalvol")), "fitvol": _t(lambda: os.listdir("/fitvol")),
                       "storevol": _t(lambda: os.listdir("/storevol")), "repo": _t(lambda: os.listdir("/repo")),
                       "other_jobs": _t(lambda: os.listdir("/opt/p4jobs")),
                       "driver_environ": _t(lambda: open(f"/proc/{ppid}/environ", "rb").read(8)),
                       "driver_mem": _t(lambda: open(f"/proc/{ppid}/mem", "rb").read(8)),
                       "net": _t(lambda: __import__("socket").create_connection(("1.1.1.1", 443), timeout=3)),
                       "dns": _t(lambda: __import__("socket").getaddrinfo("example.com", 443)),
                       "write_tmp": _t(lambda: open("/tmp/x_worker", "w").write("x")),
                       "subprocess": _t(lambda: __import__("subprocess").run(["/bin/echo","x"], capture_output=True)),
                       "setuid0": _t(lambda: os.setuid(0)),
                       "env_modal": sorted(k for k in os.environ if k.upper().startswith("MODAL"))}
    def rollout(self, sid, z0, u, events, dt):
        z = np.tile(np.asarray(z0, float), (len(u), 1)); return {"z": z, "y": z[:, :1]}
    def readout(self, sid, z, u):
        return np.atleast_2d(z)[:, :1]
    def info(self):
        m = Adv(); m._probe(); return {"k": {"toy": 2}, "attack": m.attack}

@register
class AdvMethod(CausalStateMethod):
    name = "adv"
    def fit(self, data, *, systems, config=None, seed=0):
        return Adv()

class Sneaky(CausalStateModel):
    def __init__(self):
        self.k = {"toy": 1}
    def encode(self, sid, x, u, dt):
        return _Pwn()
    def rollout(self, sid, z0, u, events, dt):
        return {"z": np.zeros((len(u), 1)), "y": np.zeros((len(u), 1))}
    def readout(self, sid, z, u):
        return np.zeros((1, 1))
    def info(self):
        return {"k": {"toy": 1}}

@register
class SneakyMethod(CausalStateMethod):
    name = "sneaky"
    def fit(self, data, *, systems, config=None, seed=0):
        return Sneaky()
''',
}


def _container():
    """Runs as root inside the iso container: the full driver + worker dance for the scratch methods."""
    import os
    import tempfile
    import time as _time
    import numpy as np
    from brainir_causal import isolation as I

    rep = {"where": "modal (iso image, block_network=True)", "root_uid": os.getuid()}
    rep["mounts_before_lockdown"] = {p: {"exists": os.path.lexists(p), "is_symlink": os.path.islink(p), "real": os.path.realpath(p),
                                         "mode": (oct(os.stat(p).st_mode & 0o777) if os.path.exists(p) else None)}
                                     for p in ("/fitvol", "/evalvol", "/storevol")}
    rep["lockdown"] = {k: v for k, v in I.container_lockdown().items() if k in ("dumpable0", "private", "shared_tmp", "killed", "ipc_removed")}
    I.ensure_pubdir(I.PUBDIR)
    # the method snapshot goes through the SAME code path as run_iso_payload: a tar extracted by `extract_snapshot` into a per-job dir
    # under the 0711 jobs root (dirs 0755, files 0644); a root 0700 dir (e.g. tempfile.mkdtemp) is, correctly, unreadable to workers
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, src in {"__init__.py": "", **{k: v for k, v in SMOKE_PKG.items() if k != "__init__.py"}}.items():
            data = src.encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode = len(data), 0o644
            tf.addfile(ti, io.BytesIO(data))
    jobdir = Path("/opt/p4jobs") / f"j_smoke_{os.getpid()}"
    jobdir.mkdir(mode=0o711)
    os.chmod(jobdir, 0o711)
    mdir = str(I.extract_snapshot(buf.getvalue(), None, jobdir / "methods"))
    tr = I.LinuxUidTransport(pubdir=I.PUBDIR, jobs_root=str(jobdir), method_dir=mdir)
    rep["mkdtemp_dir_denied_as_expected"] = oct(os.stat(tempfile.mkdtemp(dir="/opt/p4jobs")).st_mode & 0o777)
    x = np.random.default_rng(0).standard_normal((60, 5)); u = np.zeros((60, 1))
    xb = np.random.default_rng(1).standard_normal((60, 40))

    def eval_dance(blob, xarr):
        rf = I.RemoteFresh(blob, tr, threads=1)
        d = {}
        try:
            d["encode_shape"] = list(np.shape(rf.encode("toy", xarr, u, 0.01)))
            d["capacity_reported"] = bool(rf.capacity(["toy"])["params"].get("reported"))
            rf.set_phase("lift")
            d["lift_ok"] = bool(rf.lift("toy", xarr, u, np.array([0.3, -0.2])))
            rf.encode("toy", xarr, u, 0.01)
            try:
                rf.lift("toy", xarr, u, np.array([0.1, 0.1])); d["lift_after_reveal"] = "ALLOWED"
            except PermissionError:
                d["lift_after_reveal"] = "refused"
            rf.set_phase("C")
            try:
                rf.rollout("toy", [1.0, 2.0], u[:5], [], 0.01); d["rollout_in_C"] = "ALLOWED"
            except PermissionError:
                d["rollout_in_C"] = "refused"
            d["isolation"] = {"transport": rf.record()["transport"], "phases": sorted(rf.record()["phases"])}
        finally:
            rf.close()
        return d

    for m, xarr in (("smoke_small", x), ("smoke_big", xb)):
        t0 = _time.time()
        out = I.fit_records(tr, method=m, records=[], systems={"toy": {}}, config={}, threads=2)
        t_fit = _time.time() - t0
        t1 = _time.time()
        dance = eval_dance(out["model"], xarr)
        rep[m] = {"fit_s": round(t_fit, 2), "eval_s": round(_time.time() - t1, 2), "model_bytes": len(out["model"]),
                  "fit_worker": out["worker"].get("where"), "fit_worker_tripwire_hits": (out["worker"].get("stats") or {}).get("tripwire_hits"),
                  **dance}

    # adversary (1): through RemoteFresh (tripwire ON) — the attacks fail; the worker still answers
    ab = I.fit_records(tr, method="adv", records=[], systems={"toy": {}})["model"]
    arf = I.RemoteFresh(ab, tr, threads=1)
    try:
        arf.encode("toy", x, u, 0.01)
        rep["adversary_with_tripwire"] = (arf._call("info") or {}).get("attack")
    finally:
        arf.close()
    # adversary (2): the tripwire OFF — only the OS boundary (uid, permissions, dumpable 0, no network) stands in the way
    w = I.WorkerClient(tr, "A", method_dir=tr.method_dir_in_worker, threads=1, tripwire=False)
    try:
        w.request("load_model", blob=ab)
        rep["adversary_os_only"] = (w.request("call", name="info", args=[], kwargs={}) or {}).get("attack")
    finally:
        w.close()
    # unpicklable output: the safe codec never unpickles, so nothing runs
    sb = I.fit_records(tr, method="sneaky", records=[], systems={"toy": {}})["model"]
    srf = I.RemoteFresh(sb, tr, threads=1)
    try:
        try:
            srf.encode("toy", x, u, 0.01); rep["sneaky_encode"] = "returned"
        except Exception as e:
            rep["sneaky_encode"] = f"refused: {type(e).__name__}"
    finally:
        srf.close()
    rep["pwned_created"] = os.path.exists("/evalvol/PWNED")
    return rep


def run_modal() -> dict:
    import modal
    from brainir_causal.p4modal import images
    app = modal.App("brainir-p4-iso-smoke")
    vols = {"/fitvol": modal.Volume.from_name("brainir-p4-fit", create_if_missing=True, version=2),
            "/evalvol": modal.Volume.from_name("brainir-p4-eval", create_if_missing=True, version=2),
            "/storevol": modal.Volume.from_name("brainir-p4-store", create_if_missing=True, version=2)}
    fn = app.function(image=images.iso_image(gpu=False), volumes=vols, block_network=True, serialized=True, timeout=1800,
                      cpu=4.0, memory=16384)(_container)
    t0 = time.time()
    with modal.enable_output(), app.run():
        res = fn.remote()
    res["wall_s"] = round(time.time() - t0, 1)
    from brainir_causal.p4modal.app import usd_per_s
    res["usd_approx"] = round(res["wall_s"] * (4.0 * 0.0000131 + 16.0 * 0.00000222), 4)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "research" / "phase4" / "isolation_smoke_modal.json"))
    args = ap.parse_args(argv)
    res = run_modal()
    Path(args.out).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
