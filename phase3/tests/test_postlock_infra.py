"""Post-lock infrastructure (orchestrator side): counterexample search (protocol determinism, in-family flags, deduplication,
aggregation), ablations (reading the switch table without executing code, paired differences, verdict transitions), the self-audit
(history slicing, trap logic, log parsing) and the compute summary (ledger parsing without double counting)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
import ablations as AB  # noqa: E402
import compute_summary as CS  # noqa: E402
import counterexamples as CX  # noqa: E402
import self_audit as SA  # noqa: E402


# ------------------------------------------------------------------------------------------------ counterexamples
def _job(kind="synthetic", strategy="evolve", seed=0, system="syn-x"):
    return {"system": system, "kind": kind, "tier": "dev", "strategy": strategy, "seed": seed, "budget": 8, "objective": "post",
            "init_state": True, "horizon_s": 1.0, "seed_source": "public_synthetic" if kind == "synthetic" else "public_real",
            "info": {"observed": [3, 5, 7, 9, 11], "input_dim": 1}, "x_stats": {"mean": [0.0] * 5, "sd": [0.5, 1.0, 2.0, 1.0, 1.0]}}


def _protocols(job, n=6):
    dom = CX.Domain(job, CX.job_rng(job), ["kick", "current", "silence"])
    return [dom.random_protocol(init_state=True) for _ in range(n)]


def test_protocols_are_deterministic_per_job_and_differ_across_seeds():
    a = [CX.phash(p) for p in _protocols(_job())]
    b = [CX.phash(p) for p in _protocols(_job())]
    c = [CX.phash(p) for p in _protocols(_job(seed=1))]
    d = [CX.phash(p) for p in _protocols(_job(strategy="random"))]
    assert a == b
    assert a != c and a != d


def test_protocol_times_lie_on_the_grid_and_after_the_start():
    for p in _protocols(_job(), 20):
        for e in p["events"]:
            t = e.get("t", e.get("t0"))
            assert 0.25 * 4.0 <= t <= 0.95 * 4.0
            assert abs(round(t / 0.01) * 0.01 - t) < 1e-9
            if e["kind"] == "kick":
                assert 1 <= len(e["delta"]) <= 3


def test_in_family_flags():
    xs = {"3": 0.5}
    assert CX.in_family({"kind": "kick", "t": 1.0, "delta": {"3": 1.0}}, "synthetic", xs)          # 2 sd
    assert not CX.in_family({"kind": "kick", "t": 1.0, "delta": {"3": 3.0}}, "synthetic", xs)      # 6 sd
    assert CX.in_family({"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {"3": 10.0}}, "real", {})
    assert not CX.in_family({"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {"3": -10.0}}, "real", {})   # real currents excite


def _cand(err, sig, dims, h):
    return {"err": err, "err_post": err, "err_dims": dims, "signature": sig, "hash": h, "in_family": [True], "init_state": False,
            "phase": "random"}


def test_dedup_merges_equivalent_counterexamples_only():
    s1, s2 = [["kick", [3]]], [["silence", [3, 5]]]
    cands = [_cand(10.0, s1, [9.0, 1.0], "a"), _cand(9.8, s1, [8.8, 1.0], "b"),          # same structure, same profile -> one
             _cand(5.0, s1, [4.5, 0.5], "c"),                                             # same structure, error too different
             _cand(9.9, s1, [1.0, 9.0], "d"),                                             # different error profile
             _cand(9.7, s2, [9.0, 1.0], "e")]                                             # different targets / kind
    cl = CX.dedup(cands)
    assert len(cl) == 4
    top = cl[0]
    assert top["rep"]["hash"] == "a" and top["n_members"] == 2 and set(top["members"]) == {"a", "b"}


def test_aggregate_reference_distribution_threshold_and_immediacy():
    rng = np.random.default_rng(0)
    rows = [{"phase": "random", "err": float(v), "err_post": float(v), "err_dims": [float(v)], "signature": [["kick", [3]]],
             "hash": f"r{i}", "in_family": [True], "init_state": False} for i, v in enumerate(rng.uniform(0.1, 0.5, 30))]
    bad = {"phase": "search", "err": 50.0, "err_post": 50.0, "err_dims": [50.0], "signature": [["silence", [5]]], "hash": "bad",
           "in_family": [True], "init_state": False}
    res = [{"job": {"system": "s", "strategy": "evolve", "seed": 0}, "rows": rows[:15] + [bad], "top": []},
           {"job": {"system": "s", "strategy": "random", "seed": 0}, "rows": rows[15:], "top": []}]
    out = CX.aggregate(res, abs_threshold=1.0, rel_factor=2.0, immediate_n=10)
    v = out["systems"]["s"]
    assert v["threshold"] == pytest.approx(1.0)                        # max(1, 2 x p90 of U(0.1, 0.5))
    assert v["n_candidates"] == 1 and v["n_distinct"] == 1
    assert v["broken_immediately_fraction"] == 0.0                     # the counterexample came after the first 10 protocols
    assert out["overall"]["n_systems_with_counterexamples"] == 1


def test_compare_results_detects_divergence():
    a = [{"job": {"system": "s", "strategy": "random"}, "rows": [{"hash": "x", "err": 1.0}, {"hash": "y", "err": 2.0}]}]
    b = [{"job": {"system": "s", "strategy": "random"}, "rows": [{"hash": "x", "err": 1.0}, {"hash": "y", "err": 2.0 + 1e-12}]}]
    c = [{"job": {"system": "s", "strategy": "random"}, "rows": [{"hash": "x", "err": 1.0}, {"hash": "z", "err": 2.0}]}]
    assert CX.compare_results(a, b)["all_equivalent"]
    assert not CX.compare_results(a, c)["all_equivalent"]


# ------------------------------------------------------------------------------------------------ ablations
def test_read_ablations_parses_without_executing(tmp_path):
    (tmp_path / "mymethod.py").write_text('raise RuntimeError("must never run")\nname = "mymethod"\n'
                                          'ABLATIONS = {"delays": "no delays", "sparsity": "no thresholding"}\n', encoding="utf-8")
    assert AB.read_ablations(tmp_path, "mymethod") == {"delays": "no delays", "sparsity": "no thresholding"}
    with pytest.raises(SystemExit):
        AB.read_ablations(tmp_path, "other")


def _rec(a, c, d_up, e, k2, exact, verdict="partially supported"):
    return {"A_over_full": a, "verdict": {"C": c, "D_ci95": [d_up - 0.1, d_up], "E_ratio": e, "E_testable": True, "verdict": verdict},
            "K": {"r2_true_from_model_rff": k2, "r2_model_from_true_rff": k2}, "K_dim": {"exact": exact}}


def test_paired_vs_full_directions_failures_and_transitions():
    comp = [f"s{i}" for i in range(12)]
    full = {s: _rec(1.1, 0.5, 0.1, 0.01, 0.95, True, "compact causal state discovered") for s in comp}
    var = {s: _rec(1.3, 0.4, -0.2, 0.01, 0.90, i % 2 == 0) for i, s in enumerate(comp)}
    var["s11"] = {"error": "fit failed"}
    out = AB.paired_vs_full(full, var, comp, n_boot=200)
    assert out["S1_A_over_full"]["median_diff"] == pytest.approx(0.2) and out["S1_A_over_full"]["frac_variant_worse"] == 1.0
    assert out["S2_C_heldout"]["frac_variant_better"] == 1.0
    assert out["S3_D_micro_gain"]["median_diff"] == pytest.approx(-0.1)        # max(0, upper CI): 0.1 -> 0 (version 3)
    assert out["S5_K_r2_rff"]["frac_variant_worse"] == 1.0                     # higher is better
    assert out["S1_A_over_full"]["n_failed_variant_only"] == 1 and out["S1_A_over_full"]["n"] == 11
    assert out["S6_exact_k_rate"]["full"] == 1.0 and out["S6_exact_k_rate"]["variant"] == pytest.approx(6 / 12)
    tr = AB.verdict_transitions(full, var, comp)
    assert tr["compact causal state discovered -> partially supported"] == 11
    assert tr["compact causal state discovered -> failed"] == 1


# ------------------------------------------------------------------------------------------------ self-audit
def test_self_audit_history_slicing_check_passes():
    class A:
        probe_prefix = False
    ctx = type("C", (), {"a": A()})()
    r = SA.q4(ctx)
    assert r["status"] == SA.PASS and r["evidence"]["evaluator_passes_only_the_history"]


class _Ctx:
    def __init__(self, per_sys, truth):
        self.method = "m"
        self._f = {"m": {"per_system": per_sys}}
        self._t = {"systems": truth}

    def mfinal(self):
        return self._f["m"]

    def truth(self):
        return self._t

    def trap_systems(self, letter):
        return sorted(s for s, v in self._t["systems"].items() if v.get("trap") == letter)


def test_trap_logic_fooled_handled_abstained():
    truth = {"t1": {"trap": "C", "k": 1}, "t2": {"trap": "C", "k": 1}, "t3": {"trap": "C", "k": 1}}
    k = lambda r2: {"r2_true_from_model_rff": r2, "r2_model_from_true_rff": r2}   # noqa: E731
    per = {"t1": {"verdict": {"verdict": SA.FULL_VERDICTS[0], "abstention": {}}, "K": k(0.95)},
           "t2": {"verdict": {"verdict": "not supported", "abstention": {"no_compact_state": True}}, "K": k(0.1)},
           "t3": {"verdict": {"verdict": SA.FULL_VERDICTS[0], "abstention": {}}, "K": k(0.2)}}
    out = SA._trap(_Ctx(per, truth), "C")
    rows = {r["system"]: r for r in out["rows"]}
    assert rows["t1"]["handled"] and not rows["t1"]["fooled"]
    assert rows["t2"]["handled"] and rows["t2"]["abstained"]
    assert rows["t3"]["fooled"] and out["status"] == SA.FAIL
    del per["t3"]
    truth.pop("t3")
    assert SA._trap(_Ctx(per, truth), "C")["status"] == SA.PASS


def test_md_rows_and_hidden_log_consistency(tmp_path, monkeypatch):
    (tmp_path / "LEVELB_LOG.md").write_text("# log\n\n| time (UTC) | round | suite | methods | result file |\n|---|---|---|---|---|\n"
                                            "| 2026-01-01T00:00:00Z | final_b | final | m | x |\n", encoding="utf-8")
    (tmp_path / "HIDDEN_EVALUATIONS.md").write_text("# log\n\n| time (UTC) | attempt | what | method / baseline | reason | outputs |\n"
                                                    "|---|---|---|---|---|---|\n| 2026-01-01T01:00:00Z | 01 | Level C START (real hidden) | m / b | "
                                                    "first and only planned Level C evaluation | research/phase3/level_c/01/ |\n",
                                                    encoding="utf-8")
    (tmp_path / "level_c" / "01").mkdir(parents=True)
    monkeypatch.setattr(SA, "P3", tmp_path)

    class A:
        method, final_round, level_c = "m", "", ""
    ctx = SA.Ctx(A())
    assert ctx.final_round == "final_b"
    r = SA.i8(ctx)
    assert r["status"] == SA.FAIL and any("final_b" in p for p in r["evidence"]["problems"])     # the confirmation is not logged
    with open(tmp_path / "HIDDEN_EVALUATIONS.md", "a", encoding="utf-8") as fh:
        fh.write("| 2026-01-01T00:30:00Z | final_b | Level B confirmation | m | planned | research/phase3/tournament/final_b/ |\n")
    assert SA.i8(SA.Ctx(A()))["status"] == SA.PASS


# ------------------------------------------------------------------------------------------------ compute summary
def test_ledger_rows_skip_runs_with_their_own_records(tmp_path, monkeypatch):
    (tmp_path / "COSTS_LEDGER.md").write_text(
        "# ledger\n\n## Modal\n\n| time | job | app | calls | container-s | ~USD |\n|---|---|---|---|---|---|\n"
        "| 01:00 | CALIBRATION v2, 45 dev systems | ap-1 | 45 | 14,303 | 2.10 |\n"
        "| 02:00 | round r9_x on Modal | ap-2 | 10 | 100 | 0.50 |\n"
        "| 03:00 | dev-suite smoke tournaments (details) | ap-3 | 5 | 50 | 0.10 |\n\n## Local\n\n- **Machine.** 8 cores.\n", encoding="utf-8")
    monkeypatch.setattr(CS, "P3", tmp_path)
    rows, local = CS.ledger_rows({"tournament:r9_x", "tournament:smoke_modal_dev"})
    assert [r["task"][:11] for r in rows] == ["CALIBRATION"]
    assert rows[0]["container_s"] == 14303 and rows[0]["usd"] == pytest.approx(2.10)
    assert local == ["**Machine.** 8 cores."]
