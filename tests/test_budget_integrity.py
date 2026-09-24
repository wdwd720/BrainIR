"""Budget integrity and failure accounting of the Phase 2 harness (review F findings 1-3, 8-13, 16).

A method may only simulate through the BudgetedSimulator it is given; the harness counts real simulations and rejects runs that
bypass the budget, exceed it, or query reserved parameter seeds. Failed runs stay in every success denominator."""

from __future__ import annotations

import ast
import json

import numpy as np
import pytest

from brainir import paths
from brainir.discovery import BudgetedSimulator, DiscoveryProblem, DiscoveryResult, SimQuery, keep_only
from brainir.discovery.interface import DiscoveryMethod, MethodRegistry
from brainir.discovery.pair_tournament import summarize_pairs
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import identity_consistency, run_one, summarize


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    root = tmp_path_factory.mktemp("integrity")
    for s in range(8):
        spec = InstanceSpec("ei_pair_oscillator", 40, s, n_readout=8)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            break
    export_instance(inst, ver, root, n_order_variants=1)
    return root, spec.label


def _register(cls):
    MethodRegistry.register(cls)
    return cls.name


class _Bypass(DiscoveryMethod):
    name = "test_bypass_direct_simulate"

    def discover(self, problem, sim, *, seed, config=None):
        import brainir.sim.model as M

        sim.evaluate(None, [0])  # one charged call
        params = M.sample_neuron_params(problem.model_cfg, problem.n, 0, problem.sizes)
        M.simulate(problem.W, params, problem.model_cfg, problem.stimulus(), None)  # an uncharged simulation
        return DiscoveryResult(core=[int(problem.candidate_positions()[0])])


class _ReservedSeed(DiscoveryMethod):
    name = "test_reserved_seed"

    def discover(self, problem, sim, *, seed, config=None):
        sim.evaluate(None, [5000])
        return DiscoveryResult(core=[int(problem.candidate_positions()[0])])


class _Honest(DiscoveryMethod):
    name = "test_honest"

    def discover(self, problem, sim, *, seed, config=None):
        sim.evaluate(None, [0, 1])
        return DiscoveryResult(core=[int(problem.candidate_positions()[0])])


def test_uncharged_simulation_is_caught(tiny):
    root, label = tiny
    d = root / "instances" / label
    for cls, expect in ((_Bypass, "budget integrity"), (_ReservedSeed, "seed namespace")):
        rec = run_one(_register(cls), d, "main", budget=50, seed=0, config={}, truth_path=root / "truth" / f"{label}.json", score_seeds=[5001],
                      robust=False)
        assert expect in rec.get("error", ""), rec.get("error")
        assert "structure" not in rec
    ok = run_one(_register(_Honest), d, "main", budget=50, seed=0, config={}, truth_path=root / "truth" / f"{label}.json", score_seeds=[5001],
                 robust=False)
    assert "error" not in ok and ok["integrity"]["real_simulations"] == ok["integrity"]["charged_computed"] == 2
    assert ok["env"]["source_tree_sha256"] and ok["env"]["packages"]["numpy"]


def test_failures_stay_in_the_denominators():
    ok = {"method": "m", "instance": "i", "network": "main", "seed": 0, "structure": {"success": True, "success_planted": True,
          "vs_best_alternative": {"recall": 1.0, "precision": 1.0}, "role_accuracy": None, "brier_inclusion": 0.0},
          "function": {"functional_success": True, "functional_success_causal": True, "nominal": 1.0},
          "result": {"core": [1, 2], "budget": {"calls": 10}}, "core_canonical": [1, 2]}
    recs = [ok, {**ok, "seed": 1}, {"method": "m", "instance": "j", "seed": 0, "error": "timeout"}, {"method": "m", "instance": "k", "error": "oom"}]
    s = summarize(recs)["m"]
    assert s["n_runs"] == 4 and s["n_failed"] == 2 and s["success_rate"] == 0.5 and s["functional_success_rate"] == 0.5
    assert s["functional_success_causal_rate"] == 0.5
    pairs = [{"method": "m", "mode": "joint", "score": {"both_success": True, "a": {"success": True}, "b": {"success": True},
              "correspondence": None, "role_alignment_accuracy": None, "role_graph_similarity_pred_ab": 1.0, "budget": {"total": 5}},
              "family": "f", "shift": False, "decoy": False}, {"method": "m", "mode": "joint", "error": "x"}]
    ps = summarize_pairs(pairs)["m/joint"]
    assert ps["n_runs"] == 2 and ps["n_failed"] == 1 and ps["both_success"] == 0.5 and ps["success_a"] == 0.5


