"""Adversarial models in the Docker sandbox worker (research/phase4/EVAL_ARCHITECTURE.md; review F, F-B2 / F-B3). Each model's encode
tries to reach something it must not: the driver's memory / environ, held-out paths, the network, a subprocess, turning off the
tripwire, a thread whose target is exec, monkeypatching the harness, and returning an object that would run code if unpickled. Every
attempt must FAIL or be harmless; the worker still answers with a finite latent. Skipped when Docker or the sandbox image is absent.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import numpy as np
import pytest

from brainir_causal import isolation as I

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.slow


def _docker_ok() -> bool:
    exe = shutil.which("docker") or (r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
                                     if Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe").exists() else None)
    if not exe:
        return False
    try:
        img = I.sandbox_image()
        r = subprocess.run([exe, "image", "inspect", img], capture_output=True, timeout=60, check=False)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


requires_docker = pytest.mark.skipif(not _docker_ok(), reason="docker or the p4 sandbox image is unavailable")

# an adversarial method: each numbered branch is a distinct attack; encode returns a finite latent whatever happens, and records what
# it managed to do in a module-level dict the DRIVER never sees (only the latent crosses the safe codec).
ADVERSARY = textwrap.dedent("""
    import os, sys
    import numpy as np
    from brainir_causal.api import CausalStateMethod, CausalStateModel, register

    def _try(fn):
        try:
            fn(); return "DID"
        except Exception as e:
            return type(e).__name__

    def _attack():
        # every call runs on a FRESH copy of the model, so the attacks and their outcomes are gathered WITHIN one call (info) and
        # returned through the safe codec; they cannot accumulate across calls.
        L = {}
        L["read_evalvol"] = _try(lambda: os.listdir("/evalvol"))
        L["read_repo"] = _try(lambda: open("/repo/benchmarks/causal_state_v1/PROTOCOL.md").read())
        L["read_salt"] = _try(lambda: open("/data/phase4/hidden/salt.txt").read())
        # in the Docker sandbox the worker IS pid 1 (its own, scrubbed environ; there is no driver in the container). On the Modal
        # LinuxUid transport pid 1 is the root DRIVER and this is refused (test_isolation covers it there / the probe). Either way,
        # record the environ that is readable so the test can check it is scrubbed.
        try:
            L["own_environ"] = open(f"/proc/{os.getpid()}/environ", "rb").read().decode("utf-8", "replace")
        except Exception as e:
            L["own_environ"] = type(e).__name__
        L["read_driver_mem"] = _try(lambda: open("/proc/1/mem", "rb").read(8))
        L["read_jobs"] = _try(lambda: os.listdir("/opt/p4jobs"))
        L["net"] = _try(lambda: __import__("socket").create_connection(("1.1.1.1", 443), timeout=3))
        L["subprocess"] = _try(lambda: __import__("subprocess").run(["/bin/echo", "x"]))
        L["setuid0"] = _try(lambda: os.setuid(0))
        import brainir_causal.runguard as g
        L["has_TL"] = hasattr(g, "_TL")                    # no module-level flag to switch the tripwire off (F-B2)
        box = {}
        def th():                                          # a thread whose target is exec (the old eval-guard bypass)
            try:
                exec("import os; os.listdir('/evalvol')", {}); box["r"] = "DID"
            except Exception as e:
                box["r"] = type(e).__name__
        t = __import__("threading").Thread(target=th); t.start(); t.join()
        L["thread_exec"] = box.get("r")
        return L

    class Evil(CausalStateModel):
        def __init__(self):
            self.k = {"toy": 2}
        def encode(self, sid, x, u, dt):
            _attack()                                      # the attacks run here too (a fresh copy); the latent is still finite
            return np.array([1.0, 2.0])
        def rollout(self, sid, z0, u, events, dt):
            z = np.tile(np.asarray(z0, float), (len(u), 1)); return {"z": z, "y": z[:, :1]}
        def readout(self, sid, z, u):
            return np.atleast_2d(z)[:, :1]
        def info(self):
            return {"k": dict(self.k), "attack_log": _attack()}

    @register
    class EvilMethod(CausalStateMethod):
        name = "evil"
        def fit(self, data, *, systems, config=None, seed=0):
            return Evil()

    # a model whose reduce would run code if the driver ever unpickled its output
    class Pwn:
        def __reduce__(self):
            return (os.system, ("touch /repo/PWNED",))

    class Sneaky(CausalStateModel):
        def __init__(self):
            self.k = {"toy": 1}
        def encode(self, sid, x, u, dt):
            return Pwn()                                   # a non-array, non-encodable object as a "latent"
        def rollout(self, sid, z0, u, events, dt):
            return {"z": np.zeros((len(u), 1)), "y": np.zeros((len(u), 1))}
        def readout(self, sid, z, u):
            return np.zeros((1, 1))
        def info(self):
            return {"k": dict(self.k)}

    @register
    class SneakyMethod(CausalStateMethod):
        name = "sneaky"
        def fit(self, data, *, systems, config=None, seed=0):
            return Sneaky()
