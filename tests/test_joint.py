"""Cross-connectome pair discovery (brainir.discovery.joint) on tiny synthetic pairs generated here (their truth is known because
they are generated here; synthetic only, no oracle, no real data): all four modes run, budgets hold in every mode (total <= budget_a +
budget_b, adaptation reported separately), determinism under the seed, `prior` and `joint` recover both cores, `joint` rescues a
network on which the base method alone fails and aligns the two mechanisms, helpers and the CLI."""

from __future__ import annotations

import json

import pytest

from brainir.discovery.interface import DiscoveryResult
from brainir.discovery.joint import MODES, discover_pair, infer_roles, transport_prior
from brainir.discovery.joint import main as joint_main
from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.synthetic_pairs import PairSpec, build_pair, export_pair, verify_pair

METHOD = "greedy_reference"
EASY = ("integrator", 1)
"""A tiny pair on which the base method alone recovers both mechanisms (so `prior` must too, whatever the method does with the prior)."""
RESCUE = ("negative_feedback_controller", 0)
"""A tiny pair on which the base method alone misses network a's mechanism (a background set drives the readout into the band)."""
BUDGET = 300


def _make(root, family: str, seed: int):
    for s in range(seed, seed + 10):
        spec = PairSpec(family, 30, 36, s, n_readout=8, anchor_decoy=True)
        pair = build_pair(spec)
        ver = verify_pair(pair, seeds=[0, 1, 2])
        if ver["verified"]:
            export_pair(pair, ver, root)
            truth = json.loads((root / "truth" / f"{spec.label}.json").read_text(encoding="utf-8"))
            d = root / "instances" / spec.label
            return d, truth, DiscoveryProblem.from_bundle(d, "a"), DiscoveryProblem.from_bundle(d, "b")
    raise AssertionError(f"no verified {family} pair")


def _success(core, truth_net: dict) -> bool:
    return any(set(alt) <= set(int(p) for p in core) for alt in truth_net["alternatives_positions"])


@pytest.fixture(scope="module")
def pairs(tmp_path_factory):
    root = tmp_path_factory.mktemp("joint_pairs")
    return {"easy": _make(root, *EASY), "rescue": _make(root, *RESCUE), "root": root}


@pytest.fixture(scope="module")
def runs(pairs):
    _, _, a, b = pairs["easy"]
    return {m: discover_pair(a, b, METHOD, budget_a=BUDGET, budget_b=BUDGET, seed=0, mode=m) for m in MODES}


def test_all_modes_run_with_honest_accounting(runs):
    for mode, pr in runs.items():
        bud = pr.budget
        assert bud["total"] == bud["a"] + bud["b"] + bud["adaptation"] <= 2 * BUDGET, mode
        assert bud["adaptation"] == bud["adaptation_a"] + bud["adaptation_b"]
        assert sum(p["calls"] for p in bud["phases"]) == bud["total"]
        assert all(p["calls"] <= p["allowance"] for p in bud["phases"])
        assert pr.result_a.core and pr.result_b.core, mode
        assert "role_graph_similarity" in pr.role_alignment and 0.0 <= pr.role_alignment["role_graph_similarity"] <= 1.0
        assert all(r in pr.role_alignment for r, _ in pr.result_a.roles.values())
        assert all(0.0 <= c <= 1.0 for _, _, c in pr.correspondence)
        json.dumps(pr.to_dict(), default=str)
    ind, pri, tra = runs["independent"], runs["prior"], runs["transfer"]
    # the base method on A is the same run in independent / prior / transfer (same method, seed, budget, fresh simulator)
    assert ind.result_a.core == pri.result_a.core == tra.result_a.core
    assert ind.budget["a"] == pri.budget["a"] == tra.budget["a"] <= BUDGET
    # independent and prior share nothing but the prior: no adaptation; each network within its own budget
    for pr in (ind, pri):
        assert pr.budget["adaptation"] == 0 and pr.budget["b"] <= BUDGET
    assert pri.diagnostics["prior"]["n_boosted"] > 0 and "prior" not in ind.diagnostics
    # transfer: no discovery on B; its top-1 evaluation and the adaptation stay inside budget_b and are reported apart
    assert tra.budget["by_kind"]["b"]["discovery"] == 0 and tra.budget["b"] + tra.budget["adaptation_b"] <= BUDGET
    assert tra.budget["by_kind"]["b"]["evaluation"] >= 1


