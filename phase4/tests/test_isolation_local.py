"""The model-worker driver (brainir_causal.isolation) over the LocalUnsafe transport (a separate process, the scrubbed environment and
the public code path; no OS sandbox — that is the Docker / Modal job): the phase discipline, the fit path, the bootstrap refits, and
the EQUIVALENCE of metrics computed through a RemoteFresh against the same trusted model in-process to 1e-12 (research/phase4/
EVAL_ARCHITECTURE.md; the coordinator's equivalence requirement). The Docker adversarial tests are test_eval_isolation_docker.py.
"""

from __future__ import annotations

import pickle
import textwrap
from pathlib import Path

import numpy as np
import pytest

from brainir_causal import isolation as I
from brainir_causal import runner as RN

ROOT = Path(__file__).resolve().parents[2]

# a self-contained method (its model class lives in the method package, so it unpickles in a worker and, after mount_methods, in the
# driver): a small linear system x = M s, z = C x, y = G z, with an exact encoder / dynamics / readout and a native lift.
TOY_METHOD = textwrap.dedent("""
    import numpy as np
    from brainir_causal.api import CausalStateMethod, CausalStateModel, register

    def _system(seed):
        rng = np.random.default_rng(seed)
        A = np.array([[-0.8, 2.0], [-2.0, -0.8]]); b = np.array([1.0, 0.3])
        Q, _ = np.linalg.qr(rng.standard_normal((5, 5)))
        M = Q * (1.0 + rng.random(5)); Minv = np.linalg.inv(M)
        G = np.array([[1.0, 0.0], [0.5, -1.0], [0.2, 0.7]])
        return {"A": A, "b": b, "M": M, "Minv": Minv, "C": Minv[:2], "G": G, "tau_w": 0.15, "n": 5}

    class ToyExact(CausalStateModel):
        def __init__(self, seed):
            self.p = _system(seed); self.k = {"toy": 2}
        def encode(self, sid, x, u, dt):
            return self.p["C"] @ np.asarray(x, float)[-1]
        def rollout(self, sid, z0, u_future, events, dt):
            z = np.asarray(z0, float).copy(); U = np.asarray(u_future, float).reshape(len(u_future), -1); out = [z.copy()]
            for j in range(len(U) - 1):
                tj = j * dt
                for e in events:
                    if e["kind"] == "kick" and abs(e["t"] - tj) < dt / 2:
                        dx = np.zeros(self.p["n"])
                        for kk, v in e["delta"].items(): dx[int(kk)] += v
                        z = z + self.p["C"] @ dx
                cur = np.zeros(self.p["n"])
                for e in events:
                    if e["kind"] == "current" and e["t0"] <= tj + 1e-9 and (e["t1"] is None or tj < e["t1"] - 1e-9):
                        for kk, v in e["targets"].items(): cur[int(kk)] += v
                z = z + dt * (self.p["A"] @ z + self.p["b"] * U[j, 0] + self.p["C"] @ cur)
                out.append(z.copy())
            Z = np.stack(out); return {"z": Z, "y": Z @ self.p["G"].T}
        def readout(self, sid, z, u):
            return np.atleast_2d(z) @ self.p["G"].T
        def supports(self, sid, kind):
            return kind in ("kick", "current")
        def lift(self, sid, x, u, dz, n=3, c=None):
            out = []
            for S in ((0, 1, 2, 3, 4), (0, 1, 2), (2, 3, 4))[:n]:
                Cs = self.p["C"][:, list(S)]; dx = np.linalg.pinv(Cs) @ np.asarray(dz, float)
                out.append({"events": [{"kind": "kick", "t": 0.0, "delta": {str(u_): float(v) for u_, v in zip(S, dx)}}],
                            "predicted_dz": Cs @ dx, "cost": float(np.abs(dx).sum() * 0.01)})
            return out
        def info(self):
            return {"k": dict(self.k), "n_params": {"encoder": {"toy": self.p["C"].size}, "transition": 6,
                                                    "read_in": {"toy": self.p["C"].size}, "readout": {"toy": self.p["G"].size}}}

    @register
    class ToyMethod(CausalStateMethod):
        name = "toy_method"
        def fit(self, data, *, systems, config=None, seed=0):
            return ToyExact(int((config or {}).get("seed_toy", 0)))
""")


@pytest.fixture(scope="module")
def room(tmp_path_factory):
    work = tmp_path_factory.mktemp("iso_local")
    mdir = work / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "toy_method.py").write_text(TOY_METHOD, encoding="utf-8")
    I.build_pubdir(work / "pub")
    tr = I.LocalUnsafeTransport(pubdir=work / "pub", method_dir=mdir)
    return tr, mdir


def test_pubdir_has_public_modules_and_baseline(tmp_path):
    man = I.build_pubdir(tmp_path / "pub")
    from brainir_causal import worker as W
    got = {p for p in man["files"] if p.startswith("brainir_causal/")}
    assert all(f"brainir_causal/{m}.py" in got for m in W.PUBLIC_MODULES if m != "__init__")
    # NON-public orchestrator modules never ship to a worker
    for forbidden in ("suites", "systems", "simservice", "synthadapter", "realsim", "store", "calibrate", "runner"):
        assert f"brainir_causal/{forbidden}.py" not in man["files"], forbidden
    assert man["p3_baseline"] == "ok" and any(p.startswith("brainir_state/") for p in man["files"])


def _model_bytes(room) -> bytes:
    tr, _ = room
    return I.fit_records(tr, method="toy_method", records=[], systems={"toy": {}}, config={})["model"]


