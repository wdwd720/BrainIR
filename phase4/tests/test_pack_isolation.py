"""Packed-container execution (research/phase4/LEVEL_B_EXECUTION.md; P1). Local regression guards for the volume-freshness fix (P2's
report, 2026-09-26) and the packing helpers; the Modal isolation and stress evidence is scripts/p4/smoke_pack_modal.py.

- pack_ready reloads each mounted volume exactly ONCE, before the container lockdown, and only once across concurrent calls.
- remote.run_iso / run_call never reload or commit per input in a packed class, and a commit request there fails LOUDLY.
- role_uid / slot_uids / slot_gid give each slot a disjoint uid block and its own group; resolve_iso_target refuses method code.
- Backend.run_packed schedules longest-first and resumes from a done directory without recomputation.
"""

from __future__ import annotations

import pickle

import pytest

from brainir_causal import isolation as I
from brainir_causal.p4modal import remote as R


# ---------------------------------------------------------------- uid / group blocks
def test_slots_get_disjoint_uid_blocks_and_own_group():
    assert I.role_uid("fit", None) == I.ROLE_UIDS["fit"]           # slot 0 / None = the unpacked uids
    assert I.role_uid("fit", 0) == I.ROLE_UIDS["fit"]
    blocks = [set(I.slot_uids(s)) for s in range(1, I.MAX_SLOTS + 1)]
    for a in range(len(blocks)):
        for b in range(a + 1, len(blocks)):
            assert not (blocks[a] & blocks[b]), (a + 1, b + 1)     # disjoint across slots
    # every role's uid in a slot lies in that slot's block, and the groups are distinct per slot
    for s in range(1, I.MAX_SLOTS + 1):
        for role in I.ROLE_UIDS:
            assert I.role_uid(role, s) in set(I.slot_uids(s))
        assert I.slot_gid(s) == I.SLOT_GID0 + s
    assert I.UID_MAX >= max(max(b) for b in blocks)


def test_slot_out_of_range_is_refused():
    with pytest.raises(ValueError):
        I.LinuxUidTransport(slot=0)                                # slots are 1..MAX_SLOTS (0 / None means unpacked)
    with pytest.raises(ValueError):
        I.LinuxUidTransport(slot=I.MAX_SLOTS + 1)


# ---------------------------------------------------------------- iso "call" target resolution
def test_resolve_iso_target_refuses_method_code_and_unknown_modules():
    with pytest.raises(PermissionError):
        I.resolve_iso_target("brainir_causal.methods.foo:bar")
    with pytest.raises(PermissionError):
        I.resolve_iso_target("some_other_pkg.mod:fn")
    with pytest.raises(ValueError):
        I.resolve_iso_target("brainir_causal.harness")            # no function part
    fn = I.resolve_iso_target("brainir_causal.harness:references_job")
    assert callable(fn)


