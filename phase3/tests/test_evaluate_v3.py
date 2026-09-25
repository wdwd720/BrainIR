"""Benchmark version 3 evaluator (pre-lock reviews A-D): rollout isolation, Markov / decoy / event-restart checks, the observed-target
split, the state-dependence control, the pooled real normaliser, the closure regression without base shrinkage and the v3 verdict."""

from __future__ import annotations

import numpy as np
import pytest

from brainir_state import evaluate as E
from brainir_state import harness as H
from brainir_state.api import StateModel
from brainir_state.refmodels import ProjectionLinearModel

from test_evaluate import N, data  # noqa: F401  (the toy fixture: z in R^2, x = C z, y = D z)

CFG = E.EvalConfig(n_boot=200)
_GLOBAL_STASH: dict = {}


class _Wrap(StateModel):
    """Reports a 1-D latent (the first PCA coordinate) around an honest 2-D PCA model."""

    def __init__(self, inner):
        self.inner = inner
        self.k = {"toy": 1}

    def encode(self, sid, x_hist, u_hist, dt):
        return self.inner.encode(sid, x_hist, u_hist, dt)[:1]

    def _roll(self, sid, zfull, u, events, dt):
        out = self.inner.rollout(sid, zfull, u, events, dt)
        return {"z": np.asarray(out["z"])[:, :1], "y": np.asarray(out["y"])}

    def rollout(self, sid, z0, u, events, dt):
        return self._roll(sid, np.r_[np.asarray(z0, float), 0.0], u, events, dt)

    def readout(self, sid, z, u):
        z = np.asarray(z, float)
        return self.inner.readout(sid, np.concatenate([z, np.zeros(z.shape[:-1] + (1,))], -1), u)

    def supports(self, sid, kind):
        return self.inner.supports(sid, kind)


class InstanceStash(_Wrap):
    """encode() keeps the full 2-D state in the object; rollout() uses it when z0 matches (the review A / B side channel)."""

    def encode(self, sid, x_hist, u_hist, dt):
        z = self.inner.encode(sid, x_hist, u_hist, dt)
        self._stash = np.asarray(z, float)
        return z[:1]

    def rollout(self, sid, z0, u, events, dt):
        st = getattr(self, "_stash", None)
        if st is not None and np.allclose(st[:1], z0):
            return self._roll(sid, st, u, events, dt)
        return super().rollout(sid, z0, u, events, dt)


class GlobalStash(_Wrap):
    """The same side channel through MODULE state (outside the fresh-copy guard; the decoy check must catch it)."""

    def encode(self, sid, x_hist, u_hist, dt):
        z = self.inner.encode(sid, x_hist, u_hist, dt)
        _GLOBAL_STASH["last"] = np.asarray(z, float)
        return z[:1]

    def rollout(self, sid, z0, u, events, dt):
        st = _GLOBAL_STASH.get("last")
        if st is not None and np.allclose(st[:1], z0):
            return self._roll(sid, st, u, events, dt)
        return super().rollout(sid, z0, u, events, dt)


class HiddenMemory(_Wrap):
    """Carries the second coordinate inside rollout() without reporting it: z0 is lifted with a FIXED hidden value, the rollout
    evolves the full 2-D state, so a restart from the reported z_a (which has lost the evolved hidden coordinate) differs."""

    def rollout(self, sid, z0, u, events, dt):
        return self._roll(sid, np.r_[np.asarray(z0, float), 1.0], u, events, dt)


@pytest.fixture(scope="module")
def pca2(data):  # noqa: F811
    train, _, _ = data
    return ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))


def test_fresh_copies_defeat_an_instance_side_channel(data, pca2):  # noqa: F811
    train, test, _ = data
    scale = E.readout_scale(train)
    honest = E.eval_predictive(_Wrap(pca2), "toy", test, scale, CFG)["A_nmse_h250ms"]["mean"]
    stash = E.eval_predictive(InstanceStash(pca2), "toy", test, scale, CFG)["A_nmse_h250ms"]["mean"]
    full = E.eval_predictive(pca2, "toy", test, scale, CFG)["A_nmse_h250ms"]["mean"]
    assert full < 0.05 < honest                   # the 1-D projection alone cannot predict
    assert stash == pytest.approx(honest)        # the stash never reaches a prediction


