"""cem_search on the developer's own tiny synthetic instances (truth known here, never inside the method): determinism under
seed, budget honesty, schema-valid predictions, recovery of small mechanisms including one with two alternative
implementations whose inclusion probabilities must reflect the ambiguity."""

from __future__ import annotations

import json

import numpy as np
import pytest

import brainir.methods.cem_search as cem
from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, MethodRegistry
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import run_one, score_structure


def _make(root, family, n, seed, complications=(), n_readout=8):
    for s in range(seed, seed + 8):
        spec = InstanceSpec(family, n, s, tuple(complications), n_readout=n_readout)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            export_instance(inst, ver, root, n_order_variants=1)
            return spec.label
    raise AssertionError(f"no verified {family} instance")


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("cem_suite")
    labels = {"ei": _make(root, "ei_pair_oscillator", 40, 300), "two": _make(root, "two_implementations", 50, 310),
              "ff": _make(root, "feedforward_driver", 40, 320), "mem": _make(root, "memory_switch", 40, 330),
              "auto": _make(root, "two_implementations", 60, 340, ("autonomous_module",)), "wta": _make(root, "winner_take_all", 40, 350)}
    return root, labels


def _truth(root, label):
    return json.loads((root / "truth" / f"{label}.json").read_text(encoding="utf-8"))["networks"]["main"]


def _discover(root, label, budget, seed=0, config=None):
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(p, max_calls=budget)
    res = MethodRegistry.get("cem_search").discover(p, sim, seed=seed, config=config)
    return p, sim, res


def test_registered_with_generic_defaults():
    assert "cem_search" in MethodRegistry.names()
    m = MethodRegistry.get("cem_search")
    assert isinstance(m, cem.CemSearch) and m.default_config["q_init"] > 0.5
    # no hard-coded mechanism size anywhere in the configuration
    assert not any(k in ("k", "size", "n_core") for k in m.default_config)


def test_recovers_ei_pair_deterministically_within_budget(suite):
    root, labels = suite
    label = labels["ei"]
    truth = _truth(root, label)
    p, sim, res = _discover(root, label, budget=300)
    assert sim.calls <= 300 and res.budget["calls"] == sim.calls
    assert sorted(res.core) == sorted(truth["core_positions"])
    assert all(res.inclusion_probability[c] > 0.9 for c in res.core)
    # non-members carry little probability; every candidate is assessed
    others = [q for k, q in res.inclusion_probability.items() if k not in set(res.core)]
    assert len(res.inclusion_probability) == len(p.candidate_positions()) and max(others) < 0.2
    for pos, ess in truth["essential_positions"].items():
        assert res.essential[int(pos)] == bool(ess)
    assert set(r for r, _ in res.roles.values()) <= set(cem.GENERIC_ROLES)
    assert res.predicted_function_preserved is True and res.fidelity["keep_only_pass_fraction"] >= 0.5
    # dynamics claims come from the intact network (stage-0 runs); the core's own rhythm is kept in the fidelity record
    assert res.diagnostics["dynamics_source"] == "intact" and res.predicted_frequency_hz and res.fidelity["core_frequency_hz"] > 0
    assert res.loop and set(res.loop) <= set(res.core)
    # deterministic under the seed: a fresh simulator, same seed -> identical result
    _, _, res2 = _discover(root, label, budget=300)
    assert res2.core == res.core and res2.alternatives == res.alternatives and res2.essential == res.essential
    assert res2.inclusion_probability == res.inclusion_probability and res2.roles == res.roles
    # schema-valid prediction with a JSON round trip
    pred = res.to_prediction(p, MethodInfo(name="cem_search", version="test"))
    BrainIRMechanismPrediction.from_json(pred.to_json())
    assert pred.core_ids() == [int(p.public_ids[c]) for c in sorted(res.core, key=lambda c: -res.inclusion_probability[c])]
    notes = json.loads(pred.mechanism.notes)
    assert "generic_roles" in notes and "fidelity" in notes


def test_two_implementations_reports_alternative_and_ambiguous_probabilities(suite):
    root, labels = suite
    label = labels["two"]
    truth = _truth(root, label)
    alts = [set(a) for a in truth["alternatives_positions"]]
    p, sim, res = _discover(root, label, budget=500)
    assert sim.calls <= 500
    core = set(res.core)
    assert core in alts, (core, alts)
    other = next(a for a in alts if a != core)
    assert any(set(a) == other for a in res.alternatives), (res.alternatives, other)
    pc = [res.inclusion_probability[c] for c in core]
    po = [res.inclusion_probability[c] for c in other]
    # ambiguity: the core is favoured but not certain; the other implementation keeps substantial mass; distractors do not
    assert min(pc) > max(po) and min(pc) < 0.95 and min(po) > 0.15
    rest = [q for k, q in res.inclusion_probability.items() if k not in core | other]
    assert max(rest) < 0.2
    # nothing is essential when two implementations coexist (full-network silencing keeps the function)
    assert all(res.essential[c] is False for c in core)
    assert all(res.roles[c][0] == "redundant_backup" for c in other)
    s = score_structure(res, truth)
    assert s["success"] and s["vs_best_alternative"]["recall"] == 1.0


