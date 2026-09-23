"""Contract tests for the DNg100 baseline methods (no real data).

Each baseline under benchmarks/dng100/baselines exposes a pure ``select_core(neurons, edges, stimulus_ids, readout_ids, k, seed)``
and a ``build_prediction`` helper. They are exercised on a 12-neuron synthetic network shaped like ``neurons.parquet`` /
``edges.parquet`` of the public bundle (also written to a temporary bundle directory so each method's ``main`` runs end to end
through the same environment contract as the clean-room runner). Source-level checks enforce the clean-room import rules.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brainir import paths
from brainir.benchmark.prediction import BrainIRMechanismPrediction

BASELINES = paths.repo_root() / "benchmarks" / "dng100" / "baselines"
METHODS = ["random_matched", "degree_topk", "pagerank", "betweenness_stim_to_readout", "kcore_scc", "recurrence_loop", "community",
           "statistical_motif", "greedy_prune_sim"]
STIM = [0]
READOUT = [9, 10, 11]
INTERNEURONS = list(range(1, 9))
SIGN = [1, 1, 1, 1, 1, 1, -1, -1, 0, 1, 1, 1]  # neuron 6, 7 inhibitory; 8 unknown NT (sign 0); motor neurons cholinergic
EDGES = [(0, 1, 30), (0, 2, 20), (0, 3, 10), (0, 6, 8), (1, 2, 25), (2, 1, 15), (1, 6, 12), (6, 1, 9), (6, 2, 6), (2, 3, 7), (3, 4, 6),
         (4, 5, 5), (5, 4, 5), (4, 7, 5), (7, 3, 6), (8, 5, 6), (1, 9, 20), (2, 10, 18), (6, 11, 10), (3, 9, 5), (7, 8, 0)]
"""(pre, post, synapse_count). 8 -> 5 is an anatomical edge with signed_weight 0 (unknown presynaptic sign), as the public bundle
keeps them; 7 -> 8 is a degenerate zero-count row that graph builders must tolerate."""


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"dng100_baseline_{name}", BASELINES / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tiny_network() -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = list(range(12))
    role = ["descending"] + ["vnc_intrinsic"] * 8 + ["vnc_motor"] * 3
    super_class = ["descending_neuron"] + ["intrinsic_neuron"] * 8 + ["motor_neuron"] * 3
    nt = ["acetylcholine" if s > 0 else "gaba" if s < 0 else "unknown" for s in SIGN]
    neurons = pd.DataFrame({
        "position": ids, "source_id": ids, "cell_type": ["DNxx001"] + [f"T#{i:010x}" for i in range(1, 9)] + ["MNfl1", "MNfl2", "MNfl3"],
        "instance": [None] * 12, "super_class": super_class, "sub_class": ["xl"] + ["BI"] * 8 + ["fl"] * 3, "role_class": role,
        "side": ["L"] * 12, "soma_neuromere": ["T1"] * 12, "hemilineage": [None] * 12, "nt_label": nt, "sign": np.array(SIGN, dtype=np.int8),
        "size_voxels": np.linspace(1.0e9, 2.0e9, 12), "is_stimulus": [i in STIM for i in ids], "is_readout": [i in READOUT for i in ids]})
    pre = np.array([e[0] for e in EDGES]); post = np.array([e[1] for e in EDGES]); cnt = np.array([e[2] for e in EDGES], dtype=np.int32)
    edges = pd.DataFrame({"pre_id": pre.astype(np.int64), "post_id": post.astype(np.int64), "pre_position": pre.astype(np.int32),
                          "post_position": post.astype(np.int32), "synapse_count": cnt, "signed_weight": (cnt * np.array(SIGN)[pre]).astype(np.int32)})
    neurons["out_pairs"] = neurons["source_id"].map(edges.groupby("pre_id").size()).fillna(0).astype(np.int64)
    neurons["in_pairs"] = neurons["source_id"].map(edges.groupby("post_id").size()).fillna(0).astype(np.int64)
    return neurons, edges


def bundle_data(neurons: pd.DataFrame, edges: pd.DataFrame) -> dict:
    return {"neurons": neurons, "edges": edges, "stimulus": {"cell_type": "DNxx001", "source_ids": STIM, "positions": STIM, "current": 100.0},
            "readout": {"n": len(READOUT), "source_ids": READOUT, "positions": READOUT}, "info": {"name": "tiny", "dataset": "synthetic", "version": "v0"},
            "manifest": {"benchmark_id": "dng100-benchmark-v1"}, "model_config": {}}


@pytest.fixture(scope="module")
def tiny() -> dict:
    neurons, edges = tiny_network()
    zero = edges[(edges["pre_id"] == 8) & (edges["post_id"] == 5)]
    assert int(zero["synapse_count"].iloc[0]) == 6 and int(zero["signed_weight"].iloc[0]) == 0  # the fixture carries a sign-0 edge
    return bundle_data(neurons, edges)


@pytest.fixture(scope="module")
def tiny_bundle(tmp_path_factory, tiny) -> Path:
    """The tiny network written in the public-bundle layout, so each method's main() can run through the environment contract."""
    root = tmp_path_factory.mktemp("tiny_bundle")
    d = root / "networks" / "tiny"
    d.mkdir(parents=True)
    tiny["neurons"].to_parquet(d / "neurons.parquet", index=False)
    tiny["edges"].to_parquet(d / "edges.parquet", index=False)
    for name in ("stimulus", "readout", "info"):
        (d / (("network" if name == "info" else name) + ".json")).write_text(json.dumps(tiny[name]), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(tiny["manifest"]), encoding="utf-8")
    (root / "model_config.json").write_text(json.dumps({"config": {}, "metric": {"analysis_start_s": 0.25, "rhythmic_threshold": 0.5}}), encoding="utf-8")
    return root


