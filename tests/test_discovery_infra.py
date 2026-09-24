"""Phase 2 discovery infrastructure on a tiny synthetic instance: problem loading, budgeted simulator, criteria,
interventions, result -> frozen prediction schema, greedy reference, tournament scoring. No oracle, no real data."""

from __future__ import annotations

import json
import shutil

import numpy as np
import pytest

from brainir.benchmark.prediction import BrainIRMechanismPrediction
from brainir.discovery import BudgetedSimulator, BudgetExhausted, DiscoveryProblem, DiscoveryResult, MethodRegistry, SimQuery, keep_only, silence
from brainir.discovery.criteria import criterion_from_spec
from brainir.discovery.interventions import canonical, random_partition, random_subsets
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import run_one, summarize
from brainir.sim.model import Trajectory


@pytest.fixture(scope="module")
def tiny_suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("suite")
    # a tiny background can put a parameter draw right at the rhythm threshold: take the first background seed that verifies
    for s in range(8):
        spec = InstanceSpec("ei_pair_oscillator", 40, s, n_readout=8)
        inst = build_instance(spec)
        ver = verify_instance(inst, seeds=[0, 1, 2])
        if ver["verified"]:
            break
    assert ver["verified"], ver
    export_instance(inst, ver, root, n_order_variants=2)
    return root, spec.label, ver


def test_instance_exports_public_files_and_separate_truth(tiny_suite):
    root, label, ver = tiny_suite
    d = root / "instances" / label
    assert (d / "model_config.json").exists() and (d / "manifest.json").exists()
    for net in ("main", "order1"):
        assert (d / "networks" / net / "criterion.json").exists()
    truth = json.loads((root / "truth" / f"{label}.json").read_text(encoding="utf-8"))
    assert set(truth["networks"]) == {"main", "order1"}
    # the two order variants are permutations of one graph: same edge multiset after un-permuting
    p0 = DiscoveryProblem.from_bundle(d, "main")
    p1 = DiscoveryProblem.from_bundle(d, "order1")
    perm0, perm1 = np.array(truth["networks"]["main"]["perm"]), np.array(truth["networks"]["order1"]["perm"])
    inv1 = np.empty_like(perm1); inv1[perm1] = np.arange(len(perm1))
    m = inv1[perm0]  # main position -> order1 position
    W0 = p0.W.toarray(); W1 = p1.W.toarray()
    assert np.array_equal(W0, W1[np.ix_(m, m)])
    # truth core positions differ between variants but denote the same neurons
    c0 = truth["networks"]["main"]["core_positions"]; c1 = truth["networks"]["order1"]["core_positions"]
    assert sorted(int(m[c]) for c in c0) == sorted(c1)
    # nothing in the public directory names the truth
    for f in d.rglob("*.json"):
        assert "core_positions" not in f.read_text(encoding="utf-8")


def test_problem_loading_and_candidates(tiny_suite):
    root, label, _ = tiny_suite
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    assert p.n == 40 and p.W.shape == (40, 40) and p.C.nnz >= p.W.nnz
    assert len(p.stim_positions) == 1 and p.readout_mask.sum() == 8
    cand = set(p.candidate_positions())
    assert not (cand & set(p.stim_positions)) and not (cand & set(p.readout_positions))
    assert p.criterion_spec["type"] == "rhythm" and len(p.network_hash()) == 64
    assert p.stimulus().indices == p.stim_positions


def test_budgeted_simulator_counts_caches_and_enforces(tiny_suite):
    root, label, _ = tiny_suite
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(p, max_calls=4)
    outs = sim.evaluate(None, [0, 1])
    assert sim.calls == 2 and all(o.passed for o in outs) and sim.simulated_seconds == pytest.approx(2 * p.model_cfg.t_end)
    again = sim.evaluate(None, [0, 1])
    assert sim.calls == 2 and sim.cache_hits == 2 and all(o.cached for o in again)
    # duplicate queries in one batch are simulated once
    sim.run_many([SimQuery(silence([int(p.candidate_positions()[0])]), 7)] * 3)
    assert sim.calls == 3
    with pytest.raises(BudgetExhausted):
        sim.run_many([SimQuery(None, 10), SimQuery(None, 11)])
    assert sim.calls == 3 and sim.remaining == 1
    assert canonical(keep_only(p, [3, 1]))["keep_only"] == [1, 3] and canonical(None)["kind"] == "intact"


def test_truth_is_exact_under_the_simulator(tiny_suite):
    root, label, ver = tiny_suite
    truth = json.loads((root / "truth" / f"{label}.json").read_text(encoding="utf-8"))["networks"]["main"]
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(p, max_calls=50)
    core = truth["core_positions"]
    assert sim.pass_fraction(keep_only(p, core), [0, 1]) >= 0.5
    for pos, ess in truth["essential_positions"].items():
        f = sim.pass_fraction(silence([int(pos)]), [0, 1])
        assert (f < 0.5) == bool(ess), (pos, f, ess)


