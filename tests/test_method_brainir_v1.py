"""brainir_v1 on tiny synthetic instances whose truth is generated here: registration and switches, recovery of mechanisms of four
criterion types (rhythm, selectivity, activity band, persistence), determinism under the seed and node-order independence, explicit
tied alternatives with shared probability, context members found by full-network necessity, budget honesty at tiny budgets, every
ablation switch runs within the budget, the optional prior only orders the search, cross-connectome claims on a tiny pair with a
separately reported auxiliary budget, a schema-valid prediction and the run entry point."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

import brainir.methods.brainir_v1 as v1  # registers the method
from brainir.benchmark.prediction import BrainIRMechanismPrediction, MethodInfo
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, MethodRegistry, keep_only
from brainir.discovery.interface import GENERIC_ROLES
from brainir.discovery.run import main as run_main
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.synthetic_pairs import PairSpec, build_pair, export_pair, verify_pair


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
    root = tmp_path_factory.mktemp("v1_suite")
    return {"ei": _make(root, "ei_pair_oscillator", 40, first_seed=500), "red": _make(root, "redundant_oscillator", 44, first_seed=510),
            "wta": _make(root, "winner_take_all", 40, first_seed=520), "ff": _make(root, "feedforward_driver", 40, first_seed=530),
            "mem": _make(root, "memory_switch", 40, first_seed=540), "root": root}


def _discover(inst_dir, network: str, budget: int, seed: int, config: dict | None = None):
    problem = DiscoveryProblem.from_bundle(inst_dir, network)
    sim = BudgetedSimulator(problem, max_calls=budget)
    method = MethodRegistry.get("brainir_v1")
    res = method.discover(problem, sim, seed=seed, config=config)
    return problem, sim, res


def _success(core, tn: dict) -> bool:
    return any(set(a) <= set(int(p) for p in core) for a in tn["alternatives_positions"])


def _to_order1(truth: dict) -> np.ndarray:
    perm0, perm1 = np.array(truth["networks"]["main"]["perm"]), np.array(truth["networks"]["order1"]["perm"])
    inv1 = np.empty_like(perm1)
    inv1[perm1] = np.arange(len(perm1))
    return inv1[perm0]  # main position -> order1 position


def test_registered_with_switches():
    assert "brainir_v1" in MethodRegistry.names()
    m = MethodRegistry.get("brainir_v1")
    assert isinstance(m, v1.BrainIRv1)
    for k in ("use_structural_prior", "use_group_testing", "use_active_selection", "robust_objective", "uncertainty_model", "minimality_cleanup",
              "necessity_screen", "n_seeds_per_decision", "adaptive_replication", "reliance_tiebreak", "use_cross_connectome", "max_alternatives",
              "structural_pruning", "activity_pruning", "member_essentiality"):
        assert k in m.default_config, k


def test_recovers_ei_pair_with_roles_essentiality_predictions_and_schema(suite):
    inst_dir, truth = suite["ei"]
    tn = truth["networks"]["main"]
    problem, sim, res = _discover(inst_dir, "main", budget=400, seed=0)
    assert sorted(res.core) == sorted(tn["core_positions"]), (res.core, tn["core_positions"])
    assert sim.calls <= 400 and res.budget["calls"] == sim.calls
    for p in res.core:
        assert res.essential[p] == tn["essential_positions"][str(p)]
        assert res.inclusion_probability[p] >= 0.9
    assert set(res.inclusion_probability) == set(int(x) for x in problem.candidate_positions())
    assert max(q for p, q in res.inclusion_probability.items() if p not in set(res.core)) <= 0.2
    assert {r for r, _ in res.roles.values()} == {tn["roles_positions"][str(p)] for p in res.core}
    assert all(r in GENERIC_ROLES for r, _ in res.roles.values())
    assert sorted(res.loop) == sorted(res.core) and res.predicted_frequency_hz and res.predicted_function_preserved is True
    assert res.fidelity["keep_only_pass_fraction"] >= 0.5
    d = res.diagnostics
    assert "errors" not in d and d["prober"]["budget_exhausted"] is False
    preds = d["intervention_predictions"]
    assert {x["position"] for x in preds} == set(res.core)
    assert all("silence_alone" in x and "strongest_in_core_edge" in x for x in preds)
    curve = d["size_error_curve"]
    assert any(pt["returned"] and pt["size"] == len(res.core) and pt["error"] < 0.5 for pt in curve)
    assert all(pt["error"] >= 0.5 for pt in curve if pt["size"] < len(res.core))
    assert d["auxiliary_budget"]["used"] is False  # single-network instance: no network of another dataset in the bundle
    pred = res.to_prediction(problem, MethodInfo(name="brainir_v1", version="1.0"))
    assert isinstance(pred, BrainIRMechanismPrediction) and sorted(pred.core_ids()) == sorted(int(problem.public_ids[p]) for p in res.core)
    BrainIRMechanismPrediction.from_json(pred.to_json())


def test_deterministic_under_seed_and_node_order_independent(suite):
    inst_dir, truth = suite["ei"]
    _, _, r1 = _discover(inst_dir, "main", budget=400, seed=3)
    _, _, r2 = _discover(inst_dir, "main", budget=400, seed=3)  # fresh simulator, fresh cache
    assert r1.core == r2.core and r1.inclusion_probability == r2.inclusion_probability and r1.essential == r2.essential
    assert r1.alternatives == r2.alternatives and r1.budget["calls"] == r2.budget["calls"]
    to1 = _to_order1(truth)
    for s in (0, 1):  # the same neurons from a permuted copy of the graph and other seeds
        _, _, r3 = _discover(inst_dir, "order1", budget=400, seed=s)
        assert sorted(int(to1[p]) for p in r1.core) == sorted(r3.core)


def test_redundant_mechanisms_are_reported_with_shared_probability(suite):
    inst_dir, truth = suite["red"]
    tn = truth["networks"]["main"]
    _, _, res = _discover(inst_dir, "main", budget=600, seed=0)
    alts = [sorted(a) for a in tn["alternatives_positions"]]
    assert sorted(res.core) in alts, (res.core, alts)
    assert any(sorted(a) in alts and sorted(a) != sorted(res.core) for a in res.alternatives), (res.alternatives, alts)
    assert all(res.essential[p] is False for p in res.core)  # either pair suffices: nobody is essential
    other = next(a for a in alts if a != sorted(res.core))
    sel = res.diagnostics["selection"]
    if sel["tied"]:  # the evidence could not separate the two pairs: they share the probability mass
        for p in list(res.core) + other:
            assert 0.3 <= res.inclusion_probability[p] <= 0.6, (p, res.inclusion_probability[p])
    else:  # one pair was decisively better: the other keeps a small but non-zero probability
        assert all(res.inclusion_probability[p] >= 0.85 for p in res.core)
        assert all(0.1 <= res.inclusion_probability[p] <= 0.3 for p in other)
    assert all(res.roles.get(p, ("",))[0] == "redundant_backup" for p in other)


def test_context_member_found_by_full_network_necessity(suite):
    inst_dir, truth = suite["wta"]  # selectivity: keep-only of the winner alone passes; the lateral inhibitor is needed in context
    tn = truth["networks"]["main"]
    _, sim, res = _discover(inst_dir, "main", budget=400, seed=0)
    assert _success(res.core, tn), (res.core, tn["alternatives_positions"])
    inhib = [p for p in res.core if tn["roles_positions"].get(str(p)) == "lateral_inhibition"]
    assert inhib and all(res.essential[p] is True for p in inhib)
    assert all(res.roles[p][0] == "lateral_inhibition" for p in inhib)
    assert inhib[0] in res.diagnostics["necessity_screen"]["found"] or inhib[0] in res.diagnostics["elimination"]["final"]
    # the same core without the screen misses the inhibitor (the keep-only search cannot see it)
    _, _, r0 = _discover(inst_dir, "main", budget=400, seed=0, config={"necessity_screen": False})
    assert not set(inhib) & set(r0.core)


@pytest.mark.parametrize("key", ["ff", "mem"])
def test_activity_band_and_persistence_mechanisms(suite, key):
    inst_dir, truth = suite[key]
    tn = truth["networks"]["main"]
    _, sim, res = _discover(inst_dir, "main", budget=400, seed=1)
    assert _success(res.core, tn), (key, res.core, tn["alternatives_positions"])
    assert sim.calls <= 400 and res.fidelity["keep_only_pass_fraction"] >= 0.5
    crit = {"ff": "activity_band", "mem": "persistence"}[key]
    assert crit in res.motif


def test_budget_is_never_exceeded_and_results_stay_valid(suite):
    inst_dir, _ = suite["ei"]
    for budget in (1, 4, 12, 30):
        problem, sim, res = _discover(inst_dir, "main", budget=budget, seed=0)
        assert sim.calls <= budget and res.budget["calls"] <= budget
        assert all(0.0 <= q <= 1.0 for q in res.inclusion_probability.values())
        res.to_prediction(problem, MethodInfo(name="brainir_v1", version="1.0"))
        json.dumps(res.to_dict(), default=str)


ABLATIONS = [{"use_structural_prior": False}, {"use_group_testing": False}, {"use_active_selection": False}, {"robust_objective": False},
             {"uncertainty_model": "point"}, {"minimality_cleanup": False}, {"necessity_screen": False}, {"member_essentiality": False},
             {"adaptive_replication": False}, {"n_seeds_per_decision": 1}, {"reliance_tiebreak": False}, {"max_alternatives": 0},
             {"structural_pruning": False, "activity_pruning": False}, {"use_cross_connectome": False}]


@pytest.mark.parametrize("switch", ABLATIONS, ids=lambda d: ",".join(f"{k}={v}" for k, v in d.items()))
def test_every_switched_off_configuration_runs_within_budget(suite, switch):
    inst_dir, truth = suite["ei"]
    problem, sim, res = _discover(inst_dir, "main", budget=90, seed=0, config=switch)
    assert sim.calls <= 90 and res.budget["calls"] == sim.calls and res.core
    assert _success(res.core, truth["networks"]["main"]), (switch, res.core)
    assert "errors" not in res.diagnostics, res.diagnostics.get("errors")
    check = BudgetedSimulator(problem, max_calls=4)  # an independent check of the returned core on two fresh replicates
    assert check.pass_fraction(keep_only(problem, res.core), [9001, 9002]) >= 0.5
    res.to_prediction(problem, MethodInfo(name="brainir_v1", version="1.0"))
    if switch.get("uncertainty_model") == "point":
        assert set(res.inclusion_probability.values()) <= {0.0, 1.0}


def test_budget_integrity_rules_static_and_seed_range(suite):
    src = Path(v1.__file__).read_text(encoding="utf-8")
    assert "BudgetedSimulator(" not in src and "scipy.integrate" not in src
    assert not re.search(r"^\s*(from|import)\s+(\.\.sim|brainir\.sim)\b", src, re.M)
    assert not re.search(r"\b\w*sim\w*\.(calls|max_calls|computed_calls|simulated_seconds)\s*=[^=]", src)
    inst_dir, _ = suite["ei"]
    for seed in (15, 31):  # every parameter seed the method queries stays below 5,000 (seeds 15 and 31 use the highest seed block)
        problem = DiscoveryProblem.from_bundle(inst_dir, "main")
        sim = BudgetedSimulator(problem, max_calls=250)
        seen: list[int] = []
        orig = sim.run_many

        def rec(queries, orig=orig, seen=seen):
            seen.extend(int(q.seed) for q in queries)
            for q in queries:
                iv = q.intervention
                assert iv is None or iv.weight_noise_sd == 0 or iv.weight_noise_seed is not None
                assert set(q.cfg_override) <= {"tau_sd", "a_sd", "theta_sd", "r_max_sd"}
            return orig(queries)

        sim.run_many = rec
        MethodRegistry.get("brainir_v1").discover(problem, sim, seed=seed)
        assert seen and max(seen) < 5000, (seed, max(seen))


@pytest.mark.parametrize("transform", ["add_sink_distractors", "reorder_edges"])
def test_meaning_preserving_perturbations_keep_the_core(suite, tmp_path, transform):
    from brainir.discovery.perturb import perturb_bundle

    inst_dir, truth = suite["ei"]
    _, _, base = _discover(inst_dir, "main", budget=300, seed=0)
    perturb_bundle(inst_dir, tmp_path / "p", transform, seed=3)
    _, _, pert = _discover(tmp_path / "p", "main", budget=300, seed=0)
    assert sorted(pert.core) == sorted(base.core)  # existing positions are unchanged by these transforms


def test_prior_only_orders_the_search(suite):
    inst_dir, truth = suite["ei"]
    tn = truth["networks"]["main"]
    core = set(tn["core_positions"])
    problem = DiscoveryProblem.from_bundle(inst_dir, "main")
    wrong = {int(p): (0.02 if int(p) in core else 0.95) for p in problem.candidate_positions()}
    for prior in (wrong, {str(p): 0.9 for p in core}):
        _, sim, res = _discover(inst_dir, "main", budget=400, seed=0, config={"prior": prior})
        assert sorted(res.core) == sorted(core) and sim.calls <= 400


def _pair(root, family: str, first_seed: int, n: tuple[int, int] = (30, 36), **kw):
    for s in range(first_seed, first_seed + 10):
        spec = PairSpec(family, n[0], n[1], s, n_readout=8, **kw)
        pair = build_pair(spec)
        ver = verify_pair(pair, seeds=[0, 1, 2])
        if ver["verified"]:
            export_pair(pair, ver, root)
            d = root / "instances" / spec.label
            return d, json.loads((root / "truth" / f"{spec.label}.json").read_text(encoding="utf-8"))
    raise AssertionError(f"no verified {family} pair")


def test_cross_connectome_step_shares_the_budget_and_claims_only_verified_identities(tmp_path):
    d, truth = _pair(tmp_path, "integrator", 1)
    problem = DiscoveryProblem.from_bundle(d, "a")
    sim = BudgetedSimulator(problem, max_calls=300)
    res = MethodRegistry.get("brainir_v1").discover(problem, sim, seed=0)
    assert _success(res.core, truth["networks"]["a"])
    aux = res.diagnostics["auxiliary_budget"]
    assert aux["used"] and aux["network"] == "b" and aux["calls"] <= aux["allowance"]
    assert sim.total_calls() == sim.calls + aux["calls"] <= 300  # one budget pool: the other network is paid from the same 300 calls
    assert res.budget["total_calls_incl_children"] == sim.total_calls()
    b = DiscoveryProblem.from_bundle(d, "b")
    corr = {int(x): int(y) for x, y in truth["correspondence_positions"]}
    claims = res.diagnostics["cross_connectome"]
    assert aux["transfer"]["verified"] or not claims  # identity claims only from a verified transfer
    for c in claims:  # calibrated identity probabilities, each backed by fingerprint evidence above 'none' in both directions
        assert 0.0 <= c["confidence"] <= 1.0 and c["basis"] == "connectivity" and c["other_dataset"] == b.dataset
        assert int(b.public_ids[corr[c["source_position"]]]) == c["other_source_id"]
    claimed = {(c["source_position"], c["other_source_id"]) for c in claims}
    assert claims  # this pair's transfer verifies and its member identity is claimed
    for pa, pb, w_ab, w_ba, none_ab, none_ba, _p, _e, is_claimed, linked, complete in res.diagnostics.get("identity_evidence", []):
        # claimed iff the verified transfer matched the pair, pairs up both cores one to one, and both directions beat 'none'
        assert is_claimed == (linked and complete and w_ab > none_ab and w_ba > none_ba)
        assert is_claimed == ((pa, int(b.public_ids[pb])) in claimed)
    assert "role_alignment" in res.diagnostics and 0.0 <= res.diagnostics["role_alignment"]["role_graph_similarity"] <= 1.0
    pred = res.to_prediction(problem, MethodInfo(name="brainir_v1", version="1.0"))
    assert len(pred.cross_connectome) == len(claims)
    assert any("networks/b/" in f for f in problem.files_read)  # the other network's files are recorded as inputs
    # a tight budget: the core comes first, the cross-connectome step is skipped or cut, never beyond the budget
    sim2 = BudgetedSimulator(problem, max_calls=60)
    res2 = MethodRegistry.get("brainir_v1").discover(problem, sim2, seed=0)
    assert sim2.total_calls() <= 60 and res2.core


def test_no_identity_claims_under_an_implementation_shift_across_implementations(tmp_path):
    d, truth = _pair(tmp_path, "two_implementations", 3, n=(60, 80), implementation_shift=True)
    problem = DiscoveryProblem.from_bundle(d, "a")
    sim = BudgetedSimulator(problem, max_calls=400)
    res = MethodRegistry.get("brainir_v1").discover(problem, sim, seed=0)
    b = DiscoveryProblem.from_bundle(d, "b")
    alt_b = {int(x) for alt in truth["networks"]["b"]["alternatives_positions"] for x in alt}
    perm_a, perm_b = truth["networks"]["a"]["perm"], truth["networks"]["b"]["perm"]
    for c in res.diagnostics["cross_connectome"]:  # a claim may only pair the same canonical node of the retained alternative
        pb = int(np.flatnonzero(b.public_ids == c["other_source_id"])[0])
        assert pb in alt_b and perm_a[c["source_position"]] == perm_b[pb]
    assert sim.total_calls() <= 400


def test_no_identity_claims_on_a_null_pair(tmp_path):
    """Network b implements another family (every identity claim would be false). Here the other network's own single-neuron
    mechanism is a sufficient, essential image of part of the core — a verified but partial image — so no member identity is claimed."""
    d, truth = _pair(tmp_path, "negative_feedback_controller", 0, null_family="integrator")
    problem = DiscoveryProblem.from_bundle(d, "a")
    sim = BudgetedSimulator(problem, max_calls=300)
    res = MethodRegistry.get("brainir_v1").discover(problem, sim, seed=0)
    assert _success(res.core, truth["networks"]["a"]) and sim.total_calls() <= 300
    assert res.diagnostics["cross_connectome"] == []
    assert not any(e[8] for e in res.diagnostics.get("identity_evidence", []))
    assert "role_alignment" in res.diagnostics  # the role-level output stays


def test_run_entry_point(suite, tmp_path):
    inst_dir, _ = suite["ei"]
    out = tmp_path / "pred.json"
    rj = tmp_path / "result.json"
    assert run_main(["--method", "brainir_v1", "--bundle", str(inst_dir), "--network", "main", "--out", str(out), "--budget", "300", "--seed", "0",
                     "--result-json", str(rj)]) == 0
    pred = BrainIRMechanismPrediction.from_json(out.read_text(encoding="utf-8"))
    assert pred.core_ids() and pred.method.name == "brainir_v1" and pred.method.compute["simulations"] <= 300
    assert json.loads(rj.read_text(encoding="utf-8"))["core"]
