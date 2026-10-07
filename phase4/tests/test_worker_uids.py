"""Model workers of one job never kill each other, and a worker process that DIES is an infrastructure fault, never the method's
failed call (P2's finding, 2026-09-27; research/phase4/EVAL_ARCHITECTURE.md section 6).

The bug: every model worker started within one job ran under its ROLE's uid (all phase-A workers of all models shared one uid), and a
worker start SIGKILLs every process of its uid, so interleaving calls to several `RemoteFresh` models (5.11 stability: 10 models)
killed each model's idle worker at the next model's start; its next calls failed with WorkerDied / BrokenPipeError and `safe_call`
scored them as the method's failures. The fix: every LIVE worker holds its own uid of the transport's block, and a start or a clean-up
kills only its own uid; a worker death is restarted once (a fresh process of the same phase, the same call again) and a second death
in a row fails the job loudly (`InfraFault`, a BaseException `safe_call` cannot swallow), which the orchestrator re-submits.

The transport under test is the REAL `LinuxUidTransport` (uid allocation, start, clean-up); only its OS primitives are local: a plain
child process instead of a uid switch, and a process table keyed by uid instead of /proc (so the tests run on any host).
"""

from __future__ import annotations

import os
import pickle
import subprocess
import sys
import textwrap
import types

import numpy as np
import pytest

from brainir_causal import isolation as I
from brainir_causal.fresh import safe_call

# a method whose encode reports WHICH process served the call (its pid) and which model it is (its tag); a history whose last row
# starts with 777 makes the worker process die (os._exit), the test's deterministic death
PID_METHOD = textwrap.dedent("""
    import os
    import numpy as np
    from brainir_causal.api import CausalStateMethod, CausalStateModel, register

    class PidModel(CausalStateModel):
        def __init__(self, tag):
            self.tag = float(tag)
            self.k = {"toy": 3}
        def encode(self, sid, x, u, dt):
            x = np.asarray(x, float)
            if x[-1, 0] == 777.0:
                os._exit(3)
            return np.array([float(os.getpid()), float(len(x)), self.tag])
        def rollout(self, sid, z0, u_future, events, dt):
            Z = np.tile(np.asarray(z0, float), (len(u_future), 1))
            return {"z": Z, "y": Z[:, :1]}
        def readout(self, sid, z, u):
            return np.atleast_2d(z)[:, :1]
        def supports(self, sid, kind):
            return False
        def info(self):
            return {"k": dict(self.k)}

    @register
    class PidMethod(CausalStateMethod):
        name = "pid_method"
        def fit(self, data, *, systems, config=None, seed=0):
            return PidModel((config or {}).get("tag", 0))
""")


@pytest.fixture(scope="module")
def room(tmp_path_factory):
    work = tmp_path_factory.mktemp("uids")
    mdir = work / "methods"
    mdir.mkdir()
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    (mdir / "pid_method.py").write_text(PID_METHOD, encoding="utf-8")
    pub = work / "pub"
    I.build_pubdir(pub)
    local = I.LocalUnsafeTransport(pubdir=pub, method_dir=mdir)
    blobs = {tag: I.fit_records(local, method="pid_method", records=[], systems={"toy": {}}, config={"tag": tag})["model"] for tag in (1, 2)}
    return pub, mdir, blobs, local


class FakeUidTransport(I.LinuxUidTransport):
    """The real LinuxUidTransport; a worker is a plain child process registered under its uid (no uid switch)."""

    def __init__(self, pub, mdir, jobs_root, table, slot: int = 1):
        jobs_root.mkdir(parents=True, exist_ok=True)
        super().__init__(pubdir=str(pub), jobs_root=str(jobs_root), method_dir=str(mdir), slot=slot)
        self.table = table

    def _spawn(self, argv, uid, gid, common):
        env = dict(common["env"])
        if os.name == "nt":
            env.update({"SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\WINDOWS"), "PATH": os.environ.get("PATH", ""),
                        "USERPROFILE": common["cwd"], "TEMP": common["cwd"], "TMP": common["cwd"]})
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=common["cwd"], env=env)
        self.table.setdefault(uid, []).append(p)
        return p

    def _limit(self, pid):
        pass


