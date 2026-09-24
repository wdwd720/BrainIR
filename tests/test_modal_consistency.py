"""Local and Modal execution give the same simulator outcomes (goal3 section 44, CLOUD). Opt-in: BRAINIR_TEST_MODAL=1."""

from __future__ import annotations

import os

import numpy as np
import pytest

from brainir.discovery import BudgetedSimulator, DiscoveryProblem, keep_only
from brainir.discovery.synthetic import InstanceSpec, build_instance, export_instance, verify_instance

pytestmark = [pytest.mark.modal, pytest.mark.skipif(os.environ.get("BRAINIR_TEST_MODAL") != "1", reason="set BRAINIR_TEST_MODAL=1 to run")]


def test_local_and_modal_outcomes_agree(tmp_path):
    from brainir.discovery.remote import get_discovery_backend as get_backend  # the pinned image every Phase 2 campaign uses

    spec = InstanceSpec("ei_pair_oscillator", 40, 3, n_readout=8)
    inst = build_instance(spec)
    export_instance(inst, verify_instance(inst, seeds=[0]), tmp_path)
    p = DiscoveryProblem.from_bundle(tmp_path / "instances" / spec.label, "main")
    ivs = [None, keep_only(p, [int(x) for x in p.candidate_positions()[:4]])]
    local = BudgetedSimulator(p, max_calls=10)
    remote = BudgetedSimulator(p, max_calls=10, backend=get_backend("modal", cpu=1.0, memory_mb=2048, timeout_s=600, max_containers=4))
    for iv in ivs:
        a = local.evaluate(iv, [0, 1])
        b = remote.evaluate(iv, [0, 1])
        for x, y in zip(a, b):
            assert x.passed == y.passed and x.n_active_readout == y.n_active_readout
            assert np.isclose(x.score, y.score, rtol=1e-6, atol=1e-9)
            assert np.array_equal(x.active_positions, y.active_positions)
    assert local.calls == remote.calls == 4
