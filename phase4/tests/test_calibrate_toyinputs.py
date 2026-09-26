"""Evaluation inputs of the toy linear system (test_lift_toysys.ToyLinear) in the evaluator's formats (evalio.EvalSystem, TestItem,
Pool), for the calibration / stability / transfer tests (E6). Built by hand here so the tests do not depend on the suite builder."""

from __future__ import annotations

import numpy as np
from test_lift_toysys import DT, T_END, ToyLinear, make_records, passive_protocol

from brainir_causal import protocol as P
from brainir_causal.evalio import Pool, PoolState, TestItem, make_eval_system


def z_obs_of(sysm: ToyLinear, x: np.ndarray) -> np.ndarray:
    """A causally WRONG two-dimensional 'observational shortcut' of the toy (nuisance mixed into the second coordinate)."""
    C = sysm.C.copy()
    C[1] = C[1] + 1.5 * sysm.Minv[2]
    return np.asarray(x) @ C.T


def toy_inputs(seed: int = 0, n_test_kick: int = 16, n_test_pulse: int = 8, n_pool_src: int = 6):
    s = ToyLinear(seed=seed)
    train, tz = make_records(s, seed=seed)
    truth = {"z": tz["z"], "z_obs": {r["key"]: z_obs_of(s, r["x"]) for r in train}}
    pub = s.record()
    pub.update({"kind": "synthetic", "n_units": s.n})
    sysc = make_eval_system("toy", "synthetic", DT, T_END, [r["x"] for r in train if r["split"] == "train"],
                            [r["y"] for r in train if r["split"] == "train"], 1)
    rng = np.random.default_rng(100 + seed)
    H = round(0.5 * T_END / DT)
    items, register = [], []
    for i in range(n_test_kick + n_test_pulse):
        base = passive_protocol(5000 + i, stim=float(rng.uniform(0.6, 1.4)), t_on=0.1)
        unit = int(rng.integers(0, s.n))
        t_ev = round(float(rng.uniform(0.4, 0.9)), 2)
        if i < n_test_kick:
            ev = {"kind": "kick", "t": t_ev, "delta": {str(unit): float(rng.choice([-1, 1]) * rng.uniform(0.5, 2.0))}}
            fam, shift = "kick.1", "in"
        else:
            ev = {"kind": "current", "t0": t_ev, "t1": round(t_ev + 0.1, 2), "targets": {str(unit): float(rng.uniform(-8, 8))}}
            fam, shift = "pulse.1", "near"
        q = P.validate(dict(base, events=[ev]))
        ri = s.simulate(q, full=True)
        rt = s.simulate(P.counterfactual(q), full=True)
        i0 = round(t_ev / DT)
        rel = [dict(e, **({"t": e["t"] - t_ev} if "t" in e else {"t0": e["t0"] - t_ev, "t1": e["t1"] - t_ev})) for e in q["events"]]
        items.append(TestItem(item_id=f"it{i}", system_id="toy", dt=DT, x_hist=ri["x"][: i0 + 1], u_hist=ri["u"][: i0 + 1],
                              u_future=ri["u"][i0: i0 + H + 1], events=rel, y_future=ri["y"][i0: i0 + H + 1], y_twin=rt["y"][i0: i0 + H + 1],
                              family=fam, shift=shift, magnitude_class="moderate", target_set=(unit,), onset=t_ev, group=f"g{i}",
                              x_future=ri["x"][i0: i0 + H + 1], x_twin_future=rt["x"][i0: i0 + H + 1], z_true=ri["z"][i0],
                              z_obs=z_obs_of(s, ri["x"][i0])))
        register += [{"x": ri["x"], "u": ri["u"], "y": ri["y"], "z": ri["z"], "z_obs": z_obs_of(s, ri["x"])},
                     {"x": rt["x"], "u": rt["u"], "y": rt["y"], "z": rt["z"], "z_obs": z_obs_of(s, rt["x"])}]
    # pool: states of passive trajectories, futures from restarts of the exact microstate under a common constant input
    Hf = round(0.25 * T_END / DT)
    seqs = {"none": [], "kick0": [{"kind": "kick", "t": 0.0, "delta": {"0": 1.5}}],
            "pulse1": [{"kind": "current", "t0": 0.0, "t1": 0.1, "targets": {"1": 6.0}}]}
    u_fut = np.ones((Hf + 1, 1))
    states = []
    for j in range(n_pool_src):
        seed_j = 7000 + j // 2
        pr = passive_protocol(seed_j, stim=float(rng.uniform(0.6, 1.4)), t_on=0.1)
        rec = s.simulate(pr, full=True)
        register.append({"x": rec["x"], "u": rec["u"], "y": rec["y"], "z": rec["z"], "z_obs": z_obs_of(s, rec["x"])})
        for i in sorted(rng.choice(np.arange(40, 150), size=6, replace=False)):
            fut = {}
            xf = {}
            for name, evs in seqs.items():
                q = {"system": "toy", "params_seed": seed_j, "t_end": Hf * DT, "dt": DT, "stimulus": [[0.0, 1.0]], "events": evs,
                     "r0": {"kind": "state", "values": {str(u): float(v) for u, v in enumerate(rec["x"][i])}}}
                f = s.simulate(q)
                fut[name], xf[name] = f["y"], f["x"]
            states.append(PoolState(state_id=f"p{j}@{i}", x_hist=rec["x"][: i + 1], u_hist=rec["u"][: i + 1], y_now=rec["y"][i],
                                    traj=f"src{j}", draw=str(seed_j), futures=fut, x_futures=xf, z_true=rec["z"][i],
                                    z_obs=z_obs_of(s, rec["x"][i])))
    pool = Pool(system_id="toy", dt=DT, states=states,
                sequences={n: {"events": e, "u_future": u_fut, "family": n, "kind": (e[0]["kind"] if e else "none")} for n, e in seqs.items()},
                floor_div=1e-12)
    return {"sys": s, "pub": pub, "sysc": sysc, "train": train, "truth": truth, "items": items, "pool": pool, "register": register}


def test_toy_inputs_shapes():
    inp = toy_inputs(n_test_kick=2, n_test_pulse=1, n_pool_src=2)
    from brainir_causal.evalio import check_item
    assert all(not check_item(it, inp["sysc"]) for it in inp["items"])
    assert len(inp["pool"].states) == 12