@pytest.fixture
def fake_os(monkeypatch):
    """kill_uids / ipc_cleanup over the fake process table; every kill is recorded with the LIVE processes it killed."""
    table: dict = {}
    kills: list = []

    def kill(uids=None, rounds=25):
        alive = []
        for u in (list(uids) if uids is not None else list(table)):
            for p in table.get(u, []):
                if p.poll() is None:
                    alive.append((u, p.pid))
                    p.kill()
                    p.wait(10)
        kills.append({"uids": list(uids or []), "alive_killed": alive})
        return len(alive)
    monkeypatch.setattr(I, "kill_uids", kill)
    monkeypatch.setattr(I, "ipc_cleanup", lambda uids=None: 0)
    monkeypatch.setattr(I.os, "chown", lambda *a, **k: None, raising=False)
    return table, kills


def _hist(n: int, rng_seed: int = 0):
    rng = np.random.default_rng(rng_seed)
    return rng.standard_normal((40, 2))[:n], np.zeros((n, 1))


# ---------------------------------------------------------------- the uid allocation
def test_every_live_worker_holds_its_own_uid_of_the_slot_block():
    tr = I.LinuxUidTransport(slot=2)
    a, b, c = tr._take_uid("A"), tr._take_uid("A"), tr._take_uid("B1")
    assert a == I.role_uid("A", 2) and len({a, b, c}) == 3 and set(tr.live_uids()) == {a, b, c}
    assert {a, b, c} <= set(I.slot_uids(2))                          # never another slot's uid
    tr._give_uid(a)
    d = tr._take_uid("A")
    assert d not in (a, b, c)                                        # a freed uid waits: never-used uids go first
    for _ in range(len(I.slot_uids(2)) - 4):                         # the rest of the never-used uids
        tr._take_uid("A")
    tr._give_uid(b)
    assert tr._take_uid("A") == a                                    # then the free uid used longest ago (a before b)
    assert tr._take_uid("A") == b
    with pytest.raises(I.InfraFault):                                # more live workers than uids: loud, never a shared uid
        tr._take_uid("A")


# ---------------------------------------------------------------- two interleaved models in one job
def test_two_interleaved_remote_fresh_models_in_one_job_never_kill_each_other(room, tmp_path, fake_os):
    pub, mdir, blobs, _ = room
    table, kills = fake_os
    tr = FakeUidTransport(pub, mdir, tmp_path / "jobs", table)
    ra, rb = I.RemoteFresh(blobs[1], tr, threads=1), I.RemoteFresh(blobs[2], tr, threads=1)
    pids: dict = {"a": [], "b": []}
    try:
        for n in range(10, 14):                                      # interleaved calls, increasing onsets (no digest restart)
            x, u = _hist(n)
            za = ra.encode("toy", x, u, 0.01)                         # called DIRECTLY: any failure fails the test (no safe_call)
            zb = rb.encode("toy", x, u, 0.01)
            assert (za[1], za[2], zb[1], zb[2]) == (n, 1.0, n, 2.0)
            pids["a"].append(int(za[0]))
            pids["b"].append(int(zb[0]))
        assert len(set(pids["a"])) == 1 and len(set(pids["b"])) == 1   # each model kept ONE live process throughout
        assert len(tr.live_uids()) == 2                               # two live workers, two uids
        # a digest-rule restart of A (its next history ends at a row an earlier history of that process continued) while B is live
        x5, u5 = _hist(5)
        za = ra.encode("toy", x5, u5, 0.01)
        x14, u14 = _hist(14)
        zb = rb.encode("toy", x14, u14, 0.01)
        assert int(za[0]) not in pids["a"] and int(zb[0]) == pids["b"][0]   # A restarted, B untouched
        assert (ra.n_restarts, rb.n_restarts, ra.n_infra, rb.n_infra) == (1, 0, 0, 0)
    finally:
        ra.close()
        rb.close()
    assert tr.live_uids() == []
    assert not [k for k in kills if k["alive_killed"]], kills           # no start or clean-up ever killed a live worker


def test_the_role_uid_allocation_of_before_reproduces_the_bug(room, tmp_path, fake_os, monkeypatch):
    """The regression the fix removes: with every worker of a role on the role's uid, the second model's start kills the first
    model's live worker. With the fix's restart rule the calls still succeed, but LOUDLY (infrastructure events recorded), and the
    kills of live workers are visible; before, they were silent failed calls."""
    pub, mdir, blobs, _ = room
    table, kills = fake_os
    tr = FakeUidTransport(pub, mdir, tmp_path / "jobs_old", table)

    def old_take(role):
        uid = I.role_uid(role, tr.slot)
        tr._live_uids.add(uid)
        return uid
    monkeypatch.setattr(tr, "_take_uid", old_take)
    # no spares here: under the old allocation a spare's start would kill its OWN model's live worker too (the retried call then dies
    # again and the job fails with an InfraFault: louder still); the regression shown is the cross-model kill
    ra, rb = I.RemoteFresh(blobs[1], tr, threads=1, spares=0), I.RemoteFresh(blobs[2], tr, threads=1, spares=0)
    try:
        for n in range(10, 13):
            x, u = _hist(n)
            ra.encode("toy", x, u, 0.01)
            rb.encode("toy", x, u, 0.01)
    finally:
        ra.close()
        rb.close()
    assert [k for k in kills if k["alive_killed"]]                    # live workers were killed by the other model's start
    assert ra.n_infra + rb.n_infra > 0                                # and each death was recorded as infrastructure