class StubScorer:
    """Deterministic stand-in for the simulation scorer: the rhythm needs the closed triangle {1, 2, 6}."""

    rhythmic = 0.5

    def __init__(self):
        self.calls = 0

    def keep_scores(self, sets, n_replicates=None):
        self.calls += len(sets)
        return [1.0 if {1, 2, 6} <= set(s) else 0.3 * len({1, 2, 6} & set(s)) / 3 for s in sets]

    def silence_scores(self, sets, n_replicates=None):
        return [0.0 if set(s) & {1, 2} else 0.9 for s in sets]


def _select(mod, name, tiny, k=3, seed=0):
    kw = {"scorer": StubScorer()} if name == "greedy_prune_sim" else {}
    return mod.select_core(tiny["neurons"], tiny["edges"], STIM, READOUT, k, seed=seed, **kw)


@pytest.mark.parametrize("name", METHODS)
def test_select_core_contract(name, tiny):
    mod = _load(name)
    core, detail = _select(mod, name, tiny)
    again, _ = _select(mod, name, tiny)
    assert core == again, "selection must be deterministic for a fixed seed"
    assert len(core) == 3 and len(set(core)) == 3
    assert not (set(core) & set(STIM)) and not (set(core) & set(READOUT))
    assert set(core) <= set(INTERNEURONS)
    assert all(isinstance(i, int) for i in core) and isinstance(detail, dict)
    core4, _ = _select(mod, name, tiny, k=4)
    assert len(core4) == 4 and len(set(core4)) == 4
    essential = detail.get("essential") if name == "greedy_prune_sim" else None
    pred = mod.build_prediction(tiny, core, seed=0, compute={"wall_time_s": 0.0}, essential=essential)
    assert isinstance(pred, BrainIRMechanismPrediction) and pred.core_ids() == core
    assert pred.method.name.startswith("baseline_") and pred.method.random_seed == 0 and pred.method.inputs_used
    for c in pred.core_neurons:
        s = SIGN[c.source_id]
        assert c.role == ("excitatory" if s > 0 else "inhibitory" if s < 0 else "unknown")
        if name != "greedy_prune_sim":
            assert c.essential is None
    assert BrainIRMechanismPrediction.from_json(pred.to_json()) == pred


@pytest.mark.parametrize("name", METHODS)
def test_main_runs_through_the_environment_contract(name, tiny_bundle, tmp_path, monkeypatch):
    mod = _load(name)
    out = tmp_path / f"prediction_{name}.json"
    monkeypatch.setenv("BRAINIR_BUNDLE", str(tiny_bundle))
    monkeypatch.setenv("BRAINIR_NETWORK", "tiny")
    monkeypatch.setenv("BRAINIR_OUT", str(out))
    monkeypatch.setenv("BRAINIR_SEED", "3")
    argv = ["--workers", "1", "--replicates", "1", "--t-end", "0.6", "--pool", "3"] if name == "greedy_prune_sim" else []
    if name == "statistical_motif":
        argv = ["--shuffles", "10"]
    mod.main(argv)
    pred = BrainIRMechanismPrediction.from_json(out.read_text(encoding="utf-8"))
    assert len(pred.core_neurons) == 3 and pred.method.random_seed == 3 and pred.dataset == "synthetic"
    assert set(pred.core_ids()) <= set(INTERNEURONS)
    if name == "greedy_prune_sim":
        assert all(c.essential in (True, False) for c in pred.core_neurons)
        assert pred.method.compute["simulations"] > 0
        assert (tmp_path / f"greedy_trace_{name}.json").exists()


def test_random_matched_composition_and_seed_dependence(tiny):
    mod = _load("random_matched")
    assert mod.sign_composition(3) == (2, 1) and mod.sign_composition(4) == (3, 1) and mod.sign_composition(5) == (3, 2)
    core, detail = mod.select_core(tiny["neurons"], tiny["edges"], STIM, READOUT, 3, seed=0)
    signs = [SIGN[i] for i in core]
    assert signs.count(1) == 2 and signs.count(-1) == 1
    assert set(core) <= mod.downstream_within(tiny["edges"], STIM, 2)
    cores = {tuple(mod.select_core(tiny["neurons"], tiny["edges"], STIM, READOUT, 3, seed=s)[0]) for s in range(20)}
    assert len(cores) > 1, "different seeds must be able to give different draws"


