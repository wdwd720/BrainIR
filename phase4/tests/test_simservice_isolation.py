"""Cross-agent isolation of the simulation service (review F round 2, N-M1): tokens bound to their queue (not portable), one store
namespace per agent (what another agent asked never changes the files a request touches, so never its latency), public restart
sources recomputed into each agent's namespace, the Docker pool's mapping of namespaces, and the remote path of real full networks
(an agent's job never reads or writes the shared volume store)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from brainir_causal import families as F
from brainir_causal import protocol as P
from brainir_causal import simservice as S
from brainir_causal import suites as SU
from brainir_causal.store import TrajectoryStore
from brainir_causal.synthadapter import ToySystem

SID = "syn:toy:0"


def toy_sysdef(seed=3, j=0):
    rec = ToySystem(seed, j).public_record()
    rec.update({"tier": "toy", "suite_seed": seed, "targets_public": [0, 1, 2], "edges_public": [[0, 1], [1, 0]],
                "split": F.rotation_split("R4", rec["capability"])})
    return rec


def base(**kw):
    p = {"system": SID, "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]}
    p.update(kw)
    return p


def _server(tmp_path, tokens=None, public_keys=None, name="svc"):
    return S.SimServer(tmp_path / name / "room", {SID: toy_sysdef()}, tmp_path / name / "store", pool="inline",
                       ledger_dir=tmp_path / name / "ledger", tokens=tokens, public_keys=public_keys)


@pytest.fixture()
def counting(monkeypatch):
    """Counts the toy system's simulations (every computation of a trajectory, cached or not)."""
    calls = {"n": 0}
    orig = ToySystem.simulate

    def sim(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)
    monkeypatch.setattr(ToySystem, "simulate", sim)
    return calls


# ------------------------------------------------------------------------------------------------ tokens bound to their queue
def test_a_token_is_accepted_only_through_its_own_queue(tmp_path):
    tokens = tmp_path / "outside" / "tokens.json"
    ta = S.issue_token(tokens, "dev_a", 10, queue="a")
    tb = S.issue_token(tokens, "dev_b", 10, queue="b")
    legacy = S.issue_token(tokens, "tester", 10)
    srv = _server(tmp_path, tokens=tokens)
    req = lambda tok: {"token": tok, "protocols": [base()]}
    assert srv.handle_request(req(ta), queue="a")[1]["items"][0]["ok"]
    for tok, q in ((ta, "b"), (ta, None), (tb, "a"), (tb, None)):
        with pytest.raises(PermissionError, match="missing or unknown simulation token"):
            srv.handle_request(req(tok), queue=q)
    assert srv.handle_request(req(legacy), queue="b")[1]["items"][0]["ok"]       # an unbound (trusted / test) token: any queue
    ta2 = S.issue_token(tokens, "dev_a", 10, queue="a", revoke_queue=True)      # a relaunch revokes the queue's earlier token
    srv._tok_cache = None
    with pytest.raises(PermissionError):
        srv.handle_request(req(ta), queue="a")
    assert srv.handle_request(req(ta2), queue="a")[1]["items"][0]["ok"]
    with pytest.raises(ValueError):
        S.issue_token(tokens, "x", 1, queue="../evil")


def test_the_queue_of_a_request_file_is_its_directory(tmp_path):
    tokens = tmp_path / "outside" / "tokens.json"
    ta = S.issue_token(tokens, "dev_a", 10, queue="a")
    srv = _server(tmp_path, tokens=tokens)

    def drop(queue, rid):
        d = srv.q / queue / "requests"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{rid}.json").write_text(json.dumps({"token": ta, "protocols": [base()]}), encoding="utf-8")
        return d / f"{rid}.json"
    srv.handle(drop("a", "r1"))
    srv.handle(drop("b", "r2"))                                                   # agent a's token planted in agent b's queue
    ok = json.loads((srv.q / "a" / "results" / "r1.json").read_text(encoding="utf-8"))
    bad = json.loads((srv.q / "b" / "results" / "r2.json").read_text(encoding="utf-8"))
    assert ok["status"] == "done" and ok["items"][0]["ok"]
    assert bad["status"] == "error" and "token" in bad["error"] and not (srv.q / "b" / "results" / "r2.npz").stat().st_size > 400


# ------------------------------------------------------------------------------------------------ one store namespace per agent
def _snapshot(root: Path) -> list:
    return sorted((x.relative_to(root).as_posix(), x.stat().st_size, x.stat().st_mtime_ns) for x in root.rglob("*")) if root.exists() else []


