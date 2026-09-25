"""Phase 3 infrastructure tests (goal4 section 71): state-model serialisation and determinism, no future / output leakage through the
evaluator, synthetic-truth recovery metrics, latent lifting, sharing comparisons, statistics, store keys, clean-room scanning."""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

from brainir_state import evaluate as E
from brainir_state.api import StateModel, load_model
from brainir_state.data import Trajectory
from brainir_state.evaluate_cross import holm, paired_diff, paired_ratio_diff, sharing_comparison, sharing_verdict
from brainir_state.evaluate_lift import eval_lifting
from brainir_state.evaluate_synth import abstention_row, abstention_summary, dimension_recovery, eval_latent_recovery
from brainir_state.refmodels import ProjectionLinearModel

ROOT = Path(__file__).resolve().parents[2]
DT = 0.01
N = 12
RNG = np.random.default_rng(3)
C = RNG.standard_normal((N, 2))
Cp = np.linalg.pinv(C)
W, G = 2 * np.pi * 0.8, 0.3


def _sim(z0, stim, events=(), t_end=4.0, nonlin=False):
    n = int(round(t_end / DT)) + 1
    z = np.array(z0, float)
    X, Y, U, Z = [], [], [], []
    for i in range(n):
        t = i * DT
        u = [s for ts, s in stim if ts <= t + 1e-9][-1]
        x = C @ z
        X.append(np.tanh(x) if nonlin else x); Y.append([z[0]]); U.append([u]); Z.append(z.copy())
        for e in events:
            if e["kind"] == "kick" and abs(e["t"] - t) < DT / 2:
                dx = np.zeros(N)
                for k, v in e["delta"].items():
                    dx[int(k)] = v
                z = z + Cp @ dx
        for _ in range(10):
            h = DT / 10
            z = z + h * np.array([W * z[1], -W * z[0] - 2 * G * z[1] + 3.0 * u])
    return np.arange(n) * DT, np.array(X), np.array(U), np.array(Y), np.array(Z)


def _traj(key, z0, stim, events=(), fam="x", nonlin=False):
    t, X, U, Y, Z = _sim(z0, stim, events, nonlin=nonlin)
    proto = {"system": "toy", "params_seed": 0, "t_end": 4.0, "dt": DT, "stimulus": [list(s) for s in stim], "events": list(events)}
    return Trajectory(key=key, system_id="toy", split="train", family=fam, protocol=proto, t=t, x=X.astype(np.float32), u=U.astype(np.float32),
                      y=Y.astype(np.float32)), Z


@pytest.fixture(scope="module")
def toy():
    rng = np.random.default_rng(1)
    train, test, ztest = [], [], {}
    for i in range(30):
        tr, _ = _traj(f"tr{i}", rng.standard_normal(2), [(0.0, 0.0), (round(rng.uniform(0.2, 1.0), 2), float(rng.uniform(0.3, 1.2)))])
        train.append(tr)
    for i in range(10):
        tr, Z = _traj(f"te{i}", rng.standard_normal(2), [(0.0, 0.0), (round(rng.uniform(0.2, 1.0), 2), float(rng.uniform(0.3, 1.2)))])
        test.append(tr)
        ztest[tr.key] = Z
    model = ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))
    return train, test, ztest, model


# ------------------------------------------------------------------------------------------------ state models
def test_state_model_serialisation_and_deterministic_inference(toy, tmp_path):
    train, test, _, m = toy
    m.save(tmp_path / "m.pkl")
    m2 = load_model(tmp_path / "m.pkl")
    tr = test[0]
    z1 = m.encode("toy", tr.x[:101], tr.u[:101], DT)
    z2 = m2.encode("toy", tr.x[:101], tr.u[:101], DT)
    assert z1.shape == (2,) and np.array_equal(z1, z2)
    r1 = m.rollout("toy", z1, tr.u[100:201], [], DT)
    r2 = m2.rollout("toy", z2, tr.u[100:201], [], DT)
    assert r1["y"].shape == (101, 1) and r1["z"].shape == (101, 2)
    assert np.array_equal(r1["y"], r2["y"])