def test_honest_model_passes_the_markov_checks(data, pca2):  # noqa: F811
    train, test, _ = data
    r = E.eval_rollout_checks(pca2, "toy", test, E.readout_scale(train), CFG)
    assert r["markov_ok"] and r["decoy_y_inconsistency_nmse"] < 1e-12 and r["markov_y_inconsistency_nmse"] < 1e-12
    assert r["readout_inconsistency_nmse"] < 1e-12


def test_hidden_rollout_memory_fails_markov(data, pca2):  # noqa: F811
    train, test, _ = data
    r = E.eval_rollout_checks(HiddenMemory(pca2), "toy", test, E.readout_scale(train), CFG)
    assert not r["markov_ok"] and r["markov_y_inconsistency_nmse"] > 1e-3


def test_module_level_stash_fails_the_decoy_check(data, pca2):  # noqa: F811
    train, test, _ = data
    _GLOBAL_STASH.clear()
    r = E.eval_rollout_checks(GlobalStash(pca2), "toy", test, E.readout_scale(train), CFG)
    assert not r["markov_ok"] and r["decoy_y_inconsistency_nmse"] > 1e-3


def test_intervention_extras_and_event_restart(data, pca2):  # noqa: F811
    train, _, pairs = data
    scale = E.readout_scale(train)
    zm = E.encodings_for_whitening(pca2, "toy", train, CFG).mean(0)
    c = E.eval_intervention(pca2, "toy", pairs, scale, CFG, z_mean=zm)
    p = c["C_effect_error_w250ms"]
    assert p["ratio"] < 0.2 and p["loo_max"] < 1 and np.isfinite(p["scrambled_mean"]) and "minus_scrambled_mean" in p
    assert c["markov_events"]["n"] > 0 and c["markov_events"]["y_nmse_max"] < 1e-12
    assert c["interventional_closure_gap"]["ratio"] < c["interventional_closure_gap"]["ratio_no_effect"]
    # a model with hidden memory also fails the restart after events
    ch = E.eval_intervention(HiddenMemory(pca2), "toy", pairs, scale, CFG)
    assert ch["markov_events"]["y_nmse_max"] > 1e-3


def test_events_on_unobserved_neurons_are_detected(data):  # noqa: F811
    _, _, pairs = data
    tr = pairs[0][0]
    target = next(iter(E.event_targets(tr.events()[0])))
    assert E.events_observed(tr, range(N))
    assert not E.events_observed(tr, [n for n in range(N) if n != target])


def test_pooled_scale_is_the_mean_variance(data):  # noqa: F811
    train, _, _ = data
    per_dim, pooled = E.readout_scale(train), E.readout_scale(train, pooled=True)
    Y = np.concatenate([t.y for t in train]).astype(np.float64)
    assert np.allclose(pooled, Y.var(0).mean()) and pooled.shape == per_dim.shape


def test_true_state_has_no_closure_gain_in_either_regression(data, pca2):  # noqa: F811
    """Version 3: the base (z, u) is fitted without shrinkage, so extra columns that repeat z (history, residual) cannot 'help'."""
    train, test, _ = data
    d = E.eval_closure(pca2, "toy", test, H.pca_basis(train), E.readout_scale(train), E.EvalConfig(n_boot=200, closure_repeats=3))
    for kind in ("linear", "rff"):
        r = d[f"D_y_h100ms_{kind}"]
        assert r["micro_gain_ci95"][1] < 0.05 and r["history_gain_ci95"][1] < 0.05, (kind, r)


# ------------------------------------------------------------------------------------------------------------ verdict rules
TAUS = {"tau_A": 0.5, "tau_C": 3.0, "tau_D": 0.2, "tau_E": 0.02, "tau_H": 0.2, "tau_gap": 0.1}
KA, KC, KD = H.key_a(H.SYNTH_CFG), H.key_c(H.SYNTH_CFG), H.key_d(H.SYNTH_CFG)