def test_structural_helpers_on_the_tiny_network(tiny):
    deg = _load("degree_topk")
    assert deg.stimulus_contact(tiny["edges"], STIM).to_dict() == {1: 30, 2: 20, 3: 10, 6: 8}
    assert deg.select_core(tiny["neurons"], tiny["edges"], STIM, READOUT, 3)[0] == [1, 2, 3]
    loop = _load("recurrence_loop")
    core, detail = loop.select_core(tiny["neurons"], tiny["edges"], STIM, READOUT, 3)
    assert detail["hub"] == 1 and core[0] == 1 and set(core) == {1, 2, 6}  # hub + excitatory 2-cycle partner + inhibitory 2-cycle partner
    bet = _load("betweenness_stim_to_readout")
    bc = bet.stim_readout_betweenness(tiny["edges"], STIM, READOUT)
    assert bc[1] > 0 and bc[2] > 0 and bc[6] > 0 and bc.get(8, 0) == 0
    kc = _load("kcore_scc")
    g = kc.directed_graph(tiny["neurons"], tiny["edges"])
    assert kc.reachable_largest_scc(g, STIM) == {3, 4, 5, 7}
    sm = _load("statistical_motif")
    z = sm.enrichment_z(tiny["neurons"], tiny["edges"], STIM, seed=0, n_shuffles=20, n_bins=4)
    assert list(z.loc[[1, 2, 3, 6], "S"]) == [30, 20, 10, 8] and int(z.loc[1, "R"]) == 15 + 9 and np.isfinite(z["z_S"]).all()
    assert np.allclose(sm.rank_normal(np.array([1.0, 2.0, 3.0])), -sm.rank_normal(np.array([3.0, 2.0, 1.0])))


def test_greedy_prune_keeps_the_neurons_the_score_depends_on():
    mod = _load("greedy_prune_sim")
    scorer = StubScorer()
    tiebreak = {1: 100.0, 2: 90.0, 6: 50.0, 3: 40.0, 4: 30.0}
    core, trace = mod.greedy_prune([1, 2, 3, 4, 6], 3, scorer.keep_scores, tiebreak, rhythmic=0.5)
    assert set(core) == {1, 2, 6} and len(trace) == 2 and [t["removed"] for t in trace] == [[4], [3]]  # lowest-degree tie-break first
    # batch mode above the one-by-one threshold, with the rhythm check halving the batch when it would break the rhythm
    pool = [1, 2, 6] + list(range(100, 110))
    core, trace = mod.greedy_prune(pool, 3, scorer.keep_scores, {v: float(v) for v in pool}, rhythmic=0.5, one_by_one_below=4, batch_fraction=0.5)
    assert set(core) == {1, 2, 6} and all(not t.get("budget_exhausted") for t in trace)
    # an expired budget returns the k most impactful candidates by the last leave-one-out ranking without further simulation
    core, trace = mod.greedy_prune([1, 2, 3, 4, 6], 3, scorer.keep_scores, tiebreak, rhythmic=0.5, deadline=time.time() - 1)
    assert len(core) == 3 and trace[-1]["budget_exhausted"]


def test_greedy_simulation_scorer_runs_on_the_tiny_network(tiny):
    mod = _load("greedy_prune_sim")
    st = mod.sim_state(tiny, t_end=0.6)
    s_keep = mod.score_simulation(st, "keep", (1, 2, 6), seed=1)
    s_sil = mod.score_simulation(st, "silence", (1,), seed=1)
    assert 0.0 <= s_keep <= 1.0 and 0.0 <= s_sil <= 1.0
    assert mod.candidate_pool(tiny["neurons"], tiny["edges"], STIM, READOUT)[:1] == [1]  # highest weighted degree first


FORBIDDEN_IMPORT = re.compile(r"^\s*(from|import)\s+(benchmarks|oracle|evaluate)\b", re.M)
ALLOWED_TOP_LEVEL = {"numpy", "scipy", "pandas", "networkx", "brainir", "argparse", "datetime", "json", "os", "time", "pathlib", "collections",
                     "concurrent", "sys", "math", "re", "itertools", "functools", "typing", "__future__"}


@pytest.mark.parametrize("name", METHODS)
def test_baseline_sources_respect_the_clean_room(name):
    src = (BASELINES / f"{name}.py").read_text(encoding="utf-8")
    assert not FORBIDDEN_IMPORT.search(src), "baselines must not import benchmark/evaluator code"
    tree = ast.parse(src)
    doc = ast.get_docstring(tree) or ""
    body = src.replace(doc, "", 1).lower()
    for word in ("oracle", "answer"):
        assert word not in body, f"{name}.py mentions {word!r} outside its docstring"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] in ALLOWED_TOP_LEVEL, a.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in ALLOWED_TOP_LEVEL, node.module
    assert "C:\\" not in src and "/Users/" not in src