# ---------------------------------------------------------------- pack_ready: reload ONCE, before the lockdown
def test_pack_ready_reloads_each_volume_once_before_lockdown(monkeypatch):
    I._PACK.update(ready=False, free=[], busy=set())
    events = []
    monkeypatch.setattr(I, "container_lockdown", lambda: events.append(("lockdown",)) or {"dumpable0": 0})
    monkeypatch.setattr(I, "ensure_pubdir", lambda *a, **k: {"n_files": 1})
    monkeypatch.setattr(I, "namespaces_ok", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(I.os, "makedirs", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(I.os, "chown", lambda *a, **k: None, raising=False)   # os.chown is absent on Windows
    monkeypatch.setattr(I.os, "chmod", lambda *a, **k: None, raising=False)

    class _St:
        st_mode = 0o40700
    monkeypatch.setattr(I.os, "stat", lambda *a, **k: _St())

    def reload_one(v):
        events.append(("reload", v))

    I.pack_ready(8, reload_vols=["fit", "eval", "store"], reload_once=reload_one)
    I.pack_ready(8, reload_vols=["fit", "eval", "store"], reload_once=reload_one)   # a second concurrent input: no extra reload/lockdown
    reloads = [e for e in events if e[0] == "reload"]
    assert reloads == [("reload", "fit"), ("reload", "eval"), ("reload", "store")]  # once each, in order
    assert [e for e in events if e[0] == "lockdown"] == [("lockdown",)]             # locked down exactly once
    assert events.index(("lockdown",)) > events.index(("reload", "store"))          # every reload BEFORE the lockdown
    I._PACK.update(ready=False, free=[], busy=set())


def test_pack_ready_refreshes_once_for_a_newer_wave_generation_after_draining(monkeypatch):
    import threading
    I._PACK.update(ready=False, free=[], busy=set())
    events = []
    monkeypatch.setattr(I, "container_lockdown", lambda: events.append(("lockdown",)) or {"dumpable0": 0})
    monkeypatch.setattr(I, "ensure_pubdir", lambda *a, **k: {"n_files": 1})
    monkeypatch.setattr(I, "namespaces_ok", lambda *a, **k: {"ok": True})
    for name in ("makedirs", "chown", "chmod"):
        monkeypatch.setattr(I.os, name, lambda *a, **k: None, raising=False)

    class _St:
        st_mode = 0o40700
    monkeypatch.setattr(I.os, "stat", lambda *a, **k: _St())
    rel = lambda v: events.append(("reload", v))                         # noqa: E731
    I.pack_ready(4, reload_vols=["store"], reload_once=rel, gen=1)
    I.pack_ready(4, reload_vols=["store"], reload_once=rel, gen=1)        # same wave: nothing again
    assert events == [("reload", "store"), ("lockdown",)]
    # a newer wave arrives while a slot of the older wave is busy: it waits for the drain, then refreshes exactly once
    I._PACK["busy"] = {1}
    done = []
    th = threading.Thread(target=lambda: done.append(I.pack_ready(4, reload_vols=["store"], reload_once=rel, gen=2)))
    th.start()
    th.join(timeout=0.5)
    assert th.is_alive() and events == [("reload", "store"), ("lockdown",)]  # still draining: no reload under a busy slot
    with I._PACK["cond"]:
        I._PACK["busy"] = set()
        I._PACK["cond"].notify_all()
    th.join(timeout=10)
    assert not th.is_alive() and done
    assert events[2:] == [("reload", "store"), ("lockdown",)] and I._PACK["gen"] == 2 and I._PACK["refreshes"] == 1
    I.pack_ready(4, reload_vols=["store"], reload_once=rel, gen=2)        # the same newer wave again: no second refresh
    assert len(events) == 4
    I._PACK.update(ready=False, free=[], busy=set())


def test_trusted_packed_reload_once_per_generation(monkeypatch):
    R._PACK_RELOAD.update(done=set(), gen=0, active=0)
    calls = []
    monkeypatch.setattr(R, "_reload", lambda v: calls.append(v))
    R._reload_once(["fit", "eval"], gen=5)
    R._packed_done()
    R._reload_once(["fit", "eval"], gen=5)                               # same wave: no reload
    R._packed_done()
    assert calls == ["fit", "eval"]
    R._reload_once(["fit"], gen=6)                                       # newer wave, drained (no active input): reloaded again
    R._packed_done()
    assert calls == ["fit", "eval", "fit"] and R._PACK_RELOAD["active"] == 0
    R._PACK_RELOAD.update(done=set(), gen=0, active=0)


# ---------------------------------------------------------------- remote: packed branch never reloads / commits per input
def test_run_iso_packed_branch_delegates_without_per_input_reload_or_commit(monkeypatch):
    calls = {"reload": [], "commit": []}
    monkeypatch.setattr(R, "_reload", lambda v: calls["reload"].append(v))
    monkeypatch.setattr(R, "_commit", lambda v: calls["commit"].append(v))
    seen = {}
    monkeypatch.setattr("brainir_causal.isolation.run_iso_packed",
                        lambda p, slots, reload_once=None: seen.update(slots=slots, reload_once=reload_once) or {"ok": 1})
    out = R.run_iso({"__slots": 8, "role": "fit", "reload": ["fit"], "job": {}})
    assert out["ok"] == 1 and seen["slots"] == 8 and seen["reload_once"] is R._reload
    assert calls["reload"] == [] and calls["commit"] == []          # the packed branch itself reloads/commits nothing
    with pytest.raises(ValueError):
        R.run_iso({"__slots": 8, "role": "loop", "commit": ["eval"], "job": {}})   # a commit request fails loudly


def test_run_call_packed_reloads_once_and_refuses_commit(monkeypatch):
    R._PACK_RELOAD["done"] = set()
    calls = {"reload": [], "commit": [], "sub": 0}
    monkeypatch.setattr(R, "_reload", lambda v: calls["reload"].append(v))
    monkeypatch.setattr(R, "_commit", lambda v: calls["commit"].append(v))
    monkeypatch.setattr(R, "_subprocess", lambda *a, **k: {"result": None} or {})
    monkeypatch.setattr(R, "_collect", lambda *a, **k: {})
    R.run_call({"__slots": 8, "target": "m:f", "reload": ["fit", "eval"], "job_id": "a"})
    R.run_call({"__slots": 8, "target": "m:f", "reload": ["fit", "eval"], "job_id": "b"})
    assert sorted(calls["reload"]) == ["eval", "fit"] and calls["commit"] == []     # once each across two inputs, never commit
    with pytest.raises(ValueError):
        R.run_call({"__slots": 8, "target": "m:f", "commit": ["store"], "job_id": "c"})
    R._PACK_RELOAD["done"] = set()


def test_unpacked_run_call_still_reloads_and_commits_per_input(monkeypatch):
    calls = {"reload": [], "commit": []}
    monkeypatch.setattr(R, "_reload", lambda v: calls["reload"].append(v))
    monkeypatch.setattr(R, "_commit", lambda v: calls["commit"].append(v))
    monkeypatch.setattr(R, "_subprocess", lambda *a, **k: {})
    monkeypatch.setattr(R, "_collect", lambda *a, **k: {})
    R.run_call({"target": "m:f", "reload": ["fit"], "commit": ["eval"], "job_id": "d"})
    assert calls["reload"] == ["fit"] and calls["commit"] == ["eval"]


# ---------------------------------------------------------------- Backend.run_packed: longest-first + resume
def _fake_backend():
    from brainir_causal.p4modal.app import Backend
    be = Backend.__new__(Backend)
    be.verbose = False
    be.costs, be.refusals, be.hosts = [], {}, {}
    return be


def test_run_packed_schedules_longest_first_and_resumes(tmp_path, monkeypatch):
    be = _fake_backend()
    submitted = {}

    def fake_run(payloads, cls, label="", on_result=None):
        submitted["order"] = [p["i"] for p in payloads]
        out = []
        for k, p in enumerate(payloads):
            r = {"i": p["i"], "done": True}
            out.append(r)
            if on_result:
                on_result(k, r)
        return out

    monkeypatch.setattr(be, "run", fake_run)
    payloads = [{"i": i} for i in range(4)]
    exp = [1.0, 9.0, 3.0, 9.0]                    # longest first, ties by input order: 1, 3, 2, 0
    keys = [f"k{i}" for i in range(4)]
    done = tmp_path / "done"
    res = be.run_packed(payloads, "pack_xl", expected_s=exp, keys=keys, done_dir=done)
    from brainir_causal.p4modal.app import _key_file
    assert submitted["order"] == [1, 3, 2, 0]
    assert [r["i"] for r in res] == [0, 1, 2, 3]  # returned in INPUT order
    assert (done / f"{_key_file(keys[0])}.pkl").exists()             # each result stored under its key as it arrives
    # resume: a second call submits nothing (all done files present)
    submitted["order"] = None
    res2 = be.run_packed(payloads, "pack_xl", expected_s=exp, keys=keys, done_dir=done)
    assert submitted["order"] is None
    assert [r["i"] for r in res2] == [0, 1, 2, 3]


def test_namespaces_decide_fails_closed_on_a_bad_interface_list_or_up_loopback():
    host = ("net:[1]", "ipc:[2]")
    good = "10021 20001 net:[9] ipc:[10] lo 0x8"                       # own uid/gid, own ns, only lo, lo DOWN (no IFF_UP)
    assert I._namespaces_decide(0, good, "", host, 10021, 20001)["ok"]
    # a non-loopback interface -> not ok
    d = I._namespaces_decide(0, "10021 20001 net:[9] ipc:[10] eth0,lo 0x8", "", host, 10021, 20001)
    assert not d["ok"] and any("non-loopback" in r for r in d["reasons"])
    # loopback UP (IFF_UP 0x1) -> not ok
    d = I._namespaces_decide(0, "10021 20001 net:[9] ipc:[10] lo 0x9", "", host, 10021, 20001)
    assert not d["ok"] and any("loopback is UP" in r for r in d["reasons"])
    # shares the host network namespace -> not ok
    d = I._namespaces_decide(0, "10021 20001 net:[1] ipc:[10] lo 0x8", "", host, 10021, 20001)
    assert not d["ok"] and any("host network" in r for r in d["reasons"])
    # ran as the wrong uid (setpriv failed to drop) -> not ok
    d = I._namespaces_decide(0, "0 0 net:[9] ipc:[10] lo 0x8", "", host, 10021, 20001)
    assert not d["ok"] and any("ran as 0:0" in r for r in d["reasons"])
    # the worker did not report / non-zero exit -> not ok
    assert not I._namespaces_decide(1, "", "boom", host, 10021, 20001)["ok"]
    assert not I._namespaces_decide(0, "garbage", "", host, 10021, 20001)["ok"]
    # unparseable lo flags -> assume up -> fail closed
    d = I._namespaces_decide(0, "10021 20001 net:[9] ipc:[10] lo zzz", "", host, 10021, 20001)
    assert not d["ok"] and any("loopback is UP" in r for r in d["reasons"])


def test_run_packed_requires_a_packed_class():
    be = _fake_backend()
    with pytest.raises(ValueError):
        be.run_packed([{"i": 0}], "eval_s")       # not a packed class


def test_iso_submissions_refuse_oversized_inline_data_and_accept_refs(monkeypatch):
    be = _fake_backend()
    sent = {}
    monkeypatch.setattr(be, "run", lambda payloads, cls, label="", on_result=None: sent.update(cls=cls) or [{} for _ in payloads])
    # every iso class is block_network: a >2 MiB model INLINE is refused before submission, packed or not, pointing to staging by ref
    big = {"role": "eval", "job": {}, "model": b"0" * (3 * 1024 * 1024)}
    for call, cls in ((be.run_iso, "iso_eval_s"), (be.run_iso_packed, "iso_pack_eval")):
        with pytest.raises(ValueError) as ei:
            call([big], cls)
        assert "block_network" in str(ei.value) and "stage_put" in str(ei.value) and "cls" not in sent
    # the same model passed BY REF is accepted on both
    by_ref = {"role": "eval", "job": {}, "model_ref": {"stage": "a" * 64, "size": 3 * 1024 * 1024, "vol": "store"}}
    be.run_iso([by_ref], "iso_eval_s")
    assert sent["cls"] == "iso_eval_s"
    be.run_iso_packed([by_ref], "iso_pack_eval")
    assert sent["cls"] == "iso_pack_eval"


def test_staging_is_content_addressed_hash_checked_private_and_routed_by_data_class(tmp_path):
    import os
    import stat as st
    roots = {"store": str(tmp_path / "store" / "_staged"), "eval": str(tmp_path / "eval" / "_staged")}
    data = os.urandom(3 * 1024 * 1024)
    r1 = I.stage_blob(data, vol="store", roots=roots)
    r2 = I.stage_blob(data, vol="store", roots=roots)                  # idempotent: same content -> same ref, one file
    assert r1 == r2 and r1["vol"] == "store" and r1["size"] == len(data)
    import hashlib
    assert r1["stage"] == hashlib.sha256(data).hexdigest()              # the path is the DRIVER's hash of the bytes, not a worker's name
    assert I.read_staged(r1, roots=roots) == data
    f = tmp_path / "store" / "_staged" / r1["stage"][:2] / f"{r1['stage']}.bin"
    if os.name != "nt":
        assert st.S_IMODE(os.stat(f.parent).st_mode) == 0o700 and st.S_IMODE(os.stat(f).st_mode) & 0o077 == 0
    f.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))                     # corrupted on the volume -> refused, never used
    with pytest.raises(I.WorkerError):
        I.read_staged(r1, roots=roots)
    for bad in ("../../etc/passwd", "z" * 64, "ab"):                     # a malformed ref never becomes a path
        with pytest.raises(I.WorkerError):
            I.read_staged({"stage": bad, "vol": "store"}, roots=roots)
    e = I.stage_blob(b"held-out-derived", vol="eval", roots=roots)       # evaluation records / loop files: the EVAL volume only
    assert e["vol"] == "eval" and (tmp_path / "eval" / "_staged" / e["stage"][:2] / f"{e['stage']}.bin").exists()
    assert not (tmp_path / "store" / "_staged" / e["stage"][:2]).exists()


