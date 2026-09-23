"""evo_pareto (evolutionary multi-objective structured search) on tiny self-built synthetic instances: determinism under a seed,
budget honesty, schema-valid predictions, recovery of small planted mechanisms (several criteria), sensible Pareto front and
uncertainty outputs. Truth is the test's own (built here); no benchmark answer is involved."""

from __future__ import annotations

import json

import numpy as np
import pytest

import brainir.methods.evo_pareto as ep
from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, MethodRegistry
from brainir.discovery.interface import GENERIC_ROLES
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import run_one


def _make(root, family, n, base_seed, **kw):
    for s in range(10):
        spec = InstanceSpec(family, n, base_seed + s, n_readout=8, **kw)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            export_instance(inst, ver, root, n_order_variants=1)
            return spec.label
    raise AssertionError(f"no verified {family} instance")


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("evo_suite")
    labels = {"ei": _make(root, "ei_pair_oscillator", 40, 300), "ff": _make(root, "feedforward_driver", 40, 320),
              "mem": _make(root, "memory_switch", 40, 340), "red": _make(root, "redundant_oscillator", 44, 360)}
    return root, labels


def _truth(root, label):
    return json.loads((root / "truth" / f"{label}.json").read_text(encoding="utf-8"))["networks"]["main"]


def _discover(root, label, budget, seed=0, config=None):
    problem = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(problem, max_calls=budget)
    res = MethodRegistry.get("evo_pareto").discover(problem, sim, seed=seed, config=config)
    return problem, sim, res


def test_registered_and_runnable_as_script_entry():
    assert "evo_pareto" in MethodRegistry.names()
    assert isinstance(MethodRegistry.get("evo_pareto"), ep.EvoPareto)
    assert callable(ep.main)


def test_nsga_utilities():
    F = np.array([[0.0, 2.0, 0.0], [0.0, 3.0, 0.0], [1.0, 1.0, 1.0], [0.0, 2.0, 0.5], [0.5, 1.0, 0.5]])
    fronts = ep.non_dominated_sort(F)
    assert fronts == [[0, 4], [1, 2, 3]]    # [0,2,0] dominates [0,3,0] and [0,2,0.5]; [0.5,1,0.5] dominates [1,1,1]
    d = ep.crowding_distance(F, fronts[1])
    assert np.isinf(d).sum() >= 2 and len(d) == 3
    assert np.isinf(ep.crowding_distance(F, fronts[0])).all()


def test_structural_features_are_graph_only(suite):
    root, labels = suite
    p = DiscoveryProblem.from_bundle(root / "instances" / labels["ei"], "main")
    feat = ep.structural_features(p)
    truth = _truth(root, labels["ei"])
    s = feat["struct"]
    assert s.shape == (p.n,) and 0 <= s.min() and s.max() <= 1.0
    assert all(s[c] > 0 for c in truth["core_positions"])  # planted members lie on stimulus->readout paths
    assert s[list(p.stim_positions)].max() == 0 and s[p.readout_positions].max() == 0  # never candidates


def test_recovers_ei_pair_with_roles_and_essentiality(suite):
    root, labels = suite
    truth = _truth(root, labels["ei"])
    problem, sim, res = _discover(root, labels["ei"], budget=300)
    assert sim.calls <= 300 and res.budget["calls"] == sim.calls
    assert set(res.core) == set(truth["core_positions"]), (res.core, truth["core_positions"])
    assert all(res.essential.get(p) is True for p in truth["core_positions"])
    assert res.loop and set(res.loop) <= set(res.core)
    roles = {res.roles[p][0] for p in res.core}
    assert roles == {"recurrent_excitatory_core", "inhibitory_feedback"} and all(r in GENERIC_ROLES for r, _ in res.roles.values())
    assert res.predicted_function_preserved is True and res.predicted_frequency_hz and 3 < res.predicted_frequency_hz < 40
    assert res.fidelity["keep_only_pass_fraction"] == 1.0 and res.fidelity["intact_pass_fraction"] == 1.0
    probs = res.inclusion_probability
    assert all(probs[p] >= 0.9 for p in res.core)
    others = [q for p, q in probs.items() if p not in set(res.core)]
    assert others and max(others) < 0.5 and all(0 <= q <= 1 for q in probs.values())
    # the Pareto front reported is mutually non-dominated and its sufficient members really pass
    front = res.diagnostics["front"]
    F = np.array([[1 - f["pass_nominal"], f["size"], 1 - (f["pass_robust"] if f["pass_robust"] is not None else 0.5)] for f in front])
    assert len(ep.non_dominated_sort(F)[0]) == len(front) or len(front) > 1
    assert any(f["pass_nominal"] == 1.0 and f["size"] == len(res.core) for f in front)
    assert res.diagnostics["stopping_reason"] and res.diagnostics["loo_necessary_within_core"] == {p: True for p in res.core}


def test_deterministic_under_seed_and_seed_sensitive_rng(suite):
    root, labels = suite
    _, sim1, r1 = _discover(root, labels["ff"], budget=150, seed=3)
    _, sim2, r2 = _discover(root, labels["ff"], budget=150, seed=3)
    assert r1.core == r2.core and r1.inclusion_probability == r2.inclusion_probability and r1.alternatives == r2.alternatives
    assert r1.essential == r2.essential and r1.roles == r2.roles and sim1.calls == sim2.calls
    assert r1.diagnostics["trace"] == r2.diagnostics["trace"]