def test_empty_cores_do_not_count_as_consistent():
    rs = [{"instance": "i", "core_canonical": []}, {"instance": "i", "core_canonical": []}]
    ic = identity_consistency(rs)
    assert ic["pairwise_jaccard_mean"] == 0.0 and ic["identical_fraction"] == 0.0 and ic["n_empty_cores"] == 2


def test_query_validation_and_read_only_accounting(tiny):
    root, label = tiny
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(p, max_calls=10)
    cand = [int(x) for x in p.candidate_positions()[:3]]
    with pytest.raises(ValueError, match="weight_noise_seed"):
        sim.run(SimQuery(keep_only(p, cand, weight_noise_sd=0.2), 0))
    with pytest.raises(ValueError, match="cfg_override"):
        sim.run(SimQuery(None, 0, cfg_override={"b_exc": 0.05}))
    with pytest.raises(ValueError, match="t_end"):
        sim.run(SimQuery(None, 0, t_end=p.model_cfg.t_end * 2))
    for attr in ("calls", "max_calls", "computed_calls", "simulated_seconds"):
        with pytest.raises(AttributeError):
            setattr(sim, attr, 0)
    a = sim.run(SimQuery(None, 0))
    b = sim.run(SimQuery(None, 0, t_end=p.model_cfg.t_end))  # the explicit default is the same query
    assert sim.calls == 1 and sim.cache_hits == 1 and b.score == a.score
    with pytest.raises(ValueError):
        a.active_positions[:] = 0  # memo answers are read-only
    sim.close()
    assert sim.remaining == 0


def test_spawned_simulators_are_accounted(tiny):
    root, label = tiny
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(p, max_calls=5)
    aux = sim.spawn(p, max_calls=3, kind="auxiliary")
    aux.evaluate(None, [0, 1])
    sim.evaluate(None, [0])
    rep = sim.report()
    assert sim.total_computed_calls() == 3 and rep["children"][0]["kind"] == "auxiliary" and rep["children"][0]["calls"] == 2
    assert sim.param_seeds() == [0, 1]


def test_method_modules_use_only_the_budgeted_simulator():
    """Static rules for every method module (review F finding 2c)."""
    forbidden_imports = ("brainir.sim.model", "brainir.sim.prune", "brainir.sim.screen", "brainir.sim.experiments", "scipy.integrate")
    bad = []
    for path in sorted((paths.repo_root() / "src" / "brainir" / "methods").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = ("brainir." + node.module.lstrip(".")) if node.level else node.module
                mod = mod.replace("brainir..", "brainir.")
                if node.level == 2 and node.module.startswith("sim"):
                    mod = "brainir." + node.module
                if any(mod == f or mod.startswith(f + ".") for f in forbidden_imports):
                    bad.append(f"{path.name}: from {mod} import ...")
            if isinstance(node, ast.Import):
                for a in node.names:
                    if any(a.name == f or a.name.startswith(f + ".") for f in forbidden_imports):
                        bad.append(f"{path.name}: import {a.name}")
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "BudgetedSimulator":
                bad.append(f"{path.name}: constructs BudgetedSimulator")
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in ("sim", "simulator"):
                        bad.append(f"{path.name}: assigns {t.value.id}.{t.attr}")
    assert not bad, bad


def test_result_json_roundtrip_keeps_integrity_fields(tiny):
    root, label = tiny
    from brainir.discovery.run import run_method

    pred, _res = run_method("greedy_reference", root / "instances" / label, "main", budget=120, seed=0, config={"k": 2, "pool": 8, "replicates": 1})
    comp = pred.method.compute
    assert comp["integrity"]["real_simulations"] == comp["integrity"]["charged_computed"] and comp["budget_exhausted"] is False
    assert len(comp["source_tree_sha256"]) == 64
    json.loads(pred.to_json())
    assert np.isfinite(comp["simulations"])
