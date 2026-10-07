import threading
import time

import numpy as np
import pytest

from brainir_causal import families as F
from brainir_causal import protocol as P
from brainir_causal.accounting import experiment_cost
from brainir_causal.simclient import SimClient
from brainir_causal.simservice import SimServer, check_public, issue_token
from brainir_causal.synthadapter import ToySystem
from brainir_causal.systems import BUNDLE, INTERNAL_REAL, load_real_internal


def toy_sysdef(seed=3, j=0):
    rec = ToySystem(seed, j).public_record()
    rec.update({"tier": "toy", "suite_seed": seed, "targets_public": [0, 1, 2], "edges_public": [[0, 1], [1, 0]],
                "split": F.rotation_split("R4", rec["capability"])})
    return rec


def tbase(**kw):
    p = {"system": "syn:toy:0", "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]}
    p.update(kw)
    return p


def reason(p, sysrec, **kw):
    return check_public(P.validate(p, allow_truth=True), sysrec, **kw)


def test_policy_on_the_toy_rotation():
    s = toy_sysdef()
    assert reason(tbase(), s) is None
    assert reason(tbase(events=[{"kind": "kick", "t": 0.5, "delta": {"1": 0.5}}]), s) is None
    assert reason(tbase(events=[{"kind": "silence", "t0": 0.5, "t1": 0.8, "targets": [0, 1]}]), s) is None       # sil.2 trained (R4)
    assert "held out" in reason(tbase(events=[{"kind": "silence", "t0": 0.5, "t1": 0.8, "targets": [0, 1, 2]}]), s)   # sil.g
    assert "held out" in reason(tbase(events=[{"kind": "edge_scale", "t0": 0.5, "t1": None, "edges": [[0, 1]], "factor": 0.5}]), s)
    assert "never a development family" in reason(tbase(events=[{"kind": "kick", "t": 0.2, "delta": {"1": 0.5}},
                                                                {"kind": "current", "t0": 0.5, "t1": 0.6, "targets": {"2": 0.5}}]), s)
    assert "held out" in reason(tbase(events=[{"kind": "kick", "t": 0.5, "delta": {"1": 3.0}}]), s)                  # kick.hi
    assert "public targets" in reason(tbase(events=[{"kind": "kick", "t": 0.5, "delta": {"4": 0.5}}]), s)
    assert "evaluator-only" in reason(tbase(events=[{"kind": "latent_kick", "t": 0.5, "dz": [1.0, 0.0]}]), s)
    assert "public range" in reason(tbase(params_seed=10**9), s)
    assert "stimulus" in reason(tbase(stimulus=[[0.0, 2.0]]), s)
    assert "dt" in reason(tbase(dt=0.005), s)
    assert "nominal dt" in reason(tbase(dt=0.02), s)                       # development dt = the nominal dt only (review H, M3)
    assert "t_end" in reason(tbase(t_end=9.0), s)
    assert "observed units" in reason(tbase(r0={"kind": "state", "values": {"5": 1.0}}), s)
    assert reason(tbase(r0={"kind": "state", "values": {"4": 1.0}}), s) is None
    assert "restart" in reason(tbase(r0={"kind": "restart", "key": "ab" * 32, "t": 0.1}), s)
    assert reason(tbase(r0={"kind": "restart", "key": "ab" * 32, "t": 0.1}), s, allowed_restart_keys={"ab" * 32}) is None
    assert "obs_noise" in reason(tbase(obs_noise={"sd": 0.9, "seed": 1}), s)
    assert "weight_noise" in reason(tbase(weight_noise={"sd": 0.5, "seed": 1}), s)


@pytest.mark.skipif(not INTERNAL_REAL.exists(), reason="real systems not built")
def test_policy_on_real_systems():
    internal = load_real_internal()
    full = internal["real:A:full"]
    a, b = full["targets_public"][0], full["targets_heldout"][0]
    base = {"system": "real:A:full", "params_seed": 5, "t_end": 2.0, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.05, 1.0]]}
    ok = [{**base, "events": [{"kind": "kick", "t": 0.5, "delta": {str(a): 30.0}}]},
          {**base, "events": [{"kind": "current", "t0": 0.5, "t1": 0.6, "targets": {str(a): -40.0}}]},
          {**base, "events": [{"kind": "silence", "t0": 0.5, "t1": 0.9, "targets": [a]}]},
          {**base, "stimulus": [[0.0, 0.0], [0.1, 1.3], [1.0, 0.0]]}, {**base, "weight_noise": {"sd": 0.1, "seed": 4}}]
    for p in ok:
        assert check_public(P.validate(p), full) is None, p
    assert "public targets" in check_public(P.validate({**base, "events": [{"kind": "kick", "t": 0.5, "delta": {str(b): 30.0}}]}), full)
    for ev, why in (({"kind": "silence", "t0": 0.5, "t1": None, "targets": [a]}, "held out"),
                    ({"kind": "current", "t0": 0.5, "t1": 1.5, "targets": {str(a): 20.0}}, "held out"),
                    ({"kind": "kick", "t": 0.5, "delta": {str(a): 80.0}}, "held out"),
                    ({"kind": "edge_scale", "t0": 0.5, "t1": None, "edges": [[a, a]], "factor": 0.5}, "held out"),
                    ({"kind": "param", "t0": 0.5, "t1": None, "targets": {str(a): {"gain": 1.2}}}, "held out")):
        assert why in check_public(P.validate({**base, "events": [ev]}), full), ev
    assert "public range" in check_public(P.validate({**base, "stimulus": [[0.0, 2.0]]}), full)