def test_tiny_budget_returns_partial_result_without_exceeding(suite):
    root, labels = suite
    for budget in (4, 12):
        p, sim, res = _discover(root, labels["two"], budget=budget)
        assert sim.calls <= budget
        assert isinstance(res.core, list) and all(int(c) in set(p.candidate_positions()) for c in res.core)
        assert res.diagnostics["budget_at_start"] == budget
        res.to_prediction(p, MethodInfo(name="cem_search", version="test"))  # still schema-valid


def test_other_criteria_families_are_recovered(suite):
    root, labels = suite
    for key in ("ff", "mem"):
        label = labels[key]
        truth = _truth(root, label)
        p, sim, res = _discover(root, label, budget=300)
        s = score_structure(res, truth)
        assert s["success"], (key, res.core, truth["alternatives_positions"])
        assert s["vs_best_alternative"]["precision"] == 1.0
        roles = {res.roles[c][0] for c in res.core}
        if key == "mem":
            assert roles == {"state_memory"}
        else:
            assert roles <= {"input_relay", "output_driver"} and "output_driver" in roles


def test_winner_take_all_needs_context_necessity(suite):
    """Keep-only alone accepts the winning pool without its interneuron (keep-only removes the competitor anyway); silencing in the
    intact network puts the interneuron back into the core and drops keep-only-only alternatives."""
    root, labels = suite
    label = labels["wta"]
    truth = _truth(root, label)
    p, sim, res = _discover(root, label, budget=300)
    assert sim.calls <= 300
    assert sorted(res.core) == sorted(truth["core_positions"]), (res.core, truth["core_positions"], res.diagnostics["context"])
    assert res.alternatives == [] and res.diagnostics["context"]["core_necessary"] is True
    for pos, ess in truth["essential_positions"].items():
        assert res.essential[int(pos)] == bool(ess)
    assert {res.roles[c][0] for c in res.core} == {"output_driver", "lateral_inhibition"}
    assert min(res.inclusion_probability[c] for c in res.core) > 0.6


def test_structural_pool_excludes_autonomous_module_and_unreachable(suite):
    root, labels = suite
    label = labels["auto"]
    truth = _truth(root, label)
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    pool, d_s, d_r = cem.structural_pool(p)
    module = set(truth["complication_positions"]["autonomous_module"])
    assert not (module & set(int(x) for x in pool))  # no path to the readout -> excluded without a single simulation
    for a in truth["alternatives_positions"]:
        assert set(a) <= set(int(x) for x in pool)
    assert d_s[list(p.stim_positions)].tolist() == [0] and (d_r[p.readout_positions] == 0).all()


def test_external_prior_is_optional_and_only_biases(suite):
    """config['prior'] = {position: p} biases the initial sampling distribution; a misleading prior must not prevent recovery."""
    root, labels = suite
    label = labels["ei"]
    truth = _truth(root, label)
    core = set(truth["core_positions"])
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    # misleading prior: low on the true members, high on distractors (string keys as they arrive from JSON)
    prior = {str(int(c)): 0.05 for c in core}
    prior.update({str(int(c)): 0.95 for c in p.candidate_positions() if int(c) not in core})
    _, sim, res = _discover(root, label, budget=300, config={"prior": prior})
    assert sim.calls <= 300 and set(res.core) == core
    assert res.diagnostics["external_prior"]["strength"] == 0.5
    # a supportive prior gives the same mechanism; no prior at all is the documented default
    _, _, res2 = _discover(root, label, budget=300, config={"prior": {int(c): 1.0 for c in core}})
    assert set(res2.core) == core and res2.diagnostics["external_prior"]["n_given_in_pool"] >= 1
    _, _, res3 = _discover(root, label, budget=300, config={"prior": None})
    assert set(res3.core) == core and "external_prior" not in res3.diagnostics


def test_runs_through_the_tournament_harness(suite):
    root, labels = suite
    label = labels["ei"]
    rec = run_one("cem_search", root / "instances" / label, "main", budget=200, seed=1, config=None, truth_path=root / "truth" / f"{label}.json",
                  score_seeds=[9], workers=1, robust=False)
    assert rec["structure"]["success"] and rec["function"]["nominal"] == 1.0 and rec["result"]["budget"]["calls"] <= 200
    assert rec["structure"]["brier_inclusion"] < 0.05
    assert not np.isnan(rec["structure"]["brier_inclusion"])
