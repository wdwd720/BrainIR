"""End-to-end: a tiny toy tier is built through the store (a PUBLIC part under the public policy and an orchestrator-held EVAL part),
loaded as evaluator inputs and scored by the harness (slow: the toy simulator is pure Python)."""

from __future__ import annotations

import collections
import json

import numpy as np
import pytest

from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal.api import CausalStateModel
from brainir_causal.evalio import check_item
from brainir_causal.simservice import check_public


class _Mean(CausalStateModel):
    def __init__(self, mean):
        self.k, self.mean = {"syn:toy:0": 1}, mean

    def encode(self, sid, x_hist, u_hist, dt):
        return np.asarray([float(np.mean(x_hist[-1]))])

    def rollout(self, sid, z0, u_future, events, dt):
        n = len(u_future)
        return {"z": np.tile(z0, (n, 1)), "y": np.tile(self.mean, (n, 1))}

    def readout(self, sid, z, u):
        return np.tile(self.mean, (len(np.atleast_2d(z)), 1))

    def supports(self, sid, kind):
        return True

    def info(self):
        return {"k": {"syn:toy:0": 1}, "n_params": {"encoder": {"syn:toy:0": 1}, "transition": 0, "readout": {"syn:toy:0": 1}}}


@pytest.fixture(scope="module", autouse=True)
def _test_salt(tmp_path_factory):
    """A hermetic test salt for every test of this module (phase4/tests/_hermetic.py): the real salt never leaves the orchestrator host,
    and the salted code paths run unchanged with another salt."""
    from _hermetic import hermetic_salt
    with hermetic_salt(tmp_path_factory.mktemp("salt")) as salt:
        yield salt


@pytest.fixture(scope="module")
def tiny_tier(tmp_path_factory, _test_salt):
    root = tmp_path_factory.mktemp("tiny")
    saved = {k: getattr(S, k) for k in ("B_MAIN", "D0_DESIGN", "POOL_DRAWS", "POOL_TRAJ", "POOL_STATES", "POOL_FLOOR_STATES", "N_PASSIVE_TEST",
                                        "CELLS_PER_FAMILY", "STATES_PER_CELL", "ITEMS_PER_CATEGORY", "N_EQUIV_STATES", "N_LIFT_CASES")}
    S.B_MAIN = {"synthetic": 4, "full": 4, "mech": 4}
    S.D0_DESIGN = {"obs.nominal": 2, "obs.stim": 2, "obs.init": 1, "obs.wnoise": 1}
    S.POOL_DRAWS, S.POOL_TRAJ, S.POOL_STATES, S.POOL_FLOOR_STATES = 2, 3, 2, 2
    S.N_PASSIVE_TEST, S.CELLS_PER_FAMILY, S.STATES_PER_CELL, S.ITEMS_PER_CATEGORY = 4, 1, 1, 1
    S.N_EQUIV_STATES, S.N_LIFT_CASES = 2, 2
    try:
        summ = S.build_tier("toy", workers=1, systems=["syn:toy:0"], root=root / "suites", store_root=root / "store")
    finally:
        for k, v in saved.items():
            setattr(S, k, v)
    return root, summ


@pytest.mark.slow
def test_tiny_tier_builds_without_errors(tiny_tier):
    _root, summ = tiny_tier
    c = summ["systems"]["syn:toy:0"]
    assert c["public"]["errors"] == 0 and c["eval"]["errors"] == 0
    assert c["public"]["records"] > 0 and c["eval"]["pool_states"] > 0 and c["public"]["pool_states"] > 0


