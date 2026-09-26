"""Evaluator core on a linear toy system with hand-derived truth (PROTOCOL 5.1-5.6, 5.8, 5.9, 5.12, 5.16).

Toy: true causal state s in R^3 (a damped 1.5 Hz rotation in (s1, s2) and a slow decay in s3), microstate x = C s + n in R^6 (C with
orthonormal columns; the off-manifold part n decays by half per step and never reaches s or y), readout y = G s (depends on all three
state coordinates). Kicks offset units of x before a step (the recorded sample at the kick time is the PRE-kick state); currents add
to x during their window. Hence z = C^T x is the exact causal state, and:
- ExactModel (k = 3, exact dynamics and read-in): EE ~ 0, SMS ~ 0, ICG ~ 0, MEV small, latent recovery ~ 1;
- MissingModel (k = 2, drops s3): EE > 0, SMS > 0 (the residual microstate carries s3), MEV larger than the exact model's;
- IgnoreModel (exact z, rollout ignores interventions): EE = 1 on items above the floor;
- WrongReadInModel (exact z and dynamics, kicks on units 0-1 ignored): SMS through the identity features, no x_res gain, ICG ~ 0;
- AbstainModel (supports nothing): every item abstained, EE = 1, coverage 0.
The toy is linear, so responses to interventions are state-independent (the bisimulation response differences are ~0).
"""

from __future__ import annotations

import numpy as np
import pytest

from brainir_causal.api import CausalStateModel
from brainir_causal.evalio import Pool, PoolState, StateSample, TestItem, make_eval_system
from brainir_causal.evaluate import eval_calibration, eval_composition, eval_effects, eval_observational, eval_ood, evaluate_items, predict_items
from brainir_causal.evaluate_mediation import eval_closure, eval_mediation
from brainir_causal.evaluate_micro import eval_bisimulation, eval_microstate, latent_whitener
from brainir_causal.evaluate_truth import eval_dimension_truth, eval_latent_recovery, eval_readin_truth
from brainir_causal.fresh import Fresh

DT, T_END, SID = 0.01, 2.0, "toy"
H = 100                     # long horizon = 50 % of 2 s = 100 steps
I0 = 50                     # onset sample of every item
NB = 200                    # bootstrap resamples in tests (the protocol default is 2,000)

_r = np.random.default_rng(12345)
_Q, _ = np.linalg.qr(_r.standard_normal((6, 6)))
C = _Q[:, :3]
PERP = _Q[:, 3:] @ _Q[:, 3:].T
TH = 2 * np.pi * 1.5 * DT
A = np.array([[0.995 * np.cos(TH), -0.995 * np.sin(TH), 0.0], [0.995 * np.sin(TH), 0.995 * np.cos(TH), 0.0], [0.0, 0.0, 0.995]])
B = np.array([0.2, 0.0, 0.02])
CUR_GAIN = 0.1             # current per step enters the microstate scaled by this gain
G = np.array([[1.0, 0.0, 1.0], [0.0, 1.0, -0.5]])


def _current_vec(events, i, n=6):
    v = np.zeros(n)
    for e in events:
        if e["kind"] == "current":
            t1 = e["t1"] if e["t1"] is not None else 1e9
            if e["t0"] - 1e-9 <= i * DT < t1 - 1e-9:
                for j, a in e["targets"].items():
                    v[int(j)] += float(a)
    return v


def _kick_vec(events, i, n=6):
    v = np.zeros(n)
    for e in events:
        if e["kind"] == "kick" and abs(e["t"] - i * DT) < 1e-9:
            for j, d in e["delta"].items():
                v[int(j)] += float(d)
    return v


def simulate(x0, u, events, n_steps, A_=None):
    A_ = A if A_ is None else A_
    x = np.array(x0, float)
    xs = [x.copy()]
    for i in range(n_steps):
        x = x + _kick_vec(events, i)
        cur = _current_vec(events, i)
        s = C.T @ x
        n = x - C @ s
        s1 = A_ @ s + B * float(u[i]) + CUR_GAIN * (C.T @ cur)
        n1 = 0.5 * n + CUR_GAIN * (PERP @ cur)
        x = C @ s1 + n1
        xs.append(x.copy())
    return np.array(xs)


