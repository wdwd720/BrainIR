"""Cross-network infrastructure on a tiny synthetic pair: pair generation/export, anchor-fingerprint correspondence, transfer with a
separately accounted adaptation budget, null transfer, role graphs. Synthetic only; no oracle, no real data."""

from __future__ import annotations

import json

import numpy as np
import pytest

from brainir.discovery.correspondence import fingerprints, is_labelled, match_candidates, mutual_best, null_match_scores, shared_anchor_types
from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.simulator import BudgetedSimulator
from brainir.discovery.synthetic_pairs import PairSpec, build_pair, export_pair, verify_pair
from brainir.discovery.transfer import null_transfer, role_graph, role_graph_similarity, transfer_core


@pytest.fixture(scope="module")
def tiny_pair(tmp_path_factory):
    root = tmp_path_factory.mktemp("pairs")
    for s in range(6):
        spec = PairSpec("delayed_inhibitory_oscillator", 50, 60, s, n_readout=8, anchor_decoy=True)
        pair = build_pair(spec)
        ver = verify_pair(pair, seeds=[0, 1, 2])
        if ver["verified"]:
            break
    assert ver["verified"]
    export_pair(pair, ver, root)
    truth = json.loads((root / "truth" / f"{spec.label}.json").read_text(encoding="utf-8"))
    a = DiscoveryProblem.from_bundle(root / "instances" / spec.label, "a")
    b = DiscoveryProblem.from_bundle(root / "instances" / spec.label, "b")
    return root, spec, truth, a, b


def test_pair_export_shares_anchors_but_not_tokens(tiny_pair):
    root, spec, truth, a, b = tiny_pair
    anchors = shared_anchor_types(a, b)
    assert "DNsyn" in anchors and "MNsyn" in anchors and sum(t.startswith("SRC#") for t in anchors) == 15
    tok_a = set(a.neurons.loc[~is_labelled(a.neurons["cell_type"]), "cell_type"])
    tok_b = set(b.neurons.loc[~is_labelled(b.neurons["cell_type"]), "cell_type"])
    assert tok_a and tok_b and not (tok_a & tok_b)
    # anchors are dynamically inert: source anchors receive nothing, sink anchors send nothing
    src = np.flatnonzero(a.neurons["cell_type"].astype(str).str.startswith("SRC#"))
    snk = np.flatnonzero(a.neurons["cell_type"].astype(str).str.startswith("SNK#"))
    assert a.C[src, :].sum() == 0 and a.C[:, snk].sum() == 0 and a.C[:, src].sum() > 0 and a.C[snk, :].sum() > 0
    # truth stays out of the public directory; the correspondence is between the two networks' mechanism members
    for f in (root / "instances" / spec.label).rglob("*.json"):
        assert "correspondence" not in f.read_text(encoding="utf-8")
    corr = truth["correspondence_positions"]
    assert len(corr) == 5 and {x for x, _ in corr} == set(truth["networks"]["a"]["core_positions"])
    assert truth["decoy_b_positions"]["decoy"] not in truth["networks"]["b"]["core_positions"]


def test_correspondence_ranks_true_counterparts(tiny_pair):
    _, _, truth, a, b = tiny_pair
    corr = truth["correspondence_positions"]
    res = match_candidates(a, b, [x for x, _ in corr], k=5)
    in_top5 = sum(1 for x, y in corr if y in [c["position"] for c in res["per_neuron"][x]["candidates"]])
    assert in_top5 >= 4
    top1 = sum(1 for x, y in corr if res["per_neuron"][x]["candidates"][0]["position"] == y)
    assert top1 >= 3
    z_true = np.mean([res["per_neuron"][x]["distinctiveness"] for x, _ in corr])
    null = null_match_scores(a, b, [x for x, _ in corr], n_null=20)
    assert z_true > null["z_mean"]
    fa = fingerprints(a, shared_anchor_types(a, b))
    assert fa.inp.shape == (a.n, len(fa.anchor_types)) and (fa.coverage([x for x, _ in corr]) > 0).all()
    pairs = mutual_best(a, b, [x for x, _ in corr], list(b.candidate_positions()))
    assert sum(1 for x, y, _ in pairs if [x, y] in corr) >= 3


def test_transfer_recovers_b_core_and_accounts_adaptation(tiny_pair):
    _, _, truth, a, b = tiny_pair
    core_a = truth["networks"]["a"]["core_positions"]
    sim_b = BudgetedSimulator(b, max_calls=200)
    tr = transfer_core(a, b, core_a, sim_b, seeds=[0, 1], k=3, adaptation_calls=30)
    assert tr["evaluation_calls"] == 2 and tr["adaptation_calls"] <= 30 and tr["evaluation_calls"] + tr["adaptation_calls"] == sim_b.calls
    assert tr["passed"] and set(tr["core_b"]) >= set(truth["networks"]["b"]["core_positions"])
    null = null_transfer(a, b, core_a, sim_b, seeds=[0, 1], n_null=5)
    assert null["pass_rate"] < tr["pass_fraction"]
    roles_a = {p: (r, 1.0) for p, r in truth["networks"]["a"]["roles_positions"].items()}
    roles_a = {int(p): v for p, v in roles_a.items()}
    roles_b = {int(p): (r, 1.0) for p, r in truth["networks"]["b"]["roles_positions"].items()}
    ga = role_graph(a, core_a, roles_a)
    gb = role_graph(b, truth["networks"]["b"]["core_positions"], roles_b)
    assert role_graph_similarity(ga, gb) == 1.0 and any(e["sign"] < 0 for e in ga["edges"])
    assert role_graph_similarity(ga, {"roles": ["unknown"], "edges": []}) == 0.0
