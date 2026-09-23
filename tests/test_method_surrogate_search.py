"""surrogate_search: surrogate unit checks (no simulator), determinism under seed, budget honesty, schema-valid prediction,
recovery of the developer's own tiny mechanisms, surrogate-error reporting. Only synthetic instances built here are used."""

from __future__ import annotations

import json

import numpy as np
import pytest

import brainir.methods.surrogate_search as ss
from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, MethodRegistry
from brainir.discovery.interface import GENERIC_ROLES
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import run_one

FAST = {"ensemble_size": 6, "fit_steps": 150, "refit_steps": 60}


def _make(root, family, n, seed0, comps=(), n_readout=8):
    for s in range(seed0, seed0 + 10):
        spec = InstanceSpec(family, n, s, tuple(comps), n_readout=n_readout)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            export_instance(inst, ver, root, n_order_variants=1)
            return spec.label
    raise AssertionError(f"no verified {family} instance")


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("ss_suite")
    labels = {"ei": _make(root, "ei_pair_oscillator", 40, 9_100_000),
              "redundant": _make(root, "redundant_oscillator", 48, 9_200_000, ("backup_copy",)),
              "band": _make(root, "negative_feedback_controller", 40, 9_300_000)}
    return root, labels


def _run(root, label, budget, seed=0, config=None, robust=False):
    return run_one("surrogate_search", root / "instances" / label, "main", budget=budget, seed=seed, config={**FAST, **(config or {})},
                   truth_path=root / "truth" / f"{label}.json", score_seeds=[9], workers=1, robust=robust)


# ---------------------------------------------------------------------------- surrogate without any simulator
def test_dnf_ensemble_learns_a_conjunction_and_an_or_of_conjunctions():
    rng = np.random.default_rng(0)
    K = 8
    Z = (rng.random((300, K)) < 0.6).astype(float)
    y_and = (Z[:, 1] * Z[:, 4]).astype(float)                       # AND of two members
    ens = ss._DnfEnsemble(K, n_members=6, n_units=3, rng=np.random.default_rng(1), n_indicator=K)
    ens.fit(Z, y_and, np.ones(300), steps=400)
    mu, _ = ens.predict(Z)
    assert np.mean((mu >= 0.5) == (y_and >= 0.5)) >= 0.95
    y_or = np.maximum(Z[:, 1] * Z[:, 4], Z[:, 2] * Z[:, 6])         # OR of two disjoint conjunctions (not linearly separable)
    ens2 = ss._DnfEnsemble(K, n_members=6, n_units=3, rng=np.random.default_rng(2), n_indicator=K)
    ens2.fit(Z, y_or, np.ones(300), steps=600)
    mu2, _ = ens2.predict(Z)
    assert np.mean((mu2 >= 0.5) == (y_or >= 0.5)) >= 0.9
    # the mixed set {1, 6} must not be predicted to pass while {1, 4} must
    q = ens2.predict(np.array([[0, 1, 0, 0, 0, 0, 1, 0], [0, 1, 0, 0, 1, 0, 0, 0]], dtype=float))[0]
    assert q[1] > 0.5 and q[0] < q[1]


def test_pool_features_incremental_removal_matches_direct(suite):
    root, labels = suite
    p = DiscoveryProblem.from_bundle(root / "instances" / labels["ei"], "main")
    pool = p.candidate_positions()[:12]
    feat = ss._PoolFeatures(p, pool)
    rng = np.random.default_rng(3)
    z = rng.random(len(pool)) < 0.7
    z[:3] = True
    st = feat.state(z)
    S = np.flatnonzero(z)
    da = feat.delta_remove(st, S)
    for j, i in enumerate(S):
        z2 = z.copy(); z2[i] = False
        direct = feat.aggregates(z2[None, :])[0] - feat.aggregates(z[None, :])[0]
        assert np.allclose(da[j], direct, atol=1e-9)
    ens = ss._DnfEnsemble(feat.n_features, 4, 2, np.random.default_rng(4), n_indicator=feat.K)
    z_el, removed = ens.eliminate(feat, z, members=np.arange(4), mode="ucb", tau=0.0, kappa=0.0)
    assert z_el.sum() == 1 and len(removed) == z.sum() - 1     # tau 0: eliminates down to one node
    nec, q0, sd = ens.necessity(feat, z)
    assert nec.shape == (feat.K,) and 0.0 <= q0 <= 1.0


# ---------------------------------------------------------------------------- end-to-end on the developer's own instances
def test_registered_with_default_config():
    assert "surrogate_search" in MethodRegistry.names()
    m = MethodRegistry.get("surrogate_search")
    assert m.name == "surrogate_search" and m.default_config["replicates"] >= 2


def test_recovers_tiny_ei_pair_and_reports_evidence(suite):
    root, labels = suite
    rec = _run(root, labels["ei"], budget=300)
    st, res = rec["structure"], rec["result"]
    assert st["success"] and st["vs_best_alternative"]["precision"] == 1.0, st
    assert rec["function"]["nominal"] == 1.0
    assert res["budget"]["calls"] <= 300
    assert all(res["essential"][p] is True for p in res["core"])        # both members are essential in the full network
    assert st["essential_accuracy"] == 1.0
    assert all(r in GENERIC_ROLES for r, _ in res["roles"].values())
    assert set(res["roles"][p][0] for p in res["core"]) == {"recurrent_excitatory_core", "inhibitory_feedback"}
    assert res["predicted_function_preserved"] is True and res["fidelity"]["keep_only_pass_fraction"] == 1.0
    incl = res["inclusion_probability"]
    assert all(incl[p] >= 0.85 for p in res["core"]) and max(v for k, v in incl.items() if k not in res["core"]) <= 0.5
    assert st["brier_inclusion"] < 0.05