class _Spy(StateModel):
    """Records what the evaluator passes to the encoder."""
    k = {"toy": 1}

    def __init__(self):
        self.calls = []

    def encode(self, sid, x_hist, u_hist, dt):
        self.calls.append((len(x_hist), len(u_hist)))
        return np.zeros(1)

    def rollout(self, sid, z0, u_future, events, dt):
        n = len(u_future)
        return {"z": np.zeros((n, 1)), "y": np.zeros((n, 1))}

    def readout(self, sid, z, u):
        return np.zeros((np.atleast_2d(z).shape[0], 1))


def test_encoder_never_sees_future_samples_or_the_readout(toy):
    _, test, _, _ = toy
    spy = _Spy()
    E.eval_predictive(spy, "toy", test[:2], np.ones(1), E.EvalConfig(n_boot=10, horizons_s=(0.1, 0.5), start_times_s=(0.5, 1.0)))
    starts = {int(round(0.5 / DT)) + 1, int(round(1.0 / DT)) + 1}
    assert {c[0] for c in spy.calls} == starts          # history ends AT the encoding sample: x[0..i] only
    assert all(a == b for a, b in spy.calls)
    assert not hasattr(spy, "encode_with_readout")      # method models are never given y


# ------------------------------------------------------------------------------------------------ synthetic truth (K, L)
def test_known_state_recovery_linear_and_nonlinear(toy):
    _, test, ztest, m = toy
    k = eval_latent_recovery(m, "toy", test, ztest, E.EvalConfig(start_times_s=(0.5, 1.0)))
    assert k["r2_true_from_model_linear"] > 0.99 and k["r2_model_from_true_linear"] > 0.99, k
    rng = np.random.default_rng(2)
    trn, ten, zt = [], [], {}
    for i in range(30):
        trn.append(_traj(f"n{i}", rng.standard_normal(2), [(0.0, 0.0), (0.5, 1.0)], nonlin=True)[0])
    for i in range(10):
        tr, Z = _traj(f"m{i}", rng.standard_normal(2), [(0.0, 0.0), (0.5, 1.0)], nonlin=True)
        ten.append(tr); zt[tr.key] = Z
    mn = ProjectionLinearModel(2, "pca").fit("toy", trn, list(range(N)))
    kn = eval_latent_recovery(mn, "toy", ten, zt, E.EvalConfig(start_times_s=(0.5, 1.0)))
    assert kn["r2_true_from_model_rff"] > 0.9, kn          # saturating embedding: z still decodable nonlinearly


def test_dimension_and_abstention_scoring():
    assert dimension_recovery(2, None, 2)["exact"] and not dimension_recovery(3, [2, 4], 2)["exact"]
    assert dimension_recovery(3, [2, 4], 2)["in_range"]
    assert not dimension_recovery(None, None, "none")["applicable"]
    rows = [abstention_row({"k": "none"}, {"no_compact_state": True}, None), abstention_row({"k": "none"}, {}, None),
            abstention_row({"k": 2}, {"no_compact_state": True}, None),
            abstention_row({"k": 2}, {}, {"interventional": False, "closed": True})]
    s = abstention_summary(rows)
    assert s["abstention_recall"] == 0.5 and s["false_alarm_rate"] == 0.5 and s["confident_wrong_rate"] == 0.25


# ------------------------------------------------------------------------------------------------ causal tests: lifting
def test_latent_lifting_with_an_exact_lift(toy):
    _, test, _, m = toy

    class Lifted(ProjectionLinearModel):
        def lift(self, sid, x, z, delta_z, n_candidates=3):
            cols = {v: n for n, v in self.col.items()}
            out = []
            for j in range(n_candidates):
                dx = self.P.T @ delta_z
                if j:     # add a component in the encoder's null space: same latent shift, different microstate
                    v = np.random.default_rng(j).standard_normal(len(dx))
                    v -= self.P.T @ (self.P @ v)
                    dx = dx + v * 0.3 * np.linalg.norm(dx) / np.linalg.norm(v)
                out.append([{"kind": "kick", "t": 0.0, "delta": {str(cols[i]): float(dx[i]) for i in range(len(dx))}}])
            return out

    lm = Lifted(2, "pca").fit("toy", [*test[:5], *toy[0]], list(range(N)))

    def simulate(p):
        t, X, U, Y, Z = _sim([0.3, -0.2], [tuple(s) for s in p["stimulus"]], p.get("events") or [], t_end=p["t_end"])
        return {"t": t, "x": X, "u": U, "y": Y, "z": Z}

    cases = [{"protocol": {"dt": DT, "t_end": 4.0, "stimulus": [[0.0, 0.0], [0.3, 0.8]], "events": []}, "t": 1.0}]
    r = eval_lifting(lm, "toy", cases, simulate, np.ones(1), E.EvalConfig(n_boot=50), future_s=0.5)
    assert r["supported"] and r["achieved_shift_rel_error"]["mean"] < 0.1, r
    assert r["implementation_invariance_ratio"] < 0.1, r      # distinct lifts of one shift: same future (the null space is inert)