def test_prior_and_joint_recover_both_cores(pairs, runs):
    _, truth, _, b = pairs["easy"]
    for mode in ("prior", "joint"):
        pr = runs[mode]
        assert _success(pr.result_a.core, truth["networks"]["a"]), (mode, pr.result_a.core)
        assert _success(pr.result_b.core, truth["networks"]["b"]), (mode, pr.result_b.core)
    jnt = runs["joint"]
    assert truth["decoy_b_positions"]["decoy"] not in set(jnt.result_b.core)  # the anchor decoy is rejected by simulation
    corr = {tuple(x) for x in truth["correspondence_positions"]}
    assert jnt.correspondence and all((x, y) in corr for x, y, _ in jnt.correspondence)
    assert jnt.role_alignment["role_graph_similarity"] == 1.0


def test_joint_rescues_a_network_where_the_base_method_fails(pairs):
    _, truth, a, b = pairs["rescue"]
    ind = discover_pair(a, b, METHOD, budget_a=BUDGET, budget_b=BUDGET, seed=0, mode="independent")
    jnt = discover_pair(a, b, METHOD, budget_a=BUDGET, budget_b=BUDGET, seed=0, mode="joint")
    assert not _success(ind.result_a.core, truth["networks"]["a"])  # the fact this instance was chosen for
    assert _success(jnt.result_a.core, truth["networks"]["a"]) and _success(jnt.result_b.core, truth["networks"]["b"])
    assert jnt.budget["total"] <= 2 * BUDGET and jnt.budget["adaptation"] > 0
    assert sorted(ind.result_a.core) in [sorted(x) for x in jnt.result_a.alternatives]  # the lead's own mechanism stays an alternative
    corr = {tuple(x) for x in truth["correspondence_positions"]}
    assert jnt.correspondence and all((x, y) in corr for x, y, _ in jnt.correspondence)
    assert all(jnt.result_a.essential.get(p) is not None for p in jnt.result_a.core)


def test_deterministic_under_seed(pairs, runs):
    _, _, a, b = pairs["easy"]
    again = discover_pair(a, b, METHOD, budget_a=BUDGET, budget_b=BUDGET, seed=0, mode="joint")
    first = runs["joint"]
    assert again.result_a.core == first.result_a.core and again.result_b.core == first.result_b.core
    assert again.result_a.inclusion_probability == first.result_a.inclusion_probability
    assert again.result_b.inclusion_probability == first.result_b.inclusion_probability
    assert again.correspondence == first.correspondence and again.role_alignment == first.role_alignment
    assert {k: v for k, v in again.budget.items()} == {k: v for k, v in first.budget.items()}


@pytest.mark.parametrize("mode", MODES)
def test_tiny_budgets_are_never_exceeded(pairs, mode):
    _, _, a, b = pairs["easy"]
    for ba, bb in ((0, 0), (3, 2), (10, 7)):
        pr = discover_pair(a, b, METHOD, budget_a=ba, budget_b=bb, seed=1, mode=mode)
        bud = pr.budget
        assert bud["total"] == bud["a"] + bud["b"] + bud["adaptation"] <= ba + bb, (mode, ba, bb, bud)
        if mode != "joint":  # only joint pools the two budgets
            assert sum(bud["by_kind"]["a"].values()) <= ba and sum(bud["by_kind"]["b"].values()) <= bb


def test_prior_roles_and_cli(pairs, tmp_path):
    d, truth, a, b = pairs["rescue"]
    ta = truth["networks"]["a"]
    res = DiscoveryResult(core=ta["core_positions"], inclusion_probability=dict.fromkeys(ta["core_positions"], 1.0))
    prior = transport_prior(a, b, res)
    assert set(prior) == set(int(p) for p in b.candidate_positions()) and all(0.0 <= v <= 1.0 for v in prior.values())
    base = min(prior.values())
    assert sum(v > base + 1e-9 for v in prior.values()) <= 3 * 3  # spread over at most k candidates per member
    roles = infer_roles(a, ta["core_positions"])
    assert {p: r for p, (r, _) in roles.items()} == {int(k): v for k, v in ta["roles_positions"].items()}
    out = tmp_path / "pair.json"
    rc = joint_main(["--pair", str(d), "--method", METHOD, "--mode", "transfer", "--budget-a", "200", "--budget-b", "40", "--seed", "0",
                     "--out", str(out)])
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0 and rec["mode"] == "transfer" and rec["budget"]["total"] <= 240
    assert set(rec) >= {"result_a", "result_b", "correspondence", "role_alignment", "budget", "diagnostics"}
