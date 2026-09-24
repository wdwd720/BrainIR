"""Budget integrity and failure accounting of the Phase 2 harness (review F findings 1-3, 8-13, 16).

A method may only simulate through the BudgetedSimulator it is given; the harness counts real simulations and rejects runs that
bypass the budget, exceed it, or query reserved parameter seeds. Failed runs stay in every success denominator."""

from __future__ import annotations

import ast
import json
from pathlib import Path

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
    assert rep["total_calls"] == 3 and rep["children"][0]["pooled_with_parent"] is True


def test_spawned_simulators_draw_from_the_parent_budget(tiny):
    """One budget pool per run (review E finding 6): a child's calls reduce the parent's remaining calls, and a child can never
    spend more than the parent has left, whatever its own cap."""
    from brainir.discovery import BudgetExhausted

    root, label = tiny
    p = DiscoveryProblem.from_bundle(root / "instances" / label, "main")
    sim = BudgetedSimulator(p, max_calls=6)
    aux = sim.spawn(p, max_calls=100, kind="auxiliary")
    aux.evaluate(None, [0, 1, 2, 3])
    assert sim.remaining == 2 and aux.remaining == 2 and sim.calls == 0 and sim.total_calls() == 4
    with pytest.raises(BudgetExhausted):
        aux.evaluate(None, [4, 5, 6])
    sim.evaluate(None, [0, 1])  # the parent's own memo is separate from the child's: two new calls
    assert sim.remaining == 0 and aux.remaining == 0
    with pytest.raises(BudgetExhausted):
        sim.evaluate(None, [7])
    small = BudgetedSimulator(p, max_calls=10).spawn(p, max_calls=1)
    small.evaluate(None, [0])
    with pytest.raises(BudgetExhausted):
        small.evaluate(None, [1])  # the child's own cap still binds


def test_bundle_network_api(tiny, tmp_path):
    """Methods reach other networks of a bundle through the problem, never by reading files (review E finding 8)."""
    import shutil

    from brainir.discovery.problem import same_animal

    root, label = tiny
    src = root / "instances" / label
    dst = tmp_path / "bundle"
    shutil.copytree(src, dst)
    shutil.copytree(dst / "networks" / "main", dst / "networks" / "other")
    shutil.copytree(dst / "networks" / "main", dst / "networks" / "same")
    info = json.loads((dst / "networks" / "other" / "network.json").read_text(encoding="utf-8"))
    info["dataset"] = "another-dataset"
    (dst / "networks" / "other" / "network.json").write_text(json.dumps(info), encoding="utf-8")
    p = DiscoveryProblem.from_bundle(dst, "main")
    nets = p.bundle_networks()
    assert set(nets) == {"main", "other", "same"} and nets["same"]["same_dataset"] and not nets["other"]["same_dataset"]
    assert p.other_dataset_networks() == ["other"]
    q = p.load_network("other")
    assert q.n == p.n and not same_animal(p, q) and same_animal(p, DiscoveryProblem.from_bundle(dst, "same"))
    with pytest.raises(PermissionError):
        p.load_network("same")  # another version / node order of the same animal is refused
    with pytest.raises(KeyError):
        p.load_network("missing")


class _PeekTruth(DiscoveryMethod):
    name = "test_peek_truth"

    def discover(self, problem, sim, *, seed, config=None):
        suite = problem.root.parent.parent
        (suite / "truth" / f"{problem.root.name}.json").read_text(encoding="utf-8")  # must be refused
        return DiscoveryResult(core=[int(problem.candidate_positions()[0])])


class _ListTruth(DiscoveryMethod):
    name = "test_list_truth"

    def discover(self, problem, sim, *, seed, config=None):
        import os

        os.listdir(problem.root.parent.parent / "truth")  # must be refused
        return DiscoveryResult(core=[int(problem.candidate_positions()[0])])


def test_truth_is_unreachable_while_a_method_runs(tiny):
    """The truth guard (review E finding 7): reading or listing a truth directory during discover fails the run; scoring after
    the run still reads the truth; remote-style jobs never write the truth to disk."""
    from brainir.discovery.guard import guard_active, is_denied, truth_guard
    from brainir.discovery.problem import pack_bundle
    from brainir.discovery.tournament import run_one_job

    root, label = tiny
    d = root / "instances" / label
    tp = root / "truth" / f"{label}.json"
    for cls in (_PeekTruth, _ListTruth):
        rec = run_one_job((_register(cls), str(d), "main", 50, 0, {}, str(tp), [5001], False))
        assert "truth guard" in rec.get("error", ""), rec.get("error")
    ok = run_one_job((_register(_Honest), str(d), "main", 50, 0, {}, str(tp), [5001], False))
    assert "error" not in ok and "structure" in ok  # the scorer reads the truth after the run
    # a remote-style job: the instance is unpacked from the payload, the truth stays in memory
    packs = {label: pack_bundle(d, "main"), f"truth/{tp.name}": tp.read_bytes()}
    remote = run_one_job((_register(_Honest), f"/nonexistent/instances/{label}", "main", 50, 0, {}, f"/nonexistent/truth/{tp.name}",
                          [5001], False, packs))
    assert "error" not in remote and "structure" in remote
    peek = run_one_job((_register(_PeekTruth), f"/nonexistent/instances/{label}", "main", 50, 0, {}, f"/nonexistent/truth/{tp.name}",
                        [5001], False, packs))
    assert "error" in peek
    assert not guard_active() and not is_denied(d / "networks" / "main" / "edges.parquet")
    with truth_guard():
        assert is_denied(tp) and is_denied(root / "truth_backup" / "x.json") and is_denied(root / "BUILD_REPORT.json")
        assert not is_denied(d / "networks" / "main" / "edges.parquet")
    tp.read_text(encoding="utf-8")  # outside the guard nothing is refused
    # a root that contains the package itself (e.g. a Windows truth path parsed on a Linux worker -> parent ".") is refused
    import brainir

    pkg_dir = Path(brainir.__file__).resolve().parent
    for bad in (pkg_dir, pkg_dir.parent):
        with pytest.raises(ValueError, match="contains the brainir package"):
            with truth_guard(bad):
                pass
    assert not guard_active()


