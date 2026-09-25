"""Benchmark version 3 selection and Level C rules (pre-lock reviews A-D): the Level C comparator (declared baselines, eligibility with
the Markov check, ranked among themselves on S1-S5), the selection decision rule on the bootstrap (P(rank 1) threshold, tie set
resolved by parsimony), K as the minimum of both R^2 directions, the C "no effect" flag, lineage and the resampling views."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
import level_c as L  # noqa: E402
import merge_rounds as M  # noqa: E402
from brainir_state.evaluate_cross import profile_from_systems  # noqa: E402

SIDS = [f"s{i}" for i in range(10)]


def _rec(a=1.1, c=0.5, k=2, markov=True, kk=0.9, error=False):
    if error:
        return {"error": "timeout"}
    return {"k": k, "A_over_full": a, "K": {"r2_true_from_model_rff": kk, "r2_model_from_true_rff": kk}, "K_dim": {"exact": True},
            "verdict": {"C": c, "D_ci95": [-0.05, 0.05], "E_ratio": 0.001, "E_testable": True, "markov_ok": markov}}


def _method(a=1.1, c=0.5, k=2, markov=True, n_fail=0, n_markov_bad=0, tp=10.0):
    ps = {}
    for i, s in enumerate(SIDS):
        ps[s] = _rec(a=a, c=c, k=k, markov=(markov and i >= n_markov_bad), error=i < n_fail)
    return {"per_system": ps, "transition_params_median": tp,
            "profile": profile_from_systems(ps, SIDS, {"abstention_recall": 1.0, "false_alarm_rate": 0.0}, [])}


# ---------------------------------------------------------------- comparator
def test_comparator_is_the_best_eligible_baseline_among_baselines_only():
    pm = {"lin_dmdc": _method(a=1.2), "lin_falds": _method(a=1.1), "candidate_x": _method(a=0.5), "nn_rssm": _method(a=1.0, n_markov_bad=2)}
    prof = {m: v["profile"] for m, v in pm.items()}
    tp = {m: v["transition_params_median"] for m, v in pm.items()}
    c = M.choose_comparator(pm, SIDS, prof, selected="candidate_x", transition_params=tp)
    # nn_rssm is better on A but fails the Markov check on 2 of 10 systems (80 % < 90 %): not eligible
    assert c["table"]["nn_rssm"]["eligible"] is False and c["chosen"] == "lin_falds"
    assert "candidate_x" not in c["table"]                       # non-baselines never enter the comparator ranking
    # the choice does not depend on non-baseline candidates in the round
    pm2 = dict(pm, other=_method(a=0.1))
    c2 = M.choose_comparator(pm2, SIDS, {m: v["profile"] for m, v in pm2.items()}, selected="candidate_x", transition_params=tp)
    assert c2["chosen"] == c["chosen"]


def test_comparator_eligibility_counts_fixed_list_failures_and_recognises_tuned_variants():
    pm = {"lin_falds": _method(a=1.1, n_fail=2), "lin_falds_t": _method(a=1.15), "ks_hankel": _method(a=1.3, n_fail=1)}
    prof = {m: v["profile"] for m, v in pm.items()}
    c = M.choose_comparator(pm, SIDS, prof)
    assert c["table"]["lin_falds"]["eligible"] is False         # 20 % failures > 10 %
    assert c["table"]["ks_hankel"]["eligible"] is True          # 10 % failures (the Markov rate counts failures as not ok: 90 %)
    assert M.is_baseline("lin_falds_t") and not M.is_baseline("lin_subspace_t") and c["chosen"] == "lin_falds_t"


def test_comparator_falls_back_with_a_recorded_reason_and_excludes_the_selected_method():
    pm = {"lin_dmdc": _method(markov=False), "lin_falds": _method(markov=False, a=1.0)}
    prof = {m: v["profile"] for m, v in pm.items()}
    c = M.choose_comparator(pm, SIDS, prof)
    assert c["chosen"] == "lin_falds" and "no baseline passed eligibility" in c["reason"]
    c2 = M.choose_comparator(pm, SIDS, prof, selected="lin_falds")
    assert c2["chosen"] == "lin_dmdc"
    none = M.choose_comparator({"cand": _method()}, SIDS, {"cand": _method()["profile"]})
    assert none["chosen"] is None


# ---------------------------------------------------------------- selection decision rule
def test_top_candidate_selected_when_p_rank1_reaches_half():
    ranked = {"order": ["a", "b"], "mean_rank": {"a": 1.2, "b": 1.8}}
    pm = {"a": _method(k=4), "b": _method(k=1)}
    s = M.select_candidate(ranked, {"a": {"p_rank1": 0.5}, "b": {"p_rank1": 0.5}}, pm, SIDS)
    assert s["selected"] == "a"


def test_tie_set_is_resolved_by_parsimony_then_transition_params_then_mean_rank():
    ranked = {"order": ["a", "b", "c", "d"], "mean_rank": {"a": 1.5, "b": 2.0, "c": 2.5, "d": 4.0}}
    boot = {"a": {"p_rank1": 0.45}, "b": {"p_rank1": 0.30}, "c": {"p_rank1": 0.20}, "d": {"p_rank1": 0.05}}
    pm = {"a": _method(k=3), "b": _method(k=2, tp=50), "c": _method(k=2, tp=20), "d": _method(k=1)}
    s = M.select_candidate(ranked, boot, pm, SIDS, {"a": 10, "b": 50, "c": 20, "d": 5})
    assert s["tie_set"] == ["a", "b", "c"]                      # d (P = 0.05 < 0.10) is outside the tie set despite k = 1
    assert s["selected"] == "c"                                 # median k 2 (b, c) < 3 (a); fewer transition parameters: c
    # a member whose k is available on fewer than 90 % of the systems does not qualify
    pm2 = dict(pm, c=_method(k=2, n_fail=2))
    s2 = M.select_candidate(ranked, boot, pm2, SIDS, {"a": 10, "b": 50, "c": 20, "d": 5})
    assert s2["tie_set_k"]["c"]["k_available"] == 0.8 and s2["selected"] == "b"


def test_descriptive_rankings_include_s1_s5_and_leave_one_out():
    prof = {"a": _method(a=1.0)["profile"], "b": _method(a=1.2)["profile"]}
    d = M.descriptive_rankings(prof)
    assert d["S1_S5_only"]["order"][0] == "a" and set(d["S1_S5_only"]["components_used"]) <= set(M.S1_S5)
    assert all(k.startswith("without_") for k in d["leave_one_component_out"])


# ---------------------------------------------------------------- K and C in the primary family
def test_k_is_the_minimum_of_both_directions_with_failures_at_minus_one():
    assert L.k_min_value({"r2_true_from_model_rff": 0.99, "r2_model_from_true_rff": 0.4}) == 0.4
    assert L.k_min_value({"r2_true_from_model_rff": -3.0, "r2_model_from_true_rff": 0.9}) == -1.0
    assert L.k_min_value({"r2_true_from_model_rff": 0.99}) == -1.0 and L.k_min_value(None) == -1.0
    rm = {"s1": {"k_true": 2, "K": {"r2_true_from_model_rff": 0.9, "r2_model_from_true_rff": 0.5}}, "s2": {"error": "x"}}
    rb = {"s1": {"k_true": 2, "K": {"r2_true_from_model_rff": 0.9, "r2_model_from_true_rff": 0.9}},
          "s2": {"k_true": 2, "K": {"r2_true_from_model_rff": 0.8, "r2_model_from_true_rff": 0.8}}}
    d = L.k_test_values(rm, rb, ["s1", "s2"])
    assert np.allclose(d, [0.9 - 0.5, 0.8 - (-1.0)])            # the method's failure on s2 counts as -1, it is not dropped


def test_c_row_is_interventional_only_below_the_no_effect_value():
    yes = L.c_flag({"ratio": 0.4, "ci95": [0.2, 0.9]})
    no = L.c_flag({"ratio": 0.9, "ci95": [0.5, 1.2]})
    assert yes["c_below_no_effect"] and yes["claim"] == L.C_CLAIM_YES
    assert not no["c_below_no_effect"] and no["claim"] == L.C_CLAIM_NO and not L.c_flag(None)["c_below_no_effect"]


# ---------------------------------------------------------------- lineage and views
def test_lineage_groups_reconstructions_and_overlapping_mechanisms():
    assert L.reconstruction_of("manc_v1.2.1") == L.reconstruction_of("manc_v1.2.3") == "manc"
    assert L.reconstruction_of("male-cns_v1.0") == "male-cns"
    pub = {"a:full": {"network": "n1", "mode": "full"}, "a:m1": {"network": "n1", "mode": "mech", "members": [1, 2, 3]},
           "a:m2": {"network": "n1", "mode": "mech", "members": [3, 4]}, "a:m3": {"network": "n1", "mode": "mech", "members": [7, 8]},
           "b:full": {"network": "n2", "mode": "full"}}
    internal = {"a:full": {"network": "x_v1"}, "a:m1": {"network": "x_v1"}, "a:m2": {"network": "x_v1"}, "a:m3": {"network": "x_v1"},
                "b:full": {"network": "x_v2"}}
    lin = L.lineage(pub, internal)
    assert lin["a:full"]["reconstruction"] == lin["b:full"]["reconstruction"] == "x"
    assert lin["a:m1"]["mechanism_family"] == lin["a:m2"]["mechanism_family"] != lin["a:m3"]["mechanism_family"]
    assert lin["a:full"]["mechanism_family"] is None


class _Pub:
    def __init__(self, rows, systems):
        self.rows, self.systems, self.manifest = rows, systems, {"systems": systems, "splits": ["train", "val"]}

    def select(self, system_id):
        return [r for r in self.rows if r["system_id"] == system_id]


class _SD:
    def __init__(self, root: Path, rows, systems):
        self.public_dir, self.pub = root, _Pub(rows, systems)


def test_half_views_are_seeded_halves_with_validation_and_a_subview_marker(tmp_path):
    src = tmp_path / "pub"
    (src / "traj").mkdir(parents=True)
    rows = [{"key": f"k{i:02d}", "system_id": "s", "split": "train" if i < 10 else "val"} for i in range(13)]
    for r in rows:
        (src / "traj" / f"{r['key']}.npz").write_bytes(b"x")
    sd = _SD(src, rows, {"s": {"mode": "full"}})
    v0 = L.half_view(sd, "s", tmp_path / "h0", 0)
    v0b = L.half_view(sd, "s", tmp_path / "h0b", 0)
    v1 = L.half_view(sd, "s", tmp_path / "h1", 1)
    keys = [json.loads(x)["key"] for x in (v0 / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(keys) == 5 + 3 and {"k10", "k11", "k12"} <= set(keys)
    assert json.loads((v0 / "SUBVIEW.json").read_text(encoding="utf-8"))["keys"] == keys
    assert (v0 / "index.jsonl").read_text(encoding="utf-8") == (v0b / "index.jsonl").read_text(encoding="utf-8")
    assert (v0 / "index.jsonl").read_text(encoding="utf-8") != (v1 / "index.jsonl").read_text(encoding="utf-8")
    lv = L.limited_view(sd, "s", tmp_path / "lim", every=4)
    assert json.loads((lv / "SUBVIEW.json").read_text(encoding="utf-8"))["keys"] == ["k00", "k04", "k08"]


def test_real_dataset_payloads_use_views_and_subviews(tmp_path):
    import modal_tournament as MT
    view = tmp_path / "fitview_real"
    view.mkdir()
    assert MT._real_dataset(view) == {"kind": "view", "tier": "real"}
    sub = tmp_path / "limited_x"
    sub.mkdir()
    (sub / "SUBVIEW.json").write_text(json.dumps({"base": "real", "keys": ["a", "b"]}), encoding="utf-8")
    (sub / "index.jsonl").write_text("{}\n", encoding="utf-8")
    (sub / "manifest.json").write_text("{}", encoding="utf-8")
    d = MT._real_dataset(sub)
    assert d["kind"] == "subview" and d["keys"] == ["a", "b"] and "tar" not in d
    assert MT.compare_results({"a": 1.0, "b": [1, "x"]}, {"a": 1.0 + 1e-9, "b": [1, "x"]})["n_mismatch"] == 0
    assert MT.compare_results({"a": 1.0}, {"a": 1.1})["n_mismatch"] == 1
