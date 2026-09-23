"""greedy_plus (intervention-guided group elimination) on tiny synthetic instances whose truth is generated here:
determinism under the seed, budget honesty, valid prediction schema, recovery of the planted mechanism (unique
mechanism, redundant alternatives, an essential-but-not-sufficiency-necessary member), the run entry point."""

from __future__ import annotations

import json

import numpy as np
import pytest

import brainir.methods.greedy_plus as gp  # registers the method
from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, MethodRegistry, keep_only
from brainir.discovery.run import main as run_main
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import run_one


def _make(root, family: str, n: int, complications=(), n_readout: int = 8, first_seed: int = 0):
    """Export the first verified instance of the family (a tiny background can sit at the criterion threshold)."""
    for s in range(first_seed, first_seed + 10):
        spec = InstanceSpec(family, n, s, tuple(complications), n_readout=n_readout)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            export_instance(inst, ver, root, n_order_variants=2)
            truth = json.loads((root / "truth" / f"{spec.label}.json").read_text(encoding="utf-8"))
            return root / "instances" / spec.label, truth
    raise AssertionError(f"no verified {family} instance")


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("gp_suite")
    return {"ei": _make(root, "ei_pair_oscillator", 40), "red": _make(root, "redundant_oscillator", 44),
            "wta": _make(root, "winner_take_all", 40), "root": root}


def _discover(inst_dir, network: str, budget: int, seed: int, config: dict | None = None):
    problem = DiscoveryProblem.from_bundle(inst_dir, network)
    sim = BudgetedSimulator(problem, max_calls=budget)
    method = MethodRegistry.get("greedy_plus")
    res = method.discover(problem, sim, seed=seed, config=config)
    return problem, sim, res


def test_registered_and_helpers():
    assert "greedy_plus" in MethodRegistry.names()
    assert isinstance(MethodRegistry.get("greedy_plus"), gp.GreedyPlus)
    assert gp.majority_rule(1) == (1, 0) and gp.majority_rule(2) == (2, 0) and gp.majority_rule(3) == (2, 1) and gp.majority_rule(4) == (3, 1)


def test_structural_pruning_is_exact_on_the_planted_mechanism(suite):
    inst_dir, truth = suite["ei"]
    p = DiscoveryProblem.from_bundle(inst_dir, "main")
    ok, dropped = gp.structural_candidates(p)
    core = set(truth["networks"]["main"]["core_positions"])
    assert core <= ok and not (core & dropped)
    assert ok | dropped == set(int(x) for x in p.candidate_positions())
    # a neuron without any outgoing weight can never influence the readout
    W = p.W.tocsc()
    no_out = {int(j) for j in range(p.n) if W.indptr[j + 1] == W.indptr[j]} & set(int(x) for x in p.candidate_positions())
    assert no_out <= dropped


def test_recovers_unique_mechanism_with_roles_and_essentiality(suite):
    inst_dir, truth = suite["ei"]
    tn = truth["networks"]["main"]
    problem, sim, res = _discover(inst_dir, "main", budget=400, seed=0)
    assert sorted(res.core) == sorted(tn["core_positions"]), (res.core, tn["core_positions"])
    assert sim.calls <= 400 and res.budget["calls"] == sim.calls
    assert res.fidelity["keep_only_pass_fraction"] >= 0.5 and res.predicted_function_preserved is True
    assert res.predicted_frequency_hz is not None and res.predicted_frequency_hz > 0
    for p in res.core:  # essential claims agree with the simulation-verified truth
        assert res.essential[p] == tn["essential_positions"][str(p)]
        assert res.inclusion_probability[p] >= 0.9
    # every candidate has a probability; non-members are low
    assert set(res.inclusion_probability) == set(int(x) for x in problem.candidate_positions())
    others = [q for p, q in res.inclusion_probability.items() if p not in set(res.core)]
    assert max(others) <= 0.2
    roles = {tn["roles_positions"][str(p)] for p in res.core}
    assert {r for r, _ in res.roles.values() if r != "redundant_backup"} == roles  # E -> recurrent core, I -> inhibitory feedback
    assert sorted(res.loop) == sorted(res.core)
    assert res.diagnostics["oracle"]["budget_exhausted"] is False
    assert "errors" not in res.diagnostics  # no late-phase failure was swallowed


def test_deterministic_under_seed_and_order_variant_independent(suite):
    inst_dir, truth = suite["ei"]
    _, _, r1 = _discover(inst_dir, "main", budget=400, seed=3)
    _, _, r2 = _discover(inst_dir, "main", budget=400, seed=3)  # fresh simulator, fresh cache
    assert r1.core == r2.core and r1.inclusion_probability == r2.inclusion_probability and r1.essential == r2.essential
    assert r1.alternatives == r2.alternatives and r1.budget["calls"] == r2.budget["calls"]
    # the same neurons are found on a permuted copy of the graph
    _, _, r3 = _discover(inst_dir, "order1", budget=400, seed=3)
    perm0, perm1 = np.array(truth["networks"]["main"]["perm"]), np.array(truth["networks"]["order1"]["perm"])
    inv1 = np.empty_like(perm1); inv1[perm1] = np.arange(len(perm1))
    to_order1 = inv1[perm0]
    assert sorted(int(to_order1[p]) for p in r1.core) == sorted(r3.core)