# ------------------------------------------------------------------------------------------------ cross-implementation
def test_sharing_rule_accepts_equivalent_and_rejects_worse_shared_models():
    rng = np.random.default_rng(0)
    base = {f"t{i}": float(v) for i, v in enumerate(rng.uniform(0.1, 0.2, 40))}
    same = {k: v + rng.normal(0, 0.002) for k, v in base.items()}
    worse = {k: v + 0.2 for k, v in base.items()}
    ceff = {f"p{i}": (0.1, 1.0, 0.1) for i in range(20)}

    def res(a, c):
        return {"A": {"A_nmse_h1000ms": {"mean": float(np.mean(list(a.values())))}, "_units": {"A_nmse_h1000ms": a}},
                "C": {"_units": {"C_w1000ms": c}}}
    p_small = {"encoder": 10, "readout": 2, "transition": 4, "total": 16, "reported": True}
    p_big = {"encoder": 10, "readout": 2, "transition": 8, "total": 20, "reported": True}
    good = sharing_comparison({"s1": res(same, ceff)}, {"s1": res(base, ceff)}, p_small, p_big, tau_a=0.1, a_key="A_nmse_h1000ms",
                              c_key="C_w1000ms")
    assert good["noninferior_all"] and good["fewer_parameters"]
    loio_ok = [{"adapted_beats_scratch": True, "adapted_worse": False}]
    assert sharing_verdict(good, loio_ok) == "supported"
    bad = sharing_comparison({"s1": res(worse, ceff)}, {"s1": res(base, ceff)}, p_small, p_big, tau_a=0.1, a_key="A_nmse_h1000ms",
                             c_key="C_w1000ms")
    assert sharing_verdict(bad, loio_ok) == "rejected"
    assert sharing_verdict(good, []) == "untestable"


# ------------------------------------------------------------------------------------------------ statistics
def test_paired_statistics_resample_units_and_are_reproducible():
    a = {f"t{i}": 1.0 + 0.1 * i for i in range(10)}
    b = {f"t{i}": 0.5 + 0.1 * i for i in range(10)}
    d1, d2 = paired_diff(a, b, 500, 0), paired_diff(a, b, 500, 0)
    assert d1 == d2 and abs(d1["diff"] - 0.5) < 1e-12 and d1["ci95"][0] > 0.49 and d1["p"] < 0.01
    r = paired_ratio_diff({"x": (1.0, 2.0, 0.0), "y": (1.0, 2.0, 0.0)}, {"x": (2.0, 2.0, 0.0), "y": (2.0, 2.0, 0.0)}, 200, 0)
    assert abs(r["diff"] + 0.5) < 1e-12
    # benchmark version 2: an uncomputable p-value stays in the family as p = 1 (review E B4)
    h = holm({"a": 0.01, "b": 0.04, "c": float("nan")})
    assert abs(h["a"] - 0.03) < 1e-12 and abs(h["b"] - 0.08) < 1e-12 and h["c"] == 1.0
    m, ci = E.boot_mean(np.array([1.0, 2.0, 3.0, 4.0]), 1000, 0)
    assert m == 2.5 and ci == E.boot_mean(np.array([1.0, 2.0, 3.0, 4.0]), 1000, 0)[1]      # CI regression: seeded, repeatable