def _res(markov=True, c=0.3, c_ci=(0.2, 0.5), loo=0.6, n_primary=8, hist_up=0.1, gap=0.05, ev_y=0.0):
    units = {f"t{i}": 0.1 for i in range(10)}
    return {"A_B": {KA: {"mean": 0.1}, "_units": {KA: units}},
            "C_heldout": {"n_pairs": n_primary, "n_abstained_unsupported": 0,
                          KC: {"ratio": c, "ci95": list(c_ci), "n": n_primary, "n_eff": 4.0, "loo_max": loo},
                          "markov_events": {"n": 3, "y_nmse_max": ev_y, "z_sq_mean": [0.0]}},
            "D": {KD: {"micro_gain": 0.0, "micro_gain_ci95": [-0.1, 0.1], "history_gain": 0.0, "history_gain_ci95": [-0.1, hist_up]}},
            "R": {"markov_ok": markov, "closure_gap_y_nmse": gap, "noise_curve": {"0": 0.1, "0.05": 0.11}},
            "E": {"E_ratio_latent_to_random": 0.001, "E_ratio_ci95": [0.0005, 0.002], "E_testable": True},
            "Z_train_var": [1.0]}


def _refs(worse=0.5):
    u = {f"t{i}": worse for i in range(10)}
    return {"full_state": {"A_B": {KA: {"mean": 0.09}}}, "input_only": {"A_B": {"_units": {KA: u}}},
            "readout_hist": {"A_B": {"_units": {KA: u}}}, "persistence": {"A_B": {"_units": {KA: u}}}}


def test_v3_full_verdict_and_markov_gate():
    v = H.verdict(_res(), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)
    assert v["verdict"] == H.VERDICT_FULL and v["markov_ok"] and v["compact"] and v["closed"]
    v = H.verdict(_res(markov=False), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)
    assert v["k_valid"] is False and v["compact"] is False and v["closed"] is False and v["verdict"] != H.VERDICT_FULL
    v = H.verdict(_res(ev_y=1.0), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)
    assert v["markov_ok"] is False                                     # the restart after events fails


def test_v3_interventional_rules():
    v = H.verdict(_res(loo=1.2), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)
    assert v["interventional"] is False and "leave-one-pair-out" in v["interventional_reason"]
    v = H.verdict(_res(n_primary=2), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)
    assert v["interventional"] is None and v["verdict"] != H.VERDICT_FULL
    v = H.verdict(_res(c_ci=(0.5, 1.05)), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)
    assert v["interventional"] is False


def test_v3_closed_needs_history_and_gap():
    assert H.verdict(_res(hist_up=0.5), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)["closed"] is False
    assert H.verdict(_res(gap=0.5), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)["closed"] is False


def test_v3_real_predictive_uses_input_only_and_persistence():
    refs = _refs()
    refs["readout_hist"] = {"A_B": {"_units": {KA: {f"t{i}": 0.01 for i in range(10)}}}}    # readout history beats the model
    v = H.verdict(_res(), refs, TAUS, 200, 2, "full", H.SYNTH_CFG, n_boot=200)
    assert v["predictive"] is True and v["system_kind"] == "real"
    refs["persistence"] = {"A_B": {"_units": {KA: {f"t{i}": 0.01 for i in range(10)}}}}     # persistence beats the model
    assert H.verdict(_res(), refs, TAUS, 200, 2, "full", H.SYNTH_CFG, n_boot=200)["predictive"] is False
    # synthetic: the readout-history control is judged
    refs = _refs()
    refs["readout_hist"] = {"A_B": {"_units": {KA: {f"t{i}": 0.01 for i in range(10)}}}}
    assert H.verdict(_res(), refs, TAUS, 20, 2, "synthetic", H.SYNTH_CFG, n_boot=200)["predictive"] is False


def test_v3_declared_failure_blocks_the_full_verdict():
    v = H.verdict(_res(), _refs(), TAUS, 20, 2, "synthetic", H.SYNTH_CFG, abstain={"causal_equivalence_failed": True}, n_boot=200)
    assert v["verdict"] != H.VERDICT_FULL and v["declared_failure"]


def test_mechanism_roles_move_b_families_in_distribution():
    r = H.roles_for("real", "mech")
    assert r["heldout_intervention"] == ("H_group_silence",) and "H_kick_B" in r["indist_intervention"]
    assert H.roles_for("real", "full")["heldout_intervention"] == H.HELDOUT_INTERVENTION
    assert H.roles_for("synthetic") is H.SYNTH_ROLES
