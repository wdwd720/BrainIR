"""Review E round 2, N1: the tournament driver runs the pre-registered selection rule END TO END (PROTOCOL 10): every fit seed is
evaluated and seed-averaged, the gate references (TRUE-STATE, full-state bound) get per-system rows, and `decide_round` ranks the
candidates against them. The end-to-end test builds a tiny toy tier and uses the benchmark references' own evaluations as stand-in
candidates (no model workers: the driver's assembly and decision are what is tested)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from brainir_causal import harness as H
from brainir_causal import suites as S

ROOT = Path(__file__).resolve().parents[2]


def _tournament():
    spec = importlib.util.spec_from_file_location("p4_tournament_under_test", ROOT / "scripts" / "p4" / "tournament.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["p4_tournament_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_level_b_refuses_fewer_than_three_seeds():
    T = _tournament()
    with pytest.raises(SystemExit):
        T.check_seeds([0], "B", "val")
    with pytest.raises(SystemExit):
        T.check_seeds([0, 1, 1], "B", "val")
    T.check_seeds([0, 1, 2], "B", "val")
    T.check_seeds([0], "B", "toy")                      # the test tiers are exempt


def test_decide_fails_loudly_without_true_state_rows(tmp_path):
    """A round with synthetic systems and no true-state reference row cannot be decided (the gate is never silently skipped)."""
    T = _tournament()
    from brainir_causal import select as SEL
    (tmp_path / "ROUND.json").write_text(json.dumps({"round": "r", "suite": "val", "methods": ["a"], "baselines": []}), encoding="utf-8")
    row = SEL.seed_average({0: {"s1": SEL.failed_system_values("synthetic")}})
    (tmp_path / "a.json").write_text(json.dumps({"per_system": {"s1": {"kind": "synthetic"}}, "seed_averaged": row, "seeds": [0, 1, 2]}),
                                     encoding="utf-8")
    with pytest.raises(ValueError, match="true-state reference"):
        T.decide_round(tmp_path, n_boot=100)


def test_method_names_of_per_developer_packages(tmp_path):
    """Method code lives in per-developer packages methods/<prefix>/ and a method is named "<prefix>.<module>:<name>" (or by its
    registered name): the round snapshot copies and hashes the subpackages, and every per-method file of a round uses a Windows-safe
    key."""
    T = _tournament()
    pkg = tmp_path / "room" / "src" / "brainir_causal" / "methods"
    (pkg / "dev_a").mkdir(parents=True)
    for rel, text in (("__init__.py", ""), ("dev_a/__init__.py", ""), ("dev_a/mod.py", "X = 1\n")):
        (pkg / rel).write_text(text, encoding="utf-8")
    dst, hashes = T.snapshot_methods(tmp_path / "round", tmp_path / "room")
    assert set(hashes) == {"__init__.py", "dev_a/__init__.py", "dev_a/mod.py"} and (dst / "dev_a" / "mod.py").exists()
    assert T.method_key("dev_a.mod:Model") == "dev_a.mod__Model" and T.method_key("plain") == "plain"
    assert ":" not in T.method_key("a:b:c") and "/" not in T.method_key("a/b")


def test_reference_rows_write_true_state_and_bound_rows(monkeypatch):
    """`reference_rows` (the gate references of PROTOCOL 10 rule 1): the TRUE-STATE row on synthetic systems only, with its fixed k
    repeated for every fit seed (stable by construction); the full-state bound from the reference's own verdict or from the chosen
    baseline's SEED-AVERAGED row."""
    T = _tournament()
    calls = []

    def fake_assemble(ev, refs, tol, **kw):
        calls.append((ev["sid"], ev["result"]["name"], kw["k_refits"], kw["level"]))
        return {"verdict": {"category": ev["result"]["name"]}, "selection": {"sid": ev["sid"], "name": ev["result"]["name"]}}
    monkeypatch.setattr(T.H, "assemble_verdict", fake_assemble)
    monkeypatch.setattr(T.H, "public_view", lambda v: v)
    monkeypatch.setattr(T.H, "verdict_effects", lambda res: None)
    systems = {"syn:a": {"kind": "synthetic"}, "real:b": {"kind": "real"}}
    refs_results = {"syn:a": {"true_state": {"name": "ts", "k": 2}, "full_state": {"name": "fs", "k": 6}},
                    "real:b": {"true_state": {"name": "ts", "k": 3}, "full_state": {"name": "fs"}}}
    bounds = {"full_state": {"syn:a": "ref:full_state", "real:b": "baseline:full_state_baseline"},
              "id_shortcut": {"syn:a": "ref:id_shortcut", "real:b": "ref:id_shortcut"}}
    method_rows = {"full_state_baseline": {"seed_averaged": {"real:b": {"A": False}}}}
    out = T.reference_rows(systems, refs_results, {"syn:a": {"truth_k": 2}}, bounds, method_rows, {}, True, [0, 1, 2], "B", 100, {})
    assert set(out["true_state"]) == {"syn:a"} and out["true_state"]["syn:a"]["source"] == "ref:true_state"
    assert out["true_state"]["syn:a"]["selection"] == {"sid": "syn:a", "name": "ts"}
    assert out["full_state_bound"]["syn:a"]["source"] == "ref:full_state"
    assert out["full_state_bound"]["real:b"] == {"kind": "real", "selection": {"A": False}, "source": "baseline:full_state_baseline"}
    assert ("syn:a", "ts", [2, 2, 2], "B") in calls and ("syn:a", "fs", [6, 6, 6], "B") in calls
    assert not any(c[0] == "real:b" for c in calls)                    # no true-state row on a real system