def test_each_agent_has_its_own_store_namespace(tmp_path, counting):
    tokens = tmp_path / "outside" / "tokens.json"
    ta, tb = S.issue_token(tokens, "dev_a", 50, queue="a"), S.issue_token(tokens, "dev_b", 50, queue="b")
    srv = _server(tmp_path, tokens=tokens)
    ns_a, ns_b = srv.store_for("dev_a"), srv.store_for("dev_b")
    assert ns_a != ns_b and ns_a.parent == ns_b.parent == srv.store_root / "agents" and srv.store_for(None) == srv.store_root
    p = base(events=[{"kind": "kick", "t": 0.5, "delta": {"1": 0.5}}])
    arr_a, meta_a = srv.handle_request({"token": ta, "protocols": [p]}, queue="a")
    n_after_a = counting["n"]
    srv.handle_request({"token": ta, "protocols": [p]}, queue="a")                # a's own repeat: from a's namespace
    assert counting["n"] == n_after_a and not ns_b.exists()                       # a's requests never touch b's namespace
    arr_b, meta_b = srv.handle_request({"token": tb, "protocols": [p]}, queue="b")  # b never asked: computed in b's namespace
    assert counting["n"] == 2 * n_after_a
    for k in ("i0_x", "i0_y", "i0_u", "i0_t"):
        assert np.array_equal(arr_a[k], arr_b[k])
    assert meta_a["items"][0]["key"] == meta_b["items"][0]["key"]
    srv.handle_request({"token": tb, "protocols": [p]}, queue="b")                # b's own repeat: from b's namespace
    assert counting["n"] == 2 * n_after_a
    before = _snapshot(ns_b)
    srv.handle_request({"token": ta, "protocols": [p, base(params_seed=9)]}, queue="a")   # more of a's work, new and repeated
    assert _snapshot(ns_b) == before                                              # b's files: same names, sizes and times
    for ns in (ns_a, ns_b):
        assert len([r for r in TrajectoryStore(ns).index() if r.get("source") == "simservice"]) >= 1
    assert TrajectoryStore(srv.store_root).index() == []                          # agents never write the shared store
    assert "cached" not in json.dumps(meta_b) and "computed" not in json.dumps(meta_b["items"])


def test_trusted_in_process_callers_share_the_service_store_and_agents_never_read_it(tmp_path, counting):
    tokens = tmp_path / "outside" / "tokens.json"
    ta = S.issue_token(tokens, "dev_a", 50, queue="a")
    srv = _server(tmp_path, tokens=tokens)
    srv.handle_request({"protocols": [base()]}, agent="orch1")
    n = counting["n"]
    srv.handle_request({"protocols": [base()]}, agent="orch2")
    assert counting["n"] == n                                                     # trusted callers: one shared cache
    srv.handle_request({"token": ta, "protocols": [base()]}, queue="a")
    assert counting["n"] == 2 * n                                                 # the agent's namespace does not hold it


def test_the_docker_pool_maps_store_namespaces_into_the_container(tmp_path):
    from brainir_causal.simdocker import CONTAINER_STORE, DockerPool
    pool = DockerPool(store_root=tmp_path / "store", bridge_dir=tmp_path / "bridge")    # never started: nothing reaches a container
    srv = _server(tmp_path, name="svc")
    srv.store_root = tmp_path / "store"
    assert pool.translate({"store_root": str(tmp_path / "store")})["store_root"] == CONTAINER_STORE
    ns = srv.store_for("dev_a")
    assert pool.translate({"store_root": str(ns)})["store_root"] == f"{CONTAINER_STORE}/agents/{ns.name}"
    with pytest.raises(ValueError):
        pool.translate({"store_root": str(tmp_path / "elsewhere")})


# ------------------------------------------------------------------------------------------------ public sources per agent
def test_public_restart_sources_are_recomputed_once_per_agent(tmp_path, counting):
    sysrec = toy_sysdef()
    q1 = P.validate(base())
    out = S.run_job({"sysdef": sysrec, "protocol": q1, "store_root": str(tmp_path / "bench"), "bundle": None})
    tk1 = SU.dataset_key(q1, "toy-public", "toy-engine", sysrec.get("obs_scale"))
    pub = tmp_path / "public_traj.npz"                  # the public arrays a recomputed source must reproduce (fails closed without)
    np.savez_compressed(pub, **{k: np.asarray(out[k]) for k in ("t", "x", "u", "y")})
    table = {"format": S.PUBLIC_KEYS_FORMAT, "entries": {tk1: {"store_key": out["store_key"], "system": SID, "dt": 0.01, "t_end": 1.0,
                                                               "protocol": q1, "traj": str(pub)}}, "aliases": {out["store_key"]: tk1}}
    tokens = tmp_path / "outside" / "tokens.json"
    ta, tb = S.issue_token(tokens, "dev_a", 50, queue="a"), S.issue_token(tokens, "dev_b", 50, queue="b")
    srv = _server(tmp_path, tokens=tokens, public_keys=table)
    ask_a = base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.3}, events=[{"kind": "kick", "t": 0.1, "delta": {"1": 0.5}}])
    ask_b = base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.4})
    assert srv.handle_request({"token": ta, "protocols": [ask_a]}, queue="a")[1]["items"][0]["ok"]
    assert srv.n_sources_recomputed == 1                                           # missing: recomputed into a's namespace
    ask_a2 = dict(ask_a, events=[{"kind": "kick", "t": 0.2, "delta": {"2": 0.5}}])
    srv.handle_request({"token": ta, "protocols": [ask_a2]}, queue="a")
    assert srv.n_sources_recomputed == 1                                           # a's own source: not again
    assert srv.handle_request({"token": tb, "protocols": [ask_b]}, queue="b")[1]["items"][0]["ok"]
    assert srv.n_sources_recomputed == 2                                           # b's namespace did not hold it: recomputed for b
    for who in ("dev_a", "dev_b"):
        assert TrajectoryStore(srv.store_for(who)).has(out["store_key"])
    assert not TrajectoryStore(srv.store_root).has(out["store_key"])