""")


@pytest.fixture(scope="module")
def dtr(tmp_path_factory):
    work = tmp_path_factory.mktemp("iso_docker")
    mdir = work / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "adv.py").write_text(ADVERSARY, encoding="utf-8")
    I.build_pubdir(work / "pub")
    return I.DockerTransport(pubdir=work / "pub", method_dir=mdir, cpus=2, mem_gb=4)


@requires_docker
def test_adversarial_encode_cannot_reach_anything(dtr):
    blob = I.fit_records(dtr, method="evil", records=[], systems={"toy": {}}, config={})["model"]
    rf = I.RemoteFresh(blob, dtr, threads=1)
    try:
        z = rf.encode("toy", np.zeros((4, 5)), np.zeros((4, 1)), 0.01)
        assert np.allclose(z, [1.0, 2.0])                 # the worker still answers with a finite latent
        # info() runs the attacks on a fresh copy and returns their outcomes through the safe codec
        log = (rf._call("info") or {}).get("attack_log") or {}
    finally:
        rf.close()
    assert log, "the adversary's info() should have returned its attack log"
    # nothing sensitive was reachable; every access failed (an OSError / PermissionError name, never "DID")
    for key in ("read_evalvol", "read_repo", "read_salt", "read_driver_mem", "read_jobs", "net", "subprocess", "setuid0", "thread_exec"):
        assert log.get(key) != "DID", (key, log.get(key))
    assert log.get("has_TL") is False                     # no module-level flag to switch the tripwire off (F-B2)
    assert log.get("thread_exec") not in ("DID", None)    # the thread's exec was refused too (process-wide tripwire)
    env = log.get("own_environ") or ""                    # the worker's own environment is scrubbed
    for bad in ("MODAL", "TOKEN", "SECRET", "CREDENTIAL", "AWS_", "ANTHROPIC", ".modal.toml"):
        assert bad not in env.upper(), (bad, env[:200])


@requires_docker
def test_unpicklable_output_never_reaches_the_driver(dtr):
    blob = I.fit_records(dtr, method="sneaky", records=[], systems={"toy": {}}, config={})["model"]
    rf = I.RemoteFresh(blob, dtr, threads=1)
    try:
        # the "latent" is an object whose __reduce__ would run os.system IF pickled+unpickled; the safe codec never pickles, so it
        # degrades the object to its repr. encode() then gets a dict, not a (k,) array, and fails in the driver's np.asarray. Either
        # way the driver never unpickles and os.system never runs.
        with pytest.raises((TypeError, ValueError, I.RemoteCallError)):
            rf.encode("toy", np.zeros((4, 5)), np.zeros((4, 1)), 0.01)
        raw = rf._call("readout", (("toy", np.zeros((1, 1)), np.zeros((1, 1)))))   # a well-formed call still works
        assert raw is not None
    finally:
        rf.close()
    assert not (ROOT / "PWNED").exists() and not Path("/repo/PWNED").exists()


@requires_docker
def test_worker_env_is_scrubbed(dtr):
    """The worker's environment carries no MODAL_* / credential variables and a minimal PATH / HOME."""
    blob = I.fit_records(dtr, method="evil", records=[], systems={"toy": {}}, config={})["model"]
    w = I.WorkerClient(dtr, "A", method_dir=dtr.method_dir_in_worker, threads=1)
    try:
        w.request("load_model", blob=blob)
        # a public API call that reports os.environ is not available; instead check the worker's own view via a benign encode and
        # the recorded platform uid (an unprivileged uid, not 0)
        assert w.init["platform"]["uid"] not in (0, None)
    finally:
        w.close()