@pytest.fixture(scope="module", autouse=True)
def _test_salt(tmp_path_factory):
    """A hermetic test salt for every test of this module (phase4/tests/_hermetic.py): the real salt never leaves the orchestrator host,
    and the salted code paths run unchanged with another salt."""
    from _hermetic import hermetic_salt
    with hermetic_salt(tmp_path_factory.mktemp("salt")) as salt:
        yield salt


@pytest.fixture(scope="module")
def toy_round(tmp_path_factory, _test_salt):
    """A tiny toy tier (both toy systems), the references evaluated once per system, and two stand-in candidates x 3 fit seeds."""
    root = tmp_path_factory.mktemp("tour")
    saved = {k: getattr(S, k) for k in ("B_MAIN", "D0_DESIGN", "POOL_DRAWS", "POOL_TRAJ", "POOL_STATES", "POOL_FLOOR_STATES", "N_PASSIVE_TEST",
                                        "CELLS_PER_FAMILY", "STATES_PER_CELL", "ITEMS_PER_CATEGORY", "N_EQUIV_STATES", "N_LIFT_CASES")}
    S.B_MAIN = {"synthetic": 6, "full": 6, "mech": 6}
    S.D0_DESIGN = {"obs.nominal": 2, "obs.stim": 2, "obs.init": 1, "obs.wnoise": 1}
    S.POOL_DRAWS, S.POOL_TRAJ, S.POOL_STATES, S.POOL_FLOOR_STATES = 2, 3, 2, 2
    S.N_PASSIVE_TEST, S.CELLS_PER_FAMILY, S.STATES_PER_CELL, S.ITEMS_PER_CATEGORY = 4, 1, 2, 1
    S.N_EQUIV_STATES, S.N_LIFT_CASES = 2, 2
    sids = ["syn:toy:0", "syn:toy:1"]
    try:
        S.build_tier("toy", workers=1, systems=sids, root=root / "suites", store_root=root / "store")
    finally:
        for k, v in saved.items():
            setattr(S, k, v)
    internal_path = S.tier_dirs("toy", root / "suites")["base"] / "internal_records.json"
    systems = {sid: {"kind": "synthetic", "heldout_root": str(root / "suites"), "heldout_tier": "toy", "public_root": str(root / "suites"),
                     "public_tier": "toy", "internal_path": str(internal_path)} for sid in sids}
    refs_results, refs_meta = {}, {}
    for sid, sysd in systems.items():
        job = {"sid": sid, **sysd, "store_root": str(root / "store"), "ref_cache": str(root / "refcache"), "generator": None,
               "lift": False, "n_boot": 200, "ref_names": ["no_effect", "true_state", "full_state", "id_shortcut"], "return_results": True}
        rj = H.references_job(job)
        refs_results[sid] = rj["results"]
        refs_meta[sid] = {k: rj.get(k) for k in ("truth_k", "truth_noncompressible", "kind")}
    return root, systems, refs_results, refs_meta