def test_accounting():
    c = experiment_cost(P.validate(tbase(events=[{"kind": "kick", "t": 0.5, "delta": {"1": -0.5, "2": 0.25}},
                                                 {"kind": "current", "t0": 0.2, "t1": 0.4, "targets": {"0": 1.0}},
                                                 {"kind": "silence", "t0": 0.6, "t1": None, "targets": [3, 4]}])), {"cost_units": 2})
    assert c["experiment"] == 1 and c["units"] == 2 and c["targets"] == [0, 1, 2, 3, 4] and c["simulated_s"] == 1.0
    assert c["magnitude"]["kick"] == pytest.approx(0.75) and c["magnitude"]["current"] == pytest.approx(0.2)
    assert c["magnitude"]["silence"] == pytest.approx(0.8)
    assert experiment_cost(P.validate(tbase()))["experiment"] == 0


def _server(tmp_path, systems, **kw):
    return SimServer(tmp_path / "room", systems, tmp_path / "store", bundle=BUNDLE, pool="inline", ledger_dir=tmp_path / "ledger", **kw)


def test_service_end_to_end_toy(tmp_path):
    sysrec = toy_sysdef()
    srv = _server(tmp_path, {"syn:toy:0": sysrec}, budgets={"a1": 5})
    good = tbase(events=[{"kind": "kick", "t": 0.5, "delta": {"1": 0.5}}])
    arrays, meta = srv.handle_request({"protocols": [good, good, tbase(events=[{"kind": "kick", "t": 0.5, "delta": {"4": 1}}]),
                                                     {"system": "nope"}]}, agent="a1")
    items = meta["items"]
    assert [i["ok"] for i in items] == [True, True, False, False]
    assert items[0]["key"] == items[1]["key"] == srv.served_key(P.validate(good), sysrec)
    assert items[0]["key"] != P.protocol_hash(P.validate(good))              # keyed by engine + service secret (review H, minor 8)
    assert items[0]["family"] == "kick.1" and all("cached" not in i for i in items)       # never returned (review F, M4)
    assert set(arrays) == {f"i{j}_{k}" for j in (0, 1) for k in ("t", "x", "u", "y")}
    assert arrays["i0_x"].shape == (101, 5) and np.array_equal(arrays["i0_x"], arrays["i1_x"])
    led = meta["ledger"]
    assert led["trajectories"] == 2 and led["experiments"] == 2 and led["unique_targets"] == 1
    assert "sim_calls" not in led and "cached" not in led and "targets" not in led
    assert srv.ledgers["a1"].sim_calls == 1 and srv.ledgers["a1"].cached == 1    # the split stays in the orchestrator ledger
    # restart from a served key; the served trajectory is continued from its exact float64 state
    rs = tbase(t_end=0.5, r0={"kind": "restart", "key": items[0]["key"], "t": 0.5})
    _, meta2 = srv.handle_request({"protocols": [rs]}, agent="a1")
    assert meta2["items"][0]["ok"], meta2
    # a restart time beyond the source is refused (review H, M6)
    _, meta_t = srv.handle_request({"protocols": [tbase(t_end=0.5, r0={"kind": "restart", "key": items[0]["key"], "t": 1.5})]}, agent="a1")
    assert not meta_t["items"][0]["ok"]
    # the budget (5 units, 1 per toy trajectory) runs out
    _, meta3 = srv.handle_request({"protocols": [tbase(params_seed=k) for k in range(1, 5)]}, agent="a1")
    assert [i["ok"] for i in meta3["items"]] == [True, True, False, False]
    assert "budget" in meta3["items"][2]["error"]
    # another agent may not restart from a1's trajectory
    _, meta4 = srv.handle_request({"protocols": [rs]}, agent="a2")
    assert not meta4["items"][0]["ok"] and "restart" in meta4["items"][0]["error"]