def test_fit_inline_stages_by_total_size_largest_first(tmp_path):
    import os
    roots = {"store": str(tmp_path / "s" / "_staged"), "eval": str(tmp_path / "e" / "_staged")}
    # a real full network's loop: 5 checkpoints of ~470 KB (each under STAGE_THRESHOLD) + records: 2.3 MB together, over the limit
    files = {f"ckpt_{i:04d}.pkl": os.urandom(470_000 + i) for i in range(5)}
    files.update({"loop_record.json": b"{}" * 100, "experiments.jsonl": b"x" * 20_000})
    out = {"loop_record": {"n": 5}, "files": dict(files), "file_refs": {}}
    vols = I.fit_inline(out, "loop", mounted={"store", "eval"}, roots=roots)
    inline = sum(len(b) for b in out["files"].values())
    assert vols == {"eval"} and inline <= I.MAX_INLINE_OUTPUT and out["file_refs"]
    staged = set(out["file_refs"])
    assert all(n.startswith("ckpt_") for n in staged)                   # the largest parts went first; the small records stay inline
    for n, ref in out["file_refs"].items():                            # and every staged part reads back intact, from the EVAL volume
        assert ref["vol"] == "eval" and I.read_staged(ref, roots=roots) == files[n]
    # an evaluation record just under the per-part threshold plus the rest of the reply: staged when the TOTAL is over the limit
    out = {"result": {"blob": os.urandom(I.STAGE_THRESHOLD - 1000)}, "extra": os.urandom(I.MAX_INLINE_OUTPUT - I.STAGE_THRESHOLD + 50_000)}
    assert I.fit_inline(out, "eval", mounted={"store", "eval"}, roots=roots) == {"eval"} and "result_ref" in out and "result" not in out
    # a fit's model goes to the STORE volume; small outputs are left alone
    out = {"model": os.urandom(I.MAX_INLINE_OUTPUT + 1), "side": {}}
    assert I.fit_inline(out, "fit", mounted={"store"}, roots=roots) == {"store"} and out["model_ref"]["vol"] == "store"
    small = {"model": b"x" * 10, "side": {}}
    assert I.fit_inline(small, "fit", mounted={"store"}, roots=roots) == set() and small["model"] == b"x" * 10
    # a held-out-derived part on a container without the eval volume: a clear error, never a silent loss
    with pytest.raises(I.WorkerError):
        I.fit_inline({"files": dict(files)}, "loop", mounted={"store"}, roots=roots)