def test_remote_pair_job_with_a_foreign_truth_path(tmp_path):
    """Remote pair jobs keep the truth in memory; the local truth path must not become a guarded root on the worker."""
    from brainir.discovery.pair_tournament import pair_job
    from brainir.discovery.problem import pack_bundle
    from brainir.discovery.synthetic_pairs import PairSpec, build_pair, export_pair, verify_pair

    for s in range(6):
        pair = build_pair(PairSpec("ei_pair_oscillator", 40, 44, 50 + s, n_readout=8))
        ver = verify_pair(pair, seeds=[0, 1])
        if ver["verified"]:
            break
    export_pair(pair, ver, tmp_path, salt="t")
    name = pair.spec.label
    d = tmp_path / "instances" / name
    packs = {name: {**pack_bundle(d, "a"), **pack_bundle(d, "b")}, f"truth/{name}": (tmp_path / "truth" / f"{name}.json").read_bytes()}
    rec = pair_job(("greedy_reference", "independent", f"/nonexistent/instances/{name}", 0, 120, 120, {"method_config": {"k": 2, "pool": 8}},
                    "truth.json", packs))  # a bare file name: its parent is the working directory
    assert "error" not in rec, rec.get("error")
    assert "score" in rec


TRUTH_BEARING_MODULES = ("brainir.discovery.synthetic", "brainir.discovery.synthetic_pairs", "brainir.discovery.suite_audit",
                         "brainir.discovery.tournament", "brainir.discovery.pair_tournament", "brainir.discovery.reliability",
                         "brainir.discovery.perturb", "brainir.discovery.guard", "brainir.testing", "gc", "inspect", "ctypes", "pickle")
FILE_READ_ATTRS = {"read_text", "read_bytes", "read_parquet", "read_csv", "read_json", "read_table", "read_feather", "listdir",
                   "scandir", "iterdir", "glob", "rglob", "walk", "fromfile", "loadtxt", "genfromtxt", "import_module", "__import__",
                   "from_bundle"}  # other networks only through problem.load_network (other datasets; never a same-animal sibling)
FRAME_ATTRS = {"_getframe", "f_back", "f_locals", "f_globals", "gi_frame", "tb_frame", "cr_frame", "get_objects", "get_referrers"}


def _imports_a_method(call: ast.Call) -> bool:
    """``importlib.import_module("brainir.methods.<name>")`` (a registry lookup of a method module) is the one allowed dynamic import."""
    if not call.args:
        return False
    a = call.args[0]
    head = a.values[0] if isinstance(a, ast.JoinedStr) and a.values else a
    return isinstance(head, ast.Constant) and isinstance(head.value, str) and head.value.startswith("brainir.methods.")


def _method_logic_files():
    root = paths.repo_root() / "src" / "brainir"
    return sorted((root / "methods").glob("*.py")) + [root / "discovery" / "joint.py", root / "discovery" / "correspondence.py"]


def test_method_modules_cannot_reach_truth():
    """Static rules for method logic (review E finding 7): no truth-bearing imports (the synthetic generators can regenerate
    development truth), no file reads of their own (other networks come through ``DiscoveryProblem.load_network``), no dynamic
    imports, no frame or heap introspection."""
    bad = []
    for path in _method_logic_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        is_init = path.name == "__init__.py"
        # a module's command-line entry point (def main) loads bundles for its CLI; it is not method logic
        cli = [(f.lineno, f.end_lineno) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.name == "main"]
        for node in ast.walk(tree):
            if any(lo <= getattr(node, "lineno", 0) <= hi for lo, hi in cli):
                continue
            mods = []
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    anchor = {1: f"brainir.{path.parent.name}", 2: "brainir"}.get(node.level, "brainir")
                    base = f"{anchor}.{base}" if base else anchor
                mods = [base] + [f"{base}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            for m in mods:
                if any(m == f or m.startswith(f + ".") for f in TRUTH_BEARING_MODULES):
                    bad.append(f"{path.name}:{node.lineno}: imports {m}")
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name) and f.id in ("open", "__import__", "exec", "eval", "compile"):
                    bad.append(f"{path.name}:{node.lineno}: calls {f.id}()")
                if isinstance(f, ast.Attribute):
                    owner = f.value.id if isinstance(f.value, ast.Name) else None
                    if f.attr in FILE_READ_ATTRS and not (f.attr == "import_module" and (is_init or _imports_a_method(node))):
                        bad.append(f"{path.name}:{node.lineno}: calls .{f.attr}()")
                    if f.attr in ("load", "open", "fdopen") and owner in ("json", "np", "numpy", "io", "os", "codecs", "pickle", "pd"):
                        bad.append(f"{path.name}:{node.lineno}: calls {owner}.{f.attr}()")
            if isinstance(node, ast.Attribute) and node.attr in FRAME_ATTRS:
                bad.append(f"{path.name}:{node.lineno}: uses .{node.attr}")
    assert not bad, bad


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
