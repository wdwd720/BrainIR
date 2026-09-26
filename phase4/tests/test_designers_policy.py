"""Reference designers (brainir_causal.designers): every proposal is a valid public-policy protocol."""

from __future__ import annotations

import collections

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