def test_call_role_propagates_the_targets_staged_volumes(tmp_path, monkeypatch):
    monkeypatch.setattr(I, "JOBS_ROOT", str(tmp_path / "jobs"))
    (tmp_path / "jobs").mkdir()
    monkeypatch.setattr(I, "container_lockdown", lambda: {"dumpable0": 0})
    monkeypatch.setattr(I, "ensure_pubdir", lambda *a, **k: {"n_files": 1})
    monkeypatch.setattr(I, "LinuxUidTransport", lambda **k: object())
    monkeypatch.setattr(I, "kill_uids", lambda *a, **k: 0)
    monkeypatch.setattr(I, "ipc_cleanup", lambda *a, **k: 0)
    monkeypatch.setattr(I, "_mounted_stage_vols", lambda: {"store", "eval"})
    monkeypatch.setattr(I, "resolve_iso_target",
                        lambda t: (lambda job, transport, models: {"model_ref": {"stage": "a" * 64, "size": 3, "vol": "store"},
                                                                   "staged": ["store", "elsewhere"]}))
    out = I.run_iso_payload({"role": "call", "target": "x:y", "job": {}})
    assert out["staged"] == ["store"] and out["iso"]["staged"] == ["store"]   # restricted to the staging volumes, so the runner commits


def test_warm_packed_container_refuses_an_invisible_staged_input_without_reloading(tmp_path, monkeypatch):
    import hashlib
    roots = {"store": str(tmp_path / "s" / "_staged"), "eval": str(tmp_path / "e" / "_staged")}
    monkeypatch.setattr(I, "STAGE_ROOTS", roots)
    stopped = []
    import types
    monkeypatch.setitem(__import__("sys").modules, "modal.experimental", types.SimpleNamespace(stop_fetching_inputs=lambda: stopped.append(1)))
    calls = []
    monkeypatch.setattr(I, "pack_ready", lambda slots, **k: calls.append(("pack_ready", k.get("gen"))) or {"record": {}, "namespaces": {}})

    def no_slot(*a, **k):
        raise AssertionError("a slot must not be taken for an invisible staged input")
    monkeypatch.setattr(I, "_take_slot", no_slot)
    I._PACK["busy"] = {1, 2}                                            # other slots are busy: the refusal must not wait for them
    data = b"model-bytes" * 1000
    ref = {"stage": hashlib.sha256(data).hexdigest(), "size": len(data), "vol": "store"}
    r = I.run_iso_packed({"role": "eval", "job": {}, "model_ref": ref, "__gen": 3}, 4)
    assert r["__refused__"] and r["stale_staging"] == [ref["stage"][:16]] and stopped == [1]
    assert calls == [("pack_ready", 3)]                                 # only the normal readiness call: no extra reload, no lockdown
    # once the blob is visible (a fresh container's start-up reload), the job proceeds to take a slot
    I.stage_blob(data, vol="store", roots=roots)
    assert I.staged_visible(ref, roots=roots)
    with pytest.raises(AssertionError, match="slot must not be taken"):
        I.run_iso_packed({"role": "eval", "job": {}, "model_ref": ref}, 4)   # reaches _take_slot now (stubbed to raise here)
    I._PACK["busy"] = set()


