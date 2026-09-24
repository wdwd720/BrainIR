"""Graded activity, edge-removal queries, the participation-aware audit and intact-network scoring (reviews A and G)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from brainir.discovery import BudgetedSimulator, DiscoveryProblem, DiscoveryResult, SimQuery
from brainir.discovery.suite_audit import participates, participation_threshold, reclassify_participation
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import score_intact, score_structure


@pytest.fixture(scope="module")
def ei(tmp_path_factory):
    root = tmp_path_factory.mktemp("intact")
    for s in range(8):
        spec = InstanceSpec("ei_pair_oscillator", 50, 100 + s, n_readout=8)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            break
    export_instance(inst, ver, root, n_order_variants=1)
    truth = json.loads((root / "truth" / f"{spec.label}.json").read_text(encoding="utf-8"))
    p = DiscoveryProblem.from_bundle(root / "instances" / spec.label, "main")
    return p, truth["networks"]["main"], ver


def test_outcomes_carry_graded_activity(ei):
    p, tnet, _ver = ei
    sim = BudgetedSimulator(p, max_calls=5)
    o = sim.run(SimQuery(None, 0))
    assert o.mean_rate_hz is not None and o.peak_rate_hz is not None and len(o.mean_rate_hz) == p.n
    thr = float(p.criterion_spec.get("active_rate_hz", 0.01))
    assert set(np.flatnonzero(o.peak_rate_hz > thr).tolist()) == set(o.active_positions.tolist())
    assert (o.mean_rate_hz <= o.peak_rate_hz + 1e-6).all()
    with pytest.raises(ValueError):
        o.mean_rate_hz[0] = 1.0  # read-only like active_positions
    core = [int(x) for x in tnet["core_positions"]]
    assert float(np.min(o.mean_rate_hz[core])) > 0.05  # the planted mechanism participates


def test_edge_removal_queries(ei):
    p, tnet, _ver = ei
    core = [int(x) for x in tnet["core_positions"]]
    # the strongest edge from the core onto its partner (the E -> I drive of the E-I pair)
    Wc = p.W.tocoo()
    edges = [(int(i), int(j), float(abs(w))) for i, j, w in zip(Wc.row, Wc.col, Wc.data) if int(i) in core and int(j) in core and i != j]
    post, pre, _w = max(edges, key=lambda e: e[2])
    sim = BudgetedSimulator(p, max_calls=20)
    base = sim.evaluate(None, [0, 1, 2])
    cut = sim.run_many([SimQuery(None, s, remove_edges=((post, pre),)) for s in (0, 1, 2)])
    assert sim.calls == 6 and all(o.passed for o in base) and not any(o.passed for o in cut)
    # removing an absent synapse is the unmodified query (same memo entry, no charge)
    absent = next((i, j) for i in range(p.n) for j in range(p.n) if p.W[i, j] == 0 and i != j)
    again = sim.run(SimQuery(None, 0, remove_edges=(absent,)))
    assert sim.calls == 6 and again.cached and again.score == base[0].score
    k1 = SimQuery(None, 0, remove_edges=((post, pre),)).key("h", {})
    assert k1 != SimQuery(None, 0).key("h", {})
    with pytest.raises(ValueError):
        sim.run(SimQuery(None, 0, remove_edges=((p.n, 0),)))


def test_participation_helpers():
    rates = np.array([0.0, 0.001, 50.0, 60.0, 0.2])
    thr = participation_threshold(rates, [2, 3])
    assert thr == pytest.approx(max(0.05, 0.01 * 55.0))
    assert participates(rates, [2, 3], thr) and not participates(rates, [2, 1], thr) and participates(rates, [], thr)


def test_reclassify_adds_sigma_and_keeps_participating_sets(ei):
    p, tnet, _ver = ei
    t = dict(tnet)
    t.pop("essential_pass_fraction_positions", None)
    t["unplanted_alternatives_positions"] = []
    out = reclassify_participation(p, t, seeds=(0, 1))
    new = out["truth_net"]
    assert new["alternatives_positions"] == [sorted(a) for a in tnet["alternatives_positions"]] and new["latent_backups_positions"] == []
    sig = new["essential_pass_fraction_positions"]
    assert set(int(k) for k in sig) == {int(x) for a in tnet["alternatives_positions"] for x in a}
    assert all(0.0 <= v <= 1.0 for v in sig.values())
    # a fabricated "unplanted alternative" made of a silent neuron is moved to the latent backups
    sim = BudgetedSimulator(p, max_calls=5)
    o = sim.run(SimQuery(None, 0))
    silent = int(np.argmin(o.mean_rate_hz))  # the most silent neuron
    t2 = dict(new)
    t2["alternatives_positions"] = list(new["alternatives_positions"]) + [[silent]]
    t2["unplanted_alternatives_positions"] = [[silent]]
    out2 = reclassify_participation(p, t2, seeds=(0, 1))
    assert out2["moved_to_latent"] == [[silent]] and [silent] not in out2["truth_net"]["alternatives_positions"]


def test_intact_scoring_separates_the_mechanism_from_a_silent_set(ei):
    p, tnet, _ver = ei
    core = [int(x) for x in tnet["core_positions"]]
    good = score_intact(p, DiscoveryResult(core=core), tnet, seeds=[5000, 5001])
    assert good["core_participates"] and good["silence_core_pass"] == 0.0
    sim = BudgetedSimulator(p, max_calls=5)
    o = sim.run(SimQuery(None, 0))
    cands = [int(x) for x in p.candidate_positions()]
    silent = min(cands, key=lambda q: float(o.mean_rate_hz[q]))
    bad = score_intact(p, DiscoveryResult(core=[silent]), tnet, seeds=[5000, 5001])
    assert not bad["core_participates"] and bad["silent_core_members"] == [silent] and bad["silence_core_pass"] == 1.0
    st = score_structure(DiscoveryResult(core=core[:1], inclusion_probability={core[0]: 0.9, core[1]: 0.2}), tnet)
    assert st["essential_recall"] == pytest.approx(0.5) and st["n_contested"] >= 2
    assert st["brier_contested"] is not None and st["brier_contested_any_alternative"] is not None