def test_criteria_on_constructed_trajectories():
    t = np.arange(0, 1.0, 1e-3)
    n = 4
    readout = np.array([False, False, True, True])
    osc = 5 + 4 * np.sin(2 * np.pi * 10 * t)
    r = np.zeros((len(t), n)); r[:, 2] = osc; r[:, 3] = osc
    traj = Trajectory(t=t, r=r, info={"success": True})
    res = criterion_from_spec({"type": "rhythm"}).evaluate(traj, readout)
    assert res["passed"] and res["frequency_hz"] == pytest.approx(10.0, abs=0.5) and res["n_active_readout"] == 2
    ripple = np.zeros((len(t), n)); ripple[:, 2] = 1 + 0.05 * np.sin(2 * np.pi * 10 * t)
    res2 = criterion_from_spec({"type": "rhythm"}).evaluate(Trajectory(t=t, r=ripple, info={}), readout)
    assert res2["score"] > 0.5 and not res2["passed"]  # amplitude gate rejects the 0.1 Hz ripple
    band = criterion_from_spec({"type": "activity_band", "lo_hz": 2, "hi_hz": 20}).evaluate(traj, readout)
    assert band["passed"]
    flat = np.zeros((len(t), n)); flat[:, 2] = 30.0; flat[:, 3] = 30.0  # readout mean 30 Hz: above the band
    assert not criterion_from_spec({"type": "activity_band", "lo_hz": 2, "hi_hz": 20}).evaluate(Trajectory(t=t, r=flat, info={}), readout)["passed"]
    ramp = np.zeros((len(t), n)); ramp[:, 2] = 2 + 20 * t
    assert criterion_from_spec({"type": "ramp", "window_start_s": 0.1, "window_end_s": 0.9, "min_relative_slope": 0.5}).evaluate(
        Trajectory(t=t, r=ramp, info={}), readout)["passed"]
    pers = np.zeros((len(t), n)); pers[:, 2] = 10.0
    pspec = {"type": "persistence", "stimulus_off_s": 0.5, "settle_s": 0.1, "min_fraction": 0.5}
    assert criterion_from_spec(pspec).evaluate(Trajectory(t=t, r=pers, info={}), readout)["passed"]
    decay = pers.copy(); decay[t > 0.5, 2] = 0.0
    assert not criterion_from_spec(pspec).evaluate(Trajectory(t=t, r=decay, info={}), readout)["passed"]
    sel = np.zeros((len(t), n)); sel[:, 2] = 20.0; sel[:, 3] = 0.5
    sspec = {"type": "selectivity", "group_a_positions": [2], "group_b_positions": [3]}
    assert criterion_from_spec(sspec).evaluate(Trajectory(t=t, r=sel, info={}), readout)["passed"]


def test_group_designs_are_seeded_and_cover_candidates():
    rng = np.random.default_rng(1)
    cands = list(range(20))
    groups = random_partition(cands, 4, rng)
    assert sorted(x for g in groups for x in g) == cands and len(groups) == 4
    subs = random_subsets(cands, 5, 0.3, np.random.default_rng(2))
    assert len(subs) == 5 and all(set(s) <= set(cands) for s in subs)
    assert random_subsets(cands, 5, 0.3, np.random.default_rng(2)) == subs


def test_result_to_prediction_is_schema_valid(tiny_suite):
    root, label, _ = tiny_suite
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    core = [int(x) for x in p.candidate_positions()[:2]]
    res = DiscoveryResult(core=core, inclusion_probability={core[0]: 0.9, core[1]: 0.6, int(p.candidate_positions()[2]): 0.1},
                          roles={core[0]: ("recurrent_excitatory_core", 0.8)}, essential={core[0]: True}, alternatives=[core[::-1]],
                          predicted_frequency_hz=11.0, predicted_function_preserved=True, motif="test")
    from brainir.benchmark.prediction import MethodInfo
    pred = res.to_prediction(p, MethodInfo(name="t", version="0"))
    assert isinstance(pred, BrainIRMechanismPrediction) and pred.core_ids() == [int(p.public_ids[c]) for c in core]
    assert pred.core_neurons[0].confidence == 0.9 and pred.core_neurons[0].essential is True and pred.dynamics.rhythmic is True
    notes = json.loads(pred.mechanism.notes)
    assert "generic_roles" in notes and notes["alternatives"]
    BrainIRMechanismPrediction.from_json(pred.to_json())  # round trip