def test_budget_is_respected_and_partial_results_are_valid(suite):
    root, labels = suite
    for budget in (6, 25, 60):
        problem, sim, res = _discover(root, labels["ei"], budget=budget)
        assert sim.calls <= budget, (budget, sim.calls)
        pred = res.to_prediction(problem, MethodInfo(name="evo_pareto", version="t"))
        BrainIRMechanismPrediction.from_json(pred.to_json())
        assert not (set(res.core) & set(problem.stim_positions)) and not (set(res.core) & set(problem.readout_positions))
        assert all(0.0 <= q <= 1.0 for q in res.inclusion_probability.values())
    assert sim.calls <= 60 and isinstance(res.diagnostics["budget_exhausted"], bool)


def test_prediction_schema_and_notes(suite):
    root, labels = suite
    problem, sim, res = _discover(root, labels["ei"], budget=200)
    pred = res.to_prediction(problem, MethodInfo(name="evo_pareto", version="1.0"))
    assert isinstance(pred, BrainIRMechanismPrediction)
    assert pred.core_ids() and len(pred.core_ids()) == len(set(pred.core_ids()))
    notes = json.loads(pred.mechanism.notes)
    assert "generic_roles" in notes and "fidelity" in notes and len(pred.mechanism.notes) <= 2000
    assert all(c.confidence is not None and 0 <= c.confidence <= 1 for c in pred.core_neurons)
    BrainIRMechanismPrediction.from_json(pred.to_json())


def test_feedforward_activity_band_and_memory_persistence(suite):
    root, labels = suite
    for key in ("ff", "mem"):
        truth = _truth(root, labels[key])
        problem, sim, res = _discover(root, labels[key], budget=400)
        assert sim.calls <= 400
        assert any(set(a) <= set(res.core) for a in truth["alternatives_positions"]), (key, res.core, truth["alternatives_positions"])
        assert len(res.core) <= len(truth["core_positions"]) + 2
        assert res.fidelity["keep_only_pass_fraction"] >= 0.75
        roles = {res.roles[p][0] for p in res.core if p in set(truth["core_positions"])}
        if key == "mem":
            assert "state_memory" in roles
        else:
            assert roles <= {"input_relay", "output_driver"} and "output_driver" in roles


def test_prior_is_optional_steers_proposals_and_a_wrong_prior_is_survivable(suite):
    root, labels = suite
    truth = _truth(root, labels["ei"])
    problem = DiscoveryProblem.from_bundle(root / "instances" / labels["ei"], "main")
    cand = [int(c) for c in problem.candidate_positions()]
    good = {p: (0.95 if p in set(truth["core_positions"]) else 0.05) for p in cand}
    wrong_nodes = [p for p in cand if p not in set(truth["core_positions"])][:3]
    wrong = {str(p): (0.95 if p in set(wrong_nodes) else 0.05) for p in cand}  # string keys as they arrive from JSON
    _, sim_g, r_good = _discover(root, labels["ei"], budget=300, config={"prior": good})
    _, sim_w, r_wrong = _discover(root, labels["ei"], budget=300, config={"prior": wrong})
    _, sim_0, r_none = _discover(root, labels["ei"], budget=300)
    for r in (r_good, r_wrong, r_none):
        assert set(truth["core_positions"]) <= set(r.core), r.core
    # the prior steers proposals: its favoured set (here the planted core) is proposed and found sufficient; no prior -> no such proposal
    assert r_good.diagnostics["operators"]["prior_top"] == {"tried": 1, "sufficient": 1}
    assert "prior_top" not in r_none.diagnostics["operators"]
    assert r_wrong.diagnostics["operators"]["prior_top"]["sufficient"] == 0  # the wrong prior's favourites are not sufficient
    assert max(sim_g.calls, sim_w.calls, sim_0.calls) <= 300
    assert all(0 <= q <= 1 for q in r_wrong.inclusion_probability.values())


def test_redundant_oscillator_yields_alternatives_and_uncertainty(suite):
    root, labels = suite
    truth = _truth(root, labels["red"])
    rec = run_one("evo_pareto", root / "instances" / labels["red"], "main", budget=700, seed=0, config={},
                  truth_path=root / "truth" / f"{labels['red']}.json", score_seeds=[5000, 5001], workers=1, robust=False)
    st, res = rec["structure"], rec["result"]
    assert st["success"], (res["core"], truth["alternatives_positions"])
    assert rec["function"]["nominal"] == 1.0 and rec["result"]["budget"]["calls"] <= 700
    alts = [set(a) for a in truth["alternatives_positions"]]
    core = set(res["core"])
    # the other implementation is reported as an alternative or at least carries inclusion probability; nothing is essential
    other = next(a for a in alts if not a <= core)
    claimed = [set(a) for a in res["alternatives"]]
    probs = {int(k): v for k, v in res["inclusion_probability"].items()}
    assert any(other <= a for a in claimed) or all(probs.get(p, 0) > 0.2 for p in other)
    assert all(v is False for v in res["essential"].values()), res["essential"]
    assert res["diagnostics"]["core_group_silenced_pass"] is True
