"""Capacity and compute accounting (brainir_causal.capacity; PROTOCOL 5.15)."""

from __future__ import annotations

import numpy as np
from test_lift_toysys import ExactModel, ToyLinear, passive_protocol

from brainir_causal.capacity import ComputeMeter, CountingSimulator, capacity_record, introspect_params, param_counts


def test_param_counts_sum_components_over_systems():
    info = {"n_params": {"encoder": {"a": 10, "b": 20}, "transition": 7, "read_in": {"a": 3}, "readout": 5}, "history": {"a": 4}}
    pc = param_counts(info, ["a", "b"])
    assert pc == {"encoder": 30, "transition": 7, "read_in": 3, "readout": 5, "total": 45, "reported": True,
                  "history": {"a": 4, "b": None}}
    assert not param_counts({}, ["a"])["reported"]


def test_introspection_counts_arrays_once():
    class M:
        pass
    m = M()
    w = np.zeros((3, 4))
    m.a, m.b, m.lst = w, w, [np.ones(5), {"c": np.ones(2)}]
    r = introspect_params(m)
    assert r["n_numbers"] == 12 + 5 + 2 and r["n_arrays"] == 3


def test_meter_and_counting_simulator():
    s = ToyLinear()
    sim = CountingSimulator(s.simulate_many, many=True)
    with ComputeMeter() as meter:
        sim([passive_protocol(1), passive_protocol(2)])
    d = meter.as_dict()
    assert d["wall_s"] >= 0 and d["cpu_s"] >= 0 and d["gpu_s"] == 0.0
    assert sim.as_dict() == {"sim_calls": 1, "trajectories": 2, "simulated_s": 4.0, "cached": 0}
    rec = capacity_record(ExactModel(s), ["toy"], meter=meter, sim=sim)
    assert rec["params"]["total"] == 10 + 6 + 10 + 6 and rec["params_counted"]["n_numbers"] > 0