# ------------------------------------------------------------------------------------------------ real full networks: remote path
def test_real_full_network_jobs_go_remote_unless_the_requesters_namespace_holds_them(tmp_path):
    sysdef = {"system_id": "real:X:full", "kind": "real", "mode": "full", "system_hash": "h" * 64, "network": "net0"}
    srv = S.SimServer(tmp_path / "room", {}, tmp_path / "store", pool="inline", ledger_dir=tmp_path / "ledger",
                      remote_backend=lambda jobs: [])
    q = P.validate({"system": "real:X:full", "params_seed": 0, "t_end": 0.5, "dt": 0.001, "stimulus": [[0.0, 1.0]]})
    trusted, job_a = srv._job(sysdef, q), srv._job(sysdef, q, "dev_a")
    assert job_a["fresh"] and not trusted["fresh"] and job_a["store_root"] == str(srv.store_for("dev_a"))
    rec = {"t": np.arange(2.0), "x": np.ones((2, 2)), "y": np.ones((2, 1)), "u": np.ones((2, 1)), "info": {"success": True}}
    TrajectoryStore(srv.store_root).put(S.real_store_key(trusted), dict(rec), {"source": "t"})
    assert srv._is_remote(sysdef, trusted) is False                                 # the shared store holds it (trusted callers)
    assert srv._is_remote(sysdef, job_a) is True                                    # never read from another namespace: remote
    TrajectoryStore(job_a["store_root"]).put(S.real_store_key(job_a), dict(rec), {"source": "t"})
    assert srv._is_remote(sysdef, job_a) is False                                   # the agent's own repeat: from its namespace
    mech = dict(sysdef, mode="mechanism", system_id="real:X:m1")
    assert srv._is_remote(mech, srv._job(mech, dict(q, system="real:X:m1"), "dev_b")) is False   # mechanisms run locally


def test_an_agents_remote_job_neither_reads_nor_writes_the_shared_volume_store(tmp_path, monkeypatch):
    from brainir_causal.p4modal import remote as R
    runs = {"n": 0}

    class Engine:
        def run(self, system, q, store=None):
            runs["n"] += 1
            return {"t": np.arange(3.0), "x": np.ones((3, 2)), "y": np.ones((3, 1)), "u": np.zeros((3, 1)), "info": {"success": True}}

    class VStore:
        def __init__(self):
            self.recs, self.reads, self.writes = {}, 0, 0

        def get(self, key):
            self.reads += 1
            return self.recs.get(key)

        def has(self, key):
            return key in self.recs

        def put(self, key, rec, meta):
            self.writes += 1
            self.recs[key] = rec

    monkeypatch.setattr(R, "_engine", lambda network: Engine())
    monkeypatch.setattr("brainir_causal.realsim.RealSystem.from_record", staticmethod(lambda rec: object()))
    sysdef = {"system_id": "real:X:full", "kind": "real", "mode": "full", "system_hash": "h" * 64, "network": "net0"}
    q = {"system": "real:X:full", "params_seed": 0, "t_end": 0.5, "dt": 0.001, "stimulus": [[0.0, 1.0]]}
    vs = VStore()
    R.sim_record(sysdef, q, vs)                                                     # an orchestrator build fills the volume store
    assert runs["n"] == 1 and vs.writes == 1
    reads = vs.reads
    for _ in range(2):
        _, _, computed = R.sim_record(sysdef, q, vs, fresh=True)                    # agents: always simulated, the store untouched
        assert computed
    assert runs["n"] == 3 and vs.writes == 1 and vs.reads == reads
    assert R.sim_record(sysdef, q, vs)[2] is False and runs["n"] == 3               # the orchestrator's own reuse is unchanged
