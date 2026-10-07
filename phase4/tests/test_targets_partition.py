"""The synthetic target partition reads the GENERATOR's targetable set (review F round 3b, NF-1): the generator's public record names it
`targets` (the unit-test systems `targetable`); a record without it, with two disagreeing sets, an empty set or units out of range is
refused, never replaced by the observed units. Public and held-out targets partition exactly the targetable set, and neither the
held-out targets nor the targetable set is published."""

from __future__ import annotations

import pytest

from brainir_causal import suites as S
from brainir_causal.synthadapter import ToySystem

ROT = {"rotation": "R4", "reduced": False, "families_train": ["kick.1", "pulse.1", "sil.1", "sil.2"]}


def _pub(**kw):
    pub = ToySystem(3, 0).public_record()
    pub.pop("targetable", None)
    pub.update({"system_id": "syn:toy:targets", "n_units": 12, "observed": list(range(0, 12, 2))})
    pub.update(kw)
    return pub


def test_the_generator_key_and_the_unit_test_key_are_read_and_checked():
    assert S.generator_targetable(_pub(targets=[5, 1, 3, 3])) == [1, 3, 5]
    assert S.generator_targetable(_pub(targetable=[2, 7])) == [2, 7]
    assert S.generator_targetable(_pub(targets=[2, 7], targetable=[7, 2])) == [2, 7]
    for bad, msg in ((_pub(), "lists no targetable"), (_pub(targets=[1], targetable=[2]), "two different"),
                     (_pub(targets=[]), "empty"), (_pub(targets=[3, 12]), "outside")):
        with pytest.raises(ValueError, match=msg):
            S.generator_targetable(bad)


def test_the_partition_covers_the_generators_set_and_is_not_observed_minus_public():
    targetable = [1, 3, 4, 5, 7, 9, 10]                      # includes unobserved units and leaves observed units out
    pub = _pub(targets=targetable)
    public, internal = S.synthetic_records(pub, tier="toy", seed=S.DEV_SEED, rotation=ROT, system_hash="h", engine_id="e")
    t_pub, t_hid = public["targets_public"], internal["targets_heldout"]
    assert sorted(t_pub + t_hid) == targetable and not set(t_pub) & set(t_hid)
    assert internal["targetable"] == targetable
    assert t_hid != sorted(set(pub["observed"]) - set(t_pub))           # the round-2 leak: held-out = observed - public
    assert not {"targetable", "targets", "targets_heldout"} & set(public)
    with pytest.raises(ValueError, match="lists no targetable"):        # no fallback to the observed units
        S.synthetic_records(_pub(), tier="toy", seed=S.DEV_SEED, rotation=ROT, system_hash="h", engine_id="e")