def test_backend_bounds_stale_refusals(monkeypatch):
    be = _fake_backend()
    from brainir_causal.p4modal import app as A

    class _Fn:
        def __init__(self):
            self.n = 0

        def map(self, batch, order_outputs=False, return_exceptions=True):      # the first wave and every re-submission batch
            for p in batch:
                self.n += 1
                yield {"__refused__": True, "stale_staging": ["abc"], "__tag": p["__tag"]}

        def remote(self, p):
            raise AssertionError("re-submissions go out as batched maps, never one call per input")

        def spawn(self, p):
            raise AssertionError("the async path must never be used (8 KiB output limit)")
    fn = _Fn()
    be.fns = {"iso_pack_eval": fn}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)
    res = A.Backend.run(be, [{"role": "eval"}], "iso_pack_eval", poll_s=0.01, batch_s=0.01)
    assert isinstance(res[0], RuntimeError) and "not visible" in str(res[0]) and fn.n == A.MAX_STALE + 1


def test_run_resubmits_a_refused_input_at_once_not_after_the_slowest_job(monkeypatch):
    import threading
    from brainir_causal.p4modal import app as A
    be = _fake_backend()
    resubmitted = threading.Event()
    maps = []

    class _Fn:
        def map(self, batch, order_outputs=False, return_exceptions=True):
            maps.append([p["__tag"] for p in batch])
            if len(maps) == 1:                                           # the first wave
                yield {"__refused__": True, "__tag": batch[0]["__tag"]}     # input 0: refused by the host gate at once
                # input 1 is the slow job: it ends only after input 0 was re-submitted and RAN (the earlier waves re-submitted after
                # the whole map)
                assert resubmitted.wait(5.0), "the refused input was not re-submitted while the slow job was running"
                yield {"ok": True, "__tag": batch[1]["__tag"]}
            else:                                                        # a re-submission batch: synchronous, 2 MiB inline path
                resubmitted.set()
                for p in batch:
                    yield {"ok": True, "retry": True, "__tag": p["__tag"]}

        def remote(self, p):
            raise AssertionError("re-submissions go out as batched maps, never one call per input")

        def spawn(self, p):
            raise AssertionError("the async path must never be used (8 KiB output limit)")
    be.fns = {"iso_pack_eval": _Fn()}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)
    got = []
    res = A.Backend.run(be, [{"i": 0}, {"i": 1}], "iso_pack_eval", on_result=lambda i, r: got.append(i), poll_s=0.01, batch_s=0.01)
    assert res[0]["retry"] and res[1]["ok"] and sorted(got) == [0, 1] and be.refusals == {"iso_pack_eval": 1}
    assert maps == [[0, 1], [0]]