def test_greedy_reference_recovers_the_tiny_oscillator_and_is_scored(tiny_suite):
    root, label, _ = tiny_suite
    d = root / "instances" / label
    rec = run_one("greedy_reference", d, "main", budget=400, seed=0, config={"k": 2, "pool": 8, "replicates": 1},
                  truth_path=root / "truth" / f"{label}.json", score_seeds=[9], workers=1, robust=False)
    assert rec["structure"]["success"], rec["structure"]
    assert rec["result"]["budget"]["calls"] <= 400 and rec["function"]["nominal"] == 1.0
    s = summarize([rec])
    assert s["greedy_reference"]["success_rate"] == 1.0 and s["greedy_reference"]["n_runs"] == 1


def test_registry_lists_methods():
    assert "greedy_reference" in MethodRegistry.names()
    with pytest.raises(KeyError):
        MethodRegistry.get("no_such_method")


def test_cleanroom_copy_excludes_truth(tmp_path, tiny_suite):
    """The clean-room builder copies public instances but never a truth directory."""
    import importlib.util

    root, label, _ = tiny_suite
    from brainir import paths

    script = paths.repo_root() / "scripts" / "make_phase2_cleanroom.py"
    if not script.exists():
        pytest.skip("clean-room builder not present in this checkout")
    spec = importlib.util.spec_from_file_location("mk", script)
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    copied = mk._copy_tree(root, tmp_path / "copy")
    rel = {str(p.relative_to(tmp_path / "copy")).replace("\\", "/") for p in copied}
    assert any(r.startswith(f"instances/{label}/") for r in rel)
    assert not any("truth" in r for r in rel)
    shutil.rmtree(tmp_path / "copy")


def test_permuted_variant_preserves_graph_and_maps_back(tiny_suite, tmp_path):
    """Reliability sweeps permute node positions; the variant is the same graph and predictions map back to the source frame."""
    from brainir.discovery.reliability import consistency, make_permuted_bundle, to_common_frame

    root, label, _ = tiny_suite
    src = root / "instances" / label
    info = make_permuted_bundle(src, "main", seed=5, dest_root=tmp_path / "v")
    perm = info["perm"]
    p0 = DiscoveryProblem.from_bundle(src, "main")
    p1 = DiscoveryProblem.from_bundle(tmp_path / "v", "main")
    assert np.array_equal(p0.W.toarray()[np.ix_(perm, perm)], p1.W.toarray())
    assert sorted(int(perm[s]) for s in p1.stim_positions) == sorted(int(s) for s in p0.stim_positions)
    assert sorted(int(perm[r]) for r in p1.readout_positions) == sorted(int(r) for r in p0.readout_positions)
    assert p0.network_hash() != p1.network_hash()  # a different presentation of the same graph
    core_v = [int(x) for x in p1.candidate_positions()[:3]]
    from brainir.benchmark.prediction import MethodInfo
    pred = DiscoveryResult(core=core_v).to_prediction(p1, MethodInfo(name="t", version="0"))
    back = to_common_frame(pred, perm, info["positional"])
    assert back == sorted(int(perm[c]) for c in core_v)
    c = consistency([[1, 2, 3], [1, 2, 3], [1, 2, 4]])
    assert c["modal_core"] == [1, 2, 3] and c["modal_core_frequency"] == pytest.approx(2 / 3) and 0 < c["pairwise_jaccard_mean"] < 1


def test_pack_unpack_bundle_roundtrip(tiny_suite, tmp_path):
    from brainir.discovery.problem import pack_bundle, unpack_bundle

    root, label, _ = tiny_suite
    src = root / "instances" / label
    pack = pack_bundle(src, "main")
    assert "networks/main/neurons.parquet" in pack and "model_config.json" in pack
    unpack_bundle(pack, tmp_path / "u")
    assert DiscoveryProblem.from_bundle(tmp_path / "u", "main").network_hash() == DiscoveryProblem.from_bundle(src, "main").network_hash()


def test_causal_effect_cache_saves_compute_not_budget(tiny_suite, tmp_path):
    """The persistent store answers identical queries across runs, but every served query is still charged as a call."""
    from brainir.discovery.simulator import CausalEffectCache, sim_code_version

    root, label, _ = tiny_suite
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    store = CausalEffectCache(tmp_path / "effects.sqlite")
    s1 = BudgetedSimulator(p, max_calls=10, store=store)
    o1 = s1.evaluate(None, [0, 1])
    assert s1.calls == 2 and s1.computed_calls == 2 and s1.store_hits == 0 and len(store) == 2
    s2 = BudgetedSimulator(p, max_calls=10, store=store)
    o2 = s2.evaluate(None, [0, 1])
    assert s2.calls == 2 and s2.computed_calls == 0 and s2.store_hits == 2
    assert [o.score for o in o1] == [o.score for o in o2] and [o.passed for o in o1] == [o.passed for o in o2]
    assert np.array_equal(o1[0].active_positions, o2[0].active_positions)
    # another intervention (or seed) is never answered from the store
    cand = [int(x) for x in p.candidate_positions()[:3]]
    s2.evaluate(silence([cand[0]]), [0])
    s2.evaluate(keep_only(p, cand), [0])
    assert s2.computed_calls == 2
    rep = s2.report()
    assert rep["n_distinct_interventions"] == 3 and rep["n_candidate_mechanisms"] == 1
    assert rep["code_version"] == sim_code_version() and rep["cpu_seconds"] > 0 and rep["store_hits"] == 2
    # the budget binds even when the store could answer
    s3 = BudgetedSimulator(p, max_calls=1, store=store)
    with pytest.raises(BudgetExhausted):
        s3.evaluate(None, [0, 1])
    store.close()


