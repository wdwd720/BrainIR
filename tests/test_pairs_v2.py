"""Harder synthetic pairs, identity-claim scoring and the control arms of the pair tournament (review E findings 1, 4, 5, 11)."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from brainir.discovery import DiscoveryProblem
from brainir.discovery.pair_tournament import identity_truth, independent_pooled, reliability_bins, score_identity_claims
from brainir.discovery.perturb import null_correspondence
from brainir.discovery.synthetic_pairs import PairSpec, build_pair, export_pair, hard_pair_specs, verify_pair


def _first_verified(spec: PairSpec, tries: int = 6):
    for k in range(tries):
        s = replace(spec, seed=spec.seed + 1000 * k)
        pair = build_pair(s)
        ver = verify_pair(pair, seeds=[0, 1, 2])
        if ver["verified"]:
            return pair, ver
    pytest.skip("no verified draw")


def test_hard_settings_are_structural():
    spec = PairSpec("ring_oscillator", 90, 110, 7, anchor_decoy=True, decoy_sign_consistent=True, structural_decoy=True,
                    homologous_background=True, blank_hemilineage=True, motif_count_jitter=0.3, motif_edge_dropout=0.2, motif_extra_edges=1,
                    anchor_share=0.5, anchor_count_noise=0.6)
    p = build_pair(spec)
    b = p.b
    # the structural decoy is a wired, isolated copy of b's mechanism
    D, M = p.structural_decoy_b["nodes"], p.structural_decoy_b["copies"]
    rest = np.setdiff1d(np.arange(b.W.shape[0]), D)
    assert not b.C[np.ix_(D, rest)].any() and not b.C[np.ix_(rest, D)].any()
    assert np.array_equal(b.W[np.ix_(D, D)], b.W[np.ix_(M, M)]) and [int(b.signs[d]) for d in D] == [int(b.signs[x]) for x in M]
    # every column's weights carry the column's published sign (no decoy given away by its sign)
    for W, s in ((p.a.W, p.a.signs), (b.W, b.signs)):
        for j in range(W.shape[0]):
            col = W[:, j][W[:, j] != 0]
            assert s[j] == 0 or (np.sign(col) == s[j]).all(), j
    # interneuron hemilineage is blank; homologs pair distinct distractors
    for inst, meta in ((p.a, p.meta_a), (b, p.meta_b)):
        rows = [i for i in range(inst.W.shape[0]) if inst.node_class[i] == "vnc_intrinsic"]
        assert meta.loc[rows, "hemilineage"].isna().all()
    assert len(p.homologs) > 10 and len({y for _x, y in p.homologs}) == len(p.homologs)
    assert not set(y for _x, y in p.homologs) & set(D)
    assert p.identities == p.correspondence and len(p.identities) == 4


def test_null_and_shift_identities():
    null = build_pair(PairSpec("ei_pair_oscillator", 60, 70, 3, null_family="negative_feedback_controller"))
    assert null.identities == [] and null.correspondence == [] and null.b.truth["family"] == "negative_feedback_controller"
    shift = build_pair(PairSpec("two_implementations", 60, 80, 4, implementation_shift=True))
    kept = shift.b.truth["core"]
    assert shift.correspondence == [] and sorted(x for x, _y in shift.identities) == sorted(kept)
    with pytest.raises(ValueError):
        build_pair(PairSpec("ei_pair_oscillator", 60, 70, 3, null_family="ei_pair_oscillator"))


def test_hard_design_spec_list():
    specs = hard_pair_specs()
    labels = [s.label for s in specs]
    assert len(labels) == len(set(labels))
    assert sum(1 for s in specs if s.null_family) == 8 and sum(1 for s in specs if s.implementation_shift) == 4
    assert all(s.blank_hemilineage and s.homologous_background for s in specs)
    assert sum(1 for s in specs if max(s.n_total_a, s.n_total_b) >= 2000) == 4


def test_identity_truth_old_and_new_formats_agree(tmp_path):
    pair, ver = _first_verified(PairSpec("two_implementations", 50, 60, 11, implementation_shift=True, n_readout=8))
    export_pair(pair, ver, tmp_path, salt="t")
    truth = json.loads((tmp_path / "truth" / f"{pair.spec.label}.json").read_text(encoding="utf-8"))
    new_ids, _ = identity_truth(truth)
    old = {k: v for k, v in truth.items() if k != "identity_positions"}  # a truth file written before the field existed
    old_ids, _ = identity_truth(old)
    assert new_ids == old_ids and len(new_ids) == len(pair.identities) > 0


def test_score_identity_claims():
    ids = {(1, 10), (2, 20)}
    s = score_identity_claims([(1, 10, 0.9), (2, 21, 0.8), (3, 30, None), (1, 10, 0.5)], ids, {(3, 30)}, core_a=[1, 2])
    assert s["n_claimed"] == 3 and s["n_correct"] == 2 and s["n_homolog"] == 1 and s["n_false"] == 1
    assert s["precision"] == pytest.approx(2 / 3) and s["recall"] == 0.5 and s["recall_core"] == 0.5
    assert s["brier"] == pytest.approx(((0.9 - 1) ** 2 + (0.8 - 0) ** 2) / 2)
    empty = score_identity_claims([], set())
    assert empty["precision"] is None and empty["n_claimed"] == 0
    bins = reliability_bins([(0.95, True), (0.9, False), (0.1, False)], n_bins=2)
    assert [b["n"] for b in bins] == [1, 2] and bins[1]["observed"] == 0.5


def test_null_correspondence_keeps_simulations(tmp_path):
    pair, ver = _first_verified(PairSpec("ei_pair_oscillator", 50, 60, 21, n_readout=8))
    export_pair(pair, ver, tmp_path, salt="t")
    d = tmp_path / "instances" / pair.spec.label
    a, b = DiscoveryProblem.from_bundle(d, "a"), DiscoveryProblem.from_bundle(d, "b")
    nb = null_correspondence(b, a, seed=3)
    assert nb.network_hash() == b.network_hash()
    anchors = b.neurons["cell_type"].astype(str).str.startswith(("SRC#", "SNK#")).to_numpy()
    assert sorted(nb.neurons.loc[anchors, "cell_type"]) == sorted(b.neurons.loc[anchors, "cell_type"])
    assert (nb.neurons.loc[anchors, "cell_type"].to_numpy() != b.neurons.loc[anchors, "cell_type"].to_numpy()).any()
    fixed = list(b.stim_positions) + [int(x) for x in b.readout_positions]
    assert (nb.neurons.loc[fixed, "cell_type"].to_numpy() == b.neurons.loc[fixed, "cell_type"].to_numpy()).all()


def test_compare_pair_arms_pairs_runs_and_counts_failures():
    import importlib.util

    from brainir import paths

    spec = importlib.util.spec_from_file_location("compare_pair_arms", paths.repo_root() / "scripts" / "compare_pair_arms.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def rec(inst, seed, mode, ok, total):
        return {"method": "m", "mode": mode, "instance": inst, "seed": seed, "suite": "s", "_limit": 200,
                "score": {"both_success": ok, "budget": {"total": total}}}

    recs = [rec("i1", 0, "joint", True, 50), rec("i1", 0, "joint_null", False, 150), rec("i2", 0, "joint", True, 80),
            rec("i2", 0, "joint_null", True, 100), {"method": "m", "mode": "joint", "instance": "i3", "seed": 0, "suite": "s", "_limit": 200,
                                                     "error": "x"}, rec("i3", 0, "joint_null", True, 120)]
    r = mod.compare(recs, "m", "joint", "joint_null", n_boot=200)
    assert r["n_runs"] == 3 and r["wins"] == 1 and r["losses"] == 1
    assert r["success_a"] == pytest.approx(2 / 3) and r["success_diff"] == pytest.approx(0.0)
    assert r["calls_saved"] == pytest.approx(((150 - 50) + (100 - 80) + (120 - 200)) / 3)
    assert mod.sign_test(5, 0) == pytest.approx(2 / 32) and mod.sign_test(0, 0) is None


def test_independent_pooled_arm(tmp_path):
    pair, ver = _first_verified(PairSpec("ei_pair_oscillator", 50, 60, 31, n_readout=8))
    export_pair(pair, ver, tmp_path, salt="t")
    d = tmp_path / "instances" / pair.spec.label
    a, b = DiscoveryProblem.from_bundle(d, "a"), DiscoveryProblem.from_bundle(d, "b")
    res = independent_pooled(a, b, "greedy_reference", budget_a=120, budget_b=60, seed=0, config={"method_config": {"k": 2, "pool": 8}})
    ph = res.budget["phases"]
    assert ph[0]["allowance"] == 120 and ph[1]["allowance"] == 60 + (120 - ph[0]["calls"])
    assert res.budget["total"] == ph[0]["calls"] + ph[1]["calls"] <= 180 and res.correspondence == []
