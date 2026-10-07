"""Reference designers (brainir_causal.designers): every proposal is a valid public-policy protocol."""

from __future__ import annotations

import collections
import math

import numpy as np
import pytest

from brainir_causal import designers as D
from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal.api import get_designer, registered_designers
from brainir_causal.simservice import check_public


def toy_pub():
    pubs, _, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    return pubs[min(pubs)]


def real_mech_pub():
    from brainir_causal.systems import load_real_public
    pubs = load_real_public()
    return pubs[min(s for s in pubs if ":m" in s)]


def test_all_reference_designers_are_registered():
    assert set(D.REFERENCE_DESIGNERS) <= set(registered_designers())


@pytest.mark.parametrize("name", D.REFERENCE_DESIGNERS)
@pytest.mark.parametrize("which", ["toy", "real_mech"])
def test_designers_propose_public_policy_protocols(name, which):
    pub = toy_pub() if which == "toy" else real_mech_pub()
    d = get_designer(name)
    rng = np.random.default_rng(3)
    props = []
    for _ in range(4):
        props += d.propose(pub["system_id"], pub, None, [], 5, 100, rng)
    assert props
    for p in props:
        q = P.validate(p)
        assert check_public(q, pub, allowed_restart_keys=set()) is None, (name, check_public(q, pub, allowed_restart_keys=set()))
    if name == "passive":
        assert all(not P.validate(p)["events"] for p in props) and len(props) == 40
    else:
        assert all(P.validate(p)["events"] for p in props) and len(props) == 20


def test_fixed_designer_ignores_the_loop_seed():
    pub = toy_pub()
    a = get_designer("fixed").propose(pub["system_id"], pub, None, [], 6, 100, np.random.default_rng(1))
    b = get_designer("fixed").propose(pub["system_id"], pub, None, [], 6, 100, np.random.default_rng(99))
    assert [P.canonical_json(x) for x in a] == [P.canonical_json(x) for x in b]


def test_uniform_designer_covers_cells_before_repeating():
    pub = toy_pub()
    d = get_designer("uniform")
    rng = np.random.default_rng(0)
    fams = D._Base.families(pub)
    n_cells = sum(len(pub["targets_public"]) if f not in ("edge.w", "edge.rm") else 1 for f in fams) * len(S.MAG_CLASSES)
    props = d.propose(pub["system_id"], pub, None, [], n_cells, 1000, rng)
    from brainir_causal.families import family_of
    seen = collections.Counter()
    for p in props:
        fam = family_of(p, pub)
        units = sorted(P.intervened_units(p))
        seen[(fam, units[0] if fam not in ("edge.w", "edge.rm") else None)] += 1
    assert len(props) == n_cells
    assert max(seen.values()) - min(seen.values()) <= len(S.MAG_CLASSES)


def test_magnitude_sweep_increases_magnitude_within_a_target():
    pub = toy_pub()
    d = get_designer("magnitude_sweep")
    props = d.propose(pub["system_id"], pub, None, [], 4, 100, np.random.default_rng(5))
    mags = []
    for p in props:
        e = P.validate(p)["events"][0]
        if e["kind"] == "kick":
            mags.append(max(abs(v) for v in e["delta"].values()))
        elif e["kind"] in ("current",):
            mags.append(max(abs(v) for v in e["targets"].values()))
        elif e["kind"] == "current_seq":
            mags.append(max(abs(v) for lst in e["targets"].values() for v in lst))
    if len(mags) == 4:
        assert mags == sorted(mags)


def test_structural_ranking_uses_the_public_graph():
    pub = real_mech_pub()
    ranked = D.structural_ranking(pub)
    assert sorted(ranked) == sorted(pub["targets_public"])