def test_alternatives_and_essential_only_member(suite):
    inst_dir, truth = suite["red"]
    tn = truth["networks"]["main"]
    _, _, res = _discover(inst_dir, "main", budget=500, seed=0)
    alts = [sorted(a) for a in tn["alternatives_positions"]]
    assert sorted(res.core) in alts, (res.core, alts)
    found = [sorted(a) for a in res.alternatives]
    assert any(a in alts and a != sorted(res.core) for a in found), (found, alts)  # the other E-I pair is reported as an alternative
    assert all(res.essential[p] is False for p in res.core)  # either pair suffices: nobody is essential
    assert "errors" not in res.diagnostics
    assert not any(set(res.core) < set(a) for a in found)  # non-minimal supersets of the core are not reported as alternatives
    for a in found:
        for p in a:
            if p not in set(res.core):
                assert 0.05 <= res.inclusion_probability[p] <= 0.6
    # winner-take-all: the lateral inhibitor is essential in the full network although keep-only of the winner alone passes
    inst_dir, truth = suite["wta"]
    tn = truth["networks"]["main"]
    _, _, res = _discover(inst_dir, "main", budget=500, seed=0)
    assert sorted(res.core) == sorted(tn["core_positions"]), (res.core, tn["core_positions"])
    assert res.diagnostics["essential_screen"]["found"]
    assert all(res.essential[p] for p in res.core)
    assert {res.roles[p][0] for p in res.core} == {"output_driver", "lateral_inhibition"}


def test_budget_is_respected_and_partial_results_are_valid(suite):
    inst_dir, truth = suite["red"]
    tn = truth["networks"]["main"]
    for budget in (6, 12, 25):
        problem, sim, res = _discover(inst_dir, "main", budget=budget, seed=1)
        assert sim.calls <= budget
        assert res.core  # a passing superset of a mechanism is returned even when the elimination could not finish
        assert any(set(a) <= set(res.core) for a in tn["alternatives_positions"])
        if budget >= 12:  # the partial core still performs the function (checked with a fresh, independent simulator)
            assert BudgetedSimulator(problem, max_calls=10).pass_fraction(keep_only(problem, res.core), [7, 8]) >= 0.5
        pred = res.to_prediction(problem, MethodInfo(name="greedy_plus", version="test"))
        BrainIRMechanismPrediction.from_json(pred.to_json())
        assert len(pred.mechanism.notes) <= 2000


def test_prediction_schema_and_run_entry_point(suite, tmp_path):
    inst_dir, truth = suite["ei"]
    out = tmp_path / "pred.json"
    rj = tmp_path / "result.json"
    rc = run_main(["--method", "greedy_plus", "--bundle", str(inst_dir), "--network", "main", "--out", str(out), "--budget", "300", "--seed", "0",
                   "--result-json", str(rj)])
    assert rc == 0 and out.exists()
    pred = BrainIRMechanismPrediction.from_json(out.read_text(encoding="utf-8"))
    assert pred.method.name == "greedy_plus" and pred.core_ids() and pred.dynamics.rhythmic is True
    notes = json.loads(pred.mechanism.notes)
    assert "generic_roles" in notes and "fidelity" in notes and notes["budget"]["calls"] <= 300
    res = json.loads(rj.read_text(encoding="utf-8"))
    assert sorted(res["core"]) == sorted(truth["networks"]["main"]["core_positions"])
    assert all(c.confidence is not None and 0 <= c.confidence <= 1 for c in pred.core_neurons)


def test_optional_prior_orders_the_search_but_never_decides(suite):
    inst_dir, truth = suite["ei"]
    tn = truth["networks"]["main"]
    problem = DiscoveryProblem.from_bundle(inst_dir, "main")
    cand = [int(x) for x in problem.candidate_positions()]
    core = set(tn["core_positions"])
    # a misleading prior (high on non-members, low on the true members) still yields the true mechanism
    bad_prior = {str(p): (0.05 if p in core else 0.9) for p in cand}
    _, sim, res = _discover(inst_dir, "main", budget=400, seed=0, config={"prior": bad_prior})
    assert sorted(res.core) == sorted(core) and res.diagnostics["prior_used"] is True and sim.calls <= 400
    assert all(res.inclusion_probability[p] >= 0.9 for p in res.core)
    # ordering helper: low prior first (ascending), high prior first (descending); uniform without a prior
    prior = {1: 0.9, 2: 0.1, 3: 0.5}
    assert gp.ordered([1, 2, 3], np.random.default_rng(0), prior, jitter=0.0) == [2, 3, 1]
    assert gp.ordered([1, 2, 3], np.random.default_rng(0), prior, jitter=0.0, descending=True) == [1, 3, 2]
    assert sorted(gp.ordered([1, 2, 3], np.random.default_rng(0), None)) == [1, 2, 3]
    assert gp.parse_prior({"1": 0.5, "x": 0.2, "2": 5.0, "99999": 0.1}, frozenset({1, 2})) == {1: 0.5, 2: 1.0}
    assert gp.parse_prior(None, frozenset({1})) is None and gp.parse_prior({}, frozenset({1})) is None


def test_scored_by_the_tournament(suite):
    inst_dir, truth = suite["ei"]
    rec = run_one("greedy_plus", inst_dir, "main", budget=300, seed=0, config=None, truth_path=suite["root"] / "truth" / f"{inst_dir.name}.json",
                  score_seeds=[9], workers=1, robust=False)
    assert rec["structure"]["success"] and rec["structure"]["vs_best_alternative"]["precision"] == 1.0
    assert rec["function"]["nominal"] == 1.0 and rec["structure"]["brier_inclusion"] < 0.05
    assert rec["structure"]["role_accuracy"] == 1.0 and rec["structure"]["essential_accuracy"] == 1.0