def test_permuted_variant_verifies_and_hides_its_permutation(tiny_suite, tmp_path):
    """A node-order variant is a verifiable bundle on its own, and nothing inside it reveals the permutation."""
    from brainir.benchmark.bundle import verify_bundle
    from brainir.discovery.reliability import make_permuted_bundle

    root, label, _ = tiny_suite
    src = root / "instances" / label
    assert verify_bundle(src)["ok"]  # synthetic exports use the benchmark manifest format
    info = make_permuted_bundle(src, "main", seed=11, dest_root=tmp_path / "work" / "variants" / "order1")
    vdir = tmp_path / "work" / "variants" / "order1"
    v = verify_bundle(vdir)
    assert v["ok"], v
    inside = [p for p in vdir.rglob("*") if p.is_file()]
    assert not any("perm" in p.name or "_private" in p.as_posix() for p in inside)
    # nothing inside the variant names the permutation seed (a method could otherwise regenerate the permutation)
    for p in inside:
        if p.suffix in (".json", ".md"):
            text = p.read_text(encoding="utf-8")
            assert "order_variant_seed" not in text and "node_order_variant" not in text, p.name
    private = tmp_path / "work" / "variants__private" / "perm_order1_main.json"
    assert private.exists() and info["private_dir"] == str(private.parent)
    assert not str(private).startswith(str(vdir))


def test_meaning_preserving_perturbations(tiny_suite, tmp_path):
    """Anti-gaming transforms keep every existing position, the function and (except the parameter change) the dynamics."""
    from brainir.benchmark.bundle import verify_bundle
    from brainir.discovery.perturb import TRANSFORMS, perturb_bundle

    root, label, _ = tiny_suite
    src = root / "instances" / label
    p0 = DiscoveryProblem.from_bundle(src, "main")
    truth = json.loads((root / "truth" / f"{label}.json").read_text(encoding="utf-8"))["networks"]["main"]
    for t in TRANSFORMS:
        dest = tmp_path / t
        perturb_bundle(src, dest, t, seed=3, n_extra=12)
        assert verify_bundle(dest)["ok"], t
        p1 = DiscoveryProblem.from_bundle(dest, "main")
        assert p1.stim_positions == p0.stim_positions and (p1.readout_positions == p0.readout_positions).all()
        n0 = p0.n
        if t == "add_sink_distractors":
            assert p1.n == n0 + 12 and p1.W[:n0, :n0].toarray().tolist() == p0.W.toarray().tolist()
            assert p1.W[:n0, n0:].nnz == 0  # the new neurons send nothing into the original network
        elif t != "widen_parameters":
            assert (p1.W != p0.W).nnz == 0
        if t in ("reorder_edges", "resalt_tokens", "strip_annotations", "add_sink_distractors"):
            sim = BudgetedSimulator(p1, max_calls=4)
            assert sim.pass_fraction(keep_only(p1, truth["core_positions"]), [0, 1]) >= 0.5
    toks0 = set(p0.neurons["cell_type"])
    toks1 = set(DiscoveryProblem.from_bundle(tmp_path / "resalt_tokens", "main").neurons["cell_type"])
    assert "DNsyn" in toks1 and not ({t for t in toks0 if t.startswith("T#")} & toks1)


def test_cross_connectome_diagnostics_become_schema_claims(tiny_suite):
    root, label, _ = tiny_suite
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    core = [int(x) for x in p.candidate_positions()[:2]]
    res = DiscoveryResult(core=core, diagnostics={"cross_connectome": [{"source_position": core[0], "other_dataset": "synthetic-b",
                                                                        "other_version": "v", "other_source_id": 17, "confidence": 1.3}]})
    from brainir.benchmark.prediction import MethodInfo
    pred = res.to_prediction(p, MethodInfo(name="t", version="0"))
    assert len(pred.cross_connectome) == 1
    c = pred.cross_connectome[0]
    assert c.source_id == int(p.public_ids[core[0]]) and c.other_source_id == 17 and c.confidence == 1.0 and c.basis == "connectivity"