@pytest.mark.slow
def test_run_then_decide_end_to_end_on_the_toy_tier(toy_round):
    T = _tournament()
    root, systems, refs_results, refs_meta = toy_round
    seeds = [0, 1, 2]
    # method names in the per-developer package layout (methods/<prefix>/<module>.py, named "<prefix>.<module>:<name>")
    m_true, m_noeff = "dev_a.stand_in:m_true", "dev_b.stand_in:m_noeff"
    stand_in = {m_true: "true_state", m_noeff: "no_effect"}
    round_dir, out_dir = root / "run" / "r1", root / "out" / "r1"
    out_dir.mkdir(parents=True)
    method_evals = {m: {sd: {} for sd in seeds} for m in stand_in}
    for m, ref in stand_in.items():
        for sd in seeds:
            for sid in systems:
                res = refs_results[sid][ref]
                method_evals[m][sd][sid] = {"sid": sid, "kind": "synthetic", "result": res, **{k: refs_meta[sid][k] for k in ("truth_k",
                                                                                                                          "truth_noncompressible")}}
                side = round_dir / T.method_key(m) / "fits" / f"{S._safe(sid)}_s{sd}.json"
                side.parent.mkdir(parents=True, exist_ok=True)
                side.write_text(json.dumps({"info": {"k": {sid: res.get("k") if res.get("k") is not None else 1}},
                                            "compute": {"cpu_s": 1.0 + sd}}), encoding="utf-8")
    fit_specs = [(m, sid, sd, None) for m in stand_in for sid in systems for sd in seeds]
    fit_recs = [{"ok": True}] * len(fit_specs)
    bounds = T.choose_bounds(refs_results, method_evals, systems)
    report = {"round": "r1", "suite": "toy", "methods": sorted(stand_in), "baselines": [], "results": {}}
    args = SimpleNamespace(tolerances=None, n_boot=200)
    T.assemble_round(args, report, sorted(stand_in), systems, method_evals, refs_results, bounds, round_dir, seeds, "B", fit_specs,
                     fit_recs, out_dir, refs_meta=refs_meta)
    H.dump({k: v for k, v in report.items() if k != "results"}, out_dir / "ROUND.json")
    for m in stand_in:
        r = json.loads((out_dir / f"{T.method_key(m)}.json").read_text(encoding="utf-8"))
        assert r["seeds"] == seeds
        for sid in systems:
            row = r["per_system"][sid]
            assert sorted(int(s) for s in row["seeds"]) == seeds and len(row["k_values"]) == 3
            assert row["seed_averaged"]["n_seeds"] == 3
    ts = json.loads((out_dir / "true_state.json").read_text(encoding="utf-8"))
    assert sorted(ts["per_system"]) == sorted(systems)
    assert json.loads((out_dir / "full_state_bound.json").read_text(encoding="utf-8"))["per_system"]
    rep = T.decide_round(out_dir, n_boot=200)
    assert sorted(rep["order"]) == sorted(stand_in) and rep["n_fit_seeds"] == {m: 3 for m in stand_in}
    assert rep["gates"][m_true]["kinds"]["synthetic"]["applies"] and rep["references"]["true_state_systems"] == sorted(systems)
    # the TRUE-STATE stand-in meets the gates (its rates equal the reference's); a candidate that never passes A cannot rank above it
    assert rep["gates"][m_true]["eligible"] is True
    assert rep["order"].index(m_true) <= rep["order"].index(m_noeff)
    assert (out_dir / "DECISION.json").exists() and (out_dir / "AGGREGATE_developer_facing.json").exists()