def test_run_batches_refusals_and_bounds_the_resubmission_maps(monkeypatch):
    import threading
    from brainir_causal.p4modal import app as A
    be = _fake_backend()
    live, peak, lock = [0], [0], threading.Lock()
    first = threading.Event()

    class _Fn:
        def __init__(self):
            self.calls = 0

        def map(self, batch, order_outputs=False, return_exceptions=True):
            with lock:
                self.calls += 1
                call = self.calls
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            try:
                if call == 1:                                            # the first wave: every input refused (a bad host burst)
                    for p in batch:
                        yield {"__refused__": True, "__tag": p["__tag"]}
                    first.set()
                    return
                for p in batch:                                          # re-submission batches: refused once more, then accepted
                    yield ({"ok": True, "__tag": p["__tag"]} if call > 3 else {"__refused__": True, "__tag": p["__tag"]})
            finally:
                with lock:
                    live[0] -= 1
    fn = _Fn()
    be.fns = {"iso_pack_fit": fn}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)
    monkeypatch.setattr(A, "RESUBMIT_MAPS", 2)
    res = A.Backend.run(be, [{"i": i} for i in range(20)], "iso_pack_fit", poll_s=0.01, batch_s=0.01)
    assert all(r.get("ok") for r in res) and peak[0] <= 1 + A.RESUBMIT_MAPS   # the first map + at most RESUBMIT_MAPS re-submissions
    assert fn.calls < 20                                                 # refused inputs go out in batches, not one map per input


def test_run_gives_up_a_resubmitted_call_that_keeps_failing_on_modal(monkeypatch):
    from brainir_causal.p4modal import app as A
    be = _fake_backend()
    n_maps = []

    class _Fn:
        def map(self, batch, order_outputs=False, return_exceptions=True):
            n_maps.append(1)
            if len(n_maps) == 1:
                yield {"__refused__": True, "__tag": batch[0]["__tag"]}
                return
            for _p in batch:                                             # e.g. the job exceeds its class timeout, every time
                yield RuntimeError("FunctionTimeoutError: the job exceeded its class timeout")
    be.fns = {"iso_pack_eval": _Fn()}
    monkeypatch.setattr(be, "_cost", lambda *a, **k: None)
    res = A.Backend.run(be, [{"i": 0}], "iso_pack_eval", poll_s=0.01, batch_s=0.01)
    assert isinstance(res[0], RuntimeError) and "failed repeatedly" in str(res[0]) and len(n_maps) == 1 + A.MAX_CALL_FAILS


def test_the_backend_never_uses_the_async_invocation_path():
    """spawn / spawn_map return at most 8 KiB inline (modal MAX_ASYNC_OBJECT_SIZE_BYTES) and move any larger output through the blob
    store, which a block_network (iso) container cannot reach: every Backend submission is a synchronous map, and nothing polls an async
    FunctionCall (a poll's 'not ready' is modal's or the built-in TimeoutError, which an earlier check mistook for a failure, E13)."""
    import inspect
    from brainir_causal.p4modal import app as A
    src = inspect.getsource(A)
    code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())   # comments may name it; code may not
    for bad in (".spawn(", "spawn_map(", ".remote.aio", "get(timeout=0)", "FunctionCall"):
        assert bad not in code, bad


def test_inline_size_is_the_serialized_size_not_the_text_form():
    from brainir_causal.p4modal import app as A
    model = bytes(range(256)) * 4453                                    # 1.14 MB: P3's model, refused as "4.08 MB" by the text-form estimate
    p = {"kind": "iso", "role": "call", "target": "p4post_iso:fit_c", "job": {"sid": "x", "seed": 0}, "models": {"model": model}}
    n = A._payload_bytes(p)
    assert len(model) <= n <= len(model) + 4096
    A._check_inline([p], "iso_pack_fit")                                # accepted
    with pytest.raises(ValueError, match="block_network"):
        A._check_inline([dict(p, models={"model": bytes(2 * 1024 * 1024)})], "iso_pack_fit")