def test_service_refuses_cross_system_restarts(tmp_path):
    """review H, M6: a served key of one system is no restart source for another."""
    s0, s1 = toy_sysdef(3, 0), {**toy_sysdef(3, 1), "system_id": "syn:toy:1"}
    srv = _server(tmp_path, {"syn:toy:0": s0, "syn:toy:1": s1})
    _, meta = srv.handle_request({"protocols": [tbase()]}, agent="a1")
    key = meta["items"][0]["key"]
    _, meta2 = srv.handle_request({"protocols": [tbase(system="syn:toy:1", t_end=0.5, r0={"kind": "restart", "key": key, "t": 0.5})]},
                                  agent="a1")
    assert not meta2["items"][0]["ok"] and "same system" in meta2["items"][0]["error"]


def test_identity_is_bound_by_the_token(tmp_path):
    """review F, M4: names in requests are ignored; a missing / unknown token is refused; budgets and ledgers follow the token."""
    tokens = tmp_path / "outside" / "tokens.json"
    t_a = issue_token(tokens, "dev_A", 2)
    t_b = issue_token(tokens, "dev_B", 5)
    srv = _server(tmp_path, {"syn:toy:0": toy_sysdef()}, tokens=tokens)
    with pytest.raises(PermissionError):
        srv.handle_request({"agent": "dev_A2", "protocols": [tbase()]})
    with pytest.raises(PermissionError):
        srv.handle_request({"token": "0" * 64, "protocols": [tbase()]})
    _, m = srv.handle_request({"token": t_a, "agent": "anything", "protocols": [tbase(params_seed=k) for k in range(3)]})
    assert [i["ok"] for i in m["items"]] == [True, True, False]
    _, m2 = srv.handle_request({"token": t_a, "agent": "dev_A2", "protocols": [tbase(params_seed=9)]})    # a new name gives nothing
    assert not m2["items"][0]["ok"] and "budget" in m2["items"][0]["error"]
    _, mb = srv.handle_request({"token": t_b, "protocols": [tbase(params_seed=0)]})                     # dev_A's protocol
    assert mb["items"][0]["ok"] and "cached" not in mb["items"][0]
    _, la = srv.handle_request({"token": t_a, "op": "ledger"})
    _, lb = srv.handle_request({"token": t_b, "op": "ledger"})
    assert la["ledger"]["trajectories"] == 2 and lb["ledger"]["trajectories"] == 1 and la["budget"] == 2 and lb["budget"] == 5
    assert set(srv.ledgers) == {"dev_A", "dev_B"}


def test_errors_are_generic_and_logged_outside(tmp_path):
    """review F, minor 5: simulation errors reach the client as a reference; the details go to the ledger directory."""
    srv = _server(tmp_path, {"syn:toy:0": toy_sysdef()})

    class Boom:
        def submit(self, fn, *a, **kw):
            from concurrent.futures import Future
            f = Future()
            f.set_exception(RuntimeError("secret path /store/abc and field network=X"))
            return f
    srv.pool = Boom()
    _, meta = srv.handle_request({"protocols": [tbase()]}, agent="a1")
    err = meta["items"][0]["error"]
    assert not meta["items"][0]["ok"] and err.startswith("simulation failed (reference ") and "secret" not in err
    ref = err[len("simulation failed (reference "):-1]
    logged = (tmp_path / "ledger" / "errors.jsonl").read_text(encoding="utf-8")
    assert "secret path" in logged and ref in logged


def test_client_roundtrip_through_the_queue(tmp_path, monkeypatch):
    tokens = tmp_path / "outside" / "tokens.json"
    monkeypatch.setenv("P4_SIM_TOKEN", issue_token(tokens, "c1", 10))
    srv = _server(tmp_path, {"syn:toy:0": toy_sysdef()}, tokens=tokens)

    def serve_once():
        t0 = time.time()
        while time.time() - t0 < 20:
            reqs = sorted((srv.q / "requests").glob("*.json"))
            if reqs:
                srv.handle(reqs[0])
                return
            time.sleep(0.05)

    th = threading.Thread(target=serve_once)
    th.start()
    out = SimClient(queue=srv.q, agent="c1").run([tbase(events=[{"kind": "current", "t0": 0.2, "t1": 0.3, "targets": {"2": 1.0}}])], poll=0.05)
    th.join()
    assert out[0]["ok"] and out[0]["family"] == "pulse.1" and out[0]["x"].shape == (101, 5) and out[0]["y"].shape == (101, 1)
    assert "z" not in out[0] and "state" not in out[0] and "cached" not in out[0]
    assert set(srv.ledgers) == {"c1"}


