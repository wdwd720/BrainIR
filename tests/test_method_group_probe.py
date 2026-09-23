"""The ``group_probe`` discovery method on the developer's own tiny synthetic mechanisms: deterministic under the seed,
budget-honest, schema-valid, and recovers plain, redundant, feed-forward and competitive mechanisms."""

from __future__ import annotations

import json

import pytest

import brainir.methods.group_probe as gp
from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, MethodRegistry, keep_only
from brainir.discovery.interface import GENERIC_ROLES
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance


def _make(root, family: str, n: int, seed0: int, n_readout: int = 8):
    """Build a verified tiny instance (the first seed whose truth verifies by simulation)."""
    for s in range(seed0, seed0 + 8):
        spec = InstanceSpec(family, n, s, n_readout=n_readout)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            export_instance(inst, ver, root, n_order_variants=1)
            truth = json.loads((root / "truth" / f"{spec.label}.json").read_text(encoding="utf-8"))["networks"]["main"]
            return DiscoveryProblem.from_bundle(root / "instances" / spec.label, "main"), truth
    raise AssertionError(f"no verified {family} instance")


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("gp_suite")
    return {"ei_pair": _make(root, "ei_pair_oscillator", 40, 7000), "redundant": _make(root, "redundant_oscillator", 40, 7000),
            "feedforward": _make(root, "feedforward_driver", 40, 7000), "wta": _make(root, "winner_take_all", 50, 7000)}


def _run(problem, budget: int, seed: int = 0, config: dict | None = None):
    sim = BudgetedSimulator(problem, max_calls=budget)
    method = MethodRegistry.get("group_probe")
    res = method.discover(problem, sim, seed=seed, config={**method.default_config, **(config or {})})
    return res, sim


def test_registered_and_recovers_ei_pair_with_valid_prediction(suite):
    problem, truth = suite["ei_pair"]
    assert isinstance(MethodRegistry.get("group_probe"), gp.GroupProbe)
    res, sim = _run(problem, 300)
    assert sim.calls <= 300 and res.budget["calls"] == sim.calls
    assert sorted(res.core) == sorted(truth["core_positions"])
    assert all(res.essential[p] is True for p in res.core)  # both members are essential in the truth
    assert all(res.inclusion_probability[p] > 0.9 for p in res.core)
    others = [q for p, q in res.inclusion_probability.items() if p not in set(res.core)]
    assert others and max(others) < 0.5
    assert set(res.inclusion_probability) == set(int(p) for p in problem.candidate_positions())
    assert {res.roles[p][0] for p in res.core} == {"recurrent_excitatory_core", "inhibitory_feedback"}
    assert all(r in GENERIC_ROLES for r, _ in res.roles.values())
    assert res.fidelity["keep_only_pass_fraction_fresh"] == 1.0 and res.predicted_function_preserved is True
    assert res.predicted_frequency_hz is not None and 5 < res.predicted_frequency_hz < 30
    # the reported core really is sufficient on unseen seeds (independent simulator)
    check = BudgetedSimulator(problem, max_calls=10)
    assert check.pass_fraction(keep_only(problem, res.core), [77, 78]) == 1.0
    pred = res.to_prediction(problem, MethodInfo(name="group_probe", version="test"))
    assert isinstance(pred, BrainIRMechanismPrediction)
    again = BrainIRMechanismPrediction.from_json(pred.to_json())
    assert again.core_ids() == [int(problem.public_ids[p]) for p in sorted(res.core, key=lambda p: -res.inclusion_probability[p])]
    notes = json.loads(pred.mechanism.notes)
    assert "generic_roles" in notes and "budget" in notes
    # far fewer simulations than one single-deletion pass over every candidate on the working seeds
    assert sim.calls < res.diagnostics["single_deletion_equivalent_calls"]


def test_deterministic_under_seed_and_seed_sensitive(suite):
    problem, _ = suite["ei_pair"]
    r1, s1 = _run(problem, 200)
    r2, s2 = _run(problem, 200)
    assert r1.core == r2.core and s1.calls == s2.calls
    assert r1.inclusion_probability == r2.inclusion_probability and r1.essential == r2.essential and r1.alternatives == r2.alternatives
    r3, _ = _run(problem, 200, seed=3)
    assert r3.diagnostics["working_seeds"] != r1.diagnostics["working_seeds"]
    assert sorted(r3.core) == sorted(r1.core)  # a different parameter ensemble finds the same mechanism