@pytest.mark.slow
def test_public_part_passes_the_public_policy(tiny_tier):
    root, _ = tiny_tier
    d = S.tier_dirs("toy", root / "suites")["public"] / "syn_toy_0"
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    pub = man["systems"]["syn:toy:0"]
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {r["split"] for r in rows} <= {"train", "val", "twin", "test", "pool_src"}
    assert {(r.get("meta") or {}).get("role") for r in rows} <= {"d0", "d1", "in", "passive", "pool_src"}
    public_keys = {r["meta"]["store_key"] for r in rows}
    for r in rows:
        assert check_public(P.validate(r["protocol"]), pub, allowed_restart_keys=public_keys) is None, r["family"]
    # obs.init = a restart from a nominal passive trajectory of the same part (LOG P4-D36); explicit initial states never appear
    by_store = {r["meta"]["store_key"]: r for r in rows}
    inits = [r for r in rows if r["family"] == "obs.init"]
    assert inits and all(r["protocol"]["r0"]["kind"] == "restart" for r in inits)
    for r in inits:
        src = by_store[r["protocol"]["r0"]["key"]]
        assert src["family"] in ("obs.nominal", "obs.param") and src["protocol"]["r0"]["kind"] == "rest"
        assert src["protocol"]["params_seed"] == r["protocol"]["params_seed"]
    assert not any(r["protocol"]["r0"]["kind"] == "state" for r in rows)
    assert pub["capability"]["init"]["state"] is False
    pool = json.loads((d / "pools" / "pool.json").read_text(encoding="utf-8"))
    train = set(pub["split"]["families_train"])
    assert pool["policy"] == "public" and not pool["equivalents"]
    assert all(sq["family"] in train for sq in pool["sequences"].values())
    src = {st["store_key"] for st in pool["states"]}
    for st in pool["states"][:3]:
        for sq in [{"events": []}] + list(pool["sequences"].values()):
            p = S.pool_future_protocol(pub, st, sq["events"], pool["level"])
            assert check_public(P.validate(p), pub, allowed_restart_keys=src) is None


@pytest.mark.slow
def test_public_assertion_refuses_a_violation():
    pubs, _ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    pub = pubs[min(pubs)]
    bad = {"system": pub["system_id"], "params_seed": S.HIDDEN_SEED_BASE + 5, "t_end": 4.0, "dt": 0.01}
    with pytest.raises(AssertionError):
        S.assert_public_policy(bad, pub)
    held_out = next(f for f in pub["split"]["families_heldout"] if f.startswith(("sil.", "kick.")))
    s = S.FamilySampler(pub, np.random.default_rng(0), S.seed_counter(False, "x"), targets=pub["targets_public"])
    p, _ = s.make(held_out)
    with pytest.raises(AssertionError):
        S.assert_public_policy(p, pub)


@pytest.mark.slow
def test_eval_inputs_are_consistent(tiny_tier):
    root, _ = tiny_tier
    inp = S.load_eval_inputs("syn:toy:0", heldout_dirs=S.tier_dirs("toy", root / "suites"))
    items = inp["items"]
    assert items and not any(check_item(it, inp["system"]) for it in items)
    kinds = collections.Counter(it.shift for it in items)
    assert kinds["passive"] and kinds["in"] and kinds["near"] + kinds["far"] and kinds["target"]
    for it in items:
        assert not any(e["kind"] in ("latent_set", "latent_kick") for e in it.events)
        if not it.is_passive:
            assert it.events and min(e.get("t", e.get("t0")) for e in it.events) == 0.0
    pool = inp["pool"]
    draws = collections.Counter(s.draw for s in pool.states if not s.meta.get("truth_only"))
    assert pool is not None and len(draws) == 2 and all(v >= 2 for v in draws.values())
    assert "none" in pool.sequences and len(pool.sequences) > 1
    assert all(set(s.x_futures) <= {"none"} for s in pool.states)
    assert inp["lift_cases"] and inp["samples"]
    pub_inp = S.load_eval_inputs("syn:toy:0", heldout_dirs=S.tier_dirs("toy", root / "suites"), part="public")
    assert {it.shift for it in pub_inp["items"]} <= {"in", "passive"}


@pytest.mark.slow
def test_harness_scores_a_trivial_model(tiny_tier):
    from brainir_causal import harness as H
    root, _ = tiny_tier
    inp = S.load_eval_inputs("syn:toy:0", heldout_dirs=S.tier_dirs("toy", root / "suites"))
    train = H.training_records(inp)
    mean = np.concatenate([r.y for r in train]).mean(0)
    res = H.evaluate_model(_Mean(mean), inp, lift=False, n_boot=200, families=("items", "mediation", "closure", "micro", "capacity"))
    assert "error" not in res["items"], res["items"].get("error")
    assert res["items"]["effects"]["n_items"] > 0
    v = H.system_verdict_for(res, None, H.tolerances_or_provisional()[0], n_boot=200)
    assert v["verdict"]["category"] in ("unsupported", "partially supported", "causal state supported",
                                        "causal state supported (microstate equivalence untestable)")