# ------------------------------------------------------------------------------------------------ store keys / clean room
def test_store_keys_do_not_collide_across_systems_and_carry_interventions():
    from brainir_state import protocol as P
    p = P.validate({"system": "real:a:full", "params_seed": 1, "t_end": 0.1, "dt": 0.001, "stimulus": [[0.0, 1.0]],
                    "events": [{"kind": "kick", "t": 0.05, "delta": {"3": 5.0}}]})
    k1 = P.protocol_hash(p, system_hash="sysA", simulator="sim1")
    k2 = P.protocol_hash(p, system_hash="sysB", simulator="sim1")
    q = dict(p, events=[])
    assert k1 != k2 and k1 != P.protocol_hash(q, system_hash="sysA", simulator="sim1")
    assert k1 == P.protocol_hash(json.loads(json.dumps(p)), system_hash="sysA", simulator="sim1")
    assert k1 != P.protocol_hash(p, system_hash="sysA", simulator="sim2")


def test_cleanroom_scan_rejects_forbidden_files(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib
    mk = importlib.import_module("make_phase3_cleanroom")
    room = tmp_path / "room"
    (room / "src" / "brainir_state" / "methods").mkdir(parents=True)
    (room / "docs").mkdir()
    (room / "docs" / "ok.md").write_text("generic methods text\n", encoding="utf-8")
    manifest = {"files": [{"path": "docs/ok.md", "sha256": mk._sha(room / "docs" / "ok.md")}], "work_areas": list(mk.WORK_AREAS)}
    assert mk.scan(room, manifest) == []
    for name, text in (("PHASE2_REPORT.md", "x"), ("oracle/answer.json", "{}"), ("src/brainir_state/methods/hidden_eval_log.md", "x"),
                       ("src/brainir_state/methods/n.md", "the published core was")):
        f = room / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        probs = mk.scan(room, manifest)
        assert probs, name
        f.unlink()
    (room / "docs" / "ok.md").write_text("modified\n", encoding="utf-8")
    assert any("modified" in p or "hash" in p for p in mk.scan(room, manifest))


# ------------------------------------------------------------------------------------------------ method sandbox (fit guard)
def test_import_method_finds_methods_registered_in_a_module_with_another_name(tmp_path):
    """Several baselines live in one module (e.g. lin_pcadyn in lin_baselines.py): a plain name must still resolve, and another
    developer's broken module must not hide it."""
    from brainir_state.runner import import_method
    mdir = tmp_path / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "aaa_broken.py").write_text("raise RuntimeError('broken module')\n", encoding="utf-8")
    (mdir / "fam_baselines.py").write_text('''
from brainir_state.api import StateMethod, register
class _Base(StateMethod):
    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        raise NotImplementedError
@register
class First(_Base):
    name = "fam_first"
@register
class Second(_Base):
    name = "fam_second"
''', encoding="utf-8")
    assert import_method(mdir, "fam_second").name == "fam_second"
    assert import_method(mdir, "fam_baselines:fam_first").name == "fam_first"


def test_fit_sandbox_refuses_reads_outside_the_allowed_roots(tmp_path):
    """A method that tries to read a file outside its inputs (e.g. hidden data) fails inside the sandboxed fit subprocess."""
    import subprocess
    secret = tmp_path / "hidden" / "truth.json"
    secret.parent.mkdir(parents=True)
    secret.write_text('{"answer": 42}', encoding="utf-8")
    mdir = tmp_path / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "evil.py").write_text(f'''
from brainir_state.api import StateMethod, register
@register
class Evil(StateMethod):
    name = "evil"
    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        open(r"{secret}").read()
        raise SystemExit("read succeeded")
''', encoding="utf-8")
    ds = tmp_path / "ds"
    (ds / "traj").mkdir(parents=True)
    (ds / "manifest.json").write_text(json.dumps({"systems": {"s": {"observed": [0]}}, "dt": 0.01}), encoding="utf-8")
    (ds / "index.jsonl").write_text("", encoding="utf-8")
    env = dict(__import__("os").environ, TEMP=str(tmp_path), TMP=str(tmp_path))
    code = ("import sys; from brainir_state import runguard; "
            f"runguard.default_protected = lambda: [runguard._norm(r'{tmp_path}')]; "
            "from brainir_state.runner import main; sys.exit(main(sys.argv[1:]))")
    p = subprocess.run([sys.executable, "-c", code, "fit", "--method-dir", str(mdir), "--method", "evil", "--dataset", str(ds), "--systems", "s",
                        "--out", str(tmp_path / "out" / "m.pkl")], capture_output=True, text=True, env=env, timeout=300)
    assert p.returncode != 0
    assert "method sandbox" in p.stderr and "read succeeded" not in p.stderr + p.stdout, p.stderr[-2000:]
