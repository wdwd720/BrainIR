"""The in-process TRIPWIRE (brainir_causal.runguard) and the sandboxed runner (brainir_causal.runner fit). The tripwire is a
best-effort early failure, NOT the isolation boundary: the boundary is the model-worker architecture, tested in
test_worker_codec.py / test_isolation_local.py / test_eval_isolation_docker.py (research/phase4/EVAL_ARCHITECTURE.md)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run(code: str, tmp: Path) -> subprocess.CompletedProcess:
    script = tmp / "probe.py"
    script.write_text(textwrap.dedent(code), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, timeout=120, check=False)


def test_tripwire_refuses_outside_reads_processes_and_network(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "ok.txt").write_text("fine", encoding="utf-8")
    secret = ROOT / "benchmarks" / "causal_state_v1" / "PROTOCOL.md"
    code = f"""
        from brainir_causal.runguard import install_tripwire
        tw = install_tripwire([r"{allowed}"])
        print(open(r"{allowed / 'ok.txt'}").read())
        for what, fn in (("read", lambda: open(r"{secret}").read()),
                         ("proc", lambda: __import__("subprocess").run(["cmd", "/c", "echo", "x"])),
                         ("net", lambda: __import__("socket").create_connection(("127.0.0.1", 9)))):
            try:
                fn()
                print("ALLOWED", what)
            except PermissionError as e:
                print("DENIED", what)
            except OSError as e:
                print("OSERROR", what, type(e).__name__)
        print("HITS", len(tw.hits))
    """
    p = _run(code, tmp_path)
    out = p.stdout
    assert "fine" in out, p.stderr
    assert "DENIED read" in out and "DENIED proc" in out and "DENIED net" in out, out + p.stderr


def test_tripwire_state_is_not_a_module_attribute(tmp_path):
    """review F, F-B2: the old guard had a module-level re-entrancy flag that method code could set to switch it off. The tripwire
    keeps its state in a closure, so there is nothing to assign; a thread whose target is exec is covered too (process-wide hook)."""
    secret = ROOT / "benchmarks" / "causal_state_v1" / "PROTOCOL.md"
    code = f"""
        import threading
        import brainir_causal.runguard as g
        g.install_tripwire([r"{tmp_path}"])
        # no module attribute switches it off
        assert not hasattr(g, "_TL"), "runguard still exposes a module-level re-entrancy flag"
        try:
            open(r"{secret}").read()
            print("DIRECT ALLOWED")
        except PermissionError:
            print("DIRECT DENIED")
        box = {{}}
        src = "open(r'{str(secret).replace(chr(92), '/')}').read()"
        def run():
            try:
                exec(compile(src, "<gen>", "exec"), {{}})
                box["r"] = "THREAD ALLOWED"
            except PermissionError:
                box["r"] = "THREAD DENIED"
            except Exception as e:
                box["r"] = "THREAD " + type(e).__name__
        t = threading.Thread(target=run)
        t.start(); t.join()
        print(box["r"])
    """
    p = _run(code, tmp_path)
    assert "DIRECT DENIED" in p.stdout and "THREAD DENIED" in p.stdout, p.stdout + p.stderr


def test_retired_eval_guard_refuses():
    from brainir_causal.runguard import install_eval_guard
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        install_eval_guard(["x"], allowed=["x"])


@pytest.mark.slow
def test_runner_fits_a_method_in_the_sandbox(tmp_path):
    from brainir_causal import suites as S
    from brainir_causal.data import Trajectory
    from brainir_causal.synthadapter import suite_systems
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    ctx = S.SimContext(ints[sid], store_root=tmp_path / "store", synthetic_system=suite_systems("toy", S.DEV_SEED)[sid])
    samp = S.FamilySampler(pubs[sid], __import__("numpy").random.default_rng(0), S.seed_counter(False, "rt"), targets=pubs[sid]["targets_public"])
    w = S.SetWriter(tmp_path / "data" / "sys", sid, pubs[sid], "test")
    for _ in range(2):
        q = samp.obs("obs.stim")
        r = ctx.run(q)
        w.add(Trajectory(key=r["key"], system_id=sid, split="train", family="obs.stim", protocol=q, t=r["t"], x=r["x"], u=r["u"], y=r["y"],
                         meta={"role": "d0"}))
    w.close()
    mdir = tmp_path / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "toy_mean.py").write_text(textwrap.dedent("""
        import numpy as np
        from brainir_causal.api import CausalStateMethod, CausalStateModel, register

        class M(CausalStateModel):
            def __init__(self, mean):
                self.k, self.mean = {}, mean
            def encode(self, sid, x, u, dt):
                return np.zeros(1)
            def rollout(self, sid, z0, u, events, dt):
                return {"z": np.zeros((len(u), 1)), "y": np.tile(self.mean, (len(u), 1))}
            def readout(self, sid, z, u):
                return np.tile(self.mean, (len(np.atleast_2d(z)), 1))

        @register
        class ToyMean(CausalStateMethod):
            name = "toy_mean"
            def fit(self, data, *, systems, config=None, seed=0):
                return M(np.concatenate([r.y for r in data]).mean(0))
    """), encoding="utf-8")
    out = tmp_path / "fits" / "m.pkl"
    p = subprocess.run([sys.executable, "-m", "brainir_causal.runner", "fit", "--method-dir", str(mdir), "--method", "toy_mean", "--data",
                        str(tmp_path / "data"), "--systems", sid, "--out", str(out)], capture_output=True, text=True, timeout=300, check=False,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert p.returncode == 0, p.stderr[-3000:]
    side = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert side["n_train"] == 2 and side["method"] == "toy_mean" and out.exists()