@pytest.mark.skipif(not INTERNAL_REAL.exists(), reason="real systems not built")
def test_service_real_mechanism_and_remote_hook(tmp_path, monkeypatch):
    # the service's logic, run on this host: the reference-platform gate is tested in test_reference_platform.py
    from brainir_causal.p4modal import gate as G
    monkeypatch.setattr(G, "reference_platform_problems", lambda fp=None: [])
    internal = load_real_internal()
    mech = next(s for s, d in internal.items() if d["mode"] == "mech")
    full = "real:B:full"
    calls = []

    def remote(jobs):                    # a fake remote backend: must not be called for mechanisms or stored microstates
        calls.append(len(jobs))
        return [RuntimeError("remote unavailable in tests")] * len(jobs)

    srv = _server(tmp_path, {mech: internal[mech], full: internal[full]}, remote_backend=remote)
    d = internal[mech]
    p = {"system": mech, "params_seed": 3, "t_end": 0.3, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]],
         "events": [{"kind": "kick", "t": 0.1, "delta": {str(d["targets_public"][0]): 20.0}}], "obs_noise": {"sd": 0.1, "seed": 2}}
    arrays, meta = srv.handle_request({"protocols": [p]}, agent="r1")
    assert meta["items"][0]["ok"], meta
    assert arrays["i0_x"].shape == (301, len(d["observed"])) and arrays["i0_y"].shape == (301, d["readout_dim"])
    assert meta["ledger"]["units"] == d["cost_units"] and calls == []
    pf = {"system": full, "params_seed": 3, "t_end": 0.2, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]]}
    _, meta2 = srv.handle_request({"protocols": [pf]}, agent="r1")
    assert calls == [1] and not meta2["items"][0]["ok"] and meta2["items"][0]["error"].startswith("simulation failed (reference ")
    assert "remote unavailable" in (tmp_path / "ledger" / "errors.jsonl").read_text(encoding="utf-8")


def test_policy_on_spread_and_process_noise():
    s = toy_sysdef()
    assert "params_spread" in reason(tbase(params_spread=1.5), s)
    assert reason(tbase(process_noise={"sd": 0.05, "seed": 1}), s) is None                  # the toy allows a development range
    assert "process_noise" in reason(tbase(process_noise={"sd": 0.5, "seed": 1}), s)
    toy_no = {**s, "capability": {**s["capability"], "process_noise": {"supported": True}}}  # supported, but no development range
    assert "not a development condition" in reason(tbase(process_noise={"sd": 0.05, "seed": 1}), toy_no)
    from brainir_causal.systems import REAL_CAPABILITY
    real_like = {**s, "capability": {**s["capability"], "process_noise": REAL_CAPABILITY["process_noise"]}}
    assert "not a development condition" in reason(tbase(process_noise={"sd": 0.05, "seed": 1}), real_like)


def test_toy_process_noise_and_spread():
    toy = ToySystem(3, 0)
    b = tbase(t_end=1.0)
    r0 = toy.simulate(b)
    r1 = toy.simulate({**b, "process_noise": {"sd": 0.05, "seed": 1}})
    r2 = toy.simulate({**b, "process_noise": {"sd": 0.05, "seed": 1}})
    assert np.array_equal(r1["x"], r2["x"]) and not np.array_equal(r0["x"], r1["x"])
    assert not np.array_equal(r0["x"], toy.simulate({**b, "params_spread": 2.0})["x"])


def test_client_roundtrip_through_an_agent_queue(tmp_path, monkeypatch):
    """The sandbox shows an agent only simq/<scratch>: the client defaults to it and the service answers into the same queue."""
    from brainir_causal.simclient import default_queue
    tokens = tmp_path / "outside" / "tokens.json"
    monkeypatch.setenv("P4_SIM_TOKEN", issue_token(tokens, "c2", 10))
    monkeypatch.setenv("P4_CLEAN_ROOT", str(tmp_path / "room"))
    monkeypatch.setenv("P4_AGENT_SCRATCH", "k")
    monkeypatch.delenv("P4_SANDBOX", raising=False)
    srv = _server(tmp_path, {"syn:toy:0": toy_sysdef()}, tokens=tokens)
    assert default_queue() == srv.q / "k"

    def serve_once():
        t0 = time.time()
        while time.time() - t0 < 20:
            reqs = srv.pending()
            if reqs:
                assert reqs[0].parent == srv.q / "k" / "requests"
                srv.handle(reqs[0])
                return
            time.sleep(0.05)

    th = threading.Thread(target=serve_once)
    th.start()
    out = SimClient(agent="c2").run([tbase(events=[{"kind": "current", "t0": 0.2, "t1": 0.3, "targets": {"2": 1.0}}])], poll=0.05)
    th.join()
    assert out[0]["ok"] and out[0]["x"].shape == (101, 5)
    assert not list((srv.q / "results").glob("*")) and set(srv.ledgers) == {"c2"}
    monkeypatch.setenv("P4_SANDBOX", "1")
    assert str(default_queue()).replace("\\", "/") == "/room/simq/k"