def test_describe_and_fit_and_phase_discipline(room):
    tr, mdir = room
    assert I.describe_method(tr, "toy_method")["name"] == "toy_method"
    blob = _model_bytes(room)
    assert isinstance(blob, bytes)
    rf = I.RemoteFresh(blob, tr, threads=1)
    try:
        x = np.random.default_rng(1).standard_normal((60, 5))
        u = np.zeros((60, 1))
        z = rf.encode("toy", x, u, 0.01)
        assert z.shape == (2,) and np.all(np.isfinite(z))
        from brainir_causal.evaluate_lift import lift_supported
        assert lift_supported(rf)                                 # the proxy mirrors the remote class's lift override
        assert rf.capacity(["toy"])["params"]["reported"]
        rf.set_phase("lift")
        cand = rf.lift("toy", x, u, np.array([0.3, -0.2]))
        assert cand and cand[0]["events"]
        rf.encode("toy", x, u, 0.01)                              # a B2 encode reveals the lift outcomes
        with pytest.raises(PermissionError):
            rf.lift("toy", x, u, np.array([0.1, 0.1]))            # no lift requests after that
        rf.set_phase("C")
        with pytest.raises(PermissionError):
            rf.rollout("toy", z, u[:5], [], 0.01)                 # phase C may only encode
        with pytest.raises(PermissionError):
            rf.set_phase("A")                                     # phases only move forward
    finally:
        rf.close()


def test_bootstrap_interventions_keeps_passives_and_pairs_twins():
    from brainir_causal.data import Trajectory

    def tr(key, events, twin_of=None):
        return Trajectory(key=key, system_id="s", split="twin" if twin_of else "train", family="f",
                          protocol={"events": events, "dt": 0.01}, t=np.zeros(2), x=np.zeros((2, 1)), u=np.zeros((2, 1)),
                          y=np.zeros((2, 1)), meta={"twin_of": twin_of} if twin_of else {})
    recs = [tr("p0", []), tr("p1", [])]
    for i in range(6):
        recs += [tr(f"i{i}", [{"kind": "kick", "t": 0.0, "delta": {"0": 1.0}}]), tr(f"t{i}", [], twin_of=f"i{i}")]
    boot = I.bootstrap_interventions(recs, b=1, seed=0)
    keys = [r.key for r in boot]
    assert len(set(keys)) == len(keys), "keys must stay unique"
    assert sum(1 for r in boot if not r.protocol["events"] and not (r.meta or {}).get("twin_of")) == 2  # both passives kept
    assert len([r for r in boot if r.protocol["events"]]) == 6      # a bootstrap resample of the 6 interventions
    assert {r.meta["twin_of"] for r in boot if (r.meta or {}).get("twin_of")} <= set(keys)


def _close(a, b, tol=1e-12):
    if isinstance(a, dict):
        assert set(a) == set(b), (set(a) ^ set(b))
        for k in a:
            _close(a[k], b[k], tol)
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            _close(x, y, tol)
    elif isinstance(a, (int, float, np.floating, np.integer)):
        if a != a:
            assert b != b
        else:
            assert abs(float(a) - float(b)) <= tol + tol * abs(float(a)), (a, b)


class _Pub:
    """A minimal stand-in for suites' lazy ExperimentSet: whiten_histories needs .rows and .load()."""

    def __init__(self, train):
        self.rows = [{"key": r["key"], "split": r.get("split", "train")} for r in train]
        self._by = {r["key"]: r for r in train}

    def load(self, row):
        from brainir_causal.data import Trajectory
        r = self._by[row["key"]]
        return Trajectory(key=r["key"], system_id="toy", split=r.get("split", "train"), family="", protocol=r["protocol"],
                          t=np.asarray(r["t"]), x=np.asarray(r["x"]), u=np.asarray(r["u"]), y=np.asarray(r["y"]), meta=r.get("meta") or {})


@pytest.mark.slow
def test_metrics_through_remote_fresh_equal_direct(room):
    """(b) equivalence: metrics through RemoteFresh equal direct metrics on the SAME fitted model bytes to 1e-12 (toy tier). The
    direct model is the same bytes loaded in-process (the method package mounted in the driver)."""
    from brainir_causal import harness as H
    from test_calibrate_toyinputs import toy_inputs
    tr, mdir = room
    inp = toy_inputs(seed=0)
    sysc, items, pool = inp["sysc"], inp["items"], inp["pool"]
    inputs = {"system": sysc, "items": items, "pool": pool, "samples": [], "public": _Pub(inp["train"]), "record": inp["pub"]}
    blob = _model_bytes(room)
    RN.mount_methods(mdir)
    direct = pickle.loads(blob)                                   # the SAME bytes, in-process (trusted Fresh)
    fams = ("items", "mediation", "closure", "micro")
    dres = H.evaluate_model(direct, inputs, simulate_many=None, lift=False, n_boot=200, seed=0, families=fams)
    rf = I.RemoteFresh(blob, tr, threads=1)
    try:
        rres = H.evaluate_model(rf, inputs, simulate_many=None, lift=False, n_boot=200, seed=0, families=fams)
    finally:
        rf.close()
    for key in ("EE_medium", "EE_cb_medium"):
        _close(dres["items"]["effects"][key], rres["items"]["effects"][key])
    _close((dres["mediation"].get("SMS") or {}).get("point"), (rres["mediation"].get("SMS") or {}).get("point"))
    _close((dres["closure"].get("ICG_y") or {}).get("point"), (rres["closure"].get("ICG_y") or {}).get("point"))
    _close((dres.get("micro") or {}).get("MEV", {}).get("point"), (rres.get("micro") or {}).get("MEV", {}).get("point"))