def test_call_role_reads_input_models_by_ref_and_stages_results_by_the_containers_volumes(tmp_path, monkeypatch):
    import os
    roots = {"store": str(tmp_path / "s" / "_staged"), "eval": str(tmp_path / "e" / "_staged")}
    monkeypatch.setattr(I, "STAGE_ROOTS", roots)
    monkeypatch.setattr(I, "JOBS_ROOT", str(tmp_path / "jobs"))
    (tmp_path / "jobs").mkdir()
    monkeypatch.setattr(I, "container_lockdown", lambda: {"dumpable0": 0})
    monkeypatch.setattr(I, "ensure_pubdir", lambda *a, **k: {"n_files": 1})
    monkeypatch.setattr(I, "LinuxUidTransport", lambda **k: object())
    monkeypatch.setattr(I, "kill_uids", lambda *a, **k: 0)
    monkeypatch.setattr(I, "ipc_cleanup", lambda *a, **k: 0)
    monkeypatch.setattr(I, "_mounted_stage_vols", lambda: {"store", "eval"})
    data = os.urandom(3 * 1024 * 1024)
    ref = I.stage_blob(data, vol="store", roots=roots)                  # Backend.stage_put's layout
    seen = {}
    monkeypatch.setattr(I, "resolve_iso_target", lambda t: (lambda job, transport, models: seen.update(models) or {"ok": 1}))
    p = {"role": "call", "target": "x:y", "job": {}, "models": {"small": b"s"}, "model_refs": {"model": ref}}
    assert ref in I.staged_input_refs(p)                                # a warm packed container's freshness check covers it
    I.run_iso_payload(p)
    assert seen["model"] == data and seen["small"] == b"s"              # read by the driver, hash-checked, passed on as opaque bytes
    # a large call RESULT: on a fit class (no eval volume: public data only) -> STORE; with the eval volume mounted -> EVAL
    big = {"blob": os.urandom(I.MAX_INLINE_OUTPUT + 10)}
    assert I.fit_inline({"result": big}, "call", mounted={"store"}, roots=roots) == {"store"}
    assert I.fit_inline({"result": big}, "call", mounted={"store", "eval"}, roots=roots) == {"eval"}
    with pytest.raises(I.WorkerError):                                  # an EVALUATION record never goes to the store volume
        I.fit_inline({"result": big}, "eval", mounted={"store"}, roots=roots)


def test_cost_records_container_time_with_startup_idle_tail_and_occupancy_shares():
    from brainir_causal.p4modal import app as A
    be = _fake_backend()
    recs = [{"__task": "ta-1", "__boot": -30.0, "__span": [0.0, 100.0], "container_wall_s": 100.0},
            {"__task": "ta-1", "__boot": -30.0, "__span": [50.0, 150.0], "container_wall_s": 100.0},
            {"__task": "ta-2", "__boot": 10.0, "__span": [20.0, 60.0], "container_wall_s": 40.0}]
    shares = A.occupancy_shares(recs, 8)
    assert shares == pytest.approx([75.0, 75.0, 40.0])                  # the 50 s both inputs ran count half for each
    A.Backend._cost(be, recs, "iso_pack_eval", "w1")
    c = be.costs[-1]
    assert c["busy_s"] == pytest.approx(190.0) and c["startup_s"] == pytest.approx(40.0) and c["containers"] == 2
    assert c["idle_tail_s"] == pytest.approx(2 * A.SCALEDOWN_S) and c["input_wall_s"] == pytest.approx(240.0)
    assert c["container_s"] == pytest.approx(190.0 + 40.0 + 2 * A.SCALEDOWN_S)
    assert c["usd_approx"] == pytest.approx(c["container_s"] * A.usd_per_s("iso_pack_eval"), rel=1e-3)
    assert [r["__share_s"] for r in recs] == pytest.approx(shares, abs=0.01)
    # the same container in a later wave: its busy time only (its start-up and idle tail were counted once)
    A.Backend._cost(be, [{"__task": "ta-1", "__boot": -30.0, "__span": [200.0, 210.0], "container_wall_s": 10.0}], "iso_pack_eval", "w2")
    assert be.costs[-1]["startup_s"] == 0 and be.costs[-1]["idle_tail_s"] == 0 and be.costs[-1]["busy_s"] == pytest.approx(10.0)


def test_cost_records_bill_the_refused_containers():
    """A container that only refused (host gate) is billed for its start-up and its refusals (no idle tail: it stops fetching inputs
    and exits); a refusal in a container that also ran jobs adds its span to that container's busy time; refusals from containers
    without a record (older code) cannot be priced and are ignored."""
    from brainir_causal.p4modal import app as A
    be = _fake_backend()
    recs = [{"__task": "ta-ok", "__boot": 0.0, "__span": [20.0, 120.0], "container_wall_s": 100.0}]
    refused = [{"__task": "ta-bad", "__boot": 100.0, "__span": [140.0, 142.0]},     # a refused-only container: 40 s start-up + 2 s
               {"__task": "ta-bad", "__boot": 100.0, "__span": [140.0, 143.0]},     # its other slot's refusal, at the same time
               {"__task": "ta-ok", "__boot": 0.0, "__span": [10.0, 11.0]},          # refused before the job started in the same container
               {"__task": None, "__span": None}]                                    # an older container's refusal: no record
    A.Backend._cost(be, recs, "iso_pack_fit", "w", refused=refused)
    c = be.costs[-1]
    assert c["refusals"] == 3 and c["refused_only_containers"] == 1 and c["refused_only_s"] == pytest.approx(3.0)
    assert c["busy_s"] == pytest.approx(101.0) and c["startup_s"] == pytest.approx(10.0 + 40.0) and c["idle_tail_s"] == A.SCALEDOWN_S
    assert c["container_s"] == pytest.approx(101.0 + 3.0 + 50.0 + A.SCALEDOWN_S)
    assert recs[0]["__share_s"] == pytest.approx(100.0)                             # per-job shares cover the jobs' own spans only


