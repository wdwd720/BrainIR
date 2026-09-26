"""The method sandbox (brainir_causal.runguard) and the sandboxed runner (brainir_causal.runner fit)."""

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


def test_fit_guard_refuses_outside_reads_processes_and_network(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "ok.txt").write_text("fine", encoding="utf-8")
    secret = ROOT / "benchmarks" / "causal_state_v1" / "PROTOCOL.md"
    code = f"""
        from brainir_causal.runguard import install_fit_guard
        install_fit_guard([r"{allowed}"])
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
    """
    p = _run(code, tmp_path)
    out = p.stdout
    assert "fine" in out, p.stderr
    assert "DENIED read" in out and "DENIED proc" in out and "DENIED net" in out, out + p.stderr


def test_eval_guard_restricts_method_frames_only(tmp_path):
    mdir = tmp_path / "methods"
    mdir.mkdir()
    (mdir / "evil.py").write_text(textwrap.dedent(f"""
        def read_secret():
            return open(r"{ROOT / 'benchmarks' / 'causal_state_v1' / 'PROTOCOL.md'}").read()[:10]
    """), encoding="utf-8")
    code = f"""
        import sys
        sys.path.insert(0, r"{mdir}")
        from brainir_causal.runguard import install_eval_guard
        install_eval_guard([r"{mdir}"], allowed=[r"{mdir}"])
        import evil
        print("evaluator can read:", len(open(r"{ROOT / 'benchmarks' / 'causal_state_v1' / 'PROTOCOL.md'}").read()) > 0)
        try:
            evil.read_secret()
            print("METHOD READ ALLOWED")
        except PermissionError:
            print("METHOD READ DENIED")
    """
    p = _run(code, tmp_path)
    assert "evaluator can read: True" in p.stdout and "METHOD READ DENIED" in p.stdout, p.stdout + p.stderr


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