# ------------------------------------------------------------------------------------------------------------ magnitude-matched control
@pytest.mark.parametrize("which", ["toy", "real_mech"])
def test_magnitude_matched_random_uses_the_profile_and_the_public_policy(which):
    pub = toy_pub() if which == "toy" else real_mech_pub()
    src = get_designer("magnitude_sweep").propose(pub["system_id"], pub, None, [], 12, 100, np.random.default_rng(2))
    profile = D.magnitude_profile(src, pub)
    assert profile and all(p["rel"] > 0 for p in profile)
    d = D.MagnitudeMatchedDesigner(profile)
    props = d.propose(pub["system_id"], pub, None, [], 20, 100, np.random.default_rng(4))
    assert len(props) == 20 and d.n_matched > 0
    allowed = {round(p["rel"], 4) for p in profile}
    for q in props:
        assert check_public(P.validate(q), pub, allowed_restart_keys=set()) is None
        for m in D.event_magnitudes(q, pub):
            cap_rel = 3.0 + 1e-6
            assert round(m["rel"], 4) in allowed or m["rel"] >= cap_rel - 1e-3 or m["kind"] == "edge_scale"
    empty = D.MagnitudeMatchedDesigner([])
    props = empty.propose(pub["system_id"], pub, None, [], 5, 100, np.random.default_rng(4))
    assert len(props) == 5 and empty.n_unmatched > 0 and "random_matched" in registered_designers()


def test_load_profile_reads_a_loop_experiments_file(tmp_path):
    pub = toy_pub()
    src = get_designer("random").propose(pub["system_id"], pub, None, [], 3, 100, np.random.default_rng(0))
    import json
    lines = [{"key": f"k{i}", "provenance": "designer:x", "family": "f", "twin_of": None, "protocol": q} for i, q in enumerate(src)]
    lines += [{"key": "t0", "provenance": "designer:x", "family": "obs", "twin_of": "k0", "protocol": None}]
    (tmp_path / "experiments.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    assert D.load_profile(tmp_path, pub) == D.magnitude_profile(src, pub)


# ------------------------------------------------------------------------------------------------------------ greedy_error floor
class _Rec:
    def __init__(self, key, protocol, t, x, u, y, meta=None, split="train", family="kick.1"):
        self.key, self.protocol, self.t, self.x, self.u, self.y = key, protocol, t, x, u, y
        self.meta, self.split, self.family = meta or {}, split, family


class _EffectModel:
    """Predicts a fixed effect of the given size on every item."""

    def __init__(self, size: float):
        self.size = size

    def intervention_effect(self, sid, x_hist, u_hist, u_future, events, dt):
        n = len(u_future)
        return {"effect": np.full((n, 1), self.size)}


def test_greedy_error_uses_the_evaluator_floor():
    dt, T = 0.01, 4.0
    t = np.round(np.arange(0.0, T + dt / 2, dt), 9)
    n = len(t)
    rng = np.random.default_rng(0)
    passive = [_Rec(f"p{i}", {"t_end": T, "dt": dt, "events": []}, t, rng.standard_normal((n, 2)), np.zeros((n, 1)),
                    rng.standard_normal((n, 1))) for i in range(4)]
    prot = {"system": "s", "params_seed": 1, "t_end": T, "dt": dt, "events": [{"kind": "kick", "t": 1.0, "delta": {"0": 1e-6}}]}
    y = rng.standard_normal((n, 1))
    item = _Rec("item", prot, t, np.zeros((n, 2)), np.zeros((n, 1)), y.copy())
    twin = _Rec("twin", {"t_end": T, "dt": dt, "events": []}, t, np.zeros((n, 2)), np.zeros((n, 1)), y.copy(), meta={"twin_of": "item"})
    data = passive + [item, twin]
    f2 = D.effect_floor_sq(data)
    from brainir_causal.evalio import FLOOR_FRAC, pooled_y_sd
    assert math.isclose(f2, (FLOOR_FRAC * pooled_y_sd([r.y for r in passive + [item]], [r.x for r in passive + [item]])) ** 2)
    h = round(0.125 * T / dt)
    small = math.sqrt(f2) * 0.5                                     # an error below the floor: item error 0.25, not huge
    (err, _), = D.effect_errors(_EffectModel(small), "s", data, sysrec={"t_end_default": T})
    assert math.isclose(err, (h * small ** 2) / (h * f2))
    (err, _), = D.effect_errors(_EffectModel(1e6), "s", data, sysrec={"t_end_default": T})
    assert err == 10.0                                              # capped like the evaluator
