"""Pre-imports before the guards (ctypes library loading is refused afterwards) and the Modal build adapter's job mapping."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import numpy as np

from brainir_causal import protocol as P
from brainir_causal import runguard as RG
from brainir_causal import suites as S


def test_method_import_scan(tmp_path):
    (tmp_path / "a.py").write_text("import numpy as np\nfrom scipy.linalg import svd\nfrom . import b\nimport b\nfrom brainir_causal.api import register\n",
                                   encoding="utf-8")
    (tmp_path / "b.py").write_text("import sklearn.linear_model\n", encoding="utf-8")
    mods = RG._method_imports(tmp_path)
    assert "numpy" in mods and "scipy.linalg" in mods and "sklearn.linear_model" in mods
    assert "b" not in mods and not any(m.startswith("brainir_causal") for m in mods)


def test_stack_works_under_the_fit_guard_after_preimport(tmp_path):
    code = textwrap.dedent(f"""
        from brainir_causal.runguard import install_fit_guard, preimport
        info = preimport(None)
        install_fit_guard([r"{tmp_path}"])
        import numpy as np, scipy.linalg, scipy.special
        from sklearn.linear_model import Ridge
        import torch
        X = np.random.default_rng(0).standard_normal((50, 3))
        Ridge().fit(X, X[:, 0])
        scipy.linalg.svd(X)
        torch.nn.Linear(3, 2)(torch.zeros(1, 3))
        print("STACK OK", len(info["imported"]))
    """)
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300, check=False,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert "STACK OK" in p.stdout, p.stderr[-3000:]


class _FakeBackend:
    """Stands in for p4modal.app.Backend.simulate: observed arrays, the local store key, noise-free readouts for noise-free protocols."""

    def __init__(self, internals):
        self.internals = internals
        self.calls = []

    def simulate(self, items, *, mode, store, batch, cls=None):
        from brainir.sim.model import MODEL_ID

        from brainir_causal.realsim import ENGINE_VERSION
        from brainir_causal.store import TrajectoryStore
        self.calls.append((mode, store, len(items)))
        out = []
        for it in items:
            q = it["protocol"]
            n = round(q["t_end"] / q["dt"]) + 1
            noisy = q.get("obs_noise") is not None
            y = np.full((n, 2), 5.0 if noisy else 1.0, np.float32)
            out.append({"key": TrajectoryStore.key(q, it["sysdef"]["system_hash"], f"{ENGINE_VERSION}|{MODEL_ID}"), "t": np.arange(n) * q["dt"],
                        "x": np.zeros((n, 3), np.float32), "u": np.zeros((n, 1), np.float32), "y": y, "computed": True})
        return out


def test_modal_runner_maps_jobs_and_fetches_clean_readouts():
    from brainir_causal.systems import load_real_internal
    ints = load_real_internal()
    sid = next(s for s in sorted(ints) if ":m" in s)
    be = _FakeBackend(ints)
    run = S.modal_runner(be, ints)
    base = {"system": sid, "params_seed": 3, "t_end": 0.1, "dt": 0.001}
    jobs = [(sid, base, {}), (sid, {**base, "obs_noise": {"sd": 0.1, "seed": 4}}, {})]
    res = run(jobs)
    assert be.calls == [("observed", "store", 3)]
    assert "y_clean" not in res[0]["truth"] and float(res[1]["truth"]["y_clean"][0, 0]) == 1.0 and float(res[1]["y"][0, 0]) == 5.0
    from brainir.sim.model import MODEL_ID

    from brainir_causal.realsim import ENGINE_VERSION
    engine = f"{ENGINE_VERSION}|{MODEL_ID}"
    assert res[0]["key"] == S.dataset_key(P.validate(base), ints[sid]["system_hash"], engine)
    # observation noise changes the trajectory key but not the microstate (store) key
    assert res[0]["store_key"] == res[1]["store_key"] and res[0]["key"] != res[1]["key"]
