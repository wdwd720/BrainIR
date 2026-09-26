"""Level B selection (brainir_causal.select): gates, lexicographic ranking with tie bands, halving, the pilot rule."""

from __future__ import annotations

import numpy as np

from brainir_causal import select as S


def cand(a_rate, d_rate, e_rate, comp, obs, n=20, seed=0, params=None):
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(n):
        out[f"s{i}"] = {"A": i < a_rate * n, "D": i < d_rate * n, "E": i < e_rate * n, "compression": comp(i) if callable(comp) else comp,
                        "observational": obs + 0.01 * rng.standard_normal(), "efficiency": None,
                        "simplicity": params if params is not None else 100.0 + i, "compute": 10.0}
    return out


def test_gates():
    assert S.eligibility(cand(0.5, 0.4, 0.4, 1, 1.0))["eligible"]
    assert not S.eligibility(cand(0.45, 0.9, 0.9, 1, 1.0))["eligible"]
    assert not S.eligibility(cand(0.9, 0.35, 0.9, 1, 1.0))["eligible"]
    assert not S.eligibility({})["eligible"]


def test_ranking_uses_the_first_decisive_criterion():
    c = {"good_comp": cand(1, 1, 1, 1.0, 1.0, seed=1), "bad_comp": cand(1, 1, 1, 0.0, 0.5, seed=2),
         "inelig": cand(0.1, 1, 1, 1.0, 0.1, seed=3)}
    r = S.rank(c, n_boot=500)
    assert r["order"][0] == "good_comp" and "inelig" not in r["order"]
    assert r["pairwise"]["good_comp"]["bad_comp"]["criterion"] == "compression"


def test_ties_pass_to_the_next_criterion():
    c = {"a": cand(1, 1, 1, 1.0, 0.5, seed=1), "b": cand(1, 1, 1, 1.0, 1.0, seed=2)}
    r = S.rank(c, n_boot=500)
    assert r["order"] == ["a", "b"] and r["pairwise"]["a"]["b"]["criterion"] == "observational"


def test_halving_keeps_the_better_half_and_the_carried_baseline():
    d = S.halve(["m1", "m2", "b1", "m3", "m4"], {"b1"})
    assert d["keep"] == ["m1", "m2", "b1"] and d["carried_baseline"] == "b1"
    d = S.halve(["m1", "m2", "m3", "m4", "b1"], {"b1"})
    assert d["keep"] == ["m1", "m2", "m3", "b1"]
    d = S.halve(["m1", "m2", "m3", "m4"], {"b1"}, carried_baseline="b1", finalists=3)
    assert d["keep"] == ["m1", "m2", "m3"]


def test_pilot_rule_is_deterministic():
    real = ["real:A:full", "real:A:m1", "real:A:m2", "real:B:full", "real:B:m1", "real:C:m1", "real:C:m2", "real:C:m3"]
    p = S.pilot_real(real)
    assert p == S.pilot_real(list(reversed(real))) and len(p) == 3 and all(":m" in s for s in p)
    types = {f"syn:{i:03d}": f"type{i // 2}" for i in range(50)}
    ps = S.pilot_synthetic(types)
    assert len(ps) == 25 and ps == S.pilot_synthetic(dict(reversed(list(types.items()))))
    assert len({types[s] for s in ps}) == 25