def readout(xs):
    return (G @ (C.T @ np.atleast_2d(xs).T)).T


class ExactModel(CausalStateModel):
    kdim = 3

    def __init__(self):
        self.k = {SID: self.kdim}

    def _proj(self):
        return C.T[: self.kdim]

    def encode(self, sid, x_hist, u_hist, dt):
        return self._proj() @ np.asarray(x_hist, float)[-1]

    def _A(self):
        return A[: self.kdim, : self.kdim]

    def rollout(self, sid, z0, u_future, events, dt):
        P = self._proj()
        z = np.array(z0, float)
        Z = [z.copy()]
        for i in range(len(u_future) - 1):
            z = z + P @ _kick_vec(events, i)
            z = self._A() @ z + B[: self.kdim] * float(np.asarray(u_future)[i, 0]) + CUR_GAIN * (P @ _current_vec(events, i))
            Z.append(z.copy())
        Z = np.array(Z)
        return {"z": Z, "y": Z @ G[:, : self.kdim].T}

    def readout(self, sid, z, u):
        return np.asarray(z) @ G[:, : self.kdim].T

    def supports(self, sid, kind):
        return kind in ("kick", "current")

    def read_in(self, sid, z, event):
        if event["kind"] == "kick":
            return {"dz": self._proj() @ _kick_vec([event], int(round(event["t"] / DT)))}
        return {}

    def info(self):
        return {"k": dict(self.k), "k_range": {SID: [self.kdim, self.kdim]}}


class MissingModel(ExactModel):
    kdim = 2


class IgnoreModel(ExactModel):
    def rollout(self, sid, z0, u_future, events, dt):
        return super().rollout(sid, z0, u_future, [], dt)


class WrongReadInModel(ExactModel):
    """Exact state and dynamics, but kicks on units 0 and 1 are ignored by its read-in: an identity-dependent error."""

    def rollout(self, sid, z0, u_future, events, dt):
        keep = [e for e in events if not (e["kind"] == "kick" and set(e["delta"]) & {"0", "1"})]
        return super().rollout(sid, z0, u_future, keep, dt)


class AbstainModel(ExactModel):
    def supports(self, sid, kind):
        return False


class LeakyModel(ExactModel):
    """Stores the last encoded history and would use it in the next rollout: the fresh-copy isolation must defeat it."""

    def encode(self, sid, x_hist, u_hist, dt):
        self.last = np.asarray(x_hist, float)
        return super().encode(sid, x_hist, u_hist, dt)

    def rollout(self, sid, z0, u_future, events, dt):
        out = super().rollout(sid, z0, u_future, events, dt)
        if getattr(self, "last", None) is not None:
            out["y"] = out["y"] + 1000.0
        return out