def test_budget_is_respected_and_result_is_always_valid(suite):
    problem, truth = suite["ei_pair"]
    for budget in (1, 4, 12, 30):
        res, sim = _run(problem, budget)
        assert sim.calls <= budget
        assert res.diagnostics["budget_exhausted"] or budget >= 30
        pred = res.to_prediction(problem, MethodInfo(name="group_probe", version="test"))
        BrainIRMechanismPrediction.from_json(pred.to_json())
        if res.core and not res.diagnostics["budget_exhausted"]:
            assert sorted(res.core) == sorted(truth["core_positions"])
    # a mid-sized budget that ends inside the elimination still returns a verified superset of the mechanism
    res, sim = _run(problem, 14)
    assert sim.calls <= 14
    if res.core:
        assert set(truth["core_positions"]) <= set(res.core)


def test_redundant_mechanism_reports_alternative_and_no_essential_member(suite):
    problem, truth = suite["redundant"]
    res, sim = _run(problem, 400)
    alts = [sorted(a) for a in truth["alternatives_positions"]]
    assert sorted(res.core) in alts
    assert all(res.essential[p] is False for p in res.core)
    other = [a for a in alts if a != sorted(res.core)][0]
    assert other in [sorted(a) for a in res.alternatives]
    assert all(res.roles[p][0] == "redundant_backup" for p in other)
    assert all(0 < res.inclusion_probability[p] < res.inclusion_probability[res.core[0]] for p in other)
    assert sim.calls <= 400


def test_feedforward_chain_roles_under_activity_band(suite):
    problem, truth = suite["feedforward"]
    res, sim = _run(problem, 300)
    assert sorted(res.core) == sorted(truth["core_positions"])
    roles = {p: res.roles[p][0] for p in res.core}
    assert sorted(roles.values()) == ["input_relay", "input_relay", "output_driver"]
    assert all(roles[int(p)] == r for p, r in truth["roles_positions"].items())
    assert problem.criterion_spec["type"] == "activity_band" and res.predicted_frequency_hz is None


def test_context_member_found_by_necessity_screen(suite):
    """Winner-take-all: the winner alone passes every keep-only probe (its competitor is removed by the probe), so the
    lateral-inhibition neuron is only visible to full-network silencing."""
    problem, truth = suite["wta"]
    res, sim = _run(problem, 400)
    assert sorted(res.core) == sorted(truth["core_positions"])
    assert res.diagnostics["context_members"] and set(res.diagnostics["context_members"]) <= set(res.core)
    assert all(res.essential[p] is True for p in res.core)
    assert {res.roles[p][0] for p in res.core} == {"output_driver", "lateral_inhibition"}
    # switching the screen off reproduces the sufficiency-only answer: the winner alone
    res0, _ = _run(problem, 400, config={"necessity_share": 0.0})
    assert set(res0.core) < set(res.core)


def test_external_prior_is_optional_and_biases_ordering_only(suite):
    """config['prior'] = {position: p} (e.g. transferred from another network) reorders and lifts candidates; a wrong
    prior costs probes but never changes the verified answer, and JSON string keys are accepted."""
    problem, truth = suite["ei_pair"]
    base, _ = _run(problem, 300)
    core = sorted(truth["core_positions"])
    distractor = next(int(p) for p in problem.candidate_positions() if int(p) not in set(core))
    good, s_good = _run(problem, 300, config={"prior": {str(core[0]): 0.9, str(core[1]): 0.8}})
    bad, s_bad = _run(problem, 300, config={"prior": {distractor: 0.95}})
    assert sorted(good.core) == core and sorted(bad.core) == core and sorted(base.core) == core
    assert good.diagnostics["external_prior"]["n_given"] == 2 and bad.diagnostics["external_prior"]["n_candidates_covered"] == 1
    assert "external_prior" not in base.diagnostics
    assert bad.inclusion_probability[distractor] < 0.1  # the wrong prior is overturned by the probes
    # a correct prior never costs more probes than the structural ordering
    assert s_good.calls <= base.budget["calls"]


def test_posterior_updates_and_group_acquisition():
    post = gp.Posterior({1: 0.1, 2: 0.1, 3: 0.1, 4: 0.6}, {1: 0, 2: 1, 3: 2, 4: 3}, 0.02, 0.05)
    g = post.pick_group([1, 2, 3, 4])
    assert 4 not in g and g == [1, 2, 3]  # 0.9^3 = 0.73 is closer to 1/2 than 0.9^2 = 0.81; the likely member is probed alone
    assert post.pick_group([4]) == [4]
    post.update([1, 2, 3], passed=True)
    assert max(post.q[i] for i in (1, 2, 3)) < 0.01
    post.update([4], passed=False)
    assert post.q[4] > 0.95
    post.update([4], passed=False, conf=0.5)  # disagreeing seeds: weaker evidence, still upward
    assert post.q[4] > 0.95
    q_before = post.q[2]
    post.update([2, 3], passed=False)  # a fail raises both, symmetrically
    assert post.q[2] > q_before and post.q[2] == pytest.approx(post.q[3])
