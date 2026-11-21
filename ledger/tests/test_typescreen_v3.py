"""Run 3's group screen is run 1's frozen screen plus read-outs (PREREG v3 P1): on accepted, too-weak and saturating synthetic
circuits every run 1 field equals the frozen function's, the added fields name the last simulated run, and the stored read-out of
a never-accepted replicate equals a fixed run at that run's current."""

import numpy as np
import pytest
import scipy.sparse as sp
from brainir.sim.model import ModelConfig, sample_neuron_params
from brainir.sim.screen import ScreenConfig

from brainir_ledger import jobs as J
from brainir_ledger import jobs_v3 as J3
from brainir_ledger.typescreen import fixed_run, screen_group
from brainir_ledger.typescreen_v3 import screen_group_v3

RUN1_FIELDS = ("members", "seed", "usable", "score", "frequency_hz", "n_active_readout", "current", "n_tuning_runs", "n_active_all",
               "n_high_fr")


def _net(n=40, seed=0):
    rng = np.random.default_rng(seed)
    W = sp.random(n, n, density=0.15, random_state=seed, format="csr") * 40
    W.data = np.round(W.data) + 5
    signs = np.where(rng.random(n) < 0.7, 1.0, -1.0)
    W = (W @ sp.diags(signs)).tocsr()
    W.setdiag(0)
    W.eliminate_zeros()
    readout = np.zeros(n, bool)
    readout[-8:] = True
    return W, readout


CASES = {"accepted": ScreenConfig(n_active_lower=5, n_active_upper=30, n_high_fr_upper=10),
         "too_weak": ScreenConfig(n_active_lower=10_000, n_active_upper=20_000, n_high_fr_upper=10_000),
         "saturating": ScreenConfig(n_active_lower=0, n_active_upper=-1, n_high_fr_upper=10_000)}


def _run(case, members=(0, 3, 7)):
    W, ro = _net()
    mc = ModelConfig(t_end=0.4)
    p = sample_neuron_params(mc, W.shape[0], 3)
    cfg = CASES[case]
    ex = J3.extras_fn_v3({"readout_traces": True, "watch": list(members), "mn": list(range(30, 40))}, ro, mc, cfg)
    a = screen_group(W, p, mc, list(members), ro, seed=3, cfg=cfg, extras=ex)
    b = screen_group_v3(W, p, mc, list(members), ro, seed=3, cfg=cfg, extras=ex)
    return W, ro, mc, p, cfg, ex, a, b


@pytest.mark.parametrize("case", list(CASES))
def test_run1_fields_equal_frozen(case):
    *_, a, b = _run(case)
    for f in RUN1_FIELDS:
        assert getattr(a, f) == getattr(b, f), f
    assert J._digest(a.to_dict()) == J._digest(b.to_dict())


def test_accepted_records_its_run():
    *_, a, b = _run("accepted")
    assert b.usable and b.final_verdict == "ok" and b.final_current == b.current and b.final_run_extras is None
    assert J3._ex_digest(a.extras) == J3._ex_digest(b.extras)


@pytest.mark.parametrize("case,verdict,last", [("too_weak", "weak", 128.0 * 2 ** 9), ("saturating", "strong", 128.0 / 2 ** 9)])
def test_never_accepted_keeps_last_run(case, verdict, last):
    W, ro, mc, p, cfg, ex, a, b = _run(case)
    assert not b.usable and b.n_tuning_runs == 10 and b.final_verdict == verdict and b.final_current == last
    assert b.current != b.final_current  # run 1's field is the next, untried current
    assert b.extras == {} and b.final_run_extras is not None
    fx = fixed_run(W, p, mc, [0, 3, 7], [b.final_current] * 3, ro, cfg=cfg, extras=ex)
    assert J3._ex_digest(fx["extras"]) == J3._ex_digest(b.final_run_extras)
    assert fx["verdict"] == verdict


def test_job_digests():
    W, ro = _net()
    base = {"W": W, "readout": ro, "members": [0, 3, 7], "seed": 3, "model": ModelConfig(t_end=0.4).to_dict(),
            "screen": CASES["accepted"].to_dict(), "extras": {"readout_traces": True, "watch": [0, 3, 7]}}
    old = J.run_job({**base, "key": "a", "kind": "group"})
    new = J3.run_job({**base, "key": "a", "kind": "group_v3", "extras": {**base["extras"], "mn": list(range(30, 40))}})
    assert "error" not in new and new["digest"] == old["digest"]  # run 1's digest ignores the added read-out
    again = J3.run_job({**base, "key": "a", "kind": "group_v3", "extras": {**base["extras"], "mn": list(range(30, 40))}})
    assert again["digest_v3"] == new["digest_v3"]
    other = J3.run_job({**base, "key": "a", "kind": "group_v3", "extras": {**base["extras"], "mn": list(range(20, 40))}})
    assert other["digest"] == new["digest"] and other["digest_v3"] != new["digest_v3"]
    peak = np.asarray(new["extras"]["mn_peak"])
    assert new["extras"]["mn_active"] == np.flatnonzero(peak > 0.01).tolist()
    tr = J3.unpack16(new["extras"]["mn_traces"])
    assert tr.shape[1] == len(new["extras"]["mn_active"])
    fixed = J3.run_job({**base, "key": "b", "kind": "fixed_v3", "stim_indices": [0, 3, 7], "currents": [64.0] * 3,
                        "extras": {"mn": list(range(30, 40))}})
    assert "error" not in fixed and "mn_peak" in fixed["extras"] and fixed["verdict"] in ("ok", "weak", "strong")
    passthrough = J3.run_job({**base, "key": "c", "kind": "group"})
    assert passthrough["digest"] == old["digest"] and "digest_v3" not in passthrough