def test_remote_commits_exactly_the_staged_volumes(monkeypatch):
    calls = {"reload": [], "commit": []}
    monkeypatch.setattr(R, "_reload", lambda v: calls["reload"].append(v))
    monkeypatch.setattr(R, "_commit", lambda v: calls["commit"].append(v))
    # packed: the slot's result says it staged to eval and store -> exactly those are committed, nothing else, no per-input reload
    monkeypatch.setattr("brainir_causal.isolation.run_iso_packed", lambda p, slots, reload_once=None: {"staged": ["eval", "store"]})
    R.run_iso({"__slots": 8, "role": "eval", "reload": ["fit", "eval", "store"], "job": {}})
    assert sorted(calls["commit"]) == ["eval", "store"] and calls["reload"] == []
    # unpacked: its reloads, then the staged volume committed once (no duplicate when the payload asked for it too)
    calls["commit"].clear()
    monkeypatch.setattr("brainir_causal.isolation.run_iso_payload", lambda p: {"staged": ["store"]})
    R.run_iso({"role": "fit", "reload": ["fit"], "commit": ["store"], "job": {}})
    assert calls["commit"] == ["store"] and calls["reload"] == ["fit"]
    assert R._staged_vols({"staged": ["eval", "evil"]}) == ["eval"]


# ---------------------------------------------------------------- driver thread pin (P1 dry run: packed != unpacked before it)
def test_job_threads_come_from_the_job_never_the_container():
    assert I.job_threads({"job": {"threads": 3}, "threads": 7}) == 3
    assert I.job_threads({"job": {}, "threads": 5}) == 5
    assert I.job_threads({"job": {"threads": 0}}) == 2
    assert I.job_threads({}) == 2


def test_pinned_threads_limits_blas_inside_and_restores_after(monkeypatch):
    threadpoolctl = pytest.importorskip("threadpoolctl")
    import numpy as np
    np.dot(np.ones((4, 4)), np.ones((4, 4)))                 # numpy's BLAS is loaded
    for k in I.THREAD_VARS:
        monkeypatch.delenv(k, raising=False)
    before = {d["filepath"]: d["num_threads"] for d in threadpoolctl.threadpool_info() if d.get("user_api") == "blas"}
    with I.pinned_threads(1) as n:
        assert n == 1
        assert all(I.os.environ[k] == "1" for k in I.THREAD_VARS)
        inside = [d["num_threads"] for d in threadpoolctl.threadpool_info() if d.get("user_api") == "blas"]
        assert inside and all(t == 1 for t in inside)
    assert all(k not in I.os.environ for k in I.THREAD_VARS)
    after = {d["filepath"]: d["num_threads"] for d in threadpoolctl.threadpool_info() if d.get("user_api") == "blas"}
    assert all(after[f] == t for f, t in before.items() if f in after)


def test_run_iso_payload_runs_the_driver_pinned_to_the_job_threads(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(I, "container_lockdown", lambda **k: {})
    monkeypatch.setattr(I, "ensure_pubdir", lambda d: {"n_files": 0})
    monkeypatch.setattr(I, "JOBS_ROOT", str(tmp_path))
    monkeypatch.setattr(I, "kill_uids", lambda own=None: None)
    monkeypatch.setattr(I, "ipc_cleanup", lambda own=None: None)

    def fake_fit(job, tr):
        seen["env"] = I.os.environ.get("OPENBLAS_NUM_THREADS")
        return {"model": b"m", "side": {}}
    monkeypatch.setattr(I, "fit_job", fake_fit)
    out = I.run_iso_payload({"role": "fit", "job": {"threads": 3}, "stage_threshold": 1 << 20})
    assert seen["env"] == "3" and out["iso"]["driver_threads"] == 3


# ---------------------------------------------------------------- packed cost accounting
def test_packed_cost_is_the_union_of_each_containers_input_spans():
    from brainir_causal.p4modal import app as A
    recs = [{"__task": "ta-1", "__span": [0.0, 100.0], "container_wall_s": 100.0},
            {"__task": "ta-1", "__span": [10.0, 60.0], "container_wall_s": 50.0},      # inside the first: not counted twice
            {"__task": "ta-1", "__span": [150.0, 170.0], "container_wall_s": 20.0},    # after a gap
            {"__task": "ta-2", "__span": [5.0, 45.0], "container_wall_s": 40.0},
            {"container_wall_s": 80.0}]                                              # no span (older container): wall / slots
    s, n = A.packed_span_s(recs, 8)
    assert n == 2 and s == pytest.approx(100.0 + 20.0 + 40.0 + 80.0 / 8)