# ------------------------------------------------------------------------------------------------------------ data
def _inputs(rng, n):
    vals = rng.uniform(-1, 1, n // 40 + 2)
    return np.repeat(vals, 40)[:n]


def _event(rng, kind, scale=1.0):
    j = int(rng.integers(0, 6))
    sign = 1.0 if rng.random() < 0.5 else -1.0
    if kind == "kick":
        return [{"kind": "kick", "t": 0.0, "delta": {str(j): sign * scale * float(rng.uniform(0.5, 2.0))}}], j
    return [{"kind": "current", "t0": 0.0, "t1": 0.1, "targets": {str(j): sign * scale * float(rng.uniform(1.0, 3.0))}}], j


def make_data(n_traj=60, seed=0, tiny=False, comp=False):
    rng = np.random.default_rng(seed)
    items, train_x, train_y = [], [], []
    shifts = ["in", "target", "near", "far"]
    for tr in range(n_traj):
        x0 = C @ (rng.normal(size=3) * np.array([1.0, 1.0, 3.0])) + PERP @ rng.normal(0, 0.3, 6)
        u = _inputs(rng, I0 + H + 2)
        hist = simulate(x0, u, [], I0)
        train = simulate(x0, u, [], I0 + H)
        train_x.append(train)
        train_y.append(readout(train))
        for k, kind in enumerate(("kick", "current")):
            ev, j = _event(rng, kind, 1e-7 if tiny else 1.0)
            fut = simulate(hist[-1], u[I0:], ev, H)
            twin = simulate(hist[-1], u[I0:], [], H)
            s = C.T @ hist[-1]
            dz = C.T @ _kick_vec(ev, 0) if kind == "kick" else None
            items.append(TestItem(item_id=f"t{tr}_{k}", system_id=SID, dt=DT, x_hist=hist, u_hist=u[: I0 + 1, None],
                                  u_future=u[I0: I0 + H + 1, None], events=ev, y_future=readout(fut), y_twin=readout(twin),
                                  family="kick.1" if kind == "kick" else "pulse.1", shift=shifts[tr % 4],
                                  magnitude_class=["weak", "moderate", "strong"][tr % 3], target_set=(j,), onset=I0 * DT,
                                  group=f"t{tr}", x_future=fut, x_twin_future=twin, z_true=s, dz_true=dz))
        if comp:
            ea, ja = _event(rng, "kick")
            eb, jb = _event(rng, "current")
            eb[0]["t0"], eb[0]["t1"] = 0.2, 0.3
            fut = simulate(hist[-1], u[I0:], ea + eb, H)
            twin = simulate(hist[-1], u[I0:], [], H)
            items.append(TestItem(item_id=f"t{tr}_c", system_id=SID, dt=DT, x_hist=hist, u_hist=u[: I0 + 1, None],
                                  u_future=u[I0: I0 + H + 1, None], events=ea + eb, y_future=readout(fut), y_twin=readout(twin),
                                  family="comp.seq", shift="hidden", magnitude_class="moderate", target_set=(ja, jb),
                                  onset=I0 * DT, group=f"t{tr}", x_future=fut, x_twin_future=twin,
                                  components={"a": {"events": ea, "y_future": readout(simulate(hist[-1], u[I0:], ea, H))},
                                              "b": {"events": eb, "y_future": readout(simulate(hist[-1], u[I0:], eb, H))}}))
        # passive windows (5.2)
        items.append(TestItem(item_id=f"t{tr}_p", system_id=SID, dt=DT, x_hist=hist, u_hist=u[: I0 + 1, None],
                              u_future=u[I0: I0 + H + 1, None], events=[], y_future=readout(simulate(hist[-1], u[I0:], [], H)),
                              y_twin=None, family="obs.nominal", shift="passive", group=f"t{tr}"))
    sysc = make_eval_system(SID, "synthetic", DT, T_END, train_x, train_y, n_u=1)
    return sysc, items


def draw_matrix(d):
    """The toy's state matrix in parameter draw d (draw 0 = A): rotation frequency and slow decay vary by draw."""
    th = 2 * np.pi * 1.5 * (1 + 0.15 * d / 7) * DT
    return np.array([[0.995 * np.cos(th), -0.995 * np.sin(th), 0.0], [0.995 * np.sin(th), 0.995 * np.cos(th), 0.0],
                     [0.0, 0.0, 0.995 - 0.002 * d / 7]])


def make_pool(n_traj=30, per=5, seed=1, n_draws=1):
    """n_draws x n_traj source trajectories x per states; pairs only within a draw."""
    rng = np.random.default_rng(seed)
    seqs = {"none": {"events": [], "kind": "none"},
            "kick0": {"events": [{"kind": "kick", "t": 0.0, "delta": {"0": 1.0}}], "kind": "kick"},
            "cur2": {"events": [{"kind": "current", "t0": 0.0, "t1": 0.1, "targets": {"2": 2.0}}], "kind": "current"}}
    states = []
    for d in range(n_draws):
        Ad = draw_matrix(d)
        for tr in range(n_traj):
            x0 = C @ rng.normal(size=3) + PERP @ rng.normal(0, 0.3, 6)
            u = _inputs(rng, 400)
            traj = simulate(x0, u, [], 300, Ad)
            for q in range(per):
                i = int(rng.integers(40, 280))
                fut, xf = {}, {}
                for name, sq in seqs.items():
                    f = simulate(traj[i], np.zeros(H + 1), sq["events"], H, Ad)       # the pool's common future input (zero)
                    fut[name] = readout(f)
                    xf[name] = f
                states.append(PoolState(state_id=f"p{d}_{tr}_{q}", x_hist=traj[: i + 1], u_hist=u[: i + 1, None],
                                        y_now=readout(traj[i])[0], traj=f"d{d}tr{tr}", draw=f"d{d}", futures=fut, x_futures=xf,
                                        z_true=C.T @ traj[i]))
    for s in seqs.values():
        s["u_future"] = np.zeros((H + 1, 1))
    return Pool(system_id=SID, dt=DT, states=states, sequences=seqs, floor_div=1e-12)


@pytest.fixture(scope="module")
def data():
    return make_data(n_traj=60, seed=0, comp=True)


@pytest.fixture(scope="module")
def pool():
    return make_pool()


# ------------------------------------------------------------------------------------------------------------ 5.1 / 5.2
def test_exact_model_effect_error_is_zero(data):
    sysc, items = data
    preds = predict_items(ExactModel(), sysc, items)
    eff = eval_effects(sysc, items, preds, n_boot=NB)
    for h in ("short", "medium", "long"):
        assert eff[f"EE_{h}"]["point"] < 1e-10, h
    assert eff["n_failed"] == 0 and eff["n_abstained"] == 0
    assert eff["sign_accuracy"]["covered"] == pytest.approx(1.0)
    obs = eval_observational(sysc, items, preds, n_boot=NB)
    assert obs["obs_nmse_medium"]["point"] < 1e-10


def test_ignoring_interventions_scores_one(data):
    sysc, items = data
    eff = eval_effects(sysc, items, predict_items(IgnoreModel(), sysc, items), n_boot=NB)
    assert eff["EE_medium"]["point"] == pytest.approx(1.0, abs=1e-9)
    assert eff["sign_accuracy"]["covered"] == 0.0


def test_missing_state_has_error_but_below_no_effect(data):
    sysc, items = data
    eff = eval_effects(sysc, items, predict_items(MissingModel(), sysc, items), n_boot=NB)
    assert 1e-3 < eff["EE_medium"]["point"] < 1.5
    assert set(eff["by_shift_kind"]) >= {"in", "target", "near", "far"}
    assert set(eff["by_family"]) >= {"kick.1", "pulse.1"}


def test_abstention_bookkeeping(data):
    sysc, items = data
    preds = predict_items(AbstainModel(), sysc, items)
    eff = eval_effects(sysc, items, preds, n_boot=NB)
    n_int = sum(not it.is_passive for it in items)
    assert eff["n_abstained"] == n_int and eff["n_failed"] == 0
    assert eff["EE_medium"]["point"] == pytest.approx(1.0, abs=1e-9)
    cal = eval_calibration(sysc, items, preds, eff, n_boot=NB)
    assert cal["coverage"] == 0.0
    assert cal["false_confidence"]["n"] == 0


def test_floor_for_near_zero_effects():
    sysc, items = make_data(n_traj=24, seed=3, tiny=True)
    eff = eval_effects(sysc, items, predict_items(IgnoreModel(), sysc, items), n_boot=NB)
    # true effects are far below the floor: the floor denominator dominates, so predicting no effect is scored as nearly perfect
    assert eff["EE_medium"]["point"] < 1e-6
    assert eff["detectability_counts"]["below"] == eff["n_items"]


def test_failed_predictions_count_as_cap(data):
    sysc, items = data

    class Broken(ExactModel):
        def rollout(self, sid, z0, u_future, events, dt):
            out = super().rollout(sid, z0, u_future, events, dt)
            if events:
                out["y"] = out["y"] * np.nan
            return out

    eff = eval_effects(sysc, items, predict_items(Broken(), sysc, items), n_boot=NB)
    assert eff["n_failed"] == eff["n_items"]
    assert eff["EE_medium"]["point"] == pytest.approx(10.0)


def test_fresh_copies_defeat_state_leaks(data):
    """A model that stores the last encoded history cannot carry it into a separate rollout call: passive windows are encoded and
    rolled out in two calls, each on its own fresh copy (within one intervention_effect call the model may use its own encoding)."""
    sysc, items = data
    preds = predict_items(LeakyModel(), sysc, items)
    obs = eval_observational(sysc, items, preds, n_boot=NB)
    assert obs["obs_nmse_medium"]["point"] < 1e-10
    leaky = LeakyModel()
    leaky.encode(SID, items[0].x_hist, items[0].u_hist, DT)
    assert leaky.rollout(SID, np.zeros(3), items[0].u_future, [], DT)["y"][1, 0] > 100.0     # the leak exists without isolation
    F = Fresh(ExactModel())
    F.encode(SID, items[0].x_hist, items[0].u_hist, DT)
    assert F.n_copies == 1


def test_determinism(data):
    sysc, items = data
    a = evaluate_items(MissingModel(), sysc, items, n_boot=NB)
    b = evaluate_items(MissingModel(), sysc, items, n_boot=NB)
    assert a["effects"]["EE_medium"] == b["effects"]["EE_medium"]
    assert a["calibration"]["false_confidence"] == b["calibration"]["false_confidence"]


# ------------------------------------------------------------------------------------------------------------ 5.3 / 5.4
def test_mediation_exact_vs_missing(data):
    sysc, items = data
    ex = eval_mediation(sysc, items, predict_items(ExactModel(), sysc, items), n_boot=NB)
    mi = eval_mediation(sysc, items, predict_items(MissingModel(), sysc, items), n_boot=NB)
    assert abs(ex["SMS"]["point"]) < 0.05
    assert mi["SMS"]["point"] > 0.3
    assert mi["SMS"]["ci95"][0] > ex["SMS"]["ci95"][1]
    assert mi["SMS_x_res"]["point"] > 0.2


def test_mediation_separates_readin_error_from_missing_state(data):
    """Exact state but a wrong read-in for two targets: the identity pathway carries the error, the residual microstate does not,
    and the evaluator-fitted closure finds the state complete."""
    sysc, items = data
    preds = predict_items(WrongReadInModel(), sysc, items)
    med = eval_mediation(sysc, items, preds, n_boot=NB)
    assert med["SMS_id"]["point"] > 0.3 and med["SMS_id"]["ci95"][0] > 0.1
    assert abs(med["SMS_x_res"]["point"]) < 0.05
    clo = eval_closure(WrongReadInModel(), sysc, items, preds, n_boot=NB)
    assert abs(clo["ICG_y"]["point"]) < 0.05


def test_mediation_is_stable_across_seeds(data):
    sysc, items = data
    preds = predict_items(ExactModel(), sysc, items)
    for seed in (1, 2):
        assert abs(eval_mediation(sysc, items, preds, n_boot=50, seed=seed, repeats=2)["SMS"]["point"]) < 0.02
        assert abs(eval_closure(ExactModel(), sysc, items, preds, n_boot=50, seed=seed, repeats=2)["ICG_y"]["point"]) < 0.05


def test_closure_exact_vs_missing(data):
    sysc, items = data
    ex = eval_closure(ExactModel(), sysc, items, predict_items(ExactModel(), sysc, items), n_boot=NB)
    mi = eval_closure(MissingModel(), sysc, items, predict_items(MissingModel(), sysc, items), n_boot=NB)
    assert ex["ICG_y"]["point"] < 0.05
    assert mi["ICG_y"]["point"] > 0.2
    assert ex["own_closure_gap"]["ratio"] < 1e-8
    ig = eval_closure(IgnoreModel(), sysc, items, predict_items(IgnoreModel(), sysc, items), n_boot=NB)
    assert ig["own_closure_gap"]["ratio"] == pytest.approx(1.0, rel=1e-6)


# ------------------------------------------------------------------------------------------------------------ 5.5 / 5.6
def test_microstate_equivalence(data, pool):
    sysc, items = data
    hists = [(it.x_hist, it.u_hist, it.dt) for it in items if it.is_passive]
    ex = eval_microstate(ExactModel(), sysc, pool, whiten_z=latent_whitener(ExactModel(), SID, hists), n_boot=NB)
    mi = eval_microstate(MissingModel(), sysc, pool, whiten_z=latent_whitener(MissingModel(), SID, hists), n_boot=NB)
    assert ex["whiten_source"] == "train"
    assert ex["MEV"]["point"] < mi["MEV"]["point"]
    assert ex["MEV"]["point"] < 0.2
    assert ex["comparisons"]["truth"]["mean"] < 0.2
    assert set(ex["per_sequence"]) == {"none", "kick0", "cur2"}


def test_bisimulation_curves(data, pool):
    sysc, _ = data
    bs = eval_bisimulation(ExactModel(), sysc, pool, n_bins=5, max_pairs=500)
    assert len(bs["bins"]) == 5
    assert bs["spearman"]["readout_diff"] > 0.3
    assert set(bs["latent_expansion_median"]) >= {"none", "kick0", "cur2"}


# ------------------------------------------------------------------------------------------------------------ 5.8 / 5.9 / 5.12
def test_composition_and_calibration(data):
    sysc, items = data
    preds = predict_items(ExactModel(), sysc, items)
    comp = eval_composition(ExactModel(), sysc, items, preds, n_boot=NB)
    assert comp["n_items"] == 60 and comp["consistency"]["n"] == 60
    assert comp["consistency"]["nonadditivity_error"] < 1e-8
    cal = eval_calibration(sysc, items, preds, n_boot=NB)
    assert cal["coverage"] == 1.0
    assert cal["false_confidence"]["rate"] == 0.0
    assert cal["brier_detectable"]["score"] == pytest.approx(0.0)
    ood = eval_ood(sysc, items, preds, n_boot=NB)
    assert ood["validity_auc"]["n_bad"] == 0


def test_validity_auc_detects_bad_items():
    from brainir_causal.evaluate import _auc
    assert _auc(np.array([0.1, 0.2]), np.array([0.8, 0.9])) == pytest.approx(1.0)
    assert _auc(np.array([0.5, 0.5]), np.array([0.5, 0.5])) == pytest.approx(0.5)


# ------------------------------------------------------------------------------------------------------------ 5.16
def test_truth_metrics(data):
    sysc, items = data
    samples = [StateSample(sample_id=it.item_id, x_hist=it.x_hist, u_hist=it.u_hist, dt=it.dt, group=it.group, z_true=it.z_true)
               for it in items if it.z_true is not None]
    ex = eval_latent_recovery(ExactModel(), SID, samples)
    mi = eval_latent_recovery(MissingModel(), SID, samples)
    assert ex["recovery"] > 0.95
    assert mi["r2_true_from_z"] < 0.9
    ri = eval_readin_truth(ExactModel(), SID, items, predict_items(ExactModel(), sysc, items), samples)
    assert ri["r2"] > 0.999 and ri["source"]["read_in"] > 0
    d = eval_dimension_truth(3, (3, 3), {"k": 3}, False)
    assert d["k_correct"] and d["k_true_in_range"]
    d = eval_dimension_truth(None, None, {"k": "none"}, True)
    assert d["abstention_correct"]


def test_attach_truth_with_the_generator_adapter():
    """The truth interface of brainir_causal.synthadapter (simulate(full=True)["state"], true_state, true_latent_effect) feeds the
    evaluator's truth fields."""
    from brainir_causal.evaluate_truth import attach_truth
    from brainir_causal.synthadapter import ToySystem
    sysm = ToySystem(seed=0, j=0)
    kick = {"kind": "kick", "t": 1.0, "delta": {"2": 0.5}}
    proto = {"system": sysm.system_id, "params_seed": 1, "t_end": 2.0, "dt": sysm.dt, "stimulus": [[0.0, 1.0]], "events": [kick]}
    sim = sysm.simulate(proto, full=True)
    i0 = int(round(1.0 / sysm.dt))
    it = TestItem(item_id="adapter", system_id=sysm.system_id, dt=sysm.dt, x_hist=sim["x"][: i0 + 1], u_hist=sim["u"][: i0 + 1],
                  u_future=sim["u"][i0:], events=[{**kick, "t": 0.0}], y_future=sim["y"][i0:], y_twin=sim["y"][i0:],
                  family="kick.1", meta={"state": sim["state"][i0]})
    attach_truth(sysm, [it])
    assert np.allclose(it.z_true, sim["z"][i0])
    dx = np.zeros(sysm.N)
    dx[2] = 0.5
    assert np.allclose(it.dz_true, sysm.C @ dx)


def test_truth_only_states_do_not_enter_the_pairing(data, pool):
    """Truth-equivalent states built by the dataset builder (meta["truth_only"]) feed only the truth-equivalent comparison."""
    import dataclasses
    sysc, _ = data
    rng = np.random.default_rng(9)
    extra = []
    for st in pool.states[:20]:
        x = st.x_hist[-1] + PERP @ rng.normal(0, 0.5, 6)            # same causal state, different off-manifold microstate
        fut = {name: readout(simulate(x, np.zeros(H + 1), sq["events"], H)) for name, sq in pool.sequences.items()}
        extra.append(PoolState(state_id=st.state_id + "~eq", x_hist=np.vstack([st.x_hist[:-1], x]), u_hist=st.u_hist,
                               y_now=readout(x)[0], traj="equiv:" + st.traj, draw=st.draw, futures=fut, z_true=C.T @ x,
                               equiv_class=st.state_id, meta={"truth_only": True}))
    base = [dataclasses.replace(st, equiv_class=st.state_id) for st in pool.states]
    p2 = Pool(system_id=pool.system_id, dt=pool.dt, states=base + extra, sequences=pool.sequences, floor_div=pool.floor_div)
    a = eval_microstate(ExactModel(), sysc, pool, n_boot=NB)
    b = eval_microstate(ExactModel(), sysc, p2, n_boot=NB)
    assert a["MEV"] == b["MEV"] and b["n_truth_only_states"] == 20
    assert b["comparisons"]["truth_equivalent"]["n_pairs"] == 20
    assert b["comparisons"]["truth_equivalent"]["mean"] < 1e-10
    assert eval_bisimulation(ExactModel(), sysc, p2, n_bins=5, max_pairs=500)["n_pairs"] == \
        eval_bisimulation(ExactModel(), sysc, pool, n_bins=5, max_pairs=500)["n_pairs"]


def test_mev_fixed_count_rule_on_600_state_pool(data):
    """PROTOCOL 5.5 (LOG P4-D14): a pool of 8 draws x 15 source trajectories x 5 times = 600 states; matched pairs = the M = 20
    closest candidate pairs. An exact 3-D latent is TESTABLE and scores MEV at its truth value (the same statistic with the true causal
    state as the latent: identical under the pool's whitening, within the CI under the training whitening); the draft's 2 % quantile
    rule is reported only as a sensitivity (its matches are several times farther); a latent missing a state variable scores worse."""
    sysc, items = data
    big = make_pool(n_traj=15, per=5, seed=11, n_draws=8)
    assert len(big.states) == 600
    hists = [(it.x_hist, it.u_hist, it.dt) for it in items if it.is_passive]
    ex = eval_microstate(ExactModel(), sysc, big, whiten_z=latent_whitener(ExactModel(), SID, hists), n_boot=NB)
    assert ex["testable"], ex["untestable_reason"]
    assert ex["matched"]["rule"] == "count" and ex["matched"]["M"] == 20 and ex["matched"]["n_pairs"] == 20
    assert ex["matched"]["median_dist_ratio"] < 0.1
    truth = ex["comparisons"]["truth"]["mean"]
    assert ex["MEV"]["ci95"][0] <= truth <= ex["MEV"]["ci95"][1]
    assert ex["MEV"]["point"] < 0.02
    same = eval_microstate(ExactModel(), sysc, big, whiten_z=None, n_boot=NB)       # pool whitening: the same distances as the truth
    assert same["MEV"]["point"] == pytest.approx(same["comparisons"]["truth"]["mean"], rel=1e-9)
    sens = ex["sensitivity"]["quantile_rule"]
    assert sens["n_pairs"] > 20 and sens["median_dist_ratio"] > 2 * ex["matched"]["median_dist_ratio"]
    assert sens["MEV"]["point"] > ex["MEV"]["point"]
    mi = eval_microstate(MissingModel(), sysc, big, whiten_z=latent_whitener(MissingModel(), SID, hists), n_boot=NB)
    assert mi["testable"] and mi["MEV"]["point"] > 3 * ex["MEV"]["point"] and mi["MEV"]["ci95"][0] > ex["MEV"]["point"]