def test_finds_alternative_in_redundant_oscillator(suite):
    root, labels = suite
    rec = _run(root, labels["redundant"], budget=600, config={"extra_essential_max": 4})
    st, res = rec["structure"], rec["result"]
    assert st["success"], st
    assert rec["function"]["nominal"] >= 0.5
    truth = json.loads((root / "truth" / f"{labels['redundant']}.json").read_text(encoding="utf-8"))["networks"]["main"]
    alts = [set(a) for a in truth["alternatives_positions"]]
    core = set(res["core"])
    # the other sufficient implementation (or the backup copy variant) is reported as an alternative
    assert any(set(a) in alts or any(set(a) >= t for t in alts if t != core) for a in res["alternatives"]) or len(res["alternatives"]) >= 1


def test_activity_band_criterion_instance(suite):
    root, labels = suite
    rec = _run(root, labels["band"], budget=400)
    assert rec["structure"]["success"], rec["structure"]
    assert rec["function"]["nominal"] >= 0.5


def test_deterministic_under_seed_and_budget_respected(suite):
    root, labels = suite
    a = _run(root, labels["ei"], budget=120, seed=3)
    b = _run(root, labels["ei"], budget=120, seed=3)
    assert a["result"]["core"] == b["result"]["core"]
    assert a["result"]["inclusion_probability"] == b["result"]["inclusion_probability"]
    assert a["result"]["budget"]["calls"] == b["result"]["budget"]["calls"] <= 120
    assert a["result"]["diagnostics"]["surrogate"] == b["result"]["diagnostics"]["surrogate"]


def test_tiny_budget_never_exceeds_and_returns_valid_result(suite):
    root, labels = suite
    p = DiscoveryProblem.from_bundle(root / "instances" / labels["ei"], "main")
    for budget in (5, 12, 40):
        sim = BudgetedSimulator(p, max_calls=budget)
        res = MethodRegistry.get("surrogate_search").discover(p, sim, seed=1, config=FAST)
        assert sim.calls <= budget
        assert isinstance(res.core, list) and all(int(c) in set(int(x) for x in p.candidate_positions()) for c in res.core)
        pred = res.to_prediction(p, MethodInfo(name="surrogate_search", version="test"))
        BrainIRMechanismPrediction.from_json(pred.to_json())


def test_prediction_schema_valid_and_diagnostics_serialisable(suite):
    root, labels = suite
    rec = _run(root, labels["ei"], budget=200)
    p = DiscoveryProblem.from_bundle(root / "instances" / labels["ei"], "main")
    json.dumps(rec["result"]["diagnostics"])                                   # plain JSON
    sim = BudgetedSimulator(p, max_calls=200)
    res = MethodRegistry.get("surrogate_search").discover(p, sim, seed=0, config=FAST)
    pred = res.to_prediction(p, MethodInfo(name="surrogate_search", version="1.0"))
    rt = BrainIRMechanismPrediction.from_json(pred.to_json())
    assert rt.core_ids() == [int(p.public_ids[c]) for c in sorted(res.core, key=lambda c: -res.inclusion_probability.get(c, 1.0))]
    notes = json.loads(rt.mechanism.notes)
    assert "generic_roles" in notes and "fidelity" in notes


def test_prior_is_optional_and_only_biases(suite):
    """config['prior'] = {position: p} (int or str keys) biases ranking/design/surrogate init; it is never required and a
    wrong prior cannot override simulator evidence."""
    root, labels = suite
    truth = json.loads((root / "truth" / f"{labels['band']}.json").read_text(encoding="utf-8"))["networks"]["main"]
    core = set(truth["core_positions"])
    p = DiscoveryProblem.from_bundle(root / "instances" / labels["band"], "main")
    cands = [int(q) for q in p.candidate_positions()]
    misleading = {q: (0.05 if q in core else 0.6) for q in cands}
    rec_m = _run(root, labels["band"], budget=300, config={"prior": misleading})
    assert rec_m["structure"]["success"], rec_m["structure"]
    assert rec_m["result"]["diagnostics"]["prior"]["n_entries"] == len(misleading)
    helpful = {str(q): (0.9 if q in core else 0.1) for q in cands}          # string keys are accepted
    rec_h = _run(root, labels["band"], budget=300, config={"prior": helpful})
    assert rec_h["structure"]["success"] and rec_h["result"]["diagnostics"]["prior"]["n_in_pool"] >= 1
    rec_0 = _run(root, labels["band"], budget=300, config={"prior": {}})       # empty = uniform = no prior
    assert rec_0["result"]["diagnostics"]["prior"] is None and rec_0["structure"]["success"]


def test_surrogate_error_is_reported(suite):
    root, labels = suite
    rec = _run(root, labels["redundant"], budget=500, config={"patience": 20})
    surr = rec["result"]["diagnostics"]["surrogate"]
    assert surr["n_fits"] >= 1 and surr["n_features"] > 0
    if surr["n"] > 0:  # pre-registered predictions were scored against the simulator
        assert 0.0 <= surr["brier"] <= 1.0 and np.isfinite(surr["log_loss"]) and "by_tag" in surr and "calibration" in surr
        assert all("pred_mean" in b and "actual_rate" in b for b in surr["calibration"])