# ---------------------------------------------------------------- a worker process that dies
def test_a_worker_killed_from_outside_is_restarted_and_the_call_retried_once(room, tmp_path, fake_os):
    pub, mdir, blobs, _ = room
    table, _kills = fake_os
    tr = FakeUidTransport(pub, mdir, tmp_path / "jobs_kill", table)
    ra = I.RemoteFresh(blobs[1], tr, threads=1)
    try:
        x, u = _hist(10)
        victim = int(ra.encode("toy", x, u, 0.01)[0])
        # killed from outside (e.g. the out-of-memory killer): by the pid the WORKER reported (on a Windows venv the Popen pid is the
        # launcher's, not the interpreter's)
        import signal
        os.kill(victim, signal.SIGTERM)
        x, u = _hist(11)
        z = ra.encode("toy", x, u, 0.01)                              # served by a fresh process: never a failed call
        assert int(z[0]) != victim and z[1] == 11 and ra.n_infra == 1
    finally:
        rec = ra.close()
    assert rec["infra_restarts"] == 1 and rec["phases"]["A"]["infra"][0]["what"] == "died in encode"


def test_a_worker_that_dies_again_fails_the_job_loudly_never_as_the_methods_failure(room):
    pub, mdir, blobs, local = room
    ra = I.RemoteFresh(blobs[1], local, threads=1)
    try:
        x, u = _hist(10)
        x = x.copy()
        x[-1, 0] = 777.0                                              # the worker process dies on this call, every time
        with pytest.raises(I.InfraFault):
            safe_call(ra.encode, "toy", x, u, 0.01)                   # safe_call must NOT turn it into (None, error)
        assert ra.n_infra == 2
    finally:
        ra.close()


# ---------------------------------------------------------------- the container callable, the packed child driver, the Backend
def test_the_container_callable_returns_infra_faults_as_infrastructure_results(monkeypatch):
    from brainir_causal.p4modal import app as A
    from brainir_causal.p4modal import remote as R
    stopped = []
    monkeypatch.setitem(sys.modules, "modal.experimental", types.SimpleNamespace(stop_fetching_inputs=lambda: stopped.append(1)))
    fn = A._container_callable(gated=False)

    def raising(exc):
        def f(p):
            raise exc
        return f
    monkeypatch.setattr(R, "dispatch", raising(I.WorkerDied("A worker (uid 10021 slot 1): no reply to 'call' (eof: None)")))
    r = fn({"__tag": 3, "kind": "iso"})
    assert r["__infra__"] and r["error"].startswith("InfraFault (WorkerDied)") and r["__tag"] == 3 and stopped == [1]
    monkeypatch.setattr(R, "dispatch", raising(ValueError("the job's own error")))
    r = fn({"__tag": 4})
    assert "__infra__" not in r and r["error"].startswith("ValueError")          # a job's own failure stays its result
    monkeypatch.setattr(R, "dispatch", raising(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        fn({"__tag": 5})


def test_a_packed_child_driver_returns_an_infra_fault_as_infrastructure(tmp_path, monkeypatch):
    monkeypatch.setattr(I, "set_nondumpable", lambda: 0)

    def boom(p, slot=None):
        raise I.WorkerDied("died twice")
    monkeypatch.setattr(I, "run_iso_payload", boom)
    pf, of = tmp_path / "in.pkl", tmp_path / "out.pkl"
    pf.write_bytes(pickle.dumps({"payload": {"role": "eval"}, "lock": {}}))
    assert I._slot_main(1, str(pf), str(of)) == 0
    out = pickle.loads(of.read_bytes())
    assert out["__infra__"] and "InfraFault" in out["error"]
    assert issubclass(I.PackInfraError, I.InfraFault) and not issubclass(I.PackInfraError, Exception)


def test_backend_resubmits_infrastructure_results_and_fails_loudly_when_they_persist(monkeypatch):
    from brainir_causal.p4modal import app as A
    be = A.Backend.__new__(A.Backend)
    be.verbose = False
    be.costs, be.refusals, be.hosts, be.infra_faults = [], {}, {}, {}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)

    class _Fn:
        def __init__(self, n_bad):
            self.n_bad, self.calls = n_bad, 0

        def map(self, batch, order_outputs=False, return_exceptions=True):
            for p in batch:
                self.calls += 1
                yield ({"__infra__": True, "error": "InfraFault (WorkerDied): died twice", "__tag": p["__tag"]}
                       if self.calls <= self.n_bad else {"ok": True, "__tag": p["__tag"]})
    be.fns = {"iso_pack_eval": _Fn(1)}
    res = A.Backend.run(be, [{"i": 0}], "iso_pack_eval", poll_s=0.01, batch_s=0.01)
    assert res[0]["ok"] and be.infra_faults == {"iso_pack_eval": 1}              # re-submitted, then it ran
    be.fns = {"iso_pack_eval": _Fn(99)}
    res = A.Backend.run(be, [{"i": 0}], "iso_pack_eval", poll_s=0.01, batch_s=0.01)
    assert isinstance(res[0], RuntimeError) and "call failed repeatedly" in str(res[0]) and "InfraFault" in str(res[0])


# ---------------------------------------------------------------- pre-started spare workers
def _restart_heavy(rf, n0: int = 30, k: int = 6):
    """k calls whose histories get SHORTER: each ends at a row the previous history continued, so the digest rule restarts before
    every call after the first (as on systems whose records sit on exact fixed points)."""
    out = []
    for n in range(n0, n0 - k, -1):
        x, u = _hist(n)
        z = rf.encode("toy", x, u, 0.01)
        out.append((int(z[0]), float(z[1]), float(z[2])))
    return out


def test_spares_leave_every_result_unchanged_and_never_hold_a_model_early(room, tmp_path, fake_os, monkeypatch):
    import re
    pub, mdir, blobs, _ = room
    table, _kills = fake_os
    tr = FakeUidTransport(pub, mdir, tmp_path / "jobs_spares", table)
    loaded: list = []              # (uid, Popen) of every worker that received a model
    violations: list = []
    orig = I.WorkerClient.request

    def req(self, op, **kw):
        uid = int(re.search(r"uid (\d+)", self.where).group(1))
        if op == "load_model":
            # no OTHER worker of this model that received a model may still be alive when a (spare) worker gets its model
            alive = [u for u, p in loaded if p.poll() is None]
            if alive:
                violations.append(("model loaded while an earlier loaded worker is alive", uid, alive))
        if op == "call" and uid not in {u for u, _p in loaded}:
            violations.append(("a call before the worker's model load", uid))
        r = orig(self, op, **kw)
        if op == "load_model":
            loaded.append((uid, table[uid][-1]))
        return r
    monkeypatch.setattr(I.WorkerClient, "request", req)
    r0 = I.RemoteFresh(blobs[1], tr, threads=1, spares=0)
    try:
        base = _restart_heavy(r0)
    finally:
        rec0 = r0.close()
    loaded.clear()
    r2 = I.RemoteFresh(blobs[1], tr, threads=1, spares=2)
    try:
        with_spares = _restart_heavy(r2)
    finally:
        rec2 = r2.close()
    assert [z[1:] for z in with_spares] == [z[1:] for z in base]              # identical results (the pid is the only difference)
    assert rec0["worker_restarts"] == rec2["worker_restarts"] == 5 and rec0["spares_used"] == 0
    assert rec2["spares_used"] >= 3                                         # after the first restart, restarts took spares
    assert not violations, violations
    assert tr.live_uids() == []                                             # every spare was closed with the model


def test_spares_keep_uids_free_for_the_live_workers_restarts():
    class _Tr:
        _block = list(range(10001, 10006))                                  # a block of 5 uids

        def __init__(self, live):
            self._live = live

        def live_uids(self):
            return list(range(10001, 10001 + self._live))
    rf = I.RemoteFresh(b"", _Tr(2), spares=3)
    assert rf._spare_room()                                                 # 2 live + 1 new + 2 kept free <= 5
    rf._transport = _Tr(3)
    assert not rf._spare_room()                                             # 3 + 1 + 2 > 5: no spare
    rf._transport = types.SimpleNamespace()                                  # a transport without a uid block: spares allowed
    assert rf._spare_room()
